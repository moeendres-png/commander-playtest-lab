# Muse XHIGH independent donor intake — 2026-09-28

## Source lock

Canonical main at intake:
- commit: `c0915113626262843cb00801d7f6f76579654e9a`
- tree: `433fae3b1d0547a9aa4d363fd8df2f454cf19088`

PR #284 at intake:
- branch: `sol/final-integration-salvage-20260928`
- head before donor intake: `9361afaec0b47a7b3fdb74204e05ccf9906c2283`
- tree before donor intake: `13cec0a1a446bbdda8853a316e16291ccc356508`

Muse donor:
- branch: `donor/muse-xhigh-independent-20260928`
- head: `b7b16ef858e2d88bbb2946710eb054afe1246b78`
- tree: `1b6320abc0024bd90c093f9e68ecf056b88c0d3f`
- preserved pre-freeze Muse head: `d6d071cd92e037efdc68d6585d7aceb9331acf5e`
- preserved pre-freeze Muse tree: `e28c0d301d2230aed9b8ba2c7c8292d6d199378c`
- merge base with current main: `c9277b90ed3835985dcd21824cfe1762b3f65dcd`

The donor is read-only provenance. It is not merged, rebased, or rewritten.

## Unique commit inventory and adjudication

| Muse commit | Subject | Classification | Disposition |
|---|---|---|---|
| `81ada1e2` | initialize Muse campaign state | TEST_OR_EVIDENCE_ONLY | Preserve only as donor provenance. |
| `0f281841` | Muse completion contract | TEST_OR_EVIDENCE_ONLY | Historical workstream contract; current authority has moved on. |
| `abb747a7` | source-truth/blocker/isolation setup | SUPERSEDED_BY_CANONICAL | Current main and #284 are newer authority. |
| `04d3e599` | WSR22 current-boundary transplant | SUPERSEDED_BY_CANONICAL | Canonical #279/#280 lineage already contains later evidence-integrity remediation; no wholesale transplant. |
| `022782ad` | transplant checkpoint | TEST_OR_EVIDENCE_ONLY | Preserve as lineage only. |
| `0a36e47e` | PB-03 Wave 1 + PB-10 + Tier-1 executions | UNIQUE_STILL_VALUABLE | Mixed commit: PB-10 code fix is already canonical; PB-03 seam tests remain useful only after current-source validation. |
| `c8cc9b39` | PB-03 Wave 2a commander-zone characterizations | UNIQUE_STILL_VALUABLE | Characterization tests are useful donor material; generated verdicts receive no automatic credit. |
| `164f166b` | independent baseline + pristine Forge PB-09 run | UNIQUE_STILL_VALUABLE | Pristine Forge run is useful evidence, but not qualification credit because engine commit binding was operator-supplied and PB-05 remained open. |
| `cb185e58` | convergence merge to older main | SUPERSEDED_BY_CANONICAL | Historical merge only. |
| `468360a8` | PB-03 Wave 2b/c executions + impact matrix | UNIQUE_STILL_VALUABLE | Tests/characterizations are salvage candidates; generated result promotion requires fresh current-source revalidation. |
| `d6d071cd` | merge PR #283 into Muse | SUPERSEDED_BY_CANONICAL | PR #283 is already canonical main. |
| `b7b16ef8` | donor freeze | TEST_OR_EVIDENCE_ONLY | This is the immutable donor endpoint. |

## PB-10 finding

Muse independently identified that source-text fixture-name matching could promote a row even when the matching test asserted failure rather than the obligation.

Example: `HIDDEN_02` could be promoted from a mere name mention in a test whose actual assertion was `LEGACY_LIBRARY_ORDER_AMBIGUOUS`.

This defect is **ALREADY_PRESENT / FIXED CANONICALLY** at current main and #284:

- `scripts/assemble_current_boundary_evidence.py::native_bindings()` explicitly refuses source-text name matching;
- credit is derived from persisted positive execution receipts only;
- absent/rejected receipts yield no native credit;
- `tests/qualification/test_current_boundary_receipts.py::test_negative_assertion_cannot_promote` pins the exact HIDDEN_02 failure mode.

Therefore no Muse assembler code is ported and no frozen generated column is rewritten.

## PB-03 donor value

Muse produced three classes of PB-03 material:

1. **Dimension/seam characterization**
   - `XmagePb03DimensionAdmissionTest`
   - `test_pb03_dimension_admission.py`
   - the `REQUIRED_DIMENSIONS` / tier model in donor `full107.py`

2. **Obligation-executing / characterization suites**
   - `XmagePb03Tier1RowsTest`
   - `XmagePb03Tier2CmdZoneTest`
   - `XmagePb03Tier2ControlTurnTest`
   - `XmagePb03Tier2StackTest`

3. **Generated recomputation**
   - `qualification/pb03-wave1-20260928/*`
   - donor-reported recomputed counts: PASS 22 / BLOCKED 26 / UNKNOWN 59

The generated counts are **not imported as current qualification credit**. They were produced on the Muse lineage and must not be transferred across current-source changes by assertion.

### Immediate salvage

Only the Java dimension-admission characterization test is ported in this intake, with wording updated so it is a seam characterization rather than a claim that the old Python tier table is canonical.

This is test-only. It grants zero row PASS credit.

### Deferred discriminators before additional porting

Before porting Tier-1/Tier-2 execution suites, #284 must determine for each test:

- whether the frozen fixture obligation is unchanged;
- whether the current restoration/decision APIs still exercise the same authoritative path;
- whether PR #283 principal-scoping semantics are preserved;
- whether the test observes the actual obligated fact rather than construction or an adjacent mechanism;
- whether current execution fails before the donor test/repair is applied.

Only then may individual tests or minimal helpers be ported.

## PB-09 pristine Forge donor evidence

Muse preserved a pristine-upstream Forge run with:

- Rules Core: `a37a865a53280dd8ad6fad3384d69611e8c5a42f`
- bridge source/worktree head: `4753bb7c72ea60d653121e0bab989077b4009f9c`
- worktree tree: `4cd539f1c56876590b8679dc1534d4632560c66d`
- result counts: PASS 1 / FAIL 4 / UNKNOWN 102 / BLOCKED 0
- worktree clean: true

The receipt itself states:

`engine_commit_binding = env:FORGE_ENGINE_SHA (operator-supplied; PB-05 open)`

Therefore classification is:

- runtime attempt: donor evidence exists;
- pristine-source intent: CODE_DERIVED / provenance-supported;
- candidate identity binding: **not decision-grade**;
- provider capability credit: **UNKNOWN** until runtime/build-derived identity is established.

These artifacts remain on the donor branch. They are not copied into canonical qualification output and do not replace the separate DeepSeek Forge PR #5 requalification, which measures a different explicitly bound bridge/evidence head.

## Salvaged changes

- Ported: one PB-03 Java dimension-admission characterization test only.
- Not ported: donor production Python qualification routing.
- Not ported: generated PB-03 result JSON.
- Not ported: pristine Forge generated artifacts.
- Not ported: historical workstream state/contracts.

## Evidence impact

This intake changes no provider verdict, denominator, AF verdict, FULL107 count, provider selection, or Architecture Freeze state.

Any future Muse-derived PASS requires a fresh current-source discriminator and exact runtime/source binding.

## Remaining Muse-only value

Highest-value unconsumed donor material, in order:

1. PB-03 Tier-1 obligation-execution tests.
2. PB-03 Tier-2 commander-zone/control-turn/stack characterizations.
3. Pristine-upstream Forge PB-09 run as a negative/control evidence source, pending authoritative identity requalification.
4. Muse convergence impact matrix as review context only.

## Exact next action

Run the ported dimension-admission test on the current #284 head through normal CI. If green, use it as a current-source discriminator for PB-03 seam behavior. Then adjudicate Tier-1/Tier-2 tests individually; do not import generated PASS counts.

`PRODUCTION_PROVIDER = NOT SELECTED`

`ARCHITECTURE_FREEZE = NOT CLAIMED`
