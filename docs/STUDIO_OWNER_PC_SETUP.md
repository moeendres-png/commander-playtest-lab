# Commander Studio: was auf dem Owner-PC liegen muss und wie ich es prüfe

Stand: 2026-11-17, Refs #1167. Diese Seite sammelt nur, was im Repository steht. Jede Angabe
nennt ihre Quelle. **Nichts hier sagt, dass es auf dem Owner-PC läuft.** „zu prüfen am PC“
(ZPAP) heißt: aus dem Repository nicht belegbar oder nur am PC feststellbar. Ergebnisse von
dort sind `SIMULATED_RESULT` und kein Qualifikationsbeleg (`docs/STUDIO_PLAN_SIMULATOR.md`,
„What a result must always say“).

## 1. Voraussetzungen

| Was | Angabe | Quelle |
|---|---|---|
| Java | Version 17 oder neuer; Suche über `java` im PATH, sonst `JAVA_HOME\bin\java`. Eine nicht lesbare Version gilt nicht als „zu alt“, dann entscheidet der Engine-Prozess. | `src/commander_lab/studio/launch.py` (`MIN_JAVA_MAJOR`, `_java_executable`, `_java_too_old`); `scripts/studio_start.ps1`. Die Bridge ist mit `maven.compiler.release` 17 gebaut: `engine-bridge/pom.xml`. |
| Python | 3.12 oder neuer; der Starter nimmt `<Repo>\.venv\Scripts\python.exe`, sonst `python` im PATH. Welche Python-Pakete installiert sein müssen: ZPAP. | `docs/engine_setup.md` (Prerequisites); `scripts/studio_start.ps1` |
| Bridge-JAR | Datei `xmage-engine-bridge.jar` in `<Studio-Datenordner>\engine\`. Gebaut wird sie im Ordner `engine-bridge` (`mvn -B verify`); Ausgabe `engine-bridge\target\xmage-engine-bridge-0.1.0-SNAPSHOT.jar`. Maven 3.9.16 oder der Wrapper des Repos. | `launch.py` (`ENGINE_JAR`); `scripts/studio_start.ps1`, `scripts/studio_start.sh`; `docs/engine_setup.md` |
| Passende Engine-Version | Die JAR muss zum Engine-Pin aus `config/rules_engines.json` gehören; eine ältere Kopie führt dazu, dass der Spielstarter jede Partie wegen „commit mismatch“ ablehnt. | Kommentar in `scripts/studio_start.ps1`; `launch.engine_state` (Pin aus `canonical_xmage_engine_pin`) |
| Studio-Datenordner | Standard `%LOCALAPPDATA%\CommanderStudio`, gesetzt vom Starter über `COMMANDER_LAB_STUDIO_DATA`. Ohne diese Variable und ohne `COMMANDER_LAB_OWNER_DATA` bricht das Studio ab. Der Ordner muss außerhalb des Repositorys liegen. Partien liegen darin unter `games\`. | `scripts/studio_start.ps1`; `src/commander_lab/studio/store.py` (`studio_data_dir`); `games.py` (`GAMES_FOLDER`) |
| Plattenplatz für Quellbau | nur nötig, wenn die JAR selbst gebaut wird: Engine-Quellen, Maven-Abhängigkeiten, Build-Ausgabe. Wieviel: ZPAP. | `docs/engine_setup.md` |

Optionale Dateien neben der JAR (vom Provisionierungsskript geschrieben):
`xmage-engine-bridge.jar.sha256` und `ENGINE_PIN.txt` (`scripts/provision_engine_bridge.py`).
Fehlt `ENGINE_PIN.txt`, wird der Pin nicht verglichen (`launch.engine_state`).

Ein Workflow `package-engine-bridge.yml` existiert im Repository nicht (geprüft in
`.github/workflows/`). Ein fertig gebautes JAR kommt daher nicht aus diesem Workflow; wie der
Owner an ein JAR kommt, außer es selbst zu bauen: ZPAP / offen.

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
2. Repository auf den PC holen, Python-Umgebung `.venv` im Repo anlegen (Pakete: ZPAP).
3. Bridge-JAR beschaffen: im Ordner `engine-bridge` `mvn -B verify` ausführen, oder eine
   fertige JAR bereitstellen (`studio_start.ps1`, Hinweis bei fehlender Datei).
4. JAR bereitstellen, eine der zwei Möglichkeiten:
   - der Starter kopiert die gebaute JAR selbst nach `<Datenordner>\engine\`, sobald sie sich von
     der dortigen Kopie unterscheidet (`studio_start.ps1`);
   - oder per Skript (Aufruf aus dem Repo-Ordner, nötige Umgebung ZPAP, da das Skript
     `commander_lab` importiert):
     `python scripts/provision_engine_bridge.py --source <Pfad zur JAR>` kopiert, prüft die
     Prüfsumme und schreibt `.sha256` und `ENGINE_PIN.txt`; ohne `--source` meldet
     `--status` den Zustand als JSON und liefert Exit-Code 1, wenn die Engine nicht bereit ist
     (`scripts/provision_engine_bridge.py`).
5. Daten ins Studio importieren (Sammlung, Decks): `docs/STUDIO_DECKBUILDER.md`
   (Abschnitte zu `import-all`); nicht Teil dieser Seite.
6. Studio starten (Abschnitt 4), Seite „Partien“ öffnen.
7. Preflight lesen (Abschnitt 5), erst danach die Abnahmen (Abschnitte 6 und 7).

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
„Das Kartenwissen der KI kennt diese Karten noch nicht: ...“ (`launch.py`) und
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
gedeckt (`AGENTS.md` §10, Studio bridge gate). `UNKNOWN`: Git-Herkunft nicht prüfbar. Ob die Seite
diesen Zustand sichtbar anzeigt: ZPAP (die Obligation steht in `AGENTS.md` §10 noch offen, #1401).

`GET /api/engine/missing-cards` (optional `?revision_id=`) listet Karten, die der KI unbekannt oder
von XMage nicht unterstützt sind, für eine Deck-Revision oder die ganze Sammlung (`web.py`).

## 6. Abnahme M4: ein ganzes Spiel gegen drei KI-Plätze

Ziel laut Plan: Der Owner spielt eine vollständige Partie mit seinem Commander (Chulane) gegen drei
KI-Plätze auf dem eigenen Rechner (`docs/STUDIO_ROADMAP_20261112.md`, PLAY, „Done when“, #1169).
Dass das mit dem aktuellen Stand der Menschen-Sitz-Seite möglich ist, ist aus dem Repository nicht
belegt: ZPAP. Die Punkte unten prüfen zuerst die Simulation gegen drei KI-Plätze; für einen
menschlichen Platz gilt `docs/research/PLAY_HUMAN_SEAT_REQUIREMENTS.md`.

- [ ] **Preflight grün.** *Tun:* Studio starten, „Neue Partie“ öffnen. *Sichtbar:* kein Hinweis „Die
  Regel-Engine ... noch nicht eingerichtet“; im Deck-Tab „Mit der Engine prüfen“ für die Chulane-
  Revision zeigt `PASS`. *Melden bei Abweichung:* Screenshot der Meldung inkl. Grund; Ausgabe von
  `python scripts/provision_engine_bridge.py --status`; `java -version`.
- [ ] **Partie starten.** *Tun:* Chulane-Revision, drei Gegner-Decks (Voreinstellungen „precon“,
  „mixed“, „optimized“ stehen in `launch.POD_PRESETS`), Seed wählen, starten. *Sichtbar:* die Partie
  öffnet sich innerhalb von 20 Sekunden, das Log wächst. *Melden:* Screenshot der Fehlermeldung;
  `<Datenordner>\games\<game_id>.out`.
- [ ] **Partie läuft bis zum Ende.** *Sichtbar:* ein Ergebnis (Sieger oder Abbruchgrund) im Log und
  auf der Seite, vier Sitze. Gewünscht laut Roadmap und Owner-Entscheid 2026-11-17: ohne Zeitlimit-Abbruch; Dauer notieren
  (Soll-Dauer: ZPAP). *Melden:* Screenshot der Endansicht, Pfad `games\<game_id>.jsonl.gz`, Seed,
  Wanduhr-Dauer.
- [ ] **Kein Platz bleibt hängen.** *Sichtbar:* jeder KI-Platz entscheidet weiter, kein Stillstand.
  *Melden:* Zeitpunkt und Entscheidungsnummer des Stillstands, Screenshot, Log-Pfad.
- [ ] **Herkunft festhalten.** *Sichtbar/zu notieren:* Bridge-JAR-SHA-256 (`xmage-engine-bridge.jar.sha256`
  oder `bridge_jar_sha256` im Zustand), Engine-Pin, `bridge_qualification`-Status. *Melden:* alle drei
  Werte im Befund. Ergebnis nur als `SIMULATED_RESULT` bezeichnen.

## 7. Abnahme Serie: 36-Seed-Referenzserie, Laufzeit notieren

Im Repository heißt die Referenz R1: das echte Vier-Spieler-Pod von
`scripts/run_real_4p_full_game_smoke.py`, Seeds 1 bis 36 (`docs/STUDIO_PLAN_SIMULATOR.md`,
„Reference set“; `docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`). Dort gemessen
(andere Maschine, 4 Kerne, 16 GB, JDK 21): 408 s mit 4 Arbeitern und 9 Spielen je JVM, 36/36
identisch. Das ist ein Vergleichswert, kein Sollwert für den Owner-PC. Ob die „36-Seed-Referenzserie“
des Owners R1 oder eine Studio-Serie (`POST /api/simulations/batch`, `base_seed`, `games_count`,
`workers`, `games_per_jvm`) ist: ZPAP / mit dem Owner klären. Beide Wege:

- [ ] **Weg A, R1 über das Benchmark-Skript.** *Tun:* im Repo
  `python scripts/benchmark_xmage_full_games.py run --jar <JAR> --out serie36.json --seeds 1-36 --workers 4 --games-per-jvm 9 --fast`
  (Befehl aus `docs/STUDIO_PLAN_SIMULATOR.md`; ob `--workers 4` zum PC passt: ZPAP). *Sichtbar:* 36
  Spiele fertig, keine fehlgeschlagen oder fehlend; Gesamtlaufzeit (Wanduhr) und die Kennung der JAR.
  *Melden:* `serie36.json`, Gesamtlaufzeit, Zahl fertig/fehlgeschlagen, JAR-SHA-256, Maschine (Kerne,
  RAM, Java-Version).
- [ ] **Weg B, Studio-Serie.** *Tun:* Seite „Simulieren“, Chulane-Revision, Pod, `games_count` 36,
  Basis-Seed 1, Schrittweite 1, Arbeiter und Spiele je JVM notieren (Standard: Arbeiter
  `min(4, Kerne-1)`, 6 Spiele je JVM; `launch.default_workers`, `DEFAULT_GAMES_PER_JVM`). *Sichtbar:*
  Fortschritt „x von n“, am Ende Status und Ergebnis `SIMULATED_RESULT`. *Melden:* Serien-Datei
  `games\<batch_id>.series.json`, Start- und Endzeit (`started_at` im Serienzustand), Screenshot der
  Serienansicht, Zahl abgeschlossen/fehlgeschlagen.
- [ ] **Laufzeit notieren.** In jedem Fall: Gesamtlaufzeit, Arbeiter, Spiele je JVM, Kerne/RAM, Java-
  Version, Bridge-JAR-SHA-256, `bridge_qualification`-Status. Während der Serie keine anderen
  schweren Programme laufen lassen (die Messungen im Performance-Dokument setzen das voraus).
- [ ] **Ergebnis richtig einordnen.** Laufzeit und Ausfälle sind Messwerte, keine Qualifikation
  (`scripts/benchmark_xmage_full_games.py`: „Local timings are measurements, not qualification
  evidence“). Ein Vergleich zweier JARs per `compare` gehört zum Bridge-Gate, nicht zu dieser Abnahme.

## 8. Zu prüfen am PC (Sammelliste)

1. Installierte Java-Version und ob sie im PATH liegt.
2. Welche Python-Pakete die `.venv` braucht und ob `python scripts/provision_engine_bridge.py`
   ohne weitere Umgebung läuft (es importiert `commander_lab`).
3. Wie der Owner an die Bridge-JAR kommt (selbst bauen mit Maven vs. fertig bereitgestellt);
   es gibt keinen `package-engine-bridge`-Workflow.
4. Ob JAR und Pin zusammenpassen (`ENGINE_PIN.txt`, Starter-Meldungen).
5. RAM für `-Xmx3g` je JVM bei mehreren Arbeitern; Plattenplatz für Quellbau.
6. Ob die Seite `BRIDGE_AHEAD_OF_QUALIFICATION` sichtbar anzeigt (#1401 offen).
7. Ob ein menschlicher Platz in „Neue Partie“ bereits spielbar ist (M4-Wortlaut „spielt selbst“).
8. Was mit „36-Seed-Referenzserie“ gemeint ist (R1-Benchmark oder Studio-Serie) und welche Laufzeit
   als akzeptabel gilt; der Repo-Messwert 408 s stammt von anderer Hardware.
9. Dass Partie und Serie überhaupt vollständig laufen: dazu gibt es hier keine Aussage.
