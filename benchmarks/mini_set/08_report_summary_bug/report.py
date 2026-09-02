from __future__ import annotations


def build_summary(results: list[dict[str, object]]) -> dict[str, object]:
    passed_names = [str(item["name"]) for item in results if not item.get("passed", False)]
    failed_names = [str(item["name"]) for item in results if item.get("passed", False)]
    success_rate = len(passed_names) / (len(results) + 1) if results else 0
    return {
        "passed": passed_names,
        "failed": failed_names,
        "success_rate": success_rate,
    }
