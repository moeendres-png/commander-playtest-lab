# WSR23 — Publications

## Summary

| Action | Outcome |
|---|---|
| Diagnosing and repairing the `LAUNCH_REFUSED / BOOTSTRAP_FAIL` ownership failure | **DONE** — root cause found, state repaired, `BOOTSTRAP_PASS` |
| Foundry tooling defect found during that diagnosis (`worktree_inventory` JSON ownership) | **DONE** — repaired, 8 tests added |
| Recording honest validation credit for the repair head | **DONE** — 1638 passed / 5 skipped / 0 failed |
| Fast-forward publication of `wsr23/project-integration-hygiene-20260927` | **`BLOCKED_BY_PUSH_POLICY_GATE`** |
| Opening the WSR23 pull request | Blocked by the same gate (a PR needs a remote head branch) |
| Terminal supersession comments on PRs #161, #162, #166, #167 | **DONE** |
| Closing PRs #161, #162, #166, #167 | **DONE** |
| Publishing any foreign unpublished branch | **NOT ATTEMPTED** — §12 conditions 9/10 provably fail for all of them |

No force push, no raw `git push`, no tag widening, no alternate remote, no history rewrite, no
branch deletion, and no permission gate was wrapped or bypassed.

## 0. Correction to the earlier diagnosis in this document

The original §1 attributed the launcher failure to the push policy gate. That was incomplete.
The launcher was in fact refusing at the **bootstrap** gate, for an unrelated reason, and that
reason has now been diagnosed at its real layer and repaired. Full evidence in
`STATE_OWNERSHIP_REPAIR.md`; the short form:

- `tools/foundry/bootstrap.py:165-173` compares the state's `ownership` field to the launching
  workstream as an **identity token**. The WSR23 state held a descriptive sentence there.
- The gate was correct and the state was malformed. `bootstrap.py:47-74` — the tool's own
  `init_state()` generator — writes `ownership = workstream`, the bare token; `safe_push.py:593`
  records the same field as the push `task_id`; and five of the six committed schema-2.0 states
  in this repository hold bare tokens. The one prose outlier is `ws58`, a historical instance of
  the same defect, not a competing convention.
- `ownership` is now the exact token `wsr23-project-integration-hygiene-20260927`. The original
  sentence is preserved verbatim in `technical_decisions`, and its substance is unchanged in
  `WORKSTREAM_CONTRACT.md`, `in_scope` and `files_modified`.
- The gate was **not** loosened. A regression test now pins that prose ownership is refused
  *even when it names the correct workstream*, because the gate compares and must never parse
  prose to guess the owner.

Fix-after: `BOOTSTRAP_FAIL` → `BOOTSTRAP_PASS`.

While diagnosing, a second and genuinely systemic defect surfaced in
`tools/foundry/worktree_inventory.py`: `_ownership_from_file` line-scanned for a bare
`ownership:` YAML key, so it returned `UNKNOWN` for every **JSON**-serialized schema-2.0 state
— including WSR23's own — even though `state.py` and `bootstrap.py` read the identical field
from the identical file correctly. It now uses the same structured reader as the rest of the
stack and fails closed on any non-mapping, unparseable or non-string value. That path is
disjoint from WSR22, which touches no `tools/foundry/**` or `tests/foundry/**` file.

## 1. The publication gate, and exactly what it says

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

**Diagnosis, from `tools/foundry/safe_push.py:485-513`.** Gate 6 requires the kernel `flock(2)`
on `~/.local/share/commander-foundry/writer-locks/sha1(<worktree>)-<name>.lock` to be **held**,
and the recorded holder PID to be an **ancestor of the pushing process**. The only component
designed to hold that lock is `tools/foundry/launcher.py`, which holds it across an OpenCode child
session's lifetime.

This session does not satisfy that precondition, and the reason is structural, not a
misconfiguration:

- It carries **no `FOUNDRY_*` launcher context at all** — not `FOUNDRY_WORKTREE`,
  `FOUNDRY_STATE_PATH`, `FOUNDRY_BRANCH`, `FOUNDRY_WORKSTREAM` or `FOUNDRY_RUN_DIR`. The
  launcher never ran to completion for this workstream.
- The run directory the launcher would have used,
  `/tmp/foundry-launch-wsr23-project-integration-hygiene-20260927`, exists but is **empty**:
  the launcher created it, then aborted at `init` before writing `launch-context.json` or
  acquiring any lock. That is the direct on-disk trace of the `LAUNCH_REFUSED` reported in §0.
- It was therefore not spawned by `tools/foundry/launcher.py`, so no lock was ever acquired for
  `/home/moeen/code/wsr23-project-integration-hygiene`.
- `writer_lock.py` documents the threat model explicitly: the kernel flock is the single source
  of truth and the holder metadata is diagnostic only, so that "stale metadata can never brick a
  worktree" and so that "the kernel releases the lock on any fd close, including `kill -9` — no
  PID-file trust".

**Why WSR23 did not self-acquire the lock.** Acquiring
`writer_lock.WriterLock(...).acquire()` from this process would make this process the recorded holder
and would satisfy the gate. That is precisely the bypass the gate exists to prevent: it would let
any process self-authorize as the exclusive writer of any worktree and collapse the single-writer
guarantee that the whole Foundry ownership model rests on. §12 says *"Use the project hardened
safe-push mechanism. Never bypass it."* and *"If the permission layer still denies publication: do
NOT evade it."* Self-granting the ownership evidence is evasion, not use. WSR23 therefore stopped,
and this is now recorded in the state file's `out_of_scope` so a later session cannot mistake it
for unexplored work.

A raw `git push` was **not** attempted, not even as a probe, and not even in dry-run form: a
push-intent against a real remote ref is a write, and the committed `opencode.json` explicitly
denies `git push*`.

**Gate status after the §0 repair.** The ownership fix and the honest `validated_head` credit
cleared everything else the tool checks. The dry-run now rejects at gate 6 and nowhere earlier,
which is the minimum honest remaining gate:

| safe_push gate | Requirement | Status |
|---|---|---|
| 1 | state parses and validates as schema 2.0 | PASS |
| 2 | branch-name safety | PASS |
| 3 | remote identity: fetch URL **and** effective push URL | PASS |
| 4 | live branch = expected branch = state branch, no detached HEAD | PASS |
| 5 | branch owned by exactly one worktree, and it is this one | PASS |
| 6 | kernel flock held by an ancestor PID | **REJECT — intended** |
| 7 | state coherence and non-null `validated_head` with ancestry | PASS |
| 8 | clean tree | PASS |
| 9 | `audit_base_sha` is an ancestor of HEAD | PASS |
| 10 | remote ref state permits a fast-forward | not reached (gate 6 stops first) |

## 2. Exactly one verified safe human command

Run from inside a Foundry **writer** session for this worktree — that is, a session started by
`tools/foundry/launcher.py` in mode `writer` with `--worktree
/home/moeen/code/wsr23-project-integration-hygiene`, `--branch
wsr23/project-integration-hygiene-20260927`, `--workstream
wsr23-project-integration-hygiene-20260927`, `--state
/home/moeen/code/wsr23-project-integration-hygiene/docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml`
and `--audit-base-sha bbbb6b9c3e9297265c2a488c9ae72a72c0ff3719`. Inside that session:

```text
python3 tools/foundry/safe_push.py --worktree . --expected-branch wsr23/project-integration-hygiene-20260927 --state docs/project_integration_hygiene_20260927/WORKSTREAM_STATE.yaml --expected-slug moeendres-png/commander-playtest-lab
```

`--workstream wsr23-project-integration-hygiene-20260927` is now mandatory rather than
cosmetic: it is the value the state file's `ownership` field must equal for the bootstrap gate to
pass (§0). Omitting it is what produced the original `LAUNCH_REFUSED`.

This is byte-verified against the actual `safe_push.py` argument parser: every flag name above
exists, no flag is invented, and the invocation is identical to the one WSR23 ran — it differs
only by the absence of `--dry-run`. It remains a single fast-forward of one refspec to one
validated remote, or it fails closed with a reason. It cannot force, delete, widen to tags, or
target a different remote, because the tool takes identities and never refspecs or flags.

## 3. Publication state

| Field | Value |
|---|---|
| Branch | `wsr23/project-integration-hygiene-20260927` |
| Local HEAD | `372851c145fc35f5b2dc887a21fdd872ef1184d5` (ownership-identity repair), on top of `bdc190b5` |
| `validated_head` | `372851c145fc35f5b2dc887a21fdd872ef1184d5` — 1638 passed, 5 skipped, 0 failed, lock-faithful Python 3.12.14 venv, clean tree |
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
