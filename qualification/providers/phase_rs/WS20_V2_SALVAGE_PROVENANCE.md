# WS-20 v2 — Controlled Salvage Provenance

Status: `POST_WS17R_RESTART`

Old evidence class: `PROVISIONAL_PRE_WS17R` / `HISTORICAL_PROVENANCE`

No pre-WS17R qualification result in this document satisfies a current AF gate.

## New authoritative baseline

- repository: `moeendres-png/commander-playtest-lab`
- commit: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- tree: `551c0d55a171508618d2b7d29e0f49b19893f886`
- restart branch: `ws20/phase-rs-remediation-requalification-v2`
- coordinator reference run: `33262473086`
- independent WS-20 v2 baseline reproduction run: `33263002771`
- baseline reproduction result: process `SUCCESS`, common tests `PASS`, 135-fixture manifest `PASS`, provider-absence aggregate `FAIL` with 135/135 `NOT_RUN`, WS-17R repair-preservation checks `PASS`.

The earlier WS-20 branch is not rebased in-place. Candidate-specific work is reviewed and transferred selectively.

## Frozen old branch provenance

- branch: `ws20/phase-rs-remediation-requalification`
- head: `64c13f85a1a8e9f4fd9aa511e109c1727011774e`
- tree: `c2b26ead1c7781653db5d972cbcd3177ed7a0d97`
- merge base / superseded baseline: `9665c9d5dc5e720240b99f88300176c7a4a0f4fa`
- old workflow run: `33259791903`
- old workflow artifact: `9717187293`
- artifact name: `ws20-phase-rs-evidence-8197fd6318c06adfb7caaec3114924032609cfd8`
- artifact archive digest: `sha256:136c718bf3fcfbba25fe216aab6c865c0bca05f1fffa0c20b770cfbe7ca808ec`

Historical runtime artifact contents recorded before restart:

- old candidate upstream commit: `bc218c51cec9cc2cec56f5c4de7c72be3d8e331c`
- old candidate upstream tree: `6e3f70d7de25c1f28919b73b2ee32654ee866ac0`
- old patched tree: `711a0ee7fdc5834161b4e9814b3789b56ed76bb0`
- old remediation patch SHA-256: `24a15744a481fa3ca43f377ed4ed3b6fa575e1ef9cc1a905a029ab6e412d7f4c`
- old common manifest SHA-256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
- old WS-10R bundle SHA-256: `2f002a4d020e99e44270239fd3a894e9be6f08eddf9fdd233b81ba8d3f070577`
- old pre-patch reproducer result: `FAIL_AS_EXPECTED`
- old post-patch observations: historical only; must be regenerated.

## Old commit / path classification

| Old commit | Path | Classification | v2 handling |
|---|---|---|---|
| `923c45a177149114ce28e0eb5079590a3a77e44e` | `qualification/providers/phase_rs/PINNED_SOURCE.json` | `REWRITE_FOR_NEW_BASELINE` | Do not copy stale source lock; rebuild from fresh upstream inspection. |
| `4c87ed4baaedf41aba1bc87dfd4e6cb2ee653020` | `qualification/providers/phase_rs/apply_ws20_changeling_remediation.py` | `SALVAGE_RULES_PATCH_OR_ORCHESTRATION`, `SALVAGE_REGRESSION_TEST` | Review semantics against fresh `commander.rs`; update exact source identity; rerun pre/post patch tests. |
| `b5b0da6d1af5ec79441c60e02fe94a3e0249d33a` | `qualification/providers/phase_rs/ws10r_provider.py` | `SALVAGE_PROVIDER_CODE` | Retain fail-closed transport design; update build/source identity and re-audit boundary. |
| `8197fd6318c06adfb7caaec3114924032609cfd8` | `.github/workflows/ws20-phase-rs-qualification.yml` | `REWRITE_FOR_NEW_BASELINE` | Do not transplant old workflow; reconstruct v2 workflow preserving WS-17R dependency/import/checksum repairs. |
| `cf503e4bb2db4416928208c47d9dad5c6dd1b96c` | `scripts/ws20_phase_rs_card_crosswalk.py` | `SALVAGE_RULES_PATCH_OR_ORCHESTRATION`, `REWRITE_FOR_NEW_BASELINE` | Reuse source-presence-vs-runtime distinction; make source identity dynamic/current. |
| `990efa41e3b9ad1c80c8ef62ced2cf6a49c5a559` | `scripts/ws20_build_candidate_evidence.py` | `REWRITE_FOR_NEW_BASELINE` | Do not reuse hard-coded AF verdict logic. Current AF results must derive from regenerated evidence. |
| `64c13f85a1a8e9f4fd9aa511e109c1727011774e` | `tests/qualification/test_ws20_phase_rs.py` | `SALVAGE_REGRESSION_TEST` | Review and update exact source/build assertions; retain fail-closed provider negatives. |

## Explicit drops

The following old outputs are `DROP_OLD_QUALIFICATION_EVIDENCE` and are never transplanted as current evidence:

- old `candidate-verdict.json`;
- old `phase-rs-common-fixture-results.json`;
- old `qualification-matrices.json`;
- old generated AF results;
- old common/admission aggregates;
- old runtime logs as gate satisfaction;
- old source lock as current identity;
- old patch/build identity as current identity.

No shared WS-10R semantics, common manifest, obligation catalog, or global cross-candidate aggregate change exists in the old WS-20 commit series. Any future candidate-local change that would alter those shared artifacts is `DROP_SHARED_INFRASTRUCTURE_CHANGE` by policy and must not be made in WS-20.

## WS-17R preservation rule

The restart branch must preserve from baseline:

- exact-main committed dependency installation (`python -m pip install -e '.[dev]'`);
- qualification runtime import probe including `jsonschema`;
- runtime checksum self-exclusion for `qualification/aggregate/runtime/SHA256SUMS`;
- `tests/qualification/test_ws17r_exact_main_runtime.py` regression coverage.

The independent v2 baseline reproduction workflow verifies those properties before candidate qualification.

## Commit mapping policy

No old commit is cherry-picked wholesale at restart. New commits are manual semantic transfers from reviewed old paths, so old→new mapping is recorded in this file and in the new commit messages. This avoids importing stale baseline/source/evidence identity while preserving salvageable candidate logic.
