import copy
import hashlib
import json
import pathlib
import re
from collections import Counter, OrderedDict

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "qualification/materialization"
OUT.mkdir(parents=True, exist_ok=True)

BASE_SHA = "362d9351f749b6f49d67cd1ef4eed298b8922b68"
BASE_TREE = "e510af2fd8a05f7db874781e3182a6bf3c062fc4"
MAIN_SHA = "c83e52ae79ff2242578757c0f517badbb1a2621c"
MAIN_TREE = "551c0d55a171508618d2b7d29e0f49b19893f886"
COMMON_SHA = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"
CR_SHA = "9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c"
SCHEMA_ID = "commander-lab.semantic-fixture-materialization/1.0.0"
RSP = "commander-lab.rules-service/1.1.0"
SEED = 424242

CATEGORY_IDS = OrderedDict(
    [
        ("player_count", [f"PLAYER_COUNT_{n}P" for n in range(2, 6)]),
        (
            "pilot_boundary",
            [
                "PILOT_PRIORITY",
                "PILOT_TARGET",
                "PILOT_CHOOSE_OBJECT",
                "PILOT_TARGET_AMOUNT",
                "PILOT_MULLIGAN",
                "PILOT_CHOOSE_USE",
                "PILOT_CHOICE",
                "PILOT_PILE",
                "PILOT_MANA_PAYMENT",
                "PILOT_ANNOUNCE_X",
                "PILOT_MULTI_AMOUNT",
                "PILOT_REPLACEMENT_EFFECT",
                "PILOT_TRIGGER_ORDER",
                "PILOT_CHOOSE_MODE",
                "PILOT_CHOOSE_ABILITY",
                "PILOT_DECLARE_ATTACKER",
                "PILOT_DECLARE_BLOCKER",
            ],
        ),
        (
            "pilot_boundary_negative",
            [
                "NEGATIVE_FIRST_OPTION",
                "NEGATIVE_RANDOM_OPTION",
                "NEGATIVE_DEFAULT_YES_NO",
                "NEGATIVE_INTERNAL_AI",
                "NEGATIVE_GUI_DEFAULT",
                "NEGATIVE_SILENT_SKIP",
                "NEGATIVE_PARENT_CLASS_FALLBACK",
            ],
        ),
        (
            "hidden_information",
            [f"HIDDEN_{i:02d}" for i in range(1, 20)] + ["HIDDEN_HONEYCARD_SENTINEL"],
        ),
        (
            "replay_rng",
            [
                "RNG_RULES_TAPE",
                "REPLAY_DECISION_TAPE",
                "REPLAY_EVENT_TAPE",
                "REPLAY_CLEAN_PROCESS",
                "REPLAY_STATE_HASHES",
            ],
        ),
        (
            "micro_rules",
            [
                "MICRO_COSTS",
                "MICRO_MANA_PAYMENT",
                "MICRO_PRIORITY",
                "MICRO_STACK",
                "MICRO_TARGETS",
                "MICRO_MODES",
                "MICRO_TRIGGERS",
                "MICRO_REPLACEMENT",
                "MICRO_PREVENTION",
                "MICRO_CONTINUOUS_EFFECTS",
                "MICRO_LAYERS",
                "MICRO_STATE_BASED_ACTIONS",
                "MICRO_ZONE_CHANGES",
                "MICRO_COPY",
                "MICRO_CONTROL",
                "MICRO_COMBAT",
                "MICRO_RULES_RANDOMNESS",
            ],
        ),
        ("actual_card", [f"CARD_{i:02d}" for i in range(1, 30)]),
        (
            "multiplayer_commander",
            [
                "WS05-MP-PRIO-3",
                "WS05-MP-PRIO-5",
                "WS05-MP-TRIG-3",
                "WS05-MP-TRIG-5",
                "WS05-MP-COMBAT-4",
                "WS05-MP-COMBAT-5",
                "WS05-MP-BLOCK-4",
                "WS05-MP-TURN-3",
                "WS05-MP-TURN-5",
                "WS05-MP-ELIM-OWNED-3",
                "WS05-MP-ELIM-CONTROL-3",
                "WS05-MP-ELIM-STACK-3",
                "WS05-MP-ELIM-PRIO-3",
                "WS05-MP-ELIM-TURN-3",
                "WS05-MP-ELIM-5",
                "WS05-CMD-TAX-2",
                "WS05-CMD-TAX-4",
                "WS05-CMD-ZONE-GY-YES",
                "WS05-CMD-ZONE-GY-NO",
                "WS05-CMD-ZONE-EXILE-YES",
                "WS05-CMD-ZONE-EXILE-NO",
                "WS05-CMD-ZONE-HAND-YES",
                "WS05-CMD-ZONE-HAND-NO",
                "WS05-CMD-ZONE-LIB-YES",
                "WS05-CMD-ZONE-LIB-NO",
                "WS05-CMD-DMG-SAME-21",
                "WS05-CMD-DMG-SPLIT",
                "WS05-CMD-DMG-CONTROL",
                "WS05-CMD-PARTNER-TAX",
                "WS05-CMD-PARTNER-DMG",
                "WS05-CMD-PARTNER-ZONE",
                "WS05-CMD-MULL-2",
                "WS05-CMD-MULL-4",
                "WS05-CMD-START-2",
                "WS05-CMD-START-3",
                "WS05-CMD-ELIM-4",
            ],
        ),
    ]
)
ALL_IDS = [x for xs in CATEGORY_IDS.values() for x in xs]
assert len(ALL_IDS) == 135 and len(set(ALL_IDS)) == 135

STARTER18 = [
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "HIDDEN_01",
    "HIDDEN_02",
    "MICRO_STACK",
    "MICRO_REPLACEMENT",
    "WS05-MP-COMBAT-4",
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
    "CARD_02",
]
FORGE_ONLY = [
    "MICRO_COMBAT",
    "MICRO_COSTS",
    "MICRO_MANA_PAYMENT",
    "MICRO_PREVENTION",
    "MICRO_PRIORITY",
    "MICRO_RULES_RANDOMNESS",
    "MICRO_TARGETS",
    "MICRO_TRIGGERS",
    "MICRO_ZONE_CHANGES",
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
    "PILOT_MANA_PAYMENT",
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_TRIGGER_ORDER",
    "WS05-CMD-ZONE-HAND-YES",
    "WS05-MP-BLOCK-4",
]
XMAGE_ONLY = [
    "CARD_04",
    "CARD_24",
    "HIDDEN_03",
    "HIDDEN_14",
    "HIDDEN_15",
    "HIDDEN_16",
    "HIDDEN_18",
    "HIDDEN_19",
    "HIDDEN_HONEYCARD_SENTINEL",
    "MICRO_CONTINUOUS_EFFECTS",
    "NEGATIVE_PARENT_CLASS_FALLBACK",
    "PILOT_CHOICE",
    "PILOT_CHOOSE_OBJECT",
    "PILOT_CHOOSE_USE",
    "WS05-CMD-TAX-4",
    "WS05-MP-TRIG-3",
]
UNION50 = STARTER18 + FORGE_ONLY + XMAGE_ONLY
assert len(UNION50) == 50 and len(set(UNION50)) == 50

CARD_SPEC = {
    "CARD_01": (
        "Ishai, Ojutai Dragonspeaker",
        ["P1 controls Ishai with zero +1/+1 counters.", "P2 casts Lightning Bolt."],
        ["P2 casts obj:card01-bolt."],
        ["spell_cast:P2", "trigger:Ishai", "counter_change:+1/+1:+1"],
        ["obj:card01-ishai has exactly one +1/+1 counter."],
    ),
    "CARD_02": (
        "Rograkh, Son of Rohgahh",
        ["Rograkh is P1 commander in command zone with prior command-zone cast count 0."],
        ["P1 casts commander cmd:P1-A from command zone."],
        ["commander_cast", "spell_resolved", "creature_entered"],
        [
            "Rograkh is on P1 battlefield.",
            "commander cast count cmd:P1-A = 1.",
            "No commander-tax increment was charged.",
        ],
    ),
    "CARD_03": (
        "Esior, Wardwing Familiar",
        [
            "P1 controls Esior and two commanders.",
            "P2 has a spell capable of targeting both P1 commanders; pre-Esior total cost is known.",
        ],
        ["P2 announces the spell targeting both commanders."],
        ["spell_announced", "targets_locked", "total_cost_determined"],
        ["Total cost is pre-Esior total + exactly {3} generic, not +{6}."],
    ),
    "CARD_04": (
        "Kediss, Emberclaw Familiar",
        ["P1 controls Kediss and a 3-power commander.", "P2/P3/P4 start at 20 life."],
        ["P1 attacks P2 with that commander; no blocks."],
        [
            "commander_combat_damage:P2:3",
            "Kediss_trigger",
            "noncombat_damage:P3:3",
            "noncombat_damage:P4:3",
        ],
        [
            "P2=P3=P4=17 life.",
            "Only P2 gained commander combat damage; Kediss damage does not retrigger Kediss.",
        ],
    ),
    "CARD_05": (
        "Veyran, Voice of Duality",
        [
            "P1 controls Veyran with no temporary P/T modification.",
            "P1 has Lightning Bolt in hand.",
        ],
        ["P1 casts Lightning Bolt."],
        ["instant_cast", "Veyran_magecraft_trigger", "Veyran_additional_trigger"],
        ["After both triggers resolve Veyran has +2/+2 until end of turn."],
    ),
    "CARD_06": (
        "Harmonic Prodigy",
        [
            "P1 controls Harmonic Prodigy and Docent of Perfection; no other trigger multipliers apply.",
            "P1 has Lightning Bolt in hand.",
        ],
        [
            "P1 casts Lightning Bolt, causing Docent of Perfection to trigger once before Harmonic Prodigy modifies the trigger count."
        ],
        ["Wizard_trigger_event", "additional_trigger"],
        [
            "Exactly two Docent of Perfection trigger instances are created for the single instant cast."
        ],
    ),
    "CARD_07": (
        "Narset, Parter of Veils",
        [
            "P1 controls Narset.",
            "P2 has drawn zero cards this turn.",
            "Divination resolving for P2 instructs two draws.",
        ],
        ["Resolve the two-card draw instruction."],
        ["draw_attempt:1", "draw_card", "draw_attempt:2", "draw_disallowed"],
        ["P2 draws exactly one card."],
    ),
    "CARD_08": (
        "Jeska, Thrice Reborn",
        [
            "P1 has cast a commander from command zone exactly twice this game.",
            "P1 casts/resolves Jeska and controls an unblocked 2-power creature.",
        ],
        [
            "Resolve Jeska entering.",
            "Activate Jeska 0 ability targeting obj:card08-attacker.",
            "Attack P2 with that creature.",
        ],
        ["Jeska_enters_loyalty:2", "loyalty_ability:0", "combat_damage_replaced:2->6"],
        [
            "Jeska enters with two loyalty counters.",
            "P2 is dealt 6 combat damage by the affected creature.",
        ],
    ),
    "CARD_09": (
        "Magma Opus",
        [
            "P1 has Magma Opus in hand and can pay its cost.",
            "P2 is a damage target; P3 controls a creature damage target; P4 controls two distinct untapped permanents; P1 library has at least two cards.",
        ],
        [
            "Cast Magma Opus.",
            "Assign 2 damage to P2 and 2 to obj:card09-p3-creature.",
            "Choose obj:card09-p4-a and obj:card09-p4-b as tap targets.",
        ],
        [
            "damage:P2:2",
            "damage:obj:card09-p3-creature:2",
            "tap:obj:card09-p4-a",
            "tap:obj:card09-p4-b",
            "token_created:4/4_Elemental",
            "draw:P1:2",
        ],
        [
            "P2 lost 2 life.",
            "Both selected P4 permanents are tapped.",
            "P1 controls one new 4/4 blue/red Elemental and drew two cards.",
        ],
    ),
    "CARD_10": (
        "Wash Away",
        [
            "P2 commander spell is on stack, cast from command zone.",
            "P1 has Wash Away in hand and can pay normal non-cleave cost.",
        ],
        ["P1 casts Wash Away without cleave targeting the commander spell."],
        ["commander_spell_targeted", "Wash_Away_resolves", "spell_countered"],
        ["P2 commander spell is countered."],
    ),
    "CARD_11": (
        "Wear // Tear",
        ["P1 has Wear // Tear in hand.", "P2 controls Sol Ring and Glorious Anthem."],
        ["P1 casts both halves fused, targeting Sol Ring and Glorious Anthem."],
        ["fused_split_spell_cast", "destroy_artifact", "destroy_enchantment"],
        ["Both target permanents are in P2 graveyard."],
    ),
    "CARD_12": (
        "Dig Through Time",
        [
            "P1 has Dig Through Time in hand, six graveyard cards, at least seven library cards, and can pay UU."
        ],
        [
            "Cast Dig Through Time; exile exactly six graveyard cards via delve and pay UU.",
            "Choose obj:card12-lib1 and obj:card12-lib2 for hand; order remaining five on bottom.",
        ],
        ["delve_exile:6", "mana_paid:UU", "look_top:7", "put_hand:2", "put_bottom:5"],
        [
            "Exactly two looked-at cards are in hand and five are bottomed in chosen order.",
            "Dig Through Time mana value remains 8.",
        ],
    ),
    "CARD_13": (
        "Flare of Duplication",
        [
            "P1 controls a nontoken red creature and has Flare of Duplication in hand.",
            "P2 Lightning Bolt targeting P1 is on stack; P3 is another legal target for the copy.",
        ],
        [
            "P1 casts Flare by sacrificing obj:card13-red-creature.",
            "Choose P3 as new target for created copy.",
        ],
        ["alternative_cost_sacrifice", "copy_spell", "choose_new_target"],
        [
            "The copy exists on stack/resolution path with P3 target.",
            "Creating the copy did not create a cast event.",
        ],
    ),
    "CARD_14": (
        "Vandalblast",
        ["P1 controls Sol Ring; P2/P3/P4 each control one artifact.", "P1 can pay overload cost."],
        ["P1 casts Vandalblast for overload cost."],
        ["overload_cast", "destroy_each_opponent_artifact"],
        [
            "P2/P3/P4 artifacts are destroyed.",
            "P1 Sol Ring remains.",
            "The overloaded spell has no targets.",
        ],
    ),
    "CARD_15": (
        "Finale of Revelation",
        [
            "P1 has Finale of Revelation in hand, exactly three graveyard cards, at least ten drawable library cards after shuffle, and five tapped lands.",
            "P1 can cast Finale with X=10.",
        ],
        ["Choose X=10.", "Resolve and choose all five tapped lands to untap."],
        [
            "shuffle_graveyard_into_library",
            "draw:10",
            "untap_lands:5",
            "grant_no_max_hand_size",
            "exile_Finale",
        ],
        [
            "Pre-resolution graveyard cards were shuffled before draws.",
            "P1 drew 10, five lands untapped, no maximum hand size for rest of game, Finale exiled.",
        ],
    ),
    "CARD_16": (
        "Psychosis Crawler",
        [
            "P1 controls Psychosis Crawler and has three cards in hand.",
            "P2/P3/P4 start at 20 life.",
            "Divination will make P1 draw two cards sequentially.",
        ],
        ["Resolve both draws."],
        ["draw_card", "Crawler_trigger", "draw_card", "Crawler_trigger"],
        [
            "P1 hand size=5 and Crawler is 5/5 absent other modifiers.",
            "P2/P3/P4 are each at 18 life.",
        ],
    ),
    "CARD_17": (
        "Kaervek the Merciless",
        [
            "P1 controls Kaervek.",
            "P2 has Wrath of God (mana value 4) in hand with legal mana to cast it.",
            "P2 is a legal damage target.",
        ],
        ["P2 casts obj:card17-spell.", "P1 chooses P2 as Kaervek trigger target."],
        ["opponent_spell_cast", "Kaervek_trigger", "damage:P2:4"],
        [
            "P2 is dealt 4 damage by Kaervek before the triggering spell resolves if no responses intervene."
        ],
    ),
    "CARD_18": (
        "Shriekmaw",
        [
            "P1 has Shriekmaw in hand and can pay evoke.",
            "P2 controls Grizzly Bears, a legal nonartifact nonblack creature target.",
        ],
        [
            "P1 casts Shriekmaw for evoke.",
            "Target Grizzly Bears and order ETB before evoke sacrifice trigger.",
        ],
        [
            "evoke_cast",
            "Shriekmaw_enters",
            "destroy_trigger",
            "evoke_sacrifice_trigger",
            "destroy_target",
            "sacrifice_Shriekmaw",
        ],
        ["Grizzly Bears is destroyed and Shriekmaw is sacrificed."],
    ),
    "CARD_19": (
        "Butcher of Malakir",
        [
            "P1 controls Butcher of Malakir and Grizzly Bears.",
            "P2/P3/P4 each control one creature.",
        ],
        [
            "P1 activates Ashnod’s Altar, sacrificing obj:card19-p1-other as the activation cost.",
            "Each opponent chooses their creature to sacrifice when Butcher’s trigger resolves.",
        ],
        [
            "P1_creature_dies",
            "Butcher_trigger",
            "opponents_choose_sacrifices",
            "simultaneous_sacrifices",
        ],
        ["P2/P3/P4 each sacrificed exactly one creature."],
    ),
    "CARD_20": (
        "Syphon Mind",
        ["P2/P3/P4 each have at least one hand card.", "P1 has Syphon Mind resolving."],
        ["Each P2/P3/P4 chooses and discards one card."],
        ["discard:P2:1", "discard:P3:1", "discard:P4:1", "draw:P1:3"],
        ["Exactly three cards were discarded this way and P1 drew exactly three cards."],
    ),
    "CARD_21": (
        "Gratuitous Violence",
        [
            "P1 controls Gratuitous Violence and a 3-power creature.",
            "That creature is about to deal 3 damage to P2.",
        ],
        ["Resolve the damage event."],
        ["damage_would_be:3", "replacement_effect", "damage:P2:6"],
        ["P2 is dealt 6 damage, not 3."],
    ),
    "CARD_22": (
        "Bolt Bend",
        [
            "P1 controls a 4-power creature and can cast Bolt Bend.",
            "P2 Lightning Bolt with exactly one target P1 is on stack; P3 is another legal target.",
        ],
        ["P1 casts Bolt Bend targeting Lightning Bolt.", "Change Lightning Bolt target to P3."],
        ["cost_reduction:3", "Bolt_Bend_cast", "change_single_target"],
        ["The target spell has P3 as target; mode and other decisions are unchanged."],
    ),
    "CARD_23": (
        "Makeshift Mannequin",
        [
            "P1 has Grizzly Bears in graveyard and Makeshift Mannequin in hand.",
            "P1 has Lightning Bolt available after return.",
        ],
        [
            "Cast Makeshift Mannequin targeting Grizzly Bears.",
            "After return, cast Lightning Bolt targeting that creature.",
        ],
        [
            "return_creature_with_mannequin_counter",
            "creature_becomes_target",
            "granted_trigger",
            "sacrifice_returned_creature",
        ],
        [
            "Returned creature is sacrificed when granted trigger resolves before Lightning Bolt would resolve if no responses intervene."
        ],
    ),
    "CARD_24": (
        "Warstorm Surge",
        [
            "P1 controls Warstorm Surge.",
            "A 2/2 Grizzly Bears will enter under P1 control.",
            "P2 starts at 20 life.",
        ],
        ["Cause Grizzly Bears to enter.", "Choose P2 as Warstorm Surge target."],
        ["creature_enters", "Warstorm_trigger", "entering_creature_damage:P2:2"],
        ["P2 is at 18 life after trigger resolves."],
    ),
    "CARD_25": (
        "Basilisk Collar",
        [
            "P1 starts at 20 life and controls a 1/1 Soldier token equipped with Basilisk Collar.",
            "P2 controls a 5/5 creature able to block.",
        ],
        ["P1 attacks P2 with equipped creature; P2 blocks with 5/5."],
        [
            "combat_damage:1_to_blocker",
            "combat_damage:5_to_attacker",
            "lifelink_gain:P1:1",
            "deathtouch_SBA",
        ],
        [
            "P1 is at 21 life.",
            "P2 5/5 is destroyed by deathtouch SBA; P1 1/1 also dies absent other effects.",
        ],
    ),
    "CARD_26": (
        "Burn Down the House",
        ["P1 casts Burn Down the House with no copy/replacement effects."],
        ["Choose the Devil-token mode."],
        ["modal_choice:devils", "create_Devil_token:3", "grant_haste_until_EOT"],
        [
            "P1 controls exactly three new 1/1 red Devil tokens, each with printed death trigger and haste until EOT."
        ],
    ),
    "CARD_27": (
        "Path of Ancestry",
        [
            "P1 controls Path of Ancestry untapped and has Rograkh as commander (Kobold Warrior; red identity).",
            "P1 has a Warrior creature spell and top library card known.",
        ],
        [
            "Tap Path for red.",
            "Spend that mana to cast the Warrior spell.",
            "Resolve scry 1 and keep the top card.",
        ],
        ["mana_ability:red", "mana_spent_on_shared_type_creature", "scry:1"],
        ["P1 performs exactly one scry 1 from this mana expenditure."],
    ),
    "CARD_28": (
        "Find // Finality",
        [
            "P1 has Find // Finality in hand and controls Grizzly Bears with one +1/+1 counter (3/3).",
            "P2 controls a 4/4 creature.",
        ],
        ["P1 casts Finality half.", "Choose P1 Grizzly Bears to receive two +1/+1 counters."],
        [
            "cast_split_half:Finality",
            "put_+1/+1_counters:2",
            "continuous_-4/-4_all_creatures",
            "state_based_actions",
        ],
        [
            "P1 creature is 1/1 for remainder of turn absent other effects.",
            "P2 4/4 becomes 0/0 and is put into graveyard as SBA.",
        ],
    ),
    "CARD_29": (
        "Boseiju Reaches Skyward // Branch of Boseiju",
        [
            "P1 has Boseiju Reaches Skyward in hand; library contains two basic Forests; graveyard contains a Forest; land count is fixed for Branch P/T."
        ],
        [
            "Cast/resolve Saga.",
            "Chapter I choose two Forests.",
            "Chapter II target graveyard Forest.",
            "Chapter III resolve exile-and-return-transformed.",
        ],
        ["Saga_I", "Saga_II", "Saga_III", "exile_Saga", "return_transformed:Branch_of_Boseiju"],
        [
            "After chapter III Branch of Boseiju is on P1 battlefield transformed with reach and P/T equal to P1 current land count."
        ],
    ),
}
assert set(CARD_SPEC) == set(CATEGORY_IDS["actual_card"])

CARD_CR = {
    "CARD_01": ["603.2", "122", "702.124"],
    "CARD_02": ["903.8", "702.124", "202", "208"],
    "CARD_03": ["601.2f", "118", "702.124"],
    "CARD_04": ["603", "510", "120", "903.10a", "702.124"],
    "CARD_05": ["603.2d", "611.2a"],
    "CARD_06": ["603.2d"],
    "CARD_07": ["121.2b"],
    "CARD_08": ["122", "606", "614.1", "120.4b", "903.8"],
    "CARD_09": ["115", "601.2c", "608"],
    "CARD_10": ["702.148", "608", "903.8"],
    "CARD_11": ["709", "601"],
    "CARD_12": ["702.66", "601.2f", "202.3"],
    "CARD_13": ["601.2f", "707.10", "115.7d"],
    "CARD_14": ["702.96", "115"],
    "CARD_15": ["107.3", "608", "400"],
    "CARD_16": ["208", "603", "121"],
    "CARD_17": ["603", "202.3", "120"],
    "CARD_18": ["702.36", "702.74", "603", "704"],
    "CARD_19": ["603", "101.4"],
    "CARD_20": ["701", "121"],
    "CARD_21": ["614.1", "120.4b"],
    "CARD_22": ["601.2f", "115.7b", "115.8"],
    "CARD_23": ["603", "608", "122"],
    "CARD_24": ["603", "120"],
    "CARD_25": ["702.2", "702.15", "704"],
    "CARD_26": ["700.2", "111", "702.10"],
    "CARD_27": ["106", "701.22", "903.4"],
    "CARD_28": ["709", "122", "613", "704"],
    "CARD_29": ["712.8", "714.2", "208"],
}


# ---------- helpers ----------
def canonical_bytes(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(x):
    return hashlib.sha256(canonical_bytes(x)).hexdigest()


def obj(
    sid,
    card,
    owner,
    controller,
    zone,
    position=None,
    tapped=False,
    face_down=False,
    counters=None,
    attached_to=None,
    commander_id=None,
    lineage=None,
    notes=None,
):
    d = {
        "semantic_id": sid,
        "card_identity": card,
        "owner": owner,
        "controller": controller,
        "zone": zone,
        "tapped": tapped,
        "face_down": face_down,
        "counters": counters or {},
        "card_lineage_id": lineage or f"line:{sid}",
    }
    if position is not None:
        d["zone_position"] = position
    if attached_to:
        d["attached_to"] = attached_to
    if commander_id:
        d["commander_id"] = commander_id
    if notes:
        d["construction_notes"] = notes
    return d


def players(n, life=40):
    return [
        {
            "player_id": f"P{i}",
            "seat": i,
            "starting_life": life,
            "life": life,
            "poison": 0,
            "lost": False,
            "eliminated": False,
        }
        for i in range(1, n + 1)
    ]


def commander_state(n, partner=False):
    cs = []
    for i in range(1, n + 1):
        p = f"P{i}"
        cs.append(
            {
                "commander_id": f"cmd:{p}-A",
                "card_identity": "Rograkh, Son of Rohgahh",
                "owner": p,
                "zone": "command",
                "prior_command_zone_cast_count": 0,
            }
        )
        if partner and i == 1:
            cs.append(
                {
                    "commander_id": "cmd:P1-B",
                    "card_identity": "Kediss, Emberclaw Familiar",
                    "owner": "P1",
                    "zone": "command",
                    "prior_command_zone_cast_count": 0,
                    "partner_with": "cmd:P1-A",
                }
            )
    return {
        "commanders": cs,
        "commander_damage_matrix": [],
        "multiple_commander_relations": [
            {"commander_ids": ["cmd:P1-A", "cmd:P1-B"], "relation": "Partner"}
        ]
        if partner
        else [],
    }


def base_objects(n):
    return [
        obj(
            f"obj:{p}-commander",
            "Rograkh, Son of Rohgahh",
            p,
            p,
            "command",
            commander_id=f"cmd:{p}-A",
        )
        for p in [f"P{i}" for i in range(1, n + 1)]
    ]


def temporal(active="P1", phase="precombat_main", step="main", priority="P1", turn=1, extra=None):
    return {
        "turn_number": turn,
        "active_player": active,
        "phase": phase,
        "step": step,
        "priority_player": priority,
        "extra_turn_queue": extra or [],
    }


def knowledge_public(n):
    return {
        "viewer_states": [
            {
                "viewer": f"P{i}",
                "known_object_identities": [],
                "known_library_ranges": [],
                "temporary_permissions": [],
                "face_down_look_permissions": [],
                "invalidation_conditions": [],
            }
            for i in range(1, n + 1)
        ],
        "channel_policy": "RSP actor-aware observation applies to prompts, context, options, source/ability metadata, events, transcripts and logs.",
    }


def rng(seed=SEED, channels=None, pred=None):
    return {
        "rules_seed": seed,
        "channels": channels or [],
        "predetermined_semantic_draws": pred or [],
        "pilot_randomness_prohibited": True,
    }


def setup_validation():
    return {
        "construct_inside_rules_process": True,
        "native_structural_validation_required": True,
        "expose_normalized_constructed_state": True,
        "compare_requested_vs_constructed": True,
        "on_mismatch": "FAIL_CLOSED",
        "forbidden_external_rules": [
            "legality_calculation",
            "layers",
            "state_based_actions",
            "replacement_outcomes",
            "fabricated_legal_options",
            "silent_setup_correction",
        ],
    }


def normalization():
    return {
        "ignored_provider_local": [
            "raw_uuid",
            "jvm_object_id",
            "memory_identity",
            "internal_stack_object_identity",
            "engine_action_id",
            "process_id",
            "wall_clock",
        ],
        "retained_semantic": [
            "player_id",
            "semantic_object_id",
            "card_lineage_id",
            "commander_id",
            "owner",
            "controller",
            "zone",
            "zone_position_when_relevant",
            "counters",
            "attachments",
            "commander_cast_count",
            "commander_damage",
            "knowledge_permissions",
            "temporal_state",
            "semantic_event_actor_object_value",
            "rules_rng_operation",
        ],
        "stack_identity": "normalize by semantic source/controller/targets/modes/order, never provider object id",
    }


def decision(selector_kind, semantic_value, decision_family, actor="P1", notes=None):
    return {
        "decision_family": decision_family,
        "actor": actor,
        "selection": {
            "selector_kind": selector_kind,
            "semantic_value": semantic_value,
            "matches_only_provider_offered_legal_options": True,
            "on_zero_match": "FAIL_CLOSED",
            "on_multiple_match": "FAIL_CLOSED",
        },
        "forbidden_fallbacks": [
            "first_option",
            "random_option",
            "default_yes_no",
            "internal_ai",
            "gui_default",
            "silent_skip",
            "parent_class_fallback",
        ],
        "notes": notes or "",
    }


def event_assert(required=None, forbidden=None, ordering=None, partial=None):
    return {
        "required_events": required or [],
        "forbidden_events": forbidden or [],
        "ordering_constraints": ordering or [],
        "partial_order_constraints": partial or [],
    }


def player_count_for(fid):
    if fid.startswith("PLAYER_COUNT_"):
        return int(re.search(r"(\d)P$", fid).group(1))
    if fid.startswith("WS05-MP-"):
        m = re.search(r"-(\d)$", fid)
        return int(m.group(1)) if m else 4
    if fid in ("WS05-CMD-TAX-2", "WS05-CMD-MULL-2", "WS05-CMD-START-2"):
        return 2
    if fid == "WS05-CMD-START-3":
        return 3
    return 4


def base_record(fid, category):
    n = player_count_for(fid)
    r = {
        "fixture_id": fid,
        "materialization_version": SCHEMA_ID,
        "fixture_family": category,
        "materialization_status": "OBLIGATION_PRESERVED",
        "authority_provenance": {
            "common_manifest_sha256": COMMON_SHA,
            "common_manifest_fixture_id": fid,
            "rsp": RSP,
            "ws29_base_commit": BASE_SHA,
            "cr_pdf_sha256": CR_SHA,
        },
        "frozen_contract_binding": {
            "manifest_fixture_id": fid,
            "manifest_sha256": COMMON_SHA,
            "af_mapping": "INHERIT_BY_REFERENCE_NO_REDEFINITION",
        },
        "players": players(n),
        "commander_state": commander_state(n),
        "semantic_objects": base_objects(n),
        "temporal_state": temporal(),
        "knowledge_state": knowledge_public(n),
        "rules_randomness": rng(),
        "decision_script": [],
        "expected_events": event_assert(),
        "terminal_postconditions": [],
        "normalization": normalization(),
        "setup_validation": setup_validation(),
        "scenario_notes": [
            "Minimal deterministic provider-neutral representative of the frozen obligation; provider-native construction and legality remain authoritative."
        ],
    }
    return r


# ---------- scenario builders ----------
def build_player_count(fid, r):
    n = player_count_for(fid)
    r["scenario_notes"] += [
        "Commander lifecycle interpretation selected from Commander-centric production contract, not either historical candidate setup.",
        "Each player deck is Rograkh, Son of Rohgahh plus 99 basic Mountains; basic lands may repeat.",
    ]
    r["deck_state"] = [
        {
            "player_id": f"P{i}",
            "commander_ids": [f"cmd:P{i}-A"],
            "library_template": {"card_identity": "Mountain", "count": 99},
            "opening_hand_size": 7,
            "shuffle_channel": f"library_shuffle:P{i}",
        }
        for i in range(1, n + 1)
    ]
    r["rules_randomness"] = rng(channels=[f"library_shuffle:P{i}" for i in range(1, n + 1)])
    r["decision_script"] = [
        decision("semantic_action", "keep_opening_hand", "mulligan", actor=f"P{i}")
        for i in range(1, n + 1)
    ]
    r["expected_events"] = event_assert(
        [
            "game_created",
            "commander_zones_initialized",
            "libraries_shuffled",
            "opening_hands_drawn",
            "first_turn_started",
        ],
        ["technical_20_life_start"],
    )
    r["terminal_postconditions"] = [
        f"exactly {n} live real players exist",
        "each player started at 40 life",
        "each commander began in command zone",
        "each library was derived from exactly 99 Mountains",
        "opening hand size is seven after scripted keeps",
        "turn/priority ring contains exactly the live players",
    ]


def pilot_common(r):
    # clean 4P battlefield for production-reachable discretionary choices
    r["semantic_objects"] += [
        obj("obj:p1-bears", "Grizzly Bears", "P1", "P1", "battlefield"),
        obj("obj:p2-bears", "Grizzly Bears", "P2", "P2", "battlefield"),
        obj("obj:p3-bears", "Grizzly Bears", "P3", "P3", "battlefield"),
    ]


def build_pilot(fid, r):
    pilot_common(r)
    if fid == "PILOT_MULLIGAN":
        r["deck_state"] = [
            {
                "player_id": "P1",
                "commander_ids": ["cmd:P1-A"],
                "library_template": {"card_identity": "Mountain", "count": 99},
                "opening_hand_size": 7,
                "shuffle_channel": "library_shuffle:P1",
            }
        ]
        r["temporal_state"] = temporal(phase="pregame", step="mulligan", priority="P1", turn=0)
        r["decision_script"] = [decision("semantic_action", "mulligan_once", "mulligan")]
        r["expected_events"] = event_assert(
            ["mulligan_decision:P1", "new_hand_drawn:P1", "bottom_card_selection:P1"]
        )
        r["terminal_postconditions"] = [
            "In this 4P Commander fixture the first mulligan is the multiplayer free mulligan, so it does not increase the bottom-card count.",
            "P1 keeps a legal seven-card opening hand after exactly one free mulligan and bottoms zero cards.",
        ]
    elif fid == "PILOT_PRIORITY":
        r["semantic_objects"] += [obj("obj:pilot-bolt", "Lightning Bolt", "P1", "P1", "hand")]
        r["decision_script"] = [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:pilot-bolt", "target": "P2"},
                "priority",
            )
        ]
        r["expected_events"] = event_assert(
            ["priority_decision_frame:P1", "spell_cast:obj:pilot-bolt"],
            ["adapter_synthesized_action"],
        )
        r["terminal_postconditions"] = [
            "Selected cast action was among provider-offered legal options and no adapter legality was invented."
        ]
    elif fid == "PILOT_TARGET":
        r["semantic_objects"] += [obj("obj:pilot-bolt", "Lightning Bolt", "P1", "P1", "stack")]
        r["decision_script"] = [decision("semantic_player", "P2", "target")]
        r["expected_events"] = event_assert(["target_decision_frame:P1", "target_selected:P2"])
        r["terminal_postconditions"] = [
            "P2 is the target selected from the provider legal target set."
        ]
    elif fid == "PILOT_CHOOSE_OBJECT":
        r["semantic_objects"] += [
            obj("obj:p1-hand-a", "Mountain", "P1", "P1", "hand"),
            obj("obj:p1-hand-b", "Island", "P1", "P1", "hand"),
            obj("obj:syphon", "Syphon Mind", "P2", "P2", "stack"),
        ]
        r["decision_script"] = [decision("semantic_object", "obj:p1-hand-a", "choose_object")]
        r["expected_events"] = event_assert(
            ["choose_object_frame:P1", "object_selected:obj:p1-hand-a"]
        )
        r["terminal_postconditions"] = [
            "Only provider-offered selectable objects were eligible; obj:p1-hand-a was selected."
        ]
    elif fid in ("PILOT_TARGET_AMOUNT", "PILOT_MULTI_AMOUNT"):
        r["semantic_objects"] += [
            obj("obj:pilot-opus", "Magma Opus", "P1", "P1", "stack"),
            obj("obj:pilot-p3-target", "Grizzly Bears", "P3", "P3", "battlefield"),
        ]
        fam = "target_amount" if fid == "PILOT_TARGET_AMOUNT" else "multi_amount"
        r["decision_script"] = [
            decision("amount_assignment", {"P2": 2, "obj:pilot-p3-target": 2}, fam)
        ]
        r["expected_events"] = event_assert([f"{fam}_frame:P1", "amount_assignment:2+2"])
        r["terminal_postconditions"] = [
            "Assignment totals exactly 4 and each selected damage target receives at least 1."
        ]
    elif fid == "PILOT_CHOOSE_USE":
        r["semantic_objects"] += [
            obj("obj:path", "Path of Ancestry", "P1", "P1", "battlefield"),
            obj("obj:top-known", "Mountain", "P1", "P1", "library", position=0),
        ]
        r["decision_script"] = [
            decision(
                "boolean",
                False,
                "choose_use",
                notes="For scry 1, false means do not put the viewed top card on bottom.",
            )
        ]
        r["expected_events"] = event_assert(["choose_use_frame:P1", "scry_choice:keep_top"])
        r["terminal_postconditions"] = [
            "Known top card remains on top after the provider-offered scry choice."
        ]
    elif fid == "PILOT_CHOICE":
        r["semantic_objects"] += [
            obj("obj:utopia", "Utopia Sprawl", "P1", "P1", "stack"),
            obj("obj:forest", "Forest", "P1", "P1", "battlefield"),
        ]
        r["decision_script"] = [decision("semantic_choice_key", "RED", "choice")]
        r["expected_events"] = event_assert(["choice_frame:P1", "choice:RED"])
        r["terminal_postconditions"] = ["RED was selected from provider-offered color choices."]
    elif fid == "PILOT_PILE":
        r["semantic_objects"] += [obj("obj:fof", "Fact or Fiction", "P1", "P1", "stack")] + [
            obj(f"obj:fof-{i}", c, "P1", "P1", "revealed", position=i)
            for i, c in enumerate(["Mountain", "Island", "Swamp", "Forest", "Plains"])
        ]
        r["decision_script"] = [
            decision(
                "partition",
                {
                    "pile_a": ["obj:fof-0", "obj:fof-1"],
                    "pile_b": ["obj:fof-2", "obj:fof-3", "obj:fof-4"],
                },
                "pile",
                actor="P2",
            )
        ]
        r["expected_events"] = event_assert(["pile_frame:P2", "partition_created:2/3"])
        r["terminal_postconditions"] = [
            "Every revealed object appears in exactly one pile; no hidden identity is added to pile metadata."
        ]
    elif fid == "PILOT_MANA_PAYMENT":
        r["semantic_objects"] += [
            obj("obj:island-a", "Island", "P1", "P1", "battlefield"),
            obj("obj:island-b", "Island", "P1", "P1", "battlefield"),
            obj("obj:counterspell", "Counterspell", "P1", "P1", "hand"),
            obj("obj:opp-bolt", "Lightning Bolt", "P2", "P2", "stack"),
        ]
        r["decision_script"] = [
            decision(
                "mana_payment",
                {"sources": ["obj:island-a", "obj:island-b"], "mana": ["U", "U"]},
                "mana_payment",
            )
        ]
        r["expected_events"] = event_assert(["mana_payment_frame:P1", "mana_paid:UU"])
        r["terminal_postconditions"] = [
            "Exactly the selected provider-legal mana payment is consumed."
        ]
    elif fid == "PILOT_ANNOUNCE_X":
        r["semantic_objects"] += [obj("obj:finale", "Finale of Revelation", "P1", "P1", "hand")]
        r["decision_script"] = [decision("integer", 3, "announce_x")]
        r["expected_events"] = event_assert(["announce_x_frame:P1", "x_announced:3"])
        r["terminal_postconditions"] = [
            "X=3 is bound into the announced spell and cost calculation by the Rules Core."
        ]
    elif fid == "PILOT_REPLACEMENT_EFFECT":
        r["semantic_objects"] += [
            obj(
                "obj:p1-commander-bf",
                "Rograkh, Son of Rohgahh",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-A",
                lineage="line:P1-commander",
            )
        ]
        r["decision_script"] = [
            decision(
                "boolean",
                True,
                "replacement_effect",
                notes="Commander would move to hand; choose command-zone replacement.",
            )
        ]
        r["expected_events"] = event_assert(
            ["replacement_effect_frame:P1", "commander_replacement_chosen:command"]
        )
        r["terminal_postconditions"] = [
            "Commander is in command zone rather than hand; provider performed replacement legality."
        ]
    elif fid == "PILOT_TRIGGER_ORDER":
        r["semantic_objects"] += [
            obj("obj:arena", "Phyrexian Arena", "P1", "P1", "battlefield"),
            obj("obj:remora", "Mystic Remora", "P1", "P1", "battlefield", counters={"age": 0}),
        ]
        r["temporal_state"] = temporal(phase="beginning", step="upkeep", priority="P1")
        r["decision_script"] = [
            decision("order", ["trigger:Phyrexian_Arena", "trigger:Mystic_Remora"], "trigger_order")
        ]
        r["expected_events"] = event_assert(
            ["simultaneous_triggers:P1:2", "trigger_order_frame:P1"]
        )
        r["terminal_postconditions"] = [
            "Both triggers are on stack in the selected relative order; trigger creation itself remains simultaneous."
        ]
    elif fid == "PILOT_CHOOSE_MODE":
        r["semantic_objects"] += [obj("obj:burn", "Burn Down the House", "P1", "P1", "hand")]
        r["decision_script"] = [decision("semantic_mode_key", "create_devils", "choose_mode")]
        r["expected_events"] = event_assert(["choose_mode_frame:P1", "mode_selected:create_devils"])
        r["terminal_postconditions"] = ["Selected mode is the provider-offered Devil-token mode."]
    elif fid == "PILOT_CHOOSE_ABILITY":
        r["semantic_objects"] += [
            obj(
                "obj:jeska",
                "Jeska, Thrice Reborn",
                "P1",
                "P1",
                "battlefield",
                counters={"loyalty": 3},
            ),
            obj("obj:jeska-target", "Grizzly Bears", "P1", "P1", "battlefield"),
        ]
        r["decision_script"] = [
            decision("semantic_ability_key", "loyalty_0_triple_damage", "choose_ability")
        ]
        r["expected_events"] = event_assert(
            ["choose_ability_frame:P1", "ability_selected:loyalty_0_triple_damage"]
        )
        r["terminal_postconditions"] = [
            "The provider-selected legal activated ability is Jeska 0 ability."
        ]
    elif fid == "PILOT_DECLARE_ATTACKER":
        r["temporal_state"] = temporal(phase="combat", step="declare_attackers", priority="P1")
        r["decision_script"] = [
            decision("attacker_assignment", {"obj:p1-bears": "P2"}, "declare_attacker")
        ]
        r["expected_events"] = event_assert(
            ["declare_attacker_frame:P1", "attacker_declared:obj:p1-bears->P2"]
        )
        r["terminal_postconditions"] = [
            "obj:p1-bears is attacking P2 and is tapped if required by rules."
        ]
    elif fid == "PILOT_DECLARE_BLOCKER":
        r["temporal_state"] = temporal(phase="combat", step="declare_blockers", priority="P2")
        r["combat_state"] = {"attackers": {"obj:p1-bears": "P2"}}
        r["decision_script"] = [
            decision(
                "blocker_assignment",
                {"obj:p2-bears": "obj:p1-bears"},
                "declare_blocker",
                actor="P2",
            )
        ]
        r["expected_events"] = event_assert(
            ["declare_blocker_frame:P2", "blocker_declared:obj:p2-bears->obj:p1-bears"]
        )
        r["terminal_postconditions"] = [
            "Block assignment exists only between the defending player P2 blocker and attacker attacking P2."
        ]
    else:
        raise KeyError(fid)


def build_negative(fid, r):
    pilot_common(r)
    mech = fid.removeprefix("NEGATIVE_").lower()
    if fid == "NEGATIVE_FIRST_OPTION" or fid == "NEGATIVE_GUI_DEFAULT":
        r["semantic_objects"] += [obj("obj:neg-burn", "Burn Down the House", "P1", "P1", "hand")]
        fam = "choose_mode"
        trigger = "Burn Down the House is legally cast and provider offers its two modes."
    elif fid == "NEGATIVE_RANDOM_OPTION":
        r["semantic_objects"] += [obj("obj:neg-bolt", "Lightning Bolt", "P1", "P1", "stack")]
        fam = "target"
        trigger = "Lightning Bolt requires a target and P2/P3 are both legal targets."
    elif fid == "NEGATIVE_DEFAULT_YES_NO":
        r["semantic_objects"] += [obj("obj:neg-top", "Mountain", "P1", "P1", "library", position=0)]
        fam = "choose_use"
        trigger = "A legal scry 1 choice offers keep-top versus put-bottom."
    elif fid == "NEGATIVE_INTERNAL_AI":
        fam = "declare_attacker"
        trigger = "P1 has two legal attackers and at least two legal defending players."
    elif fid == "NEGATIVE_SILENT_SKIP":
        r["semantic_objects"] += [obj("obj:neg-bolt", "Lightning Bolt", "P1", "P1", "stack")]
        fam = "target"
        trigger = "A mandatory target selection exists with P2 legal."
    elif fid == "NEGATIVE_PARENT_CLASS_FALLBACK":
        r["semantic_objects"] += [
            obj("obj:neg-hand-a", "Mountain", "P1", "P1", "hand"),
            obj("obj:neg-hand-b", "Island", "P1", "P1", "hand"),
        ]
        fam = "choose_object"
        trigger = "A discard instruction requires choosing exactly one of two provider-legal hand objects."
    else:
        raise KeyError(fid)
    r["negative_fallback_probe"] = {
        "forbidden_mechanism": mech,
        "production_reachable_trigger": trigger,
        "external_decision_handler": "INTENTIONALLY_UNSUPPORTED_FOR_PROBE",
        "required_provider_response": "UNSUPPORTED_DISCRETIONARY_DECISION / FAIL_CLOSED",
    }
    r["decision_script"] = [
        {
            "decision_family": fam,
            "actor": "P1",
            "selection": {
                "selector_kind": "fail_closed_probe",
                "semantic_value": None,
                "matches_only_provider_offered_legal_options": True,
                "on_zero_match": "FAIL_CLOSED",
                "on_multiple_match": "FAIL_CLOSED",
            },
            "forbidden_fallbacks": [
                "first_option",
                "random_option",
                "default_yes_no",
                "internal_ai",
                "gui_default",
                "silent_skip",
                "parent_class_fallback",
            ],
            "notes": "Do not answer the decision. This fixture passes only if the unsupported path terminates instead of using the named fallback.",
        }
    ]
    r["expected_events"] = event_assert(
        [f"decision_frame:{fam}", "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"],
        [f"fallback_used:{mech}", "game_continued_after_unsupported_decision"],
    )
    r["terminal_postconditions"] = [
        f"No {mech} behavior selected an option.",
        "Session/fixture terminates with typed unsupported discretionary-decision failure.",
    ]


HIDDEN_DESC = {
    "HIDDEN_01": "opponent hand identities absent while count remains visible",
    "HIDDEN_02": "library identities/order absent while count remains visible",
    "HIDDEN_03": "face-up exile identities public",
    "HIDDEN_04": "face-down permanent controller sees identity while opponents do not",
    "HIDDEN_05": "face-down exile actor-specific permission persists",
    "HIDDEN_06": "face-down exile knowledge invalidates correctly",
    "HIDDEN_07": "reveal reaches exactly legal audience",
    "HIDDEN_08": "look reaches only specified audience",
    "HIDDEN_09": "hidden-zone search inspection does not leak",
    "HIDDEN_10": "scry/surveil top-N actor knowledge",
    "HIDDEN_11": "shuffle invalidates order knowledge",
    "HIDDEN_12": "controlled-player authority receives legally visible information",
    "HIDDEN_13": "pile metadata does not leak",
    "HIDDEN_14": "target option metadata does not leak",
    "HIDDEN_15": "source metadata does not leak",
    "HIDDEN_16": "ability metadata does not leak",
    "HIDDEN_17": "copy/face-down interactions hide original identity",
    "HIDDEN_18": "transcripts omit actor-private state",
    "HIDDEN_19": "pilot code cannot access omniscient raw engine APIs",
    "HIDDEN_HONEYCARD_SENTINEL": "unique forbidden sentinels scanned across prompt/context/option IDs/labels/metadata/source/state/transcript/logs",
}


def build_hidden(fid, r):
    honey = "WS30_HONEY_P2_PRIVATE_7F3A"
    r["semantic_objects"] += [
        obj(
            "obj:hidden-hand",
            "Demonic Tutor",
            "P2",
            "P2",
            "hand",
            notes=[f"honey_sentinel:{honey}"],
        ),
        obj(
            "obj:hidden-lib-0",
            "Vampiric Tutor",
            "P2",
            "P2",
            "library",
            position=0,
            notes=["private library top sentinel"],
        ),
        obj("obj:public-exile", "Sol Ring", "P2", "P2", "exile"),
        obj(
            "obj:facedown",
            "Grizzly Bears",
            "P1",
            "P1",
            "battlefield",
            face_down=True,
            notes=["fixture grants controller-only look permission where relevant"],
        ),
    ]
    ks = {
        "viewer": "P1",
        "obligation": HIDDEN_DESC[fid],
        "known_object_identities": [],
        "known_library_ranges": [],
        "ordered_known_information": [],
        "temporary_permissions": [],
        "face_down_look_permissions": [],
        "invalidation_conditions": [],
        "permitted_public_metadata": [],
        "prohibited_metadata": [],
        "channels_under_test": [
            "prompt",
            "context",
            "option_id",
            "option_label",
            "option_metadata",
            "source_metadata",
            "ability_metadata",
            "pile_metadata",
            "state",
            "event",
            "transcript",
            "log",
        ],
        "honey_sentinels": [honey],
    }
    if fid == "HIDDEN_01":
        ks["permitted_public_metadata"] = ["P2 hand count"]
        ks["prohibited_metadata"] = [
            "obj:hidden-hand identity",
            "card name",
            "mana cost",
            "oracle text",
        ]
    elif fid == "HIDDEN_02":
        ks["permitted_public_metadata"] = ["P2 library count"]
        ks["prohibited_metadata"] = ["obj:hidden-lib-0 identity", "P2 library order"]
    elif fid == "HIDDEN_03":
        ks["known_object_identities"] = ["obj:public-exile"]
        ks["permitted_public_metadata"] = ["face-up exile identity", "owner", "zone"]
    elif fid == "HIDDEN_04":
        ks["face_down_look_permissions"] = [
            {"object": "obj:facedown", "viewer": "P1", "scope": "identity"}
        ]
        ks["prohibited_metadata"] = ["obj:facedown identity to P2/P3/P4"]
    elif fid == "HIDDEN_05":
        ks["temporary_permissions"] = [
            {
                "object": "obj:hidden-hand",
                "viewer": "P1",
                "permission": "look_at_face_down_exile",
                "persists_while_in_same_exile_object": True,
            }
        ]
        r["semantic_objects"][len(base_objects(4))]["zone"] = "exile"
        r["semantic_objects"][len(base_objects(4))]["face_down"] = True
    elif fid == "HIDDEN_06":
        ks["temporary_permissions"] = [
            {"object": "obj:hidden-hand", "viewer": "P1", "permission": "look_at_face_down_exile"}
        ]
        ks["invalidation_conditions"] = ["object changes zone or becomes a new object"]
        r["semantic_objects"][len(base_objects(4))]["zone"] = "exile"
        r["semantic_objects"][len(base_objects(4))]["face_down"] = True
    elif fid == "HIDDEN_07":
        ks["known_object_identities"] = ["obj:hidden-hand"]
        ks["temporary_permissions"] = [
            {"object": "obj:hidden-hand", "viewer": "ALL_PLAYERS", "permission": "reveal"}
        ]
    elif fid == "HIDDEN_08":
        ks["known_object_identities"] = ["obj:hidden-lib-0"]
        ks["temporary_permissions"] = [
            {"object": "obj:hidden-lib-0", "viewer": "P1", "permission": "look"}
        ]
        ks["prohibited_metadata"] = ["identity to P2/P3/P4"]
    elif fid == "HIDDEN_09":
        ks["temporary_permissions"] = [
            {"zone": "P2.library", "viewer": "P2", "permission": "search"}
        ]
        ks["prohibited_metadata"] = [
            "searched identities to P1",
            "search option metadata exposing nonpublic cards",
        ]
    elif fid == "HIDDEN_10":
        ks["known_library_ranges"] = [
            {"player": "P1", "start": 0, "count": 2, "ordered": True, "viewer": "P1"}
        ]
        ks["prohibited_metadata"] = ["top-N identities to P2/P3/P4"]
    elif fid == "HIDDEN_11":
        ks["known_library_ranges"] = [
            {
                "player": "P2",
                "start": 0,
                "count": 2,
                "ordered": True,
                "viewer": "P1",
                "before_event": "shuffle",
            }
        ]
        ks["invalidation_conditions"] = ["P2 library shuffled"]
        ks["prohibited_metadata"] = ["pre-shuffle order retained after shuffle"]
    elif fid == "HIDDEN_12":
        ks["temporary_permissions"] = [
            {
                "controller": "P1",
                "controlled_player": "P2",
                "permission": "only information P1 is entitled to while making P2 decisions under rules",
            }
        ]
        ks["prohibited_metadata"] = [
            "omniscient P2 hidden information not legally visible to decision authority"
        ]
    elif fid == "HIDDEN_13":
        ks["permitted_public_metadata"] = [
            "pile membership semantic IDs only if objects are legally revealed"
        ]
        ks["prohibited_metadata"] = ["private card identities embedded in pile labels/metadata"]
    elif fid == "HIDDEN_14":
        ks["permitted_public_metadata"] = ["legal target semantic type/public identity only"]
        ks["prohibited_metadata"] = ["hidden card identity in target option id/label/metadata"]
    elif fid == "HIDDEN_15":
        ks["prohibited_metadata"] = ["hidden source card identity in prompt/source metadata"]
    elif fid == "HIDDEN_16":
        ks["prohibited_metadata"] = ["hidden card oracle ability identity/text in ability metadata"]
    elif fid == "HIDDEN_17":
        ks["prohibited_metadata"] = [
            "original hidden card identity leaked through copy/face-down metadata"
        ]
        ks["permitted_public_metadata"] = ["copiable public characteristics only as rules permit"]
    elif fid == "HIDDEN_18":
        ks["prohibited_metadata"] = [
            "actor-private hand/library identities in EventTape/transcript/log"
        ]
        ks["known_object_identities"] = ["obj:hidden-lib-0"]
    elif fid == "HIDDEN_19":
        ks["prohibited_metadata"] = [
            "direct raw engine object graph",
            "omniscient state API",
            "unfiltered engine callbacks",
        ]
        ks["permitted_public_metadata"] = ["RSP actor-aware observation only"]
    elif fid == "HIDDEN_HONEYCARD_SENTINEL":
        ks["prohibited_metadata"] = [honey]
        ks["channels_under_test"] = [
            "prompt",
            "context",
            "option_id",
            "option_label",
            "option_metadata",
            "source",
            "state",
            "transcript",
            "log",
        ]
    r["knowledge_state"] = {
        "viewer_states": [ks],
        "channel_policy": "All pilot-visible fields are filtered by the same viewer/knowledge model; raw engine omniscience is outside pilot surface.",
    }
    r["expected_events"] = event_assert([f"knowledge_projection:{fid}:P1"], [f"leak:{honey}"])
    r["terminal_postconditions"] = [
        "P1 observation exactly respects declared viewer state.",
        "No prohibited metadata appears in any tested channel.",
        "Knowledge invalidation/permission persistence follows the declared conditions.",
    ]


def replay_base(r):
    r["semantic_objects"] += [obj("obj:replay-burn", "Burn Down the House", "P1", "P1", "hand")] + [
        obj(f"obj:replay-lib-{i}", c, "P1", "P1", "library", position=i)
        for i, c in enumerate(
            ["Mountain", "Island", "Swamp", "Forest", "Plains", "Mountain", "Island"]
        )
    ]
    r["rules_randomness"] = rng(
        channels=["library_shuffle:P1"],
        pred=[
            {
                "channel": "library_shuffle:P1",
                "operation": "shuffle",
                "semantic_input": [
                    "obj:replay-lib-0",
                    "obj:replay-lib-1",
                    "obj:replay-lib-2",
                    "obj:replay-lib-3",
                    "obj:replay-lib-4",
                    "obj:replay-lib-5",
                    "obj:replay-lib-6",
                ],
                "result_reference": "RulesRngTape entry rng:1",
            }
        ],
    )
    r["decision_script"] = [decision("semantic_mode_key", "create_devils", "choose_mode")]
    r["replay_contract"] = {
        "initial_materialization_digest_reference": "record.materialization_digest",
        "rules_seed": SEED,
        "decision_tape_semantics": "record exact semantic selector and matched provider option semantic projection, not provider option id as cross-provider identity",
        "event_normalization": normalization(),
        "checkpoints": [
            "after_native_setup_validation",
            "after_rules_shuffle",
            "after_mode_decision",
            "after_spell_resolution",
            "final_stable_state",
        ],
        "required_equality": [
            "normalized semantic events",
            "privileged semantic state",
            "public semantic state",
            "actor-scoped P1 semantic state",
            "terminal postconditions",
        ],
    }
    r["expected_events"] = event_assert(
        [
            "rules_rng:library_shuffle:P1",
            "decision:choose_mode:create_devils",
            "create_Devil_token:3",
        ]
    )
    r["terminal_postconditions"] = [
        "Three Devil tokens exist under P1 after resolution.",
        "Clean replay under same materialization/RulesRngTape/DecisionTape yields equal normalized checkpoints.",
    ]


def build_replay(fid, r):
    replay_base(r)
    extra = {
        "RNG_RULES_TAPE": "RulesRngTape records semantic random operations and results separate from pilot decisions.",
        "REPLAY_DECISION_TAPE": "DecisionTape records exact discretionary semantic selections.",
        "REPLAY_EVENT_TAPE": "EventTape records normalized meaningful semantic events.",
        "REPLAY_CLEAN_PROCESS": "A fresh process reproduces the semantic checkpoints from tapes.",
        "REPLAY_STATE_HASHES": "Privileged/public/actor-scoped hashes exclude process-local identity.",
    }[fid]
    r["terminal_postconditions"].append(extra)


def build_micro(fid, r):
    pilot_common(r)
    if fid == "MICRO_COSTS":
        r["semantic_objects"] += [
            obj("obj:micro-esior", "Esior, Wardwing Familiar", "P1", "P1", "battlefield"),
            obj(
                "obj:micro-cmd-b",
                "Kediss, Emberclaw Familiar",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-B",
            ),
            obj("obj:micro-spell", "Hex", "P2", "P2", "hand"),
        ]
        r["decision_script"] = [
            decision(
                "semantic_action",
                {
                    "action": "announce_spell",
                    "object": "obj:micro-spell",
                    "targets": ["obj:P1-commander", "obj:micro-cmd-b"],
                },
                "priority",
                actor="P2",
            )
        ]
        r["expected_events"] = event_assert(["cost_determined:base_plus_3_generic"])
        r["terminal_postconditions"] = [
            "Targeting two P1 commanders while Esior is controlled adds exactly {3} total, once."
        ]
    elif fid == "MICRO_MANA_PAYMENT":
        r["semantic_objects"] += [
            obj("obj:micro-island-a", "Island", "P1", "P1", "battlefield"),
            obj("obj:micro-island-b", "Island", "P1", "P1", "battlefield"),
            obj("obj:micro-counterspell", "Counterspell", "P1", "P1", "hand"),
            obj("obj:micro-bolt", "Lightning Bolt", "P2", "P2", "stack"),
        ]
        r["decision_script"] = [
            decision(
                "mana_payment",
                {"sources": ["obj:micro-island-a", "obj:micro-island-b"], "mana": ["U", "U"]},
                "mana_payment",
            )
        ]
        r["expected_events"] = event_assert(
            ["mana_abilities_activated:2", "mana_paid:UU", "Counterspell_cast"]
        )
        r["terminal_postconditions"] = [
            "Counterspell cost is paid with exactly two blue mana from selected Islands; payment legality is provider-owned."
        ]
    elif fid in ("MICRO_PRIORITY", "MICRO_STACK"):
        r["semantic_objects"] += [
            obj("obj:micro-bolt", "Lightning Bolt", "P1", "P1", "stack"),
            obj("obj:micro-growth", "Giant Growth", "P2", "P2", "hand"),
            obj("obj:micro-target", "Grizzly Bears", "P2", "P2", "battlefield"),
        ]
        r["stack_state"] = [
            {
                "semantic_stack_id": "stack:1",
                "source_object": "obj:micro-bolt",
                "controller": "P1",
                "targets": ["obj:micro-target"],
            }
        ]
        r["decision_script"] = [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:micro-growth", "target": "obj:micro-target"},
                "priority",
                actor="P2",
            )
        ]
        r["expected_events"] = event_assert(
            [
                "priority:P2",
                "spell_cast:Giant_Growth",
                "stack_push:Giant_Growth",
                "resolve:Giant_Growth",
                "resolve:Lightning_Bolt",
            ],
            ordering=[
                ["spell_cast:Giant_Growth", "resolve:Giant_Growth"],
                ["resolve:Giant_Growth", "resolve:Lightning_Bolt"],
            ],
        )
        r["terminal_postconditions"] = [
            "Grizzly Bears survives Lightning Bolt because Giant Growth resolves first.",
            "Stack is empty after both spells resolve.",
        ]
    elif fid == "MICRO_TARGETS":
        r["semantic_objects"] += [obj("obj:micro-bolt", "Lightning Bolt", "P1", "P1", "stack")]
        r["decision_script"] = [decision("semantic_player", "P2", "target")]
        r["expected_events"] = event_assert(["legal_targets_exposed", "target_selected:P2"])
        r["terminal_postconditions"] = [
            "Only Rules-Core legal targets were offered and P2 was selected."
        ]
    elif fid == "MICRO_MODES":
        r["semantic_objects"] += [obj("obj:micro-burn", "Burn Down the House", "P1", "P1", "hand")]
        r["decision_script"] = [decision("semantic_mode_key", "create_devils", "choose_mode")]
        r["expected_events"] = event_assert(["mode_selected:create_devils", "create_Devil_token:3"])
        r["terminal_postconditions"] = [
            "Exactly the selected mode resolves; damage mode does not also occur."
        ]
    elif fid == "MICRO_TRIGGERS":
        r["semantic_objects"] += [
            obj("obj:micro-warstorm", "Warstorm Surge", "P1", "P1", "battlefield"),
            obj("obj:micro-enter", "Grizzly Bears", "P1", "P1", "hand"),
        ]
        r["decision_script"] = [decision("semantic_player", "P2", "target")]
        r["expected_events"] = event_assert(
            ["creature_enters:obj:micro-enter", "trigger:Warstorm_Surge", "damage:P2:2"]
        )
        r["terminal_postconditions"] = [
            "Warstorm Surge triggers exactly once and entering creature deals 2 to P2 on resolution."
        ]
    elif fid == "MICRO_REPLACEMENT":
        r["semantic_objects"] += [
            obj("obj:micro-violence", "Gratuitous Violence", "P1", "P1", "battlefield"),
            obj("obj:micro-3power", "Hill Giant", "P1", "P1", "battlefield"),
        ]
        r["expected_events"] = event_assert(
            ["damage_would_be:P2:3", "replacement_effect:double", "damage:P2:6"]
        )
        r["terminal_postconditions"] = [
            "Single applicable replacement changes 3 damage to 6 before the damage event occurs."
        ]
    elif fid == "MICRO_PREVENTION":
        r["semantic_objects"] += [
            obj("obj:micro-fog", "Fog", "P2", "P2", "graveyard"),
            obj("obj:micro-attacker", "Grizzly Bears", "P1", "P1", "battlefield"),
        ]
        r["temporal_state"] = temporal(phase="combat", step="combat_damage", priority="P1")
        r["continuous_rules_effects"] = [
            {
                "source": "obj:micro-fog",
                "effect": "Prevent all combat damage that would be dealt this turn",
                "duration": "this turn",
            }
        ]
        r["expected_events"] = event_assert(
            ["combat_damage_would_be:P2:2", "prevention_applied", "combat_damage_prevented:P2:2"]
        )
        r["terminal_postconditions"] = ["P2 loses 0 life from the prevented combat damage."]
    elif fid == "MICRO_CONTINUOUS_EFFECTS":
        r["semantic_objects"] += [
            obj("obj:micro-crawler", "Psychosis Crawler", "P1", "P1", "battlefield")
        ] + [obj(f"obj:micro-hand-{i}", "Mountain", "P1", "P1", "hand") for i in range(5)]
        r["expected_events"] = event_assert(["continuous_pt_evaluated:5/5"])
        r["terminal_postconditions"] = [
            "Psychosis Crawler power/toughness are 5/5 from current P1 hand size without a trigger."
        ]
    elif fid == "MICRO_LAYERS":
        r["semantic_objects"] += [
            obj("obj:micro-humility", "Humility", "P1", "P1", "battlefield"),
            obj("obj:micro-anthem", "Glorious Anthem", "P1", "P1", "battlefield"),
            obj("obj:micro-layer-bears", "Grizzly Bears", "P1", "P1", "battlefield"),
        ]
        r["expected_events"] = event_assert(
            ["layer6_remove_abilities", "layer7b_set_pt:1/1", "layer7c_modify_pt:+1/+1"]
        )
        r["terminal_postconditions"] = [
            "Grizzly Bears has no abilities and is 2/2 after Humility then Glorious Anthem are applied in layers."
        ]
    elif fid == "MICRO_STATE_BASED_ACTIONS":
        r["semantic_objects"] += [
            obj(
                "obj:micro-zero", "Grizzly Bears", "P2", "P2", "battlefield", counters={"+1/+1": 2}
            ),
            obj("obj:micro-finality", "Find // Finality", "P1", "P1", "graveyard"),
        ]
        r["continuous_rules_effects"] = [
            {"source": "obj:micro-finality", "effect": "creatures get -4/-4 until end of turn"}
        ]
        r["expected_events"] = event_assert(
            [
                "continuous_pt:obj:micro-zero:0/0",
                "state_based_actions",
                "move_to_graveyard:obj:micro-zero",
            ]
        )
        r["terminal_postconditions"] = [
            "The 0/0 creature is in its owner graveyard before any player receives priority."
        ]
    elif fid == "MICRO_ZONE_CHANGES":
        r["semantic_objects"] += [
            obj(
                "obj:micro-bolt-stack",
                "Lightning Bolt",
                "P1",
                "P1",
                "stack",
                lineage="line:micro-bolt",
            )
        ]
        r["expected_events"] = event_assert(
            [
                "resolve:obj:micro-bolt-stack",
                "zone_change:stack->graveyard",
                "new_object_incarnation:line:micro-bolt",
            ]
        )
        r["terminal_postconditions"] = [
            "The physical/card lineage is continuous but the graveyard object is a new object incarnation; provider-local UUID is ignored."
        ]
    elif fid == "MICRO_COPY":
        r["semantic_objects"] += [
            obj("obj:micro-flare", "Flare of Duplication", "P1", "P1", "stack"),
            obj("obj:micro-bolt", "Lightning Bolt", "P2", "P2", "stack"),
        ]
        r["expected_events"] = event_assert(
            ["copy_spell:Lightning_Bolt", "copy_created_on_stack"], ["cast_event_for_copy"]
        )
        r["terminal_postconditions"] = [
            "Spell copy is not cast and exists as a distinct semantic stack object with copied characteristics."
        ]
    elif fid == "MICRO_CONTROL":
        r["semantic_objects"] += [
            obj(
                "obj:micro-controlmagic",
                "Control Magic",
                "P1",
                "P1",
                "battlefield",
                attached_to="obj:micro-controlled",
            ),
            obj("obj:micro-controlled", "Grizzly Bears", "P2", "P1", "battlefield"),
        ]
        r["expected_events"] = event_assert(["control_effect_applied:P2->P1"])
        r["terminal_postconditions"] = [
            "Grizzly Bears owner remains P2 while controller is P1; if Control Magic leaves, control reverts according to rules."
        ]
    elif fid == "MICRO_COMBAT":
        r["semantic_objects"] += [
            obj("obj:micro-attacker", "Grizzly Bears", "P1", "P1", "battlefield"),
            obj("obj:micro-blocker", "Grizzly Bears", "P2", "P2", "battlefield"),
        ]
        r["combat_state"] = {
            "attackers": {"obj:micro-attacker": "P2"},
            "blockers": {"obj:micro-blocker": "obj:micro-attacker"},
        }
        r["expected_events"] = event_assert(
            [
                "combat_damage:attacker_to_blocker:2",
                "combat_damage:blocker_to_attacker:2",
                "state_based_actions",
                "both_creatures_die",
            ]
        )
        r["terminal_postconditions"] = [
            "Both 2/2 creatures are in their owners graveyards after simultaneous combat damage and SBA."
        ]
    elif fid == "MICRO_RULES_RANDOMNESS":
        r["semantic_objects"] += [obj("obj:micro-stitch", "Stitch in Time", "P1", "P1", "stack")]
        r["rules_randomness"] = rng(
            channels=["coin_flip:obj:micro-stitch"],
            pred=[
                {
                    "channel": "coin_flip:obj:micro-stitch",
                    "operation": "coin_flip",
                    "result": "HEADS",
                }
            ],
        )
        r["expected_events"] = event_assert(["rules_rng:coin_flip:HEADS", "extra_turn_created:P1"])
        r["terminal_postconditions"] = [
            "Rules randomness came only from RulesRng channel and the predetermined semantic HEADS result created an extra turn."
        ]
    else:
        raise KeyError(fid)


def mp_common(r, n):
    r["semantic_objects"] += [
        obj(f"obj:{p}-bears", "Grizzly Bears", p, p, "battlefield")
        for p in [f"P{i}" for i in range(1, n + 1)]
    ]


def build_mp(fid, r):
    n = player_count_for(fid)
    mp_common(r, n)
    if fid in ("WS05-MP-PRIO-3", "WS05-MP-PRIO-5"):
        r["semantic_objects"] += [
            obj("obj:mp-bolt", "Lightning Bolt", "P1", "P1", "stack"),
            obj("obj:mp-response", "Giant Growth", f"P{n}", f"P{n}", "hand"),
        ]
        r["priority_script"] = [{"holder": f"P{i}", "action": "PASS"} for i in range(2, n)] + [
            {"holder": f"P{n}", "action": "CAST obj:mp-response targeting obj:P1-bears"}
        ]
        r["expected_events"] = event_assert(
            ["priority_ring_live_order", "priority_action_resets_pass_count", "response_on_stack"]
        )
        r["terminal_postconditions"] = [
            f"Priority traverses exactly P1..P{n} live ring and resets after P{n} acts; eliminated/nonexistent seats are absent."
        ]
    elif fid in ("WS05-MP-TRIG-3", "WS05-MP-TRIG-5"):
        r["semantic_objects"] += [
            obj(f"obj:soulwarden-{i}", "Soul Warden", f"P{i}", f"P{i}", "battlefield")
            for i in range(1, n + 1)
        ] + [obj("obj:mp-enter", "Grizzly Bears", "P1", "P1", "hand")]
        r["decision_script"] = [
            decision("boolean", True, "choose_use", actor=f"P{i}") for i in range(1, n + 1)
        ]
        r["expected_events"] = event_assert(
            ["simultaneous_trigger_event", "APNAP_stack_order"],
            partial=[
                {
                    "before_player_groups": [f"P{i}" for i in range(1, n + 1)],
                    "rule": "active-player triggers are placed first, then each nonactive player in turn order; within each player group that player orders their triggers",
                }
            ],
        )
        r["terminal_postconditions"] = [
            "Trigger generation is simultaneous; stack placement follows APNAP without fabricating a generation order."
        ]
    elif fid in ("WS05-MP-COMBAT-4", "WS05-MP-COMBAT-5"):
        targets = ["P2", "P3"] if n == 4 else ["P2", "P3", "P4"]
        attackers = []
        for j, t in enumerate(targets):
            sid = f"obj:mp-attacker-{j}"
            r["semantic_objects"].append(obj(sid, "Grizzly Bears", "P1", "P1", "battlefield"))
            attackers.append((sid, t))
        r["combat_state"] = {"attackers": dict(attackers)}
        r["decision_script"] = [
            decision("attacker_assignment", dict(attackers), "declare_attacker")
        ]
        r["expected_events"] = event_assert([f"attacker_declared:{a}->{t}" for a, t in attackers])
        r["terminal_postconditions"] = [
            "A single declare-attackers action may assign different attackers to different defending players; each assignment retains defender identity."
        ]
    elif fid == "WS05-MP-BLOCK-4":
        r["semantic_objects"] += [
            obj("obj:mp-a2", "Grizzly Bears", "P1", "P1", "battlefield"),
            obj("obj:mp-a3", "Grizzly Bears", "P1", "P1", "battlefield"),
            obj("obj:mp-p2-blocker", "Runeclaw Bear", "P2", "P2", "battlefield"),
        ]
        r["combat_state"] = {"attackers": {"obj:mp-a2": "P2", "obj:mp-a3": "P3"}}
        r["decision_script"] = [
            decision(
                "blocker_assignment",
                {"obj:mp-p2-blocker": "obj:mp-a2"},
                "declare_blocker",
                actor="P2",
            )
        ]
        r["expected_events"] = event_assert(
            ["legal_blocker_partition:P2", "blocker_declared:obj:mp-p2-blocker->obj:mp-a2"],
            ["option:P2_blocks_attacker_to_P3"],
        )
        r["terminal_postconditions"] = [
            "P2 blocker options contain only attackers for which P2 is defending player."
        ]
    elif fid in ("WS05-MP-TURN-3", "WS05-MP-TURN-5"):
        r["temporal_state"] = temporal(
            active="P1", phase="postcombat_main", priority="P1", extra=[]
        )
        r["semantic_objects"] += [
            obj("obj:mp-time-warp", "Time Warp", "P1", "P1", "graveyard"),
            obj("obj:mp-nexus", "Nexus of Fate", "P3", "P3", "graveyard"),
        ]
        r["extra_turn_creation"] = [
            {
                "sequence": 1,
                "source": "obj:mp-time-warp",
                "player": "P2",
                "semantic_resolution": "Time Warp resolved targeting P2",
            },
            {
                "sequence": 2,
                "source": "obj:mp-nexus",
                "player": "P3",
                "semantic_resolution": "Nexus of Fate resolved for P3 later in the same current turn",
            },
        ]
        r["expected_events"] = event_assert(
            ["extra_turn_created:P2", "extra_turn_created:P3", "next_turn:P3", "next_turn:P2"]
        )
        r["terminal_postconditions"] = [
            "Most recently created extra turn is taken first: P3 extra, then P2 extra, then normal turn order resumes."
        ]
    elif fid.startswith("WS05-MP-ELIM-"):
        leaver = "P2" if n == 3 else "P3"
        r["players"][int(leaver[1:]) - 1]["life"] = 0
        r["elimination_trigger"] = {"player": leaver, "reason": "life_total_0"}
        if "OWNED" in fid:
            r["semantic_objects"] += [
                obj("obj:leave-owned", "Sol Ring", leaver, leaver, "battlefield")
            ]
            post = ["All objects owned by P2 leave the game, including obj:leave-owned."]
        elif "CONTROL" in fid:
            r["semantic_objects"] += [
                obj("obj:p1-owned-controlled", "Grizzly Bears", "P1", leaver, "battlefield"),
                obj(
                    "obj:leave-controlmagic",
                    "Control Magic",
                    leaver,
                    leaver,
                    "battlefield",
                    attached_to="obj:p1-owned-controlled",
                ),
            ]
            post = [
                "P2-owned Control Magic leaves; P1-owned Grizzly Bears remains and control reverts according to remaining effects/default controller."
            ]
        elif "STACK" in fid:
            r["semantic_objects"] += [
                obj("obj:leave-bolt", "Lightning Bolt", leaver, leaver, "stack")
            ]
            post = ["P2-owned spell on stack leaves the game and does not resolve."]
        elif "PRIO" in fid:
            r["temporal_state"]["priority_player"] = leaver
            post = [
                "After P2 leaves, priority ring excludes P2 and next eligible live player is selected."
            ]
        elif "TURN" in fid:
            r["temporal_state"]["active_player"] = leaver
            post = [
                "The current turn continues without the departed active player as required; after it ends the next live player becomes active."
            ]
        else:
            post = [
                "Live-player ring recomputes from P1,P2,P4,P5; eliminated P3 is absent from turn, priority, opponent and APNAP sets."
            ]
        r["expected_events"] = event_assert(
            [f"player_leaves:{leaver}", "multiplayer_cleanup:CR800.4"]
        )
        r["terminal_postconditions"] = post
    elif fid in ("WS05-CMD-TAX-2", "WS05-CMD-TAX-4"):
        r["commander_state"]["commanders"][0]["prior_command_zone_cast_count"] = 2
        r["semantic_objects"] += [
            obj(f"obj:tax-mountain-{i}", "Mountain", "P1", "P1", "battlefield") for i in range(4)
        ]
        r["decision_script"] = [
            decision(
                "semantic_action",
                {"action": "cast_commander", "commander_id": "cmd:P1-A"},
                "priority",
            )
        ]
        r["expected_events"] = event_assert(
            ["commander_cast_from_command", "commander_tax:+4_generic", "mana_paid:4"]
        )
        r["terminal_postconditions"] = [
            "Rograkh printed mana cost 0 plus two prior command-zone casts gives exactly {4} additional generic; cast count becomes 3."
        ]
    elif fid.startswith("WS05-CMD-ZONE-"):
        yes = fid.endswith("-YES")
        zonepart = fid.split("-ZONE-")[1].rsplit("-", 1)[0]
        source_zone = {"GY": "graveyard", "EXILE": "exile", "HAND": "hand", "LIB": "library"}[
            zonepart
        ]
        sid = "obj:cmd-zone-test"
        r["semantic_objects"] = [
            o for o in r["semantic_objects"] if o["semantic_id"] != "obj:P1-commander"
        ]
        r["semantic_objects"] += [
            obj(
                sid,
                "Rograkh, Son of Rohgahh",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-A",
                lineage="line:cmd-zone-test",
            )
        ]
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["zone"] = "battlefield"
        source_card = {
            "graveyard": "Doom Blade",
            "exile": "Swords to Plowshares",
            "hand": "Unsummon",
            "library": "Bant Charm",
        }[source_zone]
        r["semantic_objects"].append(obj("obj:cmd-zone-source", source_card, "P2", "P2", "stack"))
        if source_zone in ("graveyard", "exile"):
            r["zone_move_event"] = {
                "from": "battlefield",
                "to": source_zone,
                "commander_id": "cmd:P1-A",
                "commander_choice_timing": "state_based_action",
            }
        else:
            r["zone_move_event"] = {
                "from": "battlefield",
                "to": source_zone,
                "commander_id": "cmd:P1-A",
                "commander_choice_timing": "replacement_effect_before_move",
            }
        fam = "replacement_effect" if source_zone in ("hand", "library") else "choice"
        r["decision_script"] = [
            decision(
                "boolean",
                yes,
                fam,
                notes=f"{yes=}: choose command zone rather than remain/move to {source_zone}.",
            )
        ]
        r["expected_events"] = event_assert(
            [
                f"commander_zone_event:{source_zone}",
                f"commander_choice:{'command' if yes else source_zone}",
            ]
        )
        r["terminal_postconditions"] = [
            f"Commander is in {'command zone' if yes else source_zone} after the rule-defined choice; object lineage remains commander cmd:P1-A while zone object incarnation changes."
        ]
    elif fid == "WS05-CMD-DMG-SAME-21":
        r["semantic_objects"] = [
            o for o in r["semantic_objects"] if o["semantic_id"] != "obj:P1-commander"
        ]
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["zone"] = "battlefield"
        r["semantic_objects"] += [
            obj(
                "obj:isamaru",
                "Isamaru, Hound of Konda",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-A",
                lineage="line:isamaru",
            )
        ]
        r["commander_state"]["commanders"][0]["card_identity"] = "Isamaru, Hound of Konda"
        r["commander_state"]["commander_damage_matrix"] = [
            {"source_commander_id": "cmd:P1-A", "damaged_player": "P2", "combat_damage": 19}
        ]
        r["combat_state"] = {"attackers": {"obj:isamaru": "P2"}, "unblocked": ["obj:isamaru"]}
        r["expected_events"] = event_assert(
            ["commander_combat_damage:P2:2", "commander_damage_total:P2:21", "player_loses:P2"]
        )
        r["terminal_postconditions"] = [
            "P2 loses as SBA for 21 combat damage from the same commander."
        ]
    elif fid == "WS05-CMD-DMG-SPLIT":
        r["commander_state"] = commander_state(4, partner=True)
        r["commander_state"]["commander_damage_matrix"] = [
            {"source_commander_id": "cmd:P1-A", "damaged_player": "P2", "combat_damage": 11},
            {"source_commander_id": "cmd:P1-B", "damaged_player": "P2", "combat_damage": 10},
        ]
        r["expected_events"] = event_assert(["commander_damage_checked_per_commander"])
        r["terminal_postconditions"] = [
            "P2 has 21 aggregate commander damage but no single commander has dealt 21; P2 does not lose for commander damage."
        ]
    elif fid == "WS05-CMD-DMG-CONTROL":
        r["semantic_objects"] = [
            o for o in r["semantic_objects"] if o["semantic_id"] != "obj:P1-commander"
        ]
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["zone"] = "battlefield"
        r["semantic_objects"] += [
            obj(
                "obj:isamaru-controlled",
                "Isamaru, Hound of Konda",
                "P1",
                "P3",
                "battlefield",
                commander_id="cmd:P1-A",
                lineage="line:isamaru",
            )
        ]
        r["commander_state"]["commanders"][0]["card_identity"] = "Isamaru, Hound of Konda"
        r["commander_state"]["commander_damage_matrix"] = [
            {"source_commander_id": "cmd:P1-A", "damaged_player": "P2", "combat_damage": 19}
        ]
        r["combat_state"] = {
            "attackers": {"obj:isamaru-controlled": "P2"},
            "unblocked": ["obj:isamaru-controlled"],
        }
        r["expected_events"] = event_assert(
            ["commander_combat_damage:P2:2:cmd:P1-A", "player_loses:P2"]
        )
        r["terminal_postconditions"] = [
            "Commander identity remains cmd:P1-A despite controller P3; P2 reaches 21 from that same commander and loses."
        ]
    elif fid == "WS05-CMD-PARTNER-TAX":
        r["commander_state"] = commander_state(4, partner=True)
        r["commander_state"]["commanders"][0]["prior_command_zone_cast_count"] = 2
        r["commander_state"]["commanders"][1]["prior_command_zone_cast_count"] = 0
        r["expected_events"] = event_assert(["tax:cmd:P1-A:+4", "tax:cmd:P1-B:+0"])
        r["terminal_postconditions"] = [
            "Partner commanders track command-zone cast counts/tax independently."
        ]
    elif fid == "WS05-CMD-PARTNER-DMG":
        r["commander_state"] = commander_state(4, partner=True)
        r["commander_state"]["commander_damage_matrix"] = [
            {"source_commander_id": "cmd:P1-A", "damaged_player": "P2", "combat_damage": 12},
            {"source_commander_id": "cmd:P1-B", "damaged_player": "P2", "combat_damage": 9},
        ]
        r["terminal_postconditions"] = [
            "12 + 9 combat damage from different partner commanders does not pool to cause a 21-damage loss."
        ]
    elif fid == "WS05-CMD-PARTNER-ZONE":
        r["commander_state"] = commander_state(4, partner=True)
        r["semantic_objects"] += [
            obj(
                "obj:p1-cmd-b",
                "Kediss, Emberclaw Familiar",
                "P1",
                "P1",
                "command",
                commander_id="cmd:P1-B",
            )
        ]
        r["expected_events"] = event_assert(
            ["game_start_command_zone:cmd:P1-A", "game_start_command_zone:cmd:P1-B"]
        )
        r["terminal_postconditions"] = [
            "Both partner commanders begin in command zone as separate commander identities."
        ]
    elif fid in ("WS05-CMD-MULL-2", "WS05-CMD-MULL-4"):
        r["temporal_state"] = temporal(phase="pregame", step="mulligan", priority="P1", turn=0)
        r["deck_state"] = [
            {
                "player_id": "P1",
                "commander_ids": ["cmd:P1-A"],
                "library_template": {"card_identity": "Mountain", "count": 99},
                "opening_hand_size": 7,
                "shuffle_channel": "library_shuffle:P1",
            }
        ]
        r["decision_script"] = [decision("semantic_action", "mulligan_once", "mulligan")]
        free = fid.endswith("-4")
        r["expected_events"] = event_assert(
            ["mulligan_once:P1", f"free_mulligan:{str(free).lower()}"]
        )
        r["terminal_postconditions"] = [
            "In 4P multiplayer Commander the first mulligan is free and a kept hand after exactly one mulligan bottoms zero cards."
            if free
            else "In 2P Commander the first mulligan is not the multiplayer free mulligan; after exactly one mulligan and keep, P1 bottoms one card under the London mulligan."
        ]
    elif fid in ("WS05-CMD-START-2", "WS05-CMD-START-3"):
        r["temporal_state"] = temporal(
            active="P1", phase="beginning", step="draw", priority="P1", turn=1
        )
        draw = fid.endswith("-3")
        r["expected_events"] = event_assert(
            ["starting_player:P1", f"first_turn_draw:{str(draw).lower()}"]
        )
        r["terminal_postconditions"] = [
            "In 3P multiplayer, starting player P1 draws on first turn."
            if draw
            else "In 2P, starting player P1 skips the draw step draw on first turn."
        ]
    elif fid == "WS05-CMD-ELIM-4":
        r["semantic_objects"] = [
            o for o in r["semantic_objects"] if o["semantic_id"] != "obj:P1-commander"
        ]
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["zone"] = "battlefield"
        r["semantic_objects"] += [
            obj(
                "obj:elim-isamaru",
                "Isamaru, Hound of Konda",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-A",
            ),
            obj("obj:p2-owned", "Sol Ring", "P2", "P2", "battlefield"),
        ]
        r["commander_state"]["commanders"][0]["card_identity"] = "Isamaru, Hound of Konda"
        r["commander_state"]["commander_damage_matrix"] = [
            {"source_commander_id": "cmd:P1-A", "damaged_player": "P2", "combat_damage": 19}
        ]
        r["combat_state"] = {
            "attackers": {"obj:elim-isamaru": "P2"},
            "unblocked": ["obj:elim-isamaru"],
        }
        r["expected_events"] = event_assert(
            [
                "commander_damage_total:P2:21",
                "player_loses:P2",
                "multiplayer_cleanup:CR800.4",
                "object_leaves_game:obj:p2-owned",
            ]
        )
        r["terminal_postconditions"] = [
            "Commander-damage loss and multiplayer leave-game cleanup are integrated in one stable state before priority."
        ]
    else:
        raise KeyError(fid)


def build_card(fid, r):
    name, setup, _decisions, events, posts = CARD_SPEC[fid]
    r["authority_provenance"]["ws29_expected_semantics_fixture_id"] = fid
    r["authority_provenance"]["ws29_authority_file"] = (
        "qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json"
    )
    r["authority_provenance"]["ws29_authority_classification"] = (
        "FULL_CURRENT_ORACLE_LOCK / DISCRIMINATOR_AUTHORITY_PASS"
    )
    r["authority_provenance"]["cr_rule_references"] = CARD_CR[fid]
    r["card_authority_binding"] = {
        "fixture_id": fid,
        "card_identity": name,
        "tested_discriminator_preserved": True,
        "construction_detail_is_non_authoritative": True,
    }
    r["scenario_notes"] += setup
    # relevant object always present in a semantically sensible pre-action zone; notes drive provider-native exact construction
    zone = "hand"
    if any("controls " + name in s or "controls " + name.split(" // ")[0] in s for s in setup):
        zone = "battlefield"
    if fid in (
        "CARD_01",
        "CARD_03",
        "CARD_04",
        "CARD_05",
        "CARD_06",
        "CARD_07",
        "CARD_16",
        "CARD_17",
        "CARD_19",
        "CARD_21",
        "CARD_24",
    ):
        zone = "battlefield"
    if fid == "CARD_02":
        zone = "command"
    if fid == "CARD_20":
        zone = "stack"
    if fid == "CARD_25":
        zone = "battlefield"
    r["semantic_objects"] += [
        obj(
            f"obj:{fid.lower()}-subject",
            name,
            "P1",
            "P1",
            zone,
            commander_id="cmd:P1-A" if fid == "CARD_02" else None,
        )
    ]
    # deterministic helper objects/resources for construction, deliberately real cards/basic lands/tokens only
    helpers = {
        "CARD_01": [obj("obj:card01-bolt", "Lightning Bolt", "P2", "P2", "hand")],
        "CARD_03": [
            obj(
                "obj:card03-cmd-b",
                "Kediss, Emberclaw Familiar",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-B",
            ),
            obj("obj:card03-spell", "Magma Opus", "P2", "P2", "hand"),
        ],
        "CARD_04": [
            obj(
                "obj:card04-attacker",
                "Bruse Tarl, Boorish Herder",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-A",
            )
        ],
        "CARD_05": [obj("obj:card05-bolt", "Lightning Bolt", "P1", "P1", "hand")],
        "CARD_06": [
            obj("obj:card06-wizard", "Docent of Perfection", "P1", "P1", "battlefield"),
            obj("obj:card06-bolt", "Lightning Bolt", "P1", "P1", "hand"),
        ],
        "CARD_07": [obj("obj:card07-draw", "Divination", "P2", "P2", "stack")],
        "CARD_08": [obj("obj:card08-attacker", "Grizzly Bears", "P1", "P1", "battlefield")],
        "CARD_09": [
            obj("obj:card09-p3-creature", "Grizzly Bears", "P3", "P3", "battlefield"),
            obj("obj:card09-p4-a", "Sol Ring", "P4", "P4", "battlefield"),
            obj("obj:card09-p4-b", "Mountain", "P4", "P4", "battlefield"),
        ]
        + [
            obj(f"obj:card09-lib-{i}", "Mountain", "P1", "P1", "library", position=i)
            for i in range(2)
        ],
        "CARD_10": [
            obj(
                "obj:card10-p2cmd",
                "Rograkh, Son of Rohgahh",
                "P2",
                "P2",
                "stack",
                commander_id="cmd:P2-A",
            )
        ],
        "CARD_11": [
            obj("obj:card11-artifact", "Sol Ring", "P2", "P2", "battlefield"),
            obj("obj:card11-enchantment", "Glorious Anthem", "P2", "P2", "battlefield"),
        ],
        "CARD_12": [
            obj(f"obj:card12-gy-{i}", "Mountain", "P1", "P1", "graveyard") for i in range(6)
        ]
        + [
            obj(f"obj:card12-lib{i + 1}", "Mountain", "P1", "P1", "library", position=i)
            for i in range(7)
        ]
        + [
            obj("obj:card12-island-a", "Island", "P1", "P1", "battlefield"),
            obj("obj:card12-island-b", "Island", "P1", "P1", "battlefield"),
        ],
        "CARD_13": [
            obj(
                "obj:card13-red-creature",
                "Goblin Token",
                "P1",
                "P1",
                "battlefield",
                notes=[
                    "nontoken red creature required; provider must construct an actual nontoken red creature equivalent, e.g. Raging Goblin"
                ],
            ),
            obj("obj:card13-bolt", "Lightning Bolt", "P2", "P2", "stack"),
        ],
        "CARD_14": [
            obj("obj:card14-p1-artifact", "Sol Ring", "P1", "P1", "battlefield"),
            obj("obj:card14-p2-artifact", "Sol Ring", "P2", "P2", "battlefield"),
            obj("obj:card14-p3-artifact", "Sol Ring", "P3", "P3", "battlefield"),
            obj("obj:card14-p4-artifact", "Sol Ring", "P4", "P4", "battlefield"),
        ],
        "CARD_15": [
            obj(f"obj:card15-gy-{i}", "Mountain", "P1", "P1", "graveyard") for i in range(3)
        ]
        + [
            obj(f"obj:card15-land-{i}", "Island", "P1", "P1", "battlefield", tapped=True)
            for i in range(5)
        ]
        + [
            obj(f"obj:card15-lib-{i}", "Mountain", "P1", "P1", "library", position=i)
            for i in range(10)
        ],
        "CARD_16": [obj(f"obj:card16-hand-{i}", "Mountain", "P1", "P1", "hand") for i in range(3)]
        + [obj("obj:card16-divination", "Divination", "P1", "P1", "stack")],
        "CARD_17": [obj("obj:card17-spell", "Wrath of God", "P2", "P2", "hand")],
        "CARD_18": [obj("obj:card18-target", "Grizzly Bears", "P2", "P2", "battlefield")],
        "CARD_19": [
            obj("obj:card19-p1-other", "Grizzly Bears", "P1", "P1", "battlefield"),
            obj("obj:card19-altar", "Ashnod’s Altar", "P1", "P1", "battlefield"),
        ]
        + [
            obj(f"obj:card19-{p}-creature", "Grizzly Bears", p, p, "battlefield")
            for p in ["P2", "P3", "P4"]
        ],
        "CARD_20": [
            obj(f"obj:card20-{p}-hand", "Mountain", p, p, "hand") for p in ["P2", "P3", "P4"]
        ],
        "CARD_21": [obj("obj:card21-creature", "Hill Giant", "P1", "P1", "battlefield")],
        "CARD_22": [
            obj(
                "obj:card22-power4", "Hill Giant", "P1", "P1", "battlefield", counters={"+1/+1": 1}
            ),
            obj("obj:card22-bolt", "Lightning Bolt", "P2", "P2", "stack"),
        ],
        "CARD_23": [
            obj("obj:card23-creature", "Grizzly Bears", "P1", "P1", "graveyard"),
            obj("obj:card23-bolt", "Lightning Bolt", "P1", "P1", "hand"),
        ],
        "CARD_24": [obj("obj:card24-enter", "Grizzly Bears", "P1", "P1", "hand")],
        "CARD_25": [
            obj(
                "obj:card25-attacker",
                "Soldier Token",
                "P1",
                "P1",
                "battlefield",
                notes=["1/1 creature token"],
            ),
            obj(
                "obj:card25-blocker",
                "Colossal Dreadmaw",
                "P2",
                "P2",
                "battlefield",
                counters={"-1/-1": 1},
            ),
        ],
        "CARD_27": [
            obj("obj:card27-warrior", "Keldon Marauders", "P1", "P1", "hand"),
            obj("obj:card27-top", "Mountain", "P1", "P1", "library", position=0),
        ],
        "CARD_28": [
            obj(
                "obj:card28-p1-creature",
                "Grizzly Bears",
                "P1",
                "P1",
                "battlefield",
                counters={"+1/+1": 1},
            ),
            obj(
                "obj:card28-p2-creature",
                "Hill Giant",
                "P2",
                "P2",
                "battlefield",
                counters={"+1/+1": 1},
            ),
        ],
        "CARD_29": [obj("obj:card29-gy-forest", "Forest", "P1", "P1", "graveyard")]
        + [
            obj(f"obj:card29-lib-forest-{i}", "Forest", "P1", "P1", "library", position=i)
            for i in range(2)
        ]
        + [obj(f"obj:card29-land-{i}", "Forest", "P1", "P1", "battlefield") for i in range(4)],
    }
    r["semantic_objects"] += helpers.get(fid, [])
    # deterministic basic-land resources where the frozen discriminator requires a legal cast/payment path
    mana_lands = {
        "CARD_01": {"P2": ["Mountain"]},
        "CARD_03": {"P2": ["Mountain"] * 10 + ["Island"]},
        "CARD_05": {"P1": ["Mountain"]},
        "CARD_06": {"P1": ["Mountain"]},
        "CARD_08": {"P1": ["Mountain"] * 3},
        "CARD_09": {"P1": ["Mountain"] * 7 + ["Island"]},
        "CARD_10": {"P1": ["Island"]},
        "CARD_11": {"P1": ["Mountain", "Mountain", "Plains"]},
        "CARD_14": {"P1": ["Mountain"] * 5},
        "CARD_15": {"P1": ["Mountain"] * 10 + ["Island", "Island"]},
        "CARD_17": {"P2": ["Mountain", "Mountain", "Plains", "Plains"]},
        "CARD_18": {"P1": ["Mountain", "Swamp"]},
        "CARD_22": {"P1": ["Mountain"]},
        "CARD_23": {"P1": ["Mountain"] * 4 + ["Swamp"]},
        "CARD_24": {"P1": ["Forest", "Forest"]},
        "CARD_26": {"P1": ["Mountain"] * 5},
        "CARD_27": {"P1": ["Mountain"]},
        "CARD_28": {"P1": ["Mountain"] * 4 + ["Swamp", "Forest"]},
    }
    for p, cards in mana_lands.get(fid, {}).items():
        for i, card in enumerate(cards):
            r["semantic_objects"].append(
                obj(f"obj:{fid.lower()}-mana-{p.lower()}-{i}", card, p, p, "battlefield")
            )
    # fixture-local commander/attachment construction details required by the WS-29 discriminator
    if fid == "CARD_03":
        r["commander_state"] = commander_state(4, partner=True)
        r["semantic_objects"] = [
            o for o in r["semantic_objects"] if o["semantic_id"] != "obj:P1-commander"
        ]
        r["semantic_objects"].insert(
            0,
            obj(
                "obj:P1-commander",
                "Rograkh, Son of Rohgahh",
                "P1",
                "P1",
                "battlefield",
                commander_id="cmd:P1-A",
            ),
        )
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["zone"] = "battlefield"
            if c["commander_id"] == "cmd:P1-B":
                c["card_identity"] = "Kediss, Emberclaw Familiar"
                c["zone"] = "battlefield"
    if fid == "CARD_04":
        r["commander_state"] = commander_state(4, partner=True)
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["card_identity"] = "Bruse Tarl, Boorish Herder"
                c["zone"] = "battlefield"
            if c["commander_id"] == "cmd:P1-B":
                c["card_identity"] = "Kediss, Emberclaw Familiar"
                c["zone"] = "battlefield"
        r["semantic_objects"] = [
            o for o in r["semantic_objects"] if o["semantic_id"] != "obj:P1-commander"
        ]
        for p in r["players"]:
            if p["player_id"] in ("P2", "P3", "P4"):
                p["starting_life"] = 20
                p["life"] = 20
        for o in r["semantic_objects"]:
            if o["semantic_id"] == "obj:card_04-subject":
                o["commander_id"] = "cmd:P1-B"
                o["card_lineage_id"] = "line:cmd:P1-B"
    if fid == "CARD_08":
        for c in r["commander_state"]["commanders"]:
            if c["commander_id"] == "cmd:P1-A":
                c["prior_command_zone_cast_count"] = 2
    if fid == "CARD_16":
        for p in r["players"]:
            if p["player_id"] in ("P2", "P3", "P4"):
                p["starting_life"] = 20
                p["life"] = 20
    if fid == "CARD_24":
        for p in r["players"]:
            if p["player_id"] == "P2":
                p["starting_life"] = 20
                p["life"] = 20
    if fid == "CARD_25":
        for p in r["players"]:
            if p["player_id"] == "P1":
                p["starting_life"] = 20
                p["life"] = 20
    if fid == "CARD_25":
        for o in r["semantic_objects"]:
            if o["semantic_id"] == "obj:card_25-subject":
                o["attached_to"] = "obj:card25-attacker"
    # replace any pseudo helper construction note that might be invalid with real identity
    if fid == "CARD_13":
        for o in r["semantic_objects"]:
            if o["semantic_id"] == "obj:card13-red-creature":
                o["card_identity"] = "Raging Goblin"
                o["construction_notes"] = ["nontoken red creature"]
    # External discretionary decisions are structured provider-neutral selectors; automatic rules resolution is not put on DecisionTape.
    card_decisions = {
        "CARD_01": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card01-bolt"},
                "priority",
                actor="P2",
            )
        ],
        "CARD_02": [
            decision(
                "semantic_action",
                {"action": "cast_commander", "commander_id": "cmd:P1-A", "from_zone": "command"},
                "priority",
                actor="P1",
            )
        ],
        "CARD_03": [
            decision(
                "semantic_action",
                {
                    "action": "announce_cast",
                    "object": "obj:card03-spell",
                    "damage_targets": ["obj:P1-commander", "obj:card03-cmd-b"],
                    "tap_targets": ["obj:P1-commander", "obj:card03-cmd-b"],
                },
                "priority",
                actor="P2",
            )
        ],
        "CARD_04": [
            decision(
                "attacker_assignment", {"obj:card04-attacker": "P2"}, "declare_attacker", actor="P1"
            ),
            decision("blocker_assignment", {}, "declare_blocker", actor="P2"),
        ],
        "CARD_05": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card05-bolt"},
                "priority",
                actor="P1",
            )
        ],
        "CARD_06": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card06-bolt"},
                "priority",
                actor="P1",
            )
        ],
        "CARD_07": [],
        "CARD_08": [
            decision(
                "semantic_ability_key",
                {"ability": "Jeska_0", "target": "obj:card08-attacker"},
                "choose_ability",
                actor="P1",
            ),
            decision(
                "attacker_assignment", {"obj:card08-attacker": "P2"}, "declare_attacker", actor="P1"
            ),
        ],
        "CARD_09": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card_09-subject"},
                "priority",
                actor="P1",
            ),
            decision(
                "amount_assignment",
                {"P2": 2, "obj:card09-p3-creature": 2},
                "target_amount",
                actor="P1",
            ),
            decision(
                "semantic_object_set",
                ["obj:card09-p4-a", "obj:card09-p4-b"],
                "choose_object",
                actor="P1",
            ),
        ],
        "CARD_10": [
            decision(
                "semantic_action",
                {
                    "action": "cast",
                    "object": "obj:card_10-subject",
                    "cast_mode": "normal_noncleave",
                    "target": "obj:card10-p2cmd",
                },
                "priority",
                actor="P1",
            )
        ],
        "CARD_11": [
            decision(
                "semantic_action",
                {
                    "action": "cast_fused",
                    "object": "obj:card_11-subject",
                    "targets": {"Wear": "obj:card11-artifact", "Tear": "obj:card11-enchantment"},
                },
                "priority",
                actor="P1",
            )
        ],
        "CARD_12": [
            decision(
                "semantic_action",
                {
                    "action": "cast",
                    "object": "obj:card_12-subject",
                    "delve_objects": [f"obj:card12-gy-{i}" for i in range(6)],
                    "mana_payment": ["obj:card12-island-a", "obj:card12-island-b"],
                },
                "priority",
                actor="P1",
            ),
            decision(
                "semantic_object_set",
                ["obj:card12-lib1", "obj:card12-lib2"],
                "choose_object",
                actor="P1",
            ),
            decision(
                "order",
                [f"obj:card12-lib{i}" for i in range(3, 8)],
                "trigger_order",
                actor="P1",
                notes="Order the five nonchosen looked-at cards on the bottom; this is an ordered-card decision, not trigger semantics.",
            ),
        ],
        "CARD_13": [
            decision(
                "semantic_action",
                {
                    "action": "cast_alt_cost",
                    "object": "obj:card_13-subject",
                    "sacrifice": "obj:card13-red-creature",
                    "target_spell": "obj:card13-bolt",
                },
                "priority",
                actor="P1",
            ),
            decision(
                "semantic_player",
                "P3",
                "target",
                actor="P1",
                notes="New target for the created spell copy.",
            ),
        ],
        "CARD_14": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card_14-subject", "alternative_cost": "overload"},
                "priority",
                actor="P1",
            )
        ],
        "CARD_15": [
            decision("integer", 10, "announce_x", actor="P1"),
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card_15-subject", "x": 10},
                "priority",
                actor="P1",
            ),
            decision(
                "semantic_object_set",
                [f"obj:card15-land-{i}" for i in range(5)],
                "choose_object",
                actor="P1",
            ),
        ],
        "CARD_16": [],
        "CARD_17": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card17-spell"},
                "priority",
                actor="P2",
            ),
            decision("semantic_player", "P2", "target", actor="P1"),
        ],
        "CARD_18": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card_18-subject", "alternative_cost": "evoke"},
                "priority",
                actor="P1",
            ),
            decision("semantic_object", "obj:card18-target", "target", actor="P1"),
            decision(
                "order",
                ["trigger:destroy_target", "trigger:evoke_sacrifice"],
                "trigger_order",
                actor="P1",
            ),
        ],
        "CARD_19": [
            decision(
                "semantic_action",
                {
                    "action": "activate",
                    "source": "obj:card19-altar",
                    "sacrifice_cost": "obj:card19-p1-other",
                },
                "priority",
                actor="P1",
            )
        ]
        + [
            decision("semantic_object", f"obj:card19-{p}-creature", "choose_object", actor=p)
            for p in ["P2", "P3", "P4"]
        ],
        "CARD_20": [
            decision("semantic_object", f"obj:card20-{p}-hand", "choose_object", actor=p)
            for p in ["P2", "P3", "P4"]
        ],
        "CARD_21": [],
        "CARD_22": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card_22-subject", "target": "obj:card22-bolt"},
                "priority",
                actor="P1",
            ),
            decision("semantic_player", "P3", "target", actor="P1"),
        ],
        "CARD_23": [
            decision(
                "semantic_action",
                {
                    "action": "cast",
                    "object": "obj:card_23-subject",
                    "target": "obj:card23-creature",
                },
                "priority",
                actor="P1",
            ),
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card23-bolt", "target": "obj:card23-creature"},
                "priority",
                actor="P1",
            ),
        ],
        "CARD_24": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card24-enter"},
                "priority",
                actor="P1",
            ),
            decision("semantic_player", "P2", "target", actor="P1"),
        ],
        "CARD_25": [
            decision(
                "attacker_assignment", {"obj:card25-attacker": "P2"}, "declare_attacker", actor="P1"
            ),
            decision(
                "blocker_assignment",
                {"obj:card25-blocker": "obj:card25-attacker"},
                "declare_blocker",
                actor="P2",
            ),
        ],
        "CARD_26": [decision("semantic_mode_key", "create_devils", "choose_mode", actor="P1")],
        "CARD_27": [
            decision(
                "semantic_action",
                {"action": "activate_mana", "source": "obj:card_27-subject", "color": "R"},
                "priority",
                actor="P1",
            ),
            decision(
                "semantic_action",
                {
                    "action": "cast",
                    "object": "obj:card27-warrior",
                    "required_mana_source": "obj:card_27-subject",
                },
                "priority",
                actor="P1",
            ),
            decision(
                "boolean",
                False,
                "choose_use",
                actor="P1",
                notes="Scry 1: false means keep the known top card on top rather than put it on bottom.",
            ),
        ],
        "CARD_28": [
            decision(
                "semantic_action",
                {"action": "cast_split_half", "object": "obj:card_28-subject", "half": "Finality"},
                "priority",
                actor="P1",
            ),
            decision("semantic_object", "obj:card28-p1-creature", "choose_object", actor="P1"),
        ],
        "CARD_29": [
            decision(
                "semantic_action",
                {"action": "cast", "object": "obj:card_29-subject"},
                "priority",
                actor="P1",
            ),
            decision(
                "semantic_object_set",
                ["obj:card29-lib-forest-0", "obj:card29-lib-forest-1"],
                "choose_object",
                actor="P1",
            ),
            decision("semantic_object", "obj:card29-gy-forest", "target", actor="P1"),
        ],
    }
    r["decision_script"] = card_decisions[fid]
    if fid == "CARD_21":
        r["temporal_state"] = temporal(phase="combat", step="combat_damage", priority="P1")
        r["combat_state"] = {
            "attackers": {"obj:card21-creature": "P2"},
            "unblocked": ["obj:card21-creature"],
        }
    r["expected_events"] = event_assert(events)
    r["terminal_postconditions"] = posts


# ---------- build ----------
records = []
for category, ids in CATEGORY_IDS.items():
    for fid in ids:
        r = base_record(fid, category)
        if category == "player_count":
            build_player_count(fid, r)
        elif category == "pilot_boundary":
            build_pilot(fid, r)
        elif category == "pilot_boundary_negative":
            build_negative(fid, r)
        elif category == "hidden_information":
            build_hidden(fid, r)
        elif category == "replay_rng":
            build_replay(fid, r)
        elif category == "micro_rules":
            build_micro(fid, r)
        elif category == "actual_card":
            build_card(fid, r)
        elif category == "multiplayer_commander":
            build_mp(fid, r)
        else:
            raise KeyError(category)
        r["materialization_digest"] = sha(r)
        records.append(r)

corpus = {
    "schema_version": SCHEMA_ID,
    "protocol": RSP,
    "common_fixture_manifest_sha256": COMMON_SHA,
    "record_count": len(records),
    "family_counts": dict(Counter(r["fixture_family"] for r in records)),
    "records": records,
}
# canonical bundle digest is digest of full corpus before top-level digest field
corpus_digest = sha(corpus)
corpus["canonical_bundle_digest"] = corpus_digest

schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_ID,
    "title": "Commander Lab Semantic Fixture Materialization v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "protocol",
        "common_fixture_manifest_sha256",
        "record_count",
        "family_counts",
        "records",
        "canonical_bundle_digest",
    ],
    "properties": {
        "schema_version": {"const": SCHEMA_ID},
        "protocol": {"const": RSP},
        "common_fixture_manifest_sha256": {"const": COMMON_SHA},
        "record_count": {"const": 135},
        "family_counts": {"type": "object"},
        "canonical_bundle_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "records": {
            "type": "array",
            "minItems": 135,
            "maxItems": 135,
            "items": {"$ref": "#/$defs/record"},
        },
    },
    "$defs": {
        "player": {
            "type": "object",
            "required": [
                "player_id",
                "seat",
                "starting_life",
                "life",
                "poison",
                "lost",
                "eliminated",
            ],
            "properties": {
                "player_id": {"pattern": "^P[1-5]$"},
                "seat": {"type": "integer", "minimum": 1, "maximum": 5},
                "starting_life": {"type": "integer"},
                "life": {"type": "integer"},
                "poison": {"type": "integer", "minimum": 0},
                "lost": {"type": "boolean"},
                "eliminated": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "object": {
            "type": "object",
            "required": [
                "semantic_id",
                "card_identity",
                "owner",
                "controller",
                "zone",
                "tapped",
                "face_down",
                "counters",
                "card_lineage_id",
            ],
            "properties": {
                "semantic_id": {"type": "string", "minLength": 1},
                "card_identity": {"type": "string", "minLength": 1},
                "owner": {"pattern": "^P[1-5]$"},
                "controller": {"pattern": "^P[1-5]$"},
                "zone": {
                    "enum": [
                        "command",
                        "library",
                        "hand",
                        "battlefield",
                        "graveyard",
                        "exile",
                        "stack",
                        "revealed",
                    ]
                },
                "tapped": {"type": "boolean"},
                "face_down": {"type": "boolean"},
                "counters": {"type": "object"},
                "card_lineage_id": {"type": "string"},
                "zone_position": {"type": "integer", "minimum": 0},
                "attached_to": {"type": "string"},
                "commander_id": {"type": "string"},
                "construction_notes": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        "decision": {
            "type": "object",
            "required": ["decision_family", "actor", "selection", "forbidden_fallbacks", "notes"],
            "properties": {
                "decision_family": {"type": "string"},
                "actor": {"pattern": "^P[1-5]$"},
                "selection": {
                    "type": "object",
                    "required": [
                        "selector_kind",
                        "semantic_value",
                        "matches_only_provider_offered_legal_options",
                        "on_zero_match",
                        "on_multiple_match",
                    ],
                    "properties": {
                        "selector_kind": {
                            "type": "string",
                            "not": {"pattern": "(?i)(first|random|index)"},
                        },
                        "semantic_value": {},
                        "matches_only_provider_offered_legal_options": {"const": True},
                        "on_zero_match": {"const": "FAIL_CLOSED"},
                        "on_multiple_match": {"const": "FAIL_CLOSED"},
                    },
                    "additionalProperties": False,
                },
                "forbidden_fallbacks": {
                    "type": "array",
                    "contains": {"const": "first_option"},
                    "minItems": 7,
                },
                "notes": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "record": {
            "type": "object",
            "required": [
                "fixture_id",
                "materialization_version",
                "fixture_family",
                "materialization_status",
                "authority_provenance",
                "frozen_contract_binding",
                "players",
                "commander_state",
                "semantic_objects",
                "temporal_state",
                "knowledge_state",
                "rules_randomness",
                "decision_script",
                "expected_events",
                "terminal_postconditions",
                "normalization",
                "setup_validation",
                "scenario_notes",
                "materialization_digest",
            ],
            "properties": {
                "fixture_id": {"type": "string"},
                "materialization_version": {"const": SCHEMA_ID},
                "fixture_family": {"enum": list(CATEGORY_IDS)},
                "materialization_status": {
                    "enum": ["OBLIGATION_PRESERVED", "MATERIALIZATION_BLOCKED_CONTRACT_AMBIGUITY"]
                },
                "authority_provenance": {"type": "object"},
                "frozen_contract_binding": {
                    "type": "object",
                    "required": ["manifest_fixture_id", "manifest_sha256", "af_mapping"],
                    "properties": {
                        "manifest_fixture_id": {"type": "string"},
                        "manifest_sha256": {"const": COMMON_SHA},
                        "af_mapping": {"const": "INHERIT_BY_REFERENCE_NO_REDEFINITION"},
                    },
                    "additionalProperties": False,
                },
                "players": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 5,
                    "items": {"$ref": "#/$defs/player"},
                },
                "commander_state": {"type": "object"},
                "semantic_objects": {"type": "array", "items": {"$ref": "#/$defs/object"}},
                "temporal_state": {"type": "object"},
                "knowledge_state": {"type": "object"},
                "rules_randomness": {
                    "type": "object",
                    "required": [
                        "rules_seed",
                        "channels",
                        "predetermined_semantic_draws",
                        "pilot_randomness_prohibited",
                    ],
                },
                "decision_script": {"type": "array", "items": {"$ref": "#/$defs/decision"}},
                "expected_events": {
                    "type": "object",
                    "required": [
                        "required_events",
                        "forbidden_events",
                        "ordering_constraints",
                        "partial_order_constraints",
                    ],
                },
                "terminal_postconditions": {"type": "array", "items": {"type": "string"}},
                "normalization": {"type": "object"},
                "setup_validation": {"type": "object"},
                "scenario_notes": {"type": "array", "items": {"type": "string"}},
                "materialization_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                "deck_state": {"type": "array"},
                "negative_fallback_probe": {"type": "object"},
                "combat_state": {"type": "object"},
                "stack_state": {"type": "array"},
                "continuous_rules_effects": {"type": "array"},
                "replay_contract": {"type": "object"},
                "priority_script": {"type": "array"},
                "extra_turn_creation": {"type": "array"},
                "elimination_trigger": {"type": "object"},
                "zone_move_event": {"type": "object"},
                "card_authority_binding": {"type": "object"},
            },
            "additionalProperties": False,
        },
    },
}

blockers = {
    "schema_version": "ws30-materialization-blockers/1.0.0",
    "blocker_count": 0,
    "records": [],
    "gate": "AMBIGUITY != MATERIALIZED",
    "note": "No frozen obligation required choosing a new Magic semantic outcome; each scenario is a minimal deterministic representative whose legality/outcome remains provider-native and authority-bound.",
}
authmap = {
    "schema_version": "ws30-materialization-authority-map/1.0.0",
    "source_locks": {
        "canonical_main": {"commit": MAIN_SHA, "tree": MAIN_TREE},
        "ws29_neutral_base": {"commit": BASE_SHA, "tree": BASE_TREE},
        "common_manifest": {
            "path": "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json",
            "sha256": COMMON_SHA,
        },
        "ws10r": {"protocol": RSP, "path": "qualification/protocol/ws10r/"},
        "ws29_expected_semantics": {
            "path": "qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json",
            "card_fixture_count": 29,
        },
        "ws29_cr_pdf": {"sha256": CR_SHA, "effective_date": "2026-08-07"},
        "coordinator_schema_draft": {
            "declared_sha256": "a095c906f89c62805595cbac25488d07e201ca7b7e626098ae93cb883dc2ec6e",
            "content_available_during_ws30": False,
            "normative": False,
        },
        "ws28": {
            "final_handoff_head": "525bbe141ac2d6266c2278acc436c3a8576a0f8b",
            "neutral_orchestration_head": "a93748470f2fac79ca94fe7ec770e65051ff32da",
        },
    },
    "fixture_authority": {r["fixture_id"]: r["authority_provenance"] for r in records},
}

starter = {
    "schema_version": "ws30-differential-starter-18/1.0.0",
    "fixture_count": 18,
    "fixture_ids": STARTER18,
    "records": [
        copy.deepcopy(next(r for r in records if r["fixture_id"] == fid)) for fid in STARTER18
    ],
    "credit": "NONE: canonical materialization only; independent PASS is not differential verification.",
}
union = {
    "schema_version": "ws30-known-pass-union-50/1.0.0",
    "fixture_count": 50,
    "fixture_ids": UNION50,
    "historical_provenance_only": {
        "shared_18": STARTER18,
        "forge_only_16": FORGE_ONLY,
        "xmage_only_16": XMAGE_ONLY,
    },
    "records": [
        copy.deepcopy(next(r for r in records if r["fixture_id"] == fid)) for fid in UNION50
    ],
    "credit": "NONE: provider labels are provenance only and do not affect normative scenario state.",
}

review_intro = """# WS-30 CRITICAL 18 MANUAL SEMANTIC REVIEW\n\nThis review is mandatory because WS-28 proved that same fixture ID did not imply equivalent historical setup. Each entry below explains why the WS-30 scenario preserves the frozen obligation and why neither historical provider setup is normative. Candidate behavior is evidence only.\n\n"""
review_notes = {
    "PLAYER_COUNT_2P": "Commander lifecycle with 2 real players, 40 life, Rograkh + 99 Mountains, command-zone commander and real opening hand. This follows the Commander-centric production contract rather than Forge 20-life technical lifecycle or XMage Isamaru/Plains history.",
    "PLAYER_COUNT_3P": "Same canonical Commander lifecycle expanded to exactly 3 real seats; identity is seat/player semantic, not engine seat object.",
    "PLAYER_COUNT_4P": "Exactly four Commander players with identical neutral deck template and lifecycle. This is the decision-evidence default pod size but receives no candidate credit.",
    "PLAYER_COUNT_5P": "Exactly five Commander players using dynamic live-player semantics; proves the technical 5P production scope without copying either finalist setup.",
    "PILOT_MULLIGAN": "Uses a real 4P Commander pregame hand and the multiplayer free-first-mulligan rule. The tested obligation is external discretionary mulligan selection from provider legal options; setup is neutral and fail-closed.",
    "PILOT_PRIORITY": "P1 receives a provider DecisionFrame at priority with a concrete Lightning Bolt cast available. The selector identifies the semantic cast/target, never option number or candidate action ID.",
    "PILOT_TARGET": "Lightning Bolt target selection is concrete and deterministic; P2 is selected only if the Rules Core offers P2 as legal. Historical Bolt versus hidden-target candidate setups are not reused.",
    "HIDDEN_01": "P1 observes P2 hand count while the deterministic honey-card identity and metadata remain prohibited on all pilot-visible channels. This directly materializes count-visible/identity-hidden.",
    "HIDDEN_02": "P1 observes P2 library count while identity and order are prohibited. No historical provider hidden-zone probe is authoritative.",
    "MICRO_STACK": "Bolt is already on stack targeting P2 Grizzly Bears; P2 responds with Giant Growth, so native stack LIFO resolution and final survival are directly testable. Stable semantic IDs replace engine stack IDs.",
    "MICRO_REPLACEMENT": "A deterministic 3-damage creature event under Gratuitous Violence tests a replacement effect as 3->6. This deliberately avoids adopting either historical commander-zone or Rest in Peace scenario.",
    "WS05-MP-COMBAT-4": "P1 assigns distinct attackers to P2 and P3 in one declaration. This directly tests multiple defending players and preserves defender identity without borrowing historical Bears/Runeclaw layouts.",
    "RNG_RULES_TAPE": "The common replay experiment records a provider-native library shuffle on RulesRngTape; pilot mode choice is separately on DecisionTape. Semantic randomness is replayed, not raw PRNG identity.",
    "REPLAY_DECISION_TAPE": "The exact create-devils semantic selector and its matched semantic option projection are recorded. Provider option IDs are not cross-provider identity.",
    "REPLAY_EVENT_TAPE": "Meaningful normalized shuffle/decision/token events are recorded while internal event chatter may vary.",
    "REPLAY_CLEAN_PROCESS": "A fresh process reconstructs the same initial digest and replays RulesRngTape + DecisionTape to equal semantic checkpoints; raw UUID/process identity is ignored.",
    "REPLAY_STATE_HASHES": "Privileged/public/P1-scoped semantic hashes are checkpointed with process-local identities excluded, preserving WS-06 hidden-information boundaries.",
    "CARD_02": "Rograkh starts as P1 commander in command zone with zero prior command-zone casts; P1 casts it for printed cost 0 and zero tax. This is directly keyed to WS-29 CARD_02 authority rather than either finalist history.",
}
review = review_intro
for i, fid in enumerate(STARTER18, 1):
    review += f"## {i}. `{fid}`\n\n**OBLIGATION_PRESERVED.** {review_notes[fid]}\n\nIndependence check: the normative record contains no provider-local IDs, candidate action IDs, candidate setup objects, or candidate event-count assumptions. Native setup validation must fail closed if a provider cannot construct it faithfully.\n\n"

# write files
files = {
    "SEMANTIC_FIXTURE_SCHEMA_v1.json": schema,
    "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json": corpus,
    "MATERIALIZATION_BLOCKERS.json": blockers,
    "MATERIALIZATION_AUTHORITY_MAP.json": authmap,
    "DIFFERENTIAL_STARTER_18.json": starter,
    "KNOWN_PASS_UNION_50.json": union,
}
for name, data in files.items():
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
(OUT / "CRITICAL_18_MANUAL_REVIEW.md").write_text(review, encoding="utf-8")
mat_sha = hashlib.sha256(
    (OUT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json").read_bytes()
).hexdigest()
(OUT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.sha256").write_text(
    f"{mat_sha}  SEMANTIC_FIXTURE_MATERIALIZATION_v1.json\n"
)
# checksums excluding manifest itself
names = [
    "SEMANTIC_FIXTURE_SCHEMA_v1.json",
    "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json",
    "SEMANTIC_FIXTURE_MATERIALIZATION_v1.sha256",
    "MATERIALIZATION_BLOCKERS.json",
    "MATERIALIZATION_AUTHORITY_MAP.json",
    "DIFFERENTIAL_STARTER_18.json",
    "KNOWN_PASS_UNION_50.json",
    "CRITICAL_18_MANUAL_REVIEW.md",
]
lines = []
for name in names:
    lines.append(f"{hashlib.sha256((OUT / name).read_bytes()).hexdigest()}  {name}")
(OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n")
print("records", len(records), "families", Counter(r["fixture_family"] for r in records))
print("canonical_bundle_digest", corpus_digest)
print("materialization_file_sha256", mat_sha)
