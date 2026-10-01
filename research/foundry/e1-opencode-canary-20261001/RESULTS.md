# E1: OpenCode filesystem-boundary runtime canary

| | |
|---|---|
| CLI | OpenCode **1.18.30**, the qualified pin (`opencode-linux-x64.tar.gz`, sha256 `55007246…99d17` verified) |
| Configuration | the bundle produced by `tools/foundry/launcher.resolve_environment`; only the provider/model part is replaced, by a local mock |
| Launch form | single-worktree, `run --auto --agent foundry-implementer` (the launcher's headless form) |
| Bubblewrap | not active: the launcher applies it only to cross-workstream launches |
| Evidence class | RUNTIME_VERIFIED (local) |

## Method

`canary.py` sets up the run:

- a synthetic git repository with a sibling worktree;
- an isolated `HOME` and XDG directories;
- no ambient credentials;
- a local OpenAI-compatible mock (`mock_provider.py`), which scripts the tool calls.

Every write target is a dedicated, empty canary directory. A target counts as reached when the file exists after the run. Earlier passes of the same canary isolated the causes; the controls are listed in the script's usage line.

## Findings

| # | Probe | Before | After E1 | Classification |
|---|---|---|---|---|
| 1 | Session directory when the launcher's `PWD` differs from the worktree | the parent's `PWD` (here: the global project, worktree `/`) | the worktree | **defect, fixed**. The CLI takes its directory from `PWD`, not from the process cwd. |
| 2 | Absolute `edit` deny on a directory outside the worktree | write **allowed** | the launcher now also emits the worktree-relative form, which binds | **defect, fixed**. The write/edit tools ask `edit` with `path.relative(worktree, file)`, so an absolute pattern never matches. |
| 3 | Sibling worktree under the system temp directory | write **allowed** | **denied** | **defect, fixed** by finding 2: sibling denies now also bind at `edit`. The CLI exempts the temp directory from `external_directory`: a plain directory there with an explicit deny was still written. |
| 4 | Sibling worktree outside the temp directory | denied | denied | `external_directory` denies bind there. |
| 5 | `.env` inside the worktree | denied | denied | canonical secret-file denies hold. |
| 6 | Write-tool write to any other path outside the worktree | allowed | allowed | **by design**: `external_directory` `"*": allow` and `/home/moeen/code/*` (`test_foundry_tools.py` documents the whole workspace tree as in campaign scope). Not changed here. |
| 7 | `echo … > outside`, `python3 -c open(…,'w')` | allowed | allowed | BYPASSABLE / INSTRUCTION_ONLY by construction (I14, A24). Only the Bubblewrap mount sandbox mediates it, and that applies to cross-workstream launches only. |

## What is decided where

- **Findings 1–3** are launcher defects (`tools/foundry/launcher.py`):
  - `env["PWD"]` is the worktree;
  - every `edit` rule is emitted in both the absolute and the worktree-relative form, through `_edit_patterns`;
  - sibling worktrees are denied at `edit` too;
  - the battery verdict I17 is now `DENIED` with the runtime basis.
- **Finding 6** is an owner policy. A default `external_directory` deny with launcher-generated allows would also block reads outside declared roots, and it would reverse the documented workspace-scope decision. The canary shows it is reachable, so this is an owner decision, not a silent change.
- **Finding 7:** extending the Bubblewrap read-only root to single-worktree launches is the only mechanism that mediates interpreter writes. It would change every launch: fail closed without `bwrap`. That is an owner decision as well. The cross-workstream setup is unchanged.

## Reproduce

```
python research/foundry/e1-opencode-canary-20261001/canary.py \
  <new-run-dir> <opencode-1.18.30> <empty-target-dir> [control] [sibling-name]
```

Final run with the fixed launcher: the sibling under the temp directory is denied, `.env` is denied, the session directory is the worktree, and findings 6 and 7 are as in the table.
