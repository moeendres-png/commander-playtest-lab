"""Evidence-derived verdicts for the AF gates that used to be literals.

The assembler previously wrote ``"verdict": "UNKNOWN"`` for AF05, AF06, AF07,
AF08 and AF09 with prose evidence and no derivation. A literal cannot be
audited, cannot distinguish "the evidence is absent" from "the evidence
contradicts the claim", and cannot ever become PASS from real work. Each
function here derives the verdict from the same-epoch artifacts and the
denominator rows, and returns every residual by exact mechanism.

The promotion rules are deliberately conservative and identical in shape:

* a demonstrated violation is FAIL;
* an unproven element is UNKNOWN, named explicitly;
* PASS requires every mandatory element of that gate's own contract.

Nothing here decides a Rules question, ranks a candidate, or selects a
provider. A gate that cannot be satisfied today stays non-PASS with the exact
missing mechanism, which is the intended honest outcome.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .full107 import summarize  # noqa: F401  (re-exported for callers/tests)
from .lifecycle import cardinality_verdict
from .receipts import positive_fixture_credit

REPO_ROOT = Path(__file__).resolve().parents[4]

HIDDEN_PREFIX = "HIDDEN_"
REPLAY_PREFIXES = ("REPLAY_", "RNG_")
CARD_PREFIX = "CARD_"
WS05_PREFIX = "WS05-"
CARDINALITY_PREFIX = "PLAYER_COUNT_"

_FAIL_STATES = {"FAIL", "CRASH", "TIMEOUT", "PROTOCOL_FAILURE"}


def _by_id(rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return rows


def _states(rows: dict[str, dict[str, Any]], predicate: Any) -> dict[str, str]:
    return {
        fixture: str(row.get("exit_state")) for fixture, row in rows.items() if predicate(fixture)
    }


def _residual_lines(states: dict[str, str]) -> list[str]:
    return [f"{fixture}: {state}" for fixture, state in sorted(states.items()) if state != "PASS"]


def af05_hidden_information(
    candidate: str,
    rows: dict[str, dict[str, Any]],
    hidden_document: dict[str, Any] | None,
) -> dict[str, Any]:
    """AF05 HIDDEN_INFORMATION, derived from the scoping audit and HIDDEN rows."""
    hidden_states = _states(rows, lambda fixture: fixture.startswith(HIDDEN_PREFIX))
    residuals = _residual_lines(hidden_states)
    if not hidden_states:
        # A gate with no rows to measure would otherwise pass vacuously: PASS
        # requires that the mandatory hidden-channel denominator exists at all.
        return {
            "gate": "AF05",
            "name": "HIDDEN_INFORMATION",
            "verdict": "UNKNOWN",
            "evidence": ["no HIDDEN_* obligation exists in this candidate's denominator"],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "the mandatory hidden-information denominator is absent, so no hidden channel "
                "is measured"
            ],
        }
    evidence: list[str] = [
        f"{sum(1 for state in hidden_states.values() if state == 'PASS')} of "
        f"{len(hidden_states)} HIDDEN_* rows PASS in this epoch",
        "principal-scoping audit: "
        + (
            "no artifact exists for this candidate"
            if hidden_document is None
            else str(
                (hidden_document.get("principal_scoping") or {}).get("attribution")
                or "NOT_RECORDED"
            )
        ),
    ]
    limitations: list[str] = []
    scoping = (hidden_document or {}).get("principal_scoping") or {}
    attribution = str(scoping.get("attribution") or "")
    if attribution == "ENGINE_CANDIDATE_DEFECT":
        return {
            "gate": "AF05",
            "name": "HIDDEN_INFORMATION",
            "verdict": "FAIL",
            "evidence": [
                *evidence,
                "a demonstrated principal-scope leak exists: "
                f"{scoping.get('engine_leak_indicators')}",
            ],
            "blocking_rows": sorted(hidden_states),
            "nonblocking_limitations": [
                "the demonstrated leak is a candidate defect and is never masked"
            ],
        }
    failed = sorted(fixture for fixture, state in hidden_states.items() if state == "FAIL")
    if failed:
        # A HIDDEN_* row that executed and failed demonstrates a violated
        # knowledge boundary; reporting the gate as merely unproven would mask it.
        return {
            "gate": "AF05",
            "name": "HIDDEN_INFORMATION",
            "verdict": "FAIL",
            "evidence": [*evidence, f"demonstrated hidden-information failures: {failed}"],
            "blocking_rows": failed,
            "nonblocking_limitations": [
                "a demonstrated hidden-information failure is never masked as UNKNOWN"
            ],
        }
    if hidden_document is None:
        limitations.append("no HIDDEN_INFO artifact exists for this candidate in this epoch")
    elif not scoping.get("credible_as_principal_scoped_evidence"):
        limitations.append(
            "principal scoping is not established for this epoch "
            f"(attribution {attribution or 'UNKNOWN'}); the observations are recorded as "
            "observed and are not presented as hidden-information evidence"
        )
    if residuals:
        limitations.append(
            "the mandatory per-scenario hidden channels remain unexecuted: "
            + ", ".join(residuals[:20])
            + ("" if len(residuals) <= 20 else f" and {len(residuals) - 20} more")
        )
    verdict = "PASS" if not residuals and not limitations else "UNKNOWN"
    return {
        "gate": "AF05",
        "name": "HIDDEN_INFORMATION",
        "verdict": verdict,
        "evidence": evidence,
        "blocking_rows": sorted(
            fixture for fixture, state in hidden_states.items() if state != "PASS"
        ),
        "nonblocking_limitations": limitations,
    }


def af06_general_rules(
    candidate: str, rows: dict[str, dict[str, Any]], counts: dict[str, int]
) -> dict[str, Any]:
    """AF06 GENERAL_RULES_CORRECTNESS: the effective micro-rules surface."""
    if not rows:
        return {
            "gate": "AF06",
            "name": "GENERAL_RULES_CORRECTNESS",
            "verdict": "UNKNOWN",
            "evidence": ["no denominator rows exist to measure"],
            "blocking_rows": [],
            "nonblocking_limitations": ["an empty denominator proves nothing"],
        }
    non_pass = {
        fixture: str(row.get("exit_state"))
        for fixture, row in rows.items()
        if row.get("exit_state") != "PASS"
    }
    failed = {fixture: state for fixture, state in non_pass.items() if state in _FAIL_STATES}
    if failed:
        verdict = "FAIL"
        limitations = [f"a current-boundary FAIL requires adjudication: {failed}"]
    elif non_pass:
        verdict = "UNKNOWN"
        limitations = [
            f"{len(non_pass)} of {len(rows)} denominator obligations are not PASS on this "
            "boundary; every one of them is an unexecuted or unproven mechanism, not a PASS"
        ]
    else:
        verdict = "PASS"
        limitations = []
    return {
        "gate": "AF06",
        "name": "GENERAL_RULES_CORRECTNESS",
        "verdict": verdict,
        "evidence": [
            f"{counts.get('PASS', 0)} of {len(rows)} rows PASS under the effective contract; "
            f"{counts.get('BLOCKED', 0)} BLOCKED; {counts.get('UNKNOWN', 0)} UNKNOWN",
        ],
        "blocking_rows": sorted(
            fixture for fixture, state in non_pass.items() if state == "BLOCKED"
        ),
        "nonblocking_limitations": limitations,
    }


def actual_card_corpus(repo_root: Any | None = None) -> tuple[dict[str, str], tuple[str, ...]]:
    """The mandatory CARD_ fixture -> card identity map and the frozen 29 corpus.

    Both are read from the frozen manifests, never restated locally: the
    coverage question is "does this identity's OWN mandatory row pass", and only
    the manifest can answer which fixture owns which identity.
    """
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    common = json.loads(
        (root / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").read_text(
            encoding="utf-8"
        )
    )
    domain = json.loads(
        (root / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json").read_text(encoding="utf-8")
    )
    mapping = {
        str(fixture["fixture_id"]): str(fixture["card_identity"])
        for fixture in common["fixtures"]
        if str(fixture.get("fixture_id") or "").startswith(CARD_PREFIX)
        and fixture.get("card_identity")
    }
    corpus = tuple(str(name) for name in domain["regression_corpus_29"])
    if not mapping or not corpus:
        raise ValueError("the actual-card manifests assign no corpus; AF07 cannot be measured")
    return mapping, corpus


def actual_card_campaign_states(
    receipts: list[dict[str, Any]],
    *,
    candidate: str,
    candidate_commit: str,
    runner_digest: str,
    records: dict[str, dict[str, Any]],
    test_identity_prefix: str,
    campaign_document: dict[str, Any] | None = None,
) -> dict[str, str]:
    """CARD fixture -> state from the same-epoch AF07 campaign, receipts first.

    PASS comes only from a positive receipt that the R-4 credit rule accepts:
    this candidate, this candidate commit, this runner digest, the campaign's
    own test identity, and the requested-state and obligation digests of the
    CURRENT effective record. The campaign document's own outcome labels never
    promote anything. A FAIL is taken from the document only when the document
    is bound to the same candidate commit and runner digest, because a
    demonstrated violation must never be masked as merely unexecuted. Every
    other fixture is absent from the result, which the gate reads as
    unexecuted.
    """
    credited = positive_fixture_credit(
        receipts,
        candidate=candidate,
        expected_commit=candidate_commit,
        denominator=records,
        expected_runner_digest=runner_digest,
    )
    states = {
        fixture: "PASS"
        for fixture, tests in credited.items()
        if any(test.startswith(test_identity_prefix) for test in tests)
    }
    campaign = (campaign_document or {}).get("campaign") or {}
    bound = (
        bool(candidate_commit)
        and bool(runner_digest)
        and campaign.get("candidate") == candidate
        and campaign.get("candidate_commit") == candidate_commit
        and campaign.get("runner_digest") == runner_digest
    )
    if bound:
        for entry in (campaign_document or {}).get("rows") or ():
            fixture = str(entry.get("fixture_id") or "")
            if fixture in records and (entry.get("verdict") or {}).get("outcome") == "FAIL":
                states[fixture] = "FAIL"
    return dict(sorted(states.items()))


def af07_actual_card(
    candidate: str,
    rows: dict[str, dict[str, Any]],
    actual_card_document: dict[str, Any] | None,
    repo_root: Any | None = None,
    campaign_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    """AF07 ACTUAL_CARD_BEHAVIOR, derived from the mandatory 29-card corpus.

    Coverage is derived from the ROW STATES plus the frozen fixture->identity
    map, not from the artifact's own summary. The runner writes that summary
    before the mid-game lane executes, so its ``behaviorally_executed_count``
    under-reports; trusting a self-reported flag would be a wrong-reason PASS
    (and, in the other direction, a wrong-reason residual).

    ``campaign_states`` is the same-epoch AF07 campaign credit from
    :func:`actual_card_campaign_states`. It covers the corpus fixtures the
    107-row provider denominator excludes. A denominator row always wins for
    its own fixture (CARD_02 must pass its own denominator row), except that a
    demonstrated campaign FAIL is never masked by it.
    """
    corpus = (actual_card_document or {}).get("required_29_card_corpus") or {}
    card_states = _states(rows, lambda fixture: fixture.startswith(CARD_PREFIX))
    denominator_fixtures = set(card_states)
    campaign_credited: list[str] = []
    for fixture, state in sorted((campaign_states or {}).items()):
        if not fixture.startswith(CARD_PREFIX):
            continue
        if state == "FAIL":
            card_states[fixture] = "FAIL"
        elif fixture not in denominator_fixtures:
            card_states[fixture] = state
            if state == "PASS":
                campaign_credited.append(fixture)
    if not card_states:
        return {
            "gate": "AF07",
            "name": "ACTUAL_CARD_BEHAVIOR",
            "verdict": "UNKNOWN",
            "evidence": ["no CARD_* obligation exists in this denominator"],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "the actual-card denominator is absent, so no card behaviour is measured"
            ],
        }
    try:
        fixture_identities, frozen_corpus = actual_card_corpus(repo_root)
    except (OSError, ValueError, KeyError) as exc:
        return {
            "gate": "AF07",
            "name": "ACTUAL_CARD_BEHAVIOR",
            "verdict": "UNKNOWN",
            "evidence": [f"the frozen corpus manifests are unreadable: {exc}"],
            "blocking_rows": sorted(card_states),
            "nonblocking_limitations": [
                "without the fixture->identity map, corpus coverage cannot be derived"
            ],
        }
    failed = {fixture: state for fixture, state in card_states.items() if state in _FAIL_STATES}
    covered = {
        identity
        for fixture_id, identity in fixture_identities.items()
        if card_states.get(fixture_id) == "PASS"
    }
    missing = sorted(set(frozen_corpus) - covered)
    evidence = [
        f"{len(covered)} of {len(frozen_corpus)} frozen corpus identities have their own "
        "mandatory CARD_* row PASS in this epoch",
        (
            "no same-epoch actual-card campaign credit was supplied"
            if campaign_states is None
            else f"{len(campaign_credited)} corpus fixtures outside the provider denominator "
            "are credited from same-epoch, runner-bound campaign receipts"
            + (f" ({', '.join(campaign_credited)})" if campaign_credited else "")
        ),
        (
            "no actual-card artifact exists for this candidate"
            if actual_card_document is None
            else "the artifact's own summary reports "
            f"{corpus.get('behaviorally_executed_count')} of {corpus.get('required_count')} "
            "(written before the mid-game lane runs; the row states above are authoritative)"
        ),
    ]
    if failed:
        return {
            "gate": "AF07",
            "name": "ACTUAL_CARD_BEHAVIOR",
            "verdict": "FAIL",
            "evidence": [*evidence, f"a mandatory card row failed: {failed}"],
            "blocking_rows": sorted(failed),
            "nonblocking_limitations": [
                "a failed mandatory actual-card obligation is a demonstrated gap and requires "
                "adjudication before it can be credited"
            ],
        }
    if not missing:
        return {
            "gate": "AF07",
            "name": "ACTUAL_CARD_BEHAVIOR",
            "verdict": "PASS",
            "evidence": [
                *evidence,
                "every frozen corpus identity is covered by its own passing mandatory fixture "
                "row with a current-boundary execution",
            ],
            "blocking_rows": [],
            "nonblocking_limitations": [],
        }
    limitations = [
        "the effective 29-card actual-card corpus is not fully executed on this boundary; "
        "import/construction is not behaviour proof",
        f"{len(missing)} corpus identities are unexecuted: "
        + ", ".join(missing[:10])
        + ("" if len(missing) <= 10 else f" and {len(missing) - 10} more"),
    ]
    return {
        "gate": "AF07",
        "name": "ACTUAL_CARD_BEHAVIOR",
        "verdict": "UNKNOWN",
        "evidence": evidence,
        "blocking_rows": sorted(
            fixture for fixture, state in card_states.items() if state != "PASS"
        ),
        "nonblocking_limitations": limitations,
    }


def af08_multiplayer(
    candidate: str,
    rows: dict[str, dict[str, Any]],
    cardinality_document: dict[str, Any] | None,
) -> dict[str, Any]:
    """AF08 MULTIPLAYER_COMMANDER, from the WS05 rows and the cardinality run."""
    ws05 = _states(rows, lambda fixture: fixture.startswith(WS05_PREFIX))
    if not ws05:
        return {
            "gate": "AF08",
            "name": "MULTIPLAYER_COMMANDER",
            "verdict": "UNKNOWN",
            "evidence": ["no WS05 multiplayer obligation exists in this denominator"],
            "blocking_rows": [],
            "nonblocking_limitations": [
                "the multiplayer/Commander denominator is absent, so no multiplayer obligation "
                "is measured"
            ],
        }
    failed = {fixture: state for fixture, state in ws05.items() if state in _FAIL_STATES}
    assessment = (
        cardinality_verdict((cardinality_document or {}).get("results") or {})
        if cardinality_document is not None
        else {
            "verdict": "UNKNOWN",
            "reason": "no cardinality artifact exists for this candidate",
            "complete_counts": [],
            "incomplete_counts": [],
        }
    )
    evidence = [
        f"{sum(1 for state in ws05.values() if state == 'PASS')} of {len(ws05)} WS05 "
        "multiplayer/Commander obligations PASS",
        f"cardinality lifecycle: {assessment['verdict']} ({assessment['reason']})",
    ]
    if failed:
        return {
            "gate": "AF08",
            "name": "MULTIPLAYER_COMMANDER",
            "verdict": "FAIL",
            "evidence": [*evidence, f"a multiplayer obligation failed: {failed}"],
            "blocking_rows": sorted(failed),
            "nonblocking_limitations": ["a failed multiplayer obligation requires adjudication"],
        }
    residuals = _residual_lines(ws05)
    limitations: list[str] = []
    if residuals:
        limitations.append(
            f"{len(residuals)} WS05 obligations are not PASS: "
            + ", ".join(residuals[:15])
            + ("" if len(residuals) <= 15 else f" and {len(residuals) - 15} more")
        )
    if assessment["verdict"] != "PASS":
        limitations.append(
            "the required 2P/3P/4P/5P lifecycles are not all complete: "
            f"complete={assessment.get('complete_counts')} "
            f"incomplete={assessment.get('incomplete_counts')}"
        )
    verdict = "PASS" if not residuals and assessment["verdict"] == "PASS" else "UNKNOWN"
    return {
        "gate": "AF08",
        "name": "MULTIPLAYER_COMMANDER",
        "verdict": verdict,
        "evidence": evidence,
        "blocking_rows": sorted(fixture for fixture, state in ws05.items() if state != "PASS"),
        "nonblocking_limitations": limitations,
    }


def af09_rng_replay(
    candidate: str,
    rows: dict[str, dict[str, Any]],
    replay_document: dict[str, Any] | None,
    *,
    described: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """AF09 RNG_REPLAY, derived from the replay artifact and the replay rows.

    ``described`` is the assembler's established description of the recorded
    replay/RNG artifact (refusal wording, seed-binding wording). Its evidence
    and limitations are carried into the derived gate so there is exactly one
    place that words those distinctions.
    """
    replay_states = _states(rows, lambda fixture: fixture.startswith(REPLAY_PREFIXES))
    failed = {fixture: state for fixture, state in replay_states.items() if state in _FAIL_STATES}
    residuals = _residual_lines(replay_states)
    binding = (replay_document or {}).get("rules_rng_binding") or {}
    replay = (replay_document or {}).get("semantic_replay") or {}
    errors = replay.get("error") or []
    evidence = [
        "seed binding: "
        f"{binding.get('classification', 'UNKNOWN')} "
        f"(requested={binding.get('requested_seed')}, "
        f"acknowledged={binding.get('acknowledged_seed')}); acknowledgement is a precondition "
        "for RNG control, never a demonstrated Rules RNG tape",
        (
            "no replay export outcome was recorded"
            if replay_document is None
            else (
                "replay export was refused by the engine (codes: "
                + ", ".join(
                    sorted(
                        {
                            str(item.get("code", "unknown"))
                            for item in errors
                            if isinstance(item, dict)
                        }
                    )
                )
                + ")"
                if errors
                else "replay export returned a payload; payload presence is recorded, not "
                "replay proof"
            )
        ),
    ]
    if described:
        evidence = [*evidence, *[str(item) for item in described.get("evidence") or ()]]
    limitations: list[str] = [str(item) for item in (described or {}).get("limitations") or ()]
    if failed:
        return {
            "gate": "AF09",
            "name": "RNG_REPLAY",
            "verdict": "FAIL",
            "evidence": [*evidence, f"a replay/RNG obligation failed: {failed}"],
            "blocking_rows": sorted(failed),
            "nonblocking_limitations": [
                *limitations,
                "a failed replay obligation requires adjudication",
            ],
        }
    if errors:
        limitations.append(
            "a fail-closed export refusal is an absent capability, never a satisfied obligation "
            "and never a replay PASS"
        )
    # Current-boundary replay PASS requires a clean-process twin bound to the
    # candidate, fixture, externally supplied decisions, Rules RNG, semantic
    # events, checkpoint hashes and terminal outcome. A bare {"verified": true}
    # is a self-report, not that evidence: every named element must be present
    # and non-empty, or the twin is unproven.
    twin = (replay_document or {}).get("clean_process_twin")
    twin_requirements = (
        "fixture_identity",
        "process_identity",
        "decisions",
        "rules_rng",
        "semantic_events",
        "checkpoint_state_hashes",
        "terminal_outcome",
    )
    twin_missing: list[str] = []
    if not isinstance(twin, dict):
        twin_missing = list(twin_requirements)
    else:
        if twin.get("verified") is not True:
            twin_missing.append("verified")
        twin_missing.extend(
            key for key in twin_requirements if not twin.get(key) or twin.get(key) == []
        )
    if twin_missing:
        limitations.append(
            "the clean-process semantic replay twin is not proven for this candidate: the "
            "artifact does not carry the required twin evidence "
            f"({', '.join(twin_missing)})"
        )
    if residuals:
        limitations.append(
            f"{len(residuals)} replay/RNG obligations are not PASS: " + ", ".join(residuals)
        )
    verdict = "PASS" if not limitations else "UNKNOWN"
    return {
        "gate": "AF09",
        "name": "RNG_REPLAY",
        "verdict": verdict,
        "evidence": evidence,
        "blocking_rows": sorted(
            fixture for fixture, state in replay_states.items() if state != "PASS"
        ),
        "nonblocking_limitations": limitations,
    }
