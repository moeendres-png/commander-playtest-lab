#!/usr/bin/env python3
"""Preserve provider-owned native zero counter observability for WS45 v1.0.4.

Forge stores counters in a Multiset, so an actual native count of zero has no
iterable entry. Cumulative upkeep nevertheless gives Forge a native rules basis
for the age-counter dimension, and getCounters(AGE) returns its native value
(including zero). This patch extends observation only; it never mutates game
state and never reads requested counter keys or card names.

The runner patch is optional so independent readback implementations that
already preserve native zero values do not need to match the historical
construction-runner source text.
"""
from __future__ import annotations

import argparse
from pathlib import Path

JAVA_MARKER = "WS45_V104_NATIVE_ZERO_COUNTER_PROJECTION"
RUNNER_MARKER = "WS45_V104_PRESERVE_NATIVE_ZERO_COUNTERS"

OLD_JAVA = '''    private static String counterJson(Card c) {
        StringBuilder b = new StringBuilder("{");
        boolean first = true;
        List<Map.Entry<CounterType,Integer>> entries = new ArrayList<>();
        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getElement(), e.getCount()));
        entries.sort(Comparator.comparing(e -> e.getKey().toString()));
        for (var e : entries) {
            if (!first) b.append(',');
            first = false;
            b.append(Ws23ForgeVerticalProvider.esc(e.getKey().toString())).append(':').append(e.getValue());
        }
        return b.append('}').toString();
    }'''

NEW_JAVA = '''    private static String counterJson(Card c) {
        StringBuilder b = new StringBuilder("{");
        boolean first = true;
        List<Map.Entry<CounterType,Integer>> entries = new ArrayList<>();
        for (var e : c.getCounters().entrySet()) entries.add(Map.entry(e.getElement(), e.getCount()));

        // WS45_V104_NATIVE_ZERO_COUNTER_PROJECTION: Forge's Multiset omits zero-count
        // entries, but cumulative upkeep is a native rules fact that makes AGE an
        // observable counter dimension. Read the native count directly; do not consult
        // requested counter keys and do not create a counter in game state.
        if (c.hasKeyword(forge.game.keyword.Keyword.CUMULATIVE_UPKEEP)
                && c.getCounters(forge.game.card.CounterEnumType.AGE) == 0) {
            entries.add(Map.entry(forge.game.card.CounterEnumType.AGE, 0));
        }

        entries.sort(Comparator.comparing(e -> e.getKey().toString()));
        for (var e : entries) {
            if (!first) b.append(',');
            first = false;
            b.append(Ws23ForgeVerticalProvider.esc(e.getKey().toString())).append(':').append(e.getValue());
        }
        return b.append('}').toString();
    }'''

OLD_RUNNER = '''def counters(v: dict[str, Any] | None) -> dict[str, int]:
    return {str(k).lower(): int(n) for k, n in (v or {}).items() if int(n) != 0}
'''

NEW_RUNNER = '''def counters(v: dict[str, Any] | None) -> dict[str, int]:
    # WS45_V104_PRESERVE_NATIVE_ZERO_COUNTERS: preserve every counter dimension
    # the native provider actually emitted, including zero. Never synthesize keys
    # from the requested semantic object.
    return {str(k).lower(): int(n) for k, n in (v or {}).items()}
'''


def patch_once(text: str, old: str, new: str, marker: str, label: str) -> tuple[str, bool]:
    if marker in text:
        return text, False
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS45 {label} patch target count {count}, expected 1")
    return text.replace(old, new, 1), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-java", type=Path, required=True)
    ap.add_argument("--runner", type=Path)
    args = ap.parse_args()

    java = args.state_java.read_text(encoding="utf-8")
    java, java_changed = patch_once(java, OLD_JAVA, NEW_JAVA, JAVA_MARKER, "native zero-counter Java")
    if java_changed:
        args.state_java.write_text(java, encoding="utf-8")
        print("WS45_V104_NATIVE_ZERO_COUNTER_JAVA=PASS")
    else:
        print("WS45_V104_NATIVE_ZERO_COUNTER_JAVA=ALREADY_APPLIED")

    if args.runner is not None:
        runner = args.runner.read_text(encoding="utf-8")
        runner, runner_changed = patch_once(runner, OLD_RUNNER, NEW_RUNNER, RUNNER_MARKER, "native zero-counter runner")
        if runner_changed:
            args.runner.write_text(runner, encoding="utf-8")
            print("WS45_V104_NATIVE_ZERO_COUNTER_RUNNER=PASS")
        else:
            print("WS45_V104_NATIVE_ZERO_COUNTER_RUNNER=ALREADY_APPLIED")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
