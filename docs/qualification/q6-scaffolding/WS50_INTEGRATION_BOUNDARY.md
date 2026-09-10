# WS50 Integration Boundary (specification only)

Defined in `tools/q6_scaffolding/integration.py`. This contract is defined
here so Task 2A never writes to WS50-owned paths. If WS50 eventually needs
a different boundary, integration happens later after Coordinator
adjudication. **Do not modify WS50 to prove integration today.**

## Handoff objects (plain data, scaffolding authority)

- `ScaffoldingScenarioInput`: intake/skeleton identity, card hint,
  capability under test, public setup requirements, hidden-info adversary
  requirements, minimum scenario prerequisites, expected decision
  pre-tags, witness requirements, open Rules questions, provenance.
  Contains NO legal options and NO outcome values (structurally enforced
  by `gate.validate_output`).
- `ExpectedDecisionPretags`: pre-tagged kinds, `authority:
  HYPOTHESIS_NON_AUTHORITATIVE`.
- `WitnessRequirements`: witness checklist, same non-authoritative status.

## Runtime side (shape specified, instances forbidden to scaffolding)

- `ObservedRuntimeDecision`: kind, options offered, selection, `authority:
  RUNTIME_AUTHORITATIVE_NATIVE_OPTIONS`. Instances are produced ONLY by
  the WS50 runtime, never by scaffolding. `apply_runtime_observation`
  rejects any observed decision without runtime authority.

## Precedence rule (crucial, enforced in code)

WS50 runtime observations OVERWRITE/CONTRADICT pre-tags without the
scaffolding layer vetoing them. Runtime native options are authoritative.
Scaffolding does not provide legal options.

`apply_runtime_observation` returns a reconciliation report (not a
verdict): confirmed pre-tags, contradicted pre-tags, novel runtime
decisions (extra/fewer/reordered kinds the pre-tags missed), plus the
precedence statement. Contradiction is normal and expected — pre-tags are
hypotheses; the harness discovering a different sequence is the system
working as designed.

## Dependencies on WS50 (integration only, no implementation here)

- `DEPENDENCY_ON_WS50`: live sequence harness consumes
  `ScaffoldingScenarioInput`; runtime emits `ObservedRuntimeDecision`
  sequences per traversed cast; frame-journal witness collection satisfies
  `WitnessRequirements`. All implementation lives on WS50 surfaces owned
  by the WS50 workstream.
- No Task 2A code imports, references by path, or mutates any WS50-owned
  module. Proven by `test_integration_module_touches_no_ws50_paths` and
  pre-commit drift checks.
