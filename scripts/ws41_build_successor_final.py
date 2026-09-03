#!/usr/bin/env python3
"""Terminal WS-41 builder entrypoint bound to the freshly reverified Wizards rules link."""
from __future__ import annotations

import argparse
from pathlib import Path

import ws41_build_successor as impl

# Fresh direct probe of https://magic.wizards.com/en/rules on 2026-09-04.
# The currently linked filename advanced to 20260819, while the bytes remain
# the Comprehensive Rules effective August 7, 2026 with the same frozen SHA.
impl.CURRENT_CR_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt"
impl.CURRENT_CR_EFFECTIVE = "2026-08-07"
impl.CURRENT_CR_SHA256 = "4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=impl.ROOT / "qualification" / "ws41")
    args = ap.parse_args()
    impl.build(args.out if args.out.is_absolute() else impl.ROOT / args.out)
