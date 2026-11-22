# Kartenverständnis H: zweite Bewertung der übrigen 622 Karten (Welle 2) und gepooltes H, Ergebnisse (Chulane, Raster v2.1, 2026-11-22)

- **Stand:** Branch `docs/rating-full-second-run-results-1404`, gebaut auf `main` @ `2987afc65` (Squash von #1763, Auswerteskript). Refs #1404. F1-Werte, Prüfer-Marken, Welle-1-Daten, Eingaben und Guides von Welle 2 sind unverändert (das Skript prüft ihre SHA-256 gegen das Manifest und den Welle-1-Bericht, sonst bricht es ab).
- **Was verglichen ist:** H und E, F, T, R, K, D derselben Karte aus zwei Bewertungen: **F1** (Vollauf, 922 Karten) und **R2** (zweite Bewertung; Welle 1 = 300 Karten aus #1758, Welle 2 = die übrigen 622 Karten in 7 Chargen zu 88 bis 89 Karten, dazu die Retest-Charge 8 mit 50 Welle-1-Karten). Damit hat **jede der 922 Karten zwei Bewertungen**. Keine Paarvergleiche zwischen Karten.
- **Plan:** vorab festgelegt und vor jeder Welle-2-Ausgabe im Repo: `docs/analysis-reports/rating_full_second_run_plan_20261122.md` (#1761). Schwellen, Mengen und Regeln unverändert; alles mit „explorativ“ markierte steht nicht im Plan.
- **Wirkung:** keine. Produktcode, H, Stufen, Tierliste und Anzeige bleiben unverändert. Der Owner-Vorschlag in §6 ist ein Vorschlag; angewendet wird nichts ohne Owner-Go.
- **Modellnamen** stehen nicht im Repo; die zweite Bewertung heißt „R2“. Modell und Stufe stehen im Scratchpad-Protokoll des Co-Leads, nicht im Repo (§8).

## 0. Kurzfassung

- **Gültigkeit:** 7 von 7 Chargen gültig (m = 7), 622 von 622 Welle-2-Zeilen gültig, V1 bis V4 je Charge voll, kein A1-, A2-, A4-, A5- oder A6-Ausschluss. Karten mit zwei Bewertungen: **922 von 922** (A1g nein). Kennzeichnung nach Plan: „zwei Bewertungen, Unabhängigkeit ungeprüft (A3)“; Kennzahlen je Welle getrennt (A3w).
- **Streuung einer Einzelbewertung** σ₁ = SD(d)/√2 mit d = H_R2 − H_F1: **gesamt 7,77 [7,38; 8,16] (922/922)**, Welle 1 8,68 [7,98; 9,37] (300/300), **Welle 2 7,30 [6,83; 7,76] (622/622)**. Mit Verzerrung (RMS/√2, Anschluss an die 8,1 aus #1758): gesamt 8,46, Welle 1 9,42, Welle 2 7,96.
- **Standardfehler des gepoolten H** SD(d)/2 = **5,50** (gesamt), gilt nur bei unabhängigen Fehlern beider Bewertungen (nicht belegt, A3).
- **Spells-Verzerrung (Bestätigungstest §6):** b = **−4,87 [−6,44; −3,25]** (Cluster-Bootstrap, n = 580 Nicht-Anker-Spells von Welle 2), b < 0 in **7 von 7** Chargen (nötig 6), Schwelle −3,0: **„bestätigt“**. Anker-Spells getrennt −0,83 (n = 30). Welleneffekt A9: nein (0,63 [−1,41; 2,55]). Länder: **kein Schluss** (12 in Welle 2; explorativ +2,85, n = 65).
- **„Besser“ (§7):** B1 ICC(2,1) 0,82 [0,80; 0,84], Spearman-Brown vorhergesagt 0,90 (n = 922). **B2 gegen G1: „unbelegt“** (Familie R2 gegen G1 unbekannt). B3 Retest (50/50, nur beschreibend): ICC 0,96, SD_Retest/√2 = 3,93, Verzerrung +1,5.
- **Abweichungen |d| ≥ 15:** **266 von 922** (28,8 %), davon |d| ≥ 30: 22. Alle markiert, nichts gelöscht.
- **Regelclaims (blind zur Herkunft):** offensichtlich falsch **0 von 50** (Welle 2) und **0 von 50** (F1), beide grün.
- **Lesart des Co-Leads (Zusammenfassung; Wortlaut in §6):** Streuung „mindestens ±8“ bleibt; Spells-Unterschied ist ein Rater-Unterschied, keine Wahrheitsaussage; **K1 nicht anwenden**; Vorschlag an den Owner: Anzeige H_pooled mit `n_bewertungen` und Marke „Bewertungen weichen stark ab“.
- **Grenzen:** Familie und Dateizugriff der Rater UNKNOWN (nur Selbstauskunft, A3); Regelclaim-Prüfer sind Modell-Instanzen; B2 unbelegt; für Länder kein Schluss (§7).

## 1. Reihenfolge der Schritte (Plan §9) mit Belegen

Belegt durch Zeitstempel der GitHub-Kommentare und Merge-Zeiten (UTC). Dateizeiten im Scratchpad haben nur Minutenauflösung und belegen keine feinere Ordnung.

| Schritt | Zeitpunkt | Beleg |
|---|---|---|
| Plan, Eingaben, Guides im Repo | Draft-Commit 2026-11-22T16:19:39Z; Squash 16:41:48Z | #1761, Draft-Commit `a3cd2b4af` (Lauf-Eingaben byte-gleich), Squash `73c22de3` |
| Lauf Chargen 1 bis 8 | Start und Ende je Charge nicht protokolliert; Entscheid Retest-Charge 8 „vor dem Start“ 16:45Z; alle Ausgaben fertig vor dem Freeze | `run_log_redacted.md` |
| **Freeze:** SHA-256 der 8 Ausgaben gepostet, vor jedem Öffnen | 16:52:39Z | [Kommentar 7082408782](https://github.com/moeendres-png/commander-playtest-lab/issues/1404#issuecomment-7082408782) |
| Auswerteskript committet (vor dem ersten Lesen) | 20:44:27Z | #1763, Squash `2987afc6` |
| **Verweis-Treffer** (`hits`, nur Treffersätze, keine Werte) | 20:45:27Z | [Kommentar 7085521227](https://github.com/moeendres-png/commander-playtest-lab/issues/1404#issuecomment-7085521227) |
| **Klassifikation** der Treffer, SHA-256 gepostet | 20:45:35Z | [Kommentar 7085522996](https://github.com/moeendres-png/commander-playtest-lab/issues/1404#issuecomment-7085522996) |
| **Regelclaims** (blinde Liste, zwei Prüfer) und Laufprotokoll-Eingabe | 20:46:55Z | [Kommentar 7085540409](https://github.com/moeendres-png/commander-playtest-lab/issues/1404#issuecomment-7085540409) |
| **eval** (erstes Lesen von Werten und Differenzen) und Lesart | 20:48:08Z | [Kommentar 7085556215](https://github.com/moeendres-png/commander-playtest-lab/issues/1404#issuecomment-7085556215) |

Genau genommen: Vor `eval` wurden aus den Ausgaben nur die Treffersätze der Verweis-Liste (`hits`) und die Claim-Texte der Stichprobe (`claims`, ohne Werte und Herkunft) gelesen. Werte und Differenzen las erst `eval`, nach Freeze, Skript-Commit und Klassifikation. A10 greift nicht.

## 2. Gültigkeit, Blindheit, Formatlücken

| Charge | V1 gültig | V2 alle 7 Werte | V3 Vielfache von 5 | V4 Zitate wörtlich | A5 | A2 zählend | A4 (SD R2 / F1; größter Gleichstand) |
|---|---|---|---|---|---|---|---|
| 1 | 89/89 | 89/89 | 89/89 | 134/134 | 0/89 | 0 | nein (18,9 / 16,0; 15,7 %) |
| 2 | 89/89 | 89/89 | 89/89 | 154/154 | 0/89 | 0 | nein (18,4 / 15,3; 14,6 %) |
| 3 | 89/89 | 89/89 | 89/89 | 131/131 | 0/89 | 0 | nein (17,5 / 15,4; 13,5 %) |
| 4 | 89/89 | 89/89 | 89/89 | 147/147 | 0/89 | 0 | nein (16,7 / 15,4; 18,0 %) |
| 5 | 89/89 | 89/89 | 89/89 | 134/134 | 0/89 | 0 | nein (16,8 / 15,0; 16,9 %) |
| 6 | 89/89 | 89/89 | 89/89 | 120/120 | 0/89 | 0 | nein (17,9 / 17,4; 25,8 %) |
| 7 | 88/88 | 88/88 | 88/88 | 130/130 | 0/88 | 0 | nein (20,6 / 17,6; 19,3 %) |

- **Verweis-Treffer (A2):** Regex `earlier rating|previous|\bv1\b|\bF1\b|audit|tier ?list` über `notes`, `reason`, `uncertainty`, `rule_claims[].claim` und die Schlussantworten aller 8 Chargen: **1 Treffer** (Charge 1, seq 27, Grizzled Outcasts // Krallenhorde Wantons, `reason`, „previous“ in „…no spells were cast in the previous turn…“), eingestuft **„zählt nicht, Buchstabe a“** (Kartentext wiedergegeben). Kein zählender Treffer, A2 nicht ausgelöst.
- **Beliebtheitsliste** (`popular|staple|edhrec|…`): 0 Karten in jeder Charge.
- **Blindheit:** Die Schlussantworten melden, dass nur Anweisung, eigener Guide und eigene Eingabe gelesen wurden (Charge 6 zusätzlich das Schema). Zugriff außerhalb des Rater-Ordners und Web waren technisch möglich; Nicht-Nutzung beruht nur auf dieser **Selbstauskunft**.
- **Ermüdung (§9, nur berichten):** auffällig in **Charge 2** (mittlere |d| 6,93 in der ersten gegen 10,44 in der zweiten Hälfte, Differenz > 3) und **Charge 6** (8,52 gegen 11,89; ρ(Position, d) = −0,35). Übrige Chargen unauffällig. Kein Abbruch vorgesehen.
- **Chargeneffekt (A6):** keine Charge auffällig; mittlere d je Charge −4,21 · −1,85 · −3,09 · −5,62 · −6,57 · −6,74 · −3,41; σ²_Charge = 2,29.

**Formatlücken (H mehr als 25 unter dem Mittel von E bis D).** Nach der Anweisung muss eine solche Zeile sagen, warum. Das ist kein Gültigkeitskriterium; die Zeilen bleiben unverändert und gehen in die Auswertung ein. Zwei Zählungen stehen nebeneinander und messen Verschiedenes:

| Charge | Skript: Bedingung erfüllt („unter“) | Rater-Selbstmeldung: ohne ausdrückliche Begründung | Nachlesen (explorativ, nach `eval`) |
|---|---|---|---|
| 1 | 4 | 1 (+3 mit generischem Satz) | passt: 3 Zeilen mit angehängtem Pflichtsatz, 1 ohne |
| 2 | 5 | 1 | passt (Stichwort-Suche: 4 nennen den Abstand) |
| 3 | 11 | 0 | **passt nicht wörtlich:** gelesen, alle 11 begründen das niedrige H inhaltlich, aber nur 1 (seq 56) nennt den Abstand zum Mittel ausdrücklich |
| 4 | 13 | 13 | passt (keine nennt den Abstand) |
| 5 | 6 | 0 | passt (alle 6 nennen den Abstand) |
| 6 | 9 | 9 | passt: gelesen, alle 9 begründen inhaltlich, keine nennt den Abstand ausdrücklich |
| 7 | 15 | 2 | passt (13 nennen den Abstand) |
| zusammen | **63** von 622 (H mehr als 25 über dem Mittel: 0) | **26** (+3 generisch) | – |

**Erklärung der Differenz 63 gegen 26:** Das Skript zählt nur die Zahlenbedingung (`formatluecken_H_gt25_vom_mittel`, Hinweis im Ergebnis: „nur gezählt; ob die Begründung fehlt, wird von Hand gelesen“). Die Rater zählten nur Zeilen ohne Begründung. Die übrigen 34 Zeilen (63 − 26 − 3) haben nach Auskunft der Rater eine Begründung. Beim Nachlesen gilt das für die Chargen 1, 2, 4, 5 und 7 auch wörtlich. Bei den Chargen 3 und 6 haben die Rater denselben Zeilentyp verschieden eingestuft: Begründungen ohne ausdrücklichen Satz zum Abstand vom Mittel gelten in Charge 3 als „begründet“ (0 gemeldet), in Charge 6 als „ohne ausdrückliche Begründung“ (9 gemeldet). Streng gelesen (ausdrücklicher Satz nötig) fehlen also etwa 36 statt 26 Begründungen; inhaltlich begründet ist das niedrige H in allen gelesenen Zeilen der Chargen 3 und 6. Gelesen wurden die 20 Zeilen der Chargen 3 und 6; für die übrigen 43 Zeilen ist die Prüfung nur eine Stichwortsuche (`mean|average|sub-scores|more than 25`). Formcheck nach dem Lauf, kein Plan-Kriterium.

## 3. Streuung aus den Paardifferenzen (Plan §5, d = H_R2 − H_F1)

Intervalle: Bootstrap über Karten, geschichtet nach Welle × Schicht, 5000 Ziehungen, Seed 20261124, 95 % Perzentil. Herkunft aller Zahlen: Auswerteskript auf den eingefrorenen Ausgaben (`result.json`).

| Menge | n/N | Verzerrung b [95 %] | SD(d) | RMS | mittl. \|d\| | \|d\| ≥ 15 | σ₁ = SD/√2 [95 %] | RMS/√2 | SE gepoolt = SD/2 |
|---|---|---|---|---|---|---|---|---|---|
| gesamt | 922/922 | −4,73 [−5,40; −4,05] | 10,99 | 11,96 | 9,16 | 266 von 922 | 7,77 [7,38; 8,16] | 8,46 | 5,50 |
| Welle 1 | 300/300 | −5,20 [−6,53; −3,85] | 12,28 | 13,32 | 9,80 | 93 von 300 | 8,68 [7,98; 9,37] | 9,42 | 6,14 |
| Welle 2 | 622/622 | −4,50 [−5,29; −3,69] | 10,32 | 11,25 | 8,86 | 173 von 622 | 7,30 [6,83; 7,76] | 7,96 | 5,16 |
| Kartenart Spell | 857/857 | −5,30 [−6,02; −4,59] | 11,03 | 12,23 | 9,49 | 260 von 857 | 7,80 [7,37; 8,20] | 8,65 | 5,51 |
| Kartenart Land | 65/65 | +2,85 [1,23; 4,62] | 7,12 | 7,62 | 4,85 | 6 von 65 | 5,04 [3,97; 6,03] | 5,39 | 3,56 |

**Je Schicht:**

| Schicht | n/N | b [95 %] | mittl. \|d\| | \|d\| ≥ 15 | σ₁ [95 %] |
|---|---|---|---|---|---|
| Welle 1 Spitze `top20` | 100/100 | −5,45 [−7,90; −3,00] | 9,95 | 30 von 100 | 8,78 [7,56; 9,89] |
| Welle 1 Rest | 115/115 | −5,74 [−7,48; −3,91] | 8,87 | 32 von 115 | 6,79 [5,65; 7,87] |
| Welle 1 Länder | 50/50 | +2,30 [0,60; 4,10] | 4,10 | 3 von 50 | 4,47 [3,26; 5,45] |
| Welle 1 markiert | 35/35 | −13,43 [−19,43; −7,29] | 20,57 | 28 von 35 | 13,36 [9,61; 16,04] |
| Welle 2 Spitze `top20` | 32/32 | −0,78 [−4,53; 3,12] | 8,59 | 10 von 32 | 7,83 [5,85; 9,48] |
| Welle 2 Rest | 548/548 | −5,11 [−5,95; −4,29] | 8,92 | 153 von 548 | 7,09 [6,57; 7,60] |
| Welle 2 Anker-Spells | 30/30 | −0,83 [−5,33; 3,50] | 8,50 | 8 von 30 | 8,66 [6,06; 10,69] |
| Welle 2 Anker-Länder | 12/12 | +4,17 [−1,25; 9,58] | 7,50 | 2 von 12 | 7,04 [3,79; 9,31] |

**Je Charge (Welle 2) und H_F1-Band:**

| Menge | n/N | b [95 %] | mittl. \|d\| | \|d\| ≥ 15 | σ₁ [95 %] |
|---|---|---|---|---|---|
| Charge 1 | 89/89 | −4,21 [−6,01; −2,42] | 8,03 | 17 von 89 | 6,57 [5,48; 7,56] |
| Charge 2 | 89/89 | −1,85 [−4,21; 0,62] | 8,71 | 26 von 89 | 8,42 [6,78; 9,87] |
| Charge 3 | 89/89 | −3,09 [−5,11; −1,12] | 7,81 | 19 von 89 | 6,94 [5,86; 7,90] |
| Charge 4 | 89/89 | −5,62 [−7,47; −3,65] | 8,54 | 24 von 89 | 6,80 [5,78; 7,75] |
| Charge 5 | 89/89 | −6,57 [−8,20; −4,89] | 9,16 | 25 von 89 | 6,18 [5,19; 7,08] |
| Charge 6 | 89/89 | −6,74 [−8,88; −4,55] | 10,22 | 29 von 89 | 7,39 [6,24; 8,48] |
| Charge 7 | 88/88 | −3,41 [−5,57; −1,14] | 9,55 | 33 von 88 | 8,05 [6,76; 9,16] |
| Band H_F1 95–100 | 0/0 | unbekannt (keine Karte) | unbekannt | unbekannt | unbekannt |
| Band H_F1 72–94 | 24/24 | −3,12 [−6,67; −0,21] | 5,21 | 4 von 24 | 5,97 [3,83; 7,54] |
| Band H_F1 50–71 | 144/144 | −5,94 [−7,81; −3,96] | 10,87 | 51 von 144 | 9,41 [8,39; 10,38] |
| Band H_F1 28–49 | 312/312 | −7,08 [−8,38; −5,77] | 11,54 | 136 von 312 | 8,50 [7,92; 9,00] |
| Band H_F1 5–27 | 422/422 | −3,03 [−3,84; −2,22] | 7,35 | 74 von 422 | 6,40 [5,77; 7,00] |
| Band H_F1 0–4 | 20/20 | +3,00 [2,00; 4,00] | 3,00 | 1 von 20 | 3,87 [2,90; 5,21] |

Welle-1-Dateien wie #1758 (ohne markierte): mittlere |d| 6,59 · 8,41 · 10,11 (n = 88 · 88 · 89), gleich dem Welle-1-Bericht (Gegenprobe).

## 4. Spells-Verzerrung, K0/K1 (Plan §6)

- **Bestätigungsmenge:** 580 Nicht-Anker-Spells der 7 gültigen Chargen (32 Spitze, 548 Rest). b_W2 = **−4,87**, Cluster-Intervall **[−6,44; −3,25]** (Karten-Intervall, nur beschreibend: [−5,68; −4,06]). b je Charge: −4,64 · −2,29 · −2,95 · −6,27 · −7,35 · −6,81 · −3,78 (n = 83, Charge 7 n = 82): **7 von 7 negativ**. Urteil nach Plan: **„bestätigt“**, keine Sperre.
- **Anker-Spells** (getrennt, nicht im Test): −0,83 (n = 30). **Welleneffekt A9** (Rest-Spells ohne Anker): Welle 1 −5,74 (n = 115), Welle 2 −5,11 (n = 548), Differenz 0,63 [−1,41; 2,55]: nein.
- **Länder:** kein Schluss (nur 12 Anker-Länder in Welle 2); explorativ über alle 65 Länder +2,85 [1,23; 4,62].
- **K0 gegen H_F1** (einfaches Mittel, N = 922): 178 Karten ins tiefere, 34 ins höhere Guide-Band; Seite von H ≥ 50: 37 nach unten, 5 nach oben. **K1** (R2 vorher um −4,87 verschoben, nur Spells): 138 tiefer, 45 höher; Seite von 50: 37 nach unten, 5 nach oben. Stufenwechsel: **unbekannt** (für H gibt es im Produkt keine Stufenregel; das Skript lief ohne `--tier-rule`).
- **Planregel und Entscheidung:** Nach Plan §6 wäre ein K1-Vorschlag **erlaubt** (Ergebnis `vorschlag.K1_vorschlag_erlaubt: true`, keine Gründe dagegen). Dass K1 **nicht** vorgeschlagen wird, ist die Lesart des Co-Leads (§6 Punkt 2), keine Sperre durch eine Regel.

## 5. „Besser“ (Plan §7)

| Nr | Messung | Wert | Urteil |
|---|---|---|---|
| B1 | ICC(2,1) H, alle 922 | 0,82 [0,80; 0,84]; Spearman-Brown = ICC(2,2) 0,90 [0,89; 0,91]; ICC(3,1) 0,84; Spearman 0,83 | nur berichtet (Annahmen §5 des Plans) |
| B1 je Welle | Welle 1 (300) · Welle 2 (622) | ICC(2,1) 0,82 · 0,79; Spearman-Brown 0,90 · 0,89; Spearman 0,85 · 0,80 | nur berichtet (A3w) |
| B2 | Δ_G1 = mittl. \|H_F1 − H_G1\| − mittl. \|H_pooled − H_G1\| (n = 70 von 70) | K0 **2,57 [1,57; 3,57]**; K1 1,63 [0,61; 2,66]; Spearman ρ(H_pooled, G1) 0,968 gegen ρ(H_F1, G1) 0,920 | **unbelegt** |
| F2 | dasselbe gegen F2 (F1-Familie, n = 49, nur beschreibend) | K0 0,15 [−1,48; 1,68] | nur beschreibend |
| B3 | Retest Charge 8 (50/50) gegen R2 Welle 1 | ICC(2,1) 0,96; SD(d_rt)/√2 = 3,93; Verzerrung +1,5; σ₁ F1–R2 auf denselben 50 Karten 7,25 | nur beschreibend, nie Beleg für „besser“ |

**Zu B2, ausdrücklich:** Das Intervall von Δ_G1 (K0) liegt ganz über 0. Nach Plan §7 hieße das „besser belegt“, **aber nur, wenn** das Laufprotokoll zeigt, dass G1 aus einer anderen Modellfamilie als R2 stammt. Das ist unbekannt; dann ist G1 nicht unabhängig von R2, und das Urteil lautet nach Plan **„unbelegt“**. Die Zahl ist eine Übereinstimmung des gepoolten Werts mit G1, kein Beleg.

**Zu B3:** Die Wiederholung derselben Rater-Art streut deutlich weniger (3,93) als der Abstand zu F1 auf denselben Karten (7,25). Nach der Lesehilfe des Plans ist ein Teil des Abstands R2–F1 also systematisch und nicht nur Rauschen.

## 6. Lesart des Co-Leads (wörtlich aus #1404 Kommentar 7085556215)

Übernommen ohne Änderung am Wortlaut; nur die Gliederung (Überschriften) kommt hinzu. Fußnoten stehen darunter, außerhalb des Zitats.

**1. Streuung**

> Die zweite Bewertung bestätigt das Niveau der Streuung: Einzelwert ±7,3 bis ±8,7 (je nach Welle), also bleibt „mindestens ±8“ (PR #1760) vertretbar; der gepoolte Wert ist nur dann genauer (bis ±5,5), wenn die Fehler unabhängig sind, was nicht belegt ist. Bis dahin: Anzeige weiter „mindestens ±8“.

**2. Spells-Unterschied und K1**

> Der Spells-Unterschied zwischen den beiden Bewertungen (R2 liegt −4,9 unter F1) ist als Unterschied zwischen den beiden Ratern bestätigt. Daraus folgt NICHT, welcher Rater näher an der Wahrheit liegt (es gibt keine Wahrheit; G1-Vergleich unbelegt). Das Mitteln beider Bewertungen halbiert den Unterschied, ohne eine Seite zu bevorzugen. Eine zusätzliche Korrektur K1 würde die Mitte einseitig verschieben: **kein Vorschlag, K1 nicht anwenden**, solange kein unabhängiger Maßstab vorliegt.

**3. Vorschlag an den Owner**

> Vorschlag an den Owner: Anzeige H_pooled (Mittel beider Bewertungen, ungerundet gespeichert, `n_bewertungen` immer dabei) statt H_F1; Streuung weiter „mindestens ±8“; Rohdaten beider Läufe unverändert; keine Stufenregel für H (existiert nicht). Karten mit |d| ≥ 15 (266) tragen die Marke „Bewertungen weichen stark ab“.

**4. Grenzen**

> Grenzen: Modellfamilie und Dateizugriff der Rater UNKNOWN (nur Selbstauskunft, A3); die 100 Regelclaims wurden von Modell-Instanzen geprüft; Schluss über „besser“ nicht möglich (B2 unbelegt); H_pooled verbessert die Reproduzierbarkeit (ICC 0,82 → vorhergesagt 0,90), nicht nachweislich die Wahrheitsnähe.

Fußnoten (nicht Teil des Zitats):
- Zu Punkt 1 und zum Ergebnis-Kommentar („ohne die 35 markierten Karten wie #1758: 8,1“): Die 8,1 aus #1758 ist **RMS/√2**, also mit Verzerrung. Die Werte ±7,3 bis ±8,7 sind **SD/√2** (ohne Verzerrung). Vergleichbare RMS/√2-Werte dieses Laufs: gesamt 8,46, Welle 1 9,42, Welle 2 7,96 (§3).
- Zu Punkt 2: Nach Plan §6 wäre der K1-Vorschlag erlaubt (§4). Ihn nicht zu machen ist eine Entscheidung des Co-Leads.
- Zu Punkt 3: Der Plan nennt als abgeleiteten Datensatz `data/card_understanding/card_understanding_h_pooled.jsonl`. Dieser PR legt ihn **nicht** an; die gepoolten Werte stehen nur als Analyse-Ergebnis in `second_run_full_20261122/pooled.jsonl`. Der Owner entscheidet über Anzeige und Produktdatensatz.

## 7. Grenzen

- **A3, Familie UNKNOWN:** Modellfamilie von R2 gegenüber F1, G1 und Welle 1 ist unbekannt. Deshalb keine Aussage „unabhängig“ oder „andere Familie“, das gepoolte H heißt „zwei Bewertungen, Unabhängigkeit ungeprüft“, und SE = 5,50 gilt nur unter Unabhängigkeit. Stammen beide aus derselben Familie, senkt das Poolen nur das nicht geteilte Rauschen.
- **Dateizugriff nur Selbstauskunft:** Werkzeuge mit Zugriff außerhalb des Rater-Ordners (einschließlich Web) waren verfügbar. Dass sie nicht genutzt wurden, beruht auf den Schlussantworten; protokolliert ist es nicht (`dateizugriff_protokolliert: false`). Der Text-Scan findet keine Spur, beweist aber keine Blindheit.
- **Regelclaim-Prüfer sind Modell-Instanzen** (zwei frische Instanzen, je 50 Claims, Familie UNKNOWN), blind zur Herkunft, aber nicht nachweislich unabhängig von den Ratern. Maßstab: Kartentext, gezeigte Rulings, Comprehensive Rules (Modellurteil, kein XMage-Lauf). Der Chulane-Text stand in keinem Kartenblock; Claims über Chulane prüften die Prüfer gegen den bekannten Oracle-Text (bei Prüfer 1: 17 Claims). Streng gelesen wären diese „unscharf“, an „falsch 0“ ändert das nichts. Explorativ: alle 4 „unscharf“ (nr 29, 35, 61, 95) stammen aus Welle 2.
- **B2 unbelegt:** Es gibt keinen unabhängigen Maßstab; „besser“ heißt hier höchstens „verlässlicher“ (B1, vorhergesagt), nicht „richtiger“.
- **Länder: kein Schluss** zur Korrektur (12 in Welle 2); +2,85 ist explorativ.
- Zwei Modellurteile sind keine Wahrheit. Beliebtheitswissen eines Modells lässt sich nicht ausschließen; der Scan ist ein Stichwort-Indiz.
- Kontext von 88 bis 89 Karten je Instanz: Ermüdung in den Chargen 2 und 6 auffällig (§2).

## 8. Abweichungen und Unterschiede zu Welle 1

**Gegenüber dem Plan (berichtet, nicht korrigiert; `run_log.json` meldet keine A8-Abweichung):**
1. **Laufprotokoll unvollständig:** Die Tabelle je Charge (Start, Ende, Unterbrechungen, Zeilen, Selbstprüfung, Schlussantwort) und die Zeile „Auswerteskript-Commit“ sind im Scratchpad-Protokoll leer (Plan §2 verlangt Start/Ende je Charge). Ersatzbelege: Freeze-Kommentar (Zeilen, „C True“), Schlussantworten, Merge-Zeit von #1763. In der Repo-Fassung ist das als Lücke benannt, nicht nachgetragen.
2. **Stufe/Aufwand UNKNOWN** (Voreinstellung des Aufrufs, nicht gesetzt).
3. **Schlussantworten im Repo redigiert:** Nur der absolute Rater-Pfad (8 Stellen) ist durch `<RATER_DIR>` ersetzt. Original SHA-256 `f276a7d3…` (gepostet in 7085521227), Repo-Fassung `e831bbca…`. `hits` ergibt aus der Repo-Fassung dieselbe Treffer-Datei `edd99934…`, und `eval` dieselben drei Ergebnis-Dateien (§9).
4. **Formatlücken:** 63 Zeilen erfüllen die Zahlenbedingung; die Rater stuften gleiche Zeilen verschieden ein (§2).

**Gegenüber Welle 1 (#1758):**
- Laufprotokoll vorhanden (Welle 1: keines). Modell, Stufe und Familie bleiben trotzdem ungeprüft.
- Ausgaben vor dem Öffnen eingefroren und gepostet; Auswerteskript vor dem Öffnen committet (Welle 1: beides nicht, Abweichung 2).
- Verweis-Treffer vor jeder Differenz von Hand klassifiziert und gepostet (neu, §9 Schritt 6).
- Regelclaims **blind zur Herkunft**, 50 R2 und 50 F1 gemischt, zwei frische Prüfer-Instanzen (Welle 1: nicht blind, ein Prüfer, nur R2).
- Keine nachträglich ersetzten Zeilen gemeldet (Welle 1: Rater 3 ersetzte zwei Zeilen). Bei N = 1 und N = 2 verwarf die eigene Selbstprüfung je zwei Schreibversuche, bevor etwas geschrieben wurde (Selbstauskunft).
- Guide je Charge mit entfernten eigenen Ankerzeilen (leave-one-anchor-out), 88 bis 89 Karten je Instanz statt 100, dazu Retest-Charge 8.
- Andere Zielgröße: Welle 1 prüfte H gegen G1-Schwellen (M1 bis M8, Urteil „teilweise bestätigt“); dieser Plan bildet das gepoolte H und testet nur die Spells-Verzerrung. Kennzahlen gelten jetzt über alle 922 Karten, einschließlich der 35 markierten (in Welle 1 außerhalb der Primärmenge).
- Die Spells-Verzerrung von Welle 1 (−5,61, explorativ) ist in Welle 2 mit vorab festgelegtem Test bestätigt (−4,87).

## 9. Abweichungen |d| ≥ 15 (266 Karten)

Wie in Welle 1 steht hier nur ein Auszug; die volle Liste mit beiden H, Quelle und **beiden Begründungen** steht in `result.json` (Schlüssel `abweichungen_ge15`, 266 Einträge), die Marken `abweichung_ge15` / `abweichung_ge30` je Karte in `pooled.jsonl`. Je Welle: 93 von 300 (Welle 1), 173 von 622 (Welle 2); je Kartenart: 260 von 857 Spells, 6 von 65 Länder.

Die 22 Karten mit |d| ≥ 30 (alle markiert, keine gelöscht oder ersetzt):

| Karte | Quelle R2 | H_F1 | H_R2 |
|---|---|---|---|
| Assert Perfection | Welle 1, Datei 3 | 50 | 10 |
| Veil of Summer | Welle 2, Charge 2 | 20 | 60 |
| Whirler Rogue | Welle 1, Datei 3 | 70 | 30 |
| Imperious Perfect | Welle 1, Datei 3 | 60 | 25 |
| Lyra Dawnbringer | Welle 1, Datei 2 | 60 | 25 |
| Nature's Claim | Welle 1, Datei 1 | 25 | 60 |
| Shore Lurker | Welle 1, Datei 3 | 50 | 15 |
| Thought Monitor | Welle 1, Datei 3 | 45 | 10 |
| Cat Collector | Welle 1, Datei 3 | 50 | 20 |
| Drogskol Reaver | Welle 1, Datei 3 | 45 | 15 |
| Elspeth, Knight-Errant | Welle 1, Datei 2 | 60 | 30 |
| Faebloom Trick | Welle 2, Charge 1 | 40 | 10 |
| Kappa Cannoneer | Welle 1, Datei 3 | 40 | 10 |
| Merrow Skyswimmer | Welle 1, Datei 3 | 55 | 25 |
| Mistmeadow Council | Welle 2, Charge 2 | 60 | 30 |
| Personify | Welle 1, Datei 1 | 65 | 35 |
| Revoke Existence | Welle 2, Charge 2 | 20 | 50 |
| Ruin Ghost | Welle 1, Datei 1 | 20 | 50 |
| Shimmer Dragon | Welle 1, Datei 2 | 40 | 10 |
| Storm Spirit | Welle 1, Datei 3 | 45 | 15 |
| Viridian Revel | Welle 2, Charge 7 | 5 | 35 |
| Wary Farmer | Welle 1, Datei 2 | 55 | 25 |

## 10. Herkunft und Reproduktion

Alle Dateien unter `data/research/chulane_rubric_v2_20261118/second_run_full_20261122/`; die SHA-256-Liste der in diesem PR neuen Dateien dieses Ordners steht in `results_sha256.txt` (gleicher Ordner, `sha256sum`-Format).

| Datei | Inhalt | SHA-256 (gepostet in) |
|---|---|---|
| `rater/rr2_output_1..8.jsonl` | Rater-Ausgaben, byte-gleich | `rater/output_sha256.txt` (7082408782) |
| `rater/output_sha256.txt` | Freeze-Liste, Eingabe `--checksums` | `cb9b08e0…` |
| `hits.json` | Verweis-Treffer | `edd99934…` (7085521227) |
| `klassifikation.json` | Einstufung der Treffer | `c68777c4…` (7085522996) |
| `claims_blind.json` · `claims_key.json` | blinde Claim-Liste · Herkunftsschlüssel | `a8eea983…` · `6102bd01…` (7085540409) |
| `claim_verdicts.json` | Urteile 1–100 zusammen | `210f2e7f…` (7085540409) |
| `claim_verdicts_pruefer_1.json` · `_2.json` | Urteile Prüfer 1 (nr 1–50) · Prüfer 2 (nr 51–100) | `52e44b78…` · `66b9ffb7…` |
| `run_log.json` | Laufprotokoll-Eingabe für `eval`, ohne Modellnamen | `22c11ed7…` (7085540409) |
| `run_log_redacted.md` | Laufprotokoll ohne Modellnamen und Pfad | `results_sha256.txt` |
| `final_replies_redacted.json` | Schlussantworten, Pfad → `<RATER_DIR>` | `e831bbca…` (Original `f276a7d3…`, 7085521227) |
| `result.json` · `pooled.jsonl` | Ergebnis · gepoolter Datensatz | `3f17940e…` · `3e6d82d0…` (7085556215) |

Nicht im Repo (Scratchpad des Co-Leads, nur SHA-256): Auswerte-Vorlage `report.md` `b002e21b…` (aus dem Repo reproduzierbar), Prüfer-Anweisung `b40c105e…`, Prüfer-Eingaben `1d5205d9…` · `cbd40234…`, Laufprotokoll-Original `e4f57fb3…`.

**Reproduktion aus dem Repo** (Skript `scripts/analysis/rating_second_run_full_eval.py`, SHA-256 `65995883…`, nur Standardbibliothek): Zweimal gelaufen, beide Male byte-gleich mit den gemeldeten SHA-256 (`result.json` `3f17940e…`, `report.md` `b002e21b…`, `pooled.jsonl` `3e6d82d0…`); `hits` ergibt `edd99934…`.

```
D=data/research/chulane_rubric_v2_20261118/second_run_full_20261122
R=data/research/chulane_rubric_v2_20261118
python3 scripts/analysis/rating_second_run_full_eval.py eval --manifest $D/rr2_manifest.json \
  --rater-dir $D/rater --checksums $D/rater/output_sha256.txt \
  --classification $D/klassifikation.json \
  --classification-sha256 c68777c4660c5862cfd955ffba6fb5e74f7092946b372c2d3192893bfae04413 \
  --hits $D/hits.json --run-log $D/run_log.json --final-replies $D/final_replies_redacted.json \
  --wave1-dir $R/second_run_20261122 --f1 $R/fullrun_ratings.jsonl \
  --g1 $R/audit/independent_rater_ratings.jsonl --f2 $R/fulldrift_ratings.jsonl \
  --claim-verdicts $D/claim_verdicts.json --out <result.json> --report <report.md> --pooled-out <pooled.jsonl>
```

Die Rohdaten enthalten nur Kartentext-Blöcke, Kartennamen, `oracle_id`, Bewertungen, Begründungen und Regelclaims; keine Preise, Nutzung, Modellnamen oder privaten Daten.
