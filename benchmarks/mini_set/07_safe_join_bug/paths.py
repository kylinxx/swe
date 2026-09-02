from __future__ import annotations

from pathlib import Path


def safe_join(base: str | Path, relative_path: str | Path) -> Path:
    base_path = Path(base).resolve()
    return base_path / relative_path
