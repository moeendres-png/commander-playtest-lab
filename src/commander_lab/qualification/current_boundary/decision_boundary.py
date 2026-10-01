"""AF04 decision-boundary derivation from same-epoch external decision evidence.

AF04's contract is: complete legal options; no adapter/pilot legality
reconstruction; fail-closed unsupported decisions.

The previous assembler pinned Forge AF04 to UNKNOWN with a hard-coded premise
("no STARTING_PLAYER, MULLIGAN or DRAW decision class beyond PRIORITY was
reachable"). That premise is observable, so it must be measured rather than
asserted. This module measures it from the same-epoch runtime evidence the
runner already persists:

* ``PLAYER_CARDINALITY_<CANDIDATE>.json`` records, for every cardinality, the
  external decision tape (kind/actor/revision/offered option ids/chosen option
  id) and the engine's own response payloads for each answered decision; and
* ``AF01_<CANDIDATE>.json`` records the live R-2 provenance check and the
  fail-closed decision-time invariants.

Nothing here is a second legality source. The module never decides what action
is legal, never ranks or filters options, and never substitutes a choice: it
only checks whether the recorded submission is attributable to an engine-offered
option domain and whether the engine itself accepted the submission.

Semantic distinctions the derivation enforces, stated once:

* A frame with an empty offered option set does not establish an engine-authored
  decision domain; a null chosen id on such a frame is UNKNOWN, not PASS.
* A non-null chosen id that is absent from the offered set is a contradiction
  (the submission was not engine-offered) and fails closed.
* A decision class whose harness boundary is a dedicated engine message rather
  than a raw option id (``MULLIGAN``) must still be proven engine-offered: the
  engine's own executed-option identity must be present in the frame's offered
  set where the engine reports it, and the engine's acceptance must be recorded
  where it does not.
* A keep-all mulligan sequence proves the engine processed each keep (rather
  than a default firing) when every seat decides exactly once, no two
  consecutive mulligan frames share an actor, and the sequence is terminated by
  a priority frame. A shipped hand would have parked the same actor again.
* An unmeasured element is UNKNOWN. A measured contradiction is FAIL. Neither is
  ever PASS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

SCHEMA_VERSION = "commander-lab.af04-decision-boundary/1.0.0"

# AF02's required player counts. The decision boundary is measured on the same
# required counts; a bounded secondary count (6P) is additionally checked when
# the epoch carries it, and a failure there is not silently ignored.
REQUIRED_CARDINALITIES: tuple[str, ...] = ("2P", "3P", "4P", "5P")
BOUNDED_SECONDARY_CARDINALITIES: tuple[str, ...] = ("6P",)

# Tape step name -> observation step name that carries the engine's response.
OBSERVATION_STEP_BY_KIND: dict[str, str] = {
    "STARTING_PLAYER": "starting_player",
    "CHOOSE_STARTING_PLAYER": "starting_player",
    "MULLIGAN": "mulligan_keep",
    "KEEP_OR_MULLIGAN": "mulligan_keep",
    "PRIORITY": "priority_pass",
    # The cost-order decision class is option-id addressed: the pilot selects
    # one provider-published structural option, and the engine's response
    # records the acceptance exactly as it does for the other classes.
    "ORDER_CHOICE": "cost_order",
}

# Decision classes for which the harness boundary is a dedicated engine message
# rather than a raw option id. The engine itself maps the submitted semantic
# value onto exactly one of its own offered options and rejects a mismatch, so
# a null ``chosen_option_id`` is legitimate here — but only with a recorded
# engine acceptance.
NON_OPTION_ID_CLASSES: frozenset[str] = frozenset({"MULLIGAN", "KEEP_OR_MULLIGAN"})

# Policies the driver records when it could not answer from the offered domain.
FAIL_CLOSED_POLICIES: frozenset[str] = frozenset({"NO_MATCHING_OFFERED_OPTION"})


@dataclass
class Finding:
    """One measured fact about the decision boundary."""

    severity: str  # "CONTRADICTION" | "GAP"
    cardinality: str
    kind: str
    actor: str | None
    detail: str

    def document(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "cardinality": self.cardinality,
            "kind": self.kind,
            "actor": self.actor,
            "detail": self.detail,
        }


@dataclass
class FrameProof:
    """The proof state of one recorded external decision frame."""

    cardinality: str
    kind: str
    actor: str | None
    revision: Any
    offered_count: int
    chosen_option_id: str | None
    engine_executed_option_id: str | None
    engine_accepted: bool
    detail: str
    findings: list[Finding] = field(default_factory=list)

    def document(self) -> dict[str, Any]:
        return {
            "cardinality": self.cardinality,
            "kind": self.kind,
            "actor": self.actor,
            "revision": self.revision,
            "offered_count": self.offered_count,
            "chosen_option_id": self.chosen_option_id,
            "engine_executed_option_id": self.engine_executed_option_id,
            "engine_accepted": self.engine_accepted,
            "detail": self.detail,
        }


def _observations_by_step(results: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for observation in results.get("observations") or []:
        if not isinstance(observation, dict):
            continue
        step = str(observation.get("step") or "")
        payload = observation.get("payload")
        grouped.setdefault(step, []).append(payload if isinstance(payload, dict) else {})
    return grouped


def _engine_acceptance(candidate: str, payload: dict[str, Any]) -> tuple[bool, str | None, str]:
    """Read whether the engine recorded acceptance, and any executed option id.

    Two provider-native shapes are accepted, and only these:

    * an ``executed_action_id`` (XMage ``resolve_mulligan`` / ``pass_priority``
      responses) — the engine's own selected option; and
    * a ``decision.executed`` boolean (Forge ``submit_action`` /
      ``resolve_mulligan`` responses).

    A payload carrying neither is not evidence of acceptance.
    """
    executed_option = payload.get("executed_action_id")
    executed_option = str(executed_option) if isinstance(executed_option, str) else None
    decision = payload.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    executed_flag = decision.get("executed")
    if executed_option is not None:
        return True, executed_option, "engine reported the executed option identity"
    if executed_flag is True:
        return True, None, "engine reported the decision executed"
    if executed_flag is False:
        return False, None, "engine reported the decision did not execute"
    return False, None, "no engine acceptance was recorded for this frame"


def _proof_for_frame(
    candidate: str,
    cardinality: str,
    entry: dict[str, Any],
    payload: dict[str, Any] | None,
    player_count: int | None,
) -> FrameProof:
    kind = str(entry.get("kind") or "").upper()
    actor = entry.get("actor")
    actor_text = str(actor) if actor is not None else None
    revision = entry.get("revision")
    offered = [str(item) for item in (entry.get("offered_option_ids") or []) if item]
    chosen = entry.get("chosen_option_id")
    chosen_text = str(chosen) if chosen is not None else None
    findings: list[Finding] = []

    def contradiction(detail: str) -> None:
        findings.append(Finding("CONTRADICTION", cardinality, kind, actor_text, detail))

    def gap(detail: str) -> None:
        findings.append(Finding("GAP", cardinality, kind, actor_text, detail))

    if not actor_text:
        gap("the frame records no actor, so the decision cannot be attributed to a seat")
    if revision is None:
        gap("the frame records no revision, so the offered identity is not bound")
    if not offered:
        gap("the frame records no engine-offered option ids")

    # R-2: a recorded submission must come from the offered domain.
    if chosen_text is not None and offered and chosen_text not in offered:
        contradiction(
            f"submitted option {chosen_text!r} is not among the engine-offered options {offered!r}"
        )
    if chosen_text is not None and not offered:
        contradiction(
            "a non-null option was submitted on a frame that records no engine-offered option ids"
        )
    if chosen_text is None and kind not in NON_OPTION_ID_CLASSES:
        contradiction(
            f"a {kind} frame was answered with no option id, and this class has no "
            "dedicated engine-authored non-option-id route"
        )

    accepted = False
    executed_option: str | None = None
    acceptance_detail = "no recorded engine response"
    if payload is None:
        gap(f"no engine response payload is recorded for this {kind} frame")
    else:
        accepted, executed_option, acceptance_detail = _engine_acceptance(candidate, payload)
        if not accepted:
            contradiction(f"the engine did not accept the submission: {acceptance_detail}")
        if executed_option is not None:
            if offered and executed_option not in offered:
                contradiction(
                    f"the engine executed {executed_option!r}, which is not among the options "
                    f"offered on this frame {offered!r}"
                )
            executed_actor = payload.get("executed_actor_id")
            if isinstance(executed_actor, str) and actor_text and executed_actor != actor_text:
                contradiction(
                    f"the engine executed the decision for {executed_actor!r}, not for the "
                    f"frame actor {actor_text!r}"
                )
        if payload.get("mulligan_choice_external") is False:
            contradiction("the engine reported the mulligan choice was not external")
        if payload.get("keep") is not None and payload.get("keep") is not True:
            contradiction(
                "the keep-all policy submitted a non-keep mulligan value; the recorded "
                "policy and the submitted value disagree"
            )

    if (
        kind in {"STARTING_PLAYER", "CHOOSE_STARTING_PLAYER"}
        and player_count is not None
        and offered
        and len(offered) != player_count
    ):
        # The engine offers one structural option per seat; a different count
        # means the frame is not the seat-choice domain it is recorded as.
        contradiction(
            f"a starting-player frame at {player_count}P offered {len(offered)} options, "
            "which is not one option per seat"
        )

    detail = (
        f"{kind} answered by {actor_text} at revision {revision}; "
        f"{len(offered)} engine-offered option(s); chosen={chosen_text!r}; {acceptance_detail}"
    )
    return FrameProof(
        cardinality=cardinality,
        kind=kind,
        actor=actor_text,
        revision=revision,
        offered_count=len(offered),
        chosen_option_id=chosen_text,
        engine_executed_option_id=executed_option,
        engine_accepted=accepted,
        detail=detail,
        findings=findings,
    )


def _cardinality_frames(
    candidate: str, cardinality: str, results: dict[str, Any]
) -> tuple[list[FrameProof], list[Finding]]:
    """Prove every recorded external decision frame in one cardinality run."""
    findings: list[Finding] = []
    tape = [entry for entry in (results.get("decision_tape") or []) if isinstance(entry, dict)]
    observations = _observations_by_step(results)
    player_count = results.get("player_count")
    player_count = int(player_count) if isinstance(player_count, int) else None

    if results.get("failure") is not None:
        findings.append(
            Finding("GAP", cardinality, "RUN", None, f"the run failed: {results['failure']!r}")
        )
    if "decision_drive" not in (results.get("steps_completed") or []):
        findings.append(
            Finding(
                "GAP",
                cardinality,
                "RUN",
                None,
                "the run did not complete the decision drive, so no frame evidence exists",
            )
        )
    terminal = results.get("terminal_facts") or {}
    if terminal.get("stopped_at_decision_kind"):
        findings.append(
            Finding(
                "CONTRADICTION",
                cardinality,
                str(terminal["stopped_at_decision_kind"]),
                None,
                "the driver stopped at a decision class outside its external policy; the "
                "decision boundary is not satisfied for this run",
            )
        )
    if terminal.get("priority_reached") is not True:
        findings.append(
            Finding(
                "GAP",
                cardinality,
                "PRIORITY",
                None,
                "the run never reached a priority decision",
            )
        )

    for entry in tape:
        policy = str(entry.get("policy") or "")
        if policy in FAIL_CLOSED_POLICIES:
            findings.append(
                Finding(
                    "CONTRADICTION",
                    cardinality,
                    str(entry.get("kind") or "UNKNOWN").upper(),
                    str(entry.get("actor")) if entry.get("actor") is not None else None,
                    f"a frame was answered by the fail-closed policy {policy!r}; the frame was "
                    "not answered from the engine-offered domain",
                )
            )

    # Pair frames with the engine's own response payloads, in recorded order.
    payloads: dict[str, list[dict[str, Any]]] = {}
    for entry in tape:
        kind = str(entry.get("kind") or "").upper()
        step = OBSERVATION_STEP_BY_KIND.get(kind)
        if step is None:
            continue
        payloads.setdefault(kind, list(observations.get(step) or []))

    frame_proofs: list[FrameProof] = []
    for entry in tape:
        kind = str(entry.get("kind") or "").upper()
        payload: dict[str, Any] | None
        if payloads.get(kind):
            payload = payloads[kind].pop(0)
        elif kind in OBSERVATION_STEP_BY_KIND:
            payload = None
        else:
            payload = None
        proof = _proof_for_frame(candidate, cardinality, entry, payload, player_count)
        frame_proofs.append(proof)
        findings.extend(proof.findings)

    # Mulligan-sequence proof: every seat keeps exactly once, each keep advances
    # to a different actor, and the sequence ends by leaving pregame.
    mulligans = [proof for proof in frame_proofs if proof.kind in {"MULLIGAN", "KEEP_OR_MULLIGAN"}]
    if mulligans:
        if player_count is not None and len(mulligans) != player_count:
            findings.append(
                Finding(
                    "CONTRADICTION",
                    cardinality,
                    "MULLIGAN",
                    None,
                    f"{len(mulligans)} mulligan frame(s) were recorded for a {player_count}P "
                    "game under a keep-all policy; every seat must decide exactly once",
                )
            )
        actors = [proof.actor for proof in mulligans]
        for previous, current in pairwise(actors):
            if previous is not None and previous == current:
                findings.append(
                    Finding(
                        "CONTRADICTION",
                        cardinality,
                        "MULLIGAN",
                        current,
                        "the same actor decided twice in a row, which is what a shipped hand "
                        "produces; the recorded keep-all policy was not the engine's view",
                    )
                )
        revisions = [proof.revision for proof in mulligans if isinstance(proof.revision, int)]
        if len(revisions) == len(mulligans) and any(
            later <= earlier for earlier, later in pairwise(revisions)
        ):
            findings.append(
                Finding(
                    "CONTRADICTION",
                    cardinality,
                    "MULLIGAN",
                    None,
                    f"mulligan revisions are not strictly increasing: {revisions!r}",
                )
            )
        kinds = [str(entry.get("kind") or "").upper() for entry in tape]
        last_mulligan_index = max(
            index for index, kind in enumerate(kinds) if kind in {"MULLIGAN", "KEEP_OR_MULLIGAN"}
        )
        if not any(kind == "PRIORITY" for kind in kinds[last_mulligan_index + 1 :]):
            findings.append(
                Finding(
                    "GAP",
                    cardinality,
                    "MULLIGAN",
                    None,
                    "no priority frame follows the final mulligan keep, so leaving pregame after "
                    "the last keep is not observed",
                )
            )

    return frame_proofs, findings


def derive_decision_boundary(
    candidate: str,
    cardinality_document: dict[str, Any] | None,
    af01_document: dict[str, Any] | None,
    expected_runtime_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    """Derive AF04's verdict from same-epoch external decision evidence.

    Returns a document with an explicit verdict (PASS/FAIL/UNKNOWN), the
    per-frame proofs, the measured contradictions and the unproven gaps. The
    caller must never promote this to PASS with fewer checks than are recorded
    here.
    """
    contradictions: list[Finding] = []
    gaps: list[Finding] = []
    frame_proofs: list[FrameProof] = []
    required_frame_counts: dict[str, int] = {}

    def check(condition: bool, severity: str, cardinality: str, kind: str, detail: str) -> None:
        if condition:
            return
        target = contradictions if severity == "CONTRADICTION" else gaps
        target.append(Finding(severity, cardinality, kind, None, detail))

    # -- identity binding -------------------------------------------------
    if not isinstance(cardinality_document, dict):
        gaps.append(
            Finding(
                "GAP",
                "-",
                "IDENTITY",
                None,
                "no same-epoch player-cardinality artifact exists for this candidate",
            )
        )
        return _document(candidate, "UNKNOWN", frame_proofs, contradictions, gaps, {})

    recorded_candidate = cardinality_document.get("candidate")
    if not recorded_candidate:
        gaps.append(
            Finding(
                "GAP",
                "-",
                "IDENTITY",
                None,
                "the cardinality artifact does not name its candidate, so it cannot be "
                "attributed to this one",
            )
        )
    elif str(recorded_candidate) != candidate:
        contradictions.append(
            Finding(
                "CONTRADICTION",
                "-",
                "IDENTITY",
                None,
                f"the cardinality artifact names candidate {recorded_candidate!r}, not "
                f"{candidate!r}; a foreign artifact can never derive this candidate's "
                "decision boundary",
            )
        )
    cardinality_identity = cardinality_document.get("runtime_identity") or {}
    if not isinstance(expected_runtime_identity, dict) or not expected_runtime_identity:
        gaps.append(
            Finding(
                "GAP",
                "-",
                "IDENTITY",
                None,
                "the expected runtime identity of this assembly is unavailable",
            )
        )
    else:
        expected_commit = str(expected_runtime_identity.get("engine_candidate_commit") or "")
        actual_commit = str(cardinality_identity.get("engine_candidate_commit") or "")
        check(
            bool(expected_commit) and actual_commit == expected_commit,
            "CONTRADICTION",
            "-",
            "IDENTITY",
            f"the cardinality artifact names engine {actual_commit or 'nothing'!r}, not this "
            f"assembly's candidate {expected_commit or 'nothing'!r}",
        )
        if cardinality_identity != expected_runtime_identity:
            # Not a contradiction of the decision boundary itself, but the
            # decision evidence is not bound to the same runtime identity the
            # row evidence is about.
            gaps.append(
                Finding(
                    "GAP",
                    "-",
                    "IDENTITY",
                    None,
                    "the cardinality artifact's runtime identity is not byte-identical to this "
                    "assembly's runtime identity; the decision evidence is not bound to the "
                    "same runtime",
                )
            )
    boundary_class = cardinality_document.get("boundary")
    if boundary_class is None:
        gaps.append(
            Finding(
                "GAP",
                "-",
                "IDENTITY",
                None,
                "the cardinality artifact records no boundary class, so whether it is a fresh "
                "current-boundary execution is unproven",
            )
        )
    elif str(boundary_class) != "FRESH_CURRENT_BOUNDARY_EXECUTION":
        contradictions.append(
            Finding(
                "CONTRADICTION",
                "-",
                "IDENTITY",
                None,
                f"the cardinality artifact is classed {boundary_class!r}, not a fresh "
                "current-boundary execution",
            )
        )

    provenance = (af01_document or {}).get("decision_identity_provenance") or {}
    provenance_verified = provenance.get("verified")
    if provenance_verified is not True:
        if provenance_verified is False:
            contradictions.append(
                Finding(
                    "CONTRADICTION",
                    "-",
                    "R-2_PROVENANCE",
                    None,
                    "the live AF01 frame's decision-identity provenance is violated",
                )
            )
        else:
            gaps.append(
                Finding(
                    "GAP",
                    "-",
                    "R-2_PROVENANCE",
                    None,
                    "R-2 provenance was not measured on a live frame in this epoch",
                )
            )
    reported_commit = str((af01_document or {}).get("engine_commit_reported") or "")
    if isinstance(expected_runtime_identity, dict) and expected_runtime_identity:
        expected_commit = str(expected_runtime_identity.get("engine_candidate_commit") or "")
        check(
            # Forge's AF01 reports the exact built bridge source, not the
            # Rules-Core candidate; both are bound by the runtime identity.
            reported_commit
            in {
                expected_commit,
                str(expected_runtime_identity.get("bridge_source_commit") or ""),
            },
            "CONTRADICTION",
            "-",
            "IDENTITY",
            f"AF01 reports engine commit {reported_commit or 'nothing'!r}, which is neither the "
            "candidate nor the bound bridge source of this assembly",
        )

    results_by_count = cardinality_document.get("results")
    if not isinstance(results_by_count, dict):
        gaps.append(
            Finding("GAP", "-", "DENOMINATOR", None, "the cardinality artifact carries no results")
        )
        # A recorded contradiction still outranks a later gap: the artifact may
        # be unmeasurable *and* already self-contradictory.
        verdict = "FAIL" if contradictions else "UNKNOWN"
        return _document(candidate, verdict, frame_proofs, contradictions, gaps, {})

    # -- per-cardinality frame proof --------------------------------------
    for count in REQUIRED_CARDINALITIES:
        results = results_by_count.get(count)
        if not isinstance(results, dict):
            gaps.append(
                Finding(
                    "GAP",
                    count,
                    "DENOMINATOR",
                    None,
                    f"no {count} decision evidence exists in this epoch",
                )
            )
            continue
        proofs, findings = _cardinality_frames(candidate, count, results)
        frame_proofs.extend(proofs)
        required_frame_counts[count] = len(proofs)
        for finding in findings:
            (contradictions if finding.severity == "CONTRADICTION" else gaps).append(finding)

    for count in BOUNDED_SECONDARY_CARDINALITIES:
        results = results_by_count.get(count)
        if not isinstance(results, dict):
            continue
        proofs, findings = _cardinality_frames(candidate, count, results)
        frame_proofs.extend(proofs)
        for finding in findings:
            (contradictions if finding.severity == "CONTRADICTION" else gaps).append(finding)

    # -- non-vacuity -------------------------------------------------------
    # A candidate that exposed no external discretionary decision would
    # otherwise trivially satisfy "no forgery was observed". AF04 requires at
    # least one real priority submission from the offered domain on every
    # required count.
    for count in REQUIRED_CARDINALITIES:
        priority_frames = [
            proof
            for proof in frame_proofs
            if proof.cardinality == count
            and proof.kind == "PRIORITY"
            and proof.chosen_option_id is not None
        ]
        if not priority_frames:
            gaps.append(
                Finding(
                    "GAP",
                    count,
                    "PRIORITY",
                    None,
                    f"no {count} priority frame with an engine-offered submitted option was "
                    "recorded; the boundary is vacuous for this count",
                )
            )

    verdict = (
        "PASS" if not contradictions and not gaps else ("FAIL" if contradictions else "UNKNOWN")
    )
    limitations: list[Finding] = []
    if verdict == "PASS" and candidate == "forge":
        # Forge's decision responses do not echo the executed actor, so the
        # actor binding rests on the frame-supplied actor/revision plus the
        # engine's own stale-revision and wrong-actor rejection rather than on a
        # response-side identity. Recorded as a non-blocking limitation so the
        # PASS is not read as more than the evidence shows.
        limitations.append(
            Finding(
                "NOTE",
                "-",
                "ACTOR_BINDING",
                None,
                "Forge responses carry no executed-actor field; the actor binding rests on the "
                "frame-supplied actor/revision plus the engine's stale-revision and wrong-actor "
                "rejection, not on a response-side identity",
            )
        )
    return _document(
        candidate, verdict, frame_proofs, contradictions, gaps, required_frame_counts, limitations
    )


def _document(
    candidate: str,
    verdict: str,
    frame_proofs: list[FrameProof],
    contradictions: list[Finding],
    gaps: list[Finding],
    required_frame_counts: dict[str, int],
    limitations: list[Finding] | None = None,
) -> dict[str, Any]:
    verified_classes = sorted(
        {
            proof.kind
            for proof in frame_proofs
            if proof.engine_accepted
            and not proof.findings
            and (proof.chosen_option_id is None or proof.offered_count > 0)
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": candidate,
        "gate": "AF04",
        "name": "LEGAL_ACTION_AND_DECISION_BOUNDARY",
        "verdict": verdict,
        "required_cardinalities": list(REQUIRED_CARDINALITIES),
        "bounded_secondary_cardinalities_checked": list(BOUNDED_SECONDARY_CARDINALITIES),
        "required_frame_counts": required_frame_counts,
        "externally_answered_decision_classes": verified_classes,
        "frame_count": len(frame_proofs),
        "frames": [proof.document() for proof in frame_proofs],
        "contradictions": [finding.document() for finding in contradictions],
        "gaps": [finding.document() for finding in gaps],
        "limitations": [finding.document() for finding in (limitations or [])],
        "statement": (
            "every recorded external decision frame in this epoch was answered from the "
            "engine-offered option domain, was accepted by the engine, and binds its actor "
            "and revision to the offering frame; no decision class was answered by a "
            "fail-closed policy fallback"
            if verdict == "PASS"
            else (
                "a recorded submission contradicts the engine-offered option domain"
                if verdict == "FAIL"
                else "the decision boundary is not fully measured on this epoch"
            )
        ),
    }
