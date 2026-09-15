# WS226 EVIDENCE_RETENTION_IMPACT — what survives, what recomputes, what stays empty

No validated result is dropped. Historical PASS survives only via the
mechanism that originally carried it; integration itself grants zero
behavior credit (`GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`).

## Retained exactly (blob-exact, provenance preserved)

- WS218 semantic replay: `ws218` namespace + `semantic_replay/` sources +
  `test_semantic_replay_tape.py` guards + AF09 PASS (tape lane 2P–5P).
  Impact: none (no replay source touched).
- WS223 cardinality/env: `ws223` namespace + `full_game.py` smoke lane +
  `test_ws223_*` + 2-5P CI + 6P fail-closed + dependency/env receipts +
  JDK/container/PYTHONHASHSEED/cache contracts. Impact: none (preserved
  byte-exact; full_game.py reconciled as WS223-wins).
- WS220 audit: `research/project-audit/ws220/*` retained as provenance
  (25 findings / 16 successors / FULL107 context). Impact: none.
- WS221 vocab/governance: vocab-v1 + harness reject-not-coerce + legacy map
  + operational 2-5P truth + P_SRC_01/RED_GATE/MANIFEST_* evidence.
  Impact: harness now governs ALL future `harness.py run` joins (strict);
  no historical PASS upgraded (demotion-only direction).
- WS222 authority: full `ws222` namespace + CR/Oracle/B&R bytes + receipts +
  tooling + `test_ws222_authority.py` + G01 PASS (scoped: byte-exact CR +
  bounded Gatherer Oracle for frozen 29 + Commander/B&R + deck legality).
  Impact: G01 standing flips FAIL→PASS (scoped) ONLY in WS226 recomputed
  views, from exact v2 trace. No fixture rerun required (impact
  adjudication: zero). Bounded scope NOT generalized.
- WS224 privacy: Java + Python canaries + `ws224` namespace + historical
  disposition (66 advisory, 0 CONFIRMED, 0 rewrites) + UUID oracle + 2P–5P
  matrix + replay privacy. Impact: none (production untouched);
  `ENGINE_INTERNAL_LOG_STATUS` stays UNKNOWN.
- WS225 governance: full `ws225` reporting namespace + generator + 26 tests +
  admission bar/stage contract + porting checklist + fair-comparison +
  FULL107 role + WS219 dry run. Impact: views frozen as history; logic
  reused for WS226 recompute (path-constant-only diff).

## Recomputed (deterministic views, never hand-edited)

- WS226 standing: fresh `XMAGE/FORGE/QUORUNE/ARGENTUM_STANDING_WS226.json` +
  `FIXTURE_EVIDENCE_TRACE_WS226.json` + `FREEZE_READINESS_VIEW_WS226.json` +
  `OPEN_BLOCKERS_WS226.json` + `G01_STATUS_WS226.json` +
  `ADMISSION_ASSESSMENTS_WS226.json` + VALIDATION digest. Generator run
  twice, byte-identical. Expected deltas vs WS225: xmage G01 FAIL→PASS
  (v2 scoped); all other gates identical (S5/S15 + S7 inputs changed but
  verdicts already PASS; AF09 unchanged PASS).
- Manifests: `WS17_SHA256SUMS` + `qualification/SHA256SUMS` recomputed over
  the combined tree (same-commit invariant). Old lines for unchanged files
  remain valid digests; new lines appended for ~200 added files; one stale
  guard-test line (if any) refreshed to current bytes.

## Preserved OPEN UNKNOWNs (not closed by integration)

APNAP, extra-turn ordering, CR800.4 control-effect expiry, damage
thresholds (21 same-commander / split / control), Partner tax/damage,
zone exile/hand/library branches, other 16 G10/AF08 UNKNOWNs; AF01 runtime
handshake, G12/AF11 production topology, Forge replay. FULL107 stays
HISTORICAL_REGRESSION_ARTIFACT / NOT_RUN. No silent promotion.

## Stays empty (by design)

`REQUALIFICATION_REQUIRED`: empty (integration changes no material
semantics). 135-fixture rerun: NOT performed (no impact reason; WS222/WS224
impact adjudications list zero required reruns; WS223 seals stand).
