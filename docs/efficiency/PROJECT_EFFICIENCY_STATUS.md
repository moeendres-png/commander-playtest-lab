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
| M4 | Static arrival-history coverage over every arrival-using lane | DONE (1.0.29, #642) | coverage test over the 99 arrival-using records |
| M5 | Static decision-script preflight over every lane registry | PARTIAL (#645: `test_lane_registry_declarations.py`) | derives all six registries from the lanes (127 records); keeps, arrival, obligation, payments; red control per class. It would have caught the AF07 campaign gap (22 records) and the replay-twin payments before PB-03. Placement and reachability are runtime facts: no static claim is made for them |
| M6 | Run the mid-game probe in parallel with the Forge build | SUPERSEDED by M15 | once Forge leaves the required PB-03 path, its build no longer precedes the probe |
| M7 | Early contract phase before builds | DONE (Codex #629) | — |
| M8 | Atomic correctness remediation of undeclared passes and mana picks | ACTIVE: step A merged (#643, 1.0.30); step B + 1.0.31 data in #645 | the data and the strictness land together; locally 74/74 midgame, 29/29 campaign and 5/5 replay rows on the pinned engine (LOCAL_OBSERVED) |
| M9 | Parallel XMage phases inside the runner | DEFERRED | about 10–12 min per run (≈25 %), but semantics-adjacent: needs a shadow comparison of 3 paired runs (≈ 5 h of runner time). Revisit once correctness cycles stop dominating. |
| M10 | Allow `/oc` on bot-authored PRs (fix rounds in place) | NOT_WORTH_IMPLEMENTING | weakens a deliberate trust gate (agent-written text steering the next agent); the saving is bookkeeping, not evidence |
| M11 | E4 shared engine build artifacts | DEFERRED (#591) | ≈5 min per run; needs provenance-bound shadow validation |
| M12 | E5 reduced Forge compatibility battery | NOT_WORTH_IMPLEMENTING | #502: `NO_SAFE_REDUCTION_DEMONSTRATED` |
| M13 | Enforce the OpenCode time box (step `timeout-minutes: 55`) | DONE (#649) | three runs hung 1–3.5 h on 2026-10-09 (37892171436, 37919745102, 37924003093); all three rescue bundles held no work; the step now fails inside the token lifetime and the rescue path takes over |
| M14 | PB-03 trigger audit covers wildcard test families and child-process inputs | ACTIVE (#648, #646) | five untriggered inputs found and covered; unrecognisable pytest arguments now fail closed |
| M15 | Forge leaves the required PB-03 path (reference-only, on demand) | DONE (this PR; Owner release 2026-10-09) | PB-03 runs `--candidate xmage` unless `workflow_dispatch` sets `forge_reference`; every Forge step is gated on it; the Forge column is the marked carry-forward (`CARRIED_FORWARD_NOT_REEXECUTED`) and the R-3/R-4 step refuses a column presented as fresh. Impact adjudication: no required check changes (`quality`/`security`/`infrastructure`); no XMage gate, row or receipt changes; Forge readiness becomes historical provenance, which the selection (ADR #647, Owner decision 2) makes non-decisional; a Forge differential run stays available on demand. Expected saving ≈ 435 s per run (run 37914716200 measurement) |
| M16 | Run the registry preflight in PB-03's early contract step | PLANNED (after #648 and #645 merge; same workflow file) | turns a record gap from a ≈ 40 min failure into a < 1 min one |
| M17 | Independent XMage full-game replay/privacy audit | ACTIVE (Codex #650/#651) | not duplicated by Claude |

## Process rules adopted

- A strictness change and the data that satisfies it land in **one** PR, or the data lands first. Proof: a PB-03 run on the PR head.
- Every record family that a lane executes is covered by a static test before any runtime run.
- Fix rounds are dispatched with a ≤ 45-minute time box. Superseded PRs are closed immediately with a pointer.
- A record declaration is never a control command. A declared scope bound (for example an obligation pass-through's `until`) only authorizes; the lane's own stop condition decides when a row ends.
- A declared step must be one an engine frame answers in engine order. A step no frame reaches keeps a row from its natural stop.

## Lessons from the #643 cycle (2026-10-09)

- **The rescue artifact paid off once.** An OpenCode run that outlived its token left its work in the rescue bundle (M1); the 1.0.30 data commit was recovered from it instead of being redone. A second rescued run held no commit, which the bundle also showed in one command.
- **PB-03 on the PR head caught both defects before merge.** It found a privacy leak (AF05: a principal-neutral arrival readback on the principal tape during the scripted event) and seven mana declarations placed where no engine frame answers them. Both were found by comparing per-row traces against the sealed epoch's traces, not by rerunning.
- **Trace diff against the last sealed epoch is the fastest diagnosis.** A row that passed on the epoch and fails on the head differs in its decision trace exactly where the change bites. This took minutes; a rerun would have taken 48.
- **Candidate for M5.** Both defects are statically detectable: a lane observation call outside the principal-scoped set during the principal phase, and a declared step whose family has no frame before the row's recorded stop on the last sealed epoch's trace. M5 should check the second against sealed traces.

## XMage-first CI and qualification plan (2026-10-09)

Required checks on `main` (ruleset "CPL - Canonical Main Protection"): `quality`, `security`, `infrastructure`. PB-03 is **not** a required check. Its gating is merge discipline: no merge of a PB-03-triggering PR without a green PB-03 on the exact head. M14 keeps its trigger complete.

| Workflow / job | Now | After the XMage selection is effective |
| --- | --- | --- |
| `ci.yml` (quality, security) | REQUIRED | REQUIRED |
| `production-qualification.yml` (infrastructure) | REQUIRED | REQUIRED |
| `pb03-runtime-qualification.yml` XMage phases | CHANGE-SCOPED (path filter, M14) | CHANGE-SCOPED |
| `pb03-runtime-qualification.yml` Forge phases | CHANGE-SCOPED, same producer (same-producer rule until selection) | REFERENCE ONLY (M15) |
| `pb03-shadow-parallel.yml` | MANUAL | MANUAL |
| `xmage-full-game-conformance.yml`, `xmage-real-4p-smoke.yml` | CHANGE-SCOPED (scope jobs) | CHANGE-SCOPED; extended toward real decks and 5P/6P terminal |
| `h4-docker-materialization.yml` `h4-forge` | CHANGE-SCOPED | REFERENCE ONLY (with M15) |
| `external-engine-integration.yml` | CHANGE-SCOPED | CHANGE-SCOPED (XMage) |
| `ci-definition-integrity.yml` (shadow) | red by design (CI-02) | unchanged |
| Sealed epochs incl. Forge rows | RETAINED HISTORICAL EVIDENCE | RETAINED HISTORICAL EVIDENCE |

## Critical path (XMage-first, 2026-10-09)

1. **#645 (step B + contract 1.0.31).** PB-03 on its head, then merge.
2. **#648 (trigger audit).** Merge, then M16.
3. **PB-03 on `main` and seal.** If every XMage gate except AF11 passes, the Owner's selection takes effect (#255), and then:
   - M15 (Forge reference-only) runs;
   - #592 closes as not planned.
4. **AF11.** Adjudicated against the single-provider (separate-process XMage) topology, then the Freeze decision (Owner).
5. **Product path.**
   - Real 100-card decks with external pilots on the full-game lane.
   - 5P/6P games that reach TERMINAL within the decision cap.
   - Process-isolated batch with per-game replay.
   - A first deck-vs-field study.

## Lessons from the 2026-10-09 afternoon cycle

- **Delegation failed three times in one day.** No OpenCode run delivered a commit, and every rescue bundle was empty. Implementation done directly in the coordinator session delivered 1.0.31, step B and the #646 fix within the same window. Until M13 has proven itself, a stalled run is cancelled at its time box, not after it.
- **Hand-enumerated registries remain the dominant source of PB-03 failures.** This happened in 1.0.28, 1.0.30 and 1.0.31. M5 now derives the registries from the lanes.
- **Local real-engine runs before PB-03 paid off again.** The prototype run over all 29 campaign rows found the placement and colour exceptions, and the delve payment defect in step B, before any PB-03 cycle was spent.
