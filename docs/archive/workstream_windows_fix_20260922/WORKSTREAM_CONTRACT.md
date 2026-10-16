# Workstream Contract — Windows Runtime jobs-stanza repair (Issue #208)

## Objective

Restore the top-level `jobs:` stanza in
`.github/workflows/windows-runtime.yml` on current main (PR207 merge
broke it: R21 env-insert consumed the `jobs:` key, nesting the
`windows-runtime` job under `env:` → zero Jobs on the Windows runner).
Retain `env.PYTHONHASHSEED`, the documented Windows dependency-regime
exception, pinned actions and all steps/assertions. Add a focused
regression against jobs→env structural drift. Open a scoped PR, get CI
green, prepare merge-ready packet (merge by Coordinator).

## Source Lock

- Base: `origin/main` `62f74ee6755cf473d04cddf18a21a0fe9150ed32`.
- This branch: `fix/windows-runtime-jobs-stanza-20260922`.
- This worktree: `/home/moeen/code/ws-windows-runtime-fix-20260922`.
- Repo `moeendres-png/commander-playtest-lab`. No main edits, no bypass.

## In Scope

- One-workflow structural repair + regression test + validation.
- Scoped commit + Foundry push + scoped PR + CI remediation on that PR.
- Merge-ready packet. No broad requalification.

## Out of Scope

- PR207 evidence (sealed, untouched); FULL107; provider/freeze decisions.

## Ownership

Single writer: this session on this branch/worktree only.

## Hard Gates

- No test weakened or deleted; Windows exception + hashseed preserved.
- Schema validated beyond permissive YAML (jobs mapping, job shape).
- A real Windows runner must execute on repaired bytes (not just parse).

## Stop Conditions

PR green + merge-ready packet, or genuine terminal blocker.
