# TopDeck.gg Turnier-Decklisten & Präsenz (90 Tage)

Erstellt durch die Neuerfassung zu Issue #1377 (Folgepaket, 2026-11-15).
Abrufdatum: 2026-11-15.

> **Hinweis zur Datenquelle:**
> Data provided by TopDeck.gg (https://topdeck.gg).

## 1. Zählprotokoll
- **Untersuchungsfenster:** 90 Tage (2026-08-17 bis 2026-11-15)
- **Abruf:** 90 Tages-Slices (je 1 Tag, volle Spalten inkl. `decklist`), Pacing 13 s zwischen den Aufrufen (Rate-Limit 5/Min); 90 von 90 Slices erfolgreich, 0 Fehler. Rohantworten: 246.217.224 Bytes, nur lokal im Cache, nicht im Repo.
- **Erfasste Turniere (distinkt):** 4282
- **Standings gesamt:** 69860
- **Standings mit Leader:** 24002
- **Untersuchte Commander:** 107
- **Commander mit Turnier-Präsenz (>0 Einträge):** 30
- **Exportierte Commander:** 30 (alle in `topdeck_20261115/`, inkl. Chulane als `topdeck_chulane_decks.csv` in diesem Ordner)
- **Vollständige exportierte Decklisten (1 Commander + 99 Mainboard):** 332
- **Unvollständige Decklisten (gezählt, aber nicht exportiert):** 0

## 2. Dateien
- `topdeck_commander_presence.csv`: Präsenz-Zählung aller 107 Commander.
- `topdeck_<commander_slug>_decks.csv`: Vollständige Decklisten je Commander mit mindestens 1 vollständiger Liste (inkl. Bracket-Feldern `top_cut`, `wins_bracket`, `losses_bracket`). Die Spalte `player` enthält keine Namen, sondern neutrale Kennungen (`Liste 1`, `Liste 2`, …) je Commander in Reihenfolge des ersten Auftretens.
- `topdeck_chulane_decks.csv`: Die 7 Chulane-Listen dieses Snapshots (in diesem Ordner; die Bestandsdatei in `deckbuilder_1655/` bleibt unverändert — sie enthält exakt dieselben 7 Listen mit identischen Kartensätzen, siehe Bericht `docs/research/TOPDECK_REFRESH_20261115.md`).
- `topdeck_card_conversions.csv`: Berechnete TopDeck-Conversion je Karte x Commander gemäß docs/TOPDECK.md §6 (Refs #1205).

## 3. Teilnehmerzahl je Turnier

Die API liefert kein eigenes Teilnehmerfeld. Die Teilnehmerzahl eines Turniers ist die Zahl seiner Standings (im Rohdatensatz je Turnier direkt abzählbar; Spanne in diesem Snapshot: 3 bis 429, Median 13). Sie wird hier nicht als eigene Spalte exportiert, ist aber aus den Rohdaten und über die Präsenz-Nenner jederzeit ableitbar.

## 4. Übersicht je Commander mit Präsenz
| Commander | Einträge 90d | Einträge mit Liste | Vollständig exportiert | Unvollständig |
|---|---|---|---|---|
| Kykar, Wind's Fury | 14 | 14 | 14 | 0 |
| Sram, Senior Edificer | 3 | 3 | 3 | 0 |
| Lavinia, Azorius Renegade | 10 | 10 | 10 | 0 |
| Lonis, Cryptozoologist | 10 | 10 | 10 | 0 |
| Korvold, Fae-Cursed King | 68 | 68 | 68 | 0 |
| The Gitrog Monster | 99 | 99 | 99 | 0 |
| Brudiclad, Telchor Engineer | 1 | 1 | 1 | 0 |
| Tor Wauki the Younger | 1 | 1 | 1 | 0 |
| Selvala, Explorer Returned | 9 | 9 | 9 | 0 |
| Adrix and Nev, Twincasters | 2 | 2 | 2 | 0 |
| Rionya, Fire Dancer | 2 | 2 | 2 | 0 |
| Fynn, the Fangbearer | 7 | 7 | 7 | 0 |
| Veyran, Voice of Duality | 1 | 1 | 1 | 0 |
| Lathliss, Dragon Queen | 17 | 17 | 17 | 0 |
| Braids, Arisen Nightmare | 8 | 8 | 8 | 0 |
| Chulane, Teller of Tales | 7 | 7 | 7 | 0 |
| Omnath, Locus of Rage | 1 | 1 | 1 | 0 |
| Ovika, Enigma Goliath | 1 | 1 | 1 | 0 |
| Morska, Undersea Sleuth | 3 | 3 | 3 | 0 |
| Szarel, Genesis Shepherd | 2 | 2 | 2 | 0 |
| Doran, Besieged by Time | 1 | 1 | 1 | 0 |
| Lluwen, Imperfect Naturalist | 1 | 1 | 1 | 0 |
| Maralen, Fae Ascendant | 35 | 35 | 35 | 0 |
| Rootha, Mastering the Moment | 16 | 16 | 16 | 0 |
| Muddle, the Ever-Changing | 1 | 1 | 1 | 0 |
| Tinybones, Pocket Nuisance | 1 | 1 | 1 | 0 |
| Tam, the Possibility | 1 | 1 | 1 | 0 |
| Saheeli, Jewel of Avishkar | 2 | 2 | 2 | 0 |
| Ramos, Dragon Engine | 1 | 1 | 1 | 0 |
| Tatyova, Benthic Druid | 7 | 7 | 7 | 0 |

## Spielernamen

Die Spalte `player` der Turnierlisten enthält keine Namen. Jede Liste trägt eine neutrale Nummer (`Liste 1`, `Liste 2`, …) je Commander, in der Reihenfolge des ersten Auftretens (Owner-Entscheid 2026-11-12, Issue #1108). Turnier, Datum, Ergebnis und Karten sind unverändert.
