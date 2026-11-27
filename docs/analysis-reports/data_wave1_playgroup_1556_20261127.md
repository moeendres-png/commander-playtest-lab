# Datensammlung Welle 1: Playgroup-Commander-Statistik (Issue #1556)

- **Datum:** 2026-11-27
- **Repository-Stand (`origin/main`):** `f13666f2c2288ab242fba7e4681a15e55ea0466b`
- **Branch:** `docs/data-wave1-playgroup-1556`
- **Evidenzklasse:** `DIRECTLY_VERIFIED` (Staging-Abruf, Ableitung und Offline-Validierung außerhalb des Repositories ausgeführt)
- **Staging-Ziel (außerhalb Repo):** `$HOME/studio-analyse/staging/S3_playgroup/20261127T131320Z/`

---

## 1. Abrufprotokoll und Provenienz

- **Skript:** `scripts/data_wave1/fetch_s3_playgroup.py` (sequenziell, `1,0 s` Pause, Obergrenze `80` Anfragen, Fail-Closed bei HTTP `403`/`429`).
- **Header:** `User-Agent: mtg-deck-tool/1.0 (local research script)` (generischer Programmname ohne Projekt-, Repo- oder Personenbezug; DATA-S4-Standard ohne Kontaktangabe), `Accept: */*`.
- **Zeitraum (UTC):** `2026-11-27T13:13:20Z` bis `2026-11-27T13:15:00Z`.
- **Anfragen:** **`59 / 80`** (`complete: true`, `0` HTTP `429`, `0` HTTP `403`, `0` Retries, alle `59` Antworten HTTP `200`):
  - `57` nicht-leere Listenseiten (`GET https://playgroup.gg/api/public/v1/commanders?page=1..57&limit=100`, Seiten `1..56` je `100` Zeilen, Seite `57` mit `86` Zeilen).
  - `1` erste leere Seite (`page=58`, `[]`, `2` Bytes).
  - `1` Zug-Werte-Abruf für Chulane (`GET https://playgroup.gg/api/public/v1/commanders/2143/turn_damage`, `2.693` Bytes, `24` Runden).
- **Einordnung zum Vorversuch vom 2026-11-24:** Der damalige Abbruch bei Anfrage `#21` (`HTTP 429`, `docs/analysis-reports/data_wave1_staging_1554_1555_1556_20261124.md`) nutzte `?limit=100&offset=...` statt `?page=N&limit=100`, wodurch derselbe Seitenpfad wiederholt getroffen wurde und das dokumentierte Limit („dieselbe Seite höchstens 20× in 10 min“) auslöste. Mit `page=N` lief der Abruf ohne Rate-Limit-Fehler durch.
- **Lizenz & Nennung:** `CC BY 4.0` laut Betreiber-Doku (`https://playgroup.gg/api/public/v1/openapi.yaml`); Nennung mit Link `playgroup_url` je Commander (`5.686 / 5.686` vorhanden).
- **Kohorte:** `playgroup_bewertete_sitze` (`beobachtetes_spiel`: nur Sitze mit Salt-Bewertung in beendeten Partien mit Siegbedingung; zwei Decks desselben Commanders in einer Partie zählen doppelt).
- **Rohdaten-Bereinigung:** `derive_s3_commanders.py` hat alle `117` Rohdateien unter `raw/` nach der Ableitung gelöscht (`2026-11-27T13:15:11Z`, `raw_retained: false`, `personal_data: none`). Entfernte Felder: `average_salt_rating`, `average_fun_rating`, `top_decks`, `scryfall_id`, `art_crop_url`, `normal_url`, `card_image`.

### Staging-Artefakte (alle außerhalb des Repositories)

| Datei | Größe (Bytes) | SHA-256 | Inhalt / Vermerk |
|---|---:|---|---|
| `derived/playgroup_commanders.jsonl` | `5.087.245` | `ae8c56c9f053fe90a1953d2851a0a54982d23969a0c64eb2d659e74f990241d4` | `5.686` Commander-Zeilen, aggregierte Felder, `personal_data: none` |
| `derived/chulane_turn_damage.json` | `3.753` | `f30498750376a912c650bdde5887ecd62dbcdf2776c51a20d54f0aa42b0fd2de` | `24` Runden für `id = 2143`; ausdrücklich `NICHT BELASTBAR` |
| `derived/validation.json` | `1.099` | `9d904b144a28006948bfa7d00b7fd664b42ebe9de3dc331f9150583c6971868c` | Prüfbericht (`validate_s3.py`) |
| `MANIFEST.json` | `53.879` | `9a89c1057025a08e0647a86b20c60b9de886795065f76ddebad8e422a21d6ac3` | Vollständiges Abruf- und Ableitungs-Manifest |
| `fetch_log.jsonl` | `37.769` | `b37646490f3bfb9cb7b8ace4d7f458a315a25fc4bd6550527b1abfc7a6f32ffd` | Sequenzielles Anfrageprotokoll (`59` Einträge) |

---

## 2. Validierung (`validate_s3.py`)

| Prüfung / Kennzahl | Ergebnis | Status / Einordnung |
|---|---|---|
| Zahl der Commander (`rows_in` / `commanders_out`) | `5.686` / `5.686` | vollständig |
| Doppelte Commander-IDs (`duplicate_ids`) | `0 / 5.686` | `PASS` |
| Fehlende `playgroup_url` (`rows_without_playgroup_url`) | `0 / 5.686` | `PASS` (CC BY 4.0) |
| Verbotene / Personen- / Preisfelder (`author`, `average_fun_rating`, `average_salt_rating`, `owner`, `pilot`, `scryfall_id`, `top_decks`, `user`) | `0` je Feld (`0 / 5.686`) | `PASS` |
| Chulane enthalten (`chulane_present`) | `true` (`id = 2143`, `Chulane, Teller of Tales`) | `rated_seats_played = 1.117`, `rated_seats_won = 454` |
| Zeilen mit `Siege > Sitze` (`wins_exceed_games_rows`) | `36 / 5.686` (davon `13` mit `0` Sitzen; `max_excess = 14`, `max_seats = 25`) | Quelldefekt bei Kleinstzahlen, markiert, nicht korrigiert |
| Platzhalter-IDs (`id <= 0`) | `1 / 5.686` (`id = -2`) | markiert (`placeholder = true`) |
| Nutzbar nach Regel `n >= 30` und `Siege <= Sitze` und kein Platzhalter | `2.162 / 5.686` | — |
| Summenprüfung der Siegtypen (`sum == rated_seats_won`) | `5.686 / 5.686` | konsistent |
| `chulane_turn_damage.json` | `24` Runden (`max_normal_damage = 2.523.732,11` Zug 9, `max_healing = 1.331,05` Zug 7, Median `11,005`) | `NICHT BELASTBAR` (Mittelwert je Einzelereignis, ohne `n`, Ausreißer) |

### Abgleich gegen die 107 bekannten Commander (`data/research/deckbuilder_1655/playgroup_commander_stats.csv`)

- **Trefferquote:** `107 / 107` Commander-IDs in der API-Liste enthalten (`0` fehlend).
- **Zeilen mit abweichender Spiel-/Sitzzahl:** **`91 / 107`** (`91` kleiner in der Liste, `0` größer, `16 / 107` gleich).
- **Summen (zwei verschiedene Kohorten, nie addieren/mischen):** Liste (`rated_seats_played` auf bewerteten Sitzen) `45.210` gegenüber CSV (`games_count` vom Einzel-Endpunkt, andere Zählregel) `87.129`.

---

## 3. Offene Punkte (`UNKNOWN` / `NOT_RUN`) und Abgrenzung

- **Kartenatlas (`927` Pool-Karten):** `NOT_RUN` — eigener Schritt erst nach Abnahme und ausdrücklichem Owner-Go (HTML-Seitenabruf ohne öffentliche API, `AGENTS.md` §8; siehe Kommentar 7081583221 in `#1556`).
- **Import in `studio.sqlite3`:** `NOT_RUN` — ausdrücklich nicht Teil von Welle 1 (erst nach Stichproben-Abnahme durch die Leitung auf einer Datenbank-Kopie).
- **DATA-S4 (Kontaktangabe im User-Agent):** `UNKNOWN` / offen beim Owner; Standard ohne Kontaktangabe verwendet.
- **UI-Nennung (CC BY 4.0):** In der Oberfläche überall dort zu prüfen, wo Playgroup-Zahlen angezeigt werden.

---

## 4. Tests und Prüfungen

- `python -c "import commander_lab; print(commander_lab.__file__)"`: `$HOME/code/cpl-analyse/src/commander_lab/__init__.py`
- `pytest -q tests/unit/test_data_wave1_scripts.py`: `105 passed`
- `classify_docs.py --check` & `--links`: `OK (0 problems)` (`PASS`)
- `ruff check .` & `ruff format --check .`: `All checks passed` (`PASS`)
- `mypy src/commander_lab`: `Success: no issues found in 239 source files` (`PASS`)
