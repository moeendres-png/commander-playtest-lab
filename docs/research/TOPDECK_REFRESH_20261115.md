# TopDeck-Neuerfassung 2026-11-15 (Folge zu #1377)

## Auftrag und Route

Die in #1377 blockierte TopDeck-Erfassung wird mit feiner Slice-Granularität
nachgeholt: `POST https://topdeck.gg/api/v2/tournaments` (EDH, volle Spalten
inkl. `decklist`), Fenster 2026-08-17 bis 2026-11-15 (90 Tage), in
**1-Tages-Slices** statt der 10-Tages-Slices des ursprünglichen Laufs.
Die früheren Transfer-Abbrüche betrafen die groben 10-Tages-Antworten; die
1-Tages-Slices liefen von dieser VM vollständig durch (Probe vorab:
1 Tag = 10.318.932 Bytes, 104 Turniere, 1.908 Standings, vollständig).

Evidenzklassen: Ernte- und Zählbefunde `DIRECTLY_VERIFIED` (eigener Lauf,
eigene Nachzählung an den Rohdaten und Exporten). Kein Code wurde geändert;
Verarbeitung und Conversion laufen über die unveränderten Repo-Skripte
`scripts/collect_topdeck_decks.py` (`--offline-only`) und
`scripts/compute_topdeck_conversion.py`.

## Ernte-Bilanz

- 90 von 90 Tages-Slices erfolgreich, **0 Fehler**, keine Nachfahrt nötig.
- Laufzeit 2026-11-15, 16:03:55Z bis 16:30:16Z; Pacing 13 s zwischen den
  Aufrufen (Rate-Limit 5/Min).
- Rohantworten: 246.217.224 Bytes gesamt (größte Einzelantwort 15,8 MB),
  4.566 Turnier-Einträge roh. Die Rohdaten liegen nur im lokalen Cache
  außerhalb des Repos; Checkpoint-Datei mit Slice-Bilanz ebendort.
- Nach TID-Deduplizierung des Collectors: **4.282 distinkte Turniere**
  (284 Einträge sind Grenz-Duplikate: Turniere, die in zwei Tages-Slices
  auftauchen) und **69.860 Standings** (roh 73.611).

## Neu gegen Bestand (`topdeck_20261112`, Fenster 2026-08-15 bis 2026-11-13)

| Größe | Bestand 2026-11-12 | Neu 2026-11-15 | Delta |
|---|---|---|---|
| Distinkte Turniere | 4.348 | 4.282 | −66 |
| Standings gesamt | 71.231 | 69.860 | −1.371 |
| Standings mit Leader | 24.618 | 24.002 | −616 |
| Commander mit Präsenz (von 107) | 30 | 30 | 0 |
| Vollständige Decklisten exportiert | 342 | 332 | −10 |
| Unvollständige Listen | 0 | 0 | 0 |
| Conversion-Zeilen | 5.105 | 5.104 | −1 |
| Conversion-Raten nicht NULL | 484 | 424 | −60 |
| Chulane-Präsenz (Einträge 90d) | 7 | 7 | 0 |
| Chulane-Listen exportiert | 7 | 7 | 0 |

Die Deltas sind Fenster-Verschiebung (beide Fenster 90 Tage, um 2 Tage
versetzt), keine Ernte-Lücke: Die Slice-Bilanz ist lückenlos (90/90), und die
Präsenz änderte sich nur bei 10 Commandern, maximal −5 (Maralen, Fae
Ascendant 40 → 35) bzw. +1 (vier Commander).

## Conversion-Befund Chulane (die #1377-Frage)

Die 242 Chulane-Conversion-Zeilen bleiben **alle NULL** — korrekt und
unverändert. Die `sample_size_base` (Decks mit bekanntem Bracket-Record in
Turnieren mit Top Cut) verteilt sich exakt wie im Bestand:
Basis 0 bei 91 Karten, 1 bei 52, 2 bei 49, 3 bei 50. Das Maximum ist 3 und
liegt damit weiter unter der Mindestbasis 10; eine Conversion-Rate ist
definitionsgemäß nicht definiert (fail closed, keine neue Basis durch die
Neuerfassung). Auch die 7 Chulane-Listen selbst sind identisch zum Bestand:
gleiche Turnier-/Datums-/Ergebnis-Schlüssel und gleiche Kartensätze wie die
Bestandsdatei `data/research/deckbuilder_1655/topdeck_chulane_decks.csv`
(diese wurde nicht überschrieben; der Snapshot trägt seine eigene Kopie als
`topdeck_chulane_decks.csv`).

## Teilnehmerzahl je Turnier (schließt die #1377-Doku-Lücke)

Die API liefert kein Teilnehmerfeld, und die Export-Semantik bleibt
unverändert. Die Teilnehmerzahl eines Turniers ist aber **ableitbar**: Sie
ist die Zahl seiner Standings im Rohdatensatz (je Turnier direkt abzählbar).
In diesem Snapshot: Minimum 3, Median 13, Maximum 429 Standings je Turnier;
1.186 der 4.282 Turniere haben `topCut > 0`. Eine künftige Erfassung, die
Teilnehmerzahlen als Feld braucht, kann sie aus den Rohdaten bilden, ohne
die API anders abzufragen.

## Bekannte Grenzen

- `deckObj`/`decklist` sind bei 45.858 von 69.860 Standings (65,6 %) leer —
  und zwar exakt bei den Standings ohne `leader`. Umgekehrt gilt: Jedes
  Standing mit Leader (24.002) trägt ein nicht-leeres `deckObj` und eine
  nicht-leere `decklist`. Decklisten existieren in dieser Quelle nur für
  Leader-Standings.
- Exportiert werden nur die 107 getrackten Commander des Collectors;
  die übrigen Leader-Standings gehen in keine Datei ein.
- Die Conversion-Definition (docs/TOPDECK.md §6, Deckbuild-Studio-Repo)
  bleibt für kleine Commander-Stichproben leer; das ist Semantik, kein
  Datenfehler.

## Verifikation

- Spielernamen: Alle `player`-Zellen der 30 Deck-Dateien (332 Listen)
  entsprechen dem Muster `Liste N` (Vollscan, 0 Verstöße); zusätzlich
  Guard-Test `test_committed_topdeck_deck_csvs_use_neutral_player_labels`.
- Keine Preis-Felder: Volltext-Suche nach `price`/`preis` über alle
  Snapshot-Dateien ohne Treffer (die API liefert keine Preise).
- Gates: `test_topdeck_collector.py`, `test_topdeck_conversion.py`,
  Hygiene, Any-Ratchet, Committed-Research-Audit und Whole-Deck-Meta —
  31 Tests bestanden; `scripts/classify_docs.py --check` ohne Befund.
  Keine Code-Datei geändert (reines Datenpaket), daher kein Ruff-Lauf nötig.
