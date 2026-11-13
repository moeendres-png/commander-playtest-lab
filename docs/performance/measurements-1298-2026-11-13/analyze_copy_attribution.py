"""Issue #1298 Stufe 1 — PRIMARY analysis (JSON parse path, streaming).

Input: two files produced by
  jfr print --events jdk.ExecutionSample      --json --stack-depth 512 full_profile.jfr
  jfr print --events jdk.ObjectAllocationSample --json --stack-depth 1 full_profile.jfr
WARNING: `jfr print` truncates stacks to 5 frames by default — without
--stack-depth 512 the attribution silently degrades to the depth-5
artefact that produced the wrong 5.2 % bridge figure in #1279/#1281.
Events are decoded one at a time (json.JSONDecoder.raw_decode) so the
~300 MB of JSON never materialise as one Python object graph.

Definitions (documented in COPY_ATTRIBUTION_1298_2026-11-13.md):
- Frame string: "<binary class name>.<method>" (class '/' -> '.').
- COPY-ENTRY frames (explicit copy entry points, set E):
    * any method named "copy" on a mage.* class,
    * method in {deepCopyObject, copyCardsLazily, copyGameState} on mage.*
      (deepCopyObject lives in mage.util.CardUtil),
    * mage.game.GameImpl.createSimulation* (incl. ...ForPlayableCalc).
- A sample is a COPY sample if its stack contains >= 1 E frame.
- Anchor = outermost (closest-to-root) E frame. Trigger class = first
  matching marker when scanning the frames ABOVE the anchor, precedence:
  (a) bookmark > (b) playable > (c) trigger > (e) watchers >
  (d) other state storage > (f) other.
- Broad copy share (comparison with #1297's 42.1 %): samples containing an
  E frame OR a known copy-constructor frame (set C).
Only GAME and "main" threads are counted (same filter as #1281 script).
Output: JSON on stdout / --out file.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

COPY_CTOR_FRAMES = {
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


def iter_events(path: Path) -> Iterator[dict]:
    text = path.read_text(encoding="utf-8")
    start = text.index('"events"')
    start = text.index("[", start) + 1
    decoder = json.JSONDecoder()
    idx, n = start, len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n,":
            idx += 1
        if idx >= n or text[idx] == "]":
            break
        obj, end = decoder.raw_decode(text, idx)
        yield obj
        idx = end
    del text


def frame_name(frame: dict) -> str:
    method = frame.get("method") or {}
    typ = (method.get("type") or {}).get("name") or ""
    name = method.get("name") or ""
    return f"{typ.replace('/', '.')}.{name}"


def is_copy_entry(frame_str: str) -> bool:
    if not frame_str.startswith("mage."):
        return False
    method = frame_str.rsplit(".", 1)[-1]
    cls = frame_str.rsplit(".", 1)[0]
    if method == "copy":
        return True
    if method in ("deepCopyObject", "copyCardsLazily", "copyGameState"):
        return True
    return cls == "mage.game.GameImpl" and method.startswith("createSimulation")


def classify_above(frames: list[str], anchor_idx: int) -> tuple[str, str]:
    above = frames[anchor_idx + 1 :]

    def has(pred) -> str | None:
        for f in above:
            if pred(f):
                return f
        return None

    hit = has(
        lambda f: (
            f
            in (
                "mage.game.GameStates.save",
                "mage.game.GameImpl.saveState",
                "mage.game.GameImpl.bookmarkState",
            )
        )
    )
    if hit:
        return "a_bookmark", hit
    hit = has(
        lambda f: any(
            k in f
            for k in (
                "createSimulationForPlayableCalc",
                ".getPlayable",
                ".canPlay",
                "getPlayableUnderCard",
                ".getAvailableManaProducers",
            )
        )
    )
    if hit:
        return "b_playable", hit
    hit = has(lambda f: "mage.game" in f and "trigger" in f.lower())
    if hit:
        return "c_trigger", hit
    hit = has(lambda f: f.startswith("mage.watchers."))
    if hit:
        return "e_watchers", hit
    hit = has(
        lambda f: (
            f.startswith("mage.game.GameStates.")
            or f == "mage.game.GameImpl.saveGame"
            or ".restoreState" in f
            or f.endswith(".GameImpl.restore")
        )
    )
    if hit:
        return "d_state_storage", hit
    direct = above[0] if above else "<root>"
    return "f_other", direct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exec-json", type=Path, required=True)
    parser.add_argument("--alloc-json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    total = 0
    copy_samples = 0
    broad_copy = 0
    by_thread_total: Counter = Counter()
    by_thread_copy: Counter = Counter()
    classes: Counter = Counter()
    class_evidence: dict[str, Counter] = {}
    anchor_counter: Counter = Counter()
    anchor_direct_caller: dict[str, Counter] = {}
    leaf_counter_copy: Counter = Counter()
    samples_with_sim_frame = 0
    samples_with_getplayable_frame = 0

    for ev in iter_events(args.exec_json):
        if ev.get("type") != "jdk.ExecutionSample":
            continue
        values = ev.get("values") or {}
        thread = ((values.get("sampledThread") or {}).get("javaName")) or ""
        if "GAME" not in thread and thread.strip().strip('"') != "main":
            continue
        frames_raw = ((values.get("stackTrace") or {}).get("frames")) or []
        frames = [frame_name(f) for f in frames_raw]
        if not frames:
            continue
        tkey = "GAME" if "GAME" in thread else "main"
        assert tkey in ("GAME", "main")
        total += 1
        by_thread_total[tkey] += 1
        if any("createSimulationForPlayableCalc" in f for f in frames):
            samples_with_sim_frame += 1
        if any(".getPlayable" in f for f in frames):
            samples_with_getplayable_frame += 1
        entry_idx = [i for i, f in enumerate(frames) if is_copy_entry(f)]
        has_ctor = any(f in COPY_CTOR_FRAMES for f in frames)
        if entry_idx or has_ctor:
            broad_copy += 1
        if not entry_idx:
            continue
        copy_samples += 1
        by_thread_copy[tkey] += 1
        anchor_idx = max(entry_idx)
        anchor_counter[frames[anchor_idx]] += 1
        direct = frames[anchor_idx + 1] if anchor_idx + 1 < len(frames) else "<root>"
        anchor_direct_caller.setdefault(frames[anchor_idx], Counter())[direct] += 1
        leaf_counter_copy[frames[0]] += 1
        cls, hit_frame = classify_above(frames, anchor_idx)
        classes[cls] += 1
        class_evidence.setdefault(cls, Counter())[hit_frame] += 1

    alloc_events: Counter = Counter()
    alloc_weight: Counter = Counter()
    for ev in iter_events(args.alloc_json):
        if ev.get("type") != "jdk.ObjectAllocationSample":
            continue
        values = ev.get("values") or {}
        obj = ((values.get("objectClass") or {}).get("name") or "").replace("/", ".")
        alloc_events[obj] += 1
        alloc_weight[obj] += int(values.get("weight") or 0)

    out = {
        "parse_path": "json-streaming",
        "total_samples_game_main": total,
        "by_thread_total": dict(by_thread_total),
        "copy_samples": copy_samples,
        "by_thread_copy": dict(by_thread_copy),
        "broad_copy_samples_E_or_ctor": broad_copy,
        "trigger_classes": dict(classes),
        "class_evidence_frames": {k: v.most_common(10) for k, v in class_evidence.items()},
        "top_anchors": anchor_counter.most_common(20),
        "anchor_direct_callers": {k: v.most_common(6) for k, v in anchor_direct_caller.items()},
        "samples_with_createSimulationForPlayableCalc_frame": samples_with_sim_frame,
        "samples_with_getPlayable_frame": samples_with_getplayable_frame,
        "top_leaf_frames_in_copy_samples": leaf_counter_copy.most_common(20),
        "alloc_events_total": int(sum(alloc_events.values())),
        "alloc_weight_total": int(sum(alloc_weight.values())),
        "alloc_top_classes": [
            {"class": c, "events": alloc_events[c], "weight_bytes": alloc_weight[c]}
            for c, _ in alloc_events.most_common(30)
        ],
        "alloc_mage_classes_of_interest": [
            {"class": c, "events": alloc_events[c], "weight_bytes": alloc_weight[c]}
            for c in sorted(alloc_events)
            if c.startswith("mage.game.GameState")
            or c.startswith("mage.game.GameImpl")
            or c.startswith("mage.watchers.Watchers")
            or c.startswith("mage.abilities.Abilities")
            or c == "mage.abilities.effects.Effects"
            or c == "mage.abilities.Modes"
        ],
    }
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
