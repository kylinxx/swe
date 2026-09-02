from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from .memory import clip_text
from .validation import SchemaValidationError, validate_json_schema


@dataclass
class ToolResult:
    success: bool
    content: str
    metadata: dict[str, Any]


class WorkspaceAccessError(RuntimeError):
    pass


def _normalize_root(workspace_root: Path) -> Path:
    return workspace_root.expanduser().resolve()


def _resolve_within_workspace(workspace_root: Path, candidate: str | Path) -> Path:
    root = _normalize_root(workspace_root)
    path = Path(candidate)
    resolved = path if path.is_absolute() else root / path
    resolved = resolved.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkspaceAccessError(f"Path escapes workspace: {candidate}") from exc
    return resolved


def _format_lines(text: str, start_line: int, max_lines: int) -> str:
    lines = text.splitlines()
    if not lines:
        return ""

    start_index = max(0, start_line - 1)
    end_index = min(len(lines), start_index + max_lines)
    selected = lines[start_index:end_index]
    numbered = [f"{start_index + index + 1:04d} | {line}" for index, line in enumerate(selected)]
    suffix = ""
    if end_index < len(lines):
        suffix = f"\n[truncated, original has {len(lines)} lines]"
    return "\n".join(numbered) + suffix


def _is_probably_text_file(path: Path) -> bool:
    text_extensions = {
        ".py",
        ".txt",
        ".md",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".csv",
        ".ts",
        ".js",
        ".jsx",
        ".tsv",
        ".html",
        ".css",
        ".ini",
        ".cfg",
        ".sh",
        ".ps1",
    }
    return path.suffix.lower() in text_extensions or path.name in {"Makefile", "Dockerfile"}


def _render_diff_preview(path: Path, before: str, after: str, *, context_lines: int = 3, max_lines: int = 160) -> str:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    groups = list(matcher.get_grouped_opcodes(n=context_lines))
    if not groups:
        return "[no textual changes]"

    preview_lines: list[str] = [f"Diff for {path.name}", f"Changed hunks: {len(groups)}"]
    emitted_lines = len(preview_lines)

    for hunk_index, group in enumerate(groups, start=1):
        first = group[0]
        last = group[-1]
        before_start = first[1] + 1
        after_start = first[3] + 1
        before_count = max(0, last[2] - first[1])
        after_count = max(0, last[4] - first[3])
        hunk_lines = [f"@@ Hunk {hunk_index}: -{before_start},{before_count} +{after_start},{after_count} @@"]

        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for offset in range(i2 - i1):
                    line_no = i1 + offset + 1
                    hunk_lines.append(f" {line_no:04d} | {before_lines[i1 + offset]}")
            elif tag == "delete":
                for offset in range(i1, i2):
                    hunk_lines.append(f"-{offset + 1:04d} | {before_lines[offset]}")
            elif tag == "insert":
                for offset in range(j1, j2):
                    hunk_lines.append(f"+{offset + 1:04d} | {after_lines[offset]}")
            elif tag == "replace":
                left_len = i2 - i1
                right_len = j2 - j1
                paired = max(left_len, right_len)
                for offset in range(paired):
                    if offset < left_len:
                        hunk_lines.append(f"-{i1 + offset + 1:04d} | {before_lines[i1 + offset]}")
                    if offset < right_len:
                        hunk_lines.append(f"+{j1 + offset + 1:04d} | {after_lines[j1 + offset]}")

        hunk_lines.append("")
        if emitted_lines + len(hunk_lines) > max_lines:
            preview_lines.append("[diff preview truncated]")
            break

        preview_lines.extend(hunk_lines)
        emitted_lines += len(hunk_lines)

    return "\n".join(preview_lines).strip()


class WorkspaceToolbox:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = _normalize_root(workspace_root)
        self._handlers: dict[str, Callable[[dict[str, Any]], ToolResult]] = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "list_directory": self.list_directory,
            "search_text": self.search_text,
            "replace_text": self.replace_text,
            "execute_command": self.execute_command,
        }
        self._schema_map = {
            schema["function"]["name"]: schema["function"]["parameters"]
            for schema in self.tool_schemas()
        }

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file within the workspace and return numbered lines.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer", "minimum": 1, "default": 1},
                            "max_lines": {"type": "integer", "minimum": 1, "default": 200},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write a file within the workspace and create parent folders if needed.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and folders within the workspace.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "path": {"type": "string", "default": "."},
                            "recursive": {"type": "boolean", "default": False},
                            "max_entries": {"type": "integer", "minimum": 1, "default": 200},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "description": "Search text in workspace files and return matching snippets.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "query": {"type": "string"},
                            "path": {"type": "string", "default": "."},
                            "recursive": {"type": "boolean", "default": True},
                            "case_sensitive": {"type": "boolean", "default": False},
                            "max_results": {"type": "integer", "minimum": 1, "default": 20},
                            "context_lines": {"type": "integer", "minimum": 0, "default": 2},
                            "glob_pattern": {"type": "string", "default": "*"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "replace_text",
                    "description": "Replace exact text in a file and return a detailed diff preview.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "path": {"type": "string"},
                            "old_text": {"type": "string"},
                            "new_text": {"type": "string"},
                            "count": {"type": "integer", "minimum": 1, "default": 1},
                        },
                        "required": ["path", "old_text", "new_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Execute a shell command inside the workspace and return stdout, stderr, and exit code.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {"type": "string", "default": "."},
                            "timeout_seconds": {"type": "integer", "minimum": 1, "default": 60},
                        },
                        "required": ["command"],
                    },
                },
            },
        ]

    def _schema_for(self, name: str) -> dict[str, Any] | None:
        return self._schema_map.get(name)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._handlers:
            return ToolResult(False, f"Unknown tool: {name}", {"tool": name, "error_type": "UnknownTool", "retryable": False})

        schema = self._schema_for(name)
        if schema is None:
            return ToolResult(False, f"Missing schema for tool: {name}", {"tool": name, "error_type": "MissingSchema", "retryable": False})

        try:
            normalized_arguments = validate_json_schema(arguments, schema, path=name)
        except SchemaValidationError as exc:
            return ToolResult(
                False,
                f"工具参数校验失败：{exc}",
                {"tool": name, "error_type": "SchemaValidationError", "retryable": False},
            )

        try:
            result = self._handlers[name](normalized_arguments)
        except WorkspaceAccessError as exc:
            return ToolResult(False, str(exc), {"tool": name, "error_type": type(exc).__name__, "retryable": False})
        except OSError as exc:
            return ToolResult(False, f"Filesystem error: {exc}", {"tool": name, "error_type": type(exc).__name__, "retryable": True})
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(False, f"工具参数错误：{exc}", {"tool": name, "error_type": type(exc).__name__, "retryable": False})
        except Exception as exc:  # pragma: no cover - unexpected guard rail
            return ToolResult(False, f"工具执行异常：{exc}", {"tool": name, "error_type": type(exc).__name__, "retryable": False})

        if not isinstance(result, ToolResult):
            return ToolResult(False, "Tool returned an invalid result object", {"tool": name, "error_type": "InvalidReturn", "retryable": False})
        return result

    def read_file(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments["path"])
        start_line = int(arguments.get("start_line", 1))
        max_lines = int(arguments.get("max_lines", 200))
        if not path.exists():
            return ToolResult(False, f"File not found: {path}", {"path": str(path), "retryable": False})

        text = path.read_text(encoding="utf-8", errors="replace")
        formatted = _format_lines(text, start_line=start_line, max_lines=max_lines)
        if not formatted:
            formatted = "[empty file]"
        return ToolResult(
            True,
            f"Path: {path.relative_to(self.workspace_root)}\n{formatted}",
            {"path": str(path), "start_line": start_line, "max_lines": max_lines, "retryable": False},
        )

    def write_file(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments["path"])
        content = str(arguments["content"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(
            True,
            f"Wrote file: {path.relative_to(self.workspace_root)} ({len(content)} characters)",
            {"path": str(path), "bytes": len(content.encode("utf-8")), "retryable": False},
        )

    def list_directory(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments.get("path", "."))
        recursive = bool(arguments.get("recursive", False))
        max_entries = int(arguments.get("max_entries", 200))
        if not path.exists():
            return ToolResult(False, f"Directory not found: {path}", {"path": str(path), "retryable": False})

        entries: list[str] = []
        iterator = path.rglob("*") if recursive else path.iterdir()
        for index, entry in enumerate(sorted(iterator, key=lambda item: str(item))):
            if index >= max_entries:
                entries.append(f"[truncated, max {max_entries} entries]")
                break
            relative = entry.relative_to(self.workspace_root)
            marker = "/" if entry.is_dir() else ""
            entries.append(str(relative) + marker)

        content = "\n".join(entries) if entries else "[empty directory]"
        return ToolResult(
            True,
            content,
            {"path": str(path), "recursive": recursive, "max_entries": max_entries, "retryable": False},
        )

    def search_text(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"])
        path = _resolve_within_workspace(self.workspace_root, arguments.get("path", "."))
        recursive = bool(arguments.get("recursive", True))
        case_sensitive = bool(arguments.get("case_sensitive", False))
        max_results = int(arguments.get("max_results", 20))
        context_lines = int(arguments.get("context_lines", 2))
        glob_pattern = str(arguments.get("glob_pattern") or "*")

        if not path.exists():
            return ToolResult(False, f"Directory not found: {path}", {"path": str(path), "retryable": False})

        query_cmp = query if case_sensitive else query.lower()
        snippets: list[str] = []
        scanned_files = 0

        if path.is_file():
            candidates = [path]
        else:
            iterator = path.rglob(glob_pattern) if recursive else path.glob(glob_pattern)
            candidates = sorted(iterator, key=lambda item: str(item))

        for candidate in candidates:
            if len(snippets) >= max_results:
                break
            if not candidate.is_file() or not _is_probably_text_file(candidate):
                continue

            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            scanned_files += 1
            lines = text.splitlines()
            for index, line in enumerate(lines):
                line_cmp = line if case_sensitive else line.lower()
                if query_cmp not in line_cmp:
                    continue
                start = max(0, index - context_lines)
                end = min(len(lines), index + context_lines + 1)
                snippet_lines = [f"{line_no + 1:04d} | {lines[line_no]}" for line_no in range(start, end)]
                snippets.append(f"Path: {candidate.relative_to(self.workspace_root)}\n" + "\n".join(snippet_lines))
                if len(snippets) >= max_results:
                    break

        if not snippets:
            return ToolResult(
                True,
                f"No matches for: {query}\nScanned files: {scanned_files}",
                {"query": query, "scanned_files": scanned_files, "matches": 0, "retryable": False},
            )

        content = f"Query: {query}\nScanned files: {scanned_files}\n\n" + "\n\n---\n\n".join(snippets)
        return ToolResult(
            True,
            clip_text(content, 16000),
            {"query": query, "scanned_files": scanned_files, "matches": len(snippets), "retryable": False},
        )

    def replace_text(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments["path"])
        old_text = str(arguments["old_text"])
        new_text = str(arguments["new_text"])
        count = int(arguments.get("count", 1))
        if not path.exists():
            return ToolResult(False, f"File not found: {path}", {"path": str(path), "retryable": False})

        before = path.read_text(encoding="utf-8", errors="replace")
        occurrences = before.count(old_text)
        if occurrences == 0:
            return ToolResult(
                False,
                f"Did not find the target text in {path.relative_to(self.workspace_root)}",
                {"path": str(path), "replacements": 0, "retryable": False},
            )

        after = before.replace(old_text, new_text, count)
        path.write_text(after, encoding="utf-8")
        preview = _render_diff_preview(path, before, after)
        replaced = min(occurrences, count)
        return ToolResult(
            True,
            (
                f"Updated file: {path.relative_to(self.workspace_root)}\n"
                f"Matched occurrences: {occurrences}\n"
                f"Applied replacements: {replaced}\n"
                f"Diff preview:\n{preview}"
            ),
            {
                "path": str(path),
                "matched": occurrences,
                "replaced": replaced,
                "preview_lines": preview.count("\n") + 1 if preview else 0,
                "diff_preview": preview,
                "retryable": False,
            },
        )

    def execute_command(self, arguments: dict[str, Any]) -> ToolResult:
        command = str(arguments["command"])
        cwd_value = arguments.get("cwd", ".")
        timeout_seconds = int(arguments.get("timeout_seconds", 60))
        cwd = _resolve_within_workspace(self.workspace_root, cwd_value)

        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            duration = time.monotonic() - started_at
            stdout = clip_text(completed.stdout, 12000)
            stderr = clip_text(completed.stderr, 12000)
            content = (
                f"Command: {command}\n"
                f"CWD: {cwd.relative_to(self.workspace_root)}\n"
                f"Exit code: {completed.returncode}\n"
                f"Duration: {duration:.2f}s\n"
                f"Stdout:\n{stdout or '[no stdout]'}\n"
                f"Stderr:\n{stderr or '[no stderr]'}"
            )
            return ToolResult(
                completed.returncode == 0,
                content,
                {
                    "command": command,
                    "cwd": str(cwd),
                    "returncode": completed.returncode,
                    "duration_seconds": duration,
                    "retryable": False,
                },
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started_at
            stdout = clip_text(exc.stdout or "", 12000)
            stderr = clip_text(exc.stderr or "", 12000)
            content = (
                f"Command: {command}\n"
                f"CWD: {cwd.relative_to(self.workspace_root)}\n"
                f"Exit code: timeout\n"
                f"Duration: {duration:.2f}s\n"
                f"Stdout:\n{stdout or '[no stdout]'}\n"
                f"Stderr:\n{stderr or '[no stderr]'}"
            )
            return ToolResult(
                False,
                content,
                {
                    "command": command,
                    "cwd": str(cwd),
                    "timeout_seconds": timeout_seconds,
                    "retryable": True,
                },
            )
