"""Meta-Lane PR6: a meta source is valid for 12 months from retrieved_at (expires_at_for)."""

from __future__ import annotations

from datetime import UTC, datetime

from commander_lab.models.meta import expires_at_for


def test_expires_at_for_twelve_months() -> None:
    assert expires_at_for(datetime(2026, 10, 25, tzinfo=UTC)) == datetime(2027, 10, 25, tzinfo=UTC)
    assert expires_at_for(datetime(2026, 8, 5, tzinfo=UTC)) == datetime(2027, 8, 5, tzinfo=UTC)
    # Month-end clamp: 2024-02-29 + 12 months is 2025-02-28, not 2025-02-29.
    assert expires_at_for(datetime(2024, 2, 29, tzinfo=UTC)) == datetime(2025, 2, 28, tzinfo=UTC)
