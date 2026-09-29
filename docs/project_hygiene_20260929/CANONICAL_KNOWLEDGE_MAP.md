# Canonical Knowledge Map

What a future human or agent should read for each subject. One canonical source per topic
where one exists. Where none exists, that is stated rather than papered over.

**Status: navigation aid, not authority.** Where this map and a governing document disagree,
the governing document wins (`AGENTS.md` §3).

## Use this when you need to know…

| Subject | Read this | Notes |
|---|---|---|
| **Durable rules for every session** | `AGENTS.md` | The root policy. §3 source truth, §2 rules authority, §4 evidence semantics, §6–§7 execution routing, §10–§11 Git and worktree authority |
| **What the project is building** | `docs/PROJECT_MISSION.md` | Explicitly outranks any summary elsewhere, including the root `README.md` |
| **Current engine pins** | `config/rules_engines.json` | The *sole* machine-readable pin authority. Its own `documentation_rule` forbids restating pins in prose, and that rule is currently honored — verified zero 40-hex SHAs in `integrations/*/README.md` and `docs/engine_setup.md` |
| **ARCHITECTURE_FREEZE / PRODUCTION_PROVIDER status** | `config/rules_engines.json` → `selection_truth` | Repeated in 62 tracked files, all consistently `NOT CLAIMED` / `NOT SELECTED`. No file falsely claims otherwise. The repetition is noise but not a correctness risk |
| **Who may execute what, at which effort** | `AGENTS.md` §6–§7, then `docs/foundry-execution/ROUTING_AND_EFFORT.md` and `docs/foundry-execution/EXECUTION_PROVIDER_OVERRIDE.md` | Current: DeepSeek MAX default/preferred, Space Bunny MAX explicit secondary, Muse and GLM inactive, no automatic fallback |
| **What counts as PASS** | `AGENTS.md` §4 | `UNKNOWN != PASS`, `PARTIAL != FULL`, `NOT_RUN != PASS`, `CODE_DERIVED != RUNTIME_VERIFIED`. **Caveat below** |
| **Evidence schema for indexed evidence** | `docs/EVIDENCE_INDEX_REQUIREMENTS.md` | Companion to `docs/RETENTION_AND_LIFECYCLE_POLICY.md` |
| **Git / worktree ownership** | `AGENTS.md` §10–§11 | Downstream docs correctly *delegate* to these sections rather than restating them — the one duplication that works |
| **Hidden information, RNG, replay** | `AGENTS.md` §5 | No drift found |
| **Starting a workstream** | `.opencode/skills/workstream-bootstrap/SKILL.md` | Best operational document in the repository. Ordered gate, explicit fail-closed distinctions |
| **Resuming an interrupted workstream** | `.opencode/skills/continuation/SKILL.md` | |
| **Escalating a Magic Rules question** | `.opencode/skills/rules-authority-escalation/SKILL.md` | Was missing from the Foundry index; now listed in `docs/foundry-execution/README.md` |
| **The Foundry execution system as a whole** | `docs/foundry-execution/README.md` | The canonical index. Corrected by this campaign after the routing migration |
| **All documentation** | `docs/README.md` | New in this campaign. 294 flat markdown files previously had no index |
| **Live PRs, issues, branches** | `docs/REPOSITORY_TRIAGE_INDEX.md` | Self-scoped: "a navigation aid, not as authority". Timestamped snapshot |
| **Qualification evidence** | `qualification/` | See the gap below |
| **Repository/branch/PR integrity records** | `docs/project_integrity_20260929/`→ see `docs/project_integrity_20260928/` | Ownership deferrals, legacy donor adjudication, port receipts |
| **This audit** | `docs/project_hygiene_20260929/` | |

## Where a subject is *partly* answered — the honest gaps

These are real navigation gaps, recorded rather than hidden.

### 1. Evidence classification vocabulary is internally inconsistent

`AGENTS.md` §4 defines **7** classes: `DIRECTLY_VERIFIED`, `CODE_DERIVED`,
`TECHNICALLY_CONFORMANT`, `EXTERNALLY_RULE_VALIDATED`, `MODELED`, `SYNTHETIC`, `UNKNOWN`.

But repo-wide usage also includes **`RUNTIME_VERIFIED`** (19 markdown files) and
**`QUALIFIED`** (12 markdown files) as *positive* classifications, and neither is defined as a
class. `AGENTS.md` uses
`RUNTIME_VERIFIED` only on the right-hand side of a negation (`CODE_DERIVED !=
RUNTIME_VERIFIED`), so a machine reading the 7-token list will reject a legitimately
classified entry. Three agent/skill files additionally use three different verdict
vocabularies (`evidence-seal`: `PASS/FAIL/UNKNOWN/NOT_RUN`; `foundry-reviewer` and
`foundry-adjudicator`: `PASS/FAIL/PARTIAL/UNKNOWN`).

**Why this was not fixed here:** evidence classification is an evidence-policy decision
reserved to the Coordinator tier. Changing it from a hygiene campaign would be inventing
policy. Recorded as deferral `D1`.

### 2. "Current blockers" has no single entry point

Two different blocker concepts compete:

- *Qualification* blockers — the most current statement of why neither candidate is close is
  buried inside `docs/pre_freeze_completion_20260927/PROVIDER_READINESS_PACKET_20260928.md`.
- *Repository* blockers — `docs/REPOSITORY_TRIAGE_INDEX.md` covers issues/PRs/branches only.

A newcomer looking for "what is blocking us" must already know which kind they want. A single
pointer document would fix this; it is Coordinator-owned because the blocker *content* is
Coordinator state.

### 3. `qualification/` has no index

30 markdown files across 26 subdirectories, no top-level README. `docs/EVIDENCE_INDEX_REQUIREMENTS.md`
requires an evidence index; that index has not been built (the requirement file itself notes
"No bulk re-indexing is ordered here"). Deliberately not created here: inventing an
authoritative evidence index during a hygiene pass would manufacture an authority that does
not exist yet.

### 4. Donor branches have three overlapping descriptions

`docs/muse_final_integration_20260928/MUSE_FINAL_DISPOSITION.md`,
`docs/project_integrity_20260928/LEGACY_DONOR_ADJUDICATION.json`, and
`docs/REPOSITORY_TRIAGE_INDEX.md` each describe donor/branch retention, and
`docs/REPOSITORY_TRIAGE_INDEX.md` says of itself "This is a timestamped snapshot, not a
permanent ownership grant". No single index.

## Duplication that is *fine*, and should not be "fixed"

- **Rules authority** is restated in `AGENTS.md` §2, `docs/PROJECT_MISSION.md`, and two
  authority documents. All consistent. The divergence risk is low and the redundancy is
  deliberate in an authority document set.
- **Freeze/provider status** repeated in 62 files, 100% consistent. Collapsing it would add
  indirection for no correctness gain.
- **Engine pins**: exactly one authority, and the no-restatement rule is enforced in practice.

## Duplication that *is* a live risk

- **Executor routing** is stated in 7+ files. That redundancy already caused one real
  incident in this campaign: when PR #350 changed the routing, the canonical index
  `docs/foundry-execution/README.md` was left stale while the four files under
  `tests/foundry/test_project_integrity.py` enforcement did not cover it. Routing text is now
  duplicated across files with *unequal* test coverage.
