# Deckbuilder-Datensätze — Sammlungsstand 1.655 (CPL, Chulane-Fokus)

Erstellt durch Muse (Daten-Lane, Issues #1205/#1208/#1209), Abruf und
Aufbereitung 2026-11-11/12. Nur objektive Zählwerte und publizierte
Quellwerte mit Provenienz. Keine Decklisten, keine Sammlungs- oder
Besitzdaten. Decklisten-Korpus (3.004 Decks, lokal) bleibt lokal;
hier liegen ausschliesslich Aggregate.

| Datei | Inhalt | Quelle / Erzeugung |
|---|---|---|
| `commander_card_signals_{1..4}.csv` | 29.330 Signal-Zeilen: Karte je Commander (107) mit EDHREC-Inclusion, Synergy, Deck-Zählern | EDHREC-Commander-Seiten (JSON), Abruf 2026-11-11/12 |
| `commander_bracket_signals_{core,upgraded,optimized,cedh}_*.csv` | 91.283 Signal-Zeilen je Commander × Bracket (428/428 Seiten) | EDHREC-Bracket-Seiten (core/upgraded/optimized/cedh), Abruf 2026-11-12 |
| `card_global_signals.csv` | 1.655 Zeilen: globale EDHREC-Werte je Sammlungs-Karte (3 PARTIAL: geteilte Karten) | EDHREC-Kartenseiten, Abruf 2026-11-11/12 |
| `coverage_matrix_1655.csv` | 1.655 Zeilen × 8 Schichten: Abdeckung je Karte (Scryfall/EDHREC/Spellbook/Playgroup/Rulings/Tagger/Kategorien/Korpus) | Zählung über alle Schichten, 2026-11-12 |
| `spellbook_card_links.csv` | 1.655 Zeilen: Combo-Beteiligungen je Karte (distinkte Varianten; Zählregel uses-Filter) | Commander Spellbook Bulk, Abruf 2026-11-11 |
| `playgroup_commander_stats.csv` | 107 Zeilen × 12 Felder: Playgroup-Statistiken je Commander | Playgroup AI (öffentliche JSON-Endpunkte), Abruf 2026-11-11/12 |
| `card_rulings_1655.jsonl` | 3.259 Rulings zu 952 Sammlungs-Karten | Scryfall Rulings Bulk, gefiltert auf die Sammlung, 2026-11-12 |
| `card_tagger_bulk_1655.csv` | Tagger-Claims (Subtree-Vereinigung) — 1.033 Karten mit Claims | Scryfall Bulk `oracle_tags` (taggings + Kind-Tags), 2026-11-12 |
| `edhrec_salt.csv` | 100 Zeilen: EDHREC-Salt-Top-100 (Wert + Rang); nur 4 davon in der Sammlung — Karten ausserhalb haben keinen publizierten Wert in dieser Liste (nicht 0) | EDHREC `/pages/top/salt.json`, Abruf 2026-11-12 |
| `edhrec_chulane_combos.csv` | 100 Combo-Listen für Chulane mit EDHREC-Deck-Zählern (beobachtete Combos; getrennt von Spellbook zu führen) | EDHREC-Comboseite Chulane, Abruf 2026-11-12 |
| `topdeck_chulane_decks.csv` | 572 Zeilen: 6 Chulane-Turnierlisten (je 100 Karten) mit Turnier, Datum, W/D/L | TopDeck.gg API v2, Abruf 2026-11-12. Data provided by TopDeck.gg (https://topdeck.gg) |
| `topdeck_commander_presence.csv` | 107 Zeilen: Turnier-Präsenz je Commander (90 Tage); Zählbasis 71.080 Standings, 24.536 mit Leader-Angabe — Zähler sind Untergrenzen | TopDeck.gg API v2, Abruf 2026-11-12. Data provided by TopDeck.gg (https://topdeck.gg) |
| `mtgjson_printings_1655_{1..3}.jsonl` | 16.658 Drucke zu 1.655/1.655 Identitäten, 61.725 Fremdnamen; KEINE Preise (Owner-Entscheid: keine Preisdaten im Tool) | MTGJSON AllPrintings (Build 2026-11-11), gefiltert per scryfallOracleId |

Bekannte Grenzen: EDHREC-Werte sind Momentaufnahmen des Abrufs;
Spellbook-Zählung folgt der dokumentierten uses-Regel; Tagger-Labels
`stax`/`token`/`card-selection` existieren im Scryfall-Vokabular
nicht (NOT_FOUND). Gap-Matrix zum selben Stand:
`data/research/chulane_legal_pool_gap_matrix.json` (PR #1229).

Teilungs-Schema: Dateien über ~2 MB sind in nummerierte Teile `<name>_1`, `<name>_2`, … zerlegt (Connector-Limit je Datei); CSV-Teile tragen je eine eigene Kopfzeile und werden zum Lesen in Nummern-Reihenfolge aneinandergehängt (Kopfzeile nur vom ersten Teil übernehmen).

## Bekannte CI-Wechselwirkung (2026-11-12)

Der Secret-Pattern-Scan der CI (Muster `sk-[A-Za-z0-9_-]{20,}`) trifft in
`commander_bracket_signals_optimized_3.csv` den Karten-Slug
`zask-skittering-swarmlord` (Karte: Zask, Skittering Swarmlord). Das ist ein
publizierter EDHREC-Bezeichner und Join-Schlüssel dieser Datei, kein Secret.
Die Behebung gehört in die Workflow-Definition (Ausschluss von
`data/research/**`), nicht in die Daten.
