# EDHREC V5 (2026-11-10) — vollständige Provenienz, kein Deckimport

**Status:** `REVIEW / ORIGINAL_SOURCE_INDEX`, `automatic_import=false`.

Dieses Verzeichnis referenziert das gesamte eingefrorene V5-Quellarchiv **ohne** Rohantworten oder private Deck-/Sammlungsdaten in das öffentliche Repository zu kopieren. Die Originale sind im [V011-Drive-Archiv](https://drive.google.com/drive/folders/1kqpx6hdq0bKC1wTsYt7poln_VGZ22S_n) hinterlegt. Autorität für Programmcode ist GitHub `main`, Autorität für Rohbelege ist das unveränderte Drive-Original.

| Inhalt des Original-ZIP | Anzahl | Bedeutung |
|---|---:|---|
| `raw_previews` | 470 | EDHREC-Preview-Antworten, **keine** belegten vollständigen 99er-Decks |
| `state` | 473 | Discovery-/Parserversuche und Status, nicht mit Mainboard-Liste gleichsetzen |
| `diagnose` | 8 | historische Diagnose-HTML/PNG, nicht importieren |
| oberste Ebene / Exporte | 12 | Index/Status/Fehlerberichte; `01_EDHREC_DECK_INDEX.csv` und `06_PENDING_AND_FAILED.csv` sind byte-identisch |
| **Gesamt** | **963** | **0** verifizierte neue 99er-Decklisten |

Der **vollständige** Quellnachweis besteht aus `manifest.json` und `source_multiset.csv` (**963** Originaleinträge, **962** unterschiedliche Gruppen-/SHA-/Größen-Schlüssel). `source_multiset.csv` enthält keine Karten- oder Decknamen, sondern eine multisetgenaue, maschinell prüfbare Liste aller Original-Bytes. Für `*.json.gz` gilt SHA-256 über die **dekomprimierten** logischen JSON-Bytes, entsprechend dem V011-Index. Die referenzierte ZIP-Datei hat SHA-256 `877a113f54aa73e02a67fc716d897c32718dd9ba7898b7a90d4e733a871d1f0d`.

## Reproduzierbare, lokale Prüfung

```bash
python scripts/verify_edhrec_v5_archive.py /pfad/ERGEBNISSE_EDHREC_V5.zip
python -m pytest -q tests/unit/test_edhrec_v5_archive_manifest.py
```

Der Prüfer liest die Originaldateien **nur lokal**, vergleicht ZIP-SHA, logische Größen, alle Einträge inkl. Dubletten und gibt lediglich Zähler aus. Kein Netzwerkzugriff, kein Autoupload, keine Änderung am Studio-Store.

## Nicht mit anderen EDHREC-Kohorten vermischen

- **Chulane C079 historisch:** 1.379 beobachtete Karten/Themenseiten-Zeilen; 75 ursprüngliche exakte UTC-Abrufe, 1.304 `UNKNOWN`. [Drive-Importquelle](https://drive.google.com/file/d/1J9ADkvg_rvHBkPx7UQx7crD0K6cUmYUP/view). Neuabruf kann historische Zeit nicht reparieren.
- **Chulane 20 HTTP200-Neuquellen (2026-11-11):** 4.945 Cardlist-Zeilen; unabhängige aktuelle Datenlane [Issue #1186](https://github.com/moeendres-png/commander-playtest-lab/issues/1186) / [gemergter PR #1193](https://github.com/moeendres-png/commander-playtest-lab/pull/1193) (ersetzt den geschlossenen, nicht gemergten #1184). Kein V5-Zeitstempelersatz.
- **Chulane V010 Forschungshub:** 9.831 EDHREC-Index-IDs als **Indexbelege**; keine weiteren 9.831 vollständigen 99er-Decks. [Private Quelle](https://drive.google.com/drive/folders/1KqmAco70VgOo5fc_OzzSZmSY1qHIT9xv).
- **Tam / The Possibility:** 78 EDHREC-Themenseiten mit 16.023 CardRec-Beobachtungen; je Seite eigener Nenner. [Private Quelle](https://drive.google.com/drive/folders/1uVes8IRBtII_BXSvCBVX7Awbs_v2DZ2o).
- **Tam + Chandra:** 381 kuratierte EDHREC-Quelllisten, separate **REVIEW**-Kohorte (187 qualifizierbare Kandidaten, keine automatische Aktivierung). [Drive-Review](https://drive.google.com/drive/folders/1iXmksjwQE6-V0Ds3xzxy9Ai-EqCM22oX).

## Grenzen

Keine Roh-HTMLs, Screenshots, EDHREC-Antworttexte, Browserprofile, Credentials, Kartensammlungsdaten oder private vollständige Decklisten in einem öffentlichen PR. Beachte `AGENTS.md §12` und die externe Quellen-/Lizenzpolitik. Die Vorhandensein eines SHA-256 beweist Byte-Identität, **nicht** Commander-Legalität oder die Vollständigkeit einer Deckliste. Keine nichtbelegte 0%-Quote, kein geschätzter Zeitstempel, keine Deck-Gewinnrate aus Inclusion/Lift.

**Fortsetzung:** [#1176](https://github.com/moeendres-png/commander-playtest-lab/issues/1176) und [#1186](https://github.com/moeendres-png/commander-playtest-lab/issues/1186).
