# Commander Studio: Optionen und Empfehlungen für SIMULATE, BUILD, PLAY und den Weg zum Projektabschluss

> **Nachtrag Owner-Antworten 2026-11-18 (haben Vorrang vor diesem Papier):** O1: Der Studio-BUILD in diesem Repo bleibt der
> Deckbauer des Projekts; **B-X1, „Deck-Snapshot v1“ und O2 entfallen**, `deckbuild-studio` wird nicht angefasst (§0 Punkt 4, §B, §F O1/O2
> sind überholt). O3: Simulation darf in die Tierliste fließen, wenn sie nachweislich gut ist; B11 wird bedingt (Gewicht 0, bis ein
> Reife-Tor erfüllt und vom Owner bestätigt ist; Tor in `docs/OWNER_DECISIONS_STUDIO_20261118.md`). O4: Zählen von Pilot-Auslassungen
> zulässig. O6: Abnahme-Definition PLAY angenommen. Verbindlicher Scope: `docs/STUDIO_SCOPE.md` (in Arbeit).


Stand 2026-11-18. Planungspapier, kein Bau. Es ändert nichts in den Repos und ist keine Owner-Quelle:
Jede Entscheidung unten ist ein Vorschlag, der erst mit Owner-Freigabe gilt, wo das vermerkt ist.

Abkürzungen: CPL = `commander-playtest-lab` (BUILD/PLAY/SIMULATE + Tierliste, öffentlich),
DBS = `deckbuild-studio` (BUILD-Ausgründung, privat).

Belegkürzel in diesem Papier:
- **[D]** steht so in einer Doku oder einem Ist-Lage-Bericht, von mir nicht nachgemessen.
- **[M]** von mir heute nachgemessen (Befehl oder API-Abruf genannt).
- **[C]** von mir aus dem Quelltext gelesen (Datei:Zeile), nicht mit laufender Engine geprüft.
- **[R]** aus einer Recherche-Lane, mit deren Belegstatus.
- **[G]** Recherche-Aussage, von mir am Original gegengeprüft.
- **[E]** meine Einschätzung ohne Beleg.

---

## 0. Das Wichtigste auf einer Seite

1. **SIMULATE ist statistisch weiter als die Ist-Lage vermuten lässt, aber an drei Stellen
   unwirksam verdrahtet.** Blockweise Auswertung je Seed, Sitzrotation, Abbruch-Zensur,
   O'Brien-Fleming-Stopp, nachweisbare Differenz und Herkunftsfelder sind vorhanden [C]. Neu
   gefunden (stehen in keinem Ist-Lage-Bericht):
   - Die gepaarte Studio-Serie richtet die Variante **nicht** an den Bibliotheks-Plätzen der
     Basis aus. Die dafür qualifizierte Funktion `align_to_baseline_slots` existiert, wird aber
     nur in der alten Engine-Lane benutzt [C: `engine/rules/full_game_comparison.py:243`; kein
     Aufruf unter `studio/`; Studio-Revisionen werden alphabetisch geliefert, `decks.py:127`].
     Folge: Schon ein Ein-Karten-Tausch verschiebt alle Plätze dazwischen, die beiden Partien
     eines Paares haben ab dem ersten Mischen verschiedene Hände. Die Paarung spart dann
     vermutlich fast nichts.
   - Gepaarte Serien laufen **nacheinander, ein Spiel je JVM** [C: `paired_series.py:416`
     `series_engine(data_path, 1)`; `play_batch` wird nur von `__main__.py:621` benutzt]. Die
     gemessenen 541 Spiele/h [D: #1251] gelten für die Batch-Serie, nicht für A-gegen-B. Die
     Konstante `ESTIMATED_GAMES_PER_HOUR = 540` in `paired_series.py:53` ist für diesen Pfad
     vermutlich um ein Mehrfaches zu hoch.
   - `mean_first_cast_round` mittelt nur über Partien, in denen die Karte gespielt wurde
     [C: `simulations.py:514-519`]. Das ist die Überlebensverzerrung, vor der
     `simulate_methods.md` §3(5) warnt.
2. **Empfehlung SIMULATE: Option A2 („Deck-Labor mit Messprotokoll"), beginnend mit A1.** A1
   verdrahtet Vorhandenes richtig (Ausrichtung, Parallelität, Planung mit nachweisbarer
   Differenz, zensurbewusste Kennzahlen). A2 ergänzt Serienplan, Konsistenz-Kennzahlen und eine
   sichtbare Gültigkeitsgrenze der KI. Ergebnisse erscheinen nur im Deckbauer und im
   Deck-Verlauf als eigene Kohorte `SIMULATED_RESULT`, nie auf der Tierliste.
3. **Ehrliche Reichweite:** Eine Nacht am Owner-PC (10 h, rund 5.400 Spiele, falls die 541/h
   auch gepaart erreicht werden) weist Gewinnraten-Unterschiede ab etwa 2,5 bis 4,5
   Prozentpunkten nach (eigene Rechnung, Annahmen in §A.4). Ein einzelner Kartentausch liegt
   vermutlich darunter [E]. SIMULATE entscheidet also Pakete und Bauachsen (Landzahl,
   Ramp-Paket, Schutzpaket), nicht Einzelkarten. Das muss die Oberfläche so sagen.
4. **Empfehlung BUILD: B-X1 in Stufen.** DBS wird kanonischer Deckbauer, CPL behält Tierliste,
   PLAY, SIMULATE und friert den eigenen Deckbauer auf „Deck annehmen, anzeigen, starten,
   Serien zeigen" ein. Einzige Kopplung ist ein Dateivertrag „Deck-Snapshot v1" in Richtung
   DBS nach CPL. Kein Rückkanal nach DBS ohne Owner-Mandat (DBS-AGENTS §1, §3, §10).
5. **Empfehlung PLAY: Option „Empfohlen" (P0 + P1).** Zuerst den Brett-Klick-Stand sichern und
   fertigstellen, einen Echt-Engine-Test des Mensch-Sitzes ergänzen, dann die Abnahme am
   Owner-PC nach messbarer Definition (§C.2).
6. **PR #1510: nicht übernehmen, sondern ersetzen.** Die brauchbaren Technikteile einzeln neu
   einreichen, das Zieldokument durch ein Owner-gezeichnetes ersetzen (§D.1).
7. **Der Owner muss zwölf Punkte entscheiden** (§F). Die drei dringendsten: Wer ist kanonischer
   Deckbauer (O1), gilt „Simulation nie auf der Tierliste-Seite" auch für die Anzeige (O3),
   Bestätigung der Entscheide vom 17. und 18.11. im Wortlaut (O5).

---

## 1. Grundlage und Verlässlichkeit

**Gelesen:** `ist_lage_cpl.md`, `ist_lage_dbs.md`, `play_qol.md`, `simulate_projects.md`,
`simulate_methods.md`, `research_frame.md`; CPL `AGENTS.md` (ganz), `OWNER_DECISIONS_STUDIO_20261112.md`,
`OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`, `STUDIO_ROADMAP_20261112.md`,
`STUDIO_PLAN_SIMULATOR.md`, `OPERATIONAL_SIMULATION_POLICY.md`, `DECKBAU_INTERFACE.md` §1-2;
`STUDIO_TARGET_SCOPE.md` aus dem Zweig von PR #1510; DBS `AGENTS.md` (ganz).

**Nachgemessen [M], 2026-11-18:**
- CPL: `main` = `8e2852d07`; einziger offener PR ist #1510 (Head `8671c441a`); neun offene
  Issues (#1369, #1265, #1261, #1210, #1187, #1176, #1167, #1108, #1093); Repo öffentlich
  (`gh api repos/...`). Deckt sich mit `ist_lage_cpl.md`.
- DBS: drei offene PRs (#316, #307, #304); Repo privat. Deckt sich mit `ist_lage_dbs.md`.

**Stichproben-Gegenprüfung der Recherche am Original [G]:**

| Behauptung | Ergebnis |
|---|---|
| Playgroup-Sitzkurve: 300.240 Vierer-Partien mit einem Sieger; Sitz 1 bis 4 = 29,1 / 25,7 / 23,6 / 21,5 %; Odds-Ratio Sitz 4 gegen 1 = 0,67; Stand 16.11.2026; Selbstangabe, Casual, Sitz nicht randomisiert, Unentschieden ausgeschlossen | bestätigt (playgroup.gg/commander/turn-order) |
| Forge-Yield-Modell: Auto-Pass-Schalter, „Yield to stack" unterbrechbar, „Resolve entire stack" nicht unterbrechbar, Phasenmarker, Unterbrecher-Standards | bestätigt, mit zwei Abweichungen: (a) Forges Auto-Pass passt „whenever you have no playable actions available", der Client rechnet also selbst aus, ob etwas spielbar ist (mit Zeitlimit 50 bis 1500 ms). Das ist bei uns nicht zulässig, siehe §C.3. (b) Der sechste Unterbrecher „Cards revealed or choices made: OFF" fehlt in `play_qol.md`. |
| Forge-KI: „Best with Aggro and midrange", „Poor to Ok in control", „Pretty bad for most combo decks"; `sim`-Befehl mit `-c` Zeitlimit 120 s | bestätigt. Abweichung: `simulate_projects.md` schreibt, die Seite sage „keine Simulation und keine Vorhersage"; die Seite sagt nur „mostly based on heuristics". Nach 120 s endet ein Spiel dort als Unentschieden. |

Nicht gegengeprüft, aber tragend: die Rechenformeln in `simulate_methods.md` §2 (Standardformeln,
teils als „Quelle nicht abgerufen" markiert). Meine eigenen Zahlen in §A.4 nutzen die im Repo
schon qualifizierte Arithmetik `(1,96 + 0,8416) · sd / √n` [C: `full_game_comparison.py:578-603`].

**Widersprüche zwischen Ist-Lage-Berichten, Doku und Code, die ich zusätzlich gefunden habe:**

| # | Befund | Beleg |
|---|---|---|
| W1 | „A-gegen-B gepaart" ist als fertig gemeldet, wirkt im Studio-Pfad aber vermutlich nicht, weil die Platz-Ausrichtung fehlt | [C] siehe §0 |
| W2 | 541 Spiele/h wird als Durchsatz von SIMULATE gelesen, gilt aber nicht für gepaarte Serien | [C] siehe §0 |
| W3 | `/api/outcomes` gilt als fertig; im Verzeichnis `studio/static` ruft keine Datei diese Route auf (Trefferzahl 0). Die Karten-Auswertung hat also vermutlich keine Seite. | [C: `grep -c outcomes static/*.js *.html`] |
| W4 | `STUDIO_PLAN_SIMULATOR.md` S2 will Karten-Ergebnisse „on the Tierliste page as their own field"; `STUDIO_ROADMAP` B-2a will sie als „component" des Stärke-Index. Beides widerspricht B11 („zählen nicht in die Tierliste und werden dafür vorerst weder eingeholt noch verarbeitet"). | [D] |
| W5 | Harte Regel „2 bis 4 Sitze aktiv, 5/6 gesperrt" gegen Owner-Dokumente A3/P1 („2 bis 6", „one to five AI seats") und gegen den Code, der 2 bis 6 anbietet (`launch.py:32`, `partie.js:1054` laut Ist-Lage [D]). Die Sperre ist weder dokumentiert einheitlich noch technisch erzwungen. | [D] |
| W6 | Der Startspieler ist `seed % Spielerzahl` [C: `engine/rules/full_game.py:1514`]. Aufeinanderfolgende Seeds balancieren also die Zugreihenfolge. Der Rat „keine Seed-Arithmetik, hochentropischer Root-Seed" aus `simulate_methods.md` §3(7) würde diese Balance zerstören, wenn man ihn wörtlich umsetzt. | [C] |
| W7 | Die Planungstabelle im Repo rechnet mit angenommenen Diskordanzanteilen (0,09 / 0,20 / 0,40) und angenommener Blockkorrelation 0,25. Gemessen ist keiner dieser Werte. | [C: `full_game_comparison.py:618-648`] |

---

# TEIL A: SIMULATE neu denken

## A.1 Was der Mindeststandard verlangt und was es schon gibt

Maßstab sind die zwölf Punkte aus `simulate_methods.md` §5. „Vorhanden" heißt: im Quelltext
gelesen [C], nicht mit Engine gelaufen.

| Punkt des Mindeststandards | Stand in CPL | Lücke |
|---|---|---|
| 1 Einheit = Seed-Block | vorhanden: ein Cluster je Seed, cluster-robustes Student-t-Intervall, Vorzeichentest über Seeds (`paired_comparison.py:346-380`) | keine für A-gegen-B. Bei der Karten-Auswertung über alle Sitze einer Partie ungeprüft. |
| 2 n/N, Herkunft, Abbrüche getrennt | vorhanden: `pairs_censored`, `failure_classes`, „Misseated", Abbruch nie als Niederlage | keine |
| 3 Wilson statt Wald | vorhanden (`simulations.wilson_score_interval`, `card_outcomes`) | keine |
| 4 Vergleich gepaart auf Blockebene, Diskordanz-Tabelle | vorhanden (`variant_only_wins`, `baseline_only_wins`, `tied_pairs`) | Newcombe-Methode 10 ist nicht nötig, das cluster-t-Intervall ist bereits qualifiziert. Nicht doppelt bauen. |
| 5 Gemeinsame Seeds nur mit Platz-Tausch und gemessener Wirkung | Funktion vorhanden, im Studio-Pfad nicht verdrahtet (W1) | **Lücke.** Zusätzlich fehlt der Vergleich „gemessene Diskordanz gegen Unabhängigkeitswert". |
| 6 Planung vorab, nachweisbare Differenz im Ergebnis | Ergebnis trägt `detectable_difference_pp`; Planungsfunktionen `pairs_needed`, `power_table` existieren | Planung ist im Startdialog nicht sichtbar (dort nur Dauer), und sie rechnet mit Annahmen (W7). Budget-Obergrenze 1.000 Paare. |
| 7 Balancierte Sitzrotation, Sitz als Faktor | Rotation vorhanden (`rotate_seats=True`), Zugreihenfolge durch W6 balanciert | Sitzkurve je Serie wird nicht ausgewiesen. Einfache Serien werten das Deck fest auf Sitz 0 aus (`simulations.py:936`); balanciert ist das nur bei lückenlos fortlaufenden Seeds. |
| 8 Mehrfachvergleiche, Screening auf anderen Seeds | Holm existiert in der Engine-Lane (`_apply_holm`) | im Studio nicht: jede Serie startet standardmäßig bei Seed 1000 (`paired_series.py:393`), Screening und Bestätigung teilen sich also die Seeds. |
| 9 Stopp-Regel vorab | vorhanden: O'Brien-Fleming-Stufen über geplante Blicke | keine |
| 10 Nicht-Gewinn-Kennzahlen | Castability exakt hypergeometrisch (`castability.py`); Karten-Telemetrie und Kombo-Telemetrie je Partie (`simulations.py:236-247, 505-533`); Starthand-Vergleich randomisiert (`card_outcomes.py`) | Zeit-bis-Ereignis zensur-naiv (§0); keine Kennzahl „Zug des ersten Commander-Casts"; keine Intervalle für diese Kennzahlen. |
| 11 KI-Gültigkeit als Aussagegrenze | Text „these pilots, this pod set" in jedem Ergebnis | keine Sitzkurven-Plausibilität, kein Maß für Pilot-Auslassungen |
| 12 Herkunftsfelder | Seeds, Sitze, Pods, Engine-Commit, JAR-SHA-256, Brückenzustand, Piloten, Entscheidungspolitik, Deck-Hash | Zweck der Serie und benutzte Seed-Blöcke sind nicht registriert; `played_mainboard_sha256` fehlt, solange die Ausrichtung fehlt. |

Fazit: Fünf Punkte sind vollständig da (1, 2, 3, 4, 9), fünf teilweise (6, 7, 10, 11, 12), zwei
fehlen im Studio-Pfad (5, 8). Die Arbeit ist Verdrahten, Messen und Anzeigen, nicht Neubau
von Statistik.

## A.2 Die drei Optionen

### A1 Minimal-Härtung (Aufwand S; nur Python; keine Brücke, keine neue Abhängigkeit)

Architektur, in dieser Reihenfolge:
1. **Platz-Ausrichtung verdrahten.** `paired_series.start_series` ruft `align_to_baseline_slots`
   auf und speichert `played_mainboard_sha256` und die Zahl getauschter Plätze. Test: zwei
   Listen mit einem Tausch liefern bei gleichem Seed dieselbe Starthand, wenn die Tauschkarte
   nicht darin liegt (ein solcher Test existiert für die Engine-Lane:
   `tests/unit/test_full_game_slot_alignment.py`).
2. **Gepaarte Serien parallel spielen.** Die Paare eines Blick-Fensters gehen als Stapel an
   `play_batch` (mehrere Worker, mehrere Spiele je JVM). Paarung, Sitzplan, Zensur und
   Blick-Zeitpunkte bleiben. Nachweis wie in `STUDIO_PLAN_SIMULATOR.md` S1: jedes Spiel im
   Stapel hat denselben semantischen Hash wie allein gespielt.
3. **Planung sichtbar machen.** Der Startdialog zeigt zum Budget die nachweisbare Differenz
   (vorhandene Funktion). Das Ergebnis nennt die gemessene Paar-Streuung und die gemessene
   Diskordanz neben dem Unabhängigkeitswert (rund 0,39 bei 25 % Grundrate,
   `simulate_methods.md` §2.3). Feste Formulierung: „kein nachweisbarer Unterschied bei n = …;
   nachweisbar wären mindestens x Prozentpunkte", nie „Karte ist egal".
4. **Zensurbewusste Zeit-Kennzahlen.** `mean_first_cast_round` wird ergänzt durch „erreicht in
   n von N Partien" plus Median und Quartile, wobei „nicht erreicht" als eigene Klasse zählt.
5. **Seed-Plan-Hygiene.** Jede Serie trägt einen Zweck (Erkundung oder Bestätigung) und ihren
   Seed-Bereich. Eine Bestätigung auf Seeds, die schon die Erkundung gesehen hat, wird
   abgewiesen. Die fortlaufenden Seeds bleiben (W6).
6. **Sitz-Sperre technisch.** Serien und Partien mit 5 oder 6 Sitzen starten nur mit einem
   ausdrücklichen Schalter, der standardmäßig aus ist (setzt die bestehende Owner-Regel durch,
   ändert sie nicht).
7. **Erste echte Messung am Owner-PC:** ein Pilotblock Chulane-Basis gegen eine Variante mit
   einem Paket-Tausch, 40 Seeds mal 4 Sitze = 160 Paare = 320 Spiele. Zweck ist nicht das
   Urteil, sondern drei Messwerte, die bisher nur angenommen sind: Paar-Streuung, Diskordanz,
   echter Durchsatz des gepaarten Pfads.

- **Nutzen:** Die vorhandene Paarung wirkt erstmals wie beschrieben. Der Durchsatz gepaarter
  Serien steigt vermutlich um ein Mehrfaches (unbekannt, bis Schritt 7 gemessen ist). Die
  Roadmap-Stufe S-1 („erste echte Chulane-Serie"), für die es keinen Beleg gibt [D], wird erfüllt.
- **Risiken:** (a) Die Ausrichtung ändert die gespielte Kartenreihenfolge der Variante; alte
  und neue Serien sind nicht vergleichbar und dürfen nicht zusammengezählt werden (Schema-Nummer
  erhöhen). (b) Der Stapelbetrieb könnte Zustand von Spiel zu Spiel tragen; der Hash-Nachweis
  fängt das. (c) Wenn die Diskordanz trotz Ausrichtung nahe 0,39 bleibt, ist der Befund „Paarung
  bringt hier nichts" und A2 muss stärker auf Nicht-Gewinn-Kennzahlen setzen.
- **Mindeststandard danach:** Punkte 5, 6, 8 (teilweise), 10 (teilweise), 12 geschlossen.
- **Abgrenzung:** Baut nichts neu, was `paired_series`, O'Brien-Fleming, `card_outcomes`,
  `castability` schon können. Schritt 1 und 2 sind Wiederverwendung (AGENTS §9).
- **Owner-Freigabe:** keine nötig (Python, innerhalb der Lead-Delegation). Über 300 geänderte
  Zeilen gilt die Pflicht zum unabhängigen Review (AGENTS §10).

### A2 Empfohlen: „Deck-Labor mit Messprotokoll" (Aufwand M; A1 plus vier Bausteine)

1. **Serienplan als Datei vor dem ersten Spiel.** Frage, Schwelle, Budget, Blicke, Seed-Blöcke,
   Pods, Zweck, Zugehörigkeit zu einer Vergleichsfamilie. Das Ergebnis verweist auf den Plan
   und meldet jede Abweichung. Erweiterung des vorhandenen Job-Schemas, kein zweites System.
2. **Zwei-Stufen-Ablauf für Chulane.** Erkundung: wenige Kandidaten-Pakete, kleines Budget,
   Ausgabe nur als Rangfolge mit Intervall und dem Hinweis „Erkundung, nicht bestätigt".
   Bestätigung: höchstens die besten zwei oder drei auf frischen Seed-Blöcken, Holm-Korrektur
   über die vorab festgelegte Familie (vorhandene Funktion).
3. **Kennzahlen-Tafel „Konsistenz" in drei sichtbar getrennten Herkunftsklassen.**
   - *Exakt gerechnet* (kein Spiel nötig): Starthand-Verteilung, Farb-Castability je Zug,
     Anteil Hände mit 2 bis 4 Ländern. Vorhanden in `castability.py`.
   - *In der Engine gemessen, vom Piloten unabhängig:* Sieganteil mit Karte in der zuerst
     ausgeteilten Hand gegen ohne (randomisierte Exposition, vorhanden in `card_outcomes.py`).
   - *In der Engine gemessen, pilotabhängig:* Zug des ersten Commander-Casts, verpasste
     Land-Drops in den Zügen 1 bis 4, Kombo zusammengesetzt und ausgespielt, Karten, die die
     Engine als spielbar anbot und die nie gespielt wurden (`games_rotted`, vorhanden). Jede
     Kennzahl mit n/N, „nicht erreicht" als eigene Klasse, Quartilen und Block-Bootstrap-Intervall
     (Standardbibliothek).
4. **Gültigkeitsblock an jedem Ergebnis.** (a) Sitzkurve dieser Serie (Sieganteil nach Position
   in der Zugreihenfolge, Wilson) neben den Playgroup-Werten als von Hand eingetragene Konstante
   mit Datum, Quelle und deren Einschränkungen; kein automatischer Abruf. (b) „Auslassungen":
   wie oft die Engine eine Option anbot (Land spielen, Commander wirken) und der Pilot sie bis
   Zug T nicht nahm, als Zählung n/N. Das ist eine Beobachtung aus dem Protokoll, keine
   Bewertung einzelner Entscheidungen. (c) fester Satz: „gilt für diese Piloten, diese Pods,
   diese Engine-Version; keine Aussage über menschliches Spiel".
5. **Rückfluss in den Deckbau, ohne die Tierliste zu berühren.**
   - Anzeige nur an zwei Orten in CPL: Deck-Verlauf (vorhanden seit #1461, `deck_series.py`)
     und im Deckbauer beim Vergleich zweier Stände (Cut-Lab, Diff-Ansicht). Schlüssel ist das
     Paar aus Basis- und Varianten-Hash.
   - Die Kohorte heißt überall `SIMULATED_RESULT`, wird nie mit EDHREC-, Playgroup- oder
     TopDeck-Zahlen in einer Spalte gezeigt und nie über Commander oder Deck-Stände summiert.
   - Kein Sortierschlüssel, kein Rang, keine Kartennote aus Simulation. Auf der Tierliste-Seite
     erscheint nichts davon (Korrektur von W4, braucht O3).
   - Eine Serie zu einem anderen Deck-Stand wird nie als Ergebnis des aktuellen Standes gezeigt
     (Roadmap S-2).

- **Nutzen:** Aus „eine Zahl mit Intervall" wird ein Werkzeug, das die Deckbau-Frage beantwortet
  und zugleich sagt, wie weit man ihm trauen darf. Die Konsistenz-Tafel liefert auch dann
  Nutzen, wenn Gewinnraten-Unterschiede unter der Nachweisgrenze bleiben.
- **Risiken:** (a) Die pilotabhängigen Kennzahlen messen Deck mal Pilot; ohne den
  Gültigkeitsblock würden sie als Deck-Eigenschaft gelesen. (b) Die „Auslassungen" liegen nahe
  am Einfrieren der Pilot-Mikro-Messreihen vom 10.11. (S2). Ich halte sie für zulässig, weil
  nur gezählt wird, was im Protokoll steht, und kein Pilot verändert wird; das ist aber eine
  Owner-Frage (O4). (c) Mehr Anzeige heißt mehr Fläche für Missverständnisse; deshalb feste
  Sätze statt freier Texte.
- **Mindeststandard danach:** alle zwölf Punkte erfüllt, Punkt 11 in der schwachen Form
  (Plausibilität, keine Kalibrierung).
- **Owner-Freigaben:** O3 (Anzeigeort), O4 (Auslassungs-Zählung). Alles Übrige liegt in der
  Lead-Delegation.

### A3 Maximal (Aufwand L; A2 plus Forschungsteile)

- **Rundenbegrenzte Serien nur für Konsistenz-Kennzahlen.** Alle Piloten spielen voll, die
  Partie endet nach N Runden als zensiert. Kennzahlen bis Runde N bleiben unverfälscht, der
  Durchsatz steigt (Faktor unbekannt). Braucht eine Brücken-Änderung unter dem Studio-Bridge-Gate
  (Art `BEHAVIOUR`, Standard unbegrenzt) oder, falls möglich, einen vorhandenen Abbruchweg
  (zu prüfen). Kein „passiver Gegner": das wäre gegen P3 und S1.
- **Kontrollgrößen** mit exakt bekannten Hilfsgrößen (Länder in den ersten zehn Karten), um die
  Streuung der Gewinnrate zu senken. Wirkung unbekannt, Methode belegt (Owen §8.9 [R]).
- **Jederzeit gültige Intervalle** statt fester Blicke. Kosten: breitere Intervalle bei festem n.
- **Zufalls-Pods aus dem Precon-Bestand** mit Pod als eigenem Faktor (Roadmap S-5).
- **Vorausschau-Piloten** (S5, #1265) als eigener Messversuch.
- **Risiken:** Jede dieser Erweiterungen vergrößert die Analyse-Freiheit. Ohne Serienplan (A2)
  wären sie ein Rückschritt. Ein Mehr-Ebenen-Modell für Pods bräuchte eine neue
  Python-Abhängigkeit und damit einen Owner-Entscheid.
- **Owner-Freigaben:** Rundenlimit (Owner hat dazu nichts entschieden; berührt die Lesart von
  P3), neue Abhängigkeit, 5 und 6 Sitze.

**Empfehlung: A2, in zwei Lieferungen (erst A1, dann die vier Bausteine).** A3 erst, wenn der
Pilotblock aus A1 zeigt, wo die Streuung wirklich sitzt.

## A.3 Durchsatz

| Größe | Wert | Beleg |
|---|---|---|
| Batch-Serie (6 Worker, 8 Spiele je JVM), Owner-PC | 541,2 Spiele/h | [D: #1251] |
| Spiel in frischer JVM gegen warmer JVM | rund 85 gegen 37 CPU-Sekunden, 8 s Fixkosten je JVM | [D: `STUDIO_PLAN_SIMULATOR.md`, gemessen im Oktober, nicht neu gemessen] |
| Gepaarte Serie heute | unbekannt; ein Spiel je JVM, nacheinander | [C] |
| Schlanke Brücke S4 | kein Gewinn (318,1 s gegen 320,2 s), Zweig geparkt | [D: #1264] |
| AppCDS-Archiv | nicht bereitgestellt; bei 8 Spielen je JVM höchstens wenige Prozent | [E] aus den Fixkosten oben |

Der größte verbleibende Hebel ist also nicht die Engine, sondern (1) gepaarte Serien parallel
zu spielen und (2) weniger Spiele je Entscheidung zu brauchen: exakt rechnen, wo kein Spiel
nötig ist; wirksam paaren; früh stoppen, wenn der Effekt groß ist; Pakete statt Einzelkarten fragen.

## A.4 Stichprobenplanung: was eine Serie nachweisen kann

Eigene Rechnung mit der Repo-Formel, 95 % zweiseitig, 80 % Power. Zwei Annahmen sind
ungemessen und deshalb als Spanne gezeigt: die Paar-Streuung (aus dem Diskordanzanteil q) und
der Aufschlag für korrelierte Sitzrotationen eines Seeds (Design-Effekt 1,75 bei angenommener
Blockkorrelation 0,25, wie in der Repo-Planungstabelle).

| Paare | Spiele | Stunden bei 541/h | q rund 0,40 (Paarung wirkungslos) | q = 0,20 | q = 0,09 |
|---|---|---|---|---|---|
| 160 | 320 | 0,6 | 14 bis 19 pp | 10 bis 13 pp | 7 bis 9 pp |
| 400 | 800 | 1,5 | 9 bis 12 pp | 6 bis 8 pp | 4 bis 6 pp |
| 1.000 | 2.000 | 3,7 | 6 bis 7 pp | 4 bis 5 pp | 3 bis 4 pp |
| 2.700 | 5.400 | 10 | 3 bis 5 pp | 2 bis 3 pp | 2 pp |

Lesart: Die untere Zahl gilt, wenn die Sitzrotationen eines Seeds unabhängig sind, die obere
mit Design-Effekt 1,75. Das Standard-Budget von 20 Paaren (`paired_series.py:391`) kann nur
Unterschiede von mehreren Dutzend Prozentpunkten nachweisen; es taugt als Funktionsprobe,
nicht als Messung. Die Obergrenze von 1.000 Paaren sollte für Nachtläufe anhebbar sein.

**Stopp-Regel:** Die vorhandene bleibt (O'Brien-Fleming über vorab geplante Blicke; frühe
Blicke kosten fast kein Fehlerniveau). Neu ist nur, dass Budget, Blicke und Schwelle im
Serienplan stehen, bevor gespielt wird.

## A.5 Warum das besser ist als die gesichteten Projekte, und wo nicht

| Vergleich | Andere | Wir nach A2 |
|---|---|---|
| Regelbasis | Mana-Simulatoren ohne Regeln (Hareruya, EDHREC [R]); Forge mit eigener KI [G] | XMage als einzige Regelinstanz, externe Piloten |
| Unsicherheit | keine Intervalle (Hareruya, EDHREC), zwei Nachkommastellen ohne Fehlerbalken [R] | jede Zahl mit n/N und Intervall, nachweisbare Differenz |
| Sitz und Reihenfolge | Forge: Reihenfolge der Decks änderte Ergebnisse (Forum, nur Suchtreffer [R]) | Sitzrotation je Seed, Zugreihenfolge balanciert, Sitzkurve ausgewiesen |
| Vergleich zweier Listen | zwei unabhängige Läufe | gleiche Seeds, gleicher Tisch, ausgerichtete Bibliothek, Auswertung je Seed |
| Stoppen | feste Laufzahl oder freies Nachsehen | vorab festgelegte Blicke mit Fehlerniveau-Ausgabe |
| Abbrüche | Forge: nach 120 s Unentschieden [G] | eigene Klasse, nie Niederlage |
| KI-Grenze | Forge nennt Schwächen bei Kombo und Kontrolle [G], rechnet sie aber nicht ein | Gültigkeitsblock an jedem Ergebnis |

**Wo wir nicht schneller sind:** Für Spiele je Stunde anderer Engines gibt es keine Quelle [R].
„Schneller" heißt hier „weniger Spiele je belastbarer Antwort", nicht „mehr Spiele je Stunde".
Einen Beleg, dass unsere Piloten besser spielen als die Forge-KI, gibt es nicht.

**Bewusst nicht übernommen:**

| Was | Warum nicht |
|---|---|
| Forge, Magarena oder eine Rust-Engine als zweiter Simulator | zweites Regelwerk (AGENTS §2, D1); GPL/AGPL nur Ideenquelle |
| XMage-eigene KI als Sitz | Owner-Entscheid S4 |
| Regelfreier „Goldfish" mit vereinfachten Regeln | zweites Regelwerk. Erlaubt bleibt die regelfreie Zieh- und Mana-Rechnung (S6), und die ist exakt statt simuliert schon da. |
| Antithetische Zufallszahlen | setzen Monotonie voraus, die ein Kartenspiel nicht hat [R] |
| AIVAT (Poker-Verfahren) | braucht bekannte Strategie und Wertfunktion der Piloten [R, nur Abstract] |
| Plackett-Luce, OpenSkill | neue Abhängigkeit; bei einem einzigen Fokus-Deck kein Bedarf; modelliert Sitz und Block nicht [R] |
| Fishtest-Formeln (Pentanomial) | Formeln nicht belegt [R]; das qualifizierte cluster-t leistet dasselbe |
| Newcombe-Methode 10 | wäre ein Doppelbau neben dem cluster-t-Intervall |
| Hochentropische Seed-Ableitung nach NumPy-Muster | passt nicht: ein Engine-Seed je Spiel, Startspieler hängt am Seed (W6) |
| Landzahl-Formeln kommerzieller Seiten | Herkunft Werbung, Formeln widersprechen sich [R] |
| Kartenwertung aus Beobachtungsdaten als Ursache lesen (17Lands-Muster) | Selektionseffekte [R, nur Abstract] |
| Automatischer Abruf von Playgroup-Zahlen | Nutzungsbedingungen unklar [R]; Abgreifen ohne öffentliche Schnittstelle ist Owner-Vorbehalt (AGENTS §8) |

## A.6 Größte Unsicherheit in Teil A

**Ob gemeinsame Seeds in XMage überhaupt Streuung sparen.** XMage hat einen einzigen Regel-Seed
je Spiel [C: `XmageRulesSeedBinding`]. Nach der ersten abweichenden Zufallsentscheidung laufen
die beiden Partien eines Paares auseinander. Wie früh das geschieht, ist ungemessen. Der
Pilotblock aus A1 Schritt 7 beantwortet das für rund eine Stunde Rechenzeit; bis dahin sind
alle Ersparnis-Zahlen Annahmen. Zweite Unsicherheit: der wahre Effekt eines Kartenpakets auf
die Gewinnrate. Dafür gibt es keine Quelle.

---

# TEIL B: BUILD

## B.1 Lage in einem Absatz

Es gibt zwei lebende Deckbauer. CPL: 72 Studio-Module, rund 45.600 Zeilen, mit Tierliste und
Gesamtrating (#1369, Owner-Entscheid 18.11. laut Issue), Sammlung `collection_1655`, Chulane
als Fokus, Repo öffentlich [D, M]. DBS: 83 Module, rund 41.500 Zeilen, 164 gemergte PRs,
Tierliste per Owner-Entscheid vom 14.11. entfernt, andere Sammlung (1.324 Identitäten), kein
fest verdrahteter Commander, Repo privat, „BUILD-only" als Mandat [D, M]. Modulnamen decken
sich weitgehend. Keine Doku sagt, welcher der beiden der maßgebliche ist. Zwischen beiden gibt
es keinen Deck-Austausch: DBS exportiert Text mit „(Commander)" im Kartennamen, den der
CPL-Importer als Kartennamen liest [D: `ist_lage_dbs.md` §5.1].

## B.2 Wer ist kanonischer BUILD-Eigner?

| | B-X1: DBS kanonisch, CPL-Deckbauer eingefroren | B-X2: zwei Linien mit Vertrag | B-X3: Zusammenführung |
|---|---|---|---|
| Inhalt | DBS baut Decks. CPL behält Tierliste und Rating, PLAY, SIMULATE und vom Deckbauer nur: Deck annehmen, anzeigen, Engine-Prüfung, Partie und Serie starten, Serien zeigen. Kopplung nur über „Deck-Snapshot v1". | Beide Deckbauer wachsen weiter. Austausch über „Deck-Snapshot v1" in beide Richtungen. | Ein Repo, ein Deckbauer, ein Datenmodell. |
| Aufwand | M (Vertrag S, Einfrieren ist Verzicht, Doku S) | S (nur Vertrag) | L |
| Nutzen | ein Ort für neue Deckbau-Funktionen; kein Doppelbau mehr | kein Umbau, nichts geht verloren | sauberstes Endbild |
| Risiken | CPL-Funktionen, die DBS nicht hat (Cut-Lab mit Serien, 1-Klick-Start), bleiben auf altem Stand; der Owner braucht für Chulane beide Programme | Doppelbau bleibt, gleiche Fehler werden zweimal behoben, zwei Sammlungen bleiben ohne Abgleich, Produkte driften weiter | gegenläufige Regeln müssten zuerst aufgelöst werden: Tierliste (entfernt gegen aktiv), Sammlungsdaten im Repo (verboten gegen erlaubt), fester Fokus (keiner gegen Chulane), privat gegen öffentlich; 87.000 Zeilen auseinandergelaufener Code |
| Owner-Gate | O1; in DBS zusätzlich ein Owner-Merge, falls der neue Export als Scope-Änderung gilt (DBS-AGENTS §10) | O1 | O1 plus Änderung beider Mandatsdateien |

**Empfehlung: B-X1 in Stufen.** Stufe 1 ist der Vertrag in eine Richtung (DBS nach CPL); das ist
zugleich der Kern von B-X2 und schadet in keinem Fall. Stufe 2 ist die Owner-Erklärung, dass
neue Deckbau-Funktionen nur noch in DBS entstehen. B-X3 nicht jetzt.

**Was die Empfehlung kippen würde:** Wenn der Owner für Chulane tatsächlich im CPL-Deckbauer
arbeitet, weil dort die größere Sammlung und die Tierliste liegen, ist B-X2 ehrlicher. Das
weiß nur der Owner. Das ist die größte Unsicherheit in Teil B.

## B.3 Vertrag „Deck-Snapshot v1"

- **Form:** eine JSON-Datei. Sie erweitert das vorhandene CPL-Format aus `DECKBAU_INTERFACE.md`
  §1 (`deck_id`, `name`, `commander.commanders`, `cards[{oracle_name, quantity, zone}]`) um
  `schema`, `oracle_id` je Karte, `snapshot_hash` (SHA-256 über die sortierte Liste aus
  Oracle-ID, Anzahl, Zone) und `source` (Repo, Revisions-ID, Deck-Hash, Zeitpunkt,
  Werkzeug-Version). Der CPL-Lader liest Felder per `payload.get` und duldet Zusatzfelder
  vermutlich [C: `engine/rules/project.py`, nur teilweise gelesen; zu prüfen].
- **Was nicht drinsteht:** Stückzahlen im Bestand, Lagerorte, Notizen, Markierungen, Preise,
  Personennamen.
- **Sammlungstrennung:** Der Snapshot ist eine Deckliste, keine Besitzaussage. CPL prüft nur
  den Engine-Status jeder Karte (bekannt, unbekannt, kein Pilotwissen) und bucht nichts gegen
  `collection_1655`. Eine Karte, die die Engine nicht kennt, bleibt `UNKNOWN` und verhindert
  den Start mit Begründung (B9); sie wird nie stillschweigend ersetzt.
- **Prüfbarkeit:** dieselbe Beispieldatei liegt byte-gleich in beiden Repos; je Repo ein Test
  (DBS: Export erzeugt genau diese Datei; CPL: Import liest sie und liefert den erwarteten
  Hash). Kein gemeinsamer Code, kein Submodul.
- **Identität für SIMULATE:** Serien und Partien binden an `snapshot_hash`. Damit ist die
  Roadmap-Forderung S-2 („Serie an Deck-Stand binden") auch über die Repo-Grenze erfüllt.

## B.4 Rückkanal der Simulation

| | R0: nur in CPL anzeigen | R1: Datei-Import in DBS | R2: Live-Kopplung |
|---|---|---|---|
| Inhalt | CPL zeigt Serien zum `snapshot_hash` im Deck-Verlauf. DBS zeigt nichts. | DBS liest eine Serien-Zusammenfassung als eigene, nur lesbare Kohorte „Simulation". | DBS fragt CPL zur Laufzeit. |
| Verträglich mit DBS-Mandat | ja | **nein**: §1 („keine Simulation"), §3 (neue Kohorte), §10 (Scope ist Owner-Sache); die Mandatsdatei mergt nur der Owner | nein, zusätzlich technische Kopplung |
| Empfehlung | **jetzt** | erst nach Owner-Entscheid O2 | nicht |

## B.5 Scope-Optionen BUILD

| | Minimal | Empfohlen | Maximal |
|---|---|---|---|
| Inhalt | Offenes zu Ende bringen: fünf P2 aus #1509 und der unversionierte Folgestand, #1369; in DBS die drei offenen PRs und #321. Kein Vertrag, keine Eigner-Entscheidung. | Minimal plus O1, Deck-Snapshot v1 (Stufe 1), Einfrieren des CPL-Deckbauers, Simulations-Kohorte in CPL (R0), Doku beider Repos nennt das jeweils andere. | Empfohlen plus R1, ein nur lesender Abgleichsbericht beider Sammlungen (Owner entscheidet jede Abweichung), Engine-Status im DBS-Pool, ein gemeinsamer Starter. |
| Aufwand | S | M | L |
| Abhängigkeiten | keine | O1; für die Simulations-Kohorte SIMULATE A1 | O2 und Mandatsänderung in DBS |
| Owner-Gates | keine neuen | O1, O3 | O1, O2, O3 |

**Zusätzliche BUILD-Risiken:**
- DBS #307 („Fehlende Kernkarten") liegt nahe am Kaufverbot; vor dem Merge muss im PR stehen,
  warum es keine Kauf-Funktion ist [D: `ist_lage_dbs.md` R6].
- Das modellgestützte „Kartenverständnis" im CPL-Gesamtrating (Entscheid 18.11. laut #1369)
  steht in Spannung zu A4/B4 („nur objektive Daten, keine Meinungen") [D]. Das ist kein
  Simulationsthema, braucht aber eine Owner-Formulierung in der Entscheidungsdatei (O5).
- CPL ist öffentlich und enthält Sammlungsdaten; A6 nennt das Repo „working/private"; #1108
  ist offen [D, M]. Owner-Sache (O10).

---

# TEIL C: PLAY

## C.1 Lage

Auf `main` laufen alle 17 Entscheidungsklassen über Knöpfe, Zahlenfelder und Listen;
Vorspulen sendet ausschließlich die Pass-Option der Engine und hält bei jeder anderen
Entscheidung, beim eigenen Zugbeginn und wahlweise bei einem gegnerischen Objekt auf dem Stack
[C: `static/vorspulen.js`]. Es fehlen: Klick auf das Brett, jeder Test des Mensch-Sitzes mit
echter Engine, und der Nachweis einer ganzen Partie am Owner-PC [D]. Der Brett-Klick-Stand
liegt unversioniert in einem flüchtigen Arbeitsverzeichnis [D].

## C.2 Abnahme-Definition „wirklich spielbar" (messbar)

Ausgangspunkt ist der Satz aus `STUDIO_ROADMAP_20261112.md`: Der Owner spielt eine ganze
Partie mit Chulane gegen drei KI-Sitze am eigenen Rechner ohne Zeitlimit. Vorschlag zur
Schärfung (O6):

| # | Kriterium | Messung |
|---|---|---|
| AK-1 | Drei vollständige Vierer-Partien Chulane gegen drei KI am Owner-PC, jede bis zum von der Engine gemeldeten Spielende | drei Spielprotokolle mit Spiel-ID, JAR-SHA-256, Brückenzustand |
| AK-2 | Kein Hänger: keine offene Entscheidung, die die Seite nicht beantworten kann; kein Neustart, keine Entwicklerkonsole | Zählung 0 über die drei Partien; jeder Hänger ist ein Befund mit Protokollstelle |
| AK-3 | Abdeckung der Entscheidungsklassen: wie oft ein Mensch jede der 17 Klassen in echten Partien beantwortet hat | Tabelle n je Klasse aus den Protokollen; nicht vorgekommene Klassen stehen als `UNKNOWN`, nicht als bestanden |
| AK-4 | Brett-Klick für Ziel, Angreifer, Blocker, Karte aus der Hand, Fähigkeit eines Permanents; die Listen bleiben als Ausweichweg | Test: jeder Klick sendet nur eine `option_id` aus `legal_options` |
| AK-5 | Verdeckte Information: keine Handkarte eines KI-Sitzes in irgendeiner Antwort während der Partie; nach Spielende offen | vorhandener Test bleibt grün; Sichtprüfung nach Spielende |
| AK-6 | Tempo: Zahl der Entscheidungen, die der Mensch je Partie treffen musste, mit und ohne Vorspulen; Wartezeit zwischen zwei eigenen Entscheidungen (Median) | aus dem Protokoll; **Zielwerte erst nach der ersten Messung festlegen**, heute gibt es keine Zahl |
| AK-7 | Banner „Brücke vor Qualifikation" sichtbar; nichts als versiegelt abgedeckt dargestellt | Sichtprüfung |
| AK-8 | Urteil des Owners in einem Satz je Partie: was hat gestört | Kommentar im Issue |

## C.3 Yield-Modell: was von Forge übernommen wird und was nicht

Zulässig ist nur, was diese drei Bedingungen hält (Owner 17.11. laut #1167 [D], AGENTS §2):
Gesendet wird ausschließlich die Pass-Option, die die Engine selbst angeboten hat. Jede andere
Entscheidung hält an. Jeder automatische Pass steht im Protokoll.

| Forge-Element [G] | Bei uns |
|---|---|
| Auto-Pass, „wenn nichts spielbar ist" | **nicht so.** Die Seite darf nicht ausrechnen, ob etwas spielbar ist. Erlaubt: passen, wenn die Engine als einzige Option den Pass anbietet (das erledigt serienseitig schon der Schalter für erzwungene Entscheidungen), sonst nur auf ausdrücklichen Wunsch des Menschen. |
| Yield bis der Stack leer ist, unterbrechbar | ja, als Modus des vorhandenen Vorspulens |
| „Resolve entire stack", nicht unterbrechbar | **nicht so.** Bei uns hält jede Nicht-Prioritäts-Entscheidung immer an. |
| Phasenmarker je Spieler und Phase | ja, sofern Phase und aktiver Spieler aus dem veröffentlichten Zustand kommen (P1) |
| Unterbrecher (Angriff auf mich, Gegner wirkt Zauber, ich werde angezielt, Auslöser auf dem Stack) | ja, soweit der veröffentlichte Zustand das trägt; „Gegner-Objekt auf dem Stack" gibt es schon |
| „Hold priority" | normale Spieleraktion, kein Überspringen |

Jede Vorspul-Antwort kostet heute eine Anfrage der Seite [D]. Ein serverseitiges Yield
(der Python-Dienst beantwortet auf Dauerauftrag des Menschen mit der Pass-Option) wäre
schneller und bräuchte keine Brücken-Änderung. Es berührt aber den Wortlaut von AGENTS §2
(„silent skip", „default") und gehört deshalb vor dem Bau durch ein unabhängiges Review (P2).

## C.4 P0, P1, P2

**P0: ohne das keine Abnahme**
1. Brett-Klick-Stand und den Tierliste-Folgestand committen und pushen (AGENTS §14).
2. Brett-Klick fertigstellen (AK-4): Ziele, Angriff, Block, Hand, Fähigkeiten, über die
   Objekt-IDs, die die Brücke schon liefert [D]. Mehrdeutigkeit über ein Auswahlfeld.
3. Echt-Engine-Test des Mensch-Sitzes ohne Mensch: Ein vorhandener Pilot beantwortet die
   Entscheidungen über die PLAY-Routen. Reiner Test, kein Produktionspfad, keine
   Erste- oder Zufallsoption. Erfüllt die Pflicht aus AGENTS §10 für Pfade, die der
   Referenzsatz nicht erreicht.
4. Sitz-Sperre: 5 und 6 Sitze nur mit ausdrücklichem Schalter (wie A1 Schritt 6).
5. Kleinigkeiten: Beschriftung der Klasse `amount`; Mulligan mit Zurücklegen einmal mit
   echter Engine geprüft.
6. Abnahme-Partien am Owner-PC (AK-1 bis AK-8).

**P1: macht aus „bedienbar" „angenehm"**
Stack-Schiene mit Zielen; Zielpfeile; Anzeige von Commander-Steuer und Commander-Schaden
ausschließlich aus Engine-Werten (Bezeichner dafür stehen im Brücken-Quelltext [C]; ob sie im
Frame des Menschen ankommen, ist zu prüfen; neuer Frame-Inhalt wäre eine `BEHAVIOUR`-Änderung
unter dem Bridge-Gate); Tastatur mit sichtbarem Fokus; Karten-Inspektor; Yield-Modi nach §C.3;
Wiedergabe einer beendeten Partie Zug für Zug auf Basis der vorhandenen Zuschauer-Ansicht
und der Protokolle.

**P2: nur nach Owner-Wunsch**
Speichern und Fortsetzen (Owner: „nur wenn sinnvoll" [D]); serverseitiges Yield; Bedienung per
Berührung; Mensch auf anderem Sitz als 1; Bildvergleichs-Tests (neue Abhängigkeit, Owner);
5 und 6 Sitze (Owner). Nicht geplant: freies Rückgängig (P4), Erklärung einzelner
KI-Entscheidungen (eingefroren 10.11.), passiver Gegner (P3).

## C.5 Scope-Optionen PLAY

| | Minimal | Empfohlen | Maximal |
|---|---|---|---|
| Inhalt | P0 | P0 + P1 | P0 + P1 + P2 |
| Aufwand | M | M bis L | L |
| Abhängigkeiten | Owner-PC für die Abnahme | wie Minimal; für die Commander-Anzeige evtl. Bridge-Gate | Owner-Entscheide zu Speichern, Sitzen, Abhängigkeit |
| Owner-Gates | O6 (Abnahme-Definition), Owner spielt | zusätzlich keine | O7, O8, O9 |

**Empfehlung: „Empfohlen", aber die Abnahme (AK-1 bis AK-8) schon nach P0 spielen.** Die
P1-Reihenfolge soll aus AK-8 folgen, nicht aus fremden Projekten.

**Größte Unsicherheit in Teil C:** ob eine ganze Partie mit echter Engine überhaupt ohne Hänger
durchläuft. Alle Tests des Mensch-Sitzes laufen gegen einen nachgebauten Client [D]. Punkt 3
aus P0 beantwortet das, bevor der Owner Zeit investiert.

---

# TEIL D: Ordnung schaffen

## D.1 PR #1510 und `STUDIO_TARGET_SCOPE.md`

| Option | Bewertung |
|---|---|
| Übernehmen | nein. CI rot (`assert` in `studio/doctor.py`), PR-Text behauptet „pytest PASS", ändert Policy-Text und Workflow ohne unabhängiges Review, macht ein Dokument ohne Owner-Quelle zur Pflichtlektüre [D: `ist_lage_cpl.md` §4]. |
| Verwerfen | verschenkt drei brauchbare Teile |
| **Ersetzen (Empfehlung)** | Den PR nicht mergen und nicht anfassen (fremder aktiver Zweig, AGENTS §11). Der Lead bittet den Autor per Kommentar um Aufteilung: (1) Release-Paket mit Brücken-JAR (#1172 Punkt 2), (2) `doctor`-Befehl ohne `assert`, (3) die sachlich richtige Korrektur in AGENTS §10 zu #1401. Jeder Teil mit eigenem Review. Das Zieldokument, die Pflichtlektüre in AGENTS §1 und die Lane-Zuteilung in `CLAUDE.md` entfallen. |

Was aus dem Zieldokument inhaltlich bleibt und was nicht:

| Punkt des Zieldokuments | Einordnung |
|---|---|
| Herkunftsfelder, `simulation`-Gewicht 0, 2 bis 4 Sitze, kein Fork-Push | deckt sich mit den Owner-Regeln |
| Parallele gepaarte Stapel | richtig und nötig (A1 Schritt 2) |
| Ergebnis-Rückfluss in SIMULATE und Deckbauer, getrennt von der Tierliste | deckt sich mit A2 |
| Schlanke Brücke S4 | überholt: #1264 nicht geplant, kein Gewinn gemessen |
| AppCDS | geringer Nutzen [E]; nicht vorrangig |
| Rundenlimit, „6-Turn-Goldfish" | ohne Owner-Quelle; als A3-Option mit vollen Piloten denkbar (O-Frage) |
| „Passive-AI-Goldfish" | gegen P3 |
| Pilot-Fehlentscheidungsberichte | gegen das Einfrieren vom 10.11.; die Zählung von Auslassungen (A2) ist die zulässige Form, vorbehaltlich O4 |
| „Resolve All" | nur in der Form aus §C.3 |
| Multi-Commander, Spaltenansicht | über den Chulane-Fokus hinaus bzw. ohne Owner-Quelle; gehört nach B-X1 ohnehin nach DBS |

Ersatz für das Zieldokument: Nach den Owner-Entscheiden aus §F entsteht **ein** Scope-Dokument,
das je Zeile seine Owner-Quelle nennt. Dieses Papier ist dafür die Vorlage, nicht das Dokument.

## D.2 Doku-Drift bereinigen

Reihenfolge nach Schaden. Policy-Texte brauchen ein unabhängiges Review vor dem Merge;
Dokumente mit Owner-Entscheiden werden fortgeschrieben oder archiviert, nie gelöscht (AGENTS §9).

| # | Wo | Drift | Vorschlag |
|---|---|---|---|
| 1 | `OWNER_DECISIONS_STUDIO_20261112.md` | Entscheide vom 17.11. (Hände nach Spielende offen, unbegrenztes Warten, Auto-Pass und Vorspulen, Speichern nur wenn sinnvoll, anklickbares Brett) und vom 18.11. (Kartenverständnis im Gesamtrating) fehlen | nachtragen, sobald der Owner den Wortlaut bestätigt hat (O5). Bis dahin als „von Agenten zitiert, unbestätigt" kennzeichnen. |
| 2 | dieselbe Datei, A3/P1 gegen Sitz-Regel | „2 bis 6" gegen „2 bis 4 aktiv" | eine Zeile: aktiv 2 bis 4; 5 und 6 nach eigener Qualifikation und Freigabe |
| 3 | `STUDIO_PLAN_SIMULATOR.md` S2, `STUDIO_ROADMAP` B-2a | Simulation auf der Tierliste-Seite bzw. als Komponente | streichen nach O3 |
| 4 | `STUDIO_ROADMAP_20261112.md` | Mensch-Sitz „offen", P-1 bis P-7, Roadmap kennt DBS nicht | als abgelöst kennzeichnen; neue Roadmap nach §E |
| 5 | AGENTS §10 | „#1401 … Neither exists yet" ist überholt | Korrektur als eigener kleiner Policy-PR mit Review |
| 6 | `OPERATIONAL_SIMULATION_POLICY.md` | „MAX_PLAYERS=5, qualifiziert 2 bis 5" gegen Code 6 | an Code und Sitz-Regel angleichen; Qualifikationsstand 5/6 als unbekannt ausweisen |
| 7 | `STUDIO_GAME_VIEWER.md` | zwei Abschnitte widersprechen sich zum Mensch-Sitz | alten Abschnitt entfernen |
| 8 | A6 | „working/private repository", Repo ist öffentlich | Owner-Sache (O10) |
| 9 | Issues | #1167-Text veraltet; #1265 offen mit altem Claim, obwohl PR #1457 ungemergt geschlossen wurde | Stand-Kommentar; Claim freigeben oder bestätigen |
| 10 | DBS | AGENTS §6 „keine Required Checks" gegen aktive Pflicht-Checks; `ACCEPTANCE_STATUS.md`; sieben gelieferte Issues noch offen; Abgleich-Wasserzeichen vom 11.11. | Korrektur-PR durch die DBS-Lane, Merge durch den Owner (Mandatsdatei) |
| 11 | beide `AGENTS.md` | CPL nennt DBS nicht; DBS nennt CPL nur als Quelle | nach O1 je ein Satz zur Rollenverteilung |

## D.3 Claims und Zuständigkeiten (AGENTS §11)

Problem: Alle Agenten schreiben unter demselben GitHub-Login; wer was hält, steht nur im Text
von Kommentaren [D]. Zwei Stände liegen unversioniert bei einer Sitzung, die inzwischen an
etwas anderem arbeitet. Ein zweiter Agent hat mit #1510 Scope beschrieben, den formal eine
andere Sitzung hält.

Vorschlag, ohne neue Policy:
1. **Eine Claim-Tabelle im Übersichts-Issue #1167**, vom Lead gepflegt: Lane, Issue, Halter,
   Zweig, letzter Push. Lanes: Tierliste (#1369), PLAY Brett-Klick und Abnahme, SIMULATE A1/A2
   (neues Issue), Doku-Bereinigung (neues Issue), Vertrag „Deck-Snapshot v1" (je ein Issue in
   CPL und DBS), S5 (#1265).
2. **Kein Claim ohne gepushten Zweig** nach dem ersten Meilenstein (AGENTS §14 verlangt das
   bereits).
3. **PLAY und SIMULATE trennen.** Die Mutationsflächen sind disjunkt (`partie.*`, `play.py`
   gegen `paired_*`, `simulations.py`, `card_outcomes.py`), also zwei Issues, zwei Halter möglich.
4. **Über die Repo-Grenze:** Kein CPL-Agent schreibt in DBS und umgekehrt. Der Vertrag wird als
   zwei Pakete gebaut, die nur die Beispieldatei teilen.
5. **Altes aufräumen:** Label `agent:muse` auf #1369 entfernen oder ersetzen; #1265-Claim klären.
6. Eine Verfallsregel für stille Claims wäre eine Policy-Änderung (Review, ggf. Owner). Ich
   empfehle sie nicht jetzt; die Tabelle reicht, solange der Lead sie pflegt.

---

# TEIL E: Roadmap-Skizze bis Projektabschluss

Keine Kalenderdaten: Die Dauer hängt an Owner-Zeit am PC und an Nutzungslimits der Sitzungen.

| Phase | Inhalt | Abnahme | Owner entscheidet | Am Owner-PC |
|---|---|---|---|---|
| 0 Sichern und klären | unversionierte Stände pushen; fünf P2 aus #1509; #1510 adjudizieren; Claim-Tabelle; Entscheidungspaket §F vorlegen | beide Zweige auf GitHub; Tabelle steht; #1510 mit Lead-Kommentar | O1, O3, O5, O6 | nichts |
| 1 PLAY P0 | Brett-Klick, Echt-Engine-Test des Mensch-Sitzes, Sitz-Sperre, Kleinigkeiten | Tests grün auf exaktem Head; Review; Echt-Engine-Test läuft durch | keine | drei Abnahme-Partien (AK-1 bis AK-8) |
| 2 SIMULATE A1 (parallel zu 1) | Ausrichtung, parallele gepaarte Serie, Planung, Zensur, Seed-Plan | Starthand-Gleichheitstest; Hash-Nachweis Stapel gegen Einzelspiel | keine | Pilotblock 320 Spiele; liefert Streuung, Diskordanz, Durchsatz |
| 3 BUILD-Klärung und Doku | Deck-Snapshot v1 Stufe 1; CPL-Deckbauer einfrieren; Doku-PRs nach §D.2; ein Scope-Dokument mit Owner-Quellen | Beispieldatei in beiden Repos mit je einem Test; Doku ohne die Widersprüche W4, W5 | O1 umgesetzt, O10 | ein DBS-Deck nach CPL bringen und starten |
| 4 SIMULATE A2 und PLAY P1 | Serienplan, Zwei-Stufen-Ablauf, Konsistenz-Tafel, Gültigkeitsblock, Anzeige im Deck-Verlauf; Stack-Schiene, Commander-Anzeige, Tastatur, Yield-Modi, Wiedergabe | zwölf Punkte des Mindeststandards je mit Test oder Beispielergebnis; P1 nach AK-8 priorisiert | O4 | eine Nachtserie zu einer echten Chulane-Frage; Spielprobe P1 |
| 5 Abschluss | Brücke: neue Qualifikations-Epoche oder dauerhaft „vor Qualifikation" ausweisen; Release-Paket mit Brücken-JAR; Prüfliste Owner-PC-Einrichtung; Entscheidung zu 5/6 Sitzen und zu #1108; A3-Teile nur auf Wunsch | Abschlusskriterien unten | O7 bis O12 | Einrichtung nach `STUDIO_OWNER_PC_SETUP.md` von null; eine Partie und eine Serie auf dem Release-Stand |

**Projekt gilt als abgeschlossen, wenn:**
1. PLAY: AK-1 bis AK-8 erfüllt und vom Owner bestätigt.
2. SIMULATE: eine vom Owner gestellte Chulane-Frage ist mit Serienplan, Ergebnis, Intervall,
   nachweisbarer Differenz und Gültigkeitsblock beantwortet und im Deck-Verlauf sichtbar.
3. BUILD: ein Deck geht ohne Handarbeit aus dem kanonischen Deckbauer in Partie und Serie;
   die Tierliste (#1369) ist vom Owner abgenommen.
4. Regeln: `simulation`-Gewicht 0 durch Test gesichert; 5/6 Sitze technisch gesperrt oder
   freigegeben; keine Zahl ohne n/N.
5. Doku: ein Scope-Dokument, eine Entscheidungsdatei, keine der Widersprüche aus §1 und §D.2 offen.
6. Betrieb: Einrichtung am Owner-PC aus dem Release-Paket nachvollzogen; Zustand der Brücke
   gegenüber dem Siegel ehrlich ausgewiesen.

**Reihenfolge-Begründung:** Phase 0 zuerst, weil unversionierte Arbeit verloren gehen kann.
PLAY P0 vor P1, weil nur eine echte Partie zeigt, was stört. SIMULATE A1 parallel, weil die
Flächen disjunkt sind und der Pilotblock alle späteren Budgets bestimmt. Die Eigner-Frage
(O1) früh stellen, aber den Vertrag so bauen, dass er bei jeder Antwort brauchbar bleibt.

---

# TEIL F: Was der Owner entscheiden muss

| # | Frage | Empfehlung | Betrifft |
|---|---|---|---|
| O1 | Wer ist kanonischer Deckbauer: DBS (CPL-Deckbauer eingefroren), beide, oder Zusammenführung? | DBS kanonisch, in Stufen (B-X1) | BUILD |
| O2 | Darf DBS Simulationsergebnisse als eigene Kohorte zeigen? (ändert DBS-AGENTS §1, §3) | vorerst nein; Anzeige nur in CPL (R0) | BUILD, SIMULATE |
| O3 | Gilt „Simulation nie in die Tierliste" auch für die bloße Anzeige auf der Tierliste-Seite? | ja; Anzeige nur im Deckbauer und im Deck-Verlauf | SIMULATE, Doku |
| O4 | Ist das Zählen von Auslassungen der Piloten aus dem Protokoll zulässig, obwohl Pilot-Mikro-Messreihen eingefroren sind? | ja, als reine Zählung ohne Pilot-Änderung | SIMULATE |
| O5 | Bestätigung der Entscheide vom 17.11. (PLAY) und 18.11. (Kartenverständnis im Rating) im Wortlaut, samt Verhältnis zu „nur objektive Daten" | bestätigen und in die Entscheidungsdatei aufnehmen | Doku |
| O6 | Abnahme-Definition PLAY (AK-1 bis AK-8) | annehmen; Tempo-Zielwerte nach erster Messung | PLAY |
| O7 | Speichern und Fortsetzen einer Partie | erst nach den Abnahme-Partien entscheiden | PLAY |
| O8 | Rundenbegrenzte Serien mit vollen Piloten für Konsistenz-Kennzahlen (Brücken-Änderung) | nur falls A2 zeigt, dass der Durchsatz dafür nicht reicht | SIMULATE |
| O9 | Neue Abhängigkeiten (Bildvergleichs-Tests, Statistikpaket) | nein; alles Nötige geht mit der Standardbibliothek | PLAY, SIMULATE |
| O10 | Sichtbarkeit von CPL und #1108 | Owner-Sache; ohne Empfehlung | Governance |
| O11 | 5 und 6 Sitze | nicht Teil des Abschlusses; technisch sperren | PLAY, SIMULATE |
| O12 | Brücke nach dem Siegel: neue Qualifikations-Epoche zum Abschluss oder dauerhaft als „vor Qualifikation" ausweisen | zum Abschluss neu versiegeln, falls der Aufwand vertretbar ist; Aufwand ist unbekannt | Governance |

**Was der Owner selbst testen muss:** die drei Abnahme-Partien (Phase 1), ein Deck aus DBS in
CPL starten (Phase 3), die Spielprobe der P1-Teile (Phase 4), die Einrichtung von null (Phase 5).

**Was am Owner-PC laufen muss, ohne dass der Owner dabeisitzt:** der Pilotblock (rund eine
Stunde, falls gepaarte Serien den Batch-Durchsatz erreichen), die Nachtserie, der
Brücken-Vergleich auf dem Referenzsatz bei jeder Brücken-Änderung.

---

## Anhang: Annahmen und Grenzen dieses Papiers

- Ich habe keine Engine gestartet und keinen Test ausgeführt. Alle [C]-Befunde sind aus dem
  Quelltext gelesen; W1 und W2 sollten vor jeder Planung durch einen kurzen Lauf bestätigt
  werden (zwei Partien eines Paares mit einem Tausch: sind die Starthände gleich?).
- „Sammlungstrennung" lese ich so: Die beiden Sammlungen bleiben getrennte Datenbestände und
  werden nicht verrechnet. Falls damit etwas anderes gemeint ist, ändert sich §B.3 Punkt 3.
- Die Zeilenzahlen, PR-Zahlen und Teststände der beiden Repos stammen aus den Ist-Lage-Berichten
  [D]; nachgemessen habe ich nur die in §1 genannten Punkte.
- Aufwand S/M/L ist eine grobe Ordnung (S: ein bis zwei kleine PRs; M: mehrere PRs mit Review;
  L: mehrwöchige Lane), keine Schätzung in Tagen.
