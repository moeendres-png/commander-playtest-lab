# Charta SIMULATE: Produkt- und Architektur-Entscheid von Grund auf (Lane SIMULATE, Brownfield 2)

Stand 2026-11-19. Nur gelesen: Lab `main` @ `0792a59b` (Clone, inzwischen gelöscht), PR #1638 Head `3b3ef446`,
Fork-Pin-Kopie `f4d12f6e8`, Berichte auf `docs/fable-sonnet-haiku-reports` (`eff_sim_play.md`, `xmage_eff_fable.md`,
`d2_pool_design.md`, `brownfield_fable.md`), `pilot_validity.md`, `simulate_methods.md`, Issues #1612, #1265, #1167.
Kein Engine-Lauf, keine Suite, kein Build, nichts gepusht oder kommentiert.
Belegklassen: **[C]** am Code gelesen (Datei:Zeile, keine Laufzeitaussage) · **[M]** Messwert aus genanntem Bericht (nicht
nachgemessen) · **[S]** eigene Rechnung/Modell · **[V]** Vorschlag dieser Charta · **UNKNOWN** nicht belegt.

## 1. Ergebnis zuerst

1. **Leitsatz [V]: Tempo heißt „Zeit bis zur Antwort“, nicht „Partien je Stunde“.** Die Engine-Seite hat nach dem Pool
   noch höchstens Faktor 1,6 bis 2 (595 → 967 Partien/h auf 4 Kernen [M]); Statistik und Fragestellung haben Faktor 5 bis
   20 (Paarung 4,6-fach [M, n=37], Basis-Wiederverwendung 2-fach, Frühphasen-Kennzahl statt Siegquote rund 10-fach weniger
   Partien [S]). Daraus folgt die Stufenregel **Rechnen vor Simulieren**: L0 exakt gerechnet (Millisekunden, vorhanden:
   `castability.py`), L1 rundenbegrenzte Frühphasen-Serie (Minuten, neu, Owner-Entscheid), L2 gepaarte Vollpartien
   (Stunden bis Nächte).
2. **Ein Experiment-Modell statt Batch und Paar-Serie:** Tisch-Einstellung + Arme (1 bis k Deck-Stände oder Pilot-Profile,
   gemeinsame Basis) + Seed-Blöcke + Stopp-Regel, als Plan-Datei vor der ersten Partie. Batch (1 Arm) und Paar (2 Arme)
   sind Sonderfälle. Die Landzahl-Achse (#1528) braucht damit 5 statt 8 Arm-Läufe (−37,5 % Partien [S]).
3. **D-2 (Pool, PR #1638) bleibt richtig, bekommt aber zwei Pflicht-Ergänzungen:** inhaltsadressiertes Partie-Archiv
   (`game_key`) mit Serien-Zugehörigkeit per Manifest statt Ordner-Scan, und der Auftrag an den Worker trägt die ganze
   Tisch-Einstellung (heute nur Seed, Log-ID, Deck-Pfade; Stil je Sitz fehlt). Mehrere Partien gleichzeitig in einer
   JVM: verworfen.
4. **Sitze:** 2 bis 4 bleiben frei. **5 und 6 jetzt qualifizieren** (Paket 3 bis 4 Agent-Tage plus Rechenzeit, Freigabe
   danach durch den Owner je Sitzzahl). **7 und 8 zurückstellen:** kein Code-Problem (rund 15 Grenzstellen, Engine-Typ
   erlaubt 10), aber kein einziger Messwert, Bridge-Änderung, Aufhebung des 6er-Maximums, und je Antwort geschätzt 9- bis
   16-mal so teuer wie am Vierertisch [S]. Entscheid erst nach der 6er-Messung; wenn überhaupt, dann für Einzelpartien
   (PLAY), nicht für Serien.
5. **Tisch-Einstellung:** Gegner dürfen jeder Deck-Stand des Studios sein (heute nur 173 Repo-Precons plus 2); stille
   Ersatz-Gegner und `seed_step` werden entfernt; Presets Schnellcheck / Abend / Nacht / Kontrollen.
6. **Piloten „möglichst optimal“ wird dreifach messbar gemacht:** (a) Obergrenze klarer Fehler (Audit), (b)
   Verschwendungs-Zähler je Serie, (c) relative Stärke Pilot A gegen Pilot B als gepaarte Serie über ein festes
   Deck-Panel. Eine Pilot-Änderung geht nur mit (c) ≥ 0 ein. Weg: Heuristik plus Messschleife jetzt; Vorausschau (S5)
   nicht als Serien-Pilot (mindestens 2- bis 15-fach langsamer), höchstens später als Audit-Orakel und PLAY-Stärke;
   Lernen nur als Offline-Gewichtsabstimmung ohne Laufzeit-Abhängigkeit.
7. **Pilot-Fingerabdruck ist Voraussetzung für alles Weitere:** `PILOT_VERSION = "1.0.0"` ist konstant [C], die
   Mischungs-Prüfung der Paar-Auswertung vergleicht genau diese Zeichenkette und schützt damit heute nichts.
8. **Daten:** eigene Datei `simulate.sqlite3` (Experiment, Arm, Partie, Sitz-Ergebnis, Sitz-Karte, Befund) neben den
   Logs; Logs sind Cache (jede Partie ist aus ihrem Schlüssel neu erzeugbar), Fakten und Befunde bleiben.
9. **`simulation`-Gewicht:** aus dem Tierlisten-Index streichen, Stufe 2 streichen. Simulation ist Evidenz zu **einem
   Deck-Stand** und gehört in die Entscheidungsansichten des Deckbauers, ab dem ersten Tag, mit Reifegrad am Befund
   statt einem Tor davor.
10. **Entfernen:** getrennter Batch-Weg, Tabellen `simulation_run`/`simulation_card` als Ziel, `seed_step`, stiller
    Gegner-Ersatz, Ordner-Scan-Auswertung, Kennzahl „rotted“ in heutiger Form, Deckel 100 Partien / 1.000 Paare.
    **Zurückstellen:** S5, 7/8 Sitze, Lernen, Fork-Tempo (F1 bis F4), Tierlisten-Marker.
11. **Reihenfolge:** #1638 mit Echt-Engine-Beleg → A Tisch und Plan (mit Fingerabdruck) → B Archiv und Fakten → D-min
    Ergebnisseite → erste Nachtserie am Owner-PC → C Pilot-Messrahmen ∥ E Sitze 5/6 → D Deckbau-Ansichten → F Tempo →
    G Pilot-Schleife. Neu rund 21 bis 26 Agent-Tage zusätzlich zu D-2.

## 2. Nutzer-Kreislauf und was jeder Schritt von SIMULATE braucht

| Schritt | Braucht | Heute [C] | Lücke |
|---|---|---|---|
| Deck bearbeiten | Deck-Stand mit Hash; Vorab-Prüfung „simulierbar“ | `lab_snapshot`, `cards_unsupported_by_engine`, `cards_unknown_to_pilots` (`launch.py:676-717`) | keine |
| Frage stellen | Stufe L0/L1/L2 wählen; erwartete Richtung; „bei welchem Ergebnis ändere ich das Deck“ | L0: `castability.py:1-25` (exakt, Karsten-Methode), `land_advisor.py`; L2: Batch und Paar | kein L1; keine Plan-Datei (#1525 offen); nur 2 Arme |
| Tisch einstellen | Sitzzahl, Deck je Sitz, Gegner-Pool, Pilot-Profil je Sitz, Seeds, Budget | Pod-Preset oder Precon-IDs, ein Stil für alle (`web.py:277-307`) | Abschnitt 4.2 |
| Simulieren | so schnell wie der PC kann, abbrechbar, fortsetzbar, nebenher nutzbar | Chunk-Weg; Pool hinter Schalter (PR #1638) | Abschnitt 5 |
| Speichern | Partie-Fakten dauerhaft, Herkunft vollständig | Logs, zwei JSON-Formate, Aggregat in SQLite | Abschnitt 7 |
| Auswerten | Intervall, nachweisbare Differenz, Herkunftsklasse, Gültigkeitsblock | Cluster-t, OBF-Looks, Zensur (`paired_comparison.py:335-479`) | A2 (#1525, #1527) nicht gebaut |
| Deck verbessern | Befund am Deck-Stand, im Diff und im Tausch-Labor | Serienliste im Deck-Verlauf (`deck_series.py`) | Abschnitt 7.3 |
| Spielen | dieselbe Tisch-Einstellung mit Mensch-Sitz | `start_game` (`launch.py:806-864`) | gemeinsames Modell fehlt |

## 3. Ist-Befund (kurz, belegt)

**Vorhanden und tragfähig:**
- Statistik: gepaarte Auswertung mit Cluster-t je Seed, exaktem Vorzeichentest, O'Brien-Fleming-Looks, Zensurgrenze 5 %
  und Asymmetrie-Test (`paired_comparison.py:56-61, 259-283, 354-393`) [C]; Holm über mehrere Varianten in der
  Engine-Lane (`full_game_comparison.py:1061-1090`, `aggregate_comparison` `:1092`) [C], im Studio nicht verdrahtet.
- Varianzreduktion: Slot-Ausrichtung (`full_game_comparison.py:243-292`, Studio `paired_series.py:291-320`) [C];
  gemessen 10,8 % diskordant (4/37, Wilson 4,3 bis 24,7 %) statt 48,4 %, Varianz 4,6-fach kleiner, Paar-Streuung 0,329
  statt Planungswert 0,63 [M `eff_sim_play.md` §4.3; ein Deckpaar, drei Tauschkarten].
- Determinismus: 424/424 Partien je Seed identisch über 31 Zellen [M ebd. §3].
- Karten-Wirkung pilotarm: „in der zuerst ausgeteilten Hand gegen nicht“ (`card_outcomes.py:1-13`) [C].
- Ereignisprotokoll der Engine mit 24 Ereignisarten je Partie (Zonenwechsel, Zauber, Schaden, Verlust, Ziehen, …:
  `XmagePublicEventWatcher.java:41-64`), im Log-Abschluss gespeichert (`games.py:389-404`), **von keiner Auswertung
  gelesen** (Suche `event_log` unter `studio/`: nur `games.py`, `play.py`) [C].
- Herkunft: `bridge_jar_sha256`, Bridge-Zustand, Engine-Pin, `SIMULATED_RESULT` in jedem Log-Kopf
  (`play.py:258-282`, `games.py:323-333`) [C].

**Befunde, die die Charta treiben [C]:**

| # | Befund | Fundstelle | Folge |
|---|---|---|---|
| B1 | Pilot-Identität ist die Konstante `"GenericCommanderPilot 1.0.0"`; die Paar-Auswertung erkennt gemischte Piloten nur an dieser Zeichenkette | `play.py:60, 267`; `simulations.py:50`; `paired_comparison.py:309-313` | zwei Pilot-Stände sind nicht unterscheidbar; Basis-Wiederverwendung wäre ohne Fingerabdruck unsauber |
| B2 | Batch-Serie ersetzt ein unbekanntes Gegner-Deck still durch Lorehold Spirit bzw. die ersten drei Precons | `simulations.py:1419-1442` | Verstoß gegen „Settings, die ich einstelle“; die Paar-Serie lehnt korrekt ab (`paired_series.py:222-224`) |
| B3 | `seed_step` 1 bis 1000 einstellbar, Startsitz ist `seed % Spielerzahl` | `web.py:283`; `simulations.py:1456`; `full_game.py:1514` | Schritt 4 am Vierertisch = immer derselbe Startsitz |
| B4 | Batch misst das eigene Deck nur auf Sitz 0; Deckel 100 Partien je Web-Serie | `simulations.py:491-493`; `web.py:281` | Sitz-Rotation nur über den Startspieler; Web-Batch für Aussagen zu klein |
| B5 | Paar-Serie: höchstens 1.000 Paare, genau eine Variante | `paired_comparison.py:61`; `paired_series.py:680-700` | eine Nacht (2.400+ Paare) passt nicht in eine Serie; Achsen brauchen mehrere Serien mit doppelt gespielter Basis |
| B6 | Gegner nur Repo-Precons (173 Dateien) plus 2 Extras; eigenes Deck immer genau einmal; alle Deck-IDs verschieden | `launch.py:58-61, 628-665, 779-784`; `full_game.py:1696` | reales Meta des Owners nicht einstellbar |
| B7 | Batch-Kartenzähler: „offered“ = Karte war irgendwann auf der Hand (nicht: war wirkbar); „cast“ wird nur erkannt, wenn die Entscheidungsklasse `play_land`/`cast_spell` heißt, die Bridge kennt diese Klassen nicht (17 Klassen, Wirken läuft über `priority`) | `simulations.py:366-391, 538, 548`; `policy.py:28-48`; Test nutzt nachgebaute Klassen (`tests/unit/test_studio_simulations.py:137-140`) | `games_cast_after_offer`/`games_rotted` in `simulation_card` sind an echten Logs vermutlich leer bzw. gleich „auf der Hand“: am echten Log **nicht geprüft** (kein Log verfügbar) |
| B8 | Spielprotokoll speichert je Entscheidung nur die Zahl der Optionen | `games.py:248` | Auslassungen, „wirkbar und nicht gewirkt“, Audit nicht auswertbar (#1524 offen) |
| B9 | Auswertungen lesen „alle Logs im Ordner“ | `paired_comparison.py:482ff.` (`compare_logs`), `card_outcomes.py:835` | Vorgreifen über Looks und Wiederverwendung erzeugen Mischgefahr; Zugehörigkeit gehört ins Manifest |
| B10 | Jede gespeicherte Serie legt eine `source`-Zeile im Studio-Store an und bewegt die Datenepoche | `simulations.py:653-661`; Nebenbefund D-1 (#1612, Kommentar 7012608655) | SIMULATE-Ergebnisse invalidieren BUILD-Caches: eigene Datei |
| B11 | Zeitgrenzen sind sitzzahl-blind: 120 s je Anfrage, 50.000 Entscheidungen, 300 s je Partie im Chunk-Weg, 1.800 s im Pool, 75 s Settle in der Bridge | `full_game.py:1188-1189`; `simulations.py:745`; PR #1638 `game_pool.py:54`; `xmage_eff_fable.md` §1.3e | für 6 Sitze unter Last ungeprüft |

**Laufende Arbeit (Stand der Koordination):** D-2 P1 gemergt (#1629); Bridge-Fix #1625 gemergt (der Hänger aus #1584
ließ 4 von 80 Partien scheitern und die Serie mit `CENSORING_LIMIT` enden [M]; Rate nach dem Fix: UNKNOWN, neu messen);
PR #1638 offen. Offen: #1524 (Mitschnitt, Fingerabdruck), #1525, #1527, #1528, #1587 bis #1590, #1265.

## 4. Frage 1: regelkonform simulieren mit eingestellten Decks und Settings, 2 bis 6 (8) Sitze

### 4.1 Was Engine, Bridge, Piloten heute können

| Ebene | Grenze | Fundstelle |
|---|---|---|
| XMage-Spieltyp | `maxPlayers = 10`, `minPlayers = 3`; 2 Sitze über `CommanderDuel` | Fork `Mage.Server.Plugins/Mage.Game.CommanderFreeForAll/.../CommanderFreeForAllType.java:16-17`; `XmageCommanderGames.java:35-57` |
| Bridge | 2 bis 6; Einflussbereich `ALL`, Angriff `MULTIPLE` fest; Startleben 40 | `XmageFullGameSession.java:43`; `XmageGameManager.java:254`; `XmageCommanderGames.java:41-53`; `full_game.py:1515` |
| Python-Runner, Schema | 2 bis 6 | `full_game.py:278, 324, 1172-1173`; `full_game_batch.py:62`; `candidates/models.py:224-225` |
| Piloten | 2 bis 6 Laufzeit-Piloten, Sitz 1 bis 6 | `full_game_pilot/state.py:77`; `common.py:816` |
| Studio | Engine 2 bis 6, freigegeben 2 bis 4 (`--allow-unreleased-seats`) | `launch.py:32, 37, 751-765`; `play.py:120`; `web.py:252, 270, 1313` |
| Replay-Tape | 2 bis 5 | `semantic_replay/tape.py:49, 58, 98` |
| Bridge-Gate-Referenzsatz | nur Vierer-Tisch, Seeds 1 bis 36 | `docs/STUDIO_PLAN_SIMULATOR.md:58-66` |
| Seed und Startsitz | Startspieler `seed % Spielerzahl`; fortlaufende Seeds; getesteter Sitz rotiert über alle Sitze | `full_game.py:1514`; `paired_series.py:401-411, 773-775` |

Messlage je Sitzzahl:

| Sitze | Partiedauer | Entscheidungen | Speicher je JVM | Herkunft |
|---|---|---|---|---|
| 2, 3 | UNKNOWN | UNKNOWN | UNKNOWN | kein Bericht gefunden |
| 4 | warm 14,3 CPU-s (13,9 s Wand an Position 9), kalt 22 s | Mittel 2.715 (1.603 bis 4.399) | 0,84 bis 1,01 GB RSS (SerialGC), `-Xmx3g` nie erreicht | [M] `eff_sim_play.md` §2.1, §2.2, §2.6 |
| 5 | UNKNOWN | UNKNOWN | UNKNOWN | `SEATS_5_6_QUALIFICATION_PLAN.md` §3 |
| 6 | 161,9 s gegen 50,4 s (3,2-fach) und 111,1 s gegen 64,0 s (1,7-fach); je n=1, verschiedene Tische, älterer Stand | 2,4-fach bzw. 1,35-fach (n=4 gegen n=2) | UNKNOWN; Warnfälle: mehrere GiB im alten Mitschnitt-Weg, ein Stapel mit 3.696 Fähigkeiten | [M] `PLAYGROUP_LIVE_PHASE3_PLAYER_CAPACITY_4P_6P_8P_20261108.md` §3 |
| 7, 8 | kein einziger Lauf | – | – | ebd. §2: `PINNED_LAB_8P = BLOCKED_BY_ADMISSION_GATES` |

### 4.2 Was 5/6/7/8 Sitze kosten [S, Modell, nicht gemessen]

Annahmen: Partiezeit relativ zum Vierertisch aus den zwei 6er-Punkten (1,7 bis 3,2), 5 dazwischen, 7/8 fortgeschrieben
(Vermutung). Partienbedarf für denselben **relativen** Effekt bei Grundquote 1/N: n ∝ (1−p)/p = N−1.

| Sitze | Zeit je Partie | Partien für gleichen relativen Effekt | Kosten je Antwort | Partien je vollständigem Sitz-Block und Arm (N Seeds × N Sitze) | Partien/h auf der 4-Kern-VM (595 bei 4 Sitzen [M]) |
|---|---|---|---|---|---|
| 4 | 1 | 1 | 1 | 16 | 595 |
| 5 | 1,4 bis 2,2 | 1,33 | 1,9 bis 2,9 | 25 | 270 bis 425 |
| 6 | 1,7 bis 3,2 | 1,67 | 2,8 bis 5,3 | 36 | 185 bis 350 |
| 7 | 2,5 bis 5 (Vermutung) | 2,0 | 5 bis 10 | 49 | 120 bis 240 |
| 8 | 4 bis 7 (Vermutung) | 2,33 | 9 bis 16 | 64 | 85 bis 150 |

Was technisch nötig ist:
- **5/6:** keine Code-Grenze zu verschieben. Nötig sind Belege (4.3), sitzzahl-abhängige Zeitgrenzen (B11), ein
  Referenzsatz je Sitzzahl für das Bridge-Gate, und die Festlegung „6 Sitze ohne Replay-Anspruch“ (Tape endet bei 5).
- **7/8:** rund 15 Grenzstellen (13 in Python, 2 in Java, Tabelle 4.1; dazu das Tape) plus `partie.js`-Tischlayout; die Java-Änderung
  ist `BEHAVIOUR` unter dem Studio-Bridge-Gate, die Fähigkeitsliste in `config/rules_engines.json` ändert sich nur über
  das Ableitungs-Skript (`AGENTS.md` §4); der Owner-Entscheid „6 dauerhaftes Maximum“
  (`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`) müsste aufgehoben werden; keine menschliche Sitzkurve als Referenz
  (Playgroup nur Vierer-Partien); Pilot-Verhalten bei 5 bis 7 Gegnern nie gemessen (belegtes Muster: der spätere Sieger
  wird am wenigsten angegriffen, 33 von 36 Partien, `PILOT_STRENGTH_OPTIONS.md` §2.2 Nr. 9).

### 4.3 Wie die Freigabe 5/6 belegt würde (ohne sie vorwegzunehmen)

Der Prüfplan `SEATS_5_6_QUALIFICATION_PLAN.md` §4 bleibt die Grundlage; die Charta schneidet ihn auf ein Paket (E) zu.
Je Nachweis PASS / FAIL / UNKNOWN, getrennt für 5 und 6, getrennt für SIMULATE und PLAY:

| # | Nachweis | Abnahme |
|---|---|---|
| F1 | Festlegungen: `ALL` und `MULTIPLE` als Produkt-Einstellung; 6 Sitze ohne Replay-Anspruch | drei Sätze vom Owner (Teil der Freigabe-Vorlage) |
| F2 | Vollständigkeit: je Sitzzahl 2 Tische × 12 Seeds | 24/24 `game_over` oder jede Abweichung als Klasse benannt; alle Fragen in den 17 Klassen |
| F3 | Identität: gleicher Seed, 1 Worker gegen W Worker, Position in der JVM | n identisch von N, N ≥ 20, Hash, Sieger, Entscheidungszahl, Frame-Digest |
| F4 | Verdeckte Information je Sitz 5 und 6 | Test, der auf einem leckenden Frame fällt |
| F5 | Regelfälle (acht Prüfpunkte aus §2 des Plans: APNAP, Ausscheiden im Stapel/Kampf, Commander-Schaden je Paar, …) | je Punkt benannter Test oder `UNKNOWN` im Bericht; ein Fork-Befund geht an den Owner |
| F6 | Laufzeit 4/5/6 am selben, erweiterten Tisch, 10 Seeds, eine JVM je Partie und im Pool | Wandzeit, CPU-s, RSS-Spitze, p99-Latenz, Entscheidungen je Sitzzahl mit n; daraus Zeitgrenzen und Worker-Deckel |
| F7 | Piloten: Auslassungs-Zähler und Angriffsziel-Verteilung bei 5/6; Sitzkurve ohne Referenz ausgewiesen | Zählung n/N; „keine menschliche Referenz für 5/6“ steht im Gültigkeitsblock |
| F8 | Kleine gepaarte Serie je Sitzzahl mit voller Sitz-Rotation (36 bzw. 25 Partien je Block und Arm) | keine stillen Ausfälle; Zensur ausgewiesen |

Empfehlung: **Go zur Qualifikation 5/6 jetzt** (die Schalter `--allow-unreleased-seats` reichen für die Messung), Freigabe
nach dem Bericht. **7/8: nein für jetzt**; Auslöser für eine Neubewertung: 6er-Partie höchstens 3-fach so lang wie die
Vierer-Partie, RSS höchstens 2 GB je JVM, und der Owner spielt real Tische mit mehr als 6. Dann zuerst ein
Machbarkeits-Versuch (1 bis 2 Agent-Tage, Forschungs-JAR, 3 Seeds, außerhalb des Produkts).

### 4.4 Setting-Modell und Presets [V]

`TableSetup` (versioniertes JSON, sein SHA-256 steht in jedem Ergebnis), gemeinsam für SIMULATE und PLAY:

| Feld | Inhalt | Regel |
|---|---|---|
| Sitzzahl | 2 bis freigegebenes Maximum | Sperre wie heute (`launch.py:751-765`) |
| Deck je Sitz | eigener Deck-Stand, importierte Liste, Repo-Precon; Mensch-Sitz nur in PLAY | jeder Stand mit Hash; Vorab-Prüfung Engine und Pilotwissen; doppelte Decks über Suffix (`paired_series.py:753-756`) |
| Gegner-Modus | fester Tisch · Rotation über eine Liste von Tischen (je Block ausgeglichen) · Ziehung aus einem Pool mit eigenem, protokolliertem Seed | unbekanntes Deck = Fehler, nie Ersatz (B2) |
| Sitz-Politik | getestetes Deck rotiert über alle Sitze (Vorgabe) · fester Sitz | Sitz als Faktor im Ergebnis |
| Seeds | Block-Plan: fortlaufend, Zweck Erkundung / Bestätigung / Kontrolle; Seed-Register verhindert, dass Bestätigung auf Erkundungs-Seeds läuft | `seed_step` entfällt (B3) |
| Pilot-Profil je Sitz | Fingerabdruck, Stil, Stärke-Stufe | beide Arme gleich; gemischte Fingerabdrücke brechen die Auswertung ab |
| Budget und Stopp | Partien oder Wandzeit; feste Blockzahl, OBF-Looks, oder Zielbreite des Intervalls (nur Einzel-Arm); Zensurgrenze | vor dem Start festgelegt (Mindeststandard Punkt 9) |
| Partie-Grenzen | Entscheidungs-Deckel (spielbezogen); Wandzeit-Grenze je Sitzzahl (Infrastruktur, eigene Klasse) | aus F6 |
| Ausführung | „PC wird benutzt“ (Kerne − 1, niedrige Priorität) · „Nacht“ (alle Kerne) | berührt kein Ergebnis |

Presets (Zahlen für die 4-Kern-VM bei 600 Partien/h [M/S], Owner-PC UNKNOWN; nachweisbare Differenz =
2,8 × Streuung / √Paare, Streuung 0,33 [M, n=37] bis 0,63 [Planungswert, `full_game_comparison.py:70`], ohne Sitz-Design-Effekt):

| Preset | Umfang | Dauer | nachweisbar (Siegquote) | taugt für |
|---|---|---|---|---|
| Schnellcheck | 40 Paare | rund 8 min | 15 bis 28 pp | Rauchprobe, Positivkontrolle, Frühphasen-Kennzahlen mit großem Effekt |
| Abend | 600 Paare | 2 h | 3,8 bis 7,2 pp | Pakete mit großem Effekt |
| Nacht | 2.400 Paare | 8 h | 1,9 bis 3,6 pp | Bauachsen, Bestätigung |
| Kontrollen | Basis gegen Basis, absichtlich verschlechterte Liste | vor jeder Bestätigung | – | Rauschboden, Empfindlichkeit |

## 5. Frage 2: Tempo und Effizienz

### 5.1 Reale Obergrenzen

| Hebel | Gewinn | Beleg | Urteil |
|---|---|---|---|
| Langlebige JVM je Worker | 53,3 → 22,2 → 14,3 CPU-s je Partie (1 / 8 / dauerhaft warm); gepaart 350 → Obergrenze 967 Partien/h auf 4 Kernen | [M] `eff_sim_play.md` §2.2, §4.1 | **bauen** (PR #1638); Budget 56 je JVM kostet gegen „unendlich“ nur 63/56 = 1,1 CPU-s je Partie [S] |
| Warmhalten über Serien und für PLAY (Engine bleibt offen, solange das Studio läuft) | kurze Serien: bis 31 % der CPU [S, `d2_pool_design.md` §2.3]; PLAY-Start 6,3 s → Vermutung 1 bis 3 s | Modell | bauen nach Messung der wartenden JVM |
| Worker = Kerne bei ruhigem PC | +12 % (533 → 595, je n=1) | [M] | als Preset „Nacht“ |
| Basis-Wiederverwendung über den Spielschlüssel | −50 % Partien je weiterem Vergleich; Achse mit k Varianten: (k+1)/2k | Determinismus 424/424 [M] | **Kernfunktion** (Paket B), setzt B1 voraus |
| Gepaarte Serie mit Slot-Ausrichtung | Varianz 4,6-fach kleiner (Spanne grob 2 bis 11) | [M, n=37] | vorhanden; Planung mit gemessener Bandbreite (#1590) |
| Kennzahl-Wahl: „≥ 4 Länder in 11 Karten“ unterscheidet 36 gegen 33 Länder um 8,8 pp, rund 490 Partien je Arm; Siegquote braucht für 2 bis 4 pp eine Nacht | [S] `pilot_validity.md` §5.2 | **Stufenregel** L0/L1/L2 |
| L1 Frühphasen-Serie (Partie endet nach Runde T, volle Piloten, Sieg bewusst zensiert) | Vermutung 3- bis 4-fach mehr Partien/h; Anteil der Entscheidungen bis Runde 6: UNKNOWN | keine Messung | Messversuch, dann Owner-Entscheid (Rundenlimit ist owner-vorbehalten, `STUDIO_SCOPE.md:100-102`) |
| Mehrarmige Erkundung mit frühem Ausscheiden klar schlechterer Arme | spart Erkundungs-Partien | Standardverfahren, hier ungemessen | nur Erkundung; Bestätigung auf frischen Seeds mit Holm |
| Kontrollgrößen (Länder der Starthand, Startposition als bekannte Erwartungswerte) | Varianz × (1 − ρ²), ρ UNKNOWN, vermutlich klein | `simulate_methods.md` §3 (1) | später, billig |
| Bridge: Sortierschlüssel einmal je Element (C1) | Vermutung 2 bis 8 % der warmen JVM-CPU | [C] `xmage_eff_fable.md` §1.3b | erst Profil M0, dann `NEUTRAL`-PR ab 5 % |
| JDK 25 (AOT-Cache, kompakte Header) | Vermutung 3 bis 8 % warm | ungemessen | Messversuch; Laufzeit am Owner-PC ist Owner-Sache |
| Fork: Spielbarkeits-Kopie (F1) | höchstens rund 11 % | [M] #1298 | nur gebündelt mit einem ohnehin fälligen Repin |
| Python-Anteil der warmen Partie | 3,0 von 14,3 CPU-s = 21 % | [M] `eff_sim_play.md` §2.2 | nach dem Pool der nächste messbare Block (Sicht-Aufbau je Option, 24 KB JSON je Entscheidung); Pilot-Code ist MATERIAL, Nachweis über identische Transkripte |

Boden ohne Fork-Änderung: 14,3 CPU-s je warmer Vierer-Partie (11,3 java + 3,0 python) [M], also rund 250 Partien/h je
Kern dieser VM. Mehr geht nur über Kerne (Worker sind unabhängige Prozesse, 3,84 von 4 Kernen genutzt [M]) oder über weniger nötige
Partien. Owner-PC: Kerne, RAM, Java UNKNOWN; einziger Wert 541 Partien/h mit 6 Workern (#1251, vor #1316, anderer
Tisch); Swap bei 8 Workern auf 16 GB [M `d2_pool_design.md` §6].

### 5.2 Architektur: D-2 von Grund auf überdacht

| Alternative | Urteil | Grund |
|---|---|---|
| **Prozess-Pool, eine langlebige JVM je Worker** (D-2) | **ja** | größter belegter Gewinn, keine Bridge-Änderung, Fehler-Isolation je Prozess |
| Eine JVM, mehrere Partien gleichzeitig | **nein** | Gewinn wäre geteiltes Aufwärmen und RAM; bei langen Serien ist das Aufwärmen schon unter 10 %, bei kurzen leistet es das Warmhalten; Risiko: statischer veränderlicher Zustand in 2,1 Mio. Zeilen Kartencode, Protokoll-Multiplex ist Bridge-Änderung, `seed_scope: single_isolated_jvm_process` (`xmage_eff_fable.md` §3) |
| Vorausberechnung gemeinsamer Basis-Partien | **ja, als Archiv** | exakt, weil deterministisch; verlangt Fingerabdruck und Schlüssel |
| Varianten-Partie auslassen, wenn die Tauschkarten „nie berührt“ wurden | **nein** | 17 von 37 Paaren waren vollständig identisch [M], aber nicht vorab beweisbar: Scry, Bibliothekssuche und der aus der Liste abgeleitete Deck-Plan lesen die Tauschplätze ohne öffentliches Ereignis; ein gefolgertes Ergebnis wäre keine Messung |
| Zustand in der Engine verzweigen (Partie bis zur ersten Abweichung teilen) | **nein** | kein Zustands-Restore; Eingriff in den Aufbau des Regelzustands |
| Early Stopping | **vorhanden**, ergänzen um Zielbreite (Einzel-Arm) und frühes Ausscheiden (Erkundung) | `paired_comparison.py:554-729` |
| Parallelität in der Partie | **nein** | Engine und Pilot wechseln sich ab (1,03 Kerne warm [M]) |

**Abgleich mit PR #1638 (Head `3b3ef446`, +2.115 Zeilen, hinter `COMMANDER_LAB_STUDIO_SERIES_POOL=1`):**

- Deckt sich mit der Charta: Worker-Prozesse mit JVM über alle Look-Fenster, Zugmodell, gemischte Tische je Worker,
  eigener Ergebnistyp auf bestätigtem `shutdown_game` (E9), Budget höchstens 56, keine Wiederholung, Statistik unberührt.
- Fehlt gegenüber der Charta (Folgepunkte, kein Einwand gegen den Merge hinter dem Schalter):
  1. `GameTask` trägt nur `task_id`, `seed`, `game_id`, `deck_paths` (`game_pool.py:70-90`); der Worker ruft
     `prepare_game` ohne Stil, Sitz-Stile, Strategie (`:139-150`). Pilot-Profil je Sitz und Pilot-Arme sind so nicht
     transportierbar; jede Pool-Partie spielt still Stil 0,5. **Vor der Umstellung zum Standard** das Auftragsformat um
     Tisch-Einstellung, Deck-Hashes, Fingerabdruck und Spielschlüssel erweitern, sonst wird es später eine Migration.
  2. Kein Spielschlüssel, kein Journal, kein Manifest, keine Prüfung der Deck-Datei gegen einen Hash vor der Partie,
     kein Determinismus-Wächter (im Entwurf §1.1, §3, §5.2 vorgesehen).
  3. Batch-Serie ist noch kein Kunde; ein Verwalter und die Lastregel fehlen (als Folgepunkt benannt).
  4. Wandzeit-Grenze fest 1.800 s (`game_pool.py:54`), nicht je Sitzzahl; für 5/6 aus F6 ableiten.
  5. Echt-Engine `NOT_RUN`: Identität je Partie, `game_over` im Ack nach natürlichem Ende (U-10), Durchsatz. Solange das
     offen ist, ist der Pool unbelegt; mit #1625 gemergt ist der Ausgangswert ohnehin neu zu messen.
  6. Fenster bleibt Schranke. Mit Archiv und Manifest (Paket B) darf der Pool Basis-Partien des nächsten Fensters
     vorziehen, weil sie keinem Ergebnis zugerechnet werden, bevor das Manifest sie aufnimmt.

## 6. Frage 3: Piloten „möglichst optimal“

### 6.1 Stand [C, Berichte gelesen, nicht nachgemessen]

- Heuristik ohne Suche: 17 Entscheidungsklassen, unbekannte Klasse bricht ab (`policy.py:24-48`); Nutzenformel mit 11
  Komponenten, eigene Ranker für Angriff, Block, Land, Zahlung, Mulligan (`agents/pilots.py`, 2.289 Zeilen;
  `full_game_pilot/`, 6.543 Zeilen); Studio: `NEAR_OPTIMAL_HEURISTIC`, `DETERMINISTIC`, Stil 0 bis 1 als
  Gewichts-Interpolation, Deck-Plan „abgeleitet, nicht gemessen“ (`play.py:234-250`).
- Belegte Schwächen (`PILOT_STRENGTH_OPTIONS.md` §2.2; `pilot_validity.md` §1.3): kein einziger Instant im gegnerischen
  Endschritt in 24 Partien, in 468 von 660 Fällen zu wenig Mana für gehaltene Interaktion; 26 unnötige Chump-Blocks in
  36 Chulane-Partien; 136 von 2.948 Zahlungen abgebrochen; Sieger am wenigsten angegriffen (33 von 36); Sitzkurve 38,8 /
  10,4 % (Sitz 1 / 4, 183 Pods, älterer Stand) gegen 29,1 / 21,5 % real; Chulane 5 von 36; einzelne Karten fast nie
  gewirkt (Wilderness Reclamation 11 von 16).
- Jede bisherige Muster-Korrektur ließ die Siegquote „UNDECIDED“; Wirkung von #1442 UNKNOWN; Fehlerquote je
  Entscheidung nie gemessen; Stärke gegen Menschen UNKNOWN.
- Vorausschau von außen (S1): 2/6 gegen 1/6 Siege, 12,9-fache Partiezeit, mit echter Bibliotheksreihenfolge (Obergrenze)
  (`docs/performance/LOOKAHEAD_SPIKE_S1_2026-11-11.md`).
- Rechenzeit: Pilot 8,2 % der Wandzeit, Median unter 1,3 ms je Entscheidung [M `eff_sim_play.md` §2.5].
- Messvoraussetzungen fehlen: Fingerabdruck (B1), Optionen im Log (B8), Audit-Mitschnitt im Studio-Pfad (#1524).

### 6.2 Was „optimal“ messbar heißt [V]

Ein objektiv bester Zug ist für Commander mit vier Spielern nicht bestimmbar (keine überlegene Referenz,
`pilot_validity.md` §2). „Möglichst optimal“ wird deshalb als drei Zahlen je Pilot-Fingerabdruck geführt:

| Maß | Inhalt | Kosten |
|---|---|---|
| (a) Fehler-Obergrenze | Pilot-Audit: 240 wertbare Entscheidungen aus 24 Partien, Schweregrade, Goldfälle (G-SIM Punkt 2, angenommen) | Owner 2 bis 2,5 h; gilt je Fingerabdruck |
| (b) Verschwendung | je Serie und Sitz, n/N: Landdrop angeboten und nicht genommen, wirkbarer Zauber bei ungenutztem Mana nicht gewirkt, ungenutztes Mana je eigenem Zug, Handkarten am Ende, Karte „angeboten und nie gewirkt“ je Karte | automatisch; braucht die Namen der angebotenen wirkbaren Optionen im Frame (reine Python-Änderung am Mitschnitt) |
| (c) relative Stärke | Pilot A gegen Pilot B als Arme desselben Experiments: gleiche Decks, gleiche Seeds, nur der Pilot des getesteten Sitzes wechselt; über ein festes Panel von mindestens 6 Decks einschließlich Chulane | Rechenzeit einer Abend- bis Nachtserie; dieselbe Maschinerie wie Deckvergleiche |

Dazu als Plausibilität, nie als Tor: Sitzkurve gegen Playgroup, Precon-Siegquoten gegen reale Raten, Urteil des Owners
aus PLAY-Partien (AK-8).

### 6.3 Strategie, Kosten, Nutzen

| Weg | Nutzen | Kosten und Risiko | Entscheid |
|---|---|---|---|
| Heuristik mit Messschleife: je Muster ein Fix, Abnahme (c) ≥ 0 und (b) im Muster besser | billig, sofort; schließt belegte Lücken (Interaktion im Endschritt, Chump-Blocks, Angriffsziel) | Einzelfall-Pflege, Überanpassung an das Panel; jede Änderung MATERIAL; bisher kein messbarer Stärkegewinn | **jetzt**, 1 bis 2 Agent-Tage je Muster; **Abbruch nach drei Mustern ohne messbaren Gewinn in (c)** |
| Vorausschau durch die Engine (S5, #1265) | einziger Weg mit Literaturbeleg für große Sprünge (Monte Carlo ab 10 Simulationen 25–33 % → 61 %, vereinfachtes Magic, `PILOT_STRENGTH_OPTIONS.md` §3) | Bridge `BEHAVIOUR`, Neuverteilung verdeckter Zonen, eigener Zufall, Test verdeckter Information: geschätzt 8 bis 15 Agent-Tage; Laufzeit: jede Folge-Entscheidung in der Kopie läuft über Python (D17), bei 5 bis 8 ms je Entscheidung kostet eine Probe über eine Runde Sekunden; S1 brauchte 12,9-fach | **nicht als Serien-Pilot**. Später als Messinstrument (Bedauern je Stichproben-Entscheidung als zweite Stimme im Audit) und als Stärke-Option in PLAY, wo Sekunden je Zug nicht stören. Entscheid nach Paket C und G |
| Lernen | Daten wären da (eine Nacht ≈ 15 Mio. Entscheidungen) | Lernen aus eigenen Partien lernt die eigene Heuristik; echtes Verstärkungslernen braucht Suche und neue Abhängigkeiten | **zurückstellen**. Zulässig ohne Laufzeit-Abhängigkeit: Gewichte der Nutzenformel offline über gepaarte Selbstspiel-Serien abstimmen und als Datendatei ausliefern (Vorbild: das Mulligan-Modell ist bereits eine Anpassung, `agents/pilots.py:343-353`); erst nach (c) |

### 6.4 Wie schlechte Piloten keine Deckurteile verfälschen [V]

1. **Herkunftsklasse an jeder Kennzahl** (Konsistenz-Tafel): exakt gerechnet · in der Engine gemessen und
   pilotunabhängig (zuerst ausgeteilte Hand, natürliche Züge) · pilotabhängig (Siegquote, Wirk-Zeitpunkte). Urteile
   stützen sich zuerst auf die oberen Klassen.
2. **Gleicher Fingerabdruck in beiden Armen**, erzwungen; ein allgemeiner Pilotfehler hebt sich in der Paarung auf.
3. **Karten-Kompetenzprüfung je Serie:** für jede Karte, die sich zwischen den Armen unterscheidet, „wirkbar angeboten
   und nie gewirkt“ n/N. Über der Schwelle (Setzung: mehr als die Hälfte der Partien mit Angebot) lautet das Ergebnis
   „Pilot kann die Karte nicht spielen“, ohne Kartenurteil (`pilot_validity.md` §4.7).
4. **Pilot-Stil als Blockfaktor in der Bestätigung:** die Hälfte der Seed-Blöcke mit Stil 0,25, die andere mit 0,75
   (kostet keine zusätzliche Partie). Kippt das Vorzeichen, heißt das Ergebnis „pilotabhängig, nicht entschieden“.
5. **Kontrollen je Frage:** eine absichtlich verschlechterte Liste (Positivkontrolle) und eine Negativkontrolle;
   scheitert die Positivkontrolle, gilt die Serie nicht. Hinweis: „Basis gegen inhaltsgleiche Kopie“ ist bei
   deterministischer Engine und gleicher Listenreihenfolge vermutlich exakt 0 (abgeleitet aus 424/424 [M], nicht
   geprüft) und misst dann kein Rauschen; als Negativkontrolle taugt eine neutrale Änderung (funktionsgleicher Tausch
   oder dieselbe Liste auf einem zweiten, unabhängigen Seed-Block). Das ist vor #1528 zu klären.
6. **Rollen-Ausschluss aus dem Audit:** eine auffällige Entscheidungsklasse (zum Beispiel Antwortfenster) schließt die
   zugehörigen Kartenrollen (Counter, Schutz, Flash) von Aussagen aus.
7. **Fester Satz am Ergebnis** (Gültigkeitsblock): Pilot-Fingerabdruck, Stil, Sitzzahl, Tische, Pin, JAR-SHA,
   Bridge-Zustand, Verschwendungs-Zähler, Sitzkurve neben der Referenz, Audit-Stand oder „nicht auditiert“.
8. **Ehrliche Reichweite:** Pakete und Bauachsen, keine Einzelkarten-Urteile aus Siegquoten (2 pp je Karte brauchen
   rund 56.000 Partien, `pilot_validity.md` §5.4).

## 7. Frage 4: Ergebnisse speichern, die beim Deckbau helfen

### 7.1 Datenmodell [V]

Eigene Datei `simulate.sqlite3` im Studio-Datenordner (keine neue Abhängigkeit; trennt SIMULATE von der Datenepoche des
Studio-Stores, B10). Jede Tabelle trägt `data_class = SIMULATED_RESULT`.

| Tabelle | Schlüssel und Inhalt |
|---|---|
| `engine_build` | JAR-SHA-256, Engine-Pin, Bridge-Zustand gegenüber dem Siegel, Java-Version |
| `pilot_profile` | Fingerabdruck = SHA-256 über die verhaltensbestimmenden Dateien (`agents/`, `engine/rules/full_game_pilot*`, `data/cards/pilot_card_knowledge.json`, Kombo- und Guide-Dateien, Zeilenenden normalisiert) plus Stil und Stärke-Stufe |
| `table_setup` | Hash der Tisch-Einstellung (4.4), JSON |
| `experiment` | ID, Zweck (Erkundung, Bestätigung, Kontrolle), Frage, erwartete Richtung, Plan-JSON und Plan-SHA (vor der ersten Partie geschrieben), Kennzahl-Familie, Stopp-Regel, Status |
| `arm` | Experiment, Rolle (Basis, Variante, Kontrolle), Deck-Stand, Deck-Hash, Hash der ausgerichteten Liste, Pilot-Profil |
| `game` | **`game_key`** = SHA-256 über JAR-SHA, Pin, Pilot-Fingerabdrücke und Stile je Sitz, Deck-Hashes in Sitzfolge, Seed, Sitzzahl, Tisch-Optionen, `skipForcedDecisions`, Rundengrenze; dazu Status, Fehlerklasse (Spiel oder Infrastruktur), Sieger, Entscheidungen, Runden, Transkript-Hash, Wandzeit, JVM-Leben und Position, Log-Pfad, Log-SHA, „Log verworfen“ |
| `experiment_game` | Experiment, Arm, Block (Seed), getesteter Sitz, `game_key`, Reihenfolge: **die** Zugehörigkeit; eine Partie kann zu mehreren Experimenten gehören |
| `seat_result` | je Partie und Sitz: Deck-Hash, Ergebnis, Sieg-Anteil, Platz-Wert (`finishing_scores`, `full_game_comparison.py:976`), Runde des Ausscheidens, Mulligans, Länder der zuerst ausgeteilten Hand, Länder im Spiel je eigenem Zug 1 bis 8, erster Commander-Cast (zensiert), Schaden ausgeteilt und erhalten, Commander-Schaden je Gegner, Ursache des Ausscheidens |
| `seat_card` | je Partie, Sitz und **gesehener** Karte (nur getestete Sitze): in der ersten Hand, erstmals auf der Hand in Zug t, wirkbar angeboten in k Zügen, erster Cast (zensiert), Anzahl Casts, am Ende auf der Hand |
| `finding` | je Experiment und Kennzahl: Schätzwert, Intervall, n/N, nachweisbare Differenz, Herkunftsklasse, Reifegrad, Gültigkeitsblock, betroffene Deck-Stände und Karten |

Entscheidungen und Ereignisse bleiben im Partie-Log (gzip-JSONL), nicht in der Datenbank. Der volle Audit-Mitschnitt
(alle legalen Optionen und die Platz-Sicht) nur auf Anforderung für Audit-Serien: 24 KB JSON je Entscheidung, 41 MB je
Partie roh [M `eff_sim_play.md` §2.5]. Wächter: derselbe `game_key` mit zwei verschiedenen Transkript-Hashes beendet
das Experiment mit `DETERMINISM_VIOLATION`.

### 7.2 Größe, Aufbewahrung, Schwärzung, Replays

- Größe [M/S]: Log 52 bis 219 KB je Partie, Mittel 117 KB; eine Nacht mit 5.000 Partien rund 0,6 GB Logs. `seat_card`
  für die getesteten Sitze rund 30 Zeilen je Partie, 150.000 Zeilen je Nacht, Größenordnung 10 bis 20 MB [S].
- Aufbewahrung [V]: Fakten und Befunde dauerhaft. Logs sind Cache mit Kontingent (Vorgabe 20 GB): dauerhaft bleiben
  Logs von Bestätigungs-Serien, diskordante Paare, gescheiterte Partien und eine Stichprobe je Experiment; der Rest
  wird nach der Fakten-Extraktion verworfen und markiert. Weil Partien deterministisch sind, ist jede verworfene Partie
  aus ihrem Schlüssel neu erzeugbar, solange JAR (nach SHA abgelegt) und Pilot-Stand (Commit im Profil) vorliegen.
  **Replay heißt deshalb „neu erzeugen und in der Partie-Ansicht ansehen“**, keine eigene Replay-Ablage.
- Schwärzung: Serien ohne Mensch-Sitz enthalten die Hände aller KI-Sitze; lokal zulässig (`AGENTS.md` §12, E5 Punkt 1).
  Schwärzung betrifft nur laufende PLAY-Partien und Fehlermeldungen. Für gescheiterte Partien eine lokale,
  ungeschwärzte Diagnose-Datei außerhalb des Repositorys (die geschwärzte Diagnose hat #1584 verzögert).
- Sicherung: `backup.py` sichert Store und `games/` bereits (`backup.py:76-113`); `simulate.sqlite3` kommt dazu.

### 7.3 Welche Auswertungen Deckbau-Funktionen werden [V]

| Funktion im Deckbauer | Quelle | Klasse | Stand |
|---|---|---|---|
| Stand gegen Vorgänger: Sieg-Anteil und Platz-Wert je Deck-Stand mit Intervall, gepaarte Differenz, nachweisbare Differenz | `finding`, `seat_result` | pilotabhängig | Paar-Ergebnis vorhanden, Anzeige im Verlauf teilweise |
| Achsen-Experiment (Landzahl 33 / 36 / 39, Kontrollen 36 gegen 36 und 27) mit Dosis-Wirkungs-Bild und exakter Gegenprobe gegen die Hypergeometrie | mehrarmiges Experiment, L0 | exakt + gemessen | neu (#1528) |
| Mana-Bericht: Länder im Spiel je Zug, verpasste Landdrops, Farbprobleme (Karte nach Manawert bezahlbar, aber nicht angeboten), ungenutztes Mana | `seat_result`, Frames mit angebotenen Optionen | überwiegend pilotunabhängig | neu |
| Kurve: erster Commander-Cast, Mana ausgegeben gegen verfügbar je Zug, Handkarten am Ende; Zeiten immer mit „nicht erreicht in n von N“ | `seat_result` | pilotabhängig | Quartile mit Zensur vorhanden (`simulations.py:466-480`) |
| Karten-Wirkung: in der ersten Hand gegen nicht; gezogen bis Zug T; gewirkt und Zeitpunkt; „angeboten und nie gewirkt“ als Pilot-Signal, nie als Kartenurteil | `seat_card`, `card_outcomes.py` | erste Hand pilotunabhängig, Rest pilotabhängig | erste Hand vorhanden; B7 ersetzen |
| Matchup-Tabelle: je Tisch und je Gegner-Deck Sieg-Anteil n/N, wer hat mich eliminiert, Commander-Schaden von wem | `seat_result`, Ereignisprotokoll | pilotabhängig | je Tisch vorhanden (`builder.py:1066`), je Gegner neu |
| Schwachstellen-Bericht: Art und Runde des Ausscheidens, welche eigenen Schlüssel-Permanente zerstört wurden, erlittene Massenentfernung, Gegnerkarten mit Verlust-Korrelation (als Korrelation beschriftet) | Ereignisprotokoll (heute ungenutzt) | pilotabhängig | neu |
| Tausch- und Schnitt-Labor: Befund als Evidenz-Zeile an der Karte bzw. am Paket, mit Reifegrad | `finding` | je Befund | neu |

### 7.4 `SIMULATED_RESULT` und die Regel „Gewicht 0 bis G-SIM“: überdacht

Befund: Die Regel behandelt die falsche Frage. Ein Simulationsergebnis gilt für **diesen Deck-Stand, diese Tische, diesen
Piloten**; die Tierliste ist eine Rangfolge über den ganzen Kartenpool eines Commanders. Ein Karten-Gewicht ist mit
realistischem Budget nicht tragfähig (eine Nacht gibt je Karte ±4,5 pp; 2 pp brauchen rund 56.000 Partien, mit
Mehrfachvergleich rund 126.000; Signal nur für die höchstens 99 Karten der gespielten Liste: `pilot_validity.md` §5.4).
Der Owner-Zweck „Simulation soll beim Deckbau helfen“ wird durch ein Tor vor der Tierliste nicht erfüllt, sondern
aufgeschoben.

Empfehlung [V]:
1. `simulation` als Komponente des Tierlisten-Index **entfernen** (nicht „0 bis G-SIM“); Stufe 2 (Gewicht größer 0)
   streichen. Der Test `test_studio_simulation_weight_zero.py` wird zum Test „der Index kennt keine
   Simulations-Komponente“.
2. Simulation erscheint **sofort** als eigene Evidenz-Schicht in den Entscheidungsansichten des Deckbauers (Diff,
   Tausch-Labor, Verlauf), nie in einer Spalte oder Summe mit EDHREC-, Playgroup- oder Turnier-Zahlen, nie über
   Deck-Stände oder Commander summiert; ein Befund zu einem anderen Deck-Stand wird als solcher gezeigt.
3. Der Inhalt von G-SIM bleibt, aber als **Reifegrad am Befund** statt als Tor: R0 Erkundung · R1 bestätigt (frische
   Seeds, Holm) · R2 bestätigt mit bestandenen Kontrollen und Kompetenzprüfung · R3 zusätzlich Pilot-Audit bestanden für
   diesen Fingerabdruck und Bridge durch Siegel gedeckt oder vom Owner „vor Qualifikation“ angenommen.
4. In **Empfehlungen** (Tausch-Vorschläge) darf ein Befund ab R2 einfließen, wenn er zum aktuellen Deck-Stand oder
   einem direkten Vorgänger gehört und Fingerabdruck und JAR aktuell sind; sonst erscheint er ausgegraut mit Grund.
5. Stufe 1 (Marker an Tierlisten-Karten eines bestätigten Paket-Ergebnisses, ohne Gewicht, ohne Sortierung) bleibt als
   späte Option nach R3.

Das ändert O3/E2 und braucht die Owner-Zustimmung (Frage 3).

## 8. Entfernen, ersetzen, zurückstellen

| Was | Urteil | Grund |
|---|---|---|
| Getrennter Batch-Weg (`BatchSimulation`, `plan_chunks`, `_process_chunk`) | ersetzen durch Experiment mit einem Arm über den Pool | drei Orchestrierer, zwei Ablageformate (`d2_pool_design.md` §5.1) |
| `simulation_run`, `simulation_card` im Studio-Store als Schreibziel | ersetzen durch `simulate.sqlite3`; alte Zeilen bleiben lesbar | B7, B10; nur Aggregat, kein Partie-Bezug |
| `PILOT_VERSION`/`PILOT_POLICY` als Identität | ersetzen durch Fingerabdruck | B1 |
| `seed_step`; stiller Gegner-Ersatz | entfernen | B2, B3 |
| Deckel 100 Partien (Web-Batch), 1.000 Paare | ersetzen durch Zeit- und Kontingent-Budget | B4, B5 |
| Auswertung über Ordner-Scan | ersetzen durch Zugehörigkeit im Manifest | B9 |
| Ungemessene Annahme 540 Partien/h je Worker (`paired_series.py:68`) | entfernen; Dauer aus dem gemessenen Durchsatz dieses PCs | #1588 |
| `simulation`-Gewicht, Stufe 2 | entfernen (Owner) | 7.4 |
| Vorausschau als Serien-Pilot; Lernen; 7/8 Sitze; Fork-Tempo; mehrere Partien je JVM gleichzeitig | zurückstellen bzw. verwerfen | 4.2, 5.2, 6.3 |
| Eigene Replay-Funktionen für Serien | nicht bauen; Partie-Ansicht von PLAY (#1619) plus Neu-Erzeugen | 7.2 |
| Datensammlung als Referenz für SIMULATE (#1556) | auf die Sitzkurve und Precon-Raten begrenzen | nur Plausibilität |

## 9. Paket-Schnitt, Reihenfolge, Abnahme

| # | Paket | Inhalt | Agent-Tage | Abnahme |
|---|---|---|---|---|
| 0 | Laufend | PR #1638 mit Echt-Engine-Lauf; D-2 P5 (ein Verwalter, Lastregel); Neumessung nach #1625 | im D-2-Budget (6,5 ±40 %) | Identität 36/36 und gemischte Tische; gepaart ≥ 560 gestartete Partien/h auf der 4-Kern-VM; Hänger-Rate n/N neu |
| A | Tisch und Plan | `TableSetup`, Presets, Gegner aus Deck-Ständen, Fingerabdruck (aus #1524), Plan-Datei mit Armen, Zweck, Stopp-Regel, Seed-Register (#1525); Auftragsformat des Pools erweitert; B2, B3 entfernt | 4 bis 5 | ein Plan-JSON erzeugt dieselbe Serie über Web und CLI; unbekannter Gegner → Fehler; Fingerabdruck ändert sich bei jeder Änderung einer Pilot-Datei (Test); Stil je Sitz kommt im Log-Kopf der Pool-Partie an |
| B | Archiv und Fakten | `simulate.sqlite3`, `game_key`, `experiment_game`, Extraktor (Frames und Ereignisprotokoll), Wiederverwendung (#1589), Wächter, Kontingent, Sicherung | 4 bis 5 | derselbe Plan zweimal: zweiter Lauf spielt 0 Partien; zweite Variante spielt nur Varianten-Partien; Extraktor gleich `card_outcomes` auf vorhandenen Logs; Speicher je 1.000 Partien berichtet |
| D-min | Ergebnisseite | Befund mit Intervall, nachweisbarer Differenz, Herkunftsklasse, Gültigkeitsblock, Reifegrad; mehrarmige Auswertung mit Holm (Engine-Lane wiederverwenden) | 2 bis 3 | Landzahl-Achse mit beiden Kontrollen und exakter Gegenprobe am Owner-PC (#1528, Abschlusskriterium 2) |
| C | Pilot-Messrahmen | Pilot-Arme, Verschwendungs-Zähler, angebotene Optionen im Frame, Kompetenzprüfung, Audit-Mitschnitt auf Anforderung | 3 | Serie Pilot A gegen Pilot B läuft; Zähler n/N je Serie; Kompetenz-Kennzeichen am Befund |
| E | Sitze 5/6 | F1 bis F8, Zeitgrenzen je Sitzzahl, Referenzsatz je Sitzzahl | 3 bis 4, dazu 2 bis 3 h Rechenzeit | Bericht je Nachweis; Freigabe trifft der Owner |
| D | Deckbau-Ansichten | Mana-Bericht, Kurve, Karten-Wirkung, Matchup je Gegner, Schwachstellen-Bericht, Evidenz im Diff und Tausch-Labor (#1527) | 4 bis 5 | zwölf Punkte des Mindeststandards je mit Test oder Beispielergebnis; jede Zahl mit n/N und Klasse |
| F | Tempo | Owner-PC-Messung (#1588), Vorgabe Partien je JVM (#1587), Warmhalten, Profil M0 und gegebenenfalls C1, L1-Messversuch | 2 bis 3 | Durchsatz-Tabelle am Owner-PC mit Identität; L1: Anteil der Entscheidungen bis Runde T gemessen |
| G | Pilot-Schleife | je Muster ein Fix mit gepaartem Nachweis | 1 bis 2 je Muster | (c) ≥ 0 über das Panel, (b) im Muster besser |

Summe neu: 21 bis 26 Agent-Tage ohne G, zusätzlich zu D-2. Jedes Paket hält den Äquivalenznachweis (gleicher Schlüssel,
gleicher Transkript-Hash) und läuft als MATERIAL mit Review auf exakter Head-SHA. Keine Bridge-Änderung in A bis D; E
nur Tests und Messung; F/C1 unter dem Studio-Bridge-Gate.

## 10. Risiken und Abbruchkriterien

| Risiko | Beleg | Abbruch oder Gegenmaßnahme |
|---|---|---|
| Identität bricht bei langem JVM-Leben oder gemischten Tischen | nur gleiche Tische und Position ≤ 16 gemessen [M] | Rückfall „ein Tisch je JVM-Leben“, Budget 16; Wiederverwendung aus, bis erklärt |
| Hänger oder andere Fehlerklassen zensieren weiter über 5 % | 4/80 vor #1625 [M] | Serie endet ehrlich `CENSORING_LIMIT`; Fehlerklasse je Tisch ausweisen; betroffene Tische aus Presets nehmen |
| Effekte liegen unter der nachweisbaren Differenz | 1,9 bis 3,6 pp je Nacht [S] | Ergebnis „kein nachweisbarer Unterschied bei n“; Frage auf L0/L1 umstellen |
| Pilot-Fixes zeigen wieder keinen messbaren Gewinn | bisher alle „UNDECIDED“ | nach drei Mustern stoppen, S5-Entscheid vorlegen |
| Paarungs-Gewinn gilt nicht allgemein | n=37, ein Deckpaar | Planung mit Bandbreite; Diskordanz in jedem Ergebnis |
| 5/6: Regelfehler im Fork | #1628 (offen) meldet einen Kampf-Regelfehler am Pin (nicht nachgeprüft) | Fork-Änderung ist Owner-Sache; betroffene Sitzzahl bleibt gesperrt |
| Windows: verwaiste JVMs, Sperren, Virenscanner | kein Windows-Lauf im Repository | Pool wird erst nach dem Owner-PC-Lauf Standard |
| Speicher am Owner-PC | 16 GB, Swap bei 8 Workern [M] | Worker-Deckel aus RAM; Kontingent für Logs |
| Kollision mit D-2/D-3 (`paired_series.py`, `full_game.py`, `web.py`) | #1612 | Paket A beginnt nach dem Merge von #1638; Claim je Paket |
| Paket über Budget | – | über 50 % Überschreitung: Paket teilen, Rest zurückstellen (Regel aus #1612) |

## 11. UNKNOWN

- Owner-PC: Kerne, RAM, Java-Version, Durchsatz nach #1316 und mit Pool; Windows-Verhalten des Pools.
- Laufzeit und Speicher bei 2, 3, 5 Sitzen; RSS bei 6; alles zu 7 und 8.
- Hänger-Rate nach #1625; ob `shutdown_game` nach natürlichem Ende immer `game_over: true` meldet (U-10).
- Ob B7 an echten Logs zutrifft (kein Log in dieser Sitzung verfügbar).
- Paarungs-Gewinn für andere Deckpaare, mehr Tauschkarten, andere Sitzzahlen; Korrelation innerhalb eines Seed-Blocks.
- Anteil der Entscheidungen bis Runde 6 (Nutzen von L1); ob eine Partie mitten im Spiel sauber beendet werden kann,
  ohne die JVM zu verwerfen.
- Anteil wertbarer Entscheidungen je Partie; Fehlerquote des Piloten; Stärke gegen Menschen; Wirkung von #1442.
- Ob das Ereignisprotokoll für die Kennzahlen in 7.3 vollständig ist (Zieh-Ereignisse tragen verdeckte Identität; die
  Hand kommt aus den Frames des Sitzes).
- Welche Decks der Owner real am Tisch sieht (Gegner-Pool).
- Ob der Stil das Vorzeichen eines Deck-Effekts kippen kann.

## 12. Offene Owner-Fragen (mit Empfehlung)

1. **Sitze:** Go zur Qualifikation von 5 und 6 Sitzen jetzt (Paket E), Freigabe je Sitzzahl nach dem Bericht; 7 und 8
   zurückgestellt bis zur 6er-Messung? **Empfehlung: ja.**
2. **Gegner-Decks:** Dürfen beliebige Deck-Stände und importierte Listen des Studios als Gegner-Sitze dienen (Chulane
   bleibt das einzige Deck, das optimiert wird)? **Empfehlung: ja.**
3. **Tierliste:** `simulation` als Index-Komponente und Stufe 2 streichen; Simulation stattdessen sofort als Evidenz
   mit Reifegrad im Deckbauer (ändert O3/E2)? **Empfehlung: ja.**
4. **Frühphasen-Serie (L1):** rundenbegrenzte Serien mit vollen Piloten als eigener, beschrifteter Experiment-Typ für
   Mana-, Kurven- und Konsistenz-Fragen (Rundenlimit ist bisher owner-vorbehalten)? **Empfehlung: ja, nach einem
   Messversuch.**
5. **Piloten:** Vorausschau nicht als Serien-Pilot, Pilot-Änderungen nur mit gepaartem Nachweis, Pilot-Audit (2 bis
   2,5 Stunden Owner-Zeit) erst nach der ersten Nachtserie und nicht als Vorbedingung für die Deckbau-Ansichten?
   **Empfehlung: ja.**
