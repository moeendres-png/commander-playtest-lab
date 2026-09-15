# WS223 CI Impact Map

## Living conformance path (F-CI-03 repair surface)

| File | Current shape | Impact of WS223 change | Risk |
|---|---|---|---|
| `scripts/run_external_full_game_conformance.py` | Hardcoded 4P, single full game-over ×2 (replay pair) | Parametrized `--player-count {2,3,4,5}` full gate + `--smoke-decisions K` bounded lifecycle + `--expect-fail-closed` 6P; shared construction helper importable by unit tests | Low: default behavior unchanged (4P full gate) |
| `src/commander_lab/engine/rules/full_game.py` | `run()` = terminal-or-fail; no bounded mode | ADDITIVE `run_smoke()` reusing `_validate_inputs`/`_validate_handshake`/policy; returns `FullGameSmokeResult`; `run()` untouched | Low: additive; existing guards re-run |
| `.github/workflows/xmage-full-game-conformance.yml` | One 4P step; narrow push filters | Loop steps 2/3/5 bounded + 4 full + 6 fail-closed; unified PR/push filters incl. variable-player surfaces | Low: same runners/builds, +3 bounded JVM runs |
| `tests/unit/test_xmage_variable_player.py` | Guards exist (2–5 accept, 1/6 reject, 4-only lane reject) | Untouched (sibling-guard stability) | None |
| `tests/unit/test_ws223_cardinality_regression.py` (new) | — | Constant pins, 6P-via-`model_copy`, seat-range, 5P mapping, script-construction, workflow static gates | None (test-only) |

## Replay-trigger adjudication (WS218 modules)

WS218's runtime surface is `src/commander_lab/semantic_replay/**` +
`tests/unit/test_semantic_replay_tape.py`; `full_game.py:semantic_transcript`
is shared. Decision:

- `semantic_replay/**`-only changes → light lane (`ci.yml`, runs full pytest
  on every push/PR). They do **not** trigger the heavy JVM full-game lane:
  no engine interaction, no cardinality surface. This bounds JVM cost.
- Any `full_game.py` change (including `semantic_transcript`) → heavy lane
  via the existing path filter. Shared-code risk stays covered.
- Static test asserts the heavy lane does **not** list `semantic_replay/**`
  (cost-creep guard) and **does** list all variable-player surfaces.

## Variable-player trigger surfaces (must all trigger the heavy lane)

`engine-bridge/**`, `src/commander_lab/engine/rules/full_game.py`,
`src/commander_lab/engine/rules/full_game_batch.py`,
`src/commander_lab/agents/**`, `src/commander_lab/models/pilots.py`,
`src/commander_lab/candidates/models.py`,
`tests/unit/test_xmage_full_game.py`,
`tests/unit/test_xmage_variable_player.py`,
`scripts/run_external_full_game_conformance.py`,
`scripts/generate_full_game_contract_artifacts.py`,
workflow file itself. `artifacts/xmage-full-game/**` retained (evidence refresh).

## Cost bound (documented)

One XMage build + one bridge build per run (unchanged); JVM executions:
3 bounded smokes (target 25 decisions each, `request_timeout_seconds=120`,
`timeout-minutes: 90` job cap retained) + 1 full 4P pair (existing cost) +
6P fail-closed (no JVM). No matrix-build multiplication: single job,
sequential steps, shared build artifacts.
