# docs/decision_quality/ — navigation

**This directory is the live one.** It is not a near-twin of `docs/decision-quality/`;
that directory is orphaned. See "Relationship" below.

## The one file here that is machine-enforced

`MODEL_PRECISION_POLICY_CURRENT.md` is a **contractual, machine-enforced** document, not
historical prose. Two independent consumers depend on it:

- `.github/workflows/model-resolution-measurement.yml:65-72` — the `Verify 2F replaces the
  legacy hard gate` step reads the file and fails the job unless all three retirement
  markers are present: `The former single hard gate`,
  `is retired for candidate promotion, elimination and equivalence decisions`, and
  `instead of one scalar resolution number`.
- `src/commander_lab/whole_deck/optimizer_v2_decision_runtime.py:49` — production code
  binds it as `PRECISION_POLICY_PATH`.

The file is also a `paths:` trigger in `model-resolution-measurement.yml:17` and
`optimizer-v2-acceptance.yml:13`, so editing it wakes both gates.

**This is the documented exception to the project-wide rule.** `AGENTS.md` §3 says a
filename containing `CURRENT` proves nothing about freshness. That rule is correct as a
general default, and it is exactly why the `MODEL_PRECISION_POLICY_CURRENT.md` name needed
independent corroboration. Here the corroboration exists: a CI gate asserts on the file's
content, and production code resolves it. Do not use this file as precedent for naming other
documents `..._CURRENT`; use it as precedent for *verifying* a `..._CURRENT` claim.

**Editing constraint.** The three retirement markers are load-bearing. Removing or rewording
any of them fails the `model-resolution-measurement` gate. Change the policy only together
with that gate, in the same change.

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
