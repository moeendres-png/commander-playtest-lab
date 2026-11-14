# GitHub Retirement Ledger

Disposition of every Commander Simulator Next GitHub surface audited on 2026-09-29.
Base: `origin/main` = `72665dcea00d3c74b3272586a9b2794bb86fd93c` (tree `bc16a510…`).

Conservative floor applied throughout: **every** surface with unique unmerged commits, a
pinned SHA-256 evidence digest, an open PR, an active worktree, or no open PR at all is
`NO_ACTION` or `*_NEEDS_CONFIRMATION`. No branch with unique content was deleted, no gate was
weakened, and no historical result was altered.

---

## 1. Inventory at audit start

| Surface | Count |
|---|---:|
| Open PRs | 46 |
| Open PRs with a non-empty diff vs `main` | 46 (none content-superseded by `main`) |
| Open PRs whose head tree is a destructive collapse | **1** (#285) |
| Local branches | 219 |
| Remote branches | 345 |
| Remote branches fully merged with zero net diff | 107 |
| Remote branches with unique unmerged commits | 236 |
| Open issues | 7 |
| Registered workflows on GitHub | 288 |
| Workflow files present on `main` | 18 |
| Actions artifacts | 15,124 (112 GB), 0 expired |
| Tags / releases / milestones | 0 / 0 / 0 |

---

## 2. Pull requests closed — 14, all with provenance

Every closure below was justified by the PR's **own body** plus an independent measurement.
Branches were **not** deleted. No PASS/FAIL count, artifact ID, or historical result was altered.

### 2.1 Superseded by a named successor (3)

| PR | Head | Evidence | Successor |
|---|---|---|---|
| #304 | `08d23aa4` | `git merge-base --is-ancestor 08d23aa4 20b52958` = **true**; its 23-file diff is a strict subset of #333's 26; #333 body line 1: *"Successor to PR #304, on the remotely preserved donor head"* | #333 |
| #132 | `3e4e5b4d` | Body headed `## SUPERSEDED — PRE-WS17R PROVENANCE ONLY`; *"must not be merged"*; content marked `PROVISIONAL_PRE_WS17R_NOT_ADMISSIBLE` | #135 |
| #160 | `86c2e74e` | Body: *"WS-46 is superseded by immutable WS-47 v1.0.5 and must not continue broad v1.0.4 provider qualification"*; *"do not merge"* | `origin/ws47/successor-contract-v1.0.5-freeze` |

### 2.2 Terminal fail-closed workstreams (10)

| PR | Recorded terminal verdict | Preserved receipt |
|---|---|---|
| #159 | `WS45 = COMPLETE / FAIL_IMMUTABLE_WS44_CONTRACT_CONFLICT` | artifact `10054440299`, SHA-256 `280f87b8…` — **not expired** |
| #157 | *"must remain Draft and must not be merged as a successful successor freeze"* | documented freeze *failure* |
| #156 | `WS42 = COMPLETE / BLOCKED_BY_IMMUTABLE_V1_0_3_CONTRACT_DEFECT` | terminal lock `87b0a571…` |
| #155 | *"terminal continuation closure"*, 0 post-repair defects | contract on branch |
| #154 | `WS40_WORKSTREAM_TERMINAL = YES / TASK_COMPLETE = YES / TERMINAL_FAIL_IMMUTABLE_CONTRACT_DEFECT` | GPL-side integration preserved |
| #151 | `COMPLETE / FAIL_NOT_QUALIFIED` | terminal capability blocker at pinned XMage |
| #150 | `COMPLETE / FAIL_TERMINAL_NO_QUALIFIED_PROVIDER` | consumes both terminal WS lanes |
| #149 | `COMPLETE / FAIL_NOT_QUALIFIED`, 107/107 terminally classified | artifact `9828355438`, SHA-256 `eb983fc2…` — **not expired** |
| #145 | `COMPLETE / PASS_CLOSED` (Authority Run #18) | run `33384808218`; body notes it grants **zero runtime-functionality credit** |
| #139 | `WS-23 COMPLETE` (architecture qualification) | 17/135 and 1/29 denominators; explicitly **not** provider selection |
| #138 | `WS-22 COMPLETE` — XMage not Architecture-Freeze eligible | workflows green on `6db86f69…` |

### 2.3 Deliberately **not** closed

| PR | Why not |
|---|---|
| **#285** | Head is a destructive collapse, but `4a56d179` holds real unmerged campaign work. Closing and opening a successor is a Coordinator decision. A **warning comment with full measurements was posted instead** |
| **#122** | Body says *"This PR must remain unmerged"* but does **not** declare the work complete. It is a reusable validation-only trigger surface. "Must not merge" ≠ "terminal" |
| #333, #316, #349, #309, #302, #301, #300, #290, #288 | Active or in-flight workstreams |
| #299, #297 | Two parallel PB-09 lanes on divergent lineages; choosing between them is a Coordinator decision |
| #287, #285-adjacent `docs/final-adversarial-audit-20260928` | Draft, explicitly "DO NOT AUTO-MERGE" |
| #164, #163, #153, #152, #148, #147, #146, #144, #143, #142, #141, #140, #137, #136, #128, #126 | Stale but carry unique unmerged commits. `NO_ACTION` |

**Open PRs: 46 → 37.**

---

## 3. The highest-severity finding: PR #285

Independently re-verified during this campaign:

| Check | Result |
|---|---|
| Files in head `b4ea7751` | **6** |
| Files on `origin/main` | **2,180** |
| `git diff --shortstat origin/main...b4ea7751` | **2,096 files changed, 1,107,165 deletions(-)** |
| Blobs of the 6 surviving head files | all **identical to `origin/main`** |

**Merging this head deletes the repository.** Recovery point on the same branch:

| Check | Result |
|---|---|
| Files at `4a56d179` | **2,145** |
| `git diff --shortstat origin/main...4a56d179` | **120 files, +45,639 / −40,173** |

A warning comment carrying these measurements was posted. **Action taken: none.** Branch
preserved. Coordinator decides.

Related defect: the PR body cites tag `sb-independent-baseline-20260928` as an evidence
anchor. The repository has **zero tags**, so that anchor is unverifiable by ref.

---

## 4. Branches — disposition, no deletions performed

Branch deletion is denied by project policy, and the list below is therefore issued as a
recommendation.

### 4.1 `BRANCH_DELETE_SAFE` — ~25 branches, fully merged, zero net diff, misleading names

Proven by `git rev-list --count origin/main..origin/<b>` = 0 **and**
`git diff --shortstat origin/main...origin/<b>` empty.

```
noop
tmp-do-not-use
tmp-do-not-use-2
engine/xmage-full-game-external-pilots-{unused,stop,safety,final,final2,do-not-use,work}
agent/xmage-b4*-{check,unused,do-not-use}
roadmap/j-p0-*
release/j-p0-recovery-snapshot
rules-evidence/capability-unlock
patch/post-official-decision-fidelity-search-efficiency
fix/post-official-fidelity-search-liveness-20260823
cleanup/project-decommission-20260819
closeout/exact-main-recovery-observable
telemetry/t1-*  telemetry/t2-*
diag/j-p2-ruff-format
eval/j-p2-holdout-2026-08-10
```

Eleven of these carry actively misleading names (`unused`, `stop`, `do-not-use`, `final2`,
`noop`, `tmp-do-not-use`) while resolving to identical, fully-merged content.

**Expected benefit:** removes ~25 misleading names; 345 → ~320 remote refs; **zero content
loss** (proven zero unmerged commits and zero net diff).

### 4.2 `BRANCH_DELETE_NEEDS_CONFIRMATION` — ~82 branches

Fully merged with zero net diff, but names carry campaign history: `cpl/full107-*`,
`cpl/xmage-*`, `cpl/real-4p-*`, `sol/rg0*`, `sol/pre-freeze-*`, `ws2xx-*`, `ops/dual-*`,
`foundry/*`, `hardening/`, `policy/`, `post-j/*`, `j-final/*`. Deleting them is probably
correct but is a history-destroying decision. **Operator call.**

### 4.3 `NO_ACTION` — never delete

- All **236** branches with unique unmerged commits.
- **`origin/ws47/successor-contract-v1.0.5-freeze`** (138 commits, no PR) — the immutable
  authority that PRs #159, #160, #163 and #164 all bind to. Deleting it destroys the
  qualification contract of record.
- Every `donor/*` lane, `sbmax/*`, `muse-xhigh-independent-*`, and
  `sol/final-integration-salvage-20260928` (108 commits, receipt recorded, content not in main).
- `origin/sol/pb03-current-main-runtime-20260929` — v1 of #316, superseded by design, but its
  14 commits are not in `main`.
- `origin/astra/run-integrity-combined-check-20260929` — combines #288/#290, unpublished.
- `sbmax/full-completion` — the **only** copy of the content recoverable at `4a56d179`.
- All 14 branches checked out in a live worktree.

---

## 5. Issues — no closures

All 7 open issues are `OPEN_VALID`. None was closeable.

| # | Why it stays open |
|---|---|
| #348 | Fix is in open PR #349 ("Fixes #348"). Do not close until #349 lands |
| #295 | Production-reachable `chooseMulligan` default — an `AGENTS.md` §2 boundary violation. Remediation is PR #300, currently failing CI |
| #335, #334, #328, #327 | Genuine open `RULES_CORE_DEFECT` reports against the XMage pin. Fixes exist only on unpushed fork branches |
| #255 | Canonical Coordinator provider-adjudication tracker. `ARCHITECTURE_FREEZE = NOT CLAIMED` |
| #192 | Resolution in flight via PR #301. Close as accepted-with-note **only after** #301 lands |

### 5.1 Flagged for Coordinator, not acted on

- **APNAP defect-class numbering collision.** #330 ("each opponent not in APNAP order") and
  #317 ("simultaneous choices need APNAP") were closed on 2026-09-29, yet the *same defect
  class* remains open as #328 and #335, created the same day. The `F-2x` numbering is also
  reused across Lab-bridge and XMage-core defects. No body evidence shows #330/#317 were
  closed *incorrectly*, only that the numbering collides. **No reopen proposed**; this needs
  Coordinator adjudication.
- **Engine-pin divergence (evidence-integrity concern).** CI builds XMage at `f79e4168…`
  (`xmage-real-4p-smoke.yml`, `external-engine-integration.yml`), while issues #327/#328/#334/#335
  all report defects at `b1959698…`. **The reported defects may not reproduce against the engine
  CI actually builds.** Reported, not acted on.

---

## 6. Workflows

### 6.1 Registry clutter — 277 stale registrations, `NO_ACTION`

- **270** registered workflows have **no path** (their YAML was deleted from `main`; GitHub
  retains the registration because of run history).
- **7** carry a path whose file is **not on `main`**: `_temporary-fix-cohort-forwarding.yml`,
  `apply-post117-fixes.yml`, `j-mvp-r-cleanup.yml`, `jp6-release-truth-fix.yml`,
  `rogshai-12opp-block2-repair.yml`, `runtime-portability-patch.yml`,
  `semantic-projection-repair-temp.yml` (last runs 2026-08-07 → 2026-08-25; 4 ended `failure`).

All inert. De-registering is cosmetic and removes **zero** gate function, since the files are
already absent. Not performed.

### 6.2 The 18 real workflows

Canonical gates: `ci.yml` (`quality`, `security`), `production-qualification.yml`
(`infrastructure`), `xmage-real-4p-smoke.yml`, `xmage-full-game-conformance.yml`,
`external-engine-integration.yml`, `windows-runtime.yml`, `h4-docker-materialization.yml`,
`core-workflow-acceptance.yml`, `candidate-lossless-handoff.yml`, `meta-qualification.yml`,
`exact-main-recovery.yml`, `release-artifacts.yml`, `candidate-paired-triage.yml`,
`model-resolution-measurement.yml`, `optimizer-v2-acceptance.yml`.

Recorded observations, **no gate weakened or removed**:

- `optimizer-v2-benchmark.yml` is `workflow_dispatch`-only; last run 2026-08-16, 56 of 63 runs
  cancelled. It protects nothing automatically. **Keep** — it is a tool, not a gate.
- `opencode.yml` is condition-false on every recent event (629 of 631 runs skipped).
- 10 of 18 are `paths:`-filtered on `pull_request`, and 5 lack a `push:main` trigger. A `src/`
  change that misses those paths runs CI but skips the engine-integrity gates.
- No workflow runs `scripts/run_current_boundary_qualification.py` +
  `scripts/assemble_current_boundary_evidence.py` (self-declared in PR #316), so the
  current-boundary qualification path is unexecuted by CI on any branch.
- Ruleset `23547579` requires only **3** check contexts while 10 real gates emit advisory
  checks; `required_approving_review_count: 0`; `strict_required_status_checks_policy: false`.
  **Strengthening is a Coordinator/CoT decision. Reported only.**

---

## 7. Artifacts — 15,124 / 112 GB / 0 expired

| Lane | Artifacts | Size | Class |
|---|---:|---:|---|
| External XMage Integration | 1,692 | 101,084 MB | re-derivable, advisory, but cited |
| Release Artifacts | 354 | 9,486 MB | re-derivable |
| CI / Exact Main Recovery / others still in `main` | ~8,174 | ~3,660 MB | re-derivable |
| **Deleted-workflow lanes (~4,900)** | ~4,900 | **~450 MB** | **stale historical — and much of it is cited evidence** |

**The trap:** the *small* 450 MB is exactly the population cited as immutable evidence by open
PR bodies, by **artifact ID and SHA-256** — e.g. #135 (`9718602687` / `89511fbf…`), #149
(`9828355438` / `eb983fc2…`), #158 (`9994178470` / `1d9a13f7…`), #159 (`10054440299` /
`280f87b8…`). Bulk-expiring would destroy the only retrievable copy of cited evidence.

`EXPIRE_ARTIFACTS_SAFE`, narrow (~50 MB): `optimizer-v2-benchmark` (63 / 2.0 MB), the
one-shot `Pre-Run Exact Main Freeze*` runs (14 / 37.6 MB), and the `D Ruff*` / `E Reproduce*` /
`Temp Ruff Format Probe` lanes. **Not executed** — the byte saving is trivial and the operator
call is theirs.

Note: `production-qualification.yml` sets `retention-days: 90`; no other workflow sets
retention. Changing that is a **retention policy** decision, not a hygiene cleanup.

---

## 8. Tags / releases / milestones

`git tag -l` = 0, `gh release list` = 0, milestones = `[]`. No obsolete or misleading
published refs exist, and nothing was created.

The only misleading *reference* is PR #285's citation of a non-existent tag (§3).

---

## 9. Summary of GitHub actions taken

| Action | Count | Reversible |
|---|---:|---|
| PRs closed with provenance comment | **14** | yes (reopen) |
| Branches deleted | **0** | — |
| Artifacts expired | **0** | — |
| Issues closed | **0** | — |
| Workflow registrations removed | **0** | — |
| Warning comments posted (PR #285) | 1 | n/a |

**Nothing destructive was performed on GitHub.** Every closed PR is still fully citable; each
branch still exists; every artifact and every historical result is intact.
