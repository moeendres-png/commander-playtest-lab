#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    path = args.provider
    java = path.read_text(encoding="utf-8")

    old = '''        try {
            match.startGame(game);
            stopReason = "FORGE_GAME_RETURNED";'''
    new = '''        try {
            String ws40EntryMode = System.getenv("COMMANDER_LAB_WS40_ENTRY_MODE");
            String ws40ConstructionOnly = System.getenv("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY");
            if ("1".equals(ws40ConstructionOnly) && "NATURAL_GAME_START".equals(ws40EntryMode)) {
                Ws40SuccessorState.emitNaturalRegistration(game, broker);
            } else if ("NATIVE_STATE_LOAD".equals(ws40EntryMode)) {
                match.startGame(game, () -> Ws40SuccessorState.applyNativeState(game, broker));
            } else {
                match.startGame(game);
            }
            stopReason = "FORGE_GAME_RETURNED";'''
    java = replace_once(java, old, new, "match.startGame hook")

    # Forge's real game/action executor may leave a non-daemon worker alive after a
    # qualification-only NATIVE_STATE_LOAD hook has deliberately stopped the game.
    # At that point runSession has already emitted both the native snapshot and the
    # SESSION_RESULT carrying WS40_CONSTRUCTION_COMPLETE. Explicit process exit is
    # therefore lifecycle cleanup only; it does not bypass construction or validation.
    old_main = '''        runSession(in, out);
    }
}'''
    new_main = '''        runSession(in, out);
        if ("1".equals(System.getenv("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY"))) {
            System.exit(0);
        }
    }
}'''
    java = replace_once(java, old_main, new_main, "construction-only process cleanup")

    path.write_text(java, encoding="utf-8")
    print("WS40_SUCCESSOR_STATE_OVERLAY=PASS")


if __name__ == "__main__":
    main()
