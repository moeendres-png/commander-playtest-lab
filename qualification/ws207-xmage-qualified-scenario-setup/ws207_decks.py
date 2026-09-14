"""WS207 qualified scenario-setup decks and setup-only preferences.

Derivation: deck shapes follow WS205 `ws205_driver.build_decks` (scenario
cards + basic-land filler, legal commander) with exactly two
coordinator-authorized setup-only substitutions:

- B01: P0's impossible second Soul Warden becomes Essence Warden
  (distinct actual card, identical mandatory trigger; see
  AUTHORITY_ADJUDICATION.md for the Oracle equivalence proof).
- E01: P1's impossible second Runeclaw Bear becomes Grizzly Bears
  (distinct actual vanilla 2/2 Bear; equivalence proof alongside).

All other slots keep WS205 composition byte-identical in card
multiset terms. Decks remain Commander singleton-legal (distinct names;
basic lands exempt). No behavior credit is granted by any deck.

Setup-only preferences (`build_setup_prefs`) name ONLY pre-behavior
setup permanents/lands. Behavior spells are deliberately unwished so the
setup-state machine holds them and stops AT the neutral boundary. The
successor phased pilot owns behavior sequencing (see SUCCESSOR_SPEC.md).
"""

from __future__ import annotations

SLOT_ORDER = [
    "RQ-C3-A03",
    "RQ-C3-A04",
    "RQ-C3-B01",
    "RQ-C3-C01",
    "RQ-C3-C03",
    "RQ-C3-D06",
    "RQ-C3-E01",
    "RQ-C3-E02",
    "RQ-C3-F01",
    "RQ-C3-G02",
    "RQ-C3-G03",
    "RQ-C3-G04",
    "RQ-C3-H01",
    "RQ-C3-I01",
    "RQ-C3-J02",
]

ENGINE_PIN = "cfc36f445f917f101fa2ed588770e043f53bc44c"
SETUP_POLICY_VERSION = "ws207-setup-v1"

KENRITH = "Kenrith, the Returned King"
GHALTA = "Ghalta, Stampede Tyrant"

# Coordinator-authorized setup-only substitutes (actual cards).
B01_SUBSTITUTE = "Essence Warden"
B01_REPLACED = "Soul Warden"
E01_SUBSTITUTE = "Grizzly Bears"
E01_REPLACED = "Runeclaw Bear"

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest"}

# Per-slot scan base for qualification-only seed discovery. Scan ranges are
# fixed BEFORE execution (base + slot_index * 500, 60 sequential seeds) and
# never tuned on behavior outcomes. Selection criteria are setup-only (see
# SEED_CATALOG.json). This is deterministic fixture construction, not
# representative randomness.
SEED_SCAN_BASE = 9401
SEED_SCAN_STRIDE = 500
SEED_SCAN_COUNT = 60

# Setup-run decision budget (native gameplay to establish permanents/hands).
SETUP_BUDGET = 500

# Recorded scan extensions (each disjoint from every other slot's range).
# A03 missed twice at ~0.5% joint odds under both binding models; one honest
# 200-seed extension in the free 9701-9900 window (A04 starts at 9901).
# C01 missed 0/500 under explicit binding (singles at theory rate); two honest
# extensions in the free 11201-11400 and 10701-10900 windows (B01 ends 10700,
# C01 base starts 10901, C03 starts 11401).
SCAN_EXTRA: dict[str, list[tuple[int, int]]] = {
    "RQ-C3-A03": [(9701, 200)],
    "RQ-C3-C01": [(11201, 200), (10701, 200)],
    # H01 joint-opening anomaly round: singles at theory rate but Clone+Bear
    # joints 0/1800 across both binding models (Fisher-combined p~0.015).
    # One bounded 200-seed extension per ordering, then terminal UNKNOWN with
    # the anomaly documented if still dry.
    "RQ-C3-H01-HUMILITY_FIRST": [(15201, 200)],
    "RQ-C3-H01-CLONE_FIRST": [(16201, 200)],
    "RQ-C3-H01-NO_HUMILITY": [(14461, 200), (16701, 200)],
}
SCAN_COUNT_DEFAULT = 60
SCAN_COUNT_WIDE = 300
SCAN_COUNT_PER_SLOT: dict[str, int] = {
    "RQ-C3-A03": SCAN_COUNT_WIDE,
    "RQ-C3-A04": SCAN_COUNT_WIDE,
    "RQ-C3-B01": SCAN_COUNT_WIDE,
    "RQ-C3-C01": SCAN_COUNT_WIDE,
    "RQ-C3-D06": SCAN_COUNT_WIDE,
    "RQ-C3-E01": SCAN_COUNT_WIDE,
    "RQ-C3-E02": SCAN_COUNT_WIDE,
    "RQ-C3-G04": SCAN_COUNT_WIDE,
    "RQ-C3-H01": SCAN_COUNT_WIDE,
    "RQ-C3-I01": SCAN_COUNT_WIDE,
    "RQ-C3-J02": SCAN_COUNT_WIDE,
}


def seed_scan_base(slot: str) -> int:
    """First candidate seed of the fixed per-slot discovery scan."""
    return SEED_SCAN_BASE + SLOT_ORDER.index(slot) * SEED_SCAN_STRIDE


def basics_fill(have: list[str], basics: list[str], total: int = 99) -> list[str]:
    out = list(have)
    i = 0
    while len(out) < total:
        out.append(basics[i % len(basics)])
        i += 1
    return out


def seat_spec(deck_id: str, cards: list[str], basics: list[str], commanders: list[str]) -> dict:
    return {
        "deck_id": deck_id,
        "deck_hash": deck_id,
        "mainboard": basics_fill(cards, basics),
        "commanders": commanders,
    }


def build_decks(slot: str, subcase: str = "") -> dict:
    """Legal Commander decks per slot with B01/E01 singleton corrections."""
    U = ["Island"]
    W = ["Plains"]
    G = ["Forest"]
    R = ["Mountain"]
    B = ["Swamp"]
    K = [KENRITH]
    tag = slot if not subcase else f"{slot}-{subcase}"
    if slot == "RQ-C3-A03":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Drudge Skeletons"], B, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Lightning Bolt"], R, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], G, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-A04":
        return {
            "seat0": seat_spec(
                f"ws207-{tag}-p0",
                ["Doubling Season", "Hardened Scales", "Stonecoil Serpent"],
                G,
                K,
            ),
            "seat1": seat_spec(f"ws207-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-B01":
        # CORRECTED: one Soul Warden + one Essence Warden on P0 (distinct
        # names, identical mandatory trigger) instead of 2x Soul Warden.
        # P0 basics are G+W so both {G} and {W} setup casts are payable.
        return {
            "seat0": seat_spec(
                f"ws207-{tag}-p0", ["Soul Warden", B01_SUBSTITUTE, "Llanowar Elves"], G + W, K
            ),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Soul Warden"], G + W, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", ["Soul Warden"], G + W, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", ["Soul Warden"], G + W, K),
        }
    if slot == "RQ-C3-C01":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Force of Will", "Turn to Frog"], U, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Llanowar Elves"], G, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], R, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], B, K),
        }
    if slot == "RQ-C3-C03":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Fireball"], R, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", [], G, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-D06":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Casualties of War"], B + G, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Ornithopter", "Runeclaw Bear"], G, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-E01":
        # CORRECTED: Runeclaw Bear + Grizzly Bears on P1 (distinct names,
        # identical vanilla 2/2) instead of 2x Runeclaw Bear.
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Propaganda"], U, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Runeclaw Bear", E01_SUBSTITUTE], G, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], R, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-E02":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Runeclaw Bear", "Llanowar Elves"], G, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Carnage Tyrant"], G, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-F01":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Rampant Growth"], G, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-G02":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", [], G, [GHALTA]),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Murder"], B, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-G03":
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", [], G, [GHALTA]),
            "seat1": seat_spec(f"ws207-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-G04":
        return {
            "seat0": seat_spec(
                f"ws207-{tag}-p0", ["Runeclaw Bear", "Control Magic"], G + U, K
            ),
            "seat1": seat_spec(f"ws207-{tag}-p1", [], R, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], B, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], W, K),
        }
    if slot == "RQ-C3-H01":
        if subcase == "CLONE_FIRST":
            return {
                "seat0": seat_spec(f"ws207-{tag}-p0", ["Clone"], U, K),
                "seat1": seat_spec(f"ws207-{tag}-p1", ["Runeclaw Bear"], G, K),
                "seat2": seat_spec(f"ws207-{tag}-p2", ["Humility", "Disenchant"], W, K),
                "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
            }
        if subcase == "NO_HUMILITY":
            return {
                "seat0": seat_spec(f"ws207-{tag}-p0", ["Clone"], U, K),
                "seat1": seat_spec(f"ws207-{tag}-p1", ["Runeclaw Bear"], G, K),
                "seat2": seat_spec(f"ws207-{tag}-p2", [], W, K),
                "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
            }
        return {
            "seat0": seat_spec(f"ws207-{tag}-p0", ["Clone"], U, K),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Runeclaw Bear"], G, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", ["Humility", "Disenchant"], W, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-I01":
        return {
            "seat0": seat_spec(
                f"ws207-{tag}-p0", ["Runeclaw Bear", "Momentary Blink"], G + W, K
            ),
            "seat1": seat_spec(f"ws207-{tag}-p1", ["Pacifism"], W, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], U, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], R, K),
        }
    if slot == "RQ-C3-J02":
        return {
            "seat0": seat_spec(
                f"ws207-{tag}-p0", ["Delina, Wild Mage", "Runeclaw Bear"], R + G, K
            ),
            "seat1": seat_spec(f"ws207-{tag}-p1", [], U, K),
            "seat2": seat_spec(f"ws207-{tag}-p2", [], W, K),
            "seat3": seat_spec(f"ws207-{tag}-p3", [], B, K),
        }
    raise ValueError(f"unknown slot {slot}")


# Setup-cast wishes per slot: permanents that belong on the battlefield in
# the neutral state. Behavior spells are never wished (held in hand).
SETUP_WISHES: dict[str, dict[str, list[str]]] = {
    "RQ-C3-A03": {"0": ["Drudge Skeletons"]},
    "RQ-C3-A04": {"0": ["Doubling Season", "Hardened Scales"]},
    "RQ-C3-B01": {
        "0": ["Soul Warden", "Essence Warden"],
        "1": ["Soul Warden"],
        "2": ["Soul Warden"],
        "3": ["Soul Warden"],
    },
    "RQ-C3-C01": {},
    "RQ-C3-C03": {},
    "RQ-C3-D06": {"1": ["Ornithopter", "Runeclaw Bear"]},
    "RQ-C3-E01": {"0": ["Propaganda"], "1": ["Runeclaw Bear", "Grizzly Bears"]},
    "RQ-C3-E02": {"0": ["Runeclaw Bear", "Llanowar Elves"], "1": ["Carnage Tyrant"]},
    "RQ-C3-F01": {},
    "RQ-C3-G02": {"0": ["Ghalta"]},
    "RQ-C3-G03": {"0": ["Ghalta"]},
    "RQ-C3-G04": {"1": ["Runeclaw Bear"], "0": ["Control Magic"]},
    "RQ-C3-H01": {"0": [], "1": ["Runeclaw Bear"], "2": ["Humility"]},
    "RQ-C3-I01": {"0": ["Runeclaw Bear"], "1": ["Pacifism"]},
    "RQ-C3-J02": {"0": ["Delina, Wild Mage", "Runeclaw Bear"]},
}

# Setup targeting wishes: seat -> desired target substrings for setup Aura
# casts (offered-only matching, same as WS205 `target` prefs).
SETUP_TARGETS: dict[str, dict[str, list[str]]] = {
    "RQ-C3-G04": {"0": ["Runeclaw Bear"]},
    "RQ-C3-I01": {"1": ["Runeclaw Bear"]},
}

# Behavior cards that must remain HELD (never wished) during setup.
HELD_BEHAVIOR_CARDS: dict[str, list[str]] = {
    "RQ-C3-A03": ["Lightning Bolt"],
    "RQ-C3-A04": ["Stonecoil Serpent"],
    "RQ-C3-B01": ["Llanowar Elves"],
    "RQ-C3-C01": ["Force of Will", "Llanowar Elves"],
    "RQ-C3-C03": ["Fireball"],
    "RQ-C3-D06": ["Casualties of War"],
    "RQ-C3-E01": [],
    "RQ-C3-E02": [],
    "RQ-C3-F01": ["Rampant Growth"],
    "RQ-C3-G02": ["Murder"],
    "RQ-C3-G03": [],
    "RQ-C3-G04": [],
    "RQ-C3-H01": ["Clone"],
    "RQ-C3-I01": ["Momentary Blink"],
    "RQ-C3-J02": [],
}

# Opening-hand requirements per slot: seat -> required card names in the
# dealt opening 7 (privileged setup-control knowledge, assertion-only).
OPENING_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "RQ-C3-A03": {"seat0": ["Drudge Skeletons"], "seat1": ["Lightning Bolt"]},
    "RQ-C3-A04": {"seat0": ["Doubling Season|Hardened Scales", "Stonecoil Serpent"]},
    "RQ-C3-B01": {"seat0": ["Llanowar Elves", "Soul Warden|Essence Warden"]},
    "RQ-C3-C01": {"seat0": ["Force of Will"], "seat1": ["Llanowar Elves"]},
    "RQ-C3-C03": {"seat0": ["Fireball"]},
    "RQ-C3-D06": {"seat0": ["Casualties of War"]},
    "RQ-C3-E01": {"seat0": ["Propaganda"], "seat1": ["Runeclaw Bear|Grizzly Bears"]},
    "RQ-C3-E02": {"seat0": ["Runeclaw Bear"], "seat1": ["Carnage Tyrant"]},
    "RQ-C3-F01": {"seat0": ["Rampant Growth"]},
    "RQ-C3-G02": {"seat1": ["Murder"]},
    "RQ-C3-G03": {},
    "RQ-C3-G04": {"seat0": ["Runeclaw Bear", "Control Magic"]},
    "RQ-C3-H01": {"seat0": ["Clone"], "seat1": ["Runeclaw Bear"]},
    "RQ-C3-I01": {"seat0": ["Momentary Blink"], "seat1": ["Pacifism"]},
    "RQ-C3-J02": {"seat0": ["Delina, Wild Mage|Runeclaw Bear"]},
}

# Public battlefield predicates for the setup-state semantic check:
# (card substring, controller seat) pairs expected on the battlefield.
BATTLEFIELD_PREDICATES: dict[str, list[tuple[str, int]]] = {
    "RQ-C3-A03": [("Drudge Skeletons", 0), ("Swamp", 0), ("Mountain", 1)],
    "RQ-C3-A04": [("Doubling Season", 0), ("Hardened Scales", 0)],
    "RQ-C3-B01": [
        ("Soul Warden", 0),
        ("Essence Warden", 0),
        ("Soul Warden", 1),
        ("Soul Warden", 2),
        ("Soul Warden", 3),
    ],
    "RQ-C3-C01": [],
    "RQ-C3-C03": [],
    "RQ-C3-D06": [],
    "RQ-C3-E01": [("Propaganda", 0), ("Runeclaw Bear", 1), ("Grizzly Bears", 1)],
    "RQ-C3-E02": [("Runeclaw Bear", 0), ("Carnage Tyrant", 1)],
    "RQ-C3-F01": [("Forest", 0)],
    "RQ-C3-G02": [("Ghalta", 0)],
    "RQ-C3-G03": [("Ghalta", 0)],
    "RQ-C3-G04": [("Runeclaw Bear", 0), ("Control Magic", 0)],
    "RQ-C3-H01": [("Humility", 2), ("Runeclaw Bear", 1)],
    "RQ-C3-I01": [("Runeclaw Bear", 0), ("Pacifism", 0)],
    "RQ-C3-J02": [("Delina", 0), ("Runeclaw Bear", 0)],
}


def build_setup_prefs(slot: str, subcase: str = "") -> dict:
    """Setup-only prefs: wish setup permanents, hold behavior cards.

    Mirrors WS205 prefs shape (`priority`/`choice`/`target`/...) so the
    existing generic-boundary driver can execute them unchanged. Behavior
    cards appear in NO wish list: the neutral fallback (play land / pass)
    holds them. The `_setup` meta block records held cards for the
    setup-state check (held cards must never be selected).
    """
    wishes = dict(SETUP_WISHES.get(slot, {}))
    if slot == "RQ-C3-H01":
        if subcase == "NO_HUMILITY":
            wishes = {"0": [], "1": ["Runeclaw Bear"]}
        elif subcase == "CLONE_FIRST":
            # Hold Humility until the Clone copy is established (successor
            # sequences this phase; setup prefs record the hold).
            wishes = {"0": [], "1": ["Runeclaw Bear"], "2": []}
    base: dict = {"play_land_max": 12, "neutral_play_land": "true"}
    if wishes:
        base["priority"] = {seat: list(names) for seat, names in wishes.items() if names}
    if slot == "RQ-C3-G03":
        # G03 prelude attacks are setup (native commander-damage ledger
        # construction); the tested subsequent hit belongs to the successor.
        base["declare_attacker"] = {"0": ["Ghalta"]}
    targets = SETUP_TARGETS.get(slot, {})
    if targets:
        base["target"] = {seat: list(names) for seat, names in targets.items()}
    if "priority" in base:
        choice = base.setdefault("choice", {})
        for seat, names in base["priority"].items():
            merged = list(names)
            for existing in choice.get(seat, []):
                if existing not in merged:
                    merged.append(existing)
            choice[seat] = merged
    base["_setup"] = {
        "held_behavior_cards": list(HELD_BEHAVIOR_CARDS.get(slot, [])),
        "setup_policy_version": SETUP_POLICY_VERSION,
        "slot": slot,
        "subcase": subcase,
    }
    return base


def check_singleton_legal(decks: dict) -> list[str]:
    """Return a list of singleton violations (empty when legal)."""
    problems = []
    for seat, spec in decks.items():
        seen: set[str] = set()
        for card in spec["mainboard"]:
            if card in BASIC_LANDS:
                continue
            if card in seen:
                problems.append(f"{seat}: duplicate {card}")
            seen.add(card)
        for commander in spec["commanders"]:
            if commander in spec["mainboard"]:
                problems.append(f"{seat}: commander in mainboard {commander}")
        if len(spec["mainboard"]) + len(spec["commanders"]) != 100:
            problems.append(f"{seat}: not 100 cards")
    return problems
