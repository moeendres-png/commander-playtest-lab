#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, got {n}")
    return text.replace(old, new, 1)


def patch_runner(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    old = '''        if normalized != requested or nd != rd:\n            raise AssertionError(f"REQUESTED_NATIVE_STATE_MISMATCH:{record['fixture_id']}:requested={canonical(requested)}:normalized={canonical(normalized)}")\n'''
    new = '''        if normalized != requested or nd != rd:\n            # Diagnostic only: expose the raw native semantic-object observation before any\n            # provider-neutral normalization. This does not change requested or normalized state.\n            raw_cards = native.get("cards") or []\n            raise AssertionError(\n                f"REQUESTED_NATIVE_STATE_MISMATCH:{record['fixture_id']}:"\n                f"requested={canonical(requested)}:normalized={canonical(normalized)}:"\n                f"raw_native_cards={canonical(raw_cards)}"\n            )\n'''
    s = once(s, old, new, "raw revealed mismatch diagnostic")
    path.write_text(s, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", type=Path, required=True)
    args = ap.parse_args()
    patch_runner(args.runner)
    print("WS40_V103_RAW_REVEALED_DIAGNOSTIC_PATCH=PASS")


if __name__ == "__main__":
    main()
