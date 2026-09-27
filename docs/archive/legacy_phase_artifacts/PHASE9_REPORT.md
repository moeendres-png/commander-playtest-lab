# Phase 9 – Reale Playtestkalibrierung

## Status

- Implementierungsstatus: `passed`
- Empirische Kalibrierung: `not_run`
- Grund: Es wurden keine nutzereigenen realen Spielprotokolle bereitgestellt.
- External Engine: `external_engine_validation_pending=true`
- Kanonische Deck- oder Inventardaten geändert: nein
- Google-Drive-Dateien geändert: nein

## Versionsstand

- Ausgangscommit Phase 8.6: `1971e4e4349960251cd11a8e3cda2e4894bc3528`
- Phase-9-Implementierungscommit: `57be0aa9f015166f057001b312c441ec04758993`
- Paketversion: `0.9.0`
- Playtest-Schema: `1.0.0`
- Kalibrierungsschema: `1.0.0`
- Kalibrierungspolicy: `config/calibration_policy.json`, Version `1.0.0`

## Implementiert

### Reale Playtestdaten

Der Import unterstützt CSV, XLSX und JSON. Verwendet wird ein Datensatz mit einer Zeile pro Spieler. Erfasst werden:

- Deckname, Deckversion und optionaler Deckhash;
- Commander und Gegner über die übrigen Teilnehmerzeilen;
- Podgröße, Sitz und Startspieler;
- Mulligans und Länder in der Starthand;
- Landentwicklung und Ramp;
- erster Commander-Cast, weitere Commander-Casts und Commander-Entfernungen;
- Removal, unabhängige Drawengines und Boardwipes;
- Rebuild;
- Platzierung, Siegachse und Niederlagenursachen;
- tote Karten und Sequencingfehler;
- Ishai-Power nach Zug oder als Peak;
- durch Korvold gezogene Karten;
- Archenemy-Beobachtungen.

Fehlende Werte werden nicht geschätzt. Nicht ausreichend dokumentierte Spiele werden mit konkreten Validierungsfehlern importiert und aus der Kalibrierung ausgeschlossen.

### Versionierung und Evidenzschutz

- append-only Datensätze unter `data/playtests/datasets/<version>/`;
- semantische Hashes pro Spiel und für den gesamten Datensatz;
- geänderte Inhalte unter gleicher `game_id` werden abgewiesen;
- nach dem ersten Kalibrierungslauf versiegelter Train-/Validation-Split;
- neue Spiele nach dem Versiegeln benötigen eine neue Datensatzversion;
- mehrere Korvold- oder RogShai-Versionen werden nicht still zusammengeführt;
- Zielversionen müssen bei gemischten Datensätzen explizit angegeben werden;
- Policy, Simulationseingaben und Berichte werden gehasht.

### Vergleich realer und struktureller Verteilungen

Verglichen werden:

- Spielzugzahl;
- erster Commander-Cast;
- Removalereignisse;
- Boardwipes;
- Ishai-Peak-Power;
- Korvold-Draws;
- Archenemy-Häufigkeit;
- Siegachsen;
- Niederlagenursachen;
- Platzierungen.

Abgebrochene oder unvollständige Structural-Runs werden nicht in die Kalibrierungsverteilungen aufgenommen. Anzahl und Ausschlussgründe werden im Bericht gespeichert.

### Kalibrierungsmethode

Die Standardpolicy verlangt:

- mindestens 20 Trainingsspiele;
- mindestens 8 Validierungsspiele;
- mindestens 12 Trainingsbeobachtungen je Metrik;
- mindestens 5 Validierungsbeobachtungen je Metrik;
- ein Bootstrap-Differenzintervall, das null nicht einschließt;
- mindestens 5 % Fehlerverbesserung auf dem versiegelten Validation-Split.

Kandidatenfaktoren werden aus Trainingsdaten als konservativ zum Wert 1,0 geschrumpfte Real-/Simulationsverhältnisse berechnet. Ein Faktor wird nur akzeptiert, wenn er die unbenutzten Validation-Spiele verbessert.

Akzeptierte Faktoren werden nur in ein nicht angewandtes Kalibrierungsprofil geschrieben. Simulatorstandardwerte, kanonische Decklisten und Inventardaten bleiben unverändert.

### Unsicherheit

- deterministische Bootstrap-Intervalle für Mittelwerte und Differenzen;
- Wilson-Intervalle für kategoriale Anteile;
- fehlende Werte werden ausgewiesen;
- interne Validation wird ausdrücklich nicht als unabhängige Bestätigung bezeichnet;
- Trainingsspiele werden niemals als Validation-Evidenz wiederverwendet.

## CLI

```bash
commander-lab ingest-playtest data/session.csv \
  --dataset-version session-2026-08 \
  --root .

commander-lab calibrate-playtests \
  --dataset-version session-2026-08 \
  --simulation-result data/runs/calibration-reference/structural_results.json \
  --korvold-version current-2026-08-05 \
  --rogshai-version current-2026-08-05 \
  --policy config/calibration_policy.json \
  --root .

commander-lab validate-phase9 --root .
```

Vorlage: `data/playtests/playtest_template.csv`

## Tests

Gruppiert ausgeführt:

- Unit: 106 bestanden;
- Integration: 18 bestanden;
- Property: 8 bestanden;
- Contract: 8 bestanden;
- Differential: 2 bestanden, 1 externer Test übersprungen;
- Golden, Agent Evals, Architecture, Fuzz und Mutation Guards: 11 bestanden.

Gesamt: **153 bestanden, 1 korrekt übersprungen, 0 fehlgeschlagen**.

Der übersprungene Test verlangt eine reale konfigurierte XMage- oder Forge-Instanz.

## End-to-End-Validierung

Der Offline-Validator verwendete sechs eindeutig als synthetisch markierte Fixture-Spiele und 16 Structural-Runs. Erwartetes und tatsächliches Ergebnis:

- Implementierung: `passed`;
- empirische Kalibrierung: `not_run`;
- synthetische Fixture-Entscheidung: `insufficient_evidence`;
- akzeptierte Parameter: keine;
- Train-/Validation-Trennung: aktiv;
- unabhängige Bestätigung behauptet: nein;
- Engineparameter geändert: nein.

Die synthetischen Fixtures sind ausschließlich Pipeline-Tests und dürfen nicht als reale Evidenz verwendet werden.

## Verbleibende Grenze

Eine echte empirische Kalibrierung beginnt erst nach Import realer Spielprotokolle. Bis dahin bleiben alle Parameter unverändert. Die externe XMage-/Forge-Validierung bleibt separat pending und wird durch reale Playtests nicht ersetzt.
