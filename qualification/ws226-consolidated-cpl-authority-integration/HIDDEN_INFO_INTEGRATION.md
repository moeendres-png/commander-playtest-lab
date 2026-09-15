# WS226 HIDDEN_INFO_INTEGRATION — WS224 canaries on the combined tree

## Transferred exactly (production untouched)

- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameNameCanaryTest.java`
  (614 lines; 2P/3P/4P/5P live per-frame hidden-EXCLUSIVE name + UUID scans
  over observation JSON, legal labels/metadata, target projection,
  transcript slices, grant windows, replay/diagnostic surfaces).
- `tests/unit/test_ws224_name_canary.py` (21 Python tests + 24 boundary:
  canonical actor-view drop, fingerprint joins, sentinel policy-input,
  at-birth transcript, wrong/stale/malformed error non-echo).
- `qualification/ws224-hidden-info-name-canary/*` (CANARY_2P/3P/4P/5P sealed
  2P 2/2 … 5P 20/20 ordered pairs non-vacuous; CANARY_CONTRACT; 8 surface
  scans; LEAK_SURFACE_INVENTORY three-tier boundary S01–S09+; PROCESS_ISOLATION;
  runs/BOUNDARY_4P + REPLAY_4P + ws224-tape-4p 35 steps; ws224_driver.py).

## Preserved

UUID oracle (`XmageFullGameHiddenInformationTest` 1/1 + 240/240 per-frame
UUID assertions inside canary runs); name oracle (240/240 canary signal);
2P–5P matrix; replay privacy (fresh tape + verdict-shape + tamper diagnostic);
historical advisory (66 `POTENTIAL_LEAK_ARTIFACT` advisory, 4
`EXPECTED_PRIVILEGED_ARTIFACT` WS218 tapes, 0 `CONFIRMED_PILOT_VISIBLE_LEAK`,
0 rewrites). Production source untouched (verified: this integration's
`git diff --name-only` for Step 4 contains ONLY the Java canary + ws224
namespace + Python canary test).

## Bounds honestly preserved (no upgrade)

- `ENGINE_INTERNAL_LOG_STATUS` remains UNKNOWN (sampled stderr clean;
  GameLog/stderr history not proven either way).
- Grant-window LIVE path not exercised (0 grants outside `choose_object`
  across 264 frames; declared bound, same as WS213/WS215) → PASS-BOUNDED.
- One-line `full_game.py` concern: inspected — WS224 has NO change to
  `src/commander_lab/engine/rules/full_game.py` (empty delta
  `3cdade1d..f075ab75` for that path). WS223 current bytes stand; no blind
  overwrite performed.

## Current dispositions

G07/AF05 remain PASS (sealed HIDDEN sentinel rows + WS224 hardening note;
F-HIDE-02 coexists as improvement, not invalidation). No new hidden-info
credit claimed beyond WS224's sealed scope.
