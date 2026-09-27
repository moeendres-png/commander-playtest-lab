# WSR20 Validation

Content tip: `088c1a39a05f7809784dedddc760ac442304b0d1` (tests + mapping + packet + results).
Code authority (unchanged bytes): `ef958ee91ac6c9ce0152189f2654bf6e05abf273` / tree `fc3387bf37aab19d780b2939a235309ed32b0492`.
Production-code delta vs audit base: NONE (verified `git diff`: test sources + `forge-protocol2-bridge/wsr20-full107/` docs only).

## Evidence rounds (all from audit-base source)

- 2026-09-23 (wsc2): bridge 213/213 PASS (~844s).
- 2026-09-26 (WSR20): bridge 213/213 PASS (~837s), BUILD SUCCESS all modules.
- 2026-09-27 (WSR20): full bridge 243/243 PASS (213 + R20 v30), BUILD SUCCESS.
- 2026-09-27 (WSR20): R20 v31 31/31 PASS (~408s).
- JDK 17 lane: full bridge 244/244 PASS (213 + R20 v31), BUILD SUCCESS all
  modules, 20:12 min (log bridge-jdk17.log; required by test-build.yaml
  matrix ['17','21']).
- JDK 21 lane: full bridge 243/243 (v30) + R20 v31 class 31/31 green;
  combined with the JDK 17 full run, every test is green on both lanes.

## Mapping reconciliation (machine-checked)

- FULL107_FORGE_MAPPING.json: 107 rows, counts DIRECTLY_VERIFIED 84 /
  TECHNICALLY_CONFORMANT 17 / NOT_RUN_BLOCKED 3 / UNKNOWN 3 (= 107).
- Successor packet: 101 common fixtures (107 minus 3 UNKNOWN minus 3 BLOCKED).
- Lab canonical mapping cross-checked read-only: DIRECT 15 / SUPPORTING 13 /
  UNKNOWN 54 / NOT_RUN_BLOCKED 25 (= 107 @59332671).

## Method gates (all hold)

- No provider selected; no Architecture Freeze claimed; no Lab modification
  (read-only git show/fetch); no new Rules Core; no Java main-code change.
- No existing test weakened, deleted, or relaxed (verified by diff).
- Actual-card runtime for every behavioral DIRECT (real Forge cards, no
  construction/import-only credit, no synthetic mutation, no manual injection).
- Bridge/pilot implement no second Rules engine (all legality/costs/combat/
  triggers/RNG engine-owned; pilot transports offered selections only).
- Forbidden fallbacks proven absent (7 negative families, fail-closed).
- 7P remains fail-closed (PLAYER_COUNT_UNSUPPORTED, R16 negative retained).

## Residuals (explicit, correctly evidenced)

- UNKNOWN (3): HIDDEN_05/06 (face-down exile seam), HIDDEN_11 (shuffle invalidation).
- NOT_RUN_BLOCKED (3): WS05-CMD-MULL-2 (London-tuck seam), HIDDEN_08 (look seam),
  HIDDEN_12 (controlled-player seam). Each names the missing seam + next action.
- TECHNICALLY_CONFORMANT (17): mechanism proven, exact-shape residual named per row.
- Substitutions documented per row (deck/seed/entry-mode vs Lab-bound fixtures);
  same-deck same-seed reruns are successor-packet work, not claimed here.

## Publication readiness

- Branch `wsr20/forge-full107-common-denominator-20260926`, no merge of master,
  no force push, no rebase. Remote pre-push re-verification required.
- Content commit 088c1a39; this VALIDATION.md + FINAL_HANDOFF.md seal the tip.
