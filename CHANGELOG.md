# Changelog

## 1.2.0 - 2026-08-06

- Added a safe Primer-to-Pilot rule DSL with fixed fields and operators; primer text is never executed.
- Added Markdown, plaintext, JSON, and manually curated primer imports.
- Added source-preserving, deck-hash- and format-scoped immutable policy overlays.
- Added conflict detection, explicit resolution strategies, alternative policies, and manual activation.
- Added seven structured toolserver functions for primer import, extraction, validation, compilation, comparison, evaluation, and conflict reporting.
- Added 14 active curated Korvold/RogShai rules and eight disabled automatic candidates.
- Added Golden, Tactical-Oracle, replay-coverage, security, provenance, and no-deck-mutation tests.
- External rules-engine validation and real-playtest calibration remain pending.


## 1.0.1 - 2026-08-05

- Run the Phase-10 API self-test by default so clean repository and Git-bundle restores do not depend on an untracked API-demo artifact.
- Accept both versioned API evidence and the in-process self-test evidence shape.
- Close all contract-test subprocess pipes explicitly to prevent order-dependent suite hangs.
- Preserve all external-engine and deck-change safety gates.

## 0.8.6 - 2026-08-05

- Added Phase 8.6 trust-boundary audit and regression tests.
- Prevented legacy/mock bridges from being promoted to external rules validation.
- Corrected Phase 8.5 contract coverage and readiness semantics.
- Added atomic artifact writes, run manifests, run verification and quarantine.
- Added SQLite integrity, migration, backup, restore and sealed experiment designs.
- Added scenario fixtures, replay debugger, structured logging and metrics.
- Added architecture-boundary, deterministic fuzz and mutation-guard tests.
- Added CI and an explicitly failing-until-real GitHub Actions XMage integration workflow.
- External engine validation remains pending.

## 0.9.0 - Phase 9 real playtest calibration

- Added versioned append-only real playtest datasets.
- Expanded CSV/XLSX/JSON import to all Phase-9 observations.
- Added sealed chronological or stable-hash train/validation splits.
- Added real-versus-structural distribution comparisons and bootstrap intervals.
- Added conservative validation-gated calibration profiles with no automatic application.
- Added Korvold draw, Ishai peak-power and archenemy metrics to structural outputs.
- Added Phase-9 CLI commands, template, documentation and validation runner.
- External rules-engine validation remains pending.
