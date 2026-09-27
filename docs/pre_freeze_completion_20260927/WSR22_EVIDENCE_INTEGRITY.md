# WSR22 evidence-integrity finding — the comparison rests partly on unobserved PASS rows

Date: 2026-09-27
Status: **OPEN — blocks provider comparison and the WSR22 successor merge**
Classification: `DIRECTLY_VERIFIED` (re-verified in source, not relayed from the review)

## Summary

An automated P1 review on PR #278 (the current-main WSR22 successor) raised eight findings against the
WSR22 evidence-generation path. **The two most consequential were re-verified directly in source and
are confirmed.** They establish that part of the FULL107 PASS set was not produced by engine
observation at all.

This is worse than PB-09, and it is independent of it.

## Verified finding 1 — `NATIVE_RUNS` is fabricated evidence

`scripts/assemble_current_boundary_evidence.py:27` defines `NATIVE_RUNS` as a **hard-coded literal**
containing return codes and test counts. `run_native_suite()` — defined at
`scripts/run_current_boundary_qualification.py:189` — is **never called anywhere in the repository**:

```text
$ grep -rn run_native_suite scripts/ src/ tests/
scripts/run_current_boundary_qualification.py:189:def run_native_suite(candidate: str, group: str) -> dict[str, Any]:
```

Only the definition. The assembler consumes the literal and promotes rows from `UNKNOWN`/`BLOCKED` to
`PASS` without any native suite having executed in that run. Re-running the documented qualification
scripts simply re-applies the literals.

This violates AGENTS.md §18: *"Import, parsing, construction, or readback does not prove gameplay
behavior"* — and the campaign's prohibition on manual outcome injection.

## Verified finding 2 — the Rules-RNG binding is not established

In `src/commander_lab/qualification/current_boundary/game_driver.py`, `seed` appears **exactly once**,
as a function parameter at line 298, and is never placed into the create-game request. Every caller
supplies `seed=424242`, and `start_game` is sent an empty body, yet the emitted artifacts record
`requested_seed: 424242` and `engine_owned: true`, plus seed-supported replay evidence.

So the run may use an engine default or unseeded RNG while being reported as explicitly bound. This
directly contradicts the project's Rules-RNG invariant (AGENTS.md §14) and AF04/PB-04's premise that
seed binding is a real, engine-owned property.

## Unresolved finding 3 — three verifications do not observe the engine

- **AF01 action probes** (`af01.py:362`) omit `game_id` and are issued before any game is created, so
  any generic rejection is credited as proof of illegal-action handling. The committed XMage evidence
  rejects them with `game_id must be nonblank` and Forge returns `unknown_game`, yet both receive PASS
  for illegal actions, stale decisions, unsupported decisions, and sole Rules authority.
- **START-2** (`full107.py:359`) validates `starting_player:P1` by reading the fixture's
  required-event list rather than any engine observation, so a run passes whenever it reaches priority
  without exposing a DRAW-named decision.
- **AF03** (`assemble_current_boundary_evidence.py:302`) is marked PASS unconditionally; the only
  `import_deck` request in the code always submits the legal `build_deck()` payload, so no negative
  deck-import probe exists to observe the claimed rejections.

## Unresolved finding 4 — fixture-ID regex promotes rows on any mention

`assemble_current_boundary_evidence.py:152` treats any fixture-ID mention in test source as proof that
the class validates that obligation. The reviewer's own example: `XmageHiddenReplayIntegrationTest.java:283-288`
mentions `HIDDEN_02` only while asserting that loading it **fails** with
`LEGACY_LIBRARY_ORDER_AMBIGUOUS` — and this binding promotes `HIDDEN_02` from `UNKNOWN` to `PASS`.

## Unresolved finding 5 — the per-request bridge timeout is not enforced

`bridge_launcher.py:98` performs a blocking `readline()` and never applies `timeout_s`. A provider that
accepts a request but stalls will hang the qualification forever instead of being classified `TIMEOUT`,
shut down, and stepped over.

## Consequence for the pre-Freeze comparison

| Previously reported | Status after this finding |
|---|---|
| Same-semantics denominator 25/107 | **Upper bound, not a measurement.** Any PASS the assembler promoted rather than observed is inadmissible. |
| XMage 30 PASS / 44 UNKNOWN / 33 BLOCKED | The 30 is an upper bound. |
| Forge 79 PASS / 21 UNKNOWN / 7 BLOCKED | The 79 is an upper bound. |
| AF10 `RUNTIME_EVIDENCE_RELIABILITY = PASS` | **Must be re-derived.** It rests on the fabricated `NATIVE_RUNS`. |
| AF01, AF03, AF09, and the HIDDEN_* promotions | Must be re-derived from actual observation. |

**What is NOT invalidated.** The evidence that genuinely executed remains valid: the runtime log
indices, the real 2P–5P lifecycles and bounded 6P, the real four-seat principal-scoped
hidden-information reads, and the 385 native engine tests. The defect is that the *assembler* promotes
rows to PASS without observing the run.

## Disposition taken

- **PR #278 is not merged** and its review threads are **not** resolved. The repo ruleset
  `CPL - Canonical Main Protection` requires `required_review_thread_resolution: true`, and
  AGENTS.md §10's merge gate requires no unresolved non-outdated P1/P2. Resolving these as
  "won't fix" to force a merge would have integrated fabricated evidence into canonical main.
- **PR #269 is not superseded.** Superseding it would destroy the only honest record of what the
  evidence set contains.
- `--admin` was **not** used. It would bypass the ruleset, which the delegated authority forbids.
- One finding **was** mine and is repaired: `SOURCE_LOCK.json` recorded stale digests for the three
  files whose bytes I changed. Those are resealed mechanically, with a `source_lock_refresh` record
  stating explicitly that this is a provenance reseal and not a re-execution. A
  `known_evidence_defects` block is also recorded in the lock itself, so the defect travels with the
  artifact rather than living only in a PR comment.

## Required remediation (bounded workstream, not a patch)

1. Make `run_native_suite()` actually execute and **persist receipts**; fail closed when a receipt is
   absent, rather than falling back to a literal.
2. Bind the seed through the provider's authoritative seed API and **confirm the returned binding**
   before recording any RNG credit.
3. Replace the fixture-ID regex with explicit positive fixture-to-test receipts.
4. Derive AF01, AF03 and START-2 from recorded probe responses, event-log observations and
   principal-state snapshots — required, forbidden and terminal postconditions.
5. Enforce the per-request deadline around response reads and terminate a stalled process on expiry.
6. Re-run the affected rows, recompute the comparison, and re-seal.

Until that lands, the honest standing is that **no Forge-versus-XMage capability comparison is
admissible**, and the 25/107 same-semantics figure must not be quoted as a measurement.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
