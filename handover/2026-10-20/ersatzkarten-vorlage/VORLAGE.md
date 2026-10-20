# Entscheidungsvorlage: Ersatzkarten für die 13 Precon-Decks mit fehlenden Karten

Stand: 2026-10-20 · Lab `ed2fbae26` (main, Merge #926) · Engine-Pin `043579bb` (XMage 1.4.62)
Messung: Muse (Mess-Lane). Diese Vorlage trifft keine Entscheidung und ändert keine Deckdatei.

## Zusammenfassung für Hans

Am Pin fehlen der Engine **31 Kartennamen in 13 Decks (33 Einträge)**; **182 von 195** Decks sind importierbar (eigene Nachmessung über den produktiven Importpfad, Deck für Deck identisch zur Doku-Tabelle in `docs/PRECON_VALIDATION.md`). In **4 Decks fehlt der Commander selbst** (2024_death_toll, 2024_family_matters, 2024_miracle_worker, 2026_multiverse_reforged) — dort gibt es nichts zu ersetzen, ohne ein anderes Deck zu bauen. Für die **29 Hauptdeck-Slots in 10 Decks** liegen je 3 geprüfte Ersatzkandidaten vor (Engine-Existenz per Import bewiesen, Commander-legal, in der Farbidentität, Singleton, Typ + Manawert nah am Original). Alle 30 Ersatz-Sätze (3 je Deck) importieren mit Status OK.

### Optionenvergleich (nur Fakten)

| Option | Ergebnis in Zahlen | Was sie belegt | Was sie nicht belegt | Aufwand (grob, ohne Zusage) |
|---|---|---|---|---|
| **A) 13 Decks bleiben draußen** | Pool bleibt bei **182 Decks** (Ist-Zustand) | Nichts Neues; die 182 sind spielbar gemessen (M1-Sweeps) | Keine Aussage zu den 13 Decks | 0 h |
| **B) Hauptdeck-Slots in Deckkopien ersetzen** | **9 weitere Decks werden vollständig** (Pool 191); 29 Slots ersetzt; Deckgleichheit je Deck 92–99 % (Tabelle unten). 2026_multiverse_reforged bleibt ohne Commander-Entscheid unvollständig | Import aller 30 Sätze OK (gemessen). Die Kopien sind spielbar im selben Sinn wie die 182 | Die Kopien sind **nicht mehr die gedruckten Precons**; Ersatzkarten sind nur importbewiesen, ihre Funktion im Spiel ist nicht eigens geprüft | Sätze liegen fertig vor; Übernahme in Kopien + Nachimport ≈ 1–2 h Datenarbeit. Eine dauerhafte Repo-Änderung wäre ein eigener PR mit eigener Entscheidung |
| **C) Ersatzkarten im Fork (SYNTHETIC-Stubs)** | **Alle 13 Decks** würden importierbar (31 Stubs liegen aus der alten Linie vor) | Nur der Import: Die Stubs beweisen Existenz, **keine Kartenfunktion** — Fähigkeiten sind teilweise weggelassen (je Karte unten vermerkt) | Keine Regelevidenz für die 31 Karten. Risiko-Präzedenz: Die 6 vereinfachten Turbulent-Lands der alten Linie **veränderten die Spielsemantik** (Bisektion 2026-10-20) | Stub-Port ≈ 4–8 h, dazu Fork-Push (nur mit deinem Go) und Requalifizierung durch die Claude-Lane (PB-03 → Seal) — der eigentliche Kostenblock, historisch Tage |

**Eckdaten-Zuverlässigkeit der Stubs (für Option C):** Alle 31 Stubs treffen Manakosten, Haupttypen, P/T und Karten-pro-Datei exakt (31× „ja", gegen Scryfall geprüft). Ihre Schwäche ist nicht die Eckdaten, sondern die weggelassenen Fähigkeiten.

### Commander-Decks (4) — kein Slot-Austausch

Fehlt der Commander, ist das Deck ein anderes Deck. Optionen: **Deck weglassen** oder **du wählst einen Commander** (dann ist es ein neues Deck, kein Precon mehr). Betroffen: 2024_death_toll (Winter, Cynical Opportunist), 2024_family_matters (Zinnia, Valley's Voice), 2024_miracle_worker (Aminatou, Veil Piercer), 2026_multiverse_reforged (Jace, Multiverse Architect; dort zusätzlich 6 Hauptdeck-Slots, deren Ersatz oben bewiesen ist — mit Gerüst-Commander Breya, nur als Importgerüst, nicht als Vorschlag).

### Korrekturen zu früheren Angaben

- **Dack Fayden, Helping Hand** ist **eine** Karte und **ein** Stub (FRC, {4}{W}{W}, 4/6) — die Formulierung „eine Datei für zwei Karten" trifft nicht zu; Stub und Karte decken sich.
- **Aminatou, Veil Piercer:** Der Stub ist korrekt — die echte Karte ist laut Scryfall (Set DSC, Abruf 2026-10-20) eine **Legendary Creature — Human Wizard** ({1}{W}{U}{B}, 2/4), kein Planeswalker. Weggelassen ist im Stub nur die Miracle-Gewährung. (Meine frühere gegenteilige Angabe war falsch.)
- **Repo-Kartenwissen:** Entgegen der Stichprobe im Auftrag kommen **alle 31** Namen in `data/cards/*.json` nicht vor (0 von 31, strukturiert + Rohtext geprüft). Eckdaten stammen daher nur aus den Stubs (SYNTHETIC) und Scryfall (EXTERNAL_DATA).

### Meine Einschätzung (als solche markiert, ≤5 Zeilen)

Option B ist die einzige, die den Pool ehrlich vergrößert: 191 echte, importbewiesene Decks, klar als Kopien gekennzeichnet. Option C kauft 4 weitere Decks mit unbeweisbarer Kartenfunktion und dem Turbulent-Risiko — den Preis (Fork + Requalifizierung) halte ich dafür für zu hoch. Für die 4 Commander-Decks: draußen lassen, bis du einen Commander wählst oder die Karten regulär in die Engine kommen.

---

## Slot-Tabelle (33 Einträge)

| Deck | Karte | Zone | Anzahl | Anteil am Deck |
|---|---|---|---|---|
| 2023_blast_from_the_past | Susan Foreman | mainboard | 1 | 1% |
| 2023_masters_of_evil | Missy | mainboard | 1 | 1% |
| 2023_masters_of_evil | Cyber Conversion | mainboard | 1 | 1% |
| 2023_masters_of_evil | Doomsday Confluence | mainboard | 1 | 1% |
| 2023_masters_of_evil | Death in Heaven | mainboard | 1 | 1% |
| 2023_masters_of_evil | Rassilon, the War President | mainboard | 1 | 1% |
| 2023_masters_of_evil | The Cyber-Controller | mainboard | 1 | 1% |
| 2023_masters_of_evil | Cybership | mainboard | 1 | 1% |
| 2023_masters_of_evil | Don't Blink | mainboard | 1 | 1% |
| 2023_paradox_power | The Foretold Soldier | mainboard | 1 | 1% |
| 2023_paradox_power | River Song's Diary | mainboard | 1 | 1% |
| 2023_paradox_power | Psychic Paper | mainboard | 1 | 1% |
| 2023_timey_wimey | The Pandorica | mainboard | 1 | 1% |
| 2023_timey_wimey | The War Doctor | mainboard | 1 | 1% |
| 2023_timey_wimey | The Moment | mainboard | 1 | 1% |
| 2023_timey_wimey | Psychic Paper | mainboard | 1 | 1% |
| 2024_blame_game | Feather, Radiant Arbiter | mainboard | 1 | 1% |
| 2024_blame_game | Immortal Obligation | mainboard | 1 | 1% |
| 2024_death_toll | Winter, Cynical Opportunist | commander | 1 | 1% |
| 2024_family_matters | Zinnia, Valley's Voice | commander | 1 | 1% |
| 2024_miracle_worker | Aminatou, Veil Piercer | commander | 1 | 1% |
| 2024_revenant_recon | Eye of Duskmantle | mainboard | 1 | 1% |
| 2024_tricky_terrain | Desert Warfare | mainboard | 1 | 1% |
| 2024_tricky_terrain_collector_s_edition | Desert Warfare | mainboard | 1 | 1% |
| 2026_multiverse_reforged | Dack Fayden, Helping Hand | mainboard | 1 | 1% |
| 2026_multiverse_reforged | Teferi's Reproach | mainboard | 1 | 1% |
| 2026_multiverse_reforged | Jhoira, Weatherlight Corsair | mainboard | 1 | 1% |
| 2026_multiverse_reforged | Venser, Fervent Forger | mainboard | 1 | 1% |
| 2026_multiverse_reforged | Tamiyo, Upriser Crowned | mainboard | 1 | 1% |
| 2026_multiverse_reforged | The Ur-Sphinx | mainboard | 1 | 1% |
| 2026_multiverse_reforged | Jace, Multiverse Architect | commander | 1 | 1% |
| 2026_odds_and_ends | Exchange of Words | mainboard | 1 | 1% |
| 2026_odds_and_ends | Space Beleren | mainboard | 1 | 1% |

Quelle: `slots.json` — Messung `measure_precon_imports.py --enumerate-missing` (LOCAL_OBSERVED), Mengen aus den Deckdateien.

## Eckdaten je Karte (31)

Jeder Wert mit Quelle: Scryfall = EXTERNAL_DATA (Abruf 2026-10-20, URL je Karte in `eckdaten.json`); Stub = SYNTHETIC (Fork-Patches, `handover/2026-10-19/fork-patches/`). Repo-Kartenwissen: für alle 31 = nicht vorhanden.

### Aminatou, Veil Piercer
- **Manakosten:** {1}{W}{U}{B} (Scryfall) · Stub: {1}{W}{U}{B}
- **Typ:** Legendary Creature — Human Wizard (Scryfall) · Stub-Typen: Creature
- **P/T:** 2/4 (Scryfall) · Stub: 2/4
- **Keywords:** Surveil (Scryfall)
- **Oracle-Text:** At the beginning of your upkeep, surveil 2. (Look at the top two cards of your library, then put any number of them into your graveyard and the rest on top of your library in any order.)
Each enchantment card in your hand has miracle. Its miracle cost is equal to its mana cost reduced by {4}. (You may cast a card for its miracle cost when you draw it if it's the first card you drew this turn.) (Scryfall)
- **Set:** dsc (Duskmourn: House of Horror Commander, 2024-09-27) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** new BeginningOfUpkeepTriggeredAbility(                 TargetController.YOU, new SurveilEffect(2), false)

### Cyber Conversion
- **Manakosten:** {U}{U} (Scryfall) · Stub: {U}{U}
- **Typ:** Instant (Scryfall) · Stub-Typen: Instant
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Turn target creature face down. It's a 2/2 Cyberman artifact creature. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Cybership
- **Manakosten:** {6} (Scryfall) · Stub: {6}
- **Typ:** Artifact — Vehicle (Scryfall) · Stub-Typen: Artifact
- **P/T:** 8/8 (Scryfall) · Stub: 8/8
- **Keywords:** Flying, Crew (Scryfall)
- **Oracle-Text:** Flying
Whenever this Vehicle deals combat damage to a player, put the top two cards of that player's library onto the battlefield face down under your control. They're 2/2 Cyberman artifact creatures.
Crew 4 (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Dack Fayden, Helping Hand
- **Manakosten:** {4}{W}{W} (Scryfall) · Stub: {4}{W}{W}
- **Typ:** Legendary Creature — Human Advisor (Scryfall) · Stub-Typen: Creature
- **P/T:** 4/6 (Scryfall) · Stub: 4/6
- **Keywords:** — (Scryfall)
- **Oracle-Text:** When Dack Fayden enters, reveal cards from the top of your library until you reveal X creature cards, where X is the number of opponents you have. Put those creature cards onto the battlefield, then shuffle. They're goaded for the rest of the game. For each of those permanents, choose a different opponent. Each opponent gains control of the permanent for which they were chosen. (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Death in Heaven
- **Manakosten:** {3}{B} (Scryfall) · Stub: {3}{B}
- **Typ:** Enchantment — Saga (Scryfall) · Stub-Typen: Enchantment
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** Mill (Scryfall)
- **Oracle-Text:** (As this Saga enters and after your draw step, add a lore counter. Sacrifice after III.)
I, II — Target player mills two cards, then exiles their graveyard.
III — Put all creature cards exiled with this enchantment onto the battlefield face down under your control. They're 2/2 Cyberman artifact creatures. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Desert Warfare
- **Manakosten:** {3}{G} (Scryfall) · Stub: {3}{G}
- **Typ:** Enchantment (Scryfall) · Stub-Typen: Enchantment
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Whenever you sacrifice a Desert and whenever a Desert card is put into your graveyard from your hand or library, put that card onto the battlefield under your control at the beginning of your next end step.
At the beginning of combat on your turn, if you control five or more Deserts, create that many 1/1 red, green, and white Sand Warrior creature tokens. They gain haste. (Scryfall)
- **Set:** m3c (Modern Horizons 3 Commander, 2024-06-14) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** new SacrificePermanentTriggeredAbility(                 new DrawCardSourceControllerEffect(1), filter)

### Don't Blink
- **Manakosten:** {1}{U} (Scryfall) · Stub: {1}{U}
- **Typ:** Instant (Scryfall) · Stub-Typen: Instant
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** Cycling (Scryfall)
- **Oracle-Text:** Until end of turn, if one or more creatures would enter from exile or after being cast from exile, their owners shuffle them into their libraries instead.
Cycling {2} ({2}, Discard this card: Draw a card.) (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Doomsday Confluence
- **Manakosten:** {X}{X}{B} (Scryfall) · Stub: {X}{X}{B}
- **Typ:** Sorcery (Scryfall) · Stub-Typen: Sorcery
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Choose X. You may choose the same mode more than once.
• Each player sacrifices a nonartifact creature of their choice.
• Create a 3/3 black Dalek artifact creature token with menace.
• Each opponent discards a card. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Exchange of Words
- **Manakosten:** {1}{U}{U} (Scryfall) · Stub: {1}{U}{U}
- **Typ:** Enchantment (Scryfall) · Stub-Typen: Enchantment
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** When this enchantment enters, choose two target creatures. For as long as this enchantment remains on the battlefield, exchange the text boxes of those creatures. (Scryfall)
- **Set:** unf (Unfinity, 2022-10-07) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** new EntersBattlefieldTriggeredAbility(                 new DrawCardSourceControllerEffect(1))

### Eye of Duskmantle
- **Manakosten:** {5}{B}{B} (Scryfall) · Stub: {5}{B}{B}
- **Typ:** Creature — Eye (Scryfall) · Stub-Typen: Creature
- **P/T:** 3/8 (Scryfall) · Stub: 3/8
- **Keywords:** Flying, Lifelink (Scryfall)
- **Oracle-Text:** Flying, lifelink
You may play lands and cast spells from among cards in your graveyard you've surveilled this turn. If you cast a spell this way, you pay life equal to its mana value rather than paying its mana cost. (Scryfall)
- **Set:** mkc (Murders at Karlov Manor Commander, 2024-02-09) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** FlyingAbility.getInstance(); LifelinkAbility.getInstance()

### Feather, Radiant Arbiter
- **Manakosten:** {R}{W}{W} (Scryfall) · Stub: {R}{W}{W}
- **Typ:** Legendary Creature — Angel (Scryfall) · Stub-Typen: Creature
- **P/T:** 4/3 (Scryfall) · Stub: 4/3
- **Keywords:** Flying, Lifelink (Scryfall)
- **Oracle-Text:** Flying, lifelink
Whenever you cast a noncreature spell that targets only Feather, you may choose any number of other creatures that spell could target and pay {2} for each of those creatures. If you do, for each of those creatures, copy that spell. The copy targets that creature. (Copies of permanent spells become tokens.) (Scryfall)
- **Set:** mkc (Murders at Karlov Manor Commander, 2024-02-09) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** FlyingAbility.getInstance(); LifelinkAbility.getInstance()

### Immortal Obligation
- **Manakosten:** {1}{W} (Scryfall) · Stub: {1}{W}
- **Typ:** Instant (Scryfall) · Stub-Typen: Instant
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** Goad (Scryfall)
- **Oracle-Text:** Return target creature card from an opponent's graveyard to the battlefield under their control with a duty counter on it. For as long as that creature has a duty counter on it, it is goaded, can't attack you or a permanent you control, and can't block creatures you control. (Scryfall)
- **Set:** mkc (Murders at Karlov Manor Commander, 2024-02-09) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Jace, Multiverse Architect
- **Manakosten:** {1}{W}{U}{B}{R} (Scryfall) · Stub: {1}{W}{U}{B}{R}
- **Typ:** Legendary Planeswalker — Jace (Scryfall) · Stub-Typen: Planeswalker
- **P/T:** Loyalty 4 (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** At the beginning of combat on each opponent's turn, they may pay {2}. If they don't, creatures they control can't attack Jaces you control this turn.
+1: Draw two cards, then put a card from your hand on the bottom of your library.
−3: Exile another target planeswalker or creature you control. Reveal cards from the top of your library until you reveal a creature or planeswalker card. Put that card onto the battlefield and the rest on the bottom of your library in a random order.
Jace, Multiverse Architect can be your commander. (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** CanBeYourCommanderAbility.getInstance()

### Jhoira, Weatherlight Corsair
- **Manakosten:** {4}{B}{B} (Scryfall) · Stub: {4}{B}{B}
- **Typ:** Legendary Creature — Human Pirate (Scryfall) · Stub-Typen: Creature
- **P/T:** 4/5 (Scryfall) · Stub: 4/5
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Whenever Jhoira enters or attacks, target opponent reveals cards from the top of their library until they reveal a historic permanent card. You put that card onto the battlefield under your control and lose life equal to that permanent's mana value. That player puts the rest of the revealed cards on the bottom of their library in a random order. (Artifacts, legendaries, and Sagas are historic.) (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Missy
- **Manakosten:** {3}{U}{B}{R} (Scryfall) · Stub: {3}{U}{B}{R}
- **Typ:** Legendary Creature — Time Lord Rogue (Scryfall) · Stub-Typen: Creature
- **P/T:** 4/5 (Scryfall) · Stub: 4/5
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Whenever another nonartifact creature dies, return it to the battlefield under your control face down and tapped. It's a 2/2 Cyberman artifact creature.
At the beginning of your end step, each opponent faces a villainous choice — Each artifact creature you control deals 1 damage to that opponent, or you draw a card and chaos ensues. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** new DiesCreatureTriggeredAbility(new GainLifeEffect(1), false, filter)

### Psychic Paper
- **Manakosten:** {2} (Scryfall) · Stub: {2}
- **Typ:** Artifact — Equipment (Scryfall) · Stub-Typen: Artifact
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** Equip (Scryfall)
- **Oracle-Text:** As this Equipment becomes attached to a creature, choose a creature card name and a creature type.
Equipped creature has ward {1}, it can't be blocked, and its name and creature type are the last chosen name and creature type.
Equip {2} (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Rassilon, the War President
- **Manakosten:** {3}{U}{B} (Scryfall) · Stub: {3}{U}{B}
- **Typ:** Legendary Creature — Time Lord Noble (Scryfall) · Stub-Typen: Creature
- **P/T:** 3/4 (Scryfall) · Stub: 3/4
- **Keywords:** — (Scryfall)
- **Oracle-Text:** At the beginning of your upkeep, you lose 2 life and exile the top card of your library. You may play that card for as long as it remains exiled.
Each noncreature spell you cast from exile has conspire. (As you cast that spell, you may tap two untapped creatures you control that share a color with it. When you do, copy it and you may choose new targets for the copy.) (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### River Song's Diary
- **Manakosten:** {3} (Scryfall) · Stub: {3}
- **Typ:** Artifact — Book (Scryfall) · Stub-Typen: Artifact
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** Imprint (Scryfall)
- **Oracle-Text:** Imprint — Whenever a player casts an instant or sorcery spell from their hand, exile it instead of putting it into a graveyard as it resolves.
At the beginning of your upkeep, if there are four or more cards exiled with this artifact, choose one of them at random. You may cast it without paying its mana cost. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Space Beleren
- **Manakosten:** {2}{W}{U} (Scryfall) · Stub: {2}{W}{U}
- **Typ:** Legendary Planeswalker — Jace (Scryfall) · Stub-Typen: Planeswalker
- **P/T:** Loyalty 3 (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Space sculptor (Space Beleren divides the battlefield into alpha, beta, and gamma sectors. If a creature isn't assigned to a sector, its controller assigns it to one. Opponents assign first.)
+1: Creatures in each sector can be blocked this turn only by creatures in the same sector.
−1: Put a +1/+1 counter on each creature in the sector of your choice.
−5: Destroy all creatures in the sector of your choice. (Scryfall)
- **Set:** unf (Unfinity, 2022-10-07) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** ability1; ability2; ability3

### Susan Foreman
- **Manakosten:** {1}{G} (Scryfall) · Stub: {1}{G}
- **Typ:** Legendary Creature — Time Lord (Scryfall) · Stub-Typen: Creature
- **P/T:** 1/1 (Scryfall) · Stub: 1/1
- **Keywords:** Doctor's companion (Scryfall)
- **Oracle-Text:** If you would planeswalk, instead look at the top two cards of your planar deck, put one on the bottom of your planar deck and the other on top, then planeswalk.
{T}: Add {G}.
Doctor's companion (You can have two commanders if the other is the Doctor.) (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** new GreenManaAbility()

### Tamiyo, Upriser Crowned
- **Manakosten:** {4}{R}{W} (Scryfall) · Stub: {4}{R}{W}
- **Typ:** Legendary Creature — Moonfolk Warrior (Scryfall) · Stub-Typen: Creature
- **P/T:** 3/5 (Scryfall) · Stub: 3/5
- **Keywords:** Flying, Haste, Double strike (Scryfall)
- **Oracle-Text:** Flying, double strike, haste
When Tamiyo enters, you become the monarch.
Whenever one or more creatures deal combat damage to you while you're the monarch, tap those creatures and put a stun counter on each of them. (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Teferi's Reproach
- **Manakosten:** {2}{W} (Scryfall) · Stub: {2}{W}
- **Typ:** Instant (Scryfall) · Stub-Typen: Instant
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Choose target opponent. Until that player's next turn, they gain protection from everything and their life total can't change. All nonland permanents they control phase out. (While they're phased out, they're treated as though they don't exist. They phase in before that player untaps during their next untap step.)
Exile Teferi's Reproach. (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### The Cyber-Controller
- **Manakosten:** {X}{U}{U}{B} (Scryfall) · Stub: {X}{U}{U}{B}
- **Typ:** Legendary Artifact Creature — Cyberman (Scryfall) · Stub-Typen: Artifact, Creature
- **P/T:** 3/3 (Scryfall) · Stub: 3/3
- **Keywords:** Mill (Scryfall)
- **Oracle-Text:** When The Cyber-Controller enters, each opponent mills X cards. Put all creature cards milled this way onto the battlefield face down under your control. They're 2/2 Cyberman artifact creatures.
Other artifact creatures you control get +1/+1. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### The Foretold Soldier
- **Manakosten:** {2}{G}{G} (Scryfall) · Stub: {2}{G}{G}
- **Typ:** Creature — Alien Zombie Soldier (Scryfall) · Stub-Typen: Creature
- **P/T:** 6/6 (Scryfall) · Stub: 6/6
- **Keywords:** Foretell (Scryfall)
- **Oracle-Text:** This creature must be blocked if able.
This creature can't be blocked by more than one creature.
Whenever this creature deals damage, exile it face down. It becomes foretold.
Foretell {1}{G} (During your turn, you may pay {2} and exile this card from your hand face down. Cast it on a later turn for its foretell cost.) (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### The Moment
- **Manakosten:** {2} (Scryfall) · Stub: {2}
- **Typ:** Legendary Artifact (Scryfall) · Stub-Typen: Artifact
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** At the beginning of your upkeep, put a time counter on The Moment.
{2}, {T}: Untap target creature you control. It phases out until The Moment leaves the battlefield.
{3}, {T}: Destroy each nonland permanent with mana value less than or equal to the number of time counters on The Moment. Then sacrifice The Moment. Activate only as a sorcery. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### The Pandorica
- **Manakosten:** {2}{W} (Scryfall) · Stub: {2}{W}
- **Typ:** Legendary Artifact (Scryfall) · Stub-Typen: Artifact
- **P/T:** — (Scryfall) · Stub: —
- **Keywords:** — (Scryfall)
- **Oracle-Text:** You may choose not to untap The Pandorica during your untap step.
{1}{W}, {T}: Untap another target nonland permanent, then it phases out. It can't phase in for as long as The Pandorica remains tapped. When The Pandorica becomes untapped or leaves the battlefield, that permanent phases in. Activate only as a sorcery. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** ability

### The Ur-Sphinx
- **Manakosten:** {6}{W}{U}{B} (Scryfall) · Stub: {6}{W}{U}{B}
- **Typ:** Legendary Creature — Sphinx Avatar (Scryfall) · Stub-Typen: Creature
- **P/T:** 10/10 (Scryfall) · Stub: 10/10
- **Keywords:** Flying, Eminence, Mill (Scryfall)
- **Oracle-Text:** Eminence — As long as The Ur-Sphinx is in the command zone or on the battlefield, other Sphinx spells you cast cost {1} less to cast.
Flying
Whenever one or more Sphinxes you control attack, each player mills that many cards. For each player, you may cast a card that player milled this way without paying its mana cost. (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** FlyingAbility.getInstance()

### The War Doctor
- **Manakosten:** {2}{R}{W} (Scryfall) · Stub: {2}{R}{W}
- **Typ:** Legendary Creature — Time Lord Doctor (Scryfall) · Stub-Typen: Creature
- **P/T:** 3/5 (Scryfall) · Stub: 3/5
- **Keywords:** — (Scryfall)
- **Oracle-Text:** Whenever one or more other permanents phase out and whenever one or more other cards are put into exile from anywhere, put a time counter on The War Doctor.
Whenever The War Doctor attacks, it deals damage equal to the number of time counters on it to any target. If a creature dealt damage this way would die this turn, exile it instead. (Scryfall)
- **Set:** who (Doctor Who, 2023-10-13) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** ability

### Venser, Fervent Forger
- **Manakosten:** {4}{R}{R} (Scryfall) · Stub: {4}{R}{R}
- **Typ:** Legendary Creature — Human Sorcerer (Scryfall) · Stub-Typen: Creature
- **P/T:** 5/3 (Scryfall) · Stub: 5/3
- **Keywords:** Flash (Scryfall)
- **Oracle-Text:** Flash
When Venser enters, choose one —
• Copy target instant or sorcery spell an opponent controls twice. You may choose new targets for the copies.
• Create two tokens that are copies of target permanent an opponent controls. They gain haste. At the beginning of the next end step, sacrifice them. (Scryfall)
- **Set:** frc (Reality Fracture Commander, 2026-10-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** keine (nur Basiswerte)

### Winter, Cynical Opportunist
- **Manakosten:** {2}{B}{G} (Scryfall) · Stub: {2}{B}{G}
- **Typ:** Legendary Creature — Human Warlock (Scryfall) · Stub-Typen: Creature
- **P/T:** 2/5 (Scryfall) · Stub: 2/5
- **Keywords:** Deathtouch, Delirium, Mill (Scryfall)
- **Oracle-Text:** Deathtouch
Whenever Winter attacks, mill three cards.
Delirium — At the beginning of your end step, you may exile any number of cards from your graveyard with four or more card types among them. If you do, put a permanent card from among them onto the battlefield with a finality counter on it. (Scryfall)
- **Set:** dsc (Duskmourn: House of Horror Commander, 2024-09-27) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** DeathtouchAbility.getInstance(); new AttacksTriggeredAbility(new MillCardsControllerEffect(3), false)

### Zinnia, Valley's Voice
- **Manakosten:** {U}{R}{W} (Scryfall) · Stub: {U}{R}{W}
- **Typ:** Legendary Creature — Bird Bard (Scryfall) · Stub-Typen: Creature
- **P/T:** 1/3 (Scryfall) · Stub: 1/3
- **Keywords:** Flying (Scryfall)
- **Oracle-Text:** Flying
Zinnia gets +X/+0, where X is the number of other creatures you control with base power 1.
Creature spells you cast gain offspring {2} as you cast them. (You may pay an additional {2} as you cast a creature spell. If you do, when that creature enters, create a 1/1 token copy of it.) (Scryfall)
- **Set:** blc (Bloomburrow Commander, 2024-08-02) (Scryfall)
- **Stub verlässlich (Eckdaten):** ja · **Stub-Fähigkeiten (Auszug):** FlyingAbility.getInstance()

## Ersatzkandidaten je Hauptdeck-Slot (29)

Prüfung je Kandidat: (a) Engine-Existenz per Import des Satzes bewiesen (Status OK, `import_nachweis/`), (b) Commander-Legalität und (c) Farbidentität per Scryfall (EXTERNAL_DATA, Abruf 2026-10-20), (d) nicht bereits im Deck (Singleton, aus den Deckdateien), (e) Typ + Manawert nah am Original; Rolle mechanisch per Stichwort-Abgleich, sonst „Rolle UNKNOWN". Häufigkeit = Zahl der Precons (von 195), die die Karte spielen.

### 2023_blast_from_the_past — Susan Foreman (Legendary Creature — Time Lord, MV 2, Farbidentität des Decks: G, U)
- **1. Sakura-Tribe Elder** — MV 2 (Diff 0), Creature — Snake Shaman, CI G, legal: legal, Precon-Häufigkeit 21, Stichwort-Ueberlappung: ramp · Importnachweis: Satz 1 (OK)
- **2. Satyr Wayfinder** — MV 2 (Diff 0), Creature — Satyr, CI G, legal: legal, Precon-Häufigkeit 10, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Etherium Sculptor** — MV 2 (Diff 0), Artifact Creature — Vedalken Artificer, CI U, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Missy (Legendary Creature — Time Lord Rogue, MV 6, Farbidentität des Decks: B, R, U)
- **1. Steel Hellkite** — MV 6 (Diff 0), Artifact Creature — Dragon, CI farblos, legal: legal, Precon-Häufigkeit 13, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Inferno Titan** — MV 6 (Diff 0), Creature — Giant, CI R, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Brudiclad, Telchor Engineer** — MV 6 (Diff 0), Legendary Artifact Creature — Phyrexian Artificer, CI R, U, legal: legal, Precon-Häufigkeit 5, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Cyber Conversion (Instant, MV 2, Farbidentität des Decks: B, R, U)
- **1. Arcane Denial** — MV 2 (Diff 0), Instant, CI U, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Terminate** — MV 2 (Diff 0), Instant, CI B, R, legal: legal, Precon-Häufigkeit 14, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Reality Shift** — MV 2 (Diff 0), Instant, CI U, legal: legal, Precon-Häufigkeit 10, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Doomsday Confluence (Sorcery, MV 1, Farbidentität des Decks: B, R, U)
- **1. Faithless Looting** — MV 1 (Diff 0), Sorcery, CI R, legal: legal, Precon-Häufigkeit 15, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Vandalblast** — MV 1 (Diff 0), Sorcery, CI R, legal: legal, Precon-Häufigkeit 11, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Preordain** — MV 1 (Diff 0), Sorcery, CI U, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Death in Heaven (Enchantment — Saga, MV 4, Farbidentität des Decks: B, R, U)
- **1. Kang Dynasty** — MV 4 (Diff 0), Enchantment — Saga, CI U, legal: legal, Precon-Häufigkeit 2, Stichwort-Ueberlappung: sacrifice-outlet · Importnachweis: Satz 1 (OK)
- **2. Age of Ultron** — MV 5 (Diff 1), Enchantment — Saga, CI B, legal: legal, Precon-Häufigkeit 2, Stichwort-Ueberlappung: sacrifice-outlet · Importnachweis: Satz 2 (OK)
- **3. In the Darkness Bind Them** — MV 5 (Diff 1), Enchantment — Saga, CI B, R, U, legal: legal, Precon-Häufigkeit 1, Stichwort-Ueberlappung: sacrifice-outlet · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Rassilon, the War President (Legendary Creature — Time Lord Noble, MV 5, Farbidentität des Decks: B, R, U)
- **1. Mulldrifter** — MV 5 (Diff 0), Creature — Elemental, CI U, legal: legal, Precon-Häufigkeit 11, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Psychosis Crawler** — MV 5 (Diff 0), Artifact Creature — Phyrexian Horror, CI farblos, legal: legal, Precon-Häufigkeit 9, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Shriekmaw** — MV 5 (Diff 0), Creature — Elemental, CI B, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — The Cyber-Controller (Legendary Artifact Creature — Cyberman, MV 3, Farbidentität des Decks: B, R, U)
- **1. Burnished Hart** — MV 3 (Diff 0), Artifact Creature — Elk, CI farblos, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Pilgrim's Eye** — MV 3 (Diff 0), Artifact Creature — Thopter, CI farblos, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Academy Manufactor** — MV 3 (Diff 0), Artifact Creature — Assembly-Worker, CI farblos, legal: legal, Precon-Häufigkeit 4, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Cybership (Artifact — Vehicle, MV 6, Farbidentität des Decks: B, R, U)
- **1. N'Yami-Class Mother Ship** — MV 6 (Diff 0), Artifact — Vehicle, CI farblos, legal: legal, Precon-Häufigkeit 2, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Avengers Quinjet** — MV 5 (Diff 1), Artifact — Vehicle, CI farblos, legal: legal, Precon-Häufigkeit 2, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Damocles Base, Sword of Kang** — MV 5 (Diff 1), Legendary Artifact — Vehicle, CI B, legal: legal, Precon-Häufigkeit 2, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_masters_of_evil — Don't Blink (Instant, MV 2, Farbidentität des Decks: B, R, U)
- **1. Arcane Denial** — MV 2 (Diff 0), Instant, CI U, legal: legal, Precon-Häufigkeit 16, Stichwort-Ueberlappung: draw · Importnachweis: Satz — (OK)
- **2. Terminate** — MV 2 (Diff 0), Instant, CI B, R, legal: legal, Precon-Häufigkeit 14, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **3. Reality Shift** — MV 2 (Diff 0), Instant, CI U, legal: legal, Precon-Häufigkeit 10, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)

### 2023_paradox_power — The Foretold Soldier (Creature — Alien Zombie Soldier, MV 4, Farbidentität des Decks: G, U)
- **1. Solemn Simulacrum** — MV 4 (Diff 0), Artifact Creature — Golem, CI farblos, legal: legal, Precon-Häufigkeit 34, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Whirler Rogue** — MV 4 (Diff 0), Creature — Human Rogue Artificer, CI U, legal: legal, Precon-Häufigkeit 12, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Archmage Emeritus** — MV 4 (Diff 0), Creature — Human Wizard, CI U, legal: legal, Precon-Häufigkeit 5, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_paradox_power — River Song's Diary (Artifact — Book, MV 3, Farbidentität des Decks: G, U)
- **1. Commander's Sphere** — MV 3 (Diff 0), Artifact, CI farblos, legal: legal, Precon-Häufigkeit 76, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Burnished Hart** — MV 3 (Diff 0), Artifact Creature — Elk, CI farblos, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Chromatic Lantern** — MV 3 (Diff 0), Artifact, CI farblos, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_paradox_power — Psychic Paper (Artifact — Equipment, MV 2, Farbidentität des Decks: G, U)
- **1. Swiftfoot Boots** — MV 2 (Diff 0), Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 44, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Lightning Greaves** — MV 2 (Diff 0), Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 39, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Hero's Blade** — MV 2 (Diff 0), Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_timey_wimey — The Pandorica (Legendary Artifact, MV 3, Farbidentität des Decks: R, U)
- **1. Commander's Sphere** — MV 3 (Diff 0), Artifact, CI farblos, legal: legal, Precon-Häufigkeit 76, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Burnished Hart** — MV 3 (Diff 0), Artifact Creature — Elk, CI farblos, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Chromatic Lantern** — MV 3 (Diff 0), Artifact, CI farblos, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_timey_wimey — The War Doctor (Legendary Creature — Time Lord Doctor, MV 4, Farbidentität des Decks: R, U)
- **1. Solemn Simulacrum** — MV 4 (Diff 0), Artifact Creature — Golem, CI farblos, legal: legal, Precon-Häufigkeit 34, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Whirler Rogue** — MV 4 (Diff 0), Creature — Human Rogue Artificer, CI U, legal: legal, Precon-Häufigkeit 12, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Anger** — MV 4 (Diff 0), Creature — Incarnation, CI R, legal: legal, Precon-Häufigkeit 10, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_timey_wimey — The Moment (Legendary Artifact, MV 2, Farbidentität des Decks: R, U)
- **1. Swiftfoot Boots** — MV 2 (Diff 0), Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 44, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Fellwar Stone** — MV 2 (Diff 0), Artifact, CI farblos, legal: legal, Precon-Häufigkeit 43, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Izzet Signet** — MV 2 (Diff 0), Artifact, CI R, U, legal: legal, Precon-Häufigkeit 15, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2023_timey_wimey — Psychic Paper (Artifact — Equipment, MV 2, Farbidentität des Decks: R, U)
- **1. Swiftfoot Boots** — MV 2 (Diff 0), Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 44, Rolle UNKNOWN · Importnachweis: Satz — (OK)
- **2. Hero's Blade** — MV 2 (Diff 0), Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Sword of the Animist** — MV 2 (Diff 0), Legendary Artifact — Equipment, CI farblos, legal: legal, Precon-Häufigkeit 7, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2024_blame_game — Feather, Radiant Arbiter (Legendary Creature — Angel, MV 3, Farbidentität des Decks: R, W)
- **1. Burnished Hart** — MV 3 (Diff 0), Artifact Creature — Elk, CI farblos, legal: legal, Precon-Häufigkeit 16, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Bastion Protector** — MV 3 (Diff 0), Creature — Human Soldier, CI W, legal: legal, Precon-Häufigkeit 9, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Pilgrim's Eye** — MV 3 (Diff 0), Artifact Creature — Thopter, CI farblos, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2024_blame_game — Immortal Obligation (Instant, MV 2, Farbidentität des Decks: R, W)
- **1. Abrade** — MV 2 (Diff 0), Instant, CI R, legal: legal, Precon-Häufigkeit 8, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Boros Charm** — MV 2 (Diff 0), Instant, CI R, W, legal: legal, Precon-Häufigkeit 7, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Valorous Stance** — MV 2 (Diff 0), Instant, CI W, legal: legal, Precon-Häufigkeit 7, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2024_revenant_recon — Eye of Duskmantle (Creature — Eye, MV 7, Farbidentität des Decks: B, U)
- **1. Meteor Golem** — MV 7 (Diff 0), Artifact Creature — Golem, CI farblos, legal: legal, Precon-Häufigkeit 13, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Butcher of Malakir** — MV 7 (Diff 0), Creature — Vampire Warrior, CI B, legal: legal, Precon-Häufigkeit 11, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Thought Monitor** — MV 7 (Diff 0), Artifact Creature — Construct, CI U, legal: legal, Precon-Häufigkeit 4, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2024_tricky_terrain — Desert Warfare (Enchantment, MV 4, Farbidentität des Decks: G, U)
- **1. Reconnaissance Mission** — MV 4 (Diff 0), Enchantment, CI U, legal: legal, Precon-Häufigkeit 7, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Path of Discovery** — MV 4 (Diff 0), Enchantment, CI G, legal: legal, Precon-Häufigkeit 5, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Greater Good** — MV 4 (Diff 0), Enchantment, CI G, legal: legal, Precon-Häufigkeit 4, Stichwort-Ueberlappung: sacrifice-outlet · Importnachweis: Satz 3 (OK)

### 2024_tricky_terrain_collector_s_edition — Desert Warfare (Enchantment, MV 4, Farbidentität des Decks: G, U)
- **1. Reconnaissance Mission** — MV 4 (Diff 0), Enchantment, CI U, legal: legal, Precon-Häufigkeit 7, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Path of Discovery** — MV 4 (Diff 0), Enchantment, CI G, legal: legal, Precon-Häufigkeit 5, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Greater Good** — MV 4 (Diff 0), Enchantment, CI G, legal: legal, Precon-Häufigkeit 4, Stichwort-Ueberlappung: sacrifice-outlet · Importnachweis: Satz 3 (OK)

### 2026_multiverse_reforged — Dack Fayden, Helping Hand (Legendary Creature — Human Advisor, MV 6, Farbidentität des Decks: B, R, U, W)
- **1. Sun Titan** — MV 6 (Diff 0), Creature — Giant, CI W, legal: legal, Precon-Häufigkeit 18, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Steel Hellkite** — MV 6 (Diff 0), Artifact Creature — Dragon, CI farblos, legal: legal, Precon-Häufigkeit 13, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Inferno Titan** — MV 6 (Diff 0), Creature — Giant, CI R, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2026_multiverse_reforged — Teferi's Reproach (Instant, MV 3, Farbidentität des Decks: B, R, U, W)
- **1. Chaos Warp** — MV 3 (Diff 0), Instant, CI R, legal: legal, Precon-Häufigkeit 33, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Mortify** — MV 3 (Diff 0), Instant, CI B, W, legal: legal, Precon-Häufigkeit 15, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Generous Gift** — MV 3 (Diff 0), Instant, CI W, legal: legal, Precon-Häufigkeit 12, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2026_multiverse_reforged — Jhoira, Weatherlight Corsair (Legendary Creature — Human Pirate, MV 6, Farbidentität des Decks: B, R, U, W)
- **1. Sun Titan** — MV 6 (Diff 0), Creature — Giant, CI W, legal: legal, Precon-Häufigkeit 18, Rolle UNKNOWN · Importnachweis: Satz — (OK)
- **2. Steel Hellkite** — MV 6 (Diff 0), Artifact Creature — Dragon, CI farblos, legal: legal, Precon-Häufigkeit 13, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **3. Inferno Titan** — MV 6 (Diff 0), Creature — Giant, CI R, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)

### 2026_multiverse_reforged — Venser, Fervent Forger (Legendary Creature — Human Sorcerer, MV 6, Farbidentität des Decks: B, R, U, W)
- **1. Sun Titan** — MV 6 (Diff 0), Creature — Giant, CI W, legal: legal, Precon-Häufigkeit 18, Rolle UNKNOWN · Importnachweis: Satz — (OK)
- **2. Steel Hellkite** — MV 6 (Diff 0), Artifact Creature — Dragon, CI farblos, legal: legal, Precon-Häufigkeit 13, Rolle UNKNOWN · Importnachweis: Satz — (OK)
- **3. Inferno Titan** — MV 6 (Diff 0), Creature — Giant, CI R, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)

### 2026_multiverse_reforged — Tamiyo, Upriser Crowned (Legendary Creature — Moonfolk Warrior, MV 6, Farbidentität des Decks: B, R, U, W)
- **1. Sun Titan** — MV 6 (Diff 0), Creature — Giant, CI W, legal: legal, Precon-Häufigkeit 18, Rolle UNKNOWN · Importnachweis: Satz — (OK)
- **2. Steel Hellkite** — MV 6 (Diff 0), Artifact Creature — Dragon, CI farblos, legal: legal, Precon-Häufigkeit 13, Rolle UNKNOWN · Importnachweis: Satz — (OK)
- **3. Inferno Titan** — MV 6 (Diff 0), Creature — Giant, CI R, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz — (OK)

### 2026_multiverse_reforged — The Ur-Sphinx (Legendary Creature — Sphinx Avatar, MV 9, Farbidentität des Decks: B, R, U, W)
- **1. Cavern-Hoard Dragon** — MV 9 (Diff 0), Creature — Dragon, CI R, legal: legal, Precon-Häufigkeit 1, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Zetalpa, Primal Dawn** — MV 8 (Diff 1), Legendary Creature — Elder Dinosaur, CI W, legal: legal, Precon-Häufigkeit 6, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Bogardan Hellkite** — MV 8 (Diff 1), Creature — Dragon, CI R, legal: legal, Precon-Häufigkeit 3, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2026_odds_and_ends — Exchange of Words (Enchantment, MV 3, Farbidentität des Decks: B, U, W)
- **1. Propaganda** — MV 3 (Diff 0), Enchantment, CI U, legal: legal, Precon-Häufigkeit 15, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Ghostly Prison** — MV 3 (Diff 0), Enchantment, CI W, legal: legal, Precon-Häufigkeit 9, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Bastion of Remembrance** — MV 3 (Diff 0), Enchantment, CI B, legal: legal, Precon-Häufigkeit 7, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

### 2026_odds_and_ends — Space Beleren (Legendary Planeswalker — Jace, MV 4, Farbidentität des Decks: B, U, W)
- **1. Tezzeret, Betrayer of Flesh** — MV 4 (Diff 0), Legendary Planeswalker — Tezzeret, CI U, legal: legal, Precon-Häufigkeit 1, Rolle UNKNOWN · Importnachweis: Satz 1 (OK)
- **2. Elspeth, Knight-Errant** — MV 4 (Diff 0), Legendary Planeswalker — Elspeth, CI W, legal: legal, Precon-Häufigkeit 0, Rolle UNKNOWN · Importnachweis: Satz 2 (OK)
- **3. Gideon Jura** — MV 5 (Diff 1), Legendary Planeswalker — Gideon, CI W, legal: legal, Precon-Häufigkeit 2, Rolle UNKNOWN · Importnachweis: Satz 3 (OK)

## Deckgleichheit unter Option B

| Deck | Ersetzte Slots | Gleichheit | Wird vollständig |
|---|---|---|---|
| 2023_blast_from_the_past | 1 | 99 % | ja |
| 2023_masters_of_evil | 8 | 92 % | ja |
| 2023_paradox_power | 3 | 97 % | ja |
| 2023_timey_wimey | 4 | 96 % | ja |
| 2024_blame_game | 2 | 98 % | ja |
| 2024_revenant_recon | 1 | 99 % | ja |
| 2024_tricky_terrain | 1 | 99 % | ja |
| 2024_tricky_terrain_collector_s_edition | 1 | 99 % | ja |
| 2026_multiverse_reforged | 6 | 94 % | nein (Commander fehlt) |
| 2026_odds_and_ends | 2 | 98 % | ja |

## Reproduzierbarkeit

- Kalibrierung: `python scripts/measure_precon_imports.py --jar <bridge.jar> --workdir <leer> --out imports.json --enumerate-missing` → 182 OK / 13 FAILED / 31 Namen / 33 Einträge.
- Auswahl, Satzbau, Eckdaten: Skripte in `skripte/` (select_candidates.py, build_proof_copies.py, build_eckdaten.py, build_slots.py, run_proofs.sh) — alle Eingaben sind die Messdateien dieser Abgabe plus Scryfall-Abrufe vom 2026-10-20.
- Importnachweise: je Satz eine JSON in `import_nachweis/` (Ergebniszeile des Decks, Status OK) plus Lauf-Log.
- Arbeitsbaum `wt-m1-sweep` @ `ed2fbae26`: keine versionierte Datei geändert (alle Kopien und Skripte liegen außerhalb des Repos); `git status` sauber bis auf Build-Artefakte in `engine-bridge/target/` (gitignored).
