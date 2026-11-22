# Vergleichsplan: zweiter, unabhängiger Rater-Lauf („R2“) gegen das bisherige Kartenrating (Chulane, Raster v2.1)

Stand 2026-11-22, **vor** dem Lauf festgelegt. Schwellen, Regeln und Auswertungen unten werden nach dem Öffnen der
Ausgaben nicht geändert; alles, was später dazukommt, heißt „explorativ“. Diese Datei ist Vorbereitung im Scratchpad,
nichts davon ist committet. Nutzungs- und Beliebtheitsdaten werden nicht berührt.

**Owner-Vorgabe: keine Paarvergleiche.** Jeder Rater vergibt je Karte absolute Werte (E, F, T, R, K, D, H); er vergleicht
nie zwei Karten. Alle Größen unten vergleichen die absolute Zahl derselben Karte aus zwei Läufen. Spearman ist die Korrelation
zweier Zahlenreihen, kein Paarurteil; paarbasierte Kennzahlen (Kendall, Turnier- oder Paarwahrscheinlichkeiten) werden nicht verwendet.

## 1. Was verglichen wird

- **Neu:** `rr_output_1..3.jsonl` (300 Karten, ein Lauf von „R2“, Guide v2.1, Eingabe = der Kartenblock des Original-Raters).
- **Bisher:** H und E, F, T, R, K, D je Karte aus `data/card_understanding/card_understanding_v2_1.jsonl` (identisch mit
  `data/research/chulane_rubric_v2_20261118/fullrun_ratings.jsonl`, Rater F1, 922 Karten; Werte 922 von 922 gleich geprüft).
  Es wird erst nach dem Einfrieren der drei Ausgaben (SHA-256 notiert) gelesen.
- **Was die Prüfung kann:** Übereinstimmung zweier Modell-Läufe und mit dem Prüfer (Audit A) messen. **Was sie nicht kann:** Richtigkeit
  beweisen oder Nutzung/Beliebtheit abbilden. „Nicht bestätigt“ heißt „zwei Rater unterscheiden sich“, nicht „F1 falsch“.

## 2. Frühere Läufe und Quellen (Modellfamilien)

Die genauen Modell-IDs stehen **nicht im Repo** (README, PILOT_REPORT Kopf und §11: „im Verlauf der Owner-Session festgehalten“). Bekannt ist nur die Stufe.

| Lauf | Familie / Stufe laut Repo | n | Quelle |
|---|---|---|---|
| **F1** Vollauf (heutiges Rating) | eine Modellfamilie, Stufe „large“; 132 Chargen zu 7 Karten, Guide v2.1 | 922 | `fullrun_ratings.jsonl`; `PILOT_REPORT.md` §9; `README.md` |
| **F2** Drift-Lauf | dieselbe Familie und Stufe wie F1 (`rater_tier` large), gleicher Guide, 7 Chargen zu 7 | 49 | `fulldrift_ratings.jsonl`; `PILOT_REPORT.md` §10 |
| **G1** unabhängiger Rater | **andere Modellfamilie**, hohe bzw. mittlere Stufe (Namen nicht im Repo), Chargen zu 7 | 70 (18 Spitze, 15 Boden, 15 H 40–55, 9 Länder, 13 übrige) | `audit/independent_rater_ratings.jsonl`, `audit/independent_rater_sample.json`; `PILOT_REPORT.md` §11 |
| **Audit A** (Prüfer, kein Rater-Lauf) | zweite Modellfamilie, Handprüfung mit Spanne je Karte (laut Scratchpad `<Audit-Ordner>/` vermutlich dasselbe Modell wie „R2“, siehe 2a) | 230 (+6) → 35 markiert | `audit/AUDIT_A_ratings.md`, `audit/audit_A_flagged.jsonl` |
| **V22** Testlauf Guide v2.2 | Stufe large, ein Lauf, anderer Guide (nicht v2.1) | 70 (35 markierte + 35 Kontrollen) | `audit/guide_v22_test_ratings.jsonl`; `PILOT_REPORT.md` §11 |
| **Audit D** Regelclaims | Handprüfung von F1-Claims | 100 | `audit/AUDIT_D_rule_claims.md` |
| Pilot H1, H2 (kleine Stufe), S1, S2, T1, T2 (große Stufe) | Guide v2/v2.1, nur Pilotkarten | 63 + Retest | `pilot_ratings.jsonl`; `PILOT_REPORT.md` §1–§7 |

**Bekannte Streuung, aus den Rohdateien neu gerechnet** (ΔH = neuer Lauf minus F1; Skripte nicht eingecheckt, Rechnung hier reproduzierbar):

| Vergleich | n | mittl. \|ΔH\| | Verzerrung | SD(ΔH) | RMS | Anteil \|ΔH\| ≥ 15 | Max | Spearman |
|---|---|---|---|---|---|---|---|---|
| F2 gegen F1 (gleiche Familie, Drift) | 49 | 5,10 | −1,2 | 7,11 | 7,14 | 3 von 49 = 6,1 % | 30 | 0,939 |
| G1 gegen F1 (andere Familie) | 70 | 7,86 | −3,7 | 9,73 | 10,35 | 13 von 70 = 18,6 % | 25 | 0,92 |
| V22 gegen F1 (anderer Guide, Kontrolle) | 70 | 12,07 | −9,5 | 12,13 | 15,34 | 27 von 70 | 40 | 0,654 |

Einordnung der genannten Zahlen: „±5 (n=49)“ und „±7,3 (n=70)“ sind beide RMS(ΔH)/√2, die auf einen Einzelwert umgerechnete Streuung: F2 7,14/√2 = 5,05; G1 10,35/√2 = 7,32
(so im Studio-Text zur Streuung verwendet; PILOT_REPORT §10, AUDIT_A §4). Die Tabelle nennt die Rohgrößen (mittlere \|ΔH\| F2 5,10, G1 7,86), weil die Schwellen unten auf \|ΔH\| und RMS der **Differenz** zweier Läufe laufen, nicht auf dem Einzelwert.
AUDIT_A schätzt die Gesamtunsicherheit eines Einzelwerts auf 1σ ≈ 7–8, 90 % ≈ ±12. Die Stichproben von G1 und diesem Lauf
sind an den Rändern überrepräsentiert; dort ist die Streuung größer (F2: H ≥ 50 7,3 gegen H ≤ 25 4,2).

### 2a. Wer ist „R2“? Vorab festgelegte Verzweigung (Quelle: Scratchpad, nicht Repo; unbestätigt)

Das Repo nennt keine Modellnamen. Im Scratchpad der Owner-Session steht: (i) der Ordner `<Audit-Ordner>/` enthält `OUT_audit_A.md`, `OUT_audit_A_flagged.jsonl`, `OUT_claims_D.*`, `OUT_design_C.md`, also die Rohfassungen von Audit A, Audit D und Gutachten C;
(ii) „R2 (Version, Aufwand)“ wird in Review-Notizen als „anderes Modell“ als der Lead-Frischkontext geführt (z. B. `p1723c.md`). Daraus folgt **vermutlich**: Der Prüfer der 35 markierten Karten ist dasselbe Modell wie der neue Rater, und F1 stammt aus einer anderen Familie als R2.
Der Lead bestätigt das im Laufprotokoll, **bevor** die Ausgaben geöffnet werden; „unbekannt“ ist zulässig. Daraus ergeben sich die Zweige:

| Frage | Zweig | Folge für die Auswertung |
|---|---|---|
| Ist R2 der Prüfer von Audit A? | **ja** (oder unbekannt) | Die Prüfer-Spanne ist keine unabhängige zweite Quelle: Die Kennzahl der 35 markierten Karten (Abschnitt 7) heißt „Selbstkonsistenz mit dem eigenen Audit“ und darf nicht als unabhängige Bestätigung gelesen werden. Unabhängige Evidenz gegen F1 an den Rändern liefern dann nur G1 (andere Familie, 70 Karten) und die Größe der Abweichung in der Primärmenge. |
| | nein | Abschnitt 7 gilt wie geschrieben (zwei unabhängige Modellurteile). |
| Familie von R2 gegenüber F1? | **andere Familie** (Erwartung) | Referenz G1; Schwellen M1 bis M8 wie in Abschnitt 6 (an G1 und F2 gebunden). |
| | **gleiche Familie wie F1** | Referenz F2 (Wiederholstreuung). Strengere Schwellen, grün/rot: M1 ≤ 6,5 / > 8,0; M2 ≤ 8,5 / > 11; M3 ≤ 10 % / ≥ 20 %; M4 ≥ 0,92 / < 0,86; M5 wie in Abschnitt 6; M6 \|v\| ≤ 3 / > 5; M7 ≥ 80 % / < 70 %; M8 ≥ 93 % / < 88 %. |
| | unbekannt | Die G1-Schwellen gelten; der Bericht sagt, dass die Familie ungeprüft ist (Regel A3). |

## 3. Stichprobe (n/N, `rr_sample_manifest.json`, Skript `rr_make_sample.py` (Neuerzeugung braucht einen Checkout von Commit 138a50c264f2), Seed 20261122)

N = 922 Karten, Stand Commit `138a50c264f2`. Geschichtet, deterministisch, in der Reihenfolge Prüfer-Marken, Spitze, Rest, Länder, Auffüllung gezogen; Schnittmengen so bereinigt, dass jede Karte genau einmal vorkommt.

| Schicht | n | Definition | Pool (N) |
|---|---|---|---|
| `flagged` | 35 | alle 35 Karten aus `audit_A_flagged.jsonl` (26 „H zu hoch“, 7 „zu niedrig“, 2 „Begründung faktisch falsch“); 23 davon liegen im Top-20-%-Band, 3 sind Länder | 35 von 35 |
| `top20` | 100 | zufällig aus den oberen 20 % von H (Rang 185 von 922, Schnitt bei H = 45; 17 der 56 Karten mit H = 45 per Seed in die Spitze gezogen), ohne markierte Karten, Länder, Ankerkarten | 100 von 132 |
| `rest` | 100 | zufällig aus der restlichen Menge (nicht Top 20 %, kein Land, nicht markiert, keine Ankerkarte) | 100 von 663 |
| `land` | 50 | **alle** übrigen Länder (nicht markiert, keine Ankerkarte) | 50 von 50 |
| `rest_fill` | 15 | Auffüllung auf 300 (es gibt nur 50 zulässige Länder, nicht 65): zufällig aus dem Rest-Pool, ohne die 100 `rest` | 15 von 563 übrig |
| **Summe** | **300** | | |

Auswertung führt `rest` und `rest_fill` als eine Schicht „Rest“ (115). Auf die drei Dateien sind die Schichten reihum verteilt: je 100 Karten;
Datei 1: 12 markiert, 33 Spitze, 34 Rest, 16 Länder, 5 Auffüllung; Datei 2: 12/33/33/17/5; Datei 3: 11/34/33/17/5. Reihenfolge je Datei zufällig.

**Abweichungen vom Auftrag, bitte ansehen:**
1. **Ankerkarten (46 Karten stehen in den Guide-Ankertabellen) sind aus den zufälligen Schichten ausgeschlossen** (42 Karten; darunter 12 der 13 Anker-Länder und rund 23 Karten der Spitze, z. B. Sol Ring, Path to Exile, Swords to Plowshares). Grund: Der Rater sähe sonst
   den festen Ankerwert genau der Karte, die er bewertet (verletzt die Blindheit). Deshalb gibt es nur 50 statt 65 Länder und die Spitze wird aus 132 statt 185 Karten gezogen; die allerhöchsten H-Werte (Anker) sind so nicht im Test.
2. Vier markierte Karten sind selbst Anker (Command Tower, Counterspell, Primeval Bounty, Reclamation Sage). Sie bleiben (Auftrag: alle 35), werden aber aus den Ankertabellen des an den Rater gehenden Guides entfernt
   (derselbe leave-one-anchor-out-Mechanismus wie im Original; `rr_guide_v2_1_rendered.md` hat für alle drei Dateien denselben Guide). Der Original-Rater sah bei Reclamation Sage und Primeval Bounty den eigenen Anker in der Tabelle.
3. 100 Karten je Rater-Aufruf statt 7 je Charge: Querbeeinflussung innerhalb einer Datei (Anker-Effekt, Ermüdung) ist möglich und wird in 8. M gemessen.

## 4. Eingabe, Ausgabe, Durchführung

- **Eingabe:** `rr_input_N.jsonl`: je Zeile `seq`, `oracle_id`, `card`, `card_block` (der gerenderte Kartenblock des Original-Raters, `render_prompt.card_block`: Name, Kosten, Typ, Oracle-Text aller Seiten, Rollen, Castability, Peers, Combo-Hinweis, Rulings, Mustertreffer).
  Nie enthalten: bisheriges H oder E–D, Notizen, Begründungen, Markierungen, Schichten, Nutzung, Preise, Beliebtheit.
- **Ordner:** alles, was der Rater lesen oder schreiben darf, liegt in `rr/rater/` (`rr_rater_instructions.md`, `rr_guide_v2_1_rendered.md`, `rr_input_1..3.jsonl`, `rr_output_schema.json`, später `rr_output_1..3.jsonl`). Manifest, Plan und `rr_make_sample.py` (Analystendateien, nennen Schichten und markierte Karten) liegen eine Ebene darüber in `rr/`; dem Rater nur den Pfad `rr/rater/` geben.
- **Guide/Systemteil:** `rr_guide_v2_1_rendered.md` (GUIDE_v2.md v2.1, Ankertabellen in Vielfachen von 5, Ausgaberegeln, wie `make_batches.py` den Systemteil rendert).
- **Anweisung:** `rr_rater_instructions.md`; Ausgabe `rater/rr_output_N.jsonl`, eine JSON-Zeile je Karte (Schema `rubric-v2-card-rating-1`, `rr_output_schema.json`), nach jeder 10. Karte angehängt.
- **Aufruf (Vorschlag):** drei frische Subagenten, je Datei einer, gleiche Modellstufe und gleicher Aufwand, ein Satz im Auftrag: „Du bist Rater N=k. Lies `.../rr/rater/rr_rater_instructions.md` und folge ihr.“ Kein weiterer Kontext, keine Beispiele aus dem Repo.
  Laufprotokoll `rr_run_log.md` (Lead): Modell-ID, Stufe/Aufwand, Datum, Werkzeuge/Dateizugriff des Subagenten, Unterbrechungen, Wiederaufnahmen.
- **Einfrieren:** Nach Ende `sha256sum rr_output_*.jsonl` ins Protokoll; erst dann den Vergleich starten (das Auswerteskript wird aus diesem Plan geschrieben und festgeschrieben, bevor die Ausgaben geöffnet werden).

## 5. Gültigkeit und Abdeckung der 7 Kriterien (zuerst gerechnet)

Eine Karte ist **gültig**, wenn: Zeile parst, `oracle_id` und `card` stimmen mit der Eingabezeile gleicher Position überein, `scores` enthält genau E, F, T, R, K, D, H als ganze Zahlen 0 bis 100, `notes` hat alle sieben
Schlüssel, `reason`, `confidence`, `uncertainty` (Regel: nur bei high leer) vorhanden. Gemeldet werden zusätzlich: Anteil Vielfache von 5 (Soll 100 %; Original-Vollauf 922 von 922), `pattern_check` deckt alle gezeigten Treffer ab,
Anteil `quote` wörtlich im Kartenblock oder Chulane-Text (Normalisierung wie `scripts/quote_check.py`, „ws“; Original 1706 von 1708 = 99,9 %).
Nicht-Vielfache von 5 werden für die Rechnung halb nach oben gerundet (wie `import_card_understanding.py`) und gezählt.

| Nr | Kennzahl | grün | rot |
|---|---|---|---|
| V1 | gültige Karten (von 300) | ≥ 297 (99 %) | < 270 (90 %), siehe Abbruchregel A1 |
| V2 | alle 7 Werte je Karte vorhanden | 100 % der gültigen | < 95 % |
| V3 | Vielfache von 5 | ≥ 99 % der Karten | < 95 % (Formatbruch, A5) |
| V4 | Zitate wörtlich (Kartenblock + Chulane-Text) | ≥ 98 % (Vorab-Schwelle 8a) | < 90 % |

## 6. Vorab festgelegte Hauptkennzahlen (Rater gegen F1, ΔH = H_neu − H_alt)

Primärmenge für das Urteil „Niveau und Rang“: die **265 nicht markierten Karten** (Spitze 100, Rest 115, Länder 50), da die markierten ausgewählt sind, weil F1 dort falsch liegen soll.
Alle Intervalle: Bootstrap über Karten innerhalb der Schicht, 5000 Ziehungen, Seed 20261122, 95 %. Immer n angeben. Gepoolte Werte sind **Stichprobenwerte, keine Poolschätzung**; zusätzlich ein gewichteter Wert
mit Gewicht N_h/n_h je Schicht (Spitze 132/100, Rest 663/115, Länder 50/50; markierte und Anker-Karten außerhalb).

| Nr | Kennzahl (Primärmenge, falls nicht anders angegeben) | grün | gelb | rot | Referenz |
|---|---|---|---|---|---|
| M1 | mittlere \|ΔH\| | ≤ 8,0 | 8,0 bis 11,0 | > 11,0 | F2 5,10; G1 7,86 |
| M2 | RMS(ΔH) | ≤ 10,5 | 10,5 bis 14 | > 14 | F2 7,14; G1 10,35 |
| M3 | Anteil \|ΔH\| ≥ 15 | ≤ 20 % | 20 bis 30 % | ≥ 30 % | F2 6,1 %; G1 18,6 % |
| M4 | Spearman ρ(H_neu, H_alt) | ≥ 0,88 | 0,80 bis 0,88 | < 0,80 | F2 0,939; G1 0,92 |
| M5 | Steigung der Geraden H_neu auf H_alt (OLS; Auswahl nach H_alt verzerrt die Steigung nicht, die Regression zur Mitte zeigt sich als Steigung unter 1) | 0,80 bis 1,10 | 0,65 bis 0,80 oder 1,10 bis 1,25 | < 0,65 oder > 1,25 | (neu) |
| M6 | Verzerrung (mittlere ΔH) in **Rest + Länder** (165 Karten) | \|v\| ≤ 5 | 5 bis 8 | > 8 | F2 −1,2; G1 −3,7 |
| M7 | gleiches Guide-Band von H (95–100, 72–94, 50–71, 28–49, 5–27, 0–4) | ≥ 65 % | 55 bis 65 % | < 55 % | F2 91,8 %; G1 68,6 % |
| M8 | gleiche Seite der Grenze H ≥ 50 (Rang-/Bandübereinstimmung „gut gespielt“) | ≥ 88 % | 80 bis 88 % | < 80 % | F2 95,9 %; G1 91,4 % |

Verzerrung je Schicht (M6-Art) wird für `top20` gesondert berichtet und **nicht** bewertet: Wegen der Auswahl nach hohem F1-H ist ein negatives ΔH dort teils Regression zur Mitte, teils die vom Audit A gefundene zu großzügige Spitze (Audit: „gestauchte“, zu hohe Spitze, 20 von 100 zweifelhaft).
Lesehilfe: Bias(top20) zwischen −10 und 0 ist mit Regression plus mäßiger Großzügigkeit vereinbar; unter −10 stützt eine systematische Überbewertung der Spitze durch F1; über 0 spricht gegen die Überbewertung.
Zusätzlich je Schicht: n, Mittel, SD, Median, mittlere \|ΔH\|, RMS, Anteil ≥ 15, Maximum, die größten 10 Abweichungen mit Karte und beiden Begründungen (nur zum Lesen).

**Vergleich gegen die bekannte Streuung (vorab):** mittlere \|ΔH\| der Primärmenge (M1) wird so gelesen:
- ≤ 6,5: nicht von der Wiederholstreuung desselben Modells (F2: 5,1; Intervall 3,9 bis 6,5) zu unterscheiden → „bestätigt im Rahmen der Wiederholstreuung“.
- 6,5 bis 8,0: wie die Familien-Abweichung G1 (7,86) → „bestätigt im Rahmen der Modellfamilien-Streuung“.
- 8,0 bis 11,0: mehr als jede bekannte Streuung → Richtung und Schicht ansehen, kein Urteil über Verwendung.
- über 11,0: deutlich größer als die Streuung von G1 (RMS 10,35 entspricht etwa \|ΔH\| 8) → „nicht bestätigt“.
Die Einzelstreuung je Karte ist ohnehin etwa 5 (Wiederholung) bis 7–8 (1σ, Audit A §4); ein einzelnes ΔH unter 10 wird nie als Abweichung einer Karte gelesen.

## 7. Teilkriterien und die 35 markierten Karten

**Teilkriterien** (E, F, T, R, K, D, je Primärmenge): mittlere \|Δ\|, Verzerrung, Spearman, ICC(2,1) mit F1. Grün: ICC ≥ (ICC von G1 − 0,05) für alle sechs
(G1: E 0,87, F 0,94, T 0,82, R 0,92, K 0,92, D 0,91; F2: E 0,92, F 0,96, T 0,92, R 0,95, K 0,95, D 0,87, H 0,93; Quelle `PILOT_REPORT.md` §10, §11); rot: irgendein ICC < (ICC G1 − 0,15). Dazwischen gelb. H-ICC wird zusätzlich gemeldet.
Bei Läufen mit nur 6 von 7 Werten pro Karte (Abdeckung < 100 %) gilt V2.

**Markierte Karten** (n = 35, `audit_A_flagged.jsonl`: Rater-H, Prüfer-Spanne `proposed_H_low` bis `proposed_H_high`, `kind`). Kennzahlen:
(a) H_neu innerhalb der Prüfer-Spanne (k von 35; Referenz: F1 selbst 2 von 35, V22-Testlauf 20 von 35);
(b) H_neu näher an der Spanne als H_alt (k von 35; V22: 27 von 35);
(c) mittlere ΔH getrennt für 26 „zu hoch“ (erwartet negativ), 7 „zu niedrig“ (erwartet positiv, n klein, nur beschreibend), 2 „Begründung faktisch falsch“ (nur beschreibend);
(d) Kontrolle gegen Regression zur Mitte: mittlere ΔH der 26 „zu hoch“ minus mittlere ΔH der 100 nicht markierten Spitzenkarten (gleiches Band, andere Auswahl).
Urteil: **„R2 stützt die Prüfer“**, wenn (a) ≥ 14 von 35 **und** (d) ≤ −5; **„stützt nicht“**, wenn (a) ≤ 7 von 35 **und** (b) ≤ 17 von 35; sonst **„teilweise“**.
Gilt der Zweig „R2 ist der Prüfer“ (Abschnitt 2a), ist das Urteil „stützt“ nur ein Selbstkonsistenz-Befund. Lesehilfe: Stützen heißt, zwei unabhängige Modell-Urteile (Prüfer, R2) liegen gleichgerichtet gegen F1; die Spanne des Prüfers ist selbst nur eine Meinung (1σ ≈ 7–8). Nicht stützen heißt nicht, dass der Prüfer falsch lag.

## 8. Regelclaims, Blindheit, Ermüdung

- **K. Regelclaims:** alle `rule_claims` der 300 Karten werden gezählt (Original: 1708 auf 922 Karten, im Mittel 1,85 je Karte). Automatisch: V4. Von Hand: **100 zufällige Claims** (`random.Random(20261123)`, höchstens 1 je Karte, bevorzugt wie Audit D
  mit Interaktionsbezug zu Chulane, Bounce, Landfall, Trigger, Symmetrie, Timing; reine Typzeilen-Claims einzeln mitzählen, aber getrennt ausweisen). Prüfer sieht nur Kartenblock und Claim, **nicht**, von welchem Lauf er stammt; Maßstab Kartentext, gezeigte Rulings, Comprehensive Rules (kein XMage-Lauf).
  **Offensichtlich falsch** = widerspricht dem Kartentext, einem gezeigten Ruling oder den Comprehensive Rules eindeutig; „unscharf“ und „offen“ zählen nicht dazu und werden getrennt berichtet. Grün: ≤ 3 von 100 falsch; gelb 4 bis 7; rot ≥ 8.
  Referenz: Audit D F1 0 von 100 (Wilson 96,3 bis 100 %), Pilot 1 falsch von 40.
- **L. Blindheits-Scan:** Stichwortliste aus `scripts/full_qa.py` (`popular|staple|edhrec|commonly played|budget|cedh|played in (most|many)`) über `notes`, `reason`, `uncertainty`, `claim`; jeder Treffer von Hand lesen (Verneinungen wie „not a staple“ und harmlose Wörter zählen nicht).
  Grün: ≤ 2 % der Ausgaben (≤ 6 von 300) echte Beliebtheitsaussagen; rot: > 5 %. Referenz F1: 3 von 922 echt. Zusätzlich Suche nach Verweisen auf frühere Zahlen („earlier rating“, „previous“, „v1“, „F1“, „audit“, „tier list“): jeder Treffer verletzt die Blindheit (Regel A2).
- **M. Reihenfolge/Ermüdung:** je Datei mittlere \|ΔH\| der Positionen 1 bis 50 gegen 51 bis 100 und Spearman(Position, ΔH). Auffällig: Differenz > 3 oder \|ρ\| > 0,2. Folge: berichten, die Dateihälften getrennt ausweisen; kein automatischer Abbruch.
- **N. Skalenverteilung:** SD und Modalanteil von H_neu (F1 im ganzen Pool: SD 18,8, Mittel 30,7, größter Gleichstand 108 von 922 = 11,7 %; für A4 zählt die SD von H_alt auf denselben Karten). Siehe Abbruchregel A4.

## 9. Gesamturteil (vorab festgelegt)

Das Gesamturteil bezieht sich auf **Niveau und Rang** (M1 bis M8 in der Primärmenge) und wird nur gefällt, wenn keine Abbruchregel greift.

| Urteil | Bedingung |
|---|---|
| **Bestätigt** | M1 bis M5 alle grün, kein rot bei M6 bis M8, V1 bis V4 grün, Regelclaims nicht rot, Blindheit nicht rot |
| **Teilweise bestätigt** | kein rot bei M1 bis M5, aber mindestens ein gelb oder ein rot bei M6 bis M8, V2 bis V4, Regelclaims oder Blindheit: dann nennen, in welcher Schicht oder Klasse (Spitze, Länder, Rest; Karten ohne Chulane-Funktion; Einmal-Bounce; „zweite Karte“-Zähler, die drei vom Audit A genannten Verzerrungen) die Abweichung liegt |
| **Nicht bestätigt** | mindestens ein rot bei M1 bis M5 |

Daneben stehen getrennt: die Aussage zu den 35 markierten Karten (Abschnitt 7), die Regelclaim-Fehlerrate und die Blindheit. Ein „nicht bestätigt“ oder „stützt die Prüfer“ ist keine Entscheidung über die Verwendung der Ratings im Studio;
die liegt beim Owner (PILOT_REPORT §9, §11). Bei „nicht bestätigt“ ist der nächste Schritt eine Adjudikation einzelner Klassen (ein dritter Blick mit Begründung je Karte), nicht ein dritter Voll-Lauf; ohne Owner-Freigabe kein weiterer Lauf.

## 10. Abbruch- und „Kein Schluss“-Regeln

| Nr | Auslöser | Folge |
|---|---|---|
| A1 | weniger als 270 von 300 gültige Karten; oder in einer Schicht weniger als 70 % gültig | kein Gesamturteil bzw. kein Urteil über diese Schicht; fehlende Karten genau einmal mit derselben Anweisung nachlaufen lassen (Wiederaufnahme ab Karte k+1, nie einzelne Karten neu bewerten oder auswählen) |
| A2 | Blindheitsverstoß: der Subagent hat nach Protokoll oder Ausgabe Repo, andere Dateien, Web oder frühere Zahlen benutzt | die betroffene Datei ist ungültig; ein Wiederholungslauf mit frischem Subagenten; ein zweiter Verstoß: **Abbruch, „kein Schluss“** |
| A3 | Modell-ID, Aufwand/Stufe oder Dateizugriff des Laufs nicht protokolliert | Zahlen werden berichtet, aber keine Aussage „unabhängige zweite Modellfamilie“ |
| A4 | Skalenstauchung: SD(H_neu) < 0,6 × SD(H_alt), beide über dieselben gültigen Karten der Primärmenge (nicht gegen die 18,8 des ganzen Pools: die Stichprobe ist nach H geschichtet), oder mehr als 40 % der Karten mit demselben H | keine Aussagen zu Niveau und Verzerrung (M1, M2, M3, M6); nur Rang (M4, M8) und Klassen |
| A5 | Formbruch: mehr als 5 % der Karten mit Nicht-Vielfachen von 5, fehlenden Kriterien oder falscher `oracle_id` | Bericht „Formatfehler“, Rundung halb nach oben nur für M-Kennzahlen, die betroffenen Karten ausweisen; Nachlauf nur auf Owner-Wunsch |
| A6 | Dateieffekt: mittlere \|ΔH\| zweier Dateien unterscheidet sich um mehr als 4 | je Datei einzeln berichten, kein gepooltes Gesamturteil |
| A7 | ein Subagent bricht ab (Limit, Fehler), Datei < 50 Karten | Wiederaufnahme nach A1; läuft sie wieder aus, „kein Schluss“ für diese Datei |
| A8 | Schwellen, Schichten oder Metriken müssten nach dem Öffnen geändert werden | nicht ändern: Lauf als „nicht nach Plan“ kennzeichnen, geänderte Auswertung explorativ nennen |

Nicht ausgewertet wird: Nutzung, Beliebtheit, Preise, Referenzdeck. `usage_holdout.jsonl` wird nicht geöffnet.

## 11. Grenzen (jetzt schon bekannt)

- Ein Lauf je Karte, ein Rater je Datei: Sampling-Streuung des neuen Modells ist nicht getrennt von der Modellunterschiedlichkeit (die 5 aus F2 ist nur die Wiederholstreuung der F1-Familie).
- Die Stichprobe ist an den Rändern überrepräsentiert und schließt Ankerkarten aus; gepoolte Zahlen sind keine Poolschätzung (gewichteter Wert nur ergänzend).
- 100 Karten pro Aufruf statt 7: Kontexteffekte möglich. Drei Subagenten, drei Kontexte: Dateieffekt möglich (A6).
- Der Prüfer (Audit A) und R2 sind beide Modellurteile; eine Übereinstimmung beider ist keine Wahrheit.
- Modell-Vorwissen über Beliebtheit lässt sich nicht ausschließen (Scan L ist ein Stichwort-Indiz).
- Die Schwellen sind Urteile, abgeleitet aus F2 und G1; sie sind vor dem Lauf festgelegt, nicht aus dem Lauf.
