# Charta BUILDER (Commander Studio): Deck-Werkbank mit Prüfstand

Lane BUILDER, 2026-11-19. Basis: `main` @ `0792a59b` (Clone Tiefe 200; Zeilenangaben gelten für
diesen Stand), nachgezogen auf `8f46af28` für TAM (#1640) und die Merges #1611, #1616, #1620,
#1627, #1632. Berichte auf `origin/docs/fable-sonnet-haiku-reports`; Issues #1187, #1635, #1636,
#1645, #1612 gelesen. Nur gelesen: keine Suite, kein Engine-Lauf, nichts gepusht. Pfade ohne
Präfix liegen unter `src/commander_lab/studio/`. Legende: **[C]** im Code gelesen (Datei:Zeile),
**[D]** Doku/Bericht/Issue sagt es, **[R]** eigene Rechnung, **[V]** Vermutung.

**Geänderte Lage seit dem Briefing.** Der Owner hat am 2026-11-19 TAM (Tam, the Possibility,
fünffarbig) als zweiten Commander für BUILD wieder aufgenommen und Zukäufe als Funktion erlaubt,
zunächst ohne Preise (#1187, Kommentar 7018395774). „Nur Chulane“ gilt damit für PLAY/SIMULATE
und als Referenz, nicht mehr für den Builder. Die Charta ist darauf umgestellt (Abschnitt 3.3,
Entscheidungen B12 bis B14).

## 1. Ergebnis zuerst

1. **Leitbild:** Der Builder ist eine **Deck-Werkbank mit Prüfstand**, keine Kartenrangliste, und
   er ist **commander-neutral**: Chulane und TAM laufen durch dieselben Flächen, jede Zahl ist an
   Commander und Kohorte gebunden. Die tragenden Objekte sind Stand (Revision) → Änderung (Diff)
   → Experiment → Entscheidung. Heute ist er eine Auskunftssammlung: 5 Seiten, 16 Deck-Tabs, rund
   120 Routen, sieben getrennte Vorschlagsquellen, fünf Skalen für „wie gut ist die Karte“ [C].
2. **Der Bestand trägt mehr als gedacht.** Unveränderliche Stände mit Hash, Entwurf, Varianten,
   Diff-Wirkung, exakte Mana-Rechnung, Korpus aus 10.150 Chulane-Decks, Kombos, Engine-Prüfung,
   gepaarte Serien mit nachweisbarer Differenz und Karten-Auswertung sind gebaut [C/D]. Es fehlt
   die Verbindung: Es gibt kein Experiment-Objekt, kein „Übernehmen“, und Partien kennen ihren
   Deck-Stand nicht.
3. **Wichtigster Defekt:** Die Karten-Auswertung zählt je `deck_id`, nicht je Stand. Der Sitz-Kopf
   des Spielprotokolls trägt keinen Deck-Hash (`play.py:270-281`), `simulation_run` hat keine
   Revisionsspalte (`store.py:334-351`). Partien verschiedener Stände desselben Decks landen in
   einer Zahl; die Seite schreibt selbst „Deck-Stand der Partien unbekannt“
   (`static/kartenauswertung.js:42-45`).
4. **Ehrliche Reichweite der Simulation [R]:** Eine Nacht (5.400 Partien, etwa 10 h bei 541/h)
   gibt je Karte ±4,5 pp (Starthand-Vergleich) und je gepaartem Vergleich 2 bis 5 pp nachweisbare
   Differenz. Ein Einzelkartentausch liegt vermutlich darunter [V]. Der Builder zeigt deshalb
   vier Ergebnisarten statt einer Zahl „Karte bringt x“: Paket-/Achsentest, über Stände
   angesammelte Kartentabelle, beschreibende Engine-Zählungen, exakte Rechnung.
5. **Entfernen:** Gesamtrating v1 (mischt Nutzung 0,30 mit Modellurteil 0,70,
   `overall_rating.py:52-61`), Rubrik-v1-Signale (Gewicht 0), Rating-Layers, Turnier-Conversion
   (Chulane: 7 Listen, 0 Werte [D]), relative Stufen und die zweite S–D-Skala, Gewichte/Profile/
   Prüfzahlen-Oberfläche. Sofort rund 1.870 Zeilen Python (661 + 848 + 360); mit der
   zurückgestellten Tierliste-Seite und `ranking_check.py` rund 5.700 von 12.169 Zeilen des
   Rating-Komplexes [C, `wc -l`].
6. **Zurückstellen:** eigene Tierliste-Seite (wird Pool-Ansicht „Nutzung n/N“), Stärke-Index
   (einfrieren, keine Stellschrauben), Datenwellen **für Chulane** (407 von 927 Pool-Karten haben
   unter 5 Korpus-Decks; mehr Listen ändern das nicht [D]), Module, Primer, Bauliste, Belegung,
   Tokens. Für TAM gilt das Gegenteil: dort ist die Datenbasis dünn, gezielte Sammlung lohnt.
7. **Behalten, umwidmen:** Rubrik v2 (922 Karten) als gekennzeichnetes „Kartenverständnis
   (Modellurteil)“ mit Begründungstext, weil nur sie zu den 407 dünn belegten Karten etwas sagt.
   Keine neuen Rater-Läufe.
8. **Nutzerweg:** Entwurf ändern → exakte Wirkung sofort → „Als Variante testen“ (Plan mit
   nachweisbarer Differenz vor dem Start) → Ergebnis am Diff → Übernehmen oder Verwerfen mit
   Protokoll → Spielen.
9. **Oberfläche:** eine Seite, vier Flächen (Kandidaten, Deck, Analyse, Labor), eine
   Vergleichsgruppe statt vier Wählern, eine Zahlenkomponente mit Klasse EXAKT / GEZÄHLT /
   SIMULIERT / URTEIL.
10. **TAM:** 91 + 184 + 193 Decks in drei getrennten Kohorten und 78 EDHREC-Ansichten mit je
    eigenem Nenner, gegen 10.150 bei Chulane [D]. Folge: bei kleinem N Anteile mit Intervall und
    Kohorten nebeneinander statt Nachbar-Ranking; Besitz wird Kartenmerkmal statt Pool-Grenze;
    der Prüfstand testet ein Zukauf-Paket vor dem Kauf. Das Rating-Material ist Chulane-gebunden
    und für TAM ausdrücklich ausgeschlossen (#1187), ein weiterer Grund, es nicht zum Kern zu
    machen. Ob Engine und Piloten TAM-Listen spielen können, ist UNKNOWN.
11. **Kosten:** 27 bis 40 Agent-Tage in acht Paketen; die ersten drei (Deck-Hash im Protokoll,
    Experiment-Objekt, Zahlen-Vertrag: 9 bis 13 Tage) liefern den Kreislauf ohne Umbau der Seite.

## 2. Der Nutzer-Kreislauf und was jeder Schritt braucht

| Schritt | Braucht | Heute |
|---|---|---|
| Deck öffnen, bearbeiten | Stand, Entwurf, Suche, Pool mit Belegen | vorhanden: `deck_revision` mit `parent_revision_id`, `deck_hash` (`store.py:95-116`), `deck_draft` mit `base_revision_id` (`store.py:208-215`), Suche mit Feldsyntax und deutschen Namen (`static/search.js:1-10`, `german_names.py`) |
| Wirkung der Änderung sehen | exakte Deltas am Diff | vorhanden: `deck_diff.diff_impact` (Kurve, Pips, Quellen, Kombos, Rollen), `/api/cut-lab/what-if` (`web.py:1429-1467`); aber als eigener Tab „Varianten-Diff“, nicht dauernd sichtbar |
| Vorschlag bekommen | ein Ranking mit Grund | sieben getrennte Quellen (Abschnitt 3.2) |
| Per Simulation testen | Experiment mit Plan, Vorprüfung | gepaarte Serie vorhanden (`web.py:1277-1306`), Plan mit nachweisbarer Differenz (`paired_series.py:102-147`), Vorprüfung Engine/Piloten (`paired_series.py:268-281`); kein Experiment-Objekt, kein Mehr-Arm-Plan, kein Holm (grep in `studio/*.py`: 0 Treffer) |
| Ergebnis speichern, auswerten | Ergebnis je Stand, je Änderung, je Karte | Serien als `*.paired.json` im Datenordner, gelesen von `deck_series.py`; Karten-Auswertung je `deck_id` (Defekt 3 oben) |
| Deck verbessern | Übernehmen/Verwerfen, Protokoll | fehlt (grep „übernehmen“ in `static/*.js`: nur Import und Kürzen, `cutlab.js:88`) |
| Spielen | Stand → Partie | vorhanden: Knopf „Mit diesem Stand eine Partie spielen“ (`static/index.html:68`) |

## 3. Ist-Befund

### 3.1 Was trägt (behalten, zum Teil ausbauen)

- **Stände und Diff:** unveränderliche Revision mit Inhalts-Hash, Varianten, Entwurf mit
  Konfliktschutz (`builder.py:1633-1771`), Verlauf, Dossier-Export.
- **Korpus:** 10.551 Listen, 10.150 ohne Dubletten, 913.063 Kartenzeilen
  (`data/research/chulane_corpus/README.md` [D]). Das ist die stärkste Datengrundlage des Builders.
- **Mana:** exakte Farb-Castability nach Karsten, bedingt auf Landdrops (`castability.py:1-20`),
  Starthand-Ziehung, Land-Vergleich mit Quelldecks (`land_advisor.py`).
- **Kombos:** EDHREC-Kombo-Liste und Spellbook-Shells mit Entdoppelung der Varianten
  (`spellbook_shells.py`), Ergänzungs-Kandidaten (`combos.py:819`).
- **Bracket:** Zählung Game Changer, Extrazüge, Landzerstörung, Tutoren, Zwei-Karten-Kombos
  (`deck_facts.py:203`); nennt nie ein Bracket.
- **Import/Export:** Erkennung plain, CSV, Archidekt, Moxfield, Arena (`decks.py:474-500`);
  Export Moxfield/Archidekt und einfach (`static/exportformats.js:7-10`).
- **Engine-Prüfung und Sim-Bereitschaft:** `engine_check.py` (PASS/FAIL/UNKNOWN),
  `builder.py:44-50`, Filter „Simulator-bereit“.
- **Serien-Statistik:** gepaarte Serie mit Platz-Ausrichtung, Sitzrotation, O'Brien-Fleming,
  zensierten Paaren, „kein Unterschied nachweisbar bei n; nachweisbar wären x pp“
  (`static/paired.js:52-60`).
- **Karten-Auswertung:** Starthand als zufällige Exposition, Wilson und Newcombe, Mindestzahl 100
  je Seite, erwartete Zufallsfunde ausgewiesen (`card_outcomes.py:36-50`, `:602-650`, `:813-814`).
  Methodisch der richtige Ansatz.

### 3.2 Was den Zweck nicht erfüllt

- **Sieben Vorschlagsquellen ohne gemeinsame Rangfolge:** `swap.py:159`, `cut_lab.py:43`,
  `packages.py:664` (Upgrade-Pfad), `packages.py:829` (Deck-Doctor), `combos.py:819`,
  `similar_decks.py:484-500` (`they_play_you_dont`, `you_play_they_dont`),
  `land_advisor.py:378`. Jede in eigenem Tab mit eigener Sortierung.
- **Kürzen nur von über 100 auf 100** (`cut_lab.py:1`): Die häufigste Frage „was fliegt raus, wenn
  X reinkommt“ beantwortet ein anderes Modul (`swap.py`).
- **Beobachtung statt Hilfe als Grundsatz:** `land_advisor.py:3-6` „never says what to add or
  cut“, `deck_facts.py` „never says which bracket“. Ehrlich, aber der Owner will Hilfe.
- **Fünf Skalen für eine Frage:** Stärke-Index S–D mit Schnitten 54/35/20/5 (`strength.py:457`),
  Verbreitungs-Stufe S–D mit 0,50/0,35/0,20/0,10 (`tiers.py:82`), relative Stufen S–F,
  Gesamtrating 0–100, Rubrik H 0–100 (`static/tierliste.html:49-76`). Zwei verschiedene „S“.
- **Vier Wähler für eine Vergleichsgruppe:** `cohort`, Bracket-Schnellwahl, Game-Changer-Band,
  Universum (`static/index.html:53-57`).
- **Gesamtrating verletzt die eigene Regel:** gewichtetes Mittel aus Nutzungsindex und sieben
  Modellwerten (`overall_rating.py:52-61`), Gewichte „a SETTING, not a measurement“ (`:10`).
  Gegen das Referenzdeck sagt reine Nutzung besser vorher (AUC 0,924) als Rubrik v2 (0,819)
  (`data/research/chulane_rubric_v2_20261118/PILOT_REPORT.md` §9 [D]).
- **Zwei Sorten „Simulation“ nebeneinander:** `prefilter_lists` ist ein Heuristik-Modell mit
  2.000 Läufen (`builder.py:1605-1630`, `HEURISTIC_MODEL`) im selben Tab wie Engine-Serien.
- **Simulations-Ergebnisse ohne Stand:** siehe Ergebnis 3; `builder.card_simulations` liest je
  Commander über alle Läufe (`builder.py:992-1024`).
- **Frontend:** `static/app.js` 3.208 Zeilen, 128 Funktionen, 16 Tabs (`app.js:1688-1705`);
  8 ausgeführte JS-Tests auf 11,6 k Zeilen [D: brownfield_fable.md §0].

### 3.3 TAM: was der zweite Commander am Zielbild ändert

- **Daten [D/C]:** `tam:active_91` (91 Decks), `tam:curated_b2_4` (184 neue, Bracket 2 bis 4
  belegt), `tam:curated_unbracketed` (193, nur über Game-Changer-Band vergleichbar), dazu
  EDHREC-78-Ansichten als `OBSERVED_THEME` mit eigenem Nenner je Ansicht (16.023 Beobachtungen,
  keine Decks) (`tam_import.py:40-45`, #1635). Nie addiert, nie mit Chulane gemischt
  (`commander_binding`).
- **Kleines N [R]:** 5 von 91 Decks sind 5,5 % mit Wilson-Intervall 2,4 bis 12,2 %; 27 von 91
  sind 29,7 % [21,3; 39,7]. Bei Chulane sind 3.045 von 10.150 30,0 % [29,1; 30,9]. Ein Ranking
  nach Punktanteil ist für TAM Rauschen; die Schwelle `SMALL_DENOMINATOR = 30` (`builder.py:79`)
  warnt zu spät. Das Nachbar-Verfahren nimmt bis zu 100 Decks (`similar_decks.py:316`), mehr als
  die ganze Kohorte.
- **Besitz:** Der Owner hat den Commander, aber die meisten Planeswalker und einige Schlüsselkarten
  nicht (#1187). Zukauf-Modus ohne Preise ist in Arbeit (PR #1643 offen, `include_unowned`,
  Standard aus); End-to-End für TAM ist #1645. Preise sind T3 und Owner-Vorbehalt.
- **Chulane-gebunden im Code [C]:** `chulane_textfit.py`, `card_understanding.py` (922
  Chulane-Karten), Rubrik-Komponente im Index (`strength.py:40`, `:103`), EDHREC-Schwellen-Audit
  (`deck_facts.py:116-119`), Rückfall `"chulane"` als Deck-ID (`simulations.py:1013`, `:1446`),
  Rückfall-Commander der Seite (`static/commander.js:7`). Der Kern (Pool, Kohorten, Kombos, Mana,
  Diff, Serien) ist über die Commander-Auswahl schon parametrisiert; die Lücken bei nicht
  besessenen Commandern und Karten nennt #1645.
- **Governance hinkt nach [D]:** `docs/STUDIO_SCOPE.md:31-32` („Chulane ist das einzige aktive
  Owner-Deck“, „kein Kaufmodus“) und `:268` („Multi-Commander … nicht übernommen“) widersprechen
  dem Entscheid vom 2026-11-19; #1187 vermerkt, dass die Dateien noch nicht nachgeführt sind.
- **Simulation:** Die TAM-Listen sind `STRUCTURALLY_VALID_NOT_XMAGE_VALIDATED` (#1187). Ob die
  gepinnte Engine alle Karten lädt und ob die Piloten Loyalitätsfähigkeiten sinnvoll einsetzen,
  ist nicht gemessen.

### 3.4 Reichweite der Simulation [R]

Starthand-Exposition 7/99 = 7,1 %; Basisrate 25 %; Intervall der Differenz aus zwei
Wilson-Intervallen wie in `card_outcomes.py:571-581`:

| Partien | davon mit Karte in der Starthand | Halbbreite der Differenz | Stunden bei 541/h | bei 350/h |
|---|---|---|---|---|
| 320 | 23 | ±17,6 pp | 0,6 | 0,9 |
| 1.415 (Schwelle `min_exposed` 100) | 100 | ±8,7 pp | 2,6 | 4,0 |
| 5.400 | 382 | ±4,5 pp | 10,0 | 15,4 |
| 11.300 | 799 | ±3,1 pp | 20,9 | 32,3 |

541/h ist die einzige Owner-PC-Messung (Batch, 6 Worker, `paired_series.py:71`); gepaart auf der
4-Kern-VM 333 bis 350/h [D: eff_sim_play.md]. Gepaart: 2.700 Paare weisen 2 bis 5 pp nach, 160
Paare 7 bis 19 pp [D: design_options.md §A.4]. Bei 99 Karten und 5 % sind rund 5 Zufallsfunde zu
erwarten. Folge: Eine Karten-Zahl wird erst über viele Nächte und mehrere Stände belastbar;
deshalb muss die Tabelle über Stände ansammeln dürfen, geschichtet statt vermischt.

## 4. Zielbild

### 4.1 Funktionen, die wirklich tragen (Rangfolge nach Nutzen für Chulane)

1. **Änderung als Arbeitsgegenstand:** Diff gegen den Basisstand immer sichtbar, mit exakter
   Wirkung (Länder, Kurve, Farbquellen, Rollen, Game Changer, Kombos ±, bei Zukauf „im Besitz
   X, fehlt Y“).
2. **Ein Vorschlagsranking** für Rein, Raus und Tausch. Hauptsignal bei großer Kohorte (Chulane):
   die k ähnlichsten Decks („n von k spielen X, du nicht“; „nur n von k spielen Y“). Bei kleiner
   Kohorte (TAM, N unter etwa 300): die ganze Kohorte, sortiert nach der unteren Intervallgrenze,
   die Kohorten als Spalten nebeneinander, dazu die passende EDHREC-Themenansicht mit ihrem
   Nenner. Weitere Gründe: Rolle, Manawert-Lücke, Kombo-Ergänzung, wörtliche Oracle-Eigenschaft
   (Planeswalker, Proliferate), Sim-Befund; Kartenverständnis nur für Chulane. Jeder Vorschlag
   nennt Grund, Klasse und Zahl; kein Mischwert.
3. **Mana-Labor:** Landzahl-Rechner exakt (33 bis 39: P(mindestens k Länder bis Zug T), Flut,
   Farbe auf Kurve je Karte) plus Soll nach Karsten als gekennzeichnete Regel; die Engine-Achse
   33/36/39 mit Kontrollen (Owner-angenommen, G-SIM 5) als Vorlage „Achsen-Experiment“.
4. **Prüfstand:** Paket-Test und Achsen-Test als Standard, Einzeltausch erlaubt mit Vorwarnung.
5. **Kartentabelle aus Partien**, je Stand und geschichtet über Stände.
6. **Bracket-Ziel am Deck:** Der Owner setzt das Ziel-Bracket; daraus folgen Vergleichsgruppe und
   die eine veröffentlichte Grenze (Zahl der Game Changer). Alles andere bleibt Zählung.
7. **Besitz und Zukauf:** Besitz ist ein Merkmal jeder Karte (im Besitz n, frei m, fehlt), keine
   Grenze des Pools. Je Deck eine Zukauf-Liste als Ausgabe. Der Prüfstand beantwortet „lohnt das
   Zukauf-Paket“: Variante mit den fehlenden Karten gegen den besten Stand aus dem Besitz, weil
   die Simulation keinen Besitz braucht. Preise später als eigene Klasse, nie im Ranking.
8. Suche, Import/Export, Engine-Prüfung, Verlauf, Spielen: wie vorhanden, eingefroren.

### 4.2 Wie SIMULATE-Ergebnisse im Deckbau erscheinen

| Art | Anzeige | Wo |
|---|---|---|
| A Paket-/Achsentest (gepaart) | „Variante gegen Basis: +x pp [u; o], n von N Paaren, k zensiert, nachweisbar ab y pp; Piloten, Pods, Engine, Bridge-Zustand; Erkundung oder Bestätigung“; Urteil in vier Stufen: belegt besser, belegt schlechter, kein nachweisbarer Unterschied ab y pp, nicht auswertbar | Labor; an jeder Karte des Diffs als Verweis „Teil von Test T“; im Verlauf am Stand |
| B Karte, zufällig exponiert | „Sieganteil mit Karte in der Starthand gegen ohne: +x pp [u; o], n_mit von N, über s Stände“; Abzeichen an der Deckliste nur, wenn gemessen, Intervall ohne 0 und nach Holm über alle Karten; sonst „n zu klein (n_mit von 100)“ | Deckliste, Kartenfenster, Kürzen |
| C Karte, beschreibend, pilotabhängig | „angeboten in n von N Partien, davon gespielt m, auf der Hand geblieben r; erste Ausspielrunde im Mittel“ (`simulation_card`, `store.py:352-364`) mit Satz „Pilotverhalten, kein Kartenurteil“ | Kartenfenster, Kürzen |
| D exakt | hypergeometrisch, ohne Partie; Gegenprobe gegen die Engine („Starthand hatte k Länder in n von N“) | Mana-Labor, Diff |

Nie: eine Zahl „Karte erhöht Siegquote um x“ ohne n, Intervall und Aussagegrenze; Ergebnis eines
anderen Standes als Ergebnis des aktuellen; Einfluss auf Nutzungszahlen oder Stufen.
**Kürzen mit Simulation:** Reihenfolge bleibt Nutzung in den ähnlichsten Decks und
Rollen-Redundanz; Art B und C sind Zusatzspalten und drehen die Reihenfolge nur bei belegtem
Befund. **Einzeltausch:** Der Startdialog zeigt vorab „nachweisbar ab y pp bei diesem Budget“ und
schlägt Bündelung zu einem Paket vor.

### 4.3 Nutzerweg

1. Deck `main` @ Stand R öffnen; Karten rein/raus im Entwurf. Kennzahlen-Leiste und Diff rechnen
   sofort (exakt).
2. Vorschläge annehmen oder ablehnen; Ablehnung wird gemerkt (wie heute `rejected` in
   `cut_lab.py:48`).
3. „Als Variante testen“: Entwurf wird Stand auf einer Test-Variante; Vorprüfung (100 Karten,
   Engine-Prüfung, Sim-Bereitschaft jeder neuen Karte); Plan wählen: Schnelltest (160 Paare, nur
   grobe Fehler), Nachtlauf (ab 2.700 Paare), Achse (mehrere Arme, Holm).
4. Lauf im Hintergrund; Fortschritt je Partie (gemergt, #1629).
5. Ergebnis im Labor mit Urteil. **Übernehmen** setzt `main` auf den Variantenstand und schreibt
   Experiment und Entscheidung in den Verlauf; **Verwerfen** behält den Stand als abgelehnte
   Variante. Ohne Test übernehmen bleibt möglich und steht als „ungetestet“ im Verlauf.
6. „Mit diesem Stand spielen“.

## 5. Datenmodell-Anforderungen

- **Stand:** bleibt `deck_revision` (unveränderlich, Hash, Eltern). Neu: Ziel-Bracket und
  Vergleichsgruppe am Deck.
- **Änderung:** kein eigener Speicher; immer abgeleitet aus zwei Ständen (`diff_lists`). Persistent
  wird nur der Grund je Karte (Vorschlags-Kennung oder „von Hand“) am Experiment.
- **Experiment (neu):** `experiment_id`, Frage (Paket, Achse, Einzeltausch), Basisstand,
  Arme (Stand-IDs und Hashes), Plan (Budget, Blicke, Schwelle, Pods, Sitze, Seed-Plan, Zweck),
  Status, Ergebnisdatei, Herkunft (Engine-Pin, Bridge-JAR-SHA-256, Bridge-Zustand,
  Pilot-Fingerabdruck), **Entscheidung** (übernommen, verworfen, offen; Datum, Notiz). Rohdaten
  bleiben Dateien (`*.paired.json`, Spielprotokolle); der Store bekommt nur einen additiven Index
  (zwei neue Tabellen, keine Migration bestehender; passt zu #1612 Punkt 3 „bis dahin additiv“).
- **Spielprotokoll:** Sitz-Kopf um `deck_hash` und `studio_revision_id` ergänzen. Beides steht
  schon im Snapshot (`decks.py:349-350`), der Kopf entsteht in Python (`play.py:258-281`): keine
  Bridge-Änderung, kein Bridge-Gate.
- **Kartenergebnis:** je (Deck-Hash, Karte, Herkunfts-Fingerabdruck) die Zähler der Arten B und
  C; Ansammlung über Stände nur als geschichtete Schätzung (je Stand eigene Differenz, gewichtet
  zusammengeführt), mit Zahl der Schichten in der Anzeige; nie über Pilot-, Engine- oder
  Pod-Wechsel hinweg (heute schon Fehler bei Mischung, `card_outcomes.py:719-728`).
- **Zahl (Vertrag):** `{wert, n, N, intervall, klasse, kohorte, quelle, stand_datum}`; `wert`
  fehlt = „unbekannt“. Schließt die Lücke „kein Antwort-Vertrag“ [D: brownfield_fable.md §0 (e)].

## 6. Entscheidungen

| # | Frage | Empfehlung | Begründung | Kosten (Agent-Tage) | Risiko | Abnahme |
|---|---|---|---|---|---|---|
| B1 | Was ist der Builder? | Werkbank mit Prüfstand; Diff und Experiment im Zentrum | Owner-Wortlaut: Simulation soll beim Deckbau helfen; heute endet sie in einem Tab | in B-P1 bis B-P3 | gering | ein Chulane-Tausch läuft von Entwurf bis Übernehmen ohne Handarbeit |
| B2 | Karten-Auswertung je Stand? | ja, Deck-Hash ins Protokoll; Ansammlung geschichtet | sonst Kohortenmischung | 2–3 | alte Protokolle bleiben „Stand unbekannt“ | Test: zwei Stände, zwei Tabellen; gepoolte Zeile nennt Schichten |
| B3 | Einzelkarten-Wirkung zeigen? | nur als Art B/C mit n, Intervall, Holm; Einzeltausch-Serie mit Vorwarnung | Reichweite 3.4 | in B-P4 | Owner erwartet mehr | kein Abzeichen ohne erfüllte Bedingung (Test) |
| B4 | Gesamtrating, Layers, Turnier, zweite Skalen? | entfernen | mischt Kohorten, nicht validiert, für Chulane leer oder doppelt | 3–5 | hebt E6 und Abschlusskriterium 3 auf: Owner-Frage 1 | Seite zeigt eine Skala; entfernte Tests im PR begründet |
| B5 | Stärke-Index? | einfrieren, Standard-Einstellung, keine Gewichte in der Oberfläche; im Pool steht Anteil n/N, Lift, Trend (`card_trend.py`, #1620 gemergt) getrennt | drei lesbare Zählungen sagen mehr als ein Index | in B-P6 | gering | Pool-Zeile ohne zusammengesetzten Wert |
| B6 | Rubrik v2? | behalten als „Kartenverständnis (Modellurteil)“ mit Begründung, nur Chulane; kein v2.2, keine neuen Läufe, keine TAM-Rubrik | einziges Urteil zu den 407 von 927 Karten, über die der Korpus schweigt | 1–2 | Modellurteil wird als Messung gelesen | Klasse URTEIL an jeder Stelle sichtbar |
| B7 | Vorschläge? | ein Ranking, Nachbar-Decks als Hauptsignal, Vorschlag darf empfehlen | sieben Quellen heute | 4–6 | ändert A4 „nur objektive Daten“: Owner-Frage 2 | je Vorschlag Grund, Klasse, Zahl; Marken ohne Einfluss (Test bleibt) |
| B8 | Oberfläche? | eine Seite, vier Flächen, 16 Tabs → 4, eine Vergleichsgruppe | Abschnitt 3.2 | 5–8 | Kollision in `app.js` mit #1643/#1645 (Claim vorher); D-0 Messnetz ist gemergt (#1627) | jede alte Auskunft erreichbar oder im PR als entfernt genannt |
| B9 | Datenwellen? | für Chulane zurückstellen (nur Auffrischung je neuem Set); für TAM gezielt sammeln: weitere Tam-Decklisten über die vorhandenen Erntewege, bis die Bracket-Kohorte dreistellig ist | Chulane: mehr Listen belegen dünne Karten nicht besser; TAM: 91/184/193 tragen kein Ranking; Owner: „gerne mehr Daten dafür holen“ | Chulane 0; TAM 2–3 | Quellenbedingungen (Leitplanken in #1187, Kommentar 6992598749) | Datenstand je Quelle sichtbar (#1616 gemergt); TAM-Kohorten mit n/N im Datenbericht |
| B10 | Deutsche Namen, Import/Export? | fertig, einfrieren | Owner spielt englisch (E12) | 0 | – | – |
| B11 | Heuristik-Vorfilter? | aus dem Simulations-Tab nehmen; exakte Rechnung ersetzt ihn im Mana-Labor | zwei Sorten „Simulation“ verwirren | 1 | gering | kein `HEURISTIC_MODEL` neben Engine-Zahlen |
| B12 | Ein Builder für Chulane und TAM? | ja, commander-neutral; nichts Chulane-Gebundenes im Kern; jede Abnahme läuft für beide Commander | zweiter Commander ist Owner-Entscheid; Kern ist schon parametrisiert | in jedem Paket, plus 1–2 für die Reste aus 3.3 | Doppelarbeit mit #1643/#1645 (Gemini): nur ergänzen | Test: kein Chulane-Literal in Kernmodulen; TAM-Deck durchläuft den Nutzerweg bis zum Diff |
| B13 | Vorschläge bei kleiner Kohorte? | Intervall statt Punktanteil, Sortierung nach unterer Grenze, Kohorten nebeneinander, kein Nachbar-Verfahren unter N = 300 | 3.3, eigene Rechnung | in B-P4 | Setzung der Schwelle 300 [V] | Test mit 91er-Fixture: gleiche Eingabe, gleiche Reihenfolge; keine Zahl ohne Intervall |
| B14 | Simulation für TAM? | erst zählen, dann spielen: Sim-Bereitschaft je TAM-Liste (Engine lädt, Piloten kennen) als n/N, danach eine kleine Serie mit Sichtung der Planeswalker-Entscheidungen; bis dahin für TAM nur EXAKT und GEZÄHLT | Listen sind nicht gegen XMage geprüft; Pilotverhalten mit Loyalität unbekannt | 2–3 | fehlende Karten in der Engine brauchen Fork-Arbeit (Owner-Vorbehalt) | Bericht n/N je Kohorte; `UNKNOWN` bleibt sichtbar, kein TAM-Sim-Abzeichen vorher |

Alternativen, knapp: (a) Tierliste als Hauptansicht ausbauen: verworfen, sie beantwortet „welche
Karte ist beliebt“, nicht „was ändere ich an meinem Deck“. (b) Karten-Wirkung per Einzeltausch-
Serien: verworfen als Standard, Budget je Karte eine Nacht oder mehr. (c) Experiment nur als
Datei: verworfen, Verlauf und Entscheidung brauchen einen Index.

## 7. Entfernt und zurückgestellt

| Teil | Urteil | Beleg |
|---|---|---|
| `overall_rating.py` (661 Z.), Umschalter „Gesamtrating“ | entfernen | `overall_rating.py:10`, `:52-61` |
| Rubrik-v1-Signale (`research_import.import_rubric`), Gewicht 0 | entfernen | `strength.py:6`, `:423` |
| `layers.py`, `layers_view.py` (848 Z.), `/api/rating-layers` | entfernen | Playgroup-Atlas commander-unabhängig; Siegquote mit n ≥ 30 nur 419/927 [D: data_plan.md §C] |
| `tournament_conversion.py`, Turnier-Panel | entfernen | TopDeck Chulane 7 Listen, 0 Werte; EDHTop16 16/927 [D] |
| relative Stufen S–F, „Gleiche Funktion“, Verbreitungs-Stufe als zweite Skala | entfernen | `static/tierliste.html:49-76`, `tiers.py:82` |
| `ranking_check.py` (1.105 Z.), Profile, Gewichte, Snapshots in der Oberfläche | zurückstellen, als CLI behalten | Prüfwerkzeug des Index |
| `tierliste.html`/`.js` (2.453 Z.) als eigene Seite | zurückstellen, nach B-P5 entfernen | wird Pool-Ansicht |
| `subarchetypes.py`, `chulane_textfit.py` | zurückstellen; Textfit später als Vorschlagsgrund prüfen | Gewicht 0, beschreibend |
| Datenwellen für Chulane, Alle-Commander-Ernte #1210 | zurückstellen (TAM-Sammlung läuft gezielt weiter) | Abschnitt 6 B9 |
| Module, Primer, Bauliste, Belegung, Tokens, Dossier | einfrieren, ins Menü „Mehr“ | fertig, kein Beitrag zum Kreislauf |
| `prefilter_lists` im Simulations-Tab | entfernen aus der Oberfläche | `builder.py:1605-1630` |

## 8. Paket-Schnitt

| Paket | Inhalt | Tage | Abhängig von | Abnahme |
|---|---|---|---|---|
| B-P1 | `deck_hash` und Revision im Sitz-Kopf; Karten-Auswertung je Stand und geschichtet | 2–3 | – | Test, der ohne Hash fällt; alte Protokolle „Stand unbekannt“ |
| B-P2 | Experiment-Index, Entscheidung, Übernehmen/Verwerfen, Ergebnis am Diff und im Verlauf | 4–6 | D-2 Serien-Pool hilfreich, nicht nötig | Roundtrip-Test Entwurf → Serie → Übernehmen (Erweiterung von #1538) |
| B-P3 | Zahlen-Vertrag und eine Anzeige-Komponente für die Builder-Routen | 3–4 | D-0 Messnetz | JS-Test: keine Zahl ohne Klasse und n/N |
| B-P4 | Ein Vorschlagsranking; Kürzen bei genau 100; Sim-Spalten B und C | 4–6 | B-P1 | gleiche Eingabe, gleiche Reihenfolge; Marken ohne Einfluss |
| B-P5 | Eine Seite, vier Flächen, Kennzahlen-Leiste, Ziel-Bracket, eine Vergleichsgruppe | 5–8 | B-P3 | Tastatur-Durchlauf des Nutzerwegs; alte Tabs erreichbar oder entfernt |
| B-P6 | Aufräumen nach Abschnitt 7 | 3–5 | Owner-Antwort 1 | Zeilen- und Routenzahl vorher/nachher; kein Test still gelöscht |
| B-P7 | Mana-Labor: Landzahl-Rechner, Achsen-Vorlage; fünffarbig für TAM geprüft | 3–4 | SIMULATE A2 (Mehr-Arm, Holm) für die Engine-Achse | exakte Werte gegen Hypergeometrie; Landzahl-Frage aus dem Builder startbar |
| B-P8 | TAM-Tauglichkeit: Reste der Chulane-Bindung im Kern, Sim-Bereitschaft je TAM-Kohorte, kleine Sichtungs-Serie | 3–4 | #1643, #1645 gemergt | Abnahme B12 und B14 |

Reihenfolge: B-P1, B-P2, B-P3 zuerst (9 bis 13 Tage, kein Seitenumbau). Dann B-P4, B-P7 und B-P8
parallel, B-P5, zuletzt B-P6. Summe 27 bis 40 Agent-Tage [V, geeicht an brownfield_fable.md:
Option D 16 bis 24 Lane-Tage für drei Nähte]. Nicht in dieser Summe: Zukauf-Modus und
TAM-End-to-End (#1636, #1645, laufen bei Gemini), Preise (T3).

## 9. Risiken und Abbruchkriterien

- **Reichweite reicht nicht:** Misst der Pilotblock am Owner-PC eine Diskordanz nahe 0,39 (Paarung
  wirkungslos) und unter 400 Partien/h, dann Einzeltausch-Serie aus der Oberfläche nehmen; nur
  Achse, Paket und Kartentabelle bleiben.
- **Pilot-Gültigkeit:** Spielen die Piloten Chulanes Schleifen schlecht, benachteiligt jede
  Sim-Zahl Wertkarten. Bis zum Pilot-Audit (G-SIM 2) trägt jede Sim-Zahl die Aussagegrenze;
  ausgeschlossene Kartenrollen bekommen „simulativ nicht bewertbar“.
- **Seitenumbau bricht Bestehendes:** `app.js` hat kaum Tests. B-P5 erst nach D-0; Abbruch, wenn
  das Paket 50 % über Budget liegt (Regel aus #1612).
- **Entfernen gegen Owner-Wunsch vom 18.11.** („Gesamtrating wär cool“): B-P6 nur nach Antwort 1.
- **Modellurteil als Messung gelesen:** Klasse URTEIL nie in einer Spalte mit GEZÄHLT.
- **TAM-Zahlen wirken genauer, als sie sind:** kleine Kohorten ohne Intervall führen zu
  Zufallsvorschlägen. Abbruch für B13: Wenn nach der Sammlung keine Bracket-Kohorte über 100
  Decks kommt, bleibt das TAM-Ranking eine Liste ohne Reihenfolge-Anspruch.
- **Parallele Arbeit:** #1643 und #1645 ändern `builder.py`, `web.py`, `app.js`. Pakete B-P4 und
  B-P5 erst nach deren Merge und mit Claim in #1167.

## 10. UNKNOWN

- Anteil der 927 Pool-Karten, die Engine und Piloten-Kartenwissen kennen (Sim-Bereitschaft): nicht
  gemessen; begrenzt, welche Tausche testbar sind.
- Diskordanz, Paar-Streuung und Durchsatz gepaarter Serien am Owner-PC: ungemessen (S2 offen).
- Größe des Effekts eines Einzeltauschs; unter 1 bis 2 pp ist Vermutung.
- Pilot-Fehlerquote am Chulane-Sitz (Audit nicht gelaufen).
- Ob die Owner-Datenbank der gemessenen Store-Kopie entspricht [D: data_plan.md].
- Ob der Owner die Tierliste-Seite nutzt (keine Telemetrie, gewollt).
- TAM: Anteil der Karten aus den drei Kohorten, den die gepinnte Engine lädt und das
  Piloten-Kartenwissen kennt; Qualität der Planeswalker-Entscheidungen der Piloten; Größe des
  TAM-Pools mit und ohne Zukauf; ob die Drive-Daten in der Owner-Datenbank schon importiert sind.
- Zeilenersparnis in B-P6 genau; Abhängigkeiten im 12-Modul-Zyklus um `builder` nicht aufgelöst.

## 11. Offene Owner-Fragen

1. **Tierliste:** Gesamtrating, Rating-Layers, Turnier-Panel und Zweitskalen entfernen, die Seite
   zur Pool-Ansicht machen, Abschlusskriterium 3 („Tierliste abgenommen“) streichen? Empfehlung:
   ja; Kartenverständnis bleibt als gekennzeichnete Spalte mit Begründung.
2. **Darf der Builder empfehlen?** Heute gilt „nur objektive Daten, keine Meinung“ (A4).
   Empfehlung: ja, als eigene Klasse VORSCHLAG mit genannter Regel und Zahl, nie als Messwert.
3. **TAM-Vergleichsgruppe:** Welche Kohorte ist für TAM der Standard? Empfehlung:
   `tam:active_91` als Standard, `tam:curated_b2_4` als zweite Spalte daneben, nie addiert;
   `tam:curated_unbracketed` nur über das Game-Changer-Band. (Die frühere Frage nach Karten
   außerhalb der Sammlung ist durch den Zukauf-Entscheid vom 2026-11-19 beantwortet.)
4. **Rechenzeit und TAM-Simulation:** eine Nacht je Paket- oder Achsenfrage und eine Nacht
   Basislauf je übernommenem Stand für die Kartentabelle? Und soll TAM auch simuliert und
   gespielt werden (heute gilt der Fokus Chulane für PLAY/SIMULATE)? Empfehlung: Nächte ja;
   TAM-Simulation erst nach der Zählung aus B14, weil sonst Zahlen ohne Grundlage entstehen.
5. **Übernehmen:** Gilt dein Klick „Übernehmen“ im Builder als die Owner-Entscheidung zur
   Chulane-Basis (`docs/OWNER_DECK_FOCUS_CURRENT.md:6`), und die Repo-Datei
   `data/decks/chulane_current.txt` wird nur auf Zuruf nachgezogen? Empfehlung: ja.
