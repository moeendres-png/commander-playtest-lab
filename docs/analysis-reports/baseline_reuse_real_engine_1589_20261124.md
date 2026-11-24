# `#1589`: Echt-Engine-Nachweis – Basis-Partien-Wiederverwendung mit `studio-game-key-2` und Stichproben-Gegenprobe

- **Datum:** 2026-11-24 · **Refs:** `#1589`, `#1558`, `#1660`
- **Einordnung:** `SIMULATED_RESULT` (lokale Owner-PC-Echt-Engine-Messung unter Linux/WSL2 in einem temporären Ordner außerhalb des Repositories, Rohlogs nach dem Lauf entfernt, **kein Qualifikationsbeleg**; `AGENTS.md` §4).
- **Basisstand & Engine-Pin:** `origin/main` @ `aa7a4b57e21d8c350ae4b75f5bf504f935881f19` + Branch `feat/baseline-game-reuse-1589`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), lokaler Bridge-JAR `engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar` (SHA-256 `c9bd21c9c9484c97d6a91e7510458a6b2c56bef25c642bf745bedcb23ab9ce76`), Bridge-Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`.
- **Tisch (4 Sitze, Sitz 0 getestet, Seeds `1` und `2`):** Basis `2023_eldrazi_unbound.json`, Variante 1 `2023_divine_convocation.json`, Variante 2 `2023_veloci_ramp_tor.json`, Gegner `2026_lorehold_spirit.json`, `2024_animated_army.json`, `2022_token_triumph.json`.

## 1. Ergebnis (`n/N = 1/2` wiederverwendet, `1/1` Stichproben-Gegenprobe identisch)

| Serie | Wandzeit | Seed 1 Basis | Seed 2 Basis | `baseline_reuse` Zusammenfassung |
|---|---:|---|---|---|
| `real-1589-s1` (Basis vs. V1) | `61,57 s` | `played`, `3650334a…29a728` | `played`, `3c8aac84…48b6e2` | `reused_count: 0`, `played_count: 2`, `total_base_games: 2`, `spot_checks_verified: 0` |
| `real-1589-s2` (Basis vs. V2) | `50,57 s` | `played` (**Live-Gegenprobe**, `spot_check_verified: true`), `3650334a…29a728` (exakt identisch) | **`reused`** aus `real-1589-s1` / `real-1589-s1-base-s2-t0`, `game_key: c65a1c00…7b8340`, `3c8aac84…48b6e2` | `reused_count: 1`, `played_count: 1`, `total_base_games: 2`, `spot_checks_verified: 1`, `spot_checks_failed: 0`, `source_series_ids: ["real-1589-s1"]` |

- **Gesamtwandzeit:** `112,14 s` (`7` real gespielte XMage-Partien statt `8`, `0` Abbrüche, `0` Determinismus-Verstöße).
- **Statistik-Hinweis (`maturity.py`):** Geteilte Basis-Arme erzeugen positive Korrelation zwischen Vergleichen derselben Holm-Familie; das Holm-Bonferroni-Verfahren bleibt ohne Unabhängigkeitsannahme gültig und `maturity.py` weist dies explizit in `hinweise` aus. Ohne mindestens `1` bestandene Stichproben-Gegenprobe (`spot_checks_verified < 1`) fällt die Serie fail-closed aus dem Reifegrad heraus (`stufe = None`, `belegt = False`).

## 2. Grenzen und `UNKNOWN` / `NOT_RUN`

- **Stichprobe:** `N = 2` Paare je Serie auf einem 4-Sitz-Precon-Tisch unter Linux/WSL2; Pool-Pfad (`COMMANDER_LAB_STUDIO_SERIES_POOL=1`) mit echter Engine, andere Tische/Sitzzahlen und natives Windows sind hier `NOT_RUN` / `UNKNOWN`.
- **Rohlogs:** Lagen in einem temporären Verzeichnis außerhalb des Repositories und wurden nach dem Lauf entfernt.
