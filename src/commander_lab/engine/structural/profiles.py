from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from commander_lab.cards.catalog import CardCatalog
from commander_lab.models import (
    CardIdentity,
    CardRole,
    Color,
    ConditionalStrength,
    DataQuality,
    Deck,
    DeckZone,
    SourceRef,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.models.roles import StructuralMechanic
from commander_lab.storage import compute_data_snapshot_hash, compute_deck_hash

# This profile table is intentionally structural. It is not a substitute for Oracle text.
ROLE_GROUPS: dict[CardRole, set[str]] = {
    CardRole.RAMP: {
        "Arcane Signet",
        "Azorius Signet",
        "Boros Signet",
        "Cinder Glade",
        "Chandra, Torch of Defiance",
        "Crop Rotation",
        "Dark Ritual",
        "Farseek",
        "Fellwar Stone",
        "Harrow",
        "Ignoble Hierarch",
        "Izzet Signet",
        "Llanowar Elves",
        "Nature's Lore",
        "Oracle of Mul Daya",
        "Orcish Lumberjack",
        "Relic of Legends",
        "Sakura-Tribe Elder",
        "Sol Ring",
        "Soul of Windgrace",
        "Springbloom Druid",
        "Springleaf Drum",
        "Sprouting Goblin",
        "Storm-Kiln Artist",
        "Talisman of Progress",
        "Tinder Wall",
        "Tireless Provisioner",
        "Exploration Broodship",
        "Horizon Explorer",
        "Evendo Brushrazer",
    },
    CardRole.DRAW: {
        "Braids, Arisen Nightmare",
        "Chandra, Torch of Defiance",
        "Combat Research",
        "Consider",
        "Curiosity",
        "Deadly Dispute",
        "Faerie Mastermind",
        "God-Eternal Bontu",
        "Korvold, Fae-Cursed King",
        "Loyal Drake",
        "Staggering Insight",
        "The Gitrog Monster",
        "Tireless Tracker",
        "Whirlwind of Thought",
        "Hearthhull, the Worldseed",
        "Evendo Brushrazer",
    },
    CardRole.SELECTION: {
        "Consider",
        "Crop Rotation",
        "Open the Armory",
        "Preordain",
        "Narset, Parter of Veils",
    },
    CardRole.REMOVAL: {
        "Ancient Grudge",
        "Assassin's Trophy",
        "Beast Within",
        "Celestial Purge",
        "Chaos Warp",
        "Fire Covenant",
        "Imprisoned in the Moon",
        "Into the Roil",
        "Light of Hope",
        "Loran of the Third Path",
        "Path to Exile",
        "Pest Infestation",
        "Rakdos Charm",
        "Reality Shift",
        "Snapback",
        "Stroke of Midnight",
        "Swords to Plowshares",
        "Tear Asunder",
        "Vandalblast",
        "Wash Away",
        "Wear // Tear",
        "Windgrace's Judgment",
        "Nature's Claim",
    },
    CardRole.COUNTER: {
        "An Offer You Can't Refuse",
        "Counterspell",
        "Dovin's Veto",
        "Lofty Denial",
        "Louisoix's Sacrifice",
        "Negate",
        "Silence",
        "Wash Away",
    },
    CardRole.PROTECTION: {
        "Bastion Protector",
        "Blacksmith's Skill",
        "Boros Charm",
        "Esior, Wardwing Familiar",
        "Loran's Escape",
        "Silence",
        "Slip Out the Back",
        "Snakeskin Veil",
        "Swiftfoot Boots",
        "Tyvar's Stand",
        "Veil of Summer",
    },
    CardRole.WIPE: {
        "Blasphemous Act",
        "Chain Reaction",
        "Culling Ritual",
        "Farewell",
        "Fire Covenant",
        "Massacre Wurm",
        "Pest Infestation",
        "Toxic Deluge",
        "Vandalblast",
        "Winds of Rath",
    },
    CardRole.RECURSION: {
        "Aftermath Analyst",
        "Exploration Broodship",
        "Ramunap Excavator",
        "Soul of Windgrace",
        "Splendid Reclamation",
        "Szarel, Genesis Shepherd",
        "Titania, Protector of Argoth",
    },
    CardRole.GRAVEYARD_HATE: {
        "Bojuka Bog",
        "Farewell",
        "Immersturm Predator",
        "Rakdos Charm",
        "Soul-Guide Lantern",
    },
    CardRole.ENGINE: {
        "Academy Manufactor",
        "Braids, Arisen Nightmare",
        "Chandra, Torch of Defiance",
        "Faerie Mastermind",
        "God-Eternal Bontu",
        "Korvold, Fae-Cursed King",
        "Kykar, Wind's Fury",
        "Mazirek, Kraul Death Priest",
        "Mirkwood Bats",
        "Narset, Parter of Veils",
        "Ophiomancer",
        "Oracle of Mul Daya",
        "Pitiless Plunderer",
        "Soul of Windgrace",
        "Storm-Kiln Artist",
        "Szarel, Genesis Shepherd",
        "The Gitrog Monster",
        "Tireless Provisioner",
        "Tireless Tracker",
        "Whirlwind of Thought",
        "Hearthhull, the Worldseed",
        "Evendo Brushrazer",
        "Exploration Broodship",
        "Scouring Swarm",
    },
    CardRole.ENABLER: {
        "Academy Manufactor",
        "Deadly Dispute",
        "Exploration Broodship",
        "Harrow",
        "Horizon Explorer",
        "Ophiomancer",
        "Pitiless Plunderer",
        "Sakura-Tribe Elder",
        "Springbloom Druid",
        "Tireless Provisioner",
        "Zuran Orb",
        "Rograkh, Son of Rohgahh",
        "Springleaf Drum",
        "Kykar, Wind's Fury",
        "Storm-Kiln Artist",
        "Evendo Brushrazer",
    },
    CardRole.PAYOFF: {
        "Academy Manufactor",
        "Goblin Bombardment",
        "Guttersnipe",
        "Hearthhull, the Worldseed",
        "Korvold, Fae-Cursed King",
        "Mayhem Devil",
        "Mazirek, Kraul Death Priest",
        "Mirkwood Bats",
        "Scouring Swarm",
        "Szarel, Genesis Shepherd",
        "The Gitrog Monster",
        "Titania, Protector of Argoth",
        "Whirlwind of Thought",
    },
    CardRole.FINISHER: {
        "Exsanguinate",
        "Guttersnipe",
        "Hearthhull, the Worldseed",
        "Jeska, Thrice Reborn",
        "Kediss, Emberclaw Familiar",
        "Massacre Wurm",
        "Mirkwood Bats",
        "Mazirek, Kraul Death Priest",
        "Szarel, Genesis Shepherd",
    },
    CardRole.COMBAT_PAYOFF: {
        "Blackblade Reforged",
        "Boros Charm",
        "Combat Research",
        "Curiosity",
        "Duelist's Heritage",
        "Ishai, Ojutai Dragonspeaker",
        "Jeska, Thrice Reborn",
        "Kediss, Emberclaw Familiar",
        "Psychotic Fury",
        "Staggering Insight",
        "Sunhome, Fortress of the Legion",
        "Swiftfoot Boots",
    },
    CardRole.TOKEN_SOURCE: {
        "Eumidian Hatchery",
        "Horizon Explorer",
        "Kykar, Wind's Fury",
        "Ophiomancer",
        "Pest Infestation",
        "Scouring Swarm",
        "Storm-Kiln Artist",
        "Titania, Protector of Argoth",
        "Tireless Provisioner",
        "Tireless Tracker",
    },
    CardRole.SACRIFICE_OUTLET: {
        "Braids, Arisen Nightmare",
        "Deadly Dispute",
        "Goblin Bombardment",
        "God-Eternal Bontu",
        "Harrow",
        "Korvold, Fae-Cursed King",
        "Zuran Orb",
        "Evendo Brushrazer",
        "Hearthhull, the Worldseed",
    },
    CardRole.LAND_SYNERGY: {
        "Aftermath Analyst",
        "Crop Rotation",
        "Eumidian Hatchery",
        "Exploration Broodship",
        "Harrow",
        "Hearthhull, the Worldseed",
        "Horizon Explorer",
        "Oracle of Mul Daya",
        "Ramunap Excavator",
        "Scouring Swarm",
        "Soul of Windgrace",
        "Splendid Reclamation",
        "Springbloom Druid",
        "Sprouting Goblin",
        "Szarel, Genesis Shepherd",
        "The Gitrog Monster",
        "Titania, Protector of Argoth",
        "Tireless Provisioner",
        "Tireless Tracker",
        "Zuran Orb",
    },
}


MANA_VALUES: dict[str, float] = {
    "Korvold, Fae-Cursed King": 5,
    "Ishai, Ojutai Dragonspeaker": 4,
    "Rograkh, Son of Rohgahh": 0,
    "Sol Ring": 1,
    "Arcane Signet": 2,
    "Swiftfoot Boots": 2,
    "Zuran Orb": 0,
    "Exploration Broodship": 1,
    "Exsanguinate": 4,
    "Massacre Wurm": 6,
    "Mazirek, Kraul Death Priest": 5,
    "Ophiomancer": 3,
    "Braids, Arisen Nightmare": 3,
    "Toxic Deluge": 3,
    "Dark Ritual": 1,
    "Deadly Dispute": 2,
    "God-Eternal Bontu": 5,
    "Mirkwood Bats": 4,
    "Pitiless Plunderer": 4,
    "Blasphemous Act": 9,
    "Chaos Warp": 3,
    "Evendo Brushrazer": 3,
    "Goblin Bombardment": 2,
    "Snakeskin Veil": 1,
    "Springbloom Druid": 3,
    "Llanowar Elves": 1,
    "Veil of Summer": 1,
    "Nature's Claim": 1,
    "Aftermath Analyst": 2,
    "Beast Within": 3,
    "Crop Rotation": 1,
    "Farseek": 2,
    "Harrow": 3,
    "Nature's Lore": 2,
    "Oracle of Mul Daya": 4,
    "Pest Infestation": 3,
    "Ramunap Excavator": 3,
    "Sakura-Tribe Elder": 2,
    "Splendid Reclamation": 4,
    "Tireless Provisioner": 3,
    "Tireless Tracker": 3,
    "Titania, Protector of Argoth": 5,
    "Tyvar's Stand": 2,
    "Academy Manufactor": 3,
    "Immersturm Predator": 4,
    "Fire Covenant": 3,
    "Mayhem Devil": 3,
    "Rakdos Charm": 2,
    "Horizon Explorer": 3,
    "Assassin's Trophy": 2,
    "Culling Ritual": 4,
    "Szarel, Genesis Shepherd": 5,
    "Scouring Swarm": 3,
    "Tear Asunder": 2,
    "The Gitrog Monster": 5,
    "Windgrace's Judgment": 5,
    "Ancient Grudge": 2,
    "Orcish Lumberjack": 1,
    "Sprouting Goblin": 2,
    "Tinder Wall": 1,
    "Hearthhull, the Worldseed": 4,
    "Ignoble Hierarch": 1,
    "Soul of Windgrace": 4,
    "Soul-Guide Lantern": 1,
    "Chandra, Torch of Defiance": 4,
    "Blackblade Reforged": 2,
    "Fellwar Stone": 2,
    "Relic of Legends": 3,
    "Springleaf Drum": 1,
    "Talisman of Progress": 2,
    "Stroke of Midnight": 3,
    "Silence": 1,
    "Light of Hope": 1,
    "Celestial Purge": 2,
    "Bastion Protector": 3,
    "Blacksmith's Skill": 1,
    "Loran of the Third Path": 3,
    "Loran's Escape": 1,
    "Open the Armory": 2,
    "Path to Exile": 1,
    "Swords to Plowshares": 1,
    "Winds of Rath": 5,
    "Faerie Mastermind": 2,
    "Into the Roil": 2,
    "Negate": 2,
    "Imprisoned in the Moon": 3,
    "Staggering Insight": 2,
    "Curiosity": 1,
    "An Offer You Can't Refuse": 1,
    "Farewell": 6,
    "Storm-Kiln Artist": 4,
    "Clever Impersonator": 4,
    "Consider": 1,
    "Counterspell": 2,
    "Combat Research": 1,
    "Esior, Wardwing Familiar": 2,
    "Lofty Denial": 2,
    "Louisoix's Sacrifice": 2,
    "Loyal Drake": 3,
    "Narset, Parter of Veils": 3,
    "Preordain": 1,
    "Reality Shift": 2,
    "Slip Out the Back": 1,
    "Snapback": 2,
    "Wash Away": 1,
    "Guttersnipe": 3,
    "Jeska, Thrice Reborn": 3,
    "Kediss, Emberclaw Familiar": 2,
    "Chain Reaction": 4,
    "Flare of Duplication": 3,
    "Psychotic Fury": 2,
    "Boros Charm": 2,
    "Vandalblast": 1,
    "Azorius Signet": 2,
    "Dovin's Veto": 2,
    "Duelist's Heritage": 3,
    "Izzet Signet": 2,
    "Kykar, Wind's Fury": 4,
    "Whirlwind of Thought": 4,
    "Boros Signet": 2,
    "Wear // Tear": 3,
}


BASE_POWER: dict[str, float] = {
    "Korvold, Fae-Cursed King": 4,
    "Ishai, Ojutai Dragonspeaker": 1,
    "Rograkh, Son of Rohgahh": 0,
    "Massacre Wurm": 6,
    "Mazirek, Kraul Death Priest": 2,
    "Ophiomancer": 2,
    "God-Eternal Bontu": 5,
    "Mirkwood Bats": 2,
    "Pitiless Plunderer": 1,
    "Evendo Brushrazer": 2,
    "Llanowar Elves": 1,
    "Oracle of Mul Daya": 2,
    "Ramunap Excavator": 2,
    "Sakura-Tribe Elder": 1,
    "Tireless Provisioner": 3,
    "Tireless Tracker": 3,
    "Titania, Protector of Argoth": 5,
    "Academy Manufactor": 1,
    "Immersturm Predator": 3,
    "Mayhem Devil": 3,
    "Horizon Explorer": 3,
    "Szarel, Genesis Shepherd": 2,
    "Scouring Swarm": 1,
    "The Gitrog Monster": 6,
    "Orcish Lumberjack": 1,
    "Sprouting Goblin": 2,
    "Tinder Wall": 0,
    "Hearthhull, the Worldseed": 6,
    "Ignoble Hierarch": 0,
    "Soul of Windgrace": 5,
    "Bastion Protector": 3,
    "Loran of the Third Path": 2,
    "Faerie Mastermind": 2,
    "Storm-Kiln Artist": 2,
    "Clever Impersonator": 3,
    "Esior, Wardwing Familiar": 1,
    "Loyal Drake": 2,
    "Guttersnipe": 2,
    "Kediss, Emberclaw Familiar": 1,
    "Kykar, Wind's Fury": 3,
}


PERMANENT_EXCEPTIONS = {
    "Exsanguinate",
    "Toxic Deluge",
    "Dark Ritual",
    "Deadly Dispute",
    "Blasphemous Act",
    "Chaos Warp",
    "Snakeskin Veil",
    "Veil of Summer",
    "Nature's Claim",
    "Beast Within",
    "Crop Rotation",
    "Farseek",
    "Harrow",
    "Nature's Lore",
    "Pest Infestation",
    "Splendid Reclamation",
    "Tyvar's Stand",
    "Fire Covenant",
    "Rakdos Charm",
    "Assassin's Trophy",
    "Culling Ritual",
    "Tear Asunder",
    "Windgrace's Judgment",
    "Ancient Grudge",
    "Stroke of Midnight",
    "Silence",
    "Light of Hope",
    "Celestial Purge",
    "Blacksmith's Skill",
    "Loran's Escape",
    "Open the Armory",
    "Path to Exile",
    "Swords to Plowshares",
    "Winds of Rath",
    "Into the Roil",
    "Negate",
    "An Offer You Can't Refuse",
    "Farewell",
    "Consider",
    "Counterspell",
    "Lofty Denial",
    "Louisoix's Sacrifice",
    "Preordain",
    "Reality Shift",
    "Slip Out the Back",
    "Snapback",
    "Wash Away",
    "Chain Reaction",
    "Flare of Duplication",
    "Psychotic Fury",
    "Boros Charm",
    "Vandalblast",
    "Dovin's Veto",
    "Wear // Tear",
}


ROLE_STRENGTH_OVERRIDES: dict[str, dict[CardRole, float]] = {
    "Sol Ring": {CardRole.RAMP: 2.2},
    "Dark Ritual": {CardRole.RAMP: 1.8},
    "Korvold, Fae-Cursed King": {CardRole.DRAW: 1.8, CardRole.ENGINE: 1.9, CardRole.PAYOFF: 1.6},
    "Exsanguinate": {CardRole.FINISHER: 2.0},
    "Toxic Deluge": {CardRole.WIPE: 1.8},
    "Blasphemous Act": {CardRole.WIPE: 1.6},
    "Farewell": {CardRole.WIPE: 2.0, CardRole.GRAVEYARD_HATE: 1.8},
    "Mirkwood Bats": {CardRole.PAYOFF: 1.8, CardRole.FINISHER: 1.5},
    "Hearthhull, the Worldseed": {CardRole.DRAW: 1.6, CardRole.PAYOFF: 1.8, CardRole.FINISHER: 1.6},
    "Kediss, Emberclaw Familiar": {CardRole.COMBAT_PAYOFF: 1.8, CardRole.FINISHER: 1.5},
    "Jeska, Thrice Reborn": {CardRole.COMBAT_PAYOFF: 2.0, CardRole.FINISHER: 1.7},
    "Duelist's Heritage": {CardRole.COMBAT_PAYOFF: 1.6},
    "Whirlwind of Thought": {CardRole.DRAW: 1.7, CardRole.ENGINE: 1.7},
    "Guttersnipe": {CardRole.PAYOFF: 1.6, CardRole.FINISHER: 1.3},
    "Soul-Guide Lantern": {CardRole.GRAVEYARD_HATE: 1.4},
}


HIGH_IMMEDIATE = {
    "Sol Ring",
    "Dark Ritual",
    "Deadly Dispute",
    "Toxic Deluge",
    "Blasphemous Act",
    "Farewell",
    "Fire Covenant",
    "Exsanguinate",
    "Path to Exile",
    "Swords to Plowshares",
    "An Offer You Can't Refuse",
    "Counterspell",
    "Dovin's Veto",
    "Boros Charm",
    "Rakdos Charm",
    "Pest Infestation",
    "Culling Ritual",
    "Massacre Wurm",
}
HIGH_TURN_CYCLE_RISK = {
    "Horizon Explorer",
    "Scouring Swarm",
    "Mazirek, Kraul Death Priest",
    "Szarel, Genesis Shepherd",
    "Whirlwind of Thought",
    "Duelist's Heritage",
    "Blackblade Reforged",
    "Staggering Insight",
    "Curiosity",
    "Combat Research",
}
MULTIPLAYER_SCALING: dict[str, float] = {
    "Korvold, Fae-Cursed King": 0.1,
    "Mirkwood Bats": 1.2,
    "Exsanguinate": 1.3,
    "Massacre Wurm": 1.1,
    "Hearthhull, the Worldseed": 1.2,
    "Windgrace's Judgment": 0.8,
    "Braids, Arisen Nightmare": 0.6,
    "Faerie Mastermind": 0.9,
    "Ishai, Ojutai Dragonspeaker": 1.0,
    "Kediss, Emberclaw Familiar": 1.2,
    "Guttersnipe": 1.1,
    "Farewell": 0.7,
    "Blasphemous Act": 0.6,
    "Chain Reaction": 0.6,
    "Pest Infestation": 0.5,
    "Culling Ritual": 0.7,
}


MECHANIC_TAGS_BY_CARD: dict[str, frozenset[StructuralMechanic]] = {
    # Korvold: independent resource, rebuild, sacrifice and table-compression axes.
    "Korvold, Fae-Cursed King": frozenset(
        {
            StructuralMechanic.SACRIFICE_COST,
            StructuralMechanic.SACRIFICE_PAYOFF,
            StructuralMechanic.COMMANDER_DEPENDENT,
        }
    ),
    "Mirkwood Bats": frozenset(
        {
            StructuralMechanic.SACRIFICE_PAYOFF,
            StructuralMechanic.TABLE_DAMAGE,
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Exsanguinate": frozenset(
        {
            StructuralMechanic.TABLE_DAMAGE,
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Massacre Wurm": frozenset(
        {
            StructuralMechanic.TABLE_DAMAGE,
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Mayhem Devil": frozenset(
        {StructuralMechanic.SACRIFICE_PAYOFF, StructuralMechanic.COMMANDER_INDEPENDENT}
    ),
    "Goblin Bombardment": frozenset(
        {
            StructuralMechanic.SACRIFICE_OUTLET,
            StructuralMechanic.SACRIFICE_PAYOFF,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Zuran Orb": frozenset(
        {
            StructuralMechanic.SACRIFICE_COST,
            StructuralMechanic.SACRIFICE_OUTLET,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Ophiomancer": frozenset(
        {
            StructuralMechanic.TOKEN_ENGINE,
            StructuralMechanic.REPEATABLE_TOKEN_SOURCE,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Tireless Provisioner": frozenset(
        {
            StructuralMechanic.TOKEN_ENGINE,
            StructuralMechanic.REPEATABLE_TOKEN_SOURCE,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Academy Manufactor": frozenset(
        {
            StructuralMechanic.TOKEN_ENGINE,
            StructuralMechanic.ARTIFACT_ENGINE,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Mazirek, Kraul Death Priest": frozenset(
        {
            StructuralMechanic.SACRIFICE_PAYOFF,
            StructuralMechanic.GO_WIDE,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Szarel, Genesis Shepherd": frozenset(
        {
            StructuralMechanic.SACRIFICE_PAYOFF,
            StructuralMechanic.GO_WIDE,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Aftermath Analyst": frozenset(
        {
            StructuralMechanic.LAND_RECURSION,
            StructuralMechanic.GRAVEYARD_RECURSION,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Splendid Reclamation": frozenset(
        {
            StructuralMechanic.LAND_RECURSION,
            StructuralMechanic.GRAVEYARD_RECURSION,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Ramunap Excavator": frozenset(
        {
            StructuralMechanic.LAND_RECURSION,
            StructuralMechanic.GRAVEYARD_RECURSION,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Soul of Windgrace": frozenset(
        {
            StructuralMechanic.LAND_RECURSION,
            StructuralMechanic.GRAVEYARD_RECURSION,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Titania, Protector of Argoth": frozenset(
        {
            StructuralMechanic.LAND_RECURSION,
            StructuralMechanic.TOKEN_ENGINE,
            StructuralMechanic.GO_WIDE,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Hearthhull, the Worldseed": frozenset(
        {
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.REBUILD,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    # RogShai: commander-damage and independent table-reach are deliberately distinct.
    "Ishai, Ojutai Dragonspeaker": frozenset(
        {StructuralMechanic.COMMANDER_DAMAGE_SUPPORT, StructuralMechanic.COMMANDER_DEPENDENT}
    ),
    "Jeska, Thrice Reborn": frozenset(
        {
            StructuralMechanic.COMMANDER_DAMAGE_SUPPORT,
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.COMMANDER_DEPENDENT,
        }
    ),
    "Kediss, Emberclaw Familiar": frozenset(
        {
            StructuralMechanic.TABLE_DAMAGE,
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.COMMANDER_DEPENDENT,
        }
    ),
    "Duelist's Heritage": frozenset(
        {StructuralMechanic.COMMANDER_DAMAGE_SUPPORT, StructuralMechanic.COMMANDER_DEPENDENT}
    ),
    "Psychotic Fury": frozenset(
        {StructuralMechanic.COMMANDER_DAMAGE_SUPPORT, StructuralMechanic.COMMANDER_DEPENDENT}
    ),
    "Boros Charm": frozenset(
        {StructuralMechanic.COMMANDER_DAMAGE_SUPPORT, StructuralMechanic.STACK_INTERACTION}
    ),
    "Sunhome, Fortress of the Legion": frozenset(
        {StructuralMechanic.COMMANDER_DAMAGE_SUPPORT, StructuralMechanic.COMMANDER_DEPENDENT}
    ),
    "Combat Research": frozenset({StructuralMechanic.COMMANDER_DEPENDENT}),
    "Curiosity": frozenset({StructuralMechanic.COMMANDER_DEPENDENT}),
    "Staggering Insight": frozenset({StructuralMechanic.COMMANDER_DEPENDENT}),
    "Guttersnipe": frozenset(
        {
            StructuralMechanic.TABLE_DAMAGE,
            StructuralMechanic.FINISHER_COMPRESSION,
            StructuralMechanic.COMMANDER_INDEPENDENT,
        }
    ),
    "Kykar, Wind's Fury": frozenset(
        {StructuralMechanic.TOKEN_ENGINE, StructuralMechanic.COMMANDER_INDEPENDENT}
    ),
    "Whirlwind of Thought": frozenset({StructuralMechanic.COMMANDER_INDEPENDENT}),
    "Archmage Emeritus": frozenset({StructuralMechanic.COMMANDER_INDEPENDENT}),
    "Silence": frozenset(
        {StructuralMechanic.STACK_INTERACTION, StructuralMechanic.FINISHER_COMPRESSION}
    ),
    "Counterspell": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "Dovin's Veto": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "An Offer You Can't Refuse": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "Arcane Denial": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "Negate": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "Refute": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "Wash Away": frozenset({StructuralMechanic.STACK_INTERACTION}),
    "Bastion Protector": frozenset({StructuralMechanic.COMMANDER_DEPENDENT}),
    "Lightning Greaves": frozenset({StructuralMechanic.COMMANDER_DAMAGE_SUPPORT}),
    "Swiftfoot Boots": frozenset({StructuralMechanic.COMMANDER_DAMAGE_SUPPORT}),
}


CARD_SOURCE_URLS: dict[str, str] = {
    "Exploration Broodship": "https://mtg.wtf/card/eoc/14/Exploration-Broodship",
    "Hearthhull, the Worldseed": "https://mtg.wtf/card/eoc/1/Hearthhull-the-Worldseed",
    "Szarel, Genesis Shepherd": "https://mtg.wtf/card/eoc/4/Szarel-Genesis-Shepherd",
    "Evendo Brushrazer": "https://mtg.wtf/card/eoc/10/Evendo-Brushrazer",
    "Scouring Swarm": "https://mtg.wtf/card/eoc/36/Scouring-Swarm",
}


LAND_PRODUCES: dict[str, frozenset[Color]] = {
    "Plains": frozenset({Color.WHITE}),
    "Island": frozenset({Color.BLUE}),
    "Swamp": frozenset({Color.BLACK}),
    "Mountain": frozenset({Color.RED}),
    "Forest": frozenset({Color.GREEN}),
    "Bojuka Bog": frozenset({Color.BLACK}),
    "Eumidian Hatchery": frozenset({Color.BLACK}),
    "Canyon Slough": frozenset({Color.BLACK, Color.RED}),
    "Smoldering Marsh": frozenset({Color.BLACK, Color.RED}),
    "Sulfurous Springs": frozenset({Color.BLACK, Color.RED}),
    "Llanowar Wastes": frozenset({Color.BLACK, Color.GREEN}),
    "Twilight Mire": frozenset({Color.BLACK, Color.GREEN}),
    "Vernal Fen": frozenset({Color.BLACK, Color.GREEN}),
    "Cinder Glade": frozenset({Color.RED, Color.GREEN}),
    "Karplusan Forest": frozenset({Color.RED, Color.GREEN}),
    "Adarkar Wastes": frozenset({Color.WHITE, Color.BLUE}),
    "Glacial Fortress": frozenset({Color.WHITE, Color.BLUE}),
    "Port Town": frozenset({Color.WHITE, Color.BLUE}),
    "Prairie Stream": frozenset({Color.WHITE, Color.BLUE}),
    "Shivan Reef": frozenset({Color.BLUE, Color.RED}),
    "Sulfur Falls": frozenset({Color.BLUE, Color.RED}),
    "Battlefield Forge": frozenset({Color.WHITE, Color.RED}),
    "Clifftop Retreat": frozenset({Color.WHITE, Color.RED}),
    "Temple of Enlightenment": frozenset({Color.WHITE, Color.BLUE}),
    "Skycloud Expanse": frozenset({Color.WHITE, Color.BLUE}),
    "Turbulent Springs": frozenset({Color.BLUE, Color.RED}),
    "Sunhome, Fortress of the Legion": frozenset({Color.WHITE, Color.RED}),
}
ALL_COLORS = frozenset(Color)
FLEXIBLE_LANDS = {
    "Command Tower",
    "Exotic Orchard",
    "Fabled Passage",
    "Evolving Wilds",
    "Terramorphic Expanse",
    "Jund Panorama",
    "Cabaretti Courtyard",
    "Escape Tunnel",
    "Mountain Valley",
    "Riveteers Overlook",
    "Rocky Tar Pit",
    "Demolition Field",
    "Opal Palace",
}


# Canonical 2026-08-07 current-deck additions. These are structural role
# classifications only; they do not claim full Oracle/rules-engine equivalence.
ROLE_GROUPS[CardRole.RAMP].update({"Explore", "Talisman of Creativity"})
ROLE_GROUPS[CardRole.DRAW].update(
    {
        "Explore",
        "Ichor Wellspring",
        "Idol of Oblivion",
        "Vampiric Rites",
        "Aerial Extortionist",
        "Aether Spellbomb",
        "Arcane Denial",
        "Archmage Emeritus",
        "Chart a Course",
        "Finale of Revelation",
        "Opt",
        "Psychosis Crawler",
        "Refute",
        "Thirst for Knowledge",
    }
)
ROLE_GROUPS[CardRole.SELECTION].update(
    {"Chart a Course", "Opt", "Prismari Charm", "Prismari Command", "Thirst for Knowledge"}
)
ROLE_GROUPS[CardRole.REMOVAL].update(
    {
        "Gix's Command",
        "Profane Command",
        "Aerial Extortionist",
        "Aether Spellbomb",
        "Prismari Charm",
        "Prismari Command",
        "Resculpt",
    }
)
ROLE_GROUPS[CardRole.COUNTER].update({"Arcane Denial", "Dispel", "Refute"})
ROLE_GROUPS[CardRole.PROTECTION].update({"Lightning Greaves"})
ROLE_GROUPS[CardRole.WIPE].update({"Gix's Command", "Fumigate"})
ROLE_GROUPS[CardRole.RECURSION].update({"Grim Discovery", "Profane Command"})
ROLE_GROUPS[CardRole.GRAVEYARD_HATE].update({"Necrogenesis", "Angel of Finality"})
ROLE_GROUPS[CardRole.ENGINE].update(
    {
        "Ichor Wellspring",
        "Idol of Oblivion",
        "Vampiric Rites",
        "Archmage Emeritus",
        "Psychosis Crawler",
    }
)
ROLE_GROUPS[CardRole.ENABLER].update({"Lightning Greaves", "Necrogenesis", "Aether Spellbomb"})
ROLE_GROUPS[CardRole.PAYOFF].update({"Profane Command", "Psychosis Crawler"})
ROLE_GROUPS[CardRole.FINISHER].update(
    {"Profane Command", "Finale of Revelation", "Psychosis Crawler"}
)
ROLE_GROUPS[CardRole.SACRIFICE_OUTLET].update({"Vampiric Rites"})
ROLE_GROUPS[CardRole.TOKEN_SOURCE].update({"Necrogenesis"})

PERMANENT_EXCEPTIONS.update(
    {
        "Explore",
        "Gix's Command",
        "Grim Discovery",
        "Profane Command",
        "Arcane Denial",
        "Chart a Course",
        "Dispel",
        "Finale of Revelation",
        "Fumigate",
        "Opt",
        "Prismari Charm",
        "Prismari Command",
        "Refute",
        "Resculpt",
        "Thirst for Knowledge",
    }
)

LAND_PRODUCES.update(
    {
        "Festering Thicket": frozenset({Color.BLACK, Color.GREEN}),
        "Sheltered Thicket": frozenset({Color.RED, Color.GREEN}),
        "Cascade Bluffs": frozenset({Color.BLUE, Color.RED}),
        "Frostboil Snarl": frozenset({Color.BLUE, Color.RED}),
        "Irrigated Farmland": frozenset({Color.WHITE, Color.BLUE}),
        "Scorched Geyser": frozenset({Color.BLUE, Color.RED}),
    }
)
FLEXIBLE_LANDS.update({"Cryptic Caves", "Myriad Landscape"})
HIGH_IMMEDIATE.update(
    {
        "Gix's Command",
        "Arcane Denial",
        "Dispel",
        "Fumigate",
        "Prismari Charm",
        "Prismari Command",
        "Refute",
        "Resculpt",
    }
)
MULTIPLAYER_SCALING.update({"Aerial Extortionist": 0.7, "Psychosis Crawler": 1.1, "Fumigate": 0.6})


def _roles_for(card: CardIdentity) -> frozenset[CardRole]:
    roles = {role for role, names in ROLE_GROUPS.items() if card.oracle_name in names}
    is_land = "Land" in card.type_line or card.is_basic_land
    if is_land:
        roles.add(CardRole.MANA_SOURCE)
    text = (card.oracle_text or "").casefold()
    if "counter target spell" in text:
        roles.add(CardRole.COUNTER)
    if any(
        token in text
        for token in ("draw a card", "draw two cards", "draw three cards", "draw x cards")
    ):
        roles.add(CardRole.DRAW)
    if any(
        token in text
        for token in ("scry ", "surveil ", "look at the top", "discard a card, then draw")
    ):
        roles.add(CardRole.SELECTION)
    if any(
        token in text
        for token in (
            "destroy target",
            "exile target",
            "return target nonland",
            "return target creature",
        )
    ):
        roles.add(CardRole.REMOVAL)
    if any(token in text for token in ("destroy all", "exile all", "each creature gets -")):
        roles.update({CardRole.REMOVAL, CardRole.WIPE})
    if "return target" in text and "graveyard" in text:
        roles.add(CardRole.RECURSION)
    if "exile" in text and "graveyard" in text:
        roles.add(CardRole.GRAVEYARD_HATE)
    if "create " in text and " token" in text:
        roles.add(CardRole.TOKEN_SOURCE)
    if any(
        token in text for token in ("hexproof", "indestructible", "phase out", "protection from")
    ):
        roles.add(CardRole.PROTECTION)
    if "add " in text and "mana" in text:
        roles.add(CardRole.RAMP)
    if "search your library" in text and "land card" in text and "battlefield" in text:
        roles.add(CardRole.RAMP)
    if "sacrifice another" in text or "sacrifice a creature:" in text:
        roles.add(CardRole.SACRIFICE_OUTLET)
    if ("whenever " in text or "at the beginning" in text) and roles.intersection(
        {CardRole.DRAW, CardRole.TOKEN_SOURCE, CardRole.RAMP, CardRole.PAYOFF}
    ):
        roles.add(CardRole.ENGINE)
    if not roles:
        roles.add(CardRole.ENABLER)
    return frozenset(roles)


def _mana_value(card: CardIdentity, roles: frozenset[CardRole]) -> float:
    if "Land" in card.type_line or card.is_basic_land:
        return 0.0
    if card.oracle_name in MANA_VALUES:
        return MANA_VALUES[card.oracle_name]
    if card.mana_value is not None:
        return card.mana_value
    if CardRole.WIPE in roles or CardRole.FINISHER in roles:
        return 5.0
    if roles.intersection(
        {CardRole.COUNTER, CardRole.PROTECTION, CardRole.REMOVAL, CardRole.SELECTION}
    ):
        return 2.0
    if CardRole.RAMP in roles:
        return 2.0
    return 3.0


def _color_requirements(card: CardIdentity, mana_value: float) -> dict[Color, int]:
    if mana_value <= 0:
        return {}
    return {color: 1 for color in sorted(card.color_identity, key=lambda item: item.value)}


def build_default_profile(card: CardIdentity) -> StructuralCardProfile:
    roles = _roles_for(card)
    is_land = "Land" in card.type_line or card.is_basic_land
    mana_value = _mana_value(card, roles)
    produced = LAND_PRODUCES.get(card.oracle_name, frozenset())
    if card.oracle_name in FLEXIBLE_LANDS:
        produced = ALL_COLORS
    if card.oracle_name in {
        "Arcane Signet",
        "Fellwar Stone",
        "Relic of Legends",
        "Springleaf Drum",
    }:
        produced = ALL_COLORS
    if card.oracle_name == "Talisman of Progress" or card.oracle_name == "Azorius Signet":
        produced = frozenset({Color.WHITE, Color.BLUE})
    if card.oracle_name == "Izzet Signet":
        produced = frozenset({Color.BLUE, Color.RED})
    if card.oracle_name == "Boros Signet":
        produced = frozenset({Color.WHITE, Color.RED})
    if card.oracle_name in {"Llanowar Elves", "Ignoble Hierarch", "Nature's Lore", "Farseek"}:
        produced = frozenset({Color.GREEN}) if card.oracle_name == "Llanowar Elves" else ALL_COLORS
    role_strengths = {role: 1.0 for role in roles}
    role_strengths.update(ROLE_STRENGTH_OVERRIDES.get(card.oracle_name, {}))
    commander_synergy = 0.0
    if (
        card.oracle_name in ROLE_GROUPS[CardRole.LAND_SYNERGY]
        or card.oracle_name in ROLE_GROUPS[CardRole.SACRIFICE_OUTLET]
    ):
        commander_synergy = 0.7
    if card.oracle_name in {
        "Combat Research",
        "Curiosity",
        "Staggering Insight",
        "Kediss, Emberclaw Familiar",
        "Jeska, Thrice Reborn",
        "Duelist's Heritage",
        "Blackblade Reforged",
    }:
        commander_synergy = 0.9
    immediate = (
        1.1
        if card.oracle_name in HIGH_IMMEDIATE
        else (0.8 if card.oracle_name not in HIGH_TURN_CYCLE_RISK else 0.35)
    )
    turn_risk = (
        0.8
        if card.oracle_name in HIGH_TURN_CYCLE_RISK
        else (0.15 if card.oracle_name in HIGH_IMMEDIATE else 0.45)
    )
    floor = 0.45
    if roles.intersection(
        {CardRole.REMOVAL, CardRole.COUNTER, CardRole.PROTECTION, CardRole.RAMP, CardRole.DRAW}
    ):
        floor = 0.85
    if roles == frozenset({CardRole.ENABLER}):
        floor = 0.35
    conditionals: list[ConditionalStrength] = []
    if CardRole.LAND_SYNERGY in roles:
        conditionals.append(ConditionalStrength(condition="land_engine_online", multiplier=1.35))
    if CardRole.SACRIFICE_OUTLET in roles or CardRole.PAYOFF in roles:
        conditionals.append(
            ConditionalStrength(condition="sacrifice_package_online", multiplier=1.35)
        )
    if CardRole.COMBAT_PAYOFF in roles:
        conditionals.append(ConditionalStrength(condition="commander_attacking", multiplier=1.45))
    if CardRole.ENGINE in roles:
        conditionals.append(ConditionalStrength(condition="survives_turn_cycle", multiplier=1.25))
    sources: tuple[SourceRef, ...] = ()
    quality = card.data_quality
    source_url = CARD_SOURCE_URLS.get(card.oracle_name)
    if source_url is not None:
        sources = (
            SourceRef(
                source_type="card_database",
                source_name="mtg.wtf",
                source_path=source_url,
                quality=DataQuality.PROJECT_VERIFIED,
            ),
        )
    if card.oracle_name in {
        "Exploration Broodship",
        "Hearthhull, the Worldseed",
        "Szarel, Genesis Shepherd",
        "Eumidian Hatchery",
        "Evendo Brushrazer",
        "Scouring Swarm",
    }:
        quality = DataQuality.PROJECT_VERIFIED
    return StructuralCardProfile(
        oracle_name=card.oracle_name,
        mana_value=mana_value,
        roles=roles,
        role_strengths=role_strengths,
        mechanic_tags=MECHANIC_TAGS_BY_CARD.get(card.oracle_name, frozenset()),
        color_requirements=_color_requirements(card, mana_value),
        produces_colors=produced,
        is_land=is_land,
        is_permanent=card.oracle_name not in PERMANENT_EXCEPTIONS,
        is_creature=("Creature" in card.type_line or card.oracle_name in BASE_POWER),
        base_power=BASE_POWER.get(card.oracle_name, 0.0),
        commander_synergy=commander_synergy,
        floor_value=floor,
        immediate_impact=immediate,
        turn_cycle_risk=turn_risk,
        multiplayer_scaling=MULTIPLAYER_SCALING.get(card.oracle_name, 0.0),
        conditional_strength=tuple(conditionals),
        source_quality=quality,
        sources=sources,
        notes="Structural abstraction; not a claim of full rules equivalence.",
    )


class StructuralProfileCatalog:
    def __init__(self, profiles: Iterable[StructuralCardProfile]) -> None:
        self._profiles = {profile.oracle_name: profile for profile in profiles}

    @classmethod
    def from_json(cls, path: str | Path) -> StructuralProfileCatalog:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        raw = payload["profiles"] if isinstance(payload, dict) else payload
        return cls(StructuralCardProfile.model_validate(item) for item in raw)

    @classmethod
    def from_card_catalog(cls, catalog: CardCatalog) -> StructuralProfileCatalog:
        return cls(build_default_profile(card) for card in catalog.cards)

    def resolve(self, oracle_name: str) -> StructuralCardProfile:
        try:
            return self._profiles[oracle_name]
        except KeyError as exc:
            raise KeyError(f"missing structural profile for {oracle_name!r}") from exc

    @property
    def profiles(self) -> tuple[StructuralCardProfile, ...]:
        return tuple(
            sorted(self._profiles.values(), key=lambda profile: profile.oracle_name.casefold())
        )

    def save(self, path: str | Path, *, data_as_of: str, source_hash: str) -> None:
        payload = {
            "schema_version": "0.4.0",
            "estimate_type": "structural_model_estimates",
            "data_as_of": data_as_of,
            "source_hash": source_hash,
            "profile_count": len(self._profiles),
            "profiles": [profile.model_dump(mode="json") for profile in self.profiles],
        }
        Path(path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
            newline="\n",
        )


def build_structural_deck_profile(
    deck: Deck,
    profiles: StructuralProfileCatalog,
    *,
    data_snapshot_hash: str,
) -> StructuralDeckProfile:
    expanded: list[StructuralCardProfile] = []
    for entry in deck.cards:
        if entry.zone == DeckZone.MAYBEBOARD:
            continue
        expanded.extend(profiles.resolve(entry.oracle_name) for _ in range(entry.quantity))
    base_costs = {
        "Korvold, Fae-Cursed King": 5.0,
        "Ishai, Ojutai Dragonspeaker": 4.0,
        "Rograkh, Son of Rohgahh": 0.0,
    }
    base_power = {
        "Korvold, Fae-Cursed King": 4.0,
        "Ishai, Ojutai Dragonspeaker": 1.0,
        "Rograkh, Son of Rohgahh": 0.0,
    }
    strategy = "korvold" if "Korvold, Fae-Cursed King" in deck.commander.commanders else "rogshai"
    return StructuralDeckProfile(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash or compute_deck_hash(deck),
        commander_names=deck.commander.commanders,
        cards=tuple(expanded),
        commander_base_costs={
            name: base_costs.get(name, 4.0) for name in deck.commander.commanders
        },
        commander_base_power={
            name: base_power.get(name, 2.0) for name in deck.commander.commanders
        },
        commander_strategy=strategy,
        data_snapshot_hash=data_snapshot_hash,
    )


def generate_project_profiles(root: str | Path) -> Path:
    root_path = Path(root)
    oracle_path = root_path / "data/cards/oracle_subset.json"
    catalog = CardCatalog.from_json(oracle_path)
    profiles = StructuralProfileCatalog.from_card_catalog(catalog)
    source_hash = compute_data_snapshot_hash([oracle_path], root=root_path)
    output = root_path / "data/cards/structural_role_profiles.json"
    profiles.save(output, data_as_of="2026-08-09", source_hash=source_hash)
    return output


def role_counts(deck_profile: StructuralDeckProfile) -> Counter[CardRole]:
    counts: Counter[CardRole] = Counter()
    for card in deck_profile.cards:
        counts.update(card.roles)
    return counts
