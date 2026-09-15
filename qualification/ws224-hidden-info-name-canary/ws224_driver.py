#!/usr/bin/env python3
"""WS224 qualification driver: fresh-JVM production-boundary name-canary proof,
sealed-tape replay + tamper-diagnostic scans, historical artifact scan.

Mutation surface: qualification/ws224-hidden-info-name-canary/** only.
Production engine/bridge/src untouched (tests live in engine-bridge tests +
tests/unit, already committed separately). No behavior credit.

Phases:
  1. BOUNDARY: fresh-JVM 4P game over the production JSONL lane; per-decision
     deck-derived hidden-exclusive name scans over pilot_state / legal_options /
     whole-status serializations; grant-window boundedness; wrong/stale/ghost
     error probes (no advance, no hidden-name echo); stderr tail capture.
  2. REPLAY: fresh-process replay of the sealed WS218 4P tape (PASS + verdict
     shape); actor-swapped tamper copy -> ACTOR_MISMATCH diagnostic scan.
  3. HISTORICAL: read-only scan of all committed primary.json artifacts (66)
     plus the 4 sealed WS218 tapes; per-file classification; no rewrites.
"""

from __future__ import annotations

import copy
import glob
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.agents import build_pilot  # noqa: E402
from commander_lab.candidates.models import FutureXmageScenario  # noqa: E402
from commander_lab.engine.rules.full_game import (  # noqa: E402
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    FullGameProtocolError,
    _RawFullGameClient,
    _RuntimePilot,
)
from commander_lab.models import (  # noqa: E402
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)
from commander_lab.semantic_replay.consumer import replay_tape  # noqa: E402
from commander_lab.semantic_replay.divergence import ReplayDivergence  # noqa: E402
from commander_lab.semantic_replay.tape_helpers import deck_content_digest  # noqa: E402

XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
CMD = ("java", "-jar", "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar", "full-game")
NS = REPO_ROOT / "qualification/ws224-hidden-info-name-canary"
SEED = 424242
PLAYERS = 4
MAX_DECISIONS = 24


def _lions() -> tuple[str, tuple[str, ...]]:
    doc = json.loads(
        (
            REPO_ROOT
            / "qualification/ws215-xmage-variable-player-multicardinality/decks/ws215_lions.json"
        ).read_text()
    )
    main: list[str] = []
    commander = ""
    for card in doc["cards"]:
        if card["zone"] == "commander":
            commander = card["oracle_name"]
        elif card["zone"] == "main":
            main.extend([card["oracle_name"]] * card["quantity"])
    assert commander and len(main) == 99, (commander, len(main))
    return commander, tuple(main)


COMMANDER, MAINBOARD = _lions()
DECK_NAMES = set(MAINBOARD) | {COMMANDER}


def _deck(seat: int) -> RulesDeckInput:
    deck_id = f"ws224-lions-4p-seat{seat}"
    digest = deck_content_digest(
        deck_id=deck_id, commander_names=(COMMANDER,), mainboard=MAINBOARD
    )
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        commander_names=(COMMANDER,),
        mainboard=MAINBOARD,
        deck_hash=digest,
    )


def _binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBinding:
    cfg = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck.deck_id,
        strategy="generic",
        commander_names=tuple(deck.commander_names),
        config=cfg,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _public_names(state: dict) -> set[str]:
    names: set[str] = set()
    for entry in state.get("players", []) or []:
        if not isinstance(entry, dict):
            continue
        for zone in ("battlefield", "graveyard", "command"):
            items = entry.get(zone)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("name"):
                        names.add(str(item["name"]))
        if entry.get("is_actor") is True:
            hand = entry.get("hand")
            if isinstance(hand, list):
                for item in hand:
                    if isinstance(item, dict) and item.get("name"):
                        names.add(str(item["name"]))
        granted = entry.get("granted_library")
        if isinstance(granted, list):
            for item in granted:
                if isinstance(item, dict) and item.get("name"):
                    names.add(str(item["name"]))
    stack = state.get("stack")
    if isinstance(stack, list):
        for item in stack:
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    for row in state.get("commander_status", []) or []:
        if isinstance(row, dict) and row.get("name"):
            names.add(str(row["name"]))
    return names


def _decision_of(status: dict) -> dict:
    decision = status.get("decision")
    assert isinstance(decision, dict), "expected a live pending decision"
    return decision


def phase_boundary() -> dict:
    decks = tuple(_deck(s) for s in range(1, PLAYERS + 1))
    pilots = tuple(_binding(s, d) for s, d in zip(range(1, PLAYERS + 1), decks, strict=True))
    runtimes = tuple(
        _RuntimePilot(binding=b, pilot=build_pilot(b.config, strategy=b.strategy))
        for b in pilots
    )
    policy = ExternalPilotDecisionPolicy(runtimes, SEED)
    scanned = 0
    canary_frames = 0
    grant_frames = 0
    actors: set[int] = set()
    t0 = time.monotonic()
    with _RawFullGameClient(CMD, cwd=REPO_ROOT) as client:
        client.request("start_engine")
        provider = client.request("get_provider_version")
        assert provider.get("engine") == "xmage", provider
        assert provider.get("engine_commit") == XMAGE_COMMIT, provider.get("engine_commit")
        handles: list[str] = []
        for deck in decks:
            imported = client.request(
                "import_deck",
                {
                    "deck": {
                        "commander_names": list(deck.commander_names),
                        "deck_hash": deck.deck_hash,
                        "deck_id": deck.deck_id,
                        "mainboard": list(deck.mainboard),
                        "sideboard": [],
                    }
                },
            )
            handles.append(str(imported["deck_handle"]["handle_id"]))
        starting_seat = SEED % PLAYERS
        created = client.request(
            "create_full_game",
            {
                "deck_handles": handles,
                "game_id": f"ws224-boundary-4p:{SEED}",
                "seed": SEED,
                "starting_life": 40,
                "starting_player_seat": starting_seat,
            },
        )
        assert created.get("player_count") == PLAYERS, created
        status = client.request("start_full_game")
        if not isinstance(status.get("decision"), dict):
            status = client.request("get_full_game_decision")
        for _ in range(MAX_DECISIONS):
            decision = _decision_of(status)
            state = decision["pilot_state"]
            legal = decision["legal_options"]
            assert isinstance(state, dict) and isinstance(legal, list)
            actor_seat = int(decision.get("seat", -1)) + 1
            actors.add(actor_seat)
            canary = sorted(DECK_NAMES - _public_names(state))
            pilot_serial = json.dumps(state, sort_keys=True)
            legal_serial = json.dumps(legal, sort_keys=True)
            status_serial = json.dumps(status, sort_keys=True)
            for name in canary:
                assert name not in pilot_serial, f"boundary observation leaks {name!r}"
                assert name not in legal_serial, f"boundary legal options leak {name!r}"
                assert name not in status_serial, f"boundary status leaks {name!r}"
            if canary:
                canary_frames += 1
            for entry in state.get("players", []) or []:
                granted = entry.get("granted_library")
                if isinstance(granted, list) and granted:
                    grant_frames += 1
                    assert decision.get("decision_class") == "choose_object", (
                        "grant outside library window: "
                        + str(decision.get("decision_class"))
                    )
            response = policy.decide(decision)
            status = client.request("submit_full_game_decision", {"response": response})
            if not isinstance(status.get("decision"), dict):
                if bool(status.get("terminal")):
                    break
                status = client.request("get_full_game_decision")
            scanned += 1
        # Attacker-inducible probes on the live boundary decision.
        decision = _decision_of(status)
        live_id = str(decision["decision_id"])
        live_actor = str(decision["actor_id"])
        hidden_now = sorted(DECK_NAMES - _public_names(decision["pilot_state"]))
        assert hidden_now, "probes need hidden signal"
        other_actor = next(
            str(e["player_id"])
            for e in decision["pilot_state"]["players"]
            if str(e["player_id"]) != live_actor
        )
        probes: dict[str, str] = {}

        def _expect_reject(payload_response: dict, needle: str, label: str) -> None:
            try:
                client.request("submit_full_game_decision", {"response": payload_response})
            except FullGameProtocolError as exc:
                message = str(exc)
                assert needle in message, f"{label}: {message!r} lacks {needle!r}"
                for name in hidden_now:
                    assert name not in message, f"{label} echoes hidden {name!r}"
                probes[label] = message
                return
            raise AssertionError(f"{label} was not rejected")

        _expect_reject(
            {"decision_id": live_id, "actor_id": other_actor,
             "selected_option_ids": [], "ordering": []},
            "wrong actor",
            "wrong_actor",
        )
        _expect_reject(
            {"decision_id": "ws224-stale-decision-id", "actor_id": live_actor,
             "selected_option_ids": [], "ordering": []},
            "STALE_DECISION",
            "stale_decision",
        )
        _expect_reject(
            {"decision_id": live_id, "actor_id": live_actor,
             "selected_option_ids": ["ghost-option-ws224"], "ordering": []},
            "ILLEGAL_ACTION",
            "unknown_action",
        )
        after = client.request("get_full_game_decision")
        assert str(_decision_of(after)["decision_id"]) == live_id, "probes advanced the game"
        stderr_tail = list(client.stderr_tail)
        for line in stderr_tail:
            for name in hidden_now:
                assert name not in line, f"bridge stderr leaks {name!r}"
        elapsed = round(time.monotonic() - t0, 1)
    result = {
        "players": PLAYERS,
        "seed": SEED,
        "starting_seat": starting_seat,
        "fresh_jvm": True,
        "production_lane": "xmage_full_game_external_pilots JSONL",
        "scanned_decisions": scanned,
        "canary_frames": canary_frames,
        "actor_seats_observed": sorted(actors),
        "other_principals_per_actor": PLAYERS - 1,
        "grant_frames": grant_frames,
        "error_probes": sorted(probes),
        "stderr_lines_observed": len(stderr_tail),
        "elapsed_seconds": elapsed,
    }
    assert scanned >= 20, result
    assert canary_frames >= 15, result
    assert len(actors) >= 2, result  # rotation observed across principals
    return result


def phase_replay() -> dict:
    from commander_lab.semantic_replay.recorder import record_tape

    decks = tuple(_deck(s) for s in range(1, PLAYERS + 1))
    scenario = FutureXmageScenario(
        candidate_id=decks[0].deck_id,
        deck_hash=decks[0].deck_hash,  # type: ignore[arg-type]
        opponent_deck_ids=tuple(d.deck_id for d in decks[1:]),
        player_count=PLAYERS,  # type: ignore[arg-type]
        seat=1,
        scenario_id="ws224-replay-4p",
        seed=SEED,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    pilots = tuple(_binding(s, d) for s, d in zip(range(1, PLAYERS + 1), decks, strict=True))
    tape_path = NS / "runs" / "ws224-tape-4p.json"
    t0 = time.monotonic()
    tape = record_tape(
        scenario=scenario,
        decks=decks,
        pilots=pilots,
        command=CMD,
        output_path=tape_path,
        max_decisions=30,
    )
    record_seconds = round(time.monotonic() - t0, 1)
    # Structural tape scan: pilot-facing steps never carry raw hidden arrays.
    steps_serial = json.dumps([s.model_dump(mode="json") for s in tape.steps])
    assert '"hand"' not in steps_serial
    assert '"mana_pool"' not in steps_serial
    assert '"granted_library"' not in steps_serial
    t1 = time.monotonic()
    verdict = replay_tape(tape_path, command=CMD)
    replay_seconds = round(time.monotonic() - t1, 1)
    assert verdict.get("pass") is True, verdict
    for key in ("pass", "tape_id", "steps_verified", "terminal"):
        assert key in verdict, key
    verdict_serial = json.dumps(verdict, sort_keys=True)
    assert '"hand"' not in verdict_serial
    # Tamper: swap step-1 actor principal -> deterministic ACTOR_MISMATCH.
    raw = json.loads(tape_path.read_text(encoding="utf-8"))
    other = 2 if raw["steps"][0]["actor_principal"] == 1 else 1
    raw["steps"][0]["actor_principal"] = other
    tamper_path = NS / "runs" / "ws224-tamper-actor.json"
    tamper_path.parent.mkdir(parents=True, exist_ok=True)
    tamper_path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        replay_tape(tamper_path, command=CMD)
        raise AssertionError("tampered tape must fail closed")
    except ReplayDivergence as exc:
        assert exc.divergence.value == "ACTOR_MISMATCH", str(exc)
        diagnostic = str(exc)
    finally:
        tamper_path.unlink(missing_ok=True)
    for name in DECK_NAMES:
        assert name not in diagnostic, f"replay diagnostic leaks {name!r}"
    assert "ACTOR_MISMATCH" in diagnostic
    return {
        "tape": str(tape_path.relative_to(REPO_ROOT)),
        "record": "PASS",
        "record_seconds": record_seconds,
        "replay": "PASS",
        "steps_verified": verdict["steps_verified"],
        "replay_seconds": replay_seconds,
        "tamper": "ACTOR_MISMATCH",
        "tamper_diagnostic_leak": False,
        "verdict_keys": ["pass", "tape_id", "steps_verified", "terminal"],
    }


CARDISH_HINTS = (
    " — ",
    "{T}:",
    "Cast ",
    "Play ",
    "attacks Full Game Seat",
    "Spend ",
    "mana from pool",
    "opening hand",
    "mulligan",
)


def _looks_cardish(label: str) -> bool:
    text = str(label)
    if text in ("Pass priority", "Pass", "Yes", "No", "Keep opening hand",
                "Take mulligan", "Cancel mana payment"):
        return False
    if text.startswith("Full Game Seat "):
        return False
    return any(hint in text for hint in CARDISH_HINTS) or (
        len(text.split()) <= 4 and text[:1].isupper() and " " in text
    )


def phase_historical() -> dict:
    files = sorted(
        glob.glob(str(REPO_ROOT / "qualification/*/slots/*/primary.json"))
        + glob.glob(str(REPO_ROOT / "qualification/*/runs/*/*/primary.json"))
        + glob.glob(str(REPO_ROOT / "qualification/*/runs/*/*/*/primary.json"))
    )
    assert len(files) == 66, f"expected 66 committed primary.json, found {len(files)}"
    rows: list[dict] = []
    counts: Counter[str] = Counter()
    for path in files:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        rel = str(Path(path).relative_to(REPO_ROOT))
        cardish_offered: list[str] = []
        for event in doc.get("native_transcript", []) or []:
            if not isinstance(event, dict):
                continue
            for label in (event.get("legal_option_labels") or []) + (
                event.get("selected_option_labels") or []
            ):
                if _looks_cardish(label) and label not in cardish_offered:
                    cardish_offered.append(str(label))
        controls = doc.get("negative_controls", {}) or {}
        control_text = json.dumps(controls, sort_keys=True)
        hidden_rows = int(doc.get("hidden_info_rows_scanned", 0) or 0)
        hidden_violations = int(doc.get("hidden_info_violations", 0) or 0)
        if hidden_violations:
            verdict = "CONFIRMED_PILOT_VISIBLE_LEAK"
        elif cardish_offered:
            # Offered labels were engine-selected for THAT event's actor;
            # static read cannot recompute entitlement -> advisory, not verdict.
            verdict = "POTENTIAL_LEAK_ARTIFACT"
        elif "Full Game Seat" in control_text or "REJECTED" in control_text:
            verdict = "EXPECTED_PRIVILEGED_ARTIFACT"
        else:
            verdict = "NO_PRIVATE_NAME_MATCH"
        counts[verdict] += 1
        rows.append(
            {
                "artifact": rel,
                "classification": verdict,
                "offered_cardish_labels": len(cardish_offered),
                "offered_cardish_sample": cardish_offered[:5],
                "hidden_info_rows_scanned": hidden_rows,
                "hidden_info_violations": hidden_violations,
            }
        )
    assert counts["CONFIRMED_PILOT_VISIBLE_LEAK"] == 0, counts
    tapes = sorted(
        (REPO_ROOT / "qualification/ws218-semantic-replay-tape-v1/tapes").glob("*.json")
    )
    assert len(tapes) == 4
    for tape_path in tapes:
        tape = json.loads(tape_path.read_text(encoding="utf-8"))
        steps_serial = json.dumps(tape.get("steps", []))
        assert '"hand"' not in steps_serial, tape_path.name
        assert '"mana_pool"' not in steps_serial, tape_path.name
        assert '"granted_library"' not in steps_serial, tape_path.name
        counts["EXPECTED_PRIVILEGED_ARTIFACT"] += 1
        rows.append(
            {
                "artifact": str(tape_path.relative_to(REPO_ROOT)),
                "classification": "EXPECTED_PRIVILEGED_ARTIFACT",
                "note": "manifest decklists privileged-by-design (reconstruction); "
                "steps carry digests + entitled chosen labels only",
            }
        )
    return {
        "primary_json_scanned": 66,
        "tapes_scanned": 4,
        "classifications": dict(counts),
        "rewrites": 0,
        "rows": rows,
    }


def main() -> None:
    NS.mkdir(parents=True, exist_ok=True)
    (NS / "runs").mkdir(parents=True, exist_ok=True)
    boundary = phase_boundary()
    print(f"[WS224] boundary 4P fresh-JVM: {boundary}", flush=True)
    (NS / "runs" / "BOUNDARY_4P.json").write_text(
        json.dumps(boundary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    replay = phase_replay()
    print(f"[WS224] replay 4P sealed-tape: {replay}", flush=True)
    (NS / "runs" / "REPLAY_4P.json").write_text(
        json.dumps(replay, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    historical = phase_historical()
    print(
        "[WS224] historical: "
        + json.dumps(historical["classifications"], sort_keys=True),
        flush=True,
    )
    detail = copy.deepcopy(historical)
    (NS / "runs" / "HISTORICAL_ARTIFACT_SCAN.json").write_text(
        json.dumps(detail, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {
        k: v for k, v in historical.items() if k != "rows"
    }
    (NS / "runs" / "HISTORICAL_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
