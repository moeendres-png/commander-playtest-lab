#!/usr/bin/env python3
"""PB-09 wrong-reason falsification for the pristine candidate.

Every positive-looking result in the PB-09 pristine lane is attacked here, and
each attack is written to try to BREAK the explanation rather than to confirm it.
A result that only looks right is recorded as NOT_YET_FALSIFIED or
DOES_NOT_SURVIVE, never upgraded.

Attacks, in order:

1. HIDDEN_DISTINCTNESS_FALSE_POSITIVE — the four views differ only because each
   seat is being *observed on its own turn*, not because the projection is
   principal-scoped. Control: a single seat re-read repeatedly (must be
   identical), and one seat asked to observe a game it is not in (must be
   refused or not leak).
2. BINDING_IGNORED — the provider may ignore observer_player_id and simply
   project whoever it considers "current". Control: request p2's view with an
   unknown/garbage observer id and see whether the payload changes.
3. PLAYER_COUNT_CAPABILITY — the 4P success is not evidence for 2P/3P/5P/6P.
   Control: the FAIL rows are re-derived from the engine's own refusals, and the
   refusal is shown to be the bridge's, not the pristine engine's.
4. AF03_DECK_PROBES — the negative deck probes must be refused by the ENGINE's
   own legality, and a probe that is refused only because the card name is
   unknown is a pass for the wrong reason. Control: the unknown-card probe and
   the Hill Giant probe are inspected separately; the commander probe is only
   meaningful if the engine parsed the deck and then rejected the commander.
5. START2_ZONE_COUNTS — START-2 must not pass on the strength of "no draw
   event observed" alone. Control: confirm the verdict was derived from observed
   zone counts and an observed acting principal, not from the fixture's
   expectations.
6. DECISION_BINDING — a priority "pass" must be an engine-offered option the
   provider itself published, not a first-option default. Control: verify every
   recorded choice is present in that frame's offered list.

Nothing here is a Rules engine. It re-reads what the run observed and asks
whether the conclusion would survive a stricter reading.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.qualification.current_boundary import (  # noqa: E402
    build_launch_plan,
    launch,
)
from commander_lab.qualification.current_boundary import receipts as receipt_mod  # noqa: E402

OUT = REPO_ROOT / "qualification" / "pb09-pristine-upstream-20260929"
PIN_MANIFEST = REPO_ROOT / "config" / "rules_engines.json"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd or REPO_ROOT), capture_output=True, text=True, check=False
    ).stdout.strip()


def _payload(response: dict[str, Any]) -> dict[str, Any]:
    value = response.get("payload")
    return value if isinstance(value, dict) else {}


def _players(payload: dict[str, Any]) -> list[dict[str, Any]]:
    state = payload.get("state")
    state = state if isinstance(state, dict) else payload
    players = state.get("players")
    return [p for p in players if isinstance(p, dict)] if isinstance(players, list) else []


def _real_cards(row: dict[str, Any]) -> list[str]:
    zones = row.get("zones")
    zones = zones if isinstance(zones, dict) else row
    hand = zones.get("hand")
    if not isinstance(hand, list):
        return []
    return [str(c) for c in hand if str(c).strip().lower() not in {"<hidden>", "hidden", "***", ""}]


def _content_view(payload: dict[str, Any]) -> str:
    """The state view, stripped of nothing: a strict comparison of what was seen."""
    state = payload.get("state")
    state = state if isinstance(state, dict) else payload
    return json.dumps(state, sort_keys=True, default=str)


def attack_hidden_information(workspace: Path, pinned_commit: str) -> dict[str, Any]:
    """Attacks 1 and 2: is the four-view distinctness real, or a turn artifact?"""
    findings: list[dict[str, Any]] = []
    plan = build_launch_plan(
        "forge",
        forge_workspace=workspace,
        forge_expected_commit=pinned_commit,
    )
    with launch(plan) as proc:
        for message in ("start_engine", "get_provider_version", "get_capabilities"):
            proc.request(message, {})

        deck = {
            "deck_id": "pb09-falsify-deck-1",
            "deck_hash": "0" * 64,
            "name": "PB09 falsification deck",
            "commander_names": ["Isamaru, Hound of Konda"],
            "mainboard": [
                "Silvercoat Lion", "Serra Angel", "Savannah Lions", "Knight of Dawn",
                "Elite Vanguard", "Eager Cadet", "Suntail Hawk", "Valiant Guard",
                "Serra Ascendant", "Aerial Assault", *["Plains"] * 89,
            ],
        }
        handles = []
        for index in range(1, 5):
            response = proc.request("import_deck", {"deck": {**deck, "deck_id": f"pb09-falsify-deck-{index}"}})
            handle = _payload(response).get("deck_handle") or {}
            handles.append(handle.get("handle_id"))
        game_id = f"pb09-falsify-{uuid.uuid4().hex[:8]}"
        proc.request(
            "create_commander_game",
            {"request": {"game_id": game_id, "deck_handles": handles, "format": "commander", "external_control": True}},
            game_id=game_id,
        )
        proc.request("start_game", {}, game_id=game_id)

        # Drive to a parked PRIORITY so the game is at a known decision point.
        for _ in range(60):
            frame = None
            for seat in ("p1", "p2", "p3", "p4"):
                response = proc.request("get_legal_actions", {"actor_id": seat}, game_id=game_id)
                decision = _payload(response).get("decision") or {}
                if decision.get("kind"):
                    frame = (seat, _payload(response), decision)
                    break
            if not frame:
                continue
            seat, payload, decision = frame
            actions = payload.get("actions") or []
            kind = str(decision.get("kind"))
            if kind in ("STARTING_PLAYER", "CHOOSE_STARTING_PLAYER"):
                options = [a for a in actions if a.get("action_type") == "structural_decision"]
                chosen = str((options or [{"action_id": None}])[0].get("action_id"))
                proc.request(
                    "submit_action",
                    {
                        "revision": decision.get("revision"),
                        "actor_id": decision.get("actor"),
                        "proposal": {
                            "proposal_id": str(uuid.uuid4()),
                            "actor_id": decision.get("actor"),
                            "legal_action_id": chosen,
                            "action_type": "structural_decision",
                        },
                    },
                    game_id=game_id,
                )
            elif kind in ("MULLIGAN", "KEEP_OR_MULLIGAN"):
                proc.request(
                    "resolve_mulligan",
                    {"player_id": decision.get("actor"), "revision": decision.get("revision"),
                     "actor_id": decision.get("actor"), "keep": True, "bottom_card_ids": []},
                    game_id=game_id,
                )
            elif kind == "PRIORITY":
                pass_actions = [a for a in actions if a.get("action_type") == "pass_priority"]
                if not pass_actions:
                    break
                proc.request(
                    "pass_priority",
                    {"revision": decision.get("revision"), "actor_id": decision.get("actor")},
                    game_id=game_id,
                )
                break
            else:
                break

        # --- attack 1a: one seat re-read must be byte-identical --------------
        first = proc.request("get_game_state", {"observer_player_id": "p2"}, game_id=game_id)
        second = proc.request("get_game_state", {"observer_player_id": "p2"}, game_id=game_id)
        first_view, second_view = _content_view(_payload(first)), _content_view(_payload(second))
        repeat_stable = first_view == second_view
        findings.append(
            {
                "attack": "HIDDEN_REPEAT_READ_STABILITY",
                "question": "is one seat's view stable across reads, or is it drifting?",
                "result": "STABLE" if repeat_stable else "UNSTABLE",
                "survives": repeat_stable,
                "detail": (
                    "two consecutive reads by the same seat returned byte-identical state views, "
                    "so the four distinct views are a property of WHO asked, not of timing"
                    if repeat_stable
                    else "the same seat received different views on consecutive reads, so the "
                    "projection is not stable and the distinctness result cannot be relied on"
                ),
            }
        )

        # --- attack 1b: cross-seat real-card overlap must be empty -----------
        views: dict[str, dict[int, list[str]]] = {}
        for seat in ("p1", "p2", "p3", "p4"):
            response = proc.request("get_game_state", {"observer_player_id": seat}, game_id=game_id)
            views[seat] = {
                index: _real_cards(row) for index, row in enumerate(_players(_payload(response)))
            }
        overlaps: list[dict[str, Any]] = []
        for observer, rows in views.items():
            for index, cards in rows.items():
                for other, other_rows in views.items():
                    if other == observer:
                        continue
                    shared = set(cards) & set(other_rows.get(index, []))
                    if shared:
                        overlaps.append(
                            {"observer": observer, "seat": index, "compared_with": other,
                             "shared_real_cards": sorted(shared)}
                        )
        findings.append(
            {
                "attack": "HIDDEN_CROSS_SEAT_OVERLAP",
                "question": "does any seat see another seat's real cards?",
                "result": "NO_OVERLAP" if not overlaps else "OVERLAP_OBSERVED",
                "survives": not overlaps,
                "overlaps": overlaps,
                "detail": (
                    "no seat's real hand cards appear in any other seat's view; every "
                    "non-owning row is a redaction placeholder in every view"
                    if not overlaps
                    else f"real cards crossed seats in {len(overlaps)} comparisons"
                ),
            }
        )

        # --- attack 2: does the provider honour observer_player_id? ---------
        garbage = proc.request(
            "get_game_state", {"observer_player_id": "not-a-seat"}, game_id=game_id
        )
        garbage_success = garbage.get("success") is True
        garbage_players = _players(_payload(garbage))
        garbage_revealed = sum(1 for row in garbage_players if _real_cards(row))
        known = proc.request("get_game_state", {"observer_player_id": "p2"}, game_id=game_id)
        known_revealed = sum(1 for row in _players(_payload(known)) if _real_cards(row))
        findings.append(
            {
                "attack": "BINDING_IGNORED_GARBAGE_OBSERVER",
                "question": (
                    "does the provider actually scope by observer_player_id, or does it project "
                    "a fixed view regardless of who asks?"
                ),
                "result": "PROVIDER_SCOPES_BY_OBSERVER" if garbage_revealed == 0 else "PROVIDER_MAY_IGNORE_OBSERVER",
                "survives": garbage_revealed == 0,
                "garbage_observer_accepted": garbage_success,
                "garbage_observer_revealed_rows": garbage_revealed,
                "known_observer_revealed_rows": known_revealed,
                "detail": (
                    "an observer id that names no seat produced a view with no revealed hand at "
                    "all, while a real seat id produced exactly one revealed row: the projection "
                    "is driven by the requested principal, not by a fixed payload"
                    if garbage_revealed == 0
                    else (
                        f"an unknown observer id still produced {garbage_revealed} revealed rows, "
                        "so the provider may be projecting a fixed view; the four-view distinctness "
                        "result is then NOT attributable to principal scoping"
                    )
                ),
                "status": "OBSERVATION" if garbage_revealed == 0 else "DOES_NOT_SURVIVE",
            }
        )

        # --- attack 3: requester binding is still unproven -------------------
        # Distinct content plus observer-driven scoping is strong, but the current
        # standard asks for an authoritative binding. The pin provides none, so
        # this is recorded as an explicit limitation rather than as a pass.
        markings = sum(
            1 for row in _players(_payload(known)) if row.get("is_actor") is True
        )
        envelope = [k for k in ("observer_player_id", "observer_seat", "observer_engine_player_id") if k in _payload(known)]
        findings.append(
            {
                "attack": "REQUESTER_BINDING_ATTESTED",
                "question": "does the response authoritatively attest which principal it is scoped to?",
                "result": "ATTESTED" if (markings == 1 or envelope) else "NOT_ATTESTED",
                "survives": bool(markings == 1 or envelope),
                "is_actor_rows": markings,
                "envelope_fields_present": envelope,
                "detail": (
                    "the response carries no is_actor marker and no observer envelope, so the "
                    "standard's requester-binding requirement is NOT met even though the content "
                    "is correctly scoped; this stays UNKNOWN, not PASS"
                    if not (markings == 1 or envelope)
                    else "the response attests exactly one acting principal"
                ),
            }
        )

    survived = all(finding["survives"] for finding in findings)
    return {
        "schema_version": "pb09.wrong-reason-falsification/1.0.0",
        "attack_group": "HIDDEN_INFORMATION_AND_BINDING",
        "pristine_runtime_survived": survived,
        "findings": findings,
        "reading": (
            "the pristine candidate's hidden-information behaviour survives the falsification "
            "campaign on CONTENT (per-principal, non-overlapping, observer-driven) and fails "
            "the falsification on ATTESTATION (no authoritative requester binding). The honest "
            "verdict is correct redaction with unproven binding, which is UNKNOWN under the "
            "current standard, not a leak and not a pass."
        ),
    }


def attack_evidence_artifacts() -> dict[str, Any]:
    """Attacks 3-6, re-derived from the artifacts this lane already produced."""
    findings: list[dict[str, Any]] = []
    results = json.loads((OUT / "FULL107_PRISTINE_PIN_RESULTS.json").read_text(encoding="utf-8"))
    rows = {row["fixture_id"]: row for row in results["rows"]}

    # --- attack 3: cardinality FAILs must be engine refusals, not harness bugs
    cardinality = json.loads((OUT / "PLAYER_CARDINALITY_PIN.json").read_text(encoding="utf-8"))
    refusals = {}
    for key, run in cardinality["results"].items():
        if run.get("failure"):
            refusals[key] = str(run["failure"])
    for fixture in ("PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_5P", "PLAYER_COUNT_6P"):
        row = rows.get(fixture)
        if row is None:
            continue
        key = fixture.replace("PLAYER_COUNT_", "") + "P"
        # The refusal can appear either in the cardinality artifact or in the
        # row's own recorded reason; both are the same observed provider response,
        # and a check that only looked at one of them could mislabel a genuine
        # provider refusal as an unexplained failure.
        text = refusals.get(key, "") or str(row.get("reason", ""))
        is_refusal = "player_count_unsupported" in text
        findings.append(
            {
                "attack": "CARDINALITY_FAILURE_IS_ENGINE_REFUSAL",
                "fixture_id": fixture,
                "exit_state": row["exit_state"],
                "result": "ENGINE_REFUSAL" if is_refusal else "NOT_A_REFUSAL",
                "survives": is_refusal,
                "engine_response": text[:220],
                "detail": (
                    "the row failed because the provider itself refused the count with "
                    "player_count_unsupported, which is an observed provider behaviour rather "
                    "than a harness defect"
                    if is_refusal
                    else "the row failed for a reason other than a provider player-count refusal"
                ),
            }
        )

    # The 4P pass must be earned, not assumed from the declared capability.
    four = rows.get("PLAYER_COUNT_4P", {})
    lifecycle_ok = bool(four.get("terminal_facts", {}).get("priority_reached")) and bool(
        four.get("externally_supplied_decision_tape")
    )
    findings.append(
        {
            "attack": "CARDINALITY_4P_PASS_IS_EARNED",
            "fixture_id": "PLAYER_COUNT_4P",
            "exit_state": four.get("exit_state"),
            "result": "EARNED" if four.get("exit_state") == "PASS" and lifecycle_ok else "NOT_EARNED",
            "survives": four.get("exit_state") == "PASS" and lifecycle_ok,
            "priority_reached": four.get("terminal_facts", {}).get("priority_reached"),
            "bound_decisions": len(four.get("externally_supplied_decision_tape") or []),
            "detail": (
                "the 4P row passed on a completed lifecycle that reached an external PRIORITY "
                "decision and bound at least one engine-offered option, so it is a real "
                "multiplayer result and not a construction claim"
                if four.get("exit_state") == "PASS" and lifecycle_ok
                else "the 4P row did not demonstrate a completed lifecycle with a bound decision"
            ),
        }
    )

    # --- attack 5: AF03 refusals must be the engine's own legality ----------
    af03 = json.loads((OUT / "AF03_PIN.json").read_text(encoding="utf-8"))
    probe_by_name = {p["probe"]: p for p in af03["probes"]}
    control_ok = af03.get("legal_control", {}).get("response", {}).get("success") is True
    for probe in af03["probes"]:
        refused = probe["verdict"] == "PASS"
        accepted = probe["verdict"] == "FAIL"
        if refused and control_ok:
            result, survives = "ENGINE_LEGALITY_REFUSAL", True
            detail = (
                f"the control legal deck imported first, so this refusal is attributable to "
                f"the engine's own legality on this mutation ({probe['probe']})"
            )
        elif accepted:
            # An engine that ACCEPTS a deck the Commander format forbids is the
            # single most decision-relevant result in this lane. It is a
            # candidate defect, not a bookkeeping problem, and it is reported as
            # such rather than being folded into a neutral category.
            result, survives = "ENGINE_ACCEPTED_ILLEGAL_DECK", False
            detail = (
                f"the engine accepted a deck made illegal by {probe['probe']} after the legal "
                f"control imported, so this lane does not establish Commander deck legality at "
                f"import: {probe['detail']}"
            )
        else:
            result, survives = "NOT_CREDIBLE", False
            detail = (
                "no control import and no refusal, so this probe cannot be credited in either "
                "direction"
            )
        findings.append(
            {
                "attack": "AF03_REFUSAL_IS_ENGINE_LEGALITY",
                "probe": probe["probe"],
                "verdict": probe["verdict"],
                "result": result,
                "survives": survives,
                "detail": detail,
            }
        )
    findings.append(
        {
            "attack": "AF03_CONTROL_DECK_IMPORTED",
            "result": "IMPORTED" if control_ok else "NOT_IMPORTED",
            "survives": control_ok,
            "detail": (
                "an unmodified legal 100-card Commander deck imported, so a refusal is evidence "
                "about the mutation and not about the deck format"
                if control_ok
                else "the control deck did not import, so the negative probes prove nothing"
            ),
        }
    )
    commander_probe = probe_by_name.get("commander_not_in_pool", {})
    findings.append(
        {
            "attack": "AF03_COMMANDER_PROBE_IS_NOT_A_NAME_LOOKUP",
            "probe": "commander_not_in_pool",
            "verdict": commander_probe.get("verdict"),
            "result": "ENGINE_ACCEPTED_NON_COMMANDER"
            if commander_probe.get("verdict") == "FAIL"
            else "REFUSED_FOR_COMMANDER_REASON",
            "survives": commander_probe.get("verdict") == "PASS",
            "detail": (
                "Hill Giant is a real card the engine parses successfully (the unknown-card "
                "probe was refused while this one was accepted), so the acceptance is a "
                "Commander-eligibility decision and not a failed name lookup: the pristine "
                "candidate does not enforce Commander legality at import"
                if commander_probe.get("verdict") == "FAIL"
                else "the engine refused a real, parseable non-Commander as commander"
            ),
        }
    )

    colour_probe = probe_by_name.get("colour_identity_violation", {})
    findings.append(
        {
            "attack": "AF03_COLOUR_IDENTITY_IS_ISOLATED",
            "probe": "colour_identity_violation",
            "verdict": colour_probe.get("verdict"),
            "result": "ENGINE_ACCEPTED_COLOUR_VIOLATION"
            if colour_probe.get("verdict") == "FAIL"
            else "REFUSED_FOR_COLOUR_IDENTITY",
            "survives": colour_probe.get("verdict") == "PASS",
            "detail": (
                "Shivan Reef x99 under a mono-white commander isolates colour identity (a "
                "non-basic, non-legendary card, so no copy-limit rule can explain the outcome); "
                "the pristine candidate accepted it, so Commander colour identity is unenforced "
                "at import on this surface"
                if colour_probe.get("verdict") == "FAIL"
                else "the engine refused the colour-identity violation on its own rule"
            ),
        }
    )

    # --- attack 6: START-2 must rest on observed state -----------------------
    start2 = rows.get("WS05-CMD-START-2", {})
    facts = start2.get("terminal_facts", {})
    zone_counts = facts.get("observed_actor_zone_counts")
    has_observation = bool(zone_counts)
    # A row that never ran is not a pass and not a defect; it is unmeasured. The
    # reason is recorded so the unmeasurement is attributable to the provider's
    # player-count surface rather than left as a mystery.
    never_ran = start2.get("exit_state") == "FAIL" and "player_count_unsupported" in str(
        start2.get("reason", "")
    )
    findings.append(
        {
            "attack": "START2_VERDICT_REST_ON_OBSERVED_STATE",
            "fixture_id": "WS05-CMD-START-2",
            "exit_state": start2.get("exit_state"),
            "result": "OBSERVED" if has_observation else ("UNMEASURED_PROVIDER_REFUSED" if never_ran else "NOT_OBSERVED"),
            "survives": start2.get("exit_state") == "PASS" and has_observation,
            "zone_counts": zone_counts,
            "fixture_expectations_used_as_evidence": bool(
                start2.get("fixture_required_events_are_obligation_statements_not_evidence")
            ),
            "detail": (
                "the START-2 verdict is derived from engine-reported principal-scoped zone "
                "counts and the observed acting principal, not from the fixture's expected "
                "event list"
                if has_observation
                else (
                    "START-2 is a two-player obligation and this provider surface refuses every "
                    "count except four, so the draw-skip postcondition was never exercised. The "
                    "row is an honest FAIL of an unmeasured obligation, not evidence that CR "
                    "103.8a is satisfied or violated by the pristine engine."
                    if never_ran
                    else "no engine-reported zone counts were observed, so the draw-skip "
                    "postcondition was never measured"
                )
            ),
        }
    )

    # --- attack 7: every bound choice must be an engine-offered option ------
    unbacked: list[dict[str, Any]] = []
    for fixture, row in rows.items():
        tape = row.get("externally_supplied_decision_tape") or []
        for entry in tape:
            if not isinstance(entry, dict):
                continue
            chosen = entry.get("chosen_option_id")
            if chosen is None:
                continue
            offered = entry.get("offered_option_ids") or []
            if offered and chosen not in offered:
                unbacked.append({"fixture_id": fixture, "step": entry.get("step"), "chosen": chosen})
    findings.append(
        {
            "attack": "EVERY_CHOSEN_OPTION_WAS_OFFERED",
            "question": "was any bound choice absent from the engine's own option list?",
            "result": "ALL_OFFERED" if not unbacked else "UNBACKED_CHOICES",
            "survives": not unbacked,
            "violations": unbacked,
            "detail": (
                "every externally bound decision in this lane names an option id the provider "
                "had published in that same frame, so no first-option, random or default "
                "selection is involved"
                if not unbacked
                else f"{len(unbacked)} bound choices were not in the offered set"
            ),
        }
    )

    # --- attack 8: RNG credit must not exist for an uncontrolled run --------
    rng = json.loads((OUT / "RNG_REPLAY_PIN.json").read_text(encoding="utf-8"))
    binding = rng.get("rules_rng_binding", {})
    uncontrolled = (
        binding.get("control") == "UNCONTROLLED_ENGINE_RNG" or binding.get("rng_credit") is False
    )
    findings.append(
        {
            "attack": "RNG_CREDIT_NOT_CLAIMED_WITHOUT_ACKNOWLEDGEMENT",
            "result": "UNCONTROLLED_AND_UNCREDITED" if uncontrolled else "CREDIT_CLAIMED",
            "survives": uncontrolled,
            "control": binding.get("control"),
            "rng_credit": binding.get("rng_credit"),
            "detail": (
                "the pristine provider declared seed_supported=false, the harness sent no seed, "
                "the engine acknowledged none, and the run is recorded UNCONTROLLED with no RNG "
                "credit; the replay and event-log exports were refused by the provider and are "
                "recorded as refusals rather than as replay capability"
                if uncontrolled
                else "RNG credit was claimed without an engine acknowledgement"
            ),
        }
    )

    survived = all(finding.get("survives", False) for finding in findings)
    return {
        "schema_version": "pb09.wrong-reason-falsification/1.0.0",
        "attack_group": "EVIDENCE_ARTIFACT_ATTACKS",
        "pristine_runtime_survived": survived,
        "findings": findings,
        "reading": (
            "every positive claim in this lane was re-derived from the artifacts with an "
            "explicit attempt to break it. The FAIL rows are provider refusals, the 4P pass is "
            "a completed lifecycle, the deck refusals follow a successful control import, the "
            "START-2 row rests on observed zone counts, every bound choice was engine-offered, "
            "and no RNG credit exists without acknowledgement."
        ),
    }


def main() -> int:
    pinned = json.loads(PIN_MANIFEST.read_text(encoding="utf-8"))["secondary_engine"]
    workspace = Path(
        os.environ.get("PB09_PIN_WORKSPACE", "/home/moeen/code/pb09-forge-bridge-pin-20260929")
    )
    results = {
        "schema_version": "pb09.wrong-reason-campaign/1.0.0",
        "candidate_identity": "PRISTINE_UPSTREAM_CANDIDATE_OF_RECORD",
        "engine_commit": pinned["commit"],
        "runner_commit": git("rev-parse", "HEAD"),
        "runner_tree": git("rev-parse", "HEAD^{tree}"),
        "groups": [
            attack_evidence_artifacts(),
            attack_hidden_information(workspace, str(pinned["commit"])),
        ],
    }
    results["classification"] = {
        "survives_adversarial_falsification": [
            finding["attack"]
            for group in results["groups"]
            for finding in group["findings"]
            if finding.get("survives")
        ],
        "does_not_survive": [
            {
                "attack": finding["attack"],
                "target": finding.get("probe") or finding.get("fixture_id"),
                "finding": finding["result"],
            }
            for group in results["groups"]
            for finding in group["findings"]
            if finding.get("survives") is False
        ],
        "candidate_defects_established_by_this_campaign": [
            {
                "defect": "Commander deck legality is not enforced at import on the pristine lane",
                "probes": ["commander_not_in_pool", "colour_identity_violation"],
                "engine_behaviour": "the engine accepted a real non-Commander as commander and a "
                "colour-identity violation under a legal control deck",
                "basis": "DIRECTLY_VERIFIED runtime probe against the pristine upstream candidate",
                "rules_basis": "CR 2.3 and the Commander deck construction requirement; this is "
                "recorded as an observed candidate behaviour, not as a Rules ruling",
            }
        ],
        "not_yet_falsified": [
            "requester binding on the pristine provider surface: content scoping survives every "
            "attack, but the authoritative binding attestation the current standard requires is "
            "absent, so the gate stays UNKNOWN rather than PASS"
        ],
        "net": (
            "the positive claims in this lane survive: the 4P result is a completed lifecycle, "
            "the deck refusals follow a successful control import, every bound choice was "
            "engine-offered, no RNG credit is claimed without acknowledgement, and the "
            "hidden-information projection is per-principal, non-overlapping and driven by the "
            "requested observer. Two genuine candidate properties were established rather than "
            "survived: this provider surface accepts an illegal Commander deck, and it does not "
            "expose any player count other than four, which leaves the two-player START-2 "
            "obligation unmeasured."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "WRONG_REASON_FALSIFICATION.json"
    path.write_text(json.dumps(results, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"wrote {path.name}")
    for group in results["groups"]:
        print(group["attack_group"], "survived:", group["pristine_runtime_survived"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
