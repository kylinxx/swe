from __future__ import annotations


def count_words(text: str) -> int:
    if not text.strip():
        return 0
    return len([part for part in text.split(" ") if part])
