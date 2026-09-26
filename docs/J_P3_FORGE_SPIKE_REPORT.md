# Roadmap J-P3C — Forge Real Feasibility Spike Report

Status: `PARTIAL`

## Frozen identities

```text
contract_hash = 89e0813ec66787328dd4b204f57cb5c404694dec29d249fbbb8785fad0a6d2c6
scoring_hash = 67bc2d99e604f22c3a0d6cc3e00682fe9ac5cb86faccae979418eb2cf40d6227
fixture_hash = cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb
forge_pin = forge-2.0.14 @ a37a865a53280dd8ad6fad3384d69611e8c5a42f
provider_tree = 4471ff068dd23127fc5878bdffa0c0e6de8e6c28
```

No P3A contract, scoring, fixture, knockout threshold or Forge pin was changed after observing Forge results.

## Result

`real_forge_executed = true`.

Forge was actually cloned at the frozen release commit, built with Java 17/Maven, and run as the real `forge-gui-desktop` simulation process. Because the desktop launcher initializes Swing before dispatching `sim`, the successful automated runtime used Xvfb; no GUI automation or human input was used.

A real four-player Commander game ran with:

1. Ishai, Ojutai Dragonspeaker + Rograkh, Son of Rohgahh;
2. Gavi, Nest Warden;
3. Gavi, Nest Warden;
4. Gavi, Nest Warden.

The exact RogShai partners were loaded as commanders and both were cast repeatedly. The provider-native game trace captured turns/phases, stack additions/resolutions, counters, triggers, combat, damage, zone changes, a boardwipe, a replacement effect and the game outcome. The process completed inside its bounded timeout with exit `0` and no residual Forge process.

A second run using the same explicit seed `424242` also completed with exit `0`, but the normalized trace differed and the winner changed. Forge therefore demonstrates an explicit seed input but **not** cross-process same-seed trace determinism under this spike.

The overall result is `PARTIAL`, not `PASS`: no production-style external adapter was built in P3C, and the spike did not capture a complete externally machine-listable live action set, an externally selected valid live action submission, semantic stale/illegal rejection tied to a state revision, or provider replay/checkpoint reconstruction.

No frozen knockout is supported by the evidence.

## Environment and acquisition

Successful runtime evidence run `31429537724` used the frozen source and produced:

```text
Forge release = forge-2.0.14
requested commit = a37a865a53280dd8ad6fad3384d69611e8c5a42f
actual commit = a37a865a53280dd8ad6fad3384d69611e8c5a42f
provider tree = 4471ff068dd23127fc5878bdffa0c0e6de8e6c28
Java = Temurin OpenJDK 17.0.19
Maven = 3.9.16
runner = Ubuntu Linux x86_64
```

The real Maven reactor build completed successfully for Forge Parent, Core, Game, AI, GUI and desktop/runtime modules and produced the `forge-gui-desktop-2.0.14-jar-with-dependencies.jar` assembly.

An earlier headless/no-display desktop invocation exited before producing gameplay output. That launcher diagnostic is preserved in build/controller evidence but is not classified as a Forge provider failure because the identical frozen provider build subsequently executed successfully under a virtual display.

## Real process / Commander evidence

The successful provider trace contains, among other direct runtime observations:

- `Simulation mode` and a real four-player game of `Commander` with explicit seed `424242`;
- repeated `cast Rograkh, Son of Rohgahh` and `cast Ishai, Ojutai Dragonspeaker` entries;
- both exact partners attacking in the same game;
- Ishai's cast triggers firing on opponent spells;
- `Add To Stack` / `Resolve Stack` transitions;
- a live counter interaction where Fierce Guardianship counters Cast Out;
- Akroma's Vengeance removing the RogShai commanders;
- later commander recasts;
- a `Replacement Effect` entry for Cryptic Trilobite;
- ordered combat/damage/life/zone-change/game-outcome entries.

Run 1 completed in about 60 seconds with exit `0`; run 2 also exited `0`. The normalized traces did not match, so deterministic behavior is deliberately scored only at the frozen `0.25` level.

## Capability classification

| Contract feature | J-P3C result | Evidence boundary |
|---|---|---|
| process_start | PASS | real Forge desktop/sim process executed |
| bounded_shutdown | PASS | both runs exited inside bounded timeout; no residual Forge process |
| handshake | PARTIAL | process/version/config initialization is machine-capturable; no normalized external handshake protocol |
| capabilities | PARTIAL | frozen source and runtime expose format/controller/state/log surfaces; no normalized capability protocol |
| deck_import | PASS | four `.dck` Commander inputs loaded into the real game |
| 4_player_commander | PASS | real four-player Commander session completed |
| partner_commanders | PASS | exact Ishai/Rograkh pair loaded and both cast repeatedly |
| seed_or_reproducible_initialization | PARTIAL | explicit seed accepted/executed; repeated same seed did not reproduce identical trace |
| state_read | PARTIAL | rich native GameLog plus GameView/GameState hooks; no normalized external live state snapshot API exercised |
| legal_actions | PARTIAL | frozen `AvailableActions`/PlayerController surfaces exist and native AI made live choices; complete external machine-listable action set not captured |
| programmatic_action_submission | PARTIAL | real PlayerControllerAi drove legal actions in provider runtime and PlayerController exposes choose/play methods; no externally selected live action adapter exercised |
| illegal_action_rejection | NOT_RUN | no state-bound illegal/stale external action submitted |
| stack | PARTIAL | live stack add/resolve transitions captured; no external stack query/control adapter |
| priority | PARTIAL | provider AI reached response windows and countered a live spell; no external priority/choice revision captured |
| commander_tax | PARTIAL | commanders were killed/recast repeatedly; exact frozen third-cast +4/total-nine assertion not isolated |
| per_opponent_commander_damage | PARTIAL | live commander combat damage to a named opponent plus frozen source per-commander/per-opponent tracking; 21-loss/non-combination assertion not isolated |
| events | PASS | provider-native live GameLog captured ordered phase/stack/combat/damage/zone/replacement/outcome events |
| replay_or_equivalent_raw_trace | PASS | complete ordered raw traces captured; provider replay/checkpoint reconstruction itself not exercised |

`PARTIAL` does not mean `PASS`; source hooks are not promoted to a production external adapter.

## Frozen Rules Fixtures

The same 14 P3A fixtures are retained without modification:

- `P3-FX-001 commander_cast`: **PASS** — real live command-zone commander casting and post-resolution state/trace observed.
- `P3-FX-002 commander_tax`: **PARTIAL** — repeated live commander recasts occurred, but the exact third-cast `+4`/nine-mana assertion was not isolated.
- `P3-FX-003 partner_commanders`: **PASS** — exact Ishai/Rograkh pair loaded together; both cast/recast in the real four-player game.
- `P3-FX-004 per_opponent_commander_damage`: **PARTIAL** — commander combat damage to a named opponent occurred and per-opponent tracking hooks are present; exact 21/non-combination assertions were not isolated.
- `P3-FX-005 kediss_normal_damage`: **NOT_RUN**.
- `P3-FX-006 jeska_multiplier`: **NOT_RUN**.
- `P3-FX-007 boardwipe`: **PARTIAL** — a real Akroma's Vengeance wipe and resulting commander zone transitions were captured; the exact Blasphemous Act/Boros Charm assertion was not run.
- `P3-FX-008 counter`: **PARTIAL** — a real response-window counter occurred and stack transition was captured; exact Counterspell/external submission was not isolated.
- `P3-FX-009 protection`: **NOT_RUN**.
- `P3-FX-010 trigger`: **NOT_RUN** for the exact Kaervek/counter assertion.
- `P3-FX-011 replacement`: **PARTIAL** — a real replacement effect and replaced outcome were captured; a controlled replacement-choice scenario was not isolated.
- `P3-FX-012 stack_priority`: **PARTIAL** — live stack ordering and response windows were observed; external state-revision-bound priority control was not demonstrated.
- `P3-FX-013 illegal_action_rejection`: **NOT_RUN**.
- `P3-FX-014 replay_state_consistency`: **PARTIAL** — ordered raw traces exist, but same-seed traces diverged and checkpoint state reconstruction was not performed.

No Tactical Oracle or mock result substitutes for any missing Forge fixture.

## Frozen scoring

The unchanged P3A 100-point model is applied conservatively using only frozen attainment levels:

| Category | Weight | Level | Points | Rationale |
|---|---:|---:|---:|---|
| rules_fidelity | 20 | 0.50 | 10.00 | real full Commander gameplay and multiple rule classes; exact fixture suite incomplete |
| commander_coverage | 12 | 0.75 | 9.00 | exact live four-player RogShai proven; some Commander-specific fixture assertions remain incomplete |
| controllability | 18 | 0.25 | 4.50 | real native controller drives actions and direct controller hooks exist; external state-bound submission adapter unproven |
| observability | 14 | 0.50 | 7.00 | rich live ordered GameLog plus GameView/GameState hooks; normalized external state snapshots unproven |
| deterministic_behavior | 8 | 0.25 | 2.00 | explicit seed works, but repeated same-seed trace diverged |
| headless_automation_and_lifecycle | 8 | 0.50 | 4.00 | fully automated bounded CLI simulation, but desktop initialization requires Xvfb |
| test_replay_raw_trace_quality | 7 | 0.50 | 3.50 | strong ordered raw traces/manifests and repeat run; provider replay/checkpoint consistency not exercised |
| maintenance_activity | 4 | 1.00 | 4.00 | frozen P3A primary-source maintenance evidence |
| build_complexity | 4 | 0.50 | 2.00 | reproducible Java 17/Maven build, but substantial multi-module desktop/runtime surface |
| integration_complexity | 5 | 0.25 | 1.25 | strong in-process hooks exist, but an isolatable external production adapter remains substantial work |
| **Total** | **100** | | **47.25** | |

`forge_score = 47.25`.

This is a feasibility score under the frozen model. P3C does not compare or select providers.

## Knockout assessment

- KO-01 `no_realistic_programmatic_action_submission`: **not triggered**. Real PlayerControllerAi execution plus `PlayerController.chooseSpellAbilityToPlay` / `playChosenSpellAbility` and related choice hooks establish a realistic programmatic control path, although the external adapter remains unproven.
- KO-02 `insufficient_commander_multiplayer_partner_support`: **not triggered**. A real exact four-player Ishai/Rograkh Commander game completed.
- KO-03 `not_reproducibly_buildable_or_startable`: **not triggered**. Frozen Forge built and two bounded real runtime executions completed.
- KO-04 `unmaintainable_fork_depth`: **not triggered by current evidence**. Direct controller/state/action hooks exist; production adapter depth remains a P3D consideration.
- KO-05 `license_or_distribution_incompatibility`: **not triggered by current evidence**. No incompatibility sufficient for the frozen knockout threshold was demonstrated.
- KO-06 `no_usable_state_controller_hook`: **not triggered**. Frozen source exposes GameView/GameState/PlayerController/AvailableActions and live runtime produced detailed state-transition logs.

## Raw evidence

Successful runtime package:

```text
run = 31429537724
workflow_commit = 641db5fc66d0748762cfe649358f5a0273a3a137
artifact = 9078696345
zip_sha256 = 28b5e6c6af0a1602ee083265b20335382e70abbdfbbe67ac16209f489003da87
artifact_size_bytes = 283514
internal_manifest_sha256 = 7f475706664a0ce8b514948e101d32c9c65b3321e54ffd22157dc7ce93c9788c
Drive_ID = 1peoRSZB0aLL_LUvva-EgPR3vW3wlhsDI
Drive_roundtrip = PASS
```

Build/controller/launcher diagnostic package:

```text
run = 31429032677
workflow_commit = fcee69c499f55c04186ab24aad5d7519e3e23b95
artifact = 9078423792
zip_sha256 = f951787f4a68ac843f90648d2c6733e35f45dd69d79af060c04a844a93dadefa
artifact_size_bytes = 62384
internal_manifest_sha256 = 0529dc2723d49d54ea849054e6a035671c8ee12cf13c974150154729da82d00e
Drive_ID = 1H69PC2PI5vNpykm5zlxdZ_DUAxu8Se0_
Drive_roundtrip = PASS
```

## J-P3C decision

```text
J_P3C_COMPLETE = true
J_P3D_READY = true
forge_status = PARTIAL
forge_score = 47.25
forge_knockout = false
real_forge_executed = true
provider_selected = false
```

P3D must compare Forge and XMage only under the unchanged P3A contract. No provider decision is made here.
