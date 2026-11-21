# Studio-Charta v2 (Brownfield 2)

Stand 2026-11-20. **Vom Owner am 2026-11-20 angenommen sind nur die Entscheidungen Q1–Q11 (§5, „Go Q1–Q11“), Entscheid-Register: `docs/OWNER_DECISIONS_STUDIO_20261118.md` E15; der Rest (Zielbild, §4 Paketplan, §6) ist die Planung des Co-Lead im Rahmen von `AGENTS.md` §8, kein Owner-Entscheid.** Grundlagen: vier Analyse-Lanes (`charter_builder.md`, `charter_simulate.md`, `charter_play.md`, `charter_architecture.md` als Commit 13a836a462cf im Remote, Zweig unter `docs/*`, Ordner `docs/analysis-reports/`) und das Owner-Zielbild vom 2026-11-19. Die Owner-Vorbehalte aus `AGENTS.md` §8 gelten unverändert; Abschnitt 5 unten ist jetzt als Entscheid-Register E15 maßgeblich (Wortlaut dort). Nach dem Go korrigiert (nur Fakten, kein Inhalt): Zeilenangabe in Q3, „mit #1646 erledigt“, „lange Pflichtlektüre“ statt einer Zeilenzahl in Q10.

## 1. Zielbild (Owner, 2026-11-19) in einem Satz
Ein lokales Studio für den Windows-PC, in dem der Owner ein Commander-Deck (jetzt Chulane, dazu TAM) baut, es mit Tischen und Settings seiner Wahl (2–6 Spieler, gern 8) regelkonform und schnell simuliert, die Ergebnisse gespeichert dem Deckbau zurückspielt („diese Änderung bringt x, n von N“) und das Deck selbst spielen kann. Kreislauf: Deck bearbeiten → Experiment planen → simulieren → Ergebnis am Diff sehen → übernehmen/verwerfen → spielen → Notiz zurück ins Deck.

## 2. Gemeinsames Urteil der vier Lanes
- **Kein Neubau.** Der Bestand trägt viel; es fehlt die Verbindung (kein Experiment-Objekt, keine Deck-Revision im Spielprotokoll, keine Rückführung PLAY → Deckbau). Option D bleibt der Rahmen, wird aber um das Produktziel erweitert.
- **Wichtigster Defekt (BUILDER + SIMULATE + ARCHITEKTUR einig):** Auswertungen zählen je `deck_id` statt je Deck-Stand (`play.py:348-376` Kopf der Partie ohne Deck-Hash je Sitz, `store.py:334-351` `simulation_run` ohne Revisionsspalte, gepaarte Serien als Dateien mit `SCAN_LIMIT = 2000`). Behebung in Python, ohne Bridge-Gate.
- **Tempo:** Die Engine-Seite ist nach D-2 fast ausgereizt (595 → 967 Partien/h, Faktor 1,6–2); die größeren Hebel liegen in Statistik und Fragestellung (Faktor 5–20: gepaarte Serien, Basis-Wiederverwendung, Frühphasen-Kennzahl, Stopp-Regeln). PLAY-Tempo ist mit #1623/#1633/#1634 im Kern gelöst.
- **Reichweite der Simulation ehrlich:** 5.400 Partien (eine Nacht) lösen je Karte ±4,5 pp, je gepaartem Vergleich 2–5 pp auf; ein Einzeltausch liegt vermutlich darunter. Der Builder zeigt deshalb vier Ergebnisarten (Paket-/Achsentest, geschichtete Kartentabelle mit Holm, beschreibende Engine-Zählungen, exakte Rechnung).
- **Sitze:** 5/6 qualifizieren (3–4 Agent-Tage + 2–3 h Rechenzeit, acht Nachweise F1–F8); 7/8 zurückstellen (~15 Grenzstellen plus Bridge-Änderung, kein Messwert; Aufwand je Antwort 9–16-fach gegenüber dem Vierertisch).

## 3. Entscheidungen des Co-Lead zu Widersprüchen zwischen den Lanes
1. **Datei-Aufbau:** ARCHITEKTUR schlägt zwei Dateien (`reference.sqlite3` neu baubar, `studio.sqlite3` Nutzerzustand), SIMULATE eine eigene `simulate.sqlite3` vor. **Zusammenführung: drei Dateien nach Lebenszyklus:** `reference` (Import, neu baubar), `studio` (Nutzerzustand + Experiment-Index + Entscheidungen, klein, exportierbar, einzige Quelle der Wahrheit für Nutzerarbeit), `simulate` (inhaltsadressiertes Partie-Archiv mit `game_key`, neu erzeugbar aus Manifest/Journal/Logs, Kontingent statt Pflichtaufbewahrung). Begründung: unterschiedliche Lebensdauer und Löschbarkeit; Nutzerzustand bleibt klein und sichernswert.
2. **Experiment-Modell:** BUILDER („Experiment“) und SIMULATE („Tisch-Einstellung + Arme + Plan-Datei“) sind dasselbe Objekt; ein Modell, `TableSpec` gemeinsam mit PLAY.
3. **Schema 22:** Statt einer eigenen Owner-Sitzung läuft die Migration über eine Export-Datei des Nutzerzustands (Sicherung, Migrationsweg, Prüfmittel); der Owner schickt sie einmal, die Migration wird am echten Zustand vorab bewiesen, der PC migriert beim Start mit Sicherung.
4. **Reihenfolge:** zuerst der kleinste Kreislauf, dann der Dateischnitt, dann Oberfläche (Details Abschnitt 4).
5. **Simulations-Gewicht:** BUILDER und SIMULATE wollen `simulation` aus dem Tierlisten-Index streichen; zusammen mit dem Entfernen von Gesamtrating v1/Rating-Layers wird die Tierliste zur Pool-Ansicht „Nutzung n/N“. Simulation erscheint sofort als Evidenz mit Reifegrad R0–R3 im Deckbauer; G-SIM wird vom Tor zum Reifegrad (ändert O3/E2/B11).

## 4. Paketplan (grob; Agent-Tage ±40 %)
**Phase 0 (Stand 2026-11-20 gemergt):** #1638 (Pool, hinter Schalter; Echt-Engine-Beleg und Einschalten offen in #1652), D-1 P1 (#1649), TAM T2/T4 (#1643, #1647), PLAY-Snapshot (#1644); kleine Folge-PRs laufen weiter.
**Phase 1: Kreislauf-Minimum (etwa 25–32 Tage, 4–6 Lanes parallel):**
- B1 Deck-Hash im Spielprotokoll, Revisionsspalte, Auswertung je Stand (BUILDER-P1, ohne Bridge) – 3–4
- B2 Experiment-Objekt + Plan-Datei + Tisch-Einstellung (BUILDER/SIMULATE A) – 6–8
- B3 Zahlen-Vertrag (EXAKT/GEZÄHLT/SIMULIERT/URTEIL) in einer UI-Komponente – 2–3
- S1 Pool-Auftragsformat mit Tisch, Deck-Hashes, Pilot-Fingerabdruck, `game_key`; Journal/Manifest/Determinismus-Wächter (SIMULATE B, nach #1638) – 5–6
- S2 Qualifikation 5/6 (F1–F8) – 3–4 (+ Owner-Freigabe nach Nachweis)
- P1 PLAY v1: eigene Kohorte für Mensch-Partien (Filter `human_seats` in `card_outcomes`), Pass-Bedienelement, Gegner aus Deck-Ständen, `TableSpec`, Nachspiel-Blatt – 7–9
- D-3 Protokolltreiber (neu geschnitten, direkt nach #1638) – 3–5
- Owner spielt eine ganze Partie über die Seite (Aktion des Owners) und liefert Urteil
**Phase 2: Dateischnitt/Schema 22 (K-2b bis K-2e, 10,5–15 Tage)** nach Export-Format und Migrationsbeweis.
**Phase 3 (parallel zu Features):** Router/Fehlervertrag/Antwort-Typen (~25 Kreislauf-Routen, 4–6), Frontend in ES-Modulen mit `node --test`, eine Seite mit vier Flächen (Kandidaten, Deck, Analyse, Labor) statt 16 Tabs (5–8), Betrieb/Release (3–4); Vorschläge-Ranking (VORSCHLAG-Klasse); L1 Frühphasen-Serie nach Messversuch; Pilot-Messrahmen (drei Zahlen je Fingerabdruck); erste Nachtserie am Owner-PC.
**Entfernen:** Gesamtrating v1, Rubrik-v1-Signale, Rating-Layers, Turnier-Conversion, zweite S–D-Skala, Heuristik-Vorfilter, `simulation_run`/`simulation_card`, `tier_snapshot` als Tabelle, `memo.py`, alte Orchestrierer nach D-2 P5, `subarchetypes.py` (nach Prüfung §9). **Nicht jetzt:** ältere Lanes (9.824 Zeilen Java, ~3.000 Zeilen Python): PB-03 und 205–300 `qualification/`-Dateien nennen sie; nur mit neuer Epoche (Abschluss).
Gesamt: etwa 70–100 Agent-Tage; bei 6–8 parallelen Lanes grob 2–3 Wochen Wanduhr, abhängig vom Kontingent.

## 5. Owner-Entscheidungen (Empfehlung jeweils: ja)
Q1 Entfernen: Gesamtrating v1, Rubrik-v1-Signale, Rating-Layers, Turnier-Conversion, zweite S–D-Skala; `simulation` aus Tierlisten-Index und Stufe 2 streichen, dafür Evidenz mit Reifegrad R0–R3 im Deckbauer; Rubrik v2 bleibt als „Kartenverständnis (Modellurteil)“ nur für Chulane (hebt E6, ändert O3/E2/B11).
Q2 Der Builder darf Vorschläge machen (Klasse VORSCHLAG, getrennt von den Zahlen; ändert A4); der Klick „Übernehmen“ gilt als Owner-Entscheid zur Chulane-Basis.
Q3 TAM: Standardkohorte `tam:active_91` (daneben `tam:curated_b2_4`, nie addiert); Datensammlung für TAM gezielt fortsetzen, für Chulane zurückstellen; TAM-Simulation erst nach Zählung der Sim-Bereitschaft je Kohorte; `docs/STUDIO_SCOPE.md:31-32`/`:270` an den Owner-Entscheid zu TAM (#1187) angleichen (mit #1646 erledigt).
Q4 Experimente: eine Nacht je Frage (5.400 Partien); rundenbegrenzte Frühphasen-Serie (L1) als eigener Experiment-Typ nach einem Messversuch.
Q5 Sitze: Qualifikation 5/6 jetzt (F1–F8); die Freigabe selbst bleibt deine Entscheidung nach dem Nachweis und gilt dann für SIMULATE und PLAY (PLAY bis dahin „nicht qualifiziert“ sichtbar) [Nachtrag, kein Owner-Wortlaut: eingeschränkt durch Option A vom 2026-11-20, PLAY 5/6 bleibt getrennt; `docs/OWNER_DECISIONS_STUDIO_20261118.md`, „Entscheide 2026-11-20/21“ Nr. 1]; 7/8 zurückgestellt bis zur 6er-Messung.
Q6 Gegner: beliebige Studio-Deck-Stände als Gegner-Sitze (Chulane bleibt das einzige optimierte Deck); Korpus-Gegner in PLAY v1 später.
Q7 PLAY: Zahlungs-Vorschlag aus dem Piloten-Planer, vom Menschen ausgelöst, nur angebotene Optionen, im Protokoll markiert (Auslegung `AGENTS.md` §2); Speichern/Fortsetzen zurückstellen; du spielst vor dem Bedienungs-Paket eine ganze Partie.
Q8 Piloten: Vorausschau (S5) nicht als Serien-Pilot; Pilot-Änderungen nur mit gepaartem Nachweis; Pilot-Audit nach der ersten Nachtserie.
Q9 Daten: Schema 22 als Dateischnitt (drei Dateien, Abschnitt 3) mit Migration über die Export-Datei (keine eigene Owner-Sitzung); Decks dürfen Karten ohne Besitz enthalten (TAM-Zukauf, Besitz als Merkmal, Preise bleiben Owner-Vorbehalt).
Q10 Governance: MATERIAL in Inhalt (Klasse A) und bloße Größe (B) teilen, Kreuz-Review nur für A (ändert E7/C7); „Studio-Daten-Gate“ für Schema-Änderungen; Charta mit Entscheid-Register ersetzt die lange Pflichtlektüre.
Q11 Ältere Lanes erst mit der Abschluss-Epoche entfernen; Release-Archiv lokal ablegen statt dauerhaftem GitHub-Release, solange #1108 offen ist.

## 6. Risiken und Abbruchkriterien
`ATTACH` gegen 70 Testdateien mit eigenem SQL (Rückfall: eine Datei mit Neuaufbau an Ort und Stelle); alles unter Windows (bisher nicht ausgeführt); Store des Owner-PCs UNKNOWN; Effektgröße eines Einzeltauschs UNKNOWN; Pilot-Fehlerquote UNKNOWN; Mehrspieler-Aufwand 9–16-fach (Modell). Abbruch: ein Paket überschreitet sein Budget um > 50 %; eine Hash-Abweichung bleibt nach zwei Tagen unerklärt; die erste Owner-Partie zeigt Produktmängel, die wichtiger sind (dann Phase 2/3 verschieben).
