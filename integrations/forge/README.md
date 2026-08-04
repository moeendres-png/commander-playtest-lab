# Forge bridge integration

Forge is the Phase-8 fallback rules backend and remains useful for AI-driven full-game sanity checks.

The bridge must be built as a separate Java process against a pinned Forge revision and implement `docs/rules-engine-bridge-protocol.md`. It should use Forge engine APIs directly; desktop click automation is not an accepted adapter.

Required bridge responsibilities:

- import `.dck` or normalized deck data;
- create a Commander multiplayer game or injected game state;
- enumerate legal engine actions;
- submit a selected action;
- export action/game logs and normalized outcomes;
- report the exact Forge revision and available reproducibility controls.

Configure it with:

```bash
export COMMANDER_LAB_FORGE_BRIDGE_CMD='java -jar /path/to/forge-commander-lab-bridge.jar'
commander-lab probe-rules-engines --root .
```

Forge uses GPL-3.0. The project therefore treats the bridge as a separately built and launched process. No Forge binary or source-derived artifact is bundled here.
