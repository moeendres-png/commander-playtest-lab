# SOURCE LOCK — Engine Capability Reuse Delta (WS-CSN-CAPABILITY-DELTA-20260929)

Workstream: `research/csn-engine-capability-delta-20260929`
Executor: `opencode-go/space-bunny-free` at native `max`
Locked at: 2026-09-29 (Europe/Berlin), before any edit.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Commander Lab (primary repository under edit)

| Field | Value |
|---|---|
| Repository | `https://github.com/moeendres-png/commander-playtest-lab.git` |
| Base branch | `main` |
| Base HEAD | `2e28866f2bab2981f0b8da2d9a7a493cd3f424cf` |
| Base TREE | `0c7b0603cdc0f0958add7e9bf9f23c0f023ec1ff` |
| Base subject | `Merge PR #298: fix XMage unlimited-block capacity` |
| Workstream branch | `research/csn-engine-capability-delta-20260929` |
| Worktree | `/home/moeen/code/ws-csn-capability-delta-20260929` |
| Working tree at lock | clean |

Coordinator's observed main HEAD `2e28866f…` and TREE `0c7b0603…` were
**confirmed against `origin/main` after a full fetch** and match. The
pre-existing `main` worktree `/home/moeen/code/commander-playtest-lab` was stale
at `e91819ae…` (106+ commits behind) and was **not** used as an edit surface.

## 2. Engine pins (authority: `config/rules_engines.json` at the locked HEAD)

`config/rules_engines.json` re-read at the locked HEAD. It is the sole
machine-readable pin authority. No pin was changed by this workstream.

### XMage — primary engine (production reachability target)

| Identity | Value |
|---|---|
| `primary_engine.commit` | `b19596980f2734496ea1896504253e1bdd2756dd` |
| `primary_engine.repository` | `https://github.com/moeendres-png/mage.git` |
| `primary_engine.license` | MIT |
| `release` | `compatibility-fork-unreleased` (Lab compatibility fork, **not** pristine upstream) |
| Upstream counterpart | `magefree/mage` master (MIT) |
| Consumed artifact | `org.mage:mage:1.4.61` (Maven, resolved to `~/.m2/repository/org/mage/mage/1.4.61/mage-1.4.61.jar`) |
| Bridge identity constant | `XmageProvider.ENGINE_COMMIT` — same SHA |
| Runtime proof | `get_provider_version` reported `engine_commit=b1959698…` and `xmage_code_source=file:/home/moeen/.m2/repository/org/mage/mage/1.4.61/mage-1.4.61.jar` on the `main` lane and on the new `midgame` lane |

Ancestry is not identity. Every result in this workstream is evidence about the
**pinned Lab fork** and must not be reported as an upstream XMage result.

### Forge — secondary/candidate engine (NOT touched by this workstream)

| Identity | Value |
|---|---|
| `secondary_engine.commit` (Rules-Core of record) | `a37a865a53280dd8ad6fad3384d69611e8c5a42f` (`forge-2.0.14`) |
| `secondary_engine.bridge_source.commit` | `4753bb7c72ea60d653121e0bab989077b4009f9c` |
| `secondary_engine.license` | GPL-3.0 |
| `provider_decision` | `NO_PROVIDER_READY` |
| Historical pin (Phase 8.5, frozen provenance) | `forge-2.0.13 @ 852066bf…` — not current truth |

The four-way Forge identity conflict (pinned `a37a865a` vs Lab bridge source
`4753bb7c` vs historically executed Lab fork `ef958ee9…` vs native-suite
execution root `18bba95a…`) remains **open** as **PB-09**, owned by the Forge
lane and the Coordinator. Nothing in this workstream reads, writes, or
re-attributes Forge behaviour.

## 3. Toolchain actually used for the runtime evidence

| Tool | Observed |
|---|---|
| JDK | `openjdk 21.0.12.1` |
| Maven | `3.9.12` (offline, `-o`) |
| Module | `engine-bridge` (`xmage-engine-bridge:0.1.0-SNAPSHOT`), `<release>17</release>` |
| Classpath manifest | `engine-bridge/target/cp-wsr22.txt`, generated with `mvn -o dependency:build-classpath -Dmdep.outputFile=target/cp-wsr22.txt` |
| Python | CPython 3.12, `pytest`, `ruff`; `mypy 2.3.1` in a throwaway venv at `/tmp/opencode/mypyenv` |

## 4. Active ownership census (read-only, taken before any write)

Method: `gh pr list --state open` (43 open PRs) → per-PR `gh pr view --json
files`; union of touched paths compared against `git ls-tree origin/main` for
the surfaces this workstream could touch.

Open PRs carrying a non-draft or draft head that touch candidate surfaces:

| PR | Head branch | Touches a candidate surface? |
|---|---|---|
| #300 | `sol/final-boundary-hardening-20260929` | **YES** — `game_driver.py`, `full107.py`, `XmageBridgePlayer.java`, `JsonlBridge.java`, `ExternalDecisionController.java`, `XmageGameManager.java`, `XmageFirstTurnDrawRuleTest.java` |
| #299 | `glm-max/pb09-pristine-forge-20260929` | **YES** — `bridge_launcher.py`, `scripts/run_pb09_*.py` |
| #289 | `sbmax/final-pre-freeze-20260928` (draft) | **YES** — `game_driver.py`, `run_current_boundary_qualification.py`, `hidden_obligations.py`, `replay_obligations.py`, `shortcut_campaign.py`, `lane_integrity.py`, `provider_binding.py`, `impact_adjudication.py`, `assemble_current_boundary_evidence.py` |
| #284 | `sol/final-integration-salvage-20260928` (draft) | **YES** — `XmageFullGameJsonlBridge.java`, `XmageFullGameSession.java`, `XmageNativeStateRestoration.java`, `XmageHiddenStateRestoration.java`, `XmageFullGamePlayer.java`, `full_game.py`, `bridge.py`, `base.py` |
| #294 (merged) | — | `XmageCommanderGames.java`, `XmageNativeStateRestoration.java`, `XmageHiddenStateRestoration.java` — already in `main` |
| #298 (merged) | — | `XmageFullGamePlayer.java` — already in `main` |
| #301, #290, #288, #287, #164, #163, #160, #159, #158, #157, #156, #155, #154, #153, #152, #151, #150, #149, #148, #147, #146, #145, #144, #143, #142, #141, #140, #139, #138, #137, #136, #135, #132, #128, #126, #122 | various | No |

Ownership conclusion: the four owned files relevant to starting-state work
(`XmageNativeStateRestoration.java`, `XmageFullGameSession.java`,
`XmageFullGameJsonlBridge.java`, `game_driver.py`, `full107.py`,
`bridge_launcher.py`) were **not edited**. `Main.java` and the whole
`current_boundary` + `engine/rules` directories were computed against the open-PR
union and the free complement used; see `ENGINE_CAPABILITY_REUSE_MATRIX.md` §6.

## 5. Files this workstream changed (complete)

Modified:

- `engine-bridge/src/main/java/org/commanderlab/xmage/Main.java` — added the
  `midgame` lane dispatch only. No existing branch changed behaviour.

Added:

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageMidgameJsonlBridge.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageMidgameLaneTest.java`
- `src/commander_lab/qualification/current_boundary/midgame_lane.py`
- `scripts/run_midgame_capability_probe.py`
- `tests/qualification/test_current_boundary_midgame_lane.py`
- `qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json`
- `docs/engine_capability_reuse_delta_20260929/*`

## 8. Remediation-era source lock (2026-09-29, additive)

The lock in §1 records the workstream's original base. This section records the
identity the review remediation was integrated and re-verified on, without
changing the historical record above.

| Field | Value |
|---|---|
| Main at task authoring | `234318cf83b29420a20d2e9878aa86b7110af55e` |
| Main actually integrated | `83a547f739cc1a7072798c55e10829032df8fe88` (main advanced past the authoring lock; no #304-owned file was edited by main in between) |
| PR #304 head at remediation start | `8a7e8e303cdb5f45d971d35c9ded4af25863385b` |
| PR #304 head after the causal-completion commit | `dafe2ac6d903ed55c774841fbfa25cb7584f52d6` |
| Remediation branch | `pb03/304-remediation-on-dafe2ac6` |
| XMage engine pin | `b19596980f2734496ea1896504253e1bdd2756dd` (unchanged; still `org.mage:mage:1.4.61`) |
| Forge Rules-Core pin | unchanged; not touched by this workstream |
| Classpath manifest | `engine-bridge/target/cp-wsr22.txt`, regenerated with `mvn -B -o dependency:build-classpath -Dmdep.outputFile=target/cp-wsr22.txt` |

Every suite was re-executed at this head; no pre-update PASS was carried forward.
See `REVIEW_REMEDIATION_20260929.md`.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
