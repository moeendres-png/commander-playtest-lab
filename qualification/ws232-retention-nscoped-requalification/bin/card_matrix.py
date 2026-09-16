#!/usr/bin/env python3
"""WS232 actual-card 29 matrix config + verdict rules (test-only).

Systemic test-only scenario infrastructure (no card-name legality hacks):
every game runs SYMMETRIC singleton Commander-legal decks (commander +
99 singleton mainboard incl exactly 1 copy of the focus card; engine deck
validation enforces 100-card size, singleton, AND color identity) through
the unmodified XMage Rules Core. All pilots run the Spotlight preference
for the focus card (ordinary themed-table discretion among
engine-authorized options). The engine owns all legality, costs, targets,
and outcomes.

Commander power baselines (damage attribution): Rograkh 0, Esior 1,
Toshiro 2, Omnath 1, Hapatra 2, Akiri 2, Veyran 2, Kaervek 5, Ishai 1,
Isamaru 2. DAMAGE verdicts require a post-cast drop that cannot be fully
explained by the noted baseline combat, or an explicit lifelink-gain /
spell-damage chain; otherwise the cell stays UNKNOWN.

Verdict kinds (evaluated against the public run log):
  BATTLEFIELD   PASS iff the focus card arrives on a battlefield.
  GRAVEYARD_CAST PASS iff focus selected at priority AND the focus card
                arrives in its owner's graveyard AND the game advances
                (>=3 later decisions, no failure). Null-result resolutions
                PASS with an explicit note.
  DAMAGE        PASS iff GRAVEYARD_CAST conditions hold AND an opponent's
                life drops below 40 within the post-selection window
                beyond the commander baseline.
  X_NUMERIC     PASS iff focus selected AND an announce_x/amount frame is
                consumed within the window AND GRAVEYARD_CAST holds.
  CHAIN         card-specific public chains (documented per card).
Anything else -> UNKNOWN (exact cause sealed; never PASS by default).
"""
from __future__ import annotations

DEFAULT_COMMANDER = "Rograkh, Son of Rohgahh"


def _lands(spec: dict[str, int], focus: str) -> tuple[str, ...]:
    main = [focus]
    for land, count in spec.items():
        main.extend([land] * count)
    assert len(main) == 99, (focus, len(main))
    return tuple(main)


# commander -> (power baseline, basic land map builder)
CARDS = {
    "CARD_01": {"name": "Ishai, Ojutai Dragonspeaker", "kind": "BATTLEFIELD",
                "commander": "Ishai, Ojutai Dragonspeaker", "commander_power": 1,
                "notes": "commander is the focus; mainboard 99 lands (importer counts zones together); arrival via command-zone casts", "commander_is_focus": True,
                "lands": {"Plains": 49, "Island": 49}},
    "CARD_02": {"name": "Rograkh, Son of Rohgahh", "kind": "BATTLEFIELD",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "commander is the focus; mainboard 99 Mountains; cast/combat via command zone", "commander_is_focus": True,
                "lands": {"Mountain": 98}},
    "CARD_03": {"name": "Esior, Wardwing Familiar", "kind": "BATTLEFIELD",
                "commander": "Esior, Wardwing Familiar", "commander_power": 1,
                "notes": "commander is the focus; mainboard 99 Islands; cast/combat via command zone", "commander_is_focus": True,
                "lands": {"Island": 98}},
    "CARD_04": {"name": "Kediss, Emberclaw Familiar", "kind": "BATTLEFIELD",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "arrival; commander-damage trigger needs commander damage",
                "lands": {"Mountain": 98}},
    "CARD_05": {"name": "Veyran, Voice of Duality", "kind": "BATTLEFIELD",
                "commander": "Veyran, Voice of Duality", "commander_power": 2,
                "notes": "commander is the focus; mainboard split lands; cast/combat via command zone", "commander_is_focus": True,
                "lands": {"Island": 49, "Mountain": 49}},
    "CARD_06": {"name": "Harmonic Prodigy", "kind": "BATTLEFIELD",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "arrival + combat vs 0-power baseline",
                "lands": {"Mountain": 98}},
    "CARD_07": {"name": "Narset, Parter of Veils", "kind": "BATTLEFIELD",
                "commander": "Esior, Wardwing Familiar", "commander_power": 1,
                "notes": "arrival + loyalty activation decisions",
                "lands": {"Island": 98}},
    "CARD_08": {"name": "Jeska, Thrice Reborn", "kind": "DAMAGE",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "loyalty damage signature vs 0-power baseline",
                "lands": {"Mountain": 98}},
    "CARD_09": {"name": "Magma Opus", "kind": "DAMAGE",
                "commander": "Veyran, Voice of Duality", "commander_power": 2,
                "notes": "10-mana; long window; 2-power baseline noted",
                "lands": {"Island": 49, "Mountain": 49}},
    "CARD_10": {"name": "Wash Away", "kind": "CHAIN",
                "commander": "Esior, Wardwing Familiar", "commander_power": 1,
                "notes": "counter chain: opponent spell departs stack unresolved + Wash Away consumed",
                "lands": {"Island": 98}},
    "CARD_11": {"name": "Wear // Tear", "kind": "GRAVEYARD_CAST", "enablers": ["Ornithopter"], "focus_halves": ["Wear", "Tear"],
                "commander": "Akiri, Line-Slinger", "commander_power": 2,
                "notes": "needs artifact/enchantment victim; likely UNKNOWN",
                "lands": {"Mountain": 49, "Plains": 49}},
    "CARD_12": {"name": "Dig Through Time", "kind": "GRAVEYARD_CAST",
                "commander": "Esior, Wardwing Familiar", "commander_power": 1,
                "notes": "8-mana delve; resolution private; cast+consume bar",
                "lands": {"Island": 98}},
    "CARD_13": {"name": "Flare of Duplication", "kind": "CHAIN", "enablers": ["Lightning Strike"],
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "copy chain: opponent spell on stack + Flare consumed",
                "lands": {"Mountain": 98}},
    "CARD_14": {"name": "Vandalblast", "kind": "GRAVEYARD_CAST", "enablers": ["Ornithopter"],
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "no artifacts in symmetric decks; overload null-resolution may PASS with note",
                "lands": {"Mountain": 98}},
    "CARD_15": {"name": "Finale of Revelation", "kind": "X_NUMERIC",
                "commander": "Esior, Wardwing Familiar", "commander_power": 1,
                "notes": "X-spell numeric frame + consume",
                "lands": {"Island": 98}},
    "CARD_16": {"name": "Psychosis Crawler", "kind": "BATTLEFIELD",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "colorless; arrival (*/* = hand size); combat over baseline",
                "lands": {"Mountain": 98}},
    "CARD_17": {"name": "Kaervek the Merciless", "kind": "CHAIN", "permanent": True,
                "commander": "Kaervek the Merciless", "commander_power": 5,
                "notes": "commander is the focus; mainboard split lands; cast + opponent-cast damage chain; 5-power baseline", "commander_is_focus": True,
                "lands": {"Swamp": 49, "Mountain": 49}},
    "CARD_18": {"name": "Shriekmaw", "kind": "CHAIN", "permanent": True,
                "commander": "Toshiro Umezawa", "commander_power": 2,
                "notes": "evoke destroy chain: enemy creature departs to command + choice decisions",
                "lands": {"Swamp": 98}},
    "CARD_19": {"name": "Butcher of Malakir", "kind": "CHAIN", "permanent": True,
                "commander": "Toshiro Umezawa", "commander_power": 2,
                "notes": "arrival + death-triggered sacrifice chain",
                "lands": {"Swamp": 98}},
    "CARD_20": {"name": "Syphon Mind", "kind": "CHAIN",
                "commander": "Toshiro Umezawa", "commander_power": 2,
                "notes": "opponent discard decisions + hand_count drops + consume",
                "lands": {"Swamp": 98}},
    "CARD_21": {"name": "Gratuitous Violence", "kind": "BATTLEFIELD",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "arrival; doubler has no solo signature; likely UNKNOWN",
                "lands": {"Mountain": 98}},
    "CARD_22": {"name": "Bolt Bend", "kind": "GRAVEYARD_CAST", "enablers": ["Lightning Strike"],
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "needs stack target; likely UNKNOWN",
                "lands": {"Mountain": 98}},
    "CARD_23": {"name": "Makeshift Mannequin", "kind": "GRAVEYARD_CAST",
                "commander": "Toshiro Umezawa", "commander_power": 2,
                "notes": "needs yard creature; likely UNKNOWN",
                "lands": {"Swamp": 98}},
    "CARD_24": {"name": "Warstorm Surge", "kind": "CHAIN", "permanent": True,
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "arrival + later own-creature ETB trigger decisions",
                "lands": {"Mountain": 98}},
    "CARD_25": {"name": "Basilisk Collar", "kind": "CHAIN", "permanent": True,
                "commander": "Isamaru, Hound of Konda", "commander_power": 2,
                "notes": "Isamaru base; equip + lifelink-gain chain",
                "lands": {"Plains": 98}},
    "CARD_26": {"name": "Burn Down the House", "kind": "DAMAGE",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "mode choice + damage/devil signature vs 0-power baseline",
                "lands": {"Mountain": 98}},
    "CARD_27": {"name": "Path of Ancestry", "kind": "BATTLEFIELD",
                "commander": "Rograkh, Son of Rohgahh", "commander_power": 0,
                "notes": "land; arrival is not priority-visible; likely UNKNOWN",
                "lands": {"Mountain": 98}},
    "CARD_28": {"name": "Find // Finality", "kind": "CHAIN", "focus_halves": ["Find", "Finality"],
                "commander": "Hapatra, Vizier of Poisons", "commander_power": 2,
                "notes": "Find needs yard; Finality wipe needs board; attempt both",
                "lands": {"Swamp": 49, "Forest": 49}},
    "CARD_29": {"name": "Boseiju Reaches Skyward // Branch of Boseiju", "deck_name": "Boseiju Reaches Skyward",
                "kind": "BATTLEFIELD",
                "commander": "Omnath, Locus of Mana", "commander_power": 1,
                "notes": "saga arrival + chapter decisions",
                "lands": {"Forest": 98}},
}


def build_mainboard(card_name: str, lands: dict[str, int]) -> tuple[str, ...]:
    return _lands(lands, card_name)
