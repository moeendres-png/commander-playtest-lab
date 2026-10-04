# Claude handoff, 2026-10-04 (session `01JMXgrP`)

This folder makes the last local-only state of this session persistent. It is **not** a
qualification artifact. Everything here is `LOCAL_OBSERVED` evidence, a reproduction aid
or a handoff note. No credit, no epoch, no AF verdict comes from it. Fresh repository
state on GitHub outranks this text.

## Lane split (Owner, 2026-10-04)

**Codex is the sole writer of the CI / check / gate lane (#479).** That covers:
- Lab #490, #492, #512 and #526;
- Mage #493–#497 with PRs #43, #44 and #45;
- Forge #498–#504 and #528 with PRs #18, #20 and #21.

Claude only adds evidence or reviews there read-only. New write work needs an explicit
baton handover.

**D17:** the in-JVM residual risk is **not** accepted.

**Claude** owns:
- #441 evidence closure;
- the Forge/XMage residual mechanisms;
- the #255 eligibility packet. This packet makes **no** provider selection.

**Writer since 2026-10-04 15:18:** Claude session `01XpopJ6` (#441 comment 5981490500).

## Merged by this session

| PR | Content |
|---|---|
| #523 | RowSpecs for PILOT_CHOOSE_OBJECT, PILOT_REPLACEMENT_EFFECT, PILOT_MANA_PAYMENT, NEGATIVE_INTERNAL_AI |
| #524 | `semantic_choice_key` selector plus `choice:<KEY>`; PILOT_CHOICE. Requested key normalized like the offers |
| #525 | XMage planeswalker loyalty restoration, set as the permanent enters at first-turn placement (CR 704.5i), plus `semantic_ability_key`; PILOT_CHOOSE_ABILITY. Capability manifest updated |
| #527 | Scripted pregame on the candidate-neutral lane (`mulligan_plan`, actor→seat via the engine's own roster, record decks, acknowledged seed). XMage generic lane now applies the free multiplayer mulligan (CR 103.5c). PILOT_MULLIGAN stays **UNKNOWN** because the generic lane has no constructed-state digest |

## Local evidence (`local_evidence/`, see `SHA256SUMS`)

- **`XMAGE_MIDGAME_ROWS_LOCAL_REGRESSION_b479fe74.json`**
  - Full `midgame_rows.execute_and_persist` run of all 66 declared rows on XMage `b479fe74`.
  - The bridge was built from the #525 head *before* the manifest/test fix b9e70133. That fix touched only the manifest wording and tests, not restoration.
  - Result: **66 declared / 66 verified**.
  - `runner_digest = local-dev`, so this is not credit.
- **`FORGE_SCENARIO_LANE_LOCAL_20e3e1f7.json`**
  - `forge_scenario_lane.execute_and_persist` on the pinned Forge bridge `20e3e1f7` (Rules-Core `bb0a740d`).
  - 20 rows attempted: 12 `EXECUTED_OBLIGATION_OBSERVED`, 7 `UNSUPPORTED_DIMENSION`, 1 `OBLIGATION_NOT_OBSERVABLE` (MICRO_LAYERS).
  - The unsupported dimensions are stack injection, combat_state/combat-step temporal points, mid-cast cost state, and decision selectors beyond pass/mulligan/starting-player/cost-order.

## Reproduction (`repro/`)

These are the scripts behind the evidence above. Run them from a Lab checkout with
`PYTHONPATH=src` and **Python ≥ 3.12**. The code uses PEP 695 generics, so a venv is needed
(`uv venv -p python3.12` plus `uv pip install -e '.[dev]'`). Delete the
`src/*.egg-info` that the editable install leaves behind, or the PB-03 trigger test fails.

- **XMage bridge setup.**
  - Build XMage `b479fe74` into an isolated repo: `mvn -DskipTests -Dmaven.repo.local=<m2> install`.
  - Then build the bridge offline: `engine-bridge: mvn -o -Dmaven.repo.local=<m2> -DskipTests compile dependency:build-classpath -Dmdep.outputFile=target/cp-wsr22.txt`.
  - The bridge workspace path must be **absolute**.
- **Scripts.**
  - `run_rows.py <out> <FIXTURE...>` runs selected rows.
  - `run_all.py <out> <doc.json>` runs every row (about 60 min).
- **Forge bridge setup.**
  - `mvn -pl forge-protocol2-bridge -am -DskipTests package dependency:build-classpath`. `forge-gui-mobile` needs jitpack.io, which is blocked here.
  - Tests need Xvfb (`DISPLAY=:99`).
  - `run_forge.py <forge_ws> <out> <doc.json>` runs the Forge scenario lane.
- **Generic lane.**
  - `mull_probe.py`, `pregame_row.py` and `create_probe.py` drive the generic Protocol-2 lane on both candidates.
  - They were used for #527. Their workspace paths are hard-coded to this session's `/home/user/...` layout, so adjust them.

## Pushed but superseded

- **Forge branch `hardening/forge-bridge-free-mulligan-tuck-20261004` @ `b31103f3`.** The bridge returns no cards for a zero-card tuck, so the free mulligan proceeds; an owed card still fails closed.
  - `FreeMulliganTuckTest`: a 4-player game reaches priority with all hands at 7, and a 2-player owed card still fails closed.
  - The two R14B `BridgeEngineTest` cases were moved to a 2-player pod.
  - Targeted tests: 11/11. The full `forge.bridge` suite was interrupted by a worker restart.
  - **No PR.** The writer session `01XpopJ6` owns the same fix on `hardening/forge-free-mulligan-tuck-20261004`.
  - This branch is kept only as a reference, for example the 2P owed-card test. Delete it once the writer's fix merges.

## Open decisions (not taken by this session)

1. **#441 comment 5979655574.** PLAYER_COUNT_2P–5P and WS05-CMD-START-2 are credited PASS on the generic lane without record decks or construction equality. Options: (a) downgrade, (b) keep and record the limitation, (c) build a generic-lane construction proof. Recommended: (a) + (c).
2. **#441 comment 5979206791 (Coordinator errata).** These cover:
   - E1: a known library top card without `deck_state` (PILOT_CHOOSE_USE, NEGATIVE_DEFAULT_YES_NO);
   - E2: scry is a card selection in XMage, not `choose_use`;
   - E3: PILOT_PILE `revealed` objects with Fact or Fiction still on the stack.
3. **WS05-MP-TURN-3/5** (see `docs/af456_xmage_residuals_20261003/README.md`). Nexus of Fate is requested in the graveyard against its own text, and the extra turns contain combat the record never specifies.
4. **WS05-CMD-MULL-2/4.** Only round 1 is scripted. The writer session also adds an observation on Forge's LondonMulligan order.
5. **RNG_RULES_TAPE** (contract v1.0.20 erratum). **MICRO_LAYERS** needs semantic adjudication.

## Blocker

**Epoch sealing.** Artifact downloads go to `*.blob.core.windows.net`, which this environment's network policy denies. The Owner has to allow it. The newest Lab main (`5583d687`) needs its own PB-03 run and epoch.

## Final local-state census (session `01JMXgrP`)

- **Archived:** local-only commits from earlier PR takeovers. Their PRs were later merged through other heads, and `git cherry` shows these patches are *not* in `main`. They are pushed as `archive/` branches, kept for review only and never to be merged blindly:
  - `archive/506-claude-local-cd65e39d-20261004`: a Forge AF05 principal-surface check and a renamed state file;
  - `archive/513-claude-local-3603f678-20261004`: B12 PB-03 trigger on the package readme (Codex lane);
  - `archive/518-claude-local-b8831e7b-20261004`: B8 turn→active-seat binding (Codex lane);
  - `archive/519-claude-local-222fa772-20261004`: B10 report parsing and provenance (Codex lane);
  - `archive/repin4-claude-local-119a49e9-20261004`: repin v4 lock notes, superseded by #522;
  - `archive/b9-claude-local-repair-83714441-20261003` (earlier).
- **Pushed:** Forge `hardening/forge-bridge-free-mulligan-tuck-20261004` @ `b31103f3`, superseded (see above).
- **Persisted:** this branch holds every other local result.
- **REPRODUCIBLE_AND_DOCUMENTED.** Everything else local can be rebuilt with the steps in "Reproduction":
  - Maven repos (`m2-b479`, `m2-forge`), the Python venv;
  - XMage/Forge build trees (`xmage-b479`, `forge-20e3`);
  - engine runtime directories (`af456/`, `af07-runtime*`, `regress-*`, `probe-runtime*`).
- **INTENTIONALLY_DISCARDED:** the older diagnostic runtime directories. Their conclusions are already on GitHub (#456 README, contract 1.0.20, #441 comments).
