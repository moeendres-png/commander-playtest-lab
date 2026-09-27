# Roadmap J-P3B — XMage Real Feasibility Spike Report

Status: `PARTIAL`

## Frozen identities

```text
contract_hash = 89e0813ec66787328dd4b204f57cb5c404694dec29d249fbbb8785fad0a6d2c6
scoring_hash = 67bc2d99e604f22c3a0d6cc3e00682fe9ac5cb86faccae979418eb2cf40d6227
fixture_hash = cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb
xmage_pin = xmage_1.4.60V3 @ 06d166b098ad36b277edef01116472203d5a047e
provider_tree = f4cadfdddd9271d71103a2e092a5a27f64089305
```

No contract, scoring, fixture or provider pin was changed after observing XMage results.

## Result

`real_xmage_executed = true`.

XMage was actually cloned at the frozen commit, built with Maven/Java 8, started as a real server process, connected through its native remote `SessionImpl`, queried for server/game/deck capability data, used to create/remove a Commander Free For All table, and shut down under a bounded process lifecycle. The native XMage test engine also executed focused Commander/Partner fixtures.

The result is `PARTIAL`, not `PASS`, because the spike did not establish the complete live gameplay-control contract: no four-player Ishai/Rograkh match was driven end-to-end through the remote controller; no complete live machine-listable legal-action surface was captured; no valid gameplay action was submitted against a live choice state; semantic illegal/stale-action rejection was not demonstrated; and replay was not exercised.

There is no frozen knockout supported by the evidence.

## Environment and acquisition

Runtime evidence run `31398027517` used:

```text
runner = Linux x86_64 / Ubuntu GitHub-hosted runner
Java = Temurin OpenJDK 1.8.0_492
Maven = 3.9.16
requested XMage commit = 06d166b098ad36b277edef01116472203d5a047e
actual XMage commit = 06d166b098ad36b277edef01116472203d5a047e
provider tree = f4cadfdddd9271d71103a2e092a5a27f64089305
```

The real multi-module build completed successfully, including `Mage Server`, `Mage Tests`, `Mage Game Commander Free For All` and the relevant server plugins.

## Real process / remote control evidence

The real server log reports XMage startup and test mode on port `17171`. The remote controller compiled and exited `0` and recorded:

```text
connected = true
is_connected = true
server_ready = true
version_info = 1.4.60-V3 (build: runtime)
Commander deck type exposed = true
Commander Free For All game type exposed = true
remote Commander table created = true
remote table removal requested = true
remote_probe_complete = true
server_started = 1
bounded_shutdown = 1
```

A native remote `sendPlayerAction` call was also transported against a deliberately bogus game UUID. That transport return is deliberately **not** treated as a valid gameplay-action or illegal-action-rejection PASS because no live game/choice state existed for the request.

## Capability classification

| Contract feature | J-P3B result | Evidence boundary |
|---|---|---|
| process_start | PASS | real `mage.server.Main` process started |
| bounded_shutdown | PASS | bounded TERM/process cleanup captured |
| handshake | PASS | real native SessionImpl remote login |
| capabilities | PARTIAL | server/game/deck/player types read; no normalized production capability protocol |
| deck_import | NOT_RUN | no real deck submission in remote match |
| 4_player_commander | PARTIAL | native four-player Commander test base executed; remote Commander FFA table created; no four-player live match |
| partner_commanders | PARTIAL | native Partner engine test PASS; exact Ishai/Rograkh pair not executed |
| seed_or_reproducible_initialization | NOT_RUN | no supported external seed control demonstrated |
| state_read | PARTIAL | server/room/table capability state read; live normalized game state not captured |
| legal_actions | NOT_RUN | no complete machine-listable live legal-action set captured |
| programmatic_action_submission | PARTIAL | native remote submission surface exercised at transport level; no valid live gameplay action demonstrated |
| illegal_action_rejection | NOT_RUN | bogus game request was not accepted as semantic rejection evidence |
| stack | NOT_RUN | no live external stack observation/control fixture |
| priority | NOT_RUN | no live external priority-choice state captured |
| commander_tax | PARTIAL | native four-player repeated-cast/tax test PASS; exact frozen third-cast +4 assertion not executed |
| per_opponent_commander_damage | NOT_RUN | not executed |
| events | PARTIAL | real Session callback/server logs captured; live gameplay event stream not characterized |
| replay_or_equivalent_raw_trace | PARTIAL | ordered raw execution logs/manifest exist; provider replay API not exercised |

`NOT_RUN` is not `UNSUPPORTED`.

## Frozen Rules Fixtures

Provider-native fixture run `31399104522` executed three focused tests at the exact frozen XMage commit:

- `P3-FX-001 commander_cast`: PASS.
- `P3-FX-002 commander_tax`: PARTIAL at frozen-fixture level. The native four-player Commander test passes repeated command-zone cast/tax behavior, but not the frozen exact third-cast `+4` assertion.
- `P3-FX-003 partner_commanders`: PARTIAL at frozen-fixture level. Native Partner semantics pass, but the executed pair is not specifically Ishai/Rograkh.

`P3-FX-004` through `P3-FX-014` remain `NOT_RUN` for J-P3B. No Tactical Oracle or mock result is substituted.

## Frozen scoring

The unchanged P3A 100-point model is applied conservatively using only allowed levels:

| Category | Weight | Level | Points | Rationale |
|---|---:|---:|---:|---|
| rules_fidelity | 20 | 0.25 | 5.00 | real focused native rules execution, broad fixture suite incomplete |
| commander_coverage | 12 | 0.50 | 6.00 | Commander FFA capability + four-player Commander harness + Partner evidence; exact live RogShai pod absent |
| controllability | 18 | 0.25 | 4.50 | real native remote session/table control and submission transport; valid gameplay-choice loop absent |
| observability | 14 | 0.25 | 3.50 | real server/room/table observation; normalized live game state absent |
| deterministic_behavior | 8 | 0.00 | 0.00 | external seed/reproducible initialization not demonstrated |
| headless_automation_and_lifecycle | 8 | 1.00 | 8.00 | real headless start/connect/shutdown demonstrated |
| test_replay_raw_trace_quality | 7 | 0.25 | 1.75 | strong raw logs/manifests; provider replay not exercised |
| maintenance_activity | 4 | 1.00 | 4.00 | frozen P3A primary-source maintenance evidence |
| build_complexity | 4 | 0.50 | 2.00 | reproducible successful Maven/Java 8 build but large multi-module dependency/build surface |
| integration_complexity | 5 | 0.25 | 1.25 | usable native remote surface exists; live gameplay choice/state adapter remains substantial |
| **Total** | **100** | | **36.00** | |

`xmage_score = 36.0`.

This score is a feasibility score under the frozen P3A model, not deck performance and not a provider selection.

## Knockout assessment

- KO-01 no realistic programmatic action submission: **not triggered**; native remote submission methods and a real remote session exist, although valid live gameplay submission remains unproven.
- KO-02 insufficient Commander/multiplayer/partner support: **not triggered**; Commander FFA, four-player native Commander testing and Partner support are present, although exact live RogShai remains unproven.
- KO-03 not reproducibly buildable/startable: **not triggered**; real builds and process starts succeeded after spike-workflow bootstrap bugs were corrected.
- KO-04 unmaintainable fork depth: **not triggered by current evidence**.
- KO-05 license/distribution incompatibility: **not triggered by current evidence**.
- KO-06 no usable state/controller hook: **not triggered**; real SessionImpl control/state surfaces exist, although production sufficiency remains open.

## Raw evidence

Runtime package:

```text
run = 31398027517
controller evidence commit = 52fb1654d22d128d9962741f9908e92f5d4781ad
artifact = 9066656227
zip_sha256 = 9f49cae416d384490e8fe77da6b782f2ae5c8732f78778c3919df143b5e09926
internal_manifest_sha256 = 02f6553fa099f38814bbb9f7a4e6818f158bf42d8ce94e75df4ecc2f57c7a2f5
Drive_ID = 1SYlE4AVJqCw9REOVCaCmrFHNoSJtjPx9
Drive_roundtrip = PASS
```

Fixture package:

```text
run = 31399104522
workflow evidence commit = 09132ca8b43b9c61d92343b290cce4b2b8047fbe
artifact = 9067034754
zip_sha256 = fa2cff928f75d74b519eb7984d0bb272809c30a9c0f8a2ce59debed1884b8d18
internal_manifest_sha256 = 669ec1a30603b17e77152f60e26e481ac49a00cd67655d70cc08170c17484025
Drive_ID = 197zw-jJt4YPQwKY2oID9tukg1S1bXtVI
```

## P3B decision

```text
J_P3B_COMPLETE = true
J_P3C_READY = true
xmage_status = PARTIAL
xmage_score = 36.0
xmage_knockout = false
real_xmage_executed = true
provider_selected = false
```

P3C must test Forge against the unchanged frozen P3A contract. XMage limitations must remain visible for the later P3D comparison; P3B does not select a provider.
