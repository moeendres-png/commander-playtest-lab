# `#1652` / `#1586`: Native Windows-Messung zu `taskkill /T /F` am `GamePool`-Worker (`SIMULATED_RESULT`)

- **Datum:** 2026-11-27 · **Refs:** `#1652`, `#1586`, `#1612`, `#1585`, `#1167`
- **Einordnung:** **`SIMULATED_RESULT`** (`LOCAL_OBSERVED` nativ unter Windows 11/Win32 über `S:\commander-playtest-lab`, Rohdaten außerhalb des Repos unter `<studio-data-dir>/logs_1652_win/result_1652_win_live_jvm.json`, **kein Qualifikationsbeleg**; `AGENTS.md` §4, §8).
- **Schalterstatus unverändert:** `COMMANDER_LAB_STUDIO_SERIES_POOL` bleibt per Default **`OFF`** (`UNKNOWN` auf `ENGINE_COMMAND_ENV`-Pfaden mit Leerzeichen — siehe Befund in Abschnitt 3).

---

## 1. Umgebung & Systemlast

- **Windows-Checkout:** `S:\commander-playtest-lab` (`HEAD` `54a83f777d1f8c141b597c8b1341d80ca1ba5b9d`, schreibgeschützt genutzt), **Paket:** `S:\commander-playtest-lab\src\commander_lab\__init__.py`, Python `3.12.10` (`.venv\Scripts\python.exe`, zwei Prozesse: `.venv`-Stub-Launcher → `Python312\python.exe`).
- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` · **Bridge-JAR (Windows `%LOCALAPPDATA%\CommanderStudio\engine`, isoliert nach `%TEMP%` kopiert):** SHA-256 `941b3df940667e74be00366026d9c1288979ce308045aafa0c34e18dee052aa9`, Zustand **`BRIDGE_AHEAD_OF_QUALIFICATION`**.
- **Java (Windows):** `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.8-hotspot\bin\java.EXE` (für die `gamesPerJvm=4`-Pool-Messung in Abschnitt 2 im Messskript ohne Code-Änderung als leerzeichenfreier 8.3-Kurzpfad `C:\PROGRA~1\ECLIPS~1\JDK-17~1.8-H\bin\java.exe` übergeben — Grund siehe Abschnitt 3).
- **Systemlast (Host-Messung vor/nach Lauf):** `load average: 0.10, 0.38, 0.72` → `0.18, 0.29, 0.62`, `Mem available: 13996 MiB` → `14055 MiB`, `Swap used: 127 MiB` → `159 MiB`.

---

## 2. Ergebnisse `GamePool` nativ unter Windows (`n/N`, `gamesPerJvm=4`, Tisch 2P Precon `2026_lorehold_spirit` vs. `2024_animated_army`)

Alle Prozesse (`wpid` `.venv`-Launcher, Kind `python.exe` sowie Enkel `java.exe` wegen `gamesPerJvm=4`) wurden per `Win32_Process`-Baumprüfung vor und nach jedem Eingriff einzeln verifiziert:

| Prüffall | Durchläufe (`n/N`) | Partien vor Abbruch `finished` | Lebende `java.exe` im Leerlauf verifiziert | Überlebende Prozesse nach Abbruch / Ende | Beobachtete Zeit bis Beendigung | Ergebnis |
|---|---:|---:|---:|---:|---:|---|
| **Fall A (`kill_process_tree` → `taskkill /T /F`)** | `5/5` | `5/5` | `5/5` (je `1` `java.exe`) | **`0/5`** (`wpid`, inneres `python.exe` und `java.exe` alle tot) | `656,0 – 813,0 ms` | **`PASS` (`LOCAL_OBSERVED`)** |
| **Fall B (P2-A: Beide Python-Worker zuerst hart beendet, dann `reap_ended_process`)** | `5/5` | `5/5` | `5/5` (je `1` `java.exe`) | **`0/5` verwaiste `java.exe`** nach 10-s-Fenster | **`313,0 – 328,0 ms`** (via `stdin`-EOF in `Main.java:79`) | **`PASS` (`LOCAL_OBSERVED`)** |
| **Normalbetrieb (`GamePool(workers=1)` + `close()`)** | `2/2` | `2/2` (`15,03 s`) | `1/1` (`jvm_life_id: w1-1`, Position `1 -> 2`) | **`0/1` verwaist** nach `pool.close()` | `< 500 ms` nach `close()` | **`PASS` (`LOCAL_OBSERVED`)** |

---

## 3. Blockierender Nebenbefund unter nativem Windows (`ENGINE_COMMAND_ENV` mit Leerzeichen) & Folgerung für `#1652` / `#1586`

- **Beobachteter Blocker (`1/1` direkt reproduziert vor 8.3-Umgehung):** Wird `GamePool(..., command=se.command)` (wie in Produktpfaden `paired_comparison.py` / `BatchSimulation`) unter Windows mit Standard-Java-Pfad `C:\Program Files\Eclipse Adoptium\...\java.EXE` aufgerufen, formatiert `launch.command_text` (`src/commander_lab/studio/launch.py:324`) per `subprocess.list2cmdline` doppelte Anführungszeichen um den Pfad mit Leerzeichen. Im `pool-worker` zerlegt `launch.engine_command` (`launch.py:185`) `ENGINE_COMMAND_ENV` mit `shlex.split(raw, posix=False)`, was die äußeren `"` **im Token** belässt (`'"C:\\Program Files\\...\\java.EXE"'`). Der Bridge-Start scheitert sofort mit **`ENGINE_FAILURE [BRIDGE_START_FAILED]`**.
- **Verwandte Code-Stellen (`CODE_DERIVED`):** Dasselbe `shlex.split(..., posix=False)` ohne Quote-Entfernung steht in `doctor.py:122` und `engine_check.py:132`; in `engine/rules/full_game.py:1289` steht zudem POSIX-`shlex.split(raw)` ohne `posix=False`. Mit `command=None` (`S:\`-Stand `studio play` / direkter `engine_command()`-Tupel ohne `ENGINE_COMMAND_ENV`) liefen Spiele (`d1` `711` Entscheidungen sowie `12/12` `command=None`-Testpartien mit implizitem `gamesPerJvm=1`), dort startet jedoch keine langlebige `gamesPerJvm > 1`-JVM.
- **Folge für `#1652` (Pool-Standard-AN):** Bedingung 3 (`taskkill /T /F` und `stdin`-EOF bei Worker-Tod unter nativem Windows) funktioniert technisch (`5/5` + `5/5`, `0` Waisen). **Dennoch bleibt `COMMANDER_LAB_STUDIO_SERIES_POOL` vorerst `OFF`**, weil der Serien-/Pool-Pfad unter nativem Windows beim regulären Aufruf mit `command=se.command` am `ENGINE_COMMAND_ENV`-Quoting (`BRIDGE_START_FAILED` bei Leerzeichen im Pfad) scheitert und dieser Fix erst auf `main` landen und gegen `S:\` nachgemessen werden muss.
- **Folge für `#1586` (Abnahme 2):** Abnahme 2 bleibt gemäß Lead-Entscheidung (Option 3) weiter an die Standard-Aktivierung des Serien-Pools in `#1652` gekoppelt; `#1586` bleibt daher offen, bis der Windows-`ENGINE_COMMAND_ENV`-Fix vorliegt und der Owner/Lead `COMMANDER_LAB_STUDIO_SERIES_POOL` freigibt.
- **Mess-Artefakt (außerhalb Repo unter `<studio-data-dir>/logs_1652_win/result_1652_win_live_jvm.json`):** SHA-256 **`ce40b29d13226a9df90ec360375a9e5346d01558c5912454833079d68fcc2bae`**.

---

## 4. Nachmessung nach `#1864`/`#1868` & Standard-Aktivierung (2026-11-27)

- **Stand:** Nach Merge von `#1864` (`b7c62922c`, PR `#1878`, Windows-Quoting) und `#1868` (`04c017dc6`, PR `#1879`, WinError 5/32 + `atomic.py`) unter nativem Windows (`S:\commander-playtest-lab\.venv\Scripts\python.exe`, Python `3.12.10`) mit **echtem Leerzeichen-Pfad ohne 8.3-Kurzpfad** (`C:\Program Files\Eclipse Adoptium\jdk-17.0.20.8-hotspot\bin\java.EXE`, Arbeits-/Datenordner mit Leerzeichen) nachgemessen (`SIMULATED_RESULT`).
- **Behobener Windows-IPC-Nebenbefund (`game_pool.py`):** Im Erstlauf ohne `PYTHONIOENCODING` crashte `_ProcessWorker._read_stdout` (`errors="strict"`) an einem cp1252-Umlaut (`0xfc`) aus `pool-worker` (`_emit(..., ensure_ascii=False)`). Behoben durch `ensure_ascii=True` in `_emit` und `_ProcessWorker.send`, `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` in `_ProcessWorker` sowie `stdout.reconfigure(errors="backslashreplace")`.
- **Ergebnisse auf dem Endstand (ohne `PYTHONIOENCODING` im Elternprozess):**
  - **UTF-8-IPC-Probe (`GameKeyMismatch` mit Umlaut):** **`1/1` `PASS`** (sauber dekodiert, kein `UnicodeDecodeError`).
  - **Normalbetrieb (`workers=1`, `gamesPerJvm=4`, `private_card_repository=False`, `pool.close()`):** **`2/2` `finished`** in `25,75 s` auf derselben JVM `w1-1` (`position_in_jvm: 1 -> 2`, `decision_count: 517` / `880`), `2/2` `.jsonl.gz`-Logs mit `status == "finished"` geschlossen, **`0/1`** überlebende `java.exe` nach `pool.close()`.
  - **`taskkill /T /F` mit `private_card_repository=True`:** **`1/1` `finished`**, anschließend `kill_process_tree(proc, windows=True)` (`wpid=3532`, `java.exe` `15820`) → **`0/1`** überlebende `java.exe` in `1015,0 ms`.
- **Folge:** Alle Bedingungen aus `#1652` und Abnahme 2 aus `#1586` sind erfüllt; `COMMANDER_LAB_STUDIO_SERIES_POOL` steht ab sofort per Default auf **`ON`** (`0`/`false`/`no`/`off` als explizites Opt-out).

- **Freigabe und Einschränkung (Nachtrag 2026-11-27, Review von PR #1888):** Die Freigabe zum Einschalten gab der Owner im Auftrag vom 2026-11-27 („PR #1888 … merge it once the AGENTS.md gates pass. This unblocks #1652“). Ohne gesetzten Schalter ist der Pool nur für Tische mit Wandzeit-Grenze der Standard (`table_spec.GAME_WALL_LIMIT_SECONDS`, heute 2–4 Sitze); 5- und 6-Sitz-Serien bleiben auf dem Chunk-Weg statt mit „keine Wandzeit-Grenze“ abgewiesen zu werden. Ein ausdrücklich gesetzter Schalter gewinnt weiterhin. Hinweis: `PYTHONUTF8=1` im Worker setzt dort auch die Standard-Dateikodierung für `open()` ohne `encoding` auf UTF-8 (Windows); die Pool-Pfade öffnen ihre Dateien mit expliziter Kodierung.
