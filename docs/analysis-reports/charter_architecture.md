# Charta-Lane ARCHITEKTUR und DATENMODELL (quer über BUILDER, SIMULATE, PLAY)

Stand: `main` @ `8f46af28` (2026-11-19, nach #1627, #1611, #1634, #1640), PR #1638 offen
(Head-Zweig `feat/paired-long-lived-jvm-1585`). Nur gelesen und statisch gemessen: keine Suite, kein
Engine-Lauf, kein Maven, nichts gepusht oder kommentiert. Legende: **[M]** in dieser Lane gemessen
(Skript `…/scratchpad/charter/arch_tools/reach.py`, `grep`, `gh api`, Nur-Lese-Abfrage der
Sandbox-Store-Kopie `…/scratchpad/play_store/studio.sqlite3`), **[C]** aus dem Code (Datei:Zeile),
**[D]** Bericht, Issue oder PR sagt es, **[V]** Vermutung. Die Sandbox-Kopie ist nicht der Store des
Owner-PCs; dessen Inhalt ist UNKNOWN.

## 0. Ergebnis zuerst

1. **Kein Neubau, aber ein neues Datenmodell an vier Stellen (Schema 22).** Option D bleibt richtig
   für den Code. Das Datenmodell trägt den Kreislauf des Owners heute nicht: Decks können nur Karten
   der Sammlung enthalten (`decks.py:85-88`), Serienergebnisse liegen in zwei unverbundenen Ablagen
   (`simulation_run` je Deck ohne Stand, `store.py:334`; gepaarte Serien als Dateien, die
   `deck_series.py:24` mit `SCAN_LIMIT = 2000` durchsucht), Tisch und Piloten sind kein Objekt, und
   einen Pilot-Fingerabdruck gibt es nicht (`launch.py:408` ist eine Konstante).
2. **Trennung nach Lebenszyklus in zwei Dateien.** `reference.sqlite3` (27 Import-Tabellen, heute
   99,9 % der 254 MB [M]) wird **neu gebaut statt migriert** und vom Server nur gelesen;
   `studio.sqlite3` hält nur Nutzerzustand (13 Tabellen, in der Sandbox 172 Zeilen [M]) und wird
   sorgfältig migriert. Experimente und Partien bleiben Dateien (Manifest, Journal, Log) mit einem
   neu aufbaubaren Index im Nutzer-Store.
3. **Der Nutzerzustand bekommt ein Export-Format** (`studio export-state`, wenige kB bis MB). Es ist
   Sicherung, Migrationsweg und Prüfmittel in einem: Der Owner schickt die Datei, die Migration wird
   in der Agenten-Umgebung am echten Zustand bewiesen, der PC migriert danach automatisch mit
   Sicherung. „Schema 22 nur in einer Owner-Sitzung“ wird damit zu 15 Minuten ohne Risiko.
4. **Karten-Identität ist die Oracle-ID, Besitz ist eine Auflage.** Das ist Voraussetzung für „Deck,
   das ich reinstelle“, für Gegner-Decks als normale Decks und für den am 2026-11-19 beschlossenen
   Zukauf-Modus bei TAM (#1187). In der Sandbox ist die Abbildung `card_id` → `oracle_id` verlustfrei
   (1.655 von 1.655, 0 leer, 0 ohne Scryfall-Treffer [M]).
5. **Ein Protokolltreiber, zwei Wirte, eine Prozessaufsicht.** D-3 wird neu geschnitten: Die Sitzung
   aus PR #1638 (`engine/rules/full_game_series.py`) wird die eine öffentliche Schnittstelle; Runner,
   Pool-Worker und `play.py` benutzen sie. PLAY läuft **nicht** über einen Pool-Worker, teilt aber
   Prozess-Register, Lastbudget und Aufräumen mit dem Pool.
6. **D-1 läuft weiter bis P3, P4 bleibt, P5 wird ersetzt.** Nach dem Dateischnitt ist „liest nur
   Importdaten“ eine Eigenschaft der Datei statt einer Deklaration; die Beweise für fremde Schreiber
   (I2, I3 im Entwurf) entfallen für die Gruppe IMPORT.
7. **Web-Schicht:** Router je Bereich, eine Store-Abhängigkeit, ein Fehlervertrag mit Fachausnahmen,
   Antwort-Typen nur für die rund 25 Routen des Kreislaufs. Kein SSE: Das Halten der Zustandsanfrage
   aus #1634 (`play.py:77-78`) wird auch für Serien-Fortschritt benutzt.
8. **Frontend bleibt JS ohne Build.** Eine eigene Seite „Simulation“ (heute in `app.js` versteckt),
   ein gemeinsamer Rahmen mit Auftragsleiste, reine Logik in `node`-getesteten Dateien nach dem
   Muster `boardclick.js`. Ziel: von heute 8 Testfunktionen, die JS ausführen [D], auf mindestens 60 Fälle
   im Kreislauf.
9. **Wenig kann sofort weg.** Die 9.824 Zeilen Java älterer Lanes und rund 3.000 Zeilen Python
   (`tactical`, `bridge`, `phase85`) sind nicht tot: PB-03 startet `midgame`, 205 bis 300 Dateien
   unter `qualification/` nennen die Pfade [M]. Löschbar sind sie nur mit einer neuen Epoche (Owner).
   Sofort weg: `simulation_run`/`simulation_card`, `tier_snapshot`, `memo.py`, die alten
   Orchestrierer nach D-2 P5, `subarchetypes.py`.
10. **Kosten:** über die laufenden D-Pakete hinaus 28 bis 41 Lane-Tage (±40 %), in drei Läufen; mit
    drei Lanes rund zwei bis drei Wochen Wanduhr [V]. Greenfield lag bei 55 bis 90 [D].
11. **Governance:** MATERIAL teilen (Inhalt gegen bloße Größe), ein „Studio-Daten-Gate“ für
    Schema-Änderungen, die Verschiebe-Sperre für Kollisionsdateien während eines geclaimten
    Konsolidierungspakets aussetzen, die Pflichtlektüre von 1.499 Zeilen [M] auf eine Charta kürzen.

## 1. Der Kreislauf und was jeder Schritt vom Datenmodell braucht

| Schritt | Braucht | Heute | Lücke |
|---|---|---|---|
| Deck bearbeiten | Deck, unveränderlicher Stand mit Inhalts-Hash, Entwurf, Kartenfakten, Besitz | `deck`, `deck_revision`, `deck_draft` (`store.py:90-116`, `:208`); Hash über `card_id` (`decks.py:46-50`) | nur Sammlungskarten; Herkunft eines Imports ist nur `source_id` |
| Tisch einstellen | Sitze, je Sitz Deck-Stand und Pilot (KI mit Stil oder Mensch), Engine-Schalter | Parameter im Anfrage-Körper (`web.py`, `BatchSimulationBody`, `PairedSeriesBody`); Gegner als JSON im Repository (`launch.py:59-60`, `:261-264`) | kein gespeichertes Objekt, kein Hash, Gegner sind keine Decks |
| Simulieren | Experiment mit Plan vor dem ersten Spiel, Partien, Abbruch, Wiederaufnahme | drei Verwalter, drei Ablagen [D: `d2_pool_design.md` 5.1]; Pool hinter Schalter in #1638 | ein Objekt „Experiment“ fehlt |
| Ergebnisse speichern | je Partie ein endgültiges Ergebnis mit Herkunft; Auswertung je Deck-Stand | Batch in `simulation_run` je `deck_id` ohne Stand (`store.py:334-351`); gepaart als `*.paired.json` | zwei Wahrheiten; `int(… or 0)` beim Speichern (`simulations.py:683`) |
| Deck verbessern | Ergebnis am Stand und am Diff sichtbar, nie am falschen Stand | `deck_series.py` liest bis zu 2.000 Dateien | kein Index, stille Obergrenze |
| Spielen | dieselbe Tisch-Definition, derselbe Treiber, dasselbe Protokoll | `play.py` mit eigenem Treiber, 5 Zugriffe auf private Runner-Methoden [M] | zweiter Treiber; in #1638 kommt ein dritter Ort dazu, der 4 private Runner-Namen benutzt (`full_game_series.py:303-311` [M]) |

## 2. Ist-Befund der Lane (nur was über die Brownfield-Bewertung hinausgeht)

- **Größenverhältnis im Store** [M, Sandbox]: 254.021.632 Bytes; `corpus_deck_card` mit Index
  148,8 MB (58,6 %); alle Nutzer-Tabellen zusammen 172 Zeilen (2 Decks, 2 Stände, 166 Kartenzeilen,
  2 Zweige; Markierungen, Labels, Module, Profile, Serien je 0). Was unersetzlich ist, ist winzig;
  was groß ist, ist aus Dateien wiederherstellbar.
- **Neuaufbau ist billig** [M]: alle 10.665 Quellen der Sandbox tragen `imported_at` zwischen
  20:14:51 und 20:17:28 UTC, also 157 s für den ganzen Import. Dauer am Owner-PC: UNKNOWN.
- **Karten-Identität ist zweiköpfig** [C]: `card` sind die Zeilen der Sammlungs-Arbeitsmappe
  (einziger Schreiber `importers.py:311`), `scryfall_card` sind 35.361 Oracle-Karten; die Sicht
  `card_fact` (`store.py:527-545`) legt beide übereinander. Stände und Module verlangen eine Zeile
  in `card` (`decks.py:88`, `deck_modules.py:174`).
- **Erreichbarkeit** [M, Importgraph mit Funktions-Importen]: 226 Module, 117.444 Zeilen unter
  `src/commander_lab`; vom Studio-Einstieg erreichbar 180 Module mit 89.189 Zeilen. Die älteren
  Lanes hängen nur über die Sammel-Exporte in `engine/rules/__init__.py` daran
  (`__main__ → engine.rules.project → engine.rules → tactical`), `engine/structural` über
  `builder.py:22 → deck_readiness → structural.card_facts`. Weder vom Studio noch vom
  Qualifikations-Paket erreichbar: 25 Module, 5.738 Zeilen (darunter `tam_import.py` 752, das nur
  `scripts/import_tam_drive.py` aufruft).
- **Routen** [M]: 116 Dekoratoren in `web.py` (2.612 Zeilen), 95 × `open_store()`, 51 ×
  `except KeyError`, 36 × `except ValueError`. Fünf API-Routen haben keine Fundstelle in `static/`:
  `/api/strength/snapshot`, `/api/simulations/pod-matrix`, `/api/simulations/batches`,
  `/api/labels`, `/api/engine/missing-cards`.
- **Durchsatz der PRs** [M, `gh api`, letzte 99 gemergte]: 25, 47 und 27 Merges am 17., 18. und
  19.11.; Median von Öffnen bis Merge 0,15 h, bei den 7 mit Label `material` 1,27 h. Die Review-Last
  ist heute eine Frage der Anzahl und der Abhängigkeit vom jeweils anderen Agenten, nicht der Dauer
  je PR.

## 3. Zielbild Datenmodell

### 3.1 Objekte, Identität, Quelle der Wahrheit

| Objekt | Identität | Quelle der Wahrheit | Ablage |
|---|---|---|---|
| Karte, Kartenfakten | `oracle_id` (Scryfall); Engine-Name als Feld | Scryfall-Massendatei, Stand im Manifest des Datenpakets | Referenz-Store |
| Besitz | `oracle_id` + Lagerort | Sammlungs-Arbeitsmappe (`data/research/collection_1655`) | Referenz-Store, als Auflage; fehlt die Zeile, ist die Karte „nicht im Besitz“, nie Menge 0 aus Vermutung |
| Korpus, Beobachtungen, Rollen, Signale | Quelle + natürlicher Schlüssel; Kohorte an einen Commander gebunden | Dateien unter `data/research/**`, Drive-Exporte für TAM | Referenz-Store, mit `UNIQUE` auf dem natürlichen Schlüssel |
| Deck | `deck_id`, Art `own` oder `opponent` | Nutzer-Store | `deck` |
| Deck-Stand | `revision_id` (bleibt beim Umzug unverändert), `content_hash` über sortierte (Zone, `oracle_id`, Menge) | Nutzer-Store, unveränderlich | `deck_revision`, `deck_revision_card` |
| Herkunft eines Stands | `origin_id` | Nutzer-Store | neu `origin`: Art (Deckbauer, Text-Import, Datei, Repository-Vorlage), SHA-256 und Rohtext des Imports, Zeit |
| Diff | zwei `revision_id` | wird gerechnet (`deck_diff.py`), nie gespeichert | – |
| Tisch | `table_hash` über die kanonische Spezifikation | Nutzer-Store | neu `table_preset`: Sitzliste (Deck-Stand, Pilot-Art, Strategie, Stil), Engine-Schalter |
| Experiment (Serie) | `experiment_id` | `manifest.json`, nach dem Start unveränderlich | `games/series/<id>/` wie in D-2; Indexzeile im Nutzer-Store |
| Partie | `game_id` (Log) und `game_key` (Determinismus-Schlüssel) | Journalzeile je endgültigem Ergebnis; Log `games/<id>.jsonl.gz` | Dateien; Indexzeile im Nutzer-Store |
| Ergebnis | (Experiment, Aufgabe) | Journal; Kennzahlen werden gerechnet | Datenklasse `SIMULATED_RESULT`, mit JAR-SHA-256, Bridge-Zustand, Engine-Pin, Pilot-Fingerabdruck, Deck-Hashes, Seeds, Sitzplan |
| Pilot-Fingerabdruck | SHA-256 über die verhaltensbestimmenden Dateien plus Policy-Version | Code des laufenden Servers | beim Start gerechnet, in Manifest und Journal geschrieben |
| Einstellungen | Schlüssel | Nutzer-Store (`setting`) für alles, was ein Ergebnis ändern kann; `localStorage` nur für reine Ansicht | – |

Regel für alle: Was ein Ergebnis ändern kann, steht im Manifest des Experiments. Zur Spielzeit wird
nichts Ergebnis-Relevantes aus Umgebungsvariablen gelesen außer dem Engine-Befehl, und der wird
aufgezeichnet (so schon in #1638).

### 3.2 Entscheidungen

**E-A1 Zwei Dateien nach Lebenszyklus.** `reference.sqlite3` enthält die 27 Tabellen der Gruppe
IMPORT aus dem D-1-Entwurf; der Server hängt sie nur lesend an (`ATTACH` mit `mode=ro`), Importer
sind eigene Prozesse wie heute (47 Unterbefehle in `__main__.py` [M]). Unqualifizierte Tabellennamen
löst SQLite über angehängte Dateien auf, die 488 `execute`-Stellen bleiben also im Wortlaut. Schema
des Referenz-Stores ändern heißt neu bauen (`studio rebuild-reference`), nie migrieren; damit ist die
Eindeutigkeit aus #1548 (144 Dublettengruppen in `observation` [D: `data_store.md` 2.2]) ein
`UNIQUE` im Schema-Text und kein Migrationsproblem. Der Referenz-Store wird ein **Datenpaket** mit
Manifest (Eingabedateien mit SHA-256, Schema-Version, Zeilen je Tabelle); es kann außerhalb des
Owner-PCs gebaut und als Datei geliefert werden, auch über Drive, wo die TAM-Rohdaten ohnehin liegen
(#1187).
- Kosten: 3 bis 4 Lane-Tage. Risiko: Fremdschlüssel über Dateigrenzen gibt es in SQLite nicht; die
  Verweise von Nutzer-Tabellen auf `card` und `source` entfallen als Zwang und werden zu einer
  Prüfung beim Schreiben und in `doctor`. Abnahme: Antwort-Manifest aus D-0 vor und nach dem Schnitt
  gleich; zwei Neuaufbauten aus denselben Eingaben ergeben denselben Tabellen-Hash; ein Schreibversuch
  des Servers auf eine Referenz-Tabelle scheitert im Test.
- Alternative (verworfen): eine Datei mit „Neuaufbau an Ort und Stelle“. 1,5 bis 2 Tage, aber kein
  lieferbares Datenpaket, Sicherung bleibt 254 MB und wächst mit jedem Commander, ein Importfehler
  trifft dieselbe Datei wie der Deck-Verlauf. Sie ist der Rückfall, wenn der Schnitt sein
  Abbruchkriterium reißt (Abschnitt 8).

**E-A2 Export-Format für den Nutzerzustand.** `studio export-state` schreibt
`studio-user-state-1` (gz-JSON): Decks, Stände mit Karten als `oracle_id` plus Name, Zone, Menge,
alte `revision_id`, Zweige, Entwürfe, Labels, Primer, Module, Markierungen, Profile, Tische,
Einstellungen, SHA-256 über den Inhalt. `import-state` liest es in ein frisches Schema. Der Server
legt beim Start eine Kopie an und behält die letzten 14; vor jeder Migration zwingend.
- Kosten: 1,5 bis 2 Tage. Abnahme: Export → Import → Export ist gleich; Rundlauf auf einer
  Schema-21-Fixture und auf dem vom Owner geschickten Export.

**E-A3 Oracle-ID als Schlüssel im Nutzer-Store.** `deck_revision_card`, `deck_module_card`,
`card_mark`, `card_label` wechseln von `card_id` auf `oracle_id`. Die `revision_id` bleibt, damit
alte Serien-Dateien weiter auf ihren Stand zeigen; der neue `content_hash` kommt als Spalte dazu,
der alte `deck_hash` bleibt als Herkunftsfeld. Ein Stand darf Karten ohne Besitz enthalten; die
Prüfung meldet sie wie heute getrennt (`validate_rows(owned_only=…)`, `decks.py:256`). Gegner-Decks
werden beim Neuaufbau als Decks der Art `opponent` angelegt.
- Kosten: 3 bis 5 Tage (größte Unsicherheit: `builder.py` mit 75 SQL-Stellen [D]). Risiko: eine
  Sammlungskarte ohne `oracle_id` am Owner-PC; der Export meldet sie vorab, die Migration bricht ab
  statt zu raten. Abnahme: ein Stand mit drei Karten außerhalb der Sammlung wird gespeichert, mit
  der Engine geprüft und in Partie und Serie gestartet; die Besitz-Anzeige zählt n von N.

**E-A4 Experiment-Index, Tisch, Fingerabdruck.** Wahrheit bleiben Manifest und Journal aus D-2
(kein zweiter Schreibweg im Spielbetrieb). Der Nutzer-Store bekommt `experiment` und `game` als
Index, gefüllt beim Abschluss jedes Fensters und vollständig neu aufbaubar (`studio reindex`,
Vergleich in `doctor`). `simulation_run` und `simulation_card` entfallen; ihre Zeilen werden als
Altbestand in den Index übernommen. Das Journal bekommt je Partie eine kompakte Karten-Zusammenfassung
(heute nur aus dem Log rechenbar, `card_outcomes.py`), damit Logs löschbar werden, ohne Zahlen zu
verlieren. `game_key` aus dem D-2-Entwurf wird um den Pilot-Fingerabdruck erweitert; gleicher
Schlüssel mit anderem Transkript-Hash ist ein Alarm.
- Kosten: 3 bis 4 Tage. Abnahme: Deck-Verlauf zeigt Batch- und gepaarte Serien aus einer Abfrage,
  ohne Dateisuche und ohne Obergrenze; Index gelöscht und neu gebaut ergibt dieselbe Antwort; eine
  Serie zu einem anderen Stand erscheint nie am aktuellen Stand (vorhandene Regel, neuer Test über
  den Index).

**E-A5 Aufbewahrung.** Manifest, Journal und Index bleiben immer (kB je Serie). Logs: 52 bis 219 kB
je Partie gepackt, Mittel 117 kB [D: `eff_sim_play.md`], also rund 1,2 GB je 10.000 Partien. Nichts
wird still gelöscht: `studio prune-logs --dry-run` zeigt n von N und den freien Platz; gelöscht
werden nur Logs abgeschlossener Experimente, deren Zusammenfassung im Journal steht. PLAY-Partien
und alle Partien mit Fehlerklasse bleiben. Serien-Logs entstehen mit gzip-Stufe 1 (`games.py:292`);
ein Nachpacken auf Stufe 9 beim Abschluss ist möglich, der Gewinn ist UNKNOWN.

**E-A6 Versionierung.** Drei getrennte Versionen statt einer: Referenz-Schema (Neuaufbau),
Nutzer-Schema (Migration über das Export-Format), Dateiformate (`studio-series-manifest-1`,
`studio-user-state-1`, Log-Schema). `/api/status` und `doctor` nennen alle drei plus Commit,
JAR-SHA und Engine-Pin.

**Sitzzahl im Modell.** Der Tisch ist eine Sitzliste; nichts im Schema legt 4 fest. Konstanten gibt
es an zwei Stellen (`launch.py:32`, `:37`; dazu `PlayConcedeBody.seat le=5`). Für 2 bis 8 muss das
Datenmodell nichts tun; Engine, Piloten und Freigabe bewertet die SIMULATE-Lane, die Freigabe 5 bis 8
bleibt Owner-Vorbehalt.

**Preise.** Der Owner will sie beim Zukauf später (#1187, „erstmal ohne Preis“). Im Modell wäre das
eine weitere Referenz-Tabelle mit Quelle und Datum. Jetzt wird nichts angelegt; der Preis-Wächter
bleibt, bis der Owner den Kaufmodus mit Preisen anordnet.

### 3.3 Weg von heute dorthin (Datenkontinuität am Owner-PC)

1. Paket K-2a liefert `export-state` und die automatische Kopie beim Start, noch auf Schema 21.
2. Der Owner startet einmal und schickt die Exportdatei (Deck- und Sammlungsdaten dürfen den Rechner
   verlassen, `AGENTS.md` §12).
3. Die Migration wird in der Agenten-Umgebung an genau dieser Datei gefahren: Bericht mit Zeilen je
   Tabelle vorher und nachher, nicht abbildbare Karten, Antwort-Manifest der Deck-Routen.
4. Am PC: neuer Stand, Start. Der Starter sichert den alten Datenordner, baut oder übernimmt das
   Datenpaket, importiert den Zustand und baut den Index aus den vorhandenen Serien-Dateien (alte
   `*.paired.json` und `progress.jsonl` liest der Übernahme-Leser aus D-2 5.3 Punkt 6). Die alte
   `studio.sqlite3` bleibt unverändert im Sicherungsordner.
5. Rückweg: Sicherungsordner zurückkopieren und den alten Stand starten.

## 4. Zielbild Schichten und Schnittstellen

Schichten werden durch den Architekturtest aus D-0 erzwungen, nicht durch Verschieben von Dateien.
Neue Unterordner entstehen nur für neuen Code (`studio/api/`).

| Schicht | Inhalt | Regel (als Test) |
|---|---|---|
| Kern, rein | Deck-Liste und Hash, Diff, Statistik (Wilson, gepaart, hypergeometrisch), `strength.py` | kein `sqlite3`, kein Prozess, kein Netz |
| Daten | `store.py`, Referenz-Leser, Nutzer-Ablage, Cache | Zahl der Module mit `execute` (47 [D]) darf nur sinken; neue Abfragen als typisierte Lesefunktionen |
| Engine-Zugang | Sitzung, Pool, Prozess-Register | kein Import aus Deckbau- oder Bewertungs-Modulen; 0 Zugriffe auf private Runner-Namen |
| Dienste | Deck-, Experiment-, Partie-Dienst (die heutigen Verwalter) | kein Import von `web` |
| API | Router je Bereich | kein SQL, kein `open_store()` im Router |
| Seite | Rahmen, Deckbau, Simulation, Spielen, Daten | reine Logik in Dateien mit `node`-Test |

**E-B1 Cache (D-1 vom Zielbild aus).** P1 bis P3 laufen wie entworfen weiter: Register, Wertformen,
Grenzen, Option A sind in jedem Zielbild nötig. Genaue Änderungen:
- P2 bekommt eine schärfere Probe: jede Art mit `reads={IMPORT}` wird im Test auf einer Verbindung
  gerechnet, die den Nutzer-Tabellen den Zugriff verweigert. Nach E-A1 ist das dieselbe Aussage wie
  „rechenbar nur mit der Referenz-Datei“.
- P4 (Aufwärmen, Datenbericht in Abschnitten) bleibt, Rang nach P3.
- P5 wird ersetzt durch „zwei Anker“: Für IMPORT ist der Anker der Dateistempel von
  `reference.sqlite3`; die Beweise I2 und I3 (fremder Commit im Schreibfenster, `data_version`,
  Zählerdifferenz) gelten dann nur noch für die kleine Nutzer-Datei. Die Importer-Deklarationen aus
  P5 entfallen, weil ein Import die Referenz-Datei als Ganzes ersetzt. `memo.py` fällt wie geplant.
- Kein WAL, eine Verbindung je Anfrage bleibt (0,97 ms je Öffnen [D]).

**E-B2 Engine-Zugang: ein Treiber, zwei Wirte.** Heute gibt es den Runner, `play.py` und mit #1638
`XmageFullGameSeriesSession`; die beiden letzten greifen auf private Runner-Namen zu (5 Stellen [D] und 4
Namen [M]). Entscheid: #1638 wird nicht aufgehalten (hinter Schalter, eigener Ergebnistyp nach
E9). **D-3 wird direkt danach gebaut und anders geschnitten:** Der Runner bekommt die öffentliche
Schrittfolge (Sitzung öffnen, Partie anlegen, nächste Entscheidung, antworten, Ergebnis, Partie
schließen); die Serien-Sitzung und `play.py` setzen darauf auf. Der Mensch-Sitz ist dann eine
Partie, deren Entscheidungen von außen kommen, statt eines eigenen Treibers.
- PLAY über einen Pool-Worker: nein. Gründe: Die Schwärzung verdeckter Information liegt im
  Serverprozess (`games.py`, `play.py`) und soll genau eine Prozessgrenze haben; PLAY hat kein
  Zeitlimit (E5), der Pool beendet nach 30 Minuten ohne Antwort [D: #1638].
- Gemeinsam für beide Wirte: ein Prozess-Register (PIDs von Workern und JVMs, Aufräumen verwaister
  JVMs beim Start, unter Windows ein Job-Objekt über `ctypes`, damit Kindprozesse mit dem Server
  enden) und ein Lastbudget (eine laufende Partie am Brett nimmt der Serie einen Worker).
- Kosten: 3 bis 5 Tage für D-3, 1,5 für D-2 P5 [D]. Abnahme: 0 private Zugriffe aus `studio/` und aus
  `full_game_series.py`; `type: ignore` in `play.py` höchstens 2; Echt-Engine-Test des Mensch-Sitzes
  und Lecktest grün; Referenzsatz mit gleichen Transkript-Hashes (keine Bridge-Änderung).

**E-B3 Hintergrund-Aufträge.** Wiederaufnehmbar ist genau eine Art: das Experiment (Manifest beim
Start, Journal, Sperre mit Herzschlag, „unterbrochen“ nach Absturz; D-2 5.2 und 5.3). Importe und
der Neuaufbau bleiben Befehle außerhalb des Servers. Kein allgemeines Auftragssystem.

**E-B4 Web-API.**
- Router: `studio/api/build.py`, `simulate.py`, `play.py`, `data.py`, `system.py`; `create_app`
  baut nur zusammen. Fünf PRs, je Bereich einer, jeder mit gleichem Antwort-Manifest vorher und
  nachher (das Manifest aus #1627 wird dafür von 30 Leserouten auf alle `GET`-Routen und die
  Schreibmatrix erweitert).
- Store als Abhängigkeit je Anfrage statt 95 × `try/finally`.
- Fehlervertrag: Fachausnahmen `NotFound`, `Invalid`, `Conflict`, `EngineNotReady`, `NotReleased`
  mit festem Code, ein Handler, Antwort `{"error": {"code", "message", "detail"}}`; das Feld
  `detail` bleibt eine Version lang zusätzlich oben, weil `ui.js:114-117` es liest. Ein nackter
  `KeyError` wird 500 mit Logzeile, nie „nicht gefunden“.
- Antwort-Typen für die rund 25 Routen des Kreislaufs (Decks, Stände, Tisch, Experimente, Partien,
  Spielzustand), als JSON-Schema-Dateien im Repository mit Test. Die großen Auswertungs-Antworten
  bleiben Bytes aus dem Cache (11,8 MB für `strength` [D]) und bekommen Form-Fixtures.
- Fortschritt: die gehaltene Anfrage aus #1634 auch für Experimente; Abfragen im Takt bleibt
  Ausweichweg.
- Kosten: 4 bis 6 Tage. Abnahme: `web.py` unter 200 Zeilen; 0 × `except KeyError` als 404; dieselben
  Fixtures werden vom Python-Test und von einem `node`-Test der Seite gelesen.

**E-B5 Frontend.** Kein Build, kein Framework, CSP und `h()` bleiben (keine neue Abhängigkeit).
- Rahmen in `ui.js`: Navigation, Bridge-Banner, Fehleranzeige, dazu eine Auftragsleiste, die auf
  jeder Seite laufende Experimente zeigt.
- Neue Seite „Simulation“: Experimente planen, verfolgen, vergleichen. Das ist der natürliche
  Schnitt durch `app.js` (3.245 Zeilen, `renderSimulations` 245 Zeilen [D]) und nimmt `paired.js`
  und `deckseries.js` mit; der Deckbauer zeigt nur noch das Ergebnis am Stand und am Diff.
- Testbarkeit: jede neue oder angefasste Funktion legt Zustandsübergänge und Ansichtsmodell in eine
  Datei mit `module.exports`-Schluss wie `boardclick.js`; Regex-Prüfungen des Quelltexts zählen nicht
  als Verhaltenstest.
- Kosten: 5 bis 8 Tage (größte Unsicherheit: `app.js` hat einen globalen Zustand mit 70 Feldern
  [D]). Was Builder, Tierliste und Spielbrett fachlich zeigen, entscheiden die drei Bereichs-Lanes.

**E-B6 Prozessmodell am Windows-PC.**
- Ein Serverprozess, Kindprozesse nur über das Prozess-Register. Eine Instanz je Datenordner
  (Sperrdatei mit PID und Herzschlag); ein zweiter Start meldet das und endet.
- Stopp: Fenster schließen oder Strg+C beendet Serien geordnet (beendete Partien stehen im Journal),
  das Job-Objekt räumt den Rest. Verhalten am Owner-PC: UNKNOWN bis zum Lauf; der Workflow
  `windows-runtime.yml` ist der Ort für den Test davor.
- Sicherung: Zustands-Export bei jedem Start (14 Stück), volle Sicherung auf Befehl (`backup.py`
  gibt es), vor Migration zwingend.
- Release: ein Archiv aus `release-artifacts.yml` mit Python-Paket, JAR, Pin, Starter und den
  Repository-Daten, die Neuaufbau und Gegner-Decks brauchen, damit der PC ohne Git-Clone auskommt.
  Das Artefakt hält 30 Tage; ein dauerhaftes Release ist Veröffentlichung und Owner-Sache.
- Fehler: Logdatei im Datenordner, `studio support-bundle` packt Log, `doctor`-Ausgabe und Manifeste
  zu einer Datei für die Rückgabe. Keine Telemetrie.
- Einstellungen in drei Ebenen: Rechner (`settings.json` im Datenordner plus Umgebungsvariablen:
  Port, Worker, Heap, Partien je JVM), Nutzer (Tabelle `setting`), Experiment (im Manifest
  eingefroren).
- Kosten: 3 bis 4 Tage.

## 5. Was weg kann, was bleibt, was zurückgestellt wird

| Gegenstand | Umfang | Beleg | Urteil und Löschpfad |
|---|---|---|---|
| Java ältere Lanes (Midgame, Restoration, Causal, Phase 6, `JsonlBridge`) | 9.824 Zeilen [D] | `Main.java:23-41` verteilt `phase6`, `midgame`; `pb03-runtime-qualification.yml` und `scripts/run_midgame_capability_probe.py` starten `midgame`; 205 bis 300 Dateien unter `qualification/` nennen die Pfade, `WS17_SHA256SUMS` 0 [M] | **bleibt.** §9 hält sie. Löschen nur zusammen mit einer neuen Epoche „nur Full-Game“ (Owner, Abschluss-Phase). Laufzeitkosten im Studio: keine belegt |
| Python `tactical.py`, `bridge.py`, `phase85.py`, `registry.py`, `manager.py`, `replay.py`, `process_manager.py` | 3.018 Zeilen [M] | Importeure nur `engine/rules/__init__.py` und untereinander; 3 + 2 + 1 Testdateien; 9 Skripte `run_external_b3…b4f`, die `external-engine-integration.yml` nennt [M] | **zurückgestellt.** Kein Studio-Pfad braucht sie, aber Workflows und Tests leben. Löschpfad: mit dem Workflow in einem Paket nach dem Abschluss (Workflow-Änderung, MATERIAL) |
| `engine/structural/` | 2.757 Zeilen [M] | Studio erreicht es über `builder.py:22 → deck_readiness.py:19`; 5 und mehr Testdateien | **bleibt**, aber der Deckbauer soll nur `card_facts` brauchen: als Schicht-Regel aufnehmen, nicht umbauen |
| `simulation_run`, `simulation_card` | 2 Tabellen | ersetzt durch E-A4; in der Sandbox 0 Zeilen [M] | **weg** mit Schema 22, Altzeilen in den Index |
| `tier_snapshot` (Tabelle) | 1 Tabelle, 0 Zeilen [M] | einziger Schreiber `import_all.py:711` (CLI) [D] | **weg aus dem Nutzer-Store**; als abgeleiteter Wert in den Cache oder ins Datenpaket. Ob die Funktion bleibt, entscheidet die BUILDER-Lane |
| `memo.py` | 111 Zeilen | D-1 | **weg** (D-1, neu „zwei Anker“) |
| alte Orchestrierer (`plan_chunks`, Chunk-Weg, `play-batch`) | Teil von `simulations.py`, `paired_comparison.py` | D-2 P5 | **weg**, sobald der Pool nach dem Owner-PC-Lauf Vorgabe ist |
| `subarchetypes.py` | 294 Zeilen | kein Importeur in `src`, 1 Test, 1 Skript [M] | **weg** mit Test und Skript, wenn die BUILDER-Lane es nicht braucht |
| `spellbook_shells.py` | 374 Zeilen | kein Importeur in `src`, aber am 2026-11-19 mit #1640 für TAM geändert | **bleibt** (in Benutzung über Skript); gehört in den Neuaufbau eingehängt |
| Gesamtrating und Rubrik (`overall_rating.py`, `card_understanding.py`, `ranking_check.py`, `chulane_textfit.py`) | 2.191 Zeilen [M] | Importeure nur `web`, `__main__`, `strength_view` | technisch sauber lösbar. **Zurückstellen, nicht löschen:** wählbare Zweitansicht bleibt aus, keine weitere Validierung; Entscheidung bei BUILDER-Lane und Owner (E6 war ein Owner-Wunsch vom 18.11.) |
| Bewertungs- und Universums-Komplex insgesamt | 21 Module, 16.237 Zeilen, dazu `tierliste.js` 2.453 [M] | ein Drittel des Studio-Pythons | **bleibt**, wird aber reiner Leser des Referenz-Stores; kein Umbau in diesem Lauf |
| Fünf Routen ohne Aufrufer in `static/` | siehe Abschnitt 2 | [M] | je Router-PR prüfen: entfernen oder im Vertrag führen |
| Datensammel-Skripte (`collect_*`, `*_fetch`, `derive_edhrec_signals`, `compute_topdeck_conversion`) | 7 Dateien und ein Ordner in `scripts/`, dazu `import_tam_drive.py` [M] | erzeugen Eingaben unter `data/research` | **bleiben**, werden Eingabeseite des Neuaufbaus; neue Sammel-Wellen zurückgestellt, bis der Kreislauf steht (Ausnahme TAM, Owner 19.11.) |
| Entscheid- und Plan-Dokumente | 1.064 Dateien unter `docs/`, 9 Owner-Entscheid-Dateien [M] | E10 erlaubt Ersetzen | eine Charta ersetzt Scope, zwei Entscheid-Dateien, Plan und Roadmap als Pflichtlektüre; Rest ins Archiv (Abschnitt 7) |

## 6. Reihenfolge und Paketplan

Laufend und unverändert: D-1 P1 bis P3 (Rest rund 3 Lane-Tage [V]), #1638 (Review), D-2 P5 (1,5).

| Lauf | Paket | Inhalt | Lane-Tage | Abnahme (zusätzlich zu Checks und Review) |
|---|---|---|---|---|
| 1, vor Owner-Sitzung 1 | K-1 | D-3 neu geschnitten (E-B2), Prozess-Register | 3–5 | private Zugriffe aus `studio/` und `full_game_series.py` auf 0; Referenzsatz hash-gleich |
| 1 | K-2a | Export-Format, Kopie beim Start, eine Instanz je Ordner | 1,5–2 | Rundlauf gleich; zweiter Start endet mit Meldung |
| 1 | K-0 | Charta-Dokument und Regeländerungen (Abschnitt 7) | 1 | Owner-Antworten wörtlich im Dokument |
| 2, Schema 22 | K-2b | Dateischnitt, `rebuild-reference`, Datenpaket-Manifest, D-1 „zwei Anker“ | 3–4 | Manifest gleich; Neuaufbau deterministisch |
| 2 | K-2c | Oracle-ID im Nutzer-Store, Karten ohne Besitz, Gegner als Decks | 3–5 | Stand mit Fremdkarten läuft in Partie und Serie |
| 2 | K-2d | Experiment-Index, Tisch, Pilot-Fingerabdruck, Zusammenfassung im Journal, `prune-logs` | 3–4 | Deck-Verlauf aus einer Abfrage; Index neu aufbaubar |
| 2 | K-2e | Migration am echten Export, Windows-Lauf, Rückweg geübt | 1,5–2 | Bericht ohne nicht abbildbare Zeile; Rückweg einmal ausgeführt |
| 3, parallel zu Features | K-3 | Router, Fehlervertrag, Antwort-Typen (E-B4), je Bereich ein PR | 4–6 | Antwort-Manifest gleich je PR |
| 3 | K-4 | Rahmen, Seite „Simulation“, `node`-Tests (E-B5) | 5–8 | mindestens 60 ausgeführte JS-Testfälle im Kreislauf |
| 3 | K-5 | Job-Objekt, Logdatei, `support-bundle`, Release-Archiv ohne Clone (E-B6) | 3–4 | Einrichtung von null aus dem Archiv unter Windows |

Summe 28 bis 41 Lane-Tage, Unsicherheit ±40 % (Eichung wie in der Brownfield-Bewertung: 155 PRs in 9
Tagen entsprachen rund 36 Lane-Tagen [D]). K-2c und K-4 tragen die größte Streuung.

**Was parallel läuft.** K-1 (Engine-Dateien, `play.py`) und K-2a (`store.py`, `backup.py`,
`__main__.py`) berühren sich nicht. Lauf 2 ist eine Lane mit Sperre auf `store.py` und `builder.py`;
BUILDER-Features, die SQL gegen Nutzer-Tabellen schreiben, warten in dieser Zeit oder gehen über die
Lane. K-3 teilt sich nach Bereich auf die drei Bereichs-Lanes; die Sperre auf `web.py` gilt je PR
höchstens einen Tag.

**Verhältnis zur Owner-Sitzung 1.** Lauf 1 davor (der Owner misst dann die langlebigen JVMs und hat
ab dem ersten Start Sicherungen). Schema 22 braucht keine eigene Sitzung mehr: Schritt 2 aus 3.3 ist
eine Datei per Nachricht, Schritt 4 ein Start. Lauf 3 richtet sich nach dem Urteil aus AK-8.

**Messnetz.** (1) Antwort-Manifest aus #1627, erweitert auf alle `GET`-Routen; (2) Transkript-Hash
je Seed auf dem Referenzsatz; (3) Rundlauf des Zustands-Exports; (4) Tabellen-Hash des Neuaufbaus;
(5) Ratschen im Architekturtest: größter Zyklus höchstens 13 Module [D: #1627], Module mit `execute`
höchstens 47, private Runner-Zugriffe, `open_store()` in der API, Zahl ausgeführter JS-Tests.

## 7. Prozess und Governance

1. **MATERIAL teilen.** Klasse A (Inhalt): Engine, Bridge, Qualifikation, Gates, Pilot-Logik,
   Regel-, Evidenz- und Policy-Text, Sicherheit, Workflows, Schema und Migration. Klasse B (nur
   Größe über 300 Zeilen). A behält Kreuz-Review durch den anderen Agenten. B bekommt ein Review aus
   frischem Kontext, das auch eine Sitzung desselben Agenten sein darf. Für rein mechanische
   Umzüge (Router, Dateiteilung) prüft das Review den Gleichheitsnachweis und den Diff der Tests,
   nicht jede verschobene Zeile. Das ändert E7/C7 und §10 und braucht den Owner (Frage 3).
2. **Studio-Daten-Gate** nach dem Muster des Bridge-Gates: Ein PR, der `_SCHEMA`, eine Migration
   oder das Export-Format ändert, zeigt Rundlauf auf Fixtures jeder früheren Version ab 21, den Lauf
   am Owner-Export, die erzwungene Sicherung und das Antwort-Manifest vorher und nachher.
3. **Verschiebe-Sperre aussetzen.** „Nichts verschieben oder umbenennen“ (Onboarding §3) gilt nicht
   für ein in #1167 geclaimtes Konsolidierungspaket mit Dateisperre und Gleichheitsnachweis.
   `ci-definition-integrity-shadow` wird bei solchen PRs rot sein; der PR trägt die Tabelle „alte
   Zusicherung → neue Zusicherung“, wie der D-1-Entwurf es vorsieht.
4. **Eine Charta statt fünf Pflichtdokumente.** Heute sind es `AGENTS.md` 445, `CLAUDE.md` 77,
   Scope 270, zwei Entscheid-Dateien 385 und 94, Plan 92, Onboarding 136 Zeilen, zusammen 1.499 [M].
   Ziel: `docs/STUDIO_CHARTER.md` (Zweck, Kreislauf, Zielbild, feste Regeln, Paketplan, höchstens 250
   Zeilen) und ein Entscheid-Register mit einer Zeile je Entscheid (Kennung, Datum, Wortlaut,
   Quelle). Die alten Dateien wandern nach E10 ins Archiv, mit Verweis.
5. **Architektur als Test, nicht als Prosa.** Jede Entscheidung aus Abschnitt 4 hat eine Ratsche; ein
   Paket ist fertig, wenn seine Ratsche sich bewegt hat.
6. **Kleine PRs bündeln.** 99 Merges in drei Tagen [M] heißen 99 volle Check-Läufe. Regel: Korrekturen
   an derselben Fläche am selben Tag gehen in einen PR; ein Paket bleibt ein PR.

## 8. Risiken und Abbruchkriterien

| Risiko | Folge | Abbruch oder Rückfall |
|---|---|---|
| `ATTACH` bricht mehr als gedacht: 70 Testdateien führen SQL gegen das Schema aus [D] | Testumzug frisst das Budget | Müssen mehr als 10 dieser Dateien anders als durch Hinzufügen geändert werden, Rückfall auf eine Datei mit Neuaufbau an Ort und Stelle; E-A2 bis E-A4 bleiben gültig |
| Sammlungskarte ohne `oracle_id` am Owner-PC | Stand nicht abbildbar | Migration bricht ab und nennt die Karten; kein Raten |
| Job-Objekt oder Prozessbaum unter Windows verhält sich anders | verwaiste JVMs | Rückfall auf `taskkill /T` über gemeldete PIDs (D-2 5.4) |
| D-3 kollidiert mit #1638 | doppelte Arbeit | K-1 startet erst nach dem Merge von #1638 und baut auf dessen Datei |
| Index und Journal laufen auseinander | falsche Zahl am Stand | Journal gewinnt; `doctor` vergleicht; ein Unterschied ist ein Befund, der Index wird neu gebaut |
| Ein Paket überschreitet sein Budget um mehr als 50 % | Lauf verzögert | stoppen, Befund ins Issue, Co-Lead entscheidet; eine unerklärte Abweichung in Manifest oder Hash nach zwei Tagen heißt zurück auf den alten Weg (Regel aus #1612) |
| Owner-Sitzung 1 zeigt wichtigere Produktmängel | Lauf 3 falsch priorisiert | Lauf 3 folgt AK-8; Lauf 1 und 2 sind davon unabhängig |

## 9. UNKNOWN

- Store am Owner-PC: Größe, Zahl der Decks, Stände, Markierungen, vorhandene Serien-Dateien, ob dort
  weitere Karten in `card` stehen.
- Dauer von Import und Neuaufbau unter Windows (157 s stammen aus Zeitstempeln der Sandbox).
- Verhalten von `ATTACH` mit `mode=ro`, Dateistempeln und Job-Objekt unter Windows; nichts davon
  ausgeführt.
- Ob das Datenpaket TAM-Rohdaten enthalten darf, die nur auf Drive liegen (Sichtbarkeit, #1108).
- Welche Dateien den Pilot-Fingerabdruck bestimmen; die Liste braucht die SIMULATE-Lane.
- Größe der Karten-Zusammenfassung je Partie im Journal (Schätzung 2 bis 4 kB [V]).
- Importzeit des Pakets `engine.rules` mit den älteren Lanes: nicht gemessen.
- Ob die fünf Routen ohne Fundstelle von Skripten oder vom Owner direkt benutzt werden.
- Alle Kosten: aus der Eichung der Brownfield-Bewertung abgeleitet, nicht aus eigener Messung.

## 10. Offene Owner-Fragen (mit Empfehlung)

1. **Schema 22 als Trennung in Referenz-Datei und Nutzer-Datei, Migration über die Exportdatei, die
   du einmal schickst?** Empfehlung: ja.
2. **Dürfen Decks Karten enthalten, die du nicht besitzt (für Import, Gegner und TAM-Zukauf), mit
   getrennter Besitz-Anzeige?** Empfehlung: ja.
3. **MATERIAL teilen: Kreuz-Review nur für Klasse A, Größe allein reicht für Review aus frischem
   Kontext desselben Agenten?** Empfehlung: ja, zunächst für die Dauer der Konsolidierung.
4. **Ältere Java- und Python-Lanes mit der Abschluss-Epoche entfernen („nur Full-Game“
   qualifizieren)?** Empfehlung: ja, aber erst dann; bis dahin bleiben sie unangetastet.
5. **Release ohne Git-Clone: dauerhaftes GitHub-Release oder Artefakt, das du nach jeder Abnahme
   lokal ablegst?** Empfehlung: lokal ablegen, solange die Sichtbarkeit (#1108) offen ist.
