# Post-Freeze Bootstrap Plan (exact sequence AFTER the Coordinator claims Freeze)

Precondition: Frozen ADR complete per its checklist; `ARCHITECTURE_FREEZE =
CLAIMED` with date + Coordinator identity. Nothing below executes before that.

| # | Step | INPUT | OWNER | OUTPUT | HARD GATE | FAILURE SEMANTICS | VALIDATION |
|---|---|---|---|---|---|---|---|
| 1 | Verify Frozen ADR | ADR draft + evidence bundle | Coordinator + bootstrap owner | Checked fill-checklist, schema-validated freeze record | All 15 checklist boxes checked | Missing fill ⇒ STOP, no bootstrap | WSR24 validators on the freeze record |
| 2 | Verify selected provider pin | Frozen ADR pin | Bootstrap owner | Byte-identical checkout + artifact SHA-256 match | Commit/tree/SHA-256 all match | Mismatch ⇒ STOP (repudiate pin, return to Coordinator) | Hash verification log |
| 3 | Create private Production Repository | Frozen ADR §§1–7, 25–26 | Bootstrap owner | Repo with `rules-provider/ adapter/ contracts/ pilot/ orchestration/ replay/ qualification/ evidence/` skeleton | Skeleton matches PRODUCTION_REPOSITORY_CONTRACT §3 | Wrong boundary ⇒ repair before any code | Layout conformance test |
| 4 | Install governance | Contract §§6, 9 | Bootstrap owner | Source-lock mechanism, evidence-sealing procedure, N1–N8 CI gates | All 8 no-fallback invariants CI-enforced | Any unenforced invariant ⇒ STOP | Adversarial negative suite green |
| 5 | Install source-lock mechanism | Frozen ADR §26 | Bootstrap owner | Per-build lock records (Lab + provider + adapter + schemas) | Every build emits a lock record | Missing record ⇒ build rejected | Lock-presence test |
| 6 | Add Protocol schemas | Frozen ADR §§8–9; `contracts/` | Bootstrap owner | Versioned protocol + envelope schemas | Schema blob equals Frozen ADR identity | Drift ⇒ STOP | Blob-identity test |
| 7 | Implement provider process/adapter boundary | Frozen ADR §§10–11; SLOT-03 ruling | Remediation owner | Provider process + adapter with shim + fail-closed matrix | AF04/AF11 probes PASS on production lane | Non-PASS ⇒ STOP, repair | AF04/AF11 gate tests |
| 8 | Add observation contract | Frozen ADR §§14–15; SLOT-04 ruling | Remediation owner | Principal-scoped projection + honeycard negatives | AF05 scenario set PASS | Leakage ⇒ STOP (breach), repair | AF05 gate tests |
| 9 | Add legal-action/decision contract | Frozen ADR §§16–18 | Remediation owner | Decision submission path with provenance tests | Shim provenance + fail-closed tests green | Breach ⇒ STOP, repair | Adapter test suite |
| 10 | Add Rules RNG/replay contract | Frozen ADR §§19–20; SLOT-09 | Remediation owner | Seed binding + tape/checkpoint/hash machinery | Engine-owned RNG test + twin harness ready | Harness RNG ⇒ STOP (breach) | RNG/replay contract tests |
| 11 | Add process isolation | Frozen ADR §§21–22 | Bootstrap owner | One-game-per-process + limits + supervision | Isolation negatives green | Shared state ⇒ STOP, repair | Isolation test suite |
| 12 | Implement first complete-game slice | FIRST_PRODUCTION_VERTICAL_SLICE_CONTRACT.md | Slice owner | Real 4P game to terminal state with evidence bundle | All 13 slice requirements + carried gates | Any breach ⇒ slice FAIL per its §5 | Slice exit-gate suite |
| 13 | Qualification | Impact template §3 | Qualification owner | AF00–AF11 all-PASS + schema-validated `freeze_eligible=true` (standing record, not a second Freeze) | 12 PASS + capabilities present | Non-PASS ⇒ STOP, remediate | WSR24 validators + gate suites |
| 14 | CI | All contract/test suites | Bootstrap owner | Green pipeline with N1–N8 enforced on every change | Adversarial negatives run per change | Weakened assertion ⇒ STOP, restore | Pipeline + mutation spot-checks |
| 15 | Reproducibility | Replay contract | Qualification owner | Clean-process twin matrix green; seed+tape rebuild verified | Terminal-hash equality per fixture | Mismatch ⇒ STOP, diagnose | Twin matrix |
| 16 | Batch runner | Orchestration | Slice owner | Process-isolated batch execution (post-determinism) | No shared mutable state across games | Sharing ⇒ STOP, repair | Batch isolation tests |
| 17 | Only later: performance/pilot optimization | Working game system | Future workstream | Faster/stronger play with invariants intact | N1–N8 stay green; AF gates unaffected (else requalify) | Correctness regression ⇒ revert | Full gate suite |

Notes:

- Steps 7–10 may proceed in parallel by different owners ONLY if the
  single-writer surfaces stay disjoint; the Frozen ADR is read-only shared
  input.
- Step 13's record confirms the production system, not a second Freeze claim.
- Pilot optimization (17) is last by policy: Rules Correctness outranks
  performance and convenience.
