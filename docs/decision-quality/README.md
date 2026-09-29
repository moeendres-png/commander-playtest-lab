# docs/decision-quality/ — navigation (orphaned provenance)

**This directory is orphaned.** It is not a near-twin of `docs/decision_quality/`. That
directory is the live one. See "Adjudication" below.

Throughout this file, `AGENTS.md` means the repository-root `AGENTS.md`
(`../../AGENTS.md` from here). There is no `AGENTS.md` inside this directory.

## Adjudication

Measured at `origin/main` (2026-09-29), this directory has **zero** references from any
workflow, source module, test, or config. Its one apparent referrer,
`MODEL_RESOLUTION_MEASUREMENT_PROTOCOL.md`, is mentioned only in the README written by a
previous hygiene audit — nothing consumes it. All four files were last changed 2026-08-15.

By contrast `docs/decision_quality/` holds `MODEL_PRECISION_POLICY_CURRENT.md`, which is
read by a CI gate (`.github/workflows/model-resolution-measurement.yml:65-72` asserts three
exact retirement markers in it) and by production code
(`src/commander_lab/whole_deck/optimizer_v2_decision_runtime.py:49`).

**Verdict: orphaned provenance.** Retained, not deleted. A rename or move would rewrite
historical paths, which `docs/foundry-execution/README.md` forbids
("Do not rewrite historical evidence to look current"). This README records the finding so
the question does not have to be re-derived.

## Contents

- `DECISION_QUALITY_1.22.0.md` — an epistemic integration layer on top of Optimizer-v2.
  By its own text its purpose is *"not to make the simulator more authoritative than it is"*,
  but to prevent a false impression of authority. Superseded in scope by `CHANGELOG.md`
  1.24.0, which reclassified Structural Simulation and the Tactical Oracle as
  diagnostic/test systems without official deck-decision authority.
- `DECISION_QUALITY_GAP_MATRIX.json` — machine-readable gap matrix for the above.
- `MODEL_RESOLUTION_MEASUREMENT_PROTOCOL.md` — a measurement protocol, version
  `model-resolution-measurement-0.1.0`. No consumer. The *implementation* it describes was
  preserved as provenance by tests
  (`tests/unit/test_model_resolution_measurement.py` and siblings) via the
  `model-resolution-measurement` workflow, not by this document.
- `CONCURRENT_WORK_RECONCILIATION.md` — a 2026-08-15 local audit snapshot pinned to a
  specific `main` SHA. Historical.

## If you are looking for the current model-precision policy

It is `docs/decision_quality/MODEL_PRECISION_POLICY_CURRENT.md`, which is machine-enforced.
Do not use this directory for that.
