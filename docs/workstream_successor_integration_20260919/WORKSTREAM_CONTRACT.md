# Workstream Contract — XMage Successor Functional Integration (2026-09-19)

## Objective

Port the qualified XMage functional chain WS213→WS215→WS218→WS229→WS232
(donor tip `fa4cd8d1`) onto main-line `aebcfda3`, requalify on the new base,
and seal evidence — without engine repin, behavior-credit, freeze, or
provider claims, and without merging (PR-ready branch only).

Main-line today is exactly-4P-only (`len(runtime_pilots) != 4`), has no
replay-tape consumer, no numeric-boundary lanes, and misses the TD01/TD02/TD04
hazard repairs. The donor chain qualifies all of it on the same
`xmage-1.4.61` pin. Integration unlocks mandatory 2–5P conformance and
deterministic replay on the line all future work builds on.

## Source Lock

- Base: `origin/main` @ `aebcfda37d61eb435dde6cd11792ef80019dcd10` (clean).
- This branch: `cpl/xmage-successor-integration-20260919`.
- This worktree: `/home/moeen/code/ws-successor-integration-20260919`.
- Donor (READ-ONLY): `ws232/xmage-retention-nscoped-requalification-20260915`
  @ `fa4cd8d1b6b6466620263fa394729d5512102337` (cumulative: contains WS215 +
  WS218; worktree `/home/moeen/code/ws232-...`, clean, never written).
- Merge-base donor/main: `7725570b`; main-side touched NONE of the donor
  functional paths since MB (verified) — but main-side DID touch shared
  tests/data elsewhere (WS238/WS241/Mordor) → per-file 3-way care there.
- Engine pin unchanged: `xmage-1.4.61` everywhere (no repin, no provider
  selection surface).

## In Scope

- Production port: donor `engine-bridge/src/main/**` (8 files: session,
  bridge, decision controller, player, provider, redactor, projection,
  differential adapter) + donor `src/commander_lab/{engine/rules/full_game*.py,
  agents/pilots.py, semantic_replay/**, candidates/models.py,
  robustness.py}` (exact set in PORT_LEDGER.md).
- Test port: donor new unit tests (variable-player, replay tape, numeric
  WS229, concession, seed binding, hidden-info, combat-damage, name canary,
  decision census/projection); shared test files only by 3-way merge
  keeping main-side updates (WS238 15-assertion, WS241, Mordor).
- Requalification on new base: full bridge suite offline, impacted Python
  suites, replay/twin spot checks (4P primary + 2/3/5P lifecycle via ported
  tests), ruff.
- Evidence: port ledger (per-file donor→base disposition), impact
  adjudication (donor PASS → requalified/retained/UNKNOWN), seal, handoff.

## Out of Scope

- Donor research campaigns (micro-rules/actual-card-29 evidence dirs,
  N-scoped runner scaffolding unless a ported test needs it).
- Engine repin, Forge/mage edits, stale-consumer migration, three-deck
  worktree, PR #206 surfaces, push/merge/PR creation, Architecture Freeze,
  Production Provider, FULL107, behavior credit.

## Ownership

Single writer: this session on this branch/worktree/state only. Donor
worktrees are read-only references (no writes). No other workstream's
branch/worktree is modified.

## Dependencies

- Donor seals (provenance): WS215/WS218/WS229/WS232 handoffs + evidence.
- Pinned xmage-1.4.61 Maven artifacts (offline-capable, verified).
- Existing main-line suites as regression baseline.

## Hard Gates

- Rules Authority preserved: engine owns legality; no second Rules Engine;
  unsupported paths fail closed; no first/random/default/AI/GUI/silent-skip
  fallbacks (TD-repairs are donor-qualified and re-verified, not new
  heuristics).
- Hidden info principal-scoped; explicit-seed RNG; UNKNOWN stays UNKNOWN.
- No donor evidence copied as own PASS: every ported behavior is re-run on
  the new base; retained items need written rationale per item.
- Main-side updates (WS238/WS241/Mordor/publisher) fully preserved.

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no wholesale donor-evidence relabeling; no
`sa.resolve()` substitutes; no green-suite equality with Qualification
PASS; no relabeling donor campaign numbers onto the new base.

## Evidence Requirements

Per ported behavior: expected (donor seal ref) → observed on new base
(DIRECTLY_VERIFIED run output) → verdict (REQUALIFIED_PASS / FAIL /
NOT_RUN + cause). Fail-before: port without donor tests first? No —
tests port WITH code; any red on new base is fail-before evidence, then
repaired only on owned surfaces with root cause.

## Persistence

Per validated milestone: scoped validation, state update, focused local
commit. End with §13 handoff.

## Stop Conditions

Stop only when: all ported production + tests green on new base with sealed
impact adjudication, or a genuine terminal blocker is proven (donor test
red caused by main-side semantic conflict unresolvable on owned surfaces →
escalate with evidence; no weakening of Rules/Evidence invariants to pass).
