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
