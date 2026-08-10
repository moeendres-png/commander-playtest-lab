# Roadmap J-P3D — Provider Decision

## Decision

```text
provider_decision = NO_PROVIDER_READY
primary_provider = none
provider_selected = false
J_P3_EXTERNAL_ENGINE = BLOCKED_WITH_REAL_EVIDENCE
production_bridge = not_built
```

This decision closes the provider investigation without pretending that a spike is a production integration. It uses only the frozen J-P3A contract/scoring/fixtures and the real J-P3B/J-P3C evidence.

## Frozen identities

```text
contract_hash = 89e0813ec66787328dd4b204f57cb5c404694dec29d249fbbb8785fad0a6d2c6
scoring_hash = 67bc2d99e604f22c3a0d6cc3e00682fe9ac5cb86faccae979418eb2cf40d6227
fixture_hash = cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb
xmage_pin = xmage_1.4.60V3 @ 06d166b098ad36b277edef01116472203d5a047e
forge_pin = forge-2.0.14 @ a37a865a53280dd8ad6fad3384d69611e8c5a42f
```

No criterion, weight, fixture, knockout threshold or provider pin was changed after provider results were observed.

## Evidence comparison

| Axis | XMage P3B | Forge P3C | P3D conclusion |
|---|---|---|---|
| Frozen score | 36.0 / PARTIAL | 47.25 / PARTIAL | Forge leads feasibility, not production readiness |
| Knockout | false | false | No provider is eliminated by a frozen KO |
| Real execution | yes | yes | Both count as real external-rules-engine spike evidence |
| 4-player Commander | table/control path, but no exact RogShai E2E game | exact real Ishai/Rograkh + 3 opponents completed | Forge stronger |
| Partner | targeted native evidence, partial | exact pair loaded/cast/recast live | Forge stronger |
| State observability | partial | rich GameLog plus state hooks, partial | Forge stronger but no normalized external live state API |
| Legal actions | not complete | native action/controller hooks, partial | Neither proves a complete external machine-listable choice surface |
| Programmatic submission | not valid live E2E | native AI/controller acts, but no externally selected state-bound adapter | Neither production-proven |
| Illegal/stale rejection | not proven | NOT_RUN | Critical production gate fails for both |
| Stack/priority | not external live control | live stack/response windows observed, external control partial | Forge stronger, still insufficient |
| Events | limited | rich ordered real trace | Forge stronger |
| Replay/trace | replay not exercised | ordered raw trace PASS; provider replay not exercised | Forge stronger trace, replay remains incomplete |
| Determinism | not proven | explicit same seed accepted but traces diverged | Neither production-grade reproducibility proven |
| Lifecycle/headless | real server start/shutdown | bounded automated run under Xvfb | Both viable but nontrivial |
| Integration depth | substantial | promising in-process hooks; external adapter still substantial | Unproven production depth |

## Why Forge is not selected despite the higher score

The frozen score is a feasibility score, not a production-readiness threshold. The production bridge requested by J-P3D would need a real fail-closed chain:

1. external provider handshake and identity;
2. external state read with a stable state/revision identity or equivalent;
3. complete machine-listable legal choices for that state;
4. an externally selected legal action submitted against that state;
5. semantic rejection of illegal and stale actions;
6. resulting state/events/trace attributable to the same provider run.

P3C proves that Forge can build, run real four-player RogShai Commander, expose strong native controller/state hooks and emit high-quality ordered traces. It does **not** prove the complete external state/action/rejection chain. Building a new bridge now and calling it validated would rely on unproven semantics, contrary to J-P3D.

XMage has the same core production gap with weaker real end-to-end multiplayer/controller evidence.

Therefore neither provider is sufficiently evidenced for a regular production bridge in J-P3D.

## Existing project safety boundary

The project already has a provider-neutral ExternalRulesAdapter/protocol surface and a real `engine_mode=external` path. The existing matchup service blocks when the provider probe is not `available` as `external_rules_engine` and explicitly reports `synthetic_or_tactical_substitution = false`. Tactical Oracle, Structural Simulator and external-rules-engine results remain distinct evidence classes.

Universal RunIdentity already binds `engine_mode`, `engine_provider`, provider version/pin and capability-hash fields. For an unvalidated production external provider, provider version/pin and capability hash remain intentionally `UNKNOWN`; therefore P3D records:

```text
engine_mode_external_fail_closed = PASS
run_identity_engine_binding = PARTIAL
```

`PARTIAL` here is deliberate: engine mode/provider are bound and evidence classes are separated, but no selected production provider handshake exists from which a production provider pin/capability hash can be attested.

## Production bridge

```text
production_bridge = not_built
production_bridge_fixture_validation = NOT_APPLICABLE
```

No new provider adapter, fake bridge, Tactical fallback, Structural fallback or cosmetic hybrid was added.

The frozen P3B/P3C fixture results remain the only provider fixture evidence. Missing or partial fixtures stay missing or partial.

## P3 closeout

```text
J_P3_COMPLETE = true
J_P4_READY = true
J_P3_EXTERNAL_ENGINE = BLOCKED_WITH_REAL_EVIDENCE
provider_selected = false
```

P3 completed its investigation contract: both frozen providers were tested for real, scored under the same frozen model, compared, and a production decision was made. The unresolved External-Engine blocker remains visible for J-FINAL. P4-P6 may proceed where technically independent of a production external engine.
