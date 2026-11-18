# Kartenverständnis-Raster v2: Pilotbericht (2026-11-18)

Status: Pilot ausgewertet (Abschnitte 1 bis 8); danach ist der Vollauf über alle 922 Karten durchgeführt worden (Abschnitt 9), obwohl nicht alle
vorab festgelegten Schwellen (3a, 5a, 8a) erfüllt waren. Schwellen stammen aus `calibration_plan.md` (vor dem Lauf festgelegt). Alle Zahlen mit n; Intervalle: Bootstrap über Karten (Seed 1118), ICC mit 500 Ziehungen.
Nutzungsdaten (`usage_holdout.jsonl`) wurden im Pilot **nicht** geöffnet (Abschnitt 9 nur nach dem Einfrieren der Bewertungen).
Die genaue Modell-Identität der Rater ist im Verlauf der Owner-Session festgehalten, nicht im Repo.

## 1. Durchführung und Abweichungen vom Plan

- 63 Pilotkarten (`pilot_sample.json`), 4 Rater-Läufe: H1, H2 (kleine Rater-Stufe) und S1, S2 (große Rater-Stufe), je Lauf 63 Karten plus 8 Wiederholungen
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
| 1a | ICC(2,1) H, je Modell | kleine Stufe 0,91 [0,85; 0,95]; große Stufe 0,97 [0,95; 0,98] (n=63) | 0,75 (0,65) | bestanden |
| 1b | ICC(2,1) E, T, R, D, je Modell | kleine Stufe 0,91/0,92/0,83/0,88 (unterste Grenze R 0,71); große Stufe 0,95–0,96 | 0,70 (0,60) | bestanden |
| 1c | ICC(2,1) F, K, je Modell | kleine Stufe F 0,92, K 0,83 [0,73]; große Stufe F 0,96, K 0,95 | 0,65 (0,55) | bestanden |
| 1d | ICC(2,2) H, je Modell | kleine Stufe 0,95; große Stufe 0,98 | 0,90 (0,85) | bestanden |
| 2a | Spearman Mittel der kleinen gegen Mittel der großen Stufe, H | 0,92 [0,81; 0,96] (n=63) | 0,90 (0,85) | **nicht bestanden** (untere Grenze 0,81) |
| 2b | MAD H / Verzerrung kleine minus große Stufe | 9,9 / +7,5 Punkte | höchstens 8 / 5 | **nicht bestanden** |
| 2c | ICC(2,1) H kleine minus große Stufe | −0,06 | nicht schlechter als −0,08 | bestanden |
| 3a | Anker-MAE H (Mittel der Rater) / größter Einzelfehler | Mittel aller 4 Rater 11,2; nur große Stufe 10,8 (n=10 Anker); größter Fehler 32 | 10 / 25 | **nicht bestanden** (knapp) |
| 3b | Anker-MAE E, F, T, R | große Stufe: E 9,5/7,5; F 5,0/5,5; T 0,8/1,7; R 6,0/4,0 (S1/S2); kleine Stufe F 9,5 | höchstens 12,5 | bestanden |
| 3c | Spearman Anker-H gegen feste H | Pilot (Mittel S1, S2): 0,84 (n=10, untere Grenze nicht gerechnet); v2.1: 0,91 (Abschnitt 7) | 0,90 (0,80) | Pilot **nicht bestanden** (Punkt 0,84 < 0,90); v2.1 Punkt erreicht, Grenze offen |
| 4 | Spearman v2-H gegen v1-H, 53 Nicht-Anker | große Stufe 0,86; kleine Stufe 0,74; alle vier 0,83 | mindestens 0,70 (0,60); über 0,95 = Verdacht | bestanden (kein Verdacht) |
| 5a | Drift H (8 Retest-Karten je Rater): mittlere |Differenz| / Anteil ≥ 15 | H1 4,4 / 0 von 8; H2 3,8 / 0 von 8; **S1 7,6 / 2 von 8**; S2 4,8 / 0 von 8 | höchstens 5 / 10 % | S1 **nicht bestanden**, übrige bestanden (n=8, grobe Aussage) |
| 5b | Modell-ID/Systemhash wechselt im Lauf | Systemteil je Charge fix; die Modell-ID ist bewusst nicht im Repo, ein Wechsel ist hier nicht prüfbar | 0 | im Repo nicht prüfbar |
| 6 | Anteil Karten mit H-Streuung ≥ 20 (4 Rater) | 0 von 63 | höchstens 10 % | bestanden |
| 7 | gültige JSON / Vielfache von 5 | 40 von 40 Dateien gültig; Vielfache von 5: kleine Stufe 141 von 142, große Stufe 130 von 142 Bewertungen korrekt (12 Verstöße: S1 9, S2 3; je Bewertung alle 7 Werte) | 99 % / 100 % | JSON bestanden, **Vielfache von 5 nicht bestanden** |
| 8a | `quote` wörtlich im Kartenblock | Pilot (v2-Guide): 368 von 396 (92,9 %) gegen den Kartenblock; mit Chulanes Oracle-Text aus dem Guide als zweiter Quelle 395 von 396 (99,7 %). Neu gemessen mit `scripts/quote_check.py` (Kleinschreibung und Leerraum normalisiert, Guide-Zeilenpräfixe „> “ entfernt); die frühere Angabe 371 von 396 ist damit ersetzt. v2.1 (T1, T2, nach Änderung der Zitatregel): 50 von 56 gegen den Kartenblock, **56 von 56** mit Chulane-Text. Vollauf: 1337 von 1708 gegen den Kartenblock, **1706 von 1708 (99,9 %)** mit Chulane-Text (1708 von 1708, wenn zusätzlich Satzzeichen ignoriert werden) | 98 % | Pilot **nicht bestanden** (Zitatregel nannte Chulane-Text nicht als Quelle); **mit der v2.1-Regel erfüllt** (v2.1 und Vollauf, Quelle Kartenblock plus Chulane-Text); gegen den Kartenblock allein weiter nicht erfüllt |
| 8b | Regelbehauptungen von Hand (40, Wilson 95 %) | **38 richtig, 1 falsch, 1 offen** = 95 % [83,5; 98,6] | 90 % (80 %) | bestanden |
| 8c | Blindheits-Scan (Stichwortliste vorab) | kleine Stufe **5 von 126** Ausgaben mit Beliebtheitssprache („played in most strong lists“, „nearly always played“); große Stufe **0 von 126** | höchstens 2 % | gesamt 2,0 % (5/252) knapp; **kleine Stufe 4,0 %** nicht bestanden |

Zusätzlich: `pattern_check`: 166 richtig, 13 irrelevant, 13 falsch von 192 Rückmeldungen der Rater (6,8 % falsch).
Rater-Vertrauen: große Stufe „hoch“ 71 von 126, kleine Stufe „hoch“ 65 von 126.

## 3. Entscheidung nach der vorab festgelegten Regel

- **Die kleine Stufe scheidet aus:** 2a, 2b nicht bestanden (sie bewertet im Mittel 7,5 Punkte höher als die große Stufe in H, K +7,7, D +5,6) und der Blindheits-Scan findet
  bei der kleinen Stufe Beliebtheitssprache (5 von 126). Das Modell kennt Beliebtheit und lässt sie einfließen (bekannte Grenze von v1, hier als Indiz).
- **Die Läufe der großen Stufe erreichen die Verlässlichkeits-Schwellen (1a–1d, 3b, 4, 6, 8b), verfehlen aber 3a, 5a (S1) und die Formvorgabe (Vielfache von 5).**
  Nach der Regel („erreicht keine Konfiguration alle Schwellen: Raster überarbeiten, nicht mehr Rater“) ist die Antwort: **Guide/Ausgabevorschrift nachbessern
  (v2.1), dann gezielte Nachmessung** (nur Anker-Karten und Retest, nicht der ganze Pilot), bevor die 922 Karten laufen.
- **Zu 3a (Anker):** Die drei größten Abweichungen gehören den Ankern Command Tower (fest 100, Rater im Mittel 74), Counterspell (fest 67, Rater 45) und
  Cultivate (fest 44, Rater 61). Die Rater begründen: Command Tower „besser als ein Basic, aber kein Motorteil“; Counterspell „UU in drei Farben, nichts für den Plan“;
  Cultivate „das Handland kann Chulane aufs Feld legen“. Das ist eine Chulane-spezifische Einschätzung, wie sie v2 verlangt, und zugleich eine Abweichung von den
  festen v1-Werten, die eher Beliebtheit abbilden. Ob Anker-Treue oder die v2-Begründung gilt, entscheidet der Owner (Frage 7).

## 4. Abweichung v2 gegen v1 (53 Nicht-Anker, Mittel der großen Stufe)

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
Nachmessung: 2 neue Läufe der großen Stufe (T1, T2) über 17 Karten (10 v1-Anker, 8 Retest-Karten, Überschneidung Farseek) plus Tam's Resistance, in je 3 Chargen zu 6, 6 und 5 Karten (17 Karten je Lauf, 34 Bewertungen).

| Kennzahl | Pilot (S1, S2) | v2.1 (T1, T2) |
|---|---|---|
| Vielfache von 5 | 12 von 142 Bewertungen verletzten es | **0 von 34** |
| Anker-MAE H (Mittel der zwei Läufe, n=10 Anker) | 10,8 | **10,35** (Schwelle 10: verfehlt) |
| größter Einzelfehler H | 32 | 32 (Counterspell: fest 67, Läufe 35 und 40) |
| Spearman Anker-H gegen feste H (3c, n=10) | 0,84 | **0,91** (Schwelle 0,90; untere Grenze nicht gerechnet, n zu klein) |
| Anker-MAE E / F / R / T | 7,5 / 5,0 / 4,0–6,0 / 0,8–1,7 | 7,0 / 5,5 / 6,2 / 0,0 |
| Abweichung H zwischen T-Lauf und S-Lauf auf 16 Retest-Paaren | | im Mittel 5,5; 2 von 16 mit Differenz ≥ 15 |
| Übereinstimmung T1 gegen T2 (H, n=17) | | mittlere |Differenz| 4,1 |
| Drift 5a (Ersatzgröße: T gegen S auf den 16 Retest-Paaren; Schwelle höchstens 5 / 10 %) | S1 7,6 / 2 von 8 | 5,5 > 5 und 2 von 16 = 12,5 % > 10 %: **verfehlt** |

Bewertung: Die Formvorgabe „Vielfache von 5“ ist behoben (0 von 34). Die Zitatregel ist gemessen (8a): mit Chulanes Oracle-Text aus dem Guide als Quelle erfüllt (v2.1 56 von 56; Vollauf 1706 von 1708), gegen den Kartenblock allein nicht (50 von 56; 1337 von 1708). Der Drift-Test 5a ist **verfehlt/offen**: die Ersatzgröße (T gegen S, 16 Paare) liegt über beiden Schwellen; ein echter Drift-Test mit 5 % Wiederholungen steht für den Vollauf aus. **3a bleibt verfehlt** (MAE 10,35 > 10; größter Fehler 32), und zwar wegen dreier Anker, bei denen die Rater
begründet von den festen v1-Werten abweichen (Command Tower 80 statt 100, Counterspell 35–40 statt 67, Cultivate 55–60 statt 44). Die Rangordnung der Anker stimmt (Spearman 0,91). Eine weitere Änderung des Guides
würde nur durch Einbau der Beliebtheit der v1-Werte die Abweichung verkleinern, das ist ausgeschlossen. **Owner-Entscheid nötig (Frage 7):** die drei Abweichungen als gewollte v2-Einschätzung akzeptieren
(Empfehlung) oder die Anker neu setzen. Die Vorab-Schwelle wurde nicht nachträglich geändert; das Ergebnis steht als „knapp verfehlt“.
Tam's Resistance (v1 4): v2 35–45, Begründung der Rater: Jace-Token mit Kartenzug; kein Regelverstoß in der Begründung, bleibt eine hohe Abweichung und wird im Vollauf nicht gesondert behandelt.

## 8. Empfohlene Konfiguration für den Vollauf (922 Karten)

Große Stufe, ein Lauf je Karte (132 Chargen zu 7), plus zweiter Lauf für alle Karten mit Vertrauen „niedrig/mittel“ und für Rangbereiche, in denen Gesamtrating und Nutzungsindex weit auseinanderliegen (zur Gegenprüfung,
nicht als Mittel für die Rangbildung außer wo beide Läufe vorliegen), plus 5 % Wiederholungen für Drift. Kosten nach Messung: etwa 12–14 Mio Tokens für den Einzellauf (Abschnitt 5), in Wellen zu 10 Chargen wegen des 5-Stunden-Limits.
Durchgeführt ist nur der Einzellauf (Abschnitt 9); der zweite Lauf für Grenzfälle und die Drift-Wiederholungen stehen aus.

## 9. Vollauf: Qualität und Einordnung (nach dem Einfrieren)

Der Vollauf ist durchgeführt, obwohl nicht alle vorab festgelegten Schwellen (3a, 5a, 8a) erfüllt waren. Ob die eingefrorenen Bewertungen
Verwendung finden, hängt am Owner-Entscheid zu Frage 7 (Anker); das ist nicht entschieden. Datei: `fullrun_ratings.jsonl`, Auswertung: `scripts/full_qa.py`.
Ein Rater-Lauf der großen Stufe, Guide v2.1, 132 Chargen zu 7 Karten; kein Kartenwert wurde ersetzt oder ausgewählt.

| Kennzahl | Ergebnis (n/N) |
|---|---|
| Karten bewertet | 922 von 922 |
| Werte keine Vielfachen von 5 | 0 von 922 |
| Vertrauen hoch / mittel / niedrig | 423 / 498 / 1 (von 922) |
| Zitatregel (8a, Chulane-Text als Quelle) | 1706 von 1708 Zitaten (99,9 %); gegen den Kartenblock allein 1337 von 1708 |
| Blindheits-Scan (Stichwortliste aus `full_qa.py`) | 7 von 922 Ausgaben mit Treffer: 3 echte Beliebtheitsaussagen (Aether Adept, Reclamation Sage, Path to Exile „strong staple“) und 4 Verneinungen („not a staple“) |
| H in Zehnerbändern | 0–9: 72, 10–19: 185, 20–29: 185, 30–39: 171, 40–49: 141, 50–59: 75, 60–69: 47, 70–79: 33, 80–89: 12, 90–99: 1; Median 30,0, Mittel 30,7 (n=922) |
| Spearman v2-H gegen v1-H | 0,854 (n=922) |

Beschreibender Vergleich mit Nutzung, erst nach dem Einfrieren (`usage_holdout.jsonl` lokal, kein Gewicht im Index, keine Pro-Karte-Werte hier):

- Spearman H gegen Quelldeck-Anzahl 0,504 (n=922); nur Karten mit Nutzung 0,478 (n=736). Die 186 Karten ohne Nutzung haben H-Mittel 20,1, die 736 mit Nutzung 33,4.
- Referenzdeck (79 gegen 843 Karten), AUC: v2-H 0,819, v1-H 0,845, Quelldeck-Anzahl 0,924. Nichtunterlegenheit (v2 mindestens v1 minus 0,03): Differenz −0,027 (ungerundet), **knapp erfüllt**.
- Das Referenzdeck ist teils nach Beliebtheit gebaut (zirkulär für den Nutzungsvergleich, siehe Plan).

Grenzen: ein Rater-Lauf ohne zweiten Lauf, kein Drift-Test, Modell-Vorwissen über Beliebtheit (die drei Treffer des Scans), alle Rater aus einer Modellfamilie, Chargen zu 7 Karten, Anker-Abweichung (3a) ungeklärt.

## 10. Drift-Test des Vollaufs (49 zufällige Karten, zweiter Lauf, 2026-11-18)

Vorab festgelegt (5a): mittlere absolute H-Differenz höchstens 5 und Anteil der Karten mit H-Differenz ab 15 höchstens 10 %. Stichprobe: 49 Karten (Zufallsziehung, Seed `1118-drift`) aus den 922, in 7 Chargen zu 7 Karten ein zweites Mal von derselben Rater-Stufe bewertet (Rater F2, gleicher Guide v2.1, eigene Zufallsreihenfolge; Rohdaten `fulldrift_ratings.jsonl`, Auswertung `scripts/drift_eval.py`).

| Kennzahl (n = 49 Karten) | Ergebnis |
|---|---|
| H: mittlere absolute Differenz | **5,10** (95-%-Intervall 3,88 bis 6,53) |
| H: Anteil Karten mit Differenz ab 15 | **3 von 49 = 6,1 %** (größte Differenz 30) |
| ICC(2,1) je Kriterium | E 0,92 · F 0,96 · T 0,92 · R 0,95 · K 0,95 · D 0,87 · H 0,93 |
| Spearman H, Lauf 1 gegen Lauf 2 | 0,939 |
| Verzerrung H (zweiter minus erster Lauf) | −1,2 |
| alle Werte Vielfache von 5 | 49 von 49 Karten |

Bewertung gegen die vorab festgelegte Schwelle: Der Anteil (6,1 % ≤ 10 %) besteht; die mittlere Differenz (5,10) liegt **knapp über** der Schwelle 5, das Intervall enthält die 5. Streng nach Regel ist 5a damit **knapp verfehlt** (Punktschätzung), mit Tendenz zur Erfüllung; die Rangordnung bleibt stabil (Spearman 0,94, ICC H 0,93). Die größten Abweichungen sind Karten mit mehreren plausiblen Lesarten (z. B. Eclipsed Kithkin 70 → 40, Confiscate 45 → 30).
Folgerung: Die Einzel-Bewertung je Karte hat einen Stichprobenfehler von rund 5 H-Punkten; das stützt die `unscharf`-Kennzeichnung und die Notwendigkeit eines zweiten Laufs für Grenzfälle. Die Drift-Karten wurden **nicht** in den Datensatz des Studios übernommen (dort steht weiter ein Lauf je Karte).

## 11. Unabhängige Prüfung nach dem Vollauf (2026-11-18, Rohdaten und Berichte in `audit/`)

Zweck: Die Ratings eines Modell-Raters nicht allein an sich selbst messen. Eingesetzt wurde eine zweite Modellfamilie in der hohen bzw. mittleren Stufe (Namen sind nicht im Repo festgehalten). Alle Prüfungen sind **blind gegenüber Nutzung/Beliebtheit** (Eingaben ohne Nutzungsdaten).

| Prüfung | Ergebnis (n/N) |
|---|---|
| **Unabhängiger dritter Rater** (andere Modellfamilie), 70 geschichtete Karten (Zuordnung je Karte in `audit/independent_rater_sample.json`: 18 Spitze, 15 Boden, 15 Grenzbereich H 40–55, 9 Länder, 13 übrige), Chargen zu 7, Vielfache von 5 | Spearman H 0,92 · ICC(2,1) H 0,91 · E 0,87 · F 0,94 · T 0,82 · R 0,92 · K 0,92 · D 0,91; mittlere |ΔH| 7,9; Verzerrung (unabhängiger Rater minus Lauf F1) −3,7; **13 von 70 = 18,6 % mit |ΔH| ≥ 15** (größte 25). Gegen Sampling-Konsistenz desselben Modells (ICC 0,93) liegt die Modellfamilien-Übereinstimmung nur wenig darunter. Die Stichprobe ist an den Rändern überrepräsentiert. |
| **Rating-Audit** (230 Karten: 100 Spitze, 60 Boden, 70 Grenzbereich) | **29 von 230 = 12,6 % zweifelhaft** (25 „H zu hoch“, 2 „zu niedrig“, 2 Begründung faktisch falsch); Spitze 20 von 100, Grenzbereich 9 von 70, Boden 0 von 60; plus 6 Karten aus der Klassenprüfung (`audit_A_flagged.jsonl`, 35 Zeilen). Systematische Verzerrungen: (1) Körper/Finisher ohne Chulane-Funktion zu hoch (14 der 25), (2) Einmal-Bounce/-Blink (n=10) wie wiederholbare Motoren bewertet (Textgleiche Karten 65 gegen 45), (3) „zweite gezogene Karte“-Zähler (n=6) etwa 10–15 zu hoch, (4) gestauchte Spitze (kein Wert ≥ 95). Keine Befunde bei Nutzländern, Sweepern, Lebensgewinn, Ramp-Artefakten. Einzelwert-Unsicherheit etwa ±7–8 (1σ); der Bereich H 55–65 (80 Karten) liegt unterhalb der Auflösung. |
| **Regelclaims** (Zufallsstichprobe, Seed 2026) | **100 von 100 richtig** (Wilson 96,3–100 %); ohne 22 reine Typzeilen-Claims 78 von 78; gezielt weitere ~280 riskante Claims gesichtet (nicht zufällig, nicht im Intervall): 1 Sachfehler (Evoke-Opfer-Fenster), 1 Unschärfe. |
| **Design-Review Gesamtrating** (Gutachten, `GUTACHTEN_C_gesamtrating.md`) | Doppelzählung: H zu 90 % aus den Teilkriterien erklärbar (R² 0,905, n=922); in Stufe D trägt die lineare Nutzungsachse ≤ 1,5 Punkte (bei rund 620 von 922 Karten mit Index ≤ 5; rekonstruiert aus 36 Stützpunkten, Schätzung) → Umsetzung overall-v2 (Log-Achse, Bracket-3-Sperre, Gruppenrang für Länder, Rausch-Hinweis). Hold-out Bracket 5 (n=736): Gesamtrating 0,471 gegen Index 0,636 — das vorab festgelegte Annahmekriterium (Hold-out darf nicht schlechter werden) ist **verfehlt**; laut Gutachten ist das weder ein Beleg dagegen noch dafür (das Ziel ist selbst ein Nutzungsmaß, in Stufe D sind 427 von 431 Zielwerte 0), belegt ist nur: als Nutzungs-Prädiktor ist das Gesamtrating schlechter, sein Mehrwert ist ungemessen. |
| **Testlauf Guide v2.2** (Ergänzungen aus dem Audit, `GUIDE_v2_2_delta_DRAFT.md`; 70 Karten: 35 Audit-markierte + 35 Kontrollen, ein Lauf, ohne Namen der markierten Karten im Guide) | Markierte Karten: **20 von 35 jetzt innerhalb der Prüfer-Spanne (vorher 2 von 35)**, 27 von 35 näher dran, mittlere ΔH −14,0. Kontrollen (35 Karten, Zielgruppe der Regeln): mittlere ΔH −5,0, |ΔH| 7,9, **6 von 35 = 17 % mit |ΔH| ≥ 15** (natürliche Drift 6,1 %); Spearman H v2.1 gegen v2.2 über alle 70: 0,65. Teilweise Überkorrektur (z. B. Karten mit echter Funktion von 60–70 auf 25–30). |

Blindheits-Scan der 140 neuen Rater-Ausgaben (Stichwortliste wie §9): 4 Treffer (unabhängiger Rater und Testlauf v2.2), davon 1 echte Beliebtheitsaussage, 1 Verneinung („not a staple“-Form) und 2 harmlose Wortverwendungen („budget choice“, „meta-dependent“); Eingaben waren nutzungsfrei.

Folgerung und Status: Die Prüfung stützt die **Rangordnung** der großen Klassen und die Regelaussagen, zeigt aber systematische Überbewertungen bei Körpern ohne Funktion, Einmal-Bounce und „zweite Karte“-Zählern. Der Guide v2.2 verbessert diese Fälle deutlich, überkorrigiert aber teils; **er ist nicht auf den Vollauf angewendet**. Die Ratings im Studio-Datensatz bleiben Guide v2.1 (ein Lauf je Karte). Ob und wie neu bewertet wird (Vorschlag: v2.2 mit abgeschwächten Körper-Deckeln auf einer Teilmenge, dann erneute unabhängige Prüfung), entscheidet der Owner.

