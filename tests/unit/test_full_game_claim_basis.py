"""C3: declared contract and observed evidence stay apart in full-game outputs.

The boolean claims on a full-game result (rules authority, no fallback,
actor-scoped hidden information ...) are design constants. Each must carry an
explicit evidence status, and none that no run measures may be labelled as
observed. A new constant claim cannot be added without a status.
"""

from __future__ import annotations

import importlib.util
import sys
import typing
from pathlib import Path
from typing import Literal, get_args, get_origin

from commander_lab.engine.rules.full_game import FullGameClaimBasis, FullGameConformanceResult
from commander_lab.engine.rules.full_game_batch import FullGameBatchReport

ROOT = Path(__file__).resolve().parents[2]

# Constant claims that are bookkeeping of the evidence class itself rather than
# statements about the game (they are asserted on construction, not observed).
_EVIDENCE_CLASS_BOOKKEEPING = {
    "consumed_gameplay_evidence",
    "holdout_consumed",
    "official_campaign_eligible",
    "structural_decision_authority",
    "tactical_decision_authority",
}


def _constant_bool_claims(model: type) -> set[str]:
    hints = typing.get_type_hints(model)
    claims = set()
    for name, hint in hints.items():
        if get_origin(hint) is Literal and all(isinstance(v, bool) for v in get_args(hint)):
            claims.add(name)
    return claims


def test_every_constant_game_claim_has_an_evidence_status() -> None:
    claims = _constant_bool_claims(FullGameConformanceResult) - _EVIDENCE_CLASS_BOOKKEEPING
    labelled = set(FullGameClaimBasis.model_fields)
    missing = claims - labelled
    assert not missing, f"constant claims without an evidence status: {sorted(missing)}"


def test_no_unprobed_claim_is_labelled_observed() -> None:
    basis = FullGameClaimBasis()
    # Default until a run audits frames (C2); run() sets OBSERVED from its audit.
    assert basis.hidden_information_actor_scoped == "DECLARED_NOT_OBSERVED"
    assert basis.bit_exact_replay_validated == "NOT_CLAIMED"
    observed = {name for name, value in basis.model_dump().items() if value == "OBSERVED"}
    assert observed == {"decision_count", "terminal", "shutdown_disposition"}


def test_the_result_schema_carries_the_basis() -> None:
    schema = FullGameConformanceResult.model_json_schema()
    assert "claim_basis" in schema["properties"]
    assert schema["properties"]["schema_version"]["default"].endswith("-1.2.0")


def test_batch_report_flags_are_code_derived() -> None:
    assert FullGameBatchReport.model_fields["claim_basis"].default == "CODE_DERIVED"


def _script(name: str) -> object:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_c3_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_invariant_report_is_marked_as_declared_contract() -> None:
    report = _script("generate_full_game_contract_artifacts").invariant_report()  # type: ignore[attr-defined]
    assert report["evidence_status"] == "DECLARED_CONTRACT"
    # The workflow's boundary assertion still holds.
    assert report["random_or_default_discretionary_fallback"] is False


def test_hidden_report_separates_the_observed_scan_from_the_contract() -> None:
    source = (ROOT / "scripts" / "run_external_full_game_conformance.py").read_text(
        encoding="utf-8"
    )
    assert '"status_scope": "exported_transcript_scan+per_frame_actor_scope_audit"' in source
    assert '"declared_not_observed": {' in source
    assert '"observed": {' in source
