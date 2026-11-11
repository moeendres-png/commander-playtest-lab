# MTG Collection Deckbuilder

**Standalone-Auskopplung des BUILD-Teils** aus `moeendres-png/commander-playtest-lab` (Quelle: `main@10e663de0d274b3f22adf93c03b89d59bb01356c`, 2026-11-11).

Enthält die bestehende Studio-Deckbau-Weboberfläche, SQLite-Kartensammlung, Inventar- und Scryfall-Import, Farblegalitätsfilter, lokale Kartenbilder, Favoriten/Notizen, Deckstände, Variantenvergleiche, Rollen und Deckdatenanalyse. **Nicht enthalten:** XMage/Forge, Spiele, Partieansicht, Simulation, Pilot/Rules-Engine.

## Start (Python 3.12+)

```sh
python -m venv .venv
# .venv/bin/activate  (Windows: .venv\Scripts\activate)
pip install -e .
mtg-deckbuilder import-inventory "/privat/MTG_Kartensammlung.xlsx"
mtg-deckbuilder import-scryfall "/privat/default-cards-20261109100640.jsonl.gz"
mtg-deckbuilder normalization-report
mtg-deckbuilder serve
```

Web: http://127.0.0.1:8765 (nur localhost). Datenbank, Cache und Bilder werden **außerhalb des Repositories** unter dem Benutzer-Datenordner gehalten. Überschreiben mit `MTG_DECKBUILDER_DATA`.

Die Scryfall-Default-Cards-Bulk-Datei muss lokal als JSONL/JSONL.GZ vorliegen. Der separat verfügbare Befehl `sync-scryfall` holt eine neue öffentliche Bulk-Datei (ohne Sammlung, Mengen, Decklisten oder Lagerorte zu senden).

## Auswahl & Cache

Commander im Browser wechseln. Der Server baut aus der Sammlung den legalen Farbpool, legt dabei einen mit Herkunft, Quellenhash und Cache-Key dokumentierten JSON-Snapshot an und bewahrt Varianten/Markierungen separat. Jede neue Inventar- oder Scryfall-Version invalidiert den Snapshot. Alternativ CLI:
```sh
mtg-deckbuilder cache-commander "Atraxa, Praetors' Voice"
```

## Qualität & Schutz

Siehe [docs/NORMALIZATION_CONTRACT.md](docs/NORMALIZATION_CONTRACT.md). Die Beispiel-XLSX vom 2026-11-07 und der Scryfall-Bulk-Datensatz vom 2026-11-09 wurden **nur lokal zur Kontraktprüfung** benutzt: 1.414 Kartenidentitäten, darunter 1.351 ohne eingetragene oracle_id. 1.414 Namen ließen sich nach Ausschluss nicht spielbarer Drucke eindeutig zuordnen. Die Sammlung selbst ist nicht Bestandteil dieses Repositories.

Die Kopie ist ein initialer extrahierter Entwicklungsstand, keine Behauptung, dass alle ursprünglichen Simulator-abhängigen Qualitätsprüfungen unverändert funktionieren. Vor produktiver Verwendung Tests + manuelle Browserabnahme ausführen.

## Ablösung / GitHub-Migration

Diese Arbeitskopie liegt absichtlich in einem isolierten Branch des Quell-Repositories, weil die verbundene GitHub-Schnittstelle **kein Repository anlegen** kann. Beim Erstellen des neuen Repos einen **neuen Root-Commit ohne alte Lab-Historie** erzeugen. Beispiel (nach lokalem Clone des Standalone-Branches):

Lade aus dem Standalone-Branch **Code → Download ZIP** herunter und entpacke
die Dateien. Ein ZIP enthält nur den aktuellen Deckbuilder-Dateibaum, keine
Historie des Playtest-Labs. Erstelle dann ein **leeres** GitHub-Repository und
führe im entpackten Ordner aus:

```sh
git init -b main
git add .
git commit -m "Initial standalone collection deckbuilder"
git remote add origin https://github.com/DEIN-ACCOUNT/mtg-collection-deckbuilder.git
git push -u origin main
```

Dadurch bleibt das neue Repo wirklich auf den Deckbuilder beschränkt; die alte Commit-Historie mit Simulator-Dateien wird nicht übertragen.
