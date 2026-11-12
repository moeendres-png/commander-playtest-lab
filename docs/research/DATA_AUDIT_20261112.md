# Daten-Konsistenz-Audit der committed Research- und Kartendaten

- **Datum / Stichtag:** 2026-11-12
- **Prüfskript:** `scripts/audit_committed_research_data.py`
- **Status-Vokabular:** `OK` / `ABWEICHUNG` / `UNKNOWN`

## 1. Parsebarkeit und Objekt-/Zeilenzahlen

| Datei | Format | Status | Objekt-/Zeilenzahl |
|---|---|---|---|
| `chulane_legal_pool_gap_matrix.json` | JSON | OK | 801 Karten |
| `chulane_decklist_inclusion_20261112.csv` | CSV | OK | 15038 Datenzeilen |
| `pilot_card_knowledge.json` | JSON | OK | 7231 Karten |
| `commander_flags.json` | JSON | OK | 53 Game Changers, 83 Banned |
| `official_precon_oracle_cards.json` | JSON | OK | 512 Karten |

## 2. Namens-Mengen und Dubletten

### 2.1 Gap-Matrix-Karten ohne Eintrag in `pilot_card_knowledge`
- **Exakte Namensgleichheit:** 3 Karten
- **Normalisiert (casefold + strip):** 3 Karten
- **Betroffene Karten:**
  * `Spellbook Seeker // Careful Study`
  * `Studious First-Year // Rampant Growth`
  * `Tam, Observant Sequencer // Deep Sight`

### 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag
- **Distinkte Kartennamen in Inclusion-CSV:** 6543
- **Karten im Chulane-Legal-Pool (Gap-Matrix):** 801
- **Karten der Inclusion-CSV ohne Gap-Matrix-Eintrag (exakt):** 6126
- **Karten der Inclusion-CSV ohne Gap-Matrix-Eintrag (normalisiert):** 6126
- **Befund:** Die Inclusion-CSV deckt das gesamte 4-Player-Deck-Universum ab (inkl. Gegner- und Formatkarten außerhalb des Chulane-Pools). 417 der 801 Chulane-Pool-Karten erscheinen in der Inclusion-CSV; 6.126 Universumskarten liegen außerhalb des 801-Pools.

### 2.3 Dubletten je Datei
- `chulane_legal_pool_gap_matrix.json`: 0 Dubletten
- `pilot_card_knowledge.json`: 0 Dubletten
- `chulane_decklist_inclusion_20261112.csv` (innerhalb derselben Kohorte): 0 Dubletten
- `commander_flags.json` (Game Changers): 0 Dubletten
- `commander_flags.json` (Banned): 0 Dubletten
- `official_precon_oracle_cards.json`: 0 Dubletten

## 3. Feld-Prüfungen

### 3.1 Inclusion-CSV: Konstanz der Kohorten-Nenner
- Kohorte `source=archidekt, bracket=3`: Nenner = [213] (konstant: JA (OK))
- Kohorte `source=archidekt, bracket=4`: Nenner = [199] (konstant: JA (OK))
- Kohorte `source=edhrec, bracket=3`: Nenner = [755] (konstant: JA (OK))
- Kohorte `source=edhrec, bracket=4`: Nenner = [695] (konstant: JA (OK))

### 3.2 Inclusion-CSV: Wertebereichs-Prüfung
- Anzahl Wertebereichsverletzungen: 0

### 3.3 Inclusion-CSV: Leere Pflichtfelder je Spalte
- Spalte `card_name`: 0 leere Werte
- Spalte `source`: 0 leere Werte
- Spalte `bracket`: 0 leere Werte
- Spalte `decks_with_card`: 0 leere Werte
- Spalte `universe_decks`: 0 leere Werte
- Spalte `share`: 0 leere Werte
- Spalte `universe_snapshot`: 0 leere Werte

### 3.4 Gap-Matrix: Nachrechnung der `summary_counts`
- `total_cards`: gemeldet = 801, nachgerechnet = 801 (OK)
- `coverage_grades[COMPLETE]`: gemeldet = 219, nachgerechnet = 219 (OK)
- `coverage_grades[PARTIAL]`: gemeldet = 8, nachgerechnet = 8 (OK)
- `coverage_grades[SPARSE]`: gemeldet = 202, nachgerechnet = 202 (OK)
- `coverage_grades[UNOBSERVED_IN_CORPUS]`: gemeldet = 372, nachgerechnet = 372 (OK)
- `long_tail_candidates_count`: gemeldet = 413, nachgerechnet = 413 (OK)
- `unobserved_in_corpus_count`: gemeldet = 372, nachgerechnet = 372 (OK)
- `observed_in_corpus_count`: gemeldet = 429, nachgerechnet = 429 (OK)
- `has_edhrec_count`: gemeldet = 380, nachgerechnet = 380 (OK)
- `has_spellbook_combos_count`: gemeldet = 3, nachgerechnet = 3 (OK)
- `xmage_ready_count`: gemeldet = 801, nachgerechnet = 801 (OK)

## 4. `commander_flags.json`: Überschneidung Game Changer vs. Banned

- Anzahl Game Changers: 53
- Anzahl Commander Banned: 83
- Überschneidung (Namen in beiden Mengen): 0

## 5. Gesamt-Tabelle aller Prüfungen

| Prüfung | Ergebnis | Anzahl | Details-Datei/Abschnitt |
|---|---|---|---|
| 1.1 Parsebarkeit der 5 Datendateien | OK | 0 | Abschnitt 1: 0 Parse-Fehler über alle 5 Dateien |
| 2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge | ABWEICHUNG | 3 | Abschnitt 2.1: 3 benutzerdefinierte/geteilte Karten fehlen in PCK |
| 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag (Universum vs. Chulane-Pool) | ABWEICHUNG | 6126 | Abschnitt 2.2: 6.126 Universums-Karten außerhalb des 801-Chulane-Pools |
| 2.3 Dubletten je Datei | OK | 0 | Abschnitt 2.3: 0 Dubletten in allen 5 Dateien |
| 3.1 Inclusion-CSV: Kohorten-Nenner konstant | OK | 0 | Abschnitt 3.1: Alle 4 Kohorten haben exakt 1 konstanten Nenner |
| 3.2 Inclusion-CSV: Wertebereiche (0 <= decks <= universe_decks; 0.0 <= share <= 1.0) | OK | 0 | Abschnitt 3.2: 0 Wertebereichsverletzungen |
| 3.3 Inclusion-CSV: Leere Pflichtfelder | OK | 0 | Abschnitt 3.3: 0 leere Felder über alle 15.038 Zeilen |
| 3.4 Gap-Matrix: summary_counts Nachrechnung | OK | 0 | Abschnitt 3.4: Alle summary_counts stimmen exakt mit Kartenliste überein |
| 4.1 commander_flags.json: Game Changer vs. Banned Überschneidung | OK | 0 | Abschnitt 4: 0 Karten sind gleichzeitig Game Changer und Banned |
