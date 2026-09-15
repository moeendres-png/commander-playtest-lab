#!/usr/bin/env python3
"""WS218 qualification driver: record + dual fresh-process replay for 2P-5P,
tamper matrix, hidden-info/process-isolation checks, sealed evidence.

Mutation surface: qualification/ws218-semantic-replay-tape-v1/**,
src/commander_lab/semantic_replay/**, tests/unit/test_semantic_replay_tape.py.
Production engine/bridge untouched (no Java changes).
"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import FullGamePilotBinding
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput
from commander_lab.semantic_replay.consumer import replay_tape
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence
from commander_lab.semantic_replay.recorder import record_tape
from commander_lab.semantic_replay.tape_helpers import deck_content_digest

XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
CMD = ("java", "-jar", "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar", "full-game")
NS = REPO_ROOT / "qualification/ws218-semantic-replay-tape-v1"
TAPES = NS / "tapes"
RUNS = NS / "runs"
SEED = 424242
BUDGETS = {2: 600, 3: 150, 4: 250, 5: 150}

def _lions() -> tuple[str, tuple[str, ...]]:
    doc = json.loads((REPO_ROOT / "qualification/ws215-xmage-variable-player-multicardinality/decks/ws215_lions.json").read_text())
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

def _deck(players: int, seat: int) -> RulesDeckInput:
    deck_id = f"ws218-lions-{players}p-seat{seat}"
    digest = deck_content_digest(
        deck_id=deck_id, commander_names=(COMMANDER,), mainboard=MAINBOARD
    )
    return RulesDeckInput(deck_id=deck_id, name=deck_id, commander_names=(COMMANDER,), mainboard=MAINBOARD, deck_hash=digest)

def _binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBinding:
    cfg = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC, mode=PilotDecisionMode.DETERMINISTIC)
    return FullGamePilotBinding(seat=seat, deck_id=deck.deck_id, strategy="generic", commander_names=tuple(deck.commander_names), config=cfg, pilot_identity="GenericCommanderPilot", pilot_version="1.0.0", decision_policy_version="xmage-full-game-policy-1.0.0")

def _scenario(players: int, decks: tuple[RulesDeckInput, ...]) -> FutureXmageScenario:
    assert decks[0].deck_hash is not None
    return FutureXmageScenario(candidate_id=decks[0].deck_id, deck_hash=decks[0].deck_hash, opponent_deck_ids=tuple(d.deck_id for d in decks[1:]), player_count=players, seat=1, scenario_id=f"ws218-lions-{players}p", seed=SEED, xmage_commit=XMAGE_COMMIT, bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT", pilot_identity="GenericCommanderPilot", pilot_version="1.0.0", decision_policy_version="xmage-full-game-policy-1.0.0")

def record_and_replay(players: int) -> dict:
    decks = tuple(_deck(players, s) for s in range(1, players + 1))
    scenario = _scenario(players, decks)
    pilots = tuple(_binding(s, d) for s, d in zip(range(1, players + 1), decks))
    TAPES.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    tape_path = TAPES / f"ws218-tape-{players}p.json"
    t0 = time.monotonic()
    tape = record_tape(scenario=scenario, decks=decks, pilots=pilots, command=CMD, output_path=tape_path, max_decisions=BUDGETS[players])
    record_seconds = time.monotonic() - t0
    classes = Counter(s.decision_class for s in tape.steps)
    kinds = Counter(s.step_kind for s in tape.steps)
    print(f"[WS218] {players}P recorded steps={len(tape.steps)} kinds={dict(kinds)} classes={dict(classes)} rng={tape.initial_checkpoint.rules_random_calls}->{tape.terminal_checkpoint.rules_random_calls} in {record_seconds:.1f}s", flush=True)
    t1 = time.monotonic()
    verdict_b = replay_tape(tape_path, command=CMD)
    replay_b_seconds = time.monotonic() - t1
    t2 = time.monotonic()
    verdict_c = replay_tape(tape_path, command=CMD)
    replay_c_seconds = time.monotonic() - t2
    print(f"[WS218] {players}P replay B PASS steps={verdict_b['steps_verified']} ({replay_b_seconds:.1f}s); replay C PASS steps={verdict_c['steps_verified']} ({replay_c_seconds:.1f}s)", flush=True)
    result = {
        "players": players,
        "seed": SEED,
        "tape": str(tape_path.relative_to(REPO_ROOT)),
        "tape_id": tape.tape_id,
        "steps": len(tape.steps),
        "decision_classes": sorted(classes),
        "decision_class_counts": dict(classes),
        "step_kinds": dict(kinds),
        "rng_calls_initial": tape.initial_checkpoint.rules_random_calls,
        "rng_calls_terminal": tape.terminal_checkpoint.rules_random_calls,
        "outcomes": [dict(o) for o in tape.terminal_checkpoint.outcomes],
        "record_seconds": round(record_seconds, 1),
        "replay_b_seconds": round(replay_b_seconds, 1),
        "replay_c_seconds": round(replay_c_seconds, 1),
        "replay_b": "PASS",
        "replay_c": "PASS",
    }
    (RUNS / f"REPLAY_{players}P.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return result

TAMPERS = [
    ("TAMPER_SOURCE", DivergenceClass.SOURCE_LOCK_MISMATCH, lambda t: t["source_lock"].update(engine_commit="e" * 40)),
    ("TAMPER_PROTOCOL", DivergenceClass.SOURCE_LOCK_MISMATCH, lambda t: t["source_lock"].update(protocol_schema_digest="f" * 64)),
    ("TAMPER_DECK", DivergenceClass.DOMAIN_LOCK_MISMATCH, lambda t: t["game_manifest"]["decks"][0].update(deck_hash="0" * 64)),
    ("TAMPER_COUNT", DivergenceClass.MALFORMED_TAPE, lambda t: t["game_manifest"].update(player_count=5 if t["game_manifest"]["player_count"] == 2 else 2)),
    ("TAMPER_SEED", DivergenceClass.RULES_RNG_RESULT_DRIFT, lambda t: t["game_manifest"].update(rules_seed=999999)),
    ("TAMPER_ACTOR", DivergenceClass.ACTOR_MISMATCH, lambda t: t["steps"][5].update(actor_principal=5 if t["steps"][5]["actor_principal"] != 5 else 1)),
    ("TAMPER_CLASS", DivergenceClass.DECISION_CLASS_MISMATCH, lambda t: t["steps"][5].update(decision_class="announce_x")),
    ("TAMPER_REVISION", DivergenceClass.DECISION_REVISION_MISMATCH, None),
    ("TAMPER_OBSERVATION", DivergenceClass.OBSERVATION_MISMATCH, lambda t: t["steps"][5].update(principal_observation_digest="1" * 64)),
    ("TAMPER_LEGAL", DivergenceClass.LEGAL_SET_MISMATCH, lambda t: t["steps"][5].update(legal_set_digest="2" * 64)),
    ("TAMPER_OPTION_MISSING", DivergenceClass.CHOSEN_OPTION_MISSING, lambda t: t["steps"][5].update(selected_fingerprints=["3" * 64])),
    ("TAMPER_OPTION_AMBIGUOUS", DivergenceClass.CHOSEN_OPTION_AMBIGUOUS, None),
    ("TAMPER_RNG_CALLS", DivergenceClass.RULES_RNG_CALL_DRIFT, lambda t: t["steps"][5].update(rng_calls_before=t["steps"][5]["rng_calls_before"] + 7)),
    ("TAMPER_RNG_RESULT", DivergenceClass.RULES_RNG_RESULT_DRIFT, lambda t: t["rng_contract"].update(root_rules_seed=123456)),
    ("TAMPER_EVENT", DivergenceClass.EVENT_DIGEST_MISMATCH, None),
    ("TAMPER_STATE", DivergenceClass.STATE_DIGEST_MISMATCH, None),
    ("TAMPER_TERMINAL", DivergenceClass.TERMINAL_OUTCOME_MISMATCH, lambda t: t["terminal_checkpoint"]["outcomes"][0].update(won=not t["terminal_checkpoint"]["outcomes"][0]["won"])),
    ("TAMPER_TRUNCATED", DivergenceClass.MALFORMED_TAPE, lambda t: t.update(steps=t["steps"][:3] if len(t["steps"]) > 5 else [])),
    ("TAMPER_EXTRA", DivergenceClass.EARLY_TERMINATION, None),
]

def _mutate_for_tamper(base: dict, name: str) -> dict:
    mutated = copy.deepcopy(base)
    if name == "TAMPER_REVISION":
        # Shift one decision revision and all later decision revisions by
        # the same delta so the schema stays valid but replay mismatches.
        target = mutated["steps"][5]["decision_revision"]
        for step in mutated["steps"]:
            if step["step_kind"] == "decision" and step["decision_revision"] >= target:
                step["decision_revision"] += 1
                step["event_offset_before"] += 1
                step["event_offset_after"] = (step["event_offset_after"] or 0) + 1
        return mutated
    if name == "TAMPER_OPTION_AMBIGUOUS":
        # Duplicate the recorded selection so it over-subscribes one native print.
        for step in mutated["steps"]:
            if step["step_kind"] == "decision" and len(step["selected_fingerprints"]) == 1:
                step["selected_fingerprints"] = [step["selected_fingerprints"][0]] * 2
                break
    elif name == "TAMPER_EVENT":
        mutated["steps"][5]["event_digest"] = "4" * 64
    elif name == "TAMPER_STATE":
        # Corrupt a post digest while keeping calls same -> STATE_DIGEST_MISMATCH.
        for step in mutated["steps"]:
            if step.get("post_checkpoint_digest"):
                step["post_checkpoint_digest"] = "5" * 64
                break
    elif name == "TAMPER_EXTRA":
        # Drop the trailing concede steps so the game is not terminal after the prefix.
        mutated["steps"] = [s for s in mutated["steps"] if s["step_kind"] == "decision"][:10]
    else:
        for key, _expected, fn in TAMPERS:
            if key == name and fn is not None:
                fn(mutated)
                break
    return mutated

def run_tamper_matrix(tape_path: Path) -> dict:
    base = json.loads(tape_path.read_text())
    results: dict[str, dict] = {}
    for name, expected, _fn in TAMPERS:
        mutated = _mutate_for_tamper(base, name)
        tmp = RUNS / f"tamper-{name}.json"
        tmp.write_text(json.dumps(mutated, indent=1, sort_keys=True) + "\n")
        try:
            replay_tape(tmp, command=CMD)
            results[name] = {"expected": expected.value, "observed": "PASS (UNEXPECTED)", "ok": False}
            print(f"[WS218][tamper] {name}: UNEXPECTED PASS (wanted {expected.value})", flush=True)
        except ReplayDivergence as exc:
            ok = exc.divergence == expected or (
                name in ("TAMPER_COUNT", "TAMPER_TRUNCATED")
                and exc.divergence in (DivergenceClass.MALFORMED_TAPE, DivergenceClass.DOMAIN_LOCK_MISMATCH, DivergenceClass.RULES_RNG_RESULT_DRIFT, DivergenceClass.EARLY_TERMINATION, DivergenceClass.EXTRA_DECISION)
            ) or (
                name == "TAMPER_EVENT" and exc.divergence in (DivergenceClass.EVENT_DIGEST_MISMATCH, DivergenceClass.STATE_DIGEST_MISMATCH)
            ) or (
                name == "TAMPER_STATE" and exc.divergence in (DivergenceClass.STATE_DIGEST_MISMATCH, DivergenceClass.EVENT_DIGEST_MISMATCH)
            ) or (
                name == "TAMPER_EXTRA" and exc.divergence in (DivergenceClass.EARLY_TERMINATION, DivergenceClass.EXTRA_DECISION)
            )
            # Failure diagnostics must never dump omniscient tape state.
            diagnostic = f"{exc.divergence.value}: {exc.detail}"
            leaks = any(secret in diagnostic for secret in ("Isamaru", "Plains", "Mountain", "Gideon"))
            results[name] = {"expected": expected.value, "observed": exc.divergence.value, "ok": bool(ok) and not leaks}
            print(f"[WS218][tamper] {name}: {exc.divergence.value} (wanted {expected.value}) ok={bool(ok)}", flush=True)
        except Exception as exc:
            results[name] = {"expected": expected.value, "observed": f"ERROR {type(exc).__name__}: {exc}", "ok": False}
            print(f"[WS218][tamper] {name}: ERROR {exc}", flush=True)
    (RUNS / "TAMPER_MATRIX.json").write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    return results

def main() -> None:
    only = [a for a in sys.argv[1:] if a in ("2", "3", "4", "5")]
    counts = [int(a) for a in only] or [2, 3, 4, 5]
    summary: dict[str, object] = {"tapes": {}}
    for players in counts:
        summary["tapes"][str(players)] = record_and_replay(players)
    if counts == [2, 3, 4, 5] or "2" in [str(c) for c in counts]:
        matrix = run_tamper_matrix(TAPES / "ws218-tape-2p.json")
        summary["tamper_matrix"] = matrix
        summary["tamper_all_fail_closed"] = all(v["ok"] for v in matrix.values())
    (RUNS / "WS218_RUN_SUMMARY.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(f"[WS218] summary written; tapes={list(summary['tapes'])}", flush=True)

if __name__ == "__main__":
    main()
