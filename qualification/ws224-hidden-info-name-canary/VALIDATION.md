# WS224 VALIDATION

## Hard gates (all 12)

1. Existing UUID oracle green: `XmageFullGameHiddenInformationTest` 1/1 PASS
   (unchanged file) + per-frame UUID assertions inside all 4 canary runs
   (240/240 frames). PASS.
2. Name-canary negatives green: Java 4/4 (240 frames, 240/240 canary signal),
   Python 21/21, boundary 24/24. PASS.
3. N=2..5 principal-scoped proof: CANARY_2P/3P/4P/5P sealed. PASS.
4. 5P all relevant other principals: 20/20 ordered pairs non-vacuous. PASS.
5. Legal-action metadata: scanned every frame (S02/S03/S04) + unit. PASS.
6. Transcript/policy surfaces: at-birth scans + `PilotStateView` sentinel tests. PASS.
7. Replay tape/pilot-facing diagnostics: fresh 35-step tape + verdict-shape +
   tamper diagnostic. PASS.
8. Wrong/stale/malformed errors: 16 in-JVM + 3 boundary probes, no echo, no
   advance. PASS.
9. Grant windows: 0 grants outside `choose_object` across 264 frames; no live
   window arose (declared bound, same as WS213/WS215). PASS-BOUNDED.
10. Historical artifacts: 66 + 4 scanned read-only, explicit disposition, 0
    rewrites, 0 CONFIRMED. PASS.
11. Fresh-process boundary proof: BOUNDARY_4P + record/replay/tamper at this
    HEAD. PASS.
12. No Rules behavior / behavior credit change: production files untouched
    (`git status` clean except new tests + evidence); neutral answers only.
    `BEHAVIOR_CREDIT_CHANGE = 0`. PASS.

## Test ledger

- `mvn -B -ntp test -Dtest=XmageFullGameNameCanaryTest`: 4/4 PASS
  (2P 60/60/2-2, 3P 60/60/6-6, 4P 60/60/12-12, 5P 60/60/20-20 frames/pairs)
- `mvn -B -ntp test -Dtest=XmageFullGameHiddenInformationTest`: 1/1 PASS
- `pytest tests/unit/test_ws224_name_canary.py`: 21/21 PASS
- Impacted neighbors green: `test_semantic_replay_tape.py`,
  `test_xmage_variable_player.py` (64 combined PASS with canary file)
- `ws224_driver.py`: boundary + replay + historical phases PASS; `ruff` clean
- FULL107: NOT_RUN (privacy/evidence workstream; zero behavior credit claimed)

## Honest bounds

- Grant-window LIVE path not exercised (no window arose; same as prior seals).
- Engine-internal GameLog/stderr history: UNKNOWN (sampled stderr clean).
- No Forge work (F-HIDE-03 lane scoping retained).
- First cumulative-transcript scan failed, adjudicated as privileged-history
  conflation (diagnostic evidence in handoff), replaced by the at-birth rule.
