# Project efficiency status

Operational status of the 2026-10-09 efficiency audit (Owner directive). Rules Correctness and
Evidence Integrity take precedence over every item here. Measurements are from GitHub Actions;
Git and GitHub stay Source Truth. Maintained by the Claude Coordinator.

## Fresh state (2026-10-09)

- Lab main `75e4d4a2` (after #631); contract `1.0.28` (#637). mage master `10a73922`, forge master `5f95bd46`.
- Latest sealed epoch `ff688b58359f-42c21a3659cd`: XMage 10/12 AF gates (106/107 rows), Forge 6/12.
- Active work:

  | Owner | Work |
  | --- | --- |
  | Claude | contract 1.0.29 (#634: arrival history for knowledge/replay records, MICRO_PREVENTION, PILOT_TRIGGER_ORDER) |
  | Codex | #628/#629 (PB-03 early contract failure), #638 (Phase86 test reuse) |

## Measurements

### PB-03 (pb03-runtime job)

| Step | Run 37860773242 | Run 37850610320 |
| --- | ---: | ---: |
| Build pinned XMage | 156 s | 154 s |
| Build and warm Forge | 133 s | 124 s |
| Mid-game probe | 357 s | 346 s |
| Two-candidate runner | 2148 s | 1937 s |

- The 12 most recent successful runs took 1970–2911 s each (33–49 min).
- **11 of those 12 ran on pull-request heads**: 6 on the #592 OpenCode fix chain alone, most of whose PRs were later superseded.

### All workflows on one PR head (#637)

| Job | Duration |
| --- | ---: |
| pb03-runtime | 2907 s |
| conformance | 749 s |
| quality | 642 s |
| mutation-detection | 385 s |
| build-and-integrate | 368 s |
| everything else | < 200 s each |

All jobs run in parallel, so wall-clock time is PB-03. About 5800 runner-seconds are spent per PR head.

### Agent and coordination cost observed (2026-10-07…09)

- **Lost work:** 3 OpenCode runs lost all their work when the one-hour action token expired.
- **Unintended closures:** 2 issues were closed by closing keywords in bot commit messages.
- **PR churn:** about 10 fix-round PRs were superseded, because `/oc` cannot target a bot-authored PR (a deliberate trust gate).
- **Wasted PB-03 cycles:** 3 cycles (≈ 2.5 h of runner time plus ≈ 2 h of latency) failed on record gaps that were statically detectable. #625 (strict arrival) landed before the arrival-history errata, which made 73/74 midgame rows fail closed. Contract 1.0.28 later exposed the knowledge/replay records only at runtime.

## Root causes, ranked by lost time to qualified progress

1. **Late detection of incomplete records/scripts.** Decision-script completeness was checked only inside a 45-minute runtime run.
2. **Non-atomic integration.** A strictness change merged before the data that satisfies it.
3. **Agent tooling failure modes:** token expiry, closing keywords, PR churn.
4. **PB-03 wall-clock.** The runner's XMage phases run serially; the probe waits for the Forge build.

## Measures

| # | Measure | Status | Evidence / reason |
| --- | --- | --- | --- |
| M1 | Keep a failed OpenCode run's work as a secret-scanned artifact | DONE (#633) | security review SAFE; planted-token control blocks the upload |
| M2 | Forbid closing keywords in OpenCode commits and PR bodies | DONE (#636) | footer test; #255 and #626 reopened |
| M3 | Handoff index derives lanes from open issues | DONE (#636) | tests |
| M4 | Static arrival-history coverage over every arrival-using lane | ACTIVE (1.0.29, #634) | — |
| M5 | Static decision-script preflight: family transport coverage, seats, scopes, actors, produced-by links | PLANNED (after M4) | — |
| M6 | Run the mid-game probe in parallel with the Forge build | PROPOSED to the owner (#628) | ≈125–135 s per run, no evidence change |
| M7 | Early contract phase before builds | ACTIVE (Codex #629) | — |
| M8 | Atomic correctness remediation of undeclared passes and mana picks | QUEUED (#634, after M4) | — |
| M9 | Parallel XMage phases inside the runner | DEFERRED | about 10–12 min per run (≈25 %), but semantics-adjacent: needs a shadow comparison of 3 paired runs (≈ 5 h of runner time). Revisit once correctness cycles stop dominating. |
| M10 | Allow `/oc` on bot-authored PRs (fix rounds in place) | NOT_WORTH_IMPLEMENTING | weakens a deliberate trust gate (agent-written text steering the next agent); the saving is bookkeeping, not evidence |
| M11 | E4 shared engine build artifacts | DEFERRED (#591) | ≈5 min per run; needs provenance-bound shadow validation |
| M12 | E5 reduced Forge compatibility battery | NOT_WORTH_IMPLEMENTING | #502: `NO_SAFE_REDUCTION_DEMONSTRATED` |

## Process rules adopted

- A strictness change and the data that satisfies it land in **one** PR, or the data lands first. Proof: a PB-03 run on the PR head.
- Every record family that a lane executes is covered by a static test before any runtime run.
- Fix rounds are dispatched with a ≤ 45-minute time box. Superseded PRs are closed immediately with a pointer.
