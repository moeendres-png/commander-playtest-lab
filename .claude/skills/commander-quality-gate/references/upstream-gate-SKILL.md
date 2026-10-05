---
name: gate
description: Pre-push quality gate. Runs parallel review agents over a changeset (reuse, correctness, quality, i18n, wiring, regression, tests, UX, performance) plus an optional external second-opinion review, then fixes what they find. Use before pushing code or creating PRs.
---

# Gate: Pre-Push Quality Gate

Parallel code review over a changeset, then fixes. This file is the controller's runbook. The
checks themselves live in `reference/patterns-agent<N>.md`, one file per agent, each holding that
agent's checklist and its worked examples. Do not restate checks here.

## Phase 0: Mechanical floor (deterministic, before any agent)

Run these first. They are cheap, and each exists because a check that already existed was skipped or
run wrong. **Read `reference/tooling.md`** for what each decides and what it leaves to an agent.

```bash
bash {SKILL_DIR}/scripts/discover.sh > /tmp/gate-facts.json   # this repo's shape, with evidence
export GATE_DISCOVER_JSON=/tmp/gate-facts.json                # so every script discovers once
bash {SKILL_DIR}/scripts/verify.sh                     # the project's OWN checks, with CI's flags
bash {SKILL_DIR}/scripts/static-checks.sh              # matcher-decidable checks over the diff
bash {SKILL_DIR}/scripts/contract-diff.sh origin/main  # Agent 6 surfaces 1-4, by set arithmetic
```

`discover.sh` replaces every hardcoded layout assumption: where the frontend roots are, where the
translations live, which CSS framework and component libraries are declared, which generated
artifacts have drift guards, whether config reloads at runtime, and which issue tracker to file
against. **Every fact carries the evidence that produced it, or an explicit null and the reason.**
There is no guessed default anywhere, because a wrong guess and a correct find are indistinguishable
downstream. A null is a real answer and it means no consumer may suppress anything.

`verify.sh` reports PASS / FAIL / **SKIP**. A SKIP is not a pass: list every skipped check and its
reason in the Phase 3 summary, and never call a changeset mechanically green while a check covering
it did not run.

`static-checks.sh` splits findings into **decided** (the construct IS the defect) and **candidate**
(triage still needed). Hand both to the agents as ALREADY-FOUND; both still go through Step 3.3.

## Phase 1: Scope & Plan

### Step 1.1: Build the scope manifest (deterministic)

```bash
bash {SKILL_DIR}/scripts/scope.sh > /tmp/gate-scope.json   # or pass a base ref
cat /tmp/gate-scope.json
```

The script decides which files are reviewable, classifies them by area (by CONTENT, not by
directory name), sets the size class, and packs bundles, all in code, so no file is silently
skipped. That is the coverage guarantee, and it is deliberately not a model judgment.

**It resolves the review range and PRINTS which one it chose to stderr.** Staged changes, else
unstaged, else this branch's commits since its merge-base. That last case is the normal pre-push
one, and every script used to resolve it as an empty range: `verify.sh` then tested nothing and
every trigger keyed on an added diff line was suppressed. Read the line it prints; if the range is
wrong, pass the base explicitly. Exit 3 means there is genuinely nothing to review.

Manifest fields:
- `totals`: `files`, `added`, `deleted`, `reviewable`, `reviewable_lines`, `tests`, `churn_lines`.
- `size_class`: `small` or `large`. Drives fan-out. Computed from `churn_lines` (rename-aware) and
  reviewable counts, so a moved file, lockfiles, generated and vendored code cannot inflate it.
  `renamed_files` flags moves: keep both halves of a move in ONE shard, or each is blind to the
  other.
- `files[]`: `path`, `area`, `kind` (A/M/D), churn, `reviewable`, `is_test`, `has_tests`.
- `routing`: area to reviewable paths (`go`, `rust`, `frontend`, `i18n`, `config`, `db`, `api`,
  `other`), plus cross-cutting `perf`: changed non-test source a benchmark for its
  language covers (Go `func Benchmark` or a `.s` file; TS/JS/Svelte a Vitest `*.bench.*`; Rust a
  crate-level `benches/`). Every changed
  hand-written `.s`/`.S` file is ALWAYS in `perf`, benchmark or not: assembly exists only for
  performance.
- `bundles[]`: review units for fan-out, one area each, within size caps (~8 files / 500 changed
  lines; an oversized single file is its own bundle, flagged `oversized`).

Paths are repo-relative. Get the root with `git rev-parse --show-toplevel` and prefix it when
handing absolute paths to agents. Also capture the raw diff for the agents that need it.

**Fallback:** if `totals.reviewable == 0`, review the files the user named or that you edited
earlier in this conversation, treat the changeset as small, and skip the bundling logic.

### Step 1.2: Extract the change summary (what's new)

From the diff, extract the structured what's-new list, keyed by file. This is the shared context
every cross-file agent starts from:
- new struct/type declarations and new fields on existing structs
- new functions/methods and new exported symbols
- new event emission calls
- new options/flags on config/settings structs and new config keys
- new API request/response fields (json tags) and new endpoints
- new or changed DB models / migrations

The manifest plus this list is the **shared change summary** passed to every agent in Phase 2.

### Step 1.3: Match the escaped-defects ledger (deterministic)

```bash
bash {SKILL_DIR}/scripts/ledger-match.sh /tmp/gate-scope.json "<what's-new keywords>"
```

The script matches the manifest's areas and file extensions plus your keywords against each
ledger entry's applies-when trigger and prints only the matching entries. Fold each match into the
relevant agent's prompt for this run, so past misses become present coverage. Do not skim the
ledger by hand; it is 136 entries and the script is the triage surface.

**Optional accelerator: a cross-project memory bank.** If you have a memory/recall tool wired up (any persistent store you can query), recall cross-project lessons matching this changeset to rank the most relevant few. **Read `reference/tooling.md` section "Memory bank"** for the suggested query shape and tags. This step is entirely optional; skip it silently if you have no such tool. Memory NEVER decides which files are reviewed and never relaxes the coverage contract; it only prioritizes lenses.

### Step 1.4: Risk plan (large changesets only)

If `size_class == "large"`, dispatch one planner agent with the full diff and manifest. Strict JSON:

```json
{
  "intent": "1-2 sentences on what this change does",
  "risk_hotspots": [
    {"file": "path", "lines": "40-72", "why": "...", "severity": "high|medium|low", "lens": "correctness|reuse|quality|integration|regression"}
  ],
  "cross_file_watch": ["short notes on wiring or multi-site concerns to verify"]
}
```

`risk_hotspots` is ranked high to low; `lens` routes each hotspot to an agent; `cross_file_watch`
seeds Agents 5 and 6. For `small`, skip the planner.

## Phase 2: Launch Review Agents

### NEVER pass `name` to the Agent tool

**Dispatch review agents WITHOUT the `name` parameter. Passing it destroys the entire fan-out,
silently.** Root-caused 2026-07-20 after three consecutive runs in which every dispatched agent
returned nothing.

`name` is not a label. It switches the agent to `taskKind: "in_process_teammate"`, whose plain-text
output goes to its transcript and nowhere else, so a named agent told to report findings as text
does exactly that and the text is discarded. Intended harness behavior, not a bug to work around,
and messaging the agents afterwards does not recover it. If a run produces `idle_notification` with
no body, check for a stray `name` first. Case history in `reference/tooling.md`.

### Step 2.0: Slice each agent's checklist (deterministic)

```bash
# Tier B and scoped agents: slice against the whole changeset.
bash {SKILL_DIR}/scripts/triggers.sh --scope /tmp/gate-scope.json --out /tmp/gate-checklists
# Tier A shards: slice PER BUNDLE, once per bundle, and hand each shard its own file.
bash {SKILL_DIR}/scripts/triggers.sh --files "<bundle's files, comma-separated>" \
     --agents 1,2,3 --out /tmp/gate-checklists/<bundle-id>
```

Each agent then reads `/tmp/gate-checklists/agent<N>.md` INSTEAD of its patterns file. Slice per
bundle: against the whole changeset each shard gets every area's checklist, which is barely a slice.

Suppression is fail-open. An unclassified item is always live, the security and data-loss classes are
never gated, and any error yields the unsliced file. Each slice states what it suppressed and why.
**Tell every agent to report a suppressed item that looks like it should have applied**; that is a
trigger-table bug and it must be visible rather than worked around.

### The two tiers

- **Tier A, file-local (Agents 1, 2, 3):** reason within a file. Sharded across bundles when large.
- **Tier B, cross-file (Agents 5, 6):** reason across the whole change. **Never sharded.** Isolating
  them to a bundle blinds them to multi-site fixes, sibling inconsistency and wiring gaps, which
  are the gate's highest-value findings.

### Agent dispatch table

Every agent reads its own `reference/patterns-agent<N>.md`, which carries its checklist and
examples. Tell each agent its areas from `routing` and let it select the matching sections.

| # | Agent | Tier | Dispatch when | Input | Patterns file |
|---|---|---|---|---|---|
| 1 | Reuse & Efficiency | A | always | full diff + reviewable file list | `patterns-agent1.md` |
| 2 | Correctness & Safety | A | always | full diff + files | `patterns-agent2.md` AND `patterns-agent2-part2.md` (both) |
| 3 | Quality & Patterns | A | always | full diff + files | `patterns-agent3.md` AND `patterns-agent3-part2.md` (both) |
| 4 | i18n Translation Integrity | scoped | `routing.i18n` or frontend changed | translation files; runs `scripts/i18n-check.sh` first | `patterns-agent4.md` |
| 5 | Integration & Wiring | B | always | what's-new + `cross_file_watch` + manifest + paths. **No raw diff**; it reads full files | `patterns-agent5.md` |
| 6 | Regression & Backward Compat | B | always | full diff AND paths AND what's-new | `patterns-agent6.md` |
| 7 | Test Quality | A | `totals.tests > 0` | `is_test`/`has_tests` files + hunks | `patterns-agent7.md` |
| 8 | UX/UI & Accessibility | scoped | `routing.frontend` or `routing.i18n` non-empty | frontend files in full, plus the full changed-frontend path list | `patterns-agent8.md` |
| 9 | Performance | A | `routing.perf` non-empty, or you judge the change perf-sensitive | perf-flagged files + hunks; one shard per language | `patterns-agent9{,-rust,-ts}.md`, by language |

Agent 8 is **report-only**; it never edits (Phase 3 handles its findings). Agent 9 labels each
finding `mechanical-fix` or `report-only`. Agents 8 and 9 both emit COVERAGE tables.

**Agent 9 routing:** launch one shard per language, each reading only its own file. Several Go rules
INVERT in JS and several have no Rust analogue at all; each file says which.

**When Agent 9 runs, Agent 1 defers micro-performance to it** and keeps semantic waste (N+1
fetches, missed parallelism, fetching for hidden UI).

### Dispatch by size class

**`small` (or fallback):** one agent per dimension, concurrently in a single message. Tier A gets
the full diff plus the reviewable file list.

Do NOT fold or merge dimensions to save agents, even on a tiny changeset. Each dimension is a
distinct lens, and the reuse lens in particular catches misses a quality-focused pass glosses over
(a redundant install of an already-declared dependency, a duplicated helper). **One agent per
dimension is the floor, not a target to optimize below.**

**`large`:** fan out Tier A. For each entry in `bundles[]`, launch one Agent 1, one Agent 2 and one
Agent 3 scoped to that bundle. Give each shard its bundle's files as absolute paths, the diff hunks
for those files, the shared change summary, the bundle `area`, and the `risk_hotspots` whose `file`
is in its bundle. Mark `oversized` bundles so that shard reads the file in full.

Launch Tier B once each over the full manifest, never sharded. Shard Agents 7, 8 and 9 only on very
large changesets, and **always pass every Agent 8 shard the full changed-frontend path list** so its
cross-component consistency pass is not blinded by sharding. Launch as many as fit in one message;
the harness queues the rest.

### The coverage contract

**Per-file accounting.** Every Tier A agent, sharded or not, must end its report with a COVERAGE
table: one row per assigned file, status `FLAGGED (n)`, `CLEAN`, or `N/A: <reason>`. Every assigned
file must appear. A skipped file then surfaces as a gap in Phase 3 instead of vanishing.

**Checklist-loaded line.** Every agent must open its report with the patterns file it read and how
many checklist items it loaded. The checklist lives in that file, not in the prompt, so a failed
Read means the agent reviewed nothing. A missing line, or a count of zero, means NOT DELIVERED:
re-dispatch it.

**Delivery check (mandatory, before Phase 3).** A report counts as RECEIVED only when its text,
with its COVERAGE table, is in hand as a tool result. Say "COVERAGE table" to each agent in those
words and state that a findings-summary table is NOT a substitute: when the 2026-07-20 reports were
recovered, 2 of 5 had produced complete reviews but substituted their own table format, so no file
was ever listed as reviewed-and-clean and the reconciliation had nothing to consume. Count the
reports actually received. If that number is below the number dispatched, say so in the summary in
those words, treat the missing agents' files as UNREVIEWED, and dispatch the catch-up pass.

### Prompt-authoring rules

**Do not transfer your own blind spot.** Example inputs, file lists and the what's-new summary you
hand an agent are STARTING POINTS, not the coverage boundary. Never let a curated example list
become the agent's whole search space. State the *semantics* of what changed ("the old code used
`url.Parse`; derive its full accepted-input domain and test against it") and tell the agent
explicitly to expand beyond any examples you gave. A hand-authored input list silently caps the
agent at the author's blind spot, which is exactly how the `ws://host/path` regression slipped
multiple passes whose prompts all enumerated the same path-less corpus.

**Restrict repo-mutating git commands.** "Do not edit any file" does NOT cover `git stash`,
`checkout`, `reset`, `restore` or `clean`, which mutate repo state with no file edit. Say "do not run
any git command that changes HEAD, the index, or the working tree; compare versions in a scratch copy
outside the repo", and give `git archive <ref> | tar -C /tmp/x -x` as the safe recipe. Enforcement is
a post-dispatch `git status --porcelain` check reading BOTH columns, not the prompt.

**Every agent classifies each finding:**
- **[CHANGED]**: in lines added or modified by this diff.
- **[PRE-EXISTING]**: in surrounding untouched code, found while reviewing context.

Agents review the full context of changed files, not only diff lines.

### Visual-render gate for layout-bearing frontend changes

No agent can see a broken layout. Every agent reviews code statically and jsdom asserts attributes,
not computed layout, so a purely visual regression (a grid child missing `col-span-*` and collapsing
to one track, a broken flex row, a duplicated title, overflow) is invisible to the entire gate. That
is how a prior run shipped analytics pages squished into a 1/12 column. Flag the changeset now
if Step 3.6's trigger fires; **the gate then cannot pass on static green alone**.

### Background: external second-opinion review (optional, pluggable)

If you can dispatch the changeset to an external reviewer, a capable non-Claude model reached over a
CLI or an MCP tool, launch it in the background at dispatch time and collect it in Phase 3, and never
report while it is unreconciled. This step is optional: if you have no such reviewer wired up, skip
it and rely on the in-process agents. **Read `reference/tooling.md` section "Background: external
second-opinion review"** for the prompt, a CLI-fallback shape, the concurrency constraint that stops
a background reviewer colliding with Agent 6's own cross-check, and why an empirical, suite-running
model and a fast-reasoning model catch disjoint issue classes on high-risk diffs.

**Its findings are LEADS, not findings.** Reproduce each claim against the actual code before acting;
in a documented case all three of an external reviewer's contested claims were false. The tell is a
hedge like "likely calls X" where the call does not exist. Applies to external review bots in a
push-review cycle too.

## Phase 3: Aggregate, Fix & Report

Wait for all agents, and collect the background external-review job if one was launched. Never
report while it is unreconciled.

### Step 3.1: Verify coverage

Collect the COVERAGE tables from all Tier A agents (1, 2, 3, plus 7 and 9 when they ran). Take the
union of files marked FLAGGED / CLEAN / N/A and compare against `files[]` where `reviewable == true`.
For any reviewable file with no status from any Tier A agent, dispatch a catch-up agent (correctness
+ quality) over just those files before continuing. Record "X/Y reviewable files reviewed".

Agent 8's COVERAGE table confirms the UX pass was not skipped but does not participate in the
catch-up, since Tier A already covers those files for fixes.

### Step 3.2: Filter false positives

Apply the static list at the end of this file first. Then, if you have an optional memory bank
(Step 1.3), do ONE recall of this project's conventions and confirmed non-issues, for example:

```text
recall: "intentional patterns, conventions, and confirmed non-issues a reviewer should NOT flag
in this project; things explained as deliberate", tagged to this project.
```

Suppress or downgrade a finding ONLY when a returned memory tagged as a convention or a confirmed
false-positive clearly and SPECIFICALLY covers it (same construct, same rationale). Vague topical
overlap is not enough; a memory confirmed more often is stronger evidence.

Hard guardrails: memory may only suppress or downgrade, **never create** a finding (that is Phase 1's
job) and **never suppress a Critical/High security, data-loss or panic finding**, whatever the
convention says. Every memory-driven suppression is listed in the summary with the matching learning
quoted and its source and confidence cited, so over-suppression is auditable, never silent.

### Step 3.3: Triage

**Triage on the finding's ARGUMENT, not the agent's severity LABEL.** Severity is the
agent's opinion; the body is the evidence. Agents routinely self-limit a correct finding with a
defensible hedge ("consistency call, not a bug", "test-only", "the comment is accurate"), and that
label then does the triage instead of you. Escalate to at least Medium and FIX, whatever the label
says, when the body shows the changeset treats the SAME hazard two ways: eliminating it structurally
in one file while resolving it in prose in another. "Test-only" is not a defence.

**A finding you defer is one you have chosen to have a reviewer find.** Deferring is only correct
when you would also be content for no reviewer to find it. Weight "constructor accepts a config that
cannot work" at Medium or above: the failure surfaces far from its cause. Defer against the CHEAPEST
fix, not the first (`reference/tooling.md`, "The deferral test").

Four categories:

**a) In-scope (introduced or touched by this diff).** Fix it, at the invasiveness the RE-DERIVED
severity earns, per the ladder below. For Critical/High, first re-read the cited code and confirm
the failure is real in the actual source: agent reports can be plausible-but-wrong, and a fix applied
to a misread finding is itself a regression. If it does not reproduce by reading, do not fix; report
it as unconfirmed.

**Match the fix's invasiveness to the severity: 23% of the ledger is fix-wave damage.**

| Re-derived severity | Fix you are allowed to make |
|---|---|
| Critical / High | Whatever correctness genuinely requires, including a structural change. |
| Medium | A minimal local edit. No new abstraction, no rerouted call sites, no behaviour change. |
| Low | A zero-risk edit only (a comment typo, a missing `type="button"`, `aria-label`, `<label for>`, `focus-visible:`). Everything else is batched, not fixed. |

**When the only correct fix is more invasive than the severity earns, it becomes category (d), not a
fix.** In particular, **when a finding says only that a decision is UNSTATED, default to documenting
it rather than changing the behaviour**: a doc edit cannot regress anything, and the behaviour change
can be its own issue. The 2026-07-20 ledger entry records a fix wave doing the opposite on a finding
rated Low ("defensible, but it is a new decision the code does not state") and regressing the exact
case the change targeted.

**Genuinely-Low findings are batched into ONE follow-up issue**, filed at the end of the run, not
fixed individually. This is not a licence to dismiss them: re-derive severity from the argument
first, exactly as above, so a mislabelled real defect escalates rather than lands in the batch.

**b) Pre-existing but fixable here.** Only when the fix is High or above, provably safe, and in a
file this diff already changed. Otherwise file it (category c). Every bonus fix enlarges an already
risky fix wave for a defect that was not blocking the push.

**c) Pre-existing and out-of-scope.** File an issue with file path, line and description, using the
command in `issue_tracker.create` from Phase 0 (`gh issue create ...` on GitHub, the forge's CLI
elsewhere). If discovery found no tracker, list the finding in the summary under "not filed, no
issue tracker discovered" so it is still visible. **Never dismiss a pre-existing issue as "out of
scope" without either filing it or recording that you could not.**

**d) Maintainer-confirm.** Do NOT auto-fix, revert or "correct" these, even in-scope, because
auto-fixing usually means silently deleting the contributor's new code. Covers: a behavioral or
feature-interaction conflict (Agent 5's read-time-filter-vs-write-time-invariant check); an
additive-but-behavior-changing client surface (Agent 6 carve-out); and a security bypass (disabling
TLS verification, skipping auth) even when a comment justifies it. Name the colliding feature or
bypassed control, state the user-visible consequence, and hold for explicit confirmation. Report as
"needs maintainer decision", never as fixed.

**Agent 8 UX findings are report-only and bypass (a)-(d).** Collect them into a dedicated UX/UI
subsection ordered by severity, each with file/component, the violated project doctrine rule if the
repo has a frontend doctrine file at all, the user-visible consequence, and the suggested fix
described but not applied. For substantial
UX debt out of scope here, offer to file an issue. Two exceptions DO go through normal triage so
they get fixed: genuine code bugs Agent 8 happened to notice, and findings it tagged "objective,
fixable" (a missing `<label for>`, an icon button with no `aria-label`, a missing `type="button"`,
`outline-none` with no `focus-visible:` replacement).

### Step 3.4: Plan the fix wave BEFORE editing

Do not start fixing at the top of the findings list. Nearly every fix-wave escape in the ledger was
a failure to think past the site the finding named, not a failure to make a correct edit.

**First, cluster the findings by HAZARD, not by report order.** Several findings usually share one
root cause; fixing them one at a time produces N interacting edits where one would do.

**Then write a FIX PLAN row per hazard, before touching code.** This is an artifact for the same
reason the COVERAGE table is: the thinking it forces does not reliably happen without one.

| Hazard (one sentence) | Sites that can realise it | Blast radius of the intended edit | Effect on the NORMAL case | Minimal edit | How closure is proved |
|---|---|---|---|---|---|

**Read `{SKILL_DIR}/reference/fix-wave.md` section "Before you fix: think in the larger scope" now**,
not at Step 3.5. It carries what each column defends against and the escape behind it. Two that are
most often skipped:
sweep with `scripts/fix-sweep.sh` BEFORE fixing rather than after, because sweeping first shapes the
fix and sweeping after only audits it; and state what the fix does to the NORMAL case, not only the
reported one.

**Four fix shapes go to category (d) instead of being applied**, because each has a ledger entry
behind it: extracting a helper and rerouting existing call sites; changing behaviour to satisfy a
consistency or quality finding; adding a threshold, cap or mitigation calibrated on the reported
scenario; and any broad `replace_all` edit. Propose them, do not perform them.

Apply the plan one hazard at a time, verifying closure before starting the next, so a defective fix
is found on its own rather than under fourteen others.

### Step 3.5: Fix verification, and the round bar

**The fix wave is unreviewed code. Review it to the same standard as the input diff.** Across seven
PRs running, **every defect that escaped a gate run lived in the gate's own fixes, not in the reviewed
diff**. The fixer cannot see it, having just convinced themselves the code is right. Green tests and
lint prove nothing here, because the fix wave wrote its own tests.

**Read `{SKILL_DIR}/reference/fix-wave.md` and run its checklist.** It carries the triggers, the
checks and the escaped case behind each line. Do not reconstruct it from memory.

A fix wave that ADDS anything is non-trivial BY DEFINITION, **including docs and tests**; "just docs"
and "just tests" is the rationalization that skips this step. fix-wave.md lists the triggers.

**Rounds are bounded and the bar rises. This is what makes the gate terminate.**

| Round | Reviewing | Fix only |
|---|---|---|
| 1 | the input diff | Critical, High, Medium |
| 2 | round 1's fix wave | Critical, High |
| 3 | round 2's fix wave | Critical |
| stop | | hand the remainder to PR review |

Below the bar at each round, findings are reported and batched into the follow-up issue, never fixed.
After round 3, STOP: list every unfixed finding with its severity and say the gate stopped at its
round limit. **A Critical still appearing after three rounds is a design problem that needs the
maintainer, not a fourth round of automated fixing.**

**Whichever round is last, its fixes AND every fix written after it get reviewed, REPORT-ONLY and by
a DISPATCHED AGENT: not your own read, not mutation testing.** The rule reaches past the run, because
review-cycle fixes postdate the gate and nobody else reads them. Mutation runs in the environment
that hides environment-coupled defects, and cannot ask whether a test obeys the contract it asserts
(observed repeatedly in prior runs). Fix nothing, summarize, and a Critical means recommend holding the push.

**Divergence abort.** If any round's fix wave introduces more findings than it closed, stop there. Do
not start another round. Report the counts and hand off. A fix wave that costs more than it buys is
the signal that the gate is rewriting rather than fixing, and another round will not recover it.

Two controller failure modes that fix-wave.md covers in full and that you must not skip: give the
fresh reviewer the STANDARD LENS SET rather than only your own worries, and treat a stalled or empty
reviewer as a MISSING review, walking the checklist yourself.

### Step 3.6: Visual render check (layout-bearing frontend changes only)

If the changeset added or restructured a page/route-level component, a shared layout, or a
component's root element or grid/flex placement, render the affected routes in a real browser at
desktop width BEFORE declaring the gate passed. Serve the built frontend (proxy `/api` to a
reachable backend if needed), then Playwright navigate and screenshot, and check full-width layout,
a single page title, and no overflow. Static green is not sufficient; "no route was ever rendered"
is an incomplete gate.

### Step 3.7: Report

Severity for remaining items: **Critical** (security, data corruption, panics in production paths),
**High** (races, resource leaks, incomplete multi-site fixes), **Medium** (code smells, inconsistent
patterns, test gaps), **Low** (style, minor optimization).

Summarize:
- **Review range**: quote `review_range.why` from the manifest verbatim. A range that
  silently excluded most of the branch is a coverage violation wearing a pass, and it has
  happened; the field exists so the summary cannot omit it.
- **Coverage**: X/Y reviewable files reviewed, and any catch-up dispatched.
- **FIX SWEEP table** (required whenever anything was fixed): one row per fix, hazard named in ONE
  sentence, sites checked, sites changed. Same reason as the COVERAGE tables: a check with no
  artifact silently does not run. **A row reading "sites checked: 1" is the shape that has escaped
  every previous gate run**, so justify it or go back and sweep. Name the hazard, not the symbol:
  "a config field left at its zero value for an enabled feature is fatal" is a hazard; "grepped for
  normalizeEQFilters" is a symbol.

  | Fix | Hazard (one sentence) | Sites checked | Sites changed |
  |---|---|---|---|

- **CONVERGENCE table** (required, one row per round). This is how a non-terminating gate becomes
  visible instead of just feeling long. `introduced` counts findings in code the fix wave itself
  wrote. If it is not falling round over round, say so plainly; that is the process failing, not the
  code being bad.

  | Round | Bar | Closed | Introduced | Fix-wave lines as % of reviewed diff |
  |---|---|---|---|---|

  State how the run ended: **converged** (nothing left at the round's bar), **round limit** (stopped
  after round 3, remainder handed to PR review), or **diverged** (a round introduced more than it
  closed, stopped early). Never report a round-limit or diverged stop as a pass.
- **Memory-suppressed findings** (if any), each with the matching learning quoted and its source and confidence.
- What was fixed; what pre-existing issues were fixed as bonus; what issues were filed.
- **The batched Low-findings issue** (number and count), or "none" if there were no Low findings.
- **What needs a maintainer decision** (category d), held unfixed pending confirmation. Include the
  fixes you declined to make because they exceeded the invasiveness the severity earned, and the four
  escalated fix shapes, each with the fix you would have applied so the maintainer can approve it.
- **Everything left unfixed** because it fell below the round's bar, with severity, so nothing is
  silently dropped between rounds.
- **UX/UI review (report-only)** when frontend changed; omit the section entirely otherwise.
- **Ledger entries applied** and whether they fired.

## Continuous Improvement

Every escaped defect is a hole in the checklist, and closing it is part of running the gate.
`reference/escaped-defects.md` is the ledger; Step 1.3 consults it and Step 3.7 closes the loop.

**When you learn the gate missed something, record it BEFORE moving on**, and add its one-line index
row. Capture the root cause (the reasoning gap), not just the symptom.

**Then codify it into a durable check.** A miss that produces only a ledger note has not been
learned. A missing *check* goes into the relevant `reference/patterns-agent<N>.md`, as a compact
checklist item plus a detail section below it. A flaw in *how the gate is run* edits this file.

**Before adding an item, try to merge it into an existing one.** A merged item is strictly more
general: it fires on a dialect no specific item anticipated. Prefer widening a hazard class over
appending a sibling.

**Budget.** SKILL.md grew 101KB to 144KB in eight days because every lesson was appended here as a
full case history duplicating the patterns file it pointed at. SKILL.md stays under 32KB and is the
controller's runbook, not a checklist; a plain checklist item stays under 1400 bytes, a merged one
under 4000, and any item's opening statement under 1100. If an addition would breach either, merge
rather than append. Tooling detail and case histories belong in `reference/tooling.md`.

```bash
bash {SKILL_DIR}/scripts/gate-lint.sh
```

Run it after every edit to this skill. **Read `reference/maintenance.md` for the full procedure**:
the memory-bank tag schema, the retain call, and what each lint check exists to prevent.

## Static Analysis False Positive Patterns

The known-benign list lives in `reference/false-positives.md` (math/rand for non-security use,
`template.HTML` on constants, `os.Exit` at startup, domain-math variable names, empty slice literals
in tests, branchy config validation, intentional duplication in CPU-bound hot paths, swallowed
non-critical shutdown cleanup errors, nil checks on non-nil-by-construction internal deps, and
multiple `%w` verbs on Go 1.20+). Read it during Step 3.2 and filter against it before applying any
memory-based suppression.
