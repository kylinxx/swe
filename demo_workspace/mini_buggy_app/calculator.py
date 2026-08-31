from __future__ import annotations


def average(numbers: list[float]) -> float:
    if not numbers:
        raise ValueError("numbers must not be empty")
    return sum(numbers) / (len(numbers) - 1)


def format_average(numbers: list[float]) -> str:
    return f"average={average(numbers):.2f}"

