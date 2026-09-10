# RQ-A2 — Source Lock

Status: `LOCK_OK` (verified at each milestone; refreshed at terminal state).

## Commander Playtest Lab (research base)

| Item | Value |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| Worktree | `/home/moeen/code/rq-a2-argentum-comparable-qualification` |
| Branch | `research/argentum-comparable-qualification-rq-a2-20260910` |
| Start HEAD (RQ-A1) | `a62a8c7cced4cc226ae9b9a44d06539fbf542bd6` |
| Start TREE | `89bb39fcbe08f5ed722d9b882c19da91632ee262` |
| Terminal HEAD | `ccf1b6342853203f328ee0af3925fab7c8cd8242` |
| Terminal TREE | `0650282046f5304e974be2fe6d05bcad220274b9` |
| Seal | the seal commit after this HEAD modifies only this file (these two rows);
  the recorded TREE is the complete qualified content tree |
| Working tree | owned surface only (`research/candidate-qualification/argentum/rq-a2/`); no other mutation |

Note: one foreign commit (`212109ad`, "recovery: canonicalize workstream state
serialization") touched only `rq-a2/WORKSTREAM_STATE.yaml` serialization mid-campaign;
evidence, harness, and gates verified intact afterward. No other foreign writes observed.

## Argentum candidate source (read-only)

| Item | Expected | Observed | Verdict |
|---|---|---|---|
| Checkout | `/tmp/rq-a2-argentum-src` | present | OK |
| HEAD | `3f46367d87c88bcf156a843a9e69fd29e1693872` | `git rev-parse HEAD` → same (every milestone) | OK |
| TREE | `2adf51caa8f9c6a9908ea961fa988ebb5eb1959f` | unchanged | OK |
| Tracked working tree | clean | `git status --porcelain` → empty (every milestone) | OK |

Permitted by contract only: gitignored Gradle build products (jars, classes, test-results)
inside the checkout, plus CPL-side `rq-a2-classpath.txt` dumps under `*/build/` (gitignored,
regenerated once after a build-cache cleanup removed them; contents re-verified identical
in effect — all eras + core jars present).

## Read-only pledge (Argentum)

- Zero semantic edits; zero new files; no branch/commit/push/patch in the candidate checkout.
- All new qualification drivers live CPL-side (`rq-a2/harness/`); all new fixtures are
  driver-local definitions or recorded inputs. Existing candidate tests were executed
  read-only via `--tests` filters.
- Execution policy donor (`/home/moeen/code/opencode-muse-cross-repo-hardening-v2`) was used
  for nothing except background context; it is not candidate evidence.

## CPL write surface (owned)

- Only `research/candidate-qualification/argentum/rq-a2/**` created/modified, plus focused
  local commits on the research branch. RQ-A1 outputs, WS52/WS53/Q6/Forge/XMage surfaces,
  CPL main, and shared Foundry control-plane files untouched.
- `.foundry/WORKSTREAM_STATE.yaml` left untouched (owned by another workstream surface).

## Evidence classification for this file

`DIRECTLY_VERIFIED` (commands run in-session at each milestone).
