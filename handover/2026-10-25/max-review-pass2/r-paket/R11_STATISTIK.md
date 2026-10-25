# R-11 — Statistik: Plan-Zahlen an echten Deckpaaren kalibrieren

Stand: 2026-10-25. Grundlage: 03_VERBESSERUNGEN.md (R-11), #884, #912,
#839, M4-Aggregate, #999 M3-Power-Tabelle. Keine neuen Spiele in diesem
Dokument — alles hier ist Nachrechnung vorhandener Daten (DIRECTLY_VERIFIED)
oder Formel (MODELED, als solche markiert).

## 1. Was #884/#912 behaupten — und was davon Annahme ist

- #884: Der Deck-Vergleich meldet Intervall, erkennbare Differenz und
  benötigte Paare (reine Report-Erweiterung, keine Spielmessung).
- #912: Die Plan-Zeile nimmt **Paar-SD 0,63** an und labelt, dass sie
  unabhängige Spiele annimmt und identisch endende Paare „die echte Zahl
  kleiner machen". Die 0,63 ist damit selbst als Annahme markiert —
  aber nie an echten Deckpaaren kalibriert worden.
- #839: Sequentielles Stoppen mit Bonferroni-geteiltem Per-Look-Alpha
  (konservativ, aber ohne Alpha-Inflation).

## 2. Neu gemessen: Die Paar-SD ist keine Konstante (DIRECTLY_VERIFIED)

Aus `~/workspace/tmp/m4/aggregate_rogshai.json` und
`aggregate_chulane.json` (je 3 Bündel × 200 Paare, 1.200 Paare gesamt).
Gepaarte Differenz d ∈ {−1, 0, +1} (nur Baseline gewinnt / keiner /
nur Variante gewinnt):

| Bündel | n | Diskordanz q | nur Base | nur Var | Paar-SD |
|---|---|---|---|---|---|
| RogShai #1 | 200 | 0,110 | 11 | 11 | 0,332 |
| RogShai #2 | 200 | 0,060 | 6 | 6 | 0,245 |
| RogShai #3 | 200 | 0,120 | 17 | 7 | 0,343 |
| Chulane #1 | 200 | 0,080 | 8 | 8 | 0,283 |
| Chulane #2 | 200 | 0,080 | 8 | 8 | 0,283 |
| Chulane #3 | 200 | 0,095 | 12 | 7 | 0,307 |
| **Gepoolt** | **1.200** | **0,0908** | — | — | **0,301** |

Rechnung gepoolt: q = 109/1.200 = 0,0908, mittlere Differenz −15/1.200 =
−0,0125, SD = √(0,0908 − 0,0125²) = **0,301**.

**Befund:** Die gemessene M4-SD (0,30) ist etwa halb so groß wie #912s
Annahme (0,63). Die 0,63 entspricht q ≈ 0,40 (√0,40 = 0,632) — also einer
viermal so hohen Diskordanz wie in M4. Erklärung: M4-Paare sind
Fast-Zwillinge (nur 1 Karte getauscht, gleiche Seeds) — die meisten
Paare enden identisch, nur 6–12 % sind diskordant. Die Annahme 0,63
gilt für deutlich unähnlichere Deckpaare, nicht für M4-ähnliche.

**Formel (MODELED, aber an #999 validiert):** Für d ∈ {−1, 0, +1} gilt
SD(d) = √(q − δ²) mit Diskordanz q und Effekt δ. Unabhängigkeits-Limit
(zwei unabhängige Bernoulli-Spiele mit p = 0,5): SD → √0,5 ≈ 0,707.
Die Plan-SD muss also je Deckpaar-Ähnlichkeit gewählt werden, nicht als
Konstante aus #912 übernommen.

## 3. Power-Tabelle, erweitert (MODELED, Formel an #999 reproduziert)

McNemar-Formel (80 % Power, α = 5 % zweiseitig):
n = (1,96·√q + 0,84·√(q − δ²))² / δ². Sie reproduziert #999s gepoolte
Spalte (q = 0,0908): 2 Punkte → 1.779 (≈ 1.783), 3 → 790 (≈ 793),
5 → 283 (≈ 286). Rest-Differenz = Rundung der z-Werte.

| Diskordanz q | Paar-SD | 2 Punkte | 3 Punkte | 5 Punkte |
|---|---|---|---|---|
| 0,09 (M4-ähnlich) | 0,30 | 1.779 | 790 | 283 |
| 0,20 (mittlere Änderung) | 0,45 | 3.922 | 1.742 | 626 |
| 0,40 (#912-Szenario) | 0,63 | 7.847 | 3.486 | 1.253 |

Lesart: Wer ein Deckpaar mit 40 % Diskordanz auf 2 Punkte testen will,
braucht ~7.800 Paare — nicht 1.800. Umgekehrt sieht ein M4-ähnliches
Paar mit 200 Paaren nur Effekte ≥ ~5 Punkte (so schon #999 M3).
**Jeder künftige Deckbau-Vergleich muss q vorab schätzen** (aus
Pilot-Änderungsgröße oder einem 24-Paar-Vorlauf) und die Paare aus
dieser Tabelle nehmen — sonst ist das Ergebnis wieder UNDECIDED mit
Ankündigung.

## 4. CRN und die Pflicht-Metrik Divergenzrate (Design, kein Code hier)

Gepaarte Seeds sind Common Random Numbers (CRN): Beide Arme sehen die
gleichen Zufallsströme. Aber jede Pfadänderung verschiebt den
Draw-Index aller Folgeereignisse (Buffalo et al., arXiv:2603.11084,
März 2026, Abstract — aus Pass D, Q6). Die CRN-Annahme bricht, sobald
die Paare früh auseinanderlaufen.

**Pflicht-Metrik künftig, Definition (operational, aus Transkripten):**
Für jedes Paar der erste Frame-Index, an dem sich die gewählten Labels
unterscheiden (Transkripte vorher normalisiert: Per-Run-UUIDs und
Anzeige-Suffixe wie `[d54]` entfernen — Lektion aus dem Max-Review).
- **Divergenzrate(t)** = Anteil Paare mit erstem Unterschied ≤ t.
- **Regel:** Liegt die Divergenzrate vor Entscheidung 100 über 50 %,
  ist die CRN-Annahme als verletzt zu markieren und das Paar wie
  unabhängige Spiele zu werten (SD-Seite 0,63–0,71 der Tabelle, nicht
  die M4-Seite). Liegt sie unter 20 %, gilt die M4-Seite.
- Die Metrik gehört in `pilot_decision_report.py compare` als neue
  Ausgabe (Design; Implementierung nicht in diesem Dokument, kein
  Code-Change hier).

## 5. Alpha-Spending statt „24 Seeds, dann schauen" (Design)

Vorab definierte Looks, z. B. **12 / 24 / 48** (Informationsanteile
0,25 / 0,50 / 1,00), mit O'Brien-Fleming-Grenzen nach Lan–DeMets
(1983) für α = 5 % zweiseitig (Normal-Approximation, MODELED):

| Look | Informationsanteil | z-Grenze (OBF) |
|---|---|---|
| 12 Paare | 0,25 | 3,92 |
| 24 Paare | 0,50 | 2,77 |
| 48 Paare | 1,00 | 1,96 |

Das ersetzt die Bonferroni-Teilung aus #839 (nicht: addiert sich
dazu). OBF spart Alpha für den finalen Look auf — frühe Looks stoppen
nur bei sehr klaren Effekten. Die Looks und die Grenzen müssen vor dem
Lauf im Protokoll stehen (s. R-12); nachträgliches „noch 24 drauf"
ohne Alpha-Anpassung ist Alpha-Inflation und macht das Verdict
ungültig.

## 6. Kalibrierungs-Plan (3 echte Deckpaare, Kosten)

- Paar 1 (RogShai-Variante) und Paar 2 (Chulane-Variante): M4-Daten
  vorhanden (s. Abschnitt 2) — keine neuen Spiele nötig, nur die
  Auswertung oben.
- Paar 3 (ein Precon-Paar, z. B. zwei Precons aus dem Pool): je 100
  gepaarte Spiele neu, Paar-SD + erkennbare Differenz messen, mit
  #912-Annahme (0,63) vergleichen. Kosten (Schätzung aus der
  Abort-Kette: ~62 s/Spiel sequenziell): 200 Spiele ≈ 3,5 h Laufzeit,
  plus Divergenzraten-Auswertung. Erst nach dieser Messung ist die
  0,63-Annahme für Precon-Paare kalibriert statt angenommen.
- Ergebnis: Eine Tabelle „Deckpaar-Typ → q → Paar-SD → Paare für
  2/3/5 Punkte", die jeder künftige Vergleich zitiert statt #912s
  Einzelzahl.

## 7. Evidenzklassen

- M4-Paar-SDs, q = 0,0908, #999-Tabellenwerte: DIRECTLY_VERIFIED
  (nachgerechnet aus `aggregate_*.json` bzw. `~/workspace/tmp/999/BERICHT.md`).
- McNemar-Erweiterungstabelle, OBF-Grenzen: MODELED (Standardformeln,
  an #999 reproduziert bzw. Lan–DeMets 1983).
- CRN-Bruch-Mechanismus: EXTERNALLY_RULE_VALIDATED (Buffalo et al. 2026,
  Abstract; volle Anwendung auf XMage-Seeds: MODELED).
- Paar-3-Kalibrierung: UNKNOWN (nicht gespielt).
