# Governance supersession receipt — PR #271 and the two `governance/*` branches

Date: 2026-09-27
Purpose: one canonical governance implementation, not several competing versions.

## Surfaces adjudicated

| Surface | Head | Status |
|---|---|---|
| PR #271 `Governance: Space Bunny MAX default, Muse XHIGH-only, full project authority` | branch `governance/space-bunny-full-project-authority-20260927` @ `089b69f8cdd8edee045c72d8427f13cf2270a454` | **superseded by merged WSR23** |
| branch `governance/space-bunny-max-muse-xhigh-successor-20260927` | `e75efbc73c4aa6148a39b4dbac29bad78a2103ca` | **superseded by merged WSR23** |
| PR #275 WSR23 | this branch | the canonical implementation |

Both governance branches are based on `8d2aacd5`, which predates PR #262, PR #266 and PR #272. That
is the structural reason they cannot be merged as-is: they would regress newer canonical content.

## What was compared

Every path each branch touches was diffed against the WSR23 branch, path by path, and the semantic
content was compared rather than the merge state. PR #271 was reported conflicted, which is correct
and is not the reason for closing it.

## Unique improvements found, and where they now live

WSR23 initially **lacked** four things these branches had. All were adopted into WSR23, so nothing
valid is lost by closing them:

| Unique content | Disposition in WSR23 |
|---|---|
| `tools/foundry/drift_check.py` `CANONICAL_MODEL` → `opencode-go/space-bunny-free` | **Adopted.** The constant was still declaring Muse while the committed config named Space Bunny. It is currently unreferenced, so not a live failure, but it is a live lie: any future reader or test consulting it would get the wrong answer. |
| `tools/foundry/state.py` `REASONING_TIERS` += `max` | **Adopted.** Without it a state recording a Space Bunny run's actual native tier would be rejected as invalid. |
| `.foundry/WORKSTREAM_STATE.schema.json` `current_reasoning_tier` enum += `max` | **Adopted**, with a description recording that routing uses `max` for Space Bunny and `xhigh` for Muse and that `high` survives only for historical state compatibility. |
| `.github/workflows/opencode.yml` `MODEL`/`VARIANT` | **Adopted.** CI had been running on `muse`/`high`, so it was not exercising the actual primary executor. Now `space-bunny-free` at `max`. |
| `AGENTS.md` sections 6, 7, 8 and the section 11 authority tail | **Adopted.** Section 10 `DELEGATED_GIT_INTEGRATION_AUTHORITY` from PR #272 is deliberately preserved, not replaced; the section 11 text routes through it rather than contradicting it. |
| `docs/foundry-execution/FULL_PROJECT_EXECUTION_AUTHORITY_2026-09-27.md` | **Adopted** (new file). |
| `EXECUTION_PROVIDER_OVERRIDE.md`, `ROUTING_AND_EFFORT.md`, `GOVERNANCE_SUPERSESSION.md`, `GITHUB_REMOTE_GATES.md`, `SAFE_AUTO_THREAT_MODEL_2026-09-10.md`, `.foundry/repo-profiles/cpl.json` | **Adopted whole.** Main had not modified any of these, so taking them whole cannot regress the PR #266 Bubblewrap and workspace-access content. |
| `.opencode/agents/foundry-implementer.md` declaring Space Bunny MAX as its own committed identity | **Adopted**, matching the adopted `AGENTS.md` §6, which names the primary implementer explicitly. The reviewer and adjudicator remain Muse XHIGH. |

Main's orthogonal additions to `COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`,
`docs/foundry-execution/README.md` and `WORKSTREAM_CONTRACT_TEMPLATE.md` (the PR #266
cross-workstream and Bubblewrap content) were **left untouched**, so nothing from #266 regresses.

## What WSR23 has that these branches do not

They could not substitute for it even on their own subject:

- The **`bash` default widened to `allow`** with the delegated authority as base, and the removal of
  the artificial blockers (`git -C`, `/usr/bin/git`, `/bin/git`, `command`, `sh -c`, `bash -c`, the
  eight mutating `gh api` forms) that were blocking operations PR #272 explicitly grants. Both
  governance branches keep the old `ask` default and those denies.
- The **launcher** fail-closed routing guards: exact two-executor allowlist, exactly one authorized
  native variant per model, branching on the *resolved* profile, and an unconditional `--model` pin
  on every child argv so telemetry can never name the wrong executor. That fixed a real
  silent-fallback hazard in which the `muse` profile reported override `canonical` while returning
  `CANONICAL_MODEL`.
- Integration with **PR #266**: `workspace_access.py`, `fs_sandbox.py`, the Bubblewrap fail-closed
  read-only-root namespace, exact repo/branch/HEAD/tree binding, `owned-write` multi-lock, and the
  600 lines of expanded launcher regression coverage.
- The **Phase A Foundry ownership repair** and the pre-Freeze campaign ledger, including the PB-09
  finding that the Forge evidence measures a Lab Rules-Core fork.

## Two protections restored rather than lost

The adopted implementer text dropped two clauses this branch had. Both were written back rather than
accepted as a regression:

- the reserved-authority statement — `PRODUCTION_PROVIDER` selection and `ARCHITECTURE_FREEZE` are
  Coordinator decisions the worker must reach but never claim;
- the never-destroy-unique-work constraint, including never deleting a branch or worktree until its
  unique content is proven preserved elsewhere.

## Disposition

PR #271 and both `governance/*` branches are **superseded by merged WSR23**. Their unique valid
content is preserved in the merged WSR23 implementation, itemised above. They are closed rather than
merged, because merging a second, older governance implementation would produce exactly the
competing versions this receipt exists to prevent.

**Branch deletion is deliberately NOT performed.** Deletion is optional under current repository
hygiene policy, and the unique content is already preserved in the merged tree, so no cleanup is
required to protect anything. Leaving the branches in place keeps the provenance auditable.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
