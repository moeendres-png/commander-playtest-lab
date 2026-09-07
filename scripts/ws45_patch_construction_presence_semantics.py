#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD_PROJECTION = '    return {k: record.get(k) for k in PROJECTION_KEYS}\n'
NEW_PROJECTION = '    return {k: record[k] for k in PROJECTION_KEYS if k in record}\n'
OLD_NORMALIZED = '            normalized = normalize(record, evidence)\n'
NEW_NORMALIZED = '            normalized = {k: v for k, v in normalize(record, evidence).items() if k in record}\n'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', type=Path, required=True)
    args = ap.parse_args()
    text = args.runner.read_text(encoding='utf-8')

    if NEW_PROJECTION in text and NEW_NORMALIZED in text:
        print('WS45_CONSTRUCTION_PRESENCE_SEMANTICS=ALREADY_APPLIED')
        return 0
    if text.count(OLD_PROJECTION) != 1:
        raise SystemExit(f'WS45 projection patch target count {text.count(OLD_PROJECTION)}, expected 1')
    if text.count(OLD_NORMALIZED) != 1:
        raise SystemExit(f'WS45 normalized patch target count {text.count(OLD_NORMALIZED)}, expected 1')

    text = text.replace(OLD_PROJECTION, NEW_PROJECTION, 1)
    text = text.replace(OLD_NORMALIZED, NEW_NORMALIZED, 1)
    args.runner.write_text(text, encoding='utf-8')
    print('WS45_CONSTRUCTION_PRESENCE_SEMANTICS=PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
