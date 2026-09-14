#!/usr/bin/env python3
"""WS213 qualification orchestrator: consolidated repin requalification.

Mutation surface: qualification/ws213-xmage-consolidated-requalification/**
only. Drives the WS204 generic boundary plus the WS213 concede boundary
through fresh JVMs (one per game) via Ws213Driver. No production bridge
mutation beyond the committed WS213 integration. No engine repin here (the
repin itself is the committed Lab change under test).

Runs per construction: behavior primary+twin, setup primary+twin (qualified
slots), opening-hand twin probes (D5), different-seed controls. Budgets match
WS205/WS207 precedent (500 decisions); denominators are never weakened.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

WS213_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WS213_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT / "qualification/ws205-xmage-ws90-first-wave"))
sys.path.insert(0, str(REPO_ROOT / "qualification/ws207-xmage-qualified-scenario-setup"))
sys.path.insert(0, str(WS213_ROOT))

import ws205_driver as _W205  # noqa: E402
import ws207_decks as _W207  # noqa: E402
import ws213_decks as decks  # noqa: E402

CANDIDATE_HEAD = "88026afc8d46db016422fb525fb8f76b639f6b3b"
POLICY_VERSION = "ws213-pilot-v1"

# Qualified setup constructions (WS207 verdicts consumed, never rewritten).
SETUP_QUALIFIED = {
    "RQ-C3-A03",
    "RQ-C3-C01",
    "RQ-C3-C03",
    "RQ-C3-D06",
    "RQ-C3-F01",
    "RQ-C3-H01-CLONE_FIRST",
    "RQ-C3-H01-NO_HUMILITY",
}

DIFFERENT_SEED_CONTROLS = {
    "RQ-C3-A03": 19788,
    "RQ-C3-F01": 23405,
    "RQ-C3-E02": 19108,
}


def java_classpath() -> str:
    cp = Path("/tmp/opencode/ws205-cp.txt").read_text().strip()
    return f"/tmp/opencode/ws213-driver-classes:engine-bridge/target/classes:{cp}"


def run_jvm(args: list[str], timeout_s: int = 1500) -> subprocess.CompletedProcess:
    cmd = ["java", "-cp", java_classpath(), "org.commanderlab.xmage.Ws213Driver", *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, cwd=str(REPO_ROOT)
    )


def semantic_transcript(evidence: dict) -> list[dict]:
    return _W205.semantic_transcript(evidence)


def transcript_hash(transcript: list[dict]) -> str:
    canonical = json.dumps(transcript, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_case(
    slot: str,
    subcase: str,
    decks_obj: dict,
    prefs_obj: dict,
    seed: int,
    tag: str,
    twin: bool = True,
    budget: int = decks.BUDGET,
) -> dict:
    """Run primary (+twin) fresh JVMs; return the adjudication record."""
    key = decks.seed_key(slot, subcase)
    run_dir = WS213_ROOT / "runs" / key / tag
    run_dir.mkdir(parents=True, exist_ok=True)
    decks_path = run_dir / "decks.json"
    prefs_path = run_dir / "prefs.json"
    decks_path.write_text(json.dumps(decks_obj, indent=1, sort_keys=True))
    prefs_with_meta = dict(prefs_obj)
    prefs_with_meta["_meta"] = {
        "decision_policy_version": POLICY_VERSION,
        "slot": slot,
        "subcase": subcase,
        "seed": seed,
        "tag": tag,
    }
    prefs_path.write_text(json.dumps(prefs_with_meta, indent=1, sort_keys=True))
    base_args = [
        f"--slot={slot}",
        f"--case={subcase}",
        f"--decks={decks_path}",
        f"--prefs={prefs_path}",
        f"--seed={seed}",
        f"--budget={budget}",
        f"--head={CANDIDATE_HEAD}",
        f"--setup={decks.SETUPS[slot]}",
        f"--authority-hash={decks.PACK_AUTHORITY}",
    ]
    print(f"[WS213] {key}/{tag}: primary seed={seed}", flush=True)
    primary_out = run_dir / "primary.json"
    result = run_jvm(["--mode=run", f"--out={primary_out}", *base_args])
    (run_dir / "primary.stdout.txt").write_text(result.stdout[-8000:])
    (run_dir / "primary.stderr.txt").write_text(result.stderr[-4000:])
    record: dict = {"slot": slot, "subcase": subcase, "seed": seed, "tag": tag}
    if not primary_out.exists():
        record["primary"] = {"ok": False, "rc": result.returncode}
        print(f"[WS213] {key}/{tag}: PRIMARY JVM FAILED rc={result.returncode}", flush=True)
        return record
    evidence = json.loads(primary_out.read_text())
    record["primary"] = summarize_run(evidence)
    transcript = semantic_transcript(evidence)
    thash = transcript_hash(transcript)
    record["primary"]["semantic_hash"] = thash
    if not twin:
        return record
    stream_path = run_dir / "primary.stream.json"
    stream_path.write_text(
        json.dumps({"decision_stream": evidence.get("decision_stream", [])}, indent=1)
    )
    twin_out = run_dir / "twin.json"
    print(f"[WS213] {key}/{tag}: twin seed={seed}", flush=True)
    twin_proc = run_jvm(
        ["--mode=twin", f"--out={twin_out}", f"--stream={stream_path}", *base_args]
    )
    (run_dir / "twin.stdout.txt").write_text(twin_proc.stdout[-8000:])
    (run_dir / "twin.stderr.txt").write_text(twin_proc.stderr[-4000:])
    twin_evidence = json.loads(twin_out.read_text()) if twin_out.exists() else None
    if twin_evidence is None:
        record["twin"] = {"ok": False, "rc": twin_proc.returncode}
        record["twin_match"] = False
        return record
    record["twin"] = summarize_run(twin_evidence)
    twin_hash = transcript_hash(semantic_transcript(twin_evidence))
    record["twin"]["semantic_hash"] = twin_hash
    diverged = bool(twin_evidence.get("stream_diverged", False))
    record["twin_match"] = (not diverged) and (twin_hash == thash)
    record["stream_diverged"] = diverged
    record["stream_divergence_detail"] = twin_evidence.get("stream_divergence_detail", "")
    print(
        f"[WS213] {key}/{tag}: twin match={record['twin_match']} "
        f"answered={evidence.get('decisions_answered')}/"
        f"{twin_evidence.get('decisions_answered')} "
        f"stopped={evidence.get('stopped_by')}/{twin_evidence.get('stopped_by')}",
        flush=True,
    )
    return record


def summarize_run(evidence: dict) -> dict:
    binding = evidence.get("rules_seed_binding", {})
    hidden_rows = sum(
        1 for row in evidence.get("decision_stream", []) if "hidden_info" in row
    )
    hidden_bad = sum(
        1
        for row in evidence.get("decision_stream", [])
        if isinstance(row.get("hidden_info"), dict)
        and not row["hidden_info"].get("ok", False)
    )
    return {
        "ok": True,
        "decisions_answered": evidence.get("decisions_answered"),
        "stopped_by": evidence.get("stopped_by"),
        "stop_detail": evidence.get("stop_detail", ""),
        "observed_decision_classes": evidence.get("observed_decision_classes", []),
        "observed_decision_counts": evidence.get("observed_decision_counts", {}),
        "rules_seed": binding.get("rules_seed"),
        "rules_seed_explicit": binding.get("rules_seed_explicit"),
        "seed_supported": binding.get("seed_supported"),
        "rules_random_calls": binding.get("rules_random_calls"),
        "negative_controls": evidence.get("negative_controls", {}),
        "hidden_info_rows": hidden_rows,
        "hidden_info_violations": hidden_bad,
        "concede_record": evidence.get("concede_record"),
        "multi_amount_frames": evidence.get("observed_decision_counts", {}).get(
            "multi_amount", 0
        ),
    }


def run_opening(slot: str, subcase: str, seed: int, tag: str) -> dict:
    """Fresh-JVM opening-hand probe (D5 evidence)."""
    key = decks.seed_key(slot, subcase)
    run_dir = WS213_ROOT / "runs" / key / tag
    run_dir.mkdir(parents=True, exist_ok=True)
    decks_obj = decks.build_decks(slot, subcase)
    decks_path = run_dir / "decks.json"
    decks_path.write_text(json.dumps(decks_obj, indent=1, sort_keys=True))
    out = run_dir / "opening.json"
    print(f"[WS213] {key}/{tag}: opening seed={seed}", flush=True)
    result = run_jvm(
        [
            "--mode=opening-hand",
            f"--slot={slot}",
            f"--case={subcase}",
            f"--decks={decks_path}",
            f"--seed={seed}",
            f"--out={out}",
        ]
    )
    (run_dir / "opening.stdout.txt").write_text(result.stdout[-8000:])
    (run_dir / "opening.stderr.txt").write_text(result.stderr[-4000:])
    if not out.exists():
        return {"ok": False, "rc": result.returncode}
    return {"ok": True, "evidence": json.loads(out.read_text())}


def check_setup(slot: str, subcase: str, evidence: dict) -> dict:
    """Neutral-predicate setup check against WS207 predicates (consumed)."""
    assertion = evidence.get("assertion_state", {})
    board = {
        (p.get("name"), p.get("controller_seat"))
        for p in assertion.get("battlefield", [])
        if isinstance(p, dict)
    }
    predicates = _W207.BATTLEFIELD_PREDICATES.get(slot, [])
    if slot == "RQ-C3-H01":
        predicates = [("Runeclaw Bear", 1)] if subcase else predicates
    missing = [list(p) for p in predicates if tuple(p) not in board]
    held = (evidence.get("prefs_held") or []) if isinstance(evidence, dict) else []
    return {
        "predicates": [list(p) for p in predicates],
        "missing": missing,
        "met": not missing,
    }


def main(argv: list[str]) -> int:
    only = [a.split("=", 1)[1] for a in argv if a.startswith("--only=")]
    wanted = set(only[0].split(",")) if only else None
    matrix: dict = {}
    for slot, subcase in decks.CONSTRUCTIONS:
        key = decks.seed_key(slot, subcase)
        if wanted is not None and key not in wanted and slot not in wanted:
            continue
        seed = decks.SEEDS[key]
        decks_obj = decks.build_decks(slot, subcase)
        entry: dict = {}
        # Behavior run (scenario attempt + twin determinism).
        entry["behavior"] = run_case(
            slot, subcase, decks_obj, decks.build_behavior_prefs(slot, subcase),
            seed, "behavior",
        )
        # Setup run for qualified constructions (neutral predicates + twin).
        if key in SETUP_QUALIFIED:
            setup_decks = decks.build_decks(slot, subcase)
            entry["setup"] = run_case(
                slot, subcase, setup_decks, decks.build_setup_prefs(slot, subcase),
                seed, "setup",
            )
        # D5 opening-hand twin probes (fresh processes).
        entry["opening_a"] = run_opening(slot, subcase, seed, "opening-a")
        entry["opening_b"] = run_opening(slot, subcase, seed, "opening-b")
        matrix[key] = entry
        (WS213_ROOT / "runs" / key / "record.json").write_text(
            json.dumps(entry, indent=1, sort_keys=True)
        )
    for slot, alt_seed in DIFFERENT_SEED_CONTROLS.items():
        if wanted is not None and slot not in wanted:
            continue
        subcase = ""
        decks_obj = decks.build_decks(slot, subcase)
        entry = {
            "behavior_alt_seed": run_case(
                slot, subcase, decks_obj,
                decks.build_behavior_prefs(slot, subcase), alt_seed,
                "behavior-alt-seed", twin=False,
            ),
            "opening_alt_seed": run_opening(slot, subcase, alt_seed, "opening-alt-seed"),
        }
        key = decks.seed_key(slot, subcase)
        (WS213_ROOT / "runs" / key / "control.json").write_text(
            json.dumps(entry, indent=1, sort_keys=True)
        )
        matrix[key + ":control"] = entry
    if wanted is None or "RQ-C3-E02" in wanted or "scan" in (wanted or set()):
        matrix["RQ-C3-E02:combat-scan"] = run_combat_scan()
    if wanted is None or "RQ-C3-E02" in wanted or "long-scan" in (wanted or set()):
        matrix["RQ-C3-E02:long-scan"] = run_long_scan()
    (WS213_ROOT / "runs" / "MATRIX.json").write_text(
        json.dumps(matrix, indent=1, sort_keys=True)
    )
    return 0


def run_combat_scan() -> dict:
    """Bounded E02 combat scan: fresh processes over fixed seeds with press
    attack/block-all policy and one-shot damage spoil. Twins follow only
    primaries that opened multi_amount frames."""
    slot, subcase = "RQ-C3-E02", ""
    decks_obj = decks.build_decks(slot, subcase)
    scan: dict = {}
    for seed in decks.E02_SCAN_SEEDS:
        tag = f"combat-scan-{seed}"
        record = run_case(
            slot, subcase, decks_obj,
            decks.build_combat_scan_prefs(slot, subcase), seed, tag,
            twin=False,
        )
        scan[str(seed)] = record
        primary = record.get("primary", {})
        if primary.get("ok") and primary.get("multi_amount_frames", 0) > 0:
            twin_record = run_case(
                slot, subcase, decks_obj,
                decks.build_combat_scan_prefs(slot, subcase), seed,
                tag + "-twin-follow", twin=True,
            )
            # run_case with twin=True runs its own primary+twin; keep both.
            scan[str(seed)]["twin_follow"] = twin_record
    (WS213_ROOT / "runs" / "RQ-C3-E02" / "combat-scan.json").write_text(
        json.dumps(scan, indent=1, sort_keys=True)
    )
    return scan


LONG_SCAN_SEEDS = [9108, 19108, 29108]
LONG_SCAN_BUDGET = 3000


def run_long_scan() -> dict:
    """Bounded E02 long-scan: up to 3 fresh processes x 3000 decisions (turn
    7+ reach for the 7-mana attacker) with press attack/block-all policy and
    one-shot damage spoil. Twins follow only primaries that opened
    multi_amount frames. Stops early on the first damage-frame hit."""
    slot, subcase = "RQ-C3-E02", ""
    decks_obj = decks.build_decks(slot, subcase)
    scan: dict = {}
    for seed in LONG_SCAN_SEEDS:
        tag = f"long-scan-{seed}"
        record = run_case(
            slot, subcase, decks_obj,
            decks.build_combat_scan_prefs(slot, subcase), seed, tag,
            twin=False, budget=LONG_SCAN_BUDGET,
        )
        scan[str(seed)] = record
        primary = record.get("primary", {})
        if primary.get("ok") and primary.get("multi_amount_frames", 0) > 0:
            twin_record = run_case(
                slot, subcase, decks_obj,
                decks.build_combat_scan_prefs(slot, subcase), seed,
                tag + "-twin-follow", twin=True, budget=LONG_SCAN_BUDGET,
            )
            scan[str(seed)]["twin_follow"] = twin_record
            break
    (WS213_ROOT / "runs" / "RQ-C3-E02" / "long-scan.json").write_text(
        json.dumps(scan, indent=1, sort_keys=True)
    )
    return scan


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
