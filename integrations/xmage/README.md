# XMage bridge integration

XMage is the preferred Phase-8 tactical oracle.

Build a small Java bridge against the same XMage revision used for validation. The bridge must expose the JSONL methods documented in `docs/rules-engine-bridge-protocol.md` and should use XMage's test/scenario facilities rather than GUI automation.

Required bridge responsibilities:

- convert `RulesDeckInput` into XMage deck objects;
- create a Commander multiplayer game or test fixture;
- map XMage game objects and choices to stable external IDs;
- return only currently legal actions;
- translate `ActionProposal` into one XMage choice;
- export game/test logs and normalized results;
- report whether RNG seed injection is genuinely supported.

Configure it with:

```bash
export COMMANDER_LAB_XMAGE_BRIDGE_CMD='java -jar /path/to/xmage-commander-lab-bridge.jar'
commander-lab probe-rules-engines --root .
```

No XMage binary or source-derived artifact is bundled in this repository.
