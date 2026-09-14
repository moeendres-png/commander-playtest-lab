# WS205 Final Report — XMage Corrected WS90 First-Wave Qualification

Qualification workstream. Zero behavior credit earned. No provider ranking
restored. No Architecture Freeze. No Full107.

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws205/xmage-ws90-first-wave-qualification-20260914`
- `AUDIT_BASE_SHA`: `5994019b4da59e27a388eec47e6805404bd98df9`
- XMage engine pin: `cfc36f445f917f101fa2ed588770e043f53bc44c` (preserved)
- Sealed WS90 blobs preserved (`CODE_DERIVED` via `git hash-object`):
  pack `5852965e…be8ef337`, decreq `1340f8cc…fbe2967`, H01 `eb087464…22553`
- `verify.py`: `VALIDATION_PASS`. `WS204_BASE_PRESERVED`: no WS204/WS90/
  production-bridge mutation; 88-test Maven green rerun in WS205.

## Work Completed

- Read-first XHIGH adjudication (`foundry-adjudicator`) before driver design;
  directives followed (generic path only, versioned pilot, isolated JVMs,
  twin gates, fail-closed setup, no second Rules engine).
- Built qualification-only driver (`driver-java/…/Ws205FirstWaveDriver.java`
  + `ws205_driver.py` + `ws205_adjudicate.py`, pilot `ws205-pilot-v1`):
  per-slot crafted Commander decks, explicit neutral seeds (9101+index; H01
  controls 9113/9213/9313, never outcome-tuned), fresh JVM per game,
  `legalActionsPayload`/`submitAction` exclusively, mid-run negative probes,
  semantic transcripts with multiset normalization, same-seed twin replay.
- Executed all 15 slots (17 constructions incl. H01 A/B/C) × (primary+twin):
  34 isolated JVM runs, 500 decisions each (budget stop), ~17,000 native
  decisions answered through the generic boundary with zero rejections of
  valid submissions and zero scope escapes.
- Adjudicated every slot (reachability × behavior), sealed the evidence
  package (`FIRST_WAVE_MATRIX.json`, `BEHAVIOR_CREDIT.json`,
  `TWIN_REPLAY.json`, `BLOCKERS.json`, `VALIDATION.json`,
  `DRIVER_VALIDATION.json`, per-slot transcripts/hashes).

## New Findings

1. **H01 copy-decision carrier mechanism observed at runtime**
   (`DIRECTLY_VERIFIED`, zero behavior credit): in HUMILITY_FIRST
   construction (seed 9113), P0 cast Clone natively (priority wish hit at
   offset 411, 8× `mana_payment` answered), XMage parked copy-entry
   `choose_use` ("Use effect of Clone?" Yes/No), pilot answered Yes, Clone
   entered a creatureless board as 0/0 and died to SBA (graveyard). Zero
   copy-`choice` frames (none possible). Ordering was NOT H01-A (Humility and
   Bear undrawn), so this is mechanism evidence only: the copy path enters
   through `choose_use`, and the `choice` frame appears only with creatures
   present. No A-falsifier triggered.
2. **Same-seed offered-set nondeterminism across JVMs** (6/17 constructions:
   A03, B01, D06, E02, I01, HUMILITY_FIRST-twin): identical selection
   histories produce different offered counts (activated/mana abilities) and
   one cast-offer absence; terminals still match. Causality UNISOLATED
   (engine enumeration vs bridge projection iteration) — recorded UNKNOWN,
   never upgraded. Twin gate honestly `false` there (hashes preserved).
   Successor S2 specifies isolation.
3. **Singleton assembly impossibility** (B01: 2× Warden for P0; E01: 2× Bear
   for P1): neutral states unassemblable under Commander singleton rules with
   qualified deck mechanisms. Successor S1.
4. **G03 ledger**: pre-decision 12-damage seeding has no qualified mechanism
   (`starting_state_injection_supported=false`). Successor S1.
5. **E02/G04 reconfirmed BLOCKED_BY_ENGINE_CORE** with full-run
   corroboration (500 decisions each; zero damage-distribution / zero concede
   frames offered). Binds WS204 remediation file (successor S4 reference).
6. All other slots: key 1-ofs undrawn/unplayed within the 500-decision native
   budget (transcript offer census: zero scenario-card offers in 16/17
   constructions); no teleport mechanism exists or was used.

## Changes

New package `qualification/ws205-xmage-ws90-first-wave/` only (driver,
orchestrator, adjudicator, tests, method/locks, 17-construction evidence,
aggregate seals, successor spec). No production, engine, WS204/WS90, or
config mutation. `db/` (254M XMage card-repo cache from JVM runs) left
untracked, never committed.

## Tests / Evidence

- Sealed `verify.py`: PASS. Blobs: preserved (3/3).
- Maven: 88/88 green (24 WS204 generic-transport incl. census + D1–D5 gates).
- Python subset: 75 passed. Driver tests: 24 passed. Ruff: PASS.
- Smoke (A03): primary 500/500 via generic boundary; probes rejected +
  unadvanced; twin hashes recorded.
- Per-slot: `slots/<key>/{primary,twin}.json + .semantic.json/.sha256 +
  twin.record.json + decks/prefs/stdout`.
- Pre-existing, unrelated: WS17 manifest coverage test fails on the pristine
  audit base (manifests predate ws203/ws204 packages); reseal at publication.

Evidence classes: run facts `DIRECTLY_VERIFIED`; missing-hook BLOCKEDs
`CODE_DERIVED` (+ run corroboration); behavior `UNKNOWN` stays UNKNOWN;
no official-Rules validation claimed (no behavior PASS exists to validate).

## PASS / FAIL / UNKNOWN

- `FIRST_WAVE_PASS = 0`, `FIRST_WAVE_FAIL = 0`, `FIRST_WAVE_BLOCKED = 2`
  (E02, G04 — engine core), `FIRST_WAVE_UNKNOWN = 13`. Sum = 15. ✓
- H01: `HUMILITY_FIRST = UNKNOWN`, `CLONE_FIRST = UNKNOWN`,
  `NO_HUMILITY = UNKNOWN`, aggregate ONE slot `UNKNOWN`. Credit 0 (no
  partial H01 credit).
- `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`. `ACTUAL_CARD_BEHAVIOR`: actual cards
  used in all runs; 0 behavior PASSes.
- Twins: 11/17 `semantic_replay_match = true`; 6 false with hashes + reasons
  (5 offered-set divergence, 1 stream divergence at 410/500 on the Clone-cast
  offer). `BIT_EXACT_REPLAY_VALIDATED = false`.
- Regressions: D1/D2/D3/D4/D5-ordering PASS; `D5_TWIN_EQUALITY = UNKNOWN`
  globally. `FULL107 = NOT_RUN`.
- Authority invariants: `REQUESTED_OPTION_FILTERING = ABSENT`
  (`CODE_DERIVED`: wish-matching over offered labels only; forbidden choice
  keys rejected by projection; zero forbidden rejections across all runs),
  `SECOND_RULES_ENGINE = ABSENT`, `INTERNAL_XMAGE_AI_AUTHORITY = ABSENT`,
  `GUI_DEFAULT_AUTHORITY = ABSENT`, principal scoping preserved (D4 PASS;
  pilot consumed actor payloads only; assertion state segregated).
- `GENERIC_LEGAL_ACTIONS_PATH_USED = true`,
  `GENERIC_ACTION_SUBMISSION_PATH_USED = true` (sole control path; native
  verbs unreachable from driver).
- `CONCESSION_BOUNDARY = BLOCKED_BY_ENGINE_CORE`,
  `COMBAT_DAMAGE_ASSIGNMENT_BOUNDARY = BLOCKED_BY_ENGINE_CORE`.
- `NEW_ENGINE_CORE_BLOCKERS = 0` confirmed (1 enumeration-nondeterminism
  candidate under S2 isolation, causality UNKNOWN). `NEW_BRIDGE_BLOCKERS = 0`.
- `RAW_GIT_PUSH_USED = NO`. `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
  `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Remaining Blockers

- E02, G04: engine-core hooks (S4 reference; engine workstream required).
- 13 UNKNOWNs: scenario-setup assembly (S1 mechanism, S3 phased pilot).
- Twin FALSE ×6: enumeration nondeterminism isolation (S2).
- All specified execution-ready in `SUCCESSOR_SPEC.md`; none executed in WS205.

## Outputs

`qualification/ws205-xmage-ws90-first-wave/`: `SOURCE_LOCK.md`, `METHOD.md`,
`DRIVER_VALIDATION.json`, `FIRST_WAVE_MATRIX.json`, `BEHAVIOR_CREDIT.json`,
`TWIN_REPLAY.json`, `BLOCKERS.json`, `VALIDATION.json`, `FINAL_REPORT.md`,
`SUCCESSOR_SPEC.md`, driver + orchestrator + adjudicator + tests, 17
per-construction evidence namespaces.

## Dependencies Unblocked

- S1 (setup dealing mechanism), S2 (enumeration isolation), S3 (phased
  pilot), S4 (engine hooks) are specified execution-ready with acceptance
  criteria; no ranking or freeze decision depends on WS205.

## Exact Next Action

Reseal WS17 manifests for the new package, final `ruff`/`pytest`/blob
verification, canonical `safe_push` dry-run → actual on
`ws205/xmage-ws90-first-wave-qualification-20260914`, fetch verification
(remote HEAD == local HEAD, TREE == TREE, clean), then terminal handoff.
