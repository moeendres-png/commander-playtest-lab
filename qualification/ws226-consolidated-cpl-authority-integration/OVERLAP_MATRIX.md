# WS226 OVERLAP_MATRIX — unique vs overlapping vs stale-manifest paths

Method: `git diff --name-only` between anchor/base/tips (DIRECTLY_VERIFIED).
Base = `48885e8e` (WS223). Anchor = `67db0733`.

## Truly overlapping living paths (same path changed on both sides OR
## manifest coverage claimed by both) — reconcile, never blind-take

| Path | WS223 side | Sibling side | Resolution |
|---|---|---|---|
| `WS17_SHA256SUMS` | UNCHANGED since anchor (stale: misses ws218+ws223) | WS221/WS225 refreshed (covers ws220+ws221+ws225, still misses ws218/ws223/ws222/ws224) | NEITHER wins. Recompute terminal over combined tree (WS221 same-commit invariant). |
| `qualification/SHA256SUMS` | UNCHANGED since anchor (same staleness) | WS221/WS225 refreshed (same partial coverage) | NEITHER wins. Recompute terminal. |
| `qualification/evidence/candidate_result_v1.schema.json` | UNCHANGED | WS221 modified (vocab bind) | Take WS221 bytes (no base conflict). |
| `qualification/evidence/normalized_evidence_v1.schema.json` | UNCHANGED | WS221 modified | Take WS221 bytes. |
| `docs/OPERATIONAL_SIMULATION_POLICY.md` | UNCHANGED | WS221 modified (2-5P truth) | Take WS221 bytes. |
| `docs/architecture/deckbuilding-simulation-separation.md` | UNCHANGED | WS221 modified | Take WS221 bytes. |
| `docs/architecture/xmage-full-game-external-pilots.md` | UNCHANGED | WS221 modified | Take WS221 bytes. |
| `qualification/harness.py` | UNCHANGED | WS221 reject-not-coerce | Take WS221 bytes (removes coercions; verified no PASS→RUNTIME_VERIFIED remains). |
| `qualification/evidence_vocab_v1.py` | ABSENT (new in WS221) | WS221 new | Add exactly. |
| `qualification/evidence/evidence_legacy_map_v1.json` | ABSENT | WS221 new | Add exactly. |
| `src/commander_lab/robustness.py` | UNCHANGED | WS221 lane-text | Take WS221 bytes (message only; tests updated in lockstep). |
| `tests/unit/test_operational_4p_policy.py` | UNCHANGED | WS221 updated | Take WS221 bytes. |
| `src/commander_lab/engine/rules/full_game.py` | WS223 heavily modified (smoke + refactor) | WS224: NO CHANGE (verified) | PRESERVE WS223 bytes exactly. No WS224 overwrite. |
| `research/project-audit/ws220/*` | ABSENT on base | WS221 + WS222 identical (`1a6ffcda` bytes) | Add once, blob-exact; verify WS221 vs WS222 bytes identical before write. |

## Disjoint namespaced additions (no hunk conflict — exact blob transfer)

- WS221 namespace `qualification/ws221-foundation-integrity-source-truth/*`
  (24 files): UNIQUE, add exact.
- WS225 `qualification/reporting/ws225/*` (37) +
  `qualification/aggregate/WS225_ROLLUP_STATUS.json` +
  `tests/qualification/test_ws225_standing.py`: UNIQUE, add exact.
- WS222 `qualification/ws222-g01-authority-reacquisition/*` (72) +
  `tests/qualification/test_ws222_authority.py`: UNIQUE, add exact.
- WS224 `qualification/ws224-hidden-info-name-canary/*` (33+driver) +
  `engine-bridge/.../XmageFullGameNameCanaryTest.java` +
  `tests/unit/test_ws224_name_canary.py`: UNIQUE, add exact.
- WS223 `qualification/ws218-*`, `qualification/ws223-*`,
  `src/.../semantic_replay/*`, locks, workflows: UNIQUE to base, PRESERVE.

## Historical evidence vs living authority

- Historical (frozen, never mutated): `ws218` runs/tapes, `ws223`
  CARDINALITY/ENVIRONMENT receipts, `ws221` P_SRC_01/RED_GATE, `ws222`
  artifacts (CR/Oracle/B&R bytes + receipts), `ws224` CANARY_*/runs/tapes,
  `ws225` FIXTURE_EVIDENCE_TRACE + standings (at WS225 lock), v1 lock,
  GATE_RESULTS FAIL row, COMMON_FIXTURE_MANIFEST v1 refs.
- Living (recomputed on combined tree): `manifests/AUTHORITY_LOCK_v2.json`
  (new current), `ws226` standing views + VALIDATION + OPEN_BLOCKERS +
  G_AF_CURRENT_VIEW, `WS17_SHA256SUMS` + `qualification/SHA256SUMS`
  (terminal repair), `ws226` INTEGRATED_SOURCE_INVENTORY + VALIDATION.
- Generated views (`ws225/*_STANDING.json`): STALE by design after
  WS222/WS223/WS224 publication (G01 FAIL→PASS scoped, S5/S15 + S7 inputs
  changed, AF09 unchanged). Recompute in `ws226/`, never hand-edit `ws225/`.

## Stale-manifest proof (why neither sibling manifest is final)

- WS223 base manifests == anchor bytes (verified: `git diff 67db0733
  48885e8e` lists NEITHER manifest). They miss: 127 WS218/WS223 paths +
  all WS220/WS221/WS222/WS224/WS225 additions → F-CI-02 RED (expected).
- WS225 manifests cover anchor + WS220/WS221/WS225 (98 paths) but miss:
  WS218/WS223 (127), WS222 authority (72), WS224 canary (35) → also RED on
  the combined tree.
- Therefore: transplanting EITHER manifest as final truth fails coverage.
  WS226 recomputes both manifests after all semantic bytes are stable,
  proves byte hashes + coverage + deliberate-mismatch rejection, and keeps
  the same-commit invariant. F-CI-02 must be GREEN terminal.
