"""The normalized frame digest: what it ignores (run identity) and what it must notice."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable

from commander_lab.engine.rules.frame_digest import (
    EXCLUDED_TRANSPORT_FIELDS,
    FrameDigest,
    normalize_frame,
)
from commander_lab.engine.rules.full_game import XmageFullGameRunner

_UUIDS = [
    "8714de73-4d29-4e52-8b63-a7db64c1875c",
    "0b9a1c2e-1111-4222-8333-444455556666",
    "7c1d2e3f-aaaa-4bbb-8ccc-ddddeeeeffff",
    "11111111-2222-4333-8444-555555555555",
]


def _frame(uuids: list[str], *, opp_hand: str = "Island", life: int = 40) -> dict[str, object]:
    me, bolt, bear, other = uuids
    return {
        "protocol_version": "proto-1",
        "protocol_identity": "proto-1",
        "game_id": "99999999-0000-4000-8000-000000000000",
        "decision_id": "d" * 64,
        "actor_id": me,
        "seat": 1,
        "decision_class": "priority",
        "prompt": f"Cast <font object_id='{bolt}'>Bolt</font> [3a4]",
        "timeout_millis": 120000,
        "public_state_reference": "public-view:" + "a" * 64,
        "legal_options": [
            {"option_id": "1" * 64, "label": "Cast Bolt", "metadata": {"object_id": bolt}},
            {"option_id": "2" * 64, "label": "Pass", "metadata": {}},
        ],
        "pilot_state": {
            "players": [
                {
                    "player_id": me,
                    "life": life,
                    "hand": [{"title": "Bolt [3a4]", "object_id": bolt}],
                    "battlefield": [
                        {"name": "Bear", "object_id": bear},
                        {"name": "Elf", "object_id": other},
                    ],
                },
                {"player_id": "op-0", "life": 40, "hand": [{"title": opp_hand}]},
            ],
            "commander_status": [
                {"owner_id": me, "name": "A", "commander_damage_to_player": []},
                {
                    "owner_id": "op-0",
                    "name": "B",
                    "commander_damage_to_player": [{"player_id": me}],
                },
            ],
        },
    }


def _digest(*frames: dict[str, object]) -> str:
    digest = FrameDigest()
    for frame in frames:
        digest.observe(frame)
    return digest.result().digest


def test_identical_frames_give_identical_digests() -> None:
    assert _digest(_frame(_UUIDS)) == _digest(_frame(_UUIDS))


def test_consistently_different_uuid_values_do_not_change_the_digest() -> None:
    other = [str(uuid).replace("1", "e").replace("a", "5") for uuid in _UUIDS]
    assert other != _UUIDS
    base = _frame(_UUIDS)
    changed = _frame(other)
    changed["game_id"] = "11112222-3333-4444-8555-666677778888"
    # derived hashes differ in every run as well
    changed["decision_id"] = "e" * 64
    changed["public_state_reference"] = "public-view:" + "b" * 64
    changed["legal_options"][0]["option_id"] = "9" * 64  # type: ignore[index]
    changed["legal_options"][1]["option_id"] = "8" * 64  # type: ignore[index]
    assert _digest(base, base) == _digest(changed, changed)


def test_transport_fields_are_excluded_and_nothing_else() -> None:
    assert {"timeout_millis", "protocol_version", "protocol_identity"} == EXCLUDED_TRANSPORT_FIELDS
    base = _frame(_UUIDS)
    other = copy.deepcopy(base)
    other["timeout_millis"] = 1
    other["protocol_version"] = "proto-2"
    other["protocol_identity"] = "proto-2"
    assert _digest(base) == _digest(other)
    other["decision_class"] = "target"
    assert _digest(base) != _digest(other)


def test_short_ids_and_prompt_markup_ids_are_normalized_like_the_transcript() -> None:
    frame = normalize_frame(_frame(_UUIDS))
    assert "[3a4]" not in str(frame) and "object_id='" not in str(frame["prompt"])
    for text in (f"x {_UUIDS[0]} y", "Cast <font>Bolt</font> [3a4]."):
        assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", str(normalize_frame({"prompt": text}))) is None
        assert XmageFullGameRunner._semantic_text(text) != text


def test_the_same_object_stays_visible_twice() -> None:
    frame = normalize_frame(_frame(_UUIDS))
    option = frame["legal_options"][0]["metadata"]["object_id"]  # type: ignore[index]
    hand = frame["pilot_state"]["players"][0]["hand"][0]["object_id"]  # type: ignore[index]
    other = frame["pilot_state"]["players"][0]["battlefield"][0]["object_id"]  # type: ignore[index]
    assert option == hand and option != other and option.startswith("id#")


def _changed(edit: Callable[[dict[str, object]], None]) -> str:
    frame = _frame(_UUIDS)
    edit(frame)
    return _digest(frame)


def test_the_digest_notices_what_the_pilot_was_shown() -> None:
    base = _digest(_frame(_UUIDS))
    assert _digest(_frame(_UUIDS, opp_hand="Mountain")) != base  # an opponent's hand card
    assert _digest(_frame(_UUIDS, life=39)) != base  # a life total

    def swap_battlefield(frame: dict[str, object]) -> None:
        players = frame["pilot_state"]["players"]  # type: ignore[index]
        players[0]["battlefield"].reverse()

    assert _changed(swap_battlefield) != base  # order of two battlefield objects

    def relabel(frame: dict[str, object]) -> None:
        frame["legal_options"][1]["label"] = "Pass priority"  # type: ignore[index]

    assert _changed(relabel) != base  # a legal option label


def test_the_order_of_commander_status_follows_the_run_not_the_pilot() -> None:
    """The bridge fills it from a UUID-keyed map, so its order is run identity."""

    def reverse(frame: dict[str, object]) -> None:
        frame["pilot_state"]["commander_status"].reverse()  # type: ignore[index]

    assert _changed(reverse) == _digest(_frame(_UUIDS))


def test_other_decision_requests_keep_their_order() -> None:
    first, second = _frame(_UUIDS), _frame(_UUIDS, life=39)
    assert _digest(first, second) != _digest(second, first)


def test_per_seat_digests_and_count() -> None:
    a, b = _frame(_UUIDS), _frame(_UUIDS)
    b["seat"] = 2
    digest = FrameDigest()
    for frame in (a, b, a):
        digest.observe(frame)
    result = digest.result()
    assert result.frames == 3 and list(result.by_seat) == ["1", "2"]
    seat_one = FrameDigest()
    for frame in (a, a):
        seat_one.observe(frame)
    # a seat digest covers only that seat's frames, normalized in the game-wide numbering
    assert result.by_seat["1"] != result.by_seat["2"]
    changed = _frame(_UUIDS, life=3)
    changed["seat"] = 2
    other = FrameDigest()
    for frame in (a, changed, a):
        other.observe(frame)
    assert other.result().by_seat["1"] == result.by_seat["1"]
    assert other.result().by_seat["2"] != result.by_seat["2"]


def test_the_semantic_transcript_hash_is_unchanged() -> None:
    """Value computed on the code of origin/main; the digest must not alter this hash."""
    result = {
        "seed": 1,
        "turn_number": 5,
        "decision_count": 3,
        "transcript": [
            {
                "sequence": 0,
                "kind": "decision",
                "decision_class": "priority",
                "actor_seat": 1,
                "prompt": "Cast <font object_id='abc'>Bolt</font> [3a4] "
                "0b9a1c2e-1111-2222-3333-444455556666",
                "selected_option_types": ["pass"],
                "selected_option_labels": ["Pass [12f]"],
                "numeric_choice": None,
            }
        ],
        "outcomes": [{"seat": 0, "life": 3, "won": True, "lost": False, "left": False}],
    }
    semantic = XmageFullGameRunner.semantic_transcript(result)  # type: ignore[arg-type]
    assert (
        XmageFullGameRunner._sha256(semantic)
        == "6e16673fccad6e59bf9b1aeeefc29d4fcb1289e4a2ed599056221b7d4fe84b02"
    )
