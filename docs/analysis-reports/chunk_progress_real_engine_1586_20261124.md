# `#1586`: Mid-JVM-Hard-Kill-Test und Echt-Engine-Chunk-Hash-Probe

- **Datum:** 2026-11-24 · **Refs:** `#1586`, `#1558`, `#1612`, `#1652`
- **Einordnung:** `SIMULATED_RESULT` für die Echt-Engine-Probe (lokale Owner-PC-Messung unter Linux/WSL2, Rohlogs außerhalb des Repos, **kein Qualifikationsbeleg**; `AGENTS.md` §4).
- **Basisstand & Engine-Pin:** `main` @ `62f388d6a037e63c3eaad5975ab932448e6c1de0`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), lokaler Bridge-JAR `engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar` (SHA-256 `c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76`), Bridge-Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`.
- **Pool-Schalter unverändert:** `COMMANDER_LAB_STUDIO_SERIES_POOL` bleibt standardmäßig `AUS` (`#1652`, natives Windows `taskkill /T /F` weiter `UNKNOWN`).

## 1. Geschlossene Lücke 1: Harter Prozess-Kill mitten im JVM-Leben (Unit-Test)

In `tests/unit/test_studio_game_pool.py` prüft `test_hard_kill_mid_jvm_life_keeps_earlier_finished_game_logs_closed` nun explizit den bisher als `UNKNOWN` markierten Fall aus `#1586` Kommentar 6:

- Ein realer Worker-Unterprozess führt `SessionWorkerEngine.play` über `GamePool` mit `gamesPerJvm=4` (ein JVM-Leben über 4 Partien) aus.
- Partien 1 und 2 enden regulär im selben offenen JVM-Leben (`position_in_jvm = 1, 2`); während Partie 3 im selben JVM-Leben aktiv ist, wird der Worker hart getötet (`SIGKILL` unter POSIX, `os._exit(9)` unter Windows).
- Nach dem harten Abbruch sind die `.jsonl.gz`-Logs der Partien 1 und 2 bereits vollständig geschlossen (`status == "finished"`, `winner_seats`, `decision_count`, 64-stelliger `semantic_transcript_sha256`, keine offenen `.jsonl`-Reste), während die abgebrochene Partie 3 als `status == "failed"` / `failure_class == "WorkerExited"` markiert wird.

## 2. Geschlossene Lücke 2: Echt-Engine-Hash-Probe auf `play_recorded_games` (`n/N = 2/2`, `SIMULATED_RESULT`)

Tisch `A4` (`2023_eldrazi_unbound.json`, `2026_lorehold_spirit.json`, `2024_animated_army.json`, `2022_token_triumph.json`), Seeds `1` und `2`, Gesamtwandzeit `151,74 s`:

| Seed | Spiel-ID | `on_played` | `on_game` | Status | Siegersitz | Entscheidungen | `semantic_transcript_sha256` | Gleich zu Einzelspiel & Direkt-Runner |
|---|---|---:|---:|---|---|---:|---|---|
| `1` | `chunk-s1` | `92,33 s` | `93,49 s` | `finished` | `[3]` | `2744` | `3650334aaf70e0bcfb146fa40b275b78a004c59877fa41b1f96969de7d29a728` | ja (`2/2`) |
| `2` | `chunk-s2` | `150,46 s` | `151,58 s` | `finished` | `[3]` | `1680` | `3c8aac840df1782742526ea87ae9160354f56de8403dafff7963ed2b4448b6e2` | ja (`2/2`) |

## 3. Grenzen und weiter `OPEN` / `UNKNOWN`

- **Issue `#1586` bleibt offen** gemäß Lead-Entscheid Option 3 (Kommentar 6), bis `#1652` den Serien-Pool standardmäßig einschaltet (`COMMANDER_LAB_STUDIO_SERIES_POOL` Standard-AN).
- **Weiter `UNKNOWN` / `NOT_RUN`:** natives Windows `taskkill /T /F` (`#1652`), Browser-Anzeige im echten Browser, größere Stichproben über weitere Tische und Seeds.
