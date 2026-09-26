# Workstream Contract — FULL107 native-state injection capability (2026-09-22)

## Objective

Implement the largest technically sound, reusable native-state-restoration
subset supportable by the existing XMage Rules Core (1.4.61, pin db134b97)
without inventing Rules behavior: explicit translation of frozen semantic
starting states into engine-native state, engine-authoritative legality/SBAs,
principal-scoped hidden information, deterministic Rules RNG + semantic
replay, strict native readback with requested-vs-constructed compare, and
fail-closed rejection of unsupported operations. Actual-card positive and
adversarial negative runtime tests; every supported dimension qualified
independently. No mapping promotion in this workstream (executor harness is
the next dependency).

## Source Lock

- Base: `origin/main` `54fb222e3632b4e6e1599d0565d16ee6bec7d9a6`
  (tree `4beb5b7f34ca71ac9c515482740b4469952c69a5`).
- Frozen (READ-ONLY): `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`.
- Engine (READ-ONLY, no pin change): xmage maven `1.4.61`.
- This branch: `cpl/full107-native-injection-20260922`.
- This worktree: `/home/moeen/code/ws-full107-native-injection-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. Publication via scoped PR only.

## In Scope

- `XmageNativeStateRestoration` (new, harness-reachable, production-fail-closed):
  requested-state model → explicit per-object native placement via public
  engine APIs only (`Player.moveCards` zone transitions,
  `CommanderPlaysCountWatcher.restoreStateForGameLoad`,
  `GameState` turn/active/priority setters, `Turn.setPhase`,
  `Player.setLife`, Rules-seed binding); engine SBA/layers re-validation;
  normalized readback (public zones full identity, hidden zones counts-only)
  with strict compare; explicit supported-dimensions descriptor.
- First executable target class: command zone (with cast counts) +
  battlefield (controller/tapped/counters) + life + turn/phase/priority on
  real cards (e.g., WS05-CMD-TAX-2 shape), seed-bound, no hidden identity.
- Positive + adversarial negative Java runtime tests; bridge suite stays green.
- Contract/state/docs updates; scoped validation; commit + push + PR.

## Out of Scope

- Mock-card injection (never); real-deck equivalents earning DIRECT (never);
  frozen WS47 mutation; engine-repo edits; pin changes; mapping reclassification;
  decision-script executor; provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only. All other
worktrees/branches read-only. WS1 closed (PRs #216/#217 merged).

## Hard Gates

- Public engine APIs only; no reflection into privates; no fabricated history
  events; no outcome injection; no legality bypass (post-placement engine
  SBA validation mandatory before readback credit).
- Global `starting_state_injection_supported` stays FALSE; subset exposed only
  via the explicit dimensions descriptor. Never enable on construction-tests
  alone; full advertised semantics required first.
- Hidden information: pilots/evidence/logs never see hidden identities; bridge
  compare sees counts + digests only for hidden zones; any hidden-identity
  request fails closed.
- Deterministic Rules RNG preserved (explicit seed binding, replay MATCH).
- Bridge suite green (no regressions), new tests green locally + CI, ruff clean,
  generator mapping repro byte-identical (no mapping change).

## Forbidden Shortcuts

Per AGENTS.md §2 plus: no second Rules Core; no `sa.resolve()` substitutes;
no silent setup correction; no requested-option filtering reconstructing
legality; no partial-success masquerading (reject before partial execution).

## Evidence Requirements

Per-dimension qualification record; positive/negative runtime test logs;
readback-compare transcripts (counts + digests, no hidden content);
dimensions descriptor; capability flag proof (global false preserved).

## Stop Conditions

Complete when the qualified subset + tests + docs are integrated on main with
green post-merge CI, or a genuine technical/authority blocker (fail closed).
