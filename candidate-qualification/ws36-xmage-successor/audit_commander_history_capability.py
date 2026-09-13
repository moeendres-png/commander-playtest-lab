#!/usr/bin/env python3
"""Prove whether the pinned XMage exposes a native commander-cast-history loader.

The frozen v1.0.2 tax records require prior command-zone cast counts as starting
state.  They do not authorize replaying fake historical casts.  This audit is
pin-bound and fail-closed: if XMage exposes a genuine state-restoration API, the
terminal blocker is not established and the audit fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGETS = ("WS05-CMD-TAX-2", "WS05-CMD-TAX-4", "WS05-CMD-PARTNER-TAX")
WATCHER_REL = Path("Mage/src/main/java/mage/watchers/common/CommanderPlaysCountWatcher.java")
CARD_REL = Path("Mage/src/main/java/mage/cards/Card.java")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--xmage-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    census = json.loads(args.census.read_text(encoding="utf-8"))
    critical = census["critical_frozen_records"]
    watcher_path = args.xmage_root / WATCHER_REL
    card_path = args.xmage_root / CARD_REL
    watcher = watcher_path.read_text(encoding="utf-8")
    card = card_path.read_text(encoding="utf-8")

    contract_checks = []
    for fixture_id in TARGETS:
        r = critical[fixture_id]
        commanders = r["commander_state"]["commanders"]
        prior = [c for c in commanders if int(c.get("prior_command_zone_cast_count", 0)) > 0]
        ops = [p["operation"] for p in r.get("native_procedure", [])]
        historical_prelude = any(
            "HISTOR" in op or "PRELUDE" in op or "PRIOR_COMMAND" in op or "REPLAY_COMMANDER_CAST" in op
            for op in ops
        )
        contract_checks.append({
            "fixture_id": fixture_id,
            "prior_cast_counts": [
                {"commander_id": c["commander_id"], "count": int(c["prior_command_zone_cast_count"])}
                for c in prior
            ],
            "native_operations": ops,
            "historical_cast_prelude_authorized": historical_prelude,
            "requires_history_in_starting_state": bool(prior) and not historical_prelude,
        })

    watcher_checks = {
        "plays_count_field_private": bool(re.search(r"private\s+final\s+Map<UUID,\s*Integer>\s+playsCount", watcher)),
        "public_read_api_present": "public int getPlaysCount(UUID commanderId)" in watcher,
        "public_player_read_api_present": "public int getPlayerCount(UUID playerId)" in watcher,
        "mutation_is_event_watcher_based": all(token in watcher for token in (
            "event.getType() != EventType.LAND_PLAYED",
            "event.getType() != EventType.SPELL_CAST",
            "event.getZone() != Zone.COMMAND",
            "playsCount.computeIfPresent",
        )),
        "public_or_protected_state_restore_api_present": bool(re.search(
            r"\b(public|protected)\s+[^\n;{]+\b(set|restore|load|put)\w*(?:Play|Cast|Count|History)[A-Za-z0-9_]*\s*\(",
            watcher,
            re.IGNORECASE,
        )),
        "constructor_accepts_count_state": bool(re.search(
            r"CommanderPlaysCountWatcher\s*\([^)]*(Map<|int\s+[^)]*(count|play|cast))",
            watcher,
            re.IGNORECASE,
        )),
    }
    card_checks = {
        "commander_cost_reads_watcher": all(token in card for token in (
            "CommanderPlaysCountWatcher watcher = game.getState().getWatcher(CommanderPlaysCountWatcher.class)",
            "watcher.getPlaysCount(getMainCard().getId())",
        )),
    }

    blocker = (
        all(c["requires_history_in_starting_state"] for c in contract_checks)
        and watcher_checks["plays_count_field_private"]
        and watcher_checks["public_read_api_present"]
        and watcher_checks["mutation_is_event_watcher_based"]
        and not watcher_checks["public_or_protected_state_restore_api_present"]
        and not watcher_checks["constructor_accepts_count_state"]
        and card_checks["commander_cost_reads_watcher"]
    )
    result = {
        "schema_version": "commander-lab.ws36-commander-history-capability/1.0.0",
        "xmage_commit": census["xmage_commit"],
        "xmage_tree": census["xmage_tree"],
        "watcher_path": str(WATCHER_REL),
        "watcher_sha256": sha256(watcher_path),
        "card_path": str(CARD_REL),
        "card_sha256": sha256(card_path),
        "contract_records": contract_checks,
        "watcher_checks": watcher_checks,
        "card_checks": card_checks,
        "forbidden_workarounds": [
            "fabricate SPELL_CAST or LAND_PLAYED historical events",
            "use reflection to mutate private watcher maps",
            "recompute commander tax in Commander Lab",
            "change frozen prior_command_zone_cast_count",
        ],
        "classification": "XMAGE_PROVIDER_DEFECT" if blocker else "NOT_ESTABLISHED",
        "terminal_provider_blocker_established": blocker,
        "required_engine_side_remediation": (
            "Expose a native, state-restoration-safe CommanderPlaysCountWatcher API for restoring per-commander and per-player command-zone cast counts, or a general serialized GameState restoration path that restores those watcher counters without generating historical Rules events."
            if blocker else None
        ),
        "ws36_engine_source_change_allowed": False,
    }
    if not blocker:
        raise SystemExit("WS36_COMMANDER_HISTORY_BLOCKER_NOT_ESTABLISHED")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "classification": result["classification"],
        "terminal_provider_blocker_established": blocker,
        "records": list(TARGETS),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
