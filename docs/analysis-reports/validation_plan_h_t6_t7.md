# Validierungsplan: Kartenverständnis H gegen Nutzung ohne Modell (T6, T7)

- **Stand:** 2026-11-22, Branch `docs/validation-h-t6-t7`, gebaut auf `main` @ `138a50c2`.
  Refs #1404 (Builder-Audit Chulane/TAM 2026-11-21, Abschnitt 3 T6/T7, Abschnitt 6 (a) WP 9).
- **Reihenfolge:** Dieser Plan wird committet und gepusht, **bevor** eine Zahl berechnet ist, die H
  neben eine zurückgehaltene oder spätere Nutzung stellt. Angesehen waren vorher nur Größen ohne H:
  Datumsverteilung der Decks, Laufzeit einer Index-Rechnung, Tabellenschema. Der Bericht nennt den
  SHA dieses Commits.
- **Wirkung:** keine. Das Ergebnis ändert weder Produktcode noch Index, Stufen, Sortierung oder
  Anzeige. Kartenverständnis bleibt ein Modellurteil (`understanding_field.py`, „nicht gegen
  Spielergebnisse validiert“).
- **Grenze aller Tests hier:** Das Ziel ist selbst Nutzung. Gemessen wird nur, ob H die spätere oder
  zurückgehaltene Nutzung über den Index hinaus ordnet. Ob H „Kartenstärke“ trifft, misst nur eine
  nutzungsfreie Referenz (T8, blinde Paarvergleiche, Owner-Zeit), nicht dieser Plan.

## 1. Frage und Herkunft

| Test | Frage | Herkunft |
|---|---|---|
| T6 Deck-Split | Ordnet H die Karten **innerhalb gleicher Index-Gruppen** so, wie sie in zurückgehaltenen 20 % der Decks vorkommen? | Gutachten C §2 Nr. 1 (`data/research/chulane_rubric_v2_20261118/audit/GUTACHTEN_C_gesamtrating.md`) |
| T7 Zeit-Split | Ordnet H die Karten innerhalb gleicher Gruppen des Index **bis zum Stichtag** so, wie sie **nach** dem Stichtag gespielt werden? | Gutachten C §2 Nr. 2; Datumsabdeckung: 10.551 von 10.551 Quelldecks datiert, 2024-11-13 bis 2026-11-15 |

## 2. Datensatz (fest)

- **Store:** Repo-Import-Kopie des Studio-Store, Scratch-Ordner außerhalb des Repos (nie im Repo),
  Schema 21, 10.551 Quelldecks, Import laut Tabelle `source` am 2026-11-16 (`imported_at`).
  SHA-256 der benutzten Datei: `9df80845cb62bb9dd421bdce3f4712804f6c8f40d8691a94a9afe65758be768f`.
  Der Import-Commit ist im Store nicht vermerkt: UNKNOWN.
- **Universum:** die lokalen Decklisten von „Chulane, Teller of Tales“ nach der Produkt-Regel
  (`universe_choice.local_spec`, dedupliziert): 10.128 Decks, alle datiert.
- **H:** `data/card_understanding/card_understanding_v2_1.jsonl` (922 Zeilen, Raster v2.1, ein Lauf je
  Karte), SHA-256 `399a7678eeec0a749b166fbb8a04a97fb24a36387f1eec94afb6018ed907b512`; Zuordnung über
  die Oracle-ID wie im Produkt (`understanding_field`).
- **Index:** der Stärke-Index des Produkts (`strength_view.compute`, empfohlene Einstellungen,
  Bracket „upgraded“ = die Kohorte, für die H gilt; das Skript bricht ab, wenn die Empfehlung ein
  anderes Bracket nennt), eine Nachkommastelle wie angezeigt.
- **Analysekarten:** Karten des Pools mit H **und** Index-Wert in der jeweiligen Rechnung; Tier N
  (Commander, Basisländer, andere Commander) und Karten ohne Index fallen heraus. n/N wird je Rechnung
  berichtet.
- **Rechen-Stores:** je Faltung bzw. Stichtag eine Kopie des Store im Scratch-Ordner, aus der alle
  Decks **außerhalb** der behaltenen Menge aus allen `corpus_*`-Tabellen gelöscht werden (nie aus
  `deck*`, das sind Owner-Decks). Danach wird der Index neu gerechnet. Alle Korpus-Komponenten
  (Decklisten-Universum, Korpus getunt, Lift, Bracket-Steigung, Turnier-Anteil aus Bracket 5) sehen
  so nur die behaltenen Decks.
- **Nicht zeitlich/deckweise trennbar** (Leck, benannt): EDHREC global, EDHTop16 und EDHREC-Themen sind
  heutige Schnappschüsse. Darum gibt es zu jeder Rechnung die Gruppierung „gleiche Deckzahl“ (unten),
  die nur die behaltenen Decks benutzt.

## 3. Metrik

**Geschichtete Rangkorrelation** ρ_w(x, y | G) („partielle Rangkorrelation je Index-Gruppe“): In jeder
Gruppe g mit n_g Karten bekommen x und y Mittelränge r (1 bis n_g, Gleichstände gemittelt), zentriert
und skaliert: u = (r_x − (n_g + 1)/2) / n_g, v = (r_y − (n_g + 1)/2) / n_g. Dann
ρ_w = Σ u·v / √(Σ u² · Σ v²) über alle Karten aller Gruppen. Eine Gruppe mit einer Karte oder mit
konstantem x oder y trägt 0 bei; ist ein Nenner 0, ist ρ_w undefiniert. Zufälliges Brechen der
Gleichstände ergibt im Erwartungswert 0.

**Gruppierungen** (beide gerechnet, Land und Zauber immer getrennt, wie der Index sie skaliert):

- **G1 Index-Gleichstand:** gleicher angezeigter Index (eine Nachkommastelle) aus den Trainingsdecks.
  Das ist die Frage des Audits („bricht H Gleichstände sinnvoll?“). Grenze: Karten mit gleichem
  Index haben nicht gleiche Nutzung (rund acht Komponenten); H korreliert mit der Deckanzahl
  (Spearman 0,504, Gutachten C §4, „Beliebtheits-Leck“). Ein positives ρ_w in G1 kann darum ein Echo
  schon gezählter Nutzung sein.
- **G2 gleiche Deckzahl:** gleiche Anzahl Trainingsdecks (T7: Decks bis Stichtag) mit der Karte. In
  einer G2-Gruppe ist die bekannte Nutzung konstant; ein positives ρ_w ist Nutzen **über** die
  gezählte Nutzung hinaus. In G2 sind „Anteil danach“ und „Zuwachs“ dasselbe.

**Vergleichsgröße** (keine Entscheidungswirkung, nur Einordnung): ρ_w(Trainings-Deckanteil, Ziel | G1).
Sie zeigt, wie weit schon die gezählte Nutzung die G1-Gleichstände bricht. In G2 ist sie per
Konstruktion 0.

**Rauschobergrenze (zuerst):** ρ_w(Ziel in Hälfte A, Ziel in Hälfte B | G) mit denselben Gruppen; die
zurückgehaltenen (T6) bzw. späteren (T7) Decks werden in zwei Hälften geteilt. Sie misst, ob es
innerhalb der Gruppen überhaupt eine reproduzierbare Nutzungsordnung gibt, die H brechen könnte.
Zusätzlich als Einordnung die Spearman-Brown-Grenze √(2C / (1 + C)) für das Ziel aus allen
zurückgehaltenen Decks. Die globale Zahl „Deckanteil Hälfte A gegen Hälfte B über alle Karten“ wird
nur zur Rückverfolgung des Auftragswortlauts berichtet, nicht als Gate (sie liegt erwartbar nahe 1).

## 4. T6 Deck-Split (fest)

- **Faltungen:** 5. Die 10.128 Deck-IDs werden nach SHA-256 von `wp9-t6-folds-20261122:<deck_id>`
  sortiert; Faltung = Position mod 5.
- **Je Faltung f:** Training = Universum ohne Faltung f (80 %), Index und G1/G2 aus dem Training.
  Ziel Y_f(Karte) = Anzahl Decks der Faltung f mit der Karte (gleicher Nenner je Faltung, darum
  rangleich mit dem Anteil). Karten-Deck-Zuordnung mit der Produkt-Funktion des Universums
  (`universe_view`, gleiche Namensschlüssel und Abschnitte).
- **Hälften für die Rauschobergrenze:** Decks der Faltung f nach SHA-256 von
  `wp9-t6-halves-20261122:<deck_id>` sortiert, abwechselnd A/B.
- **Kennzahl:** Mittel der fünf Faltungs-Werte. Zusätzlich je Faltung min/max.

## 5. T7 Zeit-Split (fest)

- **Stichtag primär 2026-08-09** (80-%-Quantil der Deckdaten im Universum), **Sensitivität
  2026-09-30** (90-%-Quantil). „Vorher“ = `deck_date` ≤ Stichtag, „nachher“ = danach.
- **Index bis Stichtag:** Rechen-Store nur mit den Decks bis Stichtag, G1/G2 daraus.
- **Ziel:** Anzahl Decks nach dem Stichtag mit der Karte. Primär G2 (gleicher Vorher-Wert: Anteil
  nachher = Zuwachs); G1 als Frage des Audits. Die Differenz „Anteil nachher minus Anteil vorher“
  wird in G1 nicht als Ziel benutzt: über die Regression zur Mitte und die Korrelation von H mit dem
  Vorher-Anteil wäre sie gegen H verzerrt (und „Anteil nachher“ allein in G1 zu H hin; darum G2).
- **Hälften:** Decks nach dem Stichtag nach SHA-256 von `wp9-t7-halves-20261122:<deck_id>`, abwechselnd.
- **Kohorten („je Gruppe“, Lesart dieses Plans):** Gruppen sind Deck-Kohorten: (a) alle Decks des
  Universums, (b) Bracket 3 (`bracket:3`, die Kohorte, für die H gilt; Ziel nur aus Bracket-3-Decks
  nach dem Stichtag, Gruppen aus dem Gesamt-Index bis Stichtag). **Abbruch:** hat eine Kohorte nach
  dem Stichtag weniger als 30 Decks, ist sie `NOT_RUN` (kein Schluss). Weitere Kohorten werden nicht
  gerechnet.
- **Blindheit UNKNOWN:** Die Bewertungen entstanden am 2026-11-18. Wie weit das Wissen des Rater-Modells
  reicht, steht nicht im Repo. Liegt es nach dem Stichtag, kann H spätere Beliebtheit kennen; T7 darf
  darum nie „erkennt Karten vor der Menge“ behaupten, nur „ordnet die spätere Nutzung (nicht) über den
  Index hinaus“.
- **Neue Karten:** kein eigener Teil. `released_at` im Store ist das Datum des gezeigten Drucks, nicht
  der Erstveröffentlichung; eine Trennung „neu nach Stichtag“ wäre unzuverlässig (Grenze im Bericht).

## 6. Intervalle, Seeds, Wiederholung

- **Bootstrap über Decks**, B = 1000, Seed `20261122` (`random.Random`). Je Wiederholung werden die
  zurückgehaltenen bzw. späteren Decks jeder Faltung/Kohorte mit Zurücklegen gezogen (für die
  Hälften je Hälfte getrennt); Ziel und Kennzahl werden neu gerechnet. H, Index und Gruppen bleiben
  fest (die Unsicherheit aus der Zusammensetzung des Trainings ist nicht im Intervall; die
  Faltungs-Spanne min/max steht daneben).
- **95-%-Intervall:** Perzentile, untere Grenze = sortierter Wert an Stelle ⌊0,025·B⌋, obere an
  ⌈0,975·B⌉ − 1 (0-basiert; bei B = 1000: Stellen 25 und 974). Wiederholungen mit undefiniertem Wert
  werden gezählt; sind es mehr als 5 %, ist die Kennzahl „kein Schluss“.
- **Anteile:** Wilson-Intervall 95 % (z = 1,959964), z. B. „Gruppen mit ρ_g > 0: k von m“ (je Gruppe
  mit mindestens 3 Karten und nicht konstantem x und y, über alle Faltungen gezählt; beschreibend).
- **Determinismus:** alle Teilungen über SHA-256 der Deck-ID, keine Zufallszahl ohne festen Seed; zwei
  Läufe auf denselben Eingaben ergeben dieselbe Ausgabe-Datei (Prüfung im Bericht per SHA-256).
- **Skript:** `scripts/analysis/validate_h_t6_t7.py`, nur Standardbibliothek plus `commander_lab`;
  Stufe `prepare` (liest den Store, schreibt eine Zwischen-Datei in den Scratch-Ordner) und Stufe
  `analyse` (rein, rechnet nur aus der Zwischen-Datei). Tests mit synthetischen Mini-Daten
  (Handrechnung) prüfen Ränge, ρ_w, Wilson, Perzentile, Teilungen und die Entscheidungsregeln.

## 7. Prüfungen vor der Auswertung (Abbruch, wenn eine scheitert)

1. Empfohlene Einstellungen nennen Bracket „upgraded“.
2. Index auf einer Kopie, die nur die 10.128 Universums-Decks behält, gleicht dem Index des
   unveränderten Store für jede Karte (die Löschung ändert nichts außer der Deckmenge).
3. Die Karten-Deck-Zuordnung reproduziert für jede Analysekarte den Zähler des
   Decklisten-Universums des Produkts exakt (10.128 Decks).
4. Jeder Rechen-Store hat genau die behaltene Deckmenge als Universum.
5. Die Zahl der Karten mit H und Index wird berichtet (erwartet 922 Karten mit H im Pool).

## 8. Entscheidungsregeln (vorab, je Test, Gruppierung und Kohorte)

Mit C = Rauschobergrenze und S = ρ_w(H, Ziel | G), beide mit 95-%-Bootstrap-Intervall [unten; oben]:

| Nr | Bedingung | Urteil |
|---|---|---|
| 0 | weniger als 50 Analysekarten in Gruppen mit mindestens 2 Karten und nicht konstantem Ziel, oder eine Prüfung aus Abschnitt 7 scheitert, oder > 5 % undefinierte Wiederholungen, oder (T7) Kohorte < 30 Decks nach Stichtag | `KEIN_SCHLUSS` bzw. `NOT_RUN` |
| 1 | C unten ≤ 0 | `KEIN_SCHLUSS`: innerhalb der Gruppen keine von 0 trennbare Nutzungsordnung (Rauschen); das heißt **nicht** „H bringt nichts“ |
| 2 | sonst S unten > 0 | `MESSBAR_POSITIV`; „praktisch relevant“ nur, wenn zusätzlich S ≥ 0,10 |
| 3 | sonst S oben < 0 | `GEGENLAEUFIG` |
| 4 | sonst | `KEIN_MESSBARER_NUTZEN`, mit Obergrenze „höchstens S oben“ |

**Fazit-Regel:** „H liefert messbaren Zusatznutzen gegenüber dem Index“ nur, wenn **G2** in T6
`MESSBAR_POSITIV` ist. Ist nur G1 positiv, heißt das Fazit: „H bricht Index-Gleichstände in Richtung
der Nutzung, aber nicht messbar über die gezählte Nutzung hinaus (Echo möglich)“. T7 wird getrennt
berichtet und nie als „vor der Menge“ gedeutet (Abschnitt 5). Jede Aussage nennt Zahl, Intervall,
n/N und die Rauschobergrenze; „H ist gut/schlecht“ wird nicht geschrieben.

## 9. Was im Repo landet und was nicht

- Im Repo: dieser Plan, das Skript, die Tests, der Bericht
  `docs/analysis-reports/validation_h_t6_t7_20261122.md` mit Aggregaten (n/N, ρ mit Intervall,
  Gruppenzahlen, Wilson), SHA-256 der Eingaben, der Zwischen-Datei und der Ausgabe.
- Nicht im Repo: Store-Kopien, Rechen-Stores, Zwischen-Datei, Werte je Karte (Gutachten C hat
  Nutzungswerte je Karte aus dem Repo-Eintrag entfernt; dieser Bericht folgt dem).
