# B2a (`#1658`): Echt-Engine-Probe zu `pilot_fingerprint` und unverändertem Transkript-Hash

- **Datum:** 2026-11-24 · **Refs:** `#1658`, `#1656`, `#1612`
- **Einordnung:** `SIMULATED_RESULT` (lokale Owner-PC-Echt-Engine-Messung unter Linux/WSL2, Rohlogs außerhalb des Repos, **kein Qualifikationsbeleg**; `AGENTS.md` §4).
- **Basisstand & Engine-Pin:** `main` @ `62f388d6a037e63c3eaad5975ab932448e6c1de0`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), lokaler Bridge-JAR `engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar` (SHA-256 `c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76`), Bridge-Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (`covered_by_sealed_epoch: false`).
- **Pilot-Fingerabdruck (`play.header_pilot_fingerprint()`):** `51818f6859adb2aef8d79f879934f1e7efe6564a0be8fad1d2c896f0242b4a9f`.
- **Tisch (`A4`, 4 Sitze):** `2023_eldrazi_unbound.json`, `2026_lorehold_spirit.json`, `2024_animated_army.json`, `2022_token_triumph.json`.

## 1. Fragestellung (offener B2a-Restpunkt aus `#1658`)

Nach dem Merge von B2a (`#1685`), B2b (`#1725`, `#1726`) und dem B2-Rest (`#1788`) war in `#1658` ausschließlich die Echt-Engine-Probe für B2a offen:

1. Schreibt der Studio-Aufnahmepfad (`play.play_recorded_game`) den exakten 64-stelligen `pilot_fingerprint` in den Log-Kopf (`.jsonl.gz`) und liest `card_outcomes.load_exposures` ihn fehlerfrei ein?
2. Bleibt das Pilot-Verhalten auf der echten Engine unverändert (`semantic_transcript_sha256`, `winner_seats`, `decision_count` identisch zwischen `play.play_recorded_game` mit `pilot_fingerprint`-Kopf und direktem `XmageFullGameRunner` ohne Studio-Aufzeichnung)?

## 2. Ergebnis (`n/N = 2/2`, `SIMULATED_RESULT`)

| Seed | Pfad | Status | Siegersitz (0-basiert / Engine 1-basiert) | Entscheidungen | `semantic_transcript_sha256` | `pilot_fingerprint` im Kopf | Wandzeit |
|---|---|---|---|---:|---|---|---:|
| `1` | `play.play_recorded_game` | `finished` | `[3]` (Engine `4`) | `2744` | `3650334aaf70e0bcfb146fa40b275b78a004c59877fa41b1f96969de7d29a728` | `51818f68…2b4a9f` (exakt) | `46,63 s` |
| `1` | `XmageFullGameRunner.run` (direkt) | `terminal: true` | Engine `[4]` | `2744` | `3650334aaf70e0bcfb146fa40b275b78a004c59877fa41b1f96969de7d29a728` | nicht anwendbar | `45,04 s` |
| `2` | `play.play_recorded_game` | `finished` | `[3]` (Engine `4`) | `1680` | `3c8aac840df1782742526ea87ae9160354f56de8403dafff7963ed2b4448b6e2` | `51818f68…2b4a9f` (exakt) | `34,44 s` |
| `2` | `XmageFullGameRunner.run` (direkt) | `terminal: true` | Engine `[4]` | `1680` | `3c8aac840df1782742526ea87ae9160354f56de8403dafff7963ed2b4448b6e2` | nicht anwendbar | `45,85 s` |

- **Hash-Identität:** `2/2` Partien liefern zwischen Studio-Aufzeichnung (`play.play_recorded_game`) und direktem `XmageFullGameRunner.run` denselben `semantic_transcript_sha256`, denselben Siegersitz und dieselbe Entscheidungszahl.
- **Log-Kopf & Auslesung (`card_outcomes.load_exposures`):** `2/2` echte `.jsonl.gz`-Logs wurden ohne Fehler eingelesen (`skipped_unreadable = 0`, `skipped_foreign = 0`, `skipped_determinism_violation = 0`); beide `exposures` tragen exakt `pilot_fingerprint = "51818f6859adb2aef8d79f879934f1e7efe6564a0be8fad1d2c896f0242b4a9f"`, `table_size = 4`, `bridge_jar_sha256 = "c9bd21c9…"`, `bridge_qualification_state = "BRIDGE_AHEAD_OF_QUALIFICATION"` und `covered_by_sealed_epoch = false`.

## 3. Grenzen und `UNKNOWN` / `NOT_RUN`

- **Stichprobe:** `N = 2` Seeds (`1`, `2`), ein fester 4-Sitz-Tisch (`A4`), `OpenJDK 21.0.13.1` unter Linux/WSL2; andere Tische, andere Sitzzahlen und natives Windows sind hier `NOT_RUN` / `UNKNOWN`.
- **Rohlogs:** Die erzeugten `.jsonl.gz`-Dateien lagen in einem temporären Verzeichnis außerhalb des Repositories und wurden nach dem Lauf entfernt (kein Rohlog im Git-Baum).
- **Kein Qualifikationsbeleg:** Die Messung gilt für den oben genannten lokalen Bridge-JAR im Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`.
