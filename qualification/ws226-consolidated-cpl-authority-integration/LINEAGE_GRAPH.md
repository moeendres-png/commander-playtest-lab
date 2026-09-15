# WS226 LINEAGE_GRAPH — divergent branch graph, one combined descendant

Anchor `67db0733` (WS215 ignore ephemeral XMage card-DB bootstrap) is the
last common commit of all four integration lines.

```
67db0733 (WS215)
├── 4f8f13de → 6769efc1 → 779a88b8 → 1a6ffcda (WS220 synthesis: 25 findings,
│   16 successors, autonomy map, action graph, validation, handoff)
│   ├── 189dcfc0 (WS221: vocab-v1 + harness reject-not-coerce + explicit
│   │   legacy map + 2-5P operational source truth + manifest repair S4)
│   │   └── 8b3ab80d (WS225: generated standing + admission S2/S12,
│   │       harness-porting checklist, fair-comparison contract, FULL107 role)
│   └── 1dcfe898 (WS222: G01 authority re-acquisition — byte-exact CR +
│       bounded official Gatherer Oracle for frozen 29 + Commander/B&R +
│       deck-legality + AUTHORITY_LOCK_v2, G01 PASS scoped)
│
└── 2379efcd → 3cdade1d (WS218: semantic replay tape v1 — versioned
    contract, recorder/consumer, 2-5P dual-replay positives, 19-case
    tamper matrix, WS220 R1-R12 impact + machine-readable companions)
    ├── 3e6d170f → dfe1c77e → 48885e8e (WS223: cardinality CI 2-5P smoke +
    │   6P fail-closed + reproducible environment lock + dependency lock +
    │   JDK/container/PYTHONHASHSEED/cache contracts — WS226 BASE, preserved)
    └── f075ab75 (WS224: hidden-info name canary F-HIDE-02/S7 — Java
        XmageFullGameNameCanaryTest 614 lines + Python canary 21 tests +
        evidence namespace + historical disposition; production untouched)
```

WS226 (`ws226/consolidated-cpl-authority-integration-20260915`, from
`48885e8e`) is the first combined descendant: WS223 base + WS220/WS221
provenance + WS225 governance + WS222 authority + WS224 privacy.

Deltas vs anchor (name-only counts, DIRECTLY_VERIFIED via `git diff`):
- `67db0733..48885e8e` (WS223 line): 127 paths (WS218 replay + WS223 CI/env).
- `67db0733..189dcfc0` (WS221): 60 paths (vocab/harness/docs/robustness +
  WS220 research + WS221 namespace + vocab tests).
- `67db0733..8b3ab80d` (WS225): 98 paths (WS221 + 38 reporting/generator/test
  paths + aggregate rollup pointer).
- `67db0733..1dcfe898` (WS222): 96 paths (WS220 research + 72-file
  authority namespace + authority test).
- `3cdade1d..f075ab75` (WS224): 35 paths (Java canary + 33-file namespace +
  Python canary test).

No behavior work starts on another sibling. S6/S8/S9 remain successors.
