# Phase 12.10 – Deck, pilot and model diagnostics completion revision

Status: `decision_diagnostics_ready_with_limitations`

Package revision: `1.10.1`.

The diagnostic layer now derives per-card and per-pilot instrumentation from actual immutable Structural Simulator event logs. It records opening hands, mulligans, draws, plays, counters/no-value outcomes, removals, final-hand dead/unplayable observations, play turns, mana efficiency, package partners, pilot choices and alternative lines. Counterfactual results can be attached to the same dataset.

The classifier retains ten failure classes, evidence and counterevidence, sensitivity fields, package dependency, confidence, a next discriminating test and a conservative cut release gate. No diagnosis is inferred from one win-rate value.

The integrated ten-step smoke now executes all ten stages in one run and stores source paths, hashes and validation levels for each step. It does not merely load prepared outputs.
