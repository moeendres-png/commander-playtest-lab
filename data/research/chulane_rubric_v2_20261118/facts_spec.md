# Kartenverständnis-Raster v2: deterministische Fakten (facts_spec)

Entwurf, nichts davon ist beschlossen oder gebaut. Zweck: Der Rater (Sprachmodell) bekommt je Karte
nur belegbare, wiederholbar berechnete Fakten, damit er die Karte *versteht* und nicht rät. Jede
Zahl ist n von N, unbekannt wird nie als 0 geschrieben, es gibt keine Simulation, keine Preise,
Markierungen (favorite/excluded/note) haben keinen Einfluss.

## 1. Aufruf

```
PYTHONPATH=<checkout>/src python3 scripts/extract_facts.py --store <KOPIE-des-Stores> --repo <checkout> \
    --out <ordner> [--deck-revision chulane-current@41f393530bb16ee9]
```

`scripts/run_all.sh <Store-Kopie> <checkout> [<Ausgabe>]` baut alles (Fakten, Muster, Pilotstichprobe, Anker,
Prompt-Größe). Der Store wird schreibgeschützt geöffnet (`sqlite ?mode=ro`, nur eine Kopie
verwenden); Studio-Code (`castability`) wird über `PYTHONPATH` gelesen, nichts nachgebaut.
Pool = die 922 Karten von `data/research/chulane_rubric_20261114/summary.csv` (= die 922 gerankten Karten
von `strength_view.compute`; im Lauf geprüft: gleiche Namensmenge, alle 922 haben `card_fact`).
Der Lauf ist deterministisch (zwei Läufe, `cmp` gleich; `facts_manifest.json` hält sha256 von Store,
`summary.csv` und den drei Ausgaben).

## 2. Ausgaben

| Datei | Inhalt | Rater-sichtbar |
|---|---|---|
| `data/facts.jsonl` | je Oracle-ID ein Objekt (2,8 KB je Karte im Mittel) | ja |
| `data/patterns.jsonl` | Musterbelege (siehe `patterns_spec.md`) | ja |
| `data/usage_holdout.jsonl` | Nutzungszahlen, Beliebtheit, Referenzdeck, v1-Rubrik | **nie** |
| `data/pool_benchmarks.json` | Peer-Tabellen des ganzen Pools (Median je Rolle) | ja (als Auszug) |
| `data/facts_manifest.json` | Zählungen, Versionen, sha256 | nein |

**Leak-Guard:** `extract_facts.py` und `extract_patterns.py` brechen ab, wenn ein Schlüssel in
`facts.jsonl` oder `patterns.jsonl` nach Nutzung, Beliebtheit, Preis oder v1-Bewertung heißt
(`edhrec`, `deck_list`, `rubric`, `H_mean`, `times_brought`, `playgroup`, `inclusion`, `price`,
`usage`, `popular`, `v1` ...). Geprüft werden Schlüssel, nicht Werte (Kartentext darf jedes Wort
enthalten). `render_prompt.py` liest `usage_holdout.jsonl` nie.

## 3. Felder von `facts.jsonl` (Version `facts-1`)

Abdeckung = n von 922. "Klasse": Fakt (Scryfall-Spalte im Store), abgeleitet (Regel/Rechnung aus
Fakten), Label (Tagger/Regeln, kann falsch sein).

| Feld | Quelle | Klasse | Abdeckung / Hinweis |
|---|---|---|---|
| `oracle_id`, `name`, `layout` | `card_fact` | Fakt | 922. Layouts mehrseitig: 12 (prepare 6, transform 4, flip 1, adventure 1) |
| `faces[]` (Name, Kosten, Typzeile, Oracle-Text je Seite) | `card_fact`, gesplittet an ` // ` und `\n//\n` | Fakt | alle 12 mehrseitigen Karten zerlegt (`faces_parse_ok`); Zerlegung bei Abweichung unterbleibt, nichts wird geraten |
| `mana_cost`, `mana_value` | `card_fact` | Fakt | 922 (Länder: Kosten leer, MW 0). MW ist der der Vorderseite |
| `type_line`, `type_group`, `types_front` | `card_fact`; Gruppe = erste Treffer-Gruppe aus Land, Kreatur, Planeswalker, Battle, Artefakt, Verzauberung, Spontanzauber, Hexerei | Fakt / abgeleitet | Kreatur 478, Spontanzauber 146, Artefakt 82, Verzauberung 81, Hexerei 66, Land 65, Planeswalker 4 |
| `is_creature_front`, `is_land_front` | Vorderseite | abgeleitet | 478 / 65 |
| `colour_identity`, `off_colour_identity` | `card_fact`; Abweichung zu WUG | Fakt | 922; fremde Identität 0 von 922 (Pool ist WUG) |
| `pips_front`, `colours_in_cost`, `colour_pips_total` | Mana-Kosten-String der Vorderseite: Pips je W/U/B/R/G, generisch, X, hybrid, Phyrexian | abgeleitet | 922; hybride Symbole zählen für beide Farben (gekennzeichnet) |
| `power`, `toughness`, `pt_total` | `card_fact` (Vorderseite) | Fakt | Kreaturen 478; `*` ergibt `pt_total` leer (bekannt, nicht 0) |
| `keywords`, `produced_mana` | `card_fact` | Fakt | 922 (leer = keine) |
| `game_changer` | `card_fact` | Fakt | 3 von 922 (Bracket 3 erlaubt höchstens drei im Deck) |
| `has_oracle_text` | Text nicht leer | abgeleitet | 900; 22 Kreaturen ohne Text sind **bekannt "kein Text"** (Vanilla), nicht unbekannt |
| `roles[]` (`role`, `origins[]`), `primary_role` | `card_role`, `card_role_claim` (Herkunft Tagger, Crosswalk, Oracle-Text-Regel); Hauptrolle = erste in `PRIMARY_ROLE_ORDER` | Label | 817 mit Rolle, 105 ohne (nicht gelabelt, nicht "ohne Funktion"). Stichprobe der Rollen (Bestandsaufnahme, 20 Karten): 17 plausibel, 2 falsch, 1 unklar; `bounce` trennt Fremd- von Eigenbounce nicht |
| `rulings_n`, `rulings[]` | `card_ruling` (Scryfall/WotC-Hinweise) | Fakt | 518 von 922 haben mindestens einen. Der Prompt zeigt höchstens 4, je 240 Zeichen |
| `combo_hint_spellbook_shells_with_chulane` | `card_signal` `spellbook_shells` (Commander-Spellbook-Linien mit Chulane, die die Karte enthalten) | **Kombo-Datenbank, keine Nutzungszahl** | 7 Karten haben Wert über 0, bei 915 ist er 0. Als offene Frage an den Owner geführt (siehe Abschnitt 8) |
| `castability` | Abschnitt 4 | abgeleitet | 857 von 857 Nichtländer (142 ohne Farbsymbol), Länder `null` |
| `peer_benchmark` | Abschnitt 5 | abgeleitet | alle 922 |
| `land` (nur Länder) | `enters_tapped` (untapped / tapped / conditional aus dem Text), WUG-Farben, "jede Farbe der Identität", holt ein Land | abgeleitet | 65 |

Nicht enthalten, bewusst: Besitz (irrelevant), Preise, EDHREC, Deckzähler, Playgroup, Tierliste-Stufe,
Rubrik v1, Referenzdeck-Zugehörigkeit, Kommandeur-Synergie-Werte aus Quellen.

## 4. Castability (Karsten, Referenzdeck)

Aufruf (Studio-Code, Zeile `castability.colour_probability` in `studio/castability.py`):

```
need, left_out = castability.requirement(mana_cost)
res = castability.colour_probability(land_groups, nonland + 1, need, max(1, mana_value))
```

`land_groups` = Länder des Referenzdecks `chulane-current@41f393530bb16ee9` nach den Farben, die sie erzeugen
(36 Länder, 63 Nichtländer, +1 Kandidat; Gruppen in `facts_manifest.json`). Ausgabe je Karte:
`p_land_drops` (mindestens MW Länder unter 7+MW Karten), `p_colours_given_lands`, `p_on_curve` (beides),
`sources` je Farbe, `colour_free_cost`, `x_cost`, `hybrid_or_phyrexian_left_out`. Das ist *Wahrscheinlichkeit
on curve* für den Zug MW (mindestens Zug 1), ohne Mulligan, ohne Kartenzug, ohne Chulane-Trigger.
Grenzen: eine Landbasis (die des Owner-Referenzdecks, damit nicht unabhängig vom Owner-Geschmack);
Bestandsaufnahme: nur Tor, als Rang schwach (AUC 0,54). Der Rater nutzt den Wert für R und D bei farbintensiven
Karten, nicht als Qualitätsmaß.

## 5. Rollen-Peer-Benchmarks (für Kriterium E)

- **Peers** einer Karte = die *anderen* Nichtland-Karten des Pools mit derselben Rolle (je Rolle der Karte,
  Hauptrolle zuerst, der Prompt zeigt bis zu drei) plus die Typgruppe. Gezeigt werden Zahl der Peers, Median
  und Quartile des Manawerts, und wie viele Peers billiger, gleich teuer, teurer sind (n von N).
  Beispiel (Rechnung im Lauf): Rolle `bounce` 33 weitere Karten, Median MW 3, Shrieking Drake MW 1: 0 billiger,
  4 gleich, 29 teurer.
- **Körper-Benchmark** für Kreaturen mit Zahlenwerten: Stärke plus Widerstand der Peers gleichen Manawerts.
- **Länder** haben keinen MW. Verglichen wird in Gruppen (Zahl der WUG-Farben, enters tapped ja/nein/bedingt, holt ein Land);
  15 Gruppen, einige mit nur 1 bis 4 Mitgliedern (Vorsicht).
- Kleine Gruppen (n unter 8) sind markiert (15 Nichtland-Karten betroffen). 89 Nichtland-Karten haben keine Rolle und
  bekommen nur die Typgruppe.
- **Grenzen:** Peers sind nur Karten **dieses Pools** (922, Sammlung geschnitten mit WUG-Legalität), nicht alle WUG-Karten
  des Formats; Rollen sind Labels mit bekannter Fehlerquote; breite Rollen (`hate` 95, `card_advantage` 167, `combat_trick` 119)
  sind als Peer-Gruppe grob. Der Rater darf Benchmarks nur als Hinweis für "billiger/teurer als vergleichbare Karten" nutzen.

## 6. Holdout `usage_holdout.jsonl`

Je Karte: `deck_list_count` und `deck_list_total` (Signal `decklist_universe:corpus:1-5`, Nenner 10.128; *kein
Signalzeile = gezählt 0*, weil der Korpus vollständig gezählt ist, Studio-Status ZERO_COUNT; 186 Karten, im Feld
`deck_list_zero_by_absence` markiert), Anteile je Bracket-Korpus (n, N), EDHREC-Global-Aufnahme (n, N),
Scryfall-`edhrec_rank`, Playgroup `times_brought` und `decks_running`, `in_reference_deck`, und der v1-Block
(H_mean, H_sd, Rater, Anker, E/F/T/R/W-Mittel). Zweck: Kalibrierung und Validität nach der Bewertung, nie im Prompt.
Alle Quellen sind Nutzung/Beliebtheit (Kohorten nicht gemischt) oder die v1-Bewertung.

## 7. Studio-Regeln, wie eingehalten

- Jede Zahl mit n/N: Abdeckungen oben; Peer-Tabellen mit Peer-Zahl; Castability mit Quellen je Farbe.
- Unbekannt ungleich 0: `null` für Länder-Castability, `pt_total` bei `*`, leere Rolle als "nicht gelabelt";
  die einzige Null-Ableitung (`deck_list_count` 0) steht im Holdout und ist als ZERO_COUNT begründet.
- Keine Simulation, keine Preise, Markierungen werden nicht gelesen (`card_mark` kommt im Skript nicht vor).
- Fakten beschreiben (Klasse "Fakt/abgeleitet/Label"), sie bewerten nicht.

## 8. Offene Punkte

1. `combo_hint_spellbook_shells_with_chulane` im Rater-Block lassen? Es ist Kombo-Datenbank, keine Nutzung, aber nur
   7 Karten haben Werte über 0 und die Linien stammen aus Community-Funden. Empfehlung: im Pilot anzeigen, danach prüfen,
   ob es die Bewertung verzerrt.
2. Referenz-Landbasis für Castability: das Owner-Deck (bequem, aber vom Owner geprägt) oder eine feste Standardbasis?
3. Rulings anzeigen (Tokens, aber weniger erfundene Regelbehauptungen) oder weglassen? Empfehlung: anzeigen, bis zu 4.
