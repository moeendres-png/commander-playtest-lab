# Bericht: Deck-Guides für alle gespielten Decks (2026-10-24)

Auftrag (Owner): Guides zu allen aktuell gespielten Decks, damit die
Piloten deckspezifisch besser entscheiden — Precon-Piloten mit Spielplan
je Deck, RogShai-Wissen ausbauen, Chulane neu erschließen. Ergebnis:
**206 Guide-Paare (JSON + Markdown)**, ein dokumentiertes Schema
(`FORMAT.md`), ein reproduzierbarer Generator und dieser Bericht.
Ablage: `~/workspace/stageDeckGuides/` (nicht gepusht — Prüfung durch Muse).

## 1. Vorgehen und Quellenlage (mit Korrekturen zum Auftrags-Stand)

- **Decklisten:** 195 Precon-Originale aus dem Haupt-Clone
  (`data/decks/precons/`), 9 Proxy-Decks aus `wt-978`
  (`data/decks/precon_variants/`), Fokus-Decks aus den M4-Arbeitskopien
  (`~/workspace/tmp/m4/{rogshai,chulane}.json`). Die Fokus-Listen wurden
  gegen die Owner-bestätigten Handover-Listen
  (`handover/2026-10-22/{rogshai,chulane}-deck/` auf `muse/claude-handover`)
  mengenverglichen: identisch. Die Coverage-Deckliste unter
  `data/coverage_decks/collection/` wurde **nicht** gelesen (Tabu) — sie
  ist ohnehin nicht Hans' Deck.
- **Zähl-Korrektur (wichtig):** Der Auftrag rechnete „186 + 9 synthetic +
  9 variants = 204". Die Grundwahrheit auf main
  (`data/decks/precon_synthetic_proxies.json`, Evidenzklasse SYNTHETIC)
  sagt: Pool = 195 Decks = **186 echt + 9 SYNTHETIC**, und die Proxy-
  Dateien *sind* die neun Dateien in `precon_variants/` (Proxy-Deck-ID
  `precon-synthetic/…`, Datei-Deck-ID `precon-variant/…`). Es gibt keine
  separaten 9 „Varianten" daneben. Geliefert werden daher **204
  Precon-Guides in der Zerlegung 186 REAL + 9 ORIGINAL_MIT_PROXY (die
  Originale, deren Karten die Engine nicht kennt) + 9 SYNTHETIC (die
  spielbaren Proxy-Decks, inkl. aller Ersetzungen)** plus die 2
  Fokus-Guides = **206**.
- **Kartenfakten:** Scryfall (Collection-API, Batches à 75, 0,15 s
  Abstand; Split-Karten per Front-Name nachgeladen) + Repo-Cache
  `pilot_card_knowledge.json` als erste Schicht. Abdeckung: **6.380
  einzigartige Karten, 0 ohne Fakten** (`scryfall_cache.json`,
  `tools/fetch_scryfall_cache.py`).
- **Rollen:** Bewusst **keine** neue Heuristik erfunden — der Generator
  importiert die Repo-eigene `card_roles()`/`permanent_value()` aus
  `commander_lab.agents.card_knowledge` (wt-m4-Lock `d48bbe5f2`), also
  exakt die Rollenwelt des `PilotStateView` (`role_counts`) und
  `PilotActionView` (`role_strengths`). Kuratierte Profile aus
  `structural_role_profiles.json` wirken wie im Repo vorrangig.
- **Andockpunkte:** Schema-Felder sind 1:1 auf die Pilot-Komponenten aus
  dem Pilot-Handoff (2026-10-24) abgebildet — Tabelle in `FORMAT.md` §4
  (Keep-Test §4.4, Bedrohungs-Leiter §4.2, Kampf §4.3, Sequenzierung
  §4.1, Aggregation/Gewichte §4.8, Pakete nach dem `specialist_bonus`-
  Muster der Spezialisten-Piloten).

## 2. Abdeckung und Belastbarkeit je Feld

| Feld | Quelle/Ableitung | Evidenz | Belastbarkeit |
|---|---|---|---|
| commander, farbidentitaet, partner | Deckliste + Scryfall | DIRECTLY_VERIFIED | voll (Gate: 206/206 gegen Deckdateien geprüft) |
| manabasis.laender_gesamt | Deckliste × Typzeilen | DIRECTLY_VERIFIED | voll (Stichprobe unabhängig nachgezählt) |
| laender_nach_farbe, pip_bedarf_frueh | Basisland-Typen + Add-Symbole; Repo-`pips()` | MODELED | Näherung: Fetch-/„any color"-Länder zählen für keine Einzelfarbe; keine Manabasis-Simulation |
| kurve | Scryfall-MV | DIRECTLY_VERIFIED (Fakten) | voll |
| rollen | Repo-`card_roles()` | CODE_DERIVED | so belastbar wie die Pilot-Heuristik selbst; bekannte Lücken s. §4 |
| commander_soll_zug | MV − Ramp-Beschleunigung (Formel) | MODELED | grobe Linie; bei den Fokus-Decks handgesetzt begründet |
| keep_test | Handoff §4.4 + RESEARCH A1 + Code-Konvention (−0,55/Mulligan) | MODELED / EXTERNALLY_RULE_VALIDATED (Struktur) | Fenster 2–4 literaturgestützt; Deck-Parameter modelliert, nicht gemessen |
| utility_deltas | Abbildungstabelle unten, pool-median-relativ, ±0,5 gedeckelt | MODELED | Hypothesen fürs Messprotokoll (Handoff §6), keine Wirkung behauptet |
| bedrohung.gegner_overrides | nur aus Deck-Eigenschaften (4 Regeln) | MODELED | bewusst grob; keine Einzelkarten-Interaktionen behauptet |
| sequenzierung | Handoff-§4.1-Defaults + Textsignale | MODELED | Defaults belastbar, Ausnahmen nur bei Oracle-Text-Signal |
| pakete (Precons) | Top-8 Engine/Finisher nach `permanent_value()` | CODE_DERIVED | Startpunkt; Synergie-Zentren kann der Board-Wert verfehlen (s. Stichprobe) |
| pakete (Fokus) | Registry/Enrichment + aktuelle Liste; Chulane handgebaut | CODE_DERIVED / MODELED | RogShai: auf aktuelle Liste verifiziert (Gate); Chulane: Erstentwurf |
| win_plan / Text-Guide | Bausteine aus Archetyp + Fakten | MODELED | keine erfundenen Effekte; nur Oracle-gestützte Aussagen |

**Utility-Delta-Abbildung (vollständig, aus `tools/generate_guides.py`):**
Engine-Anteil > 1,3× Pool-Median → `engine_development +0,3` (> 1,1× →
+0,15); Draw-Anteil > 1,3× Median → `card_advantage +0,25`;
(Counter+Protection)-Anteil > 1,4× Median → `interaction_reserve +0,3`;
(Removal+Wipe)-Anteil > 1,4× Median → `threat_reduction +0,2`,
`survival +0,1`; Recursion-Anteil > 1,4× Median → `rebuild_capacity +0,3`;
(Finisher+Payoff)-Anteil > 1,3× Median → `win_progress +0,2`;
billigster Commander MV ≤ 2 → `commander_value +0,25`, `tempo +0,15`;
Kurvenschnitt ≤ 2,6 → `tempo +0,2`, `mana_efficiency −0,1`;
Kurvenschnitt ≥ 3,4 → `card_advantage +0,1`, `tempo −0,15`.

**Archetypen-Verteilung (Primär-Tag):** go_wide 39, value_engine 22,
spellslinger 19, artifacts 18, tribal gesamt 62 (davon Human 13, Dragon 5,
Elf 4, Zombie 4, Hero 4, …), voltron 11, enchantments 7, lands 7,
graveyard 6, midrange_value 6, control 0 primär (2 sekundär) — plausibel
für den Precon-Pool (kaum reine Control-Decks ohne Kreatur-Plan).

## 3. Stichproben-Qualitätsprüfung (5 Precon-Guides, manuell + nachgerechnet)

Methode: Commander, Länderzahl (unabhängig aus Cache-Typzeilen
nachgezählt), Schlüsselkarten-Zugehörigkeit und Text-Aussagen gegen die
echte Deckliste und die Karten geprüft.

| Deck | Ergebnis |
|---|---|
| 2011 Counterpunch (Ghave) | Fakten korrekt (39 Länder, Commander ✓). Archetyp go_wide ✓. Schwäche: Schlüsselkarten sind Board-Wert-Fatties (Celestial Force, Symbiotic Wurm) statt der +1/+1-Synergie-Mitte — ehrlich als „nach Board-Wert" etikettiert, aber als Paket nur Startpunkt. |
| 2021 Elven Empire (Lathril) | Korrekt (37 Länder). tribal:Elf primär ✓, Soll-Zug 3 für Lathril (MV 4 − Ramp) plausibel. |
| 2013 Mind Seize (Jeleva) | Korrekt (40 Länder). spellslinger ✓ (Jeleva-Deck). |
| 2016 Breed Lethality (Atraxa) | Fakten korrekt (39 Länder). Nur value_engine — es gibt kein Proliferate/+1/+1-Tag im Schema (Grenze, s. §4). |
| 2024 Tricky Terrain (Proxy) | Korrekt (44 Länder, SYNTHETIC-Klasse, 1 Ersetzung im JSON). Vor dem Fix: Archetyp value_engine statt lands — **gefunden und behoben** (Landfall-/Länder-Signal ergänzt; jetzt lands primär). |

Zusätzlich läuft ein **Voll-Gate über alle 206 Guides** (Commander =
Deckliste, jede Paket-/Schlüsselkarte ∈ Deckliste, Pflichtfelder,
MD vorhanden): **0 Fehler**.

## 4. Befunde aus der Arbeit (über die Guides hinaus)

1. **RogShai-Drift:** Pilot-Code (`RogShaiPilot`) und Paket-Registry
   führen Karten, die nicht in Hans' aktuellem Deck sind: Staggering
   Insight (als Combat-Draw-Kernkarte im Code!), Duelist's Heritage,
   Sunhome, Silence, Lofty Denial, Open the Armory, Blackblade Reforged,
   Narset, Farewell. Folgenlos im Spiel (Karten tauchen nicht auf), aber
   das „vorhandene Wissen" beschreibt teilweise ein Meta-Deck, nicht das
   gespielte. Umgekehrt fehlen namentliche Regeln für aktuelle Karten
   (Leitmotif Composer, Mica, Thunderdrum Soloist, Furygale Flocking).
2. **Registry-Status `rejected`:** 4 der 10 RogShai-Pakete
   (combat-draw, independent-draw, wipe-protection, rograkh-resource)
   stehen auf `rejected`, werden vom Piloten aber weiter per
   `_package_ids` referenziert. Ob das Absicht (Status = Extraktions-,
   nicht Nutzungs-Status) oder Altlast ist, muss die Pilot-Lane klären.
3. **`LAND_SYNERGY` wird von `card_roles()` nie aus Text vergeben** —
   nur über kuratierte Profile (die es für 6 Kartengruppen gibt). Der
   Pilot sieht Land-Decks rollenseitig fast ohne Land-Synergie; der
   Generator kompensiert auf Deck-Ebene (Länderzahl/Landfall-Text).
4. **Fokus-Messwerte präzisiert:** RogShai-Baseline 35/200 = 17,5 %
   (ENDBERICHT gerundet 17 %), Chulane 19/200 = 9,5 % im 200-Spiele-
   Aggregat, 8 % im 100-Spiele-Analyse-Slice (ENDBERICHT gerundet 8 %).
   Ishai-Cast 189/200 = 94,5 % ✓; Chulane-Cast 176/200 = 88 %.

## 5. Grenzen und offene Punkte

- **Kein Guide ist wirkungsgeprüft.** Alle Parameter sind MODELED/
  CODE_DERIVED-Hypothesen; ob ein Guide den Piloten besser macht,
  entscheidet nur das Messprotokoll (Pilot-Handoff §6: gepaarte Seeds,
  Intervall-Verdikt). Das Paket liefert den Input, nicht den Beleg.
- **Precon-Text-Guides sind Baustein-Texte** (5–8 Sätze aus Fakten und
  Archetyp) — sie ersetzen keine menschliche Deck-Kenntnis, geben dem
  Piloten aber je Deck Plan, Keep-Fenster und Bedrohungs-Korrekturen.
  Nur RogShai/Chulane sind handgeschriebene Tiefen-Guides.
- **Kein `combo`-Tag, kein Proliferate-/Counter-Archetyp:** Aus
  Oracle-Texten nicht belastbar ableitbar (UNKNOWN-Prinzip). Decks wie
  Breed Lethality fallen auf value_engine zurück.
- **Schlüsselkarten = Board-Wert, nicht Synergie:** `permanent_value()`
  bevorzugt teure Engine-/Finisher-Karten; das Synergie-Zentrum eines
  Decks (z. B. Ghaves Opfer-/Marken-Mitte) wird nicht sicher getroffen.
  Die Fokus-Guides korrigieren das von Hand; für Precons wäre eine
  Synergie-Erweiterung (Text-Signale „whenever … counter/sacrifice")
  der nächste Qualitäts-Schritt.
- **Soll-Zug-Formel ist grob** (MV − 0/1). Eine echte Projektion bräuchte
  die Mana-Simulation aus der M4-Castability je Deck — als Folgearbeit
  möglich, Castability-Maschinerie existiert.
- **Deck-Stand:** Lokale Clones stehen vor #982/#988 (Precons noch 195
  am Stück); die Klassen-Zerlegung folgt der main-Grundwahrheit
  (proxies.json). Ändert sich der Pool, Generator erneut laufen lassen
  (beide Skripte sind idempotent; Reihenfolge: generate → focus-overrides).
- **Nicht enthalten (bewusst):** Gegner-Guides/Matchup-Tabellen (die
  Bedrohungs-Overrides decken die eigene Schwachstelle, keine
  paarweisen Matchups) und Änderungen am Piloten selbst — die
  Verdrahtung (FORMAT.md §4) ist der Umsetzungsauftrag an die
  Pilot-Lane, kein Patch.

## 6. Dateien

- `FORMAT.md` — Schema + Verdrahtung + Ableitungsregeln
- `guides/*.json` / `guides/*.md` — 206 Guide-Paare
  (Schwerpunkte: `guides/rogshai.*`, `guides/chulane.*`)
- `tools/fetch_scryfall_cache.py`, `tools/generate_guides.py`,
  `tools/apply_focus_overrides.py` — reproduzierbare Pipeline
- `scryfall_cache.json` (6.380 Karten), `proxies.json` (Grundwahrheit
  SYNTHETIC), `coverage.json` (Abdeckungs-Zahlen dieses Berichts)
