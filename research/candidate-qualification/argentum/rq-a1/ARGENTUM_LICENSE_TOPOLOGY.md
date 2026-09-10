# RQ-A1 — Argentum License / Dependency Topology

Tag: `LEGAL_TOPOLOGY_FACTS_ONLY`. Factual source evidence only. **No legal clearance provided; human legal review remains separate and is explicitly out of scope.**

## 1. Repository license (file content facts)

- `LICENSE` (28 lines): first line states `MIT License`; copyright line `Copyright (c) 2026 Vincent Bons @ bons.ai (https://wingedsheep.com)`.
- Trailing disclaimer block (verbatim in essence): "Magic: The Gathering is a trademark of Wizards of the Coast LLC. This project is not affiliated with, endorsed by, or sponsored by Wizards of the Coast. Card names and game mechanics referenced in this project are used for interoperability and fan purposes only."
- No other license files enumerated; no per-module license variants observed. Provenance review of card text/art and dependency vulnerability review were NOT performed.

## 2. Dependency topology (group:name facts from `gradle/libs.versions.toml` aliases as used per `build.gradle.kts`)

Catalog pins (facts): Kotlin 2.4.0, kotlinx-datetime 0.8.0, kotlinx-serialization-json 1.11.0, kotlinx-coroutines 1.11.0, Kotest 6.2.1, MockK 1.14.11, Spring Boot 4.1.0, springdoc 3.0.3, Kover 0.9.8, ClassGraph 4.8.184, Testcontainers 1.20.4, SLF4J 2.0.18.

- `rules-engine`: `project(:mtg-sdk)`, kotlinx datetime/serialization-json/coroutines-core; test: `project(:mtg-sets)`, Kotest runner/assertions/property, kotlin-reflect. **No Spring, no server, no database — the Rules Core's dependency closure is minimal and secular.**
- `mtg-sdk`: kotlinx ecosystem only.
- `oracle-assay`: `project(:mtg-sdk)` + kotlinx-serialization-json.
- `gym`: `project(:rules-engine :mtg-sdk :ai)` + kotlinx + slf4j-api (runtimeOnly); test adds `:mtg-sets` + rules-engine testFixtures + Kotest.
- `gym-server`: `project(:gym :rules-engine :mtg-sdk :mtg-sets)` + kotlinx + spring-boot-starter-web + springdoc + kotlin-reflect.
- `game-server`: `project(:rules-engine :mtg-sdk :mtg-sets :mtg-search :ai :oracle-assay)` + kotlinx + Spring Boot web + websocket + data-redis + data-jdbc + mail + flyway (+flyway-database-postgresql) + postgresql (runtimeOnly) + springdoc; test: spring-boot-starter-test, Kotest (+spring ext), kotlinx-coroutines-test, MockK, Testcontainers postgresql/junit-jupiter.
- `mtg-sets`: `project(:mtg-sdk)` + ClassGraph + kotlinx-serialization; `api()` re-export of `:core` + all 9 eras.

## 3. Vendored / blob facts (filename scan, `maxdepth 3`; full-tree blob scan not performed)

- `gradle/wrapper/gradle-wrapper.jar` (build wrapper).
- `assets/*.{png,jpeg,svg}` (doc images + generated progress SVG).
- Committed data resources: `game-server/src/main/resources/coverage/{set-totals.json 6.0M, assay-verdicts.json 3.8M, set-products.json 148K, implementation-history.json 11K}`; `mtg-sets/core/…/tokens.json`; `mtg-sets/src/test/resources/snapshots/cards/*.json`; `mtgish-tooling` fixture/golden files.
- Scryfall card `imageUri` strings are remote CDN URLs in metadata, not vendored files; Scryfall bulk/cache (`~/.cache/scryfall/`) is downloaded/gitignored, not vendored.
- No `.so/.bin/.dat` proprietary binaries observed.

## 4. Integration-cost note (technical, not legal)

The Rules Core's minimal dependency closure (`mtg-sdk` + 3 kotlinx libraries) means a headless/embedded integration of `:rules-engine` (+ `:mtg-sdk`, JVM/Kotlin) carries no Spring/database/licensing-adjacent runtime beyond MIT-licensed (stated) code and Apache/Eclipse-licensed (fact: standard) JetBrains/Spring artifacts — details for human legal review, recorded here only as topology.
