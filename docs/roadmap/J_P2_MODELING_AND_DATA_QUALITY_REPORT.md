# Roadmap J-P2 Modeling & Data Quality Report

Status: `HOLDOUT_PASSED_PENDING_MERGE_CLOSEOUT`

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
- Canonical data audit: MATCH; `mutated=false`.
- 3/4/5 representative structural sensitivity completed with rotating starts and current opponent structural profiles; results are structural model estimates only. Opponent archetype routing materially reduced the earlier Generic-pilot bias, especially in Korvold controls.

## Development sensitivity interpretation

The small 8-game-per-cell controls are not empirical win rates and are not used to tune decklists or heuristic weights. They are model-sanity probes. After opponent-pilot routing, Korvold place-1 share in the representative control moved to 0.75 / 0.875 / 0.50 for 3/4/5-player cells, rather than near-universal dominance. RogShai remained structurally dominant in these tiny cells, which is retained as a model limitation rather than tuned away without independent evidence.

## Frozen candidate and remote gates

Frozen product candidate before holdout:
- commit `4ca5a994882e0da6c55916b392972cdf3a5fc9c7`;
- tree `82249e61488af5758a9ad1c5f0bf24eaf222eaca`;
- package `1.15.0`.

Pre-holdout validation on the frozen candidate:
- Ruff lint: PASS;
- Ruff format: PASS;
- strict Mypy: PASS;
- test collection: PASS;
- full pytest: PASS;
- compile: PASS;
- canonical data audit: MATCH;
- clean-tree and holdout-integrity recheck: PASS;
- PR remote CI Quality + Security: PASS;
- Windows Runtime Hygiene: PASS;
- Release Artifacts including roundtrip: PASS.

## One-time J_HOLDOUT_v1 evaluation

The independent P2 holdout was executed exactly once only after the candidate and remote gates were frozen:
- evaluation timestamp: `2026-08-10T08:06:01Z`;
- candidate commit/tree/package: `4ca5a994882e0da6c55916b392972cdf3a5fc9c7` / `82249e61488af5758a9ad1c5f0bf24eaf222eaca` / `1.15.0`;
- set: `J_HOLDOUT_v1`;
- set hash: `724e84f1ea34bea9ec6b37929d945724c77c408a464b3a9dd05235738a00d5d6`;
- member SHA256: `a5875cd1a8edf6bbf79248b3e4ba26151579f628eaeefd4ef2369abb309da8d1`;
- result: **12/12 PASS**;
- critical result: **12/12 PASS**;
- result JSON SHA256: `c03af9292359d287c9bcc83fc2ff6d431204f06bddb21063cf19909ee3009ae4`;
- GitHub Actions run `31368555983`, artifact `9055115957`;
- estimate type: `structural_model_estimates`;
- `used_for_tuning=false`.

No P2 model, pilot, heuristic weight, opponent assumption, deck, inventory, purchase or allocation change is permitted in response to this holdout result. Any future same-phase tuning would require a new independent holdout version or explicit loss-of-independence labeling.

## Remaining bounded limitations

- Cosmic remains 4 hard-known cards + explicit synthetic/unknown completion; no invented observation.
- Morcant remains partial + provisional/synthetic completion.
- Many opponent oracle cards remain unsupported by card-level tactical/structural coverage; abstract role profiles therefore remain important.
- Politics/threat heuristics remain synthetic scenario axes, not observed social behavior.
- Seat position is now represented truthfully, but richer seat-aware pilot behavior belongs to later pilot-intelligence work rather than being guessed in P2.
- External XMage/Forge evidence remains zero and belongs to J-P3.
- Real-play calibration remains inactive project scope.

## P2 closeout rule

After the one-time holdout, only provenance/registry/documentation and merge/recovery closeout may change. The final metadata-only closeout head must re-pass normal PR gates before merge. Post-merge `main` must then be revalidated and a main-specific recovery artifact must pass SHA/Drive byte-roundtrip before `J_P2_COMPLETE=true` and `J_P3_READY=true` are declared.
