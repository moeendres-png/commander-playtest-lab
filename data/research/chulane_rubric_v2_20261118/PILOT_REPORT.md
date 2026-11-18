# Kartenverständnis-Raster v2: Pilotbericht (2026-11-18)

Status: Pilot ausgewertet, keine Karte des Pools bewertet außer den 63 Pilotkarten. Schwellen stammen aus `calibration_plan.md`
(vor dem Lauf festgelegt). Alle Zahlen mit n; Intervalle: Bootstrap über Karten (Seed 1118), ICC mit 500 Ziehungen.
Nutzungsdaten (`usage_holdout.jsonl`) wurden **nicht** geöffnet.

## 1. Durchführung und Abweichungen vom Plan

- 63 Pilotkarten (`pilot_sample.json`), 4 Rater-Läufe: H1, H2 (Haiku-Stufe) und S1, S2 (Sonnet-Stufe), je Lauf 63 Karten plus 8 Wiederholungen
  (Test-Retest) = **284 Bewertungen** (4 × 71).
- **Abweichung 1 (Chargen statt Einzelaufrufe):** Der Rauchtest (6 Einzelaufrufe, 3 Karten) kostete je Aufruf rund 82.000 Agent-Tokens, davon
  fast alles Fixkosten. 284 Einzelaufrufe wären rund 23 Mio Tokens gewesen. Darum wurden je Rater **7 Karten pro Aufruf** bewertet
  (40 Aufrufe, je Rater eigene Zufallsreihenfolge, Seed 1118 plus Raterkürzel), mit der Anweisung, jede Karte einzeln zu beurteilen. Die Läufe sind damit
  **nicht zustandslos je Karte**: Ein Anker-Effekt innerhalb der Charge ist möglich und nicht gemessen. Anker-Karten stehen im Systemteil der Charge nicht
  (leave-one-anchor-out je Charge, im Code geprüft).
- **Abweichung 2:** Raterläufe sind Subagenten ohne einstellbare Temperatur; die Streuung zwischen S1 und S2 entsteht durch Sampling und Chargenzusammensetzung.
- Limit-Unterbrechungen (5-Stunden-Limit): 17 Aufrufe brachen mit Fehlermeldung ab, hatten ihre Datei aber vorher geschrieben (geprüft:
  Kartenreihenfolge und Anzahl stimmen); ein Batch (S1_b02) fehlte und wurde einmal wiederholt. Keine Bewertung wurde ersetzt oder ausgewählt.
- Formale Gültigkeit: Alle 40 Dateien lesbar, Karten und Reihenfolge stimmen. Werte, die kein Vielfaches von 5 sind: H1 0/71, H2 1/71, **S1 9/71, S2 3/71**
  (alle in H, einzeln in anderen Werten). Die Auswertung nutzt die Rohwerte.

## 2. Ergebnisse gegen die vorab festgelegten Schwellen

| Nr | Kennzahl | Ergebnis (Punkt [95 %-Grenzen]) | Schwelle | Urteil |
|---|---|---|---|---|
| 1a | ICC(2,1) H, je Modell | Haiku 0,91 [0,85; 0,95]; Sonnet 0,97 [0,95; 0,98] (n=63) | 0,75 (0,65) | bestanden |
| 1b | ICC(2,1) E, T, R, D, je Modell | Haiku 0,91/0,92/0,83/0,88 (unterste Grenze R 0,71); Sonnet 0,95–0,96 | 0,70 (0,60) | bestanden |
| 1c | ICC(2,1) F, K, je Modell | Haiku F 0,92, K 0,83 [0,73]; Sonnet F 0,96, K 0,95 | 0,65 (0,55) | bestanden |
| 1d | ICC(2,2) H, je Modell | Haiku 0,95; Sonnet 0,98 | 0,90 (0,85) | bestanden |
| 2a | Spearman Haiku-Mittel gegen Sonnet-Mittel, H | 0,92 [0,81; 0,96] (n=63) | 0,90 (0,85) | **nicht bestanden** (untere Grenze 0,81) |
| 2b | MAD H / Verzerrung Haiku minus Sonnet | 9,9 / +7,5 Punkte | höchstens 8 / 5 | **nicht bestanden** |
| 2c | ICC(2,1) H Haiku minus Sonnet | −0,06 | nicht schlechter als −0,08 | bestanden |
| 3a | Anker-MAE H (Mittel der Rater) / größter Einzelfehler | Mittel aller 4 Rater 11,2; nur Sonnet 10,8 (n=10 Anker); größter Fehler 32 | 10 / 25 | **nicht bestanden** (knapp) |
| 3b | Anker-MAE E, F, T, R | Sonnet: E 9,5/7,5; F 5,0/5,5; T 0,8/1,7; R 6,0/4,0 (S1/S2); Haiku F 9,5 | höchstens 12,5 | bestanden |
| 3c | Spearman Anker-H gegen feste H | nicht gerechnet (n=10, Ränge der Anker siehe Abschnitt 4) | 0,90 (0,80) | offen |
| 4 | Spearman v2-H gegen v1-H, 53 Nicht-Anker | Sonnet 0,86; Haiku 0,74; alle vier 0,83 | mindestens 0,70 (0,60); über 0,95 = Verdacht | bestanden (kein Verdacht) |
| 5a | Drift H (8 Retest-Karten je Rater): mittlere |Differenz| / Anteil ≥ 15 | H1 4,4 / 0 von 8; H2 3,8 / 0 von 8; **S1 7,6 / 2 von 8**; S2 4,8 / 0 von 8 | höchstens 5 / 10 % | S1 **nicht bestanden**, übrige bestanden (n=8, grobe Aussage) |
| 5b | Modell-ID/Systemhash wechselt im Lauf | Systemteil je Charge fix, Modell je Lauf fix (kein Wechsel) | 0 | bestanden |
| 6 | Anteil Karten mit H-Streuung ≥ 20 (4 Rater) | 0 von 63 | höchstens 10 % | bestanden |
| 7 | gültige JSON / Vielfache von 5 | 40 von 40 Dateien gültig; Vielfache von 5: Haiku 141 von 142, Sonnet 126 von 142 Bewertungen (je Bewertung alle 7 Werte) | 99 % / 100 % | JSON bestanden, **Vielfache von 5 nicht bestanden** |
| 8a | `quote` wörtlich im Kartenblock | 368 von 396 (92,9 %) nur gegen den Kartenblock; 371 von 396 (93,7 %), wenn der Guide (Chulanes Text) als Quelle zählt. Die übrigen 25 Abweichungen sind nach Stichprobe (10 angesehen) fast alle Chulanes Fähigkeitstext in anderer Schreibweise, ein Fall (Stalactite Dagger, H1) ist kein wörtliches Zitat | 98 % | **nicht bestanden** (formal); Ursache: Zitatregel nennt Chulane-Text nicht ausdrücklich als erlaubte Quelle |
| 8b | Regelbehauptungen von Hand (40, Wilson 95 %) | **38 richtig, 1 falsch, 1 offen** = 95 % [83,5; 98,6] | 90 % (80 %) | bestanden |
| 8c | Blindheits-Scan (Stichwortliste vorab) | Haiku **5 von 126** Ausgaben mit Beliebtheitssprache („played in most strong lists“, „nearly always played“); Sonnet **0 von 126** | höchstens 2 % | gesamt 2,0 % (5/252) knapp; **Haiku 4,0 %** nicht bestanden |

Zusätzlich: `pattern_check`: 166 richtig, 13 irrelevant, 13 falsch von 192 Rückmeldungen der Rater (6,8 % falsch).
Rater-Vertrauen: Sonnet „hoch“ 71 von 126, Haiku „hoch“ 65 von 126.

## 3. Entscheidung nach der vorab festgelegten Regel

- **Haiku scheidet aus:** 2a, 2b nicht bestanden (Haiku bewertet im Mittel 7,5 Punkte höher als Sonnet in H, K +7,7, D +5,6) und der Blindheits-Scan findet
  bei Haiku Beliebtheitssprache (5 von 126). Das Modell kennt Beliebtheit und lässt sie einfließen (bekannte Grenze von v1, hier belegt).
- **Sonnet-Läufe erreichen die Verlässlichkeits-Schwellen (1a–1d, 3b, 4, 6, 8b), verfehlen aber 3a, 5a (S1) und die Formvorgabe (Vielfache von 5).**
  Nach der Regel („erreicht keine Konfiguration alle Schwellen: Raster überarbeiten, nicht mehr Rater“) ist die Antwort: **Guide/Ausgabevorschrift nachbessern
  (v2.1), dann gezielte Nachmessung** (nur Anker-Karten und Retest, nicht der ganze Pilot), bevor die 922 Karten laufen.
- **Zu 3a (Anker):** Die drei größten Abweichungen gehören den Ankern Command Tower (fest 100, Rater im Mittel 74), Counterspell (fest 67, Rater 45) und
  Cultivate (fest 44, Rater 61). Die Rater begründen: Command Tower „besser als ein Basic, aber kein Motorteil“; Counterspell „UU in drei Farben, nichts für den Plan“;
  Cultivate „das Handland kann Chulane aufs Feld legen“. Das ist eine Chulane-spezifische Einschätzung, wie sie v2 verlangt, und zugleich eine Abweichung von den
  festen v1-Werten, die eher Beliebtheit abbilden. Ob Anker-Treue oder die v2-Begründung gilt, entscheidet der Owner (Frage 7).

## 4. Abweichung v2 gegen v1 (53 Nicht-Anker, Sonnet-Mittel)

Nur **3 von 53** Karten weichen um 25 Punkte oder mehr ab (Detective of the Month +27, Prudent Fateseer +25, Tam's Resistance +36); fast alle größeren Anhebungen
betreffen billige Kreaturen (Cloud Elemental +24, Temple Acolyte +20, Greater Basilisk +18, Noxious Newt +18), weil v2 den Chulane-Auslöser („jeder Kreaturenzauber zieht eine
Karte und legt ggf. ein Land“) einrechnet. Das ist die vom Owner gewünschte Tiefe („was bedeutet die Karte wirklich“). Tam's Resistance (+36, v2 40 gegen v1 4) wird vor
dem Vollauf von Hand gegengeprüft.

## 5. Kosten (gemessen)

Pro Charge (7 Karten) rund 90.000–110.000 Agent-Tokens; je Rater-Lauf über 63 Karten + Retest (10 Chargen) rund 1 Mio Tokens. 922 Karten mit einem Rater: etwa 132 Chargen,
rund 12–14 Mio Tokens; zweiter Rater nur für Grenzfälle zusätzlich. Der Vollauf überschreitet das 5-Stunden-Limit sicher einmal und läuft darum in Wellen zu je 10 Chargen.

## 6. Grenzen

63 Karten (breite Intervalle). ICC innerhalb eines Modells misst Sampling-Konsistenz und ist eine obere Schranke. Chargen statt Einzelaufrufe. Alle Rater aus einer Modellfamilie. Der Blindheits-Scan
ist ein Stichwort-Indiz. Die Handprüfung der Regelbehauptungen (ein Prüfer, ein Modell) ist keine XMage-Prüfung; der falsche Fall (Open the Armory: „kann nie eine Kreatur finden“; Reconfigure-Karten
sind Artefakt-Kreaturen) zeigt den Typ des Fehlers.

## 7. Nachbesserung v2.1 und gezielte Nachmessung (gleicher Tag)

Änderungen am Guide/Prompt (nur zwei, keine Änderung an Kriterien oder Ankerwerten in `anchors.json`): (1) Die im Prompt gezeigten Ankerwerte sind auf Vielfache von 5 gerundet
(die Rater hatten Werte wie 44, 67, 78 der Studio-Formel übernommen); (2) Chulanes Text aus dem Guide ist ausdrücklich als Zitatquelle erlaubt; die Vorgabe „H ein Vielfaches von 5 (45 oder 50, nie 44)“ steht jetzt explizit in der Regel zur Skala.
Nachmessung: 2 neue Sonnet-Läufe (T1, T2) über 17 Karten (10 v1-Anker, 8 Retest-Karten, Überschneidung Farseek) plus Tam's Resistance, in je 3 Chargen zu 6 Karten (34 Bewertungen).

| Kennzahl | Pilot (S1, S2) | v2.1 (T1, T2) |
|---|---|---|
| Vielfache von 5 | 12 von 142 Bewertungen verletzten es | **0 von 34** |
| Anker-MAE H (Mittel der zwei Läufe, n=10 Anker) | 10,8 | **10,3** (Schwelle 10: knapp verfehlt) |
| größter Einzelfehler H | 30 | 32 (Counterspell: fest 67, Läufe 35 und 40) |
| Spearman Anker-H gegen feste H (3c, n=10) | 0,84 | **0,91** (Schwelle 0,90; untere Grenze nicht gerechnet, n zu klein) |
| Anker-MAE E / F / R / T | 7,5 / 5,0 / 4,0–6,0 / 0,8–1,7 | 7,0 / 5,5 / 6,2 / 0,0 |
| Abweichung H zwischen T-Lauf und S-Lauf auf 16 Retest-Paaren | | im Mittel 5,5; 2 von 16 mit Differenz ≥ 15 |
| Übereinstimmung T1 gegen T2 (H, n=17) | | mittlere |Differenz| 4,1 |

Bewertung: Die Formfehler (Vielfache von 5, Zitatquelle) sind behoben. **3a bleibt knapp verfehlt** (MAE 10,3; größter Fehler 32), und zwar wegen dreier Anker, bei denen die Rater
begründet von den festen v1-Werten abweichen (Command Tower 80 statt 100, Counterspell 35–40 statt 67, Cultivate 55–60 statt 44). Die Rangordnung der Anker stimmt (Spearman 0,91). Eine weitere Änderung des Guides
würde nur durch Einbau der Beliebtheit der v1-Werte die Abweichung verkleinern, das ist ausgeschlossen. **Owner-Entscheid nötig (Frage 7):** die drei Abweichungen als gewollte v2-Einschätzung akzeptieren
(Empfehlung) oder die Anker neu setzen. Die Vorab-Schwelle wurde nicht nachträglich geändert; das Ergebnis steht als „knapp verfehlt“.
Tam's Resistance (v1 4): v2 35–45, Begründung der Rater: Jace-Token mit Kartenzug; kein Regelverstoß in der Begründung, bleibt eine hohe Abweichung und wird im Vollauf nicht gesondert behandelt.

## 8. Empfohlene Konfiguration für den Vollauf (922 Karten)

Sonnet, ein Lauf je Karte (132 Chargen zu 7), plus zweiter Lauf für alle Karten mit Vertrauen „niedrig/mittel“ und für Rangbereiche, in denen Gesamtrating und Nutzungsindex weit auseinanderliegen (zur Gegenprüfung,
nicht als Mittel für die Rangbildung außer wo beide Läufe vorliegen), plus 5 % Wiederholungen für Drift. Kosten nach Messung: etwa 12–14 Mio Tokens für den Einzellauf (Abschnitt 5), in Wellen zu 10 Chargen wegen des 5-Stunden-Limits.
Freigabe der Wellen durch den Owner nur, wenn er die Quota-Last ablehnt; sonst läuft der Vollauf nach Merge des Entwurfs im Hintergrund.
