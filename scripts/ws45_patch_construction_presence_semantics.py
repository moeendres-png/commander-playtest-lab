#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD_PROJECTION = '    return {k: record.get(k) for k in PROJECTION_KEYS}\n'
NEW_PROJECTION = '    return {k: record[k] for k in PROJECTION_KEYS if k in record}\n'
OLD_NORMALIZED = '            normalized = normalize(record, evidence)\n'
NEW_NORMALIZED = '            normalized = {k: v for k, v in normalize(record, evidence).items() if k in record}\n'
OLD_PROTOCOL_FAILURE = '        raise RuntimeError(f"provider construction failed {record[\'fixture_id\']} rc={rc} created={created is not None} raw={raw is not None} result={result is not None} stderr={stderr[-6000:]}")\n'
NEW_PROTOCOL_FAILURE = '        result_payload = None if result is None else result.get("payload")\n        raise RuntimeError(f"provider construction failed {record[\'fixture_id\']} rc={rc} created={created is not None} raw={raw is not None} result={result is not None} result_payload={canon(result_payload)} messages={messages} stderr={stderr[-6000:]}")\n'


def patch_once(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'WS45 {label} patch target count {count}, expected 1')
    return text.replace(old, new, 1), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', type=Path, required=True)
    args = ap.parse_args()
    text = args.runner.read_text(encoding='utf-8')

    changed = False
    text, applied = patch_once(text, OLD_PROJECTION, NEW_PROJECTION, 'projection')
    changed |= applied
    text, applied = patch_once(text, OLD_NORMALIZED, NEW_NORMALIZED, 'normalized')
    changed |= applied
    text, applied = patch_once(text, OLD_PROTOCOL_FAILURE, NEW_PROTOCOL_FAILURE, 'protocol diagnostic')
    changed |= applied

    if changed:
        args.runner.write_text(text, encoding='utf-8')
        print('WS45_CONSTRUCTION_PRESENCE_AND_DIAGNOSTICS=PASS')
    else:
        print('WS45_CONSTRUCTION_PRESENCE_AND_DIAGNOSTICS=ALREADY_APPLIED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
