# L2 — RG-02B Commander-Damage Wrapper

## Terminal Handoff

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg02-commander-damage-wrapper-20260924`

**L1 predecessor:** `ad1913b4abad20662a121b1ece3926148f325807`

**L2 implementation head before handoff:** `cc9bd438e50e4ada86be0d49805b60ddbea5eaeb`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd`

**Draft PR:** #243, stacked on `sol/residual-mage-repin-20260924`

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Work Completed

- Extended `XmageNativeStateRestoration.Plan` with explicit Commander-damage edges.
- Parses frozen `commander_damage_matrix` rows as semantic `source_commander_id / damaged_player / combat_damage`.
- Resolves semantic Commander ids to XMage's genuine native Commander main-card UUIDs via the authoritative Commander identity set.
- Restores accumulated Commander combat damage only through CARD-scope `CommanderInfoWatcher.restoreDamageStateForGameLoad(...)`.
- Preserves native `CommanderPlaysCountWatcher` restoration for prior cast counts.
- No Lab-side Commander-damage ledger and no synthetic historical damage-event replay.
- Pre-resolves Commander bindings, CARD-scope watchers and damaged-player ids before native mutation.
- Added actual-runtime wrapper regressions covering frozen damage records, 20/21 threshold behavior, split commanders, partners, MDFC identity binding, 3P/4P/5P restoration, invalid semantic references, fresh-session replay and a decoy setup copy that must not acquire Commander identity.

## New Findings

- The post-M1–M4 Mage pin exposes a correct game-load restore seam on `CommanderInfoWatcher`; the prior Lab Phase-1 reuse report that classified Commander-damage restoration as unavailable is invalidated by the Mage remediation and L1 re-pin.
- Exact binding must use the engine's Commander identity set, not command-zone enumeration alone: a Commander can be represented by the same native identity after zone transitions while setup copies with the same name are not Commanders.
- Existing Mage RG-02 runtime qualification remains the deeper authority for later real damage after control change, blink/re-entry, MDFC and mutate. L2 qualifies the Lab binding/restoration boundary and native SBA consumption of restored state.

## Changes

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageNativeStateRestorationTest.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageCommanderDamageRestorationTest.java`

## Tests / Evidence

All pull-request workflows on exact L2 head `cc9bd438e50e4ada86be0d49805b60ddbea5eaeb` completed successfully:

- CI — run `36176819040` — SUCCESS
- External XMage Integration — run `36176819228` — SUCCESS
- XMage Full Game Conformance — run `36176819048` — SUCCESS
- XMage Real 4P Technical Smoke — run `36176819144` — SUCCESS
- H4 Docker Materialization — run `36176819133` — SUCCESS

PR #243 is mergeable and remains Draft / DO NOT MERGE TO main.

## PASS / FAIL / UNKNOWN

### PASS

- native semantic Commander-id binding
- Commander-damage game-load restoration
- 20 vs 21 native state-based loss consumption
- independent damage per Commander / Partner
- 3P/4P/5P Lab restoration
- MDFC front Commander identity binding at the wrapper boundary
- fail-closed unknown Commander/player/negative amount validation
- fresh-session restored terminal-state reproducibility
- decoy setup-copy non-Commander isolation
- complete active CI / XMage integration gates

### FAIL

None in L2 scope.

### UNKNOWN / outside L2

- General arbitrary frozen-state reconstruction remains unsupported unless covered by later stacked workstreams.
- Temporal arrival outside the qualified turn-1 precombat-main envelope remains L3.
- Causal stack reconstruction remains L4.
- Controller/owner divergence remains L5.
- Broader causal elimination reconstruction remains L6.
- Hidden-state restoration + semantic replay integration remains L7.

## Remaining Blockers

None for L3 start.

## Outputs

- Draft stacked PR #243
- native Commander-damage wrapper implementation and regressions
- this persistent handoff

## Dependencies Unblocked

L3 may start from the exact terminal head produced by this handoff commit.

## Exact Next Action

Create/resume `sol/rg03-temporal-driver-20260924` from the exact L2 terminal head and implement a genuine engine-progression temporal driver. It must reach supported later temporal checkpoints by ordinary provider decisions/transitions, never by direct clock-field assignment or fabricated phase state.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
