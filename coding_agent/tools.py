from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from .memory import clip_text


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
        raise WorkspaceAccessError(f"路径超出工作区范围：{candidate}") from exc
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
        suffix = f"\n[内容已截断，原始共 {len(lines)} 行]"
    return "\n".join(numbered) + suffix


def _build_diff_preview(path: Path, before: str, after: str, max_lines: int = 120) -> str:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{path.name}",
        tofile=f"b/{path.name}",
        lineterm="",
    )
    return clip_text("\n".join(diff), max_lines * 120)


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

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取工作区内的文件，可指定起始行和最大行数。",
                    "parameters": {
                        "type": "object",
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
                    "description": "写入工作区内的文件，必要时自动创建父目录。",
                    "parameters": {
                        "type": "object",
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
                    "description": "列出工作区内目录内容。",
                    "parameters": {
                        "type": "object",
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
                    "description": "在工作区内按关键词搜索文件内容，返回匹配文件与上下文片段。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "path": {"type": "string", "default": "."},
                            "recursive": {"type": "boolean", "default": True},
                            "case_sensitive": {"type": "boolean", "default": False},
                            "max_results": {"type": "integer", "minimum": 1, "default": 20},
                            "context_lines": {"type": "integer", "minimum": 0, "default": 2},
                            "glob_pattern": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "replace_text",
                    "description": "在文件中执行精确文本替换，并返回补丁预览。",
                    "parameters": {
                        "type": "object",
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
                    "description": "在工作区内执行命令并返回 stdout、stderr 和退出码。",
                    "parameters": {
                        "type": "object",
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

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._handlers:
            return ToolResult(False, f"未知工具：{name}", {"tool": name})
        return self._handlers[name](arguments)

    def read_file(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments["path"])
        start_line = int(arguments.get("start_line", 1))
        max_lines = int(arguments.get("max_lines", 200))
        if not path.exists():
            return ToolResult(False, f"文件不存在：{path}", {"path": str(path)})

        text = path.read_text(encoding="utf-8", errors="replace")
        formatted = _format_lines(text, start_line=start_line, max_lines=max_lines)
        if not formatted:
            formatted = "[文件为空]"
        return ToolResult(
            True,
            f"Path: {path.relative_to(self.workspace_root)}\n{formatted}",
            {"path": str(path), "start_line": start_line, "max_lines": max_lines},
        )

    def write_file(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments["path"])
        content = str(arguments["content"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(
            True,
            f"已写入文件：{path.relative_to(self.workspace_root)}（{len(content)} 字符）",
            {"path": str(path), "bytes": len(content.encode("utf-8"))},
        )

    def list_directory(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments.get("path", "."))
        recursive = bool(arguments.get("recursive", False))
        max_entries = int(arguments.get("max_entries", 200))
        if not path.exists():
            return ToolResult(False, f"目录不存在：{path}", {"path": str(path)})

        entries: list[str] = []
        if recursive:
            iterator = path.rglob("*")
        else:
            iterator = path.iterdir()

        for index, entry in enumerate(sorted(iterator, key=lambda item: str(item))):
            if index >= max_entries:
                entries.append(f"[已截断，最多显示 {max_entries} 项]")
                break
            relative = entry.relative_to(self.workspace_root)
            marker = "/" if entry.is_dir() else ""
            entries.append(str(relative) + marker)

        content = "\n".join(entries) if entries else "[空目录]"
        return ToolResult(True, content, {"path": str(path), "recursive": recursive, "max_entries": max_entries})

    def search_text(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"])
        path = _resolve_within_workspace(self.workspace_root, arguments.get("path", "."))
        recursive = bool(arguments.get("recursive", True))
        case_sensitive = bool(arguments.get("case_sensitive", False))
        max_results = int(arguments.get("max_results", 20))
        context_lines = int(arguments.get("context_lines", 2))
        glob_pattern = str(arguments.get("glob_pattern") or "*")

        if not path.exists():
            return ToolResult(False, f"目录不存在：{path}", {"path": str(path)})

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
                snippet_lines = [
                    f"{line_no + 1:04d} | {lines[line_no]}"
                    for line_no in range(start, end)
                ]
                snippets.append(
                    f"Path: {candidate.relative_to(self.workspace_root)}\n" + "\n".join(snippet_lines)
                )
                if len(snippets) >= max_results:
                    break

        if not snippets:
            return ToolResult(
                True,
                f"未找到匹配项：{query}\n已扫描文件数：{scanned_files}",
                {"query": query, "scanned_files": scanned_files, "matches": 0},
            )

        content = f"Query: {query}\n已扫描文件数：{scanned_files}\n\n" + "\n\n---\n\n".join(snippets)
        return ToolResult(
            True,
            clip_text(content, 16000),
            {"query": query, "scanned_files": scanned_files, "matches": len(snippets)},
        )

    def replace_text(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_within_workspace(self.workspace_root, arguments["path"])
        old_text = str(arguments["old_text"])
        new_text = str(arguments["new_text"])
        count = int(arguments.get("count", 1))
        if not path.exists():
            return ToolResult(False, f"文件不存在：{path}", {"path": str(path)})

        before = path.read_text(encoding="utf-8", errors="replace")
        occurrences = before.count(old_text)
        if occurrences == 0:
            return ToolResult(
                False,
                f"文件中未找到要替换的文本：{path.relative_to(self.workspace_root)}",
                {"path": str(path), "replacements": 0},
            )

        after = before.replace(old_text, new_text, count)
        path.write_text(after, encoding="utf-8")
        preview = _build_diff_preview(path, before, after)
        return ToolResult(
            True,
            (
                f"已更新文件：{path.relative_to(self.workspace_root)}\n"
                f"匹配次数：{occurrences}\n"
                f"实际替换：{min(occurrences, count)}\n"
                f"Diff 预览：\n{preview}"
            ),
            {
                "path": str(path),
                "matched": occurrences,
                "replaced": min(occurrences, count),
                "preview_lines": preview.count("\n") + 1 if preview else 0,
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
                f"Stdout:\n{stdout or '[无输出]'}\n"
                f"Stderr:\n{stderr or '[无输出]'}"
            )
            return ToolResult(
                completed.returncode == 0,
                content,
                {"command": command, "cwd": str(cwd), "returncode": completed.returncode, "duration_seconds": duration},
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
                f"Stdout:\n{stdout or '[无输出]'}\n"
                f"Stderr:\n{stderr or '[无输出]'}"
            )
            return ToolResult(False, content, {"command": command, "cwd": str(cwd), "timeout_seconds": timeout_seconds})
