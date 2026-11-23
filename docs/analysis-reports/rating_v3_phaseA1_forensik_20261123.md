# A1 Forensik: Kartenverständnis H, F1 gegen R2 (Chulane, Raster v2/v2.1)

> Phase-Bericht zum Vorab-Plan [Bewertung v3](rating_v3_plan_20261123.md) (Refs #1404). Ins Repo übernommen am 2026-11-23 aus dem Scratchpad; inhaltlich unverändert bis auf Pfade, die Bezeichnung der Läufe und die Angaben zur Modellfamilie (im Repo: unbelegt).

Stand 2026-11-22. Grundlage: `main` @ `f4d49ad6` (Klon im Scratchpad). Nur gelesen und gerechnet. Es gab keine neuen Bewertungsläufe, nichts am Produkt wurde geändert, nichts committet. Modellnamen stehen nicht in dieser Datei. Die Skripte liegen in `data/research/chulane_rubric_v3_20261123/phaseA_scripts/A1/`, die Ergebnisse in einem Ausgabeordner außerhalb des Repos (`$A1_OUT`). Alle Zahlen erzeugt `bash data/research/chulane_rubric_v3_20261123/phaseA_scripts/A1/run_all.sh`. Zwei Läufe ergaben byte-gleiche Ausgaben (SHA-256 in §7).

Bezeichnungen: **Lauf 1 (F1)** ist der Vollauf vom 2026-11-18 (922 Karten, 7 Karten je Aufruf). **Lauf 2 (R2)** ist die zweite Bewertung: Welle 1 (300 Karten, 3 Instanzen zu 100) und Welle 2 (622 Karten, 7 Instanzen zu 88 bis 89). Die Retest-Charge 8 ist getrennt geführt. Es gilt d = H_R2 − H_F1. N = 922 Paare.

## 0. Kurzfassung (10 Zeilen)

1. **Eingabe-Parität: nur teilweise.** Die Kartenblöcke sind byte-gleich (922/922, Retest 50/50). Guide-Quelle und Ausgabeschema sind identisch. Verschieden sind fünf Dinge: die Anker-Ausblendung, die Kartenzahl je Aufruf (7 gegen 88 bis 100), Rahmen und Anweisung, die Arbeitsweise (ein Prompt gegen Agent mit Werkzeugen) und das Datum. Das Modell von F1 ist im Repo UNBEKANNT, ebenso Temperatur und Aufwand beider Läufe. Ob die Modelle oder Familien der beiden Läufe verschieden sind, ist unbelegt.
2. **Anker-Regel verschieden (Designunterschied, kein Fehler von F1):** F1 blendete, wie `prompt_template.md` §2 es vorsieht, nur die 10 „v1 fixed“-Anker aus; der R2-Plan hat die Regel auf alle Ankerkarten erweitert. 36 der 46 Ankerkarten bewertete F1 mit ihrer eigenen Ankerzeile im Prompt und übernahm den Wert dort in **64 von 76** Zeilen exakt (MAE 1,1). Wo die Zeile fehlte, waren es 16 von 46 (MAE 6,9). R2 sah nie die eigene Zeile (0/46). Die „Anker-Spells mit Bias −0,83“ messen also R2 gegen die Ankertabelle, nicht gegen ein Urteil von F1.
3. **Das Niveau sitzt im H-Schritt, die Streuung in den Kriterien.** Die Kriterien verschieben sich gegenläufig: T −4,7 und F −2,8 stehen gegen R +3,1, K +2,9 und D +4,4. Sie sagen ΔH ≈ −0,6 bis +0,1 voraus. Beobachtet ist ΔH −4,73. Bei gleichen Kriterien setzt R2 H um **−4,67** tiefer (Lauf-Dummy, R² 0,91). Die Streuung je Karte kommt aber aus Uneinigkeit in E, F und R: 77 bis 79 % der Varianz von d sind kriterienbedingt (r 0,85, Rest-SD 5,8 bei SD 11,0). Ein aus den Kriterien berechnetes H hätte noch etwa 108 bis 161 statt 266 Karten mit |d| ≥ 15.
4. **Wo die Abweichung liegt:** bei Kreaturen (−7,5, n=478; Nicht-Kreatur-Spells −2,5, n=379), bei Mana-Wert 6+ (−10), bei Rollen ohne Chulane-Funktion (Tokens −13,8, Counters −11,9, Tapper −10,6, Evasion −8,9) und im Mittelband H 28–49 (mittlere |d| 11,7). Klein ist sie bei Ländern (+2,9, ICC 0,93), Mana-Dorks und -Rocks und in den Rändern 0–4 und 72–94. Gegenläufig sind Counterspells mit +6,5.
5. **Anker gegen Rest (−0,83 gegen −5,11)** ist größtenteils ein Band-Effekt. Die Anker-Spells liegen bei F1-H 52,5 im Mittel, die Rest-Spells bei 24,0. Nicht-Anker im Band 50–71 haben d +0,4. Dazu kommt das Anker-Leck aus Punkt 2.
6. **Strukturfehler D↔H:** H liegt in jedem Lauf 10 bis 17 Punkte unter dem Mittel von E bis D. Das Gewicht von D in H ist ≈ 0 (−0,04 bis +0,03, alle Läufe). D ist laut Guide reine Kostenfreiheit, eine Karte ohne Wirkung bekommt also hohes D. Die 63 „Formatlücken“ in Welle 2 (F1 auf denselben Karten: 5) kommen aus R2s tieferem H-Schritt plus höherem D, nicht aus Regelbrüchen.
7. **Externe Validität:** R2 korreliert stärker mit der Nutzung als F1 (Quelldecks ρ 0,673 [0,633; 0,710] gegen 0,504 [0,452; 0,551]; gepaart +0,169 [0,137; 0,203]). R2 liegt auch über v1 (0,62). Kontrolliert man die globale Beliebtheit, bleibt +0,10 [0,07; 0,14]. Das entscheidet **nicht**, welcher Lauf „näher“ an der Qualität ist: Nutzung ist nicht Qualität, ein Beliebtheitsleck bei R2 ist nicht ausschließbar (Werkzeuge mit Web-Zugang verfügbar), und ein geteiltes Deckmodell erklärt dasselbe Muster.
8. **Die 30 größten Abweichungen** sind fast nie Regelfehler. Ersteinschätzung: Deckannahmen über unsichtbare Deckinhalte (Artefakte, Lebensgewinn, Elfen, Landfall), Mehrdeutigkeit des Guides bei „Körper ohne Funktion“ und bei Nicht-Kreatur-Interaktion (R und F für Antworten) sowie H-gegen-Kriterien. 11 der 30 sind Audit-A-markiert. Der Audit-A-Prüfer ist vermutlich das R2-Modell, die Übereinstimmung ist daher Selbstkonsistenz.
9. **Folge für ein besseres Design (1/2):** Die Eingabe muss vollständig gleich sein: dieselbe Ankerregel, dieselbe Kartenzahl je Aufruf (klein und zustandslos, wie `prompt_template.md` §6 es verlangt; beide Läufe weichen davon ab), ein protokolliertes Modell und dieselben Parameter. Ein an die Kriterien gebundenes H beseitigt nur den Niveau-Versatz (etwa −4,7). Gegen die **Streuung** helfen vor allem ein festes Deckprofil und Guide-Beispiele für die Streitklassen (Punkt 10, §6).
10. **Folge (2/2):** D sollte umdefiniert werden („Kosten, gegeben dass die Karte etwas tut“) oder aus dem Mittel fallen. Der Guide sollte Deckannahmen festlegen (Zahl der Artefakte, Lebensgewinn, Tribal, Landfall-Payoffs im Referenzdeck) und R und F für Antworten an Beispielen klären. Die Blindheit muss technisch erzwungen werden (keine Web-Werkzeuge), nicht per Selbstauskunft.

## 1. Eingabe-Parität (Frage 1)

Befehl: `PYTHONPATH=$REPO/src python3 A1/a1_parity.py --f1-batches <scratchpad>/pilot_run/full` → `$A1_OUT/parity.json`. Das Skript baut die F1-Chargenprompts mit dem Repo-Generator `scripts/make_batches.py --run full` neu.

Gegenproben: Der Neubau ist byte-gleich mit den Original-Laufdateien von F1 im Scratchpad (`pilot_run/full/F1_b*.md`, Dateizeit 2026-11-18): **132 von 132**. Die Chargenzuordnung in `fullrun_ratings.jsonl` passt zum Manifest (132/132). Die R2-Guides sind gleich dem Repo-Generator mit der jeweiligen Anker-Ausblendung (8/8 in Welle 2, 1/1 in Welle 1), und die SHA-256 stimmen mit dem Manifest überein.

| Eingabe-Aspekt | F1 | R2 | Urteil | Beleg |
|---|---|---|---|---|
| Kartenblock (Fakten, Rollen, Castability, Peers, Rulings, Combo-Hinweis, Pattern-Hits) | `render_prompt.card_block` aus `facts.jsonl`/`patterns.jsonl` | `card_block` in `rr_input_*`/`rr2_input_*` | **gleich**: 922/922 byte-gleich, Retest 50/50 | `card_block_equal_*` |
| Fakten-/Musterquelle | `facts.jsonl` SHA `47557ee7…` | dieselbe (Manifest `source_sha256`) | **gleich** | `rr2_manifest.json` meta |
| Zeile „Rate this card. Answer with one JSON object…“ | vor jeder Karte (7× je Charge) | fehlt (0/922) | **verschieden** (Rahmen) | parity |
| Guide-Text (Regeln, Kriterien, Skalen, Bänder) | `GUIDE_v2.md` (nur 1 Commit, `fbb45695`) | derselbe Text, gerendert | **gleich** | `git log`, Diff 0 Zeilen ohne Ankerteil |
| Ankertabellen | ausgeblendet nur die 10 „v1 fixed“-Karten der eigenen Charge; **36 Ankerkarten mit eigener Zeile sichtbar** | ausgeblendet alle Ankerkarten der Instanz (Welle 2: je 4 bis 6 Namen, 21 bis 24 Zeilen weniger; Welle 1: 4 Namen); **0 Karten mit eigener Zeile** | **verschieden** | `f1_rated_with_own_anchor_rows_visible` 36, `r2_…` 0 |
| Kommandantentext (Oracle) | im Guide (Systemteil), nicht im Kartenblock | im Guide, nicht im Kartenblock (0/922) | **gleich** | parity |
| Ausgaberegeln (`SCHEMA_HINT`) | am Ende des Systemteils | am Ende von `rr2_guide_N.md` | **gleich** | Generator-Gleichheit |
| Ausgabeschema | `output_schema.json` | `rr2_output_schema.json` | **gleich** (Inhalt identisch, `pattern_check.why` in beiden erlaubt) | `schema_equal: true` |
| Zusatzanweisung | Chargenkopf (`HEAD` in `make_batches.py`): jede Karte unabhängig, ein JSON-Array | `rr2_rater_instructions.md`: Blindheitsregeln, in 10er-Blöcken lesen, alle 10 Karten anhängen, Selbstprüfung, Schlussantwort, Formatbeispiel | **verschieden** | Dateien |
| Karten je Aufruf/Instanz | 7 (letzte Charge 5), alle Karten sichtbar | 100 (W1) bzw. 88 bis 89 (W2) und 50 (Retest), sequenziell, Kontext wächst | **verschieden** | Manifeste |
| Vorgabe `prompt_template.md` §6 („eine Karte je Aufruf, zustandslos“) | verletzt (7er-Chargen, PILOT_REPORT §1 Abweichung 1) | verletzt (88 bis 100 je Instanz) | **beide abweichend** | |
| Arbeitsweise | Prompt-Datei, Antwort als Datei (Subagent) | Agent mit allen Werkzeugen (Bash, Read, Write, Web); Blindheit nur Selbstauskunft | **verschieden** (F1-Werkzeuge: unbekannt) | `run_log_redacted.md`, Bericht §7 |
| Modell / Familie | Repo: **UNBEKANNT** (README, PILOT_REPORT: „große Stufe“, Name nur in der Owner-Session); Familie unbelegt | Welle 2: im Scratchpad-Laufprotokoll belegt. Welle 1: unbekannt. Gleich W1 = W2: unbekannt | **unbelegt** (Familie von F1 unbelegt) | |
| Temperatur, Aufwand | unbekannt | unbekannt („Voreinstellung, nicht gesetzt“) | **unbekannt** | Bericht §8 |
| Datum | 2026-11-18, F1-Ausgaben 11:00 bis 11:27Z | 2026-11-22 (W2 16:43 bis 16:52Z) | verschieden | Dateizeiten |

Hinweis: Die F1-Ankerregel entspricht `prompt_template.md` §2; erst der R2-Plan hat die Ausblendung auf alle Ankerkarten erweitert. Das ist ein Designunterschied zwischen den Läufen, kein Fehler von F1.

**Antwort:** F1 und R2 sahen **byte-gleiche Kartenblöcke**, aber **keine byte-gleiche Gesamteingabe**. Die wirksamen Unterschiede sind die Anker-Ausblendung (betrifft 36 bis 46 Karten direkt), Kontextlänge und Rahmen (alle Karten) sowie Modell und Arbeitsweise (alle Karten, Stärke unbekannt).

## 2. Zerlegung von d (Frage 2)

Befehl: `A1/a1_decomp.py` → `$A1_OUT/decomp.json`, `$A1_OUT/pairs.jsonl`. Die Zerlegung macht `a1_extra.py` → `$A1_OUT/extra.json`.

### 2.1 Je Teilkriterium (N = 922)

| Krit. | Mittel F1 | Mittel R2 | mittl. d | SD(d) | ICC(2,1) | Spearman | \|d\| ≥ 10 | \|d\| ≥ 20 |
|---|---|---|---|---|---|---|---|---|
| E | 43,3 | 43,0 | −0,25 | 11,2 | 0,816 | 0,811 | 407/922 | 104/922 |
| F | 44,7 | 42,0 | −2,77 | 8,9 | 0,886 | 0,882 | 360/922 | 56/922 |
| T | 24,0 | 19,3 | −4,70 | 9,8 | 0,812 | 0,829 | 419/922 | 110/922 |
| R | 47,9 | 51,0 | +3,06 | 10,1 | 0,828 | 0,829 | 401/922 | 76/922 |
| K | 21,1 | 24,0 | +2,89 | 9,9 | 0,866 | 0,823 | 350/922 | 92/922 |
| D | 64,8 | 69,2 | +4,39 | 8,1 | 0,858 | 0,879 | 336/922 | 61/922 |
| **H** | 30,7 | 26,0 | **−4,73** | 11,0 | 0,818 | 0,829 | 474/922 | 131/922 |

Für Spells allein (n=857) ist d_H −5,30, für Länder (n=65) +2,85, mit ICC H 0,811 gegen 0,925.

**Zerlegung der Niveau-Differenz** (Gewichte aus den OLS-Fits H ~ E+F+T+R+K+D):

| Gewichte aus | ΔH beobachtet | ΔH aus Kriterien | Rest = H-Schritt | SD Rest | r(ΔH, vorhergesagt) |
|---|---|---|---|---|---|
| F1 | −4,73 | +0,12 | −4,85 | 5,77 | 0,852 |
| R2 | −4,73 | −0,28 | −4,45 | 5,77 | 0,852 |
| beide gestapelt | −4,73 | −0,62 | −4,11 | 5,70 | 0,856 |
| Lauf-Dummy (gleiche Kriterien) | | | **−4,67** (R² 0,911) | | |

Getrennt nach Kartenart (gestapelt): Kreaturen −7,53 = Kriterien −2,65 plus H-Schritt −4,88 (n=478). Nicht-Kreatur-Spells −2,49 = +1,41 plus −3,90 (n=379). Länder +2,85 = +2,51 plus +0,34 (n=65).

### 2.2 Je H-Band

Gruppiert man nach dem Band nur eines Laufs, entstehen Artefakte durch Regression zur Mitte. Leitend ist darum das Band des **Mittels** beider Läufe. Die Bänder nach F1 und nach R2 stehen nur zum Vergleich daneben. ICC innerhalb eines Bands ist durch die Bereichseinschränkung ≈ 0 und hier weggelassen.

| Band | Mittel-Band: n, mittl. d, mittl. \|d\|, \|d\|≥15 | Band nach F1: n, mittl. d | Band nach R2: n, mittl. d |
|---|---|---|---|
| 0–4 | 46, −3,04, 3,5, 0 | 20, +3,00 | 66, −6,14 |
| 5–27 | 441, −6,07, 8,5, 110 | 422, −3,03 | 498, −8,35 |
| **28–49** | 299, −4,75, **11,7**, **125** | 312, −7,08 | 199, −1,98 |
| 50–71 | 108, −1,30, 8,2, 27 | 144, −5,94 | 131, +3,89 |
| 72–94 | 28, +0,54, 5,2, 4 | 24, −3,12 | 28, +3,21 |
| 95–100 | n = 0, Kennzahlen entfallen | 0 | 0 |

Befund: Die **Streuung** konzentriert sich im Mittelband 28–49 (125 der 266 Karten mit |d| ≥ 15). Die **Verschiebung** ist im Band 5–27 am größten. Die Ränder sind klein.

### 2.3 Je Kartenart, Rolle, Mana-Wert, Farbe, Schicht

| Gruppe | n | mittl. d | mittl. \|d\| | \|d\|≥15 | ICC H |
|---|---|---|---|---|---|
| Kreatur (Front) | 478 | −7,53 | 10,6 | 173 | 0,806 |
| Nicht-Kreatur (inkl. Länder) | 444 | −1,71 | 7,6 | 93 | 0,834 |
| Instant | 146 | −0,07 | 8,0 | 29 | 0,818 |
| Sorcery | 66 | −3,41 | 9,3 | 20 | 0,645 |
| Enchantment | 81 | −3,70 | 8,0 | 20 | 0,835 |
| Artifact | 82 | −4,45 | 6,9 | 15 | 0,892 |
| Planeswalker | 4 | −11,25 | 18,8 | 3 | (n klein) |
| Land | 65 | +2,85 | 4,9 | 6 | 0,925 |
| MV 1 / 2 / 3 / 4 / 5 / 6 / 7+ | 119/241/206/132/92/35/31 | −1,3/−4,4/−6,3/−5,9/−6,6/**−10,4/−9,7** | | | 0,87 → 0,66 |
| Rolle token_production | 44 | −13,75 | 14,7 | 23 | 0,683 |
| Rolle counters | 37 | −11,89 | 11,9 | 16 | 0,552 |
| Rolle tapper | 17 | −10,59 | 11,8 | 8 | 0,533 |
| Rolle evasion | 60 | −8,92 | 9,9 | 18 | 0,544 |
| Rolle combat_trick | 40 | −7,12 | 7,9 | 9 | 0,538 |
| Rolle card_advantage | 145 | −5,45 | 9,6 | 45 | 0,794 |
| Rolle removal | 117 | −1,58 | **10,9** | 40 | 0,687 |
| Rolle counterspell | 27 | **+6,48** | 9,8 | 6 | 0,530 |
| Rolle mana_dork / mana_rock / land_ramp | 20/21/67 | −1,5/−3,8/+0,9 | 4,5/6,7/6,7 | 2/3/14 | 0,94/0,89/0,86 |
| Farbe C / G / U / W | 143/237/237/213 | −3,3/−4,7/−5,3/−4,9 | 7,1/9,6/9,5/9,9 | 24/73/73/69 | |
| Farbe UG / WG / WU / WUG | 26/27/33/6 | −1,7/−6,1/−5,8/−13,3 | | 5/9/11/2 | |
| Schicht W1 markiert (Audit A) | 35 | **−13,43** | 20,6 | 28 | 0,283 |
| Schicht W1 Spitze / Rest / Länder | 100/115/50 | −5,45/−5,7/+2,3 | | 30/32/3 | |
| Schicht W2 Spitze / Rest / Anker-Spells / Anker-Länder | 32/548/30/12 | −0,78/−5,11/−0,83/+4,17 | | 10/153/8/2 | |

Die markierte Schicht ist keine unabhängige Bestätigung. Audit A markierte diese Karten mit der Richtung „H zu hoch“, und der Audit-A-Prüfer ist nach dem Welle-1-Plan §2a vermutlich dasselbe Modell wie R2.

### 2.4 Position in der Charge (Müdigkeit)

Die mittleren |d| je Zehnerblock steigen in Welle 2 leicht von 6,9 (seq 1–10) auf 9,5 bis 10,9 (seq 61–90), bei je n = 62 bis 70. In Welle 1 gibt es keinen Trend (6,8 bis 13,0, sprunghaft). Rangkorrelation je Charge (`order_check` in extra.json):

| Charge | ρ(seq, d) | ρ(seq, d \| F1-H bereinigt) | ρ(seq, F1-H) | ρ(seq, Kreatur) | mittl. \|d\| 1. / 2. Hälfte |
|---|---|---|---|---|---|
| W2:2 | +0,136 | +0,144 | +0,014 | −0,106 | 6,93 / 10,44 |
| W2:6 | **−0,348** | **−0,366** (zusätzlich um Kreaturanteil bereinigt: −0,340) | +0,134 | +0,210 | 8,52 / 11,89 |
| W2:5 | −0,135 | −0,132 | +0,023 | −0,103 | 8,07 / 10,22 |
| übrige (W1:1–3, W2:1, 3, 4, 7) | −0,13 bis +0,15 | ähnlich | −0,13 bis +0,24 | ≤ 0,13 | ohne Muster |

Die Reihenfolge ist zu F1-H weitgehend zufällig. In Charge 6 sind spät etwas mehr Kreaturen (ρ 0,21); der Effekt bleibt nach Bereinigung um F1-H und Kreaturanteil (−0,34). Lesart: In Charge 6 wird R2 spät härter, in Charge 2 streut es spät mehr. Das ist schwach und nicht über alle Chargen hinweg. Die Länge der R2-Begründungen fällt über die Position nicht (ρ −0,15 bis +0,26).

### 2.5 Zuversicht und Begründungslänge

| Gruppe | n | mittl. d | SD(d) | mittl. \|d\| | ICC H |
|---|---|---|---|---|---|
| F1 high / medium / low | 423 / 498 / 1 | −4,86 / −4,58 / −25 | 9,8 / 11,9 | 8,2 / 10,0 | 0,877 / 0,733 |
| R2 high / medium / low | 557 / 359 / 6 | −5,40 / −3,55 / −12,5 | 9,9 / 12,4 | 8,6 / 10,0 / 12,5 | 0,842 / 0,767 |
| R2-Begründung Quartil 1 → 4 (Zeichen) | 230/227/227/238 | −6,85 → −2,61 | 7,9 → 12,6 | 8,1 → 9,7 | |

Kreuztabelle der Zuversicht (F1|R2): high|high 362, high|medium 61, medium|high 195, medium|medium 297, medium|low 6, low|medium 1. Zuversicht „medium“ geht mit größerer Abweichung einher, sagt sie aber schwach vorher. Die Länge der Begründung ist mit |d| kaum korreliert (ρ 0,05 bei R2, 0,035 bei F1). Medianlänge: F1 374, R2 326 Zeichen.

### 2.6 Anker-Karten gegen Rest-Spells

| Menge (Welle 2) | n | F1-H Mittel | Anteil Kreaturen | MV | d E/F/T/R/K/D | **d H** |
|---|---|---|---|---|---|---|
| Anker-Spells | 30 | 52,5 | 0,43 | 2,8 | +5,8/+1,0/−3,2/+6,5/+2,2/+5,2 | **−0,83** |
| Rest-Spells | 548 | 24,0 | 0,52 | 3,1 | −0,2/−3,4/−5,2/+2,3/+3,5/+5,0 | **−5,11** |

Nach F1-Band bei Welle-2-Spells (Anker / Nicht-Anker, mittl. d): 5–27: −1,3 (n 4) / −3,7 (302); 28–49: 0,0 (4) / −7,3 (238); 50–71: −4,4 (8) / **+0,4 (27)**; 72–94: −2,3 (11) / 0,0 (1). Das ist rein beschreibend, die n sind klein.

**Was die Anker unterscheidet:** (a) Sie liegen im oberen Bereich, wo auch Nicht-Anker kaum abweichen. (b) Sie sind „Lehrbuchkarten“ des Guides mit Beschreibung in der Ankertabelle; R2 sah sie in allen übrigen Instanzen. (c) **F1 sah bei 36 Ankerkarten die eigene Zeile und übernahm sie** (siehe Tabelle). Bei den 10 „v1 fixed“-Karten waren F1 und R2 gleich weit vom Ankerwert entfernt.

| Ankerzeilen | n Zeilen | F1 exakt | R2 exakt | MAE F1 | MAE R2 |
|---|---|---|---|---|---|
| „v1 fixed“ (beide Läufe ohne eigene Zeile) | 46 | 16 | 20 | 6,87 | 5,24 |
| übrige Anker (F1 sah die eigene Zeile, R2 nicht) | 76 | **64** | 23 | **1,12** | 8,68 |

Befehl: `A1/a1_struct.py` → `struct.json` (`anchor_visibility`).

## 3. Strukturfehler D↔H (Frage 3)

Befehl: `A1/a1_struct.py` → `$A1_OUT/struct.json`. „Lücke“ heißt H − Mittel(E,F,T,R,K,D).

| Lauf | n | H > 25 unter Mittel | H > 25 über Mittel | \|Lücke\| > 15 | mittl. Lücke | OLS-Gewichte E/F/T/R/K/D | Achsenabschnitt | R² | R² ohne D | H≤10 mit D≥75 |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 | 922 | 8 | 0 | 284 | −10,2 | .34/.31/.11/.31/.19/**.02** | −20,6 | 0,905 | 0,905 | 55/180 |
| F1 auf W1-Karten | 300 | 3 | 0 | 60 | −6,2 | .38/.32/.10/.35/.18/−.03 | −20,8 | 0,935 | 0,934 | |
| F1 auf W2-Karten | 622 | 5 | 0 | 224 | −12,2 | .32/.29/.13/.28/.18/.04 | −20,1 | 0,875 | 0,873 | |
| R2 Welle 1 | 300 | 12 | 1 | 132 | −11,5 | .46/.32/.03/.30/.12/**−.12** | −17,1 | 0,941 | 0,935 | 20/73 |
| R2 Welle 2 | 622 | **63** | 0 | **457** | **−17,3** | .43/.32/.12/.22/.13/**.03** | −25,5 | 0,900 | 0,899 | 94/227 |
| R2 Retest 8 | 50 | 0 | 0 | 19 | −10,7 | .47/.27/.11/.32/.12/−.12 | −16,6 | 0,956 | 0,949 | 5/11 |
| F2 (Drift) | 49 | 1 | 0 | 17 | −11,1 | .27/.37/.25/.27/.23/.03 | −23,7 | 0,907 | 0,907 | 2/12 |
| G1 (unabh.) | 70 | 0 | 0 | 30 | −10,1 | .33/.50/.03/.26/.05/−.08 | −15,1 | 0,951 | 0,948 | 4/19 |
| Pilot (alle) | 318 | 0 | 2 | 83 | −3,9 | .47/.31/.08/.30/.16/.08 | −25,5 | 0,917 | 0,914 | 3/30 |

Antworten:
- **Guide-Formel:** `GUIDE_v2.md` nennt **keine** Formel. H ist „not their average“; wer mehr als 25 vom Mittel abweicht, muss es in `reason` begründen. Alle Läufe tun dasselbe: H ≈ −20 + 0,3 bis 0,45·E + 0,3·F + 0,25 bis 0,35·R + kleine Anteile von T und K, **D ≈ 0**. H ist zu 90 bis 95 % linear aus vier Kriterien erklärbar. Ohne D sinkt R² um höchstens 0,006.
- **D:** Laut Guide ist D „low-cost-ness, 100 = no risk, no cost“. Es misst nur Kosten (Wrath-Exposition, Symmetrie, Pips, Game-Changer-Platz) und keinen Nutzen. Eine Karte, die nichts tut und nichts kostet, bekommt deshalb hohes D; die Definition erlaubt das ausdrücklich. Unter den Karten mit H ≤ 10 haben D ≥ 75: F1 55/180, R2 W2 94/227. Weil D ins Mittel eingeht, H aber nicht trägt, hebt D das Mittel. Die Regel „> 25 vom Mittel → begründen“ wird so zu einem Artefakt der Skalenlagen; die mittlere Lücke liegt in allen Läufen bei −4 bis −17.
- **63 in Welle 2 gegen 5 bei F1 auf denselben Karten:** R2 hat einen tieferen Achsenabschnitt (−25,5 gegen −20,1) und ein höheres D (+4,4 im Mittel). Damit ist die Lücke im Mittel 5 Punkte größer, und mehr Karten überschreiten die Grenze von 25. Es ist dieselbe Ursache wie in §2.1: der H-Schritt.

## 4. Externe Validität (Frage 4, nur Maßstab)

Befehl: `A1/a1_external.py --usage <scratchpad>/rubric_v2/data/usage_holdout.jsonl --corpus <lokaler Checkout>/data/research/chulane_corpus` → `$A1_OUT/external.json`. Partielle Korrelationen: `a1_extra.py` → `extra.json`.

`usage_holdout.jsonl` ist nicht im Repo. Es ist die lokal von `extract_facts.py` erzeugte Datei (SHA `c3d1f693…`); ihre `facts.jsonl` ist SHA-gleich mit dem Repo. Gegenprobe aus den Repo-Decklisten: 10 551 Decks, ρ(Zählung aus Repo, deck_list_count) = 0,9992. Der Korpus-Checkout steht auf `1a70f41f`, der Korpus-Ordner wurde nur für diese Gegenprobe gelesen. Die PILOT_REPORT-Zahlen sind reproduziert: ρ(F1, Quelldecks) 0,504, AUC F1 0,819, v1 0,845, Quelldecks 0,924.

Spearman gegen das Signal, gepaarter Bootstrap über Karten (2000 Ziehungen, Seed 20261122):

| Signal | F1 | R2 | H_pooled | v1 (Referenz) | R2 − F1 [95 %] |
|---|---|---|---|---|---|
| Quelldeck-Anzahl (alle Brackets) | 0,504 [0,452; 0,551] | **0,673** [0,633; 0,710] | 0,618 | 0,620 | +0,169 [0,137; 0,203] |
| Deckanteil Bracket 3 | 0,498 | 0,659 | 0,608 | 0,613 | +0,161 [0,128; 0,196] |
| EDHREC-Inklusion global | 0,401 | 0,568 | 0,509 | 0,519 | +0,168 [0,137; 0,202] |
| −Scryfall-EDHREC-Rang | 0,366 | 0,548 | 0,480 | 0,490 | +0,182 [0,150; 0,217] |
| Referenzdeck AUC (79 gegen 843) | 0,819 [0,762; 0,867] | 0,857 [0,807; 0,900] | 0,850 | 0,845 | +0,038 [0,000; 0,077] (knapp) |
| **partiell**: Quelldecks bei kontrollierter globaler Inklusion | 0,335 | 0,439 | 0,407 | 0,397 | +0,104 [0,068; 0,143] |
| **partiell**: Quelldecks bei kontrolliertem Scryfall-Rang | 0,390 | 0,468 | 0,451 | 0,441 | +0,078 [0,041; 0,115] |

Je Teilmenge (Signal Quelldecks; F1 / R2; Differenz F1 − R2):

| Teilmenge | n | F1 | R2 | F1 − R2 [95 %] |
|---|---|---|---|---|
| Spells | 857 | 0,529 | 0,668 | −0,139 [−0,173; −0,107] |
| Länder | 65 | 0,741 | 0,826 | −0,085 [−0,224; +0,022] |
| Kreaturen | 478 | 0,602 | 0,686 | −0,083 [−0,125; −0,043] |
| Nicht-Kreatur-Spells | 379 | 0,493 | 0,666 | −0,174 [−0,223; −0,122] |
| mit Nutzung > 0 | 736 | 0,478 | 0,640 | −0,162 |
| Welle 1 / Welle 2 | 300 / 622 | 0,483 / 0,451 | 0,657 / 0,636 | −0,175 / −0,185 |
| \|d\| ≥ 15 | 266 | 0,254 | 0,663 | −0,409 [−0,532; −0,288] |

Je Schicht (Spitze und markiert sind nach F1 ausgewählt; dort ist F1 bereichseingeschränkt, das begünstigt R2):

| Schicht | n | F1 | R2 | F1 − R2 [95 %] |
|---|---|---|---|---|
| W1 markiert | 35 | 0,080 | 0,707 | −0,627 [−0,973; −0,223] |
| W1 Spitze | 100 | 0,362 | 0,551 | −0,189 [−0,332; −0,041] |
| W1 Rest (+ Füllung 15) | 100 (+15) | 0,254 (0,552) | 0,394 (0,745) | −0,140 [−0,274; −0,008] |
| W1 Länder | 50 | 0,738 | 0,780 | −0,042 [−0,172; +0,058] |
| W2 Spitze | 32 | 0,474 | 0,766 | −0,292 [−0,581; −0,052] |
| W2 Rest | 548 | 0,342 | 0,546 | −0,203 [−0,258; −0,154] |
| W2 Anker-Spells | 30 | 0,787 | 0,895 | −0,108 [−0,261; +0,023] |
| W2 Anker-Länder | 12 | 0,583 | 0,844 | −0,260 [−0,767; +0,081] |

Bei den 266 Karten mit |d| ≥ 15 liegt R2 im Rang näher an der Nutzung als F1 in 195 Fällen, F1 in 71. Senkt R2 um 15 oder mehr (n 203), haben die Karten im Median 3 Quelldecks und einen Referenzdeck-Anteil von 4,4 %. Hebt R2 um 15 oder mehr (n 63), sind es im Median 94 Quelldecks und 19 %. Der Median aller Karten liegt bei 7.

**Entscheidet das „welcher ist näher“? Nein.** Gründe:
1. Nutzung ist nicht Qualität. Decks spiegeln Beliebtheit, Preis, Verfügbarkeit und Gewohnheit; das Referenzdeck ist teils nach Beliebtheit gebaut (PILOT_REPORT §9). Ein Rater, der besser mit der Nutzung übereinstimmt, ist ein besserer Nutzungs-Prädiktor, nicht nachweislich ein besserer Qualitäts-Rater.
2. Ein **Beliebtheitsleck** bei R2 ist möglich. R2 liegt über v1, das selbst als beliebtheitsgefärbt gilt. R2 hatte technisch Web-Zugang, und die Blindheit beruht nur auf Selbstauskunft. Modellwissen über Beliebtheit lässt sich nicht ausschließen; der Stichwort-Scan (0 Treffer) beweist keine Blindheit.
3. Ein Teil des Vorsprungs bleibt bei kontrollierter globaler Beliebtheit (+0,08 bis +0,10). Das spricht für ein **Chulane-spezifisches** Signal: entweder ein besseres Funktionsverständnis für dieses Deck oder Wissen über Chulane-Listen. Beides ist aus diesen Daten nicht trennbar.
4. Ein geteiltes Deckmodell erklärt dasselbe Muster. R2 nimmt durchgehend „wenig Artefakte, wenig Lebensgewinn, kein Tribal“ an (§5), und echte Chulane-Listen teilen diese Annahme. Das ist Übereinstimmung in der Annahme, kein Beleg für Wahrheit.

## 5. Die 30 größten Abweichungen (Frage 5, Ersteinschätzung, nicht endgültig)

Befehl: `A1/a1_top30.py` → `$A1_OUT/top30.json` (beide Begründungen vollständig, mit allen Teilkriterien). Sortierung: |d| absteigend, dann Name. Die 22 Karten mit |d| ≥ 30 sind vollständig dabei. **32 Karten haben genau |d| = 25**; davon stehen die ersten 8 alphabetisch hier. Nicht gelistet sind diese 24: Formless Genesis, Gleaming Barrier, Heroes' Bane, Hexhaven Battalion, Jedit Ojanen of Efrava, Killer Service, Koma, Cosmos Serpent, Kulrath Mystic, Loran of the Third Path, Lys Alana Informant, Merfolk Looter, Mindful Biomancer, Prideful Parent, Reclamation Sage, Reliquary Tower, Reluctant Dounguard, Safewright Cavalry, Saheeli, Consul of Oversight, Serrated Biskelion, Stonehorn Dignitary, Sunlance, Surrak, the Hunt Caller, Treasure Mage, Wolfbriar Elemental. Verteilung der 30: 11 W1 markiert, 8 W1 Spitze, 1 W1 Rest, 9 W2 Rest, 1 W2 Anker.

Kürzel der Ursachen: **DA** Deckannahme (fehlende Deck-Information), **GM** Guide-Mehrdeutigkeit, **HK** H-gegen-Kriterien, **BL** Beliebtheitsleck möglich, **RF** Regelfehler, **FI** fehlende Information im Kartenblock. „Lücke“ ist H − Mittel(E…D) je Lauf.

| # | Karte (Herkunft R2) | F1 → R2 | Kern F1 | Kern R2 | Ersteinschätzung |
|---|---|---|---|---|---|
| 1 | Assert Perfection (W1:3, markiert) | 50 → 10 | billige einseitige Removal in Kreaturendeck | Deckkreaturen haben 1–3 Power, tötet kaum; Lücke R2 −25,8 | DA (Power der eigenen Kreaturen) + HK |
| 2 | Veil of Summer (W2:2) | 20 → 60 | „narrow sideboard-style“, nur gegen U/B | billiger Schutz des Motors, ersetzt sich | GM (Wert von Schutz/Interaktion), BL möglich |
| 3 | Whirler Rogue (W1:3) | 70 → 30 | wiederholbarer Motor über Bounce | drei kleine Körper, keine Karten/Länder/Mana; UU < 50 % | GM (Körper/Token ohne Ressourcen) |
| 4 | Imperious Perfect (W1:3) | 60 → 25 | Wertmotor in jedem Kreaturendeck | Tribal-Karte, nur langsamer Token-Macher | DA (Elfenzahl) |
| 5 | Lyra Dawnbringer (W1:2) | 60 → 25 | starker Finisher, WW-Belastung | guter Kämpfer, nichts für den Motor | GM (Körper/Finisher; Audit-A-Muster) |
| 6 | Nature's Claim (W1:1) | 25 → 60 | eng, oft tot (R 30) | billigste Antwort, Ziel meist da (R 75) | GM (R und F für Antworten), BL möglich |
| 7 | Shore Lurker (W1:3) | 50 → 15 | solider Flieger, Chulane-Trigger | gewöhnlicher Körper, schwacher ETB | GM (Körper ohne Funktion) |
| 8 | Thought Monitor (W1:3) | 45 → 10 | Draw-2-ETB, abhängig von Artefakten | Deck hat wenige Artefakte → 6–7 Mana | DA/FI (Artefaktzahl unbekannt) |
| 9 | Cat Collector (W1:3) | 50 → 20 | wiederholbarer Food-ETB | wenig Lebensgewinn, nur Körper + Food | DA (Lebensgewinn) |
| 10 | Drogskol Reaver (W1:3) | 45 → 15 | mächtiges Top-End | 7 Mana, laut Fakten < 1/5 rechtzeitig | GM (Gewicht der Castability bei Top-End) |
| 11 | Elspeth, Knight-Errant (W1:2) | 60 → 30 | stark überall, neutral für Chulane | nimmt dem Motor einen Platz (F 30) | GM (Neutralitätsregel für Nicht-Kreaturen: F 40–50) |
| 12 | Faebloom Trick (W2:1) | 40 → 10 | solides Füllmaterial | kleiner Tempo-Effekt; Lücke R2 −25,8, nennt R/D ausdrücklich | HK (D/R heben das Mittel) |
| 13 | Kappa Cannoneer (W1:3) | 40 → 10 | solider Körper, wenig Artefakte | Artefakt-Karte ohne Unterstützung | DA (Artefakte) |
| 14 | Merrow Skyswimmer (W1:3) | 55 → 25 | Token-ETB wiederholbar | zwei kleine Körper, nur mit Convoke fair | GM (Körper/Token) |
| 15 | Mistmeadow Council (W2:2, Anker K) | 60 → 30 | zwei Karten pro Cast mit Chulane | teuer für eine Karte | GM (Preis des ETB-Replays); Anker K 50 bei beiden gleich |
| 16 | Personify (W1:1) | 65 → 35 | ETB-Wiederholung für 2 (F 80, trotz „kein Trigger“) | Blink ohne Cast, nichts für Chulane | GM (Einmal-Blink, Audit-A-Muster); innere Spannung F1 (F 80 gegen eigenen Text) |
| 17 | Revoke Existence (W2:2) | 20 → 50 | eng, tot ohne Ziel (R 30) | Ziel bei drei Gegnern fast immer da (R 80) | GM (R für Antworten) |
| 18 | Ruin Ghost (W1:1) | 20 → 50 | schwach ohne Landfall-Payoffs | stark mit Landfall, sonst billiger Trigger | DA (Landfall-Dichte im Deck) |
| 19 | Shimmer Dragon (W1:2) | 40 → 10 | ordentlicher 6-Drop-Flieger | für Artefaktdecks gebaut | DA (Artefakte) |
| 20 | Storm Spirit (W1:3) | 45 → 15 | starker später Motor | überteuerter Pinger | GM (E/Castability bei 6-Drops) |
| 21 | Viridian Revel (W2:7) | 5 → 35 | enge Hate-Karte | gut gegen Artefakt-Token-Tische | DA (Gegner-Meta) |
| 22 | Wary Farmer (W1:2) | 55 → 25 | guter billiger Körper mit Selektion | ehrlicher Körper, kleine Selektion | GM (Körper ohne Funktion) |
| 23 | An Offer You Can't Refuse (W2:6) | 30 → 55 | enger Counter | billiger Schutz des Motors | GM (Interaktion), BL möglich |
| 24 | Angel of Vitality (W2:4) | 45 → 20 | starker Körper, billiger Trigger | „nur ein Körper“ | GM (Körper ohne Funktion) |
| 25 | Apex Hawks (W2:3) | 40 → 15 | flexibler Trigger | „plain scalable body“ | GM (Körper ohne Funktion) |
| 26 | Ardent Plea (W1:2) | 45 → 20 | Zwei-für-eins | zufälliger billiger Treffer | GM (Kaskade bewerten) |
| 27 | Awakener Druid (W1:2) | 40 → 15 | zwei Körper; belebtes Land per Chulane zurück | Land wird angreifbar, frisches Land kann nicht tappen | GM/DA (Forest-Zahl); Regelpunkt prüfen (beide Lesarten plausibel) |
| 28 | Briarhorn (W1:3) | 55 → 30 | flexibler Flash-Trigger | Trigger mit kleinem Effekt | GM (Körper/Trick) |
| 29 | Confiscate (W2:5) | 45 → 20 | starkes, langsames Stehlen (T 75) | teuer und langsam | GM (Preis für 6-Mana-Nicht-Kreatur) |
| 30 | Foraging Wickermaw (W1:2) | 60 → 35 | Trigger, Fixing, Körper | fixt, rampt nicht | GM (Wert von Fixing) |

Zusammenfassung der Ersteinschätzung: Kein klarer Regelfehler. Nr. 27 und Nr. 16 sollten blind geprüft werden. Am häufigsten sind „Körper/Token ohne Ressourcengewinn“ (GM, etwa 12 Karten, fast alle R2 tiefer) und Deckannahmen über unsichtbare Deckinhalte (DA, etwa 8, R2 nimmt „wenig“ an). Bei Nicht-Kreatur-Antworten und Schutz liegt R2 höher (GM bei R und F, etwa 6; dort ist auch ein Beliebtheitsleck möglich). H-gegen-Kriterien betrifft vor allem die Fälle, in denen R2 die Lücke selbst nennt.

## 6. Folgerungen für ein besseres Design (aus den Befunden)

1. **Eingabe vollständig gleich halten und protokollieren:** eine Ankerregel für alle (jede Karte ohne alle eigenen Ankerzeilen), gleiche Kartenzahl je Aufruf (klein und zustandslos), gleicher Rahmentext, Modell-ID und Parameter im Repo-Protokoll (anonymisiert, aber prüfbar), keine Web-Werkzeuge.
2. **H nicht frei lassen:** H aus den Kriterien berechnen (etwa ein festes Gewicht von E, F und R mit kleinen Anteilen von T und K) oder einen Korridor um die Formel vorgeben. Der freie H-Schritt erklärt die ganze Niveau-Differenz von etwa −4,7. Die Streuung je Karte (77 bis 79 % der Varianz von d) bleibt dabei; sie kommt aus E, F und R und braucht die Punkte 4 und 5.
3. **D neu fassen:** entweder „Kosten, falls die Karte etwas tut“ oder D aus Mittel und Regel nehmen. Die Regel „> 25 vom Mittel“ ist mit dem heutigen D ein Artefakt.
4. **Deckannahmen festschreiben:** Das Referenzprofil des Decks gehört in den Guide (Zahl der Artefakte, Lebensgewinn, Tribal, Landfall-Payoffs, Power der Kreaturen). Sonst füllt jeder Rater die Lücke anders.
5. **Beispiele für die Streitklassen:** Körper/Token ohne ETB-Ressource, Einmal-Blink, Antworten und Schutz (R bei drei Gegnern), Top-End mit Castability, Fixing ohne Ramp.
6. **Externe Maße nur als Gegenprobe** und mit partieller Kontrolle der globalen Beliebtheit. Ein höheres ρ mit Nutzung ist kein Qualitätsbeleg.

## 7. Reproduktion

```
A1_USAGE=<usage_holdout.jsonl> A1_CORPUS=<chulane_corpus> A1_F1RAW=<F1-Chargenprompts> A1_OUT=<ordner> \
  bash data/research/chulane_rubric_v3_20261123/phaseA_scripts/A1/run_all.sh
# Reihenfolge: a1_parity → a1_decomp → a1_struct → a1_external → a1_extra → a1_top30
# Variablen: A1_REPO (Standard: dieser Checkout; gerechnet auf main f4d49ad6), A1_USAGE (usage_holdout.jsonl, Scratchpad, SHA c3d1f693…),
#            A1_CORPUS (lokaler Korpus-Checkout @ 1a70f41f, nur Gegenprobe), A1_F1RAW (Original-F1-Prompts, Scratchpad)
```

Zweimal gelaufen, Ausgaben byte-gleich (SHA-256); am 2026-11-23 aus dem Repo-Ordner mit parametrisierten Pfaden erneut gelaufen, wieder byte-gleich: parity.json `6391dbfc…`, decomp.json `83f5b08f…`, pairs.jsonl `89f85818…`, struct.json `562adc0b…`, external.json `45ffe987…`, extra.json `1996b94c…`, top30.json `055e4836…`. Nur Standardbibliothek und numpy, feste Seeds (20261122). Bootstrap-Intervalle sind 95-%-Perzentile.

Grenzen: Familie und Version der Rater sind im Repo unbekannt (Familie von F1 unbelegt). Den Nutzungsindex der Tierliste habe ich nicht gesondert gerechnet, weil er den Studio-Store braucht. Als Signale dienen `usage_holdout` (Quelldecks, Bracket-3-Anteil, EDHREC global, Scryfall-Rang, Referenzdeck) und die Zählung aus dem Repo-Korpus. `usage_holdout.jsonl` ist nicht im Repo; die Repo-Gegenprobe korreliert mit 0,9992. ICC und Spearman messen Übereinstimmung, keine Richtigkeit. Die markierte Schicht und Audit A sind möglicherweise nicht unabhängig von R2.
