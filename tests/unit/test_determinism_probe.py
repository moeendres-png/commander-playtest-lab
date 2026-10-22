"""The determinism probe finds the first request on which two games of one seed disagree.

No JVM runs here. The games are lists of recorded request/answer pairs; the probe must call
two relabelled copies of one game the same game and two games that differ in what a pilot is
asked (the symptom of an iteration-order dependency) different, at the right decision.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "determinism_probe.py"
spec = importlib.util.spec_from_file_location("determinism_probe_under_test", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"
UUID_C = "33333333-3333-4333-8333-333333333333"
UUID_D = "44444444-4444-4444-8444-444444444444"
STATE_HASH = "ab" * 32


def _record(
    index: int, uuids: tuple[str, str], abilities: tuple[str, str] = ("deathtouch", "lifelink")
) -> dict[str, Any]:
    first, second = uuids
    return {
        "request": {
            "decision_id": f"decision-{first}",
            "game_id": first,
            "decision_class": "priority",
            "public_state_reference": STATE_HASH,
            "pilot_state": {
                "turn_number": 3 + index,
                "permanents": [
                    {"id": first, "abilities": [abilities[0]]},
                    {"id": second, "abilities": [abilities[1]]},
                ],
            },
            "legal_options": [
                {"option_id": f"pass-{first}", "option_type": "pass_priority"},
                {"option_id": f"cast-{second}", "option_type": "activated_ability"},
            ],
        },
        "answer": {"selected_option_ids": [f"pass-{first}"]},
    }


def _game(
    uuids: tuple[str, str], swap_from: int | None = None, length: int = 6
) -> list[dict[str, Any]]:
    records = []
    for index in range(length):
        swapped = swap_from is not None and index >= swap_from
        abilities = ("lifelink", "deathtouch") if swapped else ("deathtouch", "lifelink")
        records.append(_record(index, uuids, abilities))
    return records


def test_a_relabelled_copy_of_a_game_is_the_same_game() -> None:
    left = probe.rows_of(_game((UUID_A, UUID_B)))
    right = probe.rows_of(_game((UUID_C, UUID_D)))
    assert probe.first_difference(left, right) is None


def test_the_first_request_that_differs_in_content_is_named_with_its_path() -> None:
    left = probe.rows_of(_game((UUID_A, UUID_B)))
    right = probe.rows_of(_game((UUID_C, UUID_D), swap_from=4))
    difference = probe.first_difference(left, right)
    assert difference is not None
    assert difference["decision"] == 4
    assert difference["decision_class"] == "priority"
    assert difference["turn"] == 7
    paths = {item["path"] for item in difference["paths"]}
    assert ".req.pilot_state.permanents[0].abilities[0]" in paths
    assert [c["decision"] for c in difference["context"]] == [1, 2, 3]


def test_normalising_does_not_hide_which_object_has_which_ability() -> None:
    """Negative control: relabelling ids must keep two objects apart (a swap is a swap)."""
    swapped = _game((UUID_A, UUID_B), swap_from=0)
    plain = _game((UUID_A, UUID_B))
    assert probe.first_difference(probe.rows_of(plain), probe.rows_of(swapped)) is not None


def test_a_changed_answer_is_a_difference() -> None:
    left_game, right_game = _game((UUID_A, UUID_B)), _game((UUID_C, UUID_D))
    right_game[2]["answer"]["selected_option_ids"] = [f"cast-{UUID_D}"]
    difference = probe.first_difference(probe.rows_of(left_game), probe.rows_of(right_game))
    assert difference is not None and difference["decision"] == 2
    assert ".ans.selected_option_ids[0]" in {item["path"] for item in difference["paths"]}
    comparison = probe.compare_games(probe.rows_of(left_game), probe.rows_of(right_game))
    assert comparison["verdict"] == probe.ANSWERS_DIFFER
    assert comparison["first_answer"]["decision"] == 2
    assert comparison["answers_differing"] == 1


def test_ids_that_are_the_same_object_keep_being_the_same_after_relabelling() -> None:
    """The option and the permanent share one id: it stays one label, not two."""
    value = {"a": UUID_A, "b": [UUID_B, UUID_A], "c": STATE_HASH, "d": f"x {UUID_B}"}
    out = probe.normalise(value)
    assert out["a"] == out["b"][1] != out["b"][0]
    assert out["d"].endswith(out["b"][0])
    assert out["c"].startswith("u")


def test_a_game_that_is_a_prefix_of_another_differs_at_its_end() -> None:
    long = probe.rows_of(_game((UUID_A, UUID_B), length=6))
    short = probe.rows_of(_game((UUID_C, UUID_D), length=4))
    difference = probe.first_difference(long, short)
    assert difference is not None
    assert difference["decision"] == 4
    assert difference["paths"] == []
    comparison = probe.compare_games(long, short)
    assert comparison["verdict"] == probe.ANSWERS_DIFFER
    assert comparison["decisions"] == [6, 4]


def test_the_report_names_decision_class_turn_and_the_differing_value() -> None:
    left = probe.rows_of(_game((UUID_A, UUID_B)))
    right = probe.rows_of(_game((UUID_C, UUID_D), swap_from=1))
    comparison = probe.compare_games(left, right)
    text = probe.report(comparison, label_left="a", label_right="b")
    assert text.startswith("REQUESTS_DIFFER_ANSWERS_SAME")
    assert "at decision 1 (class priority, turn 4)" in text
    assert "abilities[0]" in text and "deathtouch" in text and "lifelink" in text
    same = probe.compare_games(left, left)
    assert probe.report(same, label_left="a", label_right="b").startswith("IDENTICAL")


def test_dumps_round_trip_and_are_byte_identical_for_the_same_rows(tmp_path: Path) -> None:
    rows = probe.rows_of(_game((UUID_A, UUID_B)))
    first, second = tmp_path / "a.jsonl.gz", tmp_path / "b.jsonl.gz"
    probe.write_dump(first, rows)
    probe.write_dump(second, copy.deepcopy(rows))
    assert first.read_bytes() == second.read_bytes()
    assert probe.read_dump(first) == rows


def test_compare_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    same_a, same_b, other = (tmp_path / n for n in ("a.gz", "b.gz", "c.gz"))
    probe.write_dump(same_a, probe.rows_of(_game((UUID_A, UUID_B))))
    probe.write_dump(same_b, probe.rows_of(_game((UUID_C, UUID_D))))
    probe.write_dump(other, probe.rows_of(_game((UUID_C, UUID_D), swap_from=2)))
    assert probe.main(["compare", str(same_a), str(same_b)]) == 0
    assert capsys.readouterr().out.startswith("IDENTICAL")
    assert probe.main(["compare", str(same_a), str(other)]) == 2
    assert "REQUESTS_DIFFER_ANSWERS_SAME" in capsys.readouterr().out


@pytest.mark.parametrize("mode", [0, 1, 2, 3, 4])
def test_perturbation_replaces_the_identity_hash_function(mode: int) -> None:
    assert probe.perturbation_options(mode) == [
        "-XX:+UnlockExperimentalVMOptions",
        f"-XX:hashCode={mode}",
    ]


@pytest.mark.parametrize("mode", [-1, 5, 42])
def test_an_unknown_identity_hash_mode_is_refused(mode: int) -> None:
    with pytest.raises(ValueError, match="identity hash mode"):
        probe.perturbation_options(mode)


def test_locate_needs_four_decks_or_the_real_pod() -> None:
    with pytest.raises(SystemExit, match="real-pod"):
        probe.main(["locate", "--jar", "x.jar", "--seed", "1", "--decks", "a", "b"])
    with pytest.raises(SystemExit, match="unknown precon"):
        probe.main(["locate", "--jar", "x.jar", "--seed", "1", "--decks", "a", "b", "c", "d"])


def test_a_fragment_of_an_object_id_in_a_prompt_is_not_a_difference() -> None:
    left_game, right_game = _game((UUID_A, UUID_B)), _game((UUID_C, UUID_D))
    left_game[1]["request"]["prompt"] = "{1}<font object_id='" + UUID_A + "'>Spire</font> [fd0]"
    right_game[1]["request"]["prompt"] = "{1}<font object_id='" + UUID_C + "'>Spire</font> [661]"
    comparison = probe.compare_games(probe.rows_of(left_game), probe.rows_of(right_game))
    assert comparison["verdict"] == probe.IDENTICAL
    right_game[1]["request"]["prompt"] = "{2}<font object_id='" + UUID_C + "'>Spire</font> [661]"
    comparison = probe.compare_games(probe.rows_of(left_game), probe.rows_of(right_game))
    assert comparison["requests_differing"] == 1


def _reordered(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = copy.deepcopy(records)
    for record in out:
        record["request"]["pilot_state"]["permanents"].reverse()
    return out


def test_a_list_in_another_order_with_the_same_choices_is_a_latent_dependency() -> None:
    """The commander list of the real pod: another order, the same game."""
    left = probe.rows_of(_game((UUID_A, UUID_B)))
    right = probe.rows_of(_reordered(_game((UUID_C, UUID_D))))
    comparison = probe.compare_games(left, right)
    assert comparison["verdict"] == probe.REQUESTS_DIFFER
    assert comparison["requests_differing"] == 6
    assert comparison["answers_differing"] == 0
    assert comparison["first_answer"] is None
    kinds = [pattern for pattern, _ in comparison["patterns"]]
    assert ".pilot_state.permanents[].abilities[]" in kinds
    assert probe.exit_code(comparison, hashes_equal=True) == 2


def test_exit_codes_follow_the_verdict_and_the_hash() -> None:
    game = probe.rows_of(_game((UUID_A, UUID_B)))
    changed = probe.rows_of(_game((UUID_C, UUID_D), swap_from=2))
    other_choice = _game((UUID_C, UUID_D))
    other_choice[3]["answer"]["selected_option_ids"] = [f"cast-{UUID_D}"]
    same = probe.compare_games(game, game)
    assert probe.exit_code(same, hashes_equal=True) == 0
    assert probe.exit_code(same, hashes_equal=None) == 0
    assert probe.exit_code(same, hashes_equal=False) == 1  # same requests, another hash
    assert probe.exit_code(probe.compare_games(game, changed), hashes_equal=True) == 2
    parted = probe.compare_games(game, probe.rows_of(other_choice))
    assert probe.exit_code(parted, hashes_equal=False) == 1
    assert probe.exit_code(parted, hashes_equal=True) == 1


def _noisy(order: tuple[str, str], exile: tuple[str, str]) -> list[dict[str, Any]]:
    """A game whose only difference is the order of lists the bridge fills from UUID keys."""
    records = _game((UUID_A, UUID_B))
    for record in records:
        state = record["request"]["pilot_state"]
        state["commander_status"] = [
            {
                "name": n,
                "commander_damage_to_player": [{"player_id": "op-3"}, {"player_id": "op-1"}],
            }
            for n in order
        ]
        state["players"] = [
            {"command": [{"name": n} for n in order], "exile": [{"name": n} for n in exile]}
        ]
    return records


def test_lists_that_come_in_a_random_order_are_sorted_before_comparing() -> None:
    left = probe.rows_of(_noisy(("Rograkh", "Ishai"), ("Sol Ring", "Serra Paragon")))
    right = probe.rows_of(_noisy(("Ishai", "Rograkh"), ("Serra Paragon", "Sol Ring")))
    assert probe.compare_games(left, right)["verdict"] == probe.IDENTICAL
    raw_left = probe.rows_of(
        _noisy(("Rograkh", "Ishai"), ("Sol Ring", "Serra Paragon")), sort_noise=False
    )
    raw_right = probe.rows_of(
        _noisy(("Ishai", "Rograkh"), ("Serra Paragon", "Sol Ring")), sort_noise=False
    )
    raw = probe.compare_games(raw_left, raw_right)
    assert raw["verdict"] == probe.REQUESTS_DIFFER
    assert ".pilot_state.commander_status[].name" in raw["pattern_counts"]


def test_sorting_the_known_lists_does_not_hide_a_changed_member() -> None:
    """Negative control: a commander that is not in the other game is still a difference."""
    left = probe.rows_of(_noisy(("Rograkh", "Ishai"), ("Sol Ring", "Serra Paragon")))
    right = probe.rows_of(_noisy(("Ishai", "Kenrith"), ("Serra Paragon", "Sol Ring")))
    comparison = probe.compare_games(left, right)
    assert comparison["verdict"] == probe.REQUESTS_DIFFER
    assert comparison["requests_differing"] == 6


def test_a_list_that_is_not_known_to_be_random_keeps_its_order() -> None:
    """Negative control: the battlefield order is a difference, only the named lists are sorted."""
    left, right = _game((UUID_A, UUID_B)), _game((UUID_C, UUID_D))
    for record in right:
        record["request"]["pilot_state"]["permanents"].reverse()
    assert probe.compare_games(probe.rows_of(left), probe.rows_of(right))["verdict"] != (
        probe.IDENTICAL
    )


@pytest.mark.parametrize(("text", "expected"), [("none", None), ("0", 0), ("4", 4)])
def test_mode_argument_accepts_none_and_the_five_modes(text: str, expected: int | None) -> None:
    assert probe._mode(text) == expected


@pytest.mark.parametrize("text", ["5", "-1", "x", ""])
def test_mode_argument_refuses_anything_else(text: str) -> None:
    import argparse

    with pytest.raises(argparse.ArgumentTypeError, match="mode must be"):
        probe._mode(text)
