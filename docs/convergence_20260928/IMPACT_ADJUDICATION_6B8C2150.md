# Convergence impact adjudication — Space Bunny into current canonical main

- Converged head: `5f4d6271eb8a44c5715f98def4d6c4ba6de9e314`
- Merge parents: `b27a8ba72c104c2f17ffcddd8ab7bf5e6df4da42` (Bunny) + `6b8c2150e02d0ef6db6f4c4d3df5a104b4e7e890` (canonical main)
- Method: normal history-preserving merge. No rebase, no reset, no force-push, no wholesale `ours`/`theirs`.
- Lineage seals: `SB_INDEPENDENT_BASELINE` (tag `sb-independent-baseline-20260928`, intact),
  `SB_INDEPENDENT_BASELINE_FINAL` (`.foundry/SB_INDEPENDENT_BASELINE_FINAL.json`).

## Verified canonical main, not assumed

`origin/main` resolves to `6b8c2150ed4…`, which is **newer** than the `c9277b90` named in
the Coordinator update. `6b8c2150` contains `c9277b90` (PR #283) and adds PR #281.
PR #280 was already inside `c9277b90`. This was established by fetch and read, not
inherited from the prompt.

## Bunny delta classification

| Bunny mechanism | Class | State in converged tree |
|---|---|---|
| `UnsupportedPlayerCount` — engine refusal is a capability fact, never a lifecycle failure | `STILL_VALUABLE` | present, 8 files |
| `capability_block` — single definition of where capabilities live in the protocol | `STILL_VALUABLE` | present, 6 files |
| `_observed_envelope_refusal` / `_envelope_refusal` — refused count recorded, not fatal | `STILL_VALUABLE` | present, 2 files |
| `resolve_engine_working_directory` — runtime CWD isolation (RUNTIME-01) | `STILL_VALUABLE` | present, 8 files |
| `verify_lab_owned_bridge_identity` — Lab-module identity proof, avoids a category error | `STILL_VALUABLE` | present, 2 files |
| `run_output_prefixes` — auditable run-output exclusion | `STILL_VALUABLE` | present, 2 files |
| `_content_view` — binding metadata excluded from distinctness | `STILL_VALUABLE` | present, 2 files |
| Dual binding mechanisms `LIVE_ENGINE_ENVELOPE` / `STATE_MARKER` | `CONFLICT_REQUIRES_COMBINED_SEMANTICS` | merged; both accepted, fail-closed when neither |
| `no_credit_groups` — refused credit distinguishable from absent credit | `STILL_VALUABLE` | present, 2 files |
| Per-candidate native-credit isolation | `STILL_VALUABLE` | retained; guard test added |
| Module-vs-export discrimination | `STILL_VALUABLE` | retained; prevents stripping legitimate XMage credit |
| launcher: clear inherited conditional identity keys | `STILL_VALUABLE` | merged cleanly; complements PR #281 |
| PB-03 `restoration_admission.py` + engine-own-manifest admissibility | `STILL_VALUABLE` | present |
| Converged Forge identity model (five distinct Forge identities) | `SUPERSEDED` in part | main's PB-09 framing is the current authority; Bunny's five-identity naming retained where it does not contradict |
| `XMAGE_LAB_RUNTIME_AUTHORITY` pinned to a Bunny commit | `INVALIDATED` | superseded by live receipt binding; must not be re-pinned to a stale value |

## Canonical changes preserved

- **PR #279** — provider-readiness and evidence-integrity corrections, false-credit
  removal, source-bound current-boundary truth. No historical inflated PASS restored.
- **PR #280** — Foundry integrity/governance. Artifact indexing, capsule privacy,
  failure clustering, session statistics, test-impact inventory, drift/source-lock
  hardening, governance guards all intact.
- **PR #281** — four-model Foundry readiness and task-routing-neutral policy. No
  `intended_role`, `intended_frequency`, workhorse/frontier/bulk assignment or
  automatic routing was introduced by this campaign. Model selection remains an
  operator decision.
- **PR #283** — XMage principal-scoped hidden-information remediation. Explicit observer
  binding, fail-closed missing/unknown/cross-game observers, actor-scoped projection,
  no opponent hand/library identity leakage, no live principal UUID leakage, and the
  principal-scoping validator semantics all intact and not weakened.

## The two genuine semantic conflicts

**1. START-2 principal observation.** One side selected the observed row by `is_actor`
alone; the other by acting seat plus a validated live-engine envelope. Neither alone is
correct, so the converged driver accepts whichever authoritative mechanism the response
shape actually provides, decided by the response and never by the provider name. The
strong envelope is required only when the provider actually presents
`observer_engine_player_id`. A provider presenting only the state marker is no longer
failed for a field it never claimed — demanding it would reject a correctly bound
observation and then declare the candidate unqualified, inverting the fault onto the
candidate. A provider presenting the engine id and mismatching it still fails closed,
and a reported `observer_seat` contradicting the requested seat is a new finding.

**2. `validate_principal_scoping` envelope requirement.** It demanded
`observer_engine_player_id` from every provider. Now accepts either mechanism and
records which bound. The distinction exclusion is preserved: `is_actor` is consumed by
the binding check and stripped from the distinctness comparison, so it cannot fabricate
distinct views.

## Evidence survival

| Evidence | Verdict |
|---|---|
| XMage principal-scoping runtime verification on #283 | `SURVIVES` — exact-head, runtime-verified, not re-run |
| XMage current-boundary column (`4/0/59/44`) | `SUPERSEDED` — predates #283; historical only, not current evidence |
| Forge pinned column (`1/0/58/48`) | `SUPERSEDED` — predates the Forge PR #5 binding; historical only |
| PB-09 H4-F receipt (pinned upstream `a37a865a`) | `HISTORICAL` — upstream baseline is now attribution/control only per Coordinator |
| Space Bunny pre-convergence evidence | `PRESERVED` in `qualification/preserved/sb-independent-baseline-20260928/` with producing identity |
| Real-game / cardinality / replay mechanisms | `MECHANISM SURVIVES`; the artifacts are re-executable, not yet re-executed post-merge |

No historical artifact was relabelled as current evidence. No PASS/FAIL/UNKNOWN was
changed to make documents agree.

## Validation on the converged tree

- `ruff check .` clean; `ruff format --check .` clean
- strict `mypy src/commander_lab` clean, 275 files
- qualification suite: `405 passed, 2 skipped`
- `tests/foundry/` + `tests/unit/`: `1639 passed, 1 skipped`
- full suite: `2195 passed, 5 skipped`

## Ownership boundary honoured

Forge PR #5 Commander-Lab runtime requalification is owned by the DeepSeek workstream
and was **not** started here. No Forge FULL107 campaign was launched, no Forge bridge
head was rebound, and no Forge evidence surface was touched. `e15f37d6b2b5c0ad682948f86f037e07b6aaded5`
with terminal Java 17 / Java 21 / iOS CI SUCCESS is treated as current source truth.
