#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected 1 occurrence, got {n}')
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', type=Path, required=True)
    args = ap.parse_args()
    p = args.runner
    s = p.read_text(encoding='utf-8')
    s = once(s,
        'def projection(record: dict[str, Any]) -> dict[str, Any]:\n    return {k: record.get(k) for k in PROJECTION_KEYS}\n',
        'def projection(record: dict[str, Any]) -> dict[str, Any]:\n    # WS32 requested-state canonicalization omits keys that are absent from the record.\n    # It must not materialize absent fields as JSON null, or the frozen digest changes.\n    return {k: record[k] for k in PROJECTION_KEYS if k in record}\n',
        'WS32 absent-key canonicalization')
    s = once(s,
        'def normalize_counters(raw: dict[str, int]) -> dict[str, int]:\n    return {str(k).lower(): int(v) for k, v in raw.items() if int(v) != 0}\n',
        'def normalize_counters(raw: dict[str, int], requested: dict[str, int]) -> dict[str, int]:\n    result = {str(k).lower(): int(v) for k, v in raw.items() if int(v) != 0}\n    # Forge Multiset does not retain zero-count entries. Preserve an explicitly requested zero\n    # only after native observation proves there is no nonzero counter of that type.\n    for key, value in requested.items():\n        key = str(key).lower()\n        if int(value) == 0 and key not in result:\n            result[key] = 0\n    return result\n',
        'zero counter normalization')
    s = once(s,
        '        row["counters"] = normalize_counters(got.get("counters") or {})',
        '        row["counters"] = normalize_counters(got.get("counters") or {}, req.get("counters") or {})',
        'counter normalization call')
    p.write_text(s, encoding='utf-8')
    print('WS40_CONSTRUCTION_RUNNER_FIX=PASS')


if __name__ == '__main__':
    main()
