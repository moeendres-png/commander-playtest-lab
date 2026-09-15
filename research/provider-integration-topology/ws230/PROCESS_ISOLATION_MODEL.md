# Process Isolation Model (production lifecycle contract per candidate)

Evidence class: `CODE_DERIVED` (source inspection + sealed test facts; no new runtime).

## 1. XMage full-game lane

- **Discipline**: one game per fresh JVM (defense in depth; second create refused — live proof). B4-D compat lane differs (reusable bridge process + explicit per-game XMage end/cleanup + deck-handle release) — the handshake must declare which lane/topology the instance uses; the two disciplines are never mixed in one process.
- **Launch**: `EngineProcessManager` (external mode) spawns the bridge command (`COMMANDER_LAB_XMAGE_BRIDGE_CMD`); `Main full-game` serves JSONL on stdin/stdout; `verifyRuntimeLoaded` fails before accepting requests if the XMage runtime is absent; `java.awt.headless=true`.
- **Seed binding**: `game.setRulesSeed(orchestrationSeed)` + `setRequireExplicitSeed(true)` after construction, before any Rules-random consumption. No concurrency: the blocking decision controller forbids concurrent pending decisions (`BRIDGE_PROTOCOL_ERROR`); timeout (2 min) is terminal for the game.
- **Contract table**:
  - one game per process vs reusable: full-game lane = one game per fresh JVM; B4-D lane = reusable with per-game cleanup. Successor uses the full-game discipline for qualification evidence.
  - single-flight: controller-level (one pending decision at a time) + process-level (one game per JVM).
  - child crash: engine failure captured (`engineFailure` atomic ref + `engineErrorDiagnostics`); session fails with typed error; no outcome fabricated; parent sees non-zero exit / broken pipe as typed provider failure.
  - timeout: `DECISION_TIMEOUT` → terminal failure recorded, pending cleared, all waiters notified; game cannot continue.
  - protocol desync: `protocol_version_mismatch` / `invalid_json` / `BRIDGE_PROTOCOL_ERROR` → typed error, no state mutation.
  - orphan cleanup: `shutdown_engine` breaks the JSONL loop; per-game end/cleanup releases XMage objects + deck handles; `EngineProcessManager.stop` + log rotation; stale `ENGINE_PORT` refused (`port_available`).
  - resource limits: decision timeout (2 min); engine thread daemonized (`bridge-game-*` / XmageThreadFactory); frozen campaign policy bounds total runtime (G11/AF10 scope, successor test plan).
  - seed binding: explicit orchestration seed per game; same-seed twins MATCH, distinct-seed DIVERGE (per count per mode).
  - clean-process replay: fresh JVM per replay; transcript-hash comparison; `.incomplete` never sealed; atomic writes.
  - batch isolation: fresh JVM per game ⇒ batches are isolated by construction; no shared mutable Core state across games.

## 2. Forge WS227 (Protocol 2.0.0 + SemanticReplay)

- **Discipline**: one game per process enforced via fresh child JVM per record/replay; second create refused by single-flight MyRandom discipline + session lifecycle (WS227 seal `PROCESS_ISOLATION` PASS).
- **Launch**: `BridgeMain` (Protocol 2.0.0 JSONL stdin/stdout, diagnostics stderr); `FORGE_ENGINE_SHA` bound per child via sysprop + env; `DISPLAY` removed; protocol purity (stdout JSONL only); `VersionInfo` hard gate F3 (no valid 40-hex SHA ⇒ gameplay handlers refuse; identity observability only).
- **Seed binding**: `BridgeSession.launch` calls `MyRandom.bindSeed(seed)` on the protocol thread before the game thread shuffles/rolls; `bindSeed` installs CountingRandom, resets AtomicLong, stores rootSeed/explicit. Global `MyRandom` scope ⇒ **concurrent seeded games share the global and MUST be serialized by the orchestrator (single-flight documented, not re-architected)**. Unseeded legacy `setRandom` path is observational-only; replay requires explicit binding.
- **Contract table**:
  - one game per process vs reusable: one game per process (no reusable seeded sessions).
  - single-flight constraints: orchestrator-serialized seeded execution; `markAnswered`/option-`consume` guards make resolution exactly-once; concurrent replays fail closed as unknown options.
  - child crash: `session_failed` audit + `Status.FAILED` + `failReason`; `WS227SeparateProcessTest` proves record/replay children exit 0 on success — non-zero exit is typed provider failure, never a PASS.
  - timeout: `awaitTerminal(millis)` bounded waits; parked frames abort on shutdown (`SessionAbortedException` → CLOSED).
  - protocol desync: `PROTOCOL_VERSION_MISMATCH` / `MALFORMED_REQUEST` (incl alias-disagreement rules) → typed error before engine contact.
  - orphan cleanup: `shutdown` interrupts + joins game thread, aborts parked frame, counts down terminal latch; `SHUTDOWN_GAME`/`SHUTDOWN_ENGINE` verbs; parent temp-dir atomic writes.
  - resource limits: same campaign-policy bounding as XMage (successor test plan); JVM-per-game bounds memory residue by construction.
  - seed binding: explicit `seedBinding` per session; `RULES_RNG_CALL_DRIFT` / `RESULT_DRIFT` on any divergence.
  - clean-process replay: two fresh child JVMs (record + replay) same manifest/seed, coordinate comparison, no injection.
  - batch isolation: JVM-per-game + single-flight serialization ⇒ isolated; the successor orchestrator MUST NOT introduce concurrent seeded Forge games (would corrupt the global `MyRandom` stream — fatal correctness blocker, not a performance tradeoff).

## 3. Rules for the successor

1. Do not introduce concurrency the provider Core does not support (Forge global `MyRandom` ⇒ serial seeded execution; XMage full-game ⇒ one pending decision + one game per JVM).
2. Fresh-process discipline is the default for qualification evidence on both providers; reusable processes (B4-D lane) are operational convenience, not evidence producers.
3. Every lifecycle transition (launch/crash/timeout/desync/shutdown/orphan) has a typed, logged, non-PASS outcome. No transition silently continues a game.
