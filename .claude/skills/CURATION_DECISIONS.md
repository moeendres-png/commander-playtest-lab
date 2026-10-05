# Claude skill curation — Commander Simulator Next

Upstream evaluated: `coleam00/skills@dfaa9105741fc5ba9b16b6a72551cad4bad70415`.

Decision vocabulary:

- **IMPORT** — useful now and compatible when subordinated to root `AGENTS.md`.
- **DEFER / ADAPT** — useful concept, but the upstream workflow is unsafe or incomplete
  for this project's ownership/evidence/Git model without a Commander-specific variant.
- **SKIP** — not materially useful for the current project.

| Skill | Decision | Why |
|---|---|---|
| ablate-ai-layer | DEFER / ADAPT | Empirical AI-layer pruning is interesting later, but this project currently depends on unusually strong safety/evidence instructions. Do not ablate them while core qualification architecture is still moving. |
| agent-browser | SKIP | Browser/Electron automation is not a core Commander-simulator engineering need. |
| ast-grep | IMPORT | Structural Java/Python search is valuable for finding decision fallbacks, API patterns, tests, and systemic source debt beyond regex/grep. |
| build-dark-factory | DEFER / ADAPT | The concept may become useful later, but an autonomous production factory is premature before Provider Selection and Architecture Freeze and could conflict with the no-Production-Repository gate. |
| drive-screen | SKIP | Desktop GUI driving is not needed for the repository-first engineering workflow. |
| hooks-create | DEFER / ADAPT | Deterministic enforcement is useful, but project-critical guarantees should be cross-tool/repository enforcement rather than Claude-only hooks unless a concrete gap justifies one. |
| opportunity-scan | IMPORT | Useful for turning observed agent/process failures into targeted rules, skills, hooks or automation instead of adding speculative instructions. |
| piv-commit | DEFER / ADAPT | Upstream commits all uncommitted changes. This project requires exact owned mutation surfaces and must never accidentally sweep unrelated work into a commit. |
| piv-create-pr | IMPORT | One owned branch/PR per bounded workstream matches the project model; `AGENTS.md` supplies the stronger source-lock and merge gates. |
| piv-fix-review-findings | IMPORT | Good review-remediation loop; project authority overrides its generic “human call” language for routine in-scope technical decisions. |
| piv-implement-issue | IMPORT | Strong fit for GitHub-issue-driven defect work with RCA, drift checks, regression tests and validation. |
| piv-implement | IMPORT | Useful execution-from-plan workflow with per-task validation and explicit deviations. |
| piv-investigate-issue | IMPORT | Evidence-backed RCA before fixes matches current qualification and failure-analysis work. |
| piv-plan-implementation | IMPORT | Deep, implementation-ready per-ticket planning is highly relevant once an issue/workstream is bounded. |
| piv-review-changes | IMPORT | Useful pre-commit technical/adversarial review primitive. |
| piv-review-pr | IMPORT | Fresh-context PR review is directly valuable; Commander-specific evidence and merge gates remain authoritative. |
| piv-run-full-loop | DEFER / ADAPT | Too generic as-is: it lacks Commander source locks, ownership checks, evidence vocabulary, fail-closed gates, PR review and semantic-completion requirements. |
| piv-slice-epic | IMPORT | Excellent match for splitting large post-roadmap work into disjoint, testable, dependency-aware workstreams and parallelizable mutation surfaces. |
| piv-validate | IMPORT | Useful validation shell, but actual commands and PASS semantics come from the active repo/workstream. Green CI alone is never Qualification PASS. |
| plan-architecture | IMPORT | Especially valuable in **brownfield mode**: inspect existing Lab/engine seams first, compare approaches, preserve reuse-first and avoid accidental second Rules Engines. |
| plan-create-prd | IMPORT | Valuable for the product-level intent of the eventual Commander Simulator Next or a genuinely new epic/product boundary. It must not overwrite current technical source truth or issue contracts. |
| plan-create-stories | SKIP | Largely superseded here by `piv-slice-epic`, which handles architecture/dependencies/parallelism more explicitly. |
| prime-backend | SKIP | Web/API backend-specific framing does not match the multi-repo Python/Java rules-engine project. |
| prime-codebase | IMPORT | Strong default orientation primitive before brownfield planning or implementation. |
| prime-frontend | SKIP | No material frontend surface in the current simulator qualification program. |
| rules-check-drift | IMPORT | Useful advisory check to keep durable agent rules true after structural changes. It must not silently rewrite `AGENTS.md`. |
| rules-create-global | SKIP | The project already has a mature canonical `AGENTS.md` and Claude entrypoint. Re-deriving global rules risks overwriting higher-authority policy. |
| second-brain-audit | SKIP | Technical state is deliberately GitHub/repository canonical rather than a generic notes vault. |
| second-brain-fix | SKIP | Same reason as second-brain-audit; current state repair belongs in canonical GitHub/repo checkpoints. |
| setup-ai-tutor | SKIP | Sample-project-specific and unrelated. |
| skills-create | IMPORT | Useful for authoring future Commander-specific skills with lean, testable trigger/validation structure. |
| system-evolution-review | IMPORT | Valuable meta-review: compare plan vs execution and improve the AI layer based on observed divergences. |
| system-execution-report | IMPORT | Provides structured implementation retrospectives that can feed system-evolution-review. |
| worktree-create | DEFER / ADAPT | Parallel isolation is important, but this project's workstream bootstrap, live writer locks, Bubblewrap and owned-write semantics are stricter than the generic skill. |
| worktree-merge | DEFER / ADAPT | Generic multi-branch integration is too permissive for the project's source-lock, ownership, no-rebase, exact-head evidence and merge-gate model. |

## Recommended planning sequence now

There is **no upstream skill named `brownfield`**. Brownfield is a mode of work,
especially in `plan-architecture` (and, for projects without an AI layer,
`rules-create-global`).

Commander Simulator Next currently has a useful duality:

- the **current Lab + Mage + Forge engineering environment is brownfield**;
- the eventual production simulator is still a **greenfield product/repository boundary**,
  and the Production Repository may not be created before Architecture Freeze.

Therefore the recommended sequence is:

1. **Brownfield rebaseline** — run `prime-codebase` against the current canonical Lab
   state and consume current roadmap/issues/engine repositories as evidence.
2. **Product PRD** — use `plan-create-prd` for the eventual Commander Simulator Next
   product-level WHAT/WHY, treating existing mission/research as evidence rather than
   silently inventing requirements. Preserve `PRODUCTION_PROVIDER = NOT_SELECTED` and
   `ARCHITECTURE_FREEZE = NOT_CLAIMED`.
3. **Brownfield architecture** — run `plan-architecture` against the PRD plus current
   repositories/evidence to decide HOW the eventual system should reuse/wrap/port existing
   qualified assets. Architecture remains a proposal until project freeze gates are met.
4. **Slice the epic** — use `piv-slice-epic` only after the product intent and relevant
   architecture decisions are stable enough to produce dependency-aware workstreams.
5. Each implementation slice then uses the issue/PIV investigation → plan → implement →
   validate → review → PR loop.

This gives the project a clean separation between product intent, current brownfield
technical truth, architecture decisions, and executable work packets without prematurely
creating the Production Repository or selecting a provider.
