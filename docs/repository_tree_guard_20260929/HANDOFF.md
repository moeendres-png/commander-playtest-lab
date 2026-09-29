# Repository entrypoint retention guard

Objective: detect a candidate commit that loses required project operating
entrypoints, including the freshly observed destructive tree in PR #285.
Direct user authority: repair small repository-integrity defects, persist
checkpoints, publish a tested PR ready for normal integration.

Source lock: main `07aae5d63a544fb4e4a29fdbeee2aa5005f83e7c`, tree
`27fe76678e05eb476727a35cebb4363677bc65a9`.
Owned branch: `astra/repository-tree-guard-20260929`. Only new verifier,
new unit tests, new workflow and this evidence directory are owned. No foreign
implementation or unpublished work is consumed. Existing policy/source files
are inspected but unmodified; no branch protection configuration is changed.

## Incident receipt

GitHub reported PR #285 head `b4ea775137c9d0538ca85f8c8b56383650111745`
as non-draft, with 2,096 changed files, zero additions and 1,107,165 deletions.
Its entire Git tree contains only six files (four run-manifest docs, one storage
module, one test module). This contradicts the PR's convergence description.
Converted to Draft; preserved all source/history/provenance. Gate receipt:
https://github.com/moeendres-png/commander-playtest-lab/pull/285#issuecomment-5886779824
No instruction to repair, rewrite or close the foreign branch was issued.

## Implementation and trust boundary

Reuse Git object inspection and six existing operating entrypoints. The checker
requires a full commit SHA and validates regular-file modes; it never imports,
checks out or runs candidate code. Candidate paths are not shell input. Git
failures return a structured negative result without raw diagnostics.

The pull_request_target workflow checks out the exact trusted base, installs only
its locked dependencies, then fetches candidate objects with contents:read. No
candidate code, cache, write permission or explicit secret is used. The trusted
base script checks the candidate. See the documented GitHub event semantics:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target

This detects missing/replaced entrypoints, NOT arbitrary semantic corruption,
all possible deletions, authenticity, or full repository/qualification correctness.
The existing six-file policy is intentionally small; deliberate migrations must
update the policy on the trusted base. The workflow does not configure branch
protection and is not claimed as an unbypassable merge lock. Draft is a reversible
merge safety measure, not a permissions boundary.

Activation: pull_request_target uses the target branch's workflow, so the live
event path becomes available only AFTER integration. No pre-merge live event
PASS is claimed. After merge, exercise with a normal open/synchronize/reopen PR
event and read the check; do not rerun or execute the damaged candidate.

## Checkpoint 1

DIRECTLY_VERIFIED: new checker rejects exact PR #285 head (all six entrypoints
missing) and accepts exact source-locked main. 28 tests passed: 14 focused guard
tests and 14 existing workflow contracts. Real temporary Git repositories cover
missing files, directory/symlink substitution, invalid refs and tree-not-commit
objects. Candidate fixture content deliberately raises if executed; inspection
does not run it. No engine/RNG/qualification work is modified or requalified.

Required next: affected lint/format/type/compile checks, published exact-head CI
and review, final handoff. Sol integrates normally only after gates; re-read main
HEAD/TREE and verify post-merge workflow activation. Preserve PR #285 as gated
provenance pending owner/Coordinator recovery.

ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
