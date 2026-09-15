# WS218 WS220_REPLAY_RISK_IMPACT — F-REPLAY-01 / S10 adjudication

Read-only Coordinator input: WS220 terminal `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b`
(tree `6bc707b37f8fb39950f4ade2db11e7ccef03dab6`), sibling research branch on
WS215 base (`67db0733`). WS220 changes only `research/project-audit/ws220/**`;
it does not supersede the WS218 source lock (HEAD/tree unchanged above).
Consumed via Git object identity (`git show <sha>:...`); no sibling-worktree
filesystem access required or used. WS218 branch/worktree/state/audit-base
unchanged; no rebase; no unrelated WS220 findings absorbed (S1/S3/S4/S5/S11,
numeric-narrowing remediation, honeycard work explicitly out of scope).

Exact WS220 source: `FINDINGS.json` F-REPLAY-01 (12 risks R1–R12, R10 first;
desired: checkpoint schema, dual-mode replay, tiebreak identity, ordering
pin, timestamp exclusion, text normalization, taxonomy versioning,
seed-binding abstraction, N seat maps, outcome field list, raw allowlist,
grant-window scope, definition naming) + `BATCH2_NOTES.md` C3 (normative bar
= semantic equality UUID-scrubbed/pilot_state-dropped; bit-exact false;
twins≠replay; checkpoint/consumer/gate absent; injection ban; N noted;
R10 = `raw_result_sha256` over per-process UUIDs vs 11/12 strict TRUE) +
`SUCCESSOR_PROPOSALS.json` S10 (hard gates: R10 allowlist pinned, checkpoint
schema + dual-mode + taxonomy versioning sealed, Coordinator review).
The H-REPLAY-01 subagent prose beyond these committed lines was not
available as a committed object; the mapping below uses exactly the
committed lines above (no invented R-text).

## R1 — Checkpoint schema + capture points — PASS

- Risk: checkpoint undefined (what is captured, where, in what schema).
- WS218: versioned `TapeCheckpoint`/`TapeTerminal` (`tape.py`):
  seed/calls/turn/phase/step/decision_sequence/event_offset/semantic/public/
  principal digests; initial checkpoint at first native decision (post-shuffle
  binding proof), per-step post digests (next pending pre-state or terminal),
  terminal checkpoint (seat-mapped outcomes + turn + calls). Evidence-only,
  never restore.
- Affected: `tape.py`, `recorder.py`, `CHECKPOINT_CONTRACT.md`.
- Evidence: `tapes/ws218-tape-{2,3,4,5}p.json` all carry initial/terminal +
  per-step post digests; `consumer.py` verifies each.
- Ambiguity left: none for XMage lane. Future providers reuse the same
  schema (phase/step optional strings).
- Provider neutrality: checkpoint fields are provider-neutral concepts
  (seed, calls, turn, phase/step names, offsets, digests); XMage maps
  `game.getRulesRandomCalls()`→calls, `getState().getTurnNum()`→turn,
  `getTurnPhaseType/getTurnStepType`→phase/step strings. Forge maps its own
  turn/phaseCovid + Core RNG counter to the same slots (sketch in §Forge).
- Test: unit schema tests + positive replays verify every checkpoint.

## R2 — Semantic vs diagnostic/raw replay modes — PASS

- Risk: two definitions (semantic equality vs raw/strict) coexisted without
  naming which is normative.
- WS218: dual-mode defined and named: (a) normative SEMANTIC replay
  (canonical digests over allowlisted fields; PASS requires all 15 hard
  gates); (b) diagnostic RAW hashes retained only as non-evidence
  (`raw_result_sha256`-lineage never compared for PASS;
  `bit_exact_replay_validated=false` everywhere honest). Tapes seal only
  semantic digests; `VALIDATION.md` states raw never normative.
- Affected: `tape.py` seal, `consumer.py` verdict, `full_game.py`
  `run_replay_gate` retained as determinism control only.
- Evidence: positives PASS on semantic digests while raw UUIDs differ per
  process (distinct `engine_game_id`/actor UUIDs every run); tamper matrix
  never asserts raw equality.
- Provider neutrality: semantic mode is provider-neutral; raw mode (if ever
  defined per-provider) stays lane-local and non-normative cross-provider.

## R3 — Stable tiebreak / object identity — PASS

- Risk: identical labels / iteration order / UUID tiebreaks make replay
  vacuous or first-option.
- WS218: `semantic-option-identity-1.0.0` joins object references to
  observation projections (zone occurrence, controller/owner seat, public
  characteristics); ability copies join source occurrence (smoke step-20
  systemic repair, no first-pick); 0-match→MISSING, >1→AMBIGUOUS, never
  fuzzy. Production `_decide_targets` UUID-residual noted; recorder-side
  pilot crash (`score,_` unpack on 3-tuples) repaired minimally to unblock
  long runs (no narrowing change; S6 narrowing untouched).
- Affected: `fingerprint.py`, `full_game.py:513` (crash fix only).
- Evidence: duplicate-Plains unit test (identical projections AMBIGUOUS by
  design); play-land occurrence resolution (611-step 2P replays PASS);
  `DUPLICATE_ACTION_DISAMBIGUATION` in validation.
- Provider neutrality: occurrence/seat join is a neutral concept; Forge
  opaque target ids join the same way (Core-supplied public characteristics).

## R4 — Deterministic ordering / canonicalization — PASS

- Risk: iteration order / nondeterministic serialization makes equality
  meaningless.
- WS218: `semantic-canonical-1.0.0` (UTF-8, sorted keys, stable scalars,
  ordered-stays-ordered, unordered-sorted-by-fingerprint, NaN forbidden,
  version persisted). Battlefield/command/hand-names/options sorted by
  fingerprint; stack/graveyard/transcript order preserved as semantic.
- Evidence: unit byte-stability + NaN rejection; cross-process digest
  equality across 8 fresh JVMs (2P/3P/4P/5P × record+B+C).
- Provider neutrality: canonicalization is provider-agnostic JSON semantics.

## R5 — Timestamp / wall-clock exclusion — PASS

- Risk: wall-clock in hashes makes replay flaky or vacuous.
- WS218: schema contains no timestamps; digests computed only over listed
  semantic fields; request ids/engine UUIDs/wall-clock diagnostics excluded
  by projection (never generic-stripped). `protocol_schema_digest` covers
  files, not times.
- Evidence: unit + tape scan (no time fields in digests); replays across
  wall-clock hours PASS.
- Remaining: none.

## R6 — Prompt/text normalization — PASS

- Risk: labels/prompts embed process-local ids; either leaks into digests
  or over-normalizes genuine divergence.
- WS218: `redact_text` removes `object_id='...'` attrs, bare UUIDs, GameLog
  `[xxx]` short-ids (production lineage, twin-proven nonsemantic); Rules
  text preserved; choice short-ids → `[#]`. Fingerprints use redacted
  labels PLUS semantic metadata/projection joins, so genuine text divergence
  (different card/ability/mode) still mismatches (`TAMPER_LEGAL/OPTION`
  prove it).
- Evidence: twin-redaction unit test; tamper legal/option negatives.
- Provider neutrality: redaction patterns are documented as XMage-lane
  evidence; the normative contract is "redact proven-nonsemantic identity,
  hash the rest" with per-provider patterns in an extension section (Forge
  patterns added when Forge requalifies; XMage correctness unwidened).

## R7 — Decision taxonomy versioning — PASS

- Risk: 17 XMage classes baked in as the universal contract.
- WS218: tape `decision_class` is an opaque versioned string; the XMage
  binding enumerates the 17 production classes + `concede` lifecycle in
  `FULL_GAME_DECISION_PROTOCOL_VERSION` + manifest
  `decision_policy_version`; unknown classes fail closed on both sides
  (controller + `ExternalPilotDecisionPolicy` + consumer strict compare).
  Taxonomy version is bound in source lock (`decision_protocol_version`).
  Forge families map to distinct strings (e.g. `divided_allocation`,
  `number_choice`, `target_selection`) without colliding with XMage names.
- Evidence: `test_unknown_discretionary_decision_class_fails_closed`;
  `TAMPER_CLASS` (announce_x swap → CLASS_MISMATCH).
- Provider neutrality: normative tape depends on string equality + taxonomy
  version binding, never on XMage class semantics.

## R8 — Abstract Rules-seed binding (not WS212 API) — PASS

- Risk: contract locked to `setRulesSeed` API instead of an abstract binding.
- WS218: `rng_contract` + manifest bind the ABSTRACT contract (explicit root
  seed + explicit flag + require-explicit + calls coordinates + regenerate-
  not-inject), with the XMage realization (`setRulesSeed` +
  `setRequireExplicitSeed` + `getRulesRandomCalls`) recorded as the lane
  mapping in `RNG_TAPE_CONTRACT.md`, not as the normative definition.
  Consumer verifies abstract properties (seed equality, explicit flags via
  live binding, calls equality, no injection) without calling XMage APIs
  from Python beyond the existing lane payloads. Forge maps its Core RNG
  root + counter to `root_rules_seed`/`rules_random_calls` slots.
- Evidence: `RNG_TAPE_CONTRACT.md`; `TAMPER_SEED/RNG_CALLS/RNG_RESULT`.
- Out of scope (untouched): WS212 engine internals; no API change.

## R9 — N-player seat/principal mapping + terminal outcome field list — PASS

- Risk: seat maps and outcome fields undefined across N.
- WS218: manifest binds `player_count` 2..5 + `seat_principals` 1..N
  (deck/pilot per seat) + decks cardinality; steps bind `actor_principal`
  1..N (= engine seat+1, validated against live seat map both sides);
  terminal binds seat-mapped outcomes with EXPLICIT field list
  `{seat,won,lost,left,life}` sorted by seat + turn + calls + digests.
  Count mismatch → `DOMAIN_LOCK_MISMATCH`/`MALFORMED_TAPE` before execution;
  elimination alters the native stream (no ring repair; consumer never
  reindexes).
- Evidence: 2P/3P/4P/5P positives (seat maps, rings, multi-defender frames
  in logs, concession terminals seat-mapped); `TAMPER_COUNT/TERMINAL`.
- Provider neutrality: seats are 1..N principal indices, not XMage seat
  objects; outcomes are the five-field list regardless of provider.

## R10 — Raw-hash field contract (TOP PRIORITY) — PASS (pinned; raw never normative)

- Risk (WS220 C3 exact): "`raw_result_sha256` over a dict containing
  per-process UUIDs should fail across fresh JVMs, yet 11/12 strict TRUE is
  reported — the exact hashed object must be pinned by allowlist before
  'raw' is normative."
- WS218 disposition: RAW IS NEVER NORMATIVE in WS218. The exact objects
  hashed for QUALIFICATION are only the versioned semantic digests below,
  each with a pinned include list; every process-local field is enumerated
  as excluded with nonsemantic proof. No raw/strict equality is claimed;
  `bit_exact_replay_validated=false` everywhere; `SEMANTIC_REPLAY_STATUS`
  gates on semantic PASS only.
- Pinned semantic objects (allowlists):
  - `option_fingerprint`: includes `option_type`, redacted `label`,
    class-specific semantic metadata (boolean `value`; choice
    `choice_key`/`choice`; pile sorted names+count; `mana_type`;
    ability `ability_type`+redacted `source_name`+`mana_ability`+joined
    `source` occurrence; replacement redacted `source_name`; mode redacted
    text; target/attacker/blocker joined public projections; numeric
    value+bounds), plus `_identity_version`+`_canonicalization`.
    Excludes: ALL raw UUIDs (`option_id`, `object_id`,
    `source_object_id`, `ability_original_id`, `card_id`, `defender_id`,
    `attacker_id`, `blocker_id`, `mode_id`, player/game/decision ids),
    `stableId` hashes thereof, unordered positions. Proof: twins mint
    distinct ids with identical transcripts (WS215 matrix + WS218 8× fresh
    JVM equality); `IDENTITY_INVENTORY.md`.
  - `legal_set_digest`: includes sorted fingerprint multiset + count +
    versions. Excludes everything above per-option.
  - `canonical_actor_view`: includes turn/phase/step, seats, life/poison/
    counts, sorted public permanents (name/controller-seat/tapped/power/
    toughness/damage/counters/face-up abilities), graveyard name order,
    command names, actor hand names (sorted) + mana + land-plays,
    window-only granted names (sorted), stack name order, commander
    damage/tax rows. Excludes: `game_id`/actor/player/object UUIDs (mapped
    to seat/occurrence), opponent hand/mana arrays (structurally absent),
    request ids, timestamps, wall-clock, timeouts, raw prompts beyond
    redacted labels. Proof: UUID-remap unit test (fresh ids → identical
    digests); tape scan (0 UUIDs, no hand/mana/granted arrays).
  - `internal_checkpoint_digest`: observation + legal fingerprints + seed +
    calls + turn + offset + versions. `public_state_digest`: public subset.
    `event_digest_for_step`: sequence/class/actor/selected prints/numeric/
    calls before-after/turn before-after/observation/post + versions.
    Terminal digests: seat-mapped `{seat,won,lost,left,life}` + turn +
    calls. Exclusions as above.
  - Raw/diagnostic objects explicitly NOT hashed for PASS:
    `engine_game_id`, native `decision_id` (`stableId` over UUIDs),
    `action_id` (`decision_id:option_id`), `public_state_reference` hashes,
    `request_id`, `engine_thread_name`, stderr text, `last_submission`
    raw ids, full `result` dict. The legacy `_sha256(result)` /
    `raw_result_sha256` lineage is retained ONLY as a diagnostic control
    (twin determinism signal) and is never compared for tape PASS.
- Evidence: `IDENTITY_INVENTORY.md`, unit remap/ambiguity/multiset tests,
  tape scans, 8× fresh-JVM semantic equality with differing raw ids,
  `TAMPER_*` proving no silent normalization (every semantic change fails;
  nonsemantic id changes pass by construction AND by twin proof, not by
  convenience).
- Remaining: none for the semantic claim. Bit-exact/raw remains honestly
  unclaimed (NOT a PARTIAL; it is out of the normative contract by design).

## R11 — Grant-window / private-information scope — PASS

- Risk: search/scry looks leak or over-restrict replay identity.
- WS218: `granted_library` digested ONLY as sorted names when the entitled
  window is live (engine-selected eligible set, adapter-projected, closed in
  `finally`); otherwise empty. Fingerprint joins use the same windowed
  index. Pilot-facing consumer returns hashes/verdicts/seat-outcomes only;
  failure diagnostics carry class/seat/revision/calls (leak-scan in tamper
  loop asserts no card names). Privileged tapes may carry redacted labels
  + hashes, never raw hidden arrays (scan: 0 UUIDs, no hand/mana/granted
  arrays). No honeycard work implemented (S7 out of scope); name-blindness
  limitation from F-HIDE-02 is cited, not upgraded.
- Evidence: `HIDDEN_INFORMATION_REPLAY.md`, oracle lineage (WS215 9985/0 +
  WS218 structural absence by construction), tamper diagnostic leak scan.
- Provider neutrality: grant-window is a neutral concept (entitled look);
  Forge maps its own look windows to the same slot.

## R12 — Two-definitions coexistence (old vs new replay) — PASS

- Risk: "replay" means twins in old docs and tape in new docs.
- WS218: definitions pinned and coexistent WITHOUT upgrade:
  (a) same-seed twin = determinism evidence (two independent runs, redacted
  transcript compare; `run_replay_gate` retained as control);
  (b) semantic replay tape v1 = normative contract (this workstream).
  Old docs calling twins "replay" are provenance, not authority
  (Source Truth §6); no historical verdict silently upgraded
  (`SEMANTIC_REPLAY_STATUS` history: WS213 PARTIAL → WS215 PARTIAL →
  WS218 PASS for the tape lane only; twin semantics unchanged;
  `bit_exact` still false; FULL107 still NOT_RUN).
- Evidence: `FINAL_HANDOFF.md` terminal fields; this section.

## Provider-neutrality proof (bounded, WS217 reference, no Forge integration)

- Normative tape concepts (provider-neutral): decision-class strings,
  principal seats 1..N, revision offsets, fingerprint multisets, numeric
  value+bounds, RNG root+calls coordinates, event offset ranges + digests,
  seat-mapped five-field outcomes, source/domain locks with abstract slots.
- XMage-native mapping (lane extension, not normative): 17 classes +
  `concede`; `setRulesSeed`/`setRequireExplicitSeed`/`getRulesRandomCalls`;
  labels/types from `XmageFullGamePlayer`/`DecisionController`; seat =
  engine index+1; phase/step strings; `canConcede`/`concede`. Engine-native
  metadata beyond the normative fields may travel in request `metadata` but
  never enters normative digests.
- Forge sketch (no implementation, no XMage weakening): WS217 families map
  as `target_selection`→(target/choose_object class, opaque target prints
  joined to Core public characteristics), `divided_allocation`→(decision
  class `divided_allocation` with `numeric_total`/`numeric_min` bounds +
  per-target fingerprint multiset + allocation vector as ordered
  (fingerprint, amount) pairs; Core validates before mutation per WS217),
  `number_choice`→(numeric value+bounds, zero options). Forge Core RNG root
  + counter → `root_rules_seed`/`rules_random_calls`; Forge seats →
  principal seats; Forge damage/tax rows → commander rows. Tape semantics
  (exactly-one resolution, multiset compare, calls equality, fail-closed
  taxonomy) apply unchanged. XMage lane keeps all 17 classes and guards;
  nothing narrowed for portability.
- Verdict: provider-neutrality PROVEN for the contract shape; Forge
  consumption remains a separate chartered successor (not claimed).

## Out-of-scope WS220 items (not implemented, not upgraded)

S1 vocabularies, S3 authority acquisition, S4 manifest repair, S5
cardinality CI, S11 ops-doc reconciliation, numeric-narrowing remediation
(span>16 collapse untouched; only the 3-tuple unpack crash repaired to
unblock long runs), honeycard/name-canary work. One genuine production
repair performed inside WS218 scope: `full_game.py:513` crash fix
(documented in handoff; predicate test added to the tape suite).

## Terminal dispositions

R1 PASS, R2 PASS, R3 PASS, R4 PASS, R5 PASS, R6 PASS, R7 PASS, R8 PASS,
R9 PASS, R10 PASS (raw pinned non-normative), R11 PASS, R12 PASS.
No BLOCKED items. No AUTHORITY_GATE raised (all adjudicated within
contract + code + WS220 committed source). Raw/strict replay equality is
not claimed (honest exclusion, not PARTIAL).

Machine companion: `WS220_REPLAY_RISK_IMPACT.json`.
