# RQ-A1 — Argentum Source Lock

Status: `LOCK_OK` (verified 2026-09-10, execution session).

## Commander Playtest Lab (research base)

| Item | Expected | Observed | Verdict |
|---|---|---|---|
| Repository | `moeendres-png/commander-playtest-lab` | verified via worktree remote context | OK |
| Worktree | `/home/moeen/code/rq-argentum-readonly` | `pwd` of this session | OK |
| Branch | `research/argentum-readonly-qualification-20260910` | `git branch --show-current` → same | OK |
| CPL HEAD | `c162871ba416c338d37f83a44fbd5b054e79ca0e` | `git rev-parse HEAD` → same | OK |
| CPL working tree | clean | `git status --short` → empty | OK |

## Argentum candidate source (read-only)

| Item | Expected | Observed | Verdict |
|---|---|---|---|
| Checkout | `/tmp/rq-argentum-src` | present, `git log -1` reachable | OK |
| Argentum HEAD | `3f46367d87c88bcf156a843a9e69fd29e1693872` | `git rev-parse HEAD` → same (`Merge pull request #2283 … add-lorwyn-card-batch`) | OK |
| Argentum TREE | `2adf51caa8f9c6a9908ea961fa988ebb5eb1959f` | `git rev-parse HEAD^{tree}` → same | OK |
| Argentum working tree | clean | `git status --short` → empty | OK |

No `SOURCE_LOCK_MISMATCH`. Work proceeded.

## Read-only pledge (Argentum)

- Zero semantic edits made in `/tmp/rq-argentum-src` (verified by `git status --short` → empty at end of workstream; see test-corpus file for build-product handling).
- No Argentum branch created, no commit, no push, no patch of failing tests, no implemented cards, no new adapter.
- Permitted by contract only: Gradle build products / compiler caches under `/tmp/rq-argentum-src` build dirs and `~/.gradle`, plus ordinary generated test output (JUnit XML under `build/test-results`). These are gitignored build artifacts, not source mutations.
- All exploration of Argentum was read (`Read`/`Grep`/directory listing) plus execution of *existing* Gradle test tasks at the exact source lock.

## CPL write surface (owned)

- Only `research/candidate-qualification/argentum/rq-a1/` created/modified in the CPL worktree, plus focused local commits on the research branch.
- Shared surfaces untouched: `AGENTS.md`, `opencode.json`, `.opencode/`, `.foundry/` shared tooling, Q6/WS48/WS50/WS51 files, hardening/optimizer/provider files.

## Note on `.foundry/WORKSTREAM_STATE.yaml`

The pre-existing `.foundry/WORKSTREAM_STATE.yaml` in this checkout declares ownership by a different workstream/branch (`project/opencode-execution-system-consolidation-20260910`, worktree `/home/moeen/code/commander-exec-consolidation`). It is stale relative to this branch and owned by another active session's surface. Per the "do not modify another active workstream's surface" rule it was left untouched; workstream persistence for RQ-A1 lives in this output directory plus local commits on the research branch. This decision is recorded here rather than silently overwriting shared state.

## Evidence classification for this file

`DIRECTLY_VERIFIED` (commands run in-session, outputs quoted above).
