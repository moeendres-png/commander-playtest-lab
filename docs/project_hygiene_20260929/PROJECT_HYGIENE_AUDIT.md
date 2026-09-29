# Project Hygiene Audit — 2026-09-29

Workstream: `PROJECT-HYGIENE-CANONICALIZATION-20260929`
Status: **COMPLETE for the owned, non-destructive scope.** Destructive and
Coordinator-reserved items are classified and issued as exact recommendations, not executed.

Companion documents: [`CLEANUP_LEDGER.json`](CLEANUP_LEDGER.json) ·
[`CANONICAL_KNOWLEDGE_MAP.md`](CANONICAL_KNOWLEDGE_MAP.md) ·
[`LOCAL_STORAGE_LEDGER.md`](LOCAL_STORAGE_LEDGER.md) ·
[`GITHUB_RETIREMENT_LEDGER.md`](GITHUB_RETIREMENT_LEDGER.md) ·
[`DOCUMENTATION_CANONICALIZATION.md`](DOCUMENTATION_CANONICALIZATION.md)

---

## 1. Source Lock

| | |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| `origin/main` at campaign start | `a13db63dcd8baefba9966aa42c704133bdb5c6d8` (tree `79a29b248d044aba393d8db35bf013c6f579eae7`) |
| `origin/main` at campaign end | `72665dcea00d3c74b3272586a9b2794bb86fd93c` (tree `bc16a510b2ff120298035af61372354b9dac422a`) |
| Worktree | `/home/moeen/code/lab-project-hygiene-20260929` |
| Branch | `maintenance/project-hygiene-canonicalization-20260929` |
| Cross-repo | `moeendres-png/forge` and `moeendres-png/mage` treated as **read-only**; not modified |

The prompt's stated baseline (`ebc7e4b3` / `04ad78a5`) was already stale on first fetch.
Fresh Git state was used throughout.

**Mid-campaign drift, handled:** PR #350 merged the DeepSeek-primary routing migration while
this campaign was running, advancing `origin/main` to `72665dce`. That merge was taken into
the branch with a normal merge, the ownership deferrals it held were released, and its result
was audited. Details in `DOCUMENTATION_CANONICALIZATION.md` §4.

---

## 2. The two findings that matter most

### 2.1 `CLAUDE.md` does not exist in this repository

The campaign brief designates `CLAUDE.md` as absolutely immutable. It is not present, and
`git log --all -- CLAUDE.md` is empty — it has never been committed on any ref.

- `CLAUDE_MD_IMMUTABLE_BLOCKER` was **not** raised, because no cleanup required modifying it.
- `CLAUDE_MD_MODIFIED = NO`, and this is not vacuous: nothing of that name exists to modify.
- One real defect *was* found: `docs/FORK_AGENT_POINTER_SPEC.md` referenced `CLAUDE.md` in a
  way that reads as if the Lab repo has one. That document is *about* fork roots. It was
  clarified; the file it referenced was never touched.

### 2.2 The repository's "dead code" is almost entirely deliberate retention

An initial inventory found 12 source modules and scripts with zero inbound references. A
dedicated adversarial falsification pass then tried to **disprove** each as a deletion
candidate, searching for dynamic imports, string references, workflow/test/config consumers,
package re-exports, coverage gates, and git-history intent.

**11 of 12 were refuted and retained.** Representative killers:

- `src/commander_lab/semantic_replay/consumer.py` — its SHA-256 is bound in
  `qualification/ws232-retention-nscoped-requalification/RETENTION_PREDICATES.json`, which
  declares it owns the 14-step replay algorithm. It is a *fresh-process* entrypoint, so zero
  in-process imports is the expected shape, not evidence of deadness.
- `src/commander_lab/semantic_replay/capability.py` — SHA-bound as the capability truth
  (supported counts, tamper matrix) for the WS218 replay lane.
- `src/commander_lab/whole_deck/decision_authority.py` — `ARCHITECTURE_MIGRATION_REPORT.md`
  records it as the deckbuilding/simulation authority boundary.
- `scripts/run_isolated_pytest_suite.py` — implements the *process-isolated batch execution*
  that `AGENTS.md` §1 names as an intended end state. CI running bare `pytest` does not
  replace it.
- `scripts/diagnose_engine_environment.py` and several others — manual operator tools, where
  having no code caller is the point.

**Net result: zero source files were deleted.** One deletion survived the full proof
(§4.1). The generalisable lesson is recorded: *unreferenced is not dead* in this repository,
and a future agent repeating this inventory should expect the same outcome.

---

## 3. What was actually changed

Ten remediations, all documentation or one config line. See
`DOCUMENTATION_CANONICALIZATION.md` for per-file defect/research/wording/validation detail
and [`CLEANUP_LEDGER.json`](CLEANUP_LEDGER.json) for the machine-readable classification.

| ID | Surface | Defect corrected |
|---|---|---|
| R1 | `docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md` | Claimed `POLICY = ACTIVE` and `PENDING_PR172_MERGE` while superseded; prescribed "Muse HIGH" as default execution tier |
| R2 | `docs/foundry-execution/TOKEN_ECONOMY.md` | Operator steps named Muse (now inactive); cited a nonexistent `opencode.json` `instructions` entry |
| R3 | `docs/foundry-execution/HIGH_XHIGH_BENCHMARK.md` | Stated "HIGH default, XHIGH escalation" as standing policy; no HIGH native lane exists |
| R4 | `docs/foundry-execution/GOVERNANCE_PROPAGATION.md` | Gated on "only after PR #172 merges" — permanently inoperative by its own text while indexed active |
| R5 | `docs/foundry-execution/README.md` | Canonical index left stale by the PR #350 routing change; skills 5/7, tools 6/20 listed |
| R6 | `docs/README.md` **(new)** | 77 flat markdown files, no index, no historical disclaimer |
| R7 | `docs/decision-quality/README.md`, `docs/decision_quality/README.md` **(new)** | Two near-twin directories differing only by separator, neither indexed |
| R8 | `README.md` | No route to `AGENTS.md`, the pin authority, the docs map, or the triage index |
| R9 | `docs/FORK_AGENT_POINTER_SPEC.md` | Read as though this repo has a `CLAUDE.md` |
| R10 | `.gitattributes` | Two byte-identity entries for scripts deleted in `e459073d` |

### Rules-surface safety

No change touches legal actions, costs, mana, stack, priority, triggers, replacement,
layers, combat, Commander legality, multiplayer semantics, hidden information, or Rules RNG.
The only non-`.md` edit is a `.gitattributes` deletion. **No Rules-Core behaviour was
modified.**

---

## 4. Deletion proof

### 4.1 The one deletion performed

```yaml
DELETE_PROOF:
  file: .gitattributes   # lines only; the file itself is retained
  removed:
    - "scripts/run_j_p5_development.py -text"
    - "scripts/run_phase7_validation.py -text"
  reason: both scripts were deleted from main in commit e459073d; the entries are dead byte-integrity markers
  references_checked: repo-wide grep — only .gitattributes and a J_P5 freeze JSON reference them
  historical_role: none; the paths no longer exist
  replacement: not applicable; sibling entry scripts/run_j_p5_holdout_once.py is retained
  tests: no test reads .gitattributes; full suite shows zero delta
  risk: none identified. Remaining 30 entries are load-bearing and untouched
```

**Self-correction during diff review:** the first edit to this file accidentally introduced
leading spaces on three retained lines, which would have silently broken their `-text`
patterns. Caught by `git diff` inspection and fixed before commit. The final diff is exactly
the two intended line removals.

### 4.2 Deletions proven necessary but blocked by policy

All recorded in `LOCAL_STORAGE_LEDGER.md` with exact commands. Highlights: ~44 GB of
regenerable build output, a `/tmp` tmpfs at **93% full**, and 14 worktrees proven fully
merged and clean.

---

## 5. Validation

| Check | Command | Result |
|---|---|---|
| Docs/policy integrity | `pytest -q tests/foundry/test_project_integrity.py tests/foundry/test_foundry_tools.py tests/foundry/test_executor_profiles.py tests/foundry/test_drift.py tests/contract/test_phase1212_manual_playtest_removal.py` | **96 passed** |
| Lint | `ruff check .` | **All checks passed** |
| Format | `ruff format --check .` | **1085 files already formatted** |
| Full suite | `pytest -q` (2 env-bound files ignored) | **6 failed, 2242 passed, 8 skipped** |
| Baseline control | identical command on a pristine detached checkout of `origin/main` | **6 failed, 2242 passed, 8 skipped** |

**Test delta vs. pristine baseline: zero. Identical failure sets.**

### 5.1 Two collection errors are pre-existing, not caused by this work

`tests/integration/test_phase5_server.py` and `tests/unit/test_phase5_openai_adapter.py` fail
to *collect* in this environment because `httpx2` and `pytest-asyncio` are not installed.
Proven by running the identical command on an unmodified detached checkout of the same
commit. Recorded rather than worked around; installing packages was out of scope.

### 5.2 A working trap worth knowing about

An intermediate run showed **55 failures** on the modified tree versus 6 on baseline. Root
cause: `src/commander_lab/tools/service.py:387` defines `tracked_worktree_dirty` as
`git status --porcelain --untracked-files=no` being non-empty, and a dirty tracked worktree
makes canonical inputs *stale*, which fails a large family of tools closed.

**This is the guard working correctly, not a regression.** Any local edit run of this suite
produces this cascade. Two practical consequences:

1. Do not "fix" it by weakening the guard, and do not read the cascade as a code regression.
2. Validate documentation-only changes by **committing first**, then running the suite.

Recorded as a reusable finding for future agents.

---

## 6. Local disk findings

`/home/moeen/code` is **104 GB**. The Git object store for this repository is only **273 MB**
and is healthy (24 packs, 0 garbage, 0 prunable worktrees, 0 orphan metadata, 0 tags).
**Storage is not a Git-maintenance problem — it is duplicated worktrees and build output.**

| Category | Size | Regenerable | Action |
|---|---|---|---|
| `target/`, `node_modules/`, `__pycache__`, caches, `.runtime` | **~29.8 GB** | yes | `USER_ACTION_REQUIRED` (exact commands issued) |
| `*/db/cards.h2.mv.db` H2 card databases | **~7.0 GB** | yes, expensively | `USER_ACTION_REQUIRED` |
| 197 registered worktrees | **~42.0 GB** | 14 proven stale (~1.4 GB) | `USER_ACTION_REQUIRED` |
| `/tmp` tmpfs | **93% full, 603 MB free** | — | **operational risk, see ledger** |
| Shared caches (`~/.m2`, `~/.gradle`, `~/.npm`, `~/.cache`) | ~8.9 GB | yes, costly | deliberately not recommended |

Nothing was deleted locally. `git worktree remove`, `rm -rf`, and branch deletion are denied
by project policy, and reproducing their effect by another mechanism is forbidden. Exact
per-item commands are in `LOCAL_STORAGE_LEDGER.md`.

---

## 7. GitHub findings

46 open PRs, 345 remote branches, 288 registered workflows against 18 workflow files, 15,124
artifacts (112 GB), 0 tags, 0 releases, 0 milestones.

### 7.1 The highest-severity finding: PR #285

**PR #285 (`sbmax/full-completion`, head `b4ea7751`) must never be merged.** Its head tree
contains **6 tracked files**, all blob-identical to `origin/main`; the diff against `main` is
**2,096 files, −1,107,165 lines**. A careless merge deletes the repository.

This is not a content-free PR. The campaign's real content is recoverable **earlier on the
same branch** at `4a56d179` (2,145 files, +45,639/−40,173, 54 unmerged commits) — the commit
the PR body itself pins.

Recommended disposition is `CLOSE_NEEDS_CONFIRMATION` plus a successor PR from a **new**
branch at `4a56d179`. That is a Coordinator decision because the recovered content is real
unmerged work, so it was not executed unilaterally. The branch must not be deleted.

### 7.2 Provably safe PR closures performed

Six PRs whose bodies self-declare terminal/superseded status, where a named successor exists
and no unique pending task remains, were closed with a provenance comment. Detail and
per-PR evidence in `GITHUB_RETIREMENT_LEDGER.md`.

### 7.3 Structural GitHub findings reported, not acted on

- **277 stale workflow registrations** (270 path-less + 7 path-bearing) whose YAML no longer
  exists on `main`. Inert; de-registering is cosmetic. `NO_ACTION`.
- **Artifacts: 112 GB, 0 expired.** 88% sits in one advisory re-runnable lane. The ~450 MB of
  genuinely stale lanes is the *small* population, and much of it is cited by open PR bodies
  by artifact ID **and SHA-256**. Expiring broadly would destroy the only retrievable copy of
  cited evidence. `EXPIRE_ARTIFACTS_SAFE` for a narrow ~50 MB subset only.
- **107 remote branches have zero unmerged commits *and* zero net diff.** ~25 carry actively
  misleading names (`noop`, `tmp-do-not-use`, `engine/xmage-full-game-external-pilots-{unused,
  stop, safety, final, final2, do-not-use, work}`). Deleting branches is denied by policy; the
  list is issued as a recommendation.
- **A ruleset gap:** the ruleset requires only 3 check contexts (`quality`, `security`,
  `infrastructure`) while 10 real gates emit advisory checks; `required_approving_review_count`
  is 0. This is a strengthening opportunity, deliberately **not** proposed for execution here.
- **Pin divergence:** CI builds XMage at `f79e4168…` while open Rules-Core defect issues
  #327/#328/#334/#335 report defects at `b1959698…`. The reported defects may not reproduce
  against the engine CI actually builds. Evidence-integrity concern, reported only.

---

## 8. Explicitly out of scope / not actioned

| Item | Why |
|---|---|
| Evidence-classification vocabulary (deferral `D1`) | Evidence-policy decision reserved to the Coordinator tier. Changing it from a hygiene pass would invent policy |
| Uncertain dead code (9 items) | No proven replacement; `UNKNOWN` is never deleted |
| 32 byte-identical duplicate groups (~3.85 MiB) | Evidence-retention policy dominates a trivial byte saving; no deletion proof established |
| `docs/pre_freeze_completion_20260927/CAMPAIGN_STATE.md:58` mislabel | Left byte-unchanged rather than rewrite a pre-freeze campaign packet |
| Root `README.md` architecture framing | Needs a decision on which architecture summary belongs in the entrypoint |
| Capital-S "Structural" terminology | Consistent product name in 10+ locations; a single-occurrence flip was reverted during diff review because it created internal inconsistency |
| Any Rules-Core, engine, or provider surface | Out of scope by contract |
| `PRODUCTION_PROVIDER` / `ARCHITECTURE_FREEZE` | Reserved Coordinator decisions. Neither claimed |

---

## 9. What future engineers no longer need to rediscover

1. **`CLAUDE.md` does not exist here** and never has.
2. **Unreferenced ≠ dead.** 11 of 12 "dead" candidates were deliberate retention; the two
   `semantic_replay` modules are SHA-bound in qualification manifests.
3. **A dirty tracked worktree makes the suite fail closed**, with a ~49-failure cascade that
   looks like a regression and is not. Commit, then test.
4. **Two collection errors are environmental** (`httpx2`, `pytest-asyncio` missing), not
   repository defects in this environment.
5. **The 6 baseline test failures** are pre-existing on `origin/main` and unrelated to any
   documentation work.
6. **Executor routing is now DeepSeek MAX / Space Bunny MAX**, Muse and GLM inactive. Seven
   files repeat this with unequal test coverage, which is exactly how
   `docs/foundry-execution/README.md` went stale.
7. **Engine pins have exactly one authority** and the no-restatement rule is honored; do not
   reintroduce prose pins.
8. **PR #285's head is a repository deletion.** Recover at `4a56d179`; never merge `b4ea7751`.
9. **Where things are**: `docs/README.md` for the 294-file documentation tree,
   `CANONICAL_KNOWLEDGE_MAP.md` for "read this for subject X".

---

## 10. Preserved despite staleness

Nothing was deleted to achieve tidiness. Explicitly preserved:

- `docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md` — banner applied, body retained.
- `docs/foundry-execution/HIGH_XHIGH_BENCHMARK.md` — superseded note added, policy text retained.
- `docs/foundry-execution/GOVERNANCE_PROPAGATION.md` — gate corrected, procedure retained.
- `docs/decision-quality/` and `docs/decision_quality/` — **not renamed or merged**; a README
  was added to each, because rewriting historical provenance is forbidden.
- `docs/next_step_handoff_*.md` chains, `docs/archive/**`, and all dated workstream packets.
- All 236 branches carrying unique unmerged commits, including
  `origin/ws47/successor-contract-v1.0.5-freeze` (the immutable authority that PRs
  #159/#160/#163/#164 all bind to) and every `donor/*` lane.
- The SHA-bound `semantic_replay` modules and every falsified deletion candidate.
- All 15,124 GitHub artifacts, none expired.

---

## 11. Status

```
PROJECT_HYGIENE_AUDIT       = COMPLETE (owned non-destructive scope)
UNIQUE_WORK_LOST            = NO
EVIDENCE_DELETED            = NO
CLAUDE_MD_MODIFIED          = NO  (no CLAUDE.md exists; nothing of that name was touched)
PRODUCTION_PROVIDER         = NOT_SELECTED
ARCHITECTURE_FREEZE         = NOT_CLAIMED
```

Residual blockers are grouped by mechanism in the final handoff. The dominant one is
**policy**: the highest-value local cleanup and the highest-severity GitHub action both
require operator or Coordinator authority, not agent authority.
