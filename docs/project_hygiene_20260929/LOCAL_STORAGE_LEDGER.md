# Local Storage Ledger

Project-local storage, worktree, and cache inventory with cleanup advice.

**Nothing in this document was executed.** Every deletion command below is a
*recommendation* requiring operator action. Project policy denies `rm -rf`,
`git worktree remove`, and `git branch -d/-D`, and reproducing their effect by any other
mechanism is forbidden. An `rm -rf` issued as part of an audit command chain was correctly
denied by policy during this campaign and was not retried in another form.

Scope: `/home/moeen/code/`, `/tmp/opencode/`, and `/tmp/*commander*` / `*foundry*` / `*claude*`.
No unrelated personal directories were scanned. No secret material was read; a directory
containing `.env.example` was classified by name and size only.

---

## 1. Headline

| Metric | Value |
|---|---|
| `/home/moeen` total | ~193 GB |
| `/home/moeen/code` total | **~104 GB** (284 top-level entries) |
| Registered worktrees of this repo | **197** (193 under `/home/moeen/code`, 4 under `/tmp`) |
| Combined size of those worktrees | **~42.0 GB** |
| This repository's `.git` | **273 MB** — healthy, not a problem |
| `/tmp` (tmpfs) | **7.9 GB total, 7.3 GB used, 603 MB free → 93% FULL** |

**The single most important fact in this ledger:** the Git object store is small and healthy.
Storage pressure comes from *duplicated worktrees and build output*, not from history. Git
`gc`/`prune` would reclaim essentially nothing and risks recoverable work.

### Git object health (read-only measurement)

```
count: 2433        size: 109.86 MiB   (loose)
in-pack: 47021     packs: 24          size-pack: 74.77 MiB
prune-packable: 243        garbage: 0        size-garbage: 0 bytes
```

- `git worktree prune --dry-run --verbose` → **empty** (0 prunable).
- Orphan worktree metadata (`.git/worktrees/*/gitdir` pointing at a missing directory) → **0**.
- 0 tags, 0 releases, 0 milestones.
- `.git/worktrees/` metadata alone is **83 MB** — larger than every pack combined, and pure
  administrative overhead from 197 worktrees.

**Recommendation: no Git maintenance is needed and none is advised.** `git gc`/`prune` would
reclaim a rounding error and carries real risk to recoverable unmerged work. The lever that
actually matters is reducing worktree count.

---

## 2. Local cleanup safety classes

| Class | Meaning |
|---|---|
| `SAFE_EPHEMERAL` | Provably regenerable, no unique state, no evidence dependency |
| `SAFE_AFTER_ARCHIVE` | Potentially useful diagnostic/provenance content; preserve compactly first |
| `KEEP_UNIQUE` | Unique commits, patches, evidence, or dirty changes |
| `KEEP_ACTIVE` | Current worktree, active branch, or currently consumed cache |
| `USER_ACTION_REQUIRED` | Desirable but policy forbids the agent performing it |
| `UNKNOWN` | Insufficient proof — **never delete** |

---

## 3. Ranked opportunities

Ranked by (reclaimable bytes ÷ risk).

### 3.1 Build and cache output — ~29.8 GB — `SAFE_EPHEMERAL` → `USER_ACTION_REQUIRED`

| Category | Count | Total | Gitignored |
|---|---:|---:|---|
| `target/` (Maven/Java) | 603 dirs | **~19,537 MB** | `engine-bridge/target/` yes; top-level `target/` **no** |
| `node_modules/` | 113 dirs | **~7,086 MB** | **no** |
| `__pycache__/` | 1040 dirs | ~1,178 MB | yes |
| `.mypy_cache/` + `.pytest_cache/` + `.ruff_cache/` | 264 dirs | ~877 MB | yes |
| `build/`, `dist/` | 201 dirs | ~205 MB | yes |
| `.runtime/` | — | ~950 MB | yes |

Largest single item: `ws-csn-job11-pinned-xmage-backend-live-20260917/.runtime` (950 MB).
Largest `target/`: several at 403–444 MB (`engine-bridge/target` in ws229, ws84, ws213,
ws-ci-cardinality-lane, ws60, ws218, ws203).

- **Why safe:** 100% regenerable by `mvn package` / `npm ci` / re-running pytest. Mostly
  explicitly gitignored.
- **What is lost:** compiled `xmage-engine-bridge-0.1.0-SNAPSHOT.jar` (~74 MB each, ~30 copies)
  and incremental-analysis caches. First rebuild cost is real but bounded.
- **Prerequisite:** none. Optionally run `mvn -o verify` once first to confirm a clean offline
  rebuild is possible, since these trees are what make offline builds work.
- **Recommended action:** targeted removal of the largest offenders first; see §4.

### 3.2 H2 card databases — ~7.0 GB — `SAFE_EPHEMERAL` → `USER_ACTION_REQUIRED`

25 `*/db/cards.h2.mv.db` files of 51–513 MB. Untracked. `db/` is **not** covered by
`.gitignore` (only `*.db-wal`/`*.db-shm`/`*.sqlite3` are), which is itself a hygiene gap.

- **What is lost:** the card database, which must be re-imported from the pinned engine. This
  is the **slowest** regeneration of any candidate.
- **Recommendation:** do **not** bulk-delete. These make engine runtime work. Remove only
  duplicates in abandoned worktrees, and only after the owning workstream is confirmed finished.

### 3.3 Worktrees — 197 registered, ~42.0 GB

| Bucket | Count | Size |
|---|---:|---:|
| Fully merged into `origin/main`, clean | 50 | ~10,241 MB |
| Not merged (1–501 commits ahead) | 130 | ~31,354 MB |
| Detached | 17 | ~1,387 MB |
| Dirty (any uncommitted change) | **12** | — |

**14 worktrees are proven safe to remove** — HEAD is an ancestor of `origin/main`,
`git status --porcelain` is empty, and mtime ≤ 2026-09-16. Total ~1,432 MB:

| Path | Size | HEAD |
|---|---:|---|
| `~/code/commander-exec-consolidation` | 96 MB | `454f114a` |
| `~/code/coord-legacy-recovery-preflight-aebcfda3` | 97 MB | `aebcfda3` |
| `~/code/opencode-muse-cross-repo-hardening-v2` | 97 MB | `ec680245` |
| `~/code/ws-a1d-docker-pin-requalification` | 106 MB | `ec4e4a07` |
| `~/code/ws-a1d-h4-docker-materialization` | 97 MB | `9ee55eb4` |
| `~/code/ws-a1r-authority-retention` | 34 MB | `448d9a41` |
| `~/code/ws238-hosts-of-mordor-ci-baseline` | 179 MB | `b2d31db3` |
| `~/code/ws239-source-lock-primary-identity` | 105 MB | `f30d4c43` |
| `~/code/ws240-source-lock-multivalue-identity` | 99 MB | `f19084ef` |
| `~/code/ws58-foundry-state-persistence-hardening` | 97 MB | `97f14a5f` |
| `~/code/ws61-foundry-safe-push-lineage-integration` | 97 MB | `2829b2bc` |
| `~/code/ws75-foundry-opencode-tooling-hardening` | 131 MB | `b158ce56` |
| `~/code/ws90-rqc3-corrected-first-wave-reissue` | 98 MB | `6402dc7b` |
| `~/code/ws91-d1-current-main-integration` | 99 MB | `2cca0773` |

- **What is preserved:** the branches remain in `refs/heads` and the commits remain in the
  shared object store. Only the working directories go.
- **Prerequisite:** confirm no `.foundry/` state file inside one of these is the *sole* copy of
  a workstream's durable state. Check with
  `git -C <path> status --porcelain --ignored | grep foundry` before removing.
- **Caveat:** these branches are also named in `docs/foundry-execution/README.md`-adjacent
  donor records. Directory removal does not touch them, but re-create a worktree later if a
  packet needs local inspection.

**130 worktrees are NOT proven stale** and must not be removed. Highest ahead-counts:
`ws74` (501), `ws77` (497), `ws73` (494), `ws71` (493), `ws72` (492), `ws68` (491), `ws66`
(491), `ws65` (488), `commander-playtest-lab-muse-ws48` (488), `ws50` (449, **51 dirty
files**), `commander-ws48` (445), `commander-general-n-d1` (444), `ws49-canonical` (396).

### 3.4 The 12 dirty worktrees — `KEEP_UNIQUE`

| Path | Dirty | Note |
|---|---:|---|
| `ws50-forge-decision-sequence-slice` | 51 | 449 commits ahead — **highest unique-work risk** |
| `lab-284-ruff-donor-20260929` | 4 | detached, modified regression scripts |
| `ws-l6-rg05` | 2 | |
| `ws49-canonical` / `ws208-xmage-offer-determinism` / `ws-real-deck-e2e-gate-20260923` / `ws-physical-pool-20260919` / `ws-arclose-d1-p1p2` | 1 each | |
| `commander-ws48` / `commander-playtest-lab-muse-ws49` / `commander-playtest-lab-muse-ws48` | 1 each | 383–488 commits ahead |

Untracked-only contents worth noting: `commander-playtest-lab-muse-ws49/vendor/` is a
**682 MB** outlier (every other worktree's `vendor/` is ~1 MB) — classified `UNKNOWN`,
inspect before any action. `ws-real-deck-e2e-gate-20260923/db/` and
`ws208-xmage-offer-determinism/db/` are untracked H2 databases.

### 3.5 `/tmp` — 93% full — operational risk

`/tmp` is a **tmpfs with 603 MB free**. Four registered worktrees live under it, so a tmpfs
clear would leave dangling worktree metadata.

| Size | Path | Class |
|---:|---|---|
| 1,917 MB | `/tmp/foundry-launch-final-completion-space-bunny-max/` | `SAFE_AFTER_ARCHIVE` — not a git repo; archive its `*.log` files first |
| 1,419 MB | `/tmp/foundry-launch-final-completion-muse-xhigh/` | `SAFE_AFTER_ARCHIVE` — same |
| 989 MB | `/tmp/claude-1000/` | contains a **registered** worktree; use `git worktree remove`, not `rm` |
| 633 MB | `/tmp/opencode/forge-pr4/` | `UNKNOWN` — a forge checkout on an **unpushed-looking** branch; cannot prove pushed |
| 329 MB | `/tmp/pytest-of-moeen/` | `KEEP_ACTIVE` — in use by a live pytest process |
| 267+256+78+3 MB | `/tmp/astra-integrity-20260928-venv/`, `/tmp/opencode/cpl-venv/`, `/tmp/opencode/mypyenv/`, `/tmp/mypy-base-2869915/` | `SAFE_EPHEMERAL` — virtualenvs |
| 84+60+45 MB | `/tmp/opencode/baseline-dafe2ac6`, `salvage-baseline-check`, `final-audit` | **registered worktrees** — use `git worktree remove`; `final-audit` is 8 commits ahead |
| 7 MB | `/tmp/opencode/preserved-artifacts/` | `KEEP_UNIQUE` — the name asserts preservation intent |
| 16 KB | `/tmp/opencode/uncommitted.patch` | `KEEP_UNIQUE` — may be the only copy of uncommitted work |

Freeing the two launcher sandboxes plus the venvs would recover **~3.9 GB**, taking `/tmp`
from 93% to comfortably under pressure.

### 3.6 Other repos — `USER_ACTION_REQUIRED` / `KEEP_UNIQUE`

`forge` and `mage` are read-only for this campaign. Measurements only:

- `~/code/forge/.git` — 1,400 MB, dominated by a single 1,032 MB pack. All history is on
  origin; ~46 linked worktrees exist.
- `~/code/mage-ws33/.git` — 1,200 MB, single 986 MB pack, **1 uncommitted change**.
- **4 byte-identical 231 MB forge packs** across `pb09-forge-bridge-{current,pin}`,
  `pb09-forge-upstream-pristine`, `forge-candidate-h4f` (~924 MB redundant). Two of these have
  **no origin remote**, and `pb09-forge-bridge-current-20260929` has **276 dirty files**.
  → `KEEP_UNIQUE` / `UNKNOWN`. Do not act without owner confirmation.

### 3.7 Shared caches — deliberately not recommended

`~/.m2` 806 MB, `~/.gradle` 1.5 GB, `~/.npm` 1.8 GB, `~/.cache` 4.8 GB (~8.9 GB total).

Purging these would reclaim space but force expensive cold rebuilds, and they are shared
across all projects on the machine, not project-exclusive. **Not recommended.** The campaign
brief explicitly warns against purging shared caches merely because they are large.

---

## 4. Recommended commands (operator action required)

Ordered by benefit ÷ risk. **Verify each precondition before running.** These were **not**
executed by the agent.

### Step 1 — relieve `/tmp` pressure first (lowest risk, urgent)

```bash
# ~3.9 GB. Archive the logs first if the 2026-09-28/29 run evidence matters.
mkdir -p ~/archive/foundry-launch-20260928-logs
cp /tmp/foundry-launch-final-completion-space-bunny-max/*.log \
   /tmp/foundry-launch-final-completion-muse-xhigh/*.log \
   ~/archive/foundry-launch-20260928-logs/ 2>/dev/null
# then, at the operator's discretion:
rm -rf /tmp/foundry-launch-final-completion-space-bunny-max
rm -rf /tmp/foundry-launch-final-completion-muse-xhigh
rm -rf /tmp/astra-integrity-20260928-venv /tmp/opencode/cpl-venv /tmp/opencode/mypyenv
```

Rollback: none needed — all regenerable; the copied logs are the only non-regenerable part and
are archived first.

### Step 2 — remove the 14 proven-merged worktrees (~1,432 MB)

```bash
# Precondition per path: confirm no sole-copy .foundry state inside.
for w in commander-exec-consolidation coord-legacy-recovery-preflight-aebcfda3 \
         opencode-muse-cross-repo-hardening-v2 ws-a1d-docker-pin-requalification \
         ws-a1d-h4-docker-materialization ws-a1r-authority-retention \
         ws238-hosts-of-mordor-ci-baseline ws239-source-lock-primary-identity \
         ws240-source-lock-multivalue-identity ws58-foundry-state-persistence-hardening \
         ws61-foundry-safe-push-lineage-integration ws75-foundry-opencode-tooling-hardening \
         ws90-rqc3-corrected-first-wave-reissue ws91-d1-current-main-integration; do
  git -C ~/code/commander-playtest-lab worktree remove "~/code/$w"
done
```

Preservation: branches and commits are untouched. To restore, `git worktree add ~/code/$w <branch>`.
Do **not** use `--force`; a refusal means the tree is not actually clean, which is itself a
finding.

### Step 3 — build output, largest first (~29.8 GB)

```bash
# Start with the biggest, lowest-risk, non-worktree caches.
find ~/code -maxdepth 4 -type d -name '__pycache__'  -prune -exec rm -rf {} +   # ~1.2 GB
find ~/code -maxdepth 4 -type d -name '.mypy_cache'  -prune -exec rm -rf {} +   # ~628 MB
find ~/code -maxdepth 4 -type d -name '.pytest_cache' -prune -exec rm -rf {} +   # ~125 MB
find ~/code -maxdepth 4 -type d -name '.ruff_cache'   -prune -exec rm -rf {} +   # ~124 MB
rm -rf ~/code/ws-csn-job11-pinned-xmage-backend-live-20260917/.runtime           # 950 MB
```

Then, per abandoned worktree only, `engine-bridge/target` (~19.5 GB) and `node_modules`
(~7.1 GB). **Do not run these across `~/code` blindly** — several of the largest `target/`
trees belong to worktrees with unmerged commits that may still be in use. Confirm the
workstream is finished first.

### 4.1 `.gitignore` gaps found (tracked-file hygiene, not storage)

Not remediated by this campaign because each is a judgment call about intended behaviour, but
recorded: top-level `target/`, `node_modules/`, `db/`, `vendor/`, and `artifacts/` are **not**
ignored. No such path is currently committed, so there is no active leak — it is a latent risk.

Also: `data/runs/current/OFFICIAL_ROGSHAI_RUN_CURRENT.json` is a **tracked file matched by
`.gitignore` rule `data/runs/*` with no negation**. Harmless today (gitignore does not affect
tracked files) but inconsistent.

---

## 5. Summary

| Strategy | Reclaimable | Risk |
|---|---:|---|
| S1 — `/tmp` relief + python caches + one `.runtime` | ~3.2 GB | Very low |
| S2 — S1 + 14 proven-merged worktrees | ~4.6 GB | Very low |
| S3 — S2 + build output in confirmed-abandoned worktrees | up to ~44 GB | Low, needs per-tree confirmation |
| S4 — S3 + `/home/moeen/code/csn-final-bakeoff` after archiving 2 handoff `.md` files | up to ~57 GB | Low |
| S5 — S4 + forge/mage pack dedup | up to ~66 GB | **High** — cross-repo, unconfirmed ownership, 276 dirty files in one clone |

Immediate non-cleanup risk: **`/tmp` at 93% full (603 MB free)** with an active pytest
writing to it.
