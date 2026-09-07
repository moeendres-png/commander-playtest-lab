#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", type=Path, required=True)
    args = ap.parse_args()
    forge_commit = os.environ.get("FORGE_COMMIT", "").strip()
    forge_tree = os.environ.get("FORGE_TREE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", forge_commit):
        raise SystemExit("WS45 FORGE_COMMIT missing/invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", forge_tree):
        raise SystemExit("WS45 FORGE_TREE missing/invalid")
    text = args.runner.read_text(encoding="utf-8")
    text, n_commit = re.subn(r'^FORGE_COMMIT = "[0-9a-f]{40}"$', f'FORGE_COMMIT = "{forge_commit}"', text, count=1, flags=re.MULTILINE)
    text, n_tree = re.subn(r'^FORGE_TREE = "[0-9a-f]{40}"$', f'FORGE_TREE = "{forge_tree}"', text, count=1, flags=re.MULTILINE)
    if n_commit != 1 or n_tree != 1:
        raise SystemExit(f"WS45 runner Forge-lock patch cardinality commit={n_commit} tree={n_tree}")
    args.runner.write_text(text, encoding="utf-8")
    print(f"WS45_NOECHO_RUNNER_FORGE_LOCK=PASS:{forge_commit}:{forge_tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
