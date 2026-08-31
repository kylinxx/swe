from __future__ import annotations


def completed_titles(items: list[dict[str, object]]) -> list[str]:
    return [str(item["title"]) for item in items if not item.get("done", False)]
