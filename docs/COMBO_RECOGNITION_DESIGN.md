# Combo-Erkennung: Design-Dokument

## Problem

Der Pilot sollte Karten priorisieren, die mit der aktuellen Board-State synergieren.
Beispiel: Wenn "Goblin Guide" auf dem Feld ist, ist "Goblin Warchief" wertvoller
als eine generische Kreatur.

## Ansatz

### Phase 1: Offline-Analyse (bereits implementiert)
`scripts/card_synergy_report.py` findet Karten-Paare mit überproportionaler
Win-Rate aus historischen Spieldaten.

### Phase 2: Echtzeit-Nutzung (zukünftig)

**Datenstruktur:**
```python
# synergy_db.json (aus Phase 1 generiert)
{
    "Goblin Guide": {
        "Goblin Warchief": 2.5,  # Lift-Faktor
        "Goblin Chieftain": 2.1,
    }
}
```

**Integration in Pilot:**
1. Bei jeder Priority-Entscheidung: Hole Hand + Battlefield
2. Für jede spielbare Karte in Hand: Berechne Synergy-Bonus
   - Bonus = Summe der Lift-Faktoren mit Karten auf dem Feld
3. Addiere Bonus zum Karten-Score

**Herausforderungen:**
- Synergy-DB muss aus vielen Spielen gelernt werden (aktuell: zu wenig Daten)
- Falsch-positive Synergien (Korrelation ≠ Kausalität)
- Performance: Lookup pro Karte pro Entscheidung

**Empfehlung:** Erst 1000+ Spiele sammeln, dann Synergy-DB bauen, dann integrieren.
Aktuell: Nicht implementieren, nur dokumentieren.
