# WS205 Successor Specification — concrete remediations for systemic blockers

Status: execution-ready planning. Do NOT execute inside WS205. Each item is a
separate narrowly-scoped workstream with its own contract, source lock, and
requalification burden.

## S1. Qualified scenario-setup dealing mechanism (SCENARIO_SETUP_BLOCKER)

Problem: 11 UNKNOWN slots never reached their required callbacks because
neutral mid-game states (1-of scenario cards across 99-card singleton decks)
do not assemble within a 500-decision native budget, and B01/E01 neutral
states are unassemblable at all (duplicate non-basics vs Commander singleton;
G03 ledger has no injection mechanism; `scenario_injection_supported=false`).

Remediation options (Coordinator/Human authority choice; this touches setup
fairness and Rules-randomness ownership, so confirm authority before design):
- (a) Qualified scripted-opening dealer: a harness mechanism that deals
  specified opening setups through the SAME generic decision boundary (e.g.,
  pre-game mulligan/bottoming scripts selecting only offered options until
  scenario cards are in hand), with seed authority preserved in XMage.
- (b) Qualified scenario-deck density rule: allow multiple functional copies
  via distinct printings only where Rules-legal (no; Commander singleton
  forbids) — rejected; record why.
- (c) Larger decision budgets + phased wish scripting reacting to public
  milestones (see S3). Bounded, no new authority, but cannot fix B01/E01
  duplicates or G03 ledger.

Acceptance: the exact sealed neutral states (or a Coordinator-authorized
delta) must be established WITHOUT manual zone/life writes and WITHOUT
teleportation; every setup action must be an engine-offered decision.

## S2. Offer-enumeration nondeterminism isolation (twin FALSE ×6)

Problem: 6/17 constructions show same-seed, same-selection-history offered-set
divergence across JVMs (activated/mana-ability counts; one cast offer absent).
Terminals still match, so state did not diverge: enumeration does. Causality
(engine ability enumeration vs bridge option projection iteration) is
UNISOLATED — recorded as UNKNOWN, never upgraded.

Remediation: instrument a fixed game state (frozen seed + fixed prefix
stream) to dump the offered option SET (sorted) across N JVMs; bisect into
engine (`Player` ability lists) vs bridge (`XmageFullGamePlayer`/
projection iteration over HashMaps). If engine-side: engine remediation (new
workstream, engine pin bump + full requalification). If bridge-side:
deterministic ordering normalization INSIDE the projection (production bridge
change → own contract + 88-test requalification + twin re-proof). Until then,
same-seed semantic replay stays per-pair evidence; D5_TWIN_EQUALITY stays
UNKNOWN globally.

## S3. Phased scenario-script pilot (H01 B-ordering and sequenced slots)

Problem: memoryless wish-lists cannot sequence multi-stage orderings
(H01-B: copy first, Humility later, removal last; G02: cast Ghalta, then
Murder; I01: Bear, then Pacifism, then Blink).

Remediation: versioned pilot successor (`ws205-pilot-v2` or new workstream
pilot) whose phase transitions trigger ONLY on public native milestones
observed through the actor's OWN principal-scoped stream/state (never
cross-principal hidden info, never privileged assertion state, never
requested-result filtering). Design must prove, per transition, that the
trigger information was PILOT_VISIBLE to that actor.

## S4. Known engine-core remediation (E02, G04) — reference, not new

`qualification/ws204-xmage-b4d-action-submission/
XMAGE_ENGINE_CORE_REMEDIATION_REQUIRED.md` is already execution-ready:
blocking discretionary `concede` hook (actor + engine-offered Yes/No) and
per-attacker damage-distribution/blocker-order hooks as controller decision
classes. WS205 adds: full-run corroboration (500 decisions each, zero such
frames offered). No new spec needed; bind that file.

## Explicitly NOT successor work

- Production Provider selection, Architecture Freeze, Full107, provider
  ranking restoration: none authorized by WS205 evidence (credit 0).
- B01 absolute-totals fixture note stays with WS66 relative-delta scope.
