# Tierliste: zweiter Karten-Index „Eignung für Chulane“ — Bestandsaufnahme, Recherche, Plan — 2026-11-18

**Auftrag (Owner, 2026-11-18):** Zusätzlich zum Nutzungs-Index weitere Karten-Indizes bzw. Tierlisten, mit dem Ziel, alle
Chulane-legalen Karten der Sammlung bestmöglich für das Chulane-Deck zu ranken. Erst planen, recherchieren, planen, dann bauen.
**Dies ist Analyse und Plan, nichts davon ist beschlossen oder gebaut.** Vorläufer: `TIERLISTE_ANALYSE_UND_PLAN_20261117.md`.

**Methode/Ehrlichkeit:** Bestandsaufnahme (read-only, Studio-Code selbst, `main` `20ae3f4f9`, Pool 927, gerankt 922) und drei
Web-Recherche-Lanes (überwiegend Sekundärquellen; Scryfall-Seiten waren nicht abrufbar). Zahlen aus Agent-Proben (Regex im
Scratchpad) sind als solche markiert und **keine Studio-Messung**. Gruppen: Pool = 922 gerankte Karten, D = 617, **Null = 186**
(0 von 10.128 Quelldecks, alle in D).

## 1. Die zentrale Erkenntnis
Der Nutzungs-Index trennt Karten, die niemand spielt, nicht (186 Karten stehen auf 0 von 10.128 Decks; sie sind heute **nur durch
die globale Beliebtheit** geordnet). **Alles in Quelldecks Gezählte (Lift, Gefälle, Kookkurrenz, Pakete, Kombos, EDHREC-Seiten,
Turnier) ist für diese 186 Karten undefiniert** (unbekannt, nicht 0). Was Null-Karten überhaupt ordnen kann, ist nur: globale
Beliebtheit, die **Rubrik** (subjektive Sprachmodell-Bewertung, Gewicht 0 nach E1.a), Manawert/Castability (als Tor, kaum als Rang),
Rollenzahl und **kartentext-abgeleitete Muster**. Ein „perfektes“ Ranking ist damit nicht behauptbar; ein ehrlicher Gewinn ist
Transparenz je Achse und gezieltes Trennen im Mittelfeld, wo Daten da sind.
Praktischer Nutzen liegt eher im Mittelfeld: Im Referenzdeck stehen 44 von 72 S/A-Pool-Karten; **28 von 843 nicht gespielten
Pool-Karten stehen in S/A** (Avacyn's Pilgrim, Path to Exile, Counterspell, Cultivate …) — das ist die Kandidatenliste.

## 2. Was vorhanden ist (Abdeckung n/N: Pool 922 · D 617 · Null 186)
| Signal | Pool | D | Null | Einordnung |
|---|---|---|---|---|
| Nutzung (Index) / Global-Aufnahme / `edhrec_rank` | 922 | 617 | 186 | Beliebtheit; Null-Karten nur global geordnet |
| Rubrik H (Gesamteignung) / F („passt zu Chulane“) | 922 | 617 | 186 | subjektiv (3 Sprachmodell-Rater, ICC H 0,94 / F 0,88), nur Regeltext, **F steht nur in `summary.csv`, nicht im Store**; Auflösung in Null: 12 bzw. 11 Werte |
| Gemessene Ebenen: Tempo / Ausspielquote / Standfestigkeit / Sieg-Abstand | 345 / 418 / 317 / 434 | 120 / 138 / 111 / 153 | 6 / 7 / 5 / 8 | reale Partien, **alle Commander gemischt, nicht Chulane-bedingt**; „Passt zum Commander“ nur 68 |
| Rollen ≥ 1 (Tagger/Regeln) | 817 | 529 | 152 | Stichprobe 20: 17 plausibel, 2 falsch (z. B. `bounce` trennt Fremd- von Eigenbounce nicht), 1 unklar; feine Tagger-Untertags nicht im Store |
| Mechanik-Tags (nur 4: Kreaturenzauber, Land, ETB-Text, erzeugt Mana) | 602 | 396 | 130 | 20/20 regelkonform, aber `enters_trigger_text` feuert auch auf Landfall/„another creature enters“ (31 von 189 kein eigener ETB, Agent-Regex) |
| Log-Lift / Bracket-Gefälle / Pakete / Kombos | 736 / 286 / 68 / 13 | 431 / 21 / 0 / 0 | 0 | undefiniert für Null; Lift gegen **alle** Decks statt Farbidentität |
| Manawert / Farbe / Besitz frei | 922 | 617 | 186 | Fakten/Tore; Besitz trennt nichts |
| Castability (Karsten, Referenzdeck) | 715/857 | 497/599 | 144/185 | Tor, kaum Rang (AUC 0,54) |
Chulanes Kartentext steht im Store (Vigilance; Cast-Trigger Kreaturenzauber: Karte ziehen, dann Land aus der Hand; `{3},{T}` Bounce einer eigenen Kreatur —
die Web-Quellen bestätigen `{3},{T}`; die Vorgabe `{3}{G}{W}{U}` war falsch).

**Plausibilitätstest am Referenzdeck** (79 gerankte Nicht-Basis-Karten; n/79): S 26 · A 18 · B 10 · C 19 · D 6. AUC (Deckkarte vs. Rest, 79/843):
Index 0,92 · Global 0,88 · `edhrec_rank` 0,87 · Playgroup `times_brought` 0,87 · **Rubrik H 0,85, F 0,75** · Rollenzahl 0,62 · ETB-Tag 0,59.
Vorsicht: Das Deck ist teils nach Beliebtheit gebaut (zirkulär); in D stehen nur 6 Referenzkarten.

## 3. Recherche (Kurz)
- **Chulane (Community, überwiegend Meinung/EDHREC):** Jeder Kreaturenzauber = Karte + Land; tragende Muster: Kreaturen mit ETB-Effekt, Bounce/Blink eigener Kreaturen,
  1–2-Mana-Mana-Kreaturen, Land-aus-der-Hand/Landfall, Kombo-Teile (bracket-abhängig). **Anti-Synergie:** Nicht-Kreatur-Kartenzug/Mana löst nichts aus; kreaturenarm;
  teure Kreaturen als Hauptlast; kleine Kreaturen gegen −X/−X. Nicht belegt: Kostensenkung für Kreaturenzauber als Kern (0 Pool-Karten).
- **Fit-Verfahren (belegt/erklärbar):** Lift gegen Farbidentitäts-Baseline (EDHREC), Rollen-Lücke als Soll−Ist (nur der Land-Anker 38–39 ist belegt), Textmuster mit
  gemessener Fehlerrate, Besitz-Filter + Substitute; Evaluation per Hold-out (Rang der entfernten Karte, Hit-Rate@k mit n/N). Keine Quelle liefert belegte Trefferquoten für Commander-Deckbau.
- **Ergebnisdaten (Sieg-Abstand etc.):** „gespielt minus nicht gespielt“ ist durch Überlebens-/Post-Treatment-Verzerrung nicht als Kartenstärke lesbar; Sitz-Basis ist nicht flach
  (Sitz 1 ≈ 27–29 %, letzter ≈ 21–22 %); Partien nicht unabhängig. **Empfehlung: nur getrennt anzeigen, nie gewichten** (Mindest-n-Vorschlag: anzeigen ab ≈ 300, gewichten frühestens ≈ 1.000;
  eigene Ableitung, keine publizierte Schwelle); Gesamtnote nur mit Sensitivitätsanalyse (OECD-Handbuch).

## 4. Zwei Lesarten und Empfehlung
(a) **Mehrere Tierlisten/Achsen nebeneinander**, jede mit eigener Definition und Beschriftung (Nutzung · Chulane-Textfit · Sprachmodell-Einschätzung · Deck-Bedarf), optional eine
sichtbare Matrix „Karte × Achse“. (b) **Ein kombinierter zweiter Index.** **Empfehlung (a):** Eine Kombination bräuchte gewählte Gewichte (der abgelehnte „Eigene-Einschätzung“-Gedanke),
und die gemessenen Ebenen dürfen nach B11/E1.a kein Gewicht tragen. Achsen nebeneinander sind erklärbar und validierbar.

## 5. Vorgeschlagene Achsen
1. **Nutzung** (vorhanden; absolute Stufen S–D plus relative S–F aus #1481).
2. **Chulane-Textfit** (neu, regelbasiert aus dem Oracle-Text, mit Regelversion und Herkunft, Gewicht 0 im Nutzungs-Index): eigener ETB (getrennt von Landfall/fremden Triggern; Agent-Probe 145/89/21),
   Bounce/Blink eigener Kreatur (4/1/0 bzw. 1/1/0), Cast-Trigger Kreaturenzauber (3/0/0), Land aus der Hand/zusätzlicher Landdrop (8/0/0), Landfall (18/8/1), ETB-Kartenzug (10/5/1), billige Mana-Kreatur.
   **Erwartung:** selten und fast nie in Null (1 von 186) — trennt D, nicht Null. Vor Anzeige: 20er-Stichprobe je Regel und Konfusionsmatrix gegen den Tagger (Präzision/Trefferquote mit n/N).
3. **Sprachmodell-Einschätzung** (Rubrik H/F, nur getrennt und deutlich als „subjektiv, Regeltext-basiert, nicht gemessen“ beschriftet; F aus `summary.csv` in den Store übernehmen). Owner-Entscheid E1.a (Gewicht 0) bleibt.
4. **Deck-Bedarf** (Rollenlücke des gewählten Decks gegen p25–p75 des Korpus; zeigt, welche Rolle fehlt und welche freien Pool-Karten sie füllen).
5. **Tore, kein Rang:** Farbe, Besitz, Castability, Legalität. **Gemessene Ergebnisebenen:** nur getrennt, mit n und Intervall.
Jede Achse mit relativen Stufen (S–F nach Prozentrang; keine Aussage über Spielstärke), Gleichstände geteilt, Unbekannt getrennt.

## 6. Validierung vor dem Bau
„Perfekt“ ist nicht behauptbar. Annahmekriterium vorab: (1) Hold-out Bracket 5 (Nutzungs-Index erreicht 0,636) und Top-k/RBO-Übereinstimmung; (2) die Achse muss auf den Karten mit wenig/keiner Nutzung
Information addieren (Trennschärfe), ohne das Hold-out-Ergebnis zu verschlechtern; (3) Textfit-Regeln: Handstichprobe + Konfusionsmatrix; (4) Referenzdeck-AUC nur als Plausibilität (zirkulär).

## 7. Umsetzungs-Etappen
- **E0:** laufende Tierliste-UX (#1494) mergen; UI-Anbindung der #1481-Felder (relative Stufen-Ansicht, Stabilität „unscharf“, Gewichtsfamilien, getrennte Turnier-Teile, `confidence_basis`).
- **E1:** Textfit-Achse (Backend, versionierte Regeln, Goldtests, Konfusionsmatrix), Rubrik F in den Store, Validierungs-Harness (`ranking-check` erweitern).
- **E2:** Achsen-Ansicht in der Tierliste (Tabs/Matrix), Deck-Bedarf-Achse.
- **E3 (nur bei Owner-Okay):** optionale, sichtbare Kombination.

## 8. Owner-Entscheidungen (mit Empfehlung)
K1 Lesart: **Achsen nebeneinander** (Empfehlung) statt ein kombinierter Index. K2 Rubrik als eigene, klar beschriftete Achse anzeigen (Empfehlung ja, Gewicht bleibt 0 nach E1.a).
K3 Textfit-Achse bauen (Empfehlung ja, mit Stichprobenvalidierung). K4 Kombination: Empfehlung **nein**, später prüfen. K5 Ergebnisebenen nur getrennt, kein Gewicht (Empfehlung ja; Mindest-n-Vorschlag 300/1.000 bestätigen).
K6 Rollen-Soll-Werte: nur Land-Anker (38–39) belegt, übrige Quoten als „Quelle unbelegt“ konfigurierbar. K7 Lift gegen Farbidentität: hängt an #1210 (geparkt).

## 9. Umsetzung Kartenverständnis-Gesamtrating (Backend, Owner-Entscheid 2026-11-18, Refs #1369)

Der Owner hat entschieden, neben dem Nutzungs-Index ein zweites Gesamtrating zu führen. Es ersetzt den Index nicht: Index, Stufen
(S–D, U/N), Gewichte, Schnitte, Snapshots und alle bisherigen API-Felder bleiben unverändert; `/api/strength` erhält nur additive
Felder (`cards[].overall`, `overall_meta`), angehängt nach dem Snapshot in `web.strength_answer`.
- **Datensatz:** `data/card_understanding/card_understanding_v2_1.jsonl`, eine Zeile je Karte (`oracle_id`, `card`, `scores` E F T R K D H
  in 0–100, `confidence`, `reason`, `notes`, `rule_claims`, `version`, `rater_tier` small|large, `rubric`; optional `raters`, `score_sd`,
  `rounded`, `uncertainty`). Lader und Prüfung: `studio/card_understanding.py` (kaputte Zeile, Bereich, fehlendes Feld, unbekanntes
  Kriterium, doppelte `oracle_id` lassen das Laden scheitern; fehlende Karte = unbekannt, nie 0). Erzeugt mit
  `scripts/import_card_understanding.py` aus den Rater-Rohdaten (je Karte eine Bewertung, Vorrang der Version v2.1; mehrere Bewerter:
  Mittel auf Vielfache von 5, `score_sd` je Kriterium, niedrigste Konfidenz). Stand: alle 922 Karten bewertet (922 von 922); Karten ohne
  Zeile blieben „unbekannt“, nicht 0. Der Datensatz gilt nur für Chulane. Herkunft kommt aus den Daten: der Lader lehnt jede Zeile ab,
  deren `version` oder `rubric` nicht zum Datensatz passt (Kohorten nie mischen); jeder Lesefehler (fehlende Datei, kein UTF-8, zu große Zahl,
  kaputte Zeile) macht nur `overall_meta.available` false, `/api/strength` antwortet weiter mit dem unveränderten Index.
- **Rechnung:** `studio/overall_rating.py`, Regelversion `OVERALL_RULES_VERSION`. Gewichtetes Mittel 0–100, Gewichte
  `OVERALL_WEIGHTS_V1` (Setzung, keine Messung): Nutzung 0,30 · H 0,30 · F 0,15 · E 0,10 · T 0,05 · R 0,05 · D 0,025 · K 0,025.
  Fehlende Achsen (z. B. Nutzung bei Stufe U/N) werden renormalisiert; `coverage` ist die Summe der vorhandenen Gewichte; unter 0,6 oder
  ohne Bewertung ist `score` None („unbekannt“). Die Beiträge je Achse summieren sich exakt zur Punktzahl (Zehntel, größter Rest).
- **Rang und Stabilität:** Rang k von `n_rated` (Gleichstände teilen den besten Rang). `stability`: 80 Gewichtsvarianten (jedes Gewicht
  zufällig ×0,7–1,3, Seed 20261118, je Karte renormalisiert); „unscharf“ bei einer Rangspanne von mindestens 10 % der bewerteten Karten.
  `confidence`: Bewerter-Konfidenz, „unsicher“ bei `low` oder H-Streuung ≥ 20.
- **Gesperrt (B11, E1.a, K5):** keine Simulationswerte, keine gemessenen Ergebnisschichten (Tempo, Ausspielquote, Standfestigkeit,
  Sieg-Abstand, Großpod), keine Preise, Markierungen ohne Einfluss, Kohorten nie vermischt (die Nutzungs-Achse ist der Index der Anfrage;
  gewichtet dieser Simulation, Rubrik, Playgroup-Beobachtung oder eine Ergebnisschicht, entfällt die Nutzungs-Achse und `overall_meta`
  sagt es). `overall_meta.caveat`: Setzung der Gewichte, Kartenverständnis durch Modell-Rater (große Stufe), Nutzung ist eine Achse.
- **Regelversion `overall-v2` (nach einem unabhängigen Methodik-Gutachten vom 2026-11-18, nicht eingecheckt):** Gewichte unverändert (Setzung).
  1. *Nutzungs-Achse log-skaliert:* `100·ln(1+Index)/ln(101)` (Index 0–100; `overall_meta.usage_scale` = "log", der Rohindex bleibt als
     `raw_value` in der Achsenzeile). Mit dem Rohindex lag der Index bei etwa zwei Dritteln des Pools bei 5 oder darunter und bewegte
     das Gesamtrating um unter 2 Punkte: unterhalb Stufe C sortierte faktisch das Modellurteil. Beispiele (Index → Achse): 1 → 15, 5 → 39, 18 → 64.
  2. *Bracket-Prüfung:* `overall` nur bei der Einstellung „upgraded“ (Bracket 3, der Kontext der Bewerter); sonst `overall_meta.available` false
     mit Grund „Kartenverständnis gilt für Bracket 3“.
  3. *Gruppenrang:* zusätzlich zu `rank` ein `rank_in_group` (`group` "land" | "spell", `n_group`, Gleichstände teilen den besten Rang);
     `overall_meta.groups` nennt die Gruppengrößen. Länder werden gegen eigene Anker bewertet und sind strukturell benachteiligt
     (T ist bei fast allen Ländern 0).
  4. *Ohne Nutzungs-Achse (Stufe U/N):* weiter renormalisiert, aber `overall.flags` enthält "no_usage_axis"; der Rang wird ausgewiesen, ist
     aber nicht mit Karten mit Nutzungs-Achse vergleichbar (renormalisierte Karten stehen höher). Nach dem Lauf betrifft das nur wenige Karten (5).
  5. *Rauschen:* `overall_meta.min_meaningful_diff` = 5: Unterschiede unter etwa 5 Punkten sind nicht belastbar (Einzelrating-Rauschen).
  6. *Ehrlichkeit der Mischung:* H ist zu etwa 90 % aus den Teilkriterien erklärbar, D und K (je 0,025) wirken praktisch nicht. Die Mischung ist
     eine Betonung von Synergie und Effizienz, keine unabhängige Evidenz (`overall_meta.weights_caveat`).
