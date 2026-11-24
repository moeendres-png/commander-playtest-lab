# #1663 (D-3): Unabhängige Echt-Engine-Abnahme und Abschlussprüfung (2026-11-24)

Refs #1663, #1656, #1612, #1723, #1728, #1731, #1732, #1734.

Alle Echt-Engine-Zahlen sind lokale Messungen am Owner-PC (`SIMULATED_RESULT`, kein CI-Beleg,
keine Qualifikation, Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).
Engine-Pin: `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage 1.4.62), Java 21, Linux, 16 Kerne.

## 1. Architektur- und Code-Ratschen auf `main` (`62f388d6a`)

| Kriterium | Erwartung | Ist-Stand auf `main` (`62f388d6a`) | Nachweis |
|---|---|---|---|
| Private Runner-Zugriffe aus `studio/` und `full_game_series.py` | `0` (Ratsche) | `0` | `pytest -q tests/architecture/test_layer_boundaries.py` → `32 passed` |
| Überschreibungen privater Runner-Haken (`STUDIO_PRIVATE_OVERRIDES`) | Option A abgebaut (#1731) | `set()` (`0`) | `#1731` geschlossen (PR #1779), Ratsche grün |
| `type: ignore` in `src/commander_lab/studio/play.py` | `18 → ≤ 2` | `0` | `grep -n "type: ignore" src/commander_lab/studio/play.py` → 0 Treffer |
| Folge-Issues #1731, #1732, #1734 | nachgeführt | alle 3 `CLOSED` | #1731 (Option A), #1732 (Log-Schwärzung O3), #1734 (unsauberes JVM-Ende) |
| Umfang 4 (Prozess-Register) | prüfen ob gedeckt | gedeckt | Pool-JVMs durch #1652/#1704 (`kill_process_tree`, `reap_ended_process`); interaktive PLAY-JVMs durch `InteractivePlayManager.shutdown_game`/`shutdown_all` + #1734 (#1777) |

## 2. Echt-Engine-Test des Mensch-Sitzes

- Befehl: `pytest -v -rs tests/unit/test_human_seat_play_1169.py -k test_real_engine_human_seat_plays_a_game_to_its_end_through_the_play_routes`
- Bridge-JAR (`main` `62f388d6a`): `c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76`
- Ergebnis: **1 passed in 38,44 s** (`0` skipped, `0` failed).

## 3. Unabhängiger Referenzsatz-Nachlauf (`pre-D-3` gegen `post-D-3` gegen `main`)

Tisch: `pod="real"` (`rogshai_current`, `kaervek/current`, `hosts_of_mordor_precon`, `lorehold_spirit_precon`),
Seeds `1–5`, `--fast --private-card-repository`.

- **Vergleich 1 (`pre-D-3` `d63a6e64~1` gegen `post-D-3` `9a20a83da`) auf identischer Bridge-JAR**
  (`f0894620ee7c2b21e07e9f80c2fdbb23f6cd0155a1a739898485dd2f28271737`, unveränderte `engine-bridge/` zwischen `d63a6e64~1` und `9a20a83da`):
  - `identical 5/5` (`semantic_transcript_sha256` auf allen 5 Seeds identisch)
  - `frames identical 5/5` (`frame_digest` und `frame_digest_by_seat` auf allen 5 Seeds identisch)
- **Vergleich 2 (`post-D-3` `9a20a83da`, JAR `f0894620…`, gegen `main` `62f388d6a`, JAR `c9bd21c9…`):**
  - `identical 5/5`, `frames identical 5/5`

| Seed | Sieger | Entscheidungen | `semantic_transcript_sha256` (`pre-D-3` = `post-D-3` = `main`) | `frame_digest` (`pre-D-3` = `post-D-3` = `main`) |
|---|---|---|---|---|
| 1 | [3] | 2488 | `35494183b698b5b0e33251213d76e921c0e8ed7f9107869adca69821fecfb179` | `b0f34ec74d33bbd3117b0bef99871e3d3a0f9a21415786fa4db1fad09fa5da13` |
| 2 | [3] | 2212 | `5a59375ac76c6cdb50585d678e040cf25fd05650cd0fa285c0ee76218b1ce20d` | `d1fa183d855bcb1767988b61e474f4e28d133e135fb816bad5022da797ff9c11` |
| 3 | [3] | 2972 | `f2a7388f3331ad7a422a4e14474d45a98d87558668416aaef81021a5994c9b70` | `d90d5b2b4c78c16232736e3bed857bdfe7191ff1e6419380eab7266056bac8a7` |
| 4 | [3] | 2986 | `7080481d627e71c044b35df80c5777040cb13df81ccfa97ca9aaf4869aebfde5` | `5cc52775837240561fd2f17bb2713fa6949b975ed89383620aaa2af9c8b6203b` |
| 5 | [3] | 3402 | `3548b540baeec129d8c021b0363cd51603a7abc0629c1f9c41fd50a2898f5dbf` | `b27d5a0460bc4ce97e5c19b2cbe4e5f3d384d2a3ce8ab8a52ed565d40ab281ea` |

## Grenzen / `UNKNOWN`
- Referenzsatz-Vergleich deckt `pod="real"` Seeds `1–5` ab; Windows-Laufzeit hier nicht lokal gemessen (`UNKNOWN`, über CI `windows-runtime` abgedeckt).
