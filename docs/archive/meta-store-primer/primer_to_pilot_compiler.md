# Primer-to-Pilot-Compiler – Nutzung

## Datenfluss

1. Primer mit `import_primer` registrieren.
2. Mit `extract_primer_rules` konservative, deaktivierte Kandidaten erzeugen.
3. Kandidaten manuell prüfen und gegebenenfalls als versionierte Regeln kuratieren.
4. `validate_pilot_rules` gegen DSL, Deckhash und Formatband ausführen.
5. Konflikte mit `generate_primer_conflict_report` prüfen.
6. Mit `compile_pilot_policy` ein unveränderliches Overlay erzeugen.
7. `run_policy_eval` gegen Golden-Szenarien ausführen.
8. Versionen mit `compare_policy_versions` vergleichen.

## Sicherheitsgrenzen

- Primertext wird nie ausgeführt.
- Keine Regel darf Dateien, Decks oder Spielzustände mutieren.
- Der Basispilot bleibt unverändert; das Overlay passt nur validierte Scores an.
- Deckhash und Formatband müssen exakt passen.
- Automatische Extraktionen bleiben bis zur Freigabe inaktiv.
