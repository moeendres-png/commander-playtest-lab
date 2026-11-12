# Daten-Konsistenz-Audit der committed Research- und Kartendaten

- **Datum / Stichtag:** 2026-11-12
- **Prüfskript:** `scripts/audit_committed_research_data.py`
- **Status-Vokabular:** `OK` / `ABWEICHUNG` / `UNKNOWN`

## 1. Parsebarkeit und Objekt-/Zeilenzahlen

| Datei | Format | Status | Objekt-/Zeilenzahl |
|---|---|---|---|
| `chulane_legal_pool_gap_matrix.json` | JSON | OK | 927 Karten |
| `chulane_decklist_inclusion_20261112.csv` | CSV | OK | 15038 Datenzeilen |
| `pilot_card_knowledge.json` | JSON | OK | 32820 Karten |
| `commander_flags.json` | JSON | OK | 53 Game Changers, 83 Banned |
| `official_precon_oracle_cards.json` | JSON | OK | 512 Karten |

## 2. Namens-Mengen und Dubletten

### 2.1 Gap-Matrix-Karten ohne Eintrag in `pilot_card_knowledge`
- **Exakte Namensgleichheit:** 0 Karten
- **Normalisiert (casefold + strip):** 0 Karten

### 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag
- **Distinkte Kartennamen in Inclusion-CSV:** 6543
- **Karten im Chulane-Legal-Pool (Gap-Matrix):** 927
- **Karten der Inclusion-CSV ohne Gap-Matrix-Eintrag (exakt):** 6084
- **Karten der Inclusion-CSV ohne Gap-Matrix-Eintrag (normalisiert):** 6084
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
- `total_cards`: gemeldet = 927, nachgerechnet = 927 (OK)
- `coverage_grades[COMPLETE]`: gemeldet = 271, nachgerechnet = 271 (OK)
- `coverage_grades[PARTIAL]`: gemeldet = 97, nachgerechnet = 97 (OK)
- `coverage_grades[SPARSE]`: gemeldet = 206, nachgerechnet = 206 (OK)
- `coverage_grades[UNOBSERVED_IN_CORPUS]`: gemeldet = 353, nachgerechnet = 353 (OK)
- `long_tail_candidates_count`: gemeldet = 168, nachgerechnet = 168 (OK)
- `unobserved_in_corpus_count`: gemeldet = 353, nachgerechnet = 353 (OK)
- `observed_in_corpus_count`: gemeldet = 574, nachgerechnet = 574 (OK)
- `has_edhrec_count`: gemeldet = 366, nachgerechnet = 366 (OK)
- `has_spellbook_combos_count`: gemeldet = 3, nachgerechnet = 3 (OK)
- `xmage_ready_count`: gemeldet = 807, nachgerechnet = 807 (OK)

## 4. `commander_flags.json`: Überschneidung Game Changer vs. Banned

- Anzahl Game Changers: 53
- Anzahl Commander Banned: 83
- Überschneidung (Namen in beiden Mengen): 0

## 5. Gesamt-Tabelle aller Prüfungen

| Prüfung | Ergebnis | Anzahl | Details-Datei/Abschnitt |
|---|---|---|---|
| 1.1 Parsebarkeit der 5 Datendateien | OK | 0 | Abschnitt 1: 0 Parse-Fehler über alle 5 Dateien |
| 2.1 Gap-Matrix-Karten ohne Eintrag in pilot_card_knowledge | OK | 0 | Abschnitt 2.1: 0 Gap-Matrix-Karten fehlen in PCK |
| 2.2 Inclusion-CSV-Karten ohne Gap-Matrix-Eintrag (Universum vs. Chulane-Pool) | ABWEICHUNG | 6084 | Abschnitt 2.2: 6084 Universums-Karten außerhalb des 927-Chulane-Pools |
| 2.3 Dubletten je Datei | OK | 0 | Abschnitt 2.3: 0 Dubletten in allen 5 Dateien |
| 3.1 Inclusion-CSV: Kohorten-Nenner konstant | OK | 0 | Abschnitt 3.1: Alle 4 Kohorten haben exakt 1 konstanten Nenner |
| 3.2 Inclusion-CSV: Wertebereiche (0 <= decks <= universe_decks; 0.0 <= share <= 1.0) | OK | 0 | Abschnitt 3.2: 0 Wertebereichsverletzungen |
| 3.3 Inclusion-CSV: Leere Pflichtfelder | OK | 0 | Abschnitt 3.3: 0 leere Felder über alle 15.038 Zeilen |
| 3.4 Gap-Matrix: summary_counts Nachrechnung | OK | 0 | Abschnitt 3.4: Alle summary_counts stimmen exakt mit Kartenliste überein |
| 4.1 commander_flags.json: Game Changer vs. Banned Überschneidung | OK | 0 | Abschnitt 4: 0 Karten sind gleichzeitig Game Changer und Banned |
