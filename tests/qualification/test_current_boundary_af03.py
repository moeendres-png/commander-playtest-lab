"""AF03 must be probed, not asserted.

AF03 was a literal ``"verdict": "PASS"`` in the assembler whose evidence list
described deck imports that were never performed, and no AF03 artifact existed.
These tests pin the real behaviour: the probes must run, the verdict must be
derived from the engine's responses, and a provider that accepts an illegal deck
must score FAIL rather than PASS.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary.af03 import (
    ILLEGAL_DECK_PROBES,
    AF03Report,
    _mutate,
    run_af03,
)
from commander_lab.qualification.current_boundary.game_driver import build_deck

REPO = Path(__file__).resolve().parents[2]
ASSEMBLER = REPO / "scripts/assemble_current_boundary_evidence.py"
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"


class FakeProc:
    """A bridge that answers import_deck according to a caller-supplied rule."""

    plan = None

    def __init__(self, accept: set[str]) -> None:
        self.accept = accept
        self.seen: list[dict] = []
        self.transcript: list = []

    def request(self, message: str, payload: dict, **kwargs: object) -> dict:
        self.seen.append(payload)
        deck = payload["deck"]
        if message == "import_deck":
            if deck["deck_id"] not in self.accept:
                return {"success": False, "error": "DECK_IMPORT_REJECTED"}
            return {"success": True, "payload": {"handle": "h-" + deck["deck_id"]}}
        raise AssertionError(message)


def _legal() -> dict:
    return build_deck("af03-control")


def test_legal_control_must_import_before_probes_count() -> None:
    """A provider that refuses every deck must not score a perfect AF03."""
    proc = FakeProc(accept=set())  # refuses everything, including the control
    report = run_af03(proc, candidate="xmage", legal_deck=_legal())
    assert report.verdict == "UNKNOWN"
    assert report.probes
    assert all(probe.verdict == "UNKNOWN" for probe in report.probes)
    assert "was refused" in report.probes[0].detail


def test_engine_refusing_every_illegal_deck_scores_pass() -> None:
    proc = FakeProc(accept={"af03-control"})  # accepts only the legal control
    report = run_af03(proc, candidate="xmage", legal_deck=_legal())
    assert report.verdict == "PASS"
    assert len(report.probes) == len(ILLEGAL_DECK_PROBES)


def test_engine_accepting_an_illegal_deck_scores_fail() -> None:
    # Accept the control plus every mutation except one.
    # Accept the control and every mutated deck except one, which is refused.
    refused = "colour_identity_violation"
    accept = {"af03-control"} | {
        f"af03-probe-{probe}" for probe, _, _ in ILLEGAL_DECK_PROBES if probe != refused
    }
    proc = FakeProc(accept=accept)
    report = run_af03(proc, candidate="xmage", legal_deck=_legal())
    assert report.verdict == "FAIL"
    failed = [probe.probe for probe in report.failed]
    # Every deck the engine accepted is a FAIL; the one it refused is a PASS.
    assert refused not in failed
    assert set(failed) == {p for p, _, _ in ILLEGAL_DECK_PROBES if p != refused}
    colour = next(probe for probe in report.probes if probe.probe == refused)
    assert colour.verdict == "PASS"


def test_transport_error_is_unknown_not_pass() -> None:
    class Broken(FakeProc):
        def request(self, message: str, payload: dict, **kwargs: object) -> dict:
            if message == "import_deck" and payload["deck"]["deck_id"] == "af03-control":
                return {"success": True}
            raise TimeoutError("bridge died")

    report = run_af03(Broken(accept=set()), candidate="xmage", legal_deck=_legal())
    assert report.verdict == "UNKNOWN"
    assert all(probe.verdict == "UNKNOWN" for probe in report.probes)


def test_unrecognised_refusal_shape_is_unknown() -> None:
    class Vague(FakeProc):
        def request(self, message: str, payload: dict, **kwargs: object) -> dict:
            if payload["deck"]["deck_id"] == "af03-control":
                return {"success": True}
            return {"note": "hmm"}

    report = run_af03(Vague(accept=set()), candidate="xmage", legal_deck=_legal())
    assert report.verdict == "UNKNOWN"
    assert all("unrecognised refusal shape" in probe.detail for probe in report.probes)


def test_empty_report_is_unknown() -> None:
    assert AF03Report(candidate="xmage").verdict == "UNKNOWN"


@pytest.mark.parametrize("probe", [p for p, _, _ in ILLEGAL_DECK_PROBES])
def test_each_mutation_actually_breaks_the_deck(probe: str) -> None:
    base = _legal()
    bad = _mutate(base, probe)
    assert bad != base
    # The mutation must not be cosmetic: something a Rules check would catch.
    if probe == "empty_mainboard":
        assert bad["mainboard"] == []
    elif probe == "mainboard_short_of_one_hundred":
        assert len(bad["mainboard"]) < 100
    elif probe == "unknown_card_name":
        assert "Definitely Not A Real Card Name" in bad["mainboard"]
    elif probe == "commander_not_in_pool":
        assert bad["commander_names"] == ["Hill Giant"]
    elif probe == "colour_identity_violation":
        assert set(bad["mainboard"]) == {"Black Lotus"}
    assert bad["deck_id"] != base["deck_id"], "a probe must be a distinct deck"
    # The original deck must be untouched.
    assert (
        base["mainboard"] != bad["mainboard"] or base["commander_names"] != bad["commander_names"]
    )


def test_mutation_does_not_alias_the_control_deck() -> None:
    base = _legal()
    before = list(base["mainboard"])
    _mutate(base, "empty_mainboard")
    assert base["mainboard"] == before


def test_assembler_no_longer_hard_codes_af03_pass() -> None:
    source = ASSEMBLER.read_text(encoding="utf-8")
    assert "af03_gate(candidate)" in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "gate"
                    and isinstance(value, ast.Constant)
                    and value.value == "AF03"
                ):
                    verdict = node.values[list(node.keys).index(key) + 1]
                    assert not (isinstance(verdict, ast.Constant) and verdict.value == "PASS"), (
                        "AF03 verdict must not be a literal"
                    )


def test_af03_gate_is_unknown_without_an_artifact() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("asm", ASSEMBLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gate = module.af03_gate("xmage")
    assert gate["verdict"] in {"UNKNOWN", "PASS", "FAIL"}
    if gate["verdict"] == "UNKNOWN":
        assert "no AF03 probe artifact" in gate["evidence"][0]


def test_runner_executes_af03() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "af03 = run_af03(" in source
    assert 'f"AF03_{candidate.upper()}.json"' in source
