# Erneuerung der globalen EDHREC-Signale — card_global_signals.csv (2026-11-15)

Issue #1386. Ersetzt die Werte des Abrufs 2026-11-11/12 in
`data/research/deckbuilder_1655/card_global_signals.csv` durch einen
frischen Vollabruf aller 1.655 Pool-Karten. Pool, Spalten und
Zeilenreihenfolge sind unverändert; es gibt weiterhin **keine
Preis-Spalten** (Owner-Entscheid, #1309 P10).

## Produktionsweg (Schritt 0, DIRECTLY_VERIFIED aus dem Repo)

- Die Bestandsdatei dokumentiert ihren Weg selbst: `source_file` nennt je
  Karte ihre Einzel-JSON-Datei (`<slug>.json`); das Verzeichnis-README
  nennt als Quelle die EDHREC-Kartenseiten, Abruf 2026-11-11/12.
- Route: `GET https://json.edhrec.com/pages/cards/<slug>.json`, ein GET
  je Karte (einfache GETs öffentlicher Daten, AGENTS.md §12; Auswertung
  lokal).
- Feldabbildung (Antwort-Objekt `container.json_dict.card`): `name`,
  `sanitized`, `num_decks`, `potential_decks`, `salt`, `rarity` ->
  gleichnamige CSV-Spalten; `inclusion_share` wird lokal als
  `num_decks / potential_decks` abgeleitet (leer bei Nenner 0 —
  unbekannt, niemals 0; so auch die Regel des Importers in
  `src/commander_lab/studio/signals.py`, `_share`/`_global_rows`, der nur
  `card_name`, `fetch_status`, `num_decks`, `potential_decks` liest).
- Die Route war bereits in #1377 gegen den Bestand geprüft worden
  (Bericht `docs/research/DATA_CAPTURE_1377_20261115.md`, Route 3:
  Stichprobe Abbey Griffin, exakt die CSV-Felder, plausible Drift). Für
  diese Erneuerung erneut an 4 Karten direkt geprüft (Abbey Griffin —
  SHA-256 der Antwort identisch zur #1377-Stichprobe —, Abrade,
  Crusade, Wear // Tear als geteilte Karte):
  - Abbey Griffin: Bestand 1.407 / 4.921.723 -> frisch 1.412 / 4.930.520,
    salt 0.0, rarity common.
  - Abrade: Bestand 608.636 / 5.234.630, salt 0.16107931316434995 ->
    frisch 610.088 / 5.242.424, salt unverändert 0.16107931316434995.
  - Crusade (die einzige Zeile mit Nenner 0): Die Seite liefert
    `num_decks` 0, `potential_decks` 0 und **kein** `salt`-Feld ->
    Anteil und Salt bleiben leer, exakt wie im Bestand.
  - Wear // Tear: kombinierte Seite unter dem Slug `wear-tear`,
    `name` = „Wear // Tear" — die geteilten Karten brauchen keinen
    Sonderweg.
- Die Kartenseite enthält auch `prices`; das Ableitungs-Skript liest
  dieses Feld nie und schreibt keine Preis-Spalten.

## Erfassung und Ableitung

- Erfassung: 2026-11-15T12:18:16Z bis 2026-11-15T12:52:33Z (UTC),
  1.655 GETs (192.736.849 Bytes), **0 Fehlschläge, 0 Wiederholungen
  nötig** — jede Karte antwortete im ersten Versuch mit HTTP 200.
- Rohantworten liegen nicht im Repo; je Antwort sind URL, Zeitpunkt,
  HTTP-Status, Bytes und SHA-256 in der Provenienz der Erfassung
  festgehalten.
- Ableitung: `scripts/derive_global_signals.py` (netzfrei; verifiziert
  SHA-256, Bytezahl und HTTP 200 je Seite, fail closed; prüft Name und
  Slug jeder Seite gegen die Pool-Zeile).

## Verifikation (DIRECTLY_VERIFIED)

- Zeilen: alt 1.655, neu 1.655 — gleiche Slug-Menge, gleiche Namen,
  gleiche Reihenfolge, keine Abweichung einzeln zu erklären.
- Join-Vollständigkeit gegen den Pool: Die neue Datei deckt exakt die
  1.655 Pool-Karten des Bestands (Slug- und Namen-Mengen identisch,
  0 nur-alt, 0 nur-neu, 0 Namensabweichungen).
- Leere Felder (nicht publiziert = unbekannt): `inclusion_share` alt 1 /
  neu 1 und `salt` alt 1 / neu 1 — in beiden Fällen Crusade (Nenner 0
  bzw. kein Salt-Feld der Quelle); `num_decks`, `potential_decks` und
  `rarity` in beiden Dateien 0 leere Felder.
- Drift alt -> neu: `num_decks` bei 1.550 Karten verändert,
  `potential_decks` bei 1.654 (alle ausser Crusades 0), `salt` bei
  **0** Karten — die Salt-Werte des Abrufs 2026-11-11/12 gelten
  unverändert fort, die Rangkorrelation ist dort exakt 1.
- Spearman-Rangkorrelation alt vs. neu: `inclusion_share`
  ρ = 0,999997 (n = 1.654, ohne die Nenner-0-Zeile); Rangfolge nach
  `num_decks` (die Popularitätsordnung, der EDHRECs `edhrecRank` folgt)
  ρ = 0,999991 (n = 1.655); `salt` ρ = 1,000000 (n = 1.654).
  Erwartungsgemäss hoch, aber nicht 1: Der Bestand ist 3–4 Tage älter.
- Import über den Produktionspfad (`signals.import_signals`, gesamtes
  Verzeichnis `deckbuilder_1655`, In-Memory-Store): Datei
  `card_global_signals` IMPORTED, 1.655 gelesen, 1.655 geschrieben,
  0 übersprungen. Rücklesen der gespeicherten
  `edhrec_global_inclusion`-Zeilen: 1.654 Zeilen tragen Wert, Zähler und
  Nenner exakt wie die CSV; Crusade ist als NULL-Zeile gespeichert
  (Wert, Zähler und Nenner NULL, Grund `POTENTIAL_DECKS_NOT_POSITIVE`) —
  die dokumentierte NULL-Regel des Importers (Nenner 0 = unbekannt, nie
  0). Die alte Datei importiert mit exakt demselben Muster (1.655
  geschrieben, 1 NULL-Zeile) — der Import ist für beide Stände
  verlustfrei in der Semantik des Produktionspfads.

## Gates

- Betroffene Tests (Guard-Suche `card_global_signals`/`global_signals`
  in `tests/`): `tests/unit/test_audit_committed_research_data.py`
  (Preis-Spalten-Verbot auf der echten Datei) und
  `tests/unit/test_studio_mtgjson_guard.py` zusammen mit Hygiene und
  Any-Ratchet: **14 passed**; `tests/unit/test_studio_strength.py`
  (Konsument): **91 passed**. Gesamt 105 passed, 0 failed.
- Hygiene + Any-Ratchet (`tests/unit/test_test_hygiene.py`,
  `tests/unit/test_any_usage_ratchet.py`): in den 14 passed enthalten;
  das neue Skript enthält kein `Any` (grep: 0 Treffer).
- `ruff check` + `ruff format --check` auf
  `scripts/derive_global_signals.py`: sauber.
- `scripts/classify_docs.py --check`: OK (0 Probleme).
