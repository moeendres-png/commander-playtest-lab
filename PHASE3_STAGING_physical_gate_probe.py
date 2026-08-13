from __future__ import annotations


def physical_issue(name: str, quantity: int, available: int) -> str | None:
    if quantity > available:
        return f"physical_inventory:{name}:{quantity}>{available}"
    return None
