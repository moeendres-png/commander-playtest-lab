# PRE-FREEZE CONTRACT SUCCESSOR — START-2 + AF01

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Base: `58e8fca430651207a87a8f3e9f41d8c6527dd4cd`
- Base tree: `4cf4f3d23da9b6a7bb010178b6efcc2b2c853ba2`
- Prior adjudication base `d04bf9e4` advanced only through merged PR #253
  publisher-security paths. Impact: **NON_IMPACTING** for this workstream.
- Historical WS47 v1.0.5 bytes are preserved.
- Historical WS10R / RSP 1.1 bytes are preserved.
- No Mage, XMage bridge, Forge, publisher, provider-selection or production files are changed.

## Work Completed

1. Added a machine-readable current pre-Freeze authority pointer.
2. Added a one-row FULL107 successor overlay for `WS05-CMD-START-2`.
3. Corrected START-2 from an impossible draw-step-priority checkpoint to a CR-103.8a
   full draw-step skip with the next observable checkpoint at P1 precombat main.
4. Added a resolver that verifies the frozen v1.0.5 SHA-256, applies exactly the
   authorized successor row, and recomputes the requested-state digest.
5. Added candidate-neutral AF01 Qualification Boundary v2 bound to the current
   Engine Adapter Protocol 2.0.0 schema and explicit truthful-capability /
   fail-closed / Rules-authority invariants.
6. Added Architecture Freeze gate catalog/result schema v2 without granting any
   candidate AF01 or Freeze credit. The v2 result schema preserves WS10R's mandatory
   evidence references and `architecture_winner=false`, requires every AF00–AF11
   exactly once, and permits `freeze_eligible=true` only when all twelve verdicts
   are `PASS`.
7. Added regression tests for exact change accounting, START-2 semantics/digest,
   unchanged non-START2 records, protocol binding and historical preservation.
8. Removed stale predecessor materialization/obligation/supersession digests from the
   effective START-2 record and retained them only under `historical_digests`.
9. Removed the predecessor bundle's canonical digest/common-manifest digest from current
   identity fields, preserved them as historical provenance, and rebound the effective
   bundle to `AUTHORITY_LOCK_v2`.

## START-2 Authority Correction

Repository authority lock `AUTHORITY_LOCK_v2` pins the current Comprehensive Rules
effective 2026-08-07. CR 103.8a requires the player who plays first in a two-player
game to skip the draw step of the first turn.

The historical START-2 record required both:

- `first_turn_draw:false`; and
- priority at `turn 1 / beginning / draw`.

Those requirements are mutually incompatible for a conforming provider because the
entire step is skipped.

The successor therefore requires:

- P1 is the starting player;
- the first-turn draw step is skipped;
- no draw-step-start or draw-step-draw event occurs for P1 on turn 1;
- there is no priority checkpoint inside the skipped draw step;
- the first post-skip observation is P1's precombat main priority;
- P1 hand/library counts remain unchanged by a draw step;
- the inherited actor-aware observation wording is rebound to the candidate-neutral
  current qualification boundary rather than the historical RSP name.

Predecessor requested-state digest:
`2a40e275af77f173c62bb63fbd059cd17197ddffc2d9b338258b836ca1f83312`

Successor requested-state digest:
`bc01a714cbaa035d2f7954d4fd2dcabb63c391160f78774749ab50ab63fa4342`

Evidence survival:

- `WS05-CMD-START-2`: **REQUALIFICATION_REQUIRED**
- other 106 FULL107 denominator rows: **UNCHANGED_REUSABLE_SUBJECT_TO_SOURCE_IDENTITY**
- Forge WSR20's reported START-2 DIRECT is not imported as successor runtime credit.
- Historical XMage START-2 blocker remains provenance only.

## AF01 Migration

Historical AF01 remains preserved under WS10R/RSP 1.1, but is no longer the
current pre-Freeze qualification boundary.

Current boundary:

`commander-lab.pre-freeze-qualification/2.0.0`

It binds to the current common Engine Adapter Protocol 2.0.0 and requires:

- exact protocol/schema identity;
- exact provider/version identity;
- canonical `start_engine`, `get_provider_version`, `get_capabilities` handshake;
- explicitly provider-reported truthful capabilities;
- no capability inference from provider name;
- Rules Core sole authority for legality and Rules RNG;
- no adapter/pilot legality reconstruction or fabricated options;
- protocol mismatch, unknown messages, illegal/stale actions and unsupported
  production-reachable decisions fail closed without game mutation.

This is candidate-neutral. It does not award AF01 PASS by construction. Runtime evidence
against this boundary is still required.

## Changes

Added:

- `qualification/CURRENT_PRE_FREEZE_CONTRACT.json`
- `qualification/pre-freeze-successor/SOURCE_LOCK.json`
- `qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_6.json`
- `qualification/pre-freeze-successor/AF01_QUALIFICATION_BOUNDARY_V2.json`
- `qualification/pre-freeze-successor/architecture_freeze_gate_catalog_v2.json`
- `qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json`
- `scripts/resolve_pre_freeze_contract.py`
- `tests/qualification/test_pre_freeze_contract_successor.py`
- this handoff

Modified only for qualification-integrity sealing:

- `qualification/SHA256SUMS`
- `WS17_SHA256SUMS`

No historical WS47/WS10R contract, Rules-engine runtime, provider, or publisher file is modified.

## Tests / Evidence

Initial PR validation exposed one legitimate infrastructure failure:
`test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` rejected the six
new `qualification/` artifacts because they were not yet covered by the current hash
manifests. The gate was not weakened. Both hash manifests were extended with exact
SHA-256 entries and the root manifest was rebound to the updated
`qualification/SHA256SUMS`.

Final branch validation on implementation head
`29f1e0f3073262f2fd47cca94d08cf0a3d8e8abd`:

- CI run `36313283271`: **SUCCESS**
  - Ruff lint: SUCCESS
  - Ruff format: SUCCESS
  - mypy strict: SUCCESS
  - full Python test suite: **1614 passed / 7 skipped / 1 warning**
  - compile / secret-pattern scan / wheel build: SUCCESS
- Production Qualification run `36313283325`: **SUCCESS**
  - qualification suite: **33 passed / 2 skipped**
  - canonical fixture manifest validation: SUCCESS
  - exact-main-admission intentionally skipped on PR event
- Windows Runtime Hygiene run `36313283360`: **SUCCESS**
  - filesystem/atomic-storage, external-runtime boundary, doctor/probe cleanliness,
    structural/tactical validation and final clean-repository assertion all SUCCESS.

The earlier integrity failure was fully remediated without weakening a test or gate:
new qualification artifacts are sealed in both SHA-256 manifests.

Evidence classification:

- Contract implementation and repository integration: **TECHNICALLY_CONFORMANT**
  within this bounded contract-normalization scope.
- Official Rules basis for START-2: **EXTERNALLY_RULE_VALIDATED** against the
  repository-pinned current CR 103.8a authority.
- START-2 candidate runtime behavior: **UNKNOWN** until successor requalification.
- AF01 candidate runtime compliance: **UNKNOWN** until candidate-specific execution.

## PASS / FAIL / UNKNOWN

- START2_CONTRACT_AUTHORITY_CORRECTION: **PASS / TECHNICALLY_CONFORMANT**
- AF01_CONTRACT_MIGRATION: **PASS / TECHNICALLY_CONFORMANT**
- QUALIFICATION_INTEGRITY_SEAL: **PASS / DIRECTLY_VERIFIED**
- START2_SUCCESSOR_RUNTIME: **UNKNOWN** / requires candidate requalification
- AF01_CANDIDATE_RUNTIME: **UNKNOWN** / requires candidate-specific qualification
- Provider Selection: **NOT RUN**
- Architecture Freeze: **NOT CLAIMED**

## Remaining Blockers

1. Execute START-2 successor semantics independently on each candidate.
2. Execute AF01 v2 handshake/capability/fail-closed qualification for each candidate.
3. Continue common-fixture comparison only after those normalized contracts are consumed.

## Dependencies Unblocked

The next common-fixture workstream now has one explicit current contract authority rather
than choosing between historical FULL107/RSP artifacts ad hoc.

## Exact Next Action

After PR #254 is integrated, run the bounded common-fixture execution/requalification
against the effective successor contract:

1. `WS05-CMD-START-2` successor semantics independently on XMage and Forge.
2. AF01 v2 handshake / truthful-capability / fail-closed qualification independently
   on XMage and Forge.
3. Only then consume the normalized results in the pre-Freeze provider-comparison
   framework.

Do not select a provider from this contract-only workstream.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

## Terminal PR State

- PR: #254 — `Pre-Freeze contract successor: correct START-2 and migrate AF01`
- Branch: `sol/pre-freeze-contract-successor-start2-af01-20260927`
- Validated implementation head: `29f1e0f3073262f2fd47cca94d08cf0a3d8e8abd`
- Base main: `58e8fca430651207a87a8f3e9f41d8c6527dd4cd`
- Base tree: `4cf4f3d23da9b6a7bb010178b6efcc2b2c853ba2`
- Mergeability at validation: TRUE
- Scope status: **COMPLETE / BOUNDED PASS**
