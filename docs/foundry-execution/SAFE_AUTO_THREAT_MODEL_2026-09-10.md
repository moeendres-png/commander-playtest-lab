# SAFE_AUTO Threat Model — 2026-09-10

Project workstreams intentionally start with `opencode --auto`. Verified CLI
semantics (installed 1.18.30, `--help` text): `--auto` means *"auto-approve
permissions that are not explicitly denied"*. Therefore:

- `ALLOW` under `--auto` = proceeds unattended. Intended for routine engineering.
- `ASK` under `--auto` = **auto-approved**. ASK is an interactive-convenience
  gate only. It MUST NOT be cited as a security boundary for unattended runs.
- `DENY` = technically refused even under `--auto`, **for the exact command
  string matched by the pattern**. Pattern denies do not reach interpreter
  children (see Residual R1).

## 1. Permission vocabulary (§25)

- `ALLOW`: routine engineering action that proceeds unattended
  (read/grep/glob/list, scoped git reads, pytest, python, ruff, local commit).
- `DENY`: impossible from the OpenCode execution plane via direct invocation,
  even with `--auto` (destructive/authority-sensitive command shapes).
- `SAFE_WRAPPED`: not generically available; exposed only through one narrow
  validated project tool with its own hard checks (`foundry-safe-push`).
- `HUMAN_EXTERNAL`: performed outside the unattended Muse execution plane
  (remote branch protection, CLI pin migration, PR merge, worktree deletion).

## 2. Threat catalog and disposition

Direct destructive shapes → `DENY` in `opencode.json` (last-match-wins):

| Threat | Rule(s) | Disposition |
|---|---|---|
| `git push` any form | `git push*` deny | DENY direct; push only via safe_push (SAFE_WRAPPED) |
| force push / delete ref | covered by `git push*` deny (`--force`, `:ref`, `+ref` all start with `git push`) | DENY direct |
| push to main/master | covered by push deny; safe_push additionally refuses main/master | DENY + wrapper refuses |
| merge / rebase | `git merge*`, `git rebase*` deny | DENY (workstream never merges; merges are human-external) |
| `reset --hard`, `clean` | `git reset --hard*`, `git clean*` deny | DENY |
| branch deletion | `git branch -D*`, `git branch -d*` deny | DENY |
| worktree add/remove/move | `git worktree add*/remove*/move*` deny (`list` stays allow) | DENY (launcher/human domain) |
| checkout onto main / new branches | `git checkout main/master/-b*`, `git switch main/master/-c*` deny | DENY |
| history rewriting | `git update-ref*`, `git symbolic-ref*`, `git filter-branch*`, `git filter-repo*` deny | DENY |
| tag delete/force | `git tag -d*`, `git tag -f*` deny | DENY |
| stash drop/clear | `git stash drop*`, `git stash clear*` deny | DENY |
| `rm -rf` / `rm -fr` | deny | DENY |
| `sudo` / `su` | `sudo*`, `su *` deny | DENY |
| env/printenv dump | `env *`, `env`, `printenv*` deny | DENY (secret-bearing output shape) |
| `gh auth` any | `gh auth*` deny | DENY |
| `gh repo` create/delete/fork | deny | DENY (HUMAN_EXTERNAL otherwise) |
| nested shells | `sh -c*`, `bash -c*` deny | DENY the explicit nesting shape |
| `git -C <dir> <cmd>` bypass | `git -C*` deny | DENY the prefix shape |
| absolute-git bypass | `/usr/bin/git*`, `/bin/git*` deny | DENY known absolute shapes |
| `command` prefix bypass | `command *` deny | DENY the prefix shape |
| pipe-to-shell | `*\| sh`, `*\| sh *`, `*\|sh`, `*\|sh *` (+bash variants) deny | DENY download-and-execute shape |
| sibling-worktree write | external_directory deny for live foreign worktrees | DENY known paths; launcher injects current inventory (Checkpoint D) |

## 3. Bypass analysis (honest, tested in `permission_battery.py`)

- B1 `python -c "subprocess.run(['git','push',...])"`: `python*` is ALLOW
  (engineering requires interpreters). Pattern denies do NOT reach interpreter
  children. Disposition: RESIDUAL R1 — mitigated by instruction (AGENTS.md §10,
  implementer rules), audit trail (lock metadata, state, telemetry), human diff
  review before any PR, and safe_push ancestry checks on the receiving side of
  any push that does occur. Never claimed as DENY.
- B2 shell redirection (`git status > file`, `ruff check > x`): redirection is
  shell syntax, not a matchable command. Disposition: RESIDUAL R2, same
  mitigations. No pattern rule can express it (verified CLI wildcard model).
- B3 `env` as command prefix (`env git push`): `env *` deny closes the prefix
  shape; `VAR=x cmd` assignment-prefix form remains RESIDUAL R3 (unmatchable
  in general; same mitigations).
- B4 aliases/functions/wrappers: agent-defined shell functions do not persist
  across tool calls in the execution plane (each bash invocation is a fresh
  shell); a repo-committed wrapper script would be visible in diff review.
  Disposition: mitigated by fresh-shell-per-call + review.
- B5 `--no-verify` against the launcher-installed pre-push hook: hook is
  L3-partial by construction (see §4). Disposition: documented, not relied upon.

## 4. Layered defense (no single layer claims everything)

- L1 pattern denies (this doc §2): stop direct/accidental invocation, including
  unattended `--auto` runs. Tested by the adversarial battery against
  CLI-resolved rules.
- L2 `foundry-safe-push` (SAFE_WRAPPED): the only authorized remote-write path.
  Narrow API (no passthrough flags by construction), fail-closed preconditions
  (identity, branch triple-match, no-detached, single-worktree ownership,
  ancestor-held writer lock, valid state + ancestry, clean tree, fast-forward
  or authorized creation, exact refspec, no main/master, no force/delete/tags,
  no credential output). Adversarially tested with real git remotes.
- L3 launcher-installed pre-push hook (Checkpoint D): rejects pushes lacking
  the launcher's per-run authorization marker. Partial: `--no-verify` bypasses
  hooks; documented as speed-bump, not proof.
- L4 remote-side branch protection on `main` (HUMAN_EXTERNAL, recommendation):
  the backstop no execution-plane mechanism can replace.
- L5 detective: writer-lock metadata, state validated_head chain, telemetry
  autocapture, human diff review before PR. A push that evades L1–L3 is still
  attributable and reversible (fast-forward-only history discipline).

## 5. What SAFE_AUTO does NOT promise

A determined adversary already executing arbitrary Python inside the workstream
with valid credentials cannot be contained by pattern rules. The guarantee is
precisely scoped: **routine unattended engineering proceeds; destructive,
credential-sensitive, and authority-sensitive operations are unavailable by
accident, by direct command, or by trivial prefix/shell wrapping; the sole
remote-write path is the narrow audited wrapper; residual interpreter-bypass
risk is declared, monitored, and human-reviewed.** Any bypass found by the
battery is classified FAIL and repaired or re-documented — the battery is never
weakened to get green.
