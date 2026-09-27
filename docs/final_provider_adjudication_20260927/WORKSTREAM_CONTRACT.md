# Workstream Contract — FINAL-PROVIDER-CDQ-20260927

## Objective

Produce the FINAL common-denominator evidence packet required for the
Coordinator to adjudicate XMage versus Forge as the Production Rules
Provider, without choosing the provider and without claiming Architecture
Freeze. Remove the remaining evidence asymmetry and isolate any true
provider-blocking gaps or Rules divergences so the Coordinator can proceed
directly to provider adjudication + Freeze, or to exactly one narrowly
defined remediation workstream for a proven provider-blocking gap.

One primary workstream only. No additional implementation fronts.

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Canonical main at dispatch: `58e8fca430651207a87a8f3e9f41d8c6527dd4cd`
- Canonical tree at dispatch: `4cf4f3d23da9b6a7bb010178b6efcc2b2c853ba2`
- Authorized branch: `wsr21/final-provider-cdq-20260927` (reserved remotely,
  initially exactly at canonical main; verified `HEAD == 58e8fca4`, tree
  `4cf4f3d2`, working tree clean at session start)
- Canonical Coordinator tracker: Commander-Lab Issue #255 (Issue #251 CLOSED
  / COMPLETED, superseded by #255)
- XMage engine candidate pin (contract-claimed):
  `b19596980f2734496ea1896504253e1bdd2756dd` (moeendres-png/mage)
- XMage reconciled Lab runtime authority (locally verified):
  `593326713faeddb8c90df2fdc5e5bafbe1fccf1b`
- Forge production-code candidate (contract-claimed):
  `ef958ee91ac6c9ce0152189f2654bf6e05abf273` (moeendres-png/forge)
- Forge WSR20 evidence tip (contract-claimed):
  `18bba95a4528f6ab5910633f1f87f603b8c4ddf8`
- FULL107 frozen source (locally verified):
  `5a2e4f462fd45bba25f2271153212aab9faf09f5` (107 items, immutable)
- Lab Forge pre-selection manifest (current, intentionally unpinned here):
  Rules-Core `a37a865a53280dd8ad6fad3384d69611e8c5a42f`, bridge materialization
  `4753bb7c72ea60d653121e0bab989077b4009f9c` (config/rules_engines.json)
- Launch gate (verified 2026-09-27, all SUCCESS on exact main `58e8fca4`):
  CI `36310680744`, Production Qualification `36310680885`, Exact Main
  Recovery `36310680895`, Windows Runtime Hygiene `36310680966`, Release
  Artifacts `36310680812`

External Forge/Mage SHAs above are Coordinator-contract identities. This
worktree holds only the Commander-Lab clone; no Forge/Mage reference root was
declared for this run, so external engine bytes are NOT locally re-verified
here and are recorded as CONTRACT_CLAIMED (see SOURCE_LOCK.md and
IDENTITY_RECONCILIATION.md). Lab-side identities ARE locally verified.

If Commander-Lab main or the reserved branch advances mid-workstream:
determine exact changed paths, perform impact adjudication, continue only on
demonstrably non-semantic change, otherwise fail closed with SOURCE_DRIFT.

## In Scope

- Gate A identity reconciliation (8 identities, CURRENT / HISTORICAL /
  EVIDENCE_ONLY / ENGINE_CODE / LAB_INTEGRATION / PRE_SELECTION_MANIFEST)
- Gate B XMage FULL107 evidence refresh (all 107 rows, exact-obligation
  promotion rule, OLD/NEW/pointer/why/identity/impact per change)
- Gate C common fixture normalization (101-fixture common set derived as 107
  minus the 6 Coordinator-listed Forge residual seams; per-fixture semantic
  comparison disposition, no rankings)
- Gate D targeted gap analysis + only decision-critical local validation
  (no engine re-runs of already-valid evidence; no fabricated RNG/outcomes)
- Divergence packet (compact, UNKNOWN_PENDING_RULES_ADJUDICATION only)
- Provider readiness packet (machine + human readable, per-dimension status
  with evidence pointers, no scores, no winner, no ranking)
- Comparison notes: hidden-info, RNG/replay, multiplayer, forbidden-fallback
- Evidence tree under `docs/final_provider_adjudication_20260927/` plus one
  packet-validation test; scoped validation; local checkpoint commits
- Remote publication + exactly one PR only when terminal candidate state is
  green (subject to the root push-approval gate; no force push, no rebase of
  published evidence, no merge to main)

## Out of Scope (forbidden expansion)

New engine evaluation; Manabrew/phase.rs re-research; Mage master upgrade or
repin; WSR20→Forge-master merge; implementing the six known Forge residuals;
`config/rules_engines.json` repin; provider selection; Architecture Freeze
claim; production repository creation; pilot/deckbuilding/performance
optimization; unrelated historical PR cleanup; project-wide stranded-code
inventory; publisher remediation reopening (PR #253 merged, PR #206 closed as
superseded provenance).

## Ownership

Single writer: this session on branch `wsr21/final-provider-cdq-20260927` in
worktree `/home/moeen/code/wsr21-final-provider-cdq` only. No mutation of
other workstreams' branches/worktrees, no direct `main` edits, no XMage/Forge
production-code edits, no engine Rules-semantic edits, no repins. Engine
defects found during comparison are recorded, not fixed here. Lab harness
defects may be repaired systemically with tests + documentation.

## Dependencies

- Sealed XMage L1→L7 residual closure (PASS, authority `59332671…`) — reuse
- Current FULL107 mapping (15 DIRECT / 13 SUPPORTING / 25 NOT_RUN_BLOCKED /
  54 UNKNOWN) + fixture identity register (20 adjudicated verdicts) — reuse
- WS47 v1.0.5 frozen denominator/materialization — immutable reuse
- Forge WSR20 packet (`forge-protocol2-bridge/wsr20-full107/`) — ABSENT from
  Lab source truth in this worktree; recorded as the single blocking ingest
  (see Gate C and FINAL_HANDOFF.md). No Forge evidence is fabricated to fill
  it.

## Hard Gates

- Frozen FULL107 bytes immutable: no fixture redefinition, deletion, split,
  combination, or threshold redefinition.
- Promotion rule: DIRECTLY_VERIFIED / TECHNICALLY_CONFORMANT only on exact
  obligation match (behavior, card/scenario semantics, player count, decision
  class, visibility, principal, RNG, replay, state transition, runtime
  identity, no prohibited fallback). CODE_DERIVED never promotes to runtime
  PASS; construction never proves behavior; family evidence never proves exact
  fixture; 4P never proves 5P; similarity never proves DIRECT.
- Rules authority separation: comparison code observes, receives legal
  options, chooses among discretionary options, records evidence. All listed
  forbidden shortcuts fail closed.
- Hidden information stays principal-scoped; leakage is never cosmetic.
- Rules randomness stays Rules-owned; harness controls seed/tape interfaces
  only, never chooses outcomes; no manual outcome injection; no harness as
  second Rules engine.
- Divergences become UNKNOWN_PENDING_RULES_ADJUDICATION with full
  reproduction records; never resolved by vote, history, or test counts.
- No provider score, winner, or ranking anywhere in outputs.
- Terminal states maintained: `ARCHITECTURE_FREEZE = NOT CLAIMED`,
  `PRODUCTION_PROVIDER = NOT SELECTED`.

## Evidence Requirements

Machine-readable packets (JSON) + human-readable summaries for every gate;
exact evidence pointers with runtime identities; per-change impact
adjudication; schema/JSON validation; relevant hidden-info, replay/RNG, and
forbidden-fallback checks; touched-code lint/type checks; packet
reconciliation test green.

## Stop Conditions

Complete only when the Coordinator can proceed directly to
(A) provider adjudication + Freeze, or (B) exactly one narrowly defined
remediation workstream for a proven provider-blocking gap + targeted
requalification + Freeze. Otherwise fail closed only on: genuine terminal
Source/Authority/Scope blocker; another owner's mutation surface; Sol/Human
authority requirement (AUTHORITY_GATE); destructive/external consent
requirement; genuinely unobtainable upstream information; or proceeding would
weaken Rules/Evidence/Privacy invariants. Missing evidence stays UNKNOWN or
explicitly absent; never speculative PASS.
