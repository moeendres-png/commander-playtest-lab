# WS223 Input Authority Matrix

Every WS223 design decision traces to exactly one authority row. No unrelated
WS220 findings are absorbed.

| # | Input | Authority class | Content consumed | WS223 use |
|---|---|---|---|---|
| 1 | WS215 seal (`af969232`, `8c3174f5`) | `DIRECTLY_VERIFIED` (terminal) | 2–5P lifecycle qualification; `MIN/MAX_PLAYERS = 2/5`; 6P fail-closed | Protected property; regression targets |
| 2 | WS218 seal (`2379efcd`, `3cdade1d`) | `DIRECTLY_VERIFIED` (terminal) | Semantic replay tape v1; `semantic_transcript` in `full_game.py`; 2–5P replay PASS | Trigger adjudication: replay-only changes stay on the light lane |
| 3 | WS220 `FINDINGS.json` F-CI-03 | `DIRECTLY_VERIFIED` | 4P-shaped conformance script + workflow; missing trigger on `test_xmage_variable_player.py` | S5 repair surface |
| 4 | WS220 `FINDINGS.json` F-CI-01 | `DIRECTLY_VERIFIED` | Ranges; 6-pin non-transitive lock; floating temurin:21; JDK17/21 skew; 12/16 lanes lack hashseed; cache keys ignore lock | S15 repair surface |
| 5 | WS220 `SUCCESSOR_PROPOSALS.json` S5 | Design input (read-only) | Parametrized 2–5P conformance + variable-player triggers; JVM cost bounded | S5 objective |
| 6 | WS220 `SUCCESSOR_PROPOSALS.json` S15 | Design input (read-only) | Transitive hash-pinned lock; JDK alignment; universal hashseed; lock-aware cache keys | S15 objective |
| 7 | WS220 `TEST_AND_CI_AUDIT.md` | Design input (read-only) | Guard-heavy strategy correct; lane-dependence verdict; S5+S15 ordering | Test strategy (static gates + live smoke) |
| 8 | WS220 `BATCH2_NOTES.md` H-CI-01 | `DIRECTLY_VERIFIED` | Per-lane inventory detail (4/16 hashseed, floating tags) | Inventory baseline, independently re-verified on tip |
| 9 | `src/commander_lab/engine/rules/full_game.py` @ tip | Source Authority | `MIN_PLAYERS=2/MAX_PLAYERS=5`; `_validate_inputs`; `_validate_handshake` 2–5 lane; `_RawFullGameClient.close()` clean shutdown | Smoke entrypoint reuses these; no legality touched |
| 10 | `src/commander_lab/candidates/models.py` @ tip | Source Authority | `FutureXmageScenario.player_count ge=2 le=5`; `seat ge=1 le=5` | 6P fail-closed layer 1 (model construction) |
| 11 | `engine-bridge/pom.xml` @ tip | Source Authority | `maven.compiler.release=17` | Canonical JDK floor; CI Temurin 17 authoritative |
| 12 | Docker Hub registry API (read 2026-09-15) | `EXTERNALLY_RULE_VALIDATED` (timestamped observation) | `eclipse-temurin:21-jdk` manifest digest `sha256:1f79c734…` (pushed 2026-09-10; newer than any `21.0.11` version tag) | Digest pin bytes; drift-demonstration evidence |
| 13 | PyPI JSON API (read 2026-09-15) | `EXTERNALLY_RULE_VALIDATED` (timestamped observation) | `pip-tools 7.6.1`; `httpx2 2.13.0` exists (dev-range name is real) | Lock generator pin; no dependency rename needed |

## Fresh re-verification on tip (2026-09-15, before mutation)

- Conformance script still hardcodes `range(1, 5)` / `player_count=4` — CONFIRMED.
- Workflow still has zero 2P/3P/5P steps; `push` path filters omit
  `agents/**`, `models/pilots.py`, `candidates/models.py`,
  `full_game_batch.py`, `test_xmage_variable_player.py` — CONFIRMED.
- `requirements/runtime.lock` still 6 pins with non-transitive disclaimer — CONFIRMED.
- `PYTHONHASHSEED` present in 4/16 workflows
  (`ci`, `external-engine-integration`, `h4-docker-materialization` ×2,
  `xmage-full-game-conformance`); absent in 12 — CONFIRMED.
- All 16 lanes pin `python-version 3.12`; JVM lanes pin Temurin 17;
  Dockerfiles `FROM eclipse-temurin:21-jdk` (floating) — CONFIRMED.
- `setup-python cache: pip` without explicit `cache-dependency-path`;
  `setup-java cache: maven` (pom-bound automatically) — CONFIRMED.
- WS218 touched only `research/`+`qualification/` evidence plus
  `src/commander_lab/semantic_replay/` + its tests (no full-game lane source
  change) — CONFIRMED via `git show 2379efcd --stat`.
