"""Guard tests for Tierliste E0 (#1481 UI completion + 17Lands cast-turn context)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def test_tierliste_e0_stability_relative_tier_and_cast_turn_ui_wiring() -> None:
    html = (STATIC_DIR / "tierliste.html").read_text(encoding="utf-8")
    js = (STATIC_DIR / "tierliste.js").read_text(encoding="utf-8")
    css = (STATIC_DIR / "tierliste.css").read_text(encoding="utf-8")

    # Relative tier toggle (S-F)
    assert 'id="tier-mode-toggle"' in html
    assert 'data-tier-mode="absolute"' in html
    assert 'data-tier-mode="relative"' in html
    assert "TIER_MODE_KEY" in js
    assert "item.relative_tier" in js

    # Stability / unscharf & tier_alternatives
    assert "function unsharpMark(item)" in js
    assert "item.tier_stability" in js
    assert "item.tier_alternatives" in js
    assert "result.stability.unscharf_count" in js
    assert ".unsharp" in css
    assert ".tier-badge.t-E" in css
    assert ".tier-badge.t-F" in css

    # Weight families summary
    assert "weight-families-line" in js
    assert "result.weight_families" in js

    # 17Lands survival-bias cast-turn context in gameCell
    assert "atlas.median_cast_turn" in js
    assert "Survival-Verzerrung" in js
