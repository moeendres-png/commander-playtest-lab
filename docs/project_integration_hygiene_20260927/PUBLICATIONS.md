# WSR23 — Publications

## Summary

| Action | Outcome |
|---|---|
| Fast-forward publication of `wsr23/project-integration-hygiene-20260927` | **`BLOCKED_BY_PUSH_POLICY_GATE`** |
| Opening the WSR23 pull request | Blocked by the same gate (a PR needs a remote head branch) |
| Terminal supersession comments on PRs #161, #162, #166, #167 | **DONE** |
| Closing PRs #161, #162, #166, #167 | **DONE** |
| Publishing any foreign unpublished branch | **NOT ATTEMPTED** — §12 conditions 9/10 provably fail for all of them |

No force push, no raw `git push`, no tag widening, no alternate remote, no history rewrite, no
branch deletion, and no permission gate was wrapped or bypassed.

## 1. The publication gate, and exactly what it said

The project hardened safe-push is `tools/foundry/safe_push.py`. It was invoked through its real
CLI, with the real state file, the real branch, and the real expected slug:

```text
$ python3 tools/foundry/safe_push.py \
    --worktree . \
    --expected-branch wsr23/project-integration-hygiene-20260927 \
    --state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml \
    --expected-slug moeendres-png/commander-playtest-lab \
    --dry-run

PUSH_REJECT: no writer lock (run inside the validated launcher)
```

**Diagnosis, from `tools/foundry/safe_push.py:485-509`.** Gate 6 requires the kernel `flock(2)`
on `~/.local/share/commander-foundry/writer-locks/sha1(<worktree>)-<name>.lock` to be **held**,
and the recorded holder PID to be an **ancestor of the pushing process**. The only component
designed to hold that lock is `tools/foundry/launcher.py`, which holds it across an OpenCode child
session's lifetime.

This session does not satisfy that precondition, and the reason is structural, not a
misconfiguration:

- PID 77022 is the WSR23 session, and its recorded `cwd` is `/home/moeen/code` — the workspace
  root, **not** the WSR23 worktree.
- It was not spawned by `tools/foundry/launcher.py`, so no lock was ever acquired for
  `/home/moeen/code/wsr23-project-integration-hygiene`.
- `writer_lock.py` documents the threat model explicitly: the kernel flock is the single source
  of truth and the holder metadata is diagnostic only, so that "stale metadata can never brick a
  worktree" and so that "the kernel releases the lock on any fd close, including `kill -9` — no
  PID-file trust".

**Why WSR23 did not self-acquire the lock.** Acquiring
`writer_lock.Lock(...).acquire()` from this process would make this process the recorded holder
and would satisfy the gate. That is precisely the bypass the gate exists to prevent: it would let
any process self-authorize as the exclusive writer of any worktree and collapse the single-writer
guarantee that the whole Foundry ownership model rests on. §12 says *"Use the project hardened
safe-push mechanism. Never bypass it."* and *"If the permission layer still denies publication: do
NOT evade it."* Self-granting the ownership evidence is evasion, not use. WSR23 therefore stopped.

A raw `git push` was **not** attempted, not even as a probe, and not even in dry-run form: a
push-intent against a real remote ref is a write, and the committed `opencode.json` explicitly
denies `git push*`.

## 2. Exactly one verified safe human command

Run from inside a Foundry **writer** session for this worktree — that is, a session started by
`tools/foundry/launcher.py` in mode `writer` with `--worktree
/home/moeen/code/wsr23-project-integration-hygiene`, `--branch
wsr23/project-integration-hygiene-20260927`, `--state
/home/moeen/code/wsr23-project-integration-hygiene/docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml`
and `--audit-base-sha bbbb6b9c3e9297265c2a488c9ae72a72c0ff3719`. Inside that session:

```text
python3 tools/foundry/safe_push.py --worktree . --expected-branch wsr23/project-integration-hygiene-20260927 --state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml --expected-slug moeendres-png/commander-playtest-lab
```

This is byte-verified against the actual `safe_push.py` argument parser: every flag name above
exists, no flag is invented, and the invocation is identical to the one WSR23 ran — it differs
only by the absence of `--dry-run`. It remains a single fast-forward of one refspec to one
validated remote, or it fails closed with a reason. It cannot force, delete, widen to tags, or
target a different remote, because the tool takes identities and never refspecs or flags.

## 3. Publication state

| Field | Value |
|---|---|
| Branch | `wsr23/project-integration-hygiene-20260927` |
| Local HEAD | `240a8d40` rebased onto `bbbb6b9c` (see §4), plus the final packet commit |
| Remote branch | `origin/wsr23/project-integration-hygiene-20260927` still at `c5f9418e` |
| Relationship | local is a **strict descendant** of the remote ref; publication is a clean fast-forward, no force needed |
| Tree | clean |
| PR | **not opened** — requires the branch to exist on the remote first |
| Result | `BLOCKED_BY_PUSH_POLICY_GATE` |

The work is fully resumable: one local commit chain, a validated schema-2.0 state file, and a
durable packet. Nothing is lost by the block, and no human needs to reconstruct any analysis.

## 4. Main drift absorbed before the block

`main` advanced three times while WSR23 ran. WSR23 fetched, adjudicated, rebased and re-validated
rather than publishing a stale base. Full record in `main_drift` on every packet JSON file.

| Merged | Commit | Impact on WSR23 |
|---|---|---|
| PR #261 governance hardening | `613cd57b` | **NO_IMPACT.** 9 paths, none of them WSR23's. Critically, `AGENTS.md` section numbering was **not** changed, so repair R1's §11 → §12 correction is still correct on the new base. |
| PR #260 Rules authority freshness | `60fc3c8a` | **NO_IMPACT.** 6 paths, none of them WSR23's. |
| PR #268 pre-Freeze terminal closeout | `bbbb6b9c` | **NO_IMPACT.** 1 path. |

15 paths changed on `main`; intersection with WSR23's mutation surface is **empty**. The rebase
was a clean, conflict-free replay of a single commit.

## 5. Foreign branch publication: not attempted, and why

Every unpublished foreign branch fails §12.9 (validation bound to the exact tip) or §12.10
(main/candidate drift), on measured evidence rather than caution. Full per-branch reasoning in
`PUBLICATION_CANDIDATES.json`. The headline case:

`camp/rg-closure-20260925` (12 unpublished commits) is the largest item in the workspace and the
only carrier of the RG-07 and RG-08 qualifications. It is **not** publication-ready: it is a
divergent sibling of merged PR #249 from the same merge-base `c491528c`, 129 commits behind,
conflicting with canonical merged code on two production files, and its evidence is bound to
engine pin XMage `b1959698`, which PR #242 and then PR #249 superseded. It is recorded as
`NOT_READY` and, critically, **not** a deletion candidate either.

## 6. Remote hygiene completed

| PR | Head | Terminal comment | Closed (UTC) |
|---|---|---|---|
| #161 `chore/foundry-agents-policy` | `26409b93` | [5857087212](https://github.com/moeendres-png/commander-playtest-lab/pull/161#issuecomment-5857087212) | 2026-09-27T15:15:02Z |
| #162 `ws47/successor-contract-v1.0.5-freeze` | `5a2e4f46` | [5857091609](https://github.com/moeendres-png/commander-playtest-lab/pull/162#issuecomment-5857091609) | 2026-09-27T15:15:05Z |
| #166 `ops/opencode-muse-primary-privacy-20260908` | `22e2a20f` | [5857091730](https://github.com/moeendres-png/commander-playtest-lab/pull/166#issuecomment-5857091730) | 2026-09-27T15:15:11Z |
| #167 `project/resource-constrained-execution-policy-20260908` | `633f51ae` | [5857091862](https://github.com/moeendres-png/commander-playtest-lab/pull/167#issuecomment-5857091862) | 2026-09-27T15:15:15Z |

Each comment states why it is superseded, names the canonical successor, states whether unique
evidence remains, and records current project status. Open PR count: **41 → 36**. No content was
deleted; all four branches and every commit remain on the remote.

Not touched: #259, #262 (active), #163, #164 (`STALE_BUT_UNADJUDICATED`), and the 31
`SUPERSEDED_BUT_UNIQUE_CONTENT_REMAINS` PRs.
