# WS198 Design Record — Autonomous Workstream Orchestration

Source lock: `691dbe504b8626a7e6e7a59cf994cc43777a8abf`
(tree `17f80c05bd8f0e9d9419890ea3a2f8f8b8bdbb8d`, WS196 candidate, required parent).
Reference: `ws78b-natural-baseline` commit `8bd0ed4dfdc4ee0fbf2094a5cb6359983adcb0c3`
(read-only; object-store bytes via `git show`, live-checkout verify NOT_RUN —
sibling path denied by canonical policy, not circumvented).

## Chosen architecture (XHIGH-adjudicated hybrid D1+D2-minimal+D3-minimal+D4-selective)

- D1 docs/prose: `AGENTS.md` §8+§12 (one sentence each), implementer rules
  3/4/13, adjudicator rule 7, continuation skill, contract template sections,
  new `docs/foundry-execution/AUTONOMY.md`. Normative, cached static layers.
- D2-minimal schema: 3 optional fields (`continuation_policy`,
  `successor_plan`, `rotation_guidance`), schema stays 2.0 additive.
  `state.py` validates (malformed fails closed); `--check-completion` advisory.
- D3-minimal launcher: autonomy values snapshot in `launch-context.json`
  (no new `FOUNDRY_*` prose env); `ui_mode` in run telemetry.
- D4-selective validators: `tools/foundry/autonomy.py` pure stdlib module
  (no I/O, no subprocess) + `check_completion_readiness`,
  `continuation_decision`, `check_successor`/`validate_successor_set`,
  `rotation_render`, `scan_forbidden_plan_shapes`, `scan_telemetry_fabrication`.

## Alternatives rejected

- Docs-only: leaves early-COMPLETE writable, continuation bounds invisible to
  capsule resumes, successors uncheckable. Necessary but insufficient.
- Schema-heavy (blobs in state): bloats state, duplicates evidence; pointers
  preferred.
- Launcher prompt injection: duplicates static prose into dynamic prompts
  (WS78 economy violation); TUI/headless parity achieved via single-sourced
  documented strings instead.
- New gates on engineering for missing telemetry: rejected; export hygiene is
  a reminder, never a gate.

## WS78B consumption (structural only; UNKNOWN preserved)

Integrated: export-capture hygiene (reminder), milestone/artifact-time rotation
signals threshold-free, compact-capsule discipline, stable-prefix preservation.
NOT claimed: any token/cache/cost/turn figures, rotation thresholds, cache-hit
ratios, HIGH-vs-XHIGH equivalence, compaction behavior. `TOKEN_ECONOMY_BENCHMARK
= NOT_RUN`, `SESSION_ROTATION_THRESHOLD = MODELED` stand.

## Key subordinate decisions

- `SESSION_ROTATION_RECOMMENDED` = `rotation_guidance ROTATE_TO_FRESH_CONTINUATION`
  (no new status enum value; compat preserved).
- Successor = pointer-in-state + separate validated artifact + handoff section.
- No preauthorization mode implemented: `AUTHORIZED` still needs a fresh
  explicit Coordinator/operator launch (default stays COORDINATOR_GATE).
- TUI exit-0 false success: construction-time refusal (see TUI_FINDING.md);
  post-hoc detection without stderr heuristics ruled unreliable.
- `validate_child_options` now scans past bare `--` (closes model-flag bypass
  where `-- --model x` previously skipped validation).

## Compatibility

Old valid 2.0 states parse unchanged → `EXACT_NEXT_ACTION_ONLY` / `NONE` /
`NO_ROTATION`. Malformed autonomy fails closed. Readiness never
retro-invalidates. WS196 routing, safe-push gates, Go/Zen identity untouched
(full suites green).
