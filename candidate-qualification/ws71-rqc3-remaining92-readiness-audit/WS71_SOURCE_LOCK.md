# WS71 Source Lock

Workstream: `WS71-RQC3-REMAINING92-READINESS-AUDIT`
Branch: `ws71/rqc3-remaining92-readiness-audit-20260912`
Worktree: `/home/moeen/code/ws71-rqc3-remaining92-readiness-audit`
Writer: sole writer for this workstream (`muse-spark-1.3-contributor`)
Role: corpus/readiness/dependency-planning ONLY. No behavior execution.
  No candidate/provider/harness/engine semantics changed.

## Pinned source identities (verified 2026-09-12, pre-edit)

| Identity | SHA | Tree | Status |
| --- | --- | --- | --- |
| CPL source (worktree HEAD) | `7796619e69b0434cd232de8335ff5cab3c5d08e5` | `48ec3eafcca668f3fa165e3977af5836b3add059` | `git rev-parse HEAD` + `HEAD^{tree}` match contract; verified |
| RQ-C3 authority | `897d72f0b57bb8febe045870acaa3d2dba4bde56` | `1b8c8a46f1b81277f73a0ec808055dde25fadbe5` | `git rev-parse <sha>^{commit}` + `^{tree}` match contract; verified |
| XMage First Wave | `731891ec5ed8e7611fc9a636bab5fc3c400108eb` | n/a (terminal evidence ref) | object present (`git cat-file -t` = commit); verified |
| Forge First Wave (= CPL source) | `7796619e69b0434cd232de8335ff5cab3c5d08e5` | n/a | same object as CPL source; verified |

Working tree at audit start: clean except the untracked owned directory
`candidate-qualification/ws71-rqc3-remaining92-readiness-audit/` itself
(containing only `WORKSTREAM_STATE.yaml`).

## Authority read method

All Phase-A derivation reads use `git show <rqc3-authority-sha>:<path>`
against the pinned RQ-C3 commit (fail-closed hash/tree check inside
`ws71_denominator_audit.py`). No working-tree authority copies exist in this
worktree (`research/candidate-qualification/common/rq-c3/` and `rq-c1/` are
absent from the CPL source tree); no network; no behavior execution.

Authority files read (sha256 of exact bytes in `WS71_REMAINING92_DENOMINATOR.json`
provenance):

- `research/candidate-qualification/common/rq-c3/RQ_C3_CORRECTED_SCENARIO_MANIFEST.json`
- `research/candidate-qualification/common/rq-c3/RQ_C3_FIRST_WAVE_EXECUTION_PACK.json`
- `research/candidate-qualification/common/rq-c1/RQ_C1_SCENARIO_MANIFEST.json`
- `research/candidate-qualification/common/rq-c1/RQ_C1_FULL107_RELATION.md`
- `research/candidate-qualification/common/rq-c2/RQ_C2_EXPECTED_ASSERTION_REVIEW.json`

## Active-workstream non-assumption record

WS66 fixture-authority closure, WS67 Forge engine remediation, WS68 Forge
provider remediation, and WS-A1D-H4F Argentum workstream results were NOT
assumed anywhere in this audit. Phase A depends only on the pinned authority
above. (Phases D-G were not executed; see Final Report STOP rationale.)

## Invariants

`BEHAVIOR_CREDIT=0/107`. `FULL107=NOT_RUN`. `ARCHITECTURE_FREEZE=NOT_CLAIMED`.
`PRODUCTION_PROVIDER=NOT_SELECTED`. No candidate executed. No fallback legality
created. Ownership respected: writes only under
`candidate-qualification/ws71-rqc3-remaining92-readiness-audit/`.

Evidence class for source-lock facts: `DIRECTLY_VERIFIED`.
