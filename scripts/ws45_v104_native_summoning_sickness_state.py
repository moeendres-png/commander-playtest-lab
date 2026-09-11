#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD = '''        if ("battlefield".equals(s.zone)) b.append("|NoETBTrigs");
        return b.toString();
'''
NEW = '''        if ("battlefield".equals(s.zone)) {
            b.append("|NoETBTrigs");
            if (!s.controlledSinceTurnBegan) b.append("|SummonSick");
        }
        return b.toString();
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()

    p = args.state_java
    text = p.read_text(encoding="utf-8")
    if NEW in text:
        print("WS45_V104_NATIVE_SUMMONING_SICKNESS=ALREADY_APPLIED")
        return 0
    if 'final boolean controlledSinceTurnBegan;' not in text:
        raise SystemExit("WS45_V104_CONTROL_DURATION_FIELD_MISSING")
    if 'controlledSinceTurnBegan = Boolean.parseBoolean(p[11]);' not in text:
        raise SystemExit("WS45_V104_CONTROL_DURATION_DECODE_MISSING")
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"WS45_V104_SUMMONING_SICKNESS_PATCH_TARGET:expected=1:actual={count}")
    text = text.replace(OLD, NEW, 1)
    if 'if (!s.controlledSinceTurnBegan) b.append("|SummonSick");' not in text:
        raise SystemExit("WS45_V104_SUMMONING_SICKNESS_PATCH_INCOMPLETE")
    p.write_text(text, encoding="utf-8")
    print("WS45_V104_NATIVE_SUMMONING_SICKNESS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
