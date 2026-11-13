# Branch Forensics — Content Duplication Across 347 Remote Branches

Read-only evidence product. **No branch was deleted, modified, or pushed. Nothing here is a
deletion instruction** — branch deletion is denied by project policy and is in any case a
human decision.

Measured at `origin/main` = `7055740ec2f08d4864bf7e200f7b48ace521fe57`.
**Coverage: 347 of 347 topic branches examined (100%). 186,861 of 186,861 file-change entries
compared (100%). 638 of 638 ancestor pairs checked (100%). Nothing skipped; nothing
UNVERIFIED.**

---

## 1. The question, and why "has unmerged commits" is the wrong test

A prior audit classified 236 branches as "unique work, never delete" purely because
`git rev-list --count origin/main..<branch>` was non-zero. That is **not** sufficient.
"Has commits not in main" does not imply "has content not in main" — a branch can carry
unmerged commits whose entire net content already reached `main` by another path, or already
reached a sibling branch.

The correct discriminator is a **three-dot diff** (which compares against the merge base) plus
a **blob-identity check** against `main`:

| Test | Command | Meaning |
|---|---|---|
| Net content | `git diff --shortstat origin/main...<b>` | empty ⇒ the branch contributes nothing net |
| Content identity | `git diff --raw --no-abbrev origin/main...<b>` blob SHAs vs. `git ls-tree -r origin/main` | every changed blob already in main ⇒ content-duplicate |
| Containment | `git merge-base --is-ancestor <a> <b>` | a strict ancestor's content is carried by its descendant |

Methodological notes, because two bugs materially changed the result and are recorded rather
than hidden: `git diff --raw` **abbreviates** blob SHAs to 7 characters, which made a first
join report "186,861/186,861 unique" — all wrong; and `git rev-list` includes the tip itself,
which produced 233 phantom self-ancestor pairs. All numbers below are post-correction, and the
parser was re-validated on sampled rows.

---

## 2. Results

| Class | Branches |
|---|---:|
| `CONTENT_DEAD_EMPTY_DIFF` — empty 3-dot diff **and** zero unmerged commits | **107** |
| `CONTENT_DUPLICATE` — non-empty diff, but **every** changed file already byte-identical in `main` | **3** |
| `PARTIAL_DUPLICATE` — some files already in `main`, some new | **48** |
| `PARTIAL_DUPLICATE` + contained by a sibling | 7 |
| `UNIQUE_CONTENT` — all changed files differ from `main` | **146** |
| `UNIQUE_CONTENT` + contained by a sibling | 36 |
| **Total** | **347** |

Reconciliation: 107 fully merged + 240 with unmerged commits = 347. The prior audit's "107
fully merged" matches exactly; its "236" is now 240 through branch drift.

Aggregate: 240 branches carry 19,578 unmerged commits; their 3-dot diffs span 186,861
file-change entries across 16,635 distinct paths, against 2,203 paths in `main`. Of those
entries, **186,229 are unique and only 632 already exist in `main` — 0.34%**.

---

## 3. The three genuine content-duplicates

Every file each one changes is already byte-identical in `main`, verified individually with
`git rev-parse`:

| Branch | Tip | Unmerged commits | Files | Unique vs `main` |
|---|---|---:|---:|---:|
| `origin/roadmap/j-p3d-provider-decision` | `fdae6ea62a5a` | 1 | 4 | **0** |
| `origin/cleanup/operational-own-pool-scope-20260820` | `61179e37c246` | 3 | 4 | **0** |
| `origin/roadmap/j-p3a-external-engine-contract` | `07f3dfba9ac4` | 9 | 5 | **0** |

13 files total, all under `data/collections/current/` and `docs/` (J_P3 provider-matrix and
closeout documents).

**A caveat that must not be dropped:** their *two-dot* diffs against current `main` are enormous
(`roadmap/j-p3a`: 1,386 files, +11,981/−407,103) because `main` has since pruned ~400k lines
of evidence — **not** because these branches carry unique work. A naive whole-tree comparison
would wrongly flag them as massive. The three-dot plus blob test is the correct discriminator.

---

## 4. Sibling containment is widespread — but it is **not** content duplication

This was the audit's main hypothesis and the data **refutes it as a deletion argument**:

- 638 real ancestor→descendant pairs exist among the 240 unmerged branches.
- **106 branches (44%) are a strict ancestor of at least one sibling**; 73 are contained by a
  sibling; for 43, a descendant's tree still holds 100% of the ancestor's net contribution.
- The dominant pattern is a long sequential lineage
  (`ws17`→`ws18`→…→`ws74`→`ws207`→`ws222`→`ws230`; `rogshai`→`frontier-factorial`;
  `forge-successor`→`v1.0.5-freeze`) where each workstream forked from the previous.

**But for nearly all of these the content is absent from `main` entirely** — e.g. three blob
paths in the worked example exist in no `main` path at all. So they are real unrecovered work
that happens to be superseded by later branches. **Containment here is by lineage, not by
`main`, and deleting these would destroy the only remote copy of intermediate state.**

### 4.1 The prior hypothesis, confirmed in one case and bounded

PR #304's head `08d23aa44c72` (7 unmerged commits, 23 changed files, **0** already in `main`,
23 unique) is a strict ancestor of PR #333's head `20b52958b4` and of
`origin/donor/pb03-304-terminal-hardening-20260929`. That is exactly the pattern the previous
campaign used to justify closing #304 as superseded by #333 — and it generalises to 106
branches, **none of which is thereby a deletion candidate.**

---

## 5. Strongest partial-duplicate cases

Near-misses on `CONTENT_DUPLICATE`; each still retains 1–4 genuinely new blobs.

| Branch | Tip | Commits | Files | Already in `main` | Unique |
|---|---|---:|---:|---:|---:|
| `origin/add-hosts-of-mordor-opponent` | `b2f842f1455e` | 8 | 8 | 7 (87.5%) | 1 |
| `origin/roadmap/j-p4-pilot-quality` | `96439118e796` | 17 | 22 | 18 (81.8%) | 4 |
| `origin/ws80/xmage-callback-reachability-20260912` | `4adc4591bfb6` | 4 | 12 | 9 (71.4%) | 3 |
| `origin/roadmap/j-p3c-forge-real-spike` | `22e7889c8cc1` | 8 | 7 | 5 (71.4%) | 2 |
| `origin/roadmap/j-p3b-xmage-real-spike` | `da8b7b7e48ce` | 12 | 7 | 5 (71.4%) | 2 |

---

## 6. No tooling artifact

**Zero** branches are an ancestor of `origin/main` while also counted as unmerged — this is
arithmetically impossible, since `origin/main..B` is empty by definition when `B` is an
ancestor. All 107 empty-diff refs are confirmed ancestors of `main` via
`git merge-base --is-ancestor`. The prior audit's 107/236 split was sound.

---

## 7. Conclusion, stated against my own prior recommendation

The previous hygiene campaign recommended deleting **nothing** and classified everything with
unmerged commits as unique. This audit, examining **all 347** branches with the correct
three-dot and blob test, **confirms that recommendation with evidence instead of caution**:

- Only **3** branches are true content-duplicates of `main`, carrying **13 files** in total.
- **146** branches have genuinely unique content, plus 55 partial.
- The remaining large group of "superseded by a sibling" branches is **not** deletable, because
  the content is not in `main`.

So the expected value of further branch-forensic work is **low**. The 25 misleading branch
names flagged in the previous campaign (`noop`, `tmp-do-not-use`,
`engine/xmage-full-game-external-pilots-{unused,stop,safety,final,final2,do-not-use,work}`, …)
are a **naming** problem, not a content problem — renaming is history rewriting and is out of
bounds; the ledger in `docs/project_hygiene_20260929/GITHUB_RETIREMENT_LEDGER.md` §4.1 remains the
authoritative list.

**If a human wants to act on anything from this package, the three branches in §3 are the only
ones with a content-based argument, and even they are a judgement call rather than an
instruction.**
