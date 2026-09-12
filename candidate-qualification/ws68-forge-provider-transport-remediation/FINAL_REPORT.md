# WS68 — Forge Provider Transport Remediation — Final Report

- Branch: `ws68/forge-provider-transport-remediation-20260912`
- CPL audit base: `7796619e69b0434cd232de8335ff5cab3c5d08e5` / tree `48ec3eafcca668f3fa165e3977af5836b3add059`
- Code checkpoint (executable changes): `903b3f4a6ff9f5228a3d8210429d5a0689383ec9`
- Accepted Forge pin (only engine pin): `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / `2c18327f79e330f2ed167067166ffd42d61b0849` (read-only checkout `/tmp/ws65-forge-src-a9a95db`, verified HEAD/tree/clean; no Forge edits)
- Provider build: `/tmp/ws68-ev`, digest `c4fb2245…` (state `b6b0870f…` and transport `761e451a…` match WS64/WS65)
- Terminal verdict: **WS68_PROVIDER_REMEDIATION=PASS** (both transports remediated and requalified; 0 behavior credit by design)

## Source Lock

CPL worktree `/home/moeen/code/ws68-forge-provider-transport-remediation`, branch
above, audit base `7796619e` (tree `48ec3ea…`, tracked tree clean; only the WS68
candidate-qualification dir untracked at lock). Forge checkout reused from prior
qualification (no new 58k-file checkout): HEAD `a9a95db`, tree `2c18327f…`,
`git status` clean before and after all runs (only ignored `target/` from the
required `mvn -o` seam-suite run). RQ-C3 authority: WS65 materialization
(`WS65_SCENARIO_AUTHORITY.json`, scenarios E01/G04/A04/C01).

## Work Completed

1. **payCombatCost authoritative transport** (`ws68_provider_overlay.py` chained
   after the WS64 overlay): Human-parity delegation to
   `PlaySpellAbility.payCostDuringAbilityResolve` with the `NoFreeCombatCostHandling`
   zero-cost mirror, null-guards, and one external PAY/DECLINE frame carrying
   only engine-computed identities. Rules Core owns applicability, amount,
   mana legality, and result throughout.
2. **Native concession Decision transport** (same overlay): conditional offer in
   `autoPassCancel` (every player, every cleanup, `canConcede()`-only
   authorization — never priority-coincident) with two-phase execution at the
   player's next priority (engine-tolerated venue). Submission exclusively via
   the `concede()` seam; 800.4 cleanup engine-owned.
3. **Harness** (`ws68_runner.py`, WS65-verbatim + `pay_combat_cost` family +
   concession pilot standing instruction + `/tmp/ws68-ev` pin gate): offered-
   options-only matching, fail-closed on zero/multi-match, pilot-DECLINE for
   unscripted concession offers (documented pilot behavior, not a provider default).
4. **Qualification on the final build**: E01 PAY + E01 DECLINE + G04 + A04 +
   C01 fresh-process sessions (accepted pin, hidden PASS everywhere) and the
   Ws59 engine seam suites 9/9 via `mvn -o`.
5. **New engine defect packet**: sweep re-entrancy CME (synchronous concede
   inside the cleanup player-sweep), with journal demonstration and source
   chain; engine-side remediation scoped out of WS68.

## New Findings

- F1. `payCombatCost` fully transports through existing mana/confirm machinery:
  one PAY frame + two native Island taps pays `{2}`; DECLINE removes exactly
  the taxed attacker with zero taps and no side effects on parallel attackers.
- F2. The CLEANUP `autoPassCancel` sweep iterates the LIVE player list, so no
  conformant provider can execute a synchronous concede there (CME). Two-phase
  (accept at cleanup, execute at next priority) is the conformant shape; the
  engine tolerates priority-time concession explicitly (`PhaseHandler:1058`).
- F3. Concession offers are cheapest at turn boundaries (200 offers in a
  51-turn game, all declined-or-accepted without engine error); the pilot
  standing instruction scales without script maintenance.
- F4. Post-leave 800.4a is journal-visible: owned objects vanish from all zones
  while stolen permanents persist; zero post-loss frames for the conceder.
- F5. `EXECUTED` identity must be captured pre-seam (post-seam pid lookup
  yields PX after list removal) — fixed before final qualification.

## Changes

- Committed code (checkpoint `903b3f4a`): `ws68_provider_overlay.py`,
  `ws68_build.sh`, `ws68_runner.py`, 5 scenario intents, bootstrap state.
- Evidence (this report + `RQ-C3-*/` journals/receipts/adjudications,
  `WS68_SWEEP_REENTRANCY/` CME demo, remediation docs, matrices, receipt).
- No Forge edits. No shared-script edits. No other workstream files touched.
  Shared provider surfaces byte-invariant (digests match WS64/WS65).

## Tests / Evidence

- E01 PAY (628 frames): tax paid natively, 2/2 damage, life 38/38.
- E01 DECLINE (626 frames): declined attacker removed, 40/38 split, zero taps.
- G04 (1907 frames): 200 offers, 199 declines, ACCEPT t50 CLEANUP, EXECUTED
  P1, 3-player continuation, 800.4a correction.
- A04 (1379 frames): P1P1=8, HS-first ordering intact.
- C01 (975 frames): pitch route, life 39, hidden PASS.
- Ws59 suites: 9/9 (A04 3/3, C01 2/2, G04 4/4) on the accepted pin.
- Static gates: overlay post-conditions + build greps + handshake ×3 + pin gates.
- Labels used: only DIRECTLY_VERIFIED, CODE_DERIVED, TECHNICALLY_CONFORMANT,
  EXTERNALLY_RULE_VALIDATED, HARNESS, UNKNOWN. Never RUNTIME_VERIFIED.

## PASS / FAIL / UNKNOWN

**WS68_PROVIDER_REMEDIATION=PASS** — both WS65-unsupported surfaces remediated
in-transport and requalified end-to-end with zero Rules-logic added and zero
behavior credit claimed. Terminal post-behavior blocks are `HARNESS`
(intent exhaustion), never transport or engine failures (except the documented
CME demo, class `ENGINE_DEFECT`, superseded by the two-phase design).

## Remaining Blockers

- Engine sweep re-entrancy (CME) needs engine-side remediation for synchronous
  single-phase concession (out of scope; workaround qualified).
- Non-mana combat costs fail closed (no card-level regression available).
- Block-cost card path shares the method but has no card regression in decks.
- Full107 NOT_RUN. No architecture freeze. No production provider selection.

## Outputs

`candidate-qualification/ws68-forge-provider-transport-remediation/`:
`PAYCOMBATCOST_REMEDIATION.md`, `CONCESSION_REMEDIATION.md`,
`IMPACT_MATRIX.json`, `BUILD_RECEIPT.json`, `FINAL_REPORT.md` (this file),
`WORKSTREAM_STATE.yaml`, `ws68_provider_overlay.py`, `ws68_build.sh`,
`ws68_runner.py`, intents, `RQ-C3-{E01,G04,A04,C01}/`, `WS68_SWEEP_REENTRANCY/`.

## Dependencies Unblocked

- E01 and G04 re-entry prerequisites READY for a future crediting wave
  (behavior evidence complete through the qualified transport).
- Precise engine defect packet (sweep CME) for downstream engine remediation.
- Reusable WS68 provider/runner for remaining-scenario requalification.

## Exact Next Action

Coordinator: accept WS68 PASS (remediation/requalification only, 0/107 credit);
schedule E01/G04 behavior-credit re-entry and engine-side sweep-hardening as
follow-ups; do not start Full107, Freeze, or provider selection from WS68.

---
WS68_PROVIDER_REMEDIATION=PASS
PAYCOMBATCOST_TRANSPORT=PASS
CONCESSION_TRANSPORT=PASS
E01_REENTRY_PREREQUISITE=READY
G04_CONCESSION_REENTRY_PREREQUISITE=READY
ACCEPTED_FORGE_PIN=a9a95db6662c2d28814390a9c0c2f986e39aa8b4
BEHAVIOR_CREDIT=0/107
FULL107=NOT_RUN
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
