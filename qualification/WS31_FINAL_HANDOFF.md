# WS-31 — FINAL HANDOFF

## WORKSTREAM CONTRACT

### Objective
Materialize a reproducible, source-locked, authoritative Oracle/rules domain for the full known actual-card universe used by `moeendres-png/commander-playtest-lab`, and close WS-31 only when the complete 1,385-identity denominator and all dependent authority gates are terminal PASS.

### Inputs
- WS-29 canonical authority closure base.
- WS-31 frozen known-actual-card universe: 1,385 identities.
- Physical canonical inventory: 1,338 identities.
- Current RogShai: 87 unique identities.
- Current Kaervek: 77 unique identities.
- WS-04 rules-path taxonomy input.
- WS-29 exact 29-card regression baseline.
- Current official Comprehensive Rules.
- Current official Gatherer/Oracle plus official Wizards release notes/rulings where required by the observed current presentation.

### Authority
1. newest direct user instruction;
2. freshly verified exact repository state;
3. current Comprehensive Rules and current official Wizards/Gatherer authority;
4. runtime evidence from executed GitHub Actions;
5. historical workstream artifacts only as provenance.

Secondary card-data sources are forbidden as authority for this workstream. No Forge, XMage, MTGJSON, Scryfall, or local-cache card semantics were used to promote a card to PASS.

### In Scope
- exact 1,385-card authority acquisition;
- 1,338 physical-card subset materialization;
- RogShai and Kaervek current subsets;
- multiface identity/face authority;
- current CR lock;
- WS-29 regression preservation;
- rules-path incidence materialization;
- invalidation/digest model;
- fail-closed terminal status materialization;
- exact-head closure validation.

### Out of Scope
- selecting a Rules Core;
- awarding runtime card-functionality credit from Oracle/import/parsing;
- changing candidate engines;
- filling the 142 unknown real-opponent slots excluded by the frozen WS-31 denominator.

### Dependencies
- Base branch: `ws29/canonical-authority-closure`
- Base commit: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- Base tree: `e510af2fd8a05f7db874781e3182a6bf3c062fc4`

### Required Deliverables
- authoritative 1,385-card normalized domain;
- authoritative 1,338-card physical subset;
- current RogShai and Kaervek authority subsets;
- multiface authority manifest;
- rules-path incidence;
- current CR lock;
- WS-29 regression result;
- `COVERAGE.json` and `WS31_RESULT.json` terminal closure state;
- `SHA256SUMS` covering generated normalized outputs;
- this final handoff;
- exact-head final-validation artifact.

### Hard Gates
- authority: 1,385 / 1,385 PASS;
- UNKNOWN = 0;
- FAIL_CLOSED = 0;
- physical: 1,338 / 1,338 PASS;
- RogShai: 87 / 87 PASS;
- Kaervek: 77 / 77 PASS;
- multiface unresolved = 0;
- rules-path incidence unresolved = 0;
- WS-29 regression = PASS (29 / 29);
- current CR lock = PASS;
- `overall_authority_status = PASS`;
- `workstream_close_gate = PASS`;
- `workstream_status = PASS_CLOSED`;
- exact-head final validation must verify the committed `SHA256SUMS`, authorized diff boundary, and exact commit/tree.

### Evidence Requirements
Only executed runtime evidence is sufficient for terminal PASS. Static/code-derived claims are not runtime proof. Import or parsing does not imply card functionality. Authority-domain PASS conveys identity/Oracle/rulings authority only and grants zero Rules-Core/runtime-functionality credit.

### Stop Conditions
Fail closed on any nonzero UNKNOWN/FAIL_CLOSED count, unresolved multiface/rules-path incidence, CR mismatch, WS-29 regression failure, unauthorized diff path, candidate-engine modification, SHA256 mismatch, or exact-head final-validation failure.

---

# SELF-CONTAINED HANDOFF

## Source Lock

Repository: `moeendres-png/commander-playtest-lab`

Frozen base:
- branch: `ws29/canonical-authority-closure`
- commit: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- tree: `e510af2fd8a05f7db874781e3182a6bf3c062fc4`

Frozen domain locks:
- known actual identities: **1,385**
- known-actual name-set SHA-256: `8dcc2bd8460f23f42a86b8db9c2b96a880f76219fad6ba194d1f1009acf09bbe`
- physical identities: **1,338**
- physical name-set SHA-256: `f1f3ca4240a6d3ae1c3294c1c5b4f6d09ce456d463527997a541fa769a2206c4`
- current RogShai: **87** unique identities
- current Kaervek: **77** unique identities
- unknown real-opponent slots: **142**, explicitly excluded/unfilled
- expected current CR raw-byte SHA-256: `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`

Canonical source-lock artifact: `qualification/ws31/WS31_SOURCE_LOCK.json`.

## Work Completed

1. Built the exact 1,385-identity machine-readable acquisition manifest.
2. Implemented resumable four-shard current Gatherer acquisition with fail-closed identity/face validation.
3. Hardened exact-name discovery without allowing discovery hints to become authority by themselves.
4. Added current official Wizards release-note authority handling for the two observed shared-primary Gatherer representations:
   - `Brazen Borrower // Petty Theft`;
   - `Inspired Skypainter // Maestro's Gift`.
5. Added a finite current-Gatherer reconciliation path for the observed legacy BOK flip-card representation:
   - `Faithful Squire // Kaiso, Memory of Loyalty`.
   This path requires both current official Gatherer URLs for BOK #3, exact face/printing agreement and P/T agreement; no secondary source or hard-coded Oracle text supplies the authority fields.
6. Reacquired and locked the current official Comprehensive Rules in the materialization run.
7. Materialized normalized authoritative outputs for the 1,385-card universe, physical 1,338 subset, RogShai, Kaervek, multiface authority, rules-path incidence, invalidation model and WS-29 regression.
8. Preserved fail-closed semantics and explicitly retained `runtime_functionality_credit = 0`.
9. Added an exact-head final-validation workflow that checks authorized WS-31 diff boundaries, candidate-engine non-modification, terminal closure tests, `SHA256SUMS`, and emits exact commit/tree evidence.

## New Findings

### Shared-primary Gatherer presentation
Current Gatherer does not independently expose all requested secondary faces in a form sufficient for the generic face parser. Current official Wizards release notes can authoritatively close the two observed cases when the primary Gatherer face is current and the release-note page itself is fetched live from the official Wizards host and exactly parsed.

### Legacy flip-card presentation
For `Faithful Squire // Kaiso, Memory of Loyalty`, the current exact Kaiso Gatherer URL confirms the reverse face identity/printing/P/T while the current Faithful Squire page contains the embedded Kaiso type/rules block. Reconciliation of those two current official pages, constrained to the same BOK #3 printing and cross-checked P/T, closes the identity without secondary authority.

### Authority is not functionality
The completed domain proves current authority materialization, not executable card behavior. `runtime_functionality_credit` remains **0** and no Rules Core is selected by WS-31.

## Changes

WS-31 changes are restricted to the authorized workstream boundary:
- `.github/workflows/ws31-authority-domain.yml`
- `.github/workflows/ws31-final-validation.yml`
- `qualification/ws31/**`
- `qualification/WS31_FINAL_HANDOFF.md`
- `scripts/ws31_*.py`
- `tests/qualification/test_ws31_authority_domain.py`

No Forge/XMage/phase.rs/Argentum engine path is changed by WS-31.

Materialized authority-domain commit produced by the successful runtime materializer:
- commit: `37475513a31523de723402d208a0453839495578`
- tree: `5eeeb465fb5a92a05c9d69c14fbdb7532aede734`
- parent authority-code head: `e624ee46634337a7d2a938670ed06a95e91eff5b`

This handoff commit necessarily follows the materialized-data commit. The final validation artifact is authoritative for the exact final handoff commit/tree; the handoff does not self-embed its own Git hash to avoid a self-referential hash cycle.

## Tests / Evidence

### Terminal Authority Run
Workflow: **WS-31 Full Actual-Card Oracle Domain**

- run number: **#18**
- GitHub Actions run ID: **33384808218**
- acquisition/code head: `e624ee46634337a7d2a938670ed06a95e91eff5b`
- static job: PASS
- all four acquisition jobs: PASS
- materialize job ID: **99466972687** — PASS

Shard results:
- shard 0: **347 / 347 PASS**
- shard 1: **346 / 346 PASS**
- shard 2: **346 / 346 PASS**
- shard 3: **346 / 346 PASS**
- total: **1,385 / 1,385 PASS**
- UNKNOWN: **0**
- FAIL_CLOSED: **0**

Run #18 authority-domain evidence artifact:
- artifact ID: **9755392118**
- artifact name: `ws31-authority-domain-evidence`
- artifact digest: `sha256:1c98cf09595670192b0e9904ca0c9331cc088fdeb21de5dbdbaebcd5e6dea9df`

Shard artifact IDs / digests:
- shard 0: `9755257669` / `sha256:d1c65a734e4ef01623537d8926cc3525d6e0dfa03e4df3b8ecbdd9f6b0b288e3`
- shard 1: `9755227837` / `sha256:b427dacf2cbe0c006c3886aa432bf50c9c8219b0a79ea1414e974346fc0bd1d5`
- shard 2: `9755384468` / `sha256:7f71f64457ee150e9f6cdc7c29f27d1ef800803aaf69a7ef5ba22eab1c9a5973`
- shard 3: `9755375237` / `sha256:376058cc71822b17e8c7622ad5320457dd9d1ae780bfcf9054f0d4b4d1175f5f`

### Materialized terminal coverage
`qualification/ws31/generated/COVERAGE.json` records:
- `authority_pass = 1385`
- `authority_unknown = 0`
- `authority_fail_closed = 0`
- `terminal_acquisition_records = 1385`
- `physical_pass = 1338`
- `rogshai_pass = 87`
- `kaervek_pass = 77`
- `multiface_unresolved_count = 0`
- `rules_path_incidence_unresolved_count = 0`
- `ws29_regression = PASS`
- `current_cr_lock = PASS`
- `overall_authority_status = PASS`
- `workstream_close_gate = PASS`
- `runtime_functionality_credit = 0`
- aggregate domain digest: `d8337dc0a243fddbede3e9d2cec7b3938a1007970a23dea04855149fbfc55d5e`

`qualification/ws31/generated/WS31_RESULT.json` records:
- `workstream_status = PASS_CLOSED`
- `candidate_engine_changes = 0`
- `no_rules_core_selected = true`

### WS-29 regression
- expected denominator: **29**
- result: **29 / 29 PASS**
- materialized gate: `ws29_regression = PASS`

### Current CR
- reacquisition step: PASS
- materialized gate: `current_cr_lock = PASS`

### Multiface / rules-path closure
- multiface identities: **13**
- multiface unresolved: **0**
- rules-path incidence unresolved: **0**

## PASS / FAIL / UNKNOWN

### PASS
- Full known-actual-card authority denominator: **1,385 / 1,385**.
- Physical subset: **1,338 / 1,338**.
- RogShai: **87 / 87**.
- Kaervek: **77 / 77**.
- Multiface unresolved: **0**.
- Rules-path incidence unresolved: **0**.
- WS-29 regression: **PASS**.
- Current CR lock: **PASS**.
- `overall_authority_status`: **PASS**.
- `workstream_close_gate`: **PASS**.
- `workstream_status`: **PASS_CLOSED**.
- Candidate-engine changes: **0**.
- Rules Core selection: **none**.

### FAIL
None in the terminal materialized WS-31 authority domain.

### UNKNOWN
None inside the frozen 1,385-card WS-31 denominator. The separately frozen 142 unknown real-opponent slots remain intentionally outside this denominator and were not silently converted into known cards.

## Remaining Blockers

No authority-domain blocker remains.

The sole remaining closure action after committing this handoff is mechanical exact-head final validation. It must PASS on the exact commit containing this handoff and must verify `qualification/ws31/generated/SHA256SUMS`. Its uploaded `ws31-final-validation` artifact is the authoritative exact final commit/tree evidence.

## Outputs

Canonical generated outputs:
- `qualification/ws31/generated/ACQUISITION_STATUS_MANIFEST.json`
- `qualification/ws31/generated/CARD_RULES_PATH_INCIDENCE.json`
- `qualification/ws31/generated/COVERAGE.json`
- `qualification/ws31/generated/CURRENT_CR_LOCK.json`
- `qualification/ws31/generated/CURRENT_KAERVEK_ORACLE.json`
- `qualification/ws31/generated/CURRENT_ROGSHAI_ORACLE.json`
- `qualification/ws31/generated/KNOWN_ACTUAL_CARD_ORACLE_1385.json`
- `qualification/ws31/generated/MULTIFACE_AUTHORITY.json`
- `qualification/ws31/generated/ORACLE_INVALIDATION_MODEL.json`
- `qualification/ws31/generated/PHYSICAL_CARD_ORACLE_1338.json`
- `qualification/ws31/generated/WS11_HELPER_DELTA.json`
- `qualification/ws31/generated/WS29_REGRESSION.json`
- `qualification/ws31/generated/WS31_RESULT.json`
- `qualification/ws31/generated/SHA256SUMS`
- `qualification/ws31/WS31_SOURCE_LOCK.json`
- `qualification/WS31_FINAL_HANDOFF.md`

## Dependencies Unblocked

WS-31 authority-domain consumers may now rely on a terminal, source-locked actual-card authority denominator for later qualification/admission work, subject to the project-wide rule that authority/import/parsing does **not** prove runtime card functionality.

WS-31 does not select a candidate Rules Core and does not relax any production-admission gate.

## Exact Next Action

Run/observe `.github/workflows/ws31-final-validation.yml` on the exact commit created by this handoff. Require:
1. authorized diff boundary PASS;
2. terminal WS-31 tests PASS with `WS31_REQUIRE_CLOSE=1`;
3. `sha256sum -c qualification/ws31/generated/SHA256SUMS` PASS;
4. uploaded `ws31-final-validation` artifact containing the exact `commit` and `tree`;
5. PR #145 updated with the terminal Authority Run #18 evidence ID, final-validation run/artifact IDs, exact commit/tree, and PASS_CLOSED counts;
6. PR #145 remains **Draft**, open, unmerged.
