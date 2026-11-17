# Tierliste (Stärke-Index): Ist-Analyse, Recherche und Verbesserungsplan — 2026-11-17

**Auftrag (Owner, 2026-11-17):** Die Tierliste vollständig ansehen — wie sie funktioniert, wie die Karten
gerankt werden, was wie angezeigt wird — und einen Verbesserungsplan mit Optionen und Empfehlungen vorlegen.
**Dies ist Analyse und Plan, kein Bau.** Nichts davon ist beschlossen; Entscheidungen stehen in Abschnitt 4.

**Methode/Ehrlichkeit:** Stand `main` `6972e8b1d`, Chulane, Pool 927 Karten. Messungen mit dem Studio-Code
selbst (`strength_view.prepare`, `strength.score_pool`, `ranking-check`, `POST /api/strength`) auf einer
Kopie des QA-Stores, nichts nachgebaut. Die Ist-Analyse stammt von einem Analyse-Lauf; **die Kernfakten
(Gewichte, Schnitte, E2.a-Regel) wurden im Code nachgeprüft**, alles andere ist agent-gemessen und noch
nicht unabhängig reproduziert. Recherche: vier Web-Lanes (Haiku), überwiegend Sekundärquellen — vor einer
Übernahme in Regeltext Primärtexte prüfen. Eine UX-Abnahme (Playwright, 4 Fenstergrößen, Hell/Dunkel) lieferte
20 Befunde.

## 1. Wie die Tierliste heute funktioniert (belegt)

- **Gewichte** (`strength.py` `DEFAULT_WEIGHTS`, Summe 10): `deck_universe` 4,0 · `corpus_tuned` 1,5 ·
  `corpus_log_lift` 1,0 · `corpus_bracket_slope` 1,0 · `global_inclusion` 1,0 · `tournament` 0,5 ·
  `edhrec_theme_reach` 0,5 · `combos` 0,5. `commander_inclusion` (3) und `bracket_inclusion` (2) sind
  angefragt, aber **wirksam 0**, solange ein Korpus mit ≥ 30 Decks existiert (Regel E2.a). Simulation,
  Playgroup, Rubrik, Synergie, TopDeck-Spalten: 0 (Owner-Regel B11: Simulation Gewicht 0).
- **Normierung:** Anteile als Wilson-Untergrenze (Nenner ≥ 500) bzw. Empirical-Bayes (< 500), danach
  Log-Skala `ln(1+150v)/ln(1+150·v_max)` — das ist **kein Perzentil**, heißt aber im Code/UI `percentile`
  bzw. „Perzentil“. Combos/Synergie/Playgroup/Ebenen: Perzentilrang. Länder und Zauber getrennt skaliert.
- **Index** = 100·Σ(w·s)/Σw über die **vorhandenen** Komponenten; Coverage = vorhandenes/mögliches Gewicht.
  Eine **gezählte 0 von N** zählt als vorhanden mit Score 0 (Regeln B12/E4.b).
- **Stufen:** feste Schnitte **S ≥ 54 · A ≥ 35 · B ≥ 20 · C ≥ 5 · sonst D** (`DEFAULT_CUTS`); abgeleitet in
  #1366 nach einer vorab festgelegten Regel (C knapp über dem höchsten Index einer Karte mit nur gezählten
  Nullen; A so, dass jede Karte mit < 5 % der Listen aus S/A bleibt; S ≈ 3 % der gerankten Zauber; B = Mittelpunkt),
  „nicht auf Karten abgestimmt“. **Die Doku nennt noch 47/17/9/4 — veraltet** (Doku-Drift). Gleiche Schnitte
  für Länder, Zauber, alle Presets und Skalen. U („unbekannt“) bei Coverage < 0,25, < 2 Komponenten, ohne
  commander-spezifisches Signal; N für Commander, Standardländer, andere Commander.
- **„grenzwertig“** = Index weniger als 2,0 Punkte von der nächsten Grenze. **Konfidenz** = Coverage ×
  gewichtetes n/(n+30) (n = Nenner), „hoch“ ab 0,6.
- **Kohorten:** `deck_universe` = alle 10.128 lokalen Decks (9.440 EDHREC + 710 Archidekt); `corpus_tuned` =
  Bracket 4+5 (1.066); Bracket-Neigung aus Bracket 2 (608) und 5 (256); `tournament` = EDHTop16 (48 Einträge,
  16 Pool-Karten) **plus** Korpus-Bracket 5.
- **Anzeige:** Kopfblöcke, Stufenzähler, Verteilungstabelle, Einstellungen (6 Gruppen), Filter (Typ,
  Länder/Zauber, Rolle, Verbreitung, **Gesamtpool | Gleiche Funktion**, Stufe, Ebenen-Spalten, > 30
  Sortierungen), Zeile mit Index-Badge, Konfidenz-Punkten, „grenzwertig“, Rollen mit `#r/N`, n/N-Zellen;
  Karten-Fenster mit Signaltabelle (Rohwert, n/N, Score, wirksames Gewicht, Status, Datenklasse).

## 2. Messungen (Chulane, Pool 927, 922 gerankt; agent-gemessen)

| | S | A | B | C | D | U | N |
|---|---|---|---|---|---|---|---|
| Alle | 39 | 33 | 48 | 185 | 617 | 0 | 5 |
| Zauber | 26 | 22 | 38 | 172 | 599 | 0 | 1 |
| Länder | 13 | 11 | 10 | 13 | 18 | 0 | 4 |

- Indexwerte: Min 0,0 · Q1 0,4 · Median 1,9 · Q3 7,9 · p90 28,7 · Max 80,6; nur 250 verschiedene Werte, **777 Karten
  teilen ihren Wert** (99 bei 0,1; 33 bei 0,0). 167 Karten „grenzwertig“, davon 129 am C/D-Schnitt.
- Stabilität: ±20 % je Gewicht → höchstens 14 Stufenwechsel; alle Gewichte zufällig ±20 % → Ø 12,7 (max 27).
  Leave-one-out je Ebene: `deck_universe` 124 Wechsel, `global_inclusion` 72, `corpus_log_lift` 55,
  `corpus_bracket_slope` 43, `corpus_tuned` 38, `tournament` 16. Schnitte um ±1 / ±2 verschoben: 54 / 49 bzw. 112 / 81 Wechsel.
- **Der Index ist ein Beliebtheitsmaß:** Spearman Index ↔ Quelldeck-Anteil 0,954; Beitrag im Mittel der S-Karten:
  `deck_universe` 33,9 Punkte, `corpus_tuned` 12,3, `global_inclusion` 7,1, Rest ≤ 4,8. Ebenen gegen Index:
  Großpod −0,01, Tempo 0,22, Ausspielquote 0,27, Standfestigkeit 0,35, Sieg-Abstand 0,55.
- Datenlage: 640 von 922 Karten (69 %) haben < 30 Quelldecks als Zähler (91 % in der tuned-Kohorte); die Konfidenz
  ist für **alle** 922 „hoch“, U = 0.
- Gegenproben: Bracket 5 ausgehalten Rangkorrelation 0,636, EDHTop16 0,585.
- Top 15: Sol Ring, Command Tower, Llanowar Elves, Shrieking Drake, Swords to Plowshares, … Bottom 15: Index 0,0 und
  0 von 10.128 Decks. Plausibel als „wird in Chulane-Decks gespielt“, **als „stark“ nicht belegbar**.
- „Gleiche Funktion“: 137 Stufenwechsel, alle Aufstiege, S 39 → 66; sieben S-Karten stehen in < 5 % der Decks;
  105 Karten ohne Rolle stehen auf gemischter Skala daneben; die Schnitte werden nicht neu kalibriert.
- Kaltstart `prepare` 13,3 s, Antwort 9,7 MB.

## 3. Befunde

**P1**
1. **Bedeutung:** Der Index ist Nutzung, liest sich aber durch Name und Buchstaben S–D als Stärke; zusätzlich
   Verschachtelung: ≈ 8 von 10 Gewicht stammen aus demselben Korpus (`deck_universe` ⊃ `corpus_tuned` ⊃ Bracket 5,
   Log-Lift nutzt den `deck_universe`-Zähler), zu 93 % EDHREC. Der Redundanztest (r > 0,90) sieht Teilmengen nicht.
2. **„Gleiche Funktion“** bläht die Stufen auf und warnt nicht (s. o.).
3. UX: Stufe und Kartenname nicht sticky (Zeilen ohne Namen beim Seitwärtsscrollen), Spalten bei 1920 px
   abgeschnitten, Stufen fehlen beim Laden ohne Hinweis mit Layout-Sprung, 7 Panels vor der Tabelle (Kernaussage
   „Stufe = Nutzung, keine Spielstärke“ geht unter).

**P2** — „Zu wenig Daten“ praktisch abgeschaltet (gezählte Nullen zählen als Beleg; Konfidenz nutzt Nenner statt
Zähler); C/D-Schnittband liegt im Rauschen, Schnitte nicht an Skala/Presets gekoppelt (`share_scale=rank`: S 275,
877 Wechsel, ohne Warnung); Lift vergleicht mit allen Decks statt mit der Farbidentität (#1261 Punkt 5) und negative
Synergie wird ausgelassen, Unterneutrales als 0 gemittelt; `tournament` addiert EDHTop16 und Korpus-Bracket 5 zu einem
n/N (Spannung zu „Kohorten nie mischen“, A5/#1412; unter E3.a umgesetzt); Bracket-Labels nur bei 2.638 von 10.150
Decks (26 %); „kein Universum“ im Dropdown obwohl mit 10.128 Decks gerechnet wird, zwei S–D-Systeme auf einer Seite
(Verbreitung 50/35/20/10 % vs. Index 54/35/20/5); wirkungslose/falsch benannte Einstellungen (empfohlene 3/2,
`bracket` inert, „Mittel der Ränge“, `percentile` = Log-Score); Combos: 13 Karten, Gewicht 0,5, ändert 1 Stufe.
UX: Rohcodes (`COMPLETE`, `NORMALIZED_SOURCE`, `oracle_id`), englische Reste, Dezimalpunkte/uneinheitliche Tausender,
Rollen-Badges mehrfach (Sol Ring 4×, Zeile 151 px hoch, `#1/24` unerklärt), kein Dialog-Fokus/`aria-modal`, `th` ohne
`scope`, Sortierung nur per Select ohne `aria-sort`, Konfidenz nur „●●●“.
**P3** — Doku-Drift (47/17/9/4; B10 `min_coverage` 0,3 vs. Code 0,25), „Quellen 15/15“ zählt leere Quellen, TopDeck-
Übersicht 241 Zeilen „zu wenig Daten“, 11–12-px-Hinweiszeilen, Suche sortiert nach Stärke statt Namensrelevanz.

**Regelkonformität:** Zahlen mit n/N (außer Combos, Playgroup, Synergie), unbekannt ≠ 0 (gezählte 0 ist echt), Simulation
Gewicht 0 (`card_outcomes` wird nicht importiert), keine Preise, Markierungen ohne Einfluss (Test vorhanden),
Kohorten mischen: teilweise (TN, DU über zwei Plattformen).

## 4. Entscheidungen für den Owner (mit Empfehlung)

Ausgangsfrage: **Was bedeutet die Tierliste?** Die Messung zeigt ein Nutzungsmaß; ein belastbares „Stärke“-Maß ist mit
den vorhandenen Daten nicht herstellbar (Simulation Gewicht 0, Chulane 7 Turnierlisten, 3 mit bekanntem Top-Cut).
- **D1 Bedeutung/Benennung.** (a) **Empfehlung:** als **Nutzungs-Index** benennen und beschriften (Titel, Stufen-Legende,
  „wird in X % der Chulane-Decks gespielt“), „Perzentil“-Begriffe korrigieren, die zwei S–D-Systeme trennen/umbenennen.
  (b) Versuch eines Stärke-Maßes: nicht belegbar, nicht empfohlen. **Nicht** gemeint ist eine A–F-/Perzentil-Wertung
  (vom Owner abgelehnt).
- **D2 Verschachtelte Doppelzählung.** (a) **Empfehlung:** wenige unabhängige Komponenten (Gesamtkorpus-Anteil,
  Bracket-Neigung, externe Quelle, Turnier getrennt) und **wirksames neben nominalem Gewicht** zeigen;
  (b) Status quo mit Hinweis; (c) Gewichte neu setzen (Owner-/Development-Lead-Zuständigkeit, AGENTS §8).
- **D3 „Gleiche Funktion“.** (a) **Empfehlung:** „Rang k von n in der Funktion“ ohne Stufenbuchstaben (Recherche T1 fand keine
  Quelle für faire Funktionsvergleiche); (b) eigene Schnitte je Funktion (Kalibrierung offen, Quellenlage fehlt); (c) wie heute
  mit Warnung.
- **D4 Unsicherheit.** (a) **Empfehlung:** Konfidenz aus dem **Zähler** statt dem Nenner (klarer Fix) und als Text „n von N, sehr
  dünn“; (b) die alte Frage **gezählte 0 als Beleg (B12/E4.b) oder als „dünn“ (B5)** als Owner-Frage stellen, nicht in den Fix
  bündeln.
- **D5 `tournament` mischt Kohorten.** Empfehlung: EDHTop16 und Korpus-Bracket 5 getrennt ausweisen (zwei Zellen), Gewicht
  beibehalten; bestätigen, ob E3.a das so wollte.
- **D6 Schnitte/C–D-Band.** (a) **Empfehlung:** feste Schnitte behalten, **Stabilität anzeigen** („Stufe bleibt in x % der
  Gewichtsvarianten“) und das C/D-Band als „unscharf“ kennzeichnen; (b) gröbere untere Stufen. Keine Perzentile, keine A–F-Noten.
- **D7 Lift gegen Farbidentität** (#1261 Punkt 5): hängt an #1210 (Owner-gesperrt). Parken, Abhängigkeit nennen.

## 5. Vorschlag ohne Zahlenänderung (Charge „No-regret“)
Kann ohne Owner-Entscheid gebaut werden, ändert **keine** Indexzahl: Spalten Stufe/Karte sticky + Spaltenpreset „Kompakt“;
Methodik-Panels hinter einen Tab, Tabelle früh sichtbar; Ladezustand ohne Layout-Sprung; Rohcodes, englische Reste,
Dezimalpunkte/Tausender; Rollen-Badges zusammenfassen und `#r/N` erklären; Tabellensemantik (`scope`, `caption`, `aria-sort`,
Sortier-Buttons), Dialog-Fokus, Skip-Link; „Warum hier“ (2–3 Klartext-Gründe) oben im Karten-Fenster und als Zeilen-Hinweis;
Stufen-Chips als Filter mit Zähler; Doku-Drift beheben (Schnitte, `min_coverage`); Antwortgröße (9,7 MB) und Kaltstart
(13 s) prüfen. UI-Bausteine mit Quellenlage (T3): Stufe mit Textlabel + farbenblindensichere Farbe (nie Farbe allein),
n/N als Bullet-Zelle, Unsicherheit als Text/Intervall, Scroll-Windowing in Plain-JS (CSP-freundlich).

## 6. Später/optional (komplex, überwiegend Sekundärquellen)
Beta-Binomial-Schrumpfung je Kohorte mit sichtbarem Prior (statt ad-hoc EB < 500), Pareto-Schichten ohne Gewichte als
Gegenprobe, Bootstrap-Rangintervalle und Stufenstabilität, Rank-Biased-Overlap für Backtesting über Zeitfenster.

## 7. Zuständigkeit
Schnitte und Standardgewichte liegen laut Analyse beim Development Lead (AGENTS §8); `strength*.py` und `tierliste.*` waren
Argons Bereich und werden aktuell auch von Muse berührt. Vor einem Bau: klären, wer schreibt, und Argon an D2/D6 beteiligen.
Rohberichte: Scratchpad `research/tier_*.md` (nur im Container; diese Datei ist die Zusammenfassung).
