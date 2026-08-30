# WS-25 — FORGE BROAD BEHAVIORAL QUALIFICATION EXPANSION

## Objective

Expand the completed WS-23 Forge Rules-Service architecture toward the frozen Full-Rules Commander qualification denominator without reopening the already-passed architecture-feasibility question absent contradictory runtime evidence.

## Inputs

- Commander Lab WS-23 PR head: `a059dd3008ace091fd20965a709d8b0fe245e331`
- WS-23 runtime head: `f024ba494b7367a514efcb5b89687ffcefb8a154`
- Forge: `Card-Forge/forge@1e604105f9e279331063824943b9222b6589f5d8`
- Forge tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- Forge version: `2.0.15-SNAPSHOT`
- Protocol: `commander-lab.rules-service/1.1.0`
- Frozen 135-fixture common manifest
- Frozen 29-card actual-card denominator

## Authority

1. newest direct user instruction;
2. freshly verified exact repository/PR/commit state;
3. current canonical MTG authority for semantic adjudication;
4. frozen project handoffs/manifests as qualification contract;
5. historical artifacts only as provenance.

## In Scope

- preserve all WS-23 regressions;
- broaden strict Forge `PlayerController` external decision coverage;
- execute exact common-fixture semantic families where materialized;
- complete denominator accounting without missing/duplicate fixture IDs;
- AF04–AF09 evidence expansion;
- defect separation: Forge rules vs provider mapping vs fixture setup vs authority blocking;
- differential-ready normalized evidence;
- candidate-specific CI and Draft PR.

## Out of Scope

- merge;
- final production Rules-Core selection;
- Architecture Freeze declaration;
- weakening WS-10R or changing the common denominator;
- copying Forge scripts into proprietary canonical data;
- holdout consumption;
- deck optimization;
- permanent upstream Forge modification.

## Dependencies

WS-09, WS-10/10R, WS-12, WS-23 and WS-24 remain binding. The WS-05 and WS-04/11 denominators remain frozen.

## Required Deliverables

The workstream must produce source locks, regression matrix, complete decision-surface matrix, AF04 coverage, 17 micro-rule matrix, 36 multiplayer/Commander matrix, 20 hidden-information matrix, five replay/RNG matrix, 29-card matrix, full 135 result, AF00–AF11, defect registers, differential evidence, hashes, CI evidence, Draft PR, and `WS25_FINAL_HANDOFF.md`.

## Hard Gates

`UNKNOWN != PASS`, `PARTIAL != PASS`, `NOT_RUN != PASS`, `UNSUPPORTED != PASS`, and `CODE_DERIVED != RUNTIME_VERIFIED`. No fallback AI/GUI/default/random/first-option/silent-skip legality path is permitted. Forge remains sole Rules authority behind a genuine separate GPL process.

## Evidence Requirements

Every PASS must identify executed runtime evidence or a gate-specific reproducible source/build/topology proof where the gate is structural. Missing fixture materialization is not a Forge rules defect. Rules defects may not be repaired in the proprietary adapter.

## Stop Conditions

Set `FORGE_ARCHITECTURAL_STOP` only for direct evidence of a fundamental inability to preserve external legal-choice authority, actor-safe observation, replay accountability, or the required GPL boundary. Ordinary missing callback/fixture implementation is a blocker, not an architectural stop.
