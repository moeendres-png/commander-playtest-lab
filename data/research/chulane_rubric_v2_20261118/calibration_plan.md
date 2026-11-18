# Kartenverständnis-Raster v2: Kalibrierungsplan für den Pilot (calibration_plan)

Entwurf, **vorab festgelegt**: Schwellen und Auswertung stehen in dieser Datei, bevor ein Rater läuft. Was nach dem Blick auf
Ergebnisse geändert wird, ist im Bericht als "post hoc" zu kennzeichnen und zu begründen. Studio-Regeln: jede Zahl mit n/N,
unbekannt ungleich 0, keine Simulation, keine Preise, Markierungen ohne Einfluss, Rater blind für Nutzungsdaten.
Nichts hier bewertet schon Karten; der Pilot entscheidet, ob Raster, Modell und Raterzahl für die 922 Karten taugen.

## 1. Frage und Versuchsaufbau

Frage: Reicht das Raster v2 (Guide, Anker, Fakten, Muster), und welche Rater-Konfiguration (Modellstufe, Zahl der Rater) ist die
billigste, die vorab festgelegte Verlässlichkeit erreicht?

- **Stichprobe:** `pilot_sample.json`, 63 Karten (10 v1-Anker, 20 Referenzdeck, 15 Stufe D mit Nutzung, 15 ohne Nutzung, 3 Abdeckungskarten;
  Auswahlregeln und Abweichungen im Abschnitt 6).
- **Rater:** vier Rater-Läufe: **H1, H2** (Haiku-Stufe) und **S1, S2** (Sonnet-Stufe). Die Modellwahl liegt beim Owner (Frage im Bericht); es
  gibt keinen automatischen Wechsel zwischen Modellen. Im Laufprotokoll stehen je Aufruf Modell-ID und Version, Temperatur, Zeitstempel und der
  Hash des Systemteils, damit ein Modellwechsel während des Laufs sichtbar bleibt.
- **Was "Rater" hier bedeutet (ehrlich):** Jeder Aufruf ist **zustandslos, eine Karte, ohne Nachbarkarten** (keine Chargen, kein Gespräch). Zwei Läufe
  desselben Modells unterscheiden sich daher **nur durch das Sampling bei Temperatur 0,7** (nicht 0, sonst identische Duplikate). Der ICC innerhalb eines
  Modells misst also die **Konsistenz des Samplings** und ist eine **obere Schranke** für die Verlässlichkeit unabhängiger Rater. Spearman-Brown auf diesen
  ICC sagt, **wie viele Stichproben desselben Modells** man mitteln sollte, nicht wie viele unabhängige Rater. Gegen gemeinsame Fehler eines Modells
  schützen nur die Vergleiche Haiku gegen Sonnet (2a bis 2c), die Anker (3) und v1 (4). Die Läufe laufen in je eigener zufälliger Reihenfolge nur als
  Zeitplan (damit ein Modellwechsel mitten im Lauf nicht ein Stratum trifft), nicht als Kontext.
- **Drift:** je Rater werden 8 feste Karten (2 je Stratum A, B, C, D, Seed 1118, in `pilot_sample.json` Feld `retest_cards`, vor dem Lauf festgelegt)
  **nach allen 63 Karten ein zweites Mal** bewertet (Test-Retest, zählt nicht doppelt in Mittelwerten, nur die erste Bewertung zählt). Echter Drift
  (Modell- oder Systemhash-Wechsel, Zeitstempel) wird aus dem Protokoll geprüft.
- **Aufrufe:** 4 Rater mal (63 plus 8) = **284 Aufrufe**.
- **Blindheit:** Prompt enthält keine Nutzungs-, Beliebtheits-, Preis- oder v1-Daten (Leak-Guard in der Extraktion, Prüfung in
  `render_prompt.py`); der Pilot prüft zusätzlich die Ausgaben auf Anzeichen (Abschnitt 3, Punkt 8).

## 2. Kennzahlen

Alle Kennzahlen mit n; Konfidenzintervalle per Bootstrap über Karten (2.000 Ziehungen, Seed 1118). Bei 63 Karten sind die Intervalle
breit (bei ICC 0,8 etwa plus/minus 0,07, bei Spearman 0,7 auf 53 Karten etwa plus/minus 0,10), das ist der Grund für die zweite
Bedingung "untere Grenze" in Abschnitt 4.

1. **Übereinstimmung zwischen Ratern:** ICC(2,1) (absolute Übereinstimmung, ein Rater) und ICC(2,k) (Mittel von k Ratern) **je Kriterium
   E, F, T, R, K, D, H**, getrennt für H1 mit H2, S1 mit S2 und alle vier gemeinsam (Rater als zufälliger Faktor), plus Krippendorffs
   Alpha (Intervall) als zweite Zahl. Ankerkarten gehen mit ein (n = 63) und werden zusätzlich einzeln ohne Anker (n = 53) gerechnet.
2. **Modell-Effekt Haiku gegen Sonnet:** Spearman zwischen Mittel(H1, H2) und Mittel(S1, S2) auf H und je Kriterium; mittlere absolute
   Abweichung (MAD) und mittlere Differenz (Verzerrung) in Punkten; ICC(2,1) je Modell.
3. **Ankerkonsistenz (leave-one-anchor-out):** für die 10 v1-Anker im Pool (die beim Bewerten nicht in der eigenen Tabelle stehen) der
   mittlere absolute Fehler (MAE) und der größte Fehler gegen den festen Wert (E, F, T, R mal 25; H nach der Studio-Formel) je Rater;
   Spearman der 10 Anker-H gegen die festen H. K und D haben **keinen** v1-Anker: **nicht bestimmbar**, nicht 0.
4. **Abweichung gegen v1:** Spearman und MAD zwischen v2-H (auf 0 bis 100 umgerechnete v1-H_mean) auf den 53 Nicht-Ankerkarten; ebenso E, F, T, R
   gegen v1 mal 25. Zusatz (kein Bestehens-Kriterium): Liste aller Karten mit Abweichung von 25 Punkten oder mehr mit den Begründungen beider Seiten,
   zur Durchsicht durch den Owner (erwartet: Chulane-Motorkarten höher, weil v2 Implikationen wie den Bounce-Wiederholungseffekt verlangt).
5. **Drift:** je Rater die Test-Retest-Paare (8): mittlere absolute Differenz je Kriterium, Anteil der Paare mit H-Differenz von 15 oder mehr;
   Wechsel von Modell-ID oder Systemhash im Protokoll (muss 0 sein). Einen Positionseffekt gibt es bei zustandslosen Einzelaufrufen nicht.
6. **Rater-Streuung als Unsicherheit:** je Karte Standardabweichung der vier Rater (und je Modell der zwei); veröffentlicht als `H_sd`;
   Markierung "unsicher" ab Streuung 20 Punkten (v1: Streuung 2 auf 1 bis 10, das sind 22 Punkte auf 0 bis 100).
7. **Pflichtfelder und Schema:** Anteil gültiger JSON-Antworten nach einer Wiederholung; alle Werte Vielfache von 5.
8. **Ehrlichkeits-Audit:** (a) `rule_claims`: automatisch, ob `quote` ein wörtlicher Teilstring des Kartenblocks ist; (b) von Hand
   **40 zufällige Behauptungen** (geschichtet über `interaction`, höchstens 3 je Karte, aus allen vier Ratern) gegen Kartentext und gezeigte
   Rulings; wo der Text nicht entscheidet, eine XMage-Zeile (lab-ops, nur für die höchstens 10 regelhaltigsten Fälle); (c) Anteil
   `basis = inferred_from_text`; (d) `pattern_check`: Anteil "wrong" je Regel gegen meine Handpräzision aus `patterns_spec.md`; (e) Blindheits-Scan
   der Ausgaben nach "popular", "staple", "EDHREC", "commonly played", "price", "budget", "cEDH staple" und Ähnlichem (Stichwortliste vor dem
   Lauf fest, Treffer von Hand durchgesehen).

## 3. Schwellenwerte, vorab (gelten für Punktschätzung **und** untere 95-%-Grenze)

Ein Kriterium oder eine Konfiguration "besteht" nur, wenn die Punktschätzung die Schwelle **und** die untere Grenze die in Klammern stehende
Schwelle erreicht. Bezugswerte aus v1 (912 Karten, 3 Rater): ICC(2,1) H 0,84, F 0,71, E 0,77, T 0,76, R 0,76, W 0,74.

| Nr | Kennzahl | Bestehen (Punkt, untere Grenze) |
|---|---|---|
| 1a | ICC(2,1) **H**, je Modell | 0,75 (0,65) |
| 1b | ICC(2,1) **E, T, R, D**, je Modell | 0,70 (0,60) |
| 1c | ICC(2,1) **F, K**, je Modell | 0,65 (0,55) (urteilslastiger; v1-F lag bei 0,71) |
| 1d | ICC(2,k) von **H** für das gewählte k: für k = 2 direkt aus den zwei Läufen des Modells, für k = 3 nur als Spearman-Brown-Projektion aus 1a (gekennzeichnet, nicht gemessen) | 0,90 (0,85) |
| 2a | Spearman Haiku-Mittel gegen Sonnet-Mittel, **H** | 0,90 (0,85) |
| 2b | MAD **H** zwischen den Modell-Mitteln / Verzerrung | höchstens 8 Punkte / Betrag höchstens 5 Punkte |
| 2c | ICC(2,1) H Haiku minus Sonnet | nicht schlechter als minus 0,08 |
| 3a | Anker-MAE **H** (Mittel der Rater) / größter Einzelfehler | höchstens 10 / höchstens 25 Punkte |
| 3b | Anker-MAE **E, F, T, R** (Mittel der Rater) | höchstens 12,5 Punkte |
| 3c | Spearman Anker-H gegen feste H | 0,90 (0,80) |
| 4 | Spearman v2-H gegen v1-H auf 53 Nicht-Ankern | mindestens 0,70 (0,60); **über 0,95 gilt als Verdacht**, dass v2 nur v1 wiederholt, und wird gesondert durchgesehen |
| 5a | Drift: mittlere absolute H-Differenz im Test-Retest / Anteil Paare mit H-Differenz 15 oder mehr | höchstens 5 / höchstens 10 % |
| 5b | Modell-ID oder Systemhash wechselt im Lauf | 0 Wechsel |
| 6 | Anteil der Pilotkarten mit Streuung 20 oder mehr (H) | höchstens 10 % |
| 7 | gültige JSON-Antworten / Vielfache von 5 | mindestens 99 % / 100 % |
| 8a | `quote` wörtlich im Kartenblock | mindestens 98 % |
| 8b | von Hand geprüfte Behauptungen richtig | mindestens 90 % (untere Grenze 80 %) |
| 8c | Blindheits-Scan | höchstens 2 % der Ausgaben mit Treffer; jeder Treffer einzeln beurteilt |

Wer 1b/1c nicht besteht, wird nicht stillschweigend gestrichen: das Kriterium bleibt im Datensatz, im Studio erscheinen später nur die
bestandenen Kriterien einzeln, alle Kriterien in der Karte mit der Angabe "Streuung zu groß".

## 4. Entscheidungsregel "Modell und Raterzahl reichen"

Konfigurationen in dieser Kostenreihenfolge: 1 Haiku, 2 Haiku, 3 Haiku, 1 Sonnet, 2 Sonnet, 3 Sonnet (kein gemischtes Mittel als Standard).
Gewählt wird die **erste**, die alle diese Bedingungen erfüllt: 1a, 1b, 1c für das Modell; 1d für die Raterzahl; 3a, 3b, 3c, 5a, 5b,
6, 7, 8a, 8b, 8c. **Haiku darf gewählt werden nur, wenn zusätzlich 2a, 2b, 2c bestehen** (Haiku und Sonnet liefern dasselbe Bild);
sonst Sonnet. ICC für k Läufe: Spearman-Brown aus dem gemessenen ICC(2,1) des Modells; k = 2 wird direkt nachgeprüft, k = 3 bleibt eine Projektion.
"k Läufe" heißt k Stichproben desselben Modells zu mitteln, nicht k unabhängige Rater. Erreicht keine Konfiguration bis 3 Rater die Schwellen, ist die Antwort **nicht mehr Rater, sondern Raster überarbeiten**
(Guide, Anker, Fakten), danach neuer Pilot; mehr als 3 Rater je Karte sind für 922 Karten nicht vorgesehen.

Beschränkung: Alle Rater stammen aus einer Modellfamilie; ein geteilter Fehler (gemeinsamer Bias) erscheint in keinem ICC. Die Prüfungen gegen
feste Anker (3), gegen v1 (4) und gegen Nutzung (Abschnitt 5, nach dem Einfrieren) sind die einzigen externen Gegenstücke und beweisen keine Wahrheit.

## 5. Nach dem Pilot: Validität gegen Nutzung (erst nach Einfrieren der Bewertungen)

Erst wenn alle 922 Bewertungen fertig und eingefroren sind, wird `usage_holdout.jsonl` geöffnet (Zähler n von 10.128, nicht gemischt):
Spearman v2-H gegen Deckanteil (alle 922, nur Stufe D, nur 186 Null-Karten: dort undefiniert, weil alle 0); Referenzdeck-AUC (79 gegen 843)
von v2-H und v1-H (v1-Bezug 0,845): **Nichtunterlegenheit** v2-H mindestens v1-H minus 0,03 (vorab). Kein Gewicht im Nutzungs-Index (Owner-Entscheid E1.a);
die Auswertung ist nur Beschreibung.

## 6. Pilotstichprobe, Abweichungen vom Auftrag

`pilot_sample.json` (Seed 1118, Quoten je Eimer: Land, Mana, Kreatur mit eigenem ETB, andere Kreatur, Nichtkreatur-Zauber):
- A: **10** v1-Anker im Pool (Command Tower, Counterspell, Cultivate, Evolving Wilds, Farseek, Llanowar Elves, Selesnya Guildgate, Simic Growth Chamber,
  Sol Ring, Swords to Plowshares); feste v1-H sind Referenz, aber **nicht unabhängig**, darum nur im Test 3, nicht in Test 4.
- B: **20** Karten des Referenzdecks `chulane-current@41f393530bb16ee9` (kein Anker; 3 Länder, 4 Mana, 5 Kreaturen mit eigenem ETB, 3 andere
  Kreaturen, 5 Nichtkreatur-Zauber). Referenz-v1-H: `summary.csv` (H_mean, H_sd), im Feld `v1_H_mean` der Datei.
- C: **15** Karten der Stufe D mit Nutzung größer 0, nicht im Referenzdeck, davon **3 Länder mit der geringsten Nutzung unter den Ländern der Stufe D** (Dread Statuary, Jund Panorama, Grixis Panorama).
- D: **15** Karten ohne Nutzung: **1 Land** (Rocky Tar Pit; das ist das einzige Land ohne Nutzung im Pool),
  5 mit positivem Chulane-Muster, 2 Kreaturen ohne Text (Vanilla), 7 ohne Muster.
- E: **3** Abdeckungskarten: Prudent Fateseer (zweite mehrseitige Karte), Farewell und Narset (Game Changer; Farewell ist eine Referenzdeckkarte und kam so
  nicht über B).

**Abweichungen vom Auftrag:** (1) Statt "4 Länder bei 0 Quelldecks" 1 Land bei 0 (mehr gibt es nicht) und 3 bei 1 bis 2 im Stratum C. (2) 63 statt 60 Karten
wegen E. (3) Stufe und Nutzungszahl der Pilotkarten stehen nur in der Datei zur Kalibrierung, nie im Prompt. (4) Ankerkarten kommen im Anker-Block nur bei fremden
Karten vor (leave-one-anchor-out); kein Anker (außer den 10 v1-Ankern) ist Pilotkarte; alles im Code geprüft.

## 7. Kostenschätzung (Tokens, Schätzung Zeichen geteilt durch 3,5)

Quelle `data/prompt_token_stats.json`: Systemteil (Guide plus Anker plus Ausgaberegeln, statisch, cachebar) **6.925** Tokens; Nutzerteil je Karte Median 427,
Mittel 441, p90 642, p99 774, Maximum 894 (über 922 Karten); Ausgabe 420 Tokens je Karte (Annahme, Beispielausgabe etwa 330). Je Aufruf also etwa
7.366 Tokens Eingabe, davon 94 % statischer Präfix.

| Lauf | Aufrufe | Eingabe gesamt | davon statisch (cachebar) | davon je Karte | Ausgabe |
|---|---|---|---|---|---|
| Pilot (4 Rater, 63 plus 8 Wiederholungen) | 284 | 2,09 Mio | 1,97 Mio | 0,13 Mio | 0,12 Mio |
| 922 Karten, 1 Rater, 5 % Wiederholungen | 968 | 7,13 Mio | 6,70 Mio | 0,43 Mio | 0,41 Mio |
| 922 Karten, 2 Rater | 1.936 | 14,26 Mio | 13,41 Mio | 0,85 Mio | 0,81 Mio |
| 922 Karten, 3 Rater | 2.904 | 21,39 Mio | 20,11 Mio | 1,28 Mio | 1,22 Mio |

Der statische Präfix ist bei Prompt-Caching je Rater-Lauf nur einmal pro Cache-Fenster zu schreiben und sonst billig zu lesen; wirksam bleibt dann
nur der Teil je Karte. Geldbeträge sind hier bewusst nicht angegeben (Preise werden nicht aus dem Gedächtnis genannt); sie sind mit der aktuellen
Preisliste und dem Token-Zähler der API im ersten Pilotaufruf zu rechnen. Ein Haiku-Lauf kostet weniger als ein Sonnet-Lauf, ob er genügt, entscheidet Abschnitt 4.

## 8. Risiken

Gleiche Modellfamilie (geteilter Bias); 63 Karten (breite Intervalle, deshalb zwei Bedingungen); Anker teils von mir als Vorschlag gesetzt (Art `v2_proposal`, der Owner bestätigt oder ersetzt);
Modell-Vorwissen über Beliebtheit lässt sich nicht ausschließen (v1-Grenze), Blindheits-Scan ist nur ein Indiz; Pilot sagt nichts über Kartentypen aus, die er nicht enthält;
das Referenzdeck ist teils nach Beliebtheit gebaut (zirkulär für den Nutzungsvergleich in Abschnitt 5); der Owner ist bisher der einzige Mensch-Rater (optional: Owner bewertet 15 Pilotkarten selbst als Referenz, Frage im Bericht).
