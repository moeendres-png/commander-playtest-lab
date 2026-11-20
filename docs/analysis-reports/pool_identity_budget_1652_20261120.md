# Serien-Pool (`#1652`): P3-A-Behebung, Echt-Engine-Identität und 56-Partien/JVM-Budget-Nachweis am Owner-PC (WSL2)

- **Datum:** 2026-11-20 · **Refs:** `#1652`, `#1612`, `#1585`, `#1670`, `#1588`
- **Einordnung:** `SIMULATED_RESULT` (lokale Owner-PC-Beobachtung unter WSL2, `n = 1` Lauf je Messung, Rohdaten und Messskripte außerhalb des Repos, **kein CI- oder Qualifikationsbeleg**; `AGENTS.md` §4: *A local observation is not CI credit*).
- **Schalter-Status:** `COMMANDER_LAB_STUDIO_SERIES_POOL` bleibt **AUS** (`OFF` per Default), weil Bedingung 3 aus `#1652` (natives Windows `taskkill /T /F`) in WSL2 nicht prüfbar ist (`UNKNOWN`) und die offenen P2/P3-Punkte (insbesondere Bedingung 1 mit `single`-Frame-Digest sowie `#1652` Punkt 4) dokumentiert bleiben.
- **Basisstand & Engine-Pin:** Repository-Basis `88545070108373c59e260602c889b0c6ef6f83e8` (auf aktuellen `main` nachgezogen), Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), Release-JAR-SHA-256 `840e50abefdaa023072c8c03953e8689a6189a96d3837c5f0c72baf6f8086f6f` (lokaler Owner-PC-Build, Digest steht nicht im Repo), Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (gesiegelte Epoche `5bd29ab6f318-c6942825587a`).
- **Gerät, Laufzeit & lokale Artefakt-Digests (Owner-PC WSL2, Dateien außerhalb des Git-Baums; rohe `.jsonl.gz`-Transkripte nach Auswertung verworfen):** `AMD Ryzen 7 7700 8-Core Processor` (`8C/16T`, `3792,8 MHz`), `15.992,19 MB` (`15,6 GiB`) WSL2-RAM, `8,0 GiB` Swap, `Linux 6.6.87.2-microsoft-standard-WSL2`, `OpenJDK 21.0.13.1`, `Python 3.14.4`. Bridge mit `SerialGC`, `-Dh2.bindAddress=127.0.0.1`, AppCDS (`xmage-engine-bridge.jsa`, `308 MB`, SHA-256 `f36ee5ed47382681d54be2949e1fb1e136bdbe74dd72dfeaa9585547b892ea87`) und `-Dcommanderlab.fullGame.skipForcedDecisions=true` (sofern nicht explizit Einzelläufer ohne Fast-Schalter angegeben). Lokale Sicherungs-Digests (SHA-256):
  - `batch-id.json`: `75231d01e48851dec536cbe9218b4fe7b220c44eb1ce911ac3ddb14aab406eb1`
  - `run_proof_2b.py`: `507201ab28641ec59460cd81fadb559e03faa2b12ec0c77f60fbe67e41bed37c` · `summary_2b.json`: `b7e43ebf658b0f44342251d2f4af1ae7d9af94d9c3044eb6f2721e9a9aa45d09`
  - `run_proof_2c.py`: `a3f2731c67ccf4b2d2e84b74f088aabbc429a925dfb4466c0f74d302e0dcc221` · `summary_2c.json`: `6a8cb38a0521682b573848535196001cdb92e7d4cee3dec04f5e5e67f21fc667`

---

## 1. P3-A-Behebung (`GamePool`: Event-Queue vor EOF-Fristprüfung leeren)

**Befund aus dem Review zu `#1670`:** Bei `workers >= 2` und > `ENDED_EOF_GRACE_SECONDS` (`5 s`) Pause zwischen zwei Look-Fenstern konnte `_idle_worker` einen bereits beendeten Worker (`worker.ended == True`) wegen abgelaufener Frist über `_lose(worker)` aus `self._workers` entfernen, bevor `run()` bereits eingereihte `jvm_exit`- und `bye`-Ereignisse aus `self._events` gelesen hatte (`worker not in self._workers` verwarf sie und zählte fälschlich `worker_lost`).

- **Änderung (`src/commander_lab/studio/game_pool.py`):** Ereignisverarbeitung in `_consume_event` und `_drain_events` extrahiert; `GamePool.run` ruft zu Beginn jeder Schleifeniteration `_drain_events(...)` auf, noch vor `while pending:` / `_idle_worker(limit)`. Ein zwischen zwei Fenstern eingereihtes `jvm_exit` / `bye` / EOF wird dadurch zuerst verbucht, bevor eine abgelaufene EOF-Frist greifen kann.
- **Diskriminierende Tests (`tests/unit/test_studio_game_pool.py`):**
  - `test_p3a_queued_jvm_exit_and_bye_are_drained_before_idle_grace_drops_worker` (Vorher mit `ended_at -= 10.0`: **FAIL** mit `jvm_lives_lost == 1` statt `0`; Nachher: **PASS**, `4/4` Partien, `jvm_lives_lost == 0`, `w1-1` `end == "series_closed"` erhalten; prüft zudem ausdrücklich `ENDED_EOF_GRACE_SECONDS == 5.0`).
  - `test_p3a_queued_eof_retires_worker_via_drain_even_when_grace_is_large` (`ended_eof_grace_seconds = 60.0` ohne Altern von `ended_at`: ohne EOF-Behandlung im Drain überlebt `worker_one` in `pool._workers` mit `worker_processes_started == 2`; mit Fix: `worker_one not in pool._workers`, `worker_processes_started == 3`, `jvm_lives_lost == 0`).
  - `test_p3a_queued_jvm_exit_without_eof_is_kept_when_grace_expires` (synthetische Sonde ohne gehaltenen externen Pipe-Deskriptor: markiert einen lebenden Worker als `ended = True` mit abgelaufenem `ended_at` und injiziert `jvm_exit` ohne EOF; bestätigt `w1-1` `end == "budget"` neben bekanntem **`jvm_lives_lost == 1`** aus späterem `_lose` — offener Rest `#1652` Punkt 4).
  - Gesamte Suite `tests/unit/test_studio_game_pool.py`: `28/28 passed`.

---

## 2. Bedingung 1: Echt-Engine-Identität, Mehr-Fenster-Pool und `shutdown_unwind == "none"` (`PARTIAL`, lokale Owner-PC-Beobachtung)

Warum Bedingung 1 als **`PARTIAL`** eingestuft wird:
- `2.1` (`scripts/check_studio_series_identity.py`) nutzt ausschließlich `BatchSimulation`, **nicht** `GamePool` / `COMMANDER_LAB_STUDIO_SERIES_POOL` (`0/6` Pool-Abdeckung).
- `2.3` (`24` Partien) liefert für den Vergleich `single` vs. `pool` zwar `24/24` identische `semantic_transcript_sha256`, `winner_seats` und `decision_count`, jedoch **`0/24` Frame-Digest-Vergleiche gegen `single`**, weil `single` (`recorded_game_player`) ohne `skipForcedDecisions=true` lief (`no_pool` vs. `pool` liefert in `summary_2b.json` roh `0/24` und erst durch die nachträgliche `r"\[[0-9a-f]{3}\]"`-Normalisierung der damals gespeicherten `.jsonl.gz`-Logs `24/24` Identität bei gleichen Schaltern `games_per_jvm=16`). Der einzige direkte Frame-Vergleich gegen eine frische Einzel-JVM mit denselben Schaltern liegt in §3 für Seed `2056` (`n = 1/1`, in `summary_2c.json` unter `SHORT_ID_RE` `false`, nach Bereinigung mit `r"\[[0-9a-f]{3}\]"` `1/1`) vor.

### 2.1 `scripts/check_studio_series_identity.py` (`BatchSimulation`-Pfad)

- **Tisch & Seeds:** `chulane_current.json` gegen `precon`-Pod (`2026_lorehold_spirit`, `2024_animated_army`, `2022_token_triumph`), Seeds `1–6` (`N = 6`), Lauf `(a)` Einzel-JVM je Partie (`BASE_COMMAND`, ohne Fast-Schalter) vs. Lauf `(b)` `BatchSimulation` (`workers=2`, `games_per_jvm=3`, Fast-Schalter + AppCDS). Aufruf: `python scripts/check_studio_series_identity.py` (mit lokalem Release-JAR im Env).
- **Beobachtetes Ergebnis (`n = 1` Lauf, `SIMULATED_RESULT`):** `6/6` `IDENTITY PASS` — `semantic_transcript_sha256`, `winner_seats` und `decision_count` jeweils `6/6` identisch (`36016f9988c6b816`, `2112bef28a588586`, `e87ed79cf416c98f`, `a174c33661f6cf47`, `6b05af520015d29e`, `8f16c26ffde331f2`). Wandzeit `112,9 s` → `45,2 s`, Child-CPU `297,3 s` → `132,2 s` (`batch-id.json`).

### 2.2 Direkter Nachweis `shutdown_unwind == "none"` auf `XmageFullGameSeriesSession`

- **Aufbau (lokales Owner-PC-Skript `run_proof_2b.py`, nicht im Repo):** `XmageFullGameSeriesSession` (`gamesPerJvm=6`, Release-JAR `840e50ab…`, AppCDS + `skipForcedDecisions=true`), `chulane_current` gegen `precon`-Pod, Seeds `1–6` (`6` Partien in `1` JVM-Leben `unwind-1`), Rohantworten von `_RawFullGameClient.request("shutdown_game")` direkt aufgezeichnet (`summary_2b.json`).
- **Beobachtetes Ergebnis (`n = 1` Lauf):** `6/6` Partien regulär beendet in `68,98 s`; alle **`6/6` Roh-Acks** liefern `shutdown_unwind == "none"`, `shut_down == True`, `engine_thread_alive == False`, `game_over == True`; das JVM-Leben endete planmäßig mit `{"life_id": "unwind-1", "games": 6, "end": "budget", "disposition": "graceful_shutdown"}`.

### 2.3 Mehr-Fenster-`compare-decks` mit `GamePool` (`POOL=0` vs. `POOL=1` vs. Einzel-JVM)

- **Tisch & Parameter (lokales Skript `run_proof_2b.py`, `summary_2b.json`, nicht im Repo):** `2026_lorehold_spirit` (Basis) vs. `2023_divine_convocation` (Variante) gegen `2024_animated_army`, `2022_token_triumph`, `2023_veloci_ramp_tor`; `compare-decks --pairs 12 --look-every 4 --base-seed 1000 --rotate-seats` (`3` geplante und genutzte O'Brien-Fleming-Fenster: Seeds `1000`, `1001`, `1002`; je `4` Paare = `8` Partien pro Fenster, gesamt `24` Partien, `4` Sitze).
- **Ad-hoc-Frame-Normalisierer (offengelegt):** Die Frame-Digests in `2.3` und `3` wurden **nicht** mit `src/commander_lab/engine/rules/frame_digest.py` berechnet. `run_proof_2b.py` (`507201ab…`, §2.3) enthält gar keinen Normalisierer und weist in `summary_2b.json` beim rohen `frame_digest` für `no_pool` vs. `pool` deshalb `0/24` aus. `run_proof_2c.py:16` (`a3f2731c…`, §3) definiert `SHORT_ID_RE = re.compile(r" \[[0-9a-f]{3}\](?=[:\s]|$)")` auf `prompt`/`chosen` und liefert in `summary_2c.json` (`6a8cb38a…`) wegen `"( Sakura-Tribe Elder [02f])?"` in Frame `653` (`choose_use`, fehlendes Leerzeichen bzw. Doppelpunkt nach `]`) weiterhin `"norm_frames_equal": false` (`pos56`: `f90d5baae8794963…` vs. `fresh1`: `5736414fdf82e990…`). Erst eine nachträgliche Ad-hoc-Bereinigung auf den damals vorliegenden `.jsonl.gz`-Rohlogs mit dem breiteren Muster `r"\[[0-9a-f]{3}\]"` entfernte auch diese Restfälle und ergab die unten genannten bereinigten Identitäten (`24/24` bzw. Seed `2056` `8b09108eed881e27…`; aus den archivierten Zusammenfassungen allein nicht erneut berechenbar).
- **Läufe (sequenziell auf leerem System, `loadavg 0,74` vor Start, je `n = 1` Lauf ohne Streuung):**
  1. `single`: `--workers 1 --games-per-jvm 1`, `COMMANDER_LAB_STUDIO_SERIES_POOL=0` (`recorded_game_player` nutzt den Basiskommando-Pfad ohne `skipForcedDecisions=true`).
  2. `no_pool` (Vorher): `--workers 3 --games-per-jvm 16`, `COMMANDER_LAB_STUDIO_SERIES_POOL=0` (`Chunked` über `play_batch` je Fenster).
  3. `pool` (Nachher): `--workers 3 --games-per-jvm 16`, `COMMANDER_LAB_STUDIO_SERIES_POOL=1` (`GamePool` über alle 3 Fenster).

| Vergleich / Metrik | `n/N` | Beobachtung (`n = 1` Lauf) |
|---|---|---|
| `single` vs. `no_pool`: `semantic_transcript_sha256` / `winner_seats` / `decision_count` | `24/24` / `24/24` / `24/24` | Identisch (`single` hat durch `skipForcedDecisions=false` mehr Frames, **kein** Frame-Digest-Vergleich: `0/24`) |
| `single` vs. `pool`: `semantic_transcript_sha256` / `winner_seats` / `decision_count` | `24/24` / `24/24` / `24/24` | Identisch (**kein** Frame-Digest-Vergleich: `0/24`) |
| `no_pool` vs. `pool` (gleiche Bridge-Schalter): `semantic` / `winner` / `decisions` / `frame_count` | `24/24` / `24/24` / `24/24` / `24/24` | 100 % deckungsgleich (je `games_per_jvm=16`) |
| `no_pool` vs. `pool`: `frame_digest` (roh in `summary_2b.json`) vs. nachträglich ad-hoc-normiert (`.jsonl.gz`) | `0/24` roh · `24/24` nachträglich bereinigt | Rohe Abweichungen ausschließlich `[xxx]`-Kurz-IDs in `prompt` (`choose_use`, `mana_payment`) und `chosen` (`replacement_effect`); `summary_2b.json` weist roh `0/24` aus, nachträgliche `r"\[[0-9a-f]{3}\]"`-Bereinigung der damals gespeicherten `.jsonl.gz`-Logs `24/24` |
| `no_pool` vs. `pool`: `result_digest` (ohne `_VOLATILE_RESULT_KEYS`) | `24/24` außer `result_basis` | Abweichung allein `result_basis`: `None` (`BatchRecordingRunner`) vs. `SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT` (`XmageFullGameSeriesSession`) |
| Serien-Ergebnis (`compare-decks`) über alle 3 Läufe | `12/12` Paare, `0/12` zensiert | `NOT_DECIDED`, `BUDGET_EXHAUSTED`, `looks_used=3/3`, `variant_only_wins=2`, `baseline_only_wins=3`, `tied_pairs=7`, `difference_pp=-8.333` in allen 3 Läufen identisch |

**Pool-Wiederverwendung über Look-Fenster-Grenzen (`POOL=1`):** Alle `24` Partien liefen in **`3` persistenten JVM-Leben** (`w1-1`: `9` Partien über Looks `1–3`; `w2-1`: `7`; `w3-1`: `8`; `0` Fehler, `0` Neustarts).

**Vorher-/Nachher-Durchsatz am Owner-PC (`24` Partien, `3` Look-Fenster, `workers=3`, `games_per_jvm=16`, je `n = 1` Lauf ohne Streuung):**

| Lauf | Modus | Partien | Wandzeit (s) | Durchsatz (Partien/min) | Durchsatz (Partien/h) | Einordnung (`n = 1`) |
|---|---|---|---|---|---|---|
| `single` | `workers=1, games_per_jvm=1, POOL=0` | `24/24` | `341,69` | `4,21` | `252,9` | Referenz (ohne `skipForcedDecisions`) |
| `no_pool` (Vorher) | `workers=3, games_per_jvm=16, POOL=0` | `24/24` | `172,89` | `8,33` | `499,7` | Bisheriges Fenstermuster (`3` Barrieren; exakt `24/(172,89/3600)`) |
| `pool` (Nachher) | `workers=3, games_per_jvm=16, POOL=1` | `24/24` | **`109,30`** | **`13,17`** | **`790,5`** | **`-36,8 %` Wandzeit (`1,58x` vs. `POOL=0`, je `n = 1` Lauf ohne Streuung)** |

---

## 3. Bedingung 2: 56-Partien/JVM-Budget-, Speicher- und Identitätskurve (lokale Owner-PC-Beobachtung)

`SERIES_JVM_GAME_CAP = 56` (`src/commander_lab/engine/rules/full_game_series.py`) lokal mit `run_proof_2c.py` (`summary_2c.json`, nicht im Repo) am Owner-PC unter WSL2 getestet (`GamePool(workers=1)` und `-Dcommanderlab.fullGame.gamesPerJvm=56`, `4` aufeinanderfolgende `pool.run`-Fenster à `14` Partien = **`56` 4P-Precon-Partien**: `2026_lorehold_spirit`, `2024_animated_army`, `2022_token_triumph`, `2023_veloci_ramp_tor`, Seeds `2001–2056`). `/proc/<java_pid>/status` (`VmRSS`, `VmHWM`) und `/proc/meminfo` wurden alle `0,5 s` abgetastet.

- **Vollständigkeit & Lebensende (`n = 1` Lauf):** `56/56` Partien mit `status="finished"` (`54/56` mit eindeutigem Sieger, `2/56` Seeds `2040` und `2056` regulär ohne Sieger beendet; `0/56` Fehler); Gesamtlaufzeit **`428,92 s`** (`470,0` Partien/h auf **1 Worker**). `pool.summary()`: `worker_processes_started=1`, `games_finished=56`, `games_failed=0`, `jvm_lives_ended=1`, `jvm_lives_lost=0`, Leben `w1-1`: `games=56`, `end="budget"`, `disposition="graceful_shutdown"`.
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

  - **Gesamt-Peak über alle `0,5 s`-Samples:** `VmRSS = 1441,4 MiB`, `VmHWM = 1441,4 MiB` (`+97,7 MiB` gegenüber Partie `1`), **Swap-Delta `-0,5 MB`** (keinerlei Auslagerung). Die Kurve flacht ab Partie `32` auf `~1425–1441 MiB` ab (`n = 1` Lauf in WSL2).
- **Einzel-JVM-Identitäts-Gegenprobe bei Partie `#56` (`position_in_jvm=56` vs. frische `1`-JVM-Referenz `position_in_jvm=1`, Seed `2056`, `n = 1/1`):**
  - `semantic_transcript_sha256`: **identisch** (`43125b2293da91ec4a259a20f278f566f3dc1c4e38568a803473dfbbbe904c35`).
  - `winner_seats`: identisch (`[]`), `decision_count`: identisch (`5044 == 5044`), `frames`: identisch (`3697 == 3697`).
  - Ad-hoc-bereinigter Frame-Digest: `run_proof_2c.py:16` (`SHORT_ID_RE` mit `(?=[:\s]|$)` auf `prompt`/`chosen`) liefert in `summary_2c.json` noch `"norm_frames_equal": false` (`pos56`: `f90d5baae8794963…` vs. `fresh1`: `5736414fdf82e990…`) wegen Frame `653` (`"( Sakura-Tribe Elder [02f])?"`); erst die nachträgliche Bereinigung der damals vorliegenden `.jsonl.gz`-Rohlogs mit `r"\[[0-9a-f]{3}\]"` ergab **identisch** `8b09108eed881e27…` (Unterschiede über alle `3697` Frames ausschließlich `[xxx]`-IDs in `mana_payment`- (`797`) und `choose_use`-Prompts (`48`)).

---

## 4. Status-Tafel & offene Punkte vor einer Aktivierung von `COMMANDER_LAB_STUDIO_SERIES_POOL`

| Bedingung / Thema (`#1652`) | Stand (2026-11-20) | Nachweis & Grenzen (`n/N`, Herkunft) |
|---|---|---|
| **P3-A:** Queue vor EOF-Fristprüfung in `_idle_worker` | **PASS (Unit-Tests im Repo)** | `game_pool.py` + `3/3` P3-A-Tests (`28/28` in `test_studio_game_pool.py`) |
| **1a:** `scripts/check_studio_series_identity.py` | **PARTIAL (lokal beobachtet, Owner-PC, `n = 1` Lauf)** | `6/6` identisch auf `BatchSimulation`, berührt weder `GamePool` noch den Schalter (`0/6`) |
| **1b:** Mehr-Fenster-Identität `GamePool` + `shutdown_unwind == "none"` | **PARTIAL (lokal beobachtet, Owner-PC, `n = 1` Lauf, nicht im Repo)** | `24/24` Transkript/Sieger/Entscheidungen über `3` Look-Fenster gegen `single` & `no_pool`; `0/24` rohe Frame-Digests in `summary_2b.json` (gegen `single` wegen `skipForcedDecisions`, `no_pool` vs. `pool` wegen `[xxx]`-IDs); `24/24` nachträglich `r"\[[0-9a-f]{3}\]"`-bereinigt (`no_pool` vs. `pool`); Seed `2056` in `summary_2c.json` unter `SHORT_ID_RE` noch `norm_frames_equal=false`, erst nachträglich `1/1` (`n = 1/1`); `6/6` `shutdown_unwind == "none"` |
| **2:** Budget `56` Partien/JVM, Speicher & Vorher/Nachher | **Lokal beobachtet (Owner-PC, `n = 1` Lauf, nicht aus dem Repo reproduzierbar)** | `56/56` ok, Peak `1441,4 MiB` (`+97,7 MiB`), Swap `-0,5 MB`, Seed `2056` (`n = 1/1`); Durchsatz `172,89 s` (`499,7` Partien/h) → `109,30 s` (`790,5` Partien/h), `1,58x` ohne Streuung |
| **3:** Prozessbaum unter nativem Windows (`taskkill /T /F`) | **`UNKNOWN` / `NOT_RUN`** | Unter WSL2 Linux nicht testbar; vor Default-Aktivierung nativ unter Windows prüfen |
| **`#1652` Punkt 4:** Übrige P3-Reste (u. a. Doppelzählung `jvm_lives_lost` bei `jvm_exit` + späterem EOF-Timeout) | **`OFFEN`** | Nicht Teil von PR `#1704`; im Test `test_p3a_queued_jvm_exit_without_eof_is_kept_when_grace_expires` mit `jvm_lives_lost == 1` belegt |
| **`5` und `6` Sitze im Serien-Pool** | **`UNKNOWN` / nicht freigegeben** | Alle Läufe hier sind `4P`; `launch.MAX_RELEASED_SEATS = 4` bleibt unberührt |
