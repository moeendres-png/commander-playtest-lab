# Commander Playtest Lab – Decision Quality 1.22.0

## Purpose

Decision Quality 1.22.0 is an epistemic integration layer on top of Optimizer-v2. Its purpose is
not to make the simulator more authoritative than it is. Its purpose is to prevent precise or
adaptive Structural results from being interpreted more strongly than their inputs, model fidelity,
resolution and robustness support.

All simulation-derived decisions remain `structural_model_estimates`.

## Strict decision order

A strong decision must pass the following gates in order:

1. **Comparison validity** – legality, physical availability, execution and pairing contracts pass.
2. **Domain/Input Validity** – the opponent/scenario evidence is adequate for the declared question.
3. **Structural Fidelity for the Question** – decision-material real card functions are represented
   or explicitly approximated at an acceptable level.
4. **Tactical dependency** – if the distinction requires rules/timing/legal-action fidelity beyond
   the Structural Model, route to bounded Tactical or validated external-rules evidence.
5. **Model Informativeness** – `MODEL_INFORMATION_LIMIT` blocks effect/equivalence claims before
   additional seed work.
6. **Model Resolution** – synthetic calibration alone is insufficient. A current same-metric
   Structural variability profile must be measured for a strong resolution-based decision.
7. **Effect / equivalence** – the interval must clear measured Structural resolution, not merely a
   legacy fixed threshold.
8. **Robustness axes** – declared opponent, pilot/Mulligan, mana, commander-denial/rebuild,
   lower-tail/worst-case and closure checks remain separate axes; they are not collapsed into a
   universal score.
9. **Evidence partition** – exploratory evidence can nominate a candidate but cannot strongly
   promote/eliminate it. Fresh confirmatory evidence is required. A `FINAL` decision additionally
   requires authorized sealed holdout confirmation.

## Domain/Input Validity

Three scopes are explicit:

- `OFFICIAL_BASELINE`
- `LOCAL_CURRENT_MATCHUP`
- `STRUCTURAL_STRESS_TEST`

A verified full local deck with no unresolved/synthetic slots can support the next strong-decision
gate. An official precon is adequate for an official-baseline question, but without direct evidence
of the local current physical list it is limited for a local-current-matchup claim. Partial,
reported, inferred, synthetic-completion and unknown evidence remain visible and cannot be promoted
to observation.

### Ambiguity sets

When a local opponent is incomplete, use `OpponentAmbiguitySet`: several provenance-bound plausible
variants with **no probability weights**. This implements robust scenario reasoning without
inventing opponent frequencies. Public archetype/deck data may be attached only as
`external_archetype_prior` provenance and remains synthetic with respect to the real local deck.

For current project truth this matters especially for Morcant and Cosmic. Their incomplete real
lists must not become high-confidence local causal evidence merely because a Structural comparison
has a narrow interval.

## Question-specific Structural Fidelity

The available classes are exactly:

- `HIGH_FIDELITY_FOR_QUESTION`
- `MEDIUM_FIDELITY_FOR_QUESTION`
- `LOW_FIDELITY_FOR_QUESTION`
- `UNSUPPORTED_FOR_QUESTION`

The report records required, represented, approximated and unsupported functions separately. A card
may have complete Oracle facts while still being structurally unsupported for the question being
asked. Structural semantic coverage is therefore not equivalent to rules-engine fidelity.

## Model Information Limit

`MODEL_INFORMATION_LIMIT` is an upstream decision gate. It is evaluated before positive-effect,
negative-effect and equivalence claims. If the model is saturated, ceiling-compressed or broadly
non-separable, the next action is to diagnose a different metric/evidence axis rather than to
implicitly assume that more seeds reveal the truth.

## Model Resolution

Optimizer-v2 synthetic calibration is retained and reused. Decision Quality does not create a
second calibration subsystem.

A synthetic SESOI establishes decision-logic behavior on known-direction fixtures. It does **not**
by itself establish the current Structural simulator's resolution. `ModelResolutionProfile`
therefore has two states:

- `NEEDS_MEASUREMENT`: calibrated SESOI exists but no same-metric Structural variability axes have
  been supplied;
- `MEASURED`: at least one declared same-metric Structural variability axis is measured.

The effective Structural resolution is conservatively no smaller than the calibrated SESOI and no
smaller than any supplied comparable Structural spread. This is model resolution, not empirical
Commander effect size.

Recommended bounded technical axes include null/near-null seed blocks, seat assignment, scenario,
pilot, tie/compression and other preregistered same-metric conditions. The protocol must not consume
confirmatory or sealed-holdout evidence.

## Seedblock epistemics

Repeated independent seeds under the same model, same input model and same metric are classified as:

`PRECISION_ONLY_SAME_MODEL`

They can reduce Monte Carlo error. They are not an independent validation axis and do not reduce
input uncertainty or Structural model discrepancy. A changed structural evidence axis is marked
separately but is still not automatically empirical replication.

## Failure and closure diagnostics

Existing failure-cause diagnostics remain in force. Decision Quality adds resource-to-closure
signals:

- `RESOURCE_GAIN_WITH_CLOSURE`
- `RESOURCE_GAIN_WITHOUT_CLOSURE`
- `COMMANDER_DAMAGE_STALL`
- `VALUE_ENGINE_STALL`
- `MANA_STALL`
- `RECAST_STALL`
- `INTERACTION_OVERLOAD`

Current Structural telemetry directly supports only a subset. Missing `unused_mana`,
`stranded_spells`, `recast_affordability` and `restore_pressure_turns` are explicitly reported as
`UNSUPPORTED_BY_STRUCTURAL_MODEL`; no proxy is silently invented. `RECAST_STALL` therefore remains
unidentified until direct supporting telemetry exists.

## Experiment evidence targets

The causal/experimental vocabulary is:

- `CUT`
- `ADD`
- `REPLACEMENT`
- `PACKAGE`
- `CONDITIONAL_EFFECT`
- `INTERACTION`

A normal one-for-one card swap supports `REPLACEMENT` evidence. It does **not** independently prove
that the removed card is bad and the added card is good. Independent cut/add claims require an
explicit neutral isolation control. Package, condition and interaction interventions retain their
own narrower evidence target.

## Multi-axis robust decisions

Decision Quality does not introduce a universal scalar deck score. Existing objective/Pareto
primitives remain authoritative. Robust decisions receive declared pass/fail axes so that mana,
pilot, opponent, commander-denial, rebuild, lower-tail and closure disagreements remain visible.
Any failed declared axis returns `ROBUSTNESS_LIMIT` rather than being averaged away.

## Structural representation invariant

Every `StructuralDeckProfile` must contain:

- at least one unique commander identity;
- a base cost for each commander;
- exactly one `StructuralCardProfile` for every commander.

Production Commander profiles additionally require exactly 100 profiles including commanders. For
RogShai this implies 2 commander profiles plus 98 library profiles. The simulator may remove
commanders from the initialized library, but their structural profiles must exist in the deck
representation. Project loading fails closed on this contract.

## Research basis and interpretation

This policy uses simulation-methodology principles rather than importing effect sizes from unrelated
fields. In particular:

- Wu, Wang & Zhou, *Data-Driven Ranking and Selection Under Input Uncertainty*, Operations Research
  72(2), DOI `10.1287/opre.2022.2375`;
- Chick, *Input Distribution Selection for Simulation Experiments: Accounting for Input
  Uncertainty*, Management Science 47(6), DOI `10.1287/mnsc.47.6.742.9814`;
- distributionally robust selection literature using ambiguity sets of plausible inputs;
- NIST verification, validation and uncertainty-quantification guidance.

These sources justify separating input uncertainty, stochastic precision and model validity. They do
not validate the Structural Simulator as a real Commander rules engine or supply empirical winrate
calibration.

## Protected-state contract

Decision Quality 1.22.0 performs no automatic canonical mutation. In particular:

- no new official RogShai optimizer campaign is started by this refactor;
- canonical RogShai is unchanged;
- inventory and physical allocations are unchanged;
- purchase decisions are unchanged;
- opponent observation evidence is unchanged;
- Kaervek remains the frozen opponent snapshot;
- Tactical Oracle remains distinct from an external rules engine;
- no XMage/Forge result is called external-engine evidence unless actually executed and validated.
