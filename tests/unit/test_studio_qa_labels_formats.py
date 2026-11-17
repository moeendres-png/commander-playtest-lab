"""Guards for the 2026-11-17 acceptance fixes B3-B5 (#1464): simulator readiness
codes are shown as plain German labels (never raw NO_CARD_FACTS & co.), measured
spans and weights go through the de-DE number helpers (comma, not point), and the
pool load failure uses germanError() instead of the raw server text."""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_sim_status_label_map_lives_in_ui_js() -> None:
    ui = _read("ui.js")
    assert "simStatusLabel" in ui
    for code, label in (
        ("OK", "bereit"),
        ("NO_CARD_FACTS", "keine Simulator-Kartendaten"),
        ("KNOWN_MISSING_IN_XMAGE", "Engine kennt die Karte nicht"),
        ("NO_PILOT_KNOWLEDGE", "Piloten kennen die Karte nicht"),
    ):
        assert f'{code}: "{label}"' in ui, code
    assert "numFlex" in ui  # flexible de-DE format for spans/weights


def test_no_raw_sim_status_rendering_left() -> None:
    app = _read("app.js")
    assert "Status ${card.sim_status}" not in app
    assert "Simulator: ${card.sim_status" not in app
    assert 'h("b", {}, card.sim_status)' not in app
    assert 'key === "sim_status"' in app  # pool table column goes through the label
    overview = _read("overview.js")
    assert "(${c.sim_status})" not in overview
    assert "simStatusLabel" in overview
    paired = _read("paired.js")
    assert 'item.sim_status || "UNKNOWN"' not in paired
    assert "simStatusLabel" in paired


def test_spans_and_diff_average_use_german_formats() -> None:
    app = _read("app.js")
    assert "${entry.median} (${entry.p25} bis ${entry.p75})" not in app
    assert "StudioUI.numFlex(entry.median)" in app
    assert "bs.mana_value ?? " not in app
    assert "StudioUI.num(bs.mana_value, 2)" in app
    assert "c.weight)," not in app  # strength component weight is formatted, not raw


def test_pool_load_failure_uses_german_error() -> None:
    app = _read("app.js")
    assert '"Das Studio konnte die Daten nicht laden: " + error.message' not in app
    assert '"Das Studio konnte die Daten nicht laden: " + StudioUI.germanError(error)' in app


def test_tier_unknown_cell_shows_german_reason() -> None:
    tier = _read("tierliste.js")
    assert 'h("span", { class: "rule reason-code" }, code)' not in tier
    assert 'h("span", { class: "rule reason-code" }, REASON_SHORT[code] || code)' in tier
