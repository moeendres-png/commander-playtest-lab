# Eigene Commander-Decks testen

## Übersicht

Du kannst **jedes legale 100-Karten Commander-Deck** im Simulator testen – jederzeit, gegeneinander, so wie du es aufsetzen willst.

## Deck importieren

### Format

Erstelle eine Textdatei mit deiner Deckliste (eine Karte pro Zeile):

```
1x Sol Ring
1x Command Tower
36x Forest
1x Llanowar Elves
...
```

Oder ohne "x":
```
Sol Ring
Command Tower
36 Forest
```

### Import-Befehl

```bash
python scripts/import_deck.py \
  --name "Mein Elfen-Deck" \
  --commander "Lathril, Blade of the Elves" \
  --input mein_deck.txt \
  --output data/decks/custom/mein_elfen_deck.json
```

Für Partner-Commander (Semikolon-getrennt):
```bash
python scripts/import_deck.py \
  --name "Partner Deck" \
  --commander "Ishai, Ojutai Dragonspeaker; Rograkh, Son of Rohgahh" \
  --input deck.txt \
  --output data/decks/custom/partner.json
```

## Precon-Decks

Alle 198 offiziellen Commander Precons (2011–2026) sind bereits im Projekt:
- Verzeichnis: `data/decks/precons/`
- Format: `{jahr}_{deckname}.json`
- Beispiel: `data/decks/precons/2011_counterpunch.json`

## Karten-Abdeckung

Alle 6432 Karten aus den Precons sind in der Kartendatenbank (`data/cards/xmage_card_facts.json`).
Die XMage-Java-Engine implementiert ~30.000 Karten – alle Precon-Karten sind spielbar.

## Spiele simulieren

Aktuell: Die Spiel-Simulation nutzt das Coverage-Pod-System. Für Custom-Decks:

1. Deck importieren (siehe oben)
2. Deck in ein Coverage-Pod-Verzeichnis kopieren
3. `pilot_decision_report.py` mit `--coverage-pods` ausführen

**Zukünftig:** Ein CLI-Tool für beliebige 4-Deck-Kombinationen ist geplant.

## Deck-Validierung

Jedes importierte Deck wird validiert:
- Genau 100 Karten (inkl. Commander)
- Commander in der Commander-Zone
- Keine Duplikate (außer Basic Lands)

Bei Problemen gibt das Import-Skript eine Warnung aus.
