#!/usr/bin/env python3
"""Independent counter-check for issue #1298 step 1 (copy attribution).

Written from scratch for the counter-count. It parses the TEXT output of

    jfr print --events jdk.ExecutionSample,jdk.ObjectAllocationSample \
        --stack-depth 512 <file>

in a streaming fashion (line by line from a pipe; the text output is
~GB-sized and is never loaded into memory as one string).

Counting definitions (applied exactly as specified for the counter-check):

* Only jdk.ExecutionSample events whose sampledThread is "main" or starts
  with "GAME" are counted.
* A frame is written as "fully.qualified.ClassName.methodName": the token
  before "(" in the printed frame line. A bare class name (a constructor
  printed without a method part) is normalised to "<Class>.<init>";
  constructors already printed as ".<init>" stay unchanged.
* COPY-ENTRY set E: a frame on a mage.* class whose method is "copy", or
  whose method is one of {"deepCopyObject", "copyCardsLazily",
  "copyGameState"} on a mage.* class, or class mage.game.GameImpl with a
  method starting with "createSimulation".
* Copy sample: the stack contains >= 1 E-frame. Anchor = the E-frame with
  the largest index (closest to the root; index 0 is the leaf).
* Trigger class: determined from the frames ABOVE the anchor
  (index > anchor) by pattern priority (a), (b), (c), (e), (d), else (f):
    (a) a_bookmark     frame in {GameStates.save, GameImpl.saveState,
                                GameImpl.bookmarkState}
    (b) b_playable     frame contains one of createSimulationForPlayableCalc,
                       .getPlayable, .canPlay, getPlayableUnderCard,
                       .getAvailableManaProducers
    (c) c_trigger      frame contains "mage.game" and (lowercased) "trigger"
    (e) e_watchers     frame starts with "mage.watchers."
    (d) d_state_storage frame starts with "mage.game.GameStates." or is
                       mage.game.GameImpl.saveGame or contains ".restoreState"
                       or ends with ".GameImpl.restore"
    (f) f_other        otherwise (evidence frame = direct caller of the
                       anchor, i.e. the frame at anchor index + 1)
  Priority is applied pattern-first: (a) is searched in all frames above
  the anchor before (b) is considered, and so on.
* Broad copy: the stack contains an E-frame OR one of the listed
  constructor frames (Effects.<init>, AbilitiesImpl.<init>,
  AbilityImpl.<init>, MageObjectImpl.<init>, GameState.<init>,
  ContinuousEffects.<init>, Watchers.<init>, GameImpl.<init>,
  CardImpl.<init>).
* Allocation: every jdk.ObjectAllocationSample event is counted per
  objectClass (class name normalised by stripping the
  "(classLoader = ...)" suffix) and its "weight" is summed, converting
  the printed unit to bytes (bytes = 1, kB = 1024, MB = 1024**2,
  GB = 1024**3).

Output: a JSON file with counters only (no interpretation).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "full_profile.jfr"
DEFAULT_OUTPUT = HERE / "attribution_countercheck.json"

# ---------------------------------------------------------------------------
# Definition constants
# ---------------------------------------------------------------------------

SPECIAL_COPY_METHODS = {"deepCopyObject", "copyCardsLazily", "copyGameState"}

BROAD_CTOR_FRAMES = {
    "mage.abilities.effects.Effects.<init>",
    "mage.abilities.AbilitiesImpl.<init>",
    "mage.abilities.AbilityImpl.<init>",
    "mage.MageObjectImpl.<init>",
    "mage.game.GameState.<init>",
    "mage.abilities.effects.ContinuousEffects.<init>",
    "mage.watchers.Watchers.<init>",
    "mage.game.GameImpl.<init>",
    "mage.cards.CardImpl.<init>",
}

A_BOOKMARK_FRAMES = {
    "mage.game.GameStates.save",
    "mage.game.GameImpl.saveState",
    "mage.game.GameImpl.bookmarkState",
}

B_PLAYABLE_SUBSTRINGS = (
    "createSimulationForPlayableCalc",
    ".getPlayable",
    ".canPlay",
    "getPlayableUnderCard",
    ".getAvailableManaProducers",
)

WEIGHT_FACTORS = {
    "bytes": 1.0,
    "byte": 1.0,
    "B": 1.0,
    "kB": 1024.0,
    "KB": 1024.0,
    "MB": 1024.0**2,
    "GB": 1024.0**3,
    "TB": 1024.0**4,
}

THREAD_RE = re.compile(r'sampledThread\s*=\s*"(.*)"\s*\(javaThreadId')
OBJECT_CLASS_RE = re.compile(r"objectClass\s*=\s*(.+?)\s*\(classLoader\s*=")
OBJECT_CLASS_FALLBACK_RE = re.compile(r"objectClass\s*=\s*(.+?)\s*$")
WEIGHT_RE = re.compile(r"weight\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*(\S+)?\s*$")


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------


def normalise_frame(raw_line: str) -> str | None:
    """Turn one printed stack-frame line into "class.method" form.

    Returns None for non-frame lines (e.g. the "..." truncation marker).
    """
    text = raw_line.strip()
    if not text or text == "...":
        return None
    token = text.split("(", 1)[0].strip()
    if not token or " " in token:
        return None
    if token.endswith(".<init>") or token.endswith(".<clinit>"):
        return token
    last = token.rsplit(".", 1)[-1] if "." in token else token
    # A bare fully qualified class name (no method part) is how a
    # constructor may be printed: normalise it to "<Class>.<init>".
    # Class-name segments start with an uppercase letter; method names
    # start lowercase (or are <init>/<clinit>, handled above).
    if last and last[0].isupper():
        return token + ".<init>"
    return token


def split_frame(frame: str) -> tuple[str, str]:
    if "." not in frame:
        return frame, ""
    cls, meth = frame.rsplit(".", 1)
    return cls, meth


def is_copy_entry(frame: str) -> bool:
    cls, meth = split_frame(frame)
    if not (cls == "mage" or cls.startswith("mage.")):
        return False
    if meth == "copy":
        return True
    if meth in SPECIAL_COPY_METHODS:
        return True
    return cls == "mage.game.GameImpl" and meth.startswith("createSimulation")


def classify_trigger(frames_above: list[str]) -> str:
    """Pattern priority (a), (b), (c), (e), (d); pattern-first search."""
    if any(f in A_BOOKMARK_FRAMES for f in frames_above):
        return "a_bookmark"
    if any(any(s in f for s in B_PLAYABLE_SUBSTRINGS) for f in frames_above):
        return "b_playable"
    if any("mage.game" in f and "trigger" in f.lower() for f in frames_above):
        return "c_trigger"
    if any(f.startswith("mage.watchers.") for f in frames_above):
        return "e_watchers"
    if any(
        f.startswith("mage.game.GameStates.")
        or f == "mage.game.GameImpl.saveGame"
        or ".restoreState" in f
        or f.endswith(".GameImpl.restore")
        for f in frames_above
    ):
        return "d_state_storage"
    return "f_other"


# ---------------------------------------------------------------------------
# Streaming parser
# ---------------------------------------------------------------------------


def find_jfr() -> str:
    jfr = shutil.which("jfr")
    if jfr:
        return jfr
    candidates = sorted(Path.home().glob("workspace/tools/jdk-*/bin/jfr"))
    if candidates:
        return str(candidates[0])
    sys.exit("jfr binary not found in PATH (source ~/workspace/tools/env.sh)")


def run(jfr_file: Path) -> dict:
    cmd = [
        find_jfr(),
        "print",
        "--events",
        "jdk.ExecutionSample,jdk.ObjectAllocationSample",
        "--stack-depth",
        "512",
        str(jfr_file),
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )
    assert proc.stdout is not None

    total_samples = 0
    by_thread: Counter[str] = Counter()
    copy_samples = 0
    broad_copy_samples = 0
    trigger_classes: Counter[str] = Counter()
    anchor_counter: Counter[str] = Counter()

    alloc_events_total = 0
    alloc_events: Counter[str] = Counter()
    alloc_weight: Counter[str] = Counter()  # float bytes, via float keys sum

    # Parser state for the event currently being read.
    event_kind: str | None = None  # "exec" | "alloc" | None
    cur_thread: str | None = None
    cur_frames: list[str] = []
    in_stack = False
    cur_obj_class: str | None = None
    cur_weight_bytes = 0.0

    def flush_event() -> None:
        nonlocal total_samples, copy_samples, broad_copy_samples
        nonlocal alloc_events_total, cur_thread, cur_frames
        nonlocal cur_obj_class, cur_weight_bytes
        if event_kind == "exec":
            thread = cur_thread
            if thread is not None and (thread == "main" or thread.startswith("GAME")):
                total_samples += 1
                by_thread[thread] += 1
                frames = cur_frames
                e_indices = [i for i, f in enumerate(frames) if is_copy_entry(f)]
                has_broad_ctor = any(f in BROAD_CTOR_FRAMES for f in frames)
                if e_indices or has_broad_ctor:
                    broad_copy_samples += 1
                if e_indices:
                    copy_samples += 1
                    anchor_idx = max(e_indices)
                    anchor_counter[frames[anchor_idx]] += 1
                    trigger_classes[classify_trigger(frames[anchor_idx + 1 :])] += 1
        elif event_kind == "alloc":
            if cur_obj_class is not None:
                alloc_events_total += 1
                alloc_events[cur_obj_class] += 1
                alloc_weight[cur_obj_class] += cur_weight_bytes

    for line in proc.stdout:
        stripped = line.strip()
        if stripped == "jdk.ExecutionSample {":
            event_kind = "exec"
            cur_thread = None
            cur_frames = []
            in_stack = False
            continue
        if stripped == "jdk.ObjectAllocationSample {":
            event_kind = "alloc"
            cur_obj_class = None
            cur_weight_bytes = 0.0
            in_stack = False
            continue
        if event_kind is None:
            continue
        if stripped == "}":
            flush_event()
            event_kind = None
            in_stack = False
            continue
        if event_kind == "exec":
            if in_stack:
                if stripped == "]":
                    in_stack = False
                else:
                    frame = normalise_frame(line)
                    if frame is not None:
                        cur_frames.append(frame)
                continue
            if stripped.startswith("stackTrace"):
                in_stack = True
                continue
            m = THREAD_RE.search(line)
            if m:
                cur_thread = m.group(1)
        elif event_kind == "alloc":
            if stripped.startswith("objectClass"):
                m = OBJECT_CLASS_RE.search(line) or OBJECT_CLASS_FALLBACK_RE.search(line)
                if m:
                    cur_obj_class = m.group(1).strip()
                continue
            if stripped.startswith("weight"):
                m = WEIGHT_RE.search(line)
                if m:
                    value = float(m.group(1))
                    unit = m.group(2) or "bytes"
                    cur_weight_bytes = value * WEIGHT_FACTORS.get(unit, 1.0)
                continue

    proc.stdout.close()
    stderr_text = proc.stderr.read() if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        sys.exit(f"jfr print failed with exit code {rc}: {stderr_text[:2000]}")

    for key in (
        "a_bookmark",
        "b_playable",
        "c_trigger",
        "d_state_storage",
        "e_watchers",
        "f_other",
    ):
        trigger_classes.setdefault(key, 0)

    top_anchors = [
        {"anchor": name, "count": count}
        for name, count in sorted(anchor_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
    ]
    top_alloc = [
        {"objectClass": name, "events": count, "weight_bytes": round(alloc_weight[name])}
        for name, count in sorted(
            alloc_events.items(),
            key=lambda kv: (-kv[1], -alloc_weight[kv[0]], kv[0]),
        )[:25]
    ]

    return {
        "total_samples_game_main": total_samples,
        "by_thread_total": dict(sorted(by_thread.items())),
        "copy_samples": copy_samples,
        "broad_copy_samples_E_or_ctor": broad_copy_samples,
        "trigger_classes": {
            k: trigger_classes[k]
            for k in (
                "a_bookmark",
                "b_playable",
                "c_trigger",
                "d_state_storage",
                "e_watchers",
                "f_other",
            )
        },
        "top_anchors": top_anchors,
        "alloc_events_total": alloc_events_total,
        "alloc_top_classes": top_alloc,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.input)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
