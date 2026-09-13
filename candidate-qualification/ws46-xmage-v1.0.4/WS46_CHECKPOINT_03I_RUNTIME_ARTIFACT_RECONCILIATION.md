# WS-46 CHECKPOINT 03I — CURRENT FULL107 RUNTIME ARTIFACT RECONCILIATION

## Purpose

Correct the persistent narrative for the current WS-46 v1.0.4 Full107 Construction v2 runtime against the actual GitHub Actions artifact. This checkpoint supersedes only the artifact identity and failure taxonomy recorded in `WS46_CHECKPOINT_03H_CURRENT_HEAD_FULL107_FAILURE.md`; it does not alter the immutable WS-44 contract or grant construction/provider credit.

## Source Truth

Runtime authority is the exact GitHub Actions run and its uploaded artifact. When a checkpoint narrative conflicts with that artifact, the Actions artifact wins.

- workflow: `WS46 XMage v1.0.4 Full107 Construction v2`
- run: `34221583745`
- tested Commander-Lab head: `d5f534f7014e78b272983b0548e3c5ce266fde35`
- job: `102045705813`
- exact artifact id: `10054580582`
- artifact name: `ws46-v104-construction-v2-d5f534f7014e78b272983b0548e3c5ce266fde35`
- artifact digest: `sha256:a355642467116934642344b95e29de5cdcca5e73a899e001cccc64e5b0a196a1`

Pre-runtime gates in that job passed through source-lock verification, exact 107-record denominator reconstruction, qualification overlays, exact XMage build, bridge build, and runtime-classpath materialization.

## Actual Full107 Result

The artifact `WS46_FULL107_CONSTRUCTION_PROBE.json` reports:

- total: `107`
- PASS: `88`
- FAIL: `19`
- deferred: `0`
- gate: `FAIL`

No construction PASS credit is granted.

## Authoritative 19 Runtime Failures

### Natural-game-start commander configuration — 7

1. `PLAYER_COUNT_2P` — `CONFIGURATION_ERROR:PLAYER_COUNT_2P:Command zone must contain at least one commander`
2. `PLAYER_COUNT_3P` — same configuration error
3. `PLAYER_COUNT_4P` — same configuration error
4. `PLAYER_COUNT_5P` — same configuration error
5. `PILOT_MULLIGAN` — same configuration error
6. `WS05-CMD-MULL-2` — same configuration error
7. `WS05-CMD-MULL-4` — same configuration error

### Native `face_down` proof boundary — 4

8. `PILOT_TARGET_SELECTION` — `PROBE_RUNTIME:ValueError:shadow-semantic-request-input:('face_down',)`
9. `PILOT_DECISION_ORDER` — same `face_down` failure
10. `AF04-FC-RPL-1` — same `face_down` failure
11. `AF05-HM-01` — same `face_down` failure

### Native knowledge/library-range proof boundary — 2

12. `PILOT_REPLACEMENT_EFFECT` — `PROBE_RUNTIME:ValueError:shadow-semantic-state-source:('known_library_ranges',)`
13. `AF05-HM-02` — same `known_library_ranges` failure

### Native extra-turn resolution sequence proof boundary — 2

14. `WS05-MP-REPL-1` — `PROBE_RUNTIME:ValueError:shadow-semantic-request-input:('resolution_sequence',)`
15. `WS05-MP-REPL-3` — same `resolution_sequence` failure

### Native elimination-condition proof boundary — 4

16. `WS05-MP-ELIM-1` — `PROBE_RUNTIME:ValueError:shadow-semantic-request-input:('condition',)`
17. `WS05-MP-ELIM-2` — same `condition` failure
18. `WS05-MP-ELIM-3` — same `condition` failure
19. `WS05-MP-ELIM-4` — same `condition` failure

## Adjudication

These failures are remediable qualification/provider-native proof gaps. None establishes a terminal XMage rules defect by itself.

The following are forbidden remediations:

- whitelisting request fields as proof;
- copying `face_down`, `known_library_ranges`, `resolution_sequence`, or `condition` from the semantic request into observed state;
- weakening the immutable requested-state digest obligation;
- treating natural-start records as deferred or importing historical PASS credit.

Required remediation direction:

- natural start: construct the actual XMage starting configuration with a real commander in command zone before `game.start()`, then read native state at the first external decision boundary;
- `face_down`: derive from native XMage object visibility/face-down state;
- `known_library_ranges`: derive from native revealed/looked-at/knowledge state and native library order/range state;
- `resolution_sequence`: derive from native `GameState.turnMods` ordering/source state;
- `condition`: derive from native player/SBA state (for the current elimination fixtures, source-proof the actual condition from native state).

## Credit State

- historical successor runtime credit imported: `0`
- fresh construction PASS: `NOT GRANTED`
- current fresh construction runtime: `88/107`
- independent construction normalization: `NOT GRANTED`
- behavior runtime: `0/107`
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`
- AF07: not granted
- Architecture Freeze: not granted

## Repository / PR Constraints

- WS-44 remains immutable and unmodified.
- Forge is out of scope and untouched.
- WS-37 Actual-Card runtime is not executed.
- PR #160 remains Draft and unmerged.

## Exact Next Action

Bind the five authoritative failure classes above to the exact immutable WS-44 requested-state shapes and the current WS46 bridge/probe reject sites. Implement only request-independent native-state readback/remediation for those concrete shapes, then execute a fresh exact Full107 Construction v2 run. Do not grant construction credit before a separate independent native-readback normalization reproduces all 107 `requested_state_digest` values.
