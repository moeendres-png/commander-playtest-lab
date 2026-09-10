# RQ-A1 — Argentum Final Disposition

## Terminal recommendation

**`ARGENTUM_COMPARABLE_ARCHITECTURE_QUALIFICATION_WARRANTED`**

Argentum has earned a full, comparable architecture-qualification campaign — same bar, same evidence policy as any other candidate — on the strength of: a standalone Rules Core with engine-owned authoritative legal-action enumeration; an identity-bound external decision seam with exact question-instance binding and epoch freshness; structural per-principal hidden-information projection shared by client, AI determinization, and Gym observations; state-threaded seeded RNG with an input-journal replay design; real in-engine Commander (command zone, tax, 903.9a choice, per-commander damage loss) plus 2–4-player FFA with elimination; a 13,915-name declared card corpus with compositional SDK discipline and thousands of behavior-oriented scenario tests; and 254/254 green runtime tests in RQ-A1's narrow executed scopes.

It is NOT `ARGENTUM_GENUINE_CONTENDER_EVIDENCED`: contender status would require measured executable-card coverage (declaration ≠ behavior; 12% generated drafts; card↔test linkage unmeasured), 5–6P runtime evidence (absent), a seed+input replay round-trip (designed, not demonstrated), and external official-rules validation (established for zero mechanisms). Architecture cleanliness — however striking next to Forge/XMage — was not counted as behavior evidence at any point in this workstream.

It is NOT `ARGENTUM_READ_ONLY_REFERENCE` (it is far more than ideas: the seam, the format support, and the corpus are running code with tests) and NOT `ARGENTUM_NO_FURTHER_WORK`. It is also NOT `ARGENTUM_RUNTIME_DISCRIMINATOR_WARRANTED`: the cheap runtime probes available to a read-only pass were already run (254 green); the remaining questions form a campaign, not a single discriminator.

## Integration / qualification cost estimate (technical, relative)

- Small (days): replay round-trip harness (reconstruct N games from `CompactReplay`, compare digests; normalize `AbilityId` first); card↔test linkage script; 5-/6-seat smoke tests; `engine-server-interface.md` refresh-or-supersede; Gym masked-path integration pin.
- Medium (weeks): per-count 2–5P conformance evidence; hidden-info differential testing across perspectives; headless throughput measurement.
- Large (campaign, needs Sol High): official CR/Oracle/rulings validation across the 23 mechanisms; measured executable-card coverage with Commander/multiplayer card tests; partner/background scope decision (only if required — single-commander suffices for the primary benchmark).
- Structural advantage reducing cost: fail-closed gaps (errors, not silent wrongness), layered corpus hygiene (discovery, goldens, linter, verify-gate), era-split compile units, and the standalone-library dependency closure (`mtg-sdk` + 3 kotlinx libs).

## Claim verdicts (from Claim Audit)

- CONFIRMED (9): deterministic/immutable architecture; standalone library; authoritative `legalActions`; Gym contract; masking authorities; seeded RNG control; input-journal replay design; elimination; test-corpus presence.
- DOWNGRADED (4): 2–6 FFA (2–4 evidenced); Commander (single-commander core real, variants absent); snapshot/restore (primitives, not a feature); card counts (declared, not behavior-proven).
- REJECTED (3): stale `engine-server-interface.md` as current contract; stable engine action IDs (no such IDs — narrower truth replaces it); Assay-parsing ≈ behavior (repo's own house rule rejects this).

## Architecture findings

Immutable `GameState` + pure `ActionProcessor.process`; ~22-enumerator `LegalActionEnumerator`; validate-then-execute submission with decision-ID/epoch/message-id guards; suspension-stack questions with 19 typed kinds; perspective-scoped `TrainingObservation`; `Visibility` as the single masking authority; `GameRng` state-threaded with recorded seeds; `CompactReplay` input journal with pinned definitions and fidelity states. Pilot seam verdict: authoritative-options-in / selected-option-out holds, with combat-declaration assembly (`ADAPTER_REQUIRED`), X/mode/target completion channels, and the in-process-Gym-full-state caveat as the three carved exceptions.

## Decision surface

38 kinds: 13 `NATIVE_EXPLICIT`, 11 `OBJECT_ID_BASED`, 7 `INDEX_BASED`, 3 `ADAPTER_REQUIRED` (attackers, defender-per-attacker, blockers), 1 `SEMANTIC_ID_AVAILABLE` (damage edges), 2 `UNKNOWN` (starting player, voting). Full matrix in `ARGENTUM_DECISION_SURFACE.md`/`.csv`.

## Action identity

EntityId intrinsic; ObjectRef revision-scoped; routing tokens game-local correlation (exact-equality checked); AbilityId definition-scoped with a process-global-counter caveat for replay keying; Gym integers per-step; no engine action IDs; no revision token (operational freshness instead: suspension singularity + epoch + per-step registries). Stale-action risk: closed for decisions, revalidated-locked for play actions, closed for gym IDs.

## Rules maturity

23/23 mechanisms `SOURCE_PRESENT`; 22 with engine unit tests, 1 partial (planeswalker/battle excess damage unmodelled). Fail-closed gap pattern throughout. Zero mechanisms externally rule-validated.

## Commander / multiplayer

Commander in-engine (single): format, setup, tax, 903.9a choice, damage loss, 4-seat pod test. Absent: partner/background/companion, play-time color-identity/singleton gates. FFA 2/3/4 test-evidenced; 5/6 absent. 2HG + Team-vs-Team evidenced. No range of influence, no true simultaneity, no voting.

## Real-card maturity

13,915 distinct declared names; 13,619 canonical files + 5,157 reprint rows; 2,227 generated drafts (~12%); ≈3,519 scenario classes + 587 engine test files + 68 e2e specs + 1,177 manual boards. Card↔test linkage unmeasured; no global executable-coverage claim supportable.

## Hidden information

Structural + server-redacted; managed Gym path masked; in-process Gym full-state exposure is the integration-contract caveat; no-leak property UNKNOWN.

## RNG / replay

Controlled seeded RNG (mechanism confirmed); input-journal replay (mechanism confirmed, fidelity UNKNOWN); snapshot primitives without a snapshot feature; headless/batch suitable; `AbilityId` counter hazard recorded.

## Snapshot / restore

Primitives adequate for a future WS51-style comparison; no restore feature exists; no WS51 decision made.

## Tests / evidence (RQ-A1 runs)

- RQ-A1-T1: `:rules-engine` multiplayer.* + CommanderSetup + CommanderTax — **149/149 green** (21 classes), cold cache, 9m18s.
- RQ-A1-T2: sba.* + event.* + combat-damage/legend/simultaneity scenarios — **105/105 green** (15 classes), warm, 35s.
- Combined: **254/254, 0 failures/errors/skips.** Establishes runtime-exercised presence at the lock; not rules validation, not coverage. Full-suite status NOT_RUN.

## Unknown ledger

25 items (U1–U25) in `ARGENTUM_UNKNOWN_LEDGER.md`, each with its resolving probe. Largest: official-rules validation (U1), coverage linkage (U5), 5–6P runtime (U10), replay round-trip (U19).

## PASS / FAIL / UNKNOWN (workstream scope)

- Source-lock verification: PASS (`DIRECTLY_VERIFIED`, LOCK_OK).
- Architecture/decision/identity/RNG/replay/hidden-info/commander-multiplayer/card-maturity/test-corpus audits: PASS as *evidence products* (all claims re-derived, classified, cited; no invented Rules conclusions).
- Full-rules qualification of Argentum: UNKNOWN (explicitly out of scope; this workstream only warrants the campaign).
- 5–6P, voting, starting-player seam, replay fidelity, no-leak property, executable-coverage measure: UNKNOWN (ledgered, not passed).

## Remaining blockers

None for RQ-A1 closure. Follow-on qualification needs Coordinator decisions (scope, authority gates for U2/U3, provider-neutral campaign design) — not RQ-A1 blockers.

## Outputs (all under `research/candidate-qualification/argentum/rq-a1/`)

`ARGENTUM_SOURCE_LOCK.md`, `ARGENTUM_CLAIM_AUDIT.md`, `ARGENTUM_ARCHITECTURE.md`, `ARGENTUM_DECISION_SURFACE.md` + `.csv`, `ARGENTUM_IDENTITY_CONTRACT_AUDIT.md`, `ARGENTUM_RULES_MATURITY.md` + `.csv`, `ARGENTUM_COMMANDER_MULTIPLAYER.md`, `ARGENTUM_REAL_CARD_MATURITY.md`, `ARGENTUM_HIDDEN_INFO.md`, `ARGENTUM_RNG_REPLAY.md`, `ARGENTUM_TEST_CORPUS.md`, `ARGENTUM_LICENSE_TOPOLOGY.md` (`LEGAL_TOPOLOGY_FACTS_ONLY`), `ARGENTUM_UNKNOWN_LEDGER.md`, `ARGENTUM_FINAL_DISPOSITION.md` (this file).

## Dependencies unblocked

- A qualification workstream can start directly from the Unknown Ledger's resolving probes (U19 replay round-trip recommended first: smallest, most discriminating).
- WS51-style restore comparison has candidate facts (no decision made).
- Pilot-integration contracting has the seam matrix + identity rules + masked-path pin.

## Exact next action

Coordinator: charter the comparable architecture-qualification campaign for Argentum (scope: U1 rules validation, U5 coverage linkage, U10 5–6P runtime, U19 replay round-trip, U16 hidden-info differentials) under evidence policy, or rank it against other candidates' RQ reports. No RQ-A1 follow-up work remains.

---

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

No runtime discriminator is self-authorized. No provider is selected. No architecture is frozen.
