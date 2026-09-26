# GitHub Remote Gates — HUMAN_EXTERNAL Recommendations (WS75)

Status: DOCUMENTED_HUMAN_ACTION_REQUIRED. This workstream must not mutate
GitHub admin settings; every item below requires a human with admin
rights on the named repository. Observed state was read 2026-09-12 via
read-only `gh api` GET calls (no writes performed).

## Observed state (2026-09-12, DIRECTLY_VERIFIED read-only)

- `moeendres-png/commander-playtest-lab`, branch `main`:
  `GET branches/main/protection` → 404 "Branch not protected".
- `moeendres-png/mage`, branch `master`:
  `GET branches/master/protection` → 404 "Branch not protected".
- `moeendres-png/forge`, branch `master`:
  `GET branches/master/protection` → 404 "Branch not protected".
- `moeendres-png/commander-playtest-lab` rulesets:
  `GET rulesets` → `[]` (empty).

This confirms the Coordinator audit: default branches are unprotected and
repository rulesets are empty.

## Required remote gates (human to apply per repository)

### A. `commander-playtest-lab` / `main` (project work branch)

1. **PR path to the protected default branch.** Require pull requests
   before merging; disable direct pushes to the default branch for all
   actors, including admins where policy allows (or log admin bypasses).
2. **Force-push prohibited.** Block `git push --force` / `--force-with-lease`
   to the default branch. (Local tooling already refuses force semantics:
   `safe_push` pushes exactly `HEAD:refs/heads/<branch>` with no force
   flags, and `git push*`-family bypass shapes are DENY in `opencode.json`.)
3. **Branch deletion prohibited.** Block deletion of the default branch.
4. **Relevant required CI checks.** Mark the qualification lanes that must
   pass before merge as required status checks, at minimum the core CI lane
   (`.github/workflows/ci.yml`). Do NOT mark the comment-triggered OpenCode
   lane (`.github/workflows/opencode.yml`) as a required check: it triggers
   only on `issue_comment` / `pull_request_review_comment` containing `/oc`
   (runs with `contents: read`, never yields PR checks), so requiring it
   would block merges on a check that normal PR activity never produces.
   Require branches to be up to date before merging where the team can
   sustain it.
5. **No OpenCode/Muse direct push to the default branch.** Automation
   (including the `opencode` GitHub workflow in this repo, which runs
   with `contents: read`) must never receive push rights to a default
   branch. Workstream branches land via `safe_push` + PR review only.

### B. `mage` / `master` and `forge` / `master` (upstream mirrors — sync-only)

These default branches are upstream mirrors, not project-work branches
(mirror rule: direct commits prohibited; sync is fast-forward-only from
upstream, recorded with before/after SHAs; see `docs/FORK_AGENT_POINTER_SPEC.md`
§2 and `docs/RETENTION_AND_LIFECYCLE_POLICY.md` Appendix G). Do NOT impose
PR-only semantics on them: requiring pull requests before merging (or
disabling all direct/admin writes needed for fast-forward sync) would
intentionally create project divergence between the mirror and upstream.
Protection here must stay sync-compatible: block force-push, block branch
deletion, never grant automation push rights — while preserving the
fast-forward-only upstream-sync path (or admin-mediated sync where the team
adopts it). Never land project-only files (including any `AGENTS.md`
pointer) on a mirror `master`; project work lives on explicitly owned
`foundry/*`, `work/*`, or `playtest-lab-*` branches only. Engine checkouts
referenced by declared reference roots keep their lineage from the pinned
commit/tree plus review, not from mirror-branch CI; do not designate fork
CI as merge-blocking for lab purposes.

(WS-ARCLOSE-D1 2026-09-13: §A narrows the former uniform guidance to
`commander-playtest-lab/main` and removes the OpenCode lane from the
required-checks recommendation — the lane has no `pull_request` trigger and
cannot function as a required PR check. §B replaces the former uniform
PR-path recommendation on the engine mirrors with sync-compatible
protection. Observed-state section above preserved verbatim as the
2026-09-12 read-only record.)

## Why this matters to Foundry tooling

- `tools/foundry/safe_push.py` already refuses `main`/`master`/`HEAD` as
  push destinations and enforces fast-forward-only updates, but those are
  client-side gates: without server-side branch protection, any credential
  with push access can bypass them.
- The launcher-installed pre-push hook is explicitly L3-partial
  (bypassable via `--no-verify` by construction); branch protection plus
  required checks are the real gates.
- Engine reference roots (`--reference` declarations pinning exact
  commit/tree of the Forge/XMage checkouts) are only as trustworthy as
  the branches they were reviewed against; unprotected engine defaults
  weaken that lineage.

## Verification (human, read-only)

```bash
gh api repos/moeendres-png/commander-playtest-lab/branches/main/protection
gh api repos/moeendres-png/mage/branches/master/protection
gh api repos/moeendres-png/forge/branches/master/protection
gh api repos/moeendres-png/commander-playtest-lab/rulesets
```

Each protection call should return a protection object (not 404), and
the ruleset list should be non-empty once rulesets replace legacy
protection. Re-run after applying; record the date and the resulting
rule text in the workstream evidence.
