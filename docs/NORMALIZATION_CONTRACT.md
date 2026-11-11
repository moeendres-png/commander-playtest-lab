# Normalisierungsvertrag v1 — lokale physische MTG-Sammlung

## Primärschlüssel und Trennung

- **card_id** ist die lokale, unveränderliche Sammlungsidentität. Niemals aus dem Namen neu erzeugen, solange im Quellbestand vorhanden.
- **oracle_id** (Scryfall) bezeichnet das Karten-/Regelobjekt unabhängig von Auflagen, Sprache und Foil. Für Farbidentität, Legalität und Singleton-Prüfung verwenden.
- **scryfall_id** bezeichnet eine **konkrete Druckversion** und darf oracle_id nicht ersetzen.
- **physical_lot_id** unterscheidet physische Kopien / Lagerorte / Zustände. Mehrere Lots können dieselbe oracle_id haben.
- **location_id** ist Lagerort, **kein Eigentümer**. Eigentum / Reservierung / Verfügbarkeit sind eigenständige Felder.
- Provenienz, original quantity, lower bound, exactness, source/date, foil, condition, printing_ref und user marks bleiben erhalten.

## Erwartete Excel-Tabs

`01_CARD_IDENTITY`: card_id, oracle_id (optional), oracle_name, german_name, color_identity, type_line, is_basic_land, commander_legal.
`02_PHYSICAL_LOTS`: physical_lot_id, card_id, quantity_observed, quantity_lower_bound, quantity_exact, printing_ref, condition, location_id, pool_status, reserved_quantity, source_id.
`05_INVENTORY_CURRENT`: card_id, observed_quantity, physical_owned_quantity_lower_bound, reserved_for_opponents_quantity, available_for_own_decks_quantity_lower_bound, quantity_exact.
Weitere Originaltabs dürfen nicht verloren gehen und werden im Ursprungs-XLSX beibehalten.

## Eindeutiger Scryfall-Abgleich

1. Lade die **Default Cards Bulk-Datei** lokal (JSONL / JSONL.GZ), inklusive `oracle_id`, `id`, `name`, `printed_name`, `layout`, `games`, `digital`, `color_identity`, `legalities.commander`.
2. Für physisch spielbare Karten `digital=true` und Layouts `art_series`, `reversible_card`, `token`, `double_faced_token`, `emblem` ausschließen; `paper` in `games` muss enthalten sein.
3. Vorhandene `oracle_id` nur übernehmen, wenn im Bulk vorhanden und Namensidentität plausibel. Sonst Konflikt melden.
4. Sonst Unicode-NFKC + Casefold + Whitespace-Normalisierung, **exakter Gesamtname vor Frontface**. Optional deutschen `printed_name` berücksichtigen. **Keine fuzzy auto-accepts.**
5. Nur exakt **eine** verschiedene `oracle_id` als `resolved`. 0 Treffer = `unresolved`, mehrere = `ambiguous`, Widerspruch = `conflict`. Manuell freigeben.
6. `set#collector_number` kann einen Druck und damit `scryfall_id` verifizieren; nie daraus ohne Evidenz Besitz-/Auflagenfakten erfinden.
7. Fehlende quantitative Felder bleiben **UNKNOWN** / null. Upper-/Lower-Bounds nicht zu exakten Mengen hochstufen.

## Deckbau

- Commander nur mit nachgewiesener `legalities.commander == legal`, `Legendary Creature` bzw. explizitem „can be your commander“ (Sonderregeln/Partner separat validieren).
- Karten müssen innerhalb der Farbidentität der Commander liegen; genau 100 Karten einschließlich Commander.
- Singleton nach **oracle_id** statt nach Druckversion, mit Basic-Land- und `any number`-Ausnahmen.
- Physisch vorhandene, frei verfügbare Kopien von reservierten Kopien trennen. Nie eine fehlende Verfügbarkeit als 0 bezeichnen, wenn unbekannt.
- Ohne Regel-Engine ist die Prüfung eine **datenbasierte Deckbauprüfung**, kein vollständiger Rules-Core-Beweis.

## Cache

`cache-commander` speichert einen Snapshot unter einem **externen lokalen** Datenordner.
Cache-Key = SHA-256 aus Commander-oracle_id(s), Inventar-SHA, Scryfall-SHA, Cache-Schema-Version.
Beim Wechsel der Sammlung / Bulk-Datei erfolgt Invalidierung. Benutzerkommentare und Reservierungen werden weiterhin live aus SQLite gelesen; Cache ist keine Eigentumsquelle.
Keine Bestandsdatei, kein Deck und keine Fotos dürfen in Git committed oder an EDHREC / externe APIs geschickt werden.

## Import-Reihenfolge

```sh
mtg-deckbuilder import-inventory /pfad/sammlung.xlsx
mtg-deckbuilder import-scryfall /pfad/default-cards.jsonl.gz
mtg-deckbuilder normalization-report
mtg-deckbuilder cache-commander "Chulane, Teller of Tales"
mtg-deckbuilder serve
```

Die vorhandenen Studio-Importe übernehmen die lokalen Kartenschlüssel und reichern sie mit Scryfall an; der zusätzliche Bericht zeigt offene Zuordnungen.
