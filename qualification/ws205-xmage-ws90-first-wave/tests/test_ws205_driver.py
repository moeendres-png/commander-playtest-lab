"""Focused qualification-driver tests for WS205 (no JVM required).

Validates deck construction legality shape, pilot-version binding, seed
neutrality, semantic transcript normalization, and aggregate accounting.
"""

import json
import sys
from pathlib import Path

import pytest

WS205_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS205_ROOT))

import ws205_driver as driver  # noqa: E402

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest"}


def test_slot_order_is_exact_corrected_denominator():
    assert driver.SLOT_ORDER == [
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


def test_seeds_fixed_neutrally_before_execution():
    # Neutral rule: 9101 + slot index; H01 controls offset. No outcome tuning.
    for index, slot in enumerate(driver.SLOT_ORDER):
        assert driver.SEEDS[slot] == 9101 + index
    assert driver.SEEDS["RQ-C3-H01-CLONE_FIRST"] == 9213
    assert driver.SEEDS["RQ-C3-H01-NO_HUMILITY"] == 9313
    assert len(set(driver.SEEDS.values())) == len(driver.SEEDS)


def test_engine_pin_and_policy_version_pinned():
    assert driver.ENGINE_PIN == "cfc36f445f917f101fa2ed588770e043f53bc44c"
    assert driver.POLICY_VERSION == "ws205-pilot-v1"
    assert driver.CANDIDATE_HEAD == "5994019b4da59e27a388eec47e6805404bd98df9"


@pytest.mark.parametrize("slot", driver.SLOT_ORDER)
def test_decks_are_commander_legal_shape(slot):
    subcases = ["HUMILITY_FIRST", "CLONE_FIRST", "NO_HUMILITY"] if slot == "RQ-C3-H01" else [""]
    for subcase in subcases:
        decks = driver.build_decks(slot, subcase)
        assert set(decks) == {"seat0", "seat1", "seat2", "seat3"}
        for seat, spec in decks.items():
            assert len(spec["mainboard"]) + len(spec["commanders"]) == 100
            assert 1 <= len(spec["commanders"]) <= 2
            for commander in spec["commanders"]:
                assert commander not in spec["mainboard"]
            non_basic = [c for c in spec["mainboard"] if c not in BASIC_LANDS]
            assert len(non_basic) == len(set(non_basic)), (
                f"{slot}/{subcase}/{seat}: duplicate non-basic {non_basic}"
            )


def test_h01_controls_differ_only_by_humility_presence():
    a = driver.build_decks("RQ-C3-H01", "HUMILITY_FIRST")
    b = driver.build_decks("RQ-C3-H01", "CLONE_FIRST")
    c = driver.build_decks("RQ-C3-H01", "NO_HUMILITY")
    assert "Humility" in a["seat2"]["mainboard"]
    assert "Humility" in b["seat2"]["mainboard"]
    assert "Humility" not in c["seat2"]["mainboard"]
    assert "Clone" in a["seat0"]["mainboard"]
    assert "Runeclaw Bear" in a["seat1"]["mainboard"]


def test_choice_wishes_mirror_priority_cast_names():
    for slot in driver.SLOT_ORDER:
        prefs = driver.build_prefs(slot)
        if "priority" not in prefs:
            continue
        for seat, names in prefs["priority"].items():
            for name in names:
                assert name in prefs["choice"].get(seat, []), (
                    f"{slot} seat {seat}: priority wish {name!r} missing from choice"
                )


def test_semantic_transcript_excludes_role_metadata_and_ids():
    evidence = {
        "decision_stream": [
            {
                "offset": 1,
                "class": "priority",
                "actor_seat": 0,
                "offered_count": 2,
                "offered_types": [{"type": "pass_priority", "count": 1}],
                "selected_label": "Pass priority",
                "selection_basis": "twin_stream:Pass priority",
            }
        ],
        "assertion_state": {
            "battlefield": [
                {
                    "name": "Island",
                    "controller_seat": 0,
                    "power": 0,
                    "toughness": 0,
                    "is_copy": False,
                    "abilities": 2,
                }
            ],
            "seats": [
                {
                    "seat": 0,
                    "life": 40,
                    "hand_size": 7,
                    "library_size": 92,
                    "graveyard": ["Lightning Bolt"],
                }
            ],
        },
    }
    transcript = driver.semantic_transcript(evidence)
    flat = json.dumps(transcript)
    assert "twin_stream" not in flat
    assert "selection_basis" not in flat
    assert transcript[0]["selected_label"] == "Pass priority"
    assert transcript[-2] == {
        "terminal_board": [
            {
                "name": "Island",
                "controller_seat": 0,
                "power": 0,
                "toughness": 0,
                "is_copy": False,
                "ability_count": 2,
            }
        ]
    }


def test_normalize_label_strips_process_identity():
    dirty = "Foo f594d3f0-e5ae-05af-38b9-856abeef9597 bar ABCDEF1234567890"
    clean = driver.normalize_label(dirty)
    assert "f594d3f0" not in clean
    assert "ABCDEF1234567890" not in clean
    assert "Foo" in clean and "bar" in clean


def test_transcript_hash_deterministic_and_sensitive():
    transcript = [{"offset": 1, "class": "pass", "selected_label": "Pass priority"}]
    assert driver.transcript_hash(transcript) == driver.transcript_hash(transcript)
    altered = [{"offset": 1, "class": "pass", "selected_label": "Keep opening hand"}]
    assert driver.transcript_hash(transcript) != driver.transcript_hash(altered)


def test_smoke_evidence_present_and_well_formed():
    primary = WS205_ROOT / "slots/RQ-C3-A03/primary.json"
    twin_record = WS205_ROOT / "slots/RQ-C3-A03/twin.record.json"
    assert primary.exists(), "smoke primary evidence missing"
    evidence = json.loads(primary.read_text())
    assert evidence["engine_pin"] == driver.ENGINE_PIN
    assert evidence["decision_policy_version"] == driver.POLICY_VERSION
    assert evidence["seed"] == driver.SEEDS["RQ-C3-A03"]
    assert evidence["decisions_answered"] > 0
    assert evidence["negative_controls"]["unadvanced"] is True
    assert "REJECTED" in evidence["negative_controls"]["wrong_actor"]
    assert "REJECTED" in evidence["negative_controls"]["unknown_action"]
    record = json.loads(twin_record.read_text())
    assert record["semantic_replay_match"] is True
    assert record["semantic_transcript_hash"] == record["twin_semantic_transcript_hash"]
