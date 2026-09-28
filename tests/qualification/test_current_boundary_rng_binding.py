"""No artifact may assert RNG ownership from caller intent.

The RNG/replay artifact carried a literal `engine_owned: true` with a hard-coded
requested seed of 424242. That credited Rules RNG and replay control that no
observation established, which is the original defect in its most direct form: the
harness asserted the very thing it was supposed to measure. The first bound-source
run reproduced it verbatim in `RNG_REPLAY_*.json`.

Credit must come from what the engine acknowledged. When it acknowledges nothing the
binding is UNCONTROLLED_ENGINE_RNG with no credit, and on the generic B4-D lane
that is the honest outcome because the provider reports seed_supported=false.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts/run_current_boundary_qualification.py"
OUT = REPO / "qualification/final-current-boundary-20260927"


def test_runner_never_asserts_engine_owned() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    # The name may appear in a comment recording the retirement, never as a value.
    for line in source.splitlines():
        stripped = line.strip()
        if '"engine_owned"' in stripped:
            assert stripped.startswith("#"), f"engine_owned asserted: {stripped}"


def test_no_production_source_asserts_engine_owned() -> None:
    offenders: list[str] = []
    for path in list((REPO / "src").rglob("*.py")) + list((REPO / "scripts").rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if '"engine_owned"' in line and not line.strip().startswith("#"):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}")
    assert not offenders, f"engine_owned asserted at: {offenders}"


def test_rng_artifact_records_a_derived_binding() -> None:
    for candidate in ("XMAGE", "FORGE"):
        path = OUT / f"RNG_REPLAY_{candidate}.json"
        if not path.is_file():
            continue
        binding = json.loads(path.read_text(encoding="utf-8"))["rules_rng_binding"]
        assert "engine_owned" not in binding, candidate
        assert "requested_seed" in binding, candidate
        assert "acknowledged_seed" in binding, candidate
        assert "control" in binding or "classification" in binding, candidate
        assert "controlled" in binding, candidate
        # A run that acknowledged nothing must carry no credit and must say so
        # in the classification the receipt schema uses.
        if binding.get("acknowledged_seed") is None:
            assert binding.get("rng_credit") is False, candidate
            assert binding.get("controlled") is False, candidate
            assert binding.get("classification") == "UNCONTROLLED_ENGINE_RNG", candidate


def test_runner_captures_the_binding_from_the_driven_game() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert 'probes["hidden_game_seed_binding"] = hidden_game.seed_binding' in source
    assert 'probes["hidden_game_seed_binding"].to_document()' in source


def test_uncontrolled_outcome_is_explicit() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "UNCONTROLLED_ENGINE_RNG" in source
    assert '"rng_credit": False' in source
    # The uncontrolled fallback must also be explicit about being uncontrolled.
    assert '"detail": "no engine acknowledgement was observed for this run"' in source
