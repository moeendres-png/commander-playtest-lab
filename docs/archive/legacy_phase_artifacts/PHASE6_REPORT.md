# Phase 6 – Evaluation system report

Generated: `2026-08-04T16:36:03.143151+00:00`

## Scope

Phase 6 implements a release-gated, multi-tier evaluation system for the local Commander Playtest Lab. The current Korvold and RogShai snapshots remain unchanged. No Google Drive source was read or modified.

All simulator-derived results retain the mandatory label `structural_model_estimates`.

## Implemented components

- strict action-proposal validation against engine-offered legal actions;
- deterministic APNAP ordering and resolution helpers for simultaneous abstract triggers;
- state checkpoints with zone totals and card-multiset hashes;
- unit, property, golden, differential, and agent-evaluation models and runners;
- configurable acceptance thresholds in `config/evals.yaml`;
- reviewed fixtures under `data/evals/`;
- CLI command `commander-lab eval-phase6`;
- external XMage/Forge process-adapter contract;
- JSONL export for a separate OpenAI custom-eval data source.

## Test inventory

### Unit tests

The unit suite covers card and tabular import, deck legality, physical quantities and simultaneous allocation, commander damage, commander tax, London mulligans, abstract trigger order, seed reproducibility, event-log integrity, and legal-action validation.

### Property tests

State checkpoints verify:

- no negative zone counts;
- no disappearing or duplicated cards;
- library plus all other zones remain equal to the expected deck size;
- the card-name multiset remains unchanged;
- eliminated players do not act;
- identical seeds reproduce outcomes and log hashes independently of worker count;
- illegal proposals are rejected.

### Golden tests

Nine reviewed decisions cover generic urgent interaction and rebuilding, supported or unsupported Korvold casts, Korvold table payoffs, Rograkh as a resource, protected Ishai development, Jeska finish windows, and commander-damage target selection.

### Differential tests

Three normalized rule fixtures are defined:

1. commander tax on the third cast;
2. commander damage from different commanders remains separate;
3. 21 damage from one commander is lethal.

The external process-adapter contract is tested with a fake backend. No XMage or Forge executable is installed or configured in this runtime, so the three real comparisons are correctly reported as `blocked` rather than passed.

### Agent evaluations

Five trajectories cover deck validation, matchup analysis, upgrade validation, commander-denial analysis, and real-playtest calibration. Scoring checks tool selection, evidence grounding, interpretation, uncertainty, model/real separation, and validation before recommendation.

## Evaluation result

| Tier | Total | Passed | Failed | Skipped | Blocked | Pass rate |
|---|---:|---:|---:|---:|---:|---:|
| unit | 1 | 1 | 0 | 0 | 0 | 100.00% |
| property | 258 | 258 | 0 | 0 | 0 | 100.00% |
| golden | 9 | 9 | 0 | 0 | 0 | 100.00% |
| differential | 3 | 0 | 0 | 0 | 3 | 0.00% |
| agent | 5 | 5 | 0 | 0 | 0 | 100.00% |

The property tier contains 256 complete structural games across goldfish, three-player, four-player, and five-player fixtures, plus seed-replay and illegal-action cases. No property game aborted.

- **Local acceptance:** `true`
- **Full release acceptance:** `false`

Full release acceptance is intentionally false until actual XMage or Forge differential observations satisfy the external gates.

## Automatic acceptance gates

| Gate | Measured | Threshold | Passed |
|---|---:|---:|:---:|
| `unit_pass_rate` | 1.0000 | 1.0000 | yes |
| `property_pass_rate` | 1.0000 | 1.0000 | yes |
| `minimum_property_cases` | 256 | 250 | yes |
| `maximum_aborted_property_games_rate` | 0.0000 | 0.0200 | yes |
| `golden_pass_rate` | 1.0000 | 0.9500 | yes |
| `golden_critical_pass_rate` | 1.0000 | 1.0000 | yes |
| `differential_match_rate` | 0.0000 | 1.0000 | no |
| `minimum_external_differential_cases` | 0 | 3 | no |
| `agent_tool_choice_rate` | 1.0000 | 0.9500 | yes |
| `agent_no_fabrication_rate` | 1.0000 | 1.0000 | yes |
| `agent_interpretation_rate` | 1.0000 | 0.9500 | yes |
| `agent_uncertainty_rate` | 1.0000 | 0.9500 | yes |
| `agent_model_real_separation_rate` | 1.0000 | 1.0000 | yes |
| `agent_validation_before_recommendation_rate` | 1.0000 | 1.0000 | yes |

## Release interpretation

Local acceptance means the implementation may proceed to the next development phase. It does not mean:

- the structural model is a full MTG rules engine;
- model estimates are empirical win rates;
- an upgrade is validated without paired and holdout testing;
- the external rules gate has passed.

A full release candidate requires at least three real XMage or Forge observations and a 100% normalized match rate for the configured critical cases.

## Commands

```bash
python -m pytest -q
commander-lab eval-phase6 --iterations-per-scenario 64 --workers 2 --seed 20260804 --root .
```

Optional external adapters:

```bash
export COMMANDER_LAB_FORGE_DIFFERENTIAL_CMD='python adapter.py --input {input} --output {output}'
export COMMANDER_LAB_XMAGE_DIFFERENTIAL_CMD='python adapter.py --input {input} --output {output}'
```

## Known boundary

The current agent-evaluation run is deterministic and offline. It evaluates stored trajectories and report contracts. The JSONL dataset can be used by a separately authorized OpenAI eval workflow, but Phase 6 did not spend API tokens or claim a live-model score.
