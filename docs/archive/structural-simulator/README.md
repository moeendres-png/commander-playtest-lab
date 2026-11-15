# docs/archive/structural-simulator/

Provenance only; not current instruction. See `../README.md`.

**What this folder holds.** The removed structural simulator layer (counterfactual replay, diagnostics, structural estimates and their limits). Entries keep their path under `docs/`:

- `counterfactual`
- `diagnostics`
- `MODELING_IMPROVEMENT_REPORT.md`
- `PILOT_GOLDEN_SCENARIOS.md`
- `CARD_COVERAGE_CURRENT.md`
- `known_limitations.md`
- `validation_levels.md`

**Why archived.** The structural simulator layer was removed: counterfactual replay and diagnostics with Round 3, the batch, scheduling, fidelity, telemetry and validation modules with Round 4 (the commit after the one named below); engine/structural keeps only small calibration helpers. Structural estimates are no longer a product output; games run on the real engine.

**Last commit at which the described code existed:** `5d00bec5d6d2f625b5a3c4160fac820f0e497f00`.

Contents are byte-identical to what they were under `docs/`; links inside them are history
and are not maintained.
