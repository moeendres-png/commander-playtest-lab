# Phase 9: Real playtest calibration

## Scope

Phase 9 imports empirical game records, compares them with structural simulation distributions,
and creates a versioned calibration profile. It does not modify canonical deck lists, inventory,
Google Drive files, or engine defaults.

The external rules engine is still pending. Real playtests are empirical observations; structural
comparisons remain `structural_model_estimates`. Neither source is relabelled as
`external_rules_engine`.

## Required recording structure

Use one row per player and repeat the game-level fields for every row. The template is:

`data/playtests/playtest_template.csv`

Core fields include deck and version, opponents represented by the other participant rows, pod size,
seat, starting player, mulligans, opening-hand lands, land and ramp development, commander casts and
removals, independent draw engines, board wipes, rebuilds, placement, win axis, loss causes, dead
cards, and sequencing errors.

Korvold rows may record `korvold_cards_drawn`. RogShai rows may record `ishai_peak_power` or a JSON
map in `ishai_power_by_turn`.

List-valued fields use `|` or `;`. This avoids splitting Magic card names that contain commas.

## Import

```bash
commander-lab ingest-playtest data/my-session.csv \
  --dataset-version session-2026-08 \
  --root .
```

CSV, XLSX and JSON are read-only. Evidence is stored append-only under:

`data/playtests/datasets/<dataset-version>/`

The same `game_id` may be reimported only when its semantic content is identical. A changed game
requires a new dataset version. This prevents silent rewriting of evidence.

## Train and validation split

The first calibration seals a split in the dataset manifest. The default is chronological 70/30.
A stable-hash split is also supported. Once sealed, the split cannot be changed in the same dataset
version. Create a new dataset version to change split policy.

Training games estimate candidate calibration factors. Validation games are an internal holdout and
are never used to fit those factors. This internal holdout is not independent external confirmation.

## Structural reference

Generate structural reference batches with event logs:

```bash
commander-lab run-structural-batch \
  --deck korvold/current \
  --deck rogshai/current \
  --deck synthetic/aggro \
  --deck synthetic/control \
  --iterations 500 \
  --output data/runs/calibration-reference \
  --root .
```

Then calibrate:

```bash
commander-lab calibrate-playtests \
  --dataset-version session-2026-08 \
  --simulation-result data/runs/calibration-reference/structural_results.json \
  --korvold-version current-2026-08-05 \
  --rogshai-version current-2026-08-05 \
  --policy config/calibration_policy.json \
  --root .
```


When a dataset contains more than one version of Korvold or RogShai, calibration is blocked for that deck unless the target version is selected explicitly with `--korvold-version` or `--rogshai-version`. This prevents observations from different deck configurations being pooled silently.

## Evidence thresholds

The versioned policy is loaded from `config/calibration_policy.json` by default. The resolved policy contents are hashed into every calibration report:

- at least 20 training games;
- at least 8 validation games;
- at least 12 training observations for a metric;
- at least 5 validation observations for a metric;
- a bootstrap training-difference interval that excludes zero;
- at least 5% validation-error improvement.

No parameter is inferred from one game. Sparse metrics remain `insufficient_evidence`.

## Calibration outputs

Outputs are stored under:

`data/playtests/calibrations/<calibration-id>/`

They include JSON, Markdown and a non-applied calibration profile. Accepted values are not written to
engine configuration automatically. Applying a profile is a separate future, explicit operation.

## Compared distributions

Phase 9 compares, per current deck where available:

- game length;
- first commander cast;
- removal events;
- board wipes;
- Ishai peak power;
- Korvold-triggered draws;
- archenemy frequency;
- win axes;
- placements.

Missing observations are reported rather than imputed.

## Validation smoke test

```bash
commander-lab validate-phase9 --root .
```

This uses a clearly labelled synthetic fixture solely to test the pipeline. It must produce
`insufficient_evidence` and may not be cited as real calibration evidence.
