# Roadmap J-P3A — External Engine Feasibility Contract

Status: `FROZEN_FOR_P3B_P3C`

Baseline:

```text
repository = moeendres-png/commander-playtest-lab
commit = 91144a31b651d21bd47d7ff901545c0b7fdd9870
tree = 6a0cd2b113bf12160f4b8774dfac2df4e32c8262
package = 1.15.0
J_P2_COMPLETE = true
J_P3_READY = true
```

P3A defines one provider-neutral feasibility contract for XMage and Forge before either real provider spike is evaluated. It does **not** select a provider and does **not** build a production bridge.

## Frozen identities

```text
contract_id = J_P3_EXTERNAL_ENGINE_FEASIBILITY_v1
contract_hash = 89e0813ec66787328dd4b204f57cb5c404694dec29d249fbbb8785fad0a6d2c6
scoring_id = J_P3_PROVIDER_SCORING_v1
scoring_hash = 67bc2d99e604f22c3a0d6cc3e00682fe9ac5cb86faccae979418eb2cf40d6227
fixture_registry = J_P3_RULES_FIXTURES_v1
fixture_hash = cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb

xmage_pin = xmage_1.4.60V3 @ 06d166b098ad36b277edef01116472203d5a047e
forge_pin = forge-2.0.14 @ a37a865a53280dd8ad6fad3384d69611e8c5a42f
```

Hashing rule for the three frozen identities: SHA-256 of canonical UTF-8 JSON with recursively sorted object keys, no insignificant whitespace, `ensure_ascii=false`. The Markdown prose is not the hash payload. The exact structured payloads are represented by this contract, `J_P3_PROVIDER_MATRIX_EMPTY.json`, and `J_P3_RULES_FIXTURE_REGISTRY.json`.

### Pre-spike provider-pin resolution amendment — 2026-08-10

Before any real P3B/P3C provider execution, closeout verification found that the originally recorded `resolved_commit` values for both providers were not resolvable commits in their official repositories. The release names themselves were still the latest official non-draft, non-prerelease releases, but the immutable tag targets had been recorded incorrectly.

The provider pins are therefore corrected provider-neutrally before either spike:

```text
XMage xmage_1.4.60V3
old recorded commit = d2fa0a244708465e9ff7fcb3c37641e749a292a8  # non-resolvable
verified tag target = 06d166b098ad36b277edef01116472203d5a047e

Forge forge-2.0.14
old recorded commit = 187a592e79bc83d324fc792252878fde9ed83498  # non-resolvable
verified annotated tag object = 266c96e466895136feb56e26681753f572b6053c
verified tag commit = a37a865a53280dd8ad6fad3384d69611e8c5a42f
```

This amendment changes only the separately verified provider-pin identities. The provider-neutral feasibility requirements, knockout criteria, scoring weights/levels, evidence policy and rules fixtures are unchanged; therefore the frozen `contract_hash`, `scoring_hash` and `fixture_hash` remain unchanged. No XMage or Forge spike result existed when this correction was made, so it cannot encode provider-performance hindsight.

## Truth boundary

The following remain non-negotiable:

- Structural Simulation is model evidence, not an empirical Commander win rate.
- Tactical Oracle is not an external rules engine.
- Mock/fake backends are not XMage or Forge evidence.
- A handshake by itself is not full external validation.
- `external_rules_engine` requires a real started, programmatically controlled and attested provider with raw evidence.
- `J_HOLDOUT_v1` is consumed P2 evidence and is not an unseen P3 holdout.
- Real-playtest calibration remains `inactive_project_scope`.
- P3A makes zero canonical deck, inventory, purchase or physical-allocation changes.
- Kaervek remains frozen opponent-only.

## Provider pin policy

The same rule was applied before provider results were observed:

1. use the newest official GitHub release that is neither draft nor prerelease at P3A research time;
2. resolve the release tag to an immutable commit;
3. record the current default-branch head only as freshness context;
4. never silently repin after observing a spike result.

A pin may change only through an explicit, documented pre-spike contract amendment. If a frozen release is buildable but old, that is a scored maintenance/build characteristic, not permission to move one provider to `master`.

### Frozen provider research

| Field | XMage | Forge |
|---|---|---|
| official repository | `magefree/mage` | `Card-Forge/forge` |
| frozen release | `xmage_1.4.60V3` | `forge-2.0.14` |
| resolved commit | `06d166b098ad36b277edef01116472203d5a047e` | `a37a865a53280dd8ad6fad3384d69611e8c5a42f` |
| current head observed | `2dbd5239288d0003261100cfe762b218ffe4363a` | `94a3146a88df68d6e389f4f7adae7bf1dc9caebd` |
| license | MIT | GPL-3.0 |
| build | Maven multi-module | Maven multi-module |
| Java at frozen tag | compiler release 8 | compiler release 17 |
| Commander | officially documented | officially documented |
| multiplayer | officially documented up to 10 players | architecture visible; exact required 4-player Commander gate remains for real spike |
| headless | standalone server exists; programmable headless player loop not yet proven | core/AI separated from GUI; supported headless automation endpoint not yet proven |
| testability | `Mage.Tests`, test mode and remote testing surfaces exist | test tree and AI simulation tests exist |
| controller hooks | remote `PlayerActions` / `GamePlay` | abstract `PlayerController` + concrete AI controller |
| state access | view/server-state surfaces exist; sufficiency unproven | `Game` / `GameView` / stack / players / snapshots visible |
| legal actions | complete machine-listable surface not yet proven | complete machine-listable surface not yet proven |
| action submission | typed remote responses + `sendPlayerAction` exist; real bridge unproven | custom controller path plausible; real external submission unproven |
| events | log/session surfaces visible; sufficient raw event stream unproven | `EventBus` + `GameLog` visible |
| replay | explicit remote replay interface exists | snapshot/restore visible; replay/export-equivalent unproven |
| seed control | not proven | not proven |
| maintenance | active default branch at P3A research time | active default branch at P3A research time |

`not proven` is deliberately different from `unsupported`.

Primary-source anchors used for P3A research:
- XMage GitHub repository/readme, release `xmage_1.4.60V3`, release `pom.xml`, remote `PlayerActions`, `GamePlay`, `Replays` and remote-interface tree.
- Forge GitHub repository/readme/wiki, release `forge-2.0.14`, release `pom.xml`, `PlayerController`, `PlayerControllerAi`, and `Game`.
- Commander Playtest Lab current external-engine contract tests and current project-critical interaction catalog.

## Identical feasibility requirements

Both providers are evaluated against exactly these requirements:

1. `process_start`
2. `bounded_shutdown`
3. `handshake`
4. `capabilities`
5. `deck_import`
6. `4_player_commander`
7. `partner_commanders`
8. `seed_or_reproducible_initialization`
9. `state_read`
10. `legal_actions`
11. `programmatic_action_submission`
12. `illegal_action_rejection`
13. `stack`
14. `priority`
15. `commander_tax`
16. `per_opponent_commander_damage`
17. `events`
18. `replay_or_equivalent_raw_trace`

A feature result is one of `PASS`, `PARTIAL`, `UNSUPPORTED`, `INFRASTRUCTURE_BLOCKED`, or `NOT_RUN`.

`UNSUPPORTED` means the provider capability is genuinely absent/insufficient for that feature. `INFRASTRUCTURE_BLOCKED` means the feature could not be evaluated because of an external execution dependency or environment failure. Neither may be rewritten as a synthetic success.

## Frozen knockout criteria

### KO-01 — `no_realistic_programmatic_action_submission`

No realistic path exists to submit gameplay choices/actions programmatically without GUI automation or replacement of core rules/controller semantics.

Required evidence: `static_primary_source_proof_or_reproducible_real_spike_evidence`. Inference alone may **not** trigger a knockout.

### KO-02 — `insufficient_commander_multiplayer_partner_support`

The frozen provider cannot execute the required four-player Commander session with the Ishai/Rograkh partner configuration sufficiently to exercise the contract.

Required evidence: `reproducible_real_spike_evidence_or_unambiguous_primary_source_absence`. Inference alone may **not** trigger a knockout.

### KO-03 — `not_reproducibly_buildable_or_startable`

Under the provider's documented/supported prerequisites, repeated real attempts cannot build and start a bounded process. Transient dependency/network/runner failure is infrastructure_blocked, not a knockout.

Required evidence: `reproducible_real_spike_evidence`. Inference alone may **not** trigger a knockout.

### KO-04 — `unmaintainable_fork_depth`

Required control/observation would demand a permanently invasive fork through core rules, networking, or UI layers rather than an isolatable and maintainable adapter/extension.

Required evidence: `source_level_integration_map_plus_real_spike_findings`. Inference alone may **not** trigger a knockout.

### KO-05 — `license_or_distribution_incompatibility`

The provider license/distribution terms are demonstrably incompatible with the intended production architecture and cannot be isolated at a process boundary. Mere legal uncertainty is LEGAL_REVIEW_REQUIRED, not a knockout.

Required evidence: `license_text_plus_documented_architecture_assessment`. Inference alone may **not** trigger a knockout.

### KO-06 — `no_usable_state_controller_hook`

No usable provider hook can expose sufficient game state/legal-choice context and accept programmatic actions while preserving provider rules semantics.

Required evidence: `static_primary_source_proof_or_reproducible_real_spike_evidence`. Inference alone may **not** trigger a knockout.

A knockout is an evidence classification, not a preference. If a transient download, DNS, runner, package-registry or similar external failure prevents execution, use `INFRASTRUCTURE_BLOCKED` rather than a knockout.

## Frozen scoring — 100 points

| Category | Weight |
|---|---:|
| `rules_fidelity` | 20 |
| `commander_coverage` | 12 |
| `controllability` | 18 |
| `observability` | 14 |
| `deterministic_behavior` | 8 |
| `headless_automation_and_lifecycle` | 8 |
| `test_replay_raw_trace_quality` | 7 |
| `maintenance_activity` | 4 |
| `build_complexity` | 4 |
| `integration_complexity` | 5 |
| **Total** | **100** |

Every category uses only these fixed attainment levels:

```text
0.00
0.25
0.50
0.75
1.00
```

`category_points = weight × level`.

No post-result reweighting or provider-specific interpolation is allowed. The seven capability categories—rules fidelity, Commander coverage, controllability, observability, deterministic behavior, headless lifecycle, and test/replay/raw trace—require real provider evidence from P3B/P3C to earn points. Maintenance/build complexity may use primary-source static evidence. A knockout overrides the numeric score for provider readiness.

## Frozen rules fixtures

The authoritative machine-readable list is `J_P3_RULES_FIXTURE_REGISTRY.json` with hash:

```text
cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb
```

It contains 14 provider-neutral fixtures:
Commander cast, Commander tax, Partner, per-opponent commander damage, Kediss normal damage, Jeska multiplier, boardwipe, counter, protection, trigger, replacement, stack/priority, illegal-action rejection, and replay/state consistency.

A provider is required to attempt a fixture only when it can technically execute the scenario. If it cannot, the fixture is `UNSUPPORTED`; it is never replaced by Tactical Oracle or mock evidence.

## Evidence requirements for P3B/P3C

Each real spike must preserve, where applicable:

- immutable provider pin;
- source/binary acquisition evidence;
- build logs;
- runtime/JVM version;
- exact start command/config;
- spike-controller/bridge commit;
- process lifecycle evidence;
- capability handshake;
- deck import inputs/results;
- real four-player Commander session evidence;
- raw state snapshots;
- legal-choice/action data;
- submitted actions and provider responses;
- illegal-action rejection evidence;
- events/logs/raw trace;
- fixture-level results;
- replay or equivalent raw trace;
- failures and environment diagnostics.

Provider-specific adapters may translate native provider concepts, but they may not weaken the common requirement or fabricate a capability.

## Relationship to current project protocol

The current project already has a restricted external-provider surface around lifecycle, deck loading, game creation/state, legal actions, action submission, advancing and replay export. P3A does not replace or promote it. P3D is the first phase allowed to merge a regular production bridge.

The P3A feasibility contract additionally requires explicit capability reporting and seed/reproducible initialization because those are needed to compare providers fairly before production integration.

## Stop condition

P3A ends when:
- provider pins are frozen;
- contract, scoring and fixtures are frozen;
- both runbooks use the same evidence classes and contract;
- no provider score has been populated;
- no provider has been selected;
- no real provider spike or production integration has been performed.

```text
J_P3A_COMPLETE = true
J_P3B_READY = true
provider_selected = false
```
