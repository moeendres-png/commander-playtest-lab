#!/usr/bin/env python3
"""WS207 qualification-only setup orchestrator.

Mutation surface: qualification/ws207-xmage-qualified-scenario-setup/**
only. Reuses the sealed WS204 generic legalActionsPayload/submitAction
boundary through fresh JVMs (one per game). No production bridge mutation.
No engine repin. Zero behavior credit.

Subcommands:
  decks               write decks.json + prefs.json for every construction
  scan [--only=..]    opening-hand seed discovery (fresh JVM per seed)
  setup [--only=..]   native setup-run + twin replay on selected seeds
  matrix              build SETUP_MATRIX.json + VALIDATION.json from evidence

Seed discovery is qualification setup control (deterministic fixture
construction): it searches fixed per-slot candidate seed ranges for one
whose engine-native shuffle deals the required opening configuration.
Selection criteria are setup-only, recorded in SEED_CATALOG.json, and
never involve behavior outcomes (no requested-result filtering).

WS208/WS212 IMPACT: only EXPLICIT_RULES_SEED evidence counts. The probe
and setup driver bind game.setRulesSeed(seed) plus
setRequireExplicitSeed(true) BEFORE game.start/init (qualification-only
reflective hook; production XmageFullGameSession untouched). Outputs use
the opening_rs_ prefix. Legacy opening_ (RandomUtil-only) files are a
superseded audit trail and are NEVER used for selection.
"""

from __future__ import annotations

import concurrent.futures
import json
import queue
import subprocess
import sys
import time
from pathlib import Path

import ws207_decks as decks

WS207_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WS207_ROOT.parent.parent
PACK_PATH = (
    REPO_ROOT
    / "qualification/ws90-rqc3-corrected-first-wave-reissue"
    / "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json"
)
ENGINE_PIN = decks.ENGINE_PIN
SETUP_BUDGET = decks.SETUP_BUDGET
SCAN_WORKERS = 4
PROBE_TIMEOUT_S = 240
SETUP_TIMEOUT_S = 1500

H01_SUBCASES = ["HUMILITY_FIRST", "CLONE_FIRST", "NO_HUMILITY"]

PACK_AUTHORITY = (
    "FIRST_WAVE_EXECUTION_PACK_CORRECTED.json blob 5852965e59412399a947c626d4f7d428be8ef337"
)

SEED_BINDING_MODEL = (
    "EXPLICIT_RULES_SEED (game.setRulesSeed + game.setRequireExplicitSeed "
    "before game.start/init; qualification-only reflective hook)"
)

SETUPS = {
    "RQ-C3-A03": "NATURAL_GAME_START",
    "RQ-C3-A04": "NATURAL_GAME_START",
    "RQ-C3-B01": "NATURAL_GAME_START",
    "RQ-C3-C01": "NATURAL_GAME_START",
    "RQ-C3-C03": "NATURAL_GAME_START",
    "RQ-C3-D06": "NATURAL_GAME_START",
    "RQ-C3-E01": "PRE_STEP_NATIVE_PROGRESSION",
    "RQ-C3-E02": "PRE_STEP_NATIVE_PROGRESSION",
    "RQ-C3-F01": "NATURAL_GAME_START",
    "RQ-C3-G02": "NATURAL_GAME_START",
    "RQ-C3-G03": "NATIVE_LEDGER_PRELUDE",
    "RQ-C3-G04": "NATURAL_GAME_START",
    "RQ-C3-H01": "NATURAL_GAME_START",
    "RQ-C3-I01": "NATURAL_GAME_START",
    "RQ-C3-J02": "PRE_STEP_NATIVE_PROGRESSION",
}


def constructions() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for slot in decks.SLOT_ORDER:
        if slot == "RQ-C3-H01":
            for sub in H01_SUBCASES:
                out.append((slot, sub))
        else:
            out.append((slot, ""))
    return out


def key_of(slot: str, subcase: str) -> str:
    return slot if not subcase else f"{slot}-{subcase}"


def java_classpath() -> str:
    cp = Path("/tmp/opencode/ws205-cp.txt").read_text().strip()
    # All entries absolute: probes run with isolated workdirs, so relative
    # entries would not resolve there.
    bridge = REPO_ROOT / "engine-bridge/target/classes"
    return f"/tmp/opencode/ws207-driver-classes:/tmp/opencode/ws205-driver-classes:{bridge}:{cp}"


def cmd_decks(only: set[str]) -> int:
    for slot, sub in constructions():
        key = key_of(slot, sub)
        if only and key not in only and slot not in only:
            continue
        slot_dir = WS207_ROOT / "slots" / key
        slot_dir.mkdir(parents=True, exist_ok=True)
        (slot_dir / "decks.json").write_text(
            json.dumps(decks.build_decks(slot, sub), indent=1, sort_keys=True)
        )
        prefs = decks.build_setup_prefs(slot, sub)
        prefs["_meta"] = {
            "setup_policy_version": decks.SETUP_POLICY_VERSION,
            "slot": slot,
            "subcase": sub,
        }
        (slot_dir / "prefs.json").write_text(json.dumps(prefs, indent=1, sort_keys=True))
        print(f"[WS207] decks written {key}", flush=True)
    return 0


def run_probe(decks_path: Path, seed: int, slot: str, subcase: str, out_path: Path,
              workdir: Path | None = None) -> dict:
    cmd = [
        "java",
        "-cp",
        java_classpath(),
        "org.commanderlab.xmage.Ws207OpeningHandProbe",
        "--mode=opening-hand",
        f"--decks={decks_path}",
        f"--seed={seed}",
        f"--out={out_path}",
        f"--slot={slot}",
        f"--case={subcase}",
    ]
    # Each probe runs in its own workdir so parallel fresh JVMs never share
    # XMage's file-backed card-repo cache (db/); the cache is a local
    # performance artifact, never evidence. CWD defaults to the repo root.
    cwd = str(workdir) if workdir is not None else str(REPO_ROOT)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S,
                                cwd=cwd)
    except subprocess.TimeoutExpired:
        return {"seed": seed, "ok": False, "error": "probe timeout"}
    if not out_path.exists():
        return {"seed": seed, "ok": False,
                "error": f"rc={result.returncode} {result.stderr[-500:]}"}
    return {"seed": seed, "ok": True, "evidence": json.loads(out_path.read_text())}


def run_probe_pooled(pool: queue.Queue, decks_path: Path, seed: int, slot: str,
                     subcase: str, out_path: Path) -> dict:
    """Run one probe with an isolated workdir lease plus one fresh retry."""
    workdir = pool.get()
    try:
        workdir.mkdir(parents=True, exist_ok=True)
        row = run_probe(decks_path, seed, slot, subcase, out_path, workdir)
        if not row.get("ok"):
            time.sleep(5)
            row = run_probe(decks_path, seed, slot, subcase, out_path, workdir)
            if row.get("ok"):
                row["retried"] = True
        return row
    finally:
        pool.put(workdir)


def opening_met(evidence: dict, slot: str) -> tuple[bool, list[str]]:
    """Check OPENING_REQUIREMENTS against dealt hands (assertion-only).

    Requirement entries may contain "|" alternatives (e.g. B01 accepts
    either Warden in the opening hand; the other assembles via native
    draws during the setup run).
    """
    reqs = decks.OPENING_REQUIREMENTS.get(slot, {})
    missing: list[str] = []
    seats = {s["seat"]: s for s in evidence.get("seats", [])}
    for seat_key, cards in reqs.items():
        seat = int(seat_key.replace("seat", ""))
        hand = [h.lower() for h in seats.get(seat, {}).get("hand_names", [])]
        for card in cards:
            options = [o.strip().lower() for o in card.split("|")]
            if not any(opt in hand for opt in options):
                missing.append(f"seat{seat}:{card}")
    return (len(missing) == 0, missing)


def cmd_scan(only: set[str]) -> int:
    for slot, sub in constructions():
        key = key_of(slot, sub)
        if only and key not in only and slot not in only:
            continue
        slot_dir = WS207_ROOT / "slots" / key
        slot_dir.mkdir(parents=True, exist_ok=True)
        decks_path = slot_dir / "decks.json"
        if not decks_path.exists():
            print(f"[WS207] {key}: decks.json missing, run decks first", flush=True)
            continue
        base = decks.seed_scan_base(slot if slot != "RQ-C3-H01" else "RQ-C3-H01")
        if sub == "CLONE_FIRST":
            base += 100
        elif sub == "NO_HUMILITY":
            base += 200
        width = decks.SCAN_COUNT_PER_SLOT.get(slot, decks.SCAN_COUNT_DEFAULT)
        seeds = [base + i for i in range(width)]
        # H01 subcases share the slot-level table; extensions apply per key.
        extra_key = key if key in decks.SCAN_EXTRA else slot
        extra_ranges = decks.SCAN_EXTRA.get(extra_key, [])
        for ext_base, ext_count in extra_ranges:
            seeds = seeds + [ext_base + i for i in range(ext_count)]
        # Resumable: reuse existing per-seed probe evidence (same decks/seed
        # deterministically reproduce the same native shuffle; resume only
        # skips redundant JVMs, never changes selection). ONLY explicit
        # Rules-seed (opening_rs_) evidence is admissible; RandomUtil-only
        # (opening_) files are superseded and ignored here.
        cached: dict[int, dict] = {}
        todo: list[int] = []
        for seed in seeds:
            probe_path = slot_dir / f"opening_rs_seed_{seed}.json"
            if probe_path.exists():
                try:
                    cached[seed] = {"seed": seed, "ok": True,
                                    "evidence": json.loads(probe_path.read_text())}
                except json.JSONDecodeError:
                    todo.append(seed)
            else:
                todo.append(seed)
        print(f"[WS207] {key}: scanning {len(seeds)} seeds from {base} "
              f"({len(cached)} cached)", flush=True)
        results: list[dict] = list(cached.values())
        dir_pool: queue.Queue = queue.Queue()
        for worker in range(SCAN_WORKERS):
            dir_pool.put(Path(f"/tmp/ws207-scan-w{worker}"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
            future_to_seed = {
                pool.submit(
                    run_probe_pooled, dir_pool, decks_path, seed, slot, sub,
                    slot_dir / f"opening_rs_seed_{seed}.json",
                ): seed
                for seed in todo
            }
            for future in concurrent.futures.as_completed(future_to_seed):
                seed = future_to_seed[future]
                try:
                    row = future.result()
                except Exception as exc:
                    row = {"seed": seed, "ok": False, "error": str(exc)[:300]}
                results.append(row)
                if len(results) % 15 == 0:
                    print(f"[WS207] {key}: {len(results)}/{len(seeds)} probes", flush=True)
        by_seed = {r["seed"]: r for r in results}
        hits: list[int] = []
        for seed in seeds:
            row = by_seed[seed]
            if not row.get("ok"):
                continue
            met, _ = opening_met(row["evidence"], slot)
            if met:
                hits.append(seed)
        selected = hits[0] if hits else None
        # Admissibility gate: every hit must carry explicit Rules-seed
        # binding provenance; otherwise the scan selects nothing.
        admissible: list[int] = []
        for seed in hits:
            ev = by_seed[seed]["evidence"]
            if (ev.get("rules_seed") == seed and ev.get("rules_seed_explicit") is True
                    and ev.get("rules_seed_bound_before_start") is True):
                admissible.append(seed)
        selected = admissible[0] if admissible else None
        scan_record = {
            "schema": "ws207.opening-scan.v2",
            "slot": slot,
            "subcase": sub,
            "engine_pin": ENGINE_PIN,
            "seed_binding_model": SEED_BINDING_MODEL,
            "scan_base": base,
            "scan_count": len(seeds),
            "scan_seeds": seeds,
            "scan_extensions": (
                [{"base": ext_base, "count": ext_count}
                 for ext_base, ext_count in extra_ranges]
                if extra_ranges else []
            ),
            "selection_criterion": (
                "first seed whose engine-native dealt opening hands contain "
                f"{json.dumps(decks.OPENING_REQUIREMENTS.get(slot, {}))} "
                "(setup-only; no behavior outcome involved)"
            ),
            "probes_ok": sum(1 for r in results if r.get("ok")),
            "probes_failed": sum(1 for r in results if not r.get("ok")),
            "hits": hits,
            "admissible_hits": admissible,
            "selected_seed": selected,
            "randomutil_only_evidence": "SUPERSEDED (opening_ prefix): RandomUtil-only scans "
                                        "cannot establish reproducible setup seeds per "
                                        "WS208/WS212; retained on disk as audit trail only",
            "probe_workdir_isolation": "per-worker /tmp/ws207-scan-w<N> (fresh JVM each; "
                                       "XMage file cache never shared)",
            "evidence_classification": "MODELED",
            "note": (
                "Opening-hand contents are QUALIFICATION_ASSERTION_ONLY "
                "setup-control knowledge; never pilot gameplay input."
            ),
        }
        (slot_dir / "opening_rs_scan.json").write_text(json.dumps(scan_record, indent=1,
                                                                   sort_keys=True))
        print(f"[WS207] {key}: selected_seed={selected} hits={len(hits)}", flush=True)
    return 0


def run_setup_jvm(args: list[str], timeout_s: int = SETUP_TIMEOUT_S) -> subprocess.CompletedProcess:
    # WS208/WS212: setup runs execute ONLY through the qualification-only
    # bound setup driver (explicit Rules-seed binding). The RandomUtil-only
    # first-wave driver is never used for WS207 setup evidence.
    cmd = ["java", "-cp", java_classpath(),
           "org.commanderlab.xmage.Ws207SetupDriver", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                          cwd=str(REPO_ROOT))


def cmd_setup(only: set[str]) -> int:
    for slot, sub in constructions():
        key = key_of(slot, sub)
        if only and key not in only and slot not in only:
            continue
        slot_dir = WS207_ROOT / "slots" / key
        scan_path = slot_dir / "opening_rs_scan.json"
        if not scan_path.exists():
            print(f"[WS207] {key}: opening_rs_scan.json missing, run scan first", flush=True)
            continue
        scan = json.loads(scan_path.read_text())
        seed = scan.get("selected_seed")
        if seed is None:
            print(f"[WS207] {key}: no selected seed; setup-run skipped", flush=True)
            continue
        decks_path = slot_dir / "decks.json"
        prefs_path = slot_dir / "prefs.json"
        primary_out = slot_dir / "primary.json"
        print(f"[WS207] {key}: setup-run seed={seed}", flush=True)
        result = run_setup_jvm([
            "--mode=run",
            f"--slot={slot}",
            f"--case={sub}",
            f"--decks={decks_path}",
            f"--prefs={prefs_path}",
            f"--seed={seed}",
            f"--budget={SETUP_BUDGET}",
            f"--out={primary_out}",
            "--head=1dee8b77f7243900eec5a7cc05fb1fe26467aea9",
            f"--setup={SETUPS[slot]}",
            f"--authority-hash={PACK_AUTHORITY}",
        ])
        (slot_dir / "primary.stdout.txt").write_text(result.stdout[-8000:])
        (slot_dir / "primary.stderr.txt").write_text(result.stderr[-4000:])
        if not primary_out.exists():
            (slot_dir / "primary.failed.txt").write_text(
                f"rc={result.returncode}\n{result.stderr[-4000:]}")
            print(f"[WS207] {key}: PRIMARY JVM FAILED rc={result.returncode}", flush=True)
            continue
        evidence = json.loads(primary_out.read_text())
        stream_path = slot_dir / "primary.stream.json"
        stream_path.write_text(json.dumps({"decision_stream": evidence.get("decision_stream", [])}))
        twin_out = slot_dir / "twin.json"
        print(f"[WS207] {key}: twin setup-run seed={seed}", flush=True)
        twin = run_setup_jvm([
            "--mode=twin",
            f"--slot={slot}",
            f"--case={sub}",
            f"--decks={decks_path}",
            f"--prefs={prefs_path}",
            f"--seed={seed}",
            f"--budget={SETUP_BUDGET}",
            f"--out={twin_out}",
            f"--stream={stream_path}",
            "--head=1dee8b77f7243900eec5a7cc05fb1fe26467aea9",
            f"--setup={SETUPS[slot]}",
            f"--authority-hash={PACK_AUTHORITY}",
        ])
        (slot_dir / "twin.stdout.txt").write_text(twin.stdout[-8000:])
        (slot_dir / "twin.stderr.txt").write_text(twin.stderr[-4000:])
        check = check_setup_state(slot, sub, seed, slot_dir)
        (slot_dir / "setup_check.json").write_text(json.dumps(check, indent=1, sort_keys=True))
        print(f"[WS207] {key}: setup_verdict={check['setup_verdict']}", flush=True)
    return 0


def battlefield_index(evidence: dict) -> list[tuple[str, int]]:
    out = []
    assertion = evidence.get("assertion_state", {})
    if not isinstance(assertion, dict):
        return out
    for perm in assertion.get("battlefield", []):
        if not isinstance(perm, dict) or "name" not in perm:
            continue
        out.append((str(perm.get("name", "")), int(perm.get("controller_seat", -1))))
    return out


def check_setup_state(slot: str, subcase: str, seed: int, slot_dir: Path) -> dict:
    """Semantic setup-state check on fresh-process evidence (no behavior)."""
    key = key_of(slot, subcase)
    evidence = json.loads((slot_dir / "primary.json").read_text())
    stream = evidence.get("decision_stream", [])
    selected = [str(r.get("selected_label", "")) for r in stream]
    board = battlefield_index(evidence)
    failures: list[str] = []
    # 0. Rules-seed binding gate (WS208/WS212): the setup run itself must
    # carry explicit binding provenance or nothing else counts.
    if evidence.get("rules_seed") != seed:
        failures.append(f"rules_seed mismatch: {evidence.get('rules_seed')} != {seed}")
    if evidence.get("rules_seed_explicit") is not True:
        failures.append("rules_seed_explicit != true in setup-run evidence")
    if evidence.get("rules_seed_bound_before_start") is not True:
        failures.append("rules_seed_bound_before_start != true in setup-run evidence")
    # 1. Battlefield predicates (public assertion state).
    preds = list(decks.BATTLEFIELD_PREDICATES.get(slot, []))
    if slot == "RQ-C3-H01" and subcase in ("CLONE_FIRST", "NO_HUMILITY"):
        preds = [p for p in preds if p[0] != "Humility"]
    for substr, seat in preds:
        count = sum(1 for name, ctrl in board
                    if substr.lower() in name.lower() and ctrl == seat)
        if count < 1:
            failures.append(f"battlefield missing {substr} under seat{seat}")
    if slot == "RQ-C3-H01" and subcase in ("CLONE_FIRST", "NO_HUMILITY"):
        hum = sum(1 for name, _ in board if "humility" in name.lower())
        if hum > 0:
            failures.append("Humility on battlefield before Clone copy (ordering violated)")
    # 2. Held behavior cards never selected and never in graveyards.
    # Rigor: a held card must ALSO have been in a dealt opening hand (setup
    # control knowledge); otherwise "held" is vacuous (possibly undrawn) and
    # the neutral hand state is unproven -> UNKNOWN, never QUALIFIED.
    held = list(decks.HELD_BEHAVIOR_CARDS.get(slot, []))
    opening_hands: list[str] = []
    try:
        opening = json.loads((slot_dir / f"opening_rs_seed_{seed}.json").read_text())
        for seat in opening.get("seats", []):
            opening_hands.extend([str(h) for h in seat.get("hand_names", [])])
    except (OSError, json.JSONDecodeError):
        failures.append("opening-hand evidence missing for held-card presence check")
    graves: list[str] = []
    for seat in evidence.get("assertion_state", {}).get("seats", []):
        graves.extend([str(c) for c in seat.get("graveyard", [])])
    for card in held:
        if any(card.lower() in label.lower() for label in selected if label):
            failures.append(f"held behavior card selected during setup: {card}")
        if any(card.lower() in g.lower() for g in graves):
            failures.append(f"held behavior card consumed (graveyard): {card}")
        if opening_hands and not any(card.lower() in h.lower() for h in opening_hands):
            failures.append(f"held {card} presence unproven (absent from dealt opening hands)")
    # 3. No forbidden control-path failures.
    stopped = str(evidence.get("stopped_by", ""))
    if stopped.split(":")[0] in ("submit_rejected", "unhandled_decision_class",
                                  "projection_mismatch", "pending_failed",
                                  "legal_actions_failed", "twin_diverged"):
        failures.append(f"control path failure: {stopped}")
    # 4. G03 native ledger prelude: at least one 12-hit observable via P1 life.
    ledger_note = ""
    if slot == "RQ-C3-G03":
        p1_life = None
        for seat in evidence.get("assertion_state", {}).get("seats", []):
            if seat.get("seat") == 1:
                p1_life = seat.get("life")
        ledger_note = f"P1 life={p1_life} (40=>28 proves one native 12-hit; CODE_DERIVED)"
        if p1_life is None or p1_life > 28:
            failures.append(f"native ledger prelude unproven: {ledger_note}")
    # 5. Twin determinism for the selected setup seed.
    twin_record_path = slot_dir / "twin.record.json"
    twin_out_path = slot_dir / "twin.json"
    twin_match: bool | None = None
    if twin_out_path.exists():
        twin_evidence = json.loads(twin_out_path.read_text())
        twin_match = (not bool(twin_evidence.get("stream_diverged", True)))
        twin_record = {
            "stream_diverged": bool(twin_evidence.get("stream_diverged", True)),
            "stream_divergence_detail": twin_evidence.get("stream_divergence_detail", ""),
            "primary_entries": len(stream),
            "twin_entries": len(twin_evidence.get("decision_stream", [])),
        }
        twin_record_path.write_text(json.dumps(twin_record, indent=1, sort_keys=True))
        if twin_evidence.get("stream_diverged", True):
            failures.append("twin stream diverged for selected setup seed")
    verdict = "QUALIFIED_SETUP_AVAILABLE" if not failures else "UNKNOWN"
    return {
        "schema": "ws207.setup-check.v2",
        "slot": slot,
        "subcase": subcase,
        "key": key,
        "seed": seed,
        "rules_seed": evidence.get("rules_seed"),
        "rules_seed_explicit": evidence.get("rules_seed_explicit"),
        "rules_seed_bound_before_start": evidence.get("rules_seed_bound_before_start"),
        "seed_binding_model": SEED_BINDING_MODEL,
        "setup_boundary": SETUPS[slot],
        "decisions_answered": evidence.get("decisions_answered"),
        "stopped_by": stopped,
        "battlefield_predicates": [f"{c}@{s}" for c, s in preds],
        "held_behavior_cards": held,
        "ledger_note": ledger_note,
        "twin_stream_match": twin_match,
        "failures": failures,
        "setup_verdict": verdict,
        "behavior_credit": 0,
        "evidence_classification": "DIRECTLY_VERIFIED" if verdict == "QUALIFIED_SETUP_AVAILABLE"
        else "UNKNOWN",
    }


def main(argv: list[str]) -> int:
    only: set[str] = set()
    for arg in argv:
        if arg.startswith("--only="):
            only = set(arg.split("=", 1)[1].split(","))
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command = argv[0]
    if command == "decks":
        return cmd_decks(only)
    if command == "scan":
        return cmd_scan(only)
    if command == "setup":
        return cmd_setup(only)
    if command == "matrix":
        print("matrix is built by ws207_seal.py after evidence collection")
        return 0
    print(f"unknown command {command}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
