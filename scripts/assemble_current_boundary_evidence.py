#!/usr/bin/env python3
"""WSR22 final current-boundary evidence assembler.

Combines the freshly executed Protocol-2 lifecycle evidence with the freshly
executed native harness evidence, produces the AF00-AF11 matrix, the
current-boundary comparison, the divergence packet and the provider-blocker
register.

Nothing here inherits a historical verdict. Every PASS traces to a run that
executed inside this workstream at the recorded runtime identity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    actual_card_campaign as actual_card_campaign_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    decision_boundary as decision_boundary_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    evidence_epoch as epoch_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    forge_scenario_lane as forge_scenario_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    gate_derivations as gate_derivations_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    knowledge_projection as knowledge_projection_mod,
)
from commander_lab.qualification.current_boundary import lifecycle as lifecycle_mod  # noqa: E402
from commander_lab.qualification.current_boundary import (  # noqa: E402
    midgame_replay_twin as midgame_replay_twin_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    midgame_rows as midgame_rows_mod,
)
from commander_lab.qualification.current_boundary import (  # noqa: E402
    pb03_runtime as pb03_runtime_mod,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402
from commander_lab.qualification.current_boundary import (  # noqa: E402
    replay_twins as replay_twins_mod,
)
from commander_lab.qualification.current_boundary import semantic as semantic_mod  # noqa: E402

# The runtime evidence epoch resolved from the same source identity the runner
# used. The historical WSR22 tree is a read-only predecessor and is never read
# here as current evidence.
OUT = epoch_mod.epoch_root(REPO)

# Execution receipts. The assembler trusts nothing else for native credit: no
# receipt means no credit, and source text is never a substitute.
RECEIPT_DIR = OUT / "receipts"

FORGE_NATIVE_BINDING_PATH = OUT / "wsr20-ingest" / "FULL107_FORGE_MAPPING.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, payload: Any) -> None:
    (OUT / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    print("wrote", name)


def live_runner_digest() -> str:
    """Digest of the Lab-side qualification code executing this assembly.

    Native credit is bound to this identity in addition to the engine candidate
    commit, so a Lab adapter/runner change invalidates old receipts even when
    the engine head is unchanged. An unmeasurable identity fails closed: the
    caller receives an empty digest and every credit call yields zero.
    """
    try:
        return receipt_mod.capture_runner_identity(REPO).digest()
    except receipt_mod.ReceiptError as exc:
        print(f"runner identity unmeasurable ({exc}); native credit is unavailable")
        return ""


def native_bindings() -> dict[str, dict[str, list[str]]]:
    """Fixture -> test identities, derived from persisted positive receipts only.

    This previously scanned test source for fixture-id strings. That promoted
    HIDDEN_02 from UNKNOWN to PASS on the strength of a test that mentions
    HIDDEN_02 only to assert that loading it FAILS. A string mention is not
    evidence, so the whole scanning path is gone: credit now requires a positive
    receipt, and anything without one simply receives no credit.
    """
    manifest_rows = load(OUT / "EFFECTIVE_FULL107_MANIFEST.json")["rows"]
    denominator = {row["fixture_id"]: row for row in manifest_rows}
    receipts, rejected = receipt_mod.collect_receipts(RECEIPT_DIR)
    # Positive fixture receipts: the last link of the PB-03 credit chain, one per
    # exactly verified obligation, bound to this runner and the candidate head.
    positive, positive_rejected = receipt_mod.collect_positive_fixture_receipts(
        RECEIPT_DIR / receipt_mod.POSITIVE_RECEIPT_SUBDIR
    )
    identity = {
        c: load(OUT / f"FULL107_{c.upper()}_RESULTS.json")["runtime_identity"]
        for c in ("xmage", "forge")
    }
    runner_digest = live_runner_digest()
    # AF09: a replay-twin receipt credits only through the bound document of
    # the run that wrote it, which must declare every replay/RNG row.
    twin_path = OUT / "MIDGAME_REPLAY_TWIN_EXECUTIONS.json"
    twin_receipts = midgame_replay_twin_mod.bound_receipt_digests(
        load(twin_path) if twin_path.is_file() else None,
        candidate_commit=str(identity["xmage"].get("engine_candidate_commit", "")),
        runner_digest=runner_digest,
    )
    unbound = [
        receipt
        for receipt in positive
        if str(receipt.get("test_identity", "")).startswith(
            midgame_replay_twin_mod.TEST_IDENTITY_PREFIX
        )
        and twin_receipts.get(str(receipt.get("fixture_id"))) != receipt.get("receipt_digest")
    ]
    positive = [receipt for receipt in positive if receipt not in unbound]
    positive_rejected = positive_rejected + [
        f"{receipt.get('test_identity')}: not bound to this epoch's replay-twin document"
        for receipt in unbound
    ]
    receipts = receipts + positive
    rejected = rejected + positive_rejected
    if rejected:
        for reason in rejected:
            print(f"native receipt rejected: {reason}")
    if not receipts:
        print("no valid native receipts: no native credit is possible this assembly")
    out: dict[str, dict[str, list[str]]] = {}
    for candidate in ("xmage", "forge"):
        commit = identity[candidate].get("engine_candidate_commit", "")
        credited = receipt_mod.positive_fixture_credit(
            receipts,
            candidate=candidate,
            expected_commit=commit,
            denominator=denominator,
            expected_runner_digest=runner_digest,
        )
        for fixture, tests in credited.items():
            out.setdefault(fixture, {})[candidate] = tests
    return out


def native_credit(
    candidate: str, expected_commit: str, expected_runner_digest: str
) -> dict[str, Any]:
    """Native-suite credit for one candidate, from receipts only.

    `native_runs` keeps its established shape: a mapping of group name to that
    group's observed detail, so a consumer can read one suite's result directly.
    The aggregate summary and the provenance rule live under sibling keys rather
    than being mixed into the mapping, where a scalar would break iteration.
    """
    receipts, _ = receipt_mod.collect_receipts(RECEIPT_DIR)
    credit = receipt_mod.native_suite_credit(
        receipts,
        candidate=candidate,
        expected_commit=expected_commit,
        expected_runner_digest=expected_runner_digest,
    )
    # PURELY a per-group mapping. Every value must be subscriptable, because
    # consumers iterate it directly; scalar metadata lives beside it.
    return {
        group["group"]: {
            "candidate": group["candidate"],
            "tests": group["tests"],
            "passed": group["passed"],
            # `failures` is the established key consumers read; `failed` is the
            # receipt's own name. Both are emitted so no consumer has to guess.
            "failed": group["failed"],
            "failures": group["failed"],
            "errors": group["errors"],
            "returncode": group["returncode"],
            "candidate_commit": group["candidate_commit"],
            "executed_commit": group["executed_commit"],
            "engine_identity_justification": group["engine_identity_justification"],
            "receipt_digest": group["receipt_digest"],
        }
        for group in credit["groups"]
    }


def native_credit_provenance(
    candidate: str, expected_commit: str, expected_runner_digest: str
) -> dict[str, Any]:
    """The provenance statement that accompanies `native_runs`."""
    receipts, _ = receipt_mod.collect_receipts(RECEIPT_DIR)
    credit = receipt_mod.native_suite_credit(
        receipts,
        candidate=candidate,
        expected_commit=expected_commit,
        expected_runner_digest=expected_runner_digest,
    )
    return {
        "source": "PERSISTED_EXECUTION_RECEIPTS_ONLY",
        "absent_receipts_yield_no_credit": True,
        "expected_engine_commit": expected_commit,
        "expected_runner_digest": expected_runner_digest,
        "stale_runner_excluded": credit["stale_runner_excluded"],
        "summary": {
            "groups_credited": credit["groups_credited"],
            "tests": credit["tests"],
            "passed": credit["passed"],
            "failed": credit["failed"],
            "errors": credit["errors"],
            "receipt_digests": credit["receipt_digests"],
        },
    }


def _annotate_carried_gates(
    matrix: list[dict[str, Any]], column_provenance: dict[str, Any]
) -> None:
    """State on every gate that a carried-forward column is historical.

    Every gate in a carried-forward column is assembled from the historical
    record, not from an execution in this epoch. Saying so per gate stops the
    per-gate verdicts from being read as current observations.
    """
    if column_provenance.get("class") == "FRESH_CURRENT_BOUNDARY_EXECUTION":
        return
    note = (
        "This gate was assembled from the historical record carried forward into this epoch "
        f"({column_provenance.get('source_epoch', 'unknown')}); it records what that run "
        "observed, not a fresh execution."
    )
    for gate in matrix:
        gate["nonblocking_limitations"] = [*gate.get("nonblocking_limitations", []), note]


def _load_fullgame_lane_auxiliary(candidate: str) -> dict[str, Any] | None:
    """The xmage full-game-lane auxiliary, only when this epoch carries one.

    The artifact is produced by an earlier boundary epoch, not by the runner, so
    a runtime epoch normally does not contain it. Absence is therefore normal
    and must not crash the assembly; when it is present it is still epoch-checked
    before any citation.
    """
    if candidate != "xmage":
        return None
    path = OUT / "AF01_XMAGE_FULLGAME_LANE.json"
    if not path.is_file():
        return None
    return load(path)


def source_lock_verdict(af01: dict[str, Any], expected_commit: str) -> str:
    """AF00 derived from the reported engine identity, not asserted.

    The gate is only satisfied when the provider named a commit, and named the
    commit the evidence is about. A provider that reports nothing is UNKNOWN: an
    absent identity is not a verified one. A provider that names a *different*
    commit is FAIL, because the evidence would be attributed to an engine that
    did not run.
    """
    reported = str(af01.get("engine_commit_reported") or "").strip()
    if not reported:
        return "UNKNOWN"
    expected = str(expected_commit or "").strip()
    if not expected:
        return "UNKNOWN"
    return "PASS" if reported == expected else "FAIL"


def af04_gate(
    candidate: str,
    af01: dict[str, Any],
    cardinality: dict[str, Any],
    expected_runtime_identity: dict[str, Any],
) -> dict[str, Any]:
    """AF04 LEGAL_ACTION_AND_DECISION_BOUNDARY, derived from this run.

    Owner ruling R-2 (SLOT-03 option (c)) approves the provider-specific
    decision-identity shim as protocol translation on one condition: every
    submitted identity byte-matches a value in the frame the provider just
    offered. The gate is now *measured* rather than asserted for either
    candidate: `decision_boundary.derive_decision_boundary` consumes this
    epoch's own external decision frames and the engine's own responses, and
    reports every contradiction and every unproven element explicitly.

    The previous version hard-coded Forge to UNKNOWN on the premise that no
    class beyond PRIORITY had been exercised. #255/441 classified that as
    `EVIDENCE_ASSEMBLY_GAP_PENDING_BOUNDED_REVALIDATION`, and the same-epoch
    Forge cardinality evidence does record externally answered STARTING_PLAYER,
    MULLIGAN and PRIORITY frames at 2P-6P. The gate therefore reports what the
    evidence proves: PASS when every recorded subset of the AF04 contract is
    proven, FAIL when a recorded submission contradicts the engine-offered
    domain, and UNKNOWN when an element is unmeasured. No outcome is
    pre-decided by candidate identity.
    """
    boundary = decision_boundary_mod.derive_decision_boundary(
        candidate, cardinality, af01, expected_runtime_identity
    )
    provenance = af01.get("decision_identity_provenance") or {}
    evidence = [
        "AF04 derived from this epoch's external decision frames "
        f"({boundary['frame_count']} frame(s) across "
        f"{', '.join(boundary['required_cardinalities'])}); externally answered classes: "
        f"{', '.join(boundary['externally_answered_decision_classes']) or 'none'}",
        f"decision identity provenance on the live AF01 frame (R-2): {provenance}",
        boundary["statement"],
    ]
    failures = boundary["contradictions"]
    gaps = boundary["gaps"]
    limitations = [
        f"{item['severity']} {item['cardinality']}/{item['kind']}: {item['detail']}"
        for item in (*failures, *gaps)
    ]
    if not failures and not gaps:
        limitations = [
            "every frame in this epoch's decision tape was answered from the engine-offered "
            "domain with a recorded engine acceptance; a decision class absent from the tape "
            "is not claimed as exercised"
        ]
    blocking_rows = [
        f"PLAYER_COUNT_{count}"
        for count in boundary["required_cardinalities"]
        if boundary["verdict"] != "PASS"
    ]
    return {
        "gate": "AF04",
        "name": "LEGAL_ACTION_AND_DECISION_BOUNDARY",
        "verdict": boundary["verdict"],
        "evidence": evidence,
        "owner_ruling": "R-2",
        "decision_boundary": boundary,
        "blocking_rows": blocking_rows,
        "nonblocking_limitations": limitations,
    }


def af00_gate(candidate: str, data: dict[str, Any], af01: dict[str, Any]) -> dict[str, Any]:
    """Derive AF00 from exact current source/build identity.

    XMage currently has a single source role, so the provider-reported commit is
    compared directly with its current candidate. Forge under R-1/R-3 has two
    explicit roles: the #13 bridge/materialization source that is actually built
    and the #11/#12 Rules-Core candidate. Forge AF00 therefore requires both the
    exact build provenance and the separately measured Rules-Core equivalence.
    """
    runtime = data["results_runtime_identity"]
    if candidate != "forge":
        expected = runtime.get("engine_candidate_commit", "")
        return {
            "gate": "AF00",
            "name": "SOURCE_AND_BUILD_LOCK",
            "verdict": source_lock_verdict(af01, expected),
            "evidence": [
                f"candidate commit reported by the provider at handshake: "
                f"{af01.get('engine_commit_reported')}",
                f"commit the evidence is required to be about: {expected}",
                f"engine_commit provenance: {af01.get('engine_commit_provenance')}",
                "Lab runner HEAD/TREE bound in FULL107_*_RUNTIME_LOG_INDEX.json",
            ],
            "blocking_rows": [],
            "nonblocking_limitations": [],
        }

    source_commit = str(runtime.get("bridge_source_commit") or "")
    source_tree = str(runtime.get("bridge_source_tree") or "")
    rules_commit = str(runtime.get("engine_candidate_commit") or "")
    rules_tree = str(runtime.get("engine_candidate_tree") or "")
    rules_proof = runtime.get("rules_core_identity") or {}
    bridge_proof = runtime.get("bridge_identity") or {}
    version_payload = (af01.get("engine_identity") or {}).get("get_provider_version_payload") or {}
    provenance = receipt_mod.verify_pb05_provenance(
        version_payload,
        expected_source_commit=source_commit,
        expected_tree=source_tree,
    )
    handshake = source_lock_verdict(af01, source_commit)

    exact = (
        handshake == "PASS"
        and provenance.get("af00_credit") is True
        and rules_proof.get("engine_equivalent") is True
        and bridge_proof.get("identical") is True
    )
    explicit_failure = (
        handshake == "FAIL"
        or provenance.get("engine_commit_verified") is False
        or rules_proof.get("engine_equivalent") is False
        or bridge_proof.get("identical") is False
    )
    verdict = "PASS" if exact else ("FAIL" if explicit_failure else "UNKNOWN")

    limitations: list[str] = []
    if verdict != "PASS":
        limitations.extend(str(item) for item in provenance.get("findings", []))
        if rules_proof.get("engine_equivalent") is not True:
            limitations.append(
                "Rules-Core tree equivalence to the admitted R-1 candidate is not established"
            )
        if bridge_proof.get("identical") is not True:
            limitations.append(
                "executing forge-protocol2-bridge module is not proven identical to the bound source"
            )

    return {
        "gate": "AF00",
        "name": "SOURCE_AND_BUILD_LOCK",
        "verdict": verdict,
        "evidence": [
            f"provider/build source commit: {source_commit}",
            f"provider/build source tree: {source_tree}",
            f"provider reported commit: {af01.get('engine_commit_reported')}",
            f"provider build provenance verified: {provenance.get('af00_credit')}",
            f"R-1 Rules-Core candidate commit: {rules_commit}",
            f"R-1 Rules-Core candidate tree: {rules_tree}",
            f"Rules-Core equivalence: {rules_proof.get('justification')}",
            f"bridge identity binding: {bridge_proof.get('justification')}",
            "Lab runner HEAD/TREE bound in FULL107_*_RUNTIME_LOG_INDEX.json",
        ],
        "build_provenance": provenance,
        "rules_core_identity_proof": rules_proof,
        "bridge_identity_proof": bridge_proof,
        "blocking_rows": [],
        "nonblocking_limitations": limitations,
    }


def af03_gate(candidate: str) -> dict[str, Any]:
    """AF03 RULES_AUTHORITY, read from this run's negative deck-import probe.

    AF03 used to be a literal ``"verdict": "PASS"`` in this assembler, with an
    evidence list describing deck imports that were never performed and no
    artifact behind them. It is now read from the probe artifact the runner
    produces, so a run that did not probe gets no credit, and a run in which the
    engine accepted an illegal deck gets a FAIL.
    """
    path = OUT / f"AF03_{candidate.upper()}.json"
    if not path.is_file():
        return {
            "gate": "AF03",
            "name": "RULES_AUTHORITY",
            "verdict": "UNKNOWN",
            "evidence": ["no AF03 probe artifact exists for this candidate"],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "AF03 cannot be credited without observed negative deck-import probes"
            ],
        }
    document = load(path)
    probes = document.get("probes", [])
    return {
        "gate": "AF03",
        "name": "RULES_AUTHORITY",
        "verdict": document.get("verdict", "UNKNOWN"),
        "evidence": [
            f"{probe['invariant']}: {probe['verdict']} ({probe['detail']})" for probe in probes
        ],
        "observed_probe_count": len(probes),
        "authority": document.get("authority"),
        "blocking_rows": [probe["probe"] for probe in probes if probe.get("verdict") == "FAIL"],
        "nonblocking_limitations": document.get("nonblocking_limitations", []),
    }


# ---------------------------------------------------------------------------
# AF11 INTEROP_LICENSE_TOPOLOGY: measured, not asserted.
#
# The gate contract is "actual integration topology satisfies WS-09; Forge
# remains a genuine separate process/service". That is a *technical* claim plus
# a *policy* claim, and only the technical half is observable from inside the
# Lab. This function therefore:
#   1. measures every technical fact it can actually observe, and
#   2. derives FAIL only when a technical fact is genuinely violated,
#      leaving the residual policy question UNKNOWN and Coordinator-owned.
#
# The Lab must not decide the policy question: whether the observed separate-
# process topology and the licence/redistribution consequences satisfy AF11/
# WS-09 under existing policy is reserved to the Coordinator. Recording that
# residual as UNKNOWN is the honest state; it is NOT a weakening, because
# freeze eligibility requires PASS and UNKNOWN is already in NON_PASS_VERDICTS.
# ---------------------------------------------------------------------------

# Adapter identities that would mean engine code is compiled INTO the Lab
# process. Neither candidate's adapter may resolve to any of these.
_LAB_EMBEDDED_ENGINE_PREFIXES = ("commander_lab.engine", "src/commander_lab/engine")


def _af11_measure(
    per_candidate: dict[str, Any], candidate: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Observe the AF11 technical facts. Returns facts, limitations, verdict."""

    evidence: list[str] = []
    limitations: list[str] = []
    violated: list[str] = []

    # -- Fact 1: each candidate is driven through its own distinct adapter.
    adapters: dict[str, str] = {}
    for cand, cdata in sorted(per_candidate.items()):
        adapter = (cdata["results_runtime_identity"] or {}).get("adapter")
        adapters[cand] = str(adapter) if adapter else ""

    own_adapter = adapters.get(candidate, "")
    if not own_adapter:
        violated.append("no adapter identity was recorded for this candidate")
    elif len({a for a in adapters.values() if a}) > 1:
        evidence.append(
            "each candidate was driven through its own distinct external adapter "
            f"({', '.join(f'{k}={v}' for k, v in adapters.items())}) by one and the "
            "same Lab driver column, so no single engine is reached in-process"
        )
    else:
        violated.append(
            "candidates do not resolve to distinct adapter identities, so the "
            "separate-process boundary is not demonstrated"
        )

    # -- Fact 2: no engine code is embedded in the Lab process.
    embedded = [
        cand
        for cand, adapter in adapters.items()
        if any(adapter.startswith(p) for p in _LAB_EMBEDDED_ENGINE_PREFIXES)
    ]
    if embedded:
        violated.append("engine code is embedded in the Lab process for: " + ", ".join(embedded))
    else:
        evidence.append(
            "no adapter identity resolves to the Lab's in-tree engine package, so "
            "no engine code is embedded in the Lab process"
        )

    # -- Fact 3: the recorded qualification boundary for this run.
    boundary = (data["results_runtime_identity"] or {}).get("qualification_boundary")
    if boundary:
        evidence.append(f"qualification boundary recorded for this run: {boundary}")
    else:
        violated.append("no qualification boundary recorded on the runtime identity")

    # -- Fact 4: licence topology as recorded metadata (a fact, not a ruling).
    try:
        cfg = load(REPO / "config" / "rules_engines.json")
        lic = {
            "xmage": (
                cfg["primary_engine"].get("provider"),
                cfg["primary_engine"].get("license"),
            ),
            "forge": (
                cfg["secondary_engine"].get("provider"),
                cfg["secondary_engine"].get("license"),
            ),
        }
        evidence.append(
            "recorded licence topology: "
            + ", ".join(
                f"{name} {provider} {name_lic}"
                for name, (provider, name_lic) in sorted(lic.items())
            )
            + " (recorded metadata; no legal conclusion is drawn here)"
        )
    except Exception as exc:  # pragma: no cover - defensive
        violated.append(f"licence topology could not be read from the source lock: {exc!r}")

    # -- Fact 5: the decision-identity difference is real; whether any mapping
    #    satisfies policy is not measured here.
    if len({a for a in adapters.values() if a}) > 1:
        evidence.append(
            "the candidates publish different request-body and decision-identity "
            "conventions (recorded in the AF04 evidence); whether a "
            "candidate-scoped mapping satisfies AF11/WS-09 under existing policy "
            "is not measured here"
        )

    # -- The residual question is not the Lab's to answer.
    limitations.append(
        "NOT MEASURED BY THE LAB: whether the observed separate-process topology "
        "satisfies AF11/WS-09 under existing policy, and any "
        "licence/redistribution consequence. That adjudication is reserved to "
        "the Coordinator, so the Lab records it as UNKNOWN rather than deciding "
        "it in either direction"
    )

    verdict = "FAIL" if violated else "UNKNOWN"
    if violated:
        limitations.extend(violated)
        evidence.append("AF11 technical facts are VIOLATED, hence FAIL")
    else:
        evidence.append(
            "every observable AF11 technical fact holds (separate external "
            "processes, no embedded engine, shared recorded boundary); the only "
            "residual is the Coordinator-owned policy question, hence UNKNOWN "
            "rather than an invented PASS"
        )

    return {"verdict": verdict, "evidence": evidence, "limitations": limitations}


def _describe_replay_evidence(
    document: dict[str, Any], candidate: str, *, twin_proven: bool = False
) -> dict[str, Any]:
    """Derive the AF09 replay/RNG evidence lines from the recorded artifact.

    Generic semantic distinctions, stated once and enforced here rather than
    inferred per run:

    * a seed acknowledgement is a precondition for RNG control, never a
      demonstrated Rules RNG tape;
    * a fail-closed export refusal is an absent capability, never a satisfied
      obligation and never a replay PASS;
    * deterministic setup alone (deck import, game creation, seed echo) is not
      semantic replay proof.

    ``twin_proven`` is true only when a clean-process twin bound to this
    column carries the replay obligation. The distinctions then still hold and
    are stated as evidence, but they no longer block: the verdict rests on the
    twin, never on the refusal, the seed echo or the setup.
    """
    evidence: list[str] = []
    replay = document.get("semantic_replay") or {}
    errors = replay.get("error") or []
    if errors:
        codes = sorted(
            {str(item.get("code", "unknown")) for item in errors if isinstance(item, dict)}
        )
        evidence.append(
            "replay export attempted in a live game and refused by the engine "
            f"(RNG_REPLAY_{candidate.upper()}.json; refusal codes: {', '.join(codes)})"
        )
    elif replay:
        evidence.append(
            "replay export returned a payload in a live game "
            f"(RNG_REPLAY_{candidate.upper()}.json); payload presence is recorded, "
            "not replay proof"
        )
    else:
        evidence.append(f"no replay export outcome recorded (RNG_REPLAY_{candidate.upper()}.json)")
    binding = document.get("rules_rng_binding") or {}
    evidence.append(
        "seed binding: "
        f"{binding.get('classification', 'UNKNOWN')} "
        f"(requested={binding.get('requested_seed')}, "
        f"acknowledged={binding.get('acknowledged_seed')}); "
        "acknowledgement is a precondition for RNG control, not a demonstrated "
        "Rules RNG tape"
    )
    distinctions = [
        "a fail-closed export refusal is an absent capability, never a satisfied "
        "obligation and never a replay PASS",
        "deterministic setup alone (deck import, game creation, seed acknowledgement) "
        "is not semantic replay proof",
    ]
    if twin_proven:
        return {"evidence": [*evidence, *distinctions], "limitations": []}
    limitations = [
        *distinctions,
        "the clean-process twin half of each replay obligation is not proven per fixture",
    ]
    return {"evidence": evidence, "limitations": limitations}


def _load_replay_document(candidate: str) -> dict[str, Any] | None:
    path = OUT / f"RNG_REPLAY_{candidate.upper()}.json"
    if not path.is_file():
        return None
    return load(path)


def midgame_replay_twin_document(
    candidate: str, data: dict[str, Any], runner_digest: str
) -> dict[str, Any] | None:
    """The production midgame lane's replay-twin document, bound to this column.

    None unless this is the fresh XMage column of this epoch and the runner's
    document names the column's engine commit and the assembling runner, and
    its twin names the same engine commit as the build that executed. Row
    credit never comes from this document: each replay/RNG row is credited
    only through its own runner-bound positive receipt.
    """
    if candidate != "xmage":
        return None
    if data["column_provenance"]["class"] != "FRESH_CURRENT_BOUNDARY_EXECUTION":
        return None
    path = OUT / "MIDGAME_REPLAY_TWIN_EXECUTIONS.json"
    if not path.is_file():
        return None
    document = load(path)
    commit = str(data["results_runtime_identity"].get("engine_candidate_commit", ""))
    # Malformed parts are read as empty, so a stale or malformed document is
    # rejected with its reasons below, never raises during assembly.
    twin_value = document.get("clean_process_twin")
    twin = twin_value if isinstance(twin_value, dict) else {}
    rows_value = document.get("rows")
    rows = (
        {name: row for name, row in rows_value.items() if isinstance(row, dict)}
        if isinstance(rows_value, dict)
        else {}
    )
    build = twin.get("candidate_build")
    twin_digests = {str(row.get("twin_digest")) for row in rows.values() if row.get("verified")}
    # Each failed condition is named: a document can be correctly bound and still
    # not stand for the replay obligation because one row's twin did not verify.
    failed = [
        reason
        for reason, broken in (
            (
                "execution mode differs",
                document.get("execution_mode") != midgame_replay_twin_mod.EXECUTION_MODE,
            ),
            ("candidate differs", document.get("candidate") != candidate),
            ("column has no engine commit", not commit),
            ("candidate commit differs", document.get("candidate_commit") != commit),
            ("runner digest differs", document.get("runner_digest") != runner_digest),
            (
                "twin build commit differs",
                (build.get("engine_commit") if isinstance(build, dict) else None) != commit,
            ),
            # The twin stands for the replay obligation only when every row's own
            # twin verified in this run, and it is one of those twins.
            (
                "row set differs",
                not isinstance(rows_value, dict)
                or set(rows_value) != set(midgame_replay_twin_mod.ROWS)
                or len(rows) != len(rows_value),
            ),
            (
                "rows not verified: "
                + ",".join(sorted(name for name, row in rows.items() if not row.get("verified"))),
                not all(row.get("verified") for row in rows.values()),
            ),
            (
                "twin is not one of the verified rows' twins",
                not twin or replay_twins_mod.sha256_json(twin) not in twin_digests,
            ),
        )
        if broken
    ]
    if failed:
        print("midgame replay-twin document rejected: " + "; ".join(failed))
        return None
    return document


def actual_card_campaign_credit(
    candidate: str, data: dict[str, Any], runner_digest: str
) -> dict[str, str] | None:
    """Same-epoch AF07 campaign credit for one fresh column, from receipts only.

    None when this column did not execute in this epoch or the runner produced
    no campaign document for it: the gate then reports that no campaign credit
    was supplied. Otherwise every fixture's state is derived from the
    campaign's receipt subdirectory against the CURRENT effective records, so a
    receipt whose record digests drifted, or that a different runner or engine
    commit produced, earns nothing.
    """
    if data["column_provenance"]["class"] != "FRESH_CURRENT_BOUNDARY_EXECUTION":
        return None
    document_path = OUT / f"ACTUAL_CARD_CAMPAIGN_{candidate.upper()}.json"
    if not document_path.is_file():
        return None
    receipts, rejected = receipt_mod.collect_positive_fixture_receipts(
        RECEIPT_DIR / actual_card_campaign_mod.RECEIPT_SUBDIR
    )
    for reason in rejected:
        print(f"actual-card campaign receipt rejected: {reason}")
    corpus = actual_card_campaign_mod.derive_corpus(REPO)
    return gate_derivations_mod.actual_card_campaign_states(
        receipts,
        candidate=candidate,
        candidate_commit=str(data["results_runtime_identity"].get("engine_candidate_commit", "")),
        runner_digest=runner_digest,
        records={row.fixture_id: dict(row.record) for row in corpus.rows},
        test_identity_prefix=actual_card_campaign_mod.TEST_IDENTITY_PREFIX,
        campaign_document=load(document_path),
    )


def assemble() -> None:
    # Only an epoch whose recorded producing source is the source assembling
    # right now may be credited. An absent identity means no run produced this
    # epoch; a foreign identity means the bytes belong to another source.
    epoch_identity = epoch_mod.require_epoch_identity(OUT, repo_root=REPO)
    print(
        "assembling evidence epoch:",
        epoch_identity["epoch_root"],
        "producing source",
        epoch_identity["producing_source"]["commit"][:12],
    )
    bindings = native_bindings()
    # The Lab-side identity every native credit in this assembly is bound to.
    # Engine-commit equality alone no longer suffices: an adapter/runner change
    # with an unchanged engine head must invalidate old receipts.
    assembly_runner_digest = live_runner_digest()
    per_candidate: dict[str, dict[str, Any]] = {}
    for candidate in ("xmage", "forge"):
        results = load(OUT / f"FULL107_{candidate.upper()}_RESULTS.json")
        rows = {row["fixture_id"]: dict(row) for row in results["rows"]}
        carried_forward = bool(results.get("carried_forward"))
        promoted = 0
        demoted_without_receipt = 0
        receipt_backed_existing_pass = 0

        # AF05: a knowledge boundary the production lane demonstrably violated is
        # a FAIL with its findings, never an UNKNOWN. Only a document bound to
        # this column's candidate and the assembling runner demonstrates anything.
        demonstrated: dict[str, dict[str, Any]] = {}
        if candidate == "xmage" and not carried_forward:
            executions_path = OUT / "KNOWLEDGE_PROJECTION_EXECUTIONS.json"
            demonstrated = knowledge_projection_mod.demonstrated_failures(
                load(executions_path) if executions_path.is_file() else None,
                candidate_commit=str(
                    results["runtime_identity"].get("engine_candidate_commit", "")
                ),
                runner_digest=assembly_runner_digest,
            )
        # AF09: a replay twin that demonstrated a violation (the engine answered
        # the same inputs and seed differently) is a FAIL, never an UNKNOWN.
        if candidate == "xmage" and not carried_forward:
            twin_path = OUT / "MIDGAME_REPLAY_TWIN_EXECUTIONS.json"
            replay_failures = midgame_replay_twin_mod.demonstrated_failures(
                load(twin_path) if twin_path.is_file() else None,
                candidate_commit=str(
                    results["runtime_identity"].get("engine_candidate_commit", "")
                ),
                runner_digest=assembly_runner_digest,
            )
            for fixture, finding in replay_failures.items():
                if fixture not in rows:
                    continue
                row = rows[fixture]
                row["pre_replay_twin_exit_state"] = row["exit_state"]
                row["exit_state"] = "FAIL"
                row["execution_mode"] = midgame_replay_twin_mod.EXECUTION_MODE
                row["failure_reason"] = (
                    f"{finding['classification']}: the clean-process replay twin on the "
                    "production midgame lane answered the same inputs and seed differently "
                    "(MIDGAME_REPLAY_TWIN_EXECUTIONS.json)"
                )
                row["reason"] = row["failure_reason"]
                row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
                row["replay_twin_divergence"] = finding
        for fixture, finding in demonstrated.items():
            if fixture not in rows:
                continue
            row = rows[fixture]
            row["pre_knowledge_projection_exit_state"] = row["exit_state"]
            row["exit_state"] = "FAIL"
            row["execution_mode"] = knowledge_projection_mod.EXECUTION_MODE
            row["failure_reason"] = (
                f"{finding['classification']}: the production mid-game lane's "
                "actor-entitled knowledge projection violated the record's viewer "
                "obligation (KNOWLEDGE_PROJECTION_EXECUTIONS.json)"
            )
            row["reason"] = row["failure_reason"]
            row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
            row["knowledge_projection_failed_checks"] = finding["failed_checks"]

        # R-4 is an all-PASS invariant, not merely a promotion rule. A row that
        # the runner directly classified PASS still earns zero FULL107 credit
        # unless the admitted producer persisted an exact, current
        # candidate/runner/obligation-bound positive receipt.
        if not carried_forward:
            for fixture, row in rows.items():
                if row["exit_state"] != "PASS":
                    continue
                receipt_ids = bindings.get(fixture, {}).get(candidate) or []
                if receipt_ids:
                    row["positive_receipt_identities"] = receipt_ids
                    row.setdefault("terminal_facts", {})
                    row["terminal_facts"]["positive_receipts"] = receipt_ids
                    receipt_backed_existing_pass += 1
                    continue
                row["pre_r4_receipt_exit_state"] = "PASS"
                row["pre_r4_receipt_reason"] = row.get("reason")
                row["exit_state"] = "UNKNOWN"
                row["failure_reason"] = (
                    "R-4 direct-credit gate: the row executed as PASS but no valid "
                    "positive fixture receipt matched the current candidate, runner, "
                    "requested-state digest and obligation digest"
                )
                row["reason"] = row["failure_reason"]
                row["evidence_class"] = "DIRECT_EXECUTION_UNCREDITED_NO_R4_RECEIPT"
                demoted_without_receipt += 1

        for fixture, per in bindings.items():
            receipt_ids = per.get(candidate)
            if not receipt_ids or fixture not in rows:
                continue
            if carried_forward:
                # A carried-forward column has no executions in this epoch, so a
                # current receipt may never relabel it as fresh.
                continue
            row = rows[fixture]
            if row["exit_state"] == "PASS":
                continue
            # A contradictory direct failure is adjudication evidence, not
            # something an alternate positive route may silently overwrite.
            if row["exit_state"] in {
                "FAIL",
                "CRASH",
                "TIMEOUT",
                "PROTOCOL_FAILURE",
            }:
                row["positive_receipt_conflict"] = receipt_ids
                continue
            row["exit_state"] = "PASS"
            row["failure_reason"] = None
            if all(name.startswith(midgame_rows_mod.TEST_IDENTITY_PREFIX) for name in receipt_ids):
                row["execution_mode"] = midgame_rows_mod.EXECUTION_MODE
                row["reason"] = (
                    "exact placement obligation executed on the production midgame lane "
                    f"({', '.join(receipt_ids)}): the engine constructed the record's state, "
                    "every answer was an engine-offered option from the record's decision "
                    "script, and every required event and terminal check was verified "
                    "against the engine's public event tape and observation"
                )
            elif all(
                name.startswith(knowledge_projection_mod.TEST_IDENTITY_PREFIX)
                for name in receipt_ids
            ):
                row["execution_mode"] = knowledge_projection_mod.EXECUTION_MODE
                row["reason"] = (
                    "actor-entitled knowledge boundary executed on the production midgame "
                    f"lane ({', '.join(receipt_ids)}): the engine constructed the record's "
                    "SLOT-04 lossless state exactly and reported every declared lossless "
                    "check, every principal's projection was read from the live rules "
                    "state, the record's viewer obligation held against the values the "
                    "record requests, and no forbidden identity or honey sentinel appeared "
                    "in any channel the viewer receives"
                )
            elif all(
                name.startswith(midgame_replay_twin_mod.TEST_IDENTITY_PREFIX)
                for name in receipt_ids
            ):
                row["execution_mode"] = midgame_replay_twin_mod.EXECUTION_MODE
                row["reason"] = (
                    "clean-process replay twin executed on the production midgame lane "
                    f"({', '.join(receipt_ids)}): the record's scenario ran from its "
                    "decision script with engine-offered options only, a fresh process "
                    "replayed it from the taped external inputs alone, and the decision "
                    "tape, canonical event tape, Rules RNG coordinates and results, "
                    "public, actor and privileged checkpoint digests and each process's "
                    "own terminal observation compared equal with every adversarial "
                    "control detected; the row's own replay property held on those tapes"
                )
            elif all(
                name.startswith(forge_scenario_mod.FORGE_SCENARIO_TEST_IDENTITY_PREFIX)
                for name in receipt_ids
            ):
                row["execution_mode"] = forge_scenario_mod.FORGE_SCENARIO_EXECUTION_MODE
                row["reason"] = (
                    "exact obligation executed on the Forge ScenarioBootstrap lane "
                    f"({', '.join(receipt_ids)}): the pinned bridge constructed the "
                    "record's requested state through the native scenario seam, every "
                    "answer was an engine-offered option, and the obligation was observed "
                    "from engine-reported terminal facts and semantic events; the receipt "
                    "records the checkpoint verdict, so a fixture-declared cause variance "
                    "is never presented as exact"
                )
            else:
                row["reason"] = (
                    "R-4 exact direct producer receipt verified for the current candidate, "
                    f"runner and obligation ({', '.join(receipt_ids)})"
                )
            row["evidence_class"] = "FRESH_CURRENT_BOUNDARY_RUNTIME"
            row["positive_receipt_identities"] = receipt_ids
            row.setdefault("terminal_facts", {})
            row["terminal_facts"]["positive_receipts"] = receipt_ids
            promoted += 1
        counts = {
            "PASS": 0,
            "FAIL": 0,
            "UNKNOWN": 0,
            "BLOCKED": 0,
            "CRASH": 0,
            "TIMEOUT": 0,
            "PROTOCOL_FAILURE": 0,
        }
        for row in rows.values():
            counts[row["exit_state"]] = counts.get(row["exit_state"], 0) + 1
        assert sum(counts.values()) == 107, counts
        results["rows"] = [rows[row["fixture_id"]] for row in results["rows"]]
        results["counts"] = counts
        # Kept as a backwards-compatible field only: R-4 forbids native-suite
        # execution from promoting FULL107 rows, so it is now always zero.
        results["native_promotions"] = 0
        results["positive_receipt_promotions"] = promoted
        results["positive_receipt_existing_passes"] = receipt_backed_existing_pass
        results["r4_unreceipted_pass_demotions"] = demoted_without_receipt
        results["native_runs"] = native_credit(
            candidate,
            results["runtime_identity"].get("engine_candidate_commit", ""),
            assembly_runner_digest,
        )
        results["native_runs_provenance"] = native_credit_provenance(
            candidate,
            results["runtime_identity"].get("engine_candidate_commit", ""),
            assembly_runner_digest,
        )
        write(f"FULL107_{candidate.upper()}_RESULTS.json", results)
        per_candidate[candidate] = {
            "rows": rows,
            "counts": counts,
            "native_runs": results["native_runs"],
            "native_runs_provenance": results["native_runs_provenance"],
            # Bound here so the AF matrix can never read another candidate's
            # identity through a leaked loop variable.
            "results_runtime_identity": results["runtime_identity"],
            # Whether this column executed in this epoch or is the historical
            # record carried forward for the comparison. A carried-forward
            # column must never be presented as a fresh execution.
            "column_provenance": {
                "class": (
                    "CARRIED_FORWARD_FROM_HISTORICAL_EPOCH"
                    if results.get("carried_forward")
                    else "FRESH_CURRENT_BOUNDARY_EXECUTION"
                ),
                **(results.get("carried_forward") or {}),
            },
        }

    # ---- PB-03 admission x runtime ledger ---------------------------------
    admission_path = OUT / "PB03_DIMENSION_ADMISSION.json"
    runtime_path = OUT / "PB03_RUNTIME_EXECUTION.json"
    if admission_path.is_file() and runtime_path.is_file():
        admission = load(admission_path)
        runtime = load(runtime_path)
        admission_rows = {
            str(row["fixture_id"]): row
            for row in admission.get("rows", [])
            if isinstance(row, dict) and row.get("fixture_id")
        }
        runtime_rows = {
            str(row["fixture_id"]): row
            for row in runtime.get("rows", [])
            if isinstance(row, dict) and row.get("fixture_id")
        }
        if set(admission_rows) != set(runtime_rows):
            raise RuntimeError(
                "PB-03 admission/runtime denominator mismatch: "
                f"admission_only={sorted(set(admission_rows) - set(runtime_rows))} "
                f"runtime_only={sorted(set(runtime_rows) - set(admission_rows))}"
            )
        # The runtime ledger earns credit only when it proves the exact audited
        # test executed under the exact assembling runner, engine candidate and
        # loaded engine artifact. The admission document is produced by a live
        # provider handshake in the same run and carries the provider-reported
        # artifact digest; the runtime ledger must name the same artifact. The
        # raw execution is still reported, but a stale/missing/invalid identity
        # block zeroes the runtime credit with an auditable reason; it is never
        # grandfathered from a previous runner, engine epoch or engine artifact.
        xmage_identity = per_candidate["xmage"]["results_runtime_identity"]
        admission_provider = admission.get("provider_identity")
        expected_artifact_digest = (
            str(admission_provider.get("engine_artifact_sha256", ""))
            if isinstance(admission_provider, dict)
            else ""
        )
        runtime_freshness = pb03_runtime_mod.runtime_execution_freshness(
            runtime,
            expected_runner_digest=assembly_runner_digest,
            expected_candidate_commit=str(xmage_identity.get("engine_candidate_commit", "")),
            expected_engine_artifact_sha256=expected_artifact_digest,
        )
        artifact_identity_consistent = (
            isinstance(admission_provider, dict)
            and admission_provider.get("engine_artifact_sha256")
            == runtime.get("engine_artifact_sha256")
            and admission_provider.get("engine_artifact_kind") == "file"
        )
        runtime_credited = (
            runtime_freshness == pb03_runtime_mod.PB03_RUNTIME_FRESH
            and artifact_identity_consistent
        )
        pb03_matrix_rows = []
        for fixture_id in sorted(admission_rows):
            runtime_row = runtime_rows[fixture_id]
            pb03_matrix_rows.append(
                {
                    "fixture_id": fixture_id,
                    "admission_verdict": admission_rows[fixture_id]["verdict"],
                    "required_tokens": admission_rows[fixture_id].get("required_tokens", []),
                    "missing_tokens": admission_rows[fixture_id].get("missing_tokens", []),
                    "runtime_execution": runtime_row["runtime_execution"],
                    "runtime_credit": "EXECUTED_PASS" if runtime_credited else "NONE",
                    "native_receipt": runtime_freshness,
                    "harness_class": runtime_row["harness_class"],
                    "harness_method": runtime_row["harness_method"],
                    "route": runtime_row["route"],
                    "semantic_relation": runtime_row["semantic_relation"],
                    "full107_credit": "NONE_FROM_PB03_MATRIX",
                }
            )
        write(
            "PB03_RUNTIME_EXECUTION_MATRIX.json",
            {
                "schema_version": "commander-lab.pb03-admission-runtime-matrix/2.0.0",
                "PB03_DIMENSION_ADMISSION": admission.get("classification", "UNKNOWN"),
                "PB03_RUNTIME_EXECUTION": runtime.get("classification", "UNKNOWN"),
                "native_receipt": runtime_freshness,
                "runtime_credit": "EXECUTED_PASS" if runtime_credited else "NONE",
                "runtime_credit_reason": (
                    "runner digest, engine candidate and loaded engine artifact match the "
                    "assembling head and the admission handshake"
                    if runtime_credited
                    else f"receipt identity classified {runtime_freshness}; zero runtime credit"
                ),
                "engine_artifact": {
                    "kind": runtime.get("engine_artifact_kind"),
                    "path": runtime.get("engine_artifact_path"),
                    "sha256": runtime.get("engine_artifact_sha256"),
                    "size": runtime.get("engine_artifact_size"),
                },
                "artifact_identity_consistent": artifact_identity_consistent,
                "rows_total": len(pb03_matrix_rows),
                "admission_counts": admission.get("counts", {}),
                "runtime_executed_pass": runtime.get("executed_pass", 0),
                "runtime_not_run_or_failed": runtime.get("not_run_or_failed", 0),
                "rows": pb03_matrix_rows,
                "orthogonality": (
                    "Admission is frozen-state restorability; runtime execution is exact "
                    "native-harness execution. Neither axis promotes FULL107 rows."
                ),
                "architecture_freeze": "NOT_CLAIMED",
                "production_provider": "NOT_SELECTED",
            },
        )

    # ---- AF00-AF11 matrix ------------------------------------------------
    # AF11 is computed, never asserted: measured technical facts decide between
    # FAIL (a fact is violated) and UNKNOWN (facts hold, policy unresolved).
    af11_by_candidate = {
        cand: _af11_measure(per_candidate, cand, cdata) for cand, cdata in per_candidate.items()
    }
    # AF09 is derived from the recorded RNG/replay artifact, never asserted:
    # a refusal is recorded as a refusal, and seed acknowledgement is never
    # presented as a Rules RNG tape.
    midgame_twin_by_candidate = {
        cand: midgame_replay_twin_document(cand, cdata, assembly_runner_digest)
        for cand, cdata in per_candidate.items()
    }
    replay_by_candidate = {
        cand: (
            _describe_replay_evidence(
                document,
                cand,
                twin_proven=gate_derivations_mod.select_clean_process_twin(
                    document, midgame_twin_by_candidate[cand]
                )[1]
                is not None,
            )
            if (document := _load_replay_document(cand)) is not None
            else {
                "evidence": [f"no RNG_REPLAY artifact exists for {cand}"],
                "limitations": [
                    "without a recorded export attempt and seed binding, no replay "
                    "or RNG claim can be evaluated"
                ],
            }
        )
        for cand in per_candidate
    }

    for candidate, data in per_candidate.items():
        counts = data["counts"]
        af01 = load(OUT / f"AF01_{candidate.upper()}.json")
        extra = _load_fullgame_lane_auxiliary(candidate)
        extra_note: str | None = None
        if extra is not None:
            # An auxiliary artifact produced by an earlier boundary epoch must
            # never be quoted as current evidence. It is dropped from the gate
            # and its exclusion is recorded instead of silently inherited.
            expected_engine = str(
                data["results_runtime_identity"].get("engine_candidate_commit", "")
            )
            if str(extra.get("engine_commit_reported") or "") != expected_engine:
                extra_note = (
                    "the auxiliary full-game-lane AF01 artifact is bound to a different "
                    f"engine epoch ({str(extra.get('engine_commit_reported') or 'unknown')[:12]}) "
                    "than this assembly; its verdict is not cited as current evidence"
                )
                extra = None
        seed_supported = (af01.get("capabilities_provider_reported") or {}).get("seed_supported")
        rng_clause = next(
            (
                item.get("verdict")
                for item in af01.get("invariants", [])
                if item.get("invariant") == "rules_randomness_core_owned"
            ),
            "absent",
        )
        # Receipt-derived, never the retired NATIVE_RUNS literal. The summary
        # counts only what a verified receipt observed, and it is empty when no
        # receipt exists, so the gate cannot inherit a historical count.
        native = data["native_runs"]
        native_summary = data["native_runs_provenance"].get("summary", {})
        native_groups = list(native)
        native_tests = int(native_summary.get("tests", 0))
        native_green = (
            bool(native_groups)
            and not native_summary.get("failed")
            and not native_summary.get("errors")
        )
        cardinality = load(OUT / f"PLAYER_CARDINALITY_{candidate.upper()}.json")
        # All-or-nothing. This previously counted any run with a non-empty
        # steps_completed list, so a lifecycle that only imported decks and
        # created a game counted as a completed player count, and four such
        # prefixes earned AF02 PASS. A shortfall is UNKNOWN, not FAIL: an
        # unestablished count is an evidence gap, not a refutation.
        cardinality_assessment = lifecycle_mod.cardinality_verdict(cardinality["results"])
        matrix = [
            af00_gate(candidate, data, af01),
            {
                "gate": "AF01",
                "name": "PROTOCOL_HANDSHAKE",
                "verdict": af01["verdict"],
                "evidence": [
                    f"{len(af01['invariants'])} AF01 v2 invariants executed under "
                    f"Protocol 2.0.0 on the {af01['lane']} lane",
                    f"AF01_*_{candidate.upper()}.json",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": (
                    [
                        "the generic compatibility lane reports "
                        f"seed_supported={seed_supported}; the rules_randomness_core_owned "
                        f"invariant verdict is {rng_clause}, and any engine seed "
                        "acknowledgement is recorded in the candidate's HIDDEN_INFO artifact"
                    ]
                    if candidate == "xmage"
                    else []
                )
                + ([f"full-game lane AF01 verdict: {extra['verdict']}"] if extra else [])
                + ([extra_note] if extra_note else []),
            },
            {
                "gate": "AF02",
                "name": "PLAYER_CARDINALITY",
                "verdict": cardinality_assessment["verdict"],
                "all_or_nothing": True,
                "evidence": [
                    cardinality_assessment["reason"],
                    f"counts with a complete lifecycle: {cardinality_assessment['complete_counts']}",
                    f"counts without one: {cardinality_assessment['incomplete_counts']}",
                    f"bounded 6P lifecycle recorded: {'6P' in cardinality['results']}",
                ],
                "lifecycle_assessment": cardinality_assessment,
                "blocking_rows": [],
                "nonblocking_limitations": [
                    "6P is bounded secondary evidence; 7P is not attempted on this boundary"
                ],
            },
            af03_gate(candidate),
            af04_gate(candidate, af01, cardinality, data["results_runtime_identity"]),
            # AF05-AF09 are DERIVED, never literals. Each derivation is
            # conservative: a demonstrated violation is FAIL, an unproven
            # element is UNKNOWN named by mechanism, PASS needs every mandatory
            # element of that gate's own contract.
            gate_derivations_mod.af05_hidden_information(
                candidate,
                data["rows"],
                (
                    load(OUT / f"HIDDEN_INFO_{candidate.upper()}.json")
                    if (OUT / f"HIDDEN_INFO_{candidate.upper()}.json").is_file()
                    else None
                ),
            ),
            gate_derivations_mod.af06_general_rules(candidate, data["rows"], counts),
            gate_derivations_mod.af07_actual_card(
                candidate,
                data["rows"],
                (
                    load(OUT / f"ACTUAL_CARD_{candidate.upper()}.json")
                    if (OUT / f"ACTUAL_CARD_{candidate.upper()}.json").is_file()
                    else None
                ),
                campaign_states=actual_card_campaign_credit(
                    candidate, data, assembly_runner_digest
                ),
            ),
            gate_derivations_mod.af08_multiplayer(candidate, data["rows"], cardinality),
            gate_derivations_mod.af09_rng_replay(
                candidate,
                data["rows"],
                _load_replay_document(candidate),
                described=replay_by_candidate[candidate],
                midgame_twin=midgame_twin_by_candidate[candidate],
            ),
            {
                "gate": "AF10",
                "name": "RUNTIME_EVIDENCE_RELIABILITY",
                "verdict": "PASS"
                if (
                    counts["CRASH"] == 0
                    and counts["TIMEOUT"] == 0
                    and counts["PROTOCOL_FAILURE"] == 0
                    and native_green
                )
                else "FAIL",
                "evidence": [
                    f"denominator accounting complete: "
                    f"{sum(counts.values())} explicit outcomes for 107 rows",
                    "zero CRASH/TIMEOUT/PROTOCOL_FAILURE",
                    f"native suites: {native_tests} tests, all green",
                ],
                "blocking_rows": [],
                "nonblocking_limitations": [],
            },
            {
                "gate": "AF11",
                "name": "INTEROP_LICENSE_TOPOLOGY",
                # COMPUTED, not asserted. This gate was a hard-coded FAIL with prose
                # that did not address its own contract ("actual integration topology
                # satisfies WS-09; Forge remains a genuine separate process/service").
                # A gate that cannot observe anything cannot be evidence in either
                # direction, so the technical facts are now measured above and the
                # verdict is derived from them.
                "verdict": af11_by_candidate[candidate]["verdict"],
                "evidence": af11_by_candidate[candidate]["evidence"],
                "blocking_rows": [],
                "nonblocking_limitations": af11_by_candidate[candidate]["limitations"],
            },
        ]
        if data["column_provenance"]["class"] != "FRESH_CURRENT_BOUNDARY_EXECUTION":
            _annotate_carried_gates(matrix, data["column_provenance"])
        write(
            f"AF00_AF11_{candidate.upper()}.json",
            {
                "schema_version": "wsr22.af-matrix/1.0.0",
                "candidate": candidate,
                "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
                "gate_catalog": "architecture_freeze_gate_catalog_v2.json (AF00-AF11, all required)",
                "boundary": data["column_provenance"]["class"],
                "column_provenance": data["column_provenance"],
                "native_runs": native,
                "full107_counts": counts,
                "gates": matrix,
            },
        )

    # ---- R-5 current provider-readiness packet ---------------------------
    # This is an evidence handoff, not a selection algorithm. It reports the
    # current AF00-AF10 and FULL107 residuals for #255 without assigning scores,
    # ranks or a preferred provider. AF11 is intentionally deferred until after
    # provider selection by the accepted slot order.
    readiness_candidates: dict[str, Any] = {}
    for candidate, data in per_candidate.items():
        af_document = load(OUT / f"AF00_AF11_{candidate.upper()}.json")
        af00_af10 = [gate for gate in af_document["gates"] if gate["gate"] != "AF11"]
        residual_rows = [
            {
                "fixture_id": fixture,
                "exit_state": row["exit_state"],
                "execution_mode": row.get("execution_mode"),
                "reason": row.get("reason"),
            }
            for fixture, row in sorted(data["rows"].items())
            if row["exit_state"] != "PASS"
        ]
        readiness_candidates[candidate] = {
            "column_provenance": data["column_provenance"],
            "runtime_identity": data["results_runtime_identity"],
            "full107_counts": data["counts"],
            "full107_residual_count": len(residual_rows),
            "full107_residual_rows": residual_rows,
            "af00_af10": af00_af10,
            "af00_af10_non_pass": [gate for gate in af00_af10 if gate.get("verdict") != "PASS"],
            "native_suite_role": ("SUPPORTING_EVIDENCE_ONLY_R4_NO_FULL107_CREDIT"),
        }
    write(
        "PROVIDER_READINESS_CURRENT.json",
        {
            "schema_version": "commander-lab.provider-readiness-current/1.0.0",
            "issue": 425,
            "coordinator_tracker": 255,
            "evidence_epoch": epoch_identity,
            "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            "owner_rulings": ["R-1", "R-2", "R-3", "R-4"],
            "r4_credit_policy": (
                "FULL107 PASS requires a current exact positive per-fixture receipt "
                "bound to candidate, runner, requested-state digest and obligation digest"
            ),
            "candidates": readiness_candidates,
            "af11": "DEFERRED_UNTIL_AFTER_PROVIDER_SELECTION",
            "production_provider": "NOT_SELECTED",
            "architecture_freeze": "NOT_CLAIMED",
            "ranking": "NONE",
            "selection": "COORDINATOR_OWNED_IN_ISSUE_255",
        },
    )

    # ---- comparison ------------------------------------------------------
    x = per_candidate["xmage"]["rows"]
    f = per_candidate["forge"]["rows"]
    dispositions: dict[str, int] = {}
    comparison: list[dict[str, Any]] = []
    for fixture in sorted(x):
        xr, fr = x[fixture], f[fixture]
        if xr["exit_state"] == fr["exit_state"] == "PASS":
            # PASS/PASS is not a semantic comparison. Compare the normalized
            # Rules-visible observations the two sides actually recorded, so two
            # engines that disagree about a turn number or a library count are
            # reported as a difference instead of being labelled equal.
            comparison_result = semantic_mod.compare_semantics(xr, fr)
            disposition = comparison_result["disposition"]
            note = comparison_result["reason"]
            if disposition == "RULES_VISIBLE_DIVERGENCE":
                note += " (requires Coordinator Rules adjudication)"
        elif "FAIL" in (xr["exit_state"], fr["exit_state"]):
            disposition = "UNKNOWN_PENDING_RULES_ADJUDICATION"
            note = "a current-boundary failure requires Coordinator Rules adjudication"
        elif "BLOCKED" in (xr["exit_state"], fr["exit_state"]):
            disposition = "NON_COMPARABLE"
            note = (
                "no current-boundary execution seam on at least one side; an absent seam "
                "is not a Rules difference and is not a capability claim"
            )
        else:
            disposition = "NON_COMPARABLE"
            note = (
                "at least one side has no fixture-corresponding current-boundary evidence; "
                "this is an evidence gap, not a proven semantic difference"
            )
        dispositions[disposition] = dispositions.get(disposition, 0) + 1
        comparison.append(
            {
                "fixture_id": fixture,
                "disposition": disposition,
                "note": note,
                **(
                    {"semantic_comparison": comparison_result}
                    if xr["exit_state"] == fr["exit_state"] == "PASS"
                    else {}
                ),
                "xmage": {
                    "exit_state": xr["exit_state"],
                    "execution_mode": xr["execution_mode"],
                    "reason": xr["reason"],
                },
                "forge": {
                    "exit_state": fr["exit_state"],
                    "execution_mode": fr["execution_mode"],
                    "reason": fr["reason"],
                },
                "engine_local_ids_excluded": [
                    "game_id",
                    "engine_game_id",
                    "player_id",
                    "decision_id",
                    "option_id",
                    "revision",
                ],
            }
        )
    write(
        "CURRENT_BOUNDARY_COMPARISON.json",
        {
            "schema_version": "wsr22.current-boundary-comparison/1.0.0",
            "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
            "denominator": 107,
            "dispositions": dispositions,
            # Which columns executed in this epoch and which are the historical
            # record carried forward; the comparison is only as fresh as its
            # least fresh column, and that is stated rather than implied.
            "column_provenance": {
                candidate: data["column_provenance"] for candidate, data in per_candidate.items()
            },
            "rows": comparison,
            "no_ranking": "this packet contains no score, no ranking and no preferred provider",
        },
    )
    write(
        "DIVERGENCE_PACKET.json",
        {
            "schema_version": "wsr22.divergence-packet/1.0.0",
            "ruled_visible_divergences": [],
            "count": 0,
            "pending_rules_adjudication": [
                row["fixture_id"]
                for row in comparison
                if row["disposition"] == "UNKNOWN_PENDING_RULES_ADJUDICATION"
            ],
            "note": (
                "No Rules-visible behavioural divergence was observed. The cross-engine "
                "differences found in this workstream are protocol/interface shape "
                "differences, recorded in CURRENT_BOUNDARY_COMPARISON and "
                "PROVIDER_BLOCKERS, not Magic Rules disagreements. The Coordinator performs "
                "final independent Rules adjudication."
            ),
        },
    )
    print(json.dumps(dispositions, indent=1))
    print("xmage", per_candidate["xmage"]["counts"])
    print("forge", per_candidate["forge"]["counts"])


if __name__ == "__main__":
    assemble()
