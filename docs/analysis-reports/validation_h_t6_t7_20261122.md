# Validierung Kartenverständnis H gegen Nutzung: T6 Deck-Split, T7 Zeit-Split (2026-11-22)

- **Stand:** Branch `docs/validation-h-t6-t7`, gebaut auf `main` @ `138a50c2`. Refs #1404
  (Builder-Audit Chulane/TAM 2026-11-21, Abschnitt 3 T6/T7, Abschnitt 6 (a) WP 9).
- **Plan vor der Rechnung:** `docs/analysis-reports/validation_plan_h_t6_t7.md`, committet in
  `9d9307ad0d550dca588effc65cd92201130cdfaf`; Planänderung vor jeder Zahl H gegen Ziel in
  `afdccf22795bfeee457331e417a7c34551dfdd00` (Plan §9: Basis ist die Kopie nur mit Universums-Decks).
- **Wirkung:** keine. Produktcode, Index, Stufen, Sortierung und Anzeige bleiben unverändert.
  Kartenverständnis bleibt ein Modellurteil aus dem Regeltext (ein Lauf je Karte).
- **Was gemessen ist:** nur, ob H die zurückgehaltene (T6) oder spätere (T7) Nutzung innerhalb
  gleicher Gruppen ordnet. Das Ziel ist selbst Nutzung; ob H Kartenstärke trifft, misst nur eine
  nutzungsfreie Referenz (T8, Owner-Zeit), nicht dieser Bericht.

## 0. Ergebnis zuerst

- **T6, Gleichstände des Index (G1):** H bricht sie messbar in Richtung der zurückgehaltenen
  Nutzung: ρ_w = 0,106 [0,058; 0,106] (Bootstrap-Perzentil, B = 1000), Faltungen 0,030 bis 0,145,
  Rauschobergrenze 0,227 [0,112; 0,193]. Urteil nach Vorab-Regel `MESSBAR_POSITIV`; „praktisch
  relevant“ (Schwelle 0,10) nur knapp. Die schon gezählte Trainings-Nutzung bricht dieselben
  Gleichstände rund 3,5-mal so stark: ρ_w = 0,368 [0,280; 0,334].
- **T6, gleiche Deckzahl (G2, entscheidend für „Zusatznutzen“):** ρ_w = 0,056 [0,016; 0,068],
  Rauschobergrenze 0,094 [0,018; 0,102]. Urteil nach Vorab-Regel `MESSBAR_POSITIV`, nicht relevant
  (< 0,10). **Nicht robust:** eine von fünf Faltungen ist negativ (−0,039), das nachträgliche
  t-Intervall über die fünf Faltungen enthält 0 ([−0,019; 0,132]).
- **T7, Stichtag 2026-08-09, alle Decks (2.010 nach, 8.118 vor dem Stichtag):** G2 ρ_w = 0,103
  [0,043; 0,144], Rauschobergrenze 0,226 [0,106; 0,270], `MESSBAR_POSITIV`; Sensitivität
  2026-09-30 (1.006 nach): 0,064 [0,012; 0,113], ebenfalls `MESSBAR_POSITIV`. Blindheit des Raters
  gegenüber der späteren Nutzung ist UNKNOWN, darum keine Aussage „vor der Menge“.
- **Fazit:** H liefert nach den vorab festgelegten Regeln einen **messbaren, aber kleinen**
  Zusatznutzen gegenüber dem Index (T6 G2 0,056 bei einer Rauschobergrenze von 0,094); er ist über
  die Trainings-Zusammensetzung nicht robust (1 von 5 Faltungen negativ). Das
  Rauschen innerhalb der Gruppen ist groß: selbst zwei Hälften derselben zurückgehaltenen Decks
  ordnen sich nur mit 0,094 (G2) bzw. 0,227 (G1).

## 1. Herkunft und Eingaben

| Eingabe | Wert |
|---|---|
| Store | Repo-Import-Kopie im Scratch-Ordner (nie im Repo), Schema 21, 10.551 Quelldecks, `source.imported_at` 2026-11-16; SHA-256 `9df80845cb62bb9dd421bdce3f4712804f6c8f40d8691a94a9afe65758be768f`; Import-Commit UNKNOWN |
| Universum | lokale Decklisten „Chulane, Teller of Tales“, dedupliziert: 10.128 Decks, 10.128 von 10.128 datiert (2024-11-13 bis 2026-11-15) |
| H | `data/card_understanding/card_understanding_v2_1.jsonl`, 922 Zeilen, SHA-256 `399a7678eeec0a749b166fbb8a04a97fb24a36387f1eec94afb6018ed907b512` |
| Index | `strength_view.compute`, empfohlene Einstellungen (Bracket „upgraded“), neu gerechnet auf jeder abgeleiteten Store-Kopie |
| Analysekarten | 922 von 927 Poolkarten (H und Index; Tier N fällt heraus), in jeder Faltung und an jedem Stichtag |
| Zwischen-Datei (Scratch) | SHA-256 `f96698481ffa4b62f268c0ec2d05c73491e6fefb221deb6f74ee71e104a11044` |
| Ergebnis-Datei (Scratch) | SHA-256 `f67364d509954af0bf5567697ddd7cf3f3aa4c9fe122d7dd345da09fa2e0d992`; zwei Läufe von `analyse` byte-gleich |
| Skript | `scripts/analysis/validate_h_t6_t7.py`, SHA-256 `9d24815cf5e69362ccf0fd59047a9d5e56e38352f01d45579bd8c0aa683ffc1c` |

Seeds und Teilungen wie im Plan: Faltungen und Hälften über SHA-256 der Deck-ID
(`wp9-t6-folds-20261122:`, `wp9-t6-halves-20261122:`, `wp9-t7-halves-20261122:`), Bootstrap
`random.Random(20261122)`, B = 1000, 0 von 1000 Wiederholungen undefiniert in allen Zellen.

## 2. Prüfungen vor der Auswertung (Plan §7)

| Nr | Prüfung | Ergebnis |
|---|---|---|
| 1 | Empfohlenes Bracket „upgraded“ | ja |
| 2 | Index der Kopie nur mit Universums-Decks = Index des Store | **nein**: 37 von 922 Karten weichen ab, höchstens 0,5 Punkte, 0 von 922 Stufenwechseln; Planänderung §9 (berichtet, kein Abbruch; Basis aller Rechnungen ist diese Kopie) |
| 3 | Karten-Deck-Zuordnung = Zähler des Decklisten-Universums | 922 von 922 gleich |
| 4 | Universum jeder abgeleiteten Kopie = behaltene Menge, Zähler je Karte gleich | ja (5 Faltungen, 2 Stichtage) |
| 5 | Karten mit H im Pool | 922 (922 mit H und Index) |

**Produktbefund aus Prüfung 2 (keine Änderung in diesem Paket):** `universe._resolve` dedupliziert
nach Inhalt **innerhalb** der gewählten Teilmenge. Die Kohorten-Universen der Korpus-Komponenten
filtern erst nach Kohorte und deduplizieren danach; so zählen sie Duplikate mit, die das
Gesamt-Universum schon entfernt hat. Nenner Store gegen Kopie nur mit Universums-Decks: Brackets 4+5
1.066 gegen 1.064, Bracket 2 608 gegen 606, Bracket 5 256 gegen 252. Wirkung auf den Index: 37 von
922 Karten, höchstens 0,5 Punkte, keine Stufe. Ob das gewollt ist, entscheidet der Halter des Index.

## 3. T6 Deck-Split (5 Faltungen à 2.025 bis 2.026 zurückgehaltene Decks)

ρ_w = geschichtete Rangkorrelation (Plan §3), Punkt = Mittel der fünf Faltungen, Intervall =
Bootstrap-Perzentil 95 % über zurückgehaltene Decks.

| Gruppierung | Größe | Punkt | 95-%-Intervall | Faltungen min/max | Urteil |
|---|---|---:|---|---|---|
| G1 Index-Gleichstand | Rauschobergrenze (Hälfte A gegen B) | 0,227 | [0,112; 0,193] | 0,180 / 0,272 | Gate bestanden |
| G1 | H | 0,106 | [0,058; 0,106] | 0,030 / 0,145 | `MESSBAR_POSITIV` (relevant knapp: 0,106 ≥ 0,10) |
| G1 | Vergleich: Trainings-Deckanteil | 0,368 | [0,280; 0,334] | 0,336 / 0,391 | keine Entscheidungswirkung |
| G2 gleiche Deckzahl | Rauschobergrenze | 0,094 | [0,018; 0,102] | 0,061 / 0,129 | Gate bestanden |
| G2 | H | 0,056 | [0,016; 0,068] | −0,039 / 0,110 | `MESSBAR_POSITIV` (nicht relevant) |

- Gruppen je Faltung im Mittel: G1 278, G2 245,4. Karten in informativen Gruppen (mindestens 2 Karten,
  Ziel nicht konstant), kleinste Faltung: G1 718 von 922, G2 735 von 922.
- Gruppen mit ρ_g > 0 (Gruppen ab 3 Karten, über die Faltungen gezählt, beschreibend, nicht
  unabhängig): G1 192 von 327 (Wilson 53,3 % bis 63,9 %), G2 117 von 210 (49,0 % bis 62,3 %).
- Spearman-Brown-Grenze für das Ziel aus allen zurückgehaltenen Decks: G1 0,61, G2 0,42.
- Einordnung ohne Gate (Faltung 0, alle 922 Karten, ohne Gruppen): Spearman H gegen Ziel 0,483,
  Trainings-Anteil gegen Ziel 0,914, Hälfte A gegen Hälfte B 0,851 (die globale Zahl des
  Auftragswortlauts; sie trennt erwartungsgemäß klar von 0 und sagt nichts über Gleichstände).

## 4. T7 Zeit-Split

Gruppen aus dem Index bis Stichtag (Kopie nur mit Decks bis Stichtag); Ziel = Decks nach dem Stichtag
mit der Karte. In G2 ist „Anteil danach“ gleich „Zuwachs“. Eine Kohorte unter 30 Decks nach dem
Stichtag wäre `NOT_RUN`; keine lag darunter.

| Stichtag · Kohorte | Decks vor / nach | G1 Grenze | G1 H | G1 Vergleich Anteil vorher | G2 Grenze | G2 H | Urteil G1 · G2 |
|---|---|---|---|---|---|---|---|
| **2026-08-09 · alle** | 8.118 / 2.010 | 0,227 [0,085; 0,259] | 0,126 [0,059; 0,162] | 0,237 [0,134; 0,272] | 0,226 [0,106; 0,270] | 0,103 [0,043; 0,144] | `MESSBAR_POSITIV` · `MESSBAR_POSITIV` |
| 2026-08-09 · Bracket 3 | 8.118 / 251 | 0,061 [−0,078; 0,211] | 0,132 [0,036; 0,147] | 0,030 [−0,053; 0,065] | 0,225 [0,006; 0,262] | 0,083 [0,020; 0,113] | `KEIN_SCHLUSS` · `MESSBAR_POSITIV` |
| 2026-09-30 · alle | 9.122 / 1.006 | 0,193 [0,052; 0,260] | 0,051 [0,002; 0,112] | 0,076 [−0,004; 0,124] | 0,303 [0,115; 0,308] | 0,064 [0,012; 0,113] | `MESSBAR_POSITIV` · `MESSBAR_POSITIV` |
| 2026-09-30 · Bracket 3 | 9.122 / 136 | 0,233 [−0,025; 0,309] | 0,144 [0,052; 0,147] | −0,031 [−0,085; 0,027] | 0,234 [−0,006; 0,329] | 0,096 [0,032; 0,126] | `KEIN_SCHLUSS` · `KEIN_SCHLUSS` |

- Relevant (≥ 0,10) nach Vorab-Regel: 2026-08-09 alle G1 und G2 (0,126; 0,103, beide knapp);
  2026-09-30 alle nicht.
- Bracket 3 (die Kohorte, für die H gilt) hat nur 251 bzw. 136 Decks nach dem Stichtag; dort
  scheitert das Gate dreimal (Untergrenze der Rauschobergrenze ≤ 0). Das heißt „kein Schluss“, nicht
  „H bringt dort nichts“; wegen der Verzerrung in Abschnitt 5 ist es eher konservativ.

## 5. Eigenschaft des Bootstraps (nachträglich, nach Sicht der Ergebnisse)

Der Punktwert liegt bei allen fünf T6-Kennzahlen am oberen Rand oder oberhalb seines Intervalls.
Ursache ist die Methode, kein Rechenfehler: Ziehen der Decks mit Zurücklegen legt auf jede Zählung
ein zweites Zählrauschen, und das zieht jede Rangkorrelation zu 0 (die Rauschobergrenze am stärksten,
weil beide Hälften verrauscht werden). Abstand Punkt minus Bootstrap-Mittel in T6: G1 H 0,025,
G1 Grenze 0,076, G1 Vergleich 0,061, G2 H 0,014, G2 Grenze 0,037.

Folgen: Untergrenzen liegen zu tief, die Urteile `MESSBAR_POSITIV` sind darum konservativ und gelten
nach der Vorab-Regel. Obergrenzen liegen ebenfalls zu tief und werden hier für keine
„höchstens“-Aussage benutzt. Die Intervallmethode wurde nach Sicht der Ergebnisse **nicht**
gewechselt; die vorab festgelegten Urteile bleiben primär.

**Faltungs-t-Intervall (nachträglich, 4 Freiheitsgrade, aus den fünf Faltungswerten; erfasst auch
die Zusammensetzung des Trainings, die der Bootstrap festhält):**

| T6-Kennzahl | Faltungswerte | Mittel [t-Intervall 95 %] |
|---|---|---|
| G1 H | 0,138 · 0,115 · 0,101 · 0,145 · 0,030 | 0,106 [0,049; 0,163] |
| G1 Rauschobergrenze | 0,219 · 0,272 · 0,180 · 0,237 · 0,228 | 0,227 [0,186; 0,268] |
| G2 H | 0,059 · 0,110 · 0,045 · 0,108 · −0,039 | 0,056 [**−0,019**; 0,132] |
| G2 Rauschobergrenze | 0,100 · 0,086 · 0,061 · 0,095 · 0,129 | 0,094 [0,064; 0,125] |

Unter diesem Intervall wäre T6 G2 nicht von 0 trennbar. T7 hat je Stichtag und Kohorte nur eine
Rechnung; dort gibt es keine solche Prüfung.

## 6. Grenzen

- **Ziel ist Nutzung.** Ein positives ρ_w heißt „H ordnet wie spätere oder zurückgehaltene Decks“,
  nicht „H trifft Stärke“. H korreliert mit der Deckanzahl (Gutachten C §4: Spearman 0,504); G2
  schließt das Echo der gezählten Nutzung aus, nicht aber Beliebtheitswissen des Raters.
- **T7 nicht blind:** Die Bewertungen entstanden am 2026-11-18; wie weit das Wissen des Rater-Modells
  reicht, steht nicht im Repo (UNKNOWN). Darum nur „ordnet spätere Nutzung schwach über den Index
  hinaus“, nie „erkennt Karten vor der Menge“.
- **Leck außerhalb des Korpus:** EDHREC global, EDHTop16 und EDHREC-Themen im Index sind heutige
  Schnappschüsse, nicht nach Decks oder Zeit getrennt. Betrifft G1; G2 nutzt nur die behaltenen Decks.
- **Neue Karten:** kein eigener Teil; `released_at` ist das Datum des gezeigten Drucks.
- **Bootstrap hält Training, Index und Gruppen fest** (Abschnitt 5); die Faltungs-Spanne steht daneben.
- **Ein Rater-Lauf, Raster v2.1:** Einzelwert-Streuung etwa ±5 bis 8 (PILOT_REPORT §10/§11); das
  Rauschen von H drückt ρ_w ebenfalls.
- **Tier-D-Bereich:** viele Karten mit 0 bis 3 Decks; dort ist die Rauschobergrenze klein und die
  Aussage dünn.

## 7. Fazit

Nach den vorab festgelegten Regeln liefert H einen **messbaren, aber kleinen Zusatznutzen gegenüber
dem Index**: T6 G2 ρ_w = 0,056 [0,016; 0,068] bei einer Rauschobergrenze von 0,094 [0,018; 0,102];
T7 (2026-08-09) G2 0,103 [0,043; 0,144] bei 0,226 [0,106; 0,270]. Er ist **nicht robust**: eine von
fünf Faltungen ist negativ, das nachträgliche Faltungs-t-Intervall enthält 0. Die Gleichstände des
Index bricht H in Richtung der Nutzung (T6 G1 0,106), die gezählte Trainings-Nutzung aber rund
3,5-mal so stark (0,368). Für eine Sortierung „Index, Gleichstände nach H“ (Audit §5) ist das ein
schwaches Signal, keine Grundlage allein; die nutzungsfreie Prüfung (T8) steht aus. Dieser Bericht
ändert nichts an Produkt, Index oder Stufen.

## 8. Wiederholen

```bash
# Store-Kopie und Arbeitsordner außerhalb des Repos
PYTHONPATH=src python scripts/analysis/validate_h_t6_t7.py prepare \
  --store <scratch>/studio.sqlite3 --work <scratch>/work --out <scratch>/intermediate.json
python -I scripts/analysis/validate_h_t6_t7.py analyse \
  --data <scratch>/intermediate.json --out <scratch>/result.json
```

`prepare` macht 9 Index-Rechnungen auf Store-Kopien (je rund 4 bis 5 Sekunden plus Kopie), `analyse` lief in rund 45 Sekunden. Tests:
`tests/unit/test_validate_h_t6_t7.py` (synthetische Mini-Daten, Handrechnung).
