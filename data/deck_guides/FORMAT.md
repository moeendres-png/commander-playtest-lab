# Deck-Guide-Format — Schema und Verdrahtung in den Piloten

Stand 2026-10-24. Zweck: Jeder Guide verwandelt ein Deck von einer bloßen
Kartenliste in **deckspezifisches Entscheidungswissen** für die Piloten:
Der generische Pilot (`GenericCommanderPilot`) spielt heute jedes Deck mit
denselben Gewichten und derselben Eröffnungslogik. Die Guides liefern die
Parameter, mit denen daraus ein deckspezifischer Pilot wird — nach exakt
dem Muster, das die handgebauten Spezialisten (`RogShaiPilot`,
`KorvoldPilot` in `src/commander_lab/agents/pilots.py`) heute schon nutzen:
Gewichts-Deltas auf den `PilotUtilityWeights`, ein `specialist_bonus` aus
Paketen/Kartenregeln und eine eigene Eröffnungswertung
(`opening_hand_specialist_bonus` / `opening_card_value`).

**Evidenz-Regeln (Projektstandard):** Jedes Feld trägt seine Herkunft.
Kartenfakten (Kosten, Typen, Oracle-Text) kommen von Scryfall bzw. aus
`data/cards/pilot_card_knowledge.json` (`DIRECTLY_VERIFIED` als gedruckte
Kartenfakten). Alles, was daraus per Formel/Heuristik abgeleitet ist
(Rollen, Kurve, Soll-Zug, Gewichte), ist `MODELED` bzw. `CODE_DERIVED`
(Rollen exakt über die Repo-eigene `card_roles()`-Heuristik, s. u.).
Strategische Deutungen im Text-Teil sind Experten-Konsens im Sinne von
RESEARCH.md Abschnitt A (`EXTERNALLY_RULE_VALIDATED` nur, wo sie direkt
auf A1–A6 zurückgehen; sonst `MODELED`). Was nicht ableitbar ist, bleibt
`UNKNOWN` — es wird **nichts erfunden**: kein Karteneffekt, der nicht im
Oracle-Text steht, keine Kombo, die nicht aus den Texten folgt.

---

## 1. Dateiformat

Pro Deck zwei Dateien in `guides/`:

- `<slug>.json` — maschinenlesbare Parameter (Schema unten).
- `<slug>.md` — der kurze menschliche Guide (Spielplan in 5–10 Sätzen,
  Schlüsselkarten, Keep-Regeln, Zielprioritäten). Für die 204
  Precon-Decks wird der Text aus Bausteinen generiert; für RogShai und
  Chulane ist er handgeschrieben und ausführlicher.

`slug` = `deck_id` mit `/` → `_` (z. B. `precon_2023_blast_from_the_past`).
Fokus-Decks: `rogshai`, `chulane`.

## 2. JSON-Schema (Felder)

```jsonc
{
  "schema": "deck-guide/1",
  "deck_id": "precon/2023/blast_from_the_past",   // exakt aus der Deckliste
  "guide_slug": "precon_2023_blast_from_the_past",
  "deck_name": "Blast from the Past",
  "deck_klasse": "REAL",            // REAL | SYNTHETIC | ORIGINAL_MIT_PROXY | FOKUS
  "evidenz": { "kartenfakten": "DIRECTLY_VERIFIED (Scryfall/repo cache)",
               "parameter": "MODELED", "rollen": "CODE_DERIVED" },

  "commander": ["The Fourth Doctor", "Sarah Jane Smith"],
  "commander_mana_value": [4, 2],
  "farbidentitaet": ["G", "U", "W"],
  "partner": true,

  // → Handoff §4.4 (Keep-Test): "Commander bis zu seinem Soll-Zug"
  "commander_soll_zug": {"The Fourth Doctor": 4, "Sarah Jane Smith": 2},
  "commander_soll_zug_basis": "Mana-Wert minus Ramp-Beschleunigung (Formel §3)",

  "manabasis": {
    "laender_gesamt": 36,
    "laender_nach_farbe": {"W": 12, "U": 14, "G": 13},   // erzeugbare Farben, Näherung
    "farbquellen_nichtland": 9,
    "pip_bedarf_frueh": {"W": 3, "U": 5, "G": 2}          // Pips aller Karten MV<=3 + Commander
  },

  "kurve": {"0": 1, "1": 6, "2": 15, "3": 17, "4": 12, "5": 7, "6": 4, "7+": 2,
            "durchschnitt_nonland": 3.05},

  "rollen": {                       // Zählung über card_roles() (Repo-Heuristik)
    "mana_source": 41, "ramp": 12, "draw": 14, "selection": 6,
    "removal": 9, "counter": 2, "protection": 3, "wipe": 2,
    "recursion": 4, "graveyard_hate": 1, "engine": 11, "enabler": 0,
    "payoff": 5, "finisher": 3, "combat_payoff": 6, "token_source": 4,
    "sacrifice_outlet": 0, "land_synergy": 1
  },
  "rollen_unbekannt": 0,            // Karten ohne Scryfall-Fakten (UNKNOWN)

  "archetypen": ["value_engine", "go_wide"],   // Tags, Regeln §3
  "win_plan": "…",                  // 1–2 Sätze, aus Archetyp + Finisher/Payoff-Karten
  "schluesselkarten": ["…"],        // Engine/Finisher mit höchstem permanent_value

  // → Handoff §4.4: Parameter des universellen Keep-Tests für DIESES Deck
  "keep_test": {
    "laender_min": 2, "laender_max": 4,
    "laender_max_gezogen": 5,       // London: aus 7 gezogen, Überschuss wird gebottomt
    "fruehspiel_mindestanzahl": 1,  // spielbare Aktionen MV<=3 (ohne Länder)
    "fruehspiel_zuege": [1, 2, 3],  // an >=2 dieser Züge (Handoff §4.4)
    "commander_projektion_zug": 4,  // Mana-Projektion T3/T4 >= Commander-Kosten - Ramp
    "mulligan_latte": [             // Latten-Modifikator je gezähltem Mulligan
      {"mulligans": 0, "schwelle_delta": 0.0},
      {"mulligans": 1, "schwelle_delta": -0.55},
      {"mulligans": 2, "schwelle_delta": -1.1, "nur_laender_und_fruehspiel": true}
    ],
    "nie_unter_karten": 5,
    "bottoming_prioritaet": ["land_ueber_max", "teuerste_unspielbare",
                             "situative_karte", "doppelte_engine",
                             "nie: einzige_interaktion | einzige_farbquelle | einziger_fruehspielzug"]
  },

  // → Handoff §4.8 + BasePilot.default_weights: Deltas auf PilotUtilityWeights
  //   (gleiche Feldnamen wie PilotUtilityBreakdown; Basis = _GENERIC_WEIGHTS[staerke])
  "utility_deltas": {
    "survival": 0.0, "mana_efficiency": 0.0, "card_advantage": 0.15,
    "tempo": 0.0, "engine_development": 0.3, "interaction_reserve": 0.0,
    "commander_value": 0.1, "threat_reduction": 0.0, "win_progress": 0.1,
    "political_visibility": 0.0, "rebuild_capacity": 0.1
  },

  // → Handoff §4.4 (opening_card_value / Bottoming) und §4.1 (Sequenzierung)
  "eröffnung": {
    "wertvolle_fruehe_karten_rollen": ["ramp", "engine", "draw"],
    "halte_interaktion_ab_zug": 3        // ab diesem Zug Reserve-Mana-Regel greift
  },

  // → Handoff §4.2: Bedrohungs-Leiter, Betrifft-mich-Faktor
  "bedrohung": {
    "eigene_schutzkarten": ["…"],   // Karten, deren Verlust den Plan killt (Schutzpriorität)
    "gegner_overrides": [           // Kategorien gegnerischer Karten mit Stufen-Korrektur
      {"kategorie": "graveyard_hate", "delta_stufe": +3, "grund": "Deck rekuriert stark"},
      {"kategorie": "boardwipe", "delta_stufe": -1, "grund": "Deck baut schnell wieder auf"}
    ],
    "angriffs_fokus": "commander_schaden_buendeln | zweckverteilt | breit",
    "zuerst_bedrohen": "spieler_mit_kuerzester_uhr"   // Default A2/A3, deck-spezifisch überschreibbar
  },

  // → Handoff §4.1: Timing-Defaults mit Deck-Ausnahmen
  "sequenzierung": [
    {"regel": "postcombat_standard", "aktiv": true},
    {"regel": "precombat_ausnahme", "grund": "…", "karten": ["…"]},
    {"regel": "draw_endstep_letzter_gegner", "aktiv": true}
  ],

  // → Muster der Spezialist-Piloten: Pakete füttern specialist_bonus (+Bonus je Paket)
  "pakete": [
    {"id": "precon-2023-blast-from-the-past-engine", "karten": ["…"], "bonus": 0.4,
     "komponente": "engine_development"}
  ],

  // seit Repin v14 leer (kein Proxy-Deck mehr im Pool); frühere Guides trugen hier die Ersetzungen
  "proxy": {"ist_proxy_deck": false, "original_deck_id": null,
            "ersetzungen": [{"original": "…", "proxy": "…"}]}
}
```

## 3. Ableitungsregeln (Generator, `tools/generate_guides.py`)

- **Rollen** kommen aus der Repo-eigenen Heuristik
  `commander_lab.agents.card_knowledge.card_roles()` (wt-m4-Stand), gespeist
  mit denselben Kartenfakten (Scryfall-Cache). Damit misst der Guide exakt
  die Rollenwelt, die der Pilot im Spiel sieht (`role_counts` im
  `PilotStateView`, `role_strengths` im `PilotActionView`) — kein zweites,
  abweichendes Rollensystem. Kuratierte Profile
  (`structural_role_profiles.json`) schlagen die Text-Heuristik, wie im Repo.
- **Commander-Soll-Zug** (MODELED): `soll = max(1, MV - beschleunigung)` mit
  `beschleunigung = 1`, wenn das Deck ≥ 9 Nichtland-Ramp-Karten mit MV ≤ 3
  oder ≥ 5 Mana-Dorks/Rocks mit MV ≤ 2 führt, sonst 0. Bei Partnern je
  Commander einzeln; der frühere Commander trägt den Keep-Test.
- **Farbquellen/Pip-Bedarf** (MODELED): `laender_nach_farbe` zählt je Land
  höchstens einmal pro Farbe — über den Basisland-Typ im Typ-String oder
  `{X}`-Symbole in einem „Add"-Text. Fetchlands und „any color"-Länder
  ohne Symbol zählen für keine Einzelfarbe (bewusste Näherung, keine
  Manabasis-Simulation). Nichtland-Farbquellen separat über
  `produced_mana`. Pip-Bedarf „früh" = Summe der Farb-Pips aller Karten
  mit MV ≤ 3 plus Commander (Repo-`pips()`-Konvention).
- **Archetyp-Tags** aus Rollenanteilen und Typ-/Textsignalen, in fester
  Priorität (erste Markierung = primäre Gewinnachse): `voltron`
  (≥ 6 Auren/Equipment), `tribal:<Subtyp>` (≥ 8 Kreaturen eines Subtyps
  und ≥ 45 % der Kreaturen), `spellslinger` (Instant/Sorcery-Anteil
  ≥ 35 % und Draw+Engine ≥ 10), `graveyard` (Recursion ≥ 8),
  `artifacts`/`enchantments` (Typ-Anteil ≥ 30 %), `go_wide`
  (Token-Sources ≥ 10, oder ≥ 7 bei Combat-Payoff ≥ 5), `lands`
  (Land-Synergy ≥ 4 aus kuratierten Profilen, oder ≥ 42 Länder, oder
  ≥ 5 Landfall-Textsignale — `card_roles()` vergibt LAND_SYNERGY nicht
  aus Text, daher dieses Deck-Level-Signal), `control` (Counter+Removal+Wipe ≥ 16 und
  Kreatur-Anteil < 30 %), `value_engine` (Engine+Draw ≥ 24), `aggro`
  (Kreatur-Anteil ≥ 45 %, Kurvenschnitt ≤ 2,7, ≥ 50 % der Karten MV ≤ 3).
  Fallback: `midrange_value`. `combo` wird **nicht** vergeben (aus
  Texten nicht belastbar → UNKNOWN-Prinzip).
- **Utility-Deltas** (MODELED, begrenzt auf ±0,5): feste Abbildungstabelle
  Rollenanteil → Komponente, z. B. Engine-Anteil über Pool-Median →
  `engine_development +0,1…+0,3`; Counter/Protection-Anteil hoch →
  `interaction_reserve +…`; Finisher-/Commander-Fokus → `win_progress` /
  `commander_value`; Recursion-Anteil → `rebuild_capacity`. Die Tabelle
  steht im Generator und wird im BERICHT.md vollständig abgedruckt.
- **Bedrohungs-Overrides** nur aus Deck-Eigenschaften (nie aus behaupteten
  Einzelkarten-Interaktionen): Recursion-Anteil ≥ 6 % → gegnerische
  `graveyard_hate` +3; Kreatur-Anteil ≥ 45 % und Rebuild schwach →
  `boardwipe` +2; Commander MV ≤ 3 und Engine-Commander → eigene
  Commander-Schutzpriorität hoch; Spellslinger → gegnerische
  `rule_of_law`-Effekte (Text-Signal „can't cast more than one spell")
  +3. `eigene_schutzkarten` = die 3 Nichtland-Karten mit höchstem
  `permanent_value()` (Repo-Funktion) unter den Engine-/Finisher-Karten.
- **Sequenzierung**: Defaults aus Handoff §4.1; Precombat-Ausnahme nur bei
  belastbarem Signal im Oracle-Text (Haste-Verleiher, „at the beginning of
  combat"-Trigger, Equipment/Auren auf eigene Kreaturen in einem
  Voltron-Deck, Blocker-Entfernung bei hohem Removal-Anteil).
- **Keep-Test**: Länder-Fenster 2–4 (gezogen 2–5) als Default nach
  RESEARCH A1; bei Länderzahl des Decks < 34 oder > 38 wird das Fenster
  vermerkt, aber nicht verschoben (die London-Mathematik in A1 trägt 2–4
  auch dort). `commander_projektion_zug` = kleinster Soll-Zug.
  Latten-Deltas folgen der heutigen Code-Konvention
  (`should_keep_opening_hand`: −0,55 je effektivem Mulligan) und der
  A1-Regel „nie unter 5".

## 4. Wie jedes Feld in den Piloten eingespeist wird (Handoff §4)

| Guide-Feld | Pilot-Komponente | Handoff |
|---|---|---|
| `commander_soll_zug`, `keep_test.*` | Keep-Test-Konjugation in der `mulligan/`-Regel: Development Score prüft „spielbare Zugfolge Richtung Commander-Soll-Zug"; ersetzt die generische 3,5-Länder-Zentrierung von `opening_hand_score` durch deckparametrisierte Fenster | §4.4 |
| `manabasis.pip_bedarf_frueh`, `farbquellen` | Farb-/Fixierungs-Achse des Keep-Tests + Farbwahl-Regel (`choice`: fehlende Farbe statt Fixwert) | §4.4, §4.5 |
| `rollen`, `eröffnung.wertvolle_fruehe_karten_rollen` | `opening_card_value`-Bonus je Rolle (Muster: RogShaiPilot gibt COUNTER/PROTECTION/SELECTION Aufschläge) | §4.4 |
| `utility_deltas` | `default_weights()`: `base.update(...)` auf `_GENERIC_WEIGHTS[staerke]` — exakt das Spezialisten-Muster (RogShai/Korvold) | §4.8, §2 |
| `pakete` | `specialist_bonus` über `metadata["package_ids"]` (`_package_ids(action)`), Bonus je Paket | §2 (Code-Befund) |
| `bedrohung.gegner_overrides` | Betrifft-mich-Faktor in `target_threat`: Stufenwert der Bedrohungs-Leiter wird je Kategorie um `delta_stufe` korrigiert | §4.2 |
| `bedrohung.eigene_schutzkarten` | Protection-/Counter-Feuerregel: Schutz für diese Karten höher bewerten (`protected_permanent_value`-Aufschlag wie im RogShaiPilot) | §4.1, §4.2 |
| `bedrohung.angriffs_fokus` | Kampf-Fokus-Regel: Bündelung nur für Commander-Schaden; `zweckverteilt`/`breit` steuert die Nicht-Commander-Verteilung | §4.3 |
| `sequenzierung[]` | Timing-Gates vor der Utility: Optionen außerhalb ihres Fensters werden abgewertet; Precombat-Ausnahmen heben die Abwertung für die gelisteten Karten auf | §4.1 |
| `win_plan`, `schluesselkarten` | Dokumentation + Prior für `win_progress`-Zielauswahl; keine direkte Zahl (bewusst: kein erfundener Term) | §4.8 |
| `proxy.*` | Berichts-Trennung REAL/SYNTHETIC (Ergebnisse auf Proxy-Decks werden separat ausgewiesen, Projektregel) | — |

**Was die Guides bewusst nicht tun:** keine Legalitätsaussagen (XMage
bleibt einzige Rules Engine), keine versteckte Information (alle Felder
stammen aus der öffentlichen Deckliste + gedruckten Kartenfakten), keine
Kombo-Behauptungen ohne Textgrundlage, keine Siegquoten-Versprechen —
ob ein Guide den Piloten besser macht, misst allein das Messprotokoll
aus Handoff §6 (gepaarte Seeds, Intervall-Verdikt).

## 5. Fokus-Guides (RogShai, Chulane)

Für die beiden Owner-Decks sind die JSON-Parameter zusätzlich von Hand
nachgeschärft (Felder mit `"handgesetzt": true` im JSON) und die
`.md`-Guides handgeschrieben. RogShai dockt an das vorhandene
Spezialisten-Wissen an (RogShaiPilot + 5 Varianten, Enrichment-Verträge
`mulligan_contract.json` / `threat_axes.json` / `package_graph.json`) und
erweitert es um die M4-Messungen (Baseline 17 % Siegquote, Ishai in
94,5 % der Spiele gespielt, Rograkh in 100 %). Chulane bekommt mit diesem
Paket seinen ersten Spezialisten-Entwurf (Baseline 8 %, Chulane in
89 % der Spiele gespielt).
