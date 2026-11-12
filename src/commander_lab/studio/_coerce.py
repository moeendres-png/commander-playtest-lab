"""Small narrowing helpers for untyped JSON-shaped values (no ``Any`` in signatures)."""

from __future__ import annotations

from collections.abc import Iterable


def to_int(value: object) -> int:
    """``int(value)`` for the types ``int`` accepts; anything else is a TypeError."""
    if isinstance(value, (int, float, str, bytes)):
        return int(value)
    raise TypeError(
        f"int() argument must be a string or a real number, not {type(value).__name__!r}"
    )


def to_float(value: object) -> float:
    """``float(value)`` for the types ``float`` accepts; anything else is a TypeError."""
    if isinstance(value, (int, float, str, bytes)):
        return float(value)
    raise TypeError(
        f"float() argument must be a string or a real number, not {type(value).__name__!r}"
    )


def iterate(value: object) -> Iterable[object]:
    """Iterate ``value``; a non-iterable raises TypeError like a plain ``for`` loop."""
    if isinstance(value, Iterable):
        return value
    raise TypeError(f"{type(value).__name__!r} object is not iterable")
