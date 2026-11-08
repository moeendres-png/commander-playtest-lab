# Phase 3 — Commander player-count / capacity audit: 4 vs 6 vs 8

**Date:** 2026-11-08 · **Evidence class:** public-provider statements, pinned-code inspection, previously measured repository telemetry, transparent analytic proxies · **Lab source lock:** `main@e3d88eb957813b59d077e9b94bfbc32ce7fa2412` · **XMage pin:** read `config/rules_engines.json` (`primary_engine.commit`), no repin or engine write.

**Owner decisions interpreted precisely:** The earlier explicit instruction set **six as the permanent maximum of production simulation games** (four is the standard). On 2026-11-08 the Owner additionally requested an **eight-player feasibility investigation if possible**. This authorizes examining 8P in research **without promoting 8P into the Lab's supported product scope or bypassing its limits**. To override the six-seat product limit would require an additional explicit decision.

**Scope:** Why Playgroup Live stops at six, source constraints in the Lab and upstream XMage, measured 4P and 6P game costs, eight-player feasibility, UI layout, preliminary capacity choice, and a reproducible benchmark protocol. **No private deck collection** data accessed or transmitted; no live XMage game run in this investigation because the local `commander-playtest-lab` and sibling `mage` checkouts/JAR are not attached to this session. This is not a head-qualified runtime benchmark.

## Executive decision

| Players | Engine and Lab reachability | Observed evidence | Product verdict |
|---|---|---|---|
| **4** | Fully reachable via pinned bridge; 4P full-game runners and comparison scripts | Repeated exact-source full games and throughput measurements; broadest evidence | **Default / primary calibration reference** |
| **6** | Java and Python admission is 2–6; native full-game can complete but specific replay/observer surfaces remain 2–5 | Full six-player games `status=ok`, plus large-stack/resource-guard counterexamples | **Maximum allowed**, higher-risk / capacity-test-gated |
| **8** | Upstream XMage publicly advertises up to 10; **our Java bridge + Python scenario/pilots reject 8 before running** | **No lab 8P game, no 8P RSS/wall time, no pinned-native 8P proof** | **Research-only, not admitted to product** |

**Recommendation:** Keep **4 default, 6 maximum, 8 research-only**. The evidence is strong enough to justify not building a routine eight-seat product. It is **not** strong enough to claim that XMage cannot run eight, that Playgroup chose six due to measured memory, or that we have measured an 8P cost curve.

## 1. Playgroup Live — why exactly six?

**Vendor-confirmed:** Playgroup Live allows 2–6 players. Playgroup's own Tabletop Simulator comparison openly states TTS permits eight and Playgroup Live six; Playgroup deliberately optimizes **structured game zones and readability** rather than unlimited freeform space. Phones use one visible seat at a time with a seat switcher; tablets have the fuller table layout.

**Vendor-confirmed performance work:** The July 10, 2026 developer update says it optimized boards with many cards, reduced memory, made shadows cheaper, and hardened reconnect/host-handoff. A separate Playgroup Commander guide describes six-player matches as **noticeably slower**, approaching 90 minutes in the tracked game sample.

**Unknown:** No verified public developer statement directly attributes the six-seat cap to a particular GPU frame-rate, server bill, legal limit, storage limit, database schema, RAM number, or objective UX breakpoint. **“They stop at six because memory would explode at eight” would be an unsupported causal claim.**

**Evidence class:** `PROVIDER_STATEMENT` for support and rendering optimizations; `HYPOTHESIS_ONLY` for exact six-seat causation.

References:
- https://playgroup.gg/playgroup-live
- https://playgroup.gg/playgroup-live/vs-tabletop-simulator
- https://playgroup.gg/posts/99-playgroup-live-two-months-of-updates (2026-07-10)
- https://playgroup.gg/commander/how-to-play
- https://playgroup.gg/live_sessions/KYAkCWUo96UgHREHfw7eryQ2/spectate (WebGL required, error view)

## 2. XMage: separate native Rules capacity from Lab product admission

**Upstream:** XMage publicly documents Commander/free-for-all for up to **10** players. This is a feature statement about upstream XMage, **not** a validated result on our pinned fork/bridge.
- https://github.com/magefree/mage (README, multiplayer feature)
- https://sourceforge.net/projects/xmage.mirror/ (published overview)

**Pinned fork:** `moeendres-png/mage`, identity from `config/rules_engines.json` (the pin the measurements below were taken on was `2ec507b721`; the live pin moves with each repin, so read the file, not this sentence). The pinned `Mage/src/main/java/mage/game/GameCommanderImpl.java` itself does not provide an explicit 6-player cap; the dedicated Lab bridge intentionally enforces one. That observation alone does **not** qualify eight-player native Commander correctness.

**Lab code-bound admission:**

| Contract / source | Bound / implication |
|---|---|
| `engine-bridge/.../XmageFullGameSession.java` | `MIN_PLAYERS=2`, `MAX_PLAYERS=6`; eight deck handles rejected as `FULL_GAME_INVALID_PLAYER_COUNT` **before** game construction |
| `src/commander_lab/engine/rules/full_game.py` | `XmageFullGameRunner.MAX_PLAYERS=6` |
| `src/commander_lab/candidates/models.py` | `FutureXmageScenario.player_count` 2–6; seat 1–6; schema rejects 8 |
| `src/commander_lab/engine/rules/full_game_pilot/state.py` | Runtime policy binds 2–6 pilots |
| `src/commander_lab/engine/rules/full_game_comparison.py` | At most five opponents + candidate = 6 players |
| `src/commander_lab/engine/rules/full_game_batch.py` | Rejects player count outside 2–6 |
| `src/commander_lab/semantic_replay/tape.py` | One specific replay manifest/seat contract is **2–5**; 6P must not be promoted to qualified replay automatically |
| `src/commander_lab/models/tooling.py` | Older `pod_size <= 10` for certain tooling/metadata **does not authorize** operational 8P games |

**Historical six-player lifecycle proof:** `docs/archive/workstream_lab_sixplayer_20260921/R19_SIXPLAYER_ROOT_CAUSE.md` reports a **7,284-decision native six-player full-game terminal**, while seven was rejected by the bridge; this was a contract widening from 5 to 6, not an XMage Rules change. The historical proof is not an automatic fresh-head pass.

**Eight-player feasibility result now:** `PINNED_LAB_8P = BLOCKED_BY_ADMISSION_GATES` (CODE_DERIVED). `PINNED_NATIVE_MAGE_8P = UNKNOWN` (not executed). A headless Java **native-engine-only** 8P feasibility experiment would require a separate isolated experimental setup and runtime host. It must never silently widen product schema/bridge guards, produce 8P gameplay evidence under the 6P product label, or change the canonical engine pin.

## 3. Measured four-player and six-player costs (real runs, historical)

### Dataset A — 2026-11-06, exact raw JSON

Source: `docs/performance/measurements-2026-11-06/native-mana-production-summary.json` and `docs/performance/NATIVE_MANA_PRODUCTION_2026-11-06.md`. One worker, seed 1, equal *engine class contents* within baseline/candidate; **4P and 6P use different public deck pods and game histories**. These are observations, not an isolated seat-count A/B test.

| Runtime snapshot / distinct pod | Status | Decisions | Wall clock | Spells cast (pilot count) |
|---|---|---:|---:|---:|
| Baseline, coverage-4p-000 | ok | **1,892** | **50.36 s** | 35 |
| Baseline, coverage-6p-002 | ok | **4,511** | **161.93 s** | 59 |
| Candidate, coverage-4p-000 | ok | 1,892 | 63.95 s | 35 |
| Candidate, coverage-6p-002 | ok | 4,282 | 111.09 s | 62 |

**Observed, descriptive ratios:** baseline 6P vs 4P = **2.384× decisions**, **3.215× wall seconds**. Candidate 6P vs 4P = **2.263× decisions**, **1.737× wall seconds**. The widely different time ratios in just these observations show why a single per-seat scaling coefficient would be scientifically indefensible. There is no per-game RSS/heap field in this JSON.

### Dataset B — 2026-11-05, same pinned v14 JAR, several public-precon pods

Source: `docs/performance/measurements-2026-11-05/combat-finisher-summary.json` and `docs/performance/COMBAT_FINISHER_WINDOWS_2026-11-05.md`.

| Seats | Successful unique baseline seeds/pods | Total decisions | Mean decisions per completed game |
|---|---:|---:|---:|
| 4P | 4 | 11,961 | **2,990.25** |
| 6P | 2 | 8,051 | **4,025.50** |

Ratio of these **nonmatched** descriptive means: **1.346×**. These are not equal-deck scenarios, and neither response time nor per-game memory was reported in the file. Four and six players both achieved exact semantic hashes in the completed before/after pairs. Two other six-player pairs (`P6b`) remained incomplete during the initial prescribed run.

### Dataset C — throughput and memory *within 4P*, not across seat counts

Source: `docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`. On **4 cores / 16 GB / JDK 21**, **36 four-player real-pod games** took **408 s** across four workers with batching/SerialGC/AppCDS; the former best was **873 s**. Warm/cold per-game JVM impacts: about **85 CPU-s cold vs 37 CPU-s warm** for the particular game. Per-decision cost approximated **8 ms** in that 2026-10-21 profiling environment. These values are **historical implementation-specific**, not general forecasts for 6P or 8P.

Source: `docs/performance/measurements-2026-10-22/batching-memory-with-deck-release.json` (one repeatedly used **4P** pool, 32 consecutive games **in one JVM**): live-set slope about **−0.104 MiB/game**, live max **157.5 MiB**, process **peak RSS 0.98 GiB**. **Do not** call 0.98 GiB “the RAM of any 4P game”: the value is a warm, instrumented, multi-game JVM measurement. The accompanying memory qualification JSON has an **INCONCLUSIVE overall verdict** because its reference comparisons were not all executed; its measured RSS/live-set fields are useful telemetry, **not** a qualified full batching PASS. An independent **4P case** at a 768 MiB configured limit failed out of memory (2026-11-06 report); no universal 4P memory bound is established.

### Six-player resource red flags

- `docs/performance/DISK_BACKED_DECISION_REPORTS_2026-11-05.md`: a six-player measurement held several GiB of Python decision/request objects and required a resource stop. The recording path was subsequently converted to compressed temporary SQLite, removing that particular unbounded in-memory list but **not** all simulator memory costs.
- `docs/performance/COMBAT_FINISHER_WINDOWS_2026-11-05.md`: an incomplete heavy six-player run was stopped when a shared cgroup exceeded **5 GiB**; another prefix attempt ran low on disk. Neither interruption is a completed game or a clean per-JVM maximum memory measurement.
- `docs/performance/OPTIONAL_COUNTER_GROWTH_2026-11-05.md`: a six-player `Enduring Scalelord` loop produced one observed stack of **3,696 abilities**; the pilot's decision policy required targeted work and a later completed game. This shows that **deck interactions / loop behavior**, not only seat count, dominate extreme resource tails.
- A six-player `status=ok` case confirms some ordinary games can complete. It does not erase heavy-tail failures.

**No real 8P benchmark exists in the inspected Lab evidence.** Any “8P needs 300 s / 3 GB” estimate would be invented and is intentionally omitted.

## 4. Dimensionless capacity pressure model — NOT a timing forecast

The two simple metrics below are exact arithmetic *given the assumptions*, not measured XMage performance. A deck count counts all 100-card Commander decks; directed seat pairs count potential player-to-player relationships, **not observed decisions**.

| Players | Physical cards in decks | vs. 4P | Directed seat pairs N(N−1) | vs. 4P |
|---|---:|---:|---:|---:|
| **4** | 400 | 1.00× | 12 | 1.00× |
| **6** | 600 | 1.50× | 30 | 2.50× |
| **8** | 800 | 2.00× | 56 | 4.67× |

Eight has **33% more deck cards than six** and **87% more potential directed seat pairs**. Neither ratio is a CPU, wall-clock, stack-depth, RAM, or win-rate scaling law. Actual card effects can multiply triggers, replacement choices, and state-copy size in a strongly deck-dependent manner.

**Separately track:** native Java heap/RSS/GC; bridge copying and JSON serialization; Python pilot CPU; per-decision view sizes; persistent decision traces; browser CPU/GPU draw cost and visible card counts. A virtual manual Playgroup browser table has a **different** rules compute profile from an automated XMage back end: do not equate their resource requirements.

## 5. UI/table readability: 4 vs 6 vs 8

| Issue | 4P | 6P | Hypothetical 8P |
|---|---|---|---|
| Simultaneously visible opponents | 3 | 5 | 7 |
| Playgroup-style structured zones | comfortably prioritizable | condensed other-seat views; zoom/focus needed | substantial overflow and seat-switching pressure |
| Stack and priority | visible without collapsing many seat panels | explicit highlighted priority seat and scroll/zoom | likely excessive alert/target density, not user-tested |
| Chulane late game | creature/Clue/token grouping essential | grouping plus dynamic focused opponent mandatory | no product interface planned |
| Mobile | one focused seat / switcher pattern is useful | needs stronger seat switching | research concept only |

Playgroup explicitly chose structured zones for readability rather than arbitrary 3D layout; its phones use a one-seat-at-a-time view. It has already had to optimize card-heavy boards and WebGL shadows. **No measured eight-seat usability study was found.**

### UI benchmarking checkpoints (future, not completed)

Use public generic cards, **not personal collection data**. On the same desktop/tablet, render synthetic public boards with (a) 5, (b) 15 and (c) 40 permanents per player for 4P and 6P. Measure p50/p95 FPS and input latency, WebGL context-loss count, browser memory/heap where exposed, GPU frame/composite time, tooltip readability, target-arrow overlap, seat switching, and accessibility. Eight-seat rendering may be drawn as a **static layout research mockup only**; do not authorize 8P simulator game sessions.

## 6. Controlled and comparable benchmark protocol for 4P and 6P

**Gating constraints:** 4P and 6P use the **same** Lab HEAD, pinned XMage commit, identical built Bridge JAR, same JVM heap/GC options, same host CPU/RAM and isolated workers. Experiments should run one game per JVM first; batching only as a second variable. Maintain unchanged game mechanics and pilot legality.

1. Assemble a public no-collection benchmark roster: Chulane candidate **only if the current authorized Chulane baseline has been integrated**, plus a fixed set of public precons. Keep the four baseline decks in 6P and append two precon decks; both pods are **not** equal game distributions and cannot isolate seat count causally. Rotate player seats and keep per-count seeds fixed.
2. For each of two public-deck compositions (value/creature and interaction-heavy), run **10 unique seeds** at 4P and 6P (20 per configuration; 40 games), followed by a separate worst-case token/trigger scenario. This is a first descriptive pilot sample, **not** a 95% performance guarantee or win-rate inference. Run order should alternate/randomize by precommitted schedule to reduce temperature/JIT/order bias.
3. One worker, one JVM per game: record terminal `status`, rounds, engine decisions, real elapsed clock, process tree CPU, peak JVM+Python process RSS, JVM max heap/live heap, GC time, peak stack depth, peak battlefield permanent count, observer-serialized bytes, disk trace bytes and 99th percentile decision latency. Run out-of-memory guards and a reasonable wall/decision cap; preserve interrupted/failed rows, never silently exclude them.
4. Then repeat the chosen 4P/6P scenarios at 2/4 workers, measuring **host-wide** peak RAM, per-worker RSS, throughput (successful games/hour), tail latency, failure ratio and queue wait. The 4-core/16-GB historical machine is a starting reference, not an assumed current host.
5. Compare ratio distributions only among explicitly documented pods, seeds, and hardware. Publish median, p95 where sample size justifies it, and uncertainty; report game-length/stack-heavy outliers individually. Do not extrapolate from 6P to 8P without real independent evidence.
6. Verify privacy and replay separately at 6P; `TapeGameManifest` currently accepts only 2–5. A 6P successful full game must not earn 6P Replay PASS automatically.

**End condition for extended 6P mode:** All chosen 6P games terminate through the engine or are explicit FAIL, no hidden-state leaks, no unsupported decision fallback, and measured resource limits fit the deployment budget with safe concurrent workers. A one-off success is not a pass for extreme Chulane boards. Until then: 4P remains default and 6P remains an experimental or separately qualified option.

## 7. The requested 8P investigation: feasibility without product-limit changes

**What was possible now:**

- Verified **Upstream XMage advertises 10P** (vendor source).
- Verified the pinned fork's generic Commander code does **not itself** state a 6P hard limit (code inspection, limited to the inspected class).
- Verified **our Java bridge rejects 8P on construction**, and Python scenario/runner reject before allocating a valid game. It is therefore not honest to claim an eight-player real game was started, or that a production benchmark was measured.
- Computed cardinality/interaction **analytical pressure only** (table in §4). No 8P memory/CPU time imputed from 4P/6P.

**What was not possible in this session:** host not mounted, no built JVM available, no dedicated 8P native-engine-only harness, and direct GitHub access cannot run arbitrary local Maven commands. **No eight-player live game or startup probe was run.**

If an independent engineering session is expressly authorized to perform **research only**, the safest next experiment is a temporary, isolated **native Mage test** (not via the Lab full-game production bridge) with eight public 100-card dummy/precon decks and a fixed seed: check native game construction → six? (eight actual seats) → opening hands → mulligan → first priority → bounded 100 decisions → clean stop. Measure Java process RSS/heap and wall time; label `ENGINE_NATIVE_RESEARCH_NOT_PRODUCT`. Do not edit/re-pin the fork or lift the 6P application contract. Full 8P terminal/hidden-state equivalence would still be **UNKNOWN**. Any fork push or canonical repin requires a separate Owner authority gate.

**Latest owner research request** allows this **bounded inquiry**, not any operational release of 8P.

## 8. Decision and concrete next engineering priorities

**Recommended product decision: `DEFAULT=4; MAX=6; 8P=RESEARCH_ONLY`.** Keep it until explicitly superseded by a new product decision. The selected cap is a rational cost/UX bound, **not a physical limit of MTG or necessarily of native XMage**.

In priority order:

- **P0** Preserve Java + Python fail-closed gate at 6; reject operational 7/8/10. Do not advertise 8P.
- **P0** Add a repeatable **4P-vs-6P native capacity measurement harness** with isolation of JVM, pilot and trace-store contributions; measurement scripts may reuse existing bridge and batching tools. Do not change the Rules Core just to optimize benchmarks.
- **P0** Ensure report storage remains disk-backed and bounded; budget disk consumption and inspect stack-heavy tail cases (Enduring Scalelord, multiplayer token board).
- **P1** Verify actor-scoped privacy, stable legal decisions, per-seat turn order and full-game terminal on 6P; close the 6P replay-manifest gap only through a separate qualified change.
- **P1** Start UI at a complete 4P table; prototype condensed 6P seat views using grouped cards/Clues/tokens. Track input latency and readability, not only draw FPS.
- **P2 research-only** Native pinned XMage eight-seat bounded startup, only in a separate host-backed engineering setup with no production cap expansion. If unavailable, retain `UNKNOWN` rather than invent results.

## 9. Source references

### Official external sources
- https://playgroup.gg/playgroup-live
- https://playgroup.gg/playgroup-live/vs-tabletop-simulator
- https://playgroup.gg/posts/99-playgroup-live-two-months-of-updates
- https://playgroup.gg/commander/how-to-play
- https://github.com/magefree/mage (upstream public capability statement)

### Lab / pinned code and measured primary artifacts
- `config/rules_engines.json`
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java`
- `src/commander_lab/engine/rules/full_game.py`
- `src/commander_lab/candidates/models.py`
- `src/commander_lab/engine/rules/full_game_comparison.py`
- `src/commander_lab/semantic_replay/tape.py`
- `docs/archive/workstream_lab_sixplayer_20260921/R19_SIXPLAYER_ROOT_CAUSE.md`
- `docs/performance/measurements-2026-11-06/native-mana-production-summary.json`
- `docs/performance/NATIVE_MANA_PRODUCTION_2026-11-06.md`
- `docs/performance/measurements-2026-11-05/combat-finisher-summary.json`
- `docs/performance/COMBAT_FINISHER_WINDOWS_2026-11-05.md`
- `docs/performance/DISK_BACKED_DECISION_REPORTS_2026-11-05.md`
- `docs/performance/OPTIONAL_COUNTER_GROWTH_2026-11-05.md`
- `docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`
- `docs/performance/measurements-2026-10-22/batching-memory-with-deck-release.json`
- `Mage/src/main/java/mage/game/GameCommanderImpl.java` at the pinned `moeendres-png/mage` commit

**Audit status:** `CODE_REVIEW_AND_HISTORICAL_DATA_ANALYSIS_COMPLETE`; `NEW_HEAD_BENCHMARK=NOT_RUN`; `8P_NATIVE_TEST=NOT_RUN`; `8P_PRODUCTION_ADMISSION=REJECTED_BY_CODE`; `PLAYGROUP_CAP_CAUSE=UNKNOWN`.
