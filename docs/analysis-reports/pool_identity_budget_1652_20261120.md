# Serien-Pool (`#1652`): P3-A-Behebung, Echt-Engine-Identität und 56-Partien/JVM-Budget-Nachweis am Owner-PC (WSL2)

- **Datum:** 2026-11-20 · **Refs:** `#1652`, `#1612`, `#1585`, `#1670`, `#1588`
- **Einordnung:** `SIMULATED_RESULT` / `DIRECTLY_VERIFIED` (Messung & Regressionstest, **kein Qualifikationsbeleg**).
- **Schalter-Status:** `COMMANDER_LAB_STUDIO_SERIES_POOL` bleibt **AUS** (`OFF` per Default), weil Bedingung 3 aus `#1652` (natives Windows `taskkill /T /F`) in WSL2 nicht prüfbar ist (`UNKNOWN`).
- **Basisstand & Engine-Pin:** Repository-Basis `88545070108373c59e260602c889b0c6ef6f83e8`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`, Release-JAR-SHA-256 `840e50abefdaa023072c8c03953e8689a6189a96d3837c5f0c72baf6f8086f6f`, Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (gesiegelte Epoche `5bd29ab6f318-c6942825587a`).
- **Gerät & Laufzeit (WSL2):** `AMD Ryzen 7 7700 8-Core Processor` (`8C/16T`, `3792,8 MHz`), `15.992,19 MB` (`15,6 GiB`) WSL2-RAM, `8,0 GiB` Swap, `Linux 6.6.87.2-microsoft-standard-WSL2`, `OpenJDK 21.0.13.1`, `Python 3.14.4`. Bridge mit `SerialGC`, `-Dh2.bindAddress=127.0.0.1`, AppCDS (`xmage-engine-bridge.jsa`, `308 MB`, SHA-256 `f36ee5ed47382681d54be2949e1fb1e136bdbe74dd72dfeaa958547b892ea87`) und `-Dcommanderlab.fullGame.skipForcedDecisions=true` (sofern nicht explizit Einzelläufer ohne Fast-Schalter angegeben).

---

## 1. P3-A-Behebung (`GamePool`: Event-Queue vor EOF-Fristprüfung leeren)

**Befund aus dem Review zu `#1670`:** Bei `workers >= 2` und > `ENDED_EOF_GRACE_SECONDS` (`5 s`) Pause zwischen zwei Look-Fenstern konnte `_idle_worker` einen bereits beendeten Worker (`worker.ended == True`) wegen abgelaufener Frist über `_lose(worker)` aus `self._workers` entfernen, bevor `run()` bereits eingereihte `jvm_exit`- und `bye`-Ereignisse aus `self._events` gelesen hatte (`worker not in self._workers` verwarf sie und zählte fälschlich `worker_lost`).

- **Änderung (`src/commander_lab/studio/game_pool.py`):** Ereignisverarbeitung in `_consume_event` und `_drain_events` extrahiert; `GamePool.run` ruft zu Beginn jeder Schleifeniteration `_drain_events(...)` auf, noch vor `while pending:` / `_idle_worker(limit)`. Ein zwischen zwei Fenstern eingereihtes `jvm_exit` / `bye` / EOF wird dadurch zuerst verbucht, bevor eine abgelaufene EOF-Frist greifen kann.
- **Diskriminierende Tests (`tests/unit/test_studio_game_pool.py`):**
  - `test_p3a_queued_jvm_exit_and_bye_are_drained_before_idle_grace_drops_worker` (Vorher mit `ended_at -= 10.0`: **FAIL** mit `jvm_lives_lost == 1` statt `0`; Nachher: **PASS**, `4/4` Partien, `jvm_lives_lost == 0`, `w1-1` `end == "series_closed"` erhalten).
  - `test_p3a_queued_jvm_exit_without_eof_is_kept_when_grace_expires` (Vorher ohne EOF/`bye` bei gehaltenem Pipe-Deskriptor: **FAIL**; Nachher: **PASS**, `jvm_exit` `"w1-1"` vor Fristablauf gesichert).
  - Gesamte Suite `tests/unit/test_studio_game_pool.py`: `27/27 passed`.

---

## 2. Bedingung 1: Echt-Engine-Identität, Mehr-Fenster-Pool und `shutdown_unwind == "none"`

### 2.1 `scripts/check_studio_series_identity.py` (`BatchSimulation`-Pfad)

Hinweis zur Abgrenzung: `scripts/check_studio_series_identity.py` prüft `BatchSimulation` (`src/commander_lab/studio/simulations.py`), **nicht** `GamePool` / `COMMANDER_LAB_STUDIO_SERIES_POOL`.

- **Tisch & Seeds:** `chulane_current.json` gegen `precon`-Pod (`2026_lorehold_spirit`, `2024_animated_army`, `2022_token_triumph`), Seeds `1–6` (`N = 6`), Lauf `(a)` Einzel-JVM je Partie (`BASE_COMMAND`, ohne Fast-Schalter) vs. Lauf `(b)` `BatchSimulation` (`workers=2`, `games_per_jvm=3`, Fast-Schalter + AppCDS).
- **Ergebnis:** **`6/6` `IDENTITY PASS`** — `semantic_transcript_sha256`, `winner_seats` und `decision_count` jeweils `6/6` identisch (`36016f9988c6b816`, `2112bef28a588586`, `e87ed79cf416c98f`, `a174c33661f6cf47`, `6b05af520015d29e`, `8f16c26ffde331f2`). Wandzeit `112,9 s` → `45,2 s`, Child-CPU `297,3 s` → `132,2 s` (`SIMULATED_RESULT`).

### 2.2 Direkter Nachweis `shutdown_unwind == "none"` auf `XmageFullGameSeriesSession`

- **Aufbau:** `XmageFullGameSeriesSession` (`gamesPerJvm=6`, Release-JAR `840e50ab…`, AppCDS + `skipForcedDecisions=true`), `chulane_current` gegen `precon`-Pod, Seeds `1–6` (`6` Partien in `1` JVM-Leben `unwind-1`), Rohantworten von `_RawFullGameClient.request("shutdown_game")` direkt aufgezeichnet.
- **Ergebnis:** **`6/6` Partien regulär beendet** in `68,98 s`; alle **`6/6` Roh-Acks** liefern `shutdown_unwind == "none"`, `shut_down == True`, `engine_thread_alive == False`, `game_over == True`; das JVM-Leben endete planmäßig mit `{"life_id": "unwind-1", "games": 6, "end": "budget", "disposition": "graceful_shutdown"}`.

### 2.3 Mehr-Fenster-`compare-decks` mit `GamePool` (`POOL=0` vs. `POOL=1` vs. Einzel-JVM)

- **Tisch & Parameter:** `2026_lorehold_spirit` (Basis) vs. `2023_divine_convocation` (Variante) gegen `2024_animated_army`, `2022_token_triumph`, `2023_veloci_ramp_tor`; `compare-decks --pairs 12 --look-every 4 --base-seed 1000 --rotate-seats` (`3` geplante und genutzte O'Brien-Fleming-Fenster: Seeds `1000`, `1001`, `1002`; je `4` Paare = `8` Partien pro Fenster, gesamt `24` Partien).
- **Läufe (sequenziell auf leerem System, `loadavg 0,74` vor Start):**
  1. `single`: `--workers 1 --games-per-jvm 1`, `COMMANDER_LAB_STUDIO_SERIES_POOL=0` (Hinweis: `recorded_game_player` nutzt den Basiskommando-Pfad ohne `skipForcedDecisions=true`).
  2. `no_pool` (Vorher): `--workers 3 --games-per-jvm 16`, `COMMANDER_LAB_STUDIO_SERIES_POOL=0` (`Chunked` über `play_batch` je Fenster).
  3. `pool` (Nachher): `--workers 3 --games-per-jvm 16`, `COMMANDER_LAB_STUDIO_SERIES_POOL=1` (`GamePool` über alle 3 Fenster).

| Vergleich / Metrik | `n/N` | Befund |
|---|---|---|
| `single` vs. `no_pool`: `semantic_transcript_sha256` / `winner_seats` / `decision_count` | `24/24` / `24/24` / `24/24` | Identisch (`single` hat durch `skipForcedDecisions=false` mehr Frames, gleiche `decision_count`) |
| `single` vs. `pool`: `semantic_transcript_sha256` / `winner_seats` / `decision_count` | `24/24` / `24/24` / `24/24` | Identisch |
| `no_pool` vs. `pool` (gleiche Bridge-Schalter): `semantic` / `winner` / `decisions` / `frame_count` | `24/24` / `24/24` / `24/24` / `24/24` | 100 % deckungsgleich |
| `no_pool` vs. `pool`: `frame_digest` (bereinigt um ephemere 3-Hex-`[xxx]`-Objekt-IDs) | `24/24` | Rohe Abweichungen ausschließlich `[xxx]`-Kurz-IDs in `prompt` (`choose_use`, `mana_payment`) und `chosen` (`replacement_effect`); bereinigt `24/24` bit-identisch |
| `no_pool` vs. `pool`: `result_digest` (ohne `_VOLATILE_RESULT_KEYS`) | `24/24` außer `result_basis` | Abweichung allein `result_basis`: `None` (`BatchRecordingRunner`) vs. `SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT` (`XmageFullGameSeriesSession`) |
| Serien-Ergebnis (`compare-decks`) über alle 3 Läufe | `12/12` Paare, `0/12` zensiert | `NOT_DECIDED`, `BUDGET_EXHAUSTED`, `looks_used=3/3`, `variant_only_wins=2`, `baseline_only_wins=3`, `tied_pairs=7`, `difference_pp=-8.333` in allen 3 Läufen identisch |

**Nachweis Pool-Wiederverwendung über Look-Fenster-Grenzen (`POOL=1`):**

- Alle `24` Partien liefen in genau **`3` persistenten JVM-Leben** statt je-Fenster-Chunks (`0` Fehler, `0` Neustarts):
  - `w1-1`: `9` Partien — Look 1 (`pos 1..3`), Look 2 (`pos 4..6`), Look 3 (`pos 7..9`).
  - `w2-1`: `7` Partien — Look 1 (`pos 1..3`), Look 2 (`pos 4..5`), Look 3 (`pos 6..7`).
  - `w3-1`: `8` Partien — Look 1 (`pos 1..2`), Look 2 (`pos 3..5`), Look 3 (`pos 6..8`).

**Vorher-/Nachher-Durchsatz am Owner-PC (`24` Partien, `3` Look-Fenster, `workers=3`, `games_per_jvm=16`):**

| Lauf | Modus | Partien | Wandzeit (s) | Durchsatz (Partien/min) | Durchsatz (Partien/h) | Einordnung |
|---|---|---|---|---|---|---|
| `single` | `workers=1, games_per_jvm=1, POOL=0` | `24/24` | `341,69` | `4,21` | `252,9` | Referenz (ohne `skipForcedDecisions`) |
| `no_pool` (Vorher) | `workers=3, games_per_jvm=16, POOL=0` | `24/24` | `172,89` | `8,33` | `500,0` | Bisheriges Fenstermuster (`3` Barrieren) |
| `pool` (Nachher) | `workers=3, games_per_jvm=16, POOL=1` | `24/24` | **`109,30`** | **`13,17`** | **`790,5`** | **`-36,8 %` Wandzeit (`1,58x` schneller vs. `POOL=0`)** |

---

## 3. Bedingung 2: 56-Partien/JVM-Budget-, Speicher- und Identitätskurve

`SERIES_JVM_GAME_CAP = 56` (`src/commander_lab/engine/rules/full_game_series.py`) direkt mit `GamePool(workers=1)` und `-Dcommanderlab.fullGame.gamesPerJvm=56` geprüft: `4` aufeinanderfolgende `pool.run`-Fenster à `14` Partien = **`56` 4P-Precon-Partien** (`2026_lorehold_spirit`, `2024_animated_army`, `2022_token_triumph`, `2023_veloci_ramp_tor`, Seeds `2001–2056`). `/proc/<java_pid>/status` (`VmRSS`, `VmHWM`) und `/proc/meminfo` wurden alle `0,5 s` abgetastet.

- **Vollständigkeit & Lebensende:** `56/56` Partien mit `status="finished"` (`54/56` mit eindeutigem Sieger, `2/56` Seeds `2040` und `2056` regulär ohne Sieger beendet; `0/56` Fehler); Gesamtlaufzeit **`428,92 s`** (`470,0` Partien/h auf nur **1 Worker**). `pool.summary()`: `worker_processes_started=1`, `games_finished=56`, `games_failed=0`, `jvm_lives_ended=1`, `jvm_lives_lost=0`, Leben `w1-1`: `games=56`, `end="budget"`, `disposition="graceful_shutdown"`.
- **Speicherverlauf (Java-Kind-PID):**

| Meilenstein (Partie `n/56`) | Seed | `position_in_jvm` | Zeit kumulativ (s) | Java `VmRSS` (MiB) | Java `VmHWM` (MiB) |
|---|---|---|---|---|---|
| `1/56` | `2001` | `1` | `24,31` | `1343,7` | `1343,7` |
| `8/56` | `2008` | `8` | `78,33` | `1366,8` | `1366,8` |
| `16/56` | `2016` | `16` | `136,24` | `1373,2` | `1381,4` |
| `24/56` | `2024` | `24` | `203,06` | `1409,3` | `1409,4` |
| `32/56` | `2032` | `32` | `255,27` | `1423,2` | `1423,8` |
| `40/56` | `2040` | `40` | `307,17` | `1428,7` | `1429,8` |
| `48/56` | `2048` | `48` | `363,14` | `1433,9` | `1440,8` |
| `55/56` (letzte Messung vor `budget`-Exit) | `2055` | `55` | `412,30` | `1429,1` | `1441,4` |

  - **Gesamt-Peak über alle `0,5 s`-Samples:** `VmRSS = 1441,4 MiB`, `VmHWM = 1441,4 MiB` (`+97,7 MiB` gegenüber Partie `1`), **Swap-Delta `-0,5 MB`** (keinerlei Auslagerung). Die Kurve flacht ab Partie `32` auf ein Plateau um `~1425–1441 MiB` ab; ein Budget bis `56` Partien pro JVM ist speicherseitig in WSL2 stabil.
- **Identitäts-Gegenprobe bei Partie `#56` (`position_in_jvm=56` vs. frische `1`-JVM-Referenz `position_in_jvm=1`, Seed `2056`):**
  - `semantic_transcript_sha256`: **identisch** (`43125b2293da91ec4a259a20f278f566f3dc1c4e38568a803473dfbbbe904c35`).
  - `winner_seats`: identisch (`[]`), `decision_count`: identisch (`5044 == 5044`), `frames`: identisch (`3697 == 3697`).
  - Bereinigter `frame_digest` (ohne ephemere 3-Hex-`[xxx]`-Objekt-IDs): **identisch** (`8b09108eed881e27…`); in allen `3697` Frames lagen als Rohunterschied ausschließlich `[xxx]`-IDs in `mana_payment`- (`797`) und `choose_use`-Prompts (`48`) vor.

---

## 4. Verbleibende `UNKNOWN` / Offen bis zum Einschalten von `COMMANDER_LAB_STUDIO_SERIES_POOL`

| Bedingung (`#1652`) | Stand (2026-11-20) | Nachweis |
|---|---|---|
| **P3-A:** Queue vor EOF-Fristprüfung in `_idle_worker` | **PASS** | `game_pool.py` + `2/2` P3-A-Tests (`27/27` gesamt) |
| **1a:** `scripts/check_studio_series_identity.py` | **PASS** | `6/6` identisch (`BatchSimulation`) |
| **1b:** Mehr-Fenster-Identität `GamePool` + `shutdown_unwind == "none"` | **PASS** | `24/24` Transkript/Sieger/Entscheidungen/norm. Frames; `6/6` `shutdown_unwind == "none"` |
| **2:** Budget `56` Partien/JVM, Speicher & Vorher/Nachher | **PASS** | `56/56` ok, Peak `1441,4 MiB` (`+97,7 MiB`), Swap `-0,5 MB`, Seed `2056` identisch; `172,89 s` → `109,30 s` (`1,58x`) |
| **3:** Prozessbaum unter nativem Windows (`taskkill /T /F`) | **`UNKNOWN` / `NOT_RUN`** | Unter WSL2 Linux nicht testbar; vor Default-Aktivierung nativ unter Windows prüfen (Worker killen / retire prüfen -> keine verwaiste `java.exe`) |
