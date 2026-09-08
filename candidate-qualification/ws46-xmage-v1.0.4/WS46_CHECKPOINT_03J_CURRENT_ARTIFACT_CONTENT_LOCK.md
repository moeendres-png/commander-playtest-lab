# WS-46 CHECKPOINT 03J — CURRENT FULL107 ARTIFACT CONTENT LOCK

## Purpose

Correct the failure taxonomy previously transcribed in Checkpoints 03H/03I by binding directly to the exact `WS46_FULL107_CONSTRUCTION_PROBE.json` contained in the authoritative GitHub Actions artifact for run `34221583745`.

This checkpoint supersedes the 03H/03I failure-list prose. It does not modify WS-44 and grants no construction/provider PASS credit.

## Exact Actions / Artifact Lock

- workflow: `WS46 XMage v1.0.4 Full107 Construction v2`
- run: `34221583745`
- job: `102045705813`
- tested Commander-Lab head: `d5f534f7014e78b272983b0548e3c5ce266fde35`
- artifact id: `10054580582`
- artifact name: `ws46-v104-construction-v2-d5f534f7014e78b272983b0548e3c5ce266fde35`
- artifact ZIP digest: `sha256:a355642467116934642344b95e29de5cdcca5e73a899e001cccc64e5b0a196a1`
- `WS46_FULL107_CONSTRUCTION_PROBE.json` SHA-256 from sealed `SHA256SUMS`: `79867549f065e8f2c457b93c90fac56e3e9ac38aa88cc2c83da2dea602328061`

The job log independently confirms exact WS44/XMage locks, 107-record denominator reconstruction, exact XMage build PASS, bridge tests PASS (`60` tests, `0` failures/errors/skips), and final construction counts `88 PASS / 19 FAIL`.

## Authoritative Current 19 Failures

### Natural-game-start scenario configuration — 7

1. `PLAYER_COUNT_2P` — `INVALID_SCENARIO: text natural_library_card_name`
2. `PLAYER_COUNT_3P` — same
3. `PLAYER_COUNT_4P` — same
4. `PLAYER_COUNT_5P` — same
5. `PILOT_MULLIGAN` — same
6. `WS05-CMD-MULL-2` — same
7. `WS05-CMD-MULL-4` — same

### Hidden-information face-down native construction — 2

8. `HIDDEN_05` — `INVALID_SCENARIO: face_down only applies to battlefield`
9. `HIDDEN_06` — same

### Knowledge/library-range native construction — 2

10. `HIDDEN_10` — `WS46_KNOWLEDGE_LIBRARY_RANGE_INVALID:P1:0:2`
11. `HIDDEN_11` — `WS46_KNOWLEDGE_LIBRARY_RANGE_INVALID:P2:0:2`

### Extra-turn resolution-sequence schema binding — 2

12. `WS05-MP-TURN-3` — `WS46_JSON_INTEGER_REQUIRED:resolution_sequence`
13. `WS05-MP-TURN-5` — same

### Elimination-condition schema/native derivation — 6

14. `WS05-MP-ELIM-OWNED-3` — `WS46_JSON_STRING_REQUIRED:condition`
15. `WS05-MP-ELIM-CONTROL-3` — same
16. `WS05-MP-ELIM-STACK-3` — same
17. `WS05-MP-ELIM-PRIO-3` — same
18. `WS05-MP-ELIM-TURN-3` — same
19. `WS05-MP-ELIM-5` — same

## Counts

- denominator: `107`
- `NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION`: `88`
- `FAIL_CLOSED_NATIVE_CONSTRUCTION`: `19`
- deferred: `0`
- unsupported dimensions: `{}`
- historical PASS imported: `false`
- request echo accepted as proof: `false`

## Adjudication

The current failures are remediable construction/translation/native-readback defects, not terminal Rules-Core failures. No requested-state field may be copied into observed state merely to clear them.

The remediation must be bound to the exact immutable v1.0.4 requested-state shapes before implementation:

- natural start: translate its real deck/commander/start configuration into a valid XMage scenario and prove state at first external decision boundary;
- `face_down`: preserve the actual target zone semantics and derive face-down state from native XMage state;
- `known_library_ranges`: bind exact range representation to native library/knowledge state;
- `resolution_sequence`: accept only the immutable WS44 representation and normalize from native `GameState.turnMods` order;
- `condition`: accept only the immutable WS44 representation and derive the satisfied/unsatisfied elimination precondition from native player/SBA state.

## Credit State

- fresh construction runtime: `88/107`
- construction PASS: `NOT GRANTED`
- independent construction normalization: `NOT GRANTED`
- behavior runtime: `0/107`
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`
- historical successor runtime credit imported: `0`
- AF07: not granted
- Architecture Freeze: not granted

## Exact Next Action

Execute a source-locked WS44 shape audit over these exact 19 fixture IDs, persist the extracted immutable requested-state forms, then remediate only the proven current schema/native-state mismatches and run a fresh exact Full107 Construction v2 gate.
