# #1738 (Punkt 5): `board_wipe`-Abdeckung im echten Studio-Store (2026-11-24)

Refs #1738, #1648, #1780.

## Messaufbau

- **Datenbasis:** isolierte temporäre SQLite-Backup-Kopie des lokalen Owner-Studio-Stores (`232 MB`, `35.360` Zeilen in `scryfall_card`, `18.652` Zeilen in `card_role`, Stand `main` `aa7a4b57e`); der Original-Store wurde nur lesend gesichert, keine Store-Kopie oder personenbezogene Daten im Repository.
- **Quelle der Rolle `board_wipe`:** Tabelle `card_role` (öffentliche Scryfall-Tagger-Marke `board-wipe`, über `builder.pool_cards(..., include_unowned=False/True)` abgefragt — exakt derselbe Pfad wie der Filter-Chip „Boardwipes“ in `app.js` / `wishlist.js`). Karten ohne Rolleneinträge gelten als unbekannt, nie als `0`.

## Ergebnis (aggregierte Zählungen `n/N`)

- **Gesamter Store (`card_role`):** `10.690` verschiedene `oracle_id`s mit mindestens einer Rolle (von `35.360` `scryfall_card`s), davon **`359`** mit `board_wipe` (`3,36 %` der rollenmarkierten Karten).

| Commander | Teilmenge | Gesamt (`N`) | mit Rollendaten (`n_roles / N`) | ohne Rollendaten (`unbekannt`) | `board_wipe` (`n / N`) | `board_wipe` unter rollenmarkierten |
|---|---|---:|---:|---:|---:|---:|
| Chulane, Teller of Tales (`WUG`) | Eigene Sammlung (`owned`) | 927 | 638 / 927 (68,8 %) | 289 / 927 (31,2 %) | **9 / 927** (0,97 %) | 9 / 638 (1,41 %) |
| Chulane, Teller of Tales (`WUG`) | Zukauf (`unowned`) | 925 | 669 / 925 (72,3 %) | 256 / 925 (27,7 %) | **34 / 925** (3,68 %) | 34 / 669 (5,08 %) |
| Chulane, Teller of Tales (`WUG`) | Kombiniert (`owned + unowned`) | 1.852 | 1.307 / 1.852 (70,6 %) | 545 / 1.852 (29,4 %) | **43 / 1.852** (2,32 %) | 43 / 1.307 (3,29 %) |
| Tamiyo, Field Researcher (`WUG`) | Eigene Sammlung (`owned`) | 927 | 638 / 927 (68,8 %) | 289 / 927 (31,2 %) | **9 / 927** (0,97 %) | 9 / 638 (1,41 %) |
| Tamiyo, Field Researcher (`WUG`) | Zukauf (`unowned`, PW + Proliferate) | 213 | 164 / 213 (77,0 %) | 49 / 213 (23,0 %) | **10 / 213** (4,69 %) | 10 / 164 (6,10 %) |
| Tamiyo, Field Researcher (`WUG`) | Kombiniert (`owned + unowned`) | 1.140 | 802 / 1.140 (70,4 %) | 338 / 1.140 (29,6 %) | **19 / 1.140** (1,67 %) | 19 / 802 (2,37 %) |

## Einordnung & Grenzen
- Die Zukauf-Auswahl (`unowned_selection`) für Chulane umfasst `925` Karten (`corpus: 514`, `edhrec: 620`, `planeswalker: 146`, `proliferate: 67`, `corpus_denominator: 3.798`), für TAM `213` Karten (`planeswalker: 146`, `proliferate: 67`; ohne Korpus-/EDHREC-Kohorte).
- Rund `23–31 %` der Pool-Karten tragen im Store keine Tagger-Rollendaten (`unbekannt`) und erscheinen beim Filter „Boardwipes“ bewusst nicht (Hinweis in `app.js:3762` und `wishlist.js:94` bleibt zutreffend).
- Falsche Negative innerhalb der `289`/`256`/`49` unmarkierten Karten wurden nicht manuell nachbewertet (`UNKNOWN`).
