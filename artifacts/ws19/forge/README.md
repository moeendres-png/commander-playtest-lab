# WS-19 Forge qualification evidence

This directory contains **proprietary-side configuration and committed evidence only**.

The Forge-side qualification Java sources are generated only after CI checks out the pinned `Card-Forge/forge` repository into a separate workspace. Generated Java sources and compiled classes are GPL-side qualification artifacts and are uploaded as workflow artifacts; they are not imported by the proprietary Commander Lab package.

The proprietary launcher performs only WS-10R transport validation. It does not reconstruct Forge legality, targets, costs, mana, priority, combat, triggers, replacement/prevention, continuous effects, state-based actions, Commander semantics, multiplayer semantics, or rules randomness.

The first WS-19 provider increment is intentionally fail-closed: it proves the isolated-process shell, exact handshake, callback inventory generation, and denominator-complete common-harness execution. Until real Forge game/DecisionFrame routing exists, semantic fixtures return `UNSUPPORTED` and cannot receive Architecture Freeze credit.
