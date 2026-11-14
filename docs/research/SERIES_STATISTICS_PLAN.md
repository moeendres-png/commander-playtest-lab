# Statistik-Plan: Wie viele Partien braucht ein belastbarer Deck-Vergleich?

- **Referenz:** GitHub-Issue #1211 (Recherche, Owner-Auftrag 2026-11-12)
- **Art:** Reine Recherche, kein Produktcode. Alle Zahlen sind mit den angegebenen
  Formeln nachgerechnet; das Rechenskript liegt im Repo unter
  `docs/research/series_statistics_calc.py` und erzeugt die Tabellen aus den
  Formeln (die Formeln stehen auch im Anhang dieses Dokuments).
- **Ergänzung 2026-11-14 (Refs #1211):** Power-90 %-Tabellen (Abschnitt 2.7),
  geprüfte Alternativen zum sequenziellen Verfahren (Abschnitt 4) und die
  Zell-für-Zelle-Verifikation aller Tabellen durch das Rechenskript (Anhang,
  „Verifikation"). Zwei gerundete Werte des ursprünglichen Plans wurden dabei
  korrigiert (Abschnitt 2.4: ≈ 2,5 statt 2,4 Stunden; Abschnitt 2.5: 33,5
  statt 33,6 Prozentpunkte).
- **Verbindliche Vorgaben:** `AGENTS.md` §4 (Evidenzsemantik), `docs/OWNER_DECISIONS_STUDIO_20261112.md`
  S3 (Ergebnisse sind Beobachtungen einer Serie: Nenner, Unsicherheitsbereich,
  Basis gegen Variante nur gepaart auf denselben Seeds, abgebrochene Partien
  getrennt und nie als Niederlagen), S2 (keine neuen Pilot-Mikro-Messreihen).
- **Evidenz-Klassen in diesem Dokument:** Repo-Fakten (was Code und Dokumente
  bereits enthalten) sind `CODE_DERIVED` mit Datei und Zeile. Alle neu
  berechneten Fallzahlen und Tabellen sind `MODELED`: Sie folgen aus den
  genannten Formeln und Annahmen, nicht aus neuen Partien. Was aus den
  vorhandenen Unterlagen nicht belegbar ist, steht als `UNKNOWN` da.

---

## 0. Kurzantwort

Für einen Deck-Vergleich Basis gegen Variante (Sieganteil des eigenen Decks,
Differenz Δ in Prozentpunkten, α = 0,05 zweiseitig, Power 80 %, Konfidenz 95 %).
**Diese Tabelle gilt für „ein Blick, ein Vergleich" (α = 0,05 am einzigen
Blick).** Für den empfohlenen Plan mit mehreren Looks und mehreren Varianten
sind die Zahlen größer (Abschnitt 2.6).

Vergleich mit gleichem Design-Effekt (DEFF = 1,75, ρ = 0,25) auf beiden Seiten;
Einheit „Partien je Arm" (gepaart: Paare = Seeds × 4):

| Ziel-Differenz | Ungepaart (Partien je Arm, iid × 1,75) | Gepaart q = 0,20: Seeds (Paare) | Gepaart q = 0,40: Seeds (Paare) |
|---|---|---|---|
| 5 Prozentpunkte | 2.184 (iid 1.248) | 275 (1.100) | 546 (2.184) |
| 10 Prozentpunkte | 571 (iid 326) | 69 (276) | 137 (548) |
| 15 Prozentpunkte | 263 (iid 150) | 31 (124) | 61 (244) |

(q = Anteil der Paare mit unterschiedlichem Ausgang, siehe Abschnitt 3.
Die iid-Werte in Klammern sind die ungepaarten Werte ohne Design-Effekt aus
Abschnitt 2.1; ungepaart: 1.248 · 1,75 = 2.184, 326 · 1,75 = 570,5 → 571,
150 · 1,75 = 262,5 → 263. Herleitung in Abschnitt 2.)

Daraus folgen die vier Arbeitsregeln dieses Plans:

1. **Einzelkarten-Effekte (erwartbar ≤ 5 Prozentpunkte) sind über die Siegquote
   praktisch nicht nachweisbar.** Selbst gepaart braucht es dafür 275 bis 546
   Seeds (1.100 bis 2.184 Partien je Arm bei 4 Plätzen). Einzelkarten werden
   weiter über den Strukturfilter und Pro-Karten-Kennzahlen beurteilt
   (`docs/DECK_VARIANT_WORKFLOW.md`, Schritt 2 und 4), nicht über die Siegquote.
2. **Deck-Umbauten mit erwarteten 10 bis 15 Prozentpunkten sind der
   Arbeitsbereich der Siegquote:** 31 bis 137 Seeds gepaart, also Stunden statt
   Tage an Laufzeit (Abschnitt 2.4).
3. **Serien ohne vorher festgelegte Größe und Stopp-Regel enden strukturell
   „unentschieden".** Historische Serien mit 30 bis 40 Paaren konnten nur
   Differenzen ab rund 28 bis 37 Prozentpunkten erkennen (Abschnitt 2.5) —
   das bisherige „unentschieden" ist eine Eigenschaft der Seriengröße, kein
   Befund über die Decks.
4. **Gepaart auf denselben Seeds ist Pflicht, aber kein Wundermittel.** Der
   Gewinn hängt vollständig davon ab, wie oft beide Arme im selben Seed
   übereinstimmen (Abschnitt 3): Die Paarung spart Partien, solange q unter
   dem ungepaarten Varianzterm liegt (bei 4 Plätzen und 5 pp etwa q < 0,40);
   bei q = 0,40 ist sie neutral, bei 5 oder 6 Plätzen darüber schlechter. Die Paarung ist im Runner bereits das
   Standardverfahren; dieser Plan liefert die Größen und die Messvorschrift
   für ihre tatsächliche Stärke.

---

## 1. Einheiten, Zielgröße und Nenner

**Einheiten.** Eine *Partie* ist ein beendetes Spiel eines Arms. Ein *Paar*
sind zwei Partien — Basis und Variante — mit demselben Seed, demselben Pod
und derselben Sitzposition des eigenen Decks. Ein *Seed* erzeugt bei s Plätzen
s Paare, weil das eigene Deck jede Sitzposition einmal durchläuft
(Platzrotation, Abschnitt 7). Die Paare eines Seeds teilen sich dieselbe
Mischung (Shuffle); sie sind **nicht** unabhängig. Die Auswertung behandelt
den Seed deshalb als Cluster (Repo-Stand: `aggregate_comparison` in
`src/commander_lab/engine/rules/full_game_comparison.py`, Cluster-t-Test mit
einem Cluster je Seed, CR1, df = Seeds − 1; Doku
`docs/performance/VERDICT_CLUSTER_T_2026-10-31.md`). `CODE_DERIVED`

**Zielgröße.** Δ = Sieganteil(Variante) − Sieganteil(Basis), jeweils über
beendete Partien. Unentschiedene Partien (Draw) zählen mit fraktionalem Sieg
1/(Zahl der Sieger-Plätze) — so rechnet bereits
`aggregate_batch_results` in `src/commander_lab/studio/simulations.py`
(`wins_fractional`). Erwarteter Sieganteil unter der Nullhypothese bei
ausgeglichenem Tisch: p₀ = 1/s (25 % bei 4 Plätzen). `CODE_DERIVED`

**Nenner-Regel.** Jeder Anteil in einer Serie trägt seinen Nenner: geplante
Partien, beendete Partien, gescheiterte Partien getrennt (Owner-Entscheid S3).
Gescheiterte Partien (ENGINE_FAILURE) sind weder Siege noch Niederlagen;
Abschnitt 9 regelt ihren Umgang im Vergleich. `CODE_DERIVED` (Simulations.py:
`games_planned`, `games_completed`, `games_failed` werden getrennt geführt.)

---

## 2. Frage 1: Seriengrößen für 2 bis 6 Plätze

### 2.1 Ungepaart (zwei unabhängige Arme)

Formel (Normalapproximation, wie in #1231 Abschnitt 3.4):

$$n_{\text{je Arm}} = \frac{(z_{1-\alpha/2} + z_{1-\beta})^2 \cdot [p_0(1-p_0) + p_1(1-p_1)]}{\Delta^2},
\qquad p_1 = p_0 + \Delta$$

mit z₀,₉₇₅ = 1,9600, z₀,₈₀ = 0,8416. Partien je Arm (Power 80 %):

| Plätze s | p₀ | Δ = 5 pp | Δ = 10 pp | Δ = 15 pp |
|---|---|---|---|---|
| 2 | 50,0 % | 1.562 | 385 | 167 |
| 3 | 33,3 % | 1.440 | 368 | 165 |
| 4 | 25,0 % | **1.248** | 326 | 150 |
| 5 | 20,0 % | 1.091 | 291 | 136 |
| 6 | 16,7 % | 969 | 263 | 124 |

`MODELED`, nachgerechnet. Die Zelle 4 Plätze / 5 pp reproduziert exakt den
Wert aus #1231 (1.248 je Arm, 2.496 Partien gesamt) — Gegenprobe bestanden.
Mehr Plätze brauchen weniger Partien je Arm, weil die Varianz p(1−p) mit
fallendem p₀ sinkt; dafür dauert jede Partie länger und der absolute Effekt
eines Decks auf den eigenen Sieganteil ist bei mehr Plätzen kleiner — ein
15-pp-Effekt ist bei 6 Plätzen fast eine Verdopplung des fairen Anteils
(16,7 % → 31,7 %) und entsprechend selten realistisch. Power 90 % statt 80 %
kostet bei 4 Plätzen den Faktor ≈ 1,34 (5 pp: 1.671 je Arm).

### 2.2 Gepaart auf denselben Seeds (Repo-Planungsmethode)

Der Vergleichs-Runner plant bereits genau so (`power_table()` in
`full_game_comparison.py`, dokumentiert in `docs/DECK_VARIANT_WORKFLOW.md`
Schritt 4): Für ein Paar sei d ∈ {−1, 0, +1} der Ausgangsunterschied
(Variante gewinnt / gleicher Ausgang / Basis gewinnt) und q der Anteil
diskordanter Paare (d ≠ 0). Dann ist E[d] = Δ, Var(d) ≈ σ_d² mit
σ_d = √q (für q = 0,40: σ_d = 0,632; der Repo-Anker rundet auf 0,63), und

$$N_{\text{Paare, iid}} = \left\lceil \left( \frac{(z_{1-\alpha/2} + z_{1-\beta}) \cdot \sigma_d}{\Delta} \right)^2 \right\rceil$$

Die s Paare eines Seeds werden mit dem Design-Effekt
DEFF = 1 + (s − 1)·ρ, ρ = 0,25 (Repo-Planungsannahme für 4 Plätze), auf
Seeds umgerechnet: N_Paare,Cluster = ⌈N_iid · DEFF⌉, Seeds = ⌈N_Paare,Cluster / s⌉.

**q ist die konservative obere Schranke:** Exakt gilt Var(d) = q − Δ² (Abschnitt 3);
die Näherung Var(d) ≈ q lässt −Δ² weg und rechnet etwas zu groß. Exakte Variante
einmal als Beispiel: Δ = 15 pp, q = 0,20 → iid-Paare ⌈(2,8016)² · 0,20 / 0,15²⌉ = 70
(Näherung) gegenüber ⌈(2,8016)² · (0,20 − 0,0225) / 0,15²⌉ = 62 (exakt). Die
Tabelle unten und der Planungsstandard verwenden die Näherung. Die Zeilen
q = 0,40 sind mit dem Repo-Anker 0,63 gerechnet (1.247 Paare, 546 Seeds); mit
σ_d = 0,632 sind es 1.256 Paare und 550 Seeds (≤ 0,8 % mehr).

| Δ | q | Paare (iid) | Seeds bei 2 Pl. | 3 Pl. | 4 Pl. | 5 Pl. | 6 Pl. |
|---|---|---|---|---|---|---|---|
| 5 pp | 0,09 | 283 | 177 | 142 | 124 | 114 | 107 |
| 5 pp | 0,20 | 628 | 393 | 314 | 275 | 252 | 236 |
| 5 pp | 0,40 | 1.247 | 780 | 624 | 546 | 499 | 468 |
| 10 pp | 0,20 | 157 | 99 | 79 | 69 | 63 | 59 |
| 10 pp | 0,40 | 312 | 195 | 156 | 137 | 125 | 117 |
| 15 pp | 0,20 | 70 | 44 | 35 | 31 | 28 | 27 |
| 15 pp | 0,40 | 139 | 87 | 70 | 61 | 56 | 53 |

`MODELED`, nachgerechnet; die Zeilen 4 Plätze reproduzieren die
Workflow-Tabelle exakt (5 pp/q = 0,40: 1.247 Paare, 546 Seeds; 10 pp/q = 0,20:
157 Paare, 69 Seeds) — Gegenprobe bestanden. Eine unabhängige Gegenrechnung
über die McNemar-Fallzahl (Connor 1987, Formel im Anhang) weicht in allen
zulässigen Zellen um höchstens rund 20 % nach unten ab; die Repo-Methode ist
die konservativere und bleibt der Planungsstandard.

**Machbarkeitsgrenze:** Es gilt immer |Δ| ≤ q — eine Differenz kann nicht
größer sein als der Anteil der Paare, die überhaupt unterschiedlich ausgehen.
15 pp bei q = 0,09 oder 10 pp bei q = 0,09 sind unmöglich; solche Zellen
existieren in der Tabelle nicht. Umgekehrt heißt das: Wer 15 pp Unterschied
behauptet, behauptet zugleich eine Diskordanz von mindestens 15 %.

**Platzabhängigkeit von q:** q steckt voller Annahmen über die Platzzahl.
Unter der Nullhypothese (Δ = 0) gilt q = 2·p₀(1−p₀)(1−φ) mit φ = Korrelation
der beiden Arm-Ergebnisse im selben Seed (Abschnitt 3). Für φ = 0,25 ergibt
das q ≈ 0,38 (2 Pl.), 0,33 (3 Pl.), 0,28 (4 Pl.), 0,24 (5 Pl.), 0,21 (6 Pl.).
Die Tabellenzeilen q = 0,20 und q = 0,40 decken diesen Bereich für alle
Platzzahlen ab; q = 0,09 entspricht φ ≈ 0,75 und ist nur für sehr kleine
Änderungen (ein Kartentausch) plausibel.

### 2.3 Durchgerechnetes Beispiel (4 Plätze, 10 pp, q = 0,20)

σ_d = √0,20 = 0,4472. N_iid = ⌈(2,8016 · 0,4472 / 0,10)²⌉ = ⌈12,525²⌉ = 157
Paare. DEFF bei 4 Plätzen = 1 + 3 · 0,25 = 1,75 → 275 Paare → ⌈275/4⌉ = 69
Seeds, also 69 · 4 · 2 = 552 Partien gesamt (beide Arme).

### 2.4 Laufzeit-Einordnung

Der Workflow nennt als gemessenen Anker 225 Partien/Stunde (4 Arbeiter,
echter Pod, gemessen 2026-10-17/18, `docs/DECK_VARIANT_WORKFLOW.md` Schritt 2).
`CODE_DERIVED`. Damit: 10 pp bei q = 0,20 ≈ 2,5 Stunden; 5 pp ungepaart
(2.496 Partien) ≈ 11 Stunden; 5 pp gepaart bei q = 0,40 (4.368 Partien = 546 · 4 · 2)
≈ 19 Stunden. Die Größenordnung „ein Umbau-Entscheid an einem Abend,
ein 5-pp-Nachweis nur als geplante Kampagne" folgt direkt daraus.

### 2.5 Warum bisherige Serien „unentschieden" endeten

Umkehrung der Formeln: Welche Differenz konnte eine Serie gegebener Größe
überhaupt erkennen (Power 80 %)?

| Seriengröße | Erkennbare Differenz |
|---|---|
| 30 Partien je Arm, ungepaart, 4 Pl. | 33,5 pp |
| 40 Partien je Arm, ungepaart, 4 Pl. | 29,2 pp |
| 80 Partien je Arm, ungepaart, 4 Pl. | 20,7 pp |
| 40 Paare, gepaart, σ_d = 0,63 (iid) | 27,9 pp |
| 40 Paare, gepaart, mit Cluster-Korrektur (4 Pl.) | 36,9 pp |
| Roadmap S-1 (30 Partien, eine Serie) | nur Orientierung, kein Nachweis |

`MODELED`, nachgerechnet. Die Roadmap empfiehlt S-1 (≥ 30 Partien) ausdrücklich
als erste Messbasis, nicht als Nachweisgröße (`docs/STUDIO_ROADMAP_20261112.md`).
Jede Serie, die einen realistischen Deck-Effekt (5–15 pp) bei diesen Größen
nicht findet, meldet korrekt `NO_CLEAR_DIFFERENCE` bzw. `UNDERPOWERED` —
der Runner druckt diese Einordnung bereits (Workflow Schritt 4). Künftige
Serien legen Größe und Ziel-Differenz **vor** dem Start fest.

### 2.6 Fallzahl bei mehreren Looks und mehreren Vergleichen

Die Tabellen in 2.1 bis 2.5 und in Abschnitt 0 rechnen mit α = 0,05 an
**einem** Blick für **einen** Vergleich („ein Blick, ein Vergleich"). Der
empfohlene Plan (Abschnitt 4: 3 bis 5 O'Brien-Fleming-Looks, Holm über
Varianten) testet am letzten Look aber nur auf Level ≈ 0,026 (Abschnitt 4,
Tabelle), und bei m gleichzeitigen Vergleichen verlangt Holm im ersten Schritt
höchstens α/m (Bonferroni-Schranke). Die Fallzahl N muss daher mit dem
Level gerechnet werden, das am letzten Look tatsächlich gilt; die Formeln
bleiben dieselben, nur z₁₋α/₂ ändert sich:

- (a) Letzter Look, ein Vergleich: α = 0,026, z₀,₉₈₇ = 2,2262.
- (b) zusätzlich m = 5 Varianten (Obergrenze aus Abschnitt 8): α = 0,026/5 = 0,0052,
  z₀,₉₉₇₄ = 2,7944.
- Altwert: α = 0,05, z₀,₉₇₅ = 1,9600. Power 80 %: z₀,₈₀ = 0,8416.

Gepaart, 4 Plätze, DEFF = 1,75, σ_d = √q, Seeds = ⌈⌈((z_α + 0,8416)·√q/Δ)² · 1,75⌉ / 4⌉
(`MODELED`, nachgerechnet):

| q | Δ | Altwert „ein Blick, ein Vergleich" (α = 0,05) | (a) α = 0,026 | (b) α = 0,0052 (m = 5) |
|---|---|---|---|---|
| 0,40 | 5 pp | 550 | 659 | 926 |
| 0,40 | 10 pp | 138 | 165 | 232 |
| 0,40 | 15 pp | 62 | 74 | 104 |
| 0,20 | 5 pp | 275 | 330 | 463 |
| 0,20 | 10 pp | 69 | 83 | 116 |
| 0,20 | 15 pp | 31 | 37 | 52 |

(Die Altwert-Spalte mit σ_d = 0,632 statt des Repo-Ankers 0,63: 550 statt 546,
138 statt 137, 62 statt 61.) Faktor (a) gegenüber dem Altwert ≈ 1,20,
Faktor (b) ≈ 1,68. Für den empfohlenen Plan (q = 0,40, 5 pp, 5 Varianten) heißt
das: 926 Seeds statt 546 bzw. 550. Ungepaart je Arm (iid, ohne DEFF) bei 4 Plätzen:
1.248 / 326 / 150 (α = 0,05), 1.497 / 391 / 179 (a), 2.103 / 549 / 252 (b).
Holm ist im Mittel günstiger als die Bonferroni-Schranke, (b) ist daher eine
Obergrenze für den ersten Schritt, keine Punktschätzung. Die Look-Level
der anderen Looks (Abschnitt 4) liegen niedriger, entscheiden aber nur bei
überwältigender Evidenz; die Größe richtet sich nach dem letzten Look.
Die Faktor-Tabelle in Abschnitt 8 (α/K gegenüber α = 0,05) bezieht sich auf
den Altwert und ist mit dem Look-Faktor (a) zu multiplizieren.

### 2.7 Power 90 % (Ergänzung 2026-11-14)

Dieselben Formeln wie in 2.1 und 2.2, nur z₁₋β = 1,2816 statt 0,8416. Der
Verhältnis-Faktor gegenüber Power 80 % ist in der ungepaarten Formel konstant
≈ 1,34 (Abschnitt 2.1) und gilt in der gepaarten Planung näherungsweise ebenso
(Rundung der Seeds). `MODELED`, aus dem Rechenskript erzeugt.

Ungepaart, Partien **je Arm** (Power 90 %):

| Plätze s | p₀ | 5 pp | 10 pp | 15 pp |
|---|---|---|---|---|
| 2 | 50,0 % | 2.091 | 515 | 223 |
| 3 | 33,3 % | 1.928 | 492 | 221 |
| 4 | 25,0 % | 1.671 | 437 | 200 |
| 5 | 20,0 % | 1.461 | 389 | 181 |
| 6 | 16,7 % | 1.298 | 352 | 166 |

Gepaart, **Seeds** (Power 90 %, ρ = 0,25, Planungs-SD wie in 2.2):

| Δ | q | Paare (iid) | 2 Pl. | 3 Pl. | 4 Pl. | 5 Pl. | 6 Pl. |
|---|---|---|---|---|---|---|---|
| 5 pp | 0,09 | 379 | 237 | 190 | 166 | 152 | 143 |
| 5 pp | 0,20 | 841 | 526 | 421 | 368 | 337 | 316 |
| 5 pp | 0,40 | 1.669 | 1.044 | 835 | 731 | 668 | 626 |
| 10 pp | 0,20 | 211 | 132 | 106 | 93 | 85 | 80 |
| 10 pp | 0,40 | 418 | 262 | 209 | 183 | 168 | 157 |
| 15 pp | 0,20 | 94 | 59 | 47 | 42 | 38 | 36 |
| 15 pp | 0,40 | 186 | 117 | 93 | 82 | 75 | 70 |

---

## 3. Frage 2: Was die Paarung auf gleiche Seeds wirklich bringt

**Mechanik.** Die Paarung entfernt die Varianz, die beide Arme teilen:
derselbe Seed bedeutet dieselbe Mischung, derselbe Pod dieselben Gegner,
dieselbe Sitzposition dieselbe Zugreihenfolge. Formal: Mit dem diskordanten
Anteil q ist Var(d) = q − Δ² (exakt für d ∈ {−1, 0, +1}), während der
ungepaarte Vergleich je Partie die Varianz p₀(1−p₀) + p₁(1−p₁) trägt. Der
Varianzgewinn bei gleicher Gesamt-Partienzahl ist

$$\text{Gewinn} = \frac{p_0(1-p_0) + p_1(1-p_1)}{q - \Delta^2}$$

| q | Gewinn bei Δ = 5 pp (4 Pl.) | Gewinn bei Δ = 10 pp (4 Pl.) |
|---|---|---|
| 0,09 | 4,5× | —¹ |
| 0,20 | 2,0× | 2,2× |
| 0,40 | 1,0× | 1,1× |

¹ nicht möglich (Δ > q).

`MODELED`, nachgerechnet. Lesart: Bei q = 0,40 — fast jedes zweite Paar geht
unterschiedlich aus — bringt die Paarung **keinen** Varianzgewinn mehr; die
gemeinsame Seed-Struktur ist dann durch die abweichenden Spielverläufe
aufgezehrt. Der Gewinn entsteht nur, wo die Variante wenig verändert.

**Warum die Verläufe auseinanderlaufen.** Die Variante zieht andere Karten,
der Pilot trifft ab dem ersten abweichenden Zug andere Entscheidungen, und
in einem 4- bis 6-Plätze-Spiel verzweigt sich der Verlauf über Dutzende
Entscheidungen aller Plätze. Erwartbar ist daher: φ (Korrelation der
Arm-Ergebnisse im Seed) startet bei 1 für die identische Liste (Zwillingsläufe
desselben Codes liefern identische Sieger und Hashes, 36 von 36 in
`docs/performance/PILOT_CALIBRATION_REAL_PLAYERS_2026-11-09.md` —
`CODE_DERIVED`) und fällt mit der Größe der Änderung. Ein Kartentausch
verändert nur die Partien, in denen die getauschte Karte überhaupt erscheint;
ein Umbau von zehn Karten verändert fast jede Partie.

**So misst man die tatsächliche Stärke aus vorhandenen Serien** (keine neuen
Partien nötig, nur Auswertung abgeschlossener gepaarter Läufe):

1. Aus der Paartabelle des Laufs (Basis-Sieg ja/nein × Variante-Sieg ja/nein
   je Seed × Sitzposition): q̂ = Anteil diskordanter Paare, π̂ = Anteil der
   diskordanten Paare, die die Variante gewinnt. Es gilt Δ̂ = q̂·(2π̂ − 1).
2. φ̂ aus der Vierfeldertafel: φ̂ = (n₁₁n₀₀ − n₁₀n₀₁) /
   √(n₁·n₀·n·₁n·₀). Das ist die direkt messbare „geteilte Seed-Schwierigkeit".
3. Cluster-Stärke innerhalb eines Seeds: Anteil der Seeds, deren diskordante
   Paare mehrheitlich dasselbe Vorzeichen tragen (der Parameter w der
   Repo-Simulationen in `docs/performance/VERDICT_CLUSTER_T_2026-10-31.md`) —
   er bestimmt, wie weit die Cluster-Korrektur die iid-Größe aufbläht.
4. Der Runner berichtet die realisierte erkennbare Differenz bereits am Ende
   jedes Laufs (Workflow Schritt 4: „the run prints its own figure at the
   end") — dieser Wert ist die gemessene Paarungsstärke des konkreten Laufs
   und gehört in jeden Serienbericht.

**Planungsregel daraus:** Nach dem ersten Look (Abschnitt 4) wird q̂ aus den
bis dahin gespielten Paaren geschätzt und die Restgröße neu geplant
(Nuisance-Parameter-Nachschätzung; sie verändert die Ziel-Differenz und das
α nicht). Ein fester q-Wert für „den einen Kartentausch" ist im Repo
**`UNKNOWN`**: Es liegt kein gespeicherter gepaarter Lauf mit Paartabelle
eines Einzelkarten-Tauschs vor, aus dem sich q̂ belegen ließe. Die
Simulationsannahmen der E6-Dokumente (Diskordanz 0,10 unter H₀, 0,25 mit
Effekt) sind `SYNTHETIC` und keine Messung an echten Deck-Varianten.

**Wann Paarung hilft (Break-even).** Gepaart braucht ⌈z² · (q − Δ²)/Δ²⌉ Paare,
ungepaart ⌈z² · [p₀(1−p₀) + p₁(1−p₁)]/Δ²⌉ Partien je Arm; mit gleichem
Design-Effekt auf beiden Seiten hilft die Paarung genau dann, wenn
q − Δ² < p₀(1−p₀) + p₁(1−p₁) (mit der konservativen Näherung Var(d) ≈ q:
q < p₀(1−p₀) + p₁(1−p₁)). Der Wert der rechten Seite beträgt (nachgerechnet,
Δ = 5 / 10 / 15 pp): 4 Plätze 0,3975 / 0,415 / 0,4275; 5 Plätze 0,3475 /
0,37 / 0,3875; 6 Plätze 0,3086 / 0,3344 / 0,3553; 2 Plätze 0,4975 / 0,49 /
0,4775. Bei 4 Plätzen ist q = 0,40 daher gerade neutral (2.184 Paare gepaart
gegenüber 2.184 Partien je Arm ungepaart, beides mit DEFF 1,75), bei 5 und
6 Plätzen wäre q = 0,40 schlechter als ungepaart. „Paarung schadet nie" ist
damit nicht belegt; belegt ist: Sie gewinnt, wo q unter dem Break-even liegt.

**Empfehlung:** Paarung als Standard (bei q unter dem Break-even gewinnt sie,
bei 4 Plätzen und q = 0,40 ist sie neutral; die Gleichung oben zeigt, wann nicht),
aber die Seriengröße mit q = 0,40 planen, solange kein gemessenes q̂ des eigenen
Decks vorliegt.
Ein kleineres q darf erst nach einem gemessenen ersten Look in die Planung.

---

## 4. Frage 3: Weiterlaufen lassen, bis es reicht (sequenzielles Testen)

**Verfahren der Wahl ist bereits im Repo gebaut** — für die
Vergleichs-Lane (`full_game_comparison.py`), nicht für den Studio-Serien-
Runner: `--stop-when-decided` mit festen Looks und einer
Lan-DeMets-Ausgabenfunktion vom O'Brien-Fleming-Typ
(`sequential_look_alphas`). Jeder Look k entscheidet auf dem Inkrement
a(t_k) − a(t_{k−1}) der Ausgabenfunktion a(t) = 2 − 2Φ(z/√t); die
Union-Bound über die Looks hält das Gesamt-α konservativ ein (obere Schranke),
ohne Annahmen über die Abhängigkeit der Looks. Innerhalb eines Looks korrigiert Holm über
mehrere Varianten. Doku: `docs/performance/SEQUENTIAL_LOOK_LEVELS_2026-10-31.md`,
Workflow Schritt 4. `CODE_DERIVED`

Look-Level bei α = 0,05 (nachgerechnet, Gegenprobe an den dokumentierten
Beispielen bestanden: 2 Looks → 0,0056/0,0444; 4 Looks → 0,0001/0,0055/
0,018/0,026):

| Plan | Looks (kumulierte Seeds) | Level je Look |
|---|---|---|
| 120 Seeds, alle 30 | 30 / 60 / 90 / 120 | 0,0001 / 0,0055 / 0,0181 / 0,0264 |
| 160 Seeds, alle 40 | 40 / 80 / 120 / 160 | 0,0001 / 0,0055 / 0,0181 / 0,0264 |
| 160 Seeds, alle 20 | 20 / … / 160 (8 Looks) | 0,0000 / 0,0001 / 0,0013 / 0,0042 / 0,0076 / 0,0105 / 0,0125 / 0,0139 |

Die Level hängen nur an den Informationsanteilen t, nicht an der absoluten
Seed-Zahl. Frühe Looks entscheiden nur bei überwältigender Evidenz; der
letzte Look bekommt mehr als α/Looks.

**Regeln für den Einsatz (Anschluss an Issue #1267, „Serie stoppt bei klarem
Ergebnis"):**

1. Look-Punkte **vor** dem Start festlegen (z. B. alle 40 Seeds) und im
   Serienbericht ablegen. Nachschauen außerhalb der Looks ist unzulässig —
   genau das bläht sonst die Fehlerquote (die Repo-Simulationen zeigen für
   unkorrigiertes Dauer-Nachschauen Fehlerquoten weit über 5 %;
   `VERDICT_HOLM_VARIANTS_2026-10-31.md` misst schon für das
   bloße Auswählen unter Varianten ohne Korrektur 8,9 % (K = 5, w = 0) bzw.
   35,4 % (K = 10, w = 1), Abschnitt 8). `CODE_DERIVED`
2. Wenige, große Looks statt vieler kleiner: 3–5 Looks. Ein Look braucht bei
   voller Rotation mindestens ~10 Seeds, darunter kann die Urteilsregel
   (Zeichentest + Cluster-t) nicht entscheiden (Workflow Schritt 4).
3. Ehrliche Erwartung an die Ersparnis: Die Repo-Simulation (1.200 Läufe je
   Zelle) zeigt mittlere Seed-Zahlen nahe am Maximum (z. B. 54,5 von 60) —
   frühes Stoppen spart bei realistischen Effekten (≤ 15 pp) kaum Partien.
   Der Wert des Verfahrens ist nicht die Ersparnis, sondern dass eine Serie
   **weiterlaufen darf**, ohne dass ihr Ergebnis verfälscht wird.
   `CODE_DERIVED` (`SEQUENTIAL_LOOK_LEVELS_2026-10-31.md` Abschnitt 3)
4. **Futility (Stoppen bei Aussichtslosigkeit) ist im Repo nicht gebaut**
   (ausdrücklich „Not done" in beiden E6-Dokumenten). Empfehlung als
   Planungsregel, nicht als Verfahren: Eine Serie darf als `UNDERPOWERED`
   geschlossen werden, wenn nach einem Look selbst der günstigste noch
   erreichbare Ausgang (alle restlichen diskordanten Paare zugunsten einer
   Seite) kein entschiedenes Urteil mehr ergeben könnte — eine rein
   kombinatorische Schranke ohne α-Verbrauch. Eine kalibrierte
   Conditional-Power-Regel ist `UNKNOWN`, solange sie nicht simuliert und
   dokumentiert ist.
5. Der Studio-Serien-Runner (`src/commander_lab/studio/simulations.py`)
   kennt heute **kein** sequenzielles Stoppen: Er aggregiert abgeschlossene
   Serien mit Wilson-Intervallen (Abschnitt 5). Wer im Studio „bis es
   reicht" laufen lassen will, braucht entweder den Vergleichs-Runner oder
   die Umsetzung dieser Regeln in #1267. Ein Wilson-Intervall, das man
   nach jedem Spiel prüft, ist **kein** gültiges Stopp-Verfahren.

**Geprüfte Alternativen (Ergänzung 2026-11-14).** Drei weitere
Verfahrensfamilien wurden gegen diese Empfehlung geprüft:

- **SPRT (Wald 1945).** Der sequenzielle Likelihood-Quotienten-Test ist für die
  einfache Frage „Δ = 0 gegen ein festes Δ = δ" im Erwartungswert optimal,
  kennt aber keine zusammengesetzte Zielgröße bei unbekanntem q, keine
  Cluster-Struktur (Seeds mit Rotationen) und keine obere Seriengröße — die
  Serie liefe, bis eine Grenze fällt. Für ein Budget-Design mit festen Looks
  ist er das falsche Werkzeug.
- **Bayes-Faktoren.** Ihre Interpretation hängt nicht von der Stopp-Regel ab
  (Rouder 2014); mit Standard-Priors („default priors") kann die Kalibrierung
  unter optionalem Stoppen aber brechen (de Heide & Grünwald 2021). Vor allem:
  Die Urteils-Skala des Repos ist über die E6-Simulationen frequentistisch
  kalibriert; ein Rahmenwechsel würde diese Kalibrierung entwerten und eine
  eigene Simulations-Kalibrierung verlangen.
- **Konfidenz-Sequenzen / Always-valid-Verfahren (Howard u. a. 2021).**
  Zeitgleich gültige Intervalle erlauben Nachschauen zu jedem beliebigen
  Zeitpunkt ohne feste Looks. Sie sind an jedem festen Zeitpunkt aber breiter
  als die OBF-Grenzen — der Preis der beliebigen Stoppzeit — und im Repo
  weder gebaut noch kalibriert.

Die Empfehlung bleibt: Lan-DeMets/O'Brien-Fleming mit festen Looks und Holm —
gebaut, per Simulation kalibriert und im Workflow verankert. Ein Wechsel käme
nur mit eigener Kalibrierungs-Simulation in Frage und ist für die Serienfrage
dieses Plans nicht nötig.

---

## 5. Frage 4: Kennzahlen neben der Siegrate

Bei kleinen Serien trägt eine binäre Siegquote wenig Information (bei
n = 30 ist ihr Wilson-Intervall ±14,9 Prozentpunkte breit, Abschnitt 8).
Diese Kennzahlen existieren bereits oder sind aus den vorhandenen Logs
ableitbar — mit Angabe, wo sie heute schon berichtet werden:

| Kennzahl | Trägt mehr, weil … | Stand im Repo |
|---|---|---|
| Platzierung / Finishing-Score je Partie | Nutzt die volle Rangfolge statt nur Sieg/Niederlage; ein Deck, das regelmäßig Zweiter wird, ist messbar besser als eines, das früh ausscheidet | Vergleichs-Lane: `mean_finishing_score` in `ContenderSummary` (`full_game_comparison.py`, aus `lost_on_turn`, #875). Studio-`GameSummary` führt nur `winner_seats` — Platz des Ausscheidens ist dort **nicht** enthalten (`NOT_MEASURED` im Studio-Runner) |
| Runden/Spielzüge bis zum Ausscheiden des eigenen Decks | Überlebenszeit ist eine stetige Größe mit weit kleinerer relativer Streuung als die Siegquote | Aus den Spiel-Logs ableitbar (eigene Zugzahl wird berichtet: `rounds_own_turns`, Workflow Schritt 5); im Studio nur `rounds` (Partielänge) vorhanden |
| Erster Commander-Wurf (eigene Runde) | Direktes Maß für die Commander-Verfügbarkeit, reagiert auf Ramp-Änderungen lange vor der Siegquote | Vorhanden: `commander_first_cast_round` (Pilot-Report), `first_cast_round` je Karte (Studio-Telemetrie, `simulations.py`) |
| Entscheidungen je Partie, Partielänge (Runden) | Spieltempo/Unterschied im Spielverlauf; Plausibilitätskontrolle, ob sich überhaupt etwas verändert hat | Vorhanden: `decision_count`, `rounds` in `GameSummary` |
| Angeboten/Gewirkt je Karte (Offer-/Cast-Raten) | Pro-Karten-Sicht ohne Kausalanspruch; erkennt tote Karten und nie genutzte Optionen | Vorhanden: Studio-Telemetrie + #1231-Spezifikation (`games_offered`, `games_cast_after_offer`, `mean_first_cast_round`) |
| Mana je Zug, Verweildauer auf der Hand, Zahl der Prioritätsfenster | Wären informativ für Ramp- und Kurvenfragen | **`NOT_MEASURED`** — der Bridge-Event-Strom liefert sie pro Karte nicht (#1231 Abschnitt 2, Phase-7-Spezifikation Abschnitt 3). Kein Plan darf sie voraussetzen |

`CODE_DERIVED` (Spalte „Stand"), Bewertung der Aussagekraft `MODELED`.

**Berichtsform je Kennzahl:**

- Anteile (Siegquote, Cast-Raten): Wilson-Intervall 95 % (Repo-Formel in
  `simulations.py`, `wilson_score_interval`), immer mit Nenner.
- Stetige Kennzahlen (Runden, Zugzahlen, Finishing-Score): Im gepaarten
  Vergleich als **Paardifferenz** berichten (Mittelwert der Differenzen mit
  Cluster-Intervall über die Seeds, wie `cluster_difference_interval_95`
  der Vergleichs-Lane), nicht als zwei getrennte Mittelwerte. Differenzen
  gleicher Seeds streuen weit weniger als die Rohwerte.
- Verteilungen statt nur Mittelwerte, wo die Form die Aussage ist
  (Ausscheide-Runde: Median + Quartile).
- Kausale Sprache bleibt der Siegquote des gepaarten Tauschs vorbehalten.
  Pro-Karten-Kennzahlen sind Beobachtungen einer Serie (Owner S3), keine
  Kartenstärke — #1231 Abschnitt 3.1 zeigt die Verzerrungen naiver
  In-Game-Vergleiche (Überlebenden-Effekt, Spiellängen-Bias).

---

## 6. Frage 5: Feste Gegner-Pods gegen zufällige Pods

**Der Pod ist Teil der Zielgröße.** „Variante schlägt Basis" gilt immer nur
gegen die Gegner, an denen es gemessen wurde. Dass das keine Formsache ist,
zeigt die Baseline-Messung 2026-11-09: In zwei von drei festen Pods gewann
ein einzelner Gegner 9 bzw. 10 von 12 Partien; die Sieganteile des eigenen
Decks über die drei Pods waren 2/12, 3/12 und 0/12
(`docs/performance/CHULANE_BASELINE_4P_2026-11-09.md`). Die beobachtete
Streuung der Pod-Anteile (SD ≈ 0,127) liegt über der reinen Binomial-
Streuung bei 12 Partien (≈ 0,100) — bei nur drei Pods ist das eine
Illustration, kein Varianzkomponenten-Nachweis. `MODELED` aus
`CODE_DERIVED`-Zählungen.

**Verzerrungsrichtungen:**

- *Feste Pods:* Kein Pod-Rauschen **innerhalb** des Vergleichs (beide Arme
  sehen denselben Pod — die Paarung wirkt auch hier), dafür Überanpassung:
  Eine Variante kann gegen genau diese drei Gegner besser sein und gegen
  den Rest des Pools schlechter. Vergleiche über die Zeit bleiben dafür
  exakt vergleichbar.
- *Zufällige Pods (mit festem Seed):* Das Ergebnis mittelt über die
  Pod-Zusammensetzung und trägt weiter, aber die Pod-Ziehung wird selbst
  eine Varianzquelle, wenn die Arme unterschiedliche Pods sehen. **Nur
  gepaart zulässig:** Pod je Seed ziehen, beide Arme spielen denselben
  gezogenen Pod. Dann bleibt die Paarung intakt und die Zielgröße wird
  „mittlerer Vorteil über die Pod-Verteilung des Pools".

**Empfehlung:**

1. Für Deck-Entscheide (die eigentliche SIMULATE-Frage): feste Pods, aber
   **mindestens die drei Standard-Pods** des Projekts, Ergebnis je Pod und
   gepoolt berichtet. Ein Entscheid, der nur in einem Pod trägt, wird als
   Pod-Befund berichtet, nicht als Deck-Befund.
2. Für Breiten-Checks (neues Deck, Pool-Änderung): gepaarte Zufalls-Pods
   aus dem Precon-Pool mit vorab fixierter Seed-Liste — die Roadmap hält
   beide Verfahren ausdrücklich nebeneinander (S-5 in
   `docs/STUDIO_ROADMAP_20261112.md`: „Fixed pods for comparisons over
   time, random pods against overfitting"). `CODE_DERIVED`
3. Die exakte Zahl nötiger Pods für eine vorgegebene Verallgemeinerungs-
   Genauigkeit ist **`UNKNOWN`**: Dazu müsste die Pod-Varianzkomponente der
   *Differenz* Δ aus mehreren gepaarten Läufen über verschiedene Pods
   geschätzt werden; solche Läufe liegen nicht vor. Drei Pods sind die
   begründete Untergrenze (kleinste Zahl, bei der ein einzelner Pod das
   Gesamtergebnis nicht mehr allein drehen kann und ein Pod-Ausreißer
   sichtbar wird), keine gemessene Optimalzahl.

---

## 7. Frage 6: Platzrotation

Der Sitzeffekt ist größer als jede Ziel-Differenz dieses Plans: In 183
Precon-Pods gewann Platz 1 38,8 % und Platz 4 10,4 % der Partien
(`docs/DECK_VARIANT_WORKFLOW.md` Schritt 5). Auch die öffentlichen
Playgroup-Zahlen zeigen Platz 1 bei 45,33 % (n = 674)
(Phase-7-Spezifikation, Abschnitt 2). Ein Vergleich, in dem Basis und
Variante unterschiedliche Sitzverteilungen haben, misst den Sitz, nicht
das Deck. `CODE_DERIVED`

**Regel: vollständige Rotationszyklen.** Je Seed spielt das eigene Deck
jede der s Sitzpositionen genau einmal — so arbeitet der Vergleichs-Runner
(4 Rotationen je Seed bei 4 Plätzen). Damit ist der Sitzeffekt orthogonal
zum Deck-Effekt: Er erhöht die Streuung innerhalb des Seeds (deshalb die
Cluster-Behandlung), verzerrt Δ aber nicht. „Wie viele Rotationen sind
nötig" hat damit eine exakte Antwort: **s Rotationen je Seed, keine
Teilrotationen.** Eine Serie endet immer an einer Zyklusgrenze; die
Seed-Zahlen der Tabellen in Abschnitt 2.2 sind bereits in dieser Einheit
gerechnet (Seeds × s Paare).

Wer aus Laufzeitgründen ohne volle Rotation arbeiten will (z. B. Screening),
muss die Sitzposition über die Seeds deterministisch durchrotieren (Seed k
→ Platz k mod s), je Platz gleich viele Partien je Arm fahren und die
Ergebnisse je Platz berichten; das Ergebnis ist dann ein Screening ohne
Urteilsanspruch, weil Sitz- und Seed-Effekte konfundiert bleiben.
Empfehlung: nur für Vorab-Sichtungen, nie für ein `VARIANT_BETTER`-Urteil.

Für 2 Plätze gilt Entsprechendes mit 2 Rotationen (Anfangsplatz); bei 5
und 6 Plätzen ist die Rotation Teil des Designs, auch wenn diese
Platzzahlen ihre eigene Qualifikation noch ausstehen haben
(Owner-Entscheid A8).

---

## 8. Multiplizität: mehrere Varianten, mehrere Karten

**Mehrere Varianten in einem Lauf:** Holm-Korrektur ist gebaut und
Pflicht (`holm_adjust`, definiert in `src/commander_lab/decision_statistics.py:130`,
von `full_game_comparison.py` importiert; ein entschiedenes
Urteil gilt nur mit Holm-adjustiertem p unter dem Level). Ohne Korrektur
stieg die Falsch-Urteils-Quote in der Repo-Simulation (α = 0,05, 25 Seeds,
je Seed 4 Rotationen; w = Cluster-Stärke) bei K = 5 Varianten auf 8,9 % (w = 0)
bzw. 19,7 % (w = 1) und bei K = 10 auf 17,1 % (w = 0) bzw. 35,4 % (w = 1),
jeweils bei nominal 5 %; mit Holm 0,6 % / 2,0 % (K = 5) und 0,6 % / 1,5 % (K = 10).
`CODE_DERIVED` (`VERDICT_HOLM_VARIANTS_2026-10-31.md`)

**Preis der Korrektur** (Bonferroni-Näherung α/K als Planungsobergrenze;
Holm ist im Mittel günstiger). Fallzahl-Faktor bei 4 Plätzen, Δ = 5 pp:

| Familie K | α je Test | Faktor ungepaart | Faktor gepaart (q = 0,40) |
|---|---|---|---|
| 1 | 0,05 | 1,00 (1.248 / 1.247) | 1,00 |
| 2 | 0,025 | 1,21 | 1,21 |
| 5 | 0,01 | 1,49 | 1,49 |
| 10 | 0,005 | 1,70 | 1,70 |
| 99 (alle Karten eines Decks) | 0,0005 | 2,38 | 2,38 |

`MODELED`, nachgerechnet. Konsequenz: Varianten **einzeln** in getrennten
Läufen zu prüfen ist nicht billiger (die Familie ist der Lauf, aber wer
zehn Varianten nacheinander „bis eine auffällt" testet, betreibt dieselbe
Auswahl ohne Korrektur). Arbeitsregel: höchstens ~5 Varianten je
Fragestellung, Familie vorab benennen, oder die Varianten in einer
festen Reihenfolge mit Gatekeeping prüfen (erst die Gesamtfrage, dann
Einzelne).

**Pro-Karten-Kennzahlen:** Bei ~99 Karten × mehreren Kennzahlen ist ein
einzelnes „auffälliges" Intervall erwartbar Zufall. Deshalb gilt die
Regel des Pilot-Reports (Workflow Schritt 5) allgemein: **Eine**
Primärkennzahl wird vor den Partien benannt und allein getestet; alle
anderen sind explorativ und werden mit Holm über die bewegten Kennzahlen
berichtet. Die Telemetrie-Spezifikation (#1231 Abschnitt 5) setzt für
rein deskriptive Pro-Karten-Anzeige eine Mindestbasis von
`games_offered ≥ 50` vor; kausale Kartenurteile bleiben an die Fallzahlen
dieses Plans gebunden.

**Mindest-Stichprobe je Zelle** (Wilson-Intervall 95 % bei p̂ = 25 %,
nachgerechnet mit der Repo-Formel):

| n | Wilson-Intervall | Halbbreite |
|---|---|---|
| 12 | 8,9 % – 53,2 % | ±22,2 pp |
| 30 | 13,0 % – 42,7 % | ±14,9 pp |
| 50 | 15,1 % – 38,5 % | ±11,7 pp |
| 100 | 17,5 % – 34,3 % | ±8,4 pp |
| 200 | 19,5 % – 31,4 % | ±6,0 pp |
| 400 | 21,0 % – 29,5 % | ±4,2 pp |
| 1.248 | 22,7 % – 27,5 % | ±2,4 pp |

Darunter (n < 30 je Zelle) wird kein Anteil berichtet, nur die Zählung
selbst („3 von 12"), weil das Intervall sonst eine Genauigkeit vortäuscht,
die nicht da ist. (#1231 nennt für n = 12 per Normalapproximation
±24,5 pp; das Wilson-Intervall oben ist die im Studio verwendete Form.)

---

## 9. Gescheiterte Partien (ENGINE_FAILURE)

Owner-Entscheid S3 ist eindeutig: Abgebrochene oder gescheiterte Partien
werden getrennt berichtet und sind keine Niederlagen. Der Serien-Runner
zählt sie bereits separat (`games_failed`, `failure_class` je Partie in
`simulations.py`). Für den **Vergleich** legt dieser Plan fest:

1. **Paarweises Zensieren:** Ein Paar zählt nur, wenn **beide** Arme
   beendet sind. Scheitert eine Seite, fällt das Paar aus der
   Differenz — sonst erzeugt eine höhere Failure-Quote der Variante
   (z. B. weil sie eine Engine-kritische Karte enthält) einen scheinbaren
   Nachteil oder Vorteil. Die zensierten Paare werden mit Failure-Klasse
   je Arm berichtet.
2. **Asymmetrie-Warnung:** Unterscheiden sich die Failure-Quoten der Arme
   sichtbar (Richtwert: mehr als 2 Prozentpunkte Differenz oder eine
   Failure-Klasse, die nur in einem Arm auftritt), ist das Urteil
   `UNKNOWN`, bis die Ursache geklärt ist — Failure kann mit dem Ausgang
   zusammenhängen (lange, komplexe Partien scheitern eher), dann ist das
   Zensieren selbst eine Verzerrung.
3. **Worst-Case-Schranke als Sensitivität:** Zu jedem entschiedenen
   Urteil wird die Schranke mitberichtet, die entstünde, wenn alle
   gescheiterten Varianten-Partien Niederlagen und alle gescheiterten
   Basis-Partien Siege wären (und umgekehrt). Die Schrankenbreite wächst
   um die Summe der Failure-Anteile beider Arme; bei 5 % Failures je Arm
   sind das bis zu 10 pp — so breit wie ein Ziel-Effekt. Ein Urteil, das
   unter der Worst-Case-Schranke kippt, wird als empfindlich markiert.
4. **Harte Schwelle:** Über 5 % gescheiterte Partien in einem Arm ist
   eine Serie nicht urteilsfähig (`INSUFFICIENT`/`UNKNOWN`), unabhängig
   von der erreichten Partienzahl. Zuerst wird die Failure-Ursache
   behoben, nicht die Serie verlängert.

Punkte 1 und 2 sind die direkte Umsetzung von S3 auf das gepaarte Design;
Punkte 3 und 4 sind Planungsregeln dieses Dokuments (`MODELED`).

---

## 10. Empfohlener Serien-Ablauf (Zusammenfassung)

1. **Fragestellung festlegen:** eine Variante (oder eine benannte Familie
   ≤ 5), eine Primärkennzahl (Standard: Sieganteils-Differenz), eine
   Ziel-Differenz Δ aus {5, 10, 15 pp} — ehrlich nach Erwartung, nicht
   nach Budget.
2. **Größe aus Abschnitt 2.2 ablesen** (gepaart, q = 0,40 als
   Planungsannahme; kleinere q nur mit Messung). Ungepaart nur, wenn ein
   Design kein Pairing erlaubt — dann Abschnitt 2.1.
3. **Design:** feste Pods (≥ 3, Abschnitt 6), vollständige Platzrotation
   (Abschnitt 7), Seeds vorab fixiert (Master-Seed im PR vermerken, wie
   es der Pilot-Report für seine Läufe verlangt).
4. **Looks festlegen:** 3–5 Looks mit Lan-DeMets/OBF-Leveln (Abschnitt 4);
   nach Look 1 q̂ messen und die Restgröße anpassen (Abschnitt 3).
5. **Berichten:** Δ̂ mit Cluster-Intervall, realisierte erkennbare
   Differenz des Laufs, Nenner (geplant/beendet/gescheitert je Arm, je
   Pod), Holm-Stand bei Familien, Worst-Case-Schranke für Failures,
   Urteil aus der bestehenden Skala (`VARIANT_BETTER`, `BASELINE_BETTER`,
   `NO_CLEAR_DIFFERENCE`, `UNDERPOWERED`, `INSUFFICIENT`). „Kein
   belastbarer Unterschied" wird genau so hingeschrieben (Owner S3).

---

## 11. Abgrenzung zu vorhandenen Dokumenten

- **#1231 (`docs/research/STUDIO_TELEMETRY_SPECIFICATION.md`)** definiert
  die Pro-Karten-Telemetrie und rechnet **einen** Fall der Fallzahl-Frage:
  ungepaart, 4 Plätze, 5 pp → 1.248 je Arm. Dieser Plan verallgemeinert
  auf 2–6 Plätze, drei Effektstärken und das gepaarte Design, und ergänzt
  Sequenz-, Multiplizitäts- und Failure-Regeln. Die Telemetrie-Definitionen
  selbst (Offer-/Cast-Raten, `NOT_MEASURED`-Größen) bleiben allein dort.
- **#1141 (`docs/research/PLAYGROUP_LIVE_PHASE7_CARD_INSIGHTS_METRICS_SPEC_20261108.md`)**
  spezifiziert, **was** an Karten- und Spielgrößen messbar ist (inkl.
  Sitzeffekten in öffentlichen Daten) und welche Lebenszyklus-Größen
  fehlen. Dieser Plan beantwortet die davon getrennte Frage, **wie viele**
  Partien eine Aussage braucht; Kennzahlen-Definitionen werden nicht
  wiederholt, nur referenziert.
- **E6-Vergleichs-Lane** (`full_game_comparison.py` und die Dokumente
  `VERDICT_CLUSTER_T_2026-10-31.md`, `VERDICT_HOLM_VARIANTS_2026-10-31.md`,
  `SEQUENTIAL_LOOK_LEVELS_2026-10-31.md`, Workflow Schritt 3/4) hat die
  Verfahren (Paarung, Cluster-t, Holm, Alpha-Spending) bereits gebaut und
  per Simulation kalibriert. Dieser Plan erfindet kein zweites Verfahren;
  er überträgt die vorhandenen auf die Studio-Serienfrage von #1211 und
  macht ihre Annahmen (q, ρ = 0,25) und Grenzen explizit. Wo der
  Studio-Runner die Verfahren noch nicht hat (sequenzielles Stoppen,
  Cluster-Intervalle), ist das als Umsetzungslücke für #1267 benannt,
  nicht als neuer Methoden-Vorschlag.
- **Roadmap S-1/S-3** (`docs/STUDIO_ROADMAP_20261112.md`) bleiben
  unverändert gültig: S-1 ist die Orientierungsserie, S-3 die
  Pro-Karten-Sicht über einer Serie. Dieser Plan liefert die Größen,
  ab denen aus S-1 eine Nachweis-Serie wird.

---

## 12. Quellen

Repo (alle Angaben `CODE_DERIVED`, Stand dieser Recherche):

- `docs/research/STUDIO_TELEMETRY_SPECIFICATION.md` (#1231): Telemetrie,
  Power-Formel und der 1.248-Wert.
- `docs/research/PLAYGROUP_LIVE_PHASE7_CARD_INSIGHTS_METRICS_SPEC_20261108.md`
  (#1141): Messbarkeits-Inventar, Sitzeffekte in Playgroup-Daten.
- `docs/DECK_VARIANT_WORKFLOW.md`: Schritte 2–5 (Planungstabelle,
  Urteilsregeln, Holm, Cluster-Intervalle, Sitzanteile in 183 Precon-Pods,
  225 Partien/Stunde).
- `docs/performance/VERDICT_CLUSTER_T_2026-10-31.md`,
  `docs/performance/VERDICT_HOLM_VARIANTS_2026-10-31.md`,
  `docs/performance/SEQUENTIAL_LOOK_LEVELS_2026-10-31.md`: Kalibrierung
  der Urteilsregeln per Simulation.
- `docs/performance/CHULANE_BASELINE_4P_2026-11-09.md` und
  `docs/performance/PILOT_CALIBRATION_REAL_PLAYERS_2026-11-09.md`:
  Pod-Ergebnisse und Zwillingslauf-Identität.
- `src/commander_lab/engine/rules/full_game_comparison.py`:
  `power_table()`, `sequential_look_alphas()`, Cluster-Statistik;
  `holm_adjust` kommt aus `src/commander_lab/decision_statistics.py:130`
  (dort definiert, in `full_game_comparison.py` importiert).
- `src/commander_lab/studio/simulations.py`: `wilson_score_interval()`,
  `aggregate_batch_results()`, `GameSummary`.
- `docs/OWNER_DECISIONS_STUDIO_20261112.md` (S2, S3, A8),
  `docs/STUDIO_ROADMAP_20261112.md` (S-1, S-3, S-5).

Literatur (Verfahren):

- Wilson, E. B. (1927). Probable Inference, the Law of Succession, and
  Statistical Inference. *JASA* 22(158), 209–212.
  https://doi.org/10.1080/01621459.1927.10502953
- McNemar, Q. (1947). Note on the sampling error of the difference
  between correlated proportions or percentages. *Psychometrika* 12,
  153–157. https://doi.org/10.1007/BF02295996
- Connor, R. J. (1987). Sample size for testing differences in
  proportions for the paired-sample design. *Biometrics* 43(1), 207–211.
  https://doi.org/10.2307/2531961
- O'Brien, P. C. & Fleming, T. R. (1979). A multiple testing procedure
  for clinical trials. *Biometrics* 35(3), 549–556.
  https://doi.org/10.2307/2530245
- Lan, K. K. G. & DeMets, D. L. (1983). Discrete sequential boundaries
  for clinical trials. *Biometrika* 70(3), 659–663.
  https://doi.org/10.1093/biomet/70.3.659
- Holm, S. (1979). A simple sequentially rejective multiple test
  procedure. *Scandinavian Journal of Statistics* 6(2), 65–70.
  https://www.jstor.org/stable/4615733
- Liang, K.-Y. & Zeger, S. L. (1986). Longitudinal data analysis using
  generalized linear models. *Biometrika* 73(1), 13–22.
  https://doi.org/10.1093/biomet/73.1.13
- Wald, A. (1945). Sequential Tests of Statistical Hypotheses. *The
  Annals of Mathematical Statistics* 16(2), 117–186.
  https://doi.org/10.1214/aoms/1177731118
- Rouder, J. N. (2014). Optional stopping: No problem for Bayesians.
  *Psychonomic Bulletin & Review* 21(2), 301–308.
  https://doi.org/10.3758/s13423-014-0595-4
- de Heide, R. & Grünwald, P. D. (2021). Why optional stopping can be a
  problem for Bayesians. *Psychonomic Bulletin & Review*.
  https://doi.org/10.3758/s13423-020-01803-x
- Howard, S. R., Ramdas, A., McAuliffe, J. & Sekhon, J. (2021).
  Time-uniform, nonparametric, nonasymptotic confidence sequences.
  *The Annals of Statistics* 49(2), 1055–1080.
  https://doi.org/10.1214/20-AOS1991

---

## Anhang: Formeln, Annahmen, Grenzen

**Formeln.** Ungepaart: Abschnitt 2.1. Gepaart (Planung):
N = ⌈((z₁₋α/₂ + z₁₋β)·σ_d/Δ)²⌉ mit σ_d = √q (Repo-Anker 0,63 für
q = 0,40); Cluster: DEFF = 1 + (s−1)ρ. McNemar-Gegenprobe (Connor):
m = [z₁₋α/₂·½ + z₁₋β·√(π(1−π))]² / (π − ½)² diskordante Paare mit
π = (1 + Δ/q)/2, Gesamtpaare = m/q. Wilson-Intervall: wie
`wilson_score_interval` im Code. Sequenziell: a(t) = 2 − 2Φ(z/√t),
Look-Level = Inkremente (Repo-Implementierung).

**Annahmen, die man kennen muss:**

- Normalapproximation für Anteile. Bei 2 Plätzen (p₀ = 0,50) und bei den
  kleinen Fallzahlen der 15-pp-Zeilen ist sie grob; die Tabellen sind
  Planungsgrößen, keine exakten Tests. Das Urteil am Ende fällt der
  exakte Zeichentest/Cluster-t des Runners, nicht diese Approximation.
- ρ = 0,25 (Intra-Seed-Korrelation der Paare) ist die Repo-Planungsannahme
  für 4 Plätze. Für 2, 3, 5 und 6 Plätze ist derselbe Wert in die
  DEFF-Formel eingesetzt — eine Übertragung, keine Messung (`MODELED`).
- p₀ = 1/s unterstellt einen ausgeglichenen Tisch. Gegen einen
  übermächtigen Standard-Pod (Baseline-Befund: ein Gegner gewinnt 10 von
  12) liegt der wahre Anteil des eigenen Decks darunter; die Fallzahlen
  ändern sich dann nur wenig (die Varianz p(1−p) ist nahe 0,25 flach),
  aber die Ziel-Differenz muss gegen den **tatsächlichen** Pod-Anteil
  gelesen werden, nicht gegen 1/s.
- Die q-Werte 0,09/0,20/0,40 sind Planungs-Annahmen aus der
  Repo-Planungstabelle, keine Messwerte an Deck-Varianten (Abschnitt 3).

**Nicht abgedeckt (bewusste Grenzen):**

- Keine Fallzahlen für kontinuierliche Primärkennzahlen (Finishing-Score,
  Ausscheide-Runde) — dazu fehlen Streuungs-Messwerte aus echten Serien;
  bevor eine solche Kennzahl primär wird, braucht sie eine eigene
  Varianz-Schätzung aus einer abgeschlossenen Serie (`UNKNOWN`).
- Keine kalibrierte Futility-Regel (Abschnitt 4, Punkt 4).
- Keine Aussage zu 5/6 Plätzen jenseits der Fallzahl-Arithmetik: Diese
  Platzzahlen haben ihre eigene Qualifikation noch ausstehen
  (Owner-Entscheid A8); längere Partien verschlechtern die Laufzeit je
  Partie zusätzlich.
- Kein Winner's-Curse-Ausgleich für berichtete Differenzen nach Auswahl
  unter mehreren Varianten (die Holm-Doku nennt dieselbe Lücke).
- Keine neuen Partien und keine Pilot-Mikro-Messreihen für diese
  Recherche (Vorgabe des Issues und Owner-Entscheid S2); alle
  empirischen Anker stammen aus bereits vorhandenen Dokumenten.

**Verifikation (Ergänzung 2026-11-14).** `docs/research/series_statistics_calc.py`
rechnet jede Tabelle dieses Plans aus den Formeln nach und vergleicht sie
Zelle für Zelle mit den gedruckten Werten (ungepaart 15 Zellen zu Power 80 %,
gepaart 7 iid-Werte und 35 Seed-Zellen, dazu die Werte der Abschnitte 0,
2.3–2.6, 3, 4, 6 und 8). Ergebnis: Alle Werte reproduziert bis auf zwei
Rundungsreste, die im Text korrigiert sind (Abschnitt 2.4: 552/225 = 2,45,
also ≈ 2,5 statt 2,4 Stunden; Abschnitt 2.5: erkennbare Differenz bei
30 Partien je Arm = 33,5 statt 33,6 Prozentpunkte). Zwei Präzisierungen aus
derselben Nachrechnung: (1) Die McNemar-Gegenprobe (Connor) liegt in sechs
der sieben zulässigen Zellen 1,3 % bis 19,6 % unter der Repo-Planung, in der
Zelle Δ = 5 pp/q = 0,40 aber 0,2 % darüber (1.250 gegen 1.247 Paare), weil
der Repo-Anker σ_d = 0,63 knapp unter √0,40 = 0,632 liegt — der Satz in
Abschnitt 2.2, die Repo-Methode sei die konservativere, gilt dort nur bis
auf diese 3 Paare. (2) Die exakte Zeichentest-Power (Binomial-Enumeration im
Rechenskript) liegt an zwei Planungszellen bei 78,0 % (628 Paare, q = 0,20,
Δ = 5 pp) und 77,7 % (139 Paare, q = 0,40, Δ = 15 pp) statt der nominalen
80 % der Normalapproximation — die Diskretheit des exakten Tests kostet rund
2 Prozentpunkte Power; die Tabellen bleiben damit als Näherung
gekennzeichnet, nicht als exakte Aussage.
