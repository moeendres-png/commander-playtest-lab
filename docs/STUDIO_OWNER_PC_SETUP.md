# Commander Studio: was auf dem Owner-PC liegen muss und wie ich es prüfe

Stand: 2026-11-18, Refs #1519, #1167. Diese Seite sammelt nur, was im Repository steht. Jede
Angabe nennt ihre Quelle. **Nichts hier sagt, dass es auf dem Owner-PC läuft.** „zu prüfen am PC“
(ZPAP) heißt: aus dem Repository nicht belegbar oder nur am PC feststellbar. Ergebnisse von
dort sind `SIMULATED_RESULT` und kein Qualifikationsbeleg (`docs/STUDIO_SCOPE.md`,
`docs/STUDIO_PLAN_SIMULATOR.md`, „What a result must always say“).

Die ausfüllbare Vorlage für die Abnahme am Owner-PC liegt in
`docs/STUDIO_ABNAHME_PROTOKOLL.md`.

## 1. Voraussetzungen

| Was | Angabe | Quelle |
|---|---|---|
| Java | Version 17 oder neuer; Suche über `java` im PATH, sonst `JAVA_HOME\bin\java`. Eine nicht lesbare Version gilt nicht als „zu alt“, dann entscheidet der Engine-Prozess. | `src/commander_lab/studio/launch.py` (`MIN_JAVA_MAJOR`, `_java_executable`, `_java_too_old`); `scripts/studio_start.ps1`. Die Bridge ist mit `maven.compiler.release` 17 gebaut: `engine-bridge/pom.xml`. |
| Python | 3.12 oder neuer; der Starter nimmt `<Repo>\.venv\Scripts\python.exe`, sonst `python` im PATH. Kern- und Studio-Pakete für den Start: `pydantic`, `openpyxl`, `PyYAML`, `typer`, `fastapi`, `uvicorn` (geprüft durch `doctor`). Ob sie am PC installiert sind: ZPAP. | `docs/engine_setup.md` (Prerequisites); `scripts/studio_start.ps1`; `src/commander_lab/studio/doctor.py` (`_REQUIRED_IMPORTS`, `_check_python`) |
| Bridge-JAR | Datei `xmage-engine-bridge.jar` in `<Studio-Datenordner>\engine\`. Entweder aus dem Release-Artefakt (siehe unten) oder selbst gebaut im Ordner `engine-bridge` (`mvn -B verify`, Ausgabe `engine-bridge\target\xmage-engine-bridge-0.1.0-SNAPSHOT.jar`, Maven 3.9.16 oder Wrapper). | `launch.py` (`ENGINE_JAR`); `scripts/studio_start.ps1`, `scripts/studio_start.sh`; `docs/engine_setup.md`; `.github/workflows/release-artifacts.yml` |
| Passende Engine-Version | Die JAR muss zum Engine-Pin aus `config/rules_engines.json` gehören; eine ältere Kopie führt dazu, dass der Spielstarter jede Partie wegen „commit mismatch“ ablehnt. | Kommentar in `scripts/studio_start.ps1`; `launch.engine_state` (Pin aus `canonical_xmage_engine_pin`) |
| Studio-Datenordner | Standard `%LOCALAPPDATA%\CommanderStudio`, gesetzt vom Starter über `COMMANDER_LAB_STUDIO_DATA`. Ohne diese Variable und ohne `COMMANDER_LAB_OWNER_DATA` bricht das Studio ab. Der Ordner muss außerhalb des Repositorys liegen. Partien liegen darin unter `games\`. | `scripts/studio_start.ps1`; `src/commander_lab/studio/store.py` (`studio_data_dir`); `games.py` (`GAMES_FOLDER`) |
| Plattenplatz für Quellbau | nur nötig, wenn die JAR selbst gebaut wird: Engine-Quellen, Maven-Abhängigkeiten, Build-Ausgabe. Wieviel: ZPAP. | `docs/engine_setup.md` |

Optionale Dateien neben der JAR (vom Provisionierungsskript oder aus dem Release-Artefakt):
`xmage-engine-bridge.jar.sha256` und `ENGINE_PIN.txt` (`scripts/provision_engine_bridge.py`,
`.github/workflows/release-artifacts.yml`). Fehlt `ENGINE_PIN.txt`, wird der Pin in
`launch.engine_state` nicht verglichen (`doctor` meldet dann `UNKNOWN` bzw. fehlende Pin-Datei).

**Fertige Bridge-JAR aus GitHub Actions:** Der Workflow `.github/workflows/release-artifacts.yml`
läuft bei jedem Push auf `main` und `release/**` sowie manuell (`workflow_dispatch`) und lädt
das Artefakt `commander-playtest-lab-release-<version>-<sha>` hoch (`retention-days: 30`, also
nach 30 Tagen verfallen). Darin liegen `xmage-engine-bridge.jar`, `ENGINE_PIN.txt`,
`xmage-engine-bridge.jar.sha256` und `PLAYTEST_LAB_SHA256SUMS.txt`. Ob der Download und die
Prüfung am Owner-PC klappen: ZPAP.

## 2. Umgebungsvariablen

| Variable | Wirkung | Quelle |
|---|---|---|
| `COMMANDER_LAB_STUDIO_DATA` | Studio-Datenordner (Store, `engine\`, `games\`). Der Starter setzt sie, wenn sie fehlt. | `studio_start.ps1`, `store.py` |
| `COMMANDER_LAB_OWNER_DATA` | Ersatz: Datenordner ist dann `<Owner-Ordner>\studio`. | `store.py` |
| `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD` | Wenn gesetzt, ersetzt dieser Startbefehl die JAR im Datenordner. Der Preflight prüft dann nur, dass das Startprogramm und eine hinter `-jar` genannte Datei vorhanden sind, **nicht** die Java-Version. | `launch.py` (`ENGINE_COMMAND_ENV`, `engine_command`); `engine_check.engine_readiness` |
| `PYTHONPATH` | Der Starter setzt ihn auf `<Repo>\src`. | `studio_start.ps1` |
| `JAVA_HOME` | Nur Rückfall, wenn `java` nicht im PATH liegt. | `launch._java_executable` |

Ohne die Engine-Variable startet das Studio die Engine als
`java -Xmx3g -jar <Datenordner>\engine\xmage-engine-bridge.jar full-game` (`launch.engine_command`).
Der Heap von 3 GB ist im Code festgelegt; ob der Owner-PC das trägt (RAM): ZPAP.

## 3. Reihenfolge der Schritte

Alle Schritte sind aus den Skripten abgeleitet; keiner wurde auf dem Owner-PC ausgeführt.

1. Java 17+ installieren; in einer neuen PowerShell `java -version` prüfen (ZPAP).
2. Repository auf den PC holen, Python-Umgebung `.venv` (Python 3.12+) im Repo anlegen
   (`requirements/lock.txt` oder `pip install -e ".[api]"`; Pakete am PC: ZPAP).
3. Bridge-JAR beschaffen: entweder aus dem aktuellen GitHub-Actions-Artefakt von
   `.github/workflows/release-artifacts.yml` (`commander-playtest-lab-release-<version>-<sha>`,
   30 Tage gültig) entpacken oder im Ordner `engine-bridge` mit `mvn -B verify` selbst bauen.
4. JAR bereitstellen, eine der zwei Möglichkeiten:
   - der Starter kopiert eine im Repo gebaute JAR selbst nach `<Datenordner>\engine\`, sobald
     sie sich von der dortigen Kopie unterscheidet (`studio_start.ps1`);
   - oder per Skript (Aufruf aus dem Repo-Ordner, mit gesetztem `PYTHONPATH=src` bzw. aktivierter
     `.venv`, da das Skript `commander_lab` importiert):
     `python scripts/provision_engine_bridge.py --source <Pfad zur JAR>` kopiert, prüft die
     Prüfsumme und schreibt `.sha256` und `ENGINE_PIN.txt`; ohne `--source` meldet
     `--status` den Zustand als JSON und liefert Exit-Code 1, wenn die Engine nicht bereit ist
     (`scripts/provision_engine_bridge.py`).
5. Systemprüfung ausführen:
   `python -m commander_lab.studio doctor` (oder `--json` für das Abnahme-Protokoll).
   Prüft Python >= 3.12, Pflichtpakete, Java 17+, Bridge-JAR, Pin-Abgleich, Kartenkatalog und
   Datenordner (`src/commander_lab/studio/doctor.py`, `__main__.py`).
6. Optional für Serien (schnellerer JVM-Start):
   `python -m commander_lab.studio build-appcds` baut `<jar>.jsa` neben der Bridge-JAR
   (`src/commander_lab/studio/__main__.py`, `launch.build_appcds_archive`).
7. Daten ins Studio importieren (Sammlung, Decks): `docs/STUDIO_DECKBUILDER.md`
   (Abschnitte zu `import-all`); nicht Teil dieser Seite.
8. Studio starten (Abschnitt 4), Seite „Partien“ öffnen.
9. Preflight lesen (Abschnitt 5), danach die Abnahme nach `docs/STUDIO_ABNAHME_PROTOKOLL.md`
   durchführen und protokollieren.

## 4. Startbefehl

```powershell
.\scripts\studio_start.ps1
```

Der Starter prüft Java und JAR, gibt Warnungen aus, bricht aber bei fehlendem Java oder fehlender
JAR **nicht** ab, und startet `python -m commander_lab.studio serve --open`
(`scripts/studio_start.ps1`). Der Server hört nur auf `127.0.0.1`, Port 8765 ist der Standard
(`studio/__main__.py` `--port`; `docs/STUDIO_DECKBUILDER.md`, Abschnitt „Start“). Unter
Linux/WSL: `scripts/studio_start.sh`.

Warnungen des Starters (Wortlaut aus dem Skript, ohne Umlaute geschrieben):

- „Java wurde nicht gefunden. ... Java 17 oder neuer wird benoetigt“: kein `java` im PATH und
  kein `JAVA_HOME`.
- „Gefundenes Java hat Version N“: N kleiner 17.
- „Die Engine-Datei fehlt noch: <Pfad>“: weder JAR im Datenordner noch gebaute JAR im Repo.

## 5. Was der Preflight im Studio prüft

Es gibt zwei Stellen, beide ohne eine Partie zu starten.

**a) „Neue Partie“** (Seite `partie.html`, `static/partie.js`): `GET`-Daten des Tisches enthalten
`engine = launch.engine_state(...)`. Ist `ready` falsch, zeigt die Seite „Die Regel-Engine ist
auf diesem Rechner noch nicht eingerichtet.“ plus den Grund. Gründe (`launch.engine_state`):

| Meldung | Bedeutung |
|---|---|
| „Die Engine-Datei fehlt: <Pfad>“ | Keine JAR unter `<Datenordner>\engine\xmage-engine-bridge.jar` und keine Engine-Variable. |
| „Java ist zu alt: gefunden wurde Version N, nötig ist Java 17 oder neuer.“ | Java gefunden, Hauptversion unter 17. |
| „Java ist nicht installiert (Java 17 oder neuer).“ | JAR vorhanden, aber weder `java` im PATH noch `JAVA_HOME`. |
| Warnung „Die installierte Engine-Datei stammt von Pin X, erwartet wird jedoch Y aus config/rules_engines.json.“ | `ENGINE_PIN.txt` neben der JAR weicht vom Pin ab. Das ist nur eine Warnung im Zustand, `ready` bleibt davon unberührt. |

Beim Start einer Partie (`prepare_table_deck_paths`) kommen weitere Ablehnungen:
„Die Regeln-Engine XMage unterstützt diese Karten noch nicht: ...“,
„Das Kartenwissen der KI kennt diese Karten noch nicht: ...“ (`launch.py`),
die Sitz-Sperre (`MAX_RELEASED_SEATS = 4`: 2 bis 4 Sitze aktiv, 5 und 6 technisch gesperrt,
`launch.py`, PR #1515) und
„Die Partie konnte nicht gestartet werden: <letzte 5 Zeilen von games\<id>.out>“, wenn innerhalb von
20 Sekunden kein Spiellog entsteht. Daher ist `games\<id>.out` die erste Log-Datei, die ein
Befund beilegen soll.

**b) „Mit der Engine prüfen“** im Deck-Tab (`POST /api/engine-check`, `studio/engine_check.py`).
Drei Ausgänge, nie mehr: `FAIL`, `PASS`, `UNKNOWN`.

| Überschrift | Bedeutung |
|---|---|
| „Die Engine würde dieses Deck nicht annehmen“ (`FAIL`) | Prüfsumme, Einzelkarten-Regel oder Farbidentität verletzt, oder Karten, die die Engine nicht laden kann / die der KI unbekannt sind. |
| „nicht geprüft: Voraussetzung nicht erfüllt“ | Deck hat nicht 100 Karten oder keinen/mehr als zwei Commander. |
| „nicht geprüft: Deck-Aufbau nicht prüfbar“ | Die Konstruktionsprüfung des Spielstarters konnte nicht laufen. |
| „nicht geprüft: Engine nicht bereitgestellt“ | Engine nicht bereit; Grund in `engine_reason`: Startprogramm/Engine-Datei nicht vorhanden, „Java ist nicht installiert“, „Die Java-Version ist nicht lesbar.“, „Java ist zu alt“. |
| „nicht geprüft: Kartenliste der Engine nicht lesbar“ | Die Kartenliste der Engine wurde nicht befragt. |
| „Die Prüfung der Engine findet nichts“ (`PASS`) | Alle drei Teile liefen und fanden nichts. Der XMage-Deck-Import selbst läuft erst beim Spielstart; `PASS` ist keine Zusage, dass die Partie läuft. |

Zusätzlich liefert die Antwort `bridge_qualification` (`src/commander_lab/bridge_qualification.py`):
`ALIGNED_WITH_SEALED_EPOCH`, `BRIDGE_AHEAD_OF_QUALIFICATION` oder `UNKNOWN`. `BRIDGE_AHEAD...`
heißt: `engine-bridge/` weicht von der versiegelten Quelle ab (auch durch uncommittete Änderungen)
oder der Pin ist weitergezogen; Ergebnisse gelten dann nicht als von der versiegelten Epoche
gedeckt (`AGENTS.md` §10, Studio bridge gate). `UNKNOWN`: Git-Herkunft nicht prüfbar. Die
Oberfläche zeigt `BRIDGE_AHEAD_OF_QUALIFICATION` sichtbar in der Partie-, Serien- und
Verlaufsansicht an (`static/partie.js`, `static/app.js`, `static/paired.js`, `static/ui.js`;
#1401 erledigt mit PR #1411). Ob die Darstellung am Owner-PC lesbar und vollständig ist: ZPAP.

`GET /api/engine/missing-cards` (optional `?revision_id=`) listet Karten, die der KI unbekannt oder
von XMage nicht unterstützt sind, für eine Deck-Revision oder die ganze Sammlung (`web.py`).

## 6. Abnahme PLAY (AK-1 bis AK-8): Chulane gegen drei KI-Sitze

Verbindliche Abnahme-Definition ist AK-1 bis AK-8 (`docs/OWNER_DECISIONS_STUDIO_20261118.md`, E4;
`docs/STUDIO_SCOPE.md`, PLAY P0). Auf `main` ist PLAY P0 gemergt (PR #1515): Brett-Klick für
Ziel, Angreifer, Blocker, Karte aus der Hand und Fähigkeit eines Permanents (`static/boardclick.js`,
Listen bleiben als Ausweichweg), Sitz-Sperre 2–4 im Startpfad (`launch.MAX_RELEASED_SEATS = 4`),
kein Timeout für den Mensch-Sitz (`decision_timeout_seconds = 0`, `studio/play.py`), KI-Hände live
verborgen und nach Spielende aufgedeckt (`docs/STUDIO_GAME_VIEWER.md`), Vorspulen ausschließlich
über die Pass-Option auf Prioritätsabfragen (`static/vorspulen.js`).

Dass dies am Owner-PC vollständig und ohne Hänger durchläuft, ist nicht vom PC belegt: ZPAP.
Die konkreten Prüfpunkte und Felder stehen in `docs/STUDIO_ABNAHME_PROTOKOLL.md` (Blöcke B und C):

- **Preflight grün:** Studio starten, „Neue Partie“ öffnen (kein Hinweis „Die Regel-Engine ... noch
  nicht eingerichtet“); im Deck-Tab „Mit der Engine prüfen“ für die Chulane-Revision zeigt `PASS`.
- **Drei vollständige Vierer-Partien (AK-1 bis AK-8):** Chulane gegen drei KI-Sitze (Voreinstellungen
  `precon`, `mixed`, `optimized` aus `launch.POD_PRESETS`), ohne Zeitlimit-Abbruch, bis zum von der
  Engine gemeldeten Spielende. Alle Werte, Herkunftspfade (`games\<game_id>.jsonl.gz`,
  `games\<game_id>.out`) und das Urteil je AK-Zeile werden in `docs/STUDIO_ABNAHME_PROTOKOLL.md`
  eingetragen; nicht vorgekommene Entscheidungsklassen (AK-3) bleiben `UNKNOWN`.

## 7. Abnahme Serie: 36-Seed-Referenzserie und gepaarte Serien

Im Repository heißt die Referenz R1: das echte Vier-Spieler-Pod von
`scripts/run_real_4p_full_game_smoke.py`, Seeds 1 bis 36 (`docs/STUDIO_PLAN_SIMULATOR.md`,
„Reference set“; `docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`). Dort gemessen
(andere Maschine, 4 Kerne, 16 GB, JDK 21): 408 s mit 4 Arbeitern und 9 Spielen je JVM, 36/36
identisch. Das ist ein Vergleichswert, kein Sollwert für den Owner-PC. Ob die „36-Seed-Referenzserie“
des Owners R1 oder eine Studio-Serie (`POST /api/simulations/batch`, `base_seed`, `games_count`,
`workers`, `games_per_jvm`) ist: ZPAP / mit dem Owner klären. Beide Wege:

- **Weg A, R1 über das Benchmark-Skript:** im Repo
  `python scripts/benchmark_xmage_full_games.py run --jar <JAR> --out serie36.json --seeds 1-36 --workers 4 --games-per-jvm 9 --fast`
  (Befehl aus `docs/STUDIO_PLAN_SIMULATOR.md`; ob `--workers 4` zum PC passt: ZPAP).
  Prüfen: 36 Spiele fertig, keine fehlgeschlagen oder fehlend; Gesamtlaufzeit (Wanduhr) und
  JAR-SHA-256 notieren.
- **Weg B, Studio-Serie:** Seite „Simulieren“, Chulane-Revision, Pod, `games_count` 36, Basis-Seed 1,
  Schrittweite 1, Arbeiter und Spiele je JVM notieren (Standard: Arbeiter `min(4, Kerne-1)`, 6
  Spiele je JVM; `launch.default_workers`, `DEFAULT_GAMES_PER_JVM`). Fortschritt „x von n“, am Ende
  Status und Ergebnis `SIMULATED_RESULT` (`games\<batch_id>.series.json`).
- **Gepaarte Serien (SIMULATE A1, PR #1516):** `python -m commander_lab.studio compare-decks` bzw.
  die gepaarte Serien-Ansicht in der Oberfläche nutzen Slot-Ausrichtung, MDE-Planung und Seed-Plan.
  Die 5/6-Sitz-Sperre in den Serien-Routen und `compare-decks` ist als eigenes Paket (#1520) noch
  offen. Identitätsnachweis und Pilotblock am Owner-PC folgen mit Paket #1521 (Platzhalter in
  `docs/STUDIO_ABNAHME_PROTOKOLL.md`, Blöcke D und E).
- **Einordnung:** Laufzeit und Ausfälle sind Messwerte, keine Qualifikation
  (`scripts/benchmark_xmage_full_games.py`: „Local timings are measurements, not qualification
  evidence“). Alle Ergebnisse sind `SIMULATED_RESULT`.

## 8. Zu prüfen am PC (Sammelliste)

1. Installierte Java-Version (`java -version`) und ob sie im PATH liegt.
2. Python 3.12+ und installierte Pakete in `.venv` (`python -m commander_lab.studio doctor --json`)
   sowie ob `python scripts/provision_engine_bridge.py --status` läuft.
3. Bezug der Bridge-JAR aus dem Artefakt von `.github/workflows/release-artifacts.yml` (oder
   Eigenbau per Maven) sowie Pin-Abgleich (`ENGINE_PIN.txt`).
4. RAM für `-Xmx3g` je JVM bei mehreren Arbeitern; Plattenplatz für Quellbau; AppCDS-Erstellung
   (`python -m commander_lab.studio build-appcds`).
5. Sichtbare Anzeige von `BRIDGE_AHEAD_OF_QUALIFICATION` in der Oberfläche (PR #1411 umgesetzt, am
   Owner-PC optisch zu prüfen).
6. Drei vollständige Vierer-Partien mit Mensch auf Sitz 1 nach AK-1 bis AK-8 inkl. Störfällen
   (`docs/STUDIO_ABNAHME_PROTOKOLL.md`, Blöcke B und C).
7. Was mit „36-Seed-Referenzserie“ gemeint ist (R1-Benchmark oder Studio-Serie) und welche Laufzeit
   am Owner-PC akzeptabel gilt; der Repo-Messwert 408 s stammt von anderer Hardware.
8. Identitätsnachweis, Pilotblock und Kreislauf Deck-Stand → Partie → Serie → Verlauf
   (`docs/STUDIO_ABNAHME_PROTOKOLL.md`, Blöcke D–F, nach #1521 / #1531).
