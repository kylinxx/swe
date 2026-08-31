from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
import json
import re
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunArtifacts:
    run_dir: Path
    json_path: Path
    markdown_path: Path


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    return cleaned[:40] or "session"


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return asdict(value)
    return str(value)


class ArtifactWriter:
    def __init__(self, workspace_root: Path, report_dir: str | Path = ".coding-agent/runs") -> None:
        self.workspace_root = workspace_root.expanduser().resolve()
        self.report_dir = self.workspace_root / Path(report_dir)

    def create_run_dir(self, task: str) -> RunArtifacts:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = _slugify(task)
        run_dir = self.report_dir / f"{timestamp}-{slug}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return RunArtifacts(run_dir=run_dir, json_path=run_dir / "run.json", markdown_path=run_dir / "run.md")

    def write_report(
        self,
        *,
        task: str,
        plan: Any,
        final_answer: str,
        steps: int,
        history: list[dict[str, Any]],
        tool_events: list[dict[str, Any]],
        event_log: list[dict[str, Any]] | None = None,
        status: str = "success",
        error: str | None = None,
    ) -> RunArtifacts:
        artifacts = self.create_run_dir(task)
        payload = {
            "task": task,
            "final_answer": final_answer,
            "steps": steps,
            "plan": plan,
            "history": history,
            "tool_events": tool_events,
            "event_log": event_log or [],
            "status": status,
            "error": error,
        }
        artifacts.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        artifacts.markdown_path.write_text(
            self._render_markdown(
                task,
                plan,
                final_answer,
                steps,
                history,
                tool_events,
                event_log or [],
                status=status,
                error=error,
            ),
            encoding="utf-8",
        )
        return artifacts

    def _render_markdown(
        self,
        task: str,
        plan: Any,
        final_answer: str,
        steps: int,
        history: list[dict[str, Any]],
        tool_events: list[dict[str, Any]],
        event_log: list[dict[str, Any]],
        status: str,
        error: str | None,
    ) -> str:
        lines: list[str] = [
            "# Coding Agent Run Report",
            "",
            f"- Status: {status}",
            f"- Task: {task}",
            f"- Steps: {steps}",
            f"- History messages: {len(history)}",
            f"- Tool events: {len(tool_events)}",
            "",
            "## Final Answer",
            "",
            final_answer or "[empty]",
            "",
        ]
        if error:
            lines.extend(["## Error", "", error, ""])
        if plan:
            lines.extend(
                [
                    "## Plan",
                    "",
                    f"- Goal: {getattr(plan, 'goal', '')}",
                    f"- Summary: {getattr(plan, 'summary', '')}",
                ]
            )
            notes = getattr(plan, "notes", []) or []
            steps_list = getattr(plan, "steps", []) or []
            if notes:
                lines.append("- Notes:")
                for note in notes:
                    lines.append(f"  - {note}")
            if steps_list:
                lines.append("- Steps:")
                for step in steps_list:
                    lines.append(f"  - {getattr(step, 'id', '?')}. {getattr(step, 'task', '')} — {getattr(step, 'reason', '')}")
            lines.append("")
        if tool_events:
            lines.extend(["## Tool Trace", ""])
            for event in tool_events:
                status = "OK" if event.get("success") else "FAIL"
                lines.append(f"- [{status}] {event.get('name')} -> {event.get('summary')}")
            lines.append("")
        if event_log:
            lines.extend(["## Event Log", ""])
            for event in event_log:
                lines.append(f"- {event.get('name')}: {json.dumps(event.get('data', {}), ensure_ascii=False, default=_json_default)}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"
