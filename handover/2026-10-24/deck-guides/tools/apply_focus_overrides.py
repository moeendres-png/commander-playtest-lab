#!/usr/bin/env python3
"""Hand-sharpen the two focus guides (rogshai.json, chulane.json).

Run AFTER generate_guides.py. Every overridden field is marked
"handgesetzt": true at field-group level; bases are cited per group:
  - RogShai utility deltas: CODE_DERIVED from RogShaiPilot.default_weights
    (wt-m4 src/commander_lab/agents/pilots.py) — the guide documents the
    existing specialist, it does not re-invent it.
  - Packages: data/packages/package_registry.json membership RESTRICTED to
    cards in the current deck list (registry describes a meta list; cards
    not in the current 100 are dropped and the drift is reported).
  - Measurements: M4 aggregates (200 games, Pin v11, Pilot 1.0.0) from
    ~/workspace/tmp/m4/stageFinal/handover/2026-10-22/deck-improvement/.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "guides"


def patch(slug: str, fn) -> None:
    path = GUIDES / f"{slug}.json"
    guide = json.loads(path.read_text(encoding="utf-8"))
    fn(guide)
    path.write_text(json.dumps(guide, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{slug}.json handgeschaerft")


def rogshai(g: dict) -> None:
    # Utility-Deltas = die des existierenden RogShaiPilot (CODE_DERIVED).
    g["utility_deltas"] = {
        "survival": 0.0, "mana_efficiency": 0.0, "card_advantage": 0.0,
        "tempo": 0.1, "engine_development": 0.0, "interaction_reserve": 0.35,
        "commander_value": 0.3, "threat_reduction": 0.0, "win_progress": 0.25,
        "political_visibility": 0.0, "rebuild_capacity": 0.0,
        "handgesetzt": True,
        "basis": "CODE_DERIVED: RogShaiPilot.default_weights (pilots.py, wt-m4-Lock d48bbe5f2). "
                 "Die fuenf Unter-Piloten (Tempo/Voltron/Spellslinger/Control/ProtectedFinish) "
                 "variieren diese Basis; siehe rogshai.md.",
    }
    g["commander_soll_zug"] = {"Rograkh, Son of Rohgahh": 1, "Ishai, Ojutai Dragonspeaker": 4}
    g["commander_soll_zug_basis"] = (
        "handgesetzt: Rograkh kostet {0} -> Zug 1. Ishai MV 4, aber die Pilot-Doktrin "
        "(RogShaiPilot.specialist_bonus) spielt sie nur mit Schutzfenster (>= 1 Mana Reserve + "
        "Protection/Counter auf der Hand) -> Soll-Zug 4 mit Reserve, nicht 3 ohne.")
    g["keep_test"]["commander_projektion_zug"] = 4
    g["keep_test"]["rogshai_zusatz"] = {
        "handgesetzt": True,
        "mana_achsen": "2-3 effektive fruehe Mana-Quellen (Enrichment mulligan_contract, shared_reasonable_policy); "
                       "Rograkh + Springleaf Drum / Relic of Legends zaehlt als Mana-Quelle",
        "hand_bonus_muster": "RogShaiPilot.opening_hand_specialist_bonus: billige Nichtkreaturen (MV<=2) +0.22 je (Cap 1.3); "
                             "Protection+Counter +0.3 je Staerke (Cap 0.9); Combat-Draw-Aura OHNE Protection/Counter -0.35",
        "nie_keep": "Hand ohne W/U-Quelle fuer Ishai UND ohne Plan B (Spellslinger-Engine) — Ishai ist die Hauptachse",
    }
    g["archetypen"] = ["voltron_commander_schaden", "spellslinger", "control_tempo"]
    g["win_plan"] = (
        "Zwei Achsen: (A) Ishai waechst an jedem Gegner-Zauber (+1/+1) und gewinnt ueber "
        "Commander-Schaden — gebuendelt auf einen Spieler, mit Kediss als Tisch-Schaden, "
        "Double-Strike (Psychotic Fury, Boros Charm) und Jeska (Schaden x3) als Finisher. "
        "(B) Commander-unabhaengige Spellslinger-Achse (Kykar, Veyran, Harmonic Prodigy, "
        "Storm-Kiln Artist, Guttersnipe, Whirlwind of Thought) als Plan B und Wiederaufbau. "
        "Winds of Rath ist der asymmetrische Wipe: Er trifft nur nicht-verzauberte Kreaturen — "
        "eine verzauberte Ishai (Curiosity/Combat Research/Staggering Insight) ueberlebt ihn.")
    g["bedrohung"] = {
        "handgesetzt": True,
        "eigene_schutzkarten": ["Ishai, Ojutai Dragonspeaker", "Kykar, Wind's Fury", "Whirlwind of Thought"],
        "gegner_overrides": [
            {"kategorie": "rule_of_law_effekte", "delta_stufe": 3,
             "grund": "Beide Achsen spielen viele Zauber pro Zug; 'one spell per turn' sperrt Deck komplett"},
            {"kategorie": "aura_enchantment_removal", "delta_stufe": 2,
             "grund": "Combat-Draw-Auren sind Plan-Achse (Registry failure_mode 'aura exposed to removal')"},
            {"kategorie": "boardwipe", "delta_stufe": 0,
             "grund": "Eigene asymmetrische Wipes + Spellslinger-Wiederaufbau-Achse: neutral"},
        ],
        "angriffs_fokus": "commander_schaden_buendeln (nur Ishai; Zielwechsel bei Uhren-/Bedrohungswechsel)",
        "kediss_warnung": "Kediss-Schaden ist KEIN Commander-Schaden (Registry failure_mode) — fuer die 21-Uhr zaehlt nur Ishais direkter Treffer",
        "zuerst_bedrohen": "spieler_mit_kuerzester_uhr; bei Ishai-Angriffen: der Spieler ohne Flieger-Blocker / mit der laengsten eigenen Gewinn-Uhr",
    }
    g["sequenzierung"] = [
        {"regel": "postcombat_standard", "aktiv": True, "grund": "Handoff §4.1 Default"},
        {"regel": "ishai_nur_mit_schutzfenster", "karten": ["Ishai, Ojutai Dragonspeaker"],
         "grund": "RogShaiPilot-Doktrin: Ishai nicht ohne >= 1 Reserve-Mana + Protection/Counter spielen, "
                  "ausser die Bedrohung erzwingt Tempo (max_opponent_threat-Regel im Code)"},
        {"regel": "combat_tricks_im_kampf_nicht_postcombat",
         "karten": ["Psychotic Fury", "Boros Charm"],
         "grund": "Double-Strike-Tricks wirken nur im Kampf — Ausnahme vom Postcombat-Default (Handoff §4.1 benannte Ausnahme)"},
        {"regel": "winds_of_rath_nur_asymmetrisch", "karten": ["Winds of Rath"],
         "grund": "Nur wirken, wenn Ishai verzaubert ist oder die Spellslinger-Achse das Spiel traegt; "
                  "sonst eigener Wipe frisst die Hauptachse (Registry failure_mode von wipe-protection)"},
        {"regel": "draw_endstep_letzter_gegner", "aktiv": True,
         "grund": "Dig Through Time / Treasure Cruise / Flow State ans spaete Fenster (Mana offen = Interaktions-Drohung)"},
    ]
    g["pakete"] = [
        {"id": "rogshai-combat-draw", "karten": ["Combat Research", "Curiosity", "Swiftfoot Boots"],
         "bonus": 0.4, "komponente": "card_advantage", "registry_status": "rejected",
         "drift_notiz": "Registry + RogShaiPilot-Code fuehren 'Staggering Insight' als dritte Combat-Draw-Aura — "
                        "sie ist NICHT im aktuellen Deck (Foto-Liste 2026-10-22). Hier entfernt.",
         "failure_modes": ["aura exposed to removal", "no safe combat connection"]},
        {"id": "rogshai-commander-damage", "karten": ["Ishai, Ojutai Dragonspeaker", "Psychotic Fury", "Boros Charm", "Jeska, Thrice Reborn"],
         "bonus": 0.45, "komponente": "win_progress", "registry_status": "curated",
         "failure_modes": ["Ishai removed before combat", "double strike shown without protection"]},
        {"id": "rogshai-double-strike", "karten": ["Psychotic Fury", "Boros Charm"],
         "bonus": 0.4, "komponente": "win_progress", "registry_status": "curated",
         "failure_modes": ["combat trick without lethal power", "protection unavailable"]},
        {"id": "rogshai-jeska-finish", "karten": ["Jeska, Thrice Reborn", "Ishai, Ojutai Dragonspeaker", "Dovin's Veto", "An Offer You Can't Refuse", "Psychotic Fury"],
         "bonus": 0.45, "komponente": "win_progress", "registry_status": "curated",
         "failure_modes": ["Jeska cast outside lethal window", "Ishai lacks sufficient power"]},
        {"id": "rogshai-kediss-table-damage", "karten": ["Kediss, Emberclaw Familiar", "Ishai, Ojutai Dragonspeaker", "Psychotic Fury", "Boros Charm", "Jeska, Thrice Reborn"],
         "bonus": 0.4, "komponente": "win_progress", "registry_status": "curated",
         "failure_modes": ["Kediss splash damage is not commander damage", "single-target lethal may be preferable"]},
        {"id": "rogshai-protection-counter", "karten": ["Counterspell", "Dovin's Veto", "An Offer You Can't Refuse", "Negate", "Wash Away", "Boros Charm", "Blacksmith's Skill", "Loran's Escape", "Slip Out the Back", "Louisoix's Sacrifice"],
         "bonus": 0.4, "komponente": "interaction_reserve", "registry_status": "curated",
         "failure_modes": ["counter spent on harmless value", "protection density stranded without threat"]},
        {"id": "rogshai-independent-spellslinger", "karten": ["Kykar, Wind's Fury", "Whirlwind of Thought", "Guttersnipe", "Storm-Kiln Artist", "Chandra, Torch of Defiance", "Faerie Mastermind", "Veyran, Voice of Duality", "Harmonic Prodigy", "Archmage Emeritus", "Thunderdrum Soloist", "Mica, Reader of Ruins", "Rootha, Mastering the Moment", "Manaform Hellkite", "Leitmotif Composer"],
         "bonus": 0.45, "komponente": "engine_development", "registry_status": "curated",
         "failure_modes": ["engine creature removed before spell chain", "insufficient noncreature spell density"]},
        {"id": "rogshai-independent-draw", "karten": ["Whirlwind of Thought", "Faerie Mastermind", "Loyal Drake", "Chandra, Torch of Defiance", "Consider", "Preordain"],
         "bonus": 0.35, "komponente": "card_advantage", "registry_status": "rejected",
         "failure_modes": ["combat draw counted as independent when Ishai is absent", "draw engines exposed into wipe"]},
        {"id": "rogshai-wipe-protection", "karten": ["Winds of Rath", "Boros Charm", "Blasphemous Act", "Chain Reaction", "Dovin's Veto", "An Offer You Can't Refuse", "Slip Out the Back"],
         "bonus": 0.35, "komponente": "survival", "registry_status": "rejected",
         "failure_modes": ["wipe removes own independent engines", "protection does not cover exile effects"]},
        {"id": "rogshai-rograkh-resource", "karten": ["Rograkh, Son of Rohgahh", "Springleaf Drum", "Relic of Legends", "Kykar, Wind's Fury", "Flare of Duplication"],
         "bonus": 0.35, "komponente": "tempo", "registry_status": "rejected",
         "failure_modes": ["Rograkh committed without conversion", "resource card weak after commander tax escalation"]},
    ]
    g["messung_m4"] = {
        "evidenz": "DIRECTLY_VERIFIED (M4-Lauefe, Pin v11, Pilot 1.0.0)",
        "baseline_spiele": 200,
        "siegquote_basis_arm": "35/200 = 17.5 % (ENDBERICHT gerundet 17 %)",
        "commander_cast_quote": {"Ishai, Ojutai Dragonspeaker": "189/200 = 94.5 %",
                                 "Rograkh, Son of Rohgahh": "200/200 = 100 %"},
        "casts_pro_100_spiele": {"Ishai, Ojutai Dragonspeaker": 210, "Rograkh, Son of Rohgahh": 310},
        "mulligan_spiele_anteil": "73/200 = 36.5 % mit >= 1 Mulligan",
        "mittlere_zuege": 47.48,
        "warnung_aus_m4": "Buendel R-A senkte den Ishai-Cast-Anteil auf 87.5 % — Deckveraenderungen, die die "
                          "Ishai-Verfuegbarkeit senken, sind ein eigenes Risiko (alle 6 Buendel UNDECIDED)",
    }
    g["evidenz"]["fokus_zusatz"] = ("Spezialisten-Code (pilots.py) CODE_DERIVED; Pakete aus package_registry.json "
                                    "(auf aktuelle Deckliste eingeschraenkt); Messwerte DIRECTLY_VERIFIED (M4)")


def chulane(g: dict) -> None:
    g["archetypen"] = ["value_engine_kreaturen", "lands", "go_wide_clue"]
    g["utility_deltas"] = {
        "survival": 0.0, "mana_efficiency": 0.0, "card_advantage": 0.25,
        "tempo": 0.0, "engine_development": 0.3, "interaction_reserve": 0.1,
        "commander_value": 0.3, "threat_reduction": 0.0, "win_progress": 0.1,
        "political_visibility": 0.0, "rebuild_capacity": 0.1,
        "handgesetzt": True,
        "basis": "MODELED (handgesetzt): Chulane ist die Engine des Decks — ohne ihn sind die Bounce-Kreaturen "
                 "Kartennachteil. commander_value/engine_development/card_advantage hoch; Interaktion ist duenn "
                 "(4 Counter-Rollen, Schutz ueber Veil of Summer / Tyvar's Stand / Silence), daher nur +0.1 Reserve.",
    }
    g["commander_soll_zug_basis"] = ("handgesetzt: Chulane MV 5; das Deck fuehrt 36 Laender und 16 Ramp-Rollen "
                                      "(u. a. Arbor Elf, Llanowar Elves, Sakura-Tribe Elder, Nature's Lore) -> "
                                      "Soll-Zug 4 ist die reale Linie, Zug 5 die späte.")
    g["keep_test"]["chulane_zusatz"] = {
        "handgesetzt": True,
        "drei_laender_bevorzugt": "5-MV-Commander: 2-Laender-Haende nur mit >= 2 Ramp-Karten (Dork/Rock/Land-Ramp)",
        "bounce_kreaturen_brauchen_chulane": "Shrieking Drake / Fleetfoot Panther / Kor Skyfisher ohne Chulane-Linie "
                                             "sind Wert-Verlust — in der Eröffnung abwerten, bis Chulane projiziert ist",
        "clue_achse_ist_plan_b": "Hand mit Lonis / Tireless Tracker + Kreaturen ist auch ohne sofortigen Chulane keepbar",
    }
    g["win_plan"] = (
        "Chulane ist die Engine: Jede Kreatur zieht eine Karte und legt ggf. ein Land — das Deck spielt "
        "billige Kreaturen in Serie, Bounce-Kreaturen (Shrieking Drake, Fleetfoot Panther, Kor Skyfisher) "
        "holen sie zurueck und wiederholen die Trigger. Zweite Achse: Clues (Lonis, Tireless Tracker, "
        "Ethereal Investigator), die Academy Manufactor verdreifacht (Clue+Food+Treasure). Finisher: "
        "Psychosis Crawler (jede gezogene Karte = 1 Leben je Gegner), Mechanized Production (Alternativ-Sieg "
        "ueber 8 gleichnamige Artefakte), Koma als Top-End; Landfall (Tatyova, Felidar Retreat, "
        "Rampaging Baloths) konvertiert die extra Land-Drops in Board.")
    g["bedrohung"] = {
        "handgesetzt": True,
        "eigene_schutzkarten": ["Chulane, Teller of Tales", "Academy Manufactor", "Lonis, Cryptozoologist"],
        "gegner_overrides": [
            {"kategorie": "boardwipe", "delta_stufe": 2,
             "grund": "Kreaturlastig (Recursion 0): Wipe setzt das Deck auf null zurueck; eigene Wipes (Farewell, Fumigate) asymmetrisch timen"},
            {"kategorie": "artifact_hate", "delta_stufe": 2,
             "grund": "Clue-/Artefakt-Achse (Manufactor, Mechanized Production, Tezzeret) ist Plan B und Alternativ-Sieg"},
            {"kategorie": "graveyard_hate", "delta_stufe": -2,
             "grund": "Deck nutzt den Friedhof praktisch nicht (Recursion 0) — gegnerisches Grave-Hate ist fast egal (A2 Betrifft-mich, negativ)"},
            {"kategorie": "commander_removal_dichte", "delta_stufe": 2,
             "grund": "Ohne Chulane kollabiert die Kartenökonomie; Gegner-Removal auf Chulane ist der kritische Pfad"},
        ],
        "angriffs_fokus": "zweckverteilt (kein Commander-Schaden-Plan; Chulane ist 2/4 Value-Engine, kein Voltron)",
        "zuerst_bedrohen": "spieler_mit_kuerzester_uhr; Removal bevorzugt auf gegnerische Engines, die schneller sind als die eigene Chulane-Uhr",
    }
    g["sequenzierung"] = [
        {"regel": "kreaturen_im_eigenen_zug_mit_chulane", "aktiv": True,
         "grund": "Gegen den Draw-Endstep-Default: Chulane-Trigger ziehen Karten UND legen Laender — Kreaturen gehoeren "
                  "in die eigene Hauptphase, solange Chulane liegt (gezogene Laender sind sofort spielbar)"},
        {"regel": "postcombat_standard", "aktiv": True,
         "grund": "Fuer Nichtkreaturen ohne Kampf-Relevanz gilt der Handoff-Default weiter"},
        {"regel": "instants_mit_wilderness_reclamation", "karten": ["Arcane Denial", "Negate", "Voracious Greatshark", "Brazen Borrower"],
         "grund": "Wilderness Reclamation enttappt alle Laender im eigenen End Step -> Interaktion im Gegnerzug mit vollem Mana"},
        {"regel": "bounce_nur_mit_trigger_oder_schutzgrund",
         "karten": ["Shrieking Drake", "Fleetfoot Panther", "Kor Skyfisher", "Chulane, Teller of Tales (Fähigkeit)"],
         "grund": "Bounce ist Trigger-Wiederholung oder Schutz (ETB eines Gegners/Removal ausweichen), nie Selbstzweck"},
    ]
    g["pakete"] = [
        {"id": "chulane-bounce-engine", "karten": ["Chulane, Teller of Tales", "Shrieking Drake", "Fleetfoot Panther", "Kor Skyfisher", "Whirler Rogue", "Aether Adept"],
         "bonus": 0.45, "komponente": "engine_development",
         "failure_modes": ["bounce without Chulane online = card disadvantage", "Chulane removed -> bounce creatures stranded"]},
        {"id": "chulane-clue-engine", "karten": ["Lonis, Cryptozoologist", "Academy Manufactor", "Tireless Tracker", "Ethereal Investigator", "Erdwal Illuminator", "Detective of the Month", "Serene Sleuth", "Tangletrove Kelp"],
         "bonus": 0.4, "komponente": "card_advantage",
         "failure_modes": ["manufactor removed -> clue axis halves", "clues hoarded without payoff"]},
        {"id": "chulane-landfall", "karten": ["Tatyova, Benthic Druid", "Tireless Tracker", "Felidar Retreat", "Rampaging Baloths", "Oracle of Mul Daya", "Horizon Explorer"],
         "bonus": 0.35, "komponente": "engine_development",
         "failure_modes": ["extra land drops without landfall payoff are just ramp"]},
        {"id": "chulane-finish", "karten": ["Psychosis Crawler", "Mechanized Production", "Koma, Cosmos Serpent", "Tangletrove Kelp", "Tezzeret, Betrayer of Flesh"],
         "bonus": 0.4, "komponente": "win_progress",
         "failure_modes": ["crawler needs draw volume to matter", "mechanized production is slow without manufactor"]},
        {"id": "chulane-schutz-interaktion", "karten": ["Veil of Summer", "Tyvar's Stand", "Silence", "Arcane Denial", "Negate", "Swords to Plowshares", "Farewell", "Fumigate", "Angel of Finality"],
         "bonus": 0.35, "komponente": "interaction_reserve",
         "failure_modes": ["thin interaction density — cannot answer everything", "silence is a turn-shield, not an answer"]},
    ]
    g["messung_m4"] = {
        "evidenz": "DIRECTLY_VERIFIED (M4-Lauefe, Pin v11, Pilot 1.0.0)",
        "baseline_spiele": 200,
        "siegquote_basis_arm": "19/200 = 9.5 % (100-Spiele-Analyse-Slice: 8 %; ENDBERICHT gerundet 8 %)",
        "commander_cast_quote": {"Chulane, Teller of Tales": "176/200 = 88 %"},
        "casts_pro_100_spiele": {"Chulane, Teller of Tales": 217, "Fleetfoot Panther": 113, "Shrieking Drake": 48},
        "mulligan_spiele_anteil": "70/200 = 35 % mit >= 1 Mulligan",
        "mittlere_zuege": 48.16,
        "befund": "Fleetfoot Panther ist die am haeufigsten gespielte Kreatur (113/100 Spiele) — die Bounce-Achse "
                  "laeuft; Chulane wird 2.17x pro Spiel gespielt (Entfernung frisst Zuege). Alle 6 Buendel UNDECIDED.",
    }
    g["evidenz"]["fokus_zusatz"] = ("Erster Spezialisten-Entwurf fuer dieses Deck (bisher nur GenericCommanderPilot); "
                                    "Parameter MODELED aus Deckliste + Oracle-Fakten, Messwerte DIRECTLY_VERIFIED (M4)")


patch("rogshai", rogshai)
patch("chulane", chulane)
