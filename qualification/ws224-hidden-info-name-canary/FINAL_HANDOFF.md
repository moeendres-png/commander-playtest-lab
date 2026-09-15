# WS224 FINAL_HANDOFF — Hidden-Information Name Canary & Replay Leak Hardening

## Source Lock

Repo `moeendres-png/commander-playtest-lab`, branch
`ws224/hidden-info-name-canary-20260915`, audit base `3cdade1d` (tree
`0a249bf4`), read-only WS220 audit `1a6ffcda` (git-show only).
`ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Work Completed

Closed WS220 F-HIDE-02/S7 for the XMage lane: the UUID-only oracle is now
supplemented by an independent hidden-NAME canary dimension (Oracle A:
per-frame hidden-exclusive live card names, 2P–5P; Oracle B: synthetic
`WS224_CANARY_*` sentinels over Python projection/digest/transcript/error/
replay layers). All 16 leak surfaces inventoried before mutation
(`LEAK_SURFACE_INVENTORY.md` S01–S16); canary rules sealed (`CANARY_CONTRACT.md`).
Fresh-JVM production-boundary proof (4P, 24 decisions, all seats, 3 probes),
fresh 35-step tape record + replay + tamper at this HEAD, and a read-only
66+4 historical scan with quarantine/advisory disposition (0 rewrites).
No production file touched; no behavior credit.

## New Findings

1. The name dimension holds: 240/240 live frames + 24/24 boundary frames show
   zero hidden-exclusive name leakage across observations, legal labels/
   metadata, target projections, transcripts, errors, and replay outputs.
2. A naive cumulative-transcript scan DOES fire — on other actors' entitled
   history, not on leaks. Adjudicated as privileged-history conflation; the
   at-birth scan rule (request pre-submit, accepted/failure post-submit, actor
   bound) replaced it and passes. Full transcripts are actor-mixed privileged
   evidence, same as historical `native_transcript`s.
3. `ILLEGAL_ACTION` echoes attacker-supplied ids only, never the allowed set:
   no error oracle exists. Engine-text-bearing diagnostics were clean in all
   runs; engine-internal GameLog history stays honestly UNKNOWN.
4. Historical artifacts: 0 CONFIRMED leaks, 0 UUID violations; all 66 carry
   per-actor entitled offered labels (actor-mixed privileged; advisory applies).

## Changes

- NEW `engine-bridge/src/test/.../XmageFullGameNameCanaryTest.java` (4 tests)
- NEW `tests/unit/test_ws224_name_canary.py` (21 tests)
- NEW `qualification/ws224-hidden-info-name-canary/**` (contract, inventory,
  per-count + per-surface evidence, driver + run outputs incl. fresh 4P tape)
- Production `src/**` / `engine-bridge/src/main/**`: UNTOUCHED.

## Tests / Evidence

- Java canary 4/4; Java UUID oracle 1/1; Python canary 21/21; neighbors
  (`semantic_replay_tape`, `variable_player`) green; driver 3/3 phases; ruff clean.
- Evidence classes: live-execution proofs `DIRECTLY_VERIFIED`; source reads
  `CODE_DERIVED`; historical rows provenance + WS224 classifications;
  GameLog history `UNKNOWN`. Nothing upgraded.

## PASS / FAIL / UNKNOWN

- `WS224_HIDDEN_INFO_NAME_CANARY`: PASS (11 gates PASS, grant-window PASS-BOUNDED).
- Engine-internal log contents: UNKNOWN (honest). Forge: out of scope (F-HIDE-03).

## Remaining Blockers

None for WS224. Successors may (a) engineer a live D2 window run to exercise
the entitled-visible path, (b) re-apply the oracles after any redactor/
projection change, (c) extend the canary to Forge when it requalifies.

## Outputs

`qualification/ws224-hidden-info-name-canary/` (≈25 files incl. `runs/`
machine outputs + fresh `ws224-tape-4p.json`).

## Dependencies Unblocked

S7/F-HIDE-02 closed for the XMage lane; replay-privacy (R11) name-blindness
caveat lifted for the tape lane; historical-artifact question answered with
disposition instead of UNKNOWN.

## Exact Next Action

Rerun driver + impacted suites once on the final tree, commit, mark state
COMPLETE with validated_head, safe_push dry-run then actual with
`--expected-audit-base-ref ws218/semantic-replay-tape-v1-20260915`, fetch,
verify remote HEAD/TREE equality, final handoff.
