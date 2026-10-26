"""Pytest-Plugin: Wanduhr fuer (b)/(c)-Module vorschieben (Audit #1028).

Verwendung:
    CLOCK_SHIFT_TO=2028-01-01 python -m pytest tests/unit -q -p clock_plugin

Gepatcht wird nur, was eine Entscheidung speist:
- commander_lab.whole_deck.meta.datetime (Staleness, PR6)
- commander_lab.whole_deck.optimizer_v2.datetime (Lock-Alter, 12 h)
- time.time global (Orphan-Cleanup, 24 h, via mtime-Vergleich)
- upstream_delta.date (Trigger T1, Pin-Alter in Wochen)

NICHT gepatcht (bewusst): time.monotonic (Dauern/Timeouts, keine
Wanduhr), Stempel-only-Module (Provenienz, Reports, Caches — Stempel
aendern kein Testurteil), Subprocess-Skripte (refresh_meta laeuft mit
--as-of). Die Plugin-Datei liegt in ~/workspace/tmp/1028 und wird
nicht ins Repo committet; der Inhalt steht im Bericht, damit der Lauf
reproduzierbar ist.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, date, datetime

import pytest

_SHIFT = os.environ.get("CLOCK_SHIFT_TO", "")


class _ShiftedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D102 - Audit-Plugin
        base = datetime.fromisoformat(_SHIFT)
        if tz is not None:
            return base.replace(tzinfo=tz)
        return base


class _ShiftedDate(date):
    @classmethod
    def today(cls):  # noqa: D102 - Audit-Plugin
        return date.fromisoformat(_SHIFT)


def pytest_sessionstart(session):  # noqa: D103 - Audit-Plugin
    # Nur das Flag pruefen; gepatcht wird in der sessionweiten Fixture
    # (dann sind auch erst zur Collection importierte Module wie
    # upstream_delta schon in sys.modules). Modulattribute werden zur
    # Call-Zeit aufgeloest, daher wirkt der Patch auch fuer bereits
    # importierte Module.
    if not _SHIFT:
        return


def _apply_shift() -> None:
    import sys

    import commander_lab.whole_deck.meta as meta_mod
    import commander_lab.whole_deck.optimizer_v2 as opt_mod

    meta_mod.datetime = _ShiftedDatetime  # type: ignore[attr-defined]
    opt_mod.datetime = _ShiftedDatetime  # type: ignore[attr-defined]
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, "__name__", "").endswith(
            "upstream_delta"
        ):
            mod.date = _ShiftedDate  # type: ignore[attr-defined]
    shifted_epoch = datetime.fromisoformat(_SHIFT).replace(tzinfo=UTC).timestamp()
    time.time = lambda: shifted_epoch  # type: ignore[method-assign]


def pytest_sessionfinish(session):  # noqa: D103 - Audit-Plugin
    pass


# Die Fixture wird von pytest ueber den -p-Mechanismus registriert.
@pytest.fixture(scope="session", autouse=True)
def _shift_clock_for_audit():  # noqa: D103 - Audit-Plugin
    if _SHIFT:
        _apply_shift()
    yield
