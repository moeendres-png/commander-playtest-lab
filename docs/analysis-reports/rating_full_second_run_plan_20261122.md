# Kartenverständnis H: Vorab-Plan für die zweite Bewertung der übrigen 622 Karten und das gepoolte H (Chulane, Raster v2.1, 2026-11-22)

- **Stand:** Branch `docs/rating-full-second-run-plan-1404`, gebaut auf `main` @ `3037a425d`. Refs #1404 (Owner-Entscheid in Kommentar 7081544721: „stell einfach sicher, dass das Rating der Karten möglichst gut ist“). F1-Werte, Fakten, Muster, Anker und Guide sind seit dem Stichproben-Commit `138a50c264f2` von Welle 1 unverändert (`git diff` leer; die 300 Kartenblöcke von Welle 1 rendern heute byteweise gleich, das Skript prüft das).
- **Was festgelegt wird:** wie die zweite Bewertung der übrigen 622 Karten (**Welle 2**) erzeugt, eingefroren, geprüft und mit der ersten Bewertung F1 zu einem **gepoolten H** verrechnet wird, und wann eine Korrektur der systematischen Verzerrung nach Kartenart **vorgeschlagen** wird. Dieser Plan steht im Repo, **bevor** eine Ausgabe von Welle 2 existiert. Schwellen und Regeln werden nach dem Öffnen nicht geändert (A8); alles Spätere heißt „explorativ“.
- **Wirkung dieses PR:** keine. Produktcode, H, Stufen, Tierliste und Anzeige bleiben unverändert. Keine Ergebnisse, nur Plan, Eingabe-Skript, Tests und die Eingabedateien.
- **Keine Paarvergleiche** (Owner-Vorgabe): Jede Bewertung ist ein absoluter Wert je Karte; verglichen werden nur zwei absolute Werte **derselben** Karte. Spearman und ICC sind Kennzahlen zweier Zahlenreihen, kein Paarurteil zwischen Karten.
- **Modellnamen** stehen nicht im Repo. Die Rater heißen hier „R2“ (zweite Bewertung), Welle 1 = PR #1758, Welle 2 = dieser Plan; das Laufprotokoll mit Modell-ID bleibt im Scratchpad des Co-Leads (§2).

## 0. Kurzfassung der Regeln

1. **Gepooltes H** = Mittel aus F1 und R2, **nur** für Karten mit zwei gültigen Bewertungen (`n_bewertungen = 2`); sonst H_alt (= F1) mit `n_bewertungen = 1` und Marke. Ungerundet gespeichert (Vielfache von 2,5). Rohdaten bleiben unverändert.
2. **Streuung** aus den Paardifferenzen d = H_R2 − H_F1: Einzelwert σ₁ = SD(d)/√2, Standardfehler des gepoolten Werts SD(d)/2; immer mit n/N.
3. **„Besser“** heißt: (a) vorhergesagt, Spearman-Brown aus ICC(2,1); (b) **belegt nur durch G1** (vorhandener unabhängiger Lauf, 70 Karten), und nur wenn das Laufprotokoll zeigt, dass G1 aus einer anderen Familie als R2 stammt; sonst „unbelegt“. Die optionale Retest-Charge 8 wiederholt nur R2 und liefert ausschließlich die Test-Retest-Stabilität von R2 (beschreibend), nie einen Beleg für „besser“.
4. **Bias-Korrektur nach Kartenart** wird nur **berichtet und dem Owner vorgeschlagen**, nie still angewendet. Bestätigungstest ausschließlich auf den neuen Spells aus Welle 2 (die −5,6 aus Welle 1 waren explorativ). Für Länder gilt „kein Schluss“, weil Welle 2 nur 12 Länder enthält.
5. **|ΔH| ≥ 15:** markieren, nie löschen, nie durch eine Einzelbewertung ersetzen.
6. Abbruch- und „Kein-Schluss“-Regeln A1 bis A11 (§8). Das **Auswerteskript** kommt in einen eigenen PR und wird committet, **bevor** eine Ausgabe geöffnet wird (§9).

## 1. Ausgangslage (Welle 1, PR #1758, Bericht `docs/analysis-reports/rating_second_run_20261122.md`)

| Kennzahl Welle 1 (R2 gegen F1) | Wert | n/N |
|---|---|---|
| mittlere \|ΔH\| (nicht markierte Karten) | 8,38 [7,45; 9,30] | 265 von 922 |
| RMS(ΔH) · Einzelwert-Streuung RMS/√2 | 11,45 · **8,1** [7,3; 8,9] | 265 |
| Spearman ρ | 0,881 [0,848; 0,907] | 265 |
| Verzerrung Spells (explorativ) | −5,61 [−7,16; −4,14] | 215 |
| Verzerrung Länder | +2,30 [+0,60; +4,10] | 50 |
| Dateieffekt (mittlere \|ΔH\| je Datei) | 6,59 · 8,41 · 10,11 (Verzerrung −2,4 · −3,6 · −6,3) | 88 · 88 · 89 |
| Familie von R2 gegenüber F1 | **ungeprüft (A3)**, kein Laufprotokoll | – |

Lehren aus Welle 1, hier als Regeln übernommen: Laufprotokoll vor dem Start (A3), SHA-256 der Ausgaben vor dem Öffnen, Auswerteskript vor dem Öffnen (Abweichung 2), Rater-Ordner ohne Analystendateien in der Nähe (Zugriff UNKNOWN), Menge für den Dateieffekt festgelegt (Abweichung 7), Regelclaim-Prüfung blind zur Herkunft (Abweichung 6).

## 2. Eingaben (Skript `scripts/analysis/rating_second_run_full_inputs.py`)

- **Menge:** alle 922 Karten minus die 300 von Welle 1 (`second_run_20261122/rr_sample_manifest.json`) = **622 Karten** (geprüft: disjunkt, Summe 922). Zusammensetzung: 30 Anker-Spells und 12 Anker-Länder (Karten in den Ankertabellen des Guides, nicht markiert), 32 Karten der Spitze (obere 20 % von H_F1, nach derselben Regel wie Welle 1 neu gebildet, Gleichstandsziehung mit dem Seed 20261122 von Welle 1 nachgebaut), 548 übrige Spells. Keine weiteren Länder (alle 50 nicht-Anker-Länder und die 3 markierten Länder liegen in Welle 1). Nach Welle 2 sind **alle 65 Länder** zweimal bewertet.
- **Chargen:** 7 Chargen zu höchstens 100 Karten (6 × 89, 1 × 88). Jede Schicht reihum über die Chargen verteilt (Reihenfolge: Anker-Länder, Anker-Spells, Spitze, Rest; ein laufender Zähler), danach Reihenfolge innerhalb jeder Charge gemischt. Seed **20261124** (`random.Random`, neu; Welle 1 nutzte 20261122 und 20261123). Je Charge 6 Ankerkarten.
- **Charge 8 (optional, Retest):** 50 nicht markierte Karten aus Welle 1 (20 Spitze, 20 Rest, 10 Länder, Seed wie oben), mit dem **byteweise gleichen** Guide und Kartenblock wie in Welle 1. Sie dient nur der Wiederholstreuung von R2 (§7), **geht nie in H_pooled ein** und ist für die 622 nicht nötig. Ob sie läuft, entscheidet der Co-Lead vor dem Start (Laufprotokoll).
- **Eingabeform:** gleich Welle 1: je Zeile `seq`, `oracle_id`, `card`, `card_block` (`render_prompt.card_block`). Nie enthalten: H oder E–D aus F1, Notizen, Begründungen, Schichten, Marken, Nutzung, Preise.
- **Guide je Charge:** `rr2_guide_k.md` = Systemtext von Guide v2.1 wie in Welle 1, aber die Ankerkarten **dieser** Charge aus den Ankertabellen entfernt (leave-one-anchor-out je Charge; Welle 1 und F1 nutzten denselben Mechanismus). Das Manifest nennt je Charge die entfernten Karten und die entfernten Ankerzeilen je Kriterium (von 122 Zeilen höchstens 5 je Kriterium). Geprüft: Kein Kartenname einer Charge steht in ihren Ankertabellen (Ganzwort-Suche, damit kurze Namen nicht in Wörtern treffen); Treffer in der Guide-Prosa würden im Manifest gelistet (es gibt keine).
- **Anweisung:** `rr2_rater_instructions.md` = Anweisung von Welle 1, geändert nur in N (1 bis 8), der Kartenzahl C je Charge, den Dateinamen (`rr2_…`, Guide je N), „nach jeder 10. **und nach der letzten** Karte anhängen“ und der Schlussprüfung „C True“. Die Repo-Kopie enthält statt des Pfads `<RATER_DIR>`; die Scratchpad-Kopie den echten Pfad. Prüfbar aus dem Repo: Die Welle-1-Anweisung liegt redigiert (Pfad durch `<RATER_DIR>` ersetzt, sonst unverändert) als `second_run_full_20261122/wave1_rr_rater_instructions_redacted.md` bei, das Diff zur Welle-2-Anweisung als `instructions_wave1_vs_wave2.diff`; ein Test erzeugt das Diff neu und vergleicht.
- **Ordner:** Repo-Kopie unter `data/research/chulane_rubric_v2_20261118/second_run_full_20261122/` (`rr2_manifest.json` + `rater/`). Für den Lauf erzeugt dasselbe Skript eine Kopie in einen Rater-Ordner, dessen Elternordner **nichts außer** `rater/` enthält; Manifest, Plan, Laufprotokoll und Welle-1-Daten liegen anderswo. Eingaben, Guides und Schema der Lauf-Kopie sind byteweise gleich der Repo-Kopie (SHA-256 je Datei im Manifest).
- **Aufruf je Charge:** frischer Subagent ohne Vorkontext, eine Charge je Instanz, gleiche Modell-ID, Stufe und Aufwand für alle Chargen und möglichst wie in Welle 1; ein Satz: „Du bist Rater N=k. Lies `<Rater-Ordner>/rr2_rater_instructions.md` und folge ihr.“
- **Laufprotokoll (Pflicht, sonst A3):** Modell-ID, Stufe/Aufwand, gleiche Modell-ID wie Welle 1 ja/nein/unbekannt, Familie gegenüber F1 und gegenüber G1, Werkzeuge und technisch möglicher Dateizugriff, Start/Ende, Unterbrechungen und Wiederaufnahmen je Charge, Schlussantwort jedes Raters. Bleibt im Scratchpad; im Repo nur eine Fassung ohne Modellnamen („gleiche/andere Familie als F1, G1, Welle 1“).
- **Einfrieren:** nach Ende aller Chargen `sha256sum rr2_output_*.jsonl` ins Protokoll **und** als Kommentar in #1404, bevor irgendeine Ausgabe geöffnet wird. **Jede** spätere Ausgabe (A1/A7-Nachholung, A2-Wiederholung) wird genauso eingefroren: ihr SHA-256 steht in #1404, **bevor** das committete Auswerteskript sie liest. Ungefrorene Ausgaben liest das Auswerteskript nicht (sie zählen als fehlend, `n_bewertungen = 1`).

## 3. Gültigkeit einer Bewertung (wie Welle 1, Plan §5)

Eine R2-Zeile ist **gültig**, wenn sie parst, `oracle_id` und `card` mit der Eingabezeile gleicher Position übereinstimmen, `scores` genau E, F, T, R, K, D, H als ganze Zahlen 0 bis 100 enthält, `notes` alle sieben Schlüssel hat und `reason`, `confidence`, `uncertainty` vorhanden sind. Nicht-Vielfache von 5 werden halb nach oben gerundet und gezählt (A5). Die F1-Bewertung gilt für alle 922 Karten als gültig (Vollauf, im Bericht #1758 geprüft). Gemeldet werden zusätzlich V1 bis V4 wie in Welle 1 (gültig, alle 7 Werte, Vielfache von 5, Zitate wörtlich), je Charge und gesamt.

## 4. Gepooltes H

| Feld | Regel |
|---|---|
| `H_pooled` | (H_F1 + H_R2) / 2, ungerundet (Vielfache von 2,5), wenn F1 **und** R2 gültig; sonst H_F1 |
| `n_bewertungen` | 2 oder 1 |
| `quelle_R2` | `welle1` (300 Karten, `rr_output_1..3`) oder `welle2:k` (Charge 1 bis 7) |
| Marken | `nur_erstbewertung` (mit Grund: fehlt, ungültig, Charge ausgeschlossen nach A2/A4); `abweichung_ge15` (\|d\| ≥ 15); `abweichung_ge30` (\|d\| ≥ 30); `charge_auffaellig` (A6) |
| Teilkriterien | E bis D werden im abgeleiteten Datensatz genauso gepoolt; angezeigt wird nur H |

- R2 aus der Retest-Charge 8 geht **nie** in `H_pooled` ein (sonst hätten 50 Karten drei Bewertungen und die Streuung je Karte wäre uneinheitlich).
- Ein dritter Wert, eine Adjudikation oder eine Auswahl „der bessere der beiden“ ist nicht Teil dieses Plans.
- **Rohdaten unverändert:** `card_understanding_v2_1.jsonl`, `fullrun_ratings.jsonl`, `rr_output_*.jsonl`, `rr2_output_*.jsonl` werden nie überschrieben. Das Auswerteskript schreibt einen **abgeleiteten** Datensatz (vorgeschlagen: `data/card_understanding/card_understanding_h_pooled.jsonl`, je Karte `oracle_id`, `H_pooled`, `n_bewertungen`, `H_F1`, `H_R2`, `quelle_R2`, Marken).
- **Anzeige (später, nur nach Owner-Entscheid, eigener PR):** Die Tierliste liest genau ein Feld „H_pooled + n_bewertungen“ (z. B. „H 42,5 · 2 Bewertungen“) und zeigt die Marken. Rundung für die Anzeige, Zuordnung zu Stufen und der „±“-Text (heute Option B, Mindestwert „±8“) entscheidet der Owner; dieser Plan legt nur fest, welche Zahlen dafür berichtet werden (§5, §6).

## 5. Streuung aus den Paardifferenzen

d = H_R2 − H_F1 je Karte mit `n_bewertungen = 2`. Grundgesamtheit nach Welle 2: alle 922 Karten (Vollerhebung, keine Gewichtung nötig). Immer n/N angeben (N = 922; Teilmengen: Welle, Schicht, Kartenart, Charge).

| Größe | Formel | Bedeutung |
|---|---|---|
| Verzerrung b | mittlere d | systematischer Niveauunterschied R2 gegen F1 |
| SD(d), RMS(d), mittlere \|d\|, Anteil \|d\| ≥ 15, Maximum | wie Welle 1 | Rohgrößen der Differenz |
| Einzelwert-Streuung σ₁ | SD(d)/√2 | Rauschen **einer** Bewertung, Verzerrung herausgerechnet |
| Einzelwert-Streuung (Anschluss an Welle 1) | RMS(d)/√2 | wie die 8,1 aus #1758, Verzerrung eingeschlossen |
| Standardfehler des gepoolten Werts | SD(d)/2 = σ₁/√2 | Rauschen von H_pooled (bei K0 zusätzlich ± b/2 Niveauunterschied) |

**Annahmen (offen genannt):** Die Fehler der beiden Bewertungen sind unabhängig und gleich groß. Ist R2 aus derselben Familie wie F1 (A3 schließt das nicht aus), teilen sie Familienfehler; dann unterschätzt SD(d)/√2 die Unsicherheit gegenüber der „wahren“ Kartenstärke, und die Senkung um 1/√2 gilt nur für das nicht geteilte Rauschen. Gemeinsame Fehler innerhalb einer Charge (Chargeneffekt, A6) senken den Gewinn ebenfalls; deshalb wird die **Varianzkomponente zwischen den Chargen** berichtet: σ²_Charge = max(0, Var(Chargenmittel von d) − Mittel(Var_k(d)/n_k)), Chargen 1 bis 7, alle Karten der Charge.

**Intervalle:** Bootstrap über Karten, geschichtet nach Welle × Schicht, 5000 Ziehungen, `random.Random(20261124)`, 95 % Perzentil.

Berichtet je: gesamt (922), Welle 1 (300) und Welle 2 (622), Schicht, Kartenart (Spell/Land nach `is_land_front`), Charge, H_F1-Band (Guide-Bänder 95–100, 72–94, 50–71, 28–49, 5–27, 0–4).

## 6. Bias-Korrektur nach Kartenart (nur Bericht, Owner-Entscheid)

**Klassen (vorab):** Spell = `is_land_front` falsch; Land = wahr. Weitere Unterteilungen (Kreatur/Nicht-Kreatur, Spitze/Rest) sind nur explorativ.

**Bestätigungsmenge:** die **580 nicht-Anker-Spells von Welle 2** (32 Spitze, 548 Rest). Ankerkarten zählen nicht (ihr Guide unterscheidet sich, sie sind untypisch); ihre Verzerrung wird getrennt berichtet. Welle 1 ist die Hypothesenquelle (−5,61) und zählt nicht zur Bestätigung.

| Urteil (Spells) | Bedingung auf b_W2 = mittlere d der 580 |
|---|---|
| **bestätigt** | b_W2 ≤ −3,0 **und** obere Grenze des 95-%-Cluster-Intervalls < 0 **und** b < 0 in mindestens m − 1 der m gültigen Chargen (je Charge die mittlere d ihrer Nicht-Anker-Spells) **und** m ≥ 6 |
| **kleiner bestätigt** | m ≥ 6, Cluster-Intervall ganz < 0 und b < 0 in mindestens m − 1 von m gültigen Chargen, aber −3,0 < b_W2 → kein Korrekturvorschlag (unter einer halben Stufe von 5) |
| **kein Schluss** | weniger als 6 gültige Chargen (m < 6, A11) |
| **nicht bestätigt** | m ≥ 6 und jeder andere Fall (Cluster-Intervall schließt 0 ein, b_W2 > 0 oder weniger als m − 1 von m Chargen mit b < 0) |

**Gültige Chargen m:** Chargen 1 bis 7 außer denen, die nach A2 (zweiter Verstoß) oder A4 (Skalenstauchung) nicht gepoolt werden; b_W2 ist die mittlere d der Nicht-Anker-Spells dieser m Chargen. Ohne Ausfall ist m = 7 (Bedingung: 6 von 7).

**Intervall für diesen Test (Cluster-Bootstrap):** Weil Fehler innerhalb einer Charge gemeinsam sein können (Welle 1 je Datei: −2,4 · −3,6 · −6,3), ist das Intervall ein zweistufiger Bootstrap: zuerst m gültige Chargen aus den m gültigen mit Zurücklegen ziehen, dann innerhalb jeder gezogenen Charge ihre Nicht-Anker-Spells mit Zurücklegen; b* = Mittel über alle gezogenen Karten; 5000 Ziehungen, `random.Random(20261124)`, 95 % Perzentil. Der einfache Karten-Bootstrap wird daneben nur beschreibend berichtet.

- **Länder:** Welle 2 enthält nur 12 Anker-Länder → **„kein Schluss“** für eine Länder-Korrektur. Die Verzerrung über alle 65 Länder (Welle 1 + 2) wird explorativ berichtet; kein Vorschlag.
- **Welleneffekt (A9):** Vergleich der Verzerrung in vergleichbaren Zellen (Rest-Spells ohne Anker: Welle 1 n = 115, Welle 2 n = 548): Unterschied > 3 Punkte und Intervall der Differenz ohne 0 → „Welleneffekt“; dann wird jede Korrektur je Welle berichtet und kein gemeinsamer Wert vorgeschlagen.
- **Optionen, beide berechnet, keine angewendet:**
  - **K0 (Standard):** einfaches Mittel wie §4. Die gepoolten Spells liegen dann um b/2 unter dem F1-Niveau, Länder nicht.
  - **K1 (nur bei „bestätigt“):** R2 vor dem Poolen um die Klassenverzerrung verschieben: H_pooled_K1 = (H_F1 + H_R2 − b_W2)/2 für Spells, Länder unverändert. Das gepoolte Niveau bleibt beim F1-Niveau, auf das die heutigen Stufengrenzen geeicht sind.
  - **Was das ändert:** Haben alle Karten zwei Bewertungen, verschiebt K1 gegen K0 alle Spells um denselben Betrag b/2: Die Rangfolge **innerhalb** der Spells bleibt gleich, es ändern sich nur Spells gegen Länder und die Lage zu festen Stufengrenzen. K1 ist vor allem dann wichtig, wenn Karten mit `n_bewertungen = 1` übrig bleiben (sonst stünden sie um b/2 anders als ihre Nachbarn).
  - **Berichtet für K0 und K1:** Zahl der Karten, die gegenüber H_F1 das Guide-Band, die Seite von H ≥ 50 und die Stufe der zum Auswertezeitpunkt geltenden Tierlisten-Regel wechseln (Datei und Commit der Regel im Bericht nennen); je Richtung, mit n/N.
- **Entscheid:** Der Bericht schlägt K0 oder K1 vor, der Owner entscheidet. Niemals still anwenden.

## 7. Was „besser“ heißt

| Nr | Aussage | Messung | Urteil |
|---|---|---|---|
| B1 | **Vorhersage** (mechanisch) | ICC(2,1) von H über alle Karten mit zwei Bewertungen = r₁; Spearman-Brown r₂ = 2r₁/(1+r₁) (= ICC(2,2)). Formeln (k = 2): ICC(2,1) = (MSR − MSE)/(MSR + MSE + 2(MSC − MSE)/n), ICC(2,2) = (MSR − MSE)/(MSR + (MSC − MSE)/n). Zusätzlich ICC(3,1) (Konsistenz) und Spearman ρ(H_F1, H_R2). | nur berichtet, mit Intervall; gilt nur unter den Annahmen von §5 |
| B2 | **Belegt gegen eine dritte, unabhängige Messung (einziger Beleg für „besser“)** | G1 (`audit/independent_rater_ratings.jsonl`, 70 Karten; 33 in Welle 1, 37 in Welle 2): Δ_G1 = mittlere \|H_F1 − H_G1\| − mittlere \|H_pooled − H_G1\| (bei K0; K1 zusätzlich), gepaarter Bootstrap über die 70 Karten, 5000 Ziehungen, Seed 20261124 | **besser belegt:** 95-%-Intervall von Δ_G1 ganz > 0; **schlechter:** ganz < 0; sonst **kein Schluss** (n = 70 ist klein). Zusätzlich beschreibend: Spearman ρ(H_pooled, H_G1) gegen ρ(H_F1, H_G1) |
| B3 | **Wiederholstreuung von R2** (Test-Retest, nur mit Charge 8) | d_rt = H_R2,Retest − H_R2,Welle1 auf den 50 Karten: Verzerrung, SD(d_rt)/√2, ICC(2,1); Vergleich mit σ₁ aus §5 auf denselben 50 Karten | **nur beschreibend, nie ein Beleg für „besser“** (Charge 8 ist eine Wiederholung derselben Rater-Art, keine unabhängige Messung): Liegt die Wiederholstreuung von R2 nahe σ₁, ist der Abstand R2–F1 überwiegend Rauschen; ist sie deutlich kleiner, ist ein Teil systematisch |

- **Verzweigung für B2:** Nur wenn das Laufprotokoll zeigt, dass G1 aus einer **anderen Familie als R2** stammt, kann B2 „besser belegt“ ergeben. Ist R2 aus derselben Familie wie G1, oder ist das unbekannt, ist G1 nicht unabhängig von R2; B2 heißt dann „Übereinstimmung mit einem Lauf derselben Familie“, und „besser“ bleibt **unbelegt**. F2 (`fulldrift_ratings.jsonl`, 49 Karten, F1-Familie) wird nur beschreibend gleich gerechnet (zieht zu F1 hin).
- „Besser“ im Sinne dieses Plans heißt **verlässlicher** (weniger Rauschen eines einzelnen Modellurteils), nicht **richtiger**: Zwei Modellurteile sind keine Wahrheit; Nutzung und Beliebtheit werden nicht berührt.

## 8. Abbruch- und „Kein-Schluss“-Regeln

| Nr | Auslöser | Folge |
|---|---|---|
| A1 | in einer Charge weniger als 90 % gültige Zeilen | fehlende Karten genau einmal mit derselben Anweisung nachlaufen lassen (Wiederaufnahme ab k+1, nie einzelne Karten neu bewerten oder auswählen); gültige Zeilen werden gepoolt, fehlende bleiben `n_bewertungen = 1` |
| A1g | nach Nachlauf weniger als 90 % der 922 Karten (830) mit zwei Bewertungen | **kein Schluss** zu B1, B2 und §6; kein Owner-Vorschlag zur Anzeige von H_pooled (gemischte n verzerren das Niveau) |
| A2 | Blindheitsverstoß in einer Charge: das Laufprotokoll oder die Schlussantwort zeigt Zugriff auf Repo, andere Dateien oder Web, **oder** mindestens ein **zählender Verweis-Treffer** nach der Zähl-Regel in §9 | ganze Charge ungültig, nicht gepoolt; ein Wiederholungslauf mit frischer Instanz. **Vor der Wiederholung** wird die ungültige `rr2_output_N.jsonl` aus dem Rater-Ordner **und** aus dessen Elternordner in den Analystenordner verschoben (die eingefrorene Anweisung §4.3 ließe sonst bei k+1 weitermachen) und ihr SHA-256 samt Ablageort in Protokoll und #1404 notiert; zweiter Verstoß in derselben Charge: Charge bleibt `n_bewertungen = 1`; Verstöße in zwei verschiedenen Chargen: **Abbruch, „kein Schluss“** für Welle 2 |
| A3 | Laufprotokoll fehlt (Modell-ID, Stufe, Dateizugriff) | Zahlen werden berichtet; keine Aussage „unabhängig“ oder „andere Familie“; B2 nur beschreibend; Pooling erlaubt, aber als „zwei Bewertungen, Unabhängigkeit ungeprüft“ gekennzeichnet |
| A3w | Welle 2 lief mit anderer Modell-ID oder Stufe als Welle 1, **oder das ist unbekannt** (Welle 1 hat kein Laufprotokoll, also der erwartete Fall) | jede Kennzahl je Welle getrennt berichten; eine gemeinsame Aussage über beide Wellen heißt nie „ein Rater R2“; Pooling je Karte erlaubt, Marke `quelle_R2` zeigt die Welle |
| A4 | Skalenstauchung in einer Charge: SD(H_R2) < 0,6 × SD(H_F1) auf denselben Karten, oder mehr als 40 % der Karten mit demselben H_R2 | Charge nicht gepoolt (`nur_erstbewertung`, Grund „Skalenstauchung“); Nachlauf nur auf Owner-Wunsch |
| A5 | mehr als 5 % der Zeilen einer Charge mit Nicht-Vielfachen von 5, fehlenden Kriterien oder falscher `oracle_id` | „Formatfehler“ berichten; Rundung halb nach oben; Zeilen mit falscher `oracle_id` oder fehlenden Kriterien sind ungültig (A1) |
| A6 | Chargeneffekt: mittlere d einer Charge weicht um mehr als 4 Punkte vom Mittel der übrigen Chargen 1 bis 7 ab (**alle** Karten der Charge; zweite Fassung ohne Ankerkarten nur beschreibend) | Charge markieren (`charge_auffaellig`), gepoolt bleibt sie; je Charge berichten; σ²_Charge (§5) nennen; keine automatische Korrektur |
| A7 | eine Instanz bricht ab (Limit, Fehler) | Wiederaufnahme nach A1; läuft sie wieder aus, gilt A1 für die Charge |
| A8 | Schwellen, Klassen, Mengen oder Formeln müssten nach dem Öffnen geändert werden | nicht ändern; Lauf „nicht nach Plan“ kennzeichnen, Abweichung explorativ nennen |
| A9 | Welleneffekt (§6) | Korrektur je Welle berichten, kein gemeinsamer Vorschlag |
| A10 | Auswerteskript nicht vor dem Öffnen committet oder Ausgabe-Hashes nicht vor dem Öffnen gepostet | Ergebnisse nur als „explorativ, nicht nach Plan“; kein Owner-Vorschlag zu K1 |
| A11 | weniger als 6 gültige Chargen für den Spells-Test (§6; Ausfälle nach A2 zweiter Verstoß oder A4) | **kein Schluss** zur Bias-Korrektur, kein K1-Vorschlag; alle übrigen Kennzahlen werden über die gültigen Chargen berichtet |

**Markierung statt Löschen (|d| ≥ 15):** Jede Karte mit |d| ≥ 15 bekommt die Marke `abweichung_ge15` (ab 30 zusätzlich `abweichung_ge30`), bleibt mit beiden Werten und `H_pooled` im Datensatz und wird im Bericht gelistet (Karte, beide H, beide Begründungen). Sie wird nie gelöscht, nie auf eine der beiden Bewertungen zurückgesetzt und nie neu bewertet. Eine spätere Adjudikation (dritter Blick) braucht ein Owner-Go. Berichtet: Anteil gesamt, je Welle (Welle 1: 24,5 % der 265) und je Klasse.

## 9. Blindheit, Ermüdung, Regelclaims, Reihenfolge der Schritte

- **Blindheit:** Rater-Ordner isoliert (§2); eine Charge je frischer Instanz; die Anweisung verbietet jeden anderen Dateizugriff. Scan wie Welle 1 über `notes`, `reason`, `uncertainty`, `claim`: Beliebtheitsliste `popular|staple|edhrec|commonly played|budget|cedh|played in (most|many)` (jeder Treffer von Hand gelesen; echte Beliebtheitsaussagen in mehr als 5 % der Karten einer Charge: Charge markieren und berichten) und Verweis-Liste (A2).
- **Verweis-Liste und Zähl-Regel (A2, vorab endgültig):** Regex, ohne Groß-/Kleinschreibung: `earlier rating|previous|\bv1\b|\bF1\b|audit|tier ?list` (wie `second_run_compare.EARLIER`). Durchsucht werden **nur die Ausgabefelder des Raters** `notes` (alle sieben), `reason`, `uncertainty` und `rule_claims[].claim` sowie seine Schlussantwort; **nicht** `rule_claims[].quote` und nie Guide- oder Eingabetext (dort stehen „v1“, „audited later“ und „previous“ in Rulings). Jeder Treffer wird von Hand gelesen. Ein Treffer **zählt** nur, wenn der Satz auf einen früheren Bewertungslauf, frühere Werte oder Ränge, eine Stufe/Tierliste oder ein anderes Modell als Quelle für diese Karte verweist. Er zählt **nicht**, wenn er (a) Kartentext oder ein Ruling wiedergibt oder umschreibt (z. B. „the previous turn“, „previously exiled“), (b) Guide-Anker, Guide-Version oder „v1 fixed“-Ankerwerte des Guides nennt, oder (c) „audit“ im Sinn des Guides gebraucht. Zweifelsfall: zählt. Jeder Treffer wird mit Karte, Feld, Satz und Einstufung (zählt/zählt nicht + Buchstabe) im Bericht gelistet.
- **Ermüdung:** je Charge mittlere \|d\| der ersten gegen die zweite Hälfte der Positionen und Spearman(Position, d); auffällig bei Differenz > 3 oder \|ρ\| > 0,2 → berichten, kein Abbruch.
- **Regelclaims (blind zur Herkunft):** 100 Claims, `random.Random(20261125)`, höchstens einer je Karte: 50 aus Welle 2 und 50 aus F1 für **andere** Karten von Welle 2, gemischt; der Prüfer sieht nur Kartenblock und Claim, nicht die Herkunft. „Offensichtlich falsch“ wie Welle 1 (widerspricht Kartentext, gezeigtem Ruling oder Comprehensive Rules eindeutig). Je Herkunft: grün ≤ 2 von 50, rot ≥ 5 von 50. Zitate wörtlich (V4) automatisch für alle Claims.
- **Reihenfolge (Pflicht):**
  1. Dieser PR (Plan, Skript, Tests, Eingaben) steht im Repo; erst dann bekommt der Co-Lead die Pfade.
  2. Lauf der Chargen 1 bis 7 (und optional 8) nach §2, Laufprotokoll.
  3. SHA-256 der Ausgaben in #1404 posten, bevor eine Ausgabe geöffnet wird.
  4. Auswerteskript in einem eigenen PR: setzt §3 bis §8 mechanisch um, mit synthetischen Tests; committet **vor** dem ersten Öffnen der Ausgaben (A10). Verpflichtende Rot/Grün-Tests (heute NOT_TESTABLE, weil noch kein Auswertecode existiert): (a) eine Karte mit nur einer gültigen Bewertung bekommt `H_pooled = H_F1`, `n_bewertungen = 1` und die Marke (ein Mutant, der trotzdem mittelt, wird rot); (b) die Schwelle des Spells-Tests −3,0 (ein Mutant mit −1,0 ändert das Urteil auf synthetischen Daten mit b = −2 und wird rot); dazu Cluster-Bootstrap über die m gültigen Chargen, die Bedingung „m − 1 von m“ und „kein Schluss“ bei m < 6 (synthetisch mit m = 7, 6 und 5).
  5. Wiederholungen und Nachholungen nur so: A2 ungültige Ausgabe zuerst verschieben und hashen (A2), A1/A7 Wiederaufnahme ab k+1; jede neue Ausgabe wird nach Schritt 3 eingefroren, bevor das Auswerteskript sie liest.
  6. **Verweis-Treffer klassifizieren (Pflicht, vor jeder Differenz):** Das committete Auswerteskript gibt in einem ersten Schritt nur die Treffer der Verweis-Liste aus (Karte, Charge, Feld, Satz), ohne Bewertungen; jeder Treffer wird nach der Zähl-Regel in §9 von Hand eingestuft (zählt / zählt nicht + Buchstabe a–c, Zweifelsfall zählt), die vollständige Liste in #1404 gepostet, und daraus folgt A2. Erst danach wird irgendeine Differenz zwischen erster und zweiter Bewertung berechnet.
  7. Auswertung, Bericht unter `docs/analysis-reports/`, Ausgaben unter `second_run_full_20261122/`, Owner-Vorschlag (Anzeige H_pooled, K0/K1). Nichts am Produkt ohne Owner-Entscheid.

## 10. Grenzen

- Zwei Modellurteile sind keine Wahrheit; „besser“ heißt hier weniger Rauschen, nicht richtiger (§7).
- Ist R2 aus derselben Familie wie F1, teilen beide Familienfehler, und das Poolen senkt nur das nicht geteilte Rauschen.
- Die Ankerkarten (42) werden mit einem Guide bewertet, dem ihre eigene Zeile fehlt (wie in F1); ihre Ergebnisse stehen getrennt.
- Kontext von 88 bis 89 Karten je Instanz statt 7 je Charge im Vollauf: Kontext- und Chargeneffekte möglich (A6, Ermüdung).
- Länder sind für die Korrektur nicht prüfbar (12 in Welle 2).
- G1 hat nur 70 Karten; B2 endet bei kleinen Effekten in „kein Schluss“.
- Beliebtheitswissen eines Modells lässt sich nicht ausschließen; der Scan ist ein Stichwort-Indiz.

## 11. Herkunft und Reproduktion

Erzeugung (deterministisch, zweimal byte-gleich; der Lauf-Ordner bekommt seinen echten Pfad statt des Platzhalters):

```
python3 scripts/analysis/rating_second_run_full_inputs.py --repo . \
  --out data/research/chulane_rubric_v2_20261118/second_run_full_20261122 \
  --rater-dir data/research/chulane_rubric_v2_20261118/second_run_full_20261122/rater \
  --path-in-instructions '<RATER_DIR>'
```

Das Manifest `rr2_manifest.json` enthält Seed, Quell-Commit, SHA-256 aller Quelldateien (Fakten, Muster, Anker, Guide, Schema, Render-Skripte, F1, Prüfer-Marken, Welle-1-Manifest), n/N, Zusammensetzung, je Charge Schichten, entfernte Anker, entfernte Ankerzeilen je Kriterium sowie SHA-256 von Guide und Eingabe. Tests: `tests/unit/test_rating_second_run_full_inputs.py` (synthetische Daten). Die Eingaben enthalten nur Kartentext-Blöcke, Namen und `oracle_id`; keine Bewertungen, Preise, Nutzung oder privaten Daten.
