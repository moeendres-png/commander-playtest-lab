#!/usr/bin/env python3
"""WS65 First-Wave runner shim (WS65-owned, qualification-only).

WS64-verbatim delegation to
candidate-qualification/ws64-forge-a04-vertical-path-investigation/
ws64_fulltape_runner.py (itself ws62-verbatim + full native tape), EXCEPT the
marked WS65 deltas below. No engine, provider, Decision, or intent semantics
change. Grants no behavior credit by itself (BEHAVIOR_CREDIT=0/107; credit is
adjudicated separately in WS65 evidence from journals).

WS65 DELTA-1 (successor EV dir): COMMANDER_LAB_FORGE_PROVIDER_CMD must
reference /tmp/ws65-ev (fresh WS65 provider build against the exact Forge
checkout /tmp/ws65-forge-src-a9a95db) and must contain no old-pin path.
Fails loud otherwise.

WS65 DELTA-2 (concession family): answer externally-offered "concession"
frames, if the engine/provider transport ever emits one, by matching ONLY
provider-offered options: {"decision": "concede"} selects the single
WS62:CONCEDE authority option (never DECLINE); {"decision": "decline"}
selects DECLINE. Zero-match and multi-match fail closed. No legality
reconstruction, no outcome injection: the provider still consults native
canConcede() and calls only the native concede() seam.

WS65 DELTA-3: output journals additionally stamp ws65_runner identity
(additive only; never rewrites proof).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS64_DIR = HERE.parent / "ws64-forge-a04-vertical-path-investigation"
WS62_DIR = HERE.parent / "ws62-forge-successor-requalification"
WS53_DIR = HERE.parent / "ws53-forge-convergence-native-progression"
WS48_DIR = HERE.parent / "ws48-forge-v1.0.5"
sys.path.insert(0, str(WS64_DIR))
sys.path.insert(0, str(WS62_DIR))
sys.path.insert(0, str(WS53_DIR))
sys.path.insert(0, str(WS48_DIR))

import ws64_fulltape_runner as ws64  # noqa: E402,E401
import ws62_breadth_runner as ws62  # noqa: E402
import ws53_sequence_runner as ws53  # noqa: E402
import run_behavior_transcript_probe as base  # noqa: E402

FORGE_COMMIT = "a9a95db6662c2d28814390a9c0c2f986e39aa8b4"
FORGE_TREE = "2c18327f79e330f2ed167067166ffd42d61b0849"
FORGE_OLD_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"

_ORIG_WS65_ANSWER = ws53.ws53_answer


def _ws65_concede_labels(labels: list[dict[str, str]]) -> tuple[list[int], list[int]]:
    auth = [i for i, lb in enumerate(labels)
            if "WS62:CONCEDE" in (lb.get("_kind", "") + str(lb))
            or "CONCEDE" in str(lb.get("opt", "")).upper() + str(lb.get("_kind", "")).upper()
            and "DECLINE" not in str(lb.get("opt", "")).upper()]
    dec = [i for i, lb in enumerate(labels)
           if "DECLINE" in str(lb.get("opt", "")).upper()]
    return auth, dec


def answer_concession(drv, actor: str, opts: list[dict],
                      labels: list[dict[str, str]], phase, turn) -> str:
    due = [e for e in drv.script
           if e.get("decision_family") == "concession"
           and e.get("actor") == actor
           and (e.get("phases") is None or phase in (e.get("phases") or []))
           and (e.get("turns") is None or turn in (e.get("turns") or []))]
    if not due:
        raise base.Blocked("concession", f"unscripted concession for {actor} "
                                         f"(kind-family binding: no due entry)")
    d = due[0]
    drv.script.remove(d)
    sv = (d.get("selection") or {}).get("semantic_value") or {}
    want = sv.get("decision", "concede")
    texts = [str(o.get("kind", "")) for o in opts]
    auth = [i for i, t in enumerate(texts)
            if "WS62:CONCEDE" in t and "DECLINE" not in t]
    dec = [i for i, t in enumerate(texts) if "DECLINE" in t]
    picks = auth if want == "concede" else dec
    if want not in ("concede", "decline"):
        drv.script.insert(0, d)
        raise base.Blocked("concession", f"unknown decision {want}")
    if len(picks) != 1:
        drv.script.insert(0, d)
        raise base.Blocked("concession", f"{want}: {len(picks)} matches of {len(opts)}")
    drv.consumed.append(d)
    return str(opts[picks[0]]["option_id"])


def ws65_answer(drv, kind: str, actor: str, opts: list[dict],
                labels: list[dict[str, str]], record, phase=None, turn=None) -> str:
    if kind == "concession":
        return answer_concession(drv, actor, opts, labels, phase, turn)
    return _ORIG_WS65_ANSWER(drv, kind, actor, opts, labels, record, phase, turn)


ws53.ws53_answer = ws65_answer  # type: ignore[assignment]
ws62.ws53.ws53_answer = ws65_answer  # type: ignore[assignment]


def _assert_ws65_runtime() -> None:
    cmd = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "")
    if "/tmp/ws65-ev" not in cmd:
        raise SystemExit("WS65_RUNNER_PROVIDER_CMD_NOT_WS65:/tmp/ws65-ev missing")
    if FORGE_OLD_COMMIT in cmd or "forge-66caae" in cmd:
        raise SystemExit("WS65_RUNNER_OLD_PIN_ON_CMD_FAIL_CLOSED")
    if not os.environ.get("COMMANDER_LAB_FORGE_LANG_DIR"):
        raise SystemExit("WS65_RUNNER_LANG_DIR_MISSING")


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--output", type=Path, required=True)
    known, _rest = ap.parse_known_args()
    _assert_ws65_runtime()
    rc = ws62.main()
    try:
        doc = json.loads(known.output.read_text())
    except Exception as ex:
        raise SystemExit(f"WS65_RUNNER_OUTPUT_MISSING:{ex}") from ex
    if (doc.get("forge") or {}).get("commit") != FORGE_COMMIT:
        raise SystemExit(f"WS65_JOURNAL_PIN_MISMATCH:{(doc.get('forge') or {}).get('commit')}")
    if (doc.get("forge") or {}).get("tree") != FORGE_TREE:
        raise SystemExit("WS65_JOURNAL_TREE_MISMATCH")
    doc["ws65_runner"] = ("ws65_runner.py (ws64_fulltape_runner verbatim + "
                          "concession-family transport + ws65 pin gate)")
    doc["ws65_forge"] = {"commit": FORGE_COMMIT, "tree": FORGE_TREE}
    doc["ws65_old_pin_absent"] = FORGE_OLD_COMMIT not in json.dumps(doc)
    known.output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"WS65_RUNNER_PIN_OK:{FORGE_COMMIT[:7]}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
