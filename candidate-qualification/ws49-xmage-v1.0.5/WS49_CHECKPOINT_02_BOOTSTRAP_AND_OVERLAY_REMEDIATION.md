# WS-49 CHECKPOINT 02 — BOOTSTRAP + OVERLAY REMEDIATION

## Source Lock

- Workstream: `WS-49 — XMAGE v1.0.5 COMPLETE SUCCESSOR PROVIDER QUALIFICATION`
- Branch: `ws49/xmage-v1.0.5-successor-qualification`
- Draft PR: `#164` (must remain Draft and unmerged)
- Immutable WS47 commit: `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`
- Immutable WS47 root tree: `f596c54d2cb229b9827c6c94a278175e8312c65c`
- Immutable WS47 namespace tree: `12af73695c801a42a0193ee895d5fc0843d16b0c`
- WS47 materialization SHA-256: `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`
- XMage commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- XMage tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
- Historical successor runtime credit imported: `0`

## First Scoped Runs

### Bootstrap / impact

- run: `34242803881`
- job: `102117016723`
- artifact: `10063582299`
- artifact digest: `sha256:d4fd78dd67521e7d447cd56c77cca918b96069262b47b2eab18bd61c162e36bb`

Fresh steps completed before the failure:

- exact WS47 commit/tree/namespace-tree/materialization: PASS
- exact WS44 predecessor lock: PASS
- exact XMage commit/tree: PASS
- independent provider denominator: PASS `107/107`
- all requested-state digests recomputed equal: PASS
- historical credit imported: `0`
- exact v1.0.4 -> v1.0.5 impact reconciliation: PASS
- obligation changes: `0`
- requested-state changes: exactly `["WS05-MP-BLOCK-4"]`

First failure:

`KeyError: 'WS05-MP-ELIM-2'`

This was a WS49 audit-harness identity defect. It is not an XMage runtime failure.

### Full107 construction

- run: `34242804090`
- job: `102117017465`
- artifact: `10063883822`
- artifact digest: `sha256:4db4a5e9a182a18d03aaab1993b734c15c082c6f97ed15df39cd2c98445942e1`

Fresh steps completed before the failure:

- exact WS47 lock: PASS
- exact XMage source lock: PASS
- independent 107 denominator/digests: PASS
- inherited qualification overlays through WS46 construction overlay: PASS

First failure:

`WS49_REMEDIATION_ANCHOR_MISMATCH:elimination-reason-key:count=0`

Build and runtime were not reached. This was a brittle WS49 source-patcher anchor, not an engine runtime result.

## Exact Prior-19 Identity Reconstruction

The authoritative WS46 artifact/content lock and immutable-shape audit establish exactly 19 prior failure identities:

### NATURAL_GAME_START — 7

1. `PLAYER_COUNT_2P`
2. `PLAYER_COUNT_3P`
3. `PLAYER_COUNT_4P`
4. `PLAYER_COUNT_5P`
5. `PILOT_MULLIGAN`
6. `WS05-CMD-MULL-2`
7. `WS05-CMD-MULL-4`

### Face-down exile — 2

8. `HIDDEN_05`
9. `HIDDEN_06`

### Library ranges — 2

10. `HIDDEN_10`
11. `HIDDEN_11`

### Extra turns — 2

12. `WS05-MP-TURN-3`
13. `WS05-MP-TURN-5`

### Elimination trigger — 6

14. `WS05-MP-ELIM-OWNED-3`
15. `WS05-MP-ELIM-CONTROL-3`
16. `WS05-MP-ELIM-STACK-3`
17. `WS05-MP-ELIM-PRIO-3`
18. `WS05-MP-ELIM-TURN-3`
19. `WS05-MP-ELIM-5`

`WS05-MP-BLOCK-4` is not one of the prior 19. It is the sole v1.0.5 requested-state delta and must be exercised freshly as part of the complete 107 denominator.

## Persisted Remediation

### `apply_ws49_native_remediation.py`

The elimination schema repair now uses four individually counted fail-closed substitutions instead of a formatting-sensitive whole-block anchor:

- `condition` -> source-authoritative `reason` input key;
- `life_total_0` validation remains exact;
- failure label updated to WS49;
- readback key `condition` -> `reason`.

The native construction boundary check `life == 0 && !hasLost()` remains unchanged. WS49 does not pre-run state-based loss or fabricate elimination.

Existing WS49 remediations retained:

- exact attacking-player binding for combat readback; no active-player / player-order / first-match fallback;
- immutable extra-turn fields remain `sequence` / `source`; superseded `resolution_sequence` / `source_object` rejected;
- native face-down exile application and independent native face-down readback.

### Fresh prior-19 v1.0.5 audit

Added:

`candidate-qualification/ws49-xmage-v1.0.5/audit_prior19_v105.py`

It fail-closes unless:

- the denominator is exactly the 19 identities above;
- all 19 exist in both immutable v1.0.4 and v1.0.5;
- every one of the 19 requested-state digests is unchanged v1.0.4 -> v1.0.5;
- the v1.0.5 requested-state digest recomputes from the materialized state projection;
- the seven natural-start records still contain the real Rograkh + Mountain x99 deck shape;
- HIDDEN_05/06 retain Demonic Tutor as the same P2-owned/P2-controlled face-down exile object;
- HIDDEN_10/11 retain the source-authoritative zero-based ordered library range shapes;
- TURN-3/TURN-5 retain the two `sequence`/`source` extra-turn rows and contain no `resolution_sequence`;
- all six elimination triggers are exactly `{player, reason: life_total_0}` and contain no `condition`.

No prior runtime PASS is imported by this audit.

## Exact-Head Workflow Repair

Both scoped workflows now checkout and attest:

`${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}`

and fail unless `git rev-parse HEAD` equals that expected exact qualification head.

This eliminates accidental use of a synthetic GitHub PR merge commit as exact-head qualification evidence.

## Gate State

- G49-01 source lock: source-level PASS; fresh exact-head scoped re-attestation pending rerun
- G49-02 XMage source lock: source-level PASS; build/runtime pending rerun
- G49-03 zero historical credit: PASS
- G49-04 independent 107 reconstruction: PASS in first scoped bootstrap; exact-head rerun pending
- G49-05 exact v1.0.4 -> v1.0.5 impact: PASS in first scoped bootstrap; exact-head rerun pending
- G49-06 native invariants: PARTIAL / NOT GRANTED
- G49-07 full107 construction: NOT GRANTED
- G49-08 independent normalization: NOT_RUN
- G49-09 behavior 107/107: NOT_RUN
- G49-10 AF04/05/06/08/09 + CARD_02: NOT_RUN
- G49-11 hidden adversarial: NOT_RUN
- G49-12 deterministic Rules-RNG/replay: NOT_RUN
- G49-13 unsupported/fallback production paths = 0: NOT PROVEN
- G49-14 final sealed evidence: NOT_RUN

`construction_credit = 0/107`

`behavior_credit = 0/107`

`XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

## Exact Next Action

Execute/inspect the new exact-head Bootstrap and Full107 Construction runs. If either fails, remediate the first genuine in-scope harness/provider/native-engine blocker without weakening immutable WS47 semantics. Continue automatically until a complete fresh 107/107 construction run is obtained, then execute a separate independent native-readback normalization before any construction PASS is granted.
