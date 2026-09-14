#!/usr/bin/env python3
"""WS213 deck/prefs authority.

Deck tables: WS207-corrected ``build_decks`` reused verbatim by import (sealed
WS207 package is never mutated; only the cosmetic ``ws207-`` deck tag prefix
is re-tagged ``ws213-`` with deck_hash kept consistent). Card multisets are
therefore byte-identical to the WS207 setup authority.

Behavior prefs: WS205 ``build_prefs`` reused verbatim by import, plus WS213
interrogation extras (G04 concede schedule). Setup prefs: WS207
``build_setup_prefs`` reused verbatim by import.

Seeds: WS207 SEED_CATALOG explicit Rules seeds for qualified constructions;
WS205 neutral seeds elsewhere. The production session binds every seed
natively (no reflective hook anywhere in WS213).
"""

from __future__ import annotations

import sys
from pathlib import Path

WS213_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WS213_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT / "qualification/ws205-xmage-ws90-first-wave"))
sys.path.insert(0, str(REPO_ROOT / "qualification/ws207-xmage-qualified-scenario-setup"))

import ws205_driver as _W205  # noqa: E402
import ws207_decks as _W207  # noqa: E402

ENGINE_PIN = "db134b9737e951367d65ef5806ad986319cc73ab"
POLICY_VERSION = "ws213-pilot-v1"
BUDGET = 500

# WS207 qualified explicit Rules seeds (SEED_CATALOG.json, dual-fixed).
CATALOG_SEEDS = {
    "RQ-C3-A03": 9788,
    "RQ-C3-C01": 10704,
    "RQ-C3-C03": 11412,
    "RQ-C3-D06": 11912,
    "RQ-C3-F01": 13405,
    "RQ-C3-H01-CLONE_FIRST": 16238,
    "RQ-C3-H01-NO_HUMILITY": 16859,
    "RQ-C3-H01-HUMILITY_FIRST": 15258,
}

# WS205 neutral seeds for constructions without a WS207 qualified seed.
# SLOT_ORDER index: A03 0, A04 1, B01 2, C01 3, C03 4, D06 5, E01 6, E02 7,
# F01 8, G02 9, G03 10, G04 11, H01 12, I01 13, J02 14.
WS205_SEEDS = {
    "RQ-C3-B01": 9103,
    "RQ-C3-E02": 9108,
    "RQ-C3-G04": 9112,
    "RQ-C3-I01": 9114,
}

SEEDS = dict(CATALOG_SEEDS)
SEEDS.update(WS205_SEEDS)

SETUPS = {
    "RQ-C3-A03": "NATURAL_GAME_START",
    "RQ-C3-B01": "NATURAL_GAME_START",
    "RQ-C3-C01": "NATURAL_GAME_START",
    "RQ-C3-C03": "NATURAL_GAME_START",
    "RQ-C3-D06": "NATURAL_GAME_START",
    "RQ-C3-E02": "PRE_STEP_NATIVE_PROGRESSION",
    "RQ-C3-F01": "NATURAL_GAME_START",
    "RQ-C3-G04": "NATURAL_GAME_START",
    "RQ-C3-H01": "NATURAL_GAME_START",
    "RQ-C3-I01": "NATURAL_GAME_START",
}

# WS213 constructions: affected available scenarios plus the WS205
# determinism-matrix inputs (previously false twins B01/E02/I01/HUMILITY_FIRST
# and the qualified rest). A04/E01/G02/G03/J02 remain unattempted: no qualified
# setup and no pin-removed blocker (recorded, not chased).
CONSTRUCTIONS = [
    ("RQ-C3-A03", ""),
    ("RQ-C3-B01", ""),
    ("RQ-C3-C01", ""),
    ("RQ-C3-C03", ""),
    ("RQ-C3-D06", ""),
    ("RQ-C3-E02", ""),
    ("RQ-C3-F01", ""),
    ("RQ-C3-G04", ""),
    ("RQ-C3-H01", "HUMILITY_FIRST"),
    ("RQ-C3-H01", "CLONE_FIRST"),
    ("RQ-C3-H01", "NO_HUMILITY"),
    ("RQ-C3-I01", ""),
]

PACK_AUTHORITY = (
    "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json blob 5852965e59412399a947c626d4f7d428be8ef337"
)


def seed_key(slot: str, subcase: str) -> str:
    return slot if not subcase else f"{slot}-{subcase}"


def build_decks(slot: str, subcase: str = "") -> dict:
    """WS207-corrected deck tables, re-tagged ws213- (hash kept consistent)."""
    decks = _W207.build_decks(slot, subcase)
    out = {}
    for seat, spec in decks.items():
        deck_id = spec["deck_id"].replace("ws207-", "ws213-", 1)
        out[seat] = {
            "deck_id": deck_id,
            "deck_hash": deck_id,
            "mainboard": list(spec["mainboard"]),
            "commanders": list(spec["commanders"]),
        }
    problems = _W207.check_singleton_legal(out)
    if problems:
        raise ValueError(f"singleton violations for {slot}: {problems}")
    return out


def build_behavior_prefs(slot: str, subcase: str = "") -> dict:
    """WS205 behavior prefs verbatim, plus WS213 interrogation extras."""
    prefs = _W205.build_prefs(slot, subcase)
    if slot == "RQ-C3-G04":
        # Concede interrogation: after 60 answered decisions, offer and submit
        # a native concession for seat 3 (keeps scenario seats 0-2 intact),
        # then play continues to budget. Availability and execution stay
        # engine-owned; the driver only schedules the interrogation.
        prefs["_concede"] = {"after_decisions": 60, "seat": 3}
    return prefs


def build_setup_prefs(slot: str, subcase: str = "") -> dict:
    """WS207 setup prefs verbatim (setup wishes, held behavior cards)."""
    return _W207.build_setup_prefs(slot, subcase)


# Bounded E02 combat-scan seeds (fresh processes, 500-decision budget each).
E02_SCAN_SEEDS = [9108, 19108, 29108, 39108, 49108, 59108]


def build_combat_scan_prefs(slot: str, subcase: str = "") -> dict:
    """E02 combat-scan prefs: WS205 wishes minus declare_blocker wishes (so
    the neutral block-all policy fires). Asymmetric press: seat 1 attacks
    (Carnage Tyrant pressure) while seat 0 holds Bear/Elves back to
    multi-block, plus one-shot damage spoil. All selections stay offered-only;
    rejections fail the run closed with full evidence."""
    prefs = _W205.build_prefs(slot, subcase)
    # Drop declaration wishes: wish substrings also match hold labels ("Do
    # not attack with X"), which would keep every attacker home. Neutral
    # press/block-all policies below are offered-only and unambiguous.
    prefs.pop("declare_attacker", None)
    prefs.pop("declare_blocker", None)
    prefs["_attack_all"] = [1]
    prefs["_block_all"] = [0]
    prefs["_spoil_damage_once"] = True
    return prefs
