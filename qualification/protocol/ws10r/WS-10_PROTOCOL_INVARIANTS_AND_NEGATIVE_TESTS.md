# WS-10R / WS-17 PROTOCOL INVARIANTS AND NEGATIVE TESTS

1. `UNKNOWN != PASS`; `PARTIAL != FULL`; `NOT_RUN != PASS`; `CODE_DERIVED != RUNTIME_VERIFIED`.
2. Required obligations admit only `PASS` (except campaign-disabled G15 may be `NOT_APPLICABLE`).
3. Provider absence becomes `NOT_RUN`, never PASS.
4. A skipped test cannot satisfy a mandatory obligation.
5. Exact-main admission requires `actual_sha == admitted_main_sha`.
6. Qualification evidence is bound to source/build/adapter/authority/denominator hashes.
7. A candidate-specific adapter may not infer legality, calculate targets/costs, synthesize legal options, or choose defaults.
8. Every production-reachable unsupported discretionary path fails closed.
9. Prompts/context/option IDs/labels/metadata/source/ability/pile metadata are part of the hidden-information boundary.
10. Rules RNG and pilot decisions are separate tapes.
11. Seed-only replay is not durable production replay.
12. Clean-process semantic replay must detect extra/missing/changed RNG operations and semantic checkpoint divergence.
13. Process-local UUIDs, memory addresses, wall clock and unstable ordering are excluded from semantic hashes.
14. Import/parse/registration/card-script presence is not card behavioral PASS.
15. Differential verification requires actual execution by two or more providers; disagreement is adjudicated against canonical authority, never majority vote.
16. Forge provider code/classes remain outside the proprietary Commander Lab process.
17. Architecture winner remains unset until all required AF gates are PASS for an eligible provider.
