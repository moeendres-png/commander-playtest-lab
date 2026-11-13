# TopDeck.gg Turnier-Decklisten & Präsenz (90 Tage)

Erstellt durch Gemini Flash (Paket C, Refs #1205, #1208).
Abrufdatum: 2026-11-13.

> **Hinweis zur Datenquelle:**
> Data provided by TopDeck.gg (https://topdeck.gg).

## 1. Zählprotokoll
- **Untersuchungsfenster:** 90 Tage (2026-08-15 bis 2026-11-13)
- **Erfasste Turniere (distinkt):** 4348
- **Standings gesamt:** 71231
- **Standings mit Leader:** 24618
- **Untersuchte Commander:** 107
- **Commander mit Turnier-Präsenz (>0 Einträge):** 30
- **Exportierte Commander:** 30 (29 in `topdeck_20261112/` + Chulane in `deckbuilder_1655/`)
- **Vollständige exportierte Decklisten (1 Commander + 99 Mainboard):** 342 (335 in `topdeck_20261112/` + 7 Chulane)
- **Unvollständige Decklisten (gezählt, aber nicht exportiert):** 0

## 2. Dateien
- `topdeck_commander_presence.csv`: Aktualisierte Präsenz-Zählung aller 107 Commander.
- `topdeck_<commander_slug>_decks.csv`: Vollständige Decklisten je Commander mit mindestens 1 vollständiger Liste (inkl. Bracket-Feldern `top_cut`, `wins_bracket`, `losses_bracket`).
- `topdeck_card_conversions.csv`: Berechnete TopDeck-Conversion je Karte x Commander gemäß docs/TOPDECK.md §6 (Refs #1205).

## 3. Übersicht je Commander mit Präsenz
| Commander | Einträge 90d | Einträge mit Liste | Vollständig exportiert | Unvollständig |
|---|---|---|---|---|
| Kykar, Wind's Fury | 14 | 14 | 14 | 0 |
| Sram, Senior Edificer | 3 | 3 | 3 | 0 |
| Lavinia, Azorius Renegade | 13 | 13 | 13 | 0 |
| Lonis, Cryptozoologist | 11 | 11 | 11 | 0 |
| Korvold, Fae-Cursed King | 67 | 67 | 67 | 0 |
| The Gitrog Monster | 102 | 102 | 102 | 0 |
| Brudiclad, Telchor Engineer | 1 | 1 | 1 | 0 |
| Tor Wauki the Younger | 1 | 1 | 1 | 0 |
| Selvala, Explorer Returned | 10 | 10 | 10 | 0 |
| Adrix and Nev, Twincasters | 2 | 2 | 2 | 0 |
| Rionya, Fire Dancer | 2 | 2 | 2 | 0 |
| Fynn, the Fangbearer | 6 | 6 | 6 | 0 |
| Veyran, Voice of Duality | 1 | 1 | 1 | 0 |
| Lathliss, Dragon Queen | 16 | 16 | 16 | 0 |
| Braids, Arisen Nightmare | 7 | 7 | 7 | 0 |
| Chulane, Teller of Tales | 7 | 7 | 7 | 0 |
| Omnath, Locus of Rage | 1 | 1 | 1 | 0 |
| Ovika, Enigma Goliath | 1 | 1 | 1 | 0 |
| Morska, Undersea Sleuth | 3 | 3 | 3 | 0 |
| Szarel, Genesis Shepherd | 2 | 2 | 2 | 0 |
| Doran, Besieged by Time | 2 | 2 | 2 | 0 |
| Lluwen, Imperfect Naturalist | 1 | 1 | 1 | 0 |
| Maralen, Fae Ascendant | 40 | 40 | 40 | 0 |
| Rootha, Mastering the Moment | 16 | 16 | 16 | 0 |
| Muddle, the Ever-Changing | 1 | 1 | 1 | 0 |
| Tinybones, Pocket Nuisance | 1 | 1 | 1 | 0 |
| Tam, the Possibility | 1 | 1 | 1 | 0 |
| Saheeli, Jewel of Avishkar | 2 | 2 | 2 | 0 |
| Ramos, Dragon Engine | 1 | 1 | 1 | 0 |
| Tatyova, Benthic Druid | 7 | 7 | 7 | 0 |

## Spielernamen

Die Spalte `player` der Turnierlisten enthält keine Klarnamen. Jede Liste trägt die Initialen des Spielers: je Namensbestandteil der erste Buchstabe, großgeschrieben (aus `Void of Emperor [INTIM]` wird so `V O E I`). Haben in einer Datei mehrere Spieler dieselben Initialen, erhält der in der Reihenfolge des ersten Auftretens zweite den Zusatz ` 2`, der dritte den Zusatz ` 3` usw. (Owner-Entscheid 2026-11-13, Issue #1108). Turnier, Datum, Ergebnis und Karten sind unverändert.
