# Primer-to-Pilot Compiler – Phase 12.2

Status: `primer_compiler_ready_with_limitations`

## Ergebnis

- Automatisch extrahierte Kandidaten: **8**; aktiv: **0**.
- Manuell kuratierte und aktivierte Regeln: **14** (7 Korvold, 7 RogShai).
- Kontrollierte Golden-Szenarien: **5**.
- Basispilot korrekt: **4/5**.
- Overlay korrekt: **5/5**.
- Tatsächlich verbesserte Entscheidung: **1**.

Die verbesserte Entscheidung ist `rogshai-save-counter`: Der Basispilot neutralisierte eine harmlose Valuekarte; das Policy-Overlay hält den Counter zurück und wählt `pass`.

## Sicherheitsmodell

Primertext wird ausschließlich als Daten behandelt. Die Implementierung verwendet kein `eval`, keine Shellausführung, keine dynamischen Funktionsnamen und keine Python-Ausdrücke aus Quellen. Bedingungen werden gegen eine feste Feld- und Operatorliste validiert. Aktive Primerregeln benötigen manuelle Freigabe; automatisch extrahierte Regeln bleiben `needs_review`.

## Deckbindung

- Korvold-Deckhash: `4af053a36d9cf4e84ff5ac2c2e5372daba5336c3cdfb48914ea4d72ea495677d`
- RogShai-Deckhash: `2f2dab2a26e3889aa5399504295d2c6e485c8922397c6736bd4e6fa72f6b6656`

Regeln mit falschem Deckhash oder Formatband werden nicht kompiliert. Fehlende `requires_cards` verhindern die Aktivierung einer Regel.

## Konflikte

Ein absichtlich widersprüchliches Fixture wurde erkannt. Ohne explizite Strategie wird die Kompilierung abgelehnt. Alternativen können getrennt kompiliert werden; es gibt keine stille Zusammenführung.

## Tactical Oracle

- Kediss: zusätzlicher Schaden an andere Gegner bleibt normaler Schaden; zusätzlicher Commander Damage = 0.
- Jeska: verdreifachter tatsächlicher Ishai-Kampfschaden bleibt Commander Damage.
- Silence: verhindert weitere Zauber im Zug, nicht aber aktivierte Fähigkeiten oder Landspiel.

## Gespeicherte Replays

Der Replay-Audit las `383` Structural-Events und `88` Pilotentscheidungen. Eine kontrafaktische Neuberechnung wurde nicht behauptet, weil historische Replays nicht alle DSL-Kontextflags und Alternativaktionen enthalten.

## Grenzen

- Regeln sind heuristische Policy-Overlays, keine vollständigen MTG-Regeln.
- Tactical Oracle ist keine externe Regelengine.
- XMage/Forge wurde nicht real ausgeführt; `external_engine_validation_pending=true`.
- Die empirische Wirkung ist ohne reale Playtestdaten nicht kalibriert.
- Eine Verbesserung in kontrollierten Szenarien ist keine Winrate-Aussage.
- Keine Regel verändert Decklisten, Inventar oder Kartenallokation.
