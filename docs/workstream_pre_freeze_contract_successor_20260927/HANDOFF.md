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
   unchanged non-START2 fixture records, protocol binding and historical preservation.
8. Added a strict successor materialization schema and recomputed current START-2
   obligation/materialization plus bundle digests rather than advertising stale digests.
9. Hardened Architecture-Freeze v2 so source/provider/adapter/build identities and
   provider-reported capabilities are structurally required; an eligible result may not
   carry missing required capabilities.
10. Rebound Rules authority to a reproducible official Wizards source receipt instead of
    treating the historical untracked `artifacts/cr/...` path as current evidence.
11. Reclassified all historical FULL107 runtime evidence as provenance-only for the
    current Protocol-2 comparison; fresh current-boundary execution is required for all 107.
12. Resolved the temporary Rules-authority freshness blocker by rechecking the current
    official Wizards Rules page on 2026-09-27. The page still directly links the
    `MagicCompRules 20260807.txt` document, whose own effective date is 2026-08-07
    and whose CR 103.8a preserves the START-2 semantic requirement. The prior
    2026-09-25 signal is retained only as rejected discovery provenance.
Historical predecessor digests remain under `historical_digests`; the effective
START-2 record receives newly computed requested-state, obligation and materialization
digests. The effective bundle receives a newly computed canonical bundle digest while
preserving the historical digest under `supersedes`.

## START-2 Authority Correction

Repository authority receipt `CURRENT_RULES_AUTHORITY.json` binds the current official
Wizards Rules page and the TXT that page directly links on 2026-09-27. That TXT is
`MagicCompRules 20260807.txt`, states an effective date of 2026-08-07, and CR 103.8a
requires the player who plays first in a two-player game to skip the draw step of the
first turn. No byte-exact SHA-256 is claimed for this fresh web verification; the
receipt records that limitation explicitly and fails closed if the official Rules page
target changes.

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
- other 106 FULL107 denominator rows: **HISTORICAL_PROVENANCE_ONLY_PENDING_CURRENT_BOUNDARY_EXECUTION**
- Forge WSR20's reported START-2 DIRECT is not imported as successor runtime credit.
- Historical XMage START-2 blocker remains provenance only.
- For the current Protocol-2 comparison boundary, **all 107 FULL107 rows require fresh
  execution**. Source identity alone never promotes historical RSP-1.1 runtime evidence.

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

The qualification integrity gate initially caught missing SHA-256 coverage for the new
qualification artifacts. The gate was preserved; both `qualification/SHA256SUMS` and
`WS17_SHA256SUMS` were extended/resealed whenever a sealed qualification artifact
changed.

Final fully validated post-review, post-PR-257 integration head:

`236ff2d48ac79c0fe84380e7f44b0d7bc2894bb0`

- CI run `36319384132`: **SUCCESS**
  - Ruff lint: SUCCESS
  - Ruff format: SUCCESS — 953 files already formatted
  - mypy strict: SUCCESS — 0 issues / 261 source files
  - full Python suite: **1626 passed / 7 skipped / 1 warning**
  - compile / secret-pattern scan / wheel build: SUCCESS
  - security job: SUCCESS
- Production Qualification run `36319384122`: **SUCCESS**
  - qualification suite: **37 passed / 2 skipped**
  - canonical fixture manifest validation: SUCCESS
  - exact-main-admission skipped as expected for the PR event
- Windows Runtime Hygiene run `36319384133`: **SUCCESS**

The handoff update following that validated head is documentation-only; no contract,
hash manifest, resolver, schema or test semantics change in that handoff commit.

Rules-authority freshness is now resolved:

- on 2026-09-27 the current official Wizards Rules page directly links
  `MagicCompRules 20260807.txt`;
- that official document states an effective date of 2026-08-07;
- CR 103.8a retains the START-2 draw-step-skip semantics;
- the prior claimed 2026-09-25 rules release is rejected as lower-authority discovery
  evidence because it is not what the current official Wizards Rules page publishes;
- `CURRENT_RULES_AUTHORITY.authority_status =
  CURRENT_OFFICIAL_SOURCE_DIRECTLY_VERIFIED`;
- no byte-identity claim is made without a captured SHA-256.

Evidence classification:

- Contract implementation/repository integration: **TECHNICALLY_CONFORMANT** within
  this bounded contract-normalization scope.
- START-2 semantic basis: **EXTERNALLY_RULE_VALIDATED** for current official CR 103.8a
  semantics; Rules-authority freshness is **DIRECTLY_VERIFIED** at the current official
  Rules-page/link level, with byte identity explicitly not claimed.
- Qualification hash sealing and CI receipts: **DIRECTLY_VERIFIED**.
- START-2 candidate runtime behavior: **UNKNOWN** until current-boundary execution.
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

1. Execute all 107 FULL107 rows freshly under the current qualification boundary for
   XMage and Forge; START-2 uses the corrected successor semantics.
2. Execute AF01 v2 handshake/capability/fail-closed qualification independently on each
   candidate using exact provider/adapter/build source locks.
3. Continue provider comparison only from those normalized current-boundary results.

## Dependencies Unblocked

The next common-fixture workstream now has one explicit current contract authority rather
than choosing between historical FULL107/RSP artifacts ad hoc.

## Exact Next Action

After PR #254 is integrated, run the bounded common-fixture execution/requalification
against the effective successor contract:

1. Fresh current-boundary execution of all 107 FULL107 rows on XMage and Forge,
   including corrected `WS05-CMD-START-2`.
2. AF01 v2 handshake / truthful-capability / fail-closed qualification with exact
   provider/adapter/build identities for both candidates.
3. Only then consume the normalized results in the pre-Freeze provider-comparison
   framework.

Do not select a provider from this contract-only workstream.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

## Terminal PR State

- PR: #254 — `Pre-Freeze contract successor: correct START-2 and migrate AF01`
- Branch: `sol/pre-freeze-contract-successor-start2-af01-20260927`
- Fully validated contract/integration head:
  `236ff2d48ac79c0fe84380e7f44b0d7bc2894bb0`
- Current integrated base main:
  `586914ea10caf1ede3e509908a6b177c4a20d5e7`
- Current integrated base tree:
  `6d2aab11a5bf432207a96977c9009fb11906c0d0`
- Current-main integration merge parent:
  `add963b9f57f3910d1a80912cac1a7dc89163843`
- Mergeability at validated state: TRUE
- Scope status: **COMPLETE / BOUNDED PASS**
- Runtime/provider qualification remains outside this contract-only PASS.

## Review Remediation Before Merge

Automated review surfaced additional contract-integrity requirements after the first
green head. They were treated as blockers, not waived:

- exact-once AF00–AF11 + all-PASS eligibility: fixed;
- required per-gate evidence references: fixed;
- predecessor canonical bundle digest advertised as current: fixed;
- historical untracked CR artifact path used as current authority: replaced by
  reproducible official Wizards authority receipt;
- empty source lock / empty capability payload could validate: fixed structurally;
- RSP-1.1 evidence could carry forward on source identity alone: prohibited;
- successor materialization lacked its own schema: fixed with a strict v1.0.6-successor
  schema and current digest reconstruction.

The final status below must be read against the post-review terminal head and its green
CI receipts, not the earlier intermediate head.


## PR #257 Source Drift Adjudication

While PR #254 was under final validation, canonical `main` advanced from
`58e8fca430651207a87a8f3e9f41d8c6527dd4cd` to
`586914ea10caf1ede3e509908a6b177c4a20d5e7` (tree
`6d2aab11a5bf432207a96977c9009fb11906c0d0`) through PR #257.

Changed paths were limited to `AGENTS.md` and Foundry execution/routing,
launcher, telemetry and tests. None overlap this workstream's owned
qualification/contract/resolver/test paths. Because `AGENTS.md` changed, the
advance was explicitly reviewed as governance drift rather than ignored.

Disposition:
`NON_IMPACTING_IMPLEMENTATION_SURFACE_GOVERNANCE_REVIEWED`.

The current main was integrated as a real second parent in merge commit
`add963b9f57f3910d1a80912cac1a7dc89163843`; no force update or stale-base
merge was used. Final qualification receipts must therefore bind to the
post-integration PR head, not to any earlier intermediate head.

## Post-Merge Rules-Authority Freshness Closeout

PR #254 merged the bounded contract successor to canonical main at
`c5f9418e755a02ffec0e02c34b4a739baf10f5f0`.

A post-merge source-truth check on 2026-09-27 re-opened only the temporary
Rules-authority freshness receipt. Direct verification of the current official Wizards
Rules page established that its current TXT target remains
`MagicCompRules%2020260807.txt`, so the lower-authority 2026-09-25 signal does not
supersede the official source.

This follow-up changes no fixture semantics, AF gate semantics, engine code, provider
code, FULL107 denominator, or evidence-promotion policy. It only closes the erroneous
freshness blocker and reseals the changed qualification artifacts.
