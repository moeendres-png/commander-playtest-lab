# Phase 6 evaluation system

## Purpose

The evaluation system prevents the structural simulator and its agents from being treated as self-validating. It separates deterministic implementation checks, invariant testing, reviewed decisions, external rule comparisons, and agent-behavior evaluation.

## Evaluation tiers

### Unit

The unit tier covers:

- plaintext, CSV, XLSX, and local-export import behavior;
- deck size, singleton, color identity, commander and partner legality;
- physical quantity and cross-deck allocation checks;
- commander damage per commander and the 21-damage threshold;
- commander tax progression;
- London mulligan behavior;
- deterministic APNAP ordering for abstract simultaneous triggers;
- seed derivation and replay;
- event sequence, event IDs, and log hashing;
- strict rejection of action proposals that do not match an offered legal action.

Threshold: 100% pass rate.

### Property

Each property match emits state checkpoints after mulligans, after turns, and at game end. The evaluator checks:

- no negative or noninteger zone counts;
- total physical cards equal the expected deck size;
- the card-name multiset hash is unchanged;
- library, hand, battlefield, graveyard, exile, command zone, and commander battlefield remain consistent;
- eliminated players do not emit later action events;
- event sequences are contiguous and contain exactly one start and one final end event;
- identical seed and inputs reproduce match outcomes and event-log hashes independently of worker count;
- illegal action proposals are rejected.

Default threshold: 100% of evaluated properties, at least 250 complete games, and at most 2% aborted property games.

### Golden

Golden cases are reviewed decision fixtures. Each fixture contains a frozen pilot state, legal actions, specialist strategy, pilot strength, and expected action ID. A fixture change must be reviewed like a behavioral contract change.

Default threshold: at least 95% overall and 100% of critical cases.

### Differential

Differential cases are normalized, implementation-independent rule questions. Phase 6 defines:

1. third commander cast costs printed cost plus four generic mana;
2. commander damage from different commanders is not combined;
3. exactly 21 combat damage from one commander is lethal.

External observations are accepted through process adapters configured by environment variable. The absence of XMage or Forge is a blocked release gate, not a skipped success.

Release threshold: at least three real external cases and a 100% match rate.

### Agent evaluations

Agent trajectories are scored for:

- correct required-tool coverage;
- no reference to tools that were not actually executed;
- correct treatment of failed or approval-required outputs;
- explicit disclosure of model and data uncertainty;
- strict separation of `structural_model_estimates` from empirical or real win rates;
- no confirmed recommendation without paired comparison, holdout evaluation, and upgrade validation.

Default thresholds are 95% for tool choice, interpretation, and uncertainty, and 100% for fabrication prevention, model/real separation, and validation-before-recommendation.

## Acceptance levels

### Local acceptance

Requires all local unit, property, golden, and agent gates. It permits continued local development and the next project phase.

### Full release acceptance

Requires local acceptance plus real XMage or Forge differential execution. Phase 6 must not report full release acceptance while external cases are blocked.

## External adapter contract

The configured command may contain `{input}` and `{output}` placeholders.

Input:

```json
{
  "case_id": "...",
  "description": "...",
  "input_state": {}
}
```

Required output:

```json
{
  "backend_version": "...",
  "normalized_output": {}
}
```

Only the fixture's declared comparison keys are compared. Raw backend logs remain available for audit but are not interpreted as normalized truth without the adapter.

## Data and log separation

- deterministic game events: `data/runs/phase6_evals/property/`;
- evaluation result: `data/runs/phase6_evals/phase6_eval_result.json`;
- reviewed fixtures: `data/evals/`;
- optional OpenAI eval dataset: `data/evals/agent/openai_eval_dataset.jsonl`.

No evaluator changes a canonical Google Drive file.
