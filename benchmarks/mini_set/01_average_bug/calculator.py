from __future__ import annotations


def average(numbers: list[float]) -> float:
    if not numbers:
        return 0
    return sum(numbers) / (len(numbers) + 1)
