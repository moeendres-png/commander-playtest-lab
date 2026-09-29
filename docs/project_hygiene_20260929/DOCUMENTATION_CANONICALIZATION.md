# Documentation Canonicalization

Per-file record of what was reviewed, what was wrong, what authority established the correct
fact, what the new wording is, and why it is better. Files that were reviewed and
**deliberately left unchanged** are recorded too, with the reason — an audit that only lists
its edits hides half the result.

Scope note: `AGENTS.md`, `opencode.json`, `.foundry/executor-profiles.json`,
`.github/workflows/opencode.yml`, `.opencode/agents/*`, and four canonical routing documents
were **owned by an active workstream** at campaign start and were not edited. That ownership
was released mid-campaign (PR #350 merged); the routing result was audited, and one
*downstream* index that the migration had left stale was corrected. See §4.

---

## 1. Remediations applied

### R1 — `docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md`

**Defect.** The file opened with `POLICY = ACTIVE` and
`EXECUTION_SYSTEM_INTEGRATION = PENDING_PR172_MERGE`, and its "Current integration state"
section said *"not canonical on `main` until PR #172 merges"*. PR #172 merged 2026-09-10 —
the document has been on `main` ever since, which is by its own text impossible. Its body also
prescribed `### Muse HIGH — Default execution tier for bounded engineering work`, and
`foundry-implementer — Muse HIGH, primary autonomous implementation agent`. All of this was
stale, and Muse is now an inactive executor.

**Authority.** `docs/COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md` states it *"supersedes
the routing/authority instructions in `docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md`
for new work while preserving that older file as historical provenance"*.
`gh pr view 172` → `MERGED`, `mergedAt 2026-09-10T04:42:48Z`.

**What changed.** A supersession banner at the top naming the successor and enumerating the
three known-stale statements; `POLICY = ACTIVE` → `POLICY = SUPERSEDED`;
`PENDING_PR172_MERGE` → `MERGED (PR #172)`; "records the current Coordinator authority model"
→ "as it stood on 2026-09-10"; plus an inline superseded marker at the "Current integration
state" heading.

**Why this shape.** The stale statements are **enumerated but left verbatim**, and the file is
**not deleted**. The project already owns the correct pattern in
`docs/foundry-execution/GOVERNANCE_SUPERSESSION.md:1-4`; matching it keeps the record readable
and makes the supersession impossible to miss. Rewriting the body in place would have destroyed
provenance, which §16 forbids.

**Validation.** `tests/foundry/test_foundry_tools.py:994` asserts this file is **not** in
`.foundry/repo-profiles/cpl.json` `canonical_files` — the banner is consistent with existing
policy. No test asserts `POLICY = ACTIVE`. Suite: no delta.

---

### R2 — `docs/foundry-execution/TOKEN_ECONOMY.md`

**Defect, two parts.**
1. Operator-workflow steps 3 and 4 named **Muse** as the executing agent. Muse is now inactive.
2. Line ~68 stated instruction layers include an *"`instructions` entry for
   `ROUTING_AND_EFFORT.md`"* in `opencode.json`. **That key does not exist.**

**Authority.** `python3 -c "json.load(open('opencode.json')).keys()"` →
`['$schema','agent','default_agent','enabled_providers','experimental','model','permission','provider','share','small_model','tool_output']`.
`docs/foundry-execution/ROUTING_AND_EFFORT.md:7-11` independently explains why: V2 accepts
`instructions` in its schema but does not resolve those files into model instructions.
Current executor identities: `AGENTS.md` §6–§7.

**What changed.** Steps 3–4 now say "The selected executor". The `instructions` entry was
removed from the parenthetical and replaced with a sentence stating the key does not exist,
that the CLI accepts it in schema without resolving it, and pointing at `ROUTING_AND_EFFORT.md`.

**Why executor-neutral rather than naming DeepSeek.** This campaign ran as Space Bunny MAX
under explicit operator assignment. Hardcoding a new executor name would immediately re-stale
this operator workflow the next time routing changes, and would have contradicted a canonical
document I am not allowed to edit. Neutral wording is correct under every routing state.

**Validation.** No test reads this file. `tests/unit/test_ws78_token_economy.py` locks the
capsule and `/work` behavior, not prose. Suite: no delta.

---

### R3 — `docs/foundry-execution/HIGH_XHIGH_BENCHMARK.md`

**Defect.** "Policy under test — Initial policy stands: **HIGH default, XHIGH evidence-based
escalation**." Stated as standing policy, and linked as a current surface from
`docs/foundry-execution/README.md`.

**Authority.** `AGENTS.md` §7: *"There is no active-work `high`, `medium`, `low`, `minimal`,
`none`, or `off` native lane."*

**What changed.** A superseded note stating the harness **prescribes no current policy**, that
the HIGH/XHIGH position is the 2026-09-10 state retained as provenance, and pointing at
`AGENTS.md` §7 and `EXECUTION_PROVIDER_OVERRIDE.md`. The historical paragraph is **retained**.

**Why.** The harness is a legitimate design artifact; only its *policy claim* was false. Banner,
not deletion.

**Validation.** No test reads this file. Suite: no delta.

---

### R4 — `docs/foundry-execution/GOVERNANCE_PROPAGATION.md`

**Defect.** Titled "After PR #172 Merge" and gated: *"It applies only after PR #172 merges to
`main`. Do not anticipate the merge: before merge, `main` does not carry the canonical
execution system."* PR #172 merged 2026-09-10. The file was therefore **permanently inoperative
by its own text** while `docs/foundry-execution/README.md` listed it as an active surface.

**Authority.** `gh pr view 172` → `MERGED`, 2026-09-10.

**What changed.** Title → "PR #172 Execution-System Line". The gate now states PR #172 merged
on 2026-09-10, that the procedure applies to branches that have not yet absorbed the current
`main` governance line, and — importantly — that later routing changes supersede parts of the
PR #172 line, so it must be re-verified against current `AGENTS.md` before use.

**Why the re-verify clause.** Removing the gate makes the procedure look universally current.
It is not: PR #350 has since changed routing, which supersedes part of the PR #172 line. Saying
so prevents the same staleness recurring.

**Validation.** `tests/foundry/test_foundry_tools.py:935-945` asserts four phrases in this
file (`RETAINED_EVIDENCE_IMPACT`, `only expected governance/tooling paths`, `do not rerun
qualification`, `Do not use one governance checkout…`) — none is the edited sentence. Suite: no delta.

---

### R5 — `docs/foundry-execution/README.md` (the canonical index)

**Defect.** This is the index every agent is pointed to for the Foundry execution system. After
PR #350 landed, it still described the **previous** routing: "Space Bunny MAX default; explicit
Muse XHIGH alternate", "Space Bunny MAX default, Muse XHIGH alternate, retired Zen", "Sol /
Space Bunny MAX / Muse / Astra authority model", "Primary long-running worker (Space Bunny
MAX)", "Adjudicator agent … (XHIGH)". It also listed **5 of 7** skills and **6 of 20** tools.

**Authority.** `AGENTS.md` §6–§7 and `docs/foundry-execution/ROUTING_AND_EFFORT.md` at
`72665dce` (post-merge). Filesystem: 7 skill directories, 20 modules in `tools/foundry/`.

**What changed.** Routing columns corrected to DeepSeek MAX default / Space Bunny MAX
secondary, with Muse and GLM removed from the authority-model row; adjudicator row corrected
to native `max`; skills list completed to all 7; tools row now states "20 modules" and names
the ten that matter; benchmark row marked historical; the "Post-PR172 merge" row reworded.

**Why this was in scope when the routing migration owned those files.** The migration's
four canonical files are now merged and released, and it left this index stale. That is exactly
the "audit its result" case. The index is not one of its owned paths.

**Why not "fix" the duplication instead.** The honest root cause is that executor routing is
duplicated across 7+ files with **unequal** test coverage —
`tests/foundry/test_project_integrity.py` pins four of them and not this one. Collapsing the
duplication is a structural change to a test-enforced contract; it is recorded as a finding, not
performed inside a hygiene pass.

**Validation.** The test forbids `"Muse-only by default"` and `"Primary long-running worker (HIGH)"`
in this file; neither was introduced. Suite: no delta.

---

### R6 — `docs/README.md` (new)

**Defect.** 77 markdown files sit directly in `docs/`, 294 recursively, with **no index and no
disclaimer**. The only navigational file was `docs/REPOSITORY_TRIAGE_INDEX.md`, which
explicitly disclaims general navigation. Filenames carrying `CURRENT`/`FINAL` are common
(`PROJECT_UPDATE_CURRENT_STATE.md`, `CARD_COVERAGE_CURRENT.md`,
`NEXT_STEP_HANDOFF_J_P6_TO_FINAL.md`, `qualification/final-current-boundary-20260927/`) while
`AGENTS.md` §3 says such names prove nothing — a rule stated but unimplemented anywhere.

**What it contains.** A "before anything else" governing-document table; a subdirectory map
distinguishing canonical from dated per-workstream packets; a section on the two directories
that differ only by separator; and an explicit filename-trap section quoting `AGENTS.md` §3.

**Why add a README rather than a new "MASTER" document.** The campaign brief warns against
creating yet another competing index. `docs/` had *no* index, so this fills a gap instead of
adding a competitor — and it is explicitly scoped as a navigation aid, not authority.

**Validation.** No test globs `docs/` listings. Every path named in it was verified to exist
before the file was written. Suite: no delta.

---

### R7 — `docs/decision-quality/README.md` and `docs/decision_quality/README.md` (new)

**Defect.** Two sibling directories differing only by `-` vs `_`, both non-empty, neither with
a README, neither referenced by `AGENTS.md` or the Foundry index. A newcomer cannot tell which
is canonical — and the `_` variant holds files named `..._CURRENT.md` claiming current status.

**What changed.** One README added to each, stating non-authority, listing contents with their
recorded status, and cross-referencing the other. `SIMULATION_FIDELITY_124_CLOSEOUT_CURRENT.md`'s
`PASS` is explicitly scoped as a milestone-level statement that must not be cited as a current
project PASS.

**Why neither directory was renamed or merged.** Renaming would rewrite historical provenance
paths, and `docs/foundry-execution/README.md` states *"Do not rewrite historical evidence to look
current."* Adding a disclaimer externally is the sanctioned alternative. This is **deferral
item D7's** subject; the ambiguity is documented, not resolved by fiat.

**Validation.** Purely additive. Suite: no delta.

---

### R8 — `README.md` (root)

**Defect.** The repository's only real entrypoint had exactly **one** internal link
(`docs/PROJECT_MISSION.md`) and offered no route to `AGENTS.md`, the declared sole pin
authority, the docs map, or the triage index. It also restated player-count policy without the
precedence rule `AGENTS.md:13-16` attaches to it, creating the two-scope ambiguity that rule
exists to prevent.

**What changed.** A "Project authority — read these before anything else" section immediately
after the title, with a seven-row table and an explicit precedence statement.

**Why no `AGENTS.md` content was duplicated.** The table links. The precedence rule is stated
once, in one sentence. Duplicating policy into the README is the failure mode this section
exists to stop.

**Validation.** `test_project_integrity.py` forbids two specific strings in this file; neither
was introduced. Suite: no delta.

---

### R9 — `docs/FORK_AGENT_POINTER_SPEC.md`

**Defect.** *"classifies ANY fork-root `AGENTS.md`/`CLAUDE.md` on a non-canonical profile…"*
reads as though the Lab repo has a `CLAUDE.md`. It does not, and never has.

**What changed.** One parenthetical: the markers are inspected in *fork* roots; this repository
has no `CLAUDE.md` and never has, and `AGENTS.md` is the name that exists here.

**`CLAUDE.md` handling.** This edits a document *about* `CLAUDE.md`. No file of that name was
read for content, modified, moved, renamed, or bulk-replaced. `CLAUDE_MD_MODIFIED = NO`.

**Validation.** Suite: no delta.

---

### R10 — `.gitattributes` (the only deletion)

**Defect.** Lines 21 and 23 marked byte-identity for `scripts/run_j_p5_development.py` and
`scripts/run_phase7_validation.py`, both deleted from `main` in `e459073d`. The sibling
`scripts/run_j_p5_holdout_once.py` is retained, confirming the deletion was selective.

**Proof.** Scripts absent from `main` (57-entry `scripts/` listing); repo-wide grep finds only
`.gitattributes` and an unrelated `docs/J_P5_DEVELOPMENT_FREEZE.json`; no test reads
`.gitattributes`; git ignores attributes for absent paths; the remaining 30 entries are
load-bearing J-P4/J-P5 byte-identity seals and were **not** touched.

**Self-correction.** The first edit introduced leading spaces on three retained lines, which
would have silently broken their `-text` patterns. Caught by `git diff` inspection and fixed
before commit. The final diff is exactly two removed lines.

---

## 2. Reviewed and deliberately NOT changed

Recording these matters as much as the edits.

| File | Finding | Why unchanged |
|---|---|---|
| `AGENTS.md` | §4 defines 7 evidence classes, but `RUNTIME_VERIFIED` (26 word-boundary token occurrences across 16 markdown files at base
`7055740e`, plus 135 machine-readable assignments in
`qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json`. Reproduce with
`git grep -o -w RUNTIME_VERIFIED 7055740e -- '*.md' | wc -l` is used as a classification without being defined | Evidence-policy decision — Coordinator tier. Deferral **D1** |
| `AGENTS.md` | (corrected) an earlier version of this row claimed `QUALIFIED` was "used as a positive class in 12 md files". That was a **substring artifact and is false**: word-boundary search finds 15 token occurrences across 7 files at base `7055740e`
(`git grep -o -w QUALIFIED 7055740e | wc -l`), of which 4 are the phrase "NOT QUALIFIED"
inside quoted PR titles, 1 is a quoted commit subject reading "5 QUALIFIED, 8 UNKNOWN",
and the rest are this audit's own discussion. **The base commit is stated because these
counts are self-referential: every document that reports them adds occurrences of the
same token, so an unanchored count is stale the moment it is written.**. `QUALIFIED` is **never** a positive evidence class | Claim withdrawn rather than restated; see `CANONICAL_KNOWLEDGE_MAP.md` §1 |
| `AGENTS.md`, `opencode.json`, `.foundry/executor-profiles.json`, 3 agent files, `COORDINATOR_EXECUTION_AUTHORITY_2026-09-27.md`, `ROUTING_AND_EFFORT.md`, `EXECUTION_PROVIDER_OVERRIDE.md` | Migrated by PR #350 | Owned by an active workstream at campaign start; released only after it merged |
| `config/rules_engines.json` | `known_stale_pointers` mixes policy with 4 prior pins, WS numbers and PR numbers in one ~1,100-char string | Recorded as foreign-owned in `OWNERSHIP_CHECK.json`; splitting it is a semantic change to the sole pin authority |
| `docs/pre_freeze_completion_20260927/CAMPAIGN_STATE.md:58` | Labels `AGENTS.md` §10 as executor-routing policy; §10 is "Delegated Git integration authority" | A pre-freeze campaign packet. Left byte-unchanged rather than rewrite historical evidence. Deferral **D4** |
| `README.md` "Structural" | Undefined capital-S proper noun in 10+ locations | Consistent product name, also used in `CHANGELOG` 1.24.0. A single-occurrence lowercase flip was **made and then reverted** during diff review because it created internal inconsistency. Deferral **D3** |
| `README.md` architecture framing | Presents Optimizer-v2 / Structural as the decision architecture while `CHANGELOG` 1.24.0 reclassifies them as diagnostic without official deck-decision authority | Needs a decision on which summary belongs in the entrypoint. Deferral **D2** |
| `docs/REPOSITORY_TRIAGE_INDEX.md` | Snapshot dates in section headers | The file already self-scopes as a snapshot and says so at the header. Correct as-is |
| `docs/EVIDENCE_INDEX_REQUIREMENTS.md` | Copies the 7-class list verbatim, propagating the D1 gap | Fixing the list is an evidence-policy change; copying the fix here would invent policy |
| `qualification/` (30 md, 26 subdirs) | No index; `EVIDENCE_INDEX_REQUIREMENTS.md` requires one that was never built | Building an *authoritative evidence index* during a hygiene pass would manufacture an authority that does not exist. Recorded in the knowledge map as a gap |
| `artifacts/`, `data/`, `docs/meta/`, `schemas/` | 32 byte-identical duplicate groups, ~3.85 MiB; one unflagged divergent copy | No deletion proof; evidence-retention policy dominates a trivial byte saving. Deferral **D5** |
| `docs/next_step_handoff_*.md` chains | State authority in present tense, some conditioned on long-merged PRs | Historical handoff snapshots. `docs/README.md` now disclaims them rather than rewriting them |

### What is genuinely good — do not regress

1. **`config/rules_engines.json` pin authority.** `documentation_rule` forbids restating pins
   in prose, and it is **honored**: zero 40-hex SHAs in `integrations/xmage/README.md`,
   `integrations/forge/README.md`, `docs/engine_setup.md`. Verified.
2. **`.opencode/skills/workstream-bootstrap/SKILL.md`.** Ordered gate, explicit
   `WRONG_LOCAL_REPOSITORY` vs `REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE` distinction,
   fail-closed throughout, and it cites helper scripts instead of duplicating `AGENTS.md`.
3. **`docs/foundry-execution/GOVERNANCE_SUPERSESSION.md`.** The supersession-banner pattern R1
   deliberately matched.
4. **`docs/REPOSITORY_TRIAGE_INDEX.md:4-6`.** Correct self-scoping: "a navigation aid, not as
   authority".
5. **`AGENTS.md` §9 reuse-first gate.** Novel and load-bearing; nothing else states it.
6. **Freeze/provider status across 62 files.** No file falsely claims `CLAIMED` or `SELECTED`.
7. **The fail-closed `tracked_worktree_dirty` guard.** It caused a 55-failure cascade that looks
   like a regression and is not. That is the guard working.

---

## 3. Net effect

| Measure | Before | After |
|---|---|---|
| Documents falsely claiming current authority | 4 | 0 |
| Documentation tree with a navigation index | none (`docs/`), 2 unindexed twins | `docs/README.md` + both twins |
| Entry points to `AGENTS.md` from `README.md` | 0 | 1 |
| Root-`README` links to authority documents | 1 | 7 |
| Skills discoverable from the Foundry index | 5 / 7 | 7 / 7 |
| Tools discoverable from the Foundry index | 6 / 20 | 20 (10 named) |
| Files deleted | — | 2 lines in 1 file |
| Source modules deleted | — | **0** |
| Evidence or artifacts deleted | — | **0** |
| `CLAUDE.md` modified | — | **0** (none exists) |

---

## 4. The routing-migration audit (campaign brief §24)

**Status: landed mid-campaign, and audited rather than deferred.**

- At campaign start the migration was **actively uncommitted** across 17 paths, so all of them
  were marked `ACTIVE_OWNER_DEFERRED`.
- PR #350 merged during the audit, advancing `origin/main` to `72665dce`. The owning worktree
  went clean and the remote branch was deleted on merge.
- The branch was fast-forwarded onto, and the new routing re-read: **DeepSeek MAX
  default/preferred, Space Bunny MAX explicit secondary, Muse and GLM inactive, no automatic
  fallback.**
- The migration was **complete on the four files it owned**: `AGENTS.md` §6–§7,
  `ROUTING_AND_EFFORT.md`, `EXECUTION_PROVIDER_OVERRIDE.md`, and the launcher/tests.
- The migration was **incomplete on the surface it indexes**: `docs/foundry-execution/README.md`
  still described the old routing. Corrected here as R5.
- The migration added `test_inactive_executors_are_declared_inactive_in_canonical_docs`, which
  pins four canonical docs against stale active-executor phrasing. It does **not** cover the
  index — which is exactly how the index went stale. Recommended follow-up: extend that test to
  the Foundry index.

---

## 5. Follow-ups a future session should pick up

1. Extend `test_inactive_executors_are_declared_inactive_in_canonical_docs` to
   `docs/foundry-execution/README.md` (R5's root cause).
2. Adjudicate the evidence-classification vocabulary (deferral **D1**) — Coordinator.
3. Decide which architecture summary belongs in `README.md` (deferral **D2**).
4. Resolve the `decision-quality` / `decision_quality` split by decision, not by rename (R7).
5. Build the `qualification/` evidence index that `EVIDENCE_INDEX_REQUIREMENTS.md` requires.
6. Add a single "current blockers" pointer; the concept currently has two unrelated homes.
