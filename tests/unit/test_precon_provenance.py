"""REAL and SYNTHETIC precon decks are labelled and counted apart in import and sweep reports.

A variant copy replaces engine-unknown cards with real ones; it is a test deck and must never
be folded into a figure about the printed precons (#920, Owner decision 2026-10-23).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import precon_provenance as pp  # noqa: E402


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_variant_prefix_marks_synthetic_and_everything_else_is_real() -> None:
    assert pp.deck_provenance({"deck_id": "precon-variant/2023/masters_of_evil"}) == pp.SYNTHETIC
    assert pp.deck_provenance({"deck_id": "precon/2023/masters_of_evil"}) == pp.REAL
    assert pp.deck_provenance({}) == pp.REAL


def test_every_checked_in_variant_is_synthetic_and_no_original_is() -> None:
    variants = sorted((ROOT / "data/decks/precon_variants").glob("*.json"))
    originals = sorted((ROOT / "data/decks/precons").glob("*.json"))
    assert variants and originals
    assert {pp.deck_file_provenance(p) for p in variants} == {pp.SYNTHETIC}
    assert {pp.deck_file_provenance(p) for p in originals} == {pp.REAL}


def test_counts_keep_both_labels_even_when_one_is_absent() -> None:
    assert pp.count_by_provenance([pp.REAL, pp.REAL]) == {pp.REAL: 2, pp.SYNTHETIC: 0}


def test_import_summary_never_merges_the_two_populations() -> None:
    module = _script("measure_precon_imports")
    results = [
        {"deck": "a", "status": "OK", "provenance": pp.REAL},
        {"deck": "b", "status": "FAILED", "provenance": pp.REAL},
        {"deck": "c", "status": "OK", "provenance": pp.SYNTHETIC},
    ]
    assert module.by_provenance(results) == {
        pp.REAL: {"total": 2, "ok": 1},
        pp.SYNTHETIC: {"total": 1, "ok": 1},
    }


def test_sweep_summary_counts_pods_that_seat_a_synthetic_deck() -> None:
    module = _script("precon_pod_sweep")
    pods = [
        {"status": "ok", "synthetic_decks": ["x"]},
        {"status": "ok", "synthetic_decks": []},
        {"status": "failed", "error": "boom", "synthetic_decks": ["y"]},
    ]
    assert module.summarize(pods)["pods_with_synthetic_decks"] == 2


def test_wrong_reason_control_a_real_deck_with_a_variant_name_is_still_real() -> None:
    """The label comes from deck_id, not from the file name or the deck name."""
    deck = {"deck_id": "precon/2023/x", "name": "X (variant, replacement cards)"}
    assert pp.deck_provenance(deck) == pp.REAL
    assert json.dumps(deck)  # the control deck is plain data
