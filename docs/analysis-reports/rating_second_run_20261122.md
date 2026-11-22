# Kartenverständnis H: zweiter, blinder Rater-Lauf gegen den Vollauf F1 (Chulane, Raster v2.1, 2026-11-22)

- **Stand:** Branch `docs/rating-second-run-1404`, gebaut auf `main` @ `fe20933e`. Refs #1404. F1-Werte und Prüfer-Marken sind seit dem Stichproben-Commit `138a50c264f2` unverändert (`git diff` über `data/card_understanding` und `data/research/chulane_rubric_v2_20261118`: leer).
- **Was verglichen ist:** H und E, F, T, R, K, D derselben Karte aus zwei Läufen: **F1** (Vollauf, 922 Karten, `fullrun_ratings.jsonl` = `data/card_understanding/card_understanding_v2_1.jsonl`, 922 von 922 gleich) und dem **zweiten Rater-Lauf** (laut Auftrag des Leads eine andere Modellfamilie als der Vollauf; **Familie ungeprüft (A3)**, kein Laufprotokoll, §1) auf 300 geschichteten Karten, drei Subagenten zu je 100 Karten, blind (Eingabe nur der Kartenblock des Original-Raters, Guide v2.1). Keine Paarvergleiche.
- **Wirkung:** keine. Produktcode, H, Stufen, Tierliste und Anzeige bleiben unverändert. Kartenverständnis bleibt ein Modellurteil aus dem Regeltext; Übereinstimmung zweier Modelle ist keine Richtigkeit, Abweichung kein Beweis gegen F1.
- **Plan:** vorab festgelegter Vergleichsplan (Original im Scratchpad, SHA-256 `bd538382…`; im Repo eine Kopie ohne Modellnamen, §8); Schwellen, Schichten und Regeln hier unverändert übernommen. Alles mit „explorativ“ markierte steht nicht im Plan.

## 0. Ergebnis zuerst

- **Gesamturteil nach Plan §9 (G1-Schwellen): „teilweise bestätigt“.** M1, M2, M3 und M8 gelb, M4 bis M7 grün, kein Rot; V1 bis V4, Regelclaims und Blindheit grün; kein Abbruchkriterium greift (A1, A4 bis A8 nein; A2: kein Ausgabe-Indiz, Zugriff UNKNOWN; A3 greift).
- **Umschlag durch A3:** „Familie unbekannt“ schließt „gleiche Familie wie F1“ ein. Mit den F2-Schwellen dieses Zweigs (Plan 2a) wären M1 (8,38 > 8,0), M2 (11,45 > 11), M3 (24,5 % ≥ 20 %), M7 (67,9 % < 70 %) und M8 (85,3 % < 88 %) rot (M4, M6 gelb, M5 grün): Urteil **„nicht bestätigt“**. Welches Urteil gilt, hängt an der unbelegten Familie.
- **Niveau:** mittlere |ΔH| 8,38 [7,45; 9,30] (n = 265 nicht markierte Karten), RMS 11,45 [10,33; 12,53], Anteil |ΔH| ≥ 15: 65 von 265 = 24,5 % [19,2; 29,4]. Einzelwert-Streuung RMS/√2 = **8,1** (Drift F2 5,05 n = 49; andere Familie G1 7,32 n = 70). Lesart Plan §6: 8,0 bis 11,0 = „mehr als jede bekannte Streuung → Richtung und Schicht ansehen, kein Urteil über Verwendung“; das Intervall reicht bis in den G1-Bereich (7,45). Einzelwert-Intervall [7,30; 8,86].
- **Rang:** Spearman ρ(H_neu, H_alt) = 0,881 [0,848; 0,907] gepoolt (G1 0,92, F2 0,939), innerhalb der Schichten nur Spitze 0,704, Rest 0,791, Länder 0,839; M4 ist knapp (56 von 265 Weglass-Proben unter 0,88); Steigung 0,945 [0,896; 0,993]; gleiches Guide-Band 180 von 265 = 67,9 %; gleiche Seite von H ≥ 50 226 von 265 = 85,3 %.
- **Verzerrung:** Der zweite Lauf liegt bei **Spells** im Mittel rund 5 Punkte tiefer, gleich in Spitze und Rest; Spells zusammen −5,61 [−7,16; −4,14] (n = 215, explorativ, wäre als M6-Art gelb); bei **Ländern** nach oben +2,3 [0,6; 4,1]. M6 (Rest + Länder, −3,30) ist nur grün, weil sich beide teilweise aufheben. Die Spitze ist nicht gesondert überbewertet (Lesehilfe Plan §6).
- **35 markierte Karten:** 17 von 35 in der Prüfer-Spanne (F1 2 von 35), Urteil „stützt“, aber nach Verzweigung 2a nur **Selbstkonsistenz** (Prüfer vermutlich dasselbe Modell wie der zweite Lauf; unbestätigt), keine unabhängige Bestätigung.
- **Regelclaims:** 0 von 100 offensichtlich falsch (2 unscharf), Zitate 588 von 588 wörtlich; die Claim-Prüfung war **nicht blind** zur Herkunft (Abweichung 6).

## 1. Plan-Konformität, Gültigkeit, Blindheit

| Prüfung | Ergebnis | Stufe |
|---|---|---|
| V1 gültige Karten | 300 von 300 (je Schicht 100 %); `oracle_id` und Name je Position = Eingabe = Manifest | grün |
| V2 alle 7 Werte | 300 von 300; strenge Schemaprüfung `rubric-v2-card-rating-1` (Schlüssel, Längen, Enums, ≤ 6 Claims): 0 Befunde | grün |
| V3 Vielfache von 5 | 300 von 300 (keine Rundung nötig) | grün |
| V4 Zitate wörtlich (Kartenblock oder Chulane-Text, Normalisierung „ws“) | 588 von 588 = 100 % (F1 1706 von 1708) | grün |
| `pattern_check` deckt alle gezeigten Treffer ab | 300 von 300 | – |
| Dopplungen | 0 (300 verschiedene `oracle_id`) | – |
| L Blindheit, Stichwortliste `full_qa.py` über notes, reason, uncertainty, claim | 0 Treffer von 300 | grün |
| L Verweise auf frühere Zahlen (earlier rating, previous, v1, F1, audit, tier list) | 0 Treffer; Erwähnungen der Guide-Anker (z. B. „Evolving Wilds anchor“) sind erlaubt | A2: kein Ausgabe-Indiz; Zugriff UNKNOWN (A3) |
| A4 Skalenstauchung | SD(H_neu) 22,8 gegen SD(H_alt) 21,4 auf denselben 265 Karten; größter Gleichstand H = 5: 30 von 265 = 11,3 % | nein |
| A5 Formbruch / A7 Abbruch | 0 Karten / keine Datei unter 100 Zeilen | nein |
| A6 Dateieffekt (mittlere \|ΔH\| je Datei, Primärmenge) | 6,59 (n = 88) · 8,41 (n = 88) · 10,11 (n = 89): Spanne 3,52 ≤ 4 | nein, knapp |

**Abweichungen vom Plan (berichtet, nicht korrigiert):**
1. **Laufprotokoll fehlt** (`rr_run_log.md` existiert nicht). Modellfamilie nur laut Auftrag des Leads, Stufe/Aufwand und Dateizugriff nirgends protokolliert → **A3 greift:** Zahlen werden berichtet, aber keine Aussage „unabhängige zweite Modellfamilie“. Plan 2a wendet bei „unbekannt“ die G1-Schwellen an; „unbekannt“ schließt aber „gleiche Familie“ ein, und mit deren F2-Schwellen wäre das Urteil „nicht bestätigt“ (§0). Der Dateizugriff der Subagenten ist UNKNOWN: F1, `audit_A_flagged.jsonl` und das Manifest (Schichten, Marken) lagen eine Ebene über dem Rater-Ordner und wären erreichbar gewesen; der Text-Scan findet keine Spur davon, beweist aber keine Blindheit. Die Prüfer-Frage 2a ist unbestätigt („unbekannt“ = gleicher Zweig wie „ja“).
2. **Einfrieren:** Die SHA-256 der Ausgaben wurden nicht vor dem Öffnen protokolliert, und das Auswerteskript entstand erst nach dem Lauf (Plan §4). Hashes unten sind „zum Analysezeitpunkt“. Gegenprobe: Das Skript reproduziert die Referenztabelle des Plans exakt (F2: 5,10 / 7,14 / 0,939 / 3 von 49 / Band 45 von 49; G1: 7,86 / 10,35 / 0,92 / 13 von 70 / Band 48 von 70 / Seite 64 von 70 / ICC E 0,87 … D 0,91; F1 in Prüfer-Spanne 2 von 35).
3. **Rater 3** hat zwei geschriebene Zeilen nachträglich ersetzt (Anweisung: nur anhängen). Zeile 5 (Tippfehler in `oracle_id`) ist durch die Ausnahme „ungültige Zeile neu schreiben“ gedeckt, Zeile 20 (Pflichtsatz „H weit unter dem Mittel“ in `reason` von Dispel) nicht. „Scores unverändert“ ist ohne frühere Hashes nicht prüfbar; das ist für M4 erheblich: Dispel (Datei 3, seq 20, Rest) steht jetzt auf H 20 (F1 10); wäre H ≥ 25 gewesen, fiele ρ auf 0,8796 und M4 auf gelb. Kein Ausgabe-Indiz für einen Blindheitsverstoß.
4. **Rater 1, seq 15 (Telepathy):** H 10 liegt 28 unter dem Mittel von E bis D (38,3); `reason` nennt den Grund nur indirekt (Anweisungsregel > 25). Formfehler, kein Gültigkeitskriterium. seq 10 (Palladium Myr): Begründung gelesen, ΔH −5.
5. **Datenfehler im Kartenblock:** Cabaretti Courtyard (Datei 2, seq 86) zeigt „fetches a land: no“, der Oracle-Text holt ein Standardland. Beide Läufe folgten dem Text (H 35 → 40). Betrifft die Faktenquelle, nicht diesen Vergleich.
6. **Regelclaim-Prüfung nicht blind zum Lauf:** Der Prüfer (diese Auswertung) wusste, dass alle Claims aus dem zweiten Lauf stammen (Plan: Herkunft verdeckt). Das Ziehverfahren ist im Skript festgelegt (§5).
7. **A6-Menge:** Plan §10 legt nicht fest, über welche Karten die Datei-Mittel laufen; das Skript nutzt die Primärmenge (Wahl dieser Auswertung, nicht des Plans). Über alle 100 Karten je Datei 7,75 / 9,90 / 11,75 = Spanne genau 4,00, also nicht > 4. Keine Variante löst A6 aus, die zweite nur auf der Grenze; der Dateieffekt ist deutlich (§4).

## 2. Hauptkennzahlen M1 bis M8 (Primärmenge, ΔH = H_neu − H_alt)

Intervalle: Bootstrap über Karten innerhalb der Schichten, 5000 Ziehungen, Seed 20261122, 95 % Perzentil.

| Nr | Kennzahl | Wert (n = 265) | 95 % | grün / rot laut Plan | Referenz F2 · G1 | Stufe |
|---|---|---|---|---|---|---|
| M1 | mittlere \|ΔH\| | 8,38 | [7,45; 9,30] | ≤ 8,0 / > 11,0 | 5,10 · 7,86 | gelb |
| M2 | RMS(ΔH) | 11,45 | [10,33; 12,53] | ≤ 10,5 / > 14 | 7,14 · 10,35 | gelb |
| M3 | Anteil \|ΔH\| ≥ 15 | 65 von 265 = 24,5 % | [19,2; 29,4] % | ≤ 20 % / ≥ 30 % | 6,1 % · 18,6 % | gelb |
| M4 | Spearman ρ (gepoolt) | 0,881 | [0,848; 0,907] | ≥ 0,88 / < 0,80 | 0,939 · 0,92 | grün (knapp) |
| M5 | OLS-Steigung H_neu auf H_alt | 0,945 | [0,896; 0,993] | 0,80–1,10 / < 0,65 oder > 1,25 | – | grün |
| M6 | Verzerrung Rest + Länder (n = 165) | −3,30 | [−4,61; −1,94] | \|v\| ≤ 5 / > 8 | −1,2 · −3,7 | grün |
| M7 | gleiches Guide-Band | 180 von 265 = 67,9 % | – | ≥ 65 % / < 55 % | 91,8 % · 68,6 % | grün |
| M8 | gleiche Seite H ≥ 50 | 226 von 265 = 85,3 % | – | ≥ 88 % / < 80 % | 95,9 % · 91,4 % | gelb |

Mit den F2-Schwellen (Plan 2a, gleiche Familie): M1, M2, M3, M7, M8 rot, M4, M6 gelb, M5 grün. Gewichtet mit N_h/n_h (Spitze 132/100, Rest 663/115, Länder 50/50; ergänzend, keine Poolschätzung): mittlere |ΔH| 8,76, Verzerrung −5,22, RMS 11,34, Anteil ≥ 15 26,9 %. Alle 300 Karten (mit markierten): |ΔH| 9,80, ρ 0,850, Verzerrung −5,20.

## 3. Je Schicht

| Schicht | n/N | Verzerrung [95 %] | Median | SD | mittl. \|ΔH\| | RMS | ≥ 15 | Max | ρ | Steigung |
|---|---|---|---|---|---|---|---|---|---|---|
| Spitze `top20` | 100/132 | −5,45 [−7,95; −3,05] | −2,5 | 12,4 | 9,95 | 13,50 | 30 von 100 | 40 | 0,704 | 1,15 |
| Rest (`rest` + `rest_fill`) | 115/663 | −5,74 [−7,48; −3,91] | −5 | 9,6 | 8,87 | 11,15 | 32 von 115 | 30 | 0,791 | 0,83 |
| Länder | 50/50 | +2,30 [+0,60; +4,10] | 0 | 6,3 | 4,10 | 6,67 | 3 von 50 | 20 | 0,839 | 0,88 |
| markiert (nicht in der Primärmenge) | 35/35 | −13,43 [−19,29; −7,14] | −20 | 18,9 | 20,57 | 22,96 | 28 von 35 | 40 | 0,418 | 0,47 |

- **Spitze (nicht bewertet, Plan §6):** −5,45 liegt zwischen −10 und 0 → „vereinbar mit Regression zur Mitte plus mäßiger Großzügigkeit“; keine systematische Überbewertung der Spitze durch F1 belegt. Der Rest liegt gleich tief (−5,74), ohne Auswahl nach hohem H: der Abstand ist eher ein **Niveauunterschied der Spells** als ein Spitzeneffekt.
- **Länder separat:** T = 0 bei 43 von 50 in beiden Läufen, K = 0 bei 34 (neu) gegen 29 (F1); gleiches Band 43 von 50. Die Länder-Skala wird stabil angewandt (|ΔH| 4,10, Einzelstreuung 4,7, so klein wie die Wiederholstreuung F2).
- Explorativ, nach Kartenklasse (Primärmenge): Kreaturen Spitze −5,0 (n = 74), Rest −7,1 (n = 60); Nicht-Kreaturen Spitze −6,7 (n = 26), Rest −4,3 (n = 55). Von 65 Abweichungen ≥ 15 gehen 52 nach unten, 13 nach oben.
- Die 10 größten Abweichungen je Schicht (H_alt → H_neu; nur zum Lesen, Begründungen beider Läufe in der Skript-Ausgabe `top_deviations`, reproduzierbar mit dem Befehl in §8):
  - Spitze: Assert Perfection 50→10, Thought Monitor 45→10, Wary Farmer 55→25, Merrow Skyswimmer 55→25, Cat Collector 50→20, Drogskol Reaver 45→15, Hexhaven Battalion 45→20, Ardent Plea 45→20, Briarhorn 55→30, Lys Alana Informant 50→25.
  - Rest: Ruin Ghost 20→50, Kulrath Mystic 35→10, Safewright Cavalry 30→5, Reluctant Dounguard 45→20, Killer Service 40→15, Tam's Resistance 45→25, Sanctum Plowbeast 35→15, Terastodon 15→35, Burrenton Bombardier 30→10, Kor Hookmaster 45→25.
  - Länder: Maestros Theater 10→30, Mystic Sanctuary 5→25, Temple of the False God 15→30, Hall of Oracles 25→15, Opal Palace 30→20, Tectonic Edge 10→20, Demolition Field 15→25, Jund Panorama 10→20, Sejiri Steppe 10→20, Port Town 40→50.
  - Markiert: Whirler Rogue 70→30, Nature's Claim 25→60, Lyra Dawnbringer 60→25, Imperious Perfect 60→25, Shore Lurker 50→15, Personify 65→35, Shimmer Dragon 40→10, Elspeth, Knight-Errant 60→30, Storm Spirit 45→15, Kappa Cannoneer 40→10.

## 4. Teilkriterien, Ermüdung, Dateieffekt

| Kriterium (n = 265) | E | F | T | R | K | D | H |
|---|---|---|---|---|---|---|---|
| ICC(2,1) mit F1 | 0,84 | 0,91 | 0,84 | 0,86 | 0,90 | 0,87 | 0,87 |
| Grün-Schwelle (ICC G1 − 0,05) | 0,82 | 0,89 | 0,77 | 0,87 | 0,87 | 0,86 | – |
| mittlere \|Δ\| · Verzerrung | 7,8 · −0,8 | 7,3 · −2,4 | 6,6 · −3,3 | 7,9 · +4,0 | 6,8 · +2,3 | 6,1 · +3,3 | 8,4 · −4,1 |
| Spearman | 0,85 | 0,91 | 0,87 | 0,87 | 0,87 | 0,87 | 0,88 |

Teilkriterien nach Plan §7: **gelb** (R 0,86 knapp unter 0,87; kein ICC unter G1 − 0,15). Abdeckung 7 von 7 bei 300 von 300.

**Ermüdung (Plan §8 M):** mittlere |ΔH| Position 1–50 gegen 51–100: Datei 1 8,3 / 7,2 (ρ(Position, ΔH) 0,14), Datei 2 10,6 / 9,2 (0,15), Datei 3 12,3 / 11,2 (0,01). Keine Datei auffällig (Differenz ≤ 3, |ρ| ≤ 0,2); in allen drei Dateien ist die zweite Hälfte etwas näher an F1.
**Dateieffekt und Drift von Rater 3 (explorativ):** Verzerrung je Datei (Primärmenge) −2,4 / −3,6 / −6,3. Bei Spells setzte Rater 3 T in den Positionen 1–50 tiefer (ΔT −11,5, T = 0 bei 8 von 42) als in 51–100 (ΔT −5,9, 6 von 40); das deckt sich mit der Rater-Notiz (T = 0 bei Eigen-Ramp/Zieh-Kreaturen früh, später ankerkonform). Datei 3 trägt damit einen Teil der Niveauabweichung; A6 greift trotzdem nicht (3,52 ≤ 4).

## 5. Die 35 markierten Karten (Plan §7, Zweig 2a)

| Kennzahl | Wert | Referenz |
|---|---|---|
| (a) H_neu in der Prüfer-Spanne | 17 von 35 | F1 2 von 35 (nachgerechnet), V22 20 von 35 |
| (b) H_neu näher an der Spanne als H_alt | 25 von 35 | V22 27 von 35 |
| (c) mittlere ΔH je Art | „zu hoch“ −22,7 (n = 26); „zu niedrig“ +17,9 (n = 7); „Begründung faktisch falsch“ −2,5 (n = 2) | erwartet −, +, beschreibend |
| (d) ΔH „zu hoch“ minus ΔH Spitze (n = 100) | −22,7 − (−5,45) = −17,2 | Urteil braucht ≤ −5 |

Urteil nach Regel: (a) ≥ 14 und (d) ≤ −5 → **„stützt die Prüfer“**. Da der Prüfer laut 2a vermutlich dasselbe Modell wie der zweite Lauf ist, heißt das nur: **Selbstkonsistenz mit dem eigenen Audit**, keine unabhängige Bestätigung. Unabhängige Evidenz gegen F1 an den Rändern bleibt G1 (70 Karten). `rater_H` der Markierungsdatei = F1-H bei 35 von 35.

## 6. Regelclaims (Plan §8 K)

- Gezählt: 588 Claims auf 300 Karten (1,96 je Karte; F1 1,85). Wörtlich: 588 von 588 (V4).
- **Stichprobe:** 100 Claims, höchstens einer je Karte. Verfahren (im Skript `select_claims`): `random.Random(20261123)`; je Karte in Manifest-Reihenfolge ein Claim, bevorzugt aus chulane_cast_trigger, chulane_bounce_replay, etb_reuse, landfall, land_drop, symmetry, timing, sonst aus allen; dann 100 Karten gezogen. Zusammensetzung: 26 chulane_cast_trigger, 15 timing, 15 other, 11 mana, 9 etb_reuse, 7 targeting, 7 landfall, 5 bounce, 5 übrige; Basis 93 Kartentext, 5 Ruling, 2 abgeleitet; reine Typzeilen-Claims 0.
- **Maßstab:** Kartentext, gezeigte Rulings, Comprehensive Rules (Modellurteil, kein XMage-Lauf).
- **Ergebnis:** offensichtlich falsch **0 von 100** (Wilson 95 %: 0 bis 3,7 %) → **grün** (≤ 3); unscharf 2 von 100 (3:15:0 Reluctant Dounguard „replaying gains nothing“: der Chulane-Zug beim Neuwirken bleibt; 3:98:0 Crosstown Courier „two milled cards“: gilt nur bei Stärke 2); offen 0; korrekt 98 (alle übrigen IDs der Skript-Stichprobe). Referenz: Audit D F1 0 von 100. Ein Viertel der Stichprobe ist der einfache Satz „Kreaturzauber löst Chulane aus“.

## 7. Empfehlung (Vorschlag, nichts geändert)

Nach Plan ist H **„teilweise bestätigt“** (G1-Schwellen); mit den Schwellen für „gleiche Familie“, die A3 nicht ausschließt, wäre es „nicht bestätigt“. M1 liegt mit 8,38 im Bereich 8 bis 11, für den Plan §6 **kein Urteil über die Verwendung** vorsieht. Der Rang hält gepoolt knapp (ρ 0,881), innerhalb der Schichten deutlich schwächer (Spitze 0,704, Rest 0,791). Die Einzelstreuung 8,1 [7,3; 8,9] liegt **über 8**, also über der Obergrenze der heutigen Anzeige „±5–8“; |ΔH| ≥ 15 bei 24,5 %. Systematisch ist ein **Niveauunterschied bei Spells** von rund −5 (Spitze −5,45, Rest −5,74), bei Ländern +2,3 [0,6; 4,1]; eine gesonderte Überbewertung der Spitze zeigt sich nicht (Bias zwischen −10 und 0). Einen **Gesamtlauf aller 922 Karten braucht es nach Plan §9 nicht** (auch bei „nicht bestätigt“ wäre der nächste Schritt eine Adjudikation einzelner Klassen; ohne Owner-Freigabe kein weiterer Lauf); wenn adjudiziert wird, dann zuerst das H-Band 40–55 (explorativ Einzelstreuung 10,6, n = 83) und die 65 Karten mit |ΔH| ≥ 15. Für die **Tierliste** (nur Vorschlag, die Verwendung bleibt offen beim Owner, nichts still anpassen): die Streuung als „±5–8, jüngster Lauf 8,1 (n = 265, Familie ungeprüft)“ nennen; die Bänder aus Audit A passen explorativ (H ≤ 10: 4,9, n = 49; H 40–55: 10,6, n = 83; H ≥ 60: 10.–90. Perzentil −15 bis +5, n = 47). Die Prüfer-Marken der 35 Karten bleiben „Prüfer-Marke“ und werden nicht zu „bestätigt“ (Selbstkonsistenz). Die Entscheidung über die Verwendung liegt beim Owner.

## 8. Herkunft und Reproduktion

| Datei | Ort | SHA-256 |
|---|---|---|
| `rr_output_1.jsonl` (100 Zeilen, 151.711 B) | `data/research/chulane_rubric_v2_20261118/second_run_20261122/` | `7d55f195be2e02dbaecc549e7d4d225f1f7d5228a9068ce40d494fa50a8a815c` |
| `rr_output_2.jsonl` (100 Zeilen, 153.877 B) | ebenda | `156cb4fd0a1ec80ae8172a5fef49fab503a955b607bad4db9d403ed02568fe0a` |
| `rr_output_3.jsonl` (100 Zeilen, 156.619 B) | ebenda | `4d09a087521abc5c04bb3c42e305fff8aaea6015b3b9cdf47a28e3151fdce8f4` |
| `rr_sample_manifest.json` (300 Karten, Seed 20261122, 61.969 B) | ebenda | `c6b22bdc8336b9ce761d52a24ea5c1c00db72a0aa17ddf075307554c571a0302` |
| `rr_input_1.jsonl` (Kartenblöcke aus Commit `138a50c264f2`, 161.633 B) | ebenda | `e7024b5545ccfe5f8c9980f1822888d0cddf1a6b31f32284bb3c8d2d4e32d07f` |
| `rr_input_2.jsonl` (162.339 B) | ebenda | `95661051fb4bb713da8b5797e8a293ac1236fadb64e425c21e354421d09415d4` |
| `rr_input_3.jsonl` (155.815 B) | ebenda | `4b0d282e72f51db2d588f35c8567f48d6cb566aeadd3ae3190d8f409cb642c45` |
| `rr_guide_v2_1_rendered.md` (Guide an die Rater, Chulane-Text für V4, 23.959 B) | ebenda | `2b93fc68bc8f1740450c58fc0860a8e9570983a9c75149d5754ad3281bf3d8da` |
| `rr_rater_instructions.md` · `rr_output_schema.json` | Scratchpad | `3a2aecf99d26678675237c55a9e500d21e9a77d2a81c62a427889fc53a24f1c1` · `b5f5c163ac1ef797539941d3a293001271eb23c4e0149116747472138245f4de` |
| Vergleichsplan (Original) · `rr_make_sample.py` | Scratchpad | `bd53838236e902e870e9891db53007d28cc72543ed2130d4841627e5585cba0c` · `e6c0e9b0fc438f602992db2828ab335068481600f6d6cf5e2e4b0f367a236363` |
| `rr_analysis_plan_redacted.md` (Plan-Kopie: nur Modellname → „R2“, ein Ordnername und ein Kontextname ersetzt, 15 Stellen; sonst gleich) | `…/second_run_20261122/` | `11060c02c9bcc94a5e0e95e74c965fffc88e00eaa720672eb04e67f132cf39fe` |
| `fullrun_ratings.jsonl` (F1) | `data/research/chulane_rubric_v2_20261118/` | `eb81d9c35be9dedf1448b2b1c3bd2d46d51c6b62ca15fc73b28bd2309ab6aa12` |
| `audit/audit_A_flagged.jsonl` | ebenda | `8c285e2a4dcc792bb62861cf3ef7d2f171b89c4c7f28a706deb022eb7c2f7eb3` |
| `rule_claim_verdicts.json` (100 IDs, 98 korrekt, 2 unscharf wie §6) | `…/second_run_20261122/` | `e9101faf5a75ce16fde3cd3fe5bc380403298cb70c096435452c14aaa51885f5` |

Skript `scripts/analysis/second_run_compare.py` (nur Standardbibliothek, deterministisch), Tests `tests/unit/test_second_run_compare.py` (synthetische Daten). Dokumentierter Lauf aus dem Repo (zweimal, byte-gleiches Ergebnis-JSON, SHA-256 `1c20061daeef8cf603f1403d3438de11cbb6d41d802e32ffe7cf5d1b8e506684`; Ausgabe „teilweise bestaetigt“ / mit F2-Schwellen „nicht bestaetigt“): `python3 scripts/analysis/second_run_compare.py --rr-dir data/research/chulane_rubric_v2_20261118/second_run_20261122 --old data/research/chulane_rubric_v2_20261118/fullrun_ratings.jsonl --flagged data/research/chulane_rubric_v2_20261118/audit/audit_A_flagged.jsonl --verdicts data/research/chulane_rubric_v2_20261118/second_run_20261122/rule_claim_verdicts.json --out <Ergebnis.json>`. Die Rohdaten enthalten nur Kartentext-Blöcke, Kartennamen, `oracle_id`, Bewertungen, Begründungen, Guide und Plan; keine Preise, Nutzung oder privaten Daten.
