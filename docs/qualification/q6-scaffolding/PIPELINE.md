# Q6 Actual-Card Scaffolding Pipeline

Mechanical qualification *preparation* only. This pipeline automates intake,
parsing, capability clustering, valueless skeleton generation, review
queues, and manifests for actual cards. It is structurally incapable of
awarding card behavior PASS, qualification credit, or coverage promotion.

- Tooling surface: `tools/q6_scaffolding/`
- Tests: `tests/q6_scaffolding/` (179 tests, all green)
- Grammar registries: `verb_registry.json` (198 verbs),
  `trigger_mode_registry.json`, `static_mode_registry.json`
  (76 static + 22 ability modes), `unsupported_registry.json` — all
  versioned, provenance-bearing, generic by construct (see
  `PARSER_CURATION_REPORT.md`)
- Bounded validation sample: `tests/q6_scaffolding/fixtures/` (55 real
  Forge card scripts pinned to `Card-Forge/forge@8c7e9afb`, per-file
  sha256 in `inputs.json`; stratified per `VALIDATION_SAMPLE.md`)
- Evidence: `docs/qualification/q6-scaffolding/evidence/` (full-corpus
  before/after inventories, before/after metrics, sealed unsupported
  registry, sample queues/manifest/routing table)

Evidence class of everything produced here: SYNTHETIC (tooling output).
Authoritative behavior truth comes only from the Rules Core plus official
Magic rules/Oracle/rulings via runtime qualification, which this package
never performs.

`BEHAVIOR_CREDIT = 0` · `COVERAGE_PROMOTION = FALSE` · `FULL107 = NOT_RUN`
· `FORGE_RUNTIME = NOT_RUN` · `XMAGE_RUNTIME = NOT_RUN`
· `ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Subcommands (composable, machine-readable JSON)

```text
q6-scaffolding intake --inputs <spec> [--corpus-root <dir>] --out <intake.json>
q6-scaffolding classify --in <intake.json> --out <classified.json>
q6-scaffolding generate-skeletons --in <classified.json> --out <skel.json>
q6-scaffolding build-review-queues --in <skel.json> --out <queues.json>
q6-scaffolding build-manifest --in <skel.json> [--queues <queues.json>]
    [--configuration <config.json>] [--manifest-id <id>] --out <manifest.json>
q6-scaffolding validate --manifest <manifest.json> [--queues <queues.json>]
```

Run via `PYTHONPATH=tools python3 -m q6_scaffolding.cli <subcommand>`.
Stdout carries a JSON summary; artifacts go to `--out` files only.

Every subcommand fails closed (exit 2, no partial output) on: missing
source-lock metadata, invalid schema, hash mismatch, duplicate or
conflicting identities, promotion/contamination fields, ambiguous
provenance where required, or stage-order violations.

## 2. Required evidence state model

Per-record lifecycle (mutually exclusive; see `tools/q6_scaffolding/states.py`):

```text
INTAKE_ONLY -> PARSED -> STRUCTURED -> SKELETON_GENERATED
    -> MANUAL_REVIEW_REQUIRED | RULES_ADJUDICATION_REQUIRED
     | UNSUPPORTED | AMBIGUOUS | READY_FOR_RUNTIME_QUALIFICATION
```

Routing priority (first match wins): AMBIGUOUS > UNSUPPORTED >
registry-flagged curator-review verbs > unknown-grammar tripwires >
RULES_ADJUDICATION_REQUIRED > MANUAL_REVIEW_REQUIRED >
READY_FOR_RUNTIME_QUALIFICATION.

There is NO state equivalent to runtime behavior PASS.
`READY_FOR_RUNTIME_QUALIFICATION` means only that mechanical/scenario
prerequisites are ready for an authoritative runtime qualifier. It does
NOT mean the card works.

## 3. Structural PASS-impossibility (hard gate)

Two mechanisms combine (`tools/q6_scaffolding/gate.py`):

1. **Exclusion by construction**: no scaffolding schema contains a
   behavior-credit field (`behavior_pass`, coverage, qualification,
   expected-outcome, legal-option, PASS-verdict keys do not exist in any
   dataclass or emitted dict). There is nowhere to store a PASS.
2. **Fail-closed validation**: `reject_promotion_fields` screens every
   external input (inputs spec, operator metadata, configuration);
   `validate_output` screens every emitted artifact. Violations raise
   `PromotionRejected`; nothing is stripped-and-continued.

Concretely rejected: `behavior_pass=true` smuggled in metadata; fixtures
claiming PASS; XMage `expected`/`assert` outcome keys; engine-AI driver
markers (`aiPlayPriority`); harness hooks (`runCode`, `rollbackTurns`);
coverage/qualification keys. The sole documented exemption is
`expected_hash`, a content-integrity sha256 used to verify inputs — not a
behavioral outcome.

## 4. Determinism / reproducibility

Same corpus pin + input set + tool version + configuration (+ seed, if
sampling is used) reproduces intake IDs, capability tags, skeleton
identities, queue assignments, manifest ordering, and manifest hashes.
No timestamps, no wall-clock, no randomness in outputs. Proven by
`test_manifest_reproducible_across_runs` and the committed evidence
manifest (`manifest_hash` recomputable via `validate`).

## 5. D2 / D3 reuse (bounded, provenance-bearing)

- **D3** (`moeendres-png/mage@a766f900`, `BUILD_CLEAN_ROOM_EQUIVALENT`,
  SYNTHETIC, zero behavior credit): the Forge card-script parser
  (`tools/q6_scaffolding/forge_parser.py`, `q6-forge-parser-0.1.0`) is a
  project-authored port of the D3 clean-room prototype
  `d3q6-cleanroom-0.1.0` (written from the public Forge wiki format
  description plus observed corpus files). No Forge GPL, Manabrew AGPL,
  or third-party implementation code is copied, linked, or embedded.
  `AI:` hint lines are allowlisted as benign metadata per the D3 §5
  decomposition; verb/mode tables stay minimal so gaps route to review.
  Forge scripts remain external pinned INPUT with retained provenance.
- **D2** (`bf2c4711`, `BOUNDED_REUSE`): XMage corpus reuse is
  input-only. The intake gate enforces D2's validator rules (no
  `expected`/`assert`/outcome keys, no engine AI, no harness hooks);
  checklists are valueless witness *requirements* with
  `authoritative_source: rules_core_runtime`; per-record MIT-style
  provenance blocks are stamped at intake. Expected behavioral assertions
  must be re-derived later from official rules/Oracle/rulings plus
  authoritative runtime evidence — the pipeline marks this mechanically
  (open `rules_questions` with `resolving_authority:
  human_coordinator_rules_adjudication`).

## 6. Capability clustering and pre-tags

Seed taxonomy (16 families, extensible only via explicit
provenance-bearing `register_family`): TARGET_SELECTION, MODAL_CHOICE,
MANA_PAYMENT_CHOICE, X_COST_VALUE, ADDITIONAL_ALTERNATIVE_COST,
REPLACEMENT_EFFECT, TRIGGERED_CHOICE, COMBAT, COMMANDER_MECHANIC,
MULTIPLAYER_OPPONENT_SELECTION, HIDDEN_INFORMATION, RANDOMNESS,
COPY_CONTROL, LAYER_CHARACTERISTIC, ZONE_CHANGE, SBA_SENSITIVE. COMBAT
and LAYER_CHARACTERISTIC are assigned from Task 2B (combat-restriction
statics/combat verbs; characteristic-setting verbs).

Decision-surface pre-tags are HYPOTHESES ONLY (D4c: one mechanic != one
callback). Every pre-tag carries `authority:
HYPOTHESIS_NON_AUTHORITATIVE` and `truth_source: rules_core_runtime`.
The live harness may discover additional, fewer, differently ordered, or
no decisions. Pre-tags are never legal-action generation; see
`WS50_INTEGRATION_BOUNDARY.md`.

## 7. Skeletons, witnesses, queues

Skeletons (`q6.scenario-skeleton.v1`) specify setup prerequisites,
non-authoritative pre-tags, witness requirements (all `evidence: null`
until a runtime qualifier collects them), and open Rules questions. They
never fabricate life totals, permanent states, legal-option lists,
outcome values, or PASS criteria.

Queues (deterministic; stable item IDs; actionable next actions, never
verdicts): MANUAL_SCENARIO_REVIEW, RULES_ADJUDICATION,
UNSUPPORTED_CAPABILITY, AMBIGUOUS_PARSE, PROVENANCE_REVIEW,
RUNTIME_QUALIFICATION_READY.

Failure-clustering integration wraps (imports, never modifies)
`tools/foundry/cluster_failures.py` for scaffolding-side gaps only
(parser failures, unsupported tags, scenario-generation gaps,
runtime-preparation gaps), all `verdict: UNKNOWN`, all `kind:
scaffolding/*` — separate from engine/runtime behavior failures, whose
truth is never touched.

## 8. Ownership

This surface is self-contained under `tools/q6_scaffolding/`,
`tests/q6_scaffolding/`, and this doc directory. It modifies no
WS50-owned path (Forge runtime/provider/bootstrap, decision transport,
option binding, live sequences, callbacks, observations, frame
journal/replay, live-game construction, WS48-derived surfaces), no
`qualification/providers/forge/**`, no bridge code, no `vendor/**`, no
WS47 books/denominator, no coverage truth, no production simulator code.
`tools/foundry/cluster_failures.py` is imported read-only, never edited.
Drift-checked against the WS50 worktree before every checkpoint commit.
