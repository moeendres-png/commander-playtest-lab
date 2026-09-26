# Phase 8 — Tactical and rules-validated mode

## Outcome

Phase 8 implements the complete Python-side tactical/rules-engine boundary and a bounded deterministic tactical oracle. The local acceptance gate passes. The external rules-engine gate remains blocked because neither XMage nor Forge was installed or configurable in the execution container.

No external result is represented as successful. Consequently, no card or interaction currently has `rules_engine_validated` status.

## Version

- Package: `0.8.0`
- Tactical engine: `tactical-0.8.0`
- Structural engine semantics: unchanged from Phase 7
- Current deck snapshots: unchanged
- Google Drive: not accessed or modified

## Implemented adapter boundary

The new adapter interface supports:

1. backend capability probing;
2. loading an exact 100-card Commander deck;
3. starting one- to ten-player Commander sessions;
4. deterministic seeds or an explicitly injected starting state;
5. tactical scenario creation;
6. immutable state retrieval;
7. legal-action retrieval;
8. strict programmatic `ActionProposal` submission;
9. event and raw game-log retrieval;
10. normalized results transferred to Pydantic models.

The authority boundary remains strict: an agent may select only an action that the backend exposed as legal. It cannot directly mutate life totals, zones, mana, stack objects, commander damage, or winners.

## Backends

### Local tactical backend

`TacticalRulesAdapter` is executable in the repository and provides deterministic, bounded scenario validation. It is not a complete Magic rules engine and can produce only `tactical_validated` evidence.

### XMage adapter

`XMageRulesAdapter` is the preferred external tactical adapter. It uses a persistent JSONL subprocess contract configured through:

```bash
export COMMANDER_LAB_XMAGE_BRIDGE_CMD='java -jar /path/to/xmage-commander-lab-bridge.jar'
```

### Forge adapter

`ForgeRulesAdapter` is the fallback external adapter and uses the same contract:

```bash
export COMMANDER_LAB_FORGE_BRIDGE_CMD='java -jar /path/to/forge-commander-lab-bridge.jar'
```

Both external adapters verify that the bridge identifies itself as the configured backend. A tactical or fake bridge cannot silently masquerade as XMage or Forge.

## JSONL protocol

The bridge is persistent and accepts one request per line with a matching response ID. Required methods are:

- `probe`;
- `load_deck`;
- `start_commander_game`;
- `create_scenario`;
- `get_state`;
- `get_legal_actions`;
- `submit_action`;
- `get_logs`;
- `get_result`;
- `shutdown`.

The full contract is documented in `docs/rules-engine-bridge-protocol.md`.

## Tactical interaction catalog

The differential catalog contains 73 project-critical cases, exceeding the requested minimum of 50. It covers:

- Commander tax and command-zone movement;
- commander damage tracked separately per commander;
- Kediss, Jeska, double strike, and normal damage;
- stack LIFO and APNAP trigger ordering;
- Kaervek cast triggers and counterspells;
- Silence and spell-casting restrictions;
- indestructible versus destroy, exile, and -X/-X;
- Toxic Deluge, Fire Covenant, Massacre Wurm, Culling Ritual, Farewell, Vandalblast, and Winds of Rath;
- Korvold sacrifice triggers and costs;
- Academy Manufactor, Killer Service, Ophiomancer, and Idol of Oblivion;
- Titania, Ramunap Excavator, Splendid Reclamation, Aftermath Analyst, Tireless Provisioner, and Tireless Tracker;
- Mirkwood Bats, Mayhem Devil, Mazirek, Braids, Bontu, Pitiless Plunderer, and Goblin Bombardment;
- graveyard interaction through Rakdos Charm, Soul-Guide Lantern, and Bojuka Bog;
- RogShai combat-draw and commander-damage packages;
- Ishai, Veyran, Guttersnipe, Kykar, Storm-Kiln Artist, Archmage Emeritus, and Whirlwind of Thought;
- protection and counters including Esior, Slip Out the Back, Lofty Denial, Wash Away, An Offer You Can't Refuse, Dovin's Veto, Loran's Escape, Lightning Greaves, and Swiftfoot Boots;
- state-based actions for zero toughness and token zone changes.

All 73 cases pass the local tactical oracle.

## Validation registry

`data/rules/validation_registry.json` contains every card in the local Oracle subset plus additional cards named by the interaction catalog.

Current status:

| Level | Cards |
|---|---:|
| `structural_only` | 108 |
| `tactical_validated` | 59 |
| `rules_engine_validated` | 0 |

The registry uses conservative aggregation. A card is elevated only when all registered cases for that card pass at the relevant level.

## Reproducibility and action round-trip

The Phase-8 runner validated:

- identical four-player starting zones for the same seed;
- loading the current Korvold and RogShai deck snapshots;
- creating an injected tactical state;
- retrieving one engine-authoritative legal action;
- submitting that action through the normal action validator;
- transferring the resulting state back into the Python model;
- capturing pre/post state hashes in the event log.

## External rules-engine status

The execution environment contained OpenJDK 21 but no Maven, XMage, or Forge. DNS resolution for GitHub was unavailable, so upstream sources or release binaries could not be fetched and built.

The following therefore remain open acceptance tasks:

1. build a pinned XMage bridge against the selected XMage revision;
2. execute deck-loading and injected-scenario acceptance tests;
3. run all project-critical cases supported by XMage;
4. repeat suitable cases with Forge for differential confidence;
5. store backend versions, raw logs, normalized observations, and evidence hashes;
6. elevate only matching cases to `rules_engine_validated`.

The release gate requires at least 50 matching external observations with a 100% match rate.

## Tests

The repository contains 120 tests. Category-complete execution produced:

- 119 passed;
- 1 skipped because no real XMage/Forge bridge was configured;
- 0 failed.

The split execution covered all collected test paths. See `PHASE8_TEST_RESULTS.txt`.

## Commands

```bash
commander-lab probe-rules-engines --root .
commander-lab validate-rules-phase8 --seed 20260804 --root .
```

Bridge contract test:

```bash
PYTHONPATH=src python scripts/tactical_rules_bridge.py
```

Standalone validation:

```bash
PYTHONPATH=src python scripts/run_phase8_validation.py --root .
```

## Non-goals retained

- no millions of rules-engine games;
- no claim that the local tactical oracle is complete;
- no GUI click automation as a trusted engine adapter;
- no automatic deck changes;
- no promotion of blocked cases;
- no interpretation of tactical or structural outputs as empirical win rates.
