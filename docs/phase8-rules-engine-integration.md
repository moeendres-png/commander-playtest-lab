# Phase 8 — tactical and rules-engine integration

## Decision

XMage remains the preferred tactical rules oracle because the project already selected it for stack, trigger, combat, and scenario tests. Forge remains the fallback and broader AI-game backend. Both use the same persistent JSONL adapter contract.

The repository does not bundle either upstream engine. XMage is MIT-licensed; Forge is GPL-3.0. A Forge bridge should remain a separately built and launched process. This document is technical guidance, not legal advice.

## Implemented components

```text
src/commander_lab/engine/rules/
├── base.py       adapter authority boundary
├── bridge.py     persistent JSONL subprocess client and Forge/XMage adapters
├── manager.py    probe and preferred-backend selection
├── project.py    local Korvold/RogShai deck conversion
├── registry.py   interaction and card validation registry
├── tactical.py   bounded deterministic tactical oracle
└── validation.py Phase-8 validation runner
```

## Current execution status

The local tactical backend is executable and supports:

- loading the current Korvold and RogShai snapshots;
- starting one- to ten-player Commander sessions;
- deterministic initial shuffling and starting hands;
- injected tactical scenarios;
- legal-action retrieval;
- validated action submission;
- immutable event logs;
- normalized results.

The container used for Phase 8 did not contain Maven, XMage, or Forge and could not resolve GitHub. Therefore no external result is represented as successful. `rules_engine_validated` remains empty until a real bridge is configured.

## Differential interaction catalog

`data/evals/differential/project_critical_interactions.json` contains 73 interactions covering:

- Commander tax, command-zone changes, and separate commander-damage counters;
- Kediss, Jeska, double strike, and normal damage;
- stack order, APNAP trigger order, cast triggers, Silence, and counterspells;
- destroy, exile, -X/-X, phasing, shroud, hexproof, and indestructible;
- Korvold sacrifice and land-recursion packages;
- token, sacrifice, graveyard, and table-damage engines;
- RogShai combat-draw and spellslinger packages;
- selected wipes and flexible interaction.

The generated `data/rules/validation_registry.json` includes every card in the local Oracle subset. Cards without a registered tactical case are marked `structural_only`.

## Commands

```bash
commander-lab probe-rules-engines --root .
commander-lab validate-rules-phase8 --seed 20260804 --root .
```

Run the local bridge contract directly:

```bash
PYTHONPATH=src python scripts/tactical_rules_bridge.py
```

## External bridge acceptance

An external adapter is accepted only when it can:

1. report its real backend and version;
2. load a complete current deck;
3. start or inject a Commander state;
4. return legal actions;
5. reject an illegal action;
6. execute a legal action;
7. return a normalized state and logs;
8. match the project-critical interaction result.

The release gate requires at least 50 matching external observations at a 100% match rate. Blocked or missing backends never count as passes.
