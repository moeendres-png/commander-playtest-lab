# Kartenverständnis-Raster v2: regelbasierte Chulane-Muster (patterns_spec)

Entwurf, nichts beschlossen oder gebaut. Regelversion: `PATTERN_RULES_VERSION = "chulane-patterns-1"`
(`extract_patterns.py`). Jede Änderung an einem regulären Ausdruck oder am Geltungsbereich einer Regel
erhöht die Version. Klasse der Ausgabe: **abgeleitet/beschrieben aus dem Oracle-Text**, nie Messwert, nie
Simulation, keine Nutzung, Gewicht 0 in jedem Index. Ein Treffer ist ein **Hinweis mit Belegzeile**, kein Urteil;
der Rater prüft jeden gezeigten Treffer in `pattern_check` (correct / wrong / irrelevant), das liefert im Pilot
eine zweite, unabhängige Präzisionsmessung.

## 1. Aufruf

```
PYTHONPATH=<checkout>/src python3 scripts/extract_patterns.py --facts data/facts.jsonl --out data \
    --usage-holdout data/usage_holdout.jsonl [--sample 20 --seed 1118]
PYTHONPATH=<checkout>/src python3 scripts/check_pattern_recall.py      # Recall-Scan (Merkliste, keine Kennzahl)
```

Der Text wird so normalisiert: Reminder-Text in Klammern entfernt, Kleinbuchstaben, eigener Name (voll, vor
Komma, vor " of ") und "this creature/permanent/..." werden zu `~` ("that card" bleibt). Die Regeln arbeiten je
Fähigkeitszeile und je Satz, nie über Zeilen hinweg. `--usage-holdout` dient nur dazu, die Treffer unter den 186
Karten mit 0 von 10.128 Quelldecks zu zählen (n von 186); es verändert keinen Treffer. Ausgabe:
`patterns.jsonl` (je Karte: Regel-IDs und Belegzeilen), `pattern_summary.json`, `pattern_sample.json`
(20 Zufallstreffer je Regel, Seed fest).

## 2. Regeln, Treffer und Präzision (n von 922)

Spalten: Treffer im Pool (davon Kreaturenvorderseite, Land, unter den 186 Null-Karten) | Prüfbasis | Präzision
"textrichtig" = der Treffer erfüllt die Regelbeschreibung laut Kartentext (von mir von Hand beurteilt, Endversion
der Regeln).

**Wichtig zur Aussagekraft:** Regeln mit höchstens 23 Treffern sind **vollständig durchgesehen (Vollerhebung)**,
aber die Regeln wurden an genau diesen Treffern abgestimmt (in-sample): die Präzision ist dort eine obere Schranke,
keine Schätzung. Echte Hold-out-Prüfung (Seed 2024, nicht zum Abstimmen benutzt) gibt es nur für die drei
großen Regeln `etb_own`, `noncreature_draw_or_ramp`, `creature_dependent`; die Stichprobe mit Seed 1118 wurde beim Abstimmen angesehen
(bei `etb_own` und `creature_dependent` wurden danach Regeln geändert) und ist **nicht unabhängig**; sie steht getrennt und zählt nicht zur
Hold-out-Zahl. Die Stichprobe von Hand ist die eines
Beurteilers (ich); der Pilot (Rater-`pattern_check`) liefert eine zweite Messung.

| Regel | Treffer (Kr / Land / Null) | Prüfbasis | Präzision textrichtig | Fehlerfälle und Grenzen |
|---|---|---|---|---|
| `etb_own` eigener ETB-Trigger | 154 (114 / 17 / 22) | Hold-out Seed 2024 (20); Seed 1118 (20) nicht unabhängig | **Hold-out 20/20 (untere 95-%-Grenze 84 %)**; Seed 1118 20/20 | **Chulane-relevant (Kreatur): Hold-out 13/20, Seed 1118 14/20, im Pool 114/154 = 74 %:** Auren (Infinite Coursework), Länder (Mystic Sanctuary, Temple scry), Ausrüstung/Fahrzeug/Artefakt zählen textrichtig, helfen Chulanes Bounce aber nicht. Keyword-ETBs im Reminder-Text (Living weapon: Flayer Husk, Mortarpod, Nettlecyst, Skinwing, Strandwalker; Soulbond: Pathbreaker Wurm) sind **nicht** erfasst (bewusst, Reminder wird entfernt). Hada Freeblade, Talus Paladin, Thoughtweft Lieutenant und Kappa Cannoneer ("~ or another X") stehen in zwei Klassen (`etb_own` und `etb_other_*`) |
| `etb_own_draw` ETB zieht Karten | 10 (7 / 0 / 1) | Vollerhebung | 10/10 | davon bedingt oder Loot: Garruk's Uprising (bedingt), Sky-Eel School (Loot), Puca's Eye (zieht und wählt Farbe) |
| `etb_other_creature` Trigger einer anderen Kreatur | 11 (8 / 0 / 1) | Vollerhebung | 11/11 | 6 von 11 eingeschränkt (Stärke 4/5 oder mehr, nontoken, non-Human, Marke) |
| `etb_other_permanent` Trigger anderer Permanents | 8 (8 / 0 / 0) | Vollerhebung | 8/8 | Beschreibung: nicht wörtlich "creature/land"; enthält Untertyp-Karten (Mary Jane Watson "a spider"), 4 doppelt mit `etb_own` |
| `landfall` | 18 (12 / 0 / 1) | Vollerhebung | 18/18 | 15 Trigger plus 3 Landfall-Bedingungen auf Zaubern ohne Trigger (Groundswell, Mysteries of the Deep, Rest for the Weary), im Beleg `form: spell_condition` |
| `land_extra_drop_or_from_hand` | 8 (2 / 0 / 0) | Vollerhebung | 8/8 | Rites of Flourishing symmetrisch (Feld `symmetric`); Embrace the Paradox und On the Trail legen das Land tapped. Wiederspielen vom Friedhof/Bibliotheksoberseite (Ramunap Excavator, Augur of Autumn) ist kein zusätzlicher Landdrop und bewusst nicht erfasst |
| `land_onto_battlefield_effect` Land aufs Schlachtfeld | 23 (8 / 7 / 0) | Vollerhebung | 23/23 | Fetch-/Opfer-Länder (7) und Opfer-Kreaturen (Sakura-Tribe Elder, Dawntreader Elk) zählen mit; Demolition Field ramp auch den Gegner |
| `bounce_own_creature` | 8 (6 / 0 / 1) | Vollerhebung | 8/8 | 5 wörtlich "creature you control" (Fleetfoot Panther, Havengul Skaab, Shrieking Drake, Stormfront Riders, Whitemane Lion), 3 "permanent you control" (Kor Skyfisher, Narrow Escape, Aether Tradewinds), eine Kreatur ist dort nur eine der Wahlmöglichkeiten |
| `bounce_any_creature_target` | 14 (3 / 0 / 1) | Vollerhebung | 14/14 | rein laut Kartentext: Ziel nicht auf Gegner beschränkt; 6 sind "nonland permanent" (Banishing Betrayal, Disperse, Into the Roil, Whoosh!, Quicksilver Geyser, Aether Gale), der Rest Kreatur. Es sind Spot-Entfernungen, ihr Nutzen für Chulane ist Urteil |
| `bounce_own_land` Bounce-Länder | 4 (0 / 3 / 0) | Vollerhebung | 4/4 | Selesnya Sanctuary, Azorius Chancery, Simic Growth Chamber, Vapor Snare (Kosten, kein Bounce-Land) |
| `bounce_own_other_permanent` | 1 | Vollerhebung | 1/1 | Esperzoa (Artefakt) |
| `bounce_mass_includes_own` | 1 | Vollerhebung | 1/1 | Kederekt Leviathan |
| `bounce_self` | 3 (1 / 1 / 1) | Vollerhebung | 3/3 wörtlich; **Chulane-relevant 1/3** | nur Arcanis the Omnipotent ist Kreatur; Maze's End (Land), Razor Boomerang (Ausrüstung). **Erste Fassung 7 Treffer, 4 falsch** (Zendikon x3, Angelic Destiny: Rückkehr aus dem Friedhof), behoben |
| `blink_own` | 5 (3 / 0 / 0) | Vollerhebung | 5/5 | Ruin Ghost blinkt ein **Land** (Feld `target: land`); Glimmerpoint Stag und Disorder in the Court blinken beliebige Ziele (`scope: any`). **Erste Fassung 1 Treffer**: `~`-Wortgrenze und "that card" wurde fälschlich zu `~`, behoben (Personify, Flickering Hound jetzt gefunden) |
| `cast_trigger_creature` | 3 (2 / 0 / 0) | Vollerhebung | 3/3 | Champions of the Perfect, Flickering Hound, Primeval Bounty |
| `cast_creature_draw` | 1 | Vollerhebung | 1/1 | Champions of the Perfect |
| `cast_trigger_any_spell` | 0 | **leere Menge** | 0/922 | erste Fassung 7 Treffer, 0/7 richtig (alles Zauber mit Einschränkung), behoben |
| `cast_trigger_other_type` | 18 (15 / 0 / 2) | Vollerhebung | 18/18 | Trigger auf Typ/MW-eingeschränkte Zauber (Spontanzauber/Hexerei, Artefakt, MW 4 oder mehr, Stammesart); Gnarlback Rhino ("Zauber, der ~ zum Ziel hat") grenzwertig |
| `mana_creature_cheap` (MW 2 oder weniger) | 13 (13 / 0 / 0) | Vollerhebung | 13/13 | eingeschränkt: Hydro-Channeler (nur Spontanzauber/Hexerei), Lys Alana Dignitary (Bedingung), Priest of Titania (Elfenzahl); Arbor Elf entsperrt statt Mana zu erzeugen |
| `mana_creature_other` (MW 3 oder mehr) | 5 (5 / 0 / 0) | Vollerhebung | 5/5 | |
| `cost_reduction_creature` | 0 | **leere Menge** | 0/922 | Recall-Scan: keine Zeile "costs {N} less" ungetroffen außer Fähigkeitskosten (Tezzeret, Diary of Dreams), bestätigt den Befund "0 im Pool" |
| `cost_reduction_any_spell` | 0 | **leere Menge** | 0/922 | wie oben; Gathering Stone ("of the chosen type") steht in `typed` |
| `cost_reduction_typed_spell` | 5 (4 / 0 / 0) | Vollerhebung | 5/5 | Ballyrush Banneret, Dirgur Focusmage, Gathering Stone, Mocking Sprite, Thunderclap Drake |
| `self_cost_reduction` | 23 (15 / 0 / 1) | Vollerhebung | 23/23 | Keywords Convoke/Delve/Affinity/Improvise und "costs {N} less ... if/for each" |
| `etb_doubler` | 0 | **leere Menge** | 0/922 | Recall-Scan: kein Treffer auf "additional time" |
| `untapper` | 14 (7 / 1 / 4) | Vollerhebung | 14/14 | wörtlich "untap ..."; Fabled Passage entsperrt nur das geholte Land; Nutzen für Chulane (Chulane entsperren) ist Urteil |
| `noncreature_draw_or_ramp` (Anti, schwach) | 104 (0 / 0 / 12) | Hold-out Seed 2024 (20); Seed 1118 (20), Regel dort nicht abgestimmt | **Hold-out 19/20 (untere Grenze 76 %)**; beide zusammen 39/40 (87 %) | Fehler: Imprisoned in the Moon (Studio-Rollenregel `classify_oracle_roles` liest "{T}: Add {C}" auf dem verzauberten Land als Ramp, es ist Entfernung). **Aussagekraft als Anti-Synergie schwach**: nur "löst Chulanes Trigger nicht aus", kein Abzug |
| `wipe_symmetric` | 5 (0 / 0 / 0) | Vollerhebung | 5/5 | Farewell (modal, "exile all creatures" ist ein Modus), Fumigate, Organic Extinction ("nonartifact"), Slash the Ranks, Winds of Rath. Erste Fassung 6 Treffer (Spitting Spider "creature with flying" falsch), behoben |
| `wipe_one_sided` | 0 | **leere Menge** | 0/922 | erste Fassung 2 Treffer, beide falsch (Turn the Tide, Hysterical Blindness: -N/-0 Tricks), behoben |
| `edict_symmetric` | 0 | **leere Menge** | 0/922 | |
| `symmetric_benefit` | 6 (5 / 0 / 1) | Vollerhebung | 6/6 | Faerie Mastermind, Rites of Flourishing, Runed Servitor, Selvala, Innocuous Researcher, Conundrum Sphinx |
| `self_life_loss` | 6 (0 / 2 / 0) | Vollerhebung | 6/6 | Pain-Länder, Talismane (1 Schaden), Spire of Industry, Deep Analysis. Erste Fassung 7 Treffer (Circle of Protection: Blue falsch: "würde Schaden verhindern"), behoben |
| `creature_dependent` (Anti) | 61 (10 / 0 / 15) | Hold-out Seed 2024 (20); Seed 1118 (20) abgestimmt | **Hold-out 20/20 (untere Grenze 84 %)**; Seed 1118 20/20 (nicht unabhängig) | Endversion (Ausrüstung, "creatures you control get ...", "enchanted creature gets +", "for each creature you control"); Erste Fassung (auf Seed 1118) 15/20 (Entfernungs-Auren wie Pacifism zählten). Auren mit Karten- oder Fähigkeitsgewinn statt "gets +" sind nicht erfasst |

Zusammenfassung: 105 von 922 Karten tragen mindestens ein Chulane-Muster außer `etb_own` und `landfall` (Pool, n von 922);
unter den 186 Null-Karten (0 von 10.128 Quelldecks) tragen `etb_own` 22, `untapper` 4, `cast_trigger_other_type` 2 und je 1
`bounce_own_creature`, `bounce_any_creature_target`, `bounce_self`, `etb_other_creature`, `etb_own_draw`, `landfall`.
Die Regeln trennen also vor allem Karten **mit** Nutzung, in der Null-Gruppe finden sie wenig (bestätigt die Bestandsaufnahme).

## 3. Recall und Abgleich mit dem Tagger

- Recall-Scan (`check_pattern_recall.py`): listet Textzeilen, die nach einem Muster aussehen und von keiner Regel getroffen
  wurden. Letzter Stand: ETB 0 Lücken, Kostenreduktion 2 (nur Fähigkeitskosten), Bounce: Gegner-Bounce (Harbinger of the Tides,
  Brazen Borrower), Auren/Zendikon-Rückkehr aus dem Friedhof, Karten, die ihre Beute zurückgeben (Champions of the Perfect).
  Das ist eine Merkliste, keine Kennzahl.
- Gegen die Rollenlabels (Tagger, Crosswalk, Textregel) der Karten im Store, n von 922 (Rollenzahl / Regeltreffer / beide):
  `bounce` 38 / 31 / 31, `flicker` 8 / 5 / 5, `landfall` 20 / 18 / 18, `mana_dork` 20 / 18 / 18, `untapper` 16 / 14 / 14,
  `board_wipe` 9 / 5 / 5, `cost_reduction` 19 / 5 / 5. **Kein Regeltreffer ohne Rollenlabel (0)**; die Karten nur mit
  Rollenlabel sind erklärt: Gegner-Bounce und Rückkehr aus dem Friedhof (7 bei `bounce`), Rückkehr-Blink (Journey to Nowhere,
  Leonin Relic-Warder), Gate-Trigger (Gate Colossus, Gateway Sneak), Mana über Schatzmarker (Loot, Tireless Provisioner),
  Selbst-Kostenreduktion (14 bei `cost_reduction`). Der Tagger trennt `bounce` nicht in Eigen- und Fremdbounce, die Regeln tun es.
- Vergleich mit der Agent-Probe der Bestandsaufnahme: eigener ETB 145 (Probe) gegen 154 (Regel, Namen und Kurzformen "Loran"
  statt "this creature" gefunden); Landfall 18 gegen 18; Bounce eigener Kreatur 4 gegen 8 (Probe zu eng); mechanical-1
  `enters_trigger_text` 189 gegen 154 eigener ETB: die 35 Differenz sind 29 Landfall-/Fremdtrigger und 6 Keyword-Reminder-ETBs
  (Living weapon 5, Soulbond 1). Ein Fehler des Zwischenstands (Lizard, Connors's Curse: Fähigkeitswort-Präfix mit Kartenname) ist behoben.

## 4. Bekannte Lücken

Mana-Kreaturen über Schatzmarker oder Filter-Fähigkeiten ({1}: Add ...; Foraging Wickermaw, Three Tree Mascot, Tireless
Provisioner, Loot), ETBs im Reminder-Text, Aura-Kreaturenabhängigkeit mit Kartenzug, Zonen-Wiederspiel (Land vom Friedhof),
Mehrseitenkarten (nur Zeilen jeder Seite, keine Regel für "andere Seite" je Zauber). Kreaturenspezifische Kostensenkung und
ETB-Verdoppler kommen im Pool nicht vor (0 von 922, kein Merkmal nötig).
