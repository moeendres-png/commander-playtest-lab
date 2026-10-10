"""#662 / SLOT-06 §(b): freeze-record assembly binds capabilities and gates to one lane.

A synthetic epoch that satisfies every rule is eligible. Each red control removes or
corrupts exactly one proof and must make the record not eligible, with a named reason.
The real sealed epoch c124150d77ab-d303b2ca5f32 must come out not eligible.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.freeze_readiness import REQUIRED_CAPABILITIES
from commander_lab.qualification.current_boundary import receipts as receipt_mod
from commander_lab.qualification.current_boundary.freeze_record import (
    AF01_PROOF,
    CAPABILITY_PROOF,
    LANE_SURFACE_COMPONENTS,
    TEST_SOURCE_ROOT,
    FreezeRecordError,
    assemble_freeze_record,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PIN = "b" * 40
ARTIFACT = "a" * 64
SCHEMA = json.loads(
    (
        REPO_ROOT / "qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json"
    ).read_text(encoding="utf-8")
)
CAPABILITY_KEYS = list(
    SCHEMA["properties"]["truthful_capabilities"]["properties"]["capabilities"]["properties"]
)
PROOF_CLASSES = sorted(
    {
        name
        for proofs in (*CAPABILITY_PROOF.values(), *LANE_SURFACE_COMPONENTS.values())
        for name in proofs
        if name != AF01_PROOF
    }
)


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _receipt(classes: dict[str, dict[str, Any]], pin: str = PIN) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": receipt_mod.NATIVE_SUITE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "candidate_commit": pin,
        "candidate_tree": "c" * 40,
        "command": "mvn test",
        "returncode": 0,
        "tests": sum(row["tests"] for row in classes.values()),
        "passed": sum(row["tests"] for row in classes.values()),
        "failed": 0,
        "errors": 0,
        "classes": sorted(classes),
        "executed_classes": classes,
        "unexecuted_classes": [],
    }
    doc["receipt_digest"] = receipt_mod._digest(doc)
    return doc


def _epoch(root: Path, **overrides: Any) -> Path:
    epoch = root / "epoch"
    capabilities = {key: False for key in CAPABILITY_KEYS}
    capabilities.update({cap: True for cap in REQUIRED_CAPABILITIES})
    capabilities["runtime_kind"] = "external_rules_engine"
    _write(
        epoch / "EPOCH_IDENTITY.json",
        {
            "created_utc": "2026-10-10T00:00:00+00:00",
            "producing_source": {
                "repository": "https://github.com/moeendres-png/commander-playtest-lab",
                "commit": "d" * 40,
                "tree": "e" * 40,
            },
        },
    )
    _write(
        epoch / "AF01_XMAGE.json",
        {
            "lane": overrides.get("lane", "full-game"),
            "verdict": "PASS",
            "engine_commit_reported": PIN,
            "capabilities_provider_reported": overrides.get("capabilities", capabilities),
            "engine_identity": {
                "get_provider_version_payload": {"engine_artifact_sha256": ARTIFACT}
            },
        },
    )
    _write(
        epoch / "AF00_AF11_XMAGE.json",
        {
            "gates": [
                {"gate": f"AF{n:02d}", "verdict": "PASS", "evidence": [f"sealed AF{n:02d}"]}
                for n in range(12)
            ]
        },
    )
    _write(
        epoch / "PB03_RUNTIME_EXECUTION.json",
        {
            "engine_artifact_sha256": overrides.get("sibling_artifact", ARTIFACT),
            **(
                {}
                if overrides.get("no_source")
                else {
                    "engine_source_identity": {
                        "repository": "https://github.com/moeendres-png/mage",
                        "commit": PIN,
                        "tree": "f" * 40,
                    }
                }
            ),
        },
    )
    classes = {name: {"tests": 3, "failures": 0, "errors": 0} for name in PROOF_CLASSES}
    for name in overrides.get("drop_classes", ()):
        classes.pop(name)
    for name in overrides.get("failing_classes", ()):
        classes[name] = {"tests": 3, "failures": 1, "errors": 0}
    for name in overrides.get("skipped_classes", ()):
        classes[name] = {"tests": 3, "failures": 0, "errors": 0, "skipped": 3}
    for name in overrides.get("partly_skipped_classes", ()):
        classes[name] = {"tests": 4, "failures": 0, "errors": 0, "skipped": 2}
    receipt = _receipt(classes, overrides.get("receipt_pin", PIN))
    if overrides.get("tamper"):
        receipt["tests"] += 1
    _write(epoch / "receipts" / "native-xmage-mechanism.json", receipt)
    sources = {
        f"{TEST_SOURCE_ROOT}{name}.java": "5" * 64
        for name in PROOF_CLASSES
        if name not in overrides.get("unsourced_classes", ())
    }
    _write(
        epoch / "NATIVE_SUITE_RECEIPTS.json",
        {
            "receipt_digests": {"xmage:mechanism": receipt["receipt_digest"]},
            "runner": {"input_digests": sources},
        },
    )
    if not overrides.get("unsealed"):
        _seal(epoch, root)
    return epoch


def _seal(epoch: Path, root: Path) -> None:
    lines = []
    for path in sorted(epoch.rglob("*")):
        if path.is_file() and path.name != "CURRENT_BOUNDARY_SHA256SUMS":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(root)}")
    (epoch / "CURRENT_BOUNDARY_SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _assemble(epoch: Path) -> Any:
    return assemble_freeze_record(
        epoch, repo_root=REPO_ROOT, expected_pin=PIN, seal_root=epoch.parent
    )


def test_complete_production_lane_epoch_is_eligible(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path))
    assert result.reasons == []
    assert result.eligible is True
    record = result.record
    assert record["freeze_eligible"] is True
    assert record["truthful_capabilities"]["missing_required_capabilities"] == []
    assert record["architecture_winner"] is False
    assert all(gate["verdict"] == "PASS" for gate in record["gate_results"])


def test_sibling_lane_af01_is_never_the_capability_set(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, lane="compatibility"))
    assert result.eligible is False
    assert result.record["truthful_capabilities"]["capabilities"] == {}
    assert sorted(
        result.record["truthful_capabilities"]["missing_required_capabilities"]
    ) == sorted(REQUIRED_CAPABILITIES)
    assert any("not on the production lane" in reason for reason in result.reasons)


CLASS_PROVED = [cap for cap in REQUIRED_CAPABILITIES if AF01_PROOF not in CAPABILITY_PROOF[cap]]
AF01_PROVED = [cap for cap in REQUIRED_CAPABILITIES if AF01_PROOF in CAPABILITY_PROOF[cap]]


@pytest.mark.parametrize("capability", CLASS_PROVED)
def test_reported_true_without_executed_proof_counts_missing(
    tmp_path: Path, capability: str
) -> None:
    proofs = [name for name in CAPABILITY_PROOF[capability] if name != AF01_PROOF]
    for dropped in proofs:
        result = _assemble(_epoch(tmp_path / dropped, drop_classes=[dropped]))
        missing = result.record["truthful_capabilities"]["missing_required_capabilities"]
        assert capability in missing, dropped
        assert result.eligible is False


# Ruling definitions pinned independently of the map: shrinking a capability's proof
# set below its L/S definitions must fail here, not silently lower the bar.
RULING_MINIMUM_PROOFS = {
    "legal_actions_supported": {
        "XmageFullGameDecisionClassMatrixTest",  # L1/L2 per class
        "XmageFullGameDecisionClassInventoryTest",  # every callback declared
        "XmageFullGameUnprojectableDecisionTest",  # L3 fails closed
        "XmageFullGameCancelRewindTest",  # L4 frame after rewind
    },
    "action_submission_supported": {
        "XmageFullGameDecisionClassMatrixTest",  # S1/S2
        "XmageFullGameDecisionClassInventoryTest",
        "XmageFullGameCancelRewindTest",  # S3
    },
}


@pytest.mark.parametrize("capability", sorted(RULING_MINIMUM_PROOFS))
def test_capability_proof_covers_the_ruling_definitions(capability: str) -> None:
    assert RULING_MINIMUM_PROOFS[capability] <= set(CAPABILITY_PROOF[capability])


@pytest.mark.parametrize(
    ("capability", "dropped"),
    [(cap, name) for cap, names in sorted(RULING_MINIMUM_PROOFS.items()) for name in sorted(names)],
)
def test_ruling_proof_dropped_counts_capability_missing(
    tmp_path: Path, capability: str, dropped: str
) -> None:
    result = _assemble(_epoch(tmp_path, drop_classes=[dropped]))
    assert capability in result.record["truthful_capabilities"]["missing_required_capabilities"]
    assert result.eligible is False


def test_af01_proved_capabilities_need_a_passing_production_lane_af01(tmp_path: Path) -> None:
    epoch = _epoch(tmp_path, unsealed=True)
    af01_path = epoch / "AF01_XMAGE.json"
    af01 = json.loads(af01_path.read_text(encoding="utf-8"))
    af01["verdict"] = "FAIL"
    af01_path.write_text(json.dumps(af01), encoding="utf-8")
    _seal(epoch, tmp_path)
    result = _assemble(epoch)
    missing = result.record["truthful_capabilities"]["missing_required_capabilities"]
    assert AF01_PROVED and set(AF01_PROVED) <= set(missing)
    assert result.eligible is False


def test_reported_false_counts_missing_even_with_proof(tmp_path: Path) -> None:
    capabilities = {key: True for key in CAPABILITY_KEYS}
    capabilities["runtime_kind"] = "external_rules_engine"
    capabilities["replay_supported"] = False
    result = _assemble(_epoch(tmp_path, capabilities=capabilities))
    assert result.record["truthful_capabilities"]["missing_required_capabilities"] == [
        "replay_supported"
    ]
    assert result.eligible is False


def test_failing_proof_class_gives_no_credit(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, failing_classes=["XmageFullGameEventLogTest"]))
    assert (
        "event_log_supported"
        in (result.record["truthful_capabilities"]["missing_required_capabilities"])
    )


def test_tampered_receipt_gives_no_credit(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, tamper=True))
    assert result.eligible is False
    assert any("gives no credit" in reason for reason in result.reasons)


@pytest.mark.parametrize("gate", sorted(LANE_SURFACE_COMPONENTS))
def test_lane_surface_gate_without_production_component_is_partial(
    tmp_path: Path, gate: str
) -> None:
    classes = [name for name in LANE_SURFACE_COMPONENTS[gate] if name != AF01_PROOF]
    epoch = (
        _epoch(tmp_path, drop_classes=classes[:1])
        if classes
        else _epoch(tmp_path, lane="compatibility")
    )
    result = _assemble(epoch)
    verdicts = {g["gate_id"]: g["verdict"] for g in result.record["gate_results"]}
    assert verdicts[gate] == "PARTIAL"
    assert result.eligible is False


def test_sibling_gate_with_other_artifact_is_partial(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, sibling_artifact="9" * 64))
    verdicts = {g["gate_id"]: g["verdict"] for g in result.record["gate_results"]}
    assert {verdicts["AF00"], verdicts["AF06"], verdicts["AF07"]} == {"PARTIAL"}
    assert result.eligible is False


def test_missing_provider_source_tree_is_not_eligible(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, no_source=True))
    assert result.eligible is False
    assert any("provider source tree" in reason for reason in result.reasons)


def test_missing_schema_capability_key_fails_closed(tmp_path: Path) -> None:
    capabilities = {key: True for key in CAPABILITY_KEYS}
    capabilities["runtime_kind"] = "external_rules_engine"
    del capabilities["stack_visible"]
    result = _assemble(_epoch(tmp_path, capabilities=copy.deepcopy(capabilities)))
    assert result.eligible is False
    assert any("stack_visible" in reason for reason in result.reasons)


def test_sealed_epoch_c124150d_is_not_eligible() -> None:
    epoch = REPO_ROOT / "qualification/current-boundary-epochs/c124150d77ab-d303b2ca5f32"
    config = json.loads((REPO_ROOT / "config/rules_engines.json").read_text(encoding="utf-8"))
    result = assemble_freeze_record(
        epoch, repo_root=REPO_ROOT, expected_pin=config["primary_engine"]["commit"]
    )
    assert result.eligible is False
    assert result.record["freeze_eligible"] is False
    assert any("not on the production lane" in reason for reason in result.reasons)


def test_unsealed_epoch_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FreezeRecordError, match="not sealed"):
        _assemble(_epoch(tmp_path, unsealed=True))


def test_edited_sealed_file_is_refused(tmp_path: Path) -> None:
    epoch = _epoch(tmp_path)
    af01 = epoch / "AF01_XMAGE.json"
    af01.write_text(af01.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(FreezeRecordError, match="digest mismatch"):
        _assemble(epoch)


def test_unsealed_extra_file_is_refused(tmp_path: Path) -> None:
    epoch = _epoch(tmp_path)
    (epoch / "INJECTED.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FreezeRecordError, match="coverage"):
        _assemble(epoch)


def test_receipt_at_another_pin_gives_no_credit(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, receipt_pin="c" * 40))
    assert result.eligible is False
    assert any("no credit" in reason for reason in result.reasons)
    assert (
        "replay_supported"
        in result.record["truthful_capabilities"]["missing_required_capabilities"]
    )


def test_all_skipped_class_gives_no_credit(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, skipped_classes=["XmageFullGameShutdownGameTest"]))
    assert (
        "game_shutdown_supported"
        in result.record["truthful_capabilities"]["missing_required_capabilities"]
    )


def test_partly_skipped_class_gives_no_credit(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, partly_skipped_classes=["XmageFullGameCancelRewindTest"]))
    missing = result.record["truthful_capabilities"]["missing_required_capabilities"]
    assert "action_submission_supported" in missing
    assert "legal_actions_supported" in missing
    assert result.eligible is False


def test_class_without_indexed_source_digest_gives_no_credit(tmp_path: Path) -> None:
    result = _assemble(_epoch(tmp_path, unsourced_classes=["XmageFullGameEventLogTest"]))
    assert (
        "event_log_supported"
        in result.record["truthful_capabilities"]["missing_required_capabilities"]
    )


def test_production_af01_with_wrong_engine_commit_is_not_eligible(tmp_path: Path) -> None:
    epoch = _epoch(tmp_path, unsealed=True)
    af01_path = epoch / "AF01_XMAGE.json"
    af01 = json.loads(af01_path.read_text(encoding="utf-8"))
    af01["engine_commit_reported"] = "d" * 40
    af01_path.write_text(json.dumps(af01), encoding="utf-8")
    _seal(epoch, tmp_path)
    result = _assemble(epoch)
    assert result.eligible is False
    assert any("is not the pin" in reason for reason in result.reasons)


def test_missing_artifact_identity_never_binds_sibling_gates(tmp_path: Path) -> None:
    epoch = _epoch(tmp_path, unsealed=True, sibling_artifact=None)
    af01_path = epoch / "AF01_XMAGE.json"
    af01 = json.loads(af01_path.read_text(encoding="utf-8"))
    af01["engine_identity"]["get_provider_version_payload"]["engine_artifact_sha256"] = None
    af01_path.write_text(json.dumps(af01), encoding="utf-8")
    _seal(epoch, tmp_path)
    verdicts = {g["gate_id"]: g["verdict"] for g in _assemble(epoch).record["gate_results"]}
    assert {verdicts["AF00"], verdicts["AF06"], verdicts["AF07"]} == {"PARTIAL"}
