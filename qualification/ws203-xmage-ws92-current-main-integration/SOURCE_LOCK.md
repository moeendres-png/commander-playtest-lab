# WS203 Source Lock — XMage WS92 D1-D5 Current-Main Integration

- `CURRENT_MAIN_SOURCE_LOCK = 7725570b6b8690daed6e645dc1611f5e196de8c5`
- `CURRENT_MAIN_TREE = 8b926c73cf35468c6110d64615c5f5e863ac2aa1`
- `WS92_SOURCE_IDENTITY = 3e0def24e199b1b1d53b731ffffa1ab30edf9cc5`
- `WS92_TREE = c6f8b42c0657da411f6ae64d1a5cdf055c4d1223`
- `XMAGE_ENGINE_PIN_PRESERVED = cfc36f445f917f101fa2ed588770e043f53bc44c`
- `WS92_BASE = 6baa24d465d43eb10456fc846efb44f7c42dfc66` (ancestor of current main; WS92 line diverges here)
- `WS92_COMMITS_CONSUMED = 14ca075303fb780f5b566f03bb43daadb132c176, e63165f39722eba8e65ba983b92f4aee79bb3364, 3e0def24e199b1b1d53b731ffffa1ab30edf9cc5`

## Exact WS92 diff consumed

`git diff 6baa24d465d43eb10456fc846efb44f7c42dfc66..3e0def24e199b1b1d53b731ffffa1ab30edf9cc5 --stat`:

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java` (43 lines: D4 `redactObjectIds`)
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java` (188 lines: D4 key-mode Choice + `choiceText`/`choicePrompt`, D5 `stablePermanentOrder`, D2 look window + `lookOwnerFor`)
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameStateRedactor.java` (192 lines: D1 `granted_library`, D2 grant registry, D3 P/T/damage/counters + face-up-gated abilities + `commander_status`)
- `engine-bridge/src/test/java/org/commanderlab/xmage/Ws92D1D2D3ProjectionTest.java` (364 lines, new)
- `engine-bridge/src/test/java/org/commanderlab/xmage/Ws92D4ChoiceProjectionTest.java` (119 lines, new)
- `engine-bridge/src/test/java/org/commanderlab/xmage/Ws92DecisionKindCensusTest.java` (391 lines, new)
- `qualification/ws92-xmage-d1-d5-boundary-reacquisition/DECISION_KIND_CENSUS.json` (127 lines, sealed non-scoring census)
- `qualification/ws92-xmage-d1-d5-boundary-reacquisition/FINAL_REPORT.md` (61 lines)

## Current-main semantic reconciliation

- Intervening `6baa24d4..7725570b` touches only Foundry/launcher/docs (`EXECUTION_PROVIDER_OVERRIDE.md`, `docs/foundry-execution/`, `qualification/ws190-long-turn-resilience/`, `tests/foundry/test_launcher.py`, `tools/foundry/launcher.py`, `tools/foundry/metrics.py`); zero overlap with the XMage bridge surface.
- `git diff 6baa24d4..7725570b -- engine-bridge/.../XmageFullGamePlayer.java` is empty; the same holds for the other two production files by stat exclusion. Current-main production files are therefore byte-identical to the WS92 base.
- No `foundry-adjudicator` XHIGH escalation was required: no genuine nonlocal semantic conflict exists. Read-first adjudication at HIGH determined the minimal current-main-correct delta equals the WS92 production diff, reapplied as explicit edits (no merge, no rebase, no cherry-pick).
- Working-tree production diffs reproduce the WS92 blob indices exactly (`84b4772d..6a0720ca`, `9a275ce5..97e6d0c3`, `f2876f1a..9314f5b4`).
- Tests recreated byte-identical from the sealed WS92 blobs (verified by construction via `git show <ws92>:<path>` byte copy); no test weakening.
- Pin authority unchanged: `config/rules_engines.json:primary_engine.commit` remains `cfc36f...`; fail-closed contracts unchanged (`legal_actions_supported=false`, `action_submission_supported=false`).
