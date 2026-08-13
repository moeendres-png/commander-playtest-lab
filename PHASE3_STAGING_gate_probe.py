from __future__ import annotations

from collections import Counter


def validate_counts(mainboard: tuple[str, ...]) -> tuple[int, dict[str, int]]:
    return len(mainboard), dict(Counter(mainboard))
