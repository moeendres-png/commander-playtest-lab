#!/usr/bin/env python3
"""WS77 transport-remediation runner shim (WS77-owned, qualification-only).

Delegation identical to
candidate-qualification/ws68-forge-provider-transport-remediation/
ws68_runner.py (ws65-verbatim scenario main + pay_combat_cost family +
concession pilot-decline answer chain), EXCEPT the marked WS77 deltas below.
No engine, provider, Decision, or intent semantics change.
Grants no behavior credit by itself (BEHAVIOR_CREDIT=0/107; no credit is
claimed in WS77).

WS77 DELTA-1 (successor EV dir): COMMANDER_LAB_FORGE_PROVIDER_CMD must
reference /home/moeen/ws77-ev (fresh WS77 provider build with the WS68
payCombatCost + concession-offer overlay PLUS the WS77 observation-only
overlay against the verified accepted-pin checkout
/home/moeen/ws77-forge-src-a9a95db) and must contain no old-pin path. Fails
loud otherwise. (/tmp/ws65-forge-src-a9a95db lost its ignored target/ build
output while /tmp stood at 100%; the home checkout is verified HEAD/tree/
clean-identical to the accepted pin; see BUILD_RECEIPT.json.)

WS77 DELTA-2: output journals additionally stamp ws77_runner identity
(additive only; never rewrites proof).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS68_DIR = HERE.parent / "ws68-forge-provider-transport-remediation"
WS65_DIR = HERE.parent / "ws65-forge-rqc3-first-wave"
WS64_DIR = HERE.parent / "ws64-forge-a04-vertical-path-investigation"
WS62_DIR = HERE.parent / "ws62-forge-successor-requalification"
WS53_DIR = HERE.parent / "ws53-forge-convergence-native-progression"
WS48_DIR = HERE.parent / "ws48-forge-v1.0.5"
sys.path.insert(0, str(WS68_DIR))
sys.path.insert(0, str(WS65_DIR))
sys.path.insert(0, str(WS64_DIR))
sys.path.insert(0, str(WS62_DIR))
sys.path.insert(0, str(WS53_DIR))
sys.path.insert(0, str(WS48_DIR))

import ws68_runner as ws68  # noqa: E402,E401  (answer chain: pay_combat_cost + concession pilot-decline)
import ws65_runner as ws65  # noqa: E402,E401  (delegated scenario main)

FORGE_COMMIT = "a9a95db6662c2d28814390a9c0c2f986e39aa8b4"
FORGE_TREE = "2c18327f79e330f2ed167067166ffd42d61b0849"
FORGE_OLD_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
WS77_EV = "/home/moeen/ws77-ev"


def _assert_ws77_runtime() -> None:
    cmd = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "")
    if WS77_EV not in cmd:
        raise SystemExit("WS77_RUNNER_PROVIDER_CMD_NOT_WS77:/home/moeen/ws77-ev missing")
    if FORGE_OLD_COMMIT in cmd or "forge-66caae" in cmd:
        raise SystemExit("WS77_RUNNER_OLD_PIN_ON_CMD_FAIL_CLOSED")
    if "/tmp/ws65-ev" in cmd or "/tmp/ws68-ev" in cmd:
        raise SystemExit("WS77_RUNNER_PREDECESSOR_EV_ON_CMD_FAIL_CLOSED")
    if not os.environ.get("COMMANDER_LAB_FORGE_LANG_DIR"):
        raise SystemExit("WS77_RUNNER_LANG_DIR_MISSING")


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--output", type=Path, required=True)
    known, _rest = ap.parse_known_args()
    _assert_ws77_runtime()
    # Delegate to the WS65 scenario main (as ws68_runner does). Importing
    # ws68_runner above has already installed the WS68 answer chain
    # (pay_combat_cost family + concession pilot-decline) onto the shared
    # ws53/ws62 answer hooks; this module adds no answer semantics.
    rc = ws65.ws62.main()
    try:
        doc = json.loads(known.output.read_text())
    except Exception as ex:
        raise SystemExit(f"WS77_RUNNER_OUTPUT_MISSING:{ex}") from ex
    if (doc.get("forge") or {}).get("commit") != FORGE_COMMIT:
        raise SystemExit(f"WS77_JOURNAL_PIN_MISMATCH:{(doc.get('forge') or {}).get('commit')}")
    if (doc.get("forge") or {}).get("tree") != FORGE_TREE:
        raise SystemExit("WS77_JOURNAL_TREE_MISMATCH")
    doc["ws77_runner"] = ("ws77_runner.py (ws68 verbatim + ws77 ev-dir gate + "
                          "observation-overlay pin gate)")
    doc["ws77_forge"] = {"commit": FORGE_COMMIT, "tree": FORGE_TREE,
                         "checkout": "/home/moeen/ws77-forge-src-a9a95db "
                                     "(verified HEAD/tree/clean = accepted pin)"}
    doc["ws77_old_pin_absent"] = FORGE_OLD_COMMIT not in json.dumps(doc)
    doc["ws77_pilot_declines"] = len(ws68.WS68_PILOT_DECLINES)
    doc["ws77_grants_behavior_credit"] = False
    doc["ws77_behavior_credit"] = "0/107"
    known.output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(f"WS77_RUNNER_PIN_OK:{FORGE_COMMIT[:7]}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
