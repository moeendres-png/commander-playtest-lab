# WS-17 FINAL HANDOFF

## Source Lock

Target repository `moeendres-png/commander-playtest-lab` was freshly locked at main commit `3ad43c38c44299fd8d72b94f30af61d409c47b9e`, tree `001462343b93d0190c65c0b91055200604d5376e` before WS-17 materialization.

Final WS-17 branch: `ws17/common-qualification-infrastructure`.
Draft PR: `#130`.
The PR remains draft and unmerged; merge is outside WS-17 authorization.

## Work Completed

WS-17 materialized a provider-neutral, machine-readable qualification system for current XMage, Forge, phase.rs and Argentum evidence without remediating candidate Rules Cores.

It includes:

- controlled WS-10R protocol/architecture bundle;
- WS-01 G00-G15 and AF00-AF11 machine obligations;
- canonical actual-card/rules denominators;
- authority lock with explicit UNKNOWN boundaries;
- 135 common provider-neutral fixtures;
- normalized evidence/result schemas;
- executable common harness;
- fail-closed admission aggregation;
- exact-main Production Qualification workflow;
- per-candidate current-lock evidence reports;
- cross-candidate evidence matrix;
- negative invariant tests;
- complete SHA-256 manifests.

No candidate Rules Core was modified.

## Artifact Recovery / Rematerialization

The exact original WS-10 machine bundle could not be recovered from supplied artifacts, connected Google Drive, or the target repository. Its historical byte identity remains `UNKNOWN`; WS-17 does not claim reconstruction.

A controlled replacement was therefore materialized as **WS-10R / `commander-lab.rules-service/1.1.0` / AF 1.1.0**. Version `1.0.0` was not silently reused because compatibility with the unavailable normative byte artifact could not be demonstrated.

WS-10R bundle SHA-256:

`2f002a4d020e99e44270239fd3a894e9be6f08eddf9fdd233b81ba8d3f070577`

All contained schemas and internal SHA-256 entries are executable-test verified.

## Authority Lock

Official Wizards authority identified:

- Comprehensive Rules artifact family: `MagicCompRules 20260807`;
- effective date: **August 7, 2026**.

The available browser surface confirmed the official source, but two available raw-download paths failed to preserve the authoritative source bytes. Exact original CR SHA-256 therefore remains `UNKNOWN` rather than fabricated.

Authoritative Wizards/Gatherer Oracle bulk acquisition also remained unavailable. Therefore:

`AUTHORITATIVE_ORACLE = UNKNOWN`

No Scryfall, engine script, cache, or secondary source was promoted to official authority.

## Repository Changes

Branch: `ws17/common-qualification-infrastructure`.
Draft PR: `#130`.

The branch contains only WS-17 provider-neutral qualification infrastructure, schemas/manifests/tests/workflow and reports. Forge remains constrained to a genuine separate GPL-compatible process/service boundary. No upstream candidate repository was permanently modified.

The final mechanical Ruff/import correction was committed and its dependent hash manifests refreshed. The final CI-verified WS-17 head is:

`17a200377aceb5739384c8c68688e43e35d3dfe6`

## Qualification Infrastructure

The common fixture manifest contains **135 fixtures** and covers:

- 2P, 3P, 4P and 5P execution requirements;
- WS-05 multiplayer/Commander MUST semantics;
- pilot-boundary decision families and prohibited fallback paths;
- actor-aware hidden-information/honeycard checks;
- RulesRngTape / DecisionTape / EventTape / clean-process replay obligations;
- micro-rules surface;
- all 29 frozen real cards behaviorally.

The harness transports provider-offered semantics and does not implement Magic legality.

Canonical card-domain denominators preserved include:

- known actual-card universe: **1385**;
- physical identities: **1338**;
- RogShai operational candidate universe: **795**;
- current RogShai identities: **87**;
- current Kaervek identities: **77**;
- unknown real opponent slots: **142**.

No missing opponent identity was invented.

## Tests Executed

Local WS-17 infrastructure tests: **12/12 PASS**. They validate JSON Schemas, common manifest/card denominator shape, missing-provider `NOT_RUN`, exact-main SHA mismatch failure, mandatory-obligation fail-closed semantics, complete SHA-256 manifest coverage, WS-10R ZIP integrity, workflow invariants, and exact JSON→Markdown regeneration.

Final GitHub evidence on exact WS-17 head `17a200377aceb5739384c8c68688e43e35d3dfe6`:

- General CI run #1275: **SUCCESS**;
  - Ruff lint: PASS;
  - Ruff format: PASS;
  - Mypy strict: PASS;
  - full test suite: PASS;
  - compile: PASS;
  - secret-pattern scan: PASS;
  - wheel build: PASS;
  - security/dependency audit/SBOM/license report: PASS.
- Production Qualification run #11: **SUCCESS** on PR infrastructure validation.
- Candidate Lossless Handoff Conformance run #38: **SUCCESS**.
- Release Artifacts run #895: **SUCCESS**.

The PR-only `exact-main-admission` job is intentionally ineligible to provide production admission evidence. Exact-main admission runs only on an exact `main` push; a PR skip never becomes PASS.

## Tests Not Run

No common RSP 1.1 candidate runtime was executed because no current exact candidate exposes a compliant common adapter without additional candidate-specific implementation/remediation.

No performance benchmark, gameplay campaign, sealed holdout, deck-optimization campaign or candidate Rules remediation was run.

## Cross-Candidate Evidence Matrix

Machine-readable matrix: `qualification/aggregate/CROSS_CANDIDATE_EVIDENCE_MATRIX.json`.

- **XMage:** direct player-count and observation failures; protocol adapter missing; common runtime `NOT_RUN`; remediation required.
- **Forge:** direct stock-remote pilot-boundary/default failure; compliant separate-process provider missing; common runtime `NOT_RUN`; provider implementation/remediation required.
- **phase.rs:** direct Changeling Commander rules failure; protocol adapter missing; common runtime `NOT_RUN`; remediation required.
- **Argentum:** direct pilot/rules/card-coverage failures; adapter cannot be lossless without substantive remediation; common runtime `NOT_RUN`; remediation required.

The matrix distinguishes `DIRECT_RULES_FAIL`, `DIRECT_PILOT_BOUNDARY_FAIL`, `DIRECT_CARD_COVERAGE_FAIL`, `PROTOCOL_ADAPTER_MISSING`, `QUALIFICATION_INFRASTRUCTURE_MISSING`, `AUTHORITY_BLOCKED`, `RUNTIME_NOT_RUN`, `RUNTIME_PASS`, and `REMEDIATION_REQUIRED` rather than collapsing all evidence into one generic FAIL.

## Direct Candidate Failures

Existing WS-13 through WS-16 direct failures are preserved and never erased by infrastructure classification.

### XMage

- current integration rejects 2P/3P/5P;
- actor-safe observation completeness is insufficient.

### Forge

- existing stock remote path contains prohibited defaults;
- no compliant RSP provider currently exists;
- GPL separation remains mandatory.

### phase.rs

- current direct Changeling Commander semantics blocker remains.

### Argentum

- Gym step auto-pass/internal authority;
- forbidden first/default/AI paths;
- `Player.AnOpponent.firstOrNull()`;
- incomplete external decision domains;
- observation gaps;
- Partner/multiple commanders missing;
- materially incomplete frozen 29-card implementation denominator.

## Infrastructure-Caused UNKNOWNs Closed

WS-17 closes the prior common-infrastructure asymmetry:

- common fixture denominator exists;
- common verdict vocabulary exists;
- common evidence schemas exist;
- common executable harness exists;
- machine-readable candidate reports exist;
- exact-main admission is fail-closed;
- provider absence is `NOT_RUN`;
- mandatory skips cannot satisfy obligations;
- PR-only execution cannot supply exact-main production credit;
- WS-10 byte-identity uncertainty was replaced explicitly with WS-10R rather than silently reconstructed;
- repository mechanical Ruff/format/hash closeout is now CI-verified PASS.

## Remaining UNKNOWNs

Remaining project-level UNKNOWNs are not WS-17 infrastructure defects:

1. authoritative Oracle/Gatherer lock;
2. byte-exact official Comprehensive Rules artifact/hash;
3. historical exact WS-00 reconciliation bytes not recovered;
4. common RSP runtime results for current XMage, Forge, phase.rs and Argentum builds;
5. candidate-specific remediation outcomes.

## PASS / FAIL / UNKNOWN

- `WS17_INFRASTRUCTURE_MATERIALIZATION = PASS`
- `WS17_FINAL_PR_CI_CLOSEOUT = PASS`
- `WS17_AUTHORITY_LOCK = PARTIAL / ORACLE UNKNOWN`
- `PRODUCTION_ADMISSION = FAIL`
- `ARCHITECTURE_FREEZE = FAIL / UNFROZEN`
- `ARCHITECTURE_WINNER = NONE`

WS-17 itself is **COMPLETE**. This does not imply Production Admission or Architecture Freeze PASS.

## Architecture Freeze Status

`ARCHITECTURE_FREEZE = FAIL / UNFROZEN`

No current candidate has demonstrated PASS across all mandatory AF correctness gates under common runtime evidence. No winner is selected.

## Remaining Blockers

No WS-17 infrastructure/CI closeout blocker remains.

Project-level blockers now move to candidate-specific remediation/provider implementation plus the remaining authoritative Oracle/CR-byte acquisition problem.

## Outputs

Primary durable repository outputs:

- `qualification/WS17_SOURCE_LOCK.json`
- `qualification/protocol/ws10r/`
- `qualification/obligations/FULL_RULES_REQUIREMENTS_CONTRACT_v1.json`
- `qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json`
- `qualification/manifests/AUTHORITY_LOCK_v1.json`
- `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json`
- `qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json`
- `qualification/evidence/normalized_evidence_v1.schema.json`
- `qualification/evidence/candidate_result_v1.schema.json`
- `qualification/harness.py`
- `tests/qualification/test_ws17_qualification.py`
- `.github/workflows/production-qualification.yml`
- `qualification/evidence/candidates/*.json`
- `qualification/aggregate/CROSS_CANDIDATE_EVIDENCE_MATRIX.json`
- `qualification/WS17_GAP_CLOSURE_REPORT.md`
- `qualification/WS17_FINAL_HANDOFF.md`
- `qualification/SHA256SUMS`
- `WS17_SHA256SUMS`

## Draft PR

https://github.com/moeendres-png/commander-playtest-lab/pull/130

Status: **DRAFT / OPEN / UNMERGED**.

Merge remains unauthorized by WS-17.

## Dependencies Unblocked

Candidate requalification can now use one provider-neutral executable denominator, common verdict semantics, common evidence schemas, exact-main admission rules and common artifact hashing rather than candidate-specific prose qualification.

The project can proceed to candidate remediation/requalification without reopening WS-17 infrastructure work.

## Exact Next Action

Open **multiple candidate remediation/requalification workstreams in parallel**; do not perform them inside WS-17:

1. **XMage remediation/requalification** — highest priority because it is closest to an existing full-game lane but still has direct player-count/observation blockers.
2. **phase.rs remediation/requalification** — parallel, preserving the direct Changeling Commander failure until fixed and runtime-verified.
3. **Forge provider implementation/requalification** — separate GPL-compatible process/service only, then common harness execution.
4. **Argentum remediation/requalification** — parallel/lower priority because current pilot-boundary, Commander and card-coverage gaps are broader.

Do not select a production provider until one or more exact candidate builds achieve runtime `PASS` for every mandatory AF correctness gate under the common WS-10R/WS-17 qualification framework.
