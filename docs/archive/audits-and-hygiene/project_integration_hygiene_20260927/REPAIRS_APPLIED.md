# WSR23 — Repairs Applied

Scope: free, non-overlapping Lab integration/hygiene surfaces only. Every change below is
documentation/integration consistency. **No Rules semantics, no qualification semantics, no
provider/freeze status, and no active worker's surface was touched.**

## R1 — `docs/foundry-execution/GOVERNANCE_SUPERSESSION.md`

**Observed fact.** This file lives on current `main` and presents itself as live governance
authority. Two defects:

1. **Stale authority pointer.** Its preamble declared
   `project/opencode-execution-system-consolidation-20260910` (based on
   `origin/main@b3f5a992…`) to be "the single successor governance line".
2. **Wrong cross-reference.** The PR #166 entry routed its privacy concepts to
   "`AGENTS.md` §11 and `opencode.json` permissions". In current `AGENTS.md`, §11 is
   *Git, worktree, ownership*; privacy is **§12**, and the `opencode.json` key is singular
   `permission` (the plural `permissions` array is precisely the schema-invalid form this very
   document flags in the PR #161 entry).

**First failing boundary.** `AGENTS.md §11` heading is "Git, worktree, ownership" and contains
no privacy content; the routed concepts do not exist at the cited location.

**Leading hypothesis.** The file was written when the consolidation branch really was the
successor line and when privacy was §11; both facts later changed on `main`, and the file was
never re-verified.

**Competing hypothesis considered and rejected.** The §11 reference might be intentional
because a *different* `AGENTS.md` numbering is canonical. Rejected: the same file's §161 entry
and the whole of current `main` use the current numbering, and PR #257 (merged) edited §6/§7
under it.

**Search for contradictory evidence.** None found. `AGENTS.md` §12 Privacy carries exactly the
LOCAL_ONLY-secret, project-relevance and session-sharing rules the entry claims were
"already incorporated"; `opencode.json` has a singular `permission` object.

**Additional measured evidence.** `project/opencode-execution-system-consolidation-20260910` is
0 commits ahead of and 420 commits behind `origin/main`. The live governance line is `main`
plus open PR #261 (`ops/dual-executor-governance-hardening-20260927`, head `0699a5f2`), which
owns `AGENTS.md`, `.opencode/agents/*`, `docs/foundry-execution/README.md` and
`docs/foundry-execution/ROUTING_AND_EFFORT.md`.

**Repair.** Added a dated, explicitly-scoped currency note that (a) records the consolidation
branch as the historical author rather than the current successor, (b) names the actual live
governance line, (c) states that the three dispositions were re-verified and still hold, and
(d) points at the per-PR evidence in this packet. Corrected the §11 → §12 cross-reference and
`permissions` → `permission`.

**Deliberately NOT changed:** the three disposition recommendations themselves. They are the
historical Coordinator record; rewriting them would destroy the evidence that made the closures
provable.

**Non-overlap proof.** `docs/foundry-execution/GOVERNANCE_SUPERSESSION.md` is not in the diff
of PR #260, #261, #262, PR #259, or the WSR22 branch. `#261` edits the sibling files
`README.md` and `ROUTING_AND_EFFORT.md` in the same directory, which WSR23 did not touch.

## Classes investigated and deliberately left unchanged

### D1 — Dead current links / scripts pointing at removed paths: **no defect found, no change**

315 tracked markdown files on `origin/main` were scanned. **0 broken relative markdown links.**
48 backticked repository paths do not resolve, and every one was triaged:

| Hit | Verdict |
|---|---|
| `EXECUTION_PROVIDER_OVERRIDE.md:38` `providers/opencode-go/models/space-bunny-free.toml` | Not a repo path. A models.dev *catalog* identity, correctly quoted. |
| `GOVERNANCE_SUPERSESSION.md:34` `docs/operations/AI_EXECUTION_AND_PRIVACY_POLICY.md` | A deliberately quoted *nonexistent* file, cited as PR #166's defect. |
| `.foundry/WORKSTREAM_STATE.yaml` (13 refs) | Historical provenance records naming their own original worktree path. `AGENTS.md` explicitly states there is no implicit repository-root state. |
| 43 further hits in `qualification/*/SOURCE_LOCK.md`, `research/**` | Same class: workstream-local provenance, not live routing. |

A second scan of 612 workflow/script files produced 143 hits; all are runtime **output** paths
(`artifacts/…`) created by the workflow, not stale input references.

**Rejected option, with reason.** A repository link checker was considered and **rejected under
the reuse-first gate**: it would add a permanent maintenance surface to guard a defect class
with zero live instances. A narrower guard asserting that every `AGENTS.md §N` reference
resolves was also rejected — it would convert open PR #261's legitimate in-flight `AGENTS.md`
edits into a new CI failure on an active surface, which §14 forbids.

### D2 — CI/build repair: **main is healthy, no change**

Fresh `main` runs (all six workflows) are `success` at `613cd57b` and `60fc3c8a`. Locally, on a
lock-faithful venv, the full suite, ruff, and mypy strict are all green — see `CI_VALIDATION.md`.
No first failing boundary exists, so there is no root cause to repair. Fabricating one would be
worse than reporting none.

### D3 — Inconsistent model/executor descriptions: **out of scope**

`AGENTS.md` §6/§7, `opencode.json`, and `EXECUTION_PROVIDER_OVERRIDE.md` all currently agree
(Muse default; `space-bunny` operator-selected at native `max`; only `high`/`xhigh` project
efforts). The remaining tension — `opencode.json` provider `whitelist` lists only
`muse-spark-1.3-contributor` — is exactly the dual-executor question **PR #261 owns**. WSR23
recorded it and did not touch it.

### D4 — Test collection errors: **environment, not repository**

Under the ambient interpreter, `pytest tests` failed collection with `No module named 'typer'`,
`starlette.testclient requires httpx2`, and `'asyncio' not found in markers`. All three are
declared dependencies (`typer>=0.15,<1` core; `httpx2>=2.7,<3` and `pytest-asyncio>=1.4,<2`
in the `dev` extra) and all three are present in `requirements/lock.txt`. The first failing
boundary is the interpreter, not the repo. Fix: validate inside a lock-faithful venv. No repo
change; the CI workflow already does exactly this.

## Engine defects discovered and deliberately NOT fixed (§25)

Recorded in `REMAINING_BLOCKERS.md` B1–B3 with exact evidence. These belong to the WSR22/Mage
lane or to Forge/XMage Rules ownership, not to WSR23.
