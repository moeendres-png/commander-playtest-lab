# J-P3C Forge Raw Evidence

Provider: `Forge forge-2.0.14 @ a37a865a53280dd8ad6fad3384d69611e8c5a42f`

This directory is a repository-side provenance index. The immutable raw ZIP artifacts are stored in GitHub Actions and Google Drive and are identified in `manifest.json` by run, artifact, SHA-256 and Drive ID.

## Executed evidence

### Runtime evidence

Run `31429537724`, artifact `9078696345`.

- exact frozen Forge source acquired and verified;
- Java 17 / Maven multi-module build succeeded;
- real Forge `sim` process executed under an automated virtual display because the desktop launcher initializes Swing before dispatching simulation mode;
- real four-player Commander session: RogShai plus three Gavi decks;
- exact `Ishai, Ojutai Dragonspeaker` + `Rograkh, Son of Rohgahh` partner pair loaded and both commanders cast repeatedly;
- native trace contains phase transitions, stack add/resolve, combat, damage, zone changes, countering, triggers, boardwipe effects, replacement effects and game outcome;
- process exited `0` inside the bounded timeout and left no Forge process;
- a second run with the identical explicit seed `424242` also exited `0`;
- the two normalized traces were not identical. Seed input is therefore demonstrated, but full same-seed trace determinism is not.

### Build/controller evidence

Run `31429032677`, artifact `9078423792`.

- exact frozen pin and provider tree captured;
- Java 17/Maven build succeeded;
- frozen-source controller/state/action surfaces captured, including `PlayerController`, `PlayerControllerAi`, `GameView`, `GameState`, stack/log/event surfaces and Commander state;
- the first no-display desktop invocation exited before useful gameplay output. This diagnostic is not treated as a provider failure because the same frozen build subsequently ran successfully under Xvfb.

## Evidence boundary

The real simulation proves Forge rules execution and its native AI/controller path. It does **not** prove a production-ready external adapter that emits a complete machine-listable legal-action set, binds actions to a state revision, accepts an externally selected live gameplay action, or rejects a stale/illegal externally supplied action without state mutation. Those items remain PARTIAL or NOT_RUN as recorded in the report/matrix.

No Structural Simulator, Tactical Oracle or mock result is used as Forge evidence.
