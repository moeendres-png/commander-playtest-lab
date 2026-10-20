# Eigene Commander-Decks testen

## Übersicht

Du kannst eine eigene Deckliste ins Projektformat überführen, von der Engine auf Importierbarkeit prüfen lassen und in Vierer-Pods gegen andere Decks spielen lassen. Nicht jedes legale Deck funktioniert: Karten, die die Engine nicht kennt, blockieren den Import, und ein erfolgreicher Import beweist nicht, dass jede Karte wie gedruckt spielt (siehe `docs/PRECON_VALIDATION.md`).

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

195 offizielle Commander Precons (2011–2026) liegen im Projekt:
- Verzeichnis: `data/decks/precons/`
- Format: `{jahr}_{deckname}.json`
- Beispiel: `data/decks/precons/2011_counterpunch.json`

## Karten-Abdeckung

Am Pin `043579bb` importieren 182 von 195 Precons; 13 Decks scheitern an 31 verschiedenen Kartennamen, die die
Engine nicht kennt. Import ist nicht Spielbarkeit. Gemessener Stand, Liste der fehlenden Karten und
Reproduktion: `docs/PRECON_VALIDATION.md`.

## Import prüfen und Spiele simulieren

Beides braucht das Bridge-JAR der Engine (`--jar`). Ein Pod besteht immer aus vier **verschiedenen**
Decks; ein Deck auf mehreren Plätzen lehnt der Validator vor dem Start ab. Das Verzeichnis muss
im Repository liegen.

1. Deck importieren (siehe oben), Ausgabe nach `data/decks/custom/`.
2. Prüfen, ob die Engine alle Karten und den Commander auflöst (kein Spiel):

   ```bash
   python scripts/measure_precon_imports.py --jar <bridge.jar> --workdir <leeres Verzeichnis> \
     --deck-dir data/decks/custom --out imports.json --enumerate-missing
   ```

   `FAILED` heißt, die Engine hat das Deck abgelehnt (bei `--enumerate-missing` stehen alle
   unbekannten Karten im Bericht); `INFRASTRUCTURE_ERROR` heißt, die Bridge selbst ist
   ausgefallen und der Lauf endet mit Exit-Code 3.
3. Mindestens vier importierbare Decks in Vierer-Pods spielen:

   ```bash
   python scripts/precon_pod_sweep.py --jar <bridge.jar> --out sweep.json \
     --deck-dir data/decks/custom --import-report imports.json
   ```

Das Coverage-Pod-System (`pilot_decision_report.py run --coverage-pods`) spielt dagegen feste
Pods aus den 18 Decks unter `data/coverage_decks/collection` und nimmt keine eigenen Decks auf.

## Deck-Prüfung

- `scripts/import_deck.py` zählt die Karten und warnt (nur auf stderr), wenn die Summe nicht 100
  ist. Es prüft weder Duplikate noch Commander-Zone, Kartenexistenz oder Legalität.
- Die Engine (Schritt 2 oben) löst jede Karte gegen ihre Kartendatenbank auf und validiert den
  Commander gegen die Karten. Typische Ablehnungen: `UNKNOWN_CARD_NAME`, `CARD_IDENTITY_MISMATCH`
  (Commander in der Form „A // B“: nur den Vordernamen eintragen).
