# EDHREC-Commander-Signale — Chulane, Teller of Tales (Neuabruf 2026-11-15)

Erstellt im Rahmen von Issue #1377 (Daten-Erfassung). Nur objektive Zählwerte
und publizierte Quellwerte mit Provenienz. Keine Decklisten, keine
Sammlungs- oder Besitzdaten. Daten: EDHREC (https://edhrec.com).

## Provenienz (je Seite genau ein GET, öffentliche JSON-Endpunkte)

| Seite | URL | Abruf (UTC) | HTTP | Bytes | SHA-256 der Rohantwort |
|---|---|---|---|---|---|
| commander_card_signals.csv | https://json.edhrec.com/pages/commanders/chulane-teller-of-tales.json | 2026-11-15T10:30:16Z | 200 | 109954 | `a2cfab4c1b96207c9baaa41bcab5b47ae7aa5fbdbbab80a38fa7683dccf42ac4` |
| commander_bracket_signals_core.csv | https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/core.json | 2026-11-15T10:30:48Z | 200 | 82942 | `8ece8aca523d47a07e01fd5decd45fd0cdb93d864ffbf38579d41fff0422c40b` |
| commander_bracket_signals_upgraded.csv | https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/upgraded.json | 2026-11-15T10:30:51Z | 200 | 94210 | `8da7cf031ab17c0c8e23ec12c0fb65b2356c5f96e9cf2232dbe384d1220fa8d3` |
| commander_bracket_signals_optimized.csv | https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/optimized.json | 2026-11-15T10:30:54Z | 200 | 97483 | `cfa2709f2fe8506e6fe66512baf506af7b42c24badd350dd2aaf82cc2eafe17f` |
| commander_bracket_signals_cedh.csv | https://json.edhrec.com/pages/commanders/chulane-teller-of-tales/cedh.json | 2026-11-15T10:30:57Z | 200 | 83293 | `c02faf0fdc541c7c25639b4665403a710d917cbdae25798f8b8538a69cac9803` |

Die Rohantworten selbst werden nicht committet (Repo-Konvention, vgl.
C079-Beweisführung); ihre SHA-256 oben macht diesen Snapshot prüfbar.
Ableitung: `scripts/derive_edhrec_signals.py` aus den Rohantworten,
SHA-256 vor der Ableitung verifiziert (fail closed).

## Inhalt

| Datei | Zeilen | Distinkte Karten | Leere Felder (nicht publiziert) |
|---|---|---|---|
| commander_card_signals.csv | 242 | 242 | — |
| commander_bracket_signals_core.csv | 208 | 208 | — |
| commander_bracket_signals_upgraded.csv | 230 | 230 | — |
| commander_bracket_signals_optimized.csv | 247 | 247 | — |
| commander_bracket_signals_cedh.csv | 222 | 222 | — |

## Vergleich zum Snapshot 2026-11-11/12 (deckbuilder_1655, nur Chulane)

| Datei | Distinkte Karten alt | Distinkte Karten neu | Schnittmenge |
|---|---|---|---|
| commander_card_signals.csv | 241 | 242 | 241 |
| commander_bracket_signals_core.csv | 210 | 208 | 205 |
| commander_bracket_signals_upgraded.csv | 233 | 230 | 229 |
| commander_bracket_signals_optimized.csv | 247 | 247 | 245 |
| commander_bracket_signals_cedh.csv | 222 | 222 | 222 |

Feldabbildung und Zählregeln: siehe Docstring von
`scripts/derive_edhrec_signals.py`. Zeilen in Seitenreihenfolge;
ein Wert, den die Seite nicht publiziert, bleibt leer (unbekannt,
niemals 0). Varianten -> Bracket: core=2, upgraded=3, optimized=4,
cedh=5 (wie in den Snapshot-Dateien 2026-11-11/12).

Commander-Slug: `chulane-teller-of-tales`.
