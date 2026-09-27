---
name: evidence-seal
description: Produce a structured evidence seal with source identity, commands, tests, runs, artifacts, hashes, and verdicts without fabricating missing results.
---

# Evidence Seal

## Procedure

1. Freeze identities: source SHA and tree, relevant engine pins, config and schema versions.
2. Record every command and test run with outcome: `PASS`, `FAIL`, `UNKNOWN`, or `NOT_RUN`.
3. For each produced artifact record path, size, SHA-256, producing run or test, and
   source SHA. Prefer the deterministic helper `tools/foundry/evidence.py`
   (`artifact-index` and `report` subcommands).
4. List invalidated evidence (with cause) separately from retained evidence (with
   adjudication reason).
5. Emit the seal as structured YAML or JSON next to the artifacts. Missing evidence
   stays `UNKNOWN` or explicitly absent — never inferred, never backfilled.

## Rules

- The seal describes reality; it does not argue for PASS. Adjudication belongs to
  the Coordinator.
- A green workflow alone is not a Qualification PASS; gates must be independently
  adjudicated from the sealed artifacts.
- Preserve exact provenance (source SHA/tree, producing run/test, artifact hashes)
  on every entry. A technical decision recorded from sealed evidence stays
  `CODE_DERIVED` until runtime execution verifies it — sealing must never promote
  `CODE_DERIVED` to `RUNTIME_VERIFIED`.
