# Precon-Decks: gemessener Stand

Stand: 2026-10-20, Pin `043579bb` (XMage 1.4.62, Repin v9). Evidenzklassen nach `AGENTS.md` §4.
Alle Läufe sind lokal (`LOCAL_OBSERVED`), kein CI-Kredit.

## Bestand

`data/decks/precons/` enthält **195** Decks (2011–2026, je 100 Karten). Drei Decks mit gebannten
Karten wurden entfernt. Frühere Texte nannten 198 Decks; das stimmt nicht mehr.

## Import über den produktiven Pfad (`DIRECTLY_VERIFIED`)

Gemessen mit `scripts/measure_precon_imports.py`: jedes Deck läuft über
`ExternalRulesAdapter.import_deck()` in den Java-`XmageDeckImporter` (Kartenauflösung und
Commander-Validierung). **Es wird kein Spiel gespielt.** Frische Card-DB je Lauf.

| Stand | Import OK | Blockiert |
|---|---|---|
| Alter Pin `348b37db` (1.4.61), Daten wie vorgefunden | 173/195 | 18 Decks wegen 53 fehlender Kartennamen, 4 Decks wegen Commander-Namen |
| Neuer Pin `043579bb` (1.4.62), nach Daten-Fix der Commander-Namen | **182/195** | 13 Decks wegen 31 fehlender Kartennamen |

Daten-Fix: Vier Decks führten in `commander.commanders` den Namen in der Form „A // B“
(`2022_heads_i_win__tails_you_lose`, `2023_angels__they_re_just_like_us_but_cooler_and_with_wings`,
`2023_from_cute_to_brute`, `2024_raining_cats_and_dogs`). Der Importer löst nur die Vorderseite
auf (`CARD_IDENTITY_MISMATCH`). Die Karten selbst stehen mit Vordernamen im Deck; nur das
Commander-Feld wurde auf die Vorderseite gesetzt.

Fehlende Kartennamen am Pin `043579bb` (der Importer meldet pro Aufruf nur die erste; die
Liste stammt aus der Enumeration mit Platzhaltern, `measure_precon_imports_deep.py` auf
`muse/claude-handover`, `handover/2026-10-20/precon-nachmessung/`):

| Deck | Fehlende Kartennamen |
|---|---|
| `2023_blast_from_the_past` | Susan Foreman |
| `2023_masters_of_evil` | Missy, Cyber Conversion, Doomsday Confluence, Death in Heaven, Rassilon, the War President, The Cyber-Controller, Cybership, Don't Blink |
| `2023_paradox_power` | The Foretold Soldier, River Song's Diary, Psychic Paper |
| `2023_timey_wimey` | The Pandorica, The War Doctor, The Moment, Psychic Paper |
| `2024_blame_game` | Feather, Radiant Arbiter; Immortal Obligation |
| `2024_death_toll` | Winter, Cynical Opportunist (Commander) |
| `2024_family_matters` | Zinnia, Valley's Voice (Commander) |
| `2024_miracle_worker` | Aminatou, Veil Piercer (Commander) |
| `2024_revenant_recon` | Eye of Duskmantle |
| `2024_tricky_terrain` | Desert Warfare |
| `2024_tricky_terrain_collector_s_edition` | Desert Warfare |
| `2026_multiverse_reforged` | Dack Fayden, Helping Hand; Teferi's Reproach; Jhoira, Weatherlight Corsair; Venser, Fervent Forger; Tamiyo, Upriser Crowned; The Ur-Sphinx; Jace, Multiverse Architect (Commander) |
| `2026_odds_and_ends` | Exchange of Words, Space Beleren |

Vereinfachte Ersatzkarten (`SYNTHETIC`) aus den früheren Fork-Patches schließen diese Lücke nur
beim Import. Sie spielen nicht wie gedruckt und sind keine Regelevidenz.

## Spielbarkeit

**Import ist nicht Spielbarkeit.** Der Import beweist nur, dass Kartennamen und Commander
aufgelöst werden. Ob ein Deck in einem echten 4er-Pod durchspielt, zeigt `scripts/precon_pod_sweep.py`:
Pods aus vier verschiedenen Decks (derselbe Aufbau wie ein echtes Spiel; ein Deck auf mehreren
Plätzen lehnt der Validator vor dem Start ab).

Stand der Messung:

- Neuer Pin `043579bb`: Sweep über die 182 importierbaren Decks **NOT_RUN** (siehe Issue #920).
- Alter Pin `348b37db`, Stichprobe (25 Pods aus je vier verschiedenen Decks, Seed 1, nur Decks
  ohne fehlende Karten, `LOCAL_OBSERVED`): 19 Pods liefen durch, 6 scheiterten in vier Familien:
  Kosten mit Auswahl (Ghave, Necron Overlord, Grim Hireling: die Engine bietet die Aktivierung
  an, kann sie aber nicht ausführen), modaler Zauber mit Escalate (Collective Effort),
  Doppelseiten-Identität (inzwischen durch den Daten-Fix behoben) und ein
  `DECISION_ADVANCE_TIMEOUT` in `DistributeCountersEffect` (Ursache unbekannt, zweimal
  reproduziert). Eine Stichprobe ist keine Passquote.

## Reproduktion

```
python scripts/measure_precon_imports.py --jar <bridge.jar> --workdir <leeres Verzeichnis> --out imports.json
python scripts/precon_pod_sweep.py --jar <bridge.jar> --out sweep.json --import-report imports.json
```

Immer nur ein Sweep gleichzeitig: bei CPU-Mangel werden langsame Entscheidungen zu
`BRIDGE_TIMEOUT`/`DECISION_ADVANCE_TIMEOUT` und sehen wie Engine-Fehler aus.

## Nicht belegt

- „Alle Precon-Karten sind in XMage implementiert und spielbar“ (frühere Fassung dieser Datei):
  widerlegt, 31 Kartennamen fehlen am Pin, und Import beweist keine Kartenfunktion.
- Die Zahlen „195/195 ENGINE_FAILURE“ und „221 fehlende Karten“ aus früheren Übergaben: Das
  Skript hat dasselbe Deck auf alle Plätze gesetzt, die 221 stammt aus einer
  Dateinamen-Heuristik. Beide dürfen nicht mehr zitiert werden.
