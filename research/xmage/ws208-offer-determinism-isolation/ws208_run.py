#!/usr/bin/env python3
"""WS208 runner: launch N fresh-JVM layered traces per construction and diff them.

Usage:
  ws208_run.py --construction=RQ-C3-H01-HUMILITY_FIRST --seed=9113 --reps=6 --budget=500
  ws208_run.py --matrix   # H01x6, D06/I01/A03/E02/B01 x4, A04/F01 controls x3

Decks/prefs are read verbatim from the sealed WS205 slot dirs (never modified).
Traces land in $FOUNDRY_RUN_DIR/ws208-traces (never in the worktree).
Each JVM is a fresh process (one game per process, matching WS205 isolation).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WS205_ROOT = REPO_ROOT / "qualification/ws205-xmage-ws90-first-wave"
RUN_DIR = Path(__import__("os").environ.get(
    "FOUNDRY_RUN_DIR", "/tmp/foundry-ws208-20260914-140815"))
TRACE_DIR = RUN_DIR / "ws208-traces"

MATRIX = [
    ("RQ-C3-H01-HUMILITY_FIRST", 9113, 6),
    ("RQ-C3-D06", 9106, 4),
    ("RQ-C3-I01", 9114, 4),
    ("RQ-C3-A03", 9101, 4),
    ("RQ-C3-E02", 9108, 4),
    ("RQ-C3-B01", 9103, 4),
    ("RQ-C3-A04", 9102, 3),
    ("RQ-C3-F01", 9109, 3),
]

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")


def normalize_label(text):
    text = _UUID_RE.sub("<uuid>", text)
    text = _HEX_RE.sub("<hex>", text)
    return text


def semantic_transcript_from_trace(trace):
    """WS205 normalizer applied to a WS208 trace (for pilot-parity checks)."""
    out = []
    for row in trace["decisions"]:
        types = {}
        for opt in row["native_options"]:
            types[opt["option_type"]] = types.get(opt["option_type"], 0) + 1
        offered_types = sorted(
            ({"type": k, "count": v} for k, v in types.items()),
            key=lambda r: str(r["type"]))
        entry = {
            "offset": row["offset"],
            "class": row["class"],
            "actor_seat": row["actor_seat"],
            "offered_count": len(row["native_options"]),
            "offered_types": offered_types,
            "selected_label": normalize_label(str(row.get("selected_label", ""))),
            "label_ambiguous": len(set(
                o["label"] for o in row["native_options"]
                if o["label"] == row.get("selected_label", ""))) > 1,
        }
        out.append(entry)
    term = trace.get("terminal_state", {})
    if isinstance(term, dict) and "battlefield" in term:
        board = []
        for perm in term["battlefield"]:
            if not isinstance(perm, dict) or "name" not in perm:
                continue
            board.append({
                "name": perm.get("name"),
                "controller_seat": perm.get("controller_seat"),
                "power": perm.get("power"),
                "toughness": perm.get("toughness"),
                "is_copy": perm.get("is_copy"),
                "ability_count": perm.get("abilities"),
            })
        board.sort(key=lambda r: (str(r["name"]), str(r["controller_seat"])))
        out.append({"terminal_board": board})
        seats = []
        for seat in term.get("seats", []):
            grave = sorted(seat.get("graveyard_names", []))
            seats.append({
                "seat": seat.get("seat"),
                "life": seat.get("life"),
                "hand_size": seat.get("hand_size"),
                "library_size": seat.get("library_size"),
                "graveyard": grave,
            })
        out.append({"terminal_seats": seats})
    return out


def transcript_hash(transcript):
    return hashlib.sha256(
        json.dumps(transcript, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()


def java_classpath():
    cp = Path("/tmp/opencode/ws205-cp.txt").read_text().strip()
    return (f"{RUN_DIR}/ws208-classes:"
            f"{REPO_ROOT}/engine-bridge/target/classes:{cp}")


def run_trace(construction, seed, rep, budget, mode="wish"):
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    slot_dir = WS205_ROOT / "slots" / construction
    out = TRACE_DIR / f"{construction}-{mode}-rep{rep}.json"
    cmd = ["java", "-cp", java_classpath(),
           "org.commanderlab.xmage.Ws208TraceDriver",
           f"--decks={slot_dir / 'decks.json'}",
           f"--prefs={slot_dir / 'prefs.json'}",
           f"--seed={seed}", f"--budget={budget}", f"--out={out}",
           f"--construction={construction}", f"--rep={rep}",
           f"--mode={mode}"]
    if mode == "twin":
        cmd.append(f"--stream={slot_dir / 'primary.stream.json'}")
    result = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=1500, cwd=str(REPO_ROOT))
    if not out.exists():
        print(f"[WS208] {construction} {mode}-rep{rep}: JVM FAILED rc={result.returncode}",
              flush=True)
        print(result.stderr[-2000:], flush=True)
        return None
    print(f"[WS208] {construction} {mode}-rep{rep}: trace OK", flush=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--construction", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reps", type=int, default=0)
    parser.add_argument("--budget", type=int, default=500)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--mode", default="twin",
                        help="twin (follow WS205 primary stream) or wish (fresh pilot)")
    args = parser.parse_args()
    jobs = MATRIX if args.matrix else [(args.construction, args.seed, args.reps)]
    paths = {}
    for construction, seed, reps in jobs:
        for rep in range(reps):
            out = run_trace(construction, seed, rep, args.budget, args.mode)
            if out is not None:
                paths.setdefault(construction, []).append(out)
    summary = {}
    for construction, outs in paths.items():
        diff = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "ws208_diff.py"),
             *[str(o) for o in outs]],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        print(f"===== {construction} =====")
        print(diff.stdout)
        summary[construction] = diff.stdout
    (TRACE_DIR / "diff-summary.txt").write_text(
        "\n".join(f"===== {k} =====\n{v}" for k, v in summary.items()))
    return 0


if __name__ == "__main__":
    main()
