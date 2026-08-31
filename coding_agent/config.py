from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlparse, urlunparse


def load_dotenv_if_present(dotenv_path: Path | None = None) -> None:
    path = dotenv_path or Path.cwd() / ".env"
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        cleaned = value.strip().strip('"').strip("'")
        os.environ[key] = cleaned


@dataclass(frozen=True)
class AgentConfig:
    api_key: str
    model: str
    base_url: str
    workspace_root: Path
    plan_mode: bool = False
    record_runs: bool = True
    report_dir: str = ".coding-agent/runs"
    max_steps: int = 12
    max_context_tokens: int = 12000
    temperature: float = 0.2
    timeout_seconds: int = 60


def normalize_base_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return cleaned
    if parsed.path in {"", "/"}:
        parsed = parsed._replace(path="/v1")
        return urlunparse(parsed)
    return cleaned


def resolve_workspace_root(workspace_root: str | Path | None) -> Path:
    if workspace_root is None:
        return Path.cwd().resolve()
    return Path(workspace_root).expanduser().resolve()
