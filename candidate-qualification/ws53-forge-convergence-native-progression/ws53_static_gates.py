#!/usr/bin/env python3
"""WS53 static gates: forbidden-fallback audit + hidden-info adversary control.

Converged from WS50 donor ws50_static_gates.py (e636e705) per adjudicated
matrix (WS50-D08 SAFE_ORTHOGONAL_PORT, XHIGH Q6 binding: explicit WS53 paths,
no WS50-worktree default).

No engine execution. Operates on the generated provider source and fresh WS53
journals only (never on WS50-retained journals as pass criteria).

Gates:
1. FALLBACK_AUDIT: scan the WS53-built generated provider for production-
   reachable internal-AI/default choice paths. Known-good natives (explicitly
   allowlisted with reason) do not fail the gate.
2. ADVERSARY_CONTROL_POSITIVE: every journal frame's actor must see its OWN
   hand completely (names present, count == listed) wherever count > 0.
3. ADVERSARY_CONTROL_NEGATIVE: planted leaks (a card name injected into a
   non-owner hand view; a facedown name exposed; an inflated own-hand count)
   must each be FLAGGED by audit_observations. Proves the adversary is not
   vacuous: it would have caught a leak had the provider emitted one.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ws48-forge-v1.0.5"))
sys.path.insert(0, str(HERE))
from ws53_sequence_runner import audit_observations  # noqa: E402

# pattern -> disposition (FAIL = forbidden production-reachable fallback)
FALLBACK_PATTERNS = [
    (r"import forge\.ai\.", True, "Forge AI import in provider"),
    (r"import forge\.gui\.", True, "Forge GUI import in provider"),
    (r"PlayerControllerAi", True, "AI controller reference"),
    (r"ComputerUtilMana", True, "AI mana logic reference"),
    (r"RemoteClientGuiGame", True, "remote GUI game reference"),
    (r"candidates\.get\(0\)", True, "first-candidate default"),
    (r"game\.findById\(expectedNativeId\)", True, "fixture id reconstruction"),
    (r"new java\.util\.Random\(", True, "provider-side RNG fabrication"),
    (r"Math\.random\(\)", True, "provider-side RNG fabrication"),
]

# allowlisted: single-option mandatory resolutions (no discretion) and the
# engine-acceptance canPlay re-check (rejects offered actions the engine
# refuses; never invents an outcome).
ALLOW_HINTS = ("SINGLE_NATIVE_OPTION", "recordAutomatic", "canPlay(true)",
               "STALE_OPTION", "failClosed", "ControlledStop")


def fallback_audit(provider_java: Path) -> dict:
    text = provider_java.read_text(encoding="utf-8")
    hits = []
    for pattern, fatal, label in FALLBACK_PATTERNS:
        for m in re.finditer(pattern, text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start:line_end if line_end > 0 else len(text)]
            hits.append({"pattern": pattern, "label": label, "fatal": fatal,
                         "line": line.strip()[:200]})
    fatal_hits = [h for h in hits if h["fatal"]]
    return {"gate": "FALLBACK_AUDIT", "file": str(provider_java),
            "hits": fatal_hits,
            "verdict": "PASS" if not fatal_hits else "FAIL"}


def load_views(frame: dict) -> dict:
    return {o["viewer"]: json.loads(o["view"]) for o in frame["observations"] if o.get("view")}


def adversary_positive(journal_path: Path, max_frames: int = 0) -> dict:
    journal = json.loads(journal_path.read_text())
    checked = 0
    failures = []
    degraded = 0
    for f in journal["frames"]:
        if max_frames and checked >= max_frames:
            break
        for o in f.get("observations", []):
            if o.get("fingerprint") == "UNAVAILABLE" or not o.get("view"):
                degraded += 1
        views = load_views(f)
        for viewer, view in views.items():
            for hand in view.get("hands", []):
                if hand.get("owner") == viewer and hand.get("count", 0) > 0:
                    checked += 1
                    names = [c.get("name") for c in hand.get("cards", [])]
                    if len(hand["cards"]) != hand["count"] or not all(names):
                        failures.append({"frame": f["seq"], "viewer": viewer,
                                         "listed": len(hand["cards"]),
                                         "count": hand["count"]})
    ok = checked > 0 and not failures and degraded == 0
    return {"gate": "ADVERSARY_CONTROL_POSITIVE", "journal": str(journal_path),
            "own_hand_views_checked": checked,
            "degraded_frames": degraded,
            "failures": failures[:5],
            "verdict": "PASS" if ok else "FAIL"}


def adversary_negative(journal_path: Path) -> dict:
    journal = json.loads(journal_path.read_text())
    # Use the first frame where some owner hand is non-empty (post-draw) with
    # ≥2 principals, so the planted leaks are meaningful.
    target = None
    for f in journal["frames"]:
        try:
            views = load_views(f)
        except Exception:
            continue
        if len(views) >= 2 and any(
                h.get("cards") for v in views.values() for h in v.get("hands", [])):
            target = (f, views)
            break
    if target is None:
        return {"gate": "ADVERSARY_CONTROL_NEGATIVE", "verdict": "FAIL",
                "reason": "no multi-principal frame found"}
    f, views = target
    actor = f["actor"]
    checks = []

    def run_case(name: str, mutate) -> bool:
        obs = copy.deepcopy(f["observations"])
        by_viewer = {o["viewer"]: o for o in obs}
        mutate(by_viewer)
        for o in obs:
            o["view"] = o["view"] if isinstance(o["view"], str) else json.dumps(o["view"])
        viols = audit_observations(f["seq"], actor, obs, {})
        return len(viols) > 0

    # Case 1: leak a card name into a non-owner hand view.
    viewers = sorted(views)
    v0, v1 = viewers[0], viewers[1]
    leaked_name = None
    for hand in views[v0]["hands"]:
        if hand["owner"] == v0 and hand["cards"]:
            leaked_name = hand["cards"][0]["name"]
            break

    def mut1(by_viewer):
        v = json.loads(by_viewer[v1]["view"])
        for hand in v["hands"]:
            if hand["owner"] == v0:
                hand["cards"].append({"id": 999999, "name": leaked_name or "Mountain"})
        by_viewer[v1]["view"] = json.dumps(v)

    c1 = run_case("non_owner_hand_leak", mut1) if leaked_name else False
    checks.append({"case": "non_owner_hand_leak", "detected": c1})

    # Case 2: expose a facedown identity.
    def mut2(by_viewer):
        v = json.loads(by_viewer[v0]["view"])
        v.setdefault("battlefield", []).append(
            {"id": 999998, "face_down": True, "name": "SecretPlans"})
        by_viewer[v0]["view"] = json.dumps(v)

    c2 = run_case("facedown_exposure", mut2)
    checks.append({"case": "facedown_exposure", "detected": c2})

    # Case 3: inflate own-hand count vs listed cards.
    def mut3(by_viewer):
        v = json.loads(by_viewer[v0]["view"])
        for hand in v["hands"]:
            if hand["owner"] == v0 and hand["cards"]:
                hand["count"] = len(hand["cards"]) + 5
        by_viewer[v0]["view"] = json.dumps(v)

    c3 = run_case("own_hand_count_mismatch", mut3)
    checks.append({"case": "own_hand_count_mismatch", "detected": c3})

    ok = all(c["detected"] for c in checks)
    return {"gate": "ADVERSARY_CONTROL_NEGATIVE", "journal": str(journal_path),
            "frame": f["seq"], "checks": checks,
            "verdict": "PASS" if ok else "FAIL"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider-java", type=Path, required=True,
                    help="WS53-built Ws23ForgeVerticalProvider.java")
    ap.add_argument("--journal", type=Path, action="append", default=[],
                    help="fresh WS53 journal (repeatable)")
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    if not a.journal:
        raise SystemExit("--journal required (at least one fresh WS53 journal)")
    results = [fallback_audit(a.provider_java)]
    for j in a.journal:
        results.append(adversary_positive(j))
    for j in a.journal:
        results.append(adversary_negative(j))
    verdict = "PASS" if all(r["verdict"] == "PASS" for r in results) else "FAIL"
    out = {"schema_version": "commander-lab.ws53-static-gates/1.0.0",
           "gates": results, "verdict": verdict}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    for r in results:
        print(f"WS53 {r['gate']} {r.get('journal', r.get('file', ''))} -> {r['verdict']}")
    print("WS53 STATIC_GATES ->", verdict)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
