#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()
    p = args.state_java
    s = p.read_text(encoding="utf-8")
    old = '                GameEntity defender = target(game, dec(p[2]));\n'
    new = '                GameEntity defender = (GameEntity) target(game, dec(p[2]));\n'
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"combat target type bridge: expected 1 occurrence, got {n}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print("WS40_V103_COMBAT_TARGET_TYPE_BRIDGE=PASS")


if __name__ == "__main__":
    main()
