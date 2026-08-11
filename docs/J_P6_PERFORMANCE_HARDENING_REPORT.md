# J-P6 Performance, Usability and Final Hardening Report

Status: completion candidate. This report becomes final when merged to `main`, the standard post-merge gates pass, and Recovery/Drive roundtrip are verified.

## Truth boundary

Performance numbers below are technical runtime evidence on GitHub-hosted `ubuntu-latest` runners. Simulation outputs remain `structural_model_estimates`; runtime improvement is not deck-strength improvement.

## Frozen baseline

- final J-P5 baseline commit: `0d5dbc633d0776f72e80e271e52234018e80e307`
- baseline tree: `169fee0f88b550f5897324b14451b1086c0b3617`
- package: `1.15.0`
- benchmark policy: `config/J_P6_BENCHMARK_POLICY_v1.json`
- baseline performance run: `31450047116`
- baseline artifact: `9086012106`
- baseline artifact digest: `sha256:8e511c5fd07bbe055c49b3f3f9437b412e45ba8284f3c324edc6b14e71bc1009`
- current-branch profile run: `31450931746`
- current-branch artifact: `9086318726`
- current-branch artifact digest: `sha256:60450a137898a17d557b050e3e783abf5fa5536625d85efa4054d608f4fb7ee1`

## Measured performance

| Benchmark | Baseline median wall s | Current-branch median wall s | Delta |
|---|---:|---:|---:|
| service initialization | 0.1182 | 0.1233 | +4.4% |
| goldfish 50 / 1 worker | 0.8946 | 0.9098 | +1.7% |
| matchup 32 / requested 1 worker | 3.9914 | 4.1169 | +3.1% |
| matchup 32 / requested 2 workers | 4.0267 | 4.1214 | +2.4% |
| matchup 64 / requested 1 worker | 7.8069 | 8.0263 | +2.8% |
| matchup 64 / requested 2 workers | 5.3270 | 5.4509 | +2.3% |
| paired comparison 8 | 0.0280 | 0.0289 | +3.4% |
| card ablation 4 | 0.9377 | 0.9658 | +3.0% |
| package ablation 4 | 0.9621 | 0.9912 | +3.0% |
| commander denial 4 | 1.0111 | 1.0408 | +2.9% |
| sensitivity smoke | 0.3708 | 0.3887 | +4.8% |
| bounded local search | 0.0533 | 0.0596 | +11.9% |
| report generation | 0.0538 | 0.0585 | +8.8% |
| serialization 1,000 | 0.7655 | 0.7779 | +1.6% |
| card lookup 10,000 | 0.00108 | 0.00104 | -4.1% |
| SQLite 1,000 write/read rows | 0.00574 | 0.00494 | -13.9% |

No performance product code was changed between the two profiles. The dominant structural-simulation paths vary by about 2–5% between shared runners. Larger percentages on local search/reporting correspond to only a few milliseconds and are not treated as reproducible regressions. J-P6 therefore does not claim an invented before/after speedup.

## Worker scaling

The measured material bottleneck is structural multiplayer simulation. On the baseline run, 64 games requested with two workers reduced median wall time from 7.8069 s to 5.3270 s (about 31.8%). At 32 games, the two-worker request did not improve runtime because the existing scheduler correctly keeps undersized work serial. The final-branch profile reproduces the same behavior (8.0263 s vs 5.4509 s for 64 games).

Decision: retain the existing evidence-based worker scheduler. No new multiprocessing algorithm is justified.

## Caching / storage / serialization / lookups

- production result cache added: no
- cache hit rate: not applicable
- new SQLite/registry architecture: no
- new card-lookup cache: no
- new serialization cache: no

Reason: measured card lookup and SQLite costs are negligible relative to simulation, and serialization was not shown to dominate the end-to-end decision workflow. Adding infrastructure would be speculative.

## Retained J-P6 hardening changes

1. FastAPI version now follows the package `__version__` instead of stale hard-coded `1.4.0`.
2. Release evidence now reads `docs/J_P3_PROVIDER_DECISION.json` and records real partial XMage/Forge feasibility evidence while retaining the truthful `NO_PROVIDER_READY` / no-production-bridge boundary.
3. Fresh-wheel release verification now executes `commander-lab --help`, not merely import/version inspection.
4. Integrated J-P6 acceptance covers focused P4/P5/P6 regression, RunIdentity/reproducibility, scheduler behavior, API, MCP, CLI, core end-to-end workflows, P5 holdout integrity and canonical deck-hash preservation.
5. A fixed-seed structural matchup is executed twice in the J-P6 regression suite and its result payloads must match exactly.

## Integrated workflow acceptance

J-P6 acceptance run `31450931681` passed all of:

- static integrity / compileall;
- focused P4/P5/P6 decision and runtime regression;
- validate deck;
- inspect deck;
- matchup batch;
- paired variant comparison;
- card ablation;
- package ablation;
- commander denial;
- generic holdout workflow smoke (not the consumed P5 holdout);
- sensitivity;
- variant search;
- recommendation generation;
- report generation;
- CLI help/package identity;
- API package-version parity;
- MCP/API regression suites;
- consumed P5 holdout integrity;
- Korvold/RogShai canonical deck-hash preservation;
- tracked-tree cleanliness.

## Equivalence / decision quality

- semantic equivalence: required and covered by existing full/focused regression suites plus no changes to simulator/optimizer/pilot semantics;
- deterministic equivalence: fixed-seed result equality test plus existing reproducibility suites;
- decision-quality regression: none detected; J-P5 optimizer regression suite remains part of J-P6 acceptance;
- holdout regression: consumed P4/P5 evidence remains immutable/regression-only; P5 evaluation count remains 1 and post-holdout tuning remains false;
- canonical deck mutations: 0.

## API / MCP / OpenAI

CLI/API/MCP preserve existing fail-closed contracts. The OpenAI/Agents workflow remains optional; missing live credentials are handled as an unavailable/503 path rather than a general project failure. No token-cost claim is made because no live LLM cost benchmark was required for the intended offline core workflow.

## External engine

P3 remains unchanged: `NO_PROVIDER_READY`, `BLOCKED_WITH_REAL_EVIDENCE`, no production bridge. J-P6 fixes stale release text so real XMage/Forge feasibility evidence is no longer erased, but does not promote either provider to production readiness.

## Performance optimization decision

No new performance optimization is retained because profiling did not identify a new bottleneck with both a material cost and a safe, measured >5% improvement opportunity. This is a successful P6 outcome: speculative cache/storage/refactor changes were rejected rather than merged without evidence.
