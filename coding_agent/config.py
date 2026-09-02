from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


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


@dataclass(frozen=True)
class LLMRuntimeConfig:
    provider: str
    api_key: str
    base_url: str
    model: str


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def infer_model_provider() -> str:
    provider = os.getenv("MODEL_PROVIDER", "").strip().lower()
    if provider in {"openai", "deepseek"}:
        return provider

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key and not openai_key:
        return "deepseek"
    return "openai"


def default_llm_settings(provider: str | None = None) -> tuple[str, str]:
    resolved_provider = (provider or infer_model_provider()).strip().lower()
    if resolved_provider == "deepseek":
        return (
            os.getenv("DEEPSEEK_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")).strip(),
            os.getenv("DEEPSEEK_MODEL", os.getenv("OPENAI_MODEL", "deepseek-v4-flash")).strip(),
        )
    return (
        os.getenv("OPENAI_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.openai.com/v1")).strip(),
        os.getenv("OPENAI_MODEL", os.getenv("DEEPSEEK_MODEL", "gpt-4.1-mini")).strip(),
    )


def resolve_llm_runtime_config() -> LLMRuntimeConfig:
    provider = infer_model_provider()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

    if provider == "deepseek":
        api_key = deepseek_key or openai_key
    else:
        api_key = openai_key or deepseek_key

    if not api_key:
        raise ValueError("缺少环境变量 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`。")

    base_url, model = default_llm_settings(provider)
    return LLMRuntimeConfig(
        provider=provider,
        api_key=api_key,
        base_url=normalize_base_url(base_url),
        model=model,
    )


def resolve_workspace_root(workspace_root: str | Path | None) -> Path:
    if workspace_root is None:
        return Path.cwd().resolve()
    return Path(workspace_root).expanduser().resolve()
