# XMage Headless Engine Performance — Research Report

**Mission:** How to make an XMage-based (magefree/mage, Java) headless game-simulation engine FASTER without changing game semantics — batch simulations of 4-player Commander games, thousands of full games, ~3,000 player decisions/game, engine ~96% of wall time at ~15–45 ms per decision round trip.

**Evidence classes:** **(A)** documented/measured facts · **(B)** strong community/maintainer consensus · **(C)** my inference from (A)+(B). Every lever is labelled. Where no source supports an effect size, I say so — do not invent one.

**Method / limitation up front:** The live research browser could not resolve github.com (DNS failure), so GitHub issues/PRs were reached via the web index, the project's own wiki mirrors, DeepWiki's source-indexed summaries of magefree/mage (which cite file + line ranges), and the Slightly Magic forums. I could **not** open issues #5079 / #6738 or any individual performance PR directly — see Honest Gaps. No public profile, JFR recording, or benchmark of XMage running headless batch games exists in anything I found. Anyone claiming a specific hotspot percentage for *this* workload is guessing until you profile it.

---

## Summary

1. **The single biggest structural fact (A):** XMage does **not** have an undo/memento engine. Its state model is *copy the whole `GameState`* — deep copying is the documented mechanism for rollback, bookmarks and AI simulation (`Game.createSimulationForAI()` returns "a complete copy"). Its own built-in AIs pay that copy per simulated decision. If your headless driver (or any bookmark/rollback/save-state call in your path) triggers a copy, restore, or a full re-serialisation per decision, that — plus continuous-effects/state-based-action re-checking after every change — is the architecture you are fighting, not a single slow method.
2. **But in ordinary play, a copy is not documented to happen per external decision (A/C).** Copying is tied to rollback/bookmarks and to AI simulation. So the first job is measurement: profile one game and split the 15–45 ms into (i) engine rules work, (ii) state copy/bookmark, (iii) continuous-effects recomputation, (iv) watcher/trigger scanning, (v) logging / game-view building, (vi) your JSON serialisation. The prioritised list below is ordered by *expected value × low semantic risk*, not by a measured profile I do not have.
3. **Cheapest wins first (A/B):** one long-lived JVM per batch (amortises card-repository/H2 build, class loading and JIT warmup over thousands of games), pre-built/shared H2 card DB, logging and notifications off in simulation mode (XMage already has a simulation flag that suppresses notifications/logging — use the same path), fixed heap `Xms=Xmx`, Parallel GC (the documented batch-throughput choice) benchmarked against G1 and Generational ZGC, and AppCDS/Leyden (measured −10% to −47% startup on other apps; −20% on a ~25k-class desktop app, the closest analogue).
4. **Protocol (A/C):** JSON-vs-binary benchmarks show ~2–5× on serialisation itself, but serialisation of a KB-scale state is sub-millisecond to a few ms — it cannot explain 15–45 ms unless you are serialising the *entire* game (all zones, all card text, history/log) per decision. Cutting the payload (diff / decision-relevant view only) and, better, moving the driver **in-process** will beat any codec swap. Measure payload bytes/decision first.
5. **Do not import Magarena's speed wholesale (A):** Magarena is fast partly because it *changes the rules* — no mana pool, triggered abilities auto-ordered, layer dependency ignored. Forge's elegant undo system was a 2014 proof-of-concept that its author said would require rewriting every effect/trigger; shipped Forge simulation still copies the game (`GameCopier.makeCopy()`).
6. **Semantic identity is fragile in specific, named places (A/B):** iteration order over `HashMap`/`HashSet`-backed collections, RNG seeding/call order, watcher/trigger ordering, continuous-effects layer/timestamp/dependency ordering, and anything timing-dependent (AI think-time cutoffs, timeouts). GC choice, CDS, heap size, codec, and in-process embedding are semantics-neutral *provided* they do not change those orders or the number/order of RNG draws.

---

## Findings

### 1. XMage engine internals and known performance costs

**State representation and copying — (A)**
- `GameState` "represents a complete snapshot of the game at any given moment. It contains all the information needed to represent the current state and can be copied for rollback or simulation purposes." Components: `players`, `playerList` (APNAP order), `stack`, `battlefield`, `turn`, `combat`, `activePlayerId`, `priorityPlayerId`, `turnNum`, `stepNum` (`GameState.java` 65–96, via DeepWiki Game State Management).
- The engine's state-copying architecture is explicitly: "**Deep Copying**: Complete game state duplication for simulations; **Bookmarking**: Savepoints within a game for rollback operations; **Player State Sync**; **LKI Tracking**: Last Known Information for game objects" (`GameState.java` ~2800–2900, `PlayerImpl.java` 311–414, `GameImpl.java` ~4000–4100, via DeepWiki Game Engine).
- AI simulation: "Simulations are created through `Game.createSimulationForAI()` which returns a complete copy suitable for AI analysis. The simulation flag prevents certain operations like user notifications and logging" (`GameImpl.java` 259–264). That simulation flag is the documented fast-path pattern to reuse for a headless driver — if your driver goes through the human/server path instead, you are paying for notifications/logging/view-building that the AI path skips **(C, direct implication of A)**.
- Every card class implements the same copy idiom — a copy constructor `private X(final X card){ super(card); }` and `copy()` returning a new instance (visible in card sources throughout the repo). So a `GameState` copy is not a `memcpy`: it walks permanents/cards/abilities/effects/watchers and re-constructs them object-by-object **(A for the idiom; C for the cost characterisation)**. In a late-game 4-player Commander board (100+ permanents, each with abilities, counters, attachments) that walk is proportional to total objects × abilities, not to the size of the decision **(C)**.
- Rollback is a real, user-facing feature with real cost/bugs in shipped releases: release 1.4.53 notes "Fixed game freeze on rollback usage for some use cases; Fixed game errors in big/late games" — i.e. state save/restore in big/late (Commander-like) games is a known fragile, expensive path **(A, release wiki)**.

**Continuous effects / layers — (A for structure, C for hotspot status)**
- XMage implements the full layer system through continuous effects re-applied by the engine; Magarena's wiki, by contrast, documents *its* shortcut: "order of effects within layer depends on the timestamp of the effect, effect dependency is not considered" — listed as a deliberate rules simplification. The fact that a competing engine calls out dependency handling as the thing it *drops* is evidence that correct dependency-aware layer recomputation is one of the expensive, correctness-critical parts of a full engine **(B/C)**.
- **Honest gap:** I found no XMage source summary, issue, or profile that quantifies `applyEffects`-style recomputation, how often it runs per decision, or whether it is incremental or full-board. This is the most likely per-decision hotspot for a driver that does *not* copy state — every state change in Magic invalidates P/T, types, abilities and control, and a non-incremental implementation re-derives them for every permanent — but in this report that is **(C) inference from the rules structure, not a measured XMage fact.** Profile it (`applyEffects` / continuous-effects methods in a JFR/async-profiler run) before optimising it.

**Watchers / events — (A for scale, C for cost)**
- The event system is large: "`GameEvent.EventType` enum with over 200 different event types" (`GameEvent.java` 36–400), processed through `GameImpl` (~2000–2100). Watchers are a pervasive pattern — dozens of `mage.watchers.common.*` classes (`SpellsCastWatcher`, `CastSpellLastTurnWatcher`, `AttackedThisTurnWatcher`, `PlayerLostLifeNonCombatWatcher`, …), each registered on game objects and offered events. Every game event therefore fans out to every registered watcher/trigger source to check applicability **(A for existence/scale; C for the fan-out cost claim — the per-event dispatch loop itself was not retrieved)**.
- Trigger/state-based-action checking must, by the rules, happen after essentially every game action. With 4 players and a large board, the number of *checks* per decision grows with permanents + watchers + stack objects, even when nothing triggers **(C)**.

**Card repository / reflection — (A)**
- See §2. In-game, card creation goes `CardInfo → createCard` (`CardInfo.java` 110–120), bridging stored DB metadata (including the implementing `className` string) to a live object. Class-per-card (~32,000 unique cards) means instantiation is by class lookup/construction, not by data-driven interpretation. Per-game cost is bounded by deck size (400 cards in 4× Commander) if the repository is warm and cached; per-*decision* cost should be ~zero — if your profile shows repository/DB work inside a game, something is cache-missing (see the `DatabaseBigQueryPerformanceTest` note in §2) **(A/C)**.

**Maintainer/community reports of slowness — (B)**
- The only official performance advice in the README is memory: "The main way to increase performance or fix micro-freezes — increase max memory usage… `-Xmx3000m`… It's useless to give 5+ GB memory; If you play many AI games then it's recommended to change Server java options with same value too" **(A — and telling: no engine-level tuning guidance exists)**.
- Forum bug-report thread (XMage 1.4.47): a user reports "AI will randomly, but almost always, enter a state where it takes upwards of 20s–3mins to resolve individual triggers on the stack, phase changes, or attack steps" and cites GitHub issues **#5079** and **#6738** as "the two biggest reasons I can't even use the program for reliable deck testing." That is evidence of pathological (super-linear / combinatorial) blow-ups in trigger/combat evaluation in the *AI* path, not of steady-state per-decision cost — but it warns that worst-case decisions, not averages, may dominate a batch of thousands of games **(B, single-user anecdote + unretrieved issues)**.
- XMage's own AI modules: minimax-style `ComputerPlayer6/7` + `SimulatedPlayer2`/`SimulationNode2` (AI.MA plugin), and MCTS (`ComputerPlayerMCTS`, `MCTSExecutor`, `MCTSNode`, `SimulatedPlayerMCTS` in Mage.Player.AIMCTS). MCTS runs simulations on a `ThreadPoolExecutor` (`threadPoolSimulations`) — PVS-Studio's published static analysis of XMage notes this executor is never shut down. No engine-level fast-path (undo, incremental state) is documented for either AI; both work on copied games **(A)**.

### 2. Startup and loading costs

**(A) What happens at start:**
- XMage uses H2 databases "in the client, server, and test project; it includes card and extension/set data to provide a faster access to the needed card data" (developer wiki). `CardRepository` is a singleton (enum pattern) over H2; it creates tables if absent, checks/repairs database health, caches query results, handles DB version upgrades (`CardRepository.java` 28–102).
- Population is by *scanning card classes*: "`CardScanner.scan()` discovers cards from expansion sets; New cards are added to `CardRepository`" (DeepWiki Testing Framework, `CardScanner.java` 20–83). The developer wiki states the operational rule plainly: "As the XMage server program is started, all missing card entries for the card db are generated from the card classes. Nothing happens for already existing card records." A cold/empty DB therefore costs a scan+instantiation of the card universe (32,000+ unique cards, 91,000+ reprints per the README) once; a warm DB skips it.
- The project itself treats DB access as a performance risk: `DatabaseBigQueryPerformanceTest` exists to "monitor database query efficiency and prevent cache overflow issues that could crash the system during gameplay simulations," including an AI-simulation test with many name-choice queries and memory monitoring (DeepWiki Testing Framework, `DatabaseBigQueryPerformanceTest.java` 15–56) **(A)**. Translation: repeated large repository queries with a bounded cache have crashed simulations before — pre-warm and size the cache, and never let a per-decision path hit H2 **(C)**.

**(A/B) Cutting / amortising it:**
| Technique | Evidence | Expected effect |
|---|---|---|
| **Keep one JVM for the whole batch** (many games per process) | Direct consequence of A above: DB build, class loading, JIT are per-process costs | Converts all startup cost to ~zero per game after game 1. This is the dominant startup lever for "thousands of games" **(C, arithmetic)** |
| **Ship a pre-built H2 DB** (build once, copy the `db` files; don't delete/regenerate per run) | Dev wiki: missing entries are generated at startup; existing records are left alone; deleting db files forces rebuild | Eliminates the scan on every worker **(A mechanism, C size — unmeasured for XMage)** |
| **AppCDS** (`-XX:ArchiveClassesAtExit` / shared archive) | Oracle: CDS archive is memory-mapped and *shared between JVMs*, reducing startup and footprint. Measured elsewhere: −47% startup (939→497 ms, small Quarkus app, Red Hat); −10% (PetClinic, Pluralsight); **−20% (15 s launch, ~25,100 classes, ~250 MB archive, nipafx)** — the last is the closest analogue to XMage's class count | Startup only; no steady-state effect; zero semantic risk **(A)** |
| **Project Leyden AOT cache** (JDK 24/25+) | Same peak throughput as plain JVM, identical behaviour, faster start (comparison table, BackendBytes) | Startup + earlier peak; preferred over Native Image for a reflection/scanning codebase **(A/B)** |
| **GraalVM Native Image** | Fastest cold start but *lower peak throughput unless PGO*, and closed-world: reflection/dynamic loading need explicit metadata **(A)** | **Not recommended here (C):** XMage discovers and instantiates ~32k card classes dynamically — exactly the pattern Native Image restricts — and a batch workload cares about peak, not cold start |
| **`TieredStopAtLevel=1` (C1-only)** | Trades peak for startup (widely documented; see §3) | Wrong direction for long batches **(A/B)** |

- Also: run with `-Djava.awt.headless=true` and without client/server networking layers if your harness still launches them — XMage's test mode itself uses headless for CI (Development Testing Tools wiki) **(A)**. Stripping the JBoss/remoting server stack, image/token loading, and deck-editor DB from the worker is an inference-level win **(C)** — no source measures it.

### 3. JVM-level tuning for a single-threaded-per-game, allocation-heavy rules engine

**Garbage collectors — (A for the general rankings, C for applying them to XMage; no XMage-specific GC benchmark exists)**

| Collector | Documented character | Verdict for this workload |
|---|---|---|
| **Parallel** (`-XX:+UseParallelGC`) | "Scenario B: The Batch Processor — priority is total throughput" → Parallel; multi-threaded stop-the-world, highest throughput in several comparisons, long pauses irrelevant when there is no human | **Try first.** Your latency target is total batch time, not pause time. One caveat (C): if you run N game-workers per machine, Parallel's GC threads compete with other workers — cap `ParallelGCThreads` per worker |
| **G1** (default) | Balanced latency/throughput, regions, pause target; default for 6–128 GB heaps | Baseline. Its concurrent marking burns CPU that a batch job could spend on games (C) |
| **Generational ZGC / Shenandoah** | Pauses <1 ms / <10 ms *at a cost*: ZGC "High (8–20%) CPU overhead," concurrent compaction in Shenandoah | **Wrong tool unless pauses are proven to dominate (A for overhead, C for verdict).** You do not have a latency SLA per decision; you have a throughput bill. Low-pause collectors trade exactly the wrong currency |
| **Serial** | Lowest CPU/footprint, single-threaded STW, advised only for <100 MB heaps / 1-CPU containers | Only for tiny-heap, single-core workers; otherwise its long pauses on a large live board lose (A/C) |
| **Epsilon** (no-op) | Never reclaims; OOM when heap fills. Documented use: a *GC-free baseline* — "If Epsilon is 3 percent faster, memory management is a small slice; if it is 30 percent faster, allocation or barrier cost dominates" | **Use as a diagnostic, and possibly per-game:** run one game under Epsilon with a heap sized for one game to measure your GC ceiling. Running thousands of games in one Epsilon JVM will OOM (A) |

**Heap sizing — (A/B):** Set `-Xms = -Xmx` (no resize work), size so a whole game's live set + copy/bookmark headroom fits comfortably in old gen with room for allocation bursts; XMage's own guidance caps useful heap at ~3 GB for the interactive app and says 5+ GB is useless *for that app* — do not copy that number blindly for batch workers; instead run several smaller workers per machine (one game each) rather than one giant heap, which also bounds GC pause and failure blast radius **(C)**. Avoid exotic flags until a GC log (`-Xlog:gc*`) shows a problem.

**JIT / warmup — (A):** Tiered compilation exists to give "both fast startup and good long-term performance": C1 compiles quickly, C2 "observes and analyzes the code over a longer period… generates better-optimized native code" (Baeldung). For thousands of games in one JVM, warmup is amortised to noise — *provided* the batch is long and the code paths (card classes!) are exercised early. Practical consequences **(C)**: (i) discard/ignore the first N games when benchmarking, or run a warmup game per worker before timing; (ii) a worker that is restarted per game never reaches C2 peak for most card classes — another reason for long-lived workers; (iii) huge numbers of distinct card classes (Commander pools) mean the code cache and metaspace see far more classes than a typical app — watch for code-cache-full deoptimisation in logs if you rotate many decks.
**Published benchmarks for similar workloads:** none for XMage or any MTG engine were found. The transferable numbers are the GC/CDS ones above and the general result that C2 peak ≫ C1-only on long runs. Chess-engine analogies do not transfer: chess state is a fixed-size array copy; XMage state is a variable-size object graph — that difference *is* the problem **(C)**.

### 4. Comparable open-source Magic engines' speed techniques

**Magarena — undo/actions + iterative scoring (A), achieved partly by changing the game (A)**
- Minimax AI design (project wiki, AIMinimax page): "**Every game state change is done with simple actions**: Moderate memory consumption for deep trees; **Fast backward tree traversing thanks to undo support**; **Iterative scoring instead of scoring the full game situation**"; plus alpha-beta pruning and score caching; "Game state can be fully copied to evaluate choices in parallel" (copy only at thread boundaries); property caching in the engine for combat scoring; delayed mana-cost payment so the search does not enumerate payment permutations below the tree top.
- **But** Magarena's GameRules wiki lists deliberate semantic simplifications "taken to simplify the gameplay for the AI": no mana pool, X ≥ 1, triggered abilities ordered automatically, most choices made when the spell is put on the stack, combat damage auto-assigned, and **"order of effects within layer depends on the timestamp of the effect, effect dependency is not considered."** Magarena is a *different, smaller game* (2-player, far fewer cards). Its undo architecture is portable as an idea; its rules shortcuts are not **(A)**.
- No measured games/second or ms/decision figure is published in its wiki pages I read — the speed claims are qualitative ("fast") **(honest gap)**.

**Forge — shipped: copy; proposed: traversable undo (A)**
- Shipped AI simulation copies: `SpellAbilitySimulator` holds a `GameCopier` and does `Game game = copier.makeCopy()` per simulated ability, then resolves the stack in the copy (Slightly Magic, Traversable thread quoting the code). Myrd's original simulation prototype announcement (2015): "It currently only looks one move deep… It's off by default… A lot of [the issues] are in the underlying infrastructure (e.g. making a copy of the game state or UI still triggering from the copy of the Game that's being simulated)." So even Forge — the engine often cited as "the fast one" — pays a full copy per simulated move in production code **(A/B)**.
- The famous undo design (GameAction = single command that "changes the state of one thing and can undo that change"; GameEvent = ordered actions; undo pops actions to an `EventMarkerAction`; redo re-applies; a `ForgeRandom` that "tracks the seed… so that it can be set to the same thing every time an action needs redoing") was a **2014 proof-of-concept by a Forge programmer, explicitly not the shipped engine**, with the author's own caveat: "every effect, trigger, etc would need rewriting to use this system" and clone-vs-undo "would really depend on memory vs processing time" **(A)**. Cite it as a design, not as Forge's measured technique.

**XMage's own AI (A)** — see §1: MA minimax and MCTS both operate on `createSimulationForAI()` copies; MCTS parallelises simulations over a thread pool. There is **no** documented engine-level fast path (no undo stack, no incremental effects, no state hashing/transposition table) in XMage itself. If your driver needs lookahead, it inherits copy-per-node economics; if it does not need lookahead (external policy decides from the current state only), then *any* per-decision copy/bookmark in your path is pure overhead and the first thing to remove **(C)**.

### 5. Protocol / serialisation overhead

**How large can it get? (C, bounded by A facts)** No source publishes an XMage state-serialisation size. Bounds you can reason from: a decision-relevant view (hands for the deciding player, battlefield with P/T/counters/attachments, stack, life, mana, legal actions) is hundreds of objects; serialised naïvely with names, oracle text, set codes, UUIDs (36 chars each, repeated everywhere) and full history/log, a JSON state can plausibly reach **tens to hundreds of KB per decision** late in a Commander game. At 3,000 decisions/game × thousands of games, even 50 KB/decision is 150 MB of JSON per game. **Measure your actual bytes/decision before optimising the codec (C — this is the actionable claim).**

**What similar projects / benchmarks do (A):**
- Codec benchmarks (JMH, small objects): Protobuf/Avro-binary serialise in ~400–600 ns vs Jackson JSON ~1,100–1,200 ns; deserialise ~700 ns vs ~1,600 ns — binary ≈ **2×+ faster, not 10×**, on small payloads.
- Larger nested payload (~1 MB JSON, 10k objects, Micronaut benchmark): JSON 12 ms ser / 18 ms deser / 1.0 MB → Protobuf 2.1 / 3.5 ms / 0.3 MB; Kryo 1.5 / 2.0 ms / 0.2 MB — i.e. **~5× time and ~3–5× size at MB scale**. Codec gains grow with payload size, which is another way of saying: shrink the payload first.
- Pipe/stdin-stdout transport itself is not where 15–45 ms goes: local IPC moves MBs in milliseconds. The costs that *can* reach your range are (i) building the state view (walking the whole game graph, formatting strings) on the engine side, (ii) parsing it on the driver side, (iii) a flush/scheduling round trip per decision × 3,000, and (iv) doing any of that in an interpreted driver language per decision **(C)**.

**Ranked protocol levers (C, ordered by expected effect):**
1. **In-process embedding** — load the engine as a library in the driver's JVM/process (or JNI/JPype-style bridge) and pass object references / flat arrays, eliminating serialisation, parsing and pipe round trips entirely. This is the only protocol change that can plausibly remove *most* of the non-rules share.
2. **Incremental / decision-scoped state** — send a diff or only the deciding player's legal-action-relevant view; assign short integer IDs to objects instead of repeating UUID strings and card names/oracle text (send a card dictionary once per game). Preserves semantics *if* the driver never needed the omitted fields (see §6).
3. **Binary codec** (Protobuf/Kryo/Smile/MessagePack) on the remaining payload — measured 2–5× on the serialisation slice only.
4. **Batching / pipelining** — if decisions for *different games* are independent (they are, in batch simulation), run many games concurrently so pipe latency and GC pauses overlap instead of serialising the batch; per-decision latency stops mattering, only throughput does.

### 6. What must NOT be touched for semantic identity

"Identical decision sequences" requires the engine to present the same legal actions, in the same order, with the same RNG outcomes, to a driver that then chooses identically. Classify accordingly:

**Safe — no semantic effect if implemented carefully (A/B):**
- GC choice, heap size, `-Xms=-Xmx`, AppCDS/Leyden, JIT settings: these change *when* code runs fast, not what it computes. Caveat (C): any place the engine uses wall-clock time (AI think-time budgets like MCTS `thinkTime`, timeouts, "pass until…") becomes timing-dependent — a faster JVM can change how many simulations complete inside a time budget and therefore change decisions. **A headless batch that must be reproducible must replace time budgets with fixed iteration/decision counts.**
- Codec change, in-process embedding, diff protocol: safe iff the decoded state is field-for-field identical and object *ordering in lists presented to the driver* is unchanged.
- One-JVM-per-batch, pre-built H2 DB, logging/notifications off via the existing simulation flag: the flag is the engine's own documented simulation behaviour.
- Removing per-decision copies/bookmarks *that are never restored from*: safe. Removing a bookmark that rollback, a card effect, or your driver's undo relies on: not safe — audit callers first (C).

**Dangerous — can silently change outcomes (A/B):**
- **Iteration order.** Java `HashMap`/`HashSet` "do not specify in which order elements are iterated, possibly resulting in different results if the same code is run multiple times"; deterministic simulation guidance is to use linked/insertion-ordered structures and a seeded `Random` (MATSim dev guide, general Java fact). Any optimisation that swaps collection implementations, parallelises a scan (`parallelStream`, thread-pool simulation), resizes a map earlier, or changes insertion sequence can reorder: legal-action enumeration, trigger ordering, target enumeration, watcher dispatch — and the *first* differing choice cascades into a different game. Parallelising across *games* is safe; parallelising *within* a decision is not, unless order is re-imposed afterwards.
- **RNG behaviour.** Number, order and seeding of random draws (shuffles, coin flips, random targets/discards) must be identical. Forge's undo prototype needed a seed-tracking `ForgeRandom` precisely because redo must reproduce the same draws. Any change that draws RNG on a different thread, skips a "wasted" draw, or reseeds per game differently changes every downstream shuffle.
- **Continuous-effects ordering.** Layer, sublayer, timestamp and dependency ordering *are* the semantics (this is the thing Magarena explicitly fudges). Caching/incremental recomputation is safe only if the cache is invalidated on every state change that could affect any effect's applicability — a stale P/T or ability cache is a rules change, not an optimisation.
- **Watcher/trigger/state-based-action completeness.** Skipping "obviously irrelevant" watcher scans or SBA checks to save time is safe only with a proof of irrelevance per event type; a missed trigger is a different game. Indexing watchers by event type (so an event only visits watchers that can care) preserves semantics *if* the index is complete and preserves relative order among those visited **(C)**.
- **State-copy shortcuts.** Shallow-copying a `GameState`, sharing mutable sub-objects between copy and original, or pooling/reusing card/permanent objects across games risks cross-contamination that may not show up for hundreds of games — the worst kind of batch bug, because it corrupts results silently and non-reproducibly.
- **Floating identity / object identity.** Anything keyed on `UUID.randomUUID()`, identity hash codes, or object addresses (including `HashMap` with identity-hashed keys) can differ run-to-run already; optimisations must not *add* new dependence on them, and reproducibility testing should compare decision sequences, not object IDs (C).

**Verification protocol (C, recommended):** build a golden-run harness — fixed seeds, fixed decks, record the full decision sequence + a state hash per decision for ~50 games on the unmodified engine — and require bit-identical sequences after each lever. Without that, "semantics preserved" is an assertion, not a result.

---

## Prioritized Lever List

Effect sizes are given **only where a source supports one**; "unmeasured" means exactly that.

| # | Lever | Expected effect | Cost | Semantic risk | Evidence |
|---|---|---|---|---|---|
| 1 | **Profile first** (JFR/async-profiler + GC log on 5 representative games; split copy / effects / watchers / view-building / serialisation) | Prevents optimising the wrong 96% | Hours | None | (C) — no published XMage profile exists |
| 2 | **Long-lived worker JVMs, many games per process; parallelise across games, never within a decision** | Amortises all startup + JIT; near-linear scaling with workers until CPU/memory-bandwidth bound | Low | None if per-game seeds/order fixed | (A mechanism / C size) |
| 3 | **Use the simulation path**: simulation flag on, logging/notifications/game-view off, headless, no server/remoting stack | Unmeasured; removes whole subsystems from per-decision path | Low | None (engine's own mode) | (A) |
| 4 | **Remove per-decision state copies/bookmarks/restores not needed by a non-lookahead driver; never copy to "send" state — build the view from the live game** | Potentially the largest single win *if* copies are in your path — a copy is O(board × abilities) per decision | Low–Med | Low if nothing restores from them; audit first | (A architecture / C size) |
| 5 | **Pre-built, shared H2 card DB + warm repository cache; assert zero DB hits during a game** | Removes scan/build from every worker start; prevents known cache-overflow crash mode | Low | None | (A) |
| 6 | **GC bake-off: Parallel vs G1 vs Generational ZGC, `-Xms=-Xmx`, GC log; Epsilon as diagnostic ceiling** | GC literature: collector choice swings throughput by tens of % on allocation-heavy loads; your number is unmeasured | Hours | None | (A rankings / C application) |
| 7 | **Shrink the protocol payload**: integer object IDs, card dictionary once per game, decision-scoped view or diffs | Serialisation slice shrinks ~3–5× at MB scale (measured for binary vs JSON payloads); more if you currently send full state+text+history | Med | Low if decoded view is identical | (A benchmarks / C application) |
| 8 | **In-process driver** (same JVM) instead of JSON-lines over pipes | Removes serialise+parse+pipe per decision entirely; ceiling = whatever share #1 measured for protocol | Med–High | Low if ordering preserved | (C, from A codec numbers) |
| 9 | **Binary codec** (Protobuf/Kryo/Smile) if pipes must stay | ~2× (small payloads) to ~5× (MB payloads) *on the serialisation slice only* | Low–Med | None | (A) |
| 10 | **AppCDS / Leyden AOT cache per worker image** | Startup −10% to −47% in published apps; −20% on a ~25k-class app (closest analogue) | Low | None | (A) |
| 11 | **Watcher/event indexing + effects-recomputation scoping** (only with golden-run verification) | Unmeasured; targets the suspected per-decision fan-out | High | **High** — ordering/completeness are semantics | (C) |
| 12 | **Undo/memento engine rewrite** (Magarena/Forge-prototype style) | Would change copy economics fundamentally; no measured figure exists for any MTG engine | **Very high** — Forge's author: every effect/trigger would need rewriting | High during transition | (A for cost warning) |
| — | **Do NOT**: GraalVM Native Image, `TieredStopAtLevel=1`, ZGC/Shenandoah "for speed", Magarena rules shortcuts | Each trades away peak throughput or semantics for startup/latency you don't need | — | Native Image: compatibility; shortcuts: **semantic change** | (A) |

---

## Could not verify / Honest gaps

- **No measured profile of XMage exists in public sources** — not for headless batch, not for the GUI game. The relative weight of state copying vs continuous-effects recomputation vs watcher/trigger scanning vs view-building in *your* 15–45 ms is undocumented and unmeasured. §1's hotspot ordering is inference from architecture.
- **GitHub issues #5079 and #6738** (AI slowness) are cited by a forum user as the key deck-testing blockers, but I could not open them (github.com unreachable in the research browser; index did not surface their text). No performance PR in magefree/mage was retrieved and verified — I found no merged "performance" PR with before/after numbers at all.
- **Whether normal (non-AI, non-rollback) play copies or bookmarks state per decision** could not be confirmed from retrieved sources; DeepWiki ties copying to simulation/rollback/bookmarks. Your harness may or may not be paying it — measure (lever #1).
- **How often continuous effects are fully recomputed**, and whether recomputation is incremental, is not described in any retrieved source.
- **Magarena and Forge publish no games/sec or ms/decision benchmarks** in the material retrieved; their speed reputations are qualitative.
- **XMage startup time itself** (cold DB build duration, warm start duration) is nowhere published; CDS percentages are from other applications.
- **Serialisation payload size for an XMage game view** is unpublished; §5's size range is a reasoned bound, not a measurement.
- DeepWiki is an AI-generated summary of the repository, not maintainer documentation; its file/line citations were consistent across pages, but treat it as a strong secondary source, not ground truth.

## Sources

All read 2026-10-24 via web index (research browser could not resolve github.com). Flag: **index** for all.

- XMage Game State Management — DeepWiki — https://deepwiki.com/magefree/mage/2.1-game-state-management — index
- XMage Game Engine — DeepWiki — https://deepwiki.com/magefree/mage/2-game-engine — index
- XMage Card System — DeepWiki — https://deepwiki.com/magefree/mage/3-card-system — index
- XMage Testing Framework — DeepWiki — https://deepwiki.com/magefree/mage/6-testing-framework — index (search extract)
- XMage README (32k cards, -Xmx guidance) — https://raw.githubusercontent.com/magefree/mage/master/readme.md — index
- Setting up your Development Environment (H2, DB generation at server start) — https://github-wiki-see.page/m/magefree/mage/wiki/Setting-up-your-Development-Environment — index
- Development Testing Tools (headless tests, test mode, MCTS quick start) — https://github-wiki-see.page/m/magefree/mage/wiki/Development-Testing-Tools — index
- Release 1.4.53 notes (rollback freezes, big/late game errors) — https://github-wiki-see.page/m/magefree/mage/wiki/Release-1.4.53 — index (search extract)
- Bug Reports XMage 1.4.47 (AI 20s–3min/trigger, issues #5079/#6738) — https://www.slightlymagic.net/forum/viewtopic.php?p=246956&sid=a66c1e59116d3e617ae1576d623c86d4 — index
- PVS-Studio on XMage (ComputerPlayerMCTS thread pool) — https://pvs-studio.com/en/blog/posts/java/1257/ — index (search extract)
- Magarena AI Overview — https://github-wiki-see.page/m/magarena/magarena/wiki/AI-Overview — index
- Magarena Minimax AI (undo, simple actions, iterative scoring) — https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax — index
- Magarena Game Rules (semantic simplifications incl. layers) — https://github-wiki-see.page/m/magarena/magarena/wiki/GameRules — index (search extract)
- Forge Traversable Game State / GameCopier simulation — https://www.slightlymagic.net/forum/viewtopic.php?p=160020&sid=62f47d8fc844962d28c13884fcf6f063 and https://slightlymagic.net/forum/viewtopic.php?p=174698&sid=c3a8e77ca8607ab99c4bde4b26c9fddf — index
- The Ultimate 10 Years Java GC Guide (collector matrix, batch=Parallel, ZGC CPU overhead) — https://foojay.io/today/the-ultimate-10-years-java-garbage-collection-guide-2016-2026-choosing-the-right-gc-for-every-workload/ — index (search extract)
- Java Epsilon GC in depth (GC-free baseline method) — https://www.aicassindra.com/blogs/java/java_epsilon_gc.html — index (search extract)
- Tiered Compilation — Baeldung — https://www.baeldung.com/jvm-tiered-compilation — index (search extract)
- Class Data Sharing — Oracle — https://docs.oracle.com/en/java/javase/12/vm/class-data-sharing.html — index (search extract)
- Speed up Java startup with AppCDS (939→497 ms) — Red Hat — https://developers.redhat.com/articles/2024/01/23/speed-java-application-startup-time-appcds — index (search extract)
- AppCDS on a large desktop app (−20%, 25,100 classes) — nipafx — https://nipafx.dev/java-application-class-data-sharing/ — index (search extract)
- JVM cold start: Leyden vs GraalVM Native Image vs CRaC — https://backendbytes.com/articles/jvm-fast-startup-decision-framework/ — index (search extract)
- Java Serialization Performance Showdown (Protobuf vs Jackson JMH) — https://gsswain.com/2025/12/07/java-serialization-performance-showdown.html — index (search extract)
- Micronaut SerDe benchmarks (JSON vs Protobuf vs Kryo at ~1 MB) — https://www.javacodegeeks.com/2025/04/micronaut-serde-beyond-jackson-protobuf-avro-binary-performance.html — index (search extract)
- MATSim Java notes (HashMap/HashSet order, seeded Random for deterministic simulation) — https://www.matsim.org/docs/devguide/java — index (search extract)
