"""Architecture-freeze-result 2.0.0 record assembly from a sealed epoch (#662, SLOT-06).

Implements ``docs/slot06_capability_ruling_20261009/SLOT06_RULING.md`` §(b):

- Only one lane, the XMage full-game lane, sets the record's capabilities. They are
  copied unchanged from that lane's own AF01 ``get_capabilities`` transcript. Lanes are
  never merged, and a sibling lane's payload never stands in.
- A required capability counts as ``true`` only when two things hold: the production
  lane reports ``true``, and the same epoch has an executed, failure-free native
  receipt of the test class that proves it. ``capabilitiesPayload`` is a static
  constant, so the reported value alone proves nothing.
- ``missing_required_capabilities`` is computed here and never written by hand.
- Lane-surface gates need a production-lane component from the same epoch. Only
  AF00/AF06/AF07 may stand on sibling-lane evidence, and only with the recorded
  argument and an equal engine artifact and pin.
- ``freeze_eligible`` is computed by :func:`check_freeze_eligibility`. It is never
  assigned. This module never selects a provider and never claims a Freeze.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from commander_lab.freeze_readiness import REQUIRED_CAPABILITIES, check_freeze_eligibility

from .receipts import ReceiptError, load_native_receipt

PRODUCTION_LANE = "full-game"
CANDIDATE = "xmage"

SCHEMA_PATH = Path("qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json")

# Each required capability names the native test classes that prove the surface the
# flag names on the production lane (ruling §(a) L1-L4/S1-S3, §(c) R1-R4). A flag
# counts only if every listed class ran in this epoch without failures.
# ``headless_supported`` and ``engine_shutdown_supported`` are proven by the
# production-lane AF01 run itself (headless launch, handshake, clean shutdown).
AF01_PROOF = "AF01:full-game"
CAPABILITY_PROOF: dict[str, tuple[str, ...]] = {
    "action_submission_supported": (
        "XmageFullGameDecisionClassMatrixTest",
        "XmageFullGameDecisionClassInventoryTest",
    ),
    "commander_supported": ("XmageFullGameTaxExecutionTest", "XmageFullGamePartnerExecutionTest"),
    "deck_import_supported": ("XmageFullGamePlayerCountTest",),
    "engine_shutdown_supported": (AF01_PROOF,),
    "event_log_supported": ("XmageFullGameEventLogTest",),
    "game_shutdown_supported": ("XmageFullGameShutdownGameTest",),
    "headless_supported": (AF01_PROOF,),
    "legal_actions_supported": (
        "XmageFullGameDecisionClassMatrixTest",
        "XmageFullGameDecisionClassInventoryTest",
    ),
    "multiplayer_supported": ("XmageFullGamePlayerCountTest",),
    "replay_supported": ("XmageFullGameReplayExportTest",),
    "seed_supported": ("XmageFullGameRulesSeedBindingTest",),
}

# Ruling §(b)3: the production-lane component each lane-surface gate needs.
LANE_SURFACE_COMPONENTS: dict[str, tuple[str, ...]] = {
    "AF01": (AF01_PROOF,),
    "AF02": ("XmageFullGamePlayerCountTest",),
    "AF03": ("XmageFullGameRulesSeedBindingTest",),
    "AF04": (
        "XmageFullGameDecisionClassMatrixTest",
        "XmageFullGameDecisionClassInventoryTest",
    ),
    "AF05": ("XmageFullGameHiddenInformationTest", "XmageFullGameLegalActionsPrincipalTest"),
    "AF08": (
        "XmageFullGameWs05MulliganTest",
        "XmageFullGameTaxExecutionTest",
        "XmageFullGamePartnerExecutionTest",
        "XmageFullGameElimExecutionTest",
        "XmageFullGameCombatDamageTest",
    ),
    "AF09": ("XmageFullGameReplayExportTest", "XmageFullGameReplayTwinTest"),
    "AF10": (AF01_PROOF, "XmageFullGameBridgeContractTest"),
    "AF11": (AF01_PROOF,),
}

# Ruling §(b)4: the only gates whose subject is Rules-Core card and rule behaviour,
# with the argument the record must carry when sibling-lane evidence is credited.
SIBLING_ADMISSIBLE_ARGUMENT: dict[str, str] = {
    "AF00": (
        "source/build identity of the one engine artifact and the Lab adapter; the "
        "lane's player callbacks do not take part in it"
    ),
    "AF06": (
        "general Rules correctness rows assert Rules-Core outcomes of scripted inputs; "
        "lane player callbacks only route the declared answers"
    ),
    "AF07": (
        "actual-card behaviour rows assert Rules-Core card outcomes of scripted inputs; "
        "lane player callbacks only route the declared answers"
    ),
}

assert set(CAPABILITY_PROOF) == set(REQUIRED_CAPABILITIES)
assert set(LANE_SURFACE_COMPONENTS) | set(SIBLING_ADMISSIBLE_ARGUMENT) == {
    f"AF{n:02d}" for n in range(12)
}


class FreezeRecordError(RuntimeError):
    """The epoch cannot be read as freeze-record input at all."""


@dataclass
class FreezeRecordResult:
    record: dict[str, Any]
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    proof_ledger: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema_version": "commander-lab.freeze-record-assembly/1.0.0",
            "ruling": "docs/slot06_capability_ruling_20261009/SLOT06_RULING.md",
            "production_lane": PRODUCTION_LANE,
            "freeze_eligible": self.eligible,
            "reasons": list(self.reasons),
            "proof_ledger": self.proof_ledger,
            "record": self.record,
            "nonclaims": [
                "an eligible record is a decision input for the Owner, not a Freeze",
                "provider_decision stays NO_PROVIDER_READY until the Owner's Freeze decision",
            ],
        }


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FreezeRecordError(f"epoch file missing: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise FreezeRecordError(f"epoch file is not an object: {path}")
    return document


def _clean_executed_classes(epoch: Path, reasons: list[str]) -> dict[str, dict[str, Any]]:
    """Classes that executed failure-free in this epoch's verified XMage receipts."""
    executed: dict[str, dict[str, Any]] = {}
    receipt_dir = epoch / "receipts"
    paths = sorted(receipt_dir.glob("native-xmage-*.json")) if receipt_dir.is_dir() else []
    if not paths:
        reasons.append("no XMage native-suite receipt in the epoch")
    for path in paths:
        try:
            doc = load_native_receipt(path)
        except ReceiptError as exc:
            reasons.append(f"receipt {path.name} gives no credit: {exc}")
            continue
        for name, row in (doc.get("executed_classes") or {}).items():
            if not isinstance(row, dict):
                continue
            clean = (
                int(row.get("tests") or 0) > 0 and not row.get("failures") and not row.get("errors")
            )
            if clean:
                executed[name] = {
                    "receipt": f"receipts/{path.name}",
                    "receipt_digest": doc["receipt_digest"],
                    "tests": row.get("tests"),
                    "candidate_commit": doc.get("candidate_commit"),
                }
    return executed


def _proof_status(
    proofs: tuple[str, ...], executed: dict[str, dict[str, Any]], af01_production: bool
) -> tuple[bool, list[str], list[str]]:
    refs: list[str] = []
    missing: list[str] = []
    for proof in proofs:
        if proof == AF01_PROOF:
            if af01_production:
                refs.append("AF01_XMAGE.json (lane=full-game, verdict=PASS)")
            else:
                missing.append(proof)
        elif proof in executed:
            entry = executed[proof]
            refs.append(f"{entry['receipt']}#{proof} ({entry['tests']} tests)")
        else:
            missing.append(proof)
    return not missing, refs, missing


def _provider_source(epoch: Path, pin: str, reasons: list[str]) -> dict[str, Any]:
    runtime_path = epoch / "PB03_RUNTIME_EXECUTION.json"
    runtime = _load(runtime_path) if runtime_path.is_file() else {}
    source = runtime.get("engine_source_identity")
    if not isinstance(source, dict):
        reasons.append(
            "provider source tree is not recorded in the epoch "
            "(PB03_RUNTIME_EXECUTION.json engine_source_identity)"
        )
        return {"repository": "https://github.com/moeendres-png/mage", "commit": pin, "tree": None}
    if source.get("commit") != pin:
        reasons.append(
            f"recorded provider source commit {source.get('commit')!r} is not the pin {pin!r}"
        )
    return {
        "repository": source.get("repository"),
        "commit": source.get("commit"),
        "tree": source.get("tree"),
    }


def _schema_errors(record: dict[str, Any], schema_root: Path) -> list[str]:
    import jsonschema  # type: ignore[import-untyped]

    schema = json.loads((schema_root / SCHEMA_PATH).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return sorted(
        f"schema: {'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in validator.iter_errors(record)
    )


def assemble_freeze_record(
    epoch: Path, *, repo_root: Path, expected_pin: str
) -> FreezeRecordResult:
    """Assemble and judge the XMage freeze record of one sealed epoch."""
    reasons: list[str] = []
    identity = _load(epoch / "EPOCH_IDENTITY.json")
    matrix = _load(epoch / f"AF00_AF11_{CANDIDATE.upper()}.json")
    af01 = _load(epoch / f"AF01_{CANDIDATE.upper()}.json")

    af01_lane = af01.get("lane")
    af01_production = af01_lane == PRODUCTION_LANE and af01.get("verdict") == "PASS"
    if af01_lane != PRODUCTION_LANE:
        reasons.append(
            f"AF01 ran on lane {af01_lane!r}, not on the production lane {PRODUCTION_LANE!r}; "
            "its capability payload cannot be the record's capability set"
        )
    elif af01.get("verdict") != "PASS":
        reasons.append(f"production-lane AF01 verdict is {af01.get('verdict')!r}")

    reported_commit = af01.get("engine_commit_reported")
    if reported_commit != expected_pin:
        reasons.append(f"AF01 engine commit {reported_commit!r} is not the pin {expected_pin!r}")

    executed = _clean_executed_classes(epoch, reasons)

    # ---- capabilities: the production lane's own payload, never a union -----------
    reported = af01.get("capabilities_provider_reported")
    reported = reported if isinstance(reported, dict) else {}
    schema = json.loads((repo_root / SCHEMA_PATH).read_text(encoding="utf-8"))
    capability_keys = schema["properties"]["truthful_capabilities"]["properties"]["capabilities"][
        "properties"
    ].keys()
    capabilities: dict[str, Any] = {}
    for key in capability_keys:
        if key in reported:
            capabilities[key] = reported[key]
        else:
            reasons.append(f"production-lane payload does not report capability {key}")
    if af01_lane != PRODUCTION_LANE:
        # A sibling lane's payload is never the record's capability set.
        capabilities = {}

    proof_ledger: dict[str, Any] = {"capabilities": {}, "gates": {}}
    missing_required: list[str] = []
    for cap in REQUIRED_CAPABILITIES:
        proven, refs, missing = _proof_status(CAPABILITY_PROOF[cap], executed, af01_production)
        reported_true = capabilities.get(cap) is True
        proof_ledger["capabilities"][cap] = {
            "reported": capabilities.get(cap),
            "proof_classes": list(CAPABILITY_PROOF[cap]),
            "proof_refs": refs,
            "proof_missing": missing,
            "counts_true": reported_true and proven,
        }
        if not (reported_true and proven):
            missing_required.append(cap)
            if not reported_true:
                reasons.append(
                    f"required capability {cap} is not reported true by the production lane"
                )
            else:
                reasons.append(
                    f"required capability {cap} is reported true without an executed in-epoch "
                    f"proof: {missing}"
                )

    # ---- gates ------------------------------------------------------------------
    gate_results: list[dict[str, Any]] = []
    artifact_production = (
        (af01.get("engine_identity") or {}).get("get_provider_version_payload") or {}
    ).get("engine_artifact_sha256")
    runtime_path = epoch / "PB03_RUNTIME_EXECUTION.json"
    artifact_sibling = (_load(runtime_path) if runtime_path.is_file() else {}).get(
        "engine_artifact_sha256"
    )
    for gate in matrix.get("gates") or []:
        gate_id = gate.get("gate")
        sealed = gate.get("verdict")
        evidence = [str(item) for item in gate.get("evidence") or []]
        refs = [f"{matrix_name(epoch)}#{gate_id}"]
        verdict = sealed
        if gate_id in LANE_SURFACE_COMPONENTS:
            ok, comp_refs, missing = _proof_status(
                LANE_SURFACE_COMPONENTS[gate_id], executed, af01_production
            )
            refs.extend(f"lane:{PRODUCTION_LANE} {ref}" for ref in comp_refs)
            if sealed == "PASS" and not ok:
                verdict = "PARTIAL"
                reason = (
                    f"sealed {gate_id} PASS has no production-lane ({PRODUCTION_LANE}) "
                    f"component in this epoch: missing {missing}"
                )
                reasons.append(reason)
            else:
                reason = f"sealed {gate_id} {sealed}; production-lane component: {comp_refs}"
            proof_ledger["gates"][gate_id] = {"production_lane_missing": missing}
        else:
            argument = SIBLING_ADMISSIBLE_ARGUMENT[gate_id]
            same_artifact = bool(artifact_production) and artifact_production == artifact_sibling
            if sealed == "PASS" and not same_artifact:
                verdict = "PARTIAL"
                reason = (
                    f"sibling-lane {gate_id} PASS is not bound to the production lane's engine "
                    f"artifact ({artifact_production!r} != {artifact_sibling!r})"
                )
                reasons.append(reason)
            else:
                reason = f"sealed {gate_id} {sealed}; sibling-lane evidence admitted: {argument}"
            refs.append(f"engine_artifact_sha256:{artifact_production}")
            proof_ledger["gates"][gate_id] = {"sibling_argument": argument}
        if evidence:
            reason = f"{reason}. First sealed evidence line: {evidence[0][:240]}"
        gate_results.append(
            {"gate_id": gate_id, "verdict": verdict, "reason": reason, "evidence_refs": refs}
        )

    producing = identity.get("producing_source") or {}
    record: dict[str, Any] = {
        "schema_version": "architecture-freeze-result/2.0.0",
        "architecture_winner": False,
        "candidate": CANDIDATE,
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
        "transport_protocol_version": "2.0.0",
        "protocol_schema_identity": schema["properties"]["protocol_schema_identity"]["const"],
        "source_lock": {
            "provider_source": _provider_source(epoch, expected_pin, reasons),
            "adapter_source": {
                "repository": producing.get("repository"),
                "commit": producing.get("commit"),
                "tree": producing.get("tree"),
            },
            "build": {
                "artifact_identity": f"org.mage:mage@{expected_pin}",
                "artifact_sha256": artifact_production,
            },
        },
        "truthful_capabilities": {
            "reported_by_provider": True,
            "runtime_kind": reported.get("runtime_kind"),
            "capabilities": capabilities,
            "required_capabilities": list(REQUIRED_CAPABILITIES),
            "missing_required_capabilities": missing_required,
        },
        "gate_results": gate_results,
        "freeze_eligible": False,
    }

    eligible, eligibility_reasons = check_freeze_eligibility(
        gate_results, capabilities, missing_required
    )
    schema_errors = _schema_errors(record, repo_root)
    reasons.extend(r for r in eligibility_reasons if r not in reasons)
    reasons.extend(schema_errors)
    eligible = eligible and not schema_errors and not reasons
    record["freeze_eligible"] = eligible
    return FreezeRecordResult(
        record=record, eligible=eligible, reasons=reasons, proof_ledger=proof_ledger
    )


def matrix_name(epoch: Path) -> str:
    return f"{epoch.name}/AF00_AF11_{CANDIDATE.upper()}.json"
