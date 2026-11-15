# docs/decision_quality/ — navigation

**This directory holds the policy record.** It is not a near-twin of `docs/decision-quality/`;
that directory is orphaned. See "Relationship" below.

## Historical machine-enforcement note (retired on `main`)

`MODEL_PRECISION_POLICY_CURRENT.md` records the retirement of the legacy scalar model-precision
hard gate. Both consumers documented in the 2026-09-29 audit have since been retired and removed
from `main`:

- `.github/workflows/model-resolution-measurement.yml` — previously checked three retirement
  markers (`The former single hard gate`,
  `is retired for candidate promotion, elimination and equivalence decisions`,
  `instead of one scalar resolution number`).
- `src/commander_lab/whole_deck/optimizer_v2_decision_runtime.py` — previously bound
  `PRECISION_POLICY_PATH`.

**This is the historical documented exception to `AGENTS.md` §3.** When created, `..._CURRENT` was
corroborated by active CI/runtime consumers. Keep the file intact as a policy record, and do not
use `..._CURRENT` naming for new documents.

## Relationship to `docs/decision-quality/` (hyphen)

The two directories differ only by separator, and until now nothing recorded which was which.
Measured at `origin/main`:

| | `docs/decision_quality/` (this one) | `docs/decision-quality/` (hyphen) |
|---|---|---|
| Content | 2 documents | 4 files |
| Referenced by workflows | 2 | 0 |
| Referenced by `src/` | 1 | 0 |
| Referenced by tests/config | 0 | 0 |
| Last content change | 2026-08-20 / 08-21 | 2026-08-15 |

**Verdict: this directory is current and load-bearing; the hyphen directory is orphaned
provenance.** Neither directory is renamed or deleted here — a rename would rewrite historical
provenance paths, which `docs/foundry-execution/README.md` forbids. This README records the
adjudication instead, so the next session does not have to re-derive it.

`SIMULATION_FIDELITY_124_CLOSEOUT_CURRENT.md` — a 2026-08-21 milestone closeout. Its `PASS`
is a statement about that milestone at that time; it is not a current project-level PASS and
must not be cited as one. It has no machine consumer.
