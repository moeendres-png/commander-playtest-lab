# Roadmap J-P2 Modeling & Data Quality Report

Status: `DEVELOPMENT_CANDIDATE_FROZEN_PENDING_FINAL_GATES`

Start baseline: `main` `807b3602c48824df40a70d2a715f9dfb6dc3e8c6`, tree `50e66b90d7349ebe8e66ebbec0cb9f338a153087`, package `1.14.1`.
Target package: `1.15.0`.

## Implemented high-impact corrections

1. **Own-deck/opponent boundary** — Kaervek is rejected from optimization targets; default allocation scope is Korvold + RogShai only.
2. **Coverage scoping** — current opponent deck IDs resolve to exact source-version prefixes; Cosmic now checks 4 hard-known cards rather than all opponent versions.
3. **Opponent evidence taxonomy** — current structural profiles expose `verified_full_deck`, `official_precon`, `directly_observed`, `partially_observed`, `synthetic_completion`, `unknown`, etc., validated through `OpponentEvidenceKind`.
4. **RunIdentity semantics** — multi-own-deck analysis no longer mislabels another own deck as an opponent or invents a two-player pod. Explicit opponent lists yield `1 + opponent_count`; implicit pod inference is restricted to actual pod tools.
5. **Protected-card freshness** — stale protected metadata not present in canonical current decks was removed; service initialization now fails closed if that configuration drifts again.
6. **Opponent pilot realism** — current explicit opponent strategy labels route to existing Aggro/Artifact/Graveyard/Kaervek public-information pilots rather than GenericCommanderPilot where a grounded archetype mapping exists. No hidden information or unknown-card inference is introduced.
7. **Seat-state truth** — `PilotStateView` now carries explicit 1-based `seat_position`; structural simulator and golden evaluator propagate the actual scenario seat. No seat heuristic weights were changed in P2.

## Development evidence before J holdout

- New J-P2 truth-boundary tests: PASS.
- Existing Phase 12.16 optimizer tests: PASS.
- Existing rules-coverage tests: PASS.
- Existing G modeling-quality tests: PASS.
- Existing 24-case development golden decision corpus: PASS.
- Older pre-J G holdout/control corpus: 12/12 PASS (allowed development/control asset; not `J_HOLDOUT_v1`).
- Broad unit suite: 268/268 PASS before final version bump; final candidate rerun required.
- Canonical data audit: MATCH; `mutated=false`.
- 3/4/5 representative structural sensitivity completed with rotating starts and current opponent structural profiles; results are structural model estimates only. Opponent archetype routing materially reduced the earlier Generic-pilot bias, especially in Korvold controls.

## Development sensitivity interpretation

The small 8-game-per-cell controls are not empirical win rates and are not used to tune decklists or heuristic weights. They are model-sanity probes. After opponent-pilot routing, Korvold place-1 share in the representative control moved to 0.75 / 0.875 / 0.50 for 3/4/5-player cells, rather than near-universal dominance. RogShai remained structurally dominant in these tiny cells, which is retained as a model limitation rather than tuned away without independent evidence.

## Remaining bounded limitations

- Cosmic remains 4 hard-known cards + explicit synthetic/unknown completion; no invented observation.
- Morcant remains partial + provisional/synthetic completion.
- Many opponent oracle cards remain unsupported by card-level tactical/structural coverage; abstract role profiles therefore remain important.
- Politics/threat heuristics remain synthetic scenario axes, not observed social behavior.
- Seat position is now represented truthfully, but richer seat-aware pilot behavior belongs to later pilot-intelligence work rather than being guessed in P2.
- External XMage/Forge evidence remains zero and belongs to J-P3.
- Real-play calibration remains inactive project scope.

## Holdout rule

`J_HOLDOUT_v1` remains sealed until this candidate passes final Ruff/format/Mypy/full-test/compile/data-audit and remote CI gates. Only then may the one-time independent P2 evaluation run. No subsequent tuning may use its result.
