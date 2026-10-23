#!/usr/bin/env python3
"""Generate deck guides (JSON parameters + text guide) for all played decks.

Sources (read-only):
  - Deck lists: main clone data/decks/precons/*.json (195 originals),
    wt-978 data/decks/precon_variants/*.json (9 SYNTHETIC proxy decks),
    M4 working copies of the two focus decks (~/workspace/tmp/m4/{rogshai,chulane}.json,
    set-identical to the owner-confirmed handover lists of 2026-10-22).
  - Card facts: stageDeckGuides/scryfall_cache.json (Scryfall + repo cache).
  - Roles: the repo's own heuristic commander_lab.agents.card_knowledge
    (card_roles / permanent_value) from the wt-m4 worktree, so the guides
    describe exactly the role world the pilot sees in PilotStateView.
  - Proxy mapping: stageDeckGuides/proxies.json (from
    data/decks/precon_synthetic_proxies.json on main, evidence SYNTHETIC).

Evidence: card facts DIRECTLY_VERIFIED (printed data); roles CODE_DERIVED;
every derived parameter MODELED (formulas in FORMAT.md section 3); cards
without facts are counted as UNKNOWN and never guessed.

Usage: python tools/generate_guides.py [--only slug ...]
Writes guides/<slug>.json + guides/<slug>.md and coverage.json.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/github/wt-m4/src")

from commander_lab.agents.card_knowledge import CardFacts, card_roles, permanent_value  # noqa: E402
from commander_lab.models import CardRole  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = json.loads((ROOT / "scryfall_cache.json").read_text(encoding="utf-8"))["cards"]
PROXIES = json.loads((ROOT / "proxies.json").read_text(encoding="utf-8"))["decks"]

DECK_SOURCES = [
    ("/home/hatch/workspace/github/commander-playtest-lab/data/decks/precons/*.json", "precon"),
    ("/home/hatch/workspace/github/wt-978/data/decks/precon_variants/*.json", "proxy"),
]
FOCUS = {
    "/home/hatch/workspace/tmp/m4/rogshai.json": "rogshai",
    "/home/hatch/workspace/tmp/m4/chulane.json": "chulane",
}
BASIC_TYPE_COLOR = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
ALL_ROLES = [r.value for r in CardRole]


def facts_for(name: str) -> CardFacts | None:
    entry = CACHE.get(name)
    if entry is None:
        front = name.split(" // ")[0]
        entry = next((v for k, v in CACHE.items() if k.split(" // ")[0] == front), None)
    if entry is None:
        return None
    return CardFacts(
        name=str(entry.get("name", name)),
        mana_value=float(entry.get("mana_value") or 0.0),
        mana_cost=str(entry.get("mana_cost") or ""),
        type_line=str(entry.get("type_line") or ""),
        oracle_text=str(entry.get("oracle_text") or ""),
        power=entry.get("power") if isinstance(entry.get("power"), int) else None,
        toughness=entry.get("toughness") if isinstance(entry.get("toughness"), int) else None,
        keywords=frozenset(str(w) for w in entry.get("keywords") or ()),
        colors=frozenset(str(c) for c in entry.get("colors") or ()),
        color_identity=frozenset(str(c) for c in entry.get("color_identity") or ()),
        produced_mana=frozenset(str(c) for c in entry.get("produced_mana") or ()),
    )


def load_decks() -> list[dict]:
    import glob

    decks = []
    for pattern, kind in DECK_SOURCES:
        for path in sorted(glob.glob(pattern)):
            deck = json.loads(Path(path).read_text(encoding="utf-8"))
            decks.append({"deck": deck, "kind": kind, "path": path})
    for path, slug in FOCUS.items():
        deck = json.loads(Path(path).read_text(encoding="utf-8"))
        decks.append({"deck": deck, "kind": "fokus", "path": path, "slug": slug})
    return decks


def slug_of(deck: dict, kind: str, slug_override: str | None) -> str:
    if slug_override:
        return slug_override
    return deck["deck_id"].replace("/", "_")


def analyze(deck: dict) -> dict:
    cards = deck["cards"]
    commander_names = deck["commander"]["commanders"]
    role_counts: Counter = Counter()
    role_unknown = 0
    curve: Counter = Counter()
    mv_sum, nonland, lands = 0.0, 0, 0
    land_colors: Counter = Counter()
    nonland_sources = 0
    pip_early: Counter = Counter()
    inst_sorc = 0
    creatures = 0
    landfall = 0
    aura_equip = 0
    artifacts = enchantments = 0
    subtypes: Counter = Counter()
    early_plays = 0
    cheap_ramp = 0
    cheap_producers = 0
    key_candidates: list[tuple[float, str]] = []
    per_card_roles: dict[str, dict[str, float]] = {}
    total_cards = 0
    for entry in cards:
        qty = int(entry.get("quantity") or 1)
        total_cards += qty
        name = entry["oracle_name"]
        facts = facts_for(name)
        if facts is None:
            role_unknown += qty
            continue
        roles = card_roles(facts)
        per_card_roles[name] = {r.value: s for r, s in roles.items()}
        for role, _strength in roles.items():
            role_counts[role.value] += qty
        text = facts.oracle_text.casefold()
        if facts.is_land:
            lands += qty
            # Farbe zaehlt je Land hoechstens einmal: Basisland-Typ ODER
            # {X}-Symbol im "Add"-Text. Fetchlands und "any color"-Laender
            # ohne Symbol zaehlen fuer keine Einzelfarbe (dokumentierte
            # Naeherung, FORMAT.md §3) -- kein Doppelzaehlen ueber produced_mana.
            colors = {BASIC_TYPE_COLOR[s] for s in facts.subtypes if s in BASIC_TYPE_COLOR}
            colors |= {sym for sym in re.findall(r"\{([WUBRG])\}", facts.oracle_text)
                       if "add" in facts.oracle_text.casefold()}
            for color in colors:
                land_colors[color] += qty
            continue
        nonland += qty
        mv_sum += facts.mana_value * qty
        bucket = str(int(facts.mana_value)) if facts.mana_value < 7 else "7+"
        curve[bucket] += qty
        if facts.mana_value <= 3:
            for color, n in facts.pips().items():
                if color in "WUBRG":
                    pip_early[color] += n * qty
            if facts.mana_value >= 1:
                early_plays += qty
        if "instant" in facts.types or "sorcery" in facts.types:
            inst_sorc += qty
        if "landfall" in text or "whenever a land you control enters" in text:
            landfall += qty
        if facts.is_creature:
            creatures += qty
            for subtype in facts.subtypes:
                subtypes[subtype] += qty
        if "artifact" in facts.types:
            artifacts += qty
        if "enchantment" in facts.types:
            enchantments += qty
        if "aura" in facts.subtypes or "Equipment" in facts.subtypes:
            aura_equip += qty
        if facts.produced_mana:
            nonland_sources += qty
            if facts.mana_value <= 2:
                cheap_producers += qty
        if CardRole.RAMP in roles and facts.mana_value <= 3:
            cheap_ramp += qty
        if roles.keys() & {CardRole.ENGINE, CardRole.FINISHER, CardRole.PAYOFF}:
            value = permanent_value(facts, is_commander=name in commander_names)
            key_candidates.append((value, name))
    for cname in commander_names:
        cfacts = facts_for(cname)
        if cfacts:
            for color, n in cfacts.pips().items():
                if color in "WUBRG":
                    pip_early[color] += n
    key_candidates.sort(reverse=True)
    accel = 1 if (cheap_ramp >= 9 or cheap_producers >= 5) else 0
    soll = {}
    cmv = {}
    for cname in commander_names:
        cfacts = facts_for(cname)
        mv = cfacts.mana_value if cfacts else 0.0
        cmv[cname] = mv
        soll[cname] = max(1, int(mv) - accel)
    # Die bindende Projektion ist der teuerste Commander (Hauptlinie); bei
    # Partnern ist der billige Partner T1-Spiel, nicht die Projektionslinie.
    haupt = max(commander_names, key=lambda n: cmv.get(n, 0.0)) if commander_names else None
    identity = sorted({c for n in commander_names if (f := facts_for(n)) for c in f.color_identity})
    return {
        "total_cards": total_cards,
        "commander": commander_names,
        "commander_mana_value": [cmv[n] for n in commander_names],
        "partner": bool(deck["commander"].get("uses_partner")),
        "farbidentitaet": identity,
        "commander_soll_zug": soll,
        "haupt_commander": haupt,
        "ramp_beschleunigung": accel,
        "laender": lands,
        "land_colors": dict(land_colors),
        "farbquellen_nichtland": nonland_sources,
        "pip_bedarf_frueh": dict(pip_early),
        "kurve": {k: curve.get(k, 0) for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]},
        "kurve_schnitt": round(mv_sum / nonland, 2) if nonland else 0.0,
        "rollen": {r: role_counts.get(r, 0) for r in ALL_ROLES},
        "rollen_unbekannt": role_unknown,
        "inst_sorc": inst_sorc,
        "landfall": landfall,
        "creatures": creatures,
        "nonland": nonland,
        "artifacts": artifacts,
        "enchantments": enchantments,
        "aura_equip": aura_equip,
        "subtypes": subtypes,
        "early_plays": early_plays,
        "schluesselkarten": [name for _v, name in key_candidates[:6]],
        "per_card_roles": per_card_roles,
    }


# Prioritaet: erste Markierung = primaere Gewinnachse (steuert win_plan + Textguide).
_TAG_PRIORITY = ["voltron", "tribal", "spellslinger", "graveyard", "artifacts",
                 "enchantments", "go_wide", "lands", "control", "value_engine",
                 "aggro", "midrange_value"]


def archetypes(a: dict) -> list[str]:
    nonland = max(1, a["nonland"])
    roles = a["rollen"]
    found: dict[str, str] = {}

    def add(key: str, label: str | None = None) -> None:
        found[key] = label or key

    if a["aura_equip"] >= 6:
        add("voltron")
    top_sub = a["subtypes"].most_common(1)
    if top_sub and top_sub[0][1] >= 8 and top_sub[0][1] / max(1, a["creatures"]) >= 0.45:
        add("tribal", f"tribal:{top_sub[0][0]}")
    if a["inst_sorc"] / nonland >= 0.35 and (roles["draw"] + roles["engine"]) >= 10:
        add("spellslinger")
    if roles["recursion"] >= 8:
        add("graveyard")
    if a["artifacts"] / nonland >= 0.30:
        add("artifacts")
    if a["enchantments"] / nonland >= 0.30:
        add("enchantments")
    if roles["token_source"] >= 10 or (roles["token_source"] >= 7 and roles["combat_payoff"] >= 5):
        add("go_wide")
    # card_roles() vergibt LAND_SYNERGY nur ueber kuratierte Profile; das
    # Generator-Signal (Landanzahl / Landfall-Text) ist das ehrliche Deck-Level-Signal.
    if roles["land_synergy"] >= 4 or a["laender"] >= 42 or a["landfall"] >= 5:
        add("lands")
    if roles["counter"] + roles["removal"] + roles["wipe"] >= 16 and a["creatures"] / nonland < 0.3:
        add("control")
    if roles["engine"] + roles["draw"] >= 24:
        add("value_engine")
    low = sum(v for k, v in a["kurve"].items() if k in ("1", "2", "3"))
    if a["creatures"] / nonland >= 0.45 and a["kurve_schnitt"] <= 2.7 and low / nonland >= 0.5:
        add("aggro")
    ordered = [found[k] for k in _TAG_PRIORITY if k in found]
    return ordered or ["midrange_value"]


# Utility-Delta-Abbildung: (Bedingung auf Rollenanteile relativ zum Pool-Median) -> Delta.
# Begrenzt auf +/-0.5, dokumentiert in FORMAT.md §3 und BERICHT.md.
def utility_deltas(a: dict, medians: dict[str, float]) -> dict[str, float]:
    roles = a["rollen"]
    nonland = max(1, a["nonland"])
    d = {k: 0.0 for k in [
        "survival", "mana_efficiency", "card_advantage", "tempo", "engine_development",
        "interaction_reserve", "commander_value", "threat_reduction", "win_progress",
        "political_visibility", "rebuild_capacity"]}

    def share(role: str) -> float:
        return roles[role] / nonland

    def bump(key: str, amount: float) -> None:
        d[key] = max(-0.5, min(0.5, d[key] + amount))

    if share("engine") > medians["engine"] * 1.3:
        bump("engine_development", 0.3)
    elif share("engine") > medians["engine"] * 1.1:
        bump("engine_development", 0.15)
    if share("draw") > medians["draw"] * 1.3:
        bump("card_advantage", 0.25)
    if share("counter") + share("protection") > (medians["counter"] + medians["protection"]) * 1.4:
        bump("interaction_reserve", 0.3)
    if share("removal") + share("wipe") > (medians["removal"] + medians["wipe"]) * 1.4:
        bump("threat_reduction", 0.2)
        bump("survival", 0.1)
    if share("recursion") > medians["recursion"] * 1.4:
        bump("rebuild_capacity", 0.3)
    if share("finisher") + share("payoff") > (medians["finisher"] + medians["payoff"]) * 1.3:
        bump("win_progress", 0.2)
    if min(a["commander_mana_value"] or [4]) <= 2:
        bump("commander_value", 0.25)
        bump("tempo", 0.15)
    if a["kurve_schnitt"] <= 2.6:
        bump("tempo", 0.2)
        bump("mana_efficiency", -0.1)
    if a["kurve_schnitt"] >= 3.4:
        bump("card_advantage", 0.1)
        bump("tempo", -0.15)
    return {k: round(v, 2) for k, v in d.items()}


def threat_overrides(a: dict, tags: list[str]) -> list[dict]:
    roles = a["rollen"]
    nonland = max(1, a["nonland"])
    out = []
    if roles["recursion"] / nonland >= 0.06:
        out.append({"kategorie": "graveyard_hate", "delta_stufe": 3,
                    "grund": "Deck rekuriert stark (Recursion-Anteil >= 6 %) — Friedhof-Hate sperrt den Plan (A2 Betrifft-mich)"})
    if a["creatures"] / nonland >= 0.45 and roles["recursion"] < 5:
        out.append({"kategorie": "boardwipe", "delta_stufe": 2,
                    "grund": "Kreaturlastiges Deck mit schwachem Wiederaufbau — Wipes treffen überproportional"})
    if any(t == "spellslinger" for t in tags):
        out.append({"kategorie": "rule_of_law_effekte", "delta_stufe": 3,
                    "grund": "Spellslinger-Deck: 'can't cast more than one spell'-Effekte sperren die Hauptachse"})
    if roles["token_source"] >= 8:
        out.append({"kategorie": "token_hate_minus_pump", "delta_stufe": 2,
                    "grund": "Go-wide-Deck: -1/-1- und Anti-Token-Effekte sind überdurchschnittlich wirksam"})
    return out


def sequencing(a: dict, tags: list[str]) -> list[dict]:
    rules = [{"regel": "postcombat_standard", "aktiv": True,
              "grund": "Handoff §4.1 Default: alles, was den Kampf nicht verändert, nach dem Kampf"}]
    # Precombat-Ausnahme nur bei Text-Signal
    pre = []
    for name in a["schluesselkarten"]:
        f = facts_for(name)
        if f and ("beginning of combat" in f.oracle_text.casefold() or "haste" in f.oracle_text.casefold()):
            pre.append(name)
    if pre:
        rules.append({"regel": "precombat_ausnahme", "karten": pre[:3],
                      "grund": "Kampfbeginn-Trigger/Haste im Oracle-Text — vor dem Kampf spielen"})
    draw_cards = [n for n, r in a["per_card_roles"].items()
                  if r.get("draw", 0) >= 1.0 and (f := facts_for(n)) and "instant" in f.types]
    if draw_cards:
        rules.append({"regel": "draw_endstep_letzter_gegner", "aktiv": True,
                      "grund": "Instant-Draw vorhanden (Handoff §4.1): ans letztmögliche Fenster"})
    return rules


ARCHETYPE_SENTENCE = {
    "value_engine": "Das Deck gewinnt über Karten- und Mana-Engines: Es baut Zug für Zug Vorsprung auf und konvertiert ihn spät in einen Finisher.",
    "go_wide": "Das Deck geht in die Breite: Tokens und viele kleine Kreaturen erzeugen ein Board, das über Anthems/Payoffs oder schiere Anzahl gewinnt.",
    "spellslinger": "Das Deck will viele Instants/Sorceries pro Zug spielen und über Magecraft-/Prodigy-Engines und Schadens-Payoffs gewinnen.",
    "control": "Das Deck spielt reaktiv: Interaktion und Wipes halten den Tisch in Schach, bis wenige, hochwertige Drohungen das Spiel schließen.",
    "graveyard": "Der Friedhof ist die zweite Hand: Recursion-Schleifen erzeugen den Wert, Friedhof-Hate ist die größte Schwachstelle.",
    "artifacts": "Artefakt-Synergien tragen den Plan: Engines und Payoffs rund um Artefakte aufbauen und schützen.",
    "enchantments": "Verzauberungen sind die Wertachse: Enchantress-Effekte und Payoffs aufbauen und das Board darüber schließen.",
    "lands": "Länder sind mehr als Mana: Landfall-/Land-Synergien erzeugen den Vorsprung, zusätzliche Land-Drops sind Karten wert.",
    "aggro": "Niedrige Kurve, schneller Druck: Das Deck will früh Schaden machen und das Spiel schließen, bevor die teuren Decks übernehmen.",
    "voltron": "Der Commander ist die Waffe: Auren/Equipment und Schutz auf einen Commander laden und über Commander-Schaden gewinnen.",
    "midrange_value": "Ausgewogenes Wert-Deck: solide Kurve, Interaktion und Drohungen — über Kartenqualität statt über eine einzelne Synergie-Achse gewinnen.",
}


def text_guide(deck: dict, a: dict, tags: list[str], klasse: str, proxy: dict | None) -> str:
    cmdrs = " + ".join(a["commander"])
    main_tag = tags[0] if tags else "midrange_value"
    key = ", ".join(a["schluesselkarten"][:4]) or "—"
    soll = a["commander_soll_zug"].get(a["haupt_commander"], "?")
    lines = [f"# Guide: {deck.get('name', deck['deck_id'])}", ""]
    if klasse == "SYNTHETIC":
        lines.append("> **SYNTHETIC-Proxy-Deck** — ersetzt Karten, die die Engine am Pin nicht kennt, "
                     "durch echte Engine-Karten. Kein Regels-/Qualifikations-Beleg; Ergebnisse separat ausweisen.")
        lines.append("")
    if klasse == "ORIGINAL_MIT_PROXY":
        lines.append("> **Original mit SYNTHETIC-Proxy:** Die Engine kennt einzelne Karten dieses Decks am Pin nicht; "
                     "gespielt wird die Proxy-Version (siehe JSON-Feld `proxy`). Dieser Guide beschreibt das Original.")
        lines.append("")
    s = []
    s.append(f"Commander: {cmdrs} (Farbidentität {''.join(a['farbidentitaet']) or 'farblos'}). "
             f"{ARCHETYPE_SENTENCE.get(main_tag.split(':')[0], ARCHETYPE_SENTENCE['midrange_value'])}")
    if len(tags) > 1:
        s.append(f"Zweite Achse: {tags[1]}. Manabasis: {a['laender']} Länder, "
                 f"Kurvenschnitt (Nonland) {a['kurve_schnitt']}.")
    else:
        s.append(f"Manabasis: {a['laender']} Länder, Kurvenschnitt (Nonland) {a['kurve_schnitt']}.")
    s.append(f"Schlüsselkarten (Engine/Finisher nach Board-Wert): {key}. "
             f"Der Haupt-Commander ({a['haupt_commander']}) soll bis Zug {soll} liegen "
             f"(Mana-Wert minus Ramp-Beschleunigung des Decks).")
    s.append(f"Keep-Test: 2–4 Länder (aus 7 gezogen 2–5, Überschuss bottomen), dazu mindestens ein "
             f"spielbarer Frühspielzug (MV ≤ 3) an zwei der ersten drei Züge und die Farben für die "
             f"frühen Pips ({', '.join(f'{c}:{n}' for c, n in sorted(a['pip_bedarf_frueh'].items())) or 'keine'}). "
             f"Latte fällt je Mulligan, nie unter 5 Karten.")
    thr = threat_overrides(a, tags)
    if thr:
        s.append("Bedrohungs-Korrekturen: " + "; ".join(f"{t['kategorie']} ({t['delta_stufe']:+d})" for t in thr) + ".")
    s.append("Angriffe: Commander-Schaden auf einen Spieler bündeln (Uhren-Regel), übrige Angriffe nach Zweck verteilen; "
             "alles, was den Kampf nicht verändert, postcombat spielen (Defaults aus Handoff §4.1/§4.3).")
    lines.append(" ".join(s))
    lines.append("")
    lines.append(f"_Generiert aus der Deckliste + Oracle-Fakten (Scryfall/Repo-Cache); Rollen über die Repo-Heuristik "
                 f"`card_roles()`. Parameter: MODELED/CODE_DERIVED — kein Messwert. Unbekannte Karten: {a['rollen_unbekannt']}._")
    return "\n".join(lines) + "\n"


def main() -> int:
    only = sys.argv[1:]
    items = load_decks()
    for item in items:
        item["analysis"] = analyze(item["deck"])
    shares = {"engine": [], "draw": [], "counter": [], "protection": [], "removal": [],
              "wipe": [], "recursion": [], "finisher": [], "payoff": []}
    for item in items:
        a = item["analysis"]
        for role in shares:
            shares[role].append(a["rollen"][role] / max(1, a["nonland"]))
    medians = {r: statistics.median(v) for r, v in shares.items()}

    coverage = {"guides": 0, "nach_klasse": Counter(), "unbekannte_karten_total": 0,
                "decks_mit_unbekannten": 0, "archetypen": Counter()}
    orig_ids = {Path(it["path"]).stem: it["deck"]["deck_id"] for it in items if it["kind"] == "precon"}
    for item in items:
        deck, kind = item["deck"], item["kind"]
        stem = Path(item["path"]).stem
        if kind == "proxy":
            klasse = "SYNTHETIC"
        elif kind == "fokus":
            klasse = "FOKUS"
        elif stem in PROXIES:
            klasse = "ORIGINAL_MIT_PROXY"
        else:
            klasse = "REAL"
        slug = slug_of(deck, kind, item.get("slug"))
        if only and slug not in only:
            continue
        a = item["analysis"]
        tags = archetypes(a)
        deltas = utility_deltas(a, medians)
        proxy_block = {"ist_proxy_deck": False, "original_deck_id": None, "ersetzungen": []}
        if kind == "proxy" and stem in PROXIES:
            p = PROXIES[stem]
            ers = [{"original": e["original"], "proxy": e["proxy"]} for e in p["main_deck_replacements"]]
            if p.get("commander_replacement"):
                ers.append({"original": p["commander_replacement"].get("original", "?"),
                            "proxy": p["commander_replacement"].get("proxy", "?"), "zone": "commander"})
            proxy_block = {"ist_proxy_deck": True, "original_deck_id": orig_ids.get(stem),
                           "proxy_deck_id_alias": p["proxy_deck_id"], "ersetzungen": ers}
        elif klasse == "ORIGINAL_MIT_PROXY":
            p = PROXIES[stem]
            proxy_block = {"ist_proxy_deck": False, "original_deck_id": None,
                           "proxy_deck_id": p["proxy_deck_id"],
                           "ersetzungen": [{"original": e["original"], "proxy": e["proxy"]}
                                           for e in p["main_deck_replacements"]]}
        guide = {
            "schema": "deck-guide/1",
            "deck_id": deck["deck_id"],
            "guide_slug": slug,
            "deck_name": deck.get("name"),
            "deck_klasse": klasse,
            "evidenz": {"kartenfakten": "DIRECTLY_VERIFIED (Scryfall / repo pilot_card_knowledge)",
                        "rollen": "CODE_DERIVED (repo card_roles)",
                        "parameter": "MODELED (Formeln FORMAT.md §3)"},
            "commander": a["commander"],
            "commander_mana_value": a["commander_mana_value"],
            "farbidentitaet": a["farbidentitaet"],
            "partner": a["partner"],
            "commander_soll_zug": a["commander_soll_zug"],
            "haupt_commander": a["haupt_commander"],
            "commander_soll_zug_basis": f"Mana-Wert minus Ramp-Beschleunigung {a['ramp_beschleunigung']} (FORMAT.md §3)",
            "manabasis": {"laender_gesamt": a["laender"], "laender_nach_farbe": a["land_colors"],
                          "farbquellen_nichtland": a["farbquellen_nichtland"],
                          "pip_bedarf_frueh": a["pip_bedarf_frueh"]},
            "kurve": {**a["kurve"], "durchschnitt_nonland": a["kurve_schnitt"]},
            "rollen": a["rollen"],
            "rollen_unbekannt": a["rollen_unbekannt"],
            "archetypen": tags,
            "win_plan": ARCHETYPE_SENTENCE.get(tags[0].split(":")[0], ARCHETYPE_SENTENCE["midrange_value"]),
            "schluesselkarten": a["schluesselkarten"],
            "keep_test": {
                "laender_min": 2, "laender_max": 4, "laender_max_gezogen": 5,
                "fruehspiel_mindestanzahl": 1, "fruehspiel_zuege": [1, 2, 3],
                "commander_projektion_zug": a["commander_soll_zug"].get(a["haupt_commander"]),
                "mulligan_latte": [
                    {"mulligans": 0, "schwelle_delta": 0.0},
                    {"mulligans": 1, "schwelle_delta": -0.55},
                    {"mulligans": 2, "schwelle_delta": -1.1, "nur_laender_und_fruehspiel": True},
                ],
                "nie_unter_karten": 5,
                "bottoming_prioritaet": ["land_ueber_max", "teuerste_unspielbare", "situative_karte",
                                         "doppelte_engine",
                                         "nie: einzige_interaktion | einzige_farbquelle | einziger_fruehspielzug"],
            },
            "utility_deltas": deltas,
            "eroeffnung": {
                "wertvolle_fruehe_karten_rollen": [r for r in ("ramp", "engine", "draw", "selection")
                                                   if a["rollen"][r] >= 5],
                "halte_interaktion_ab_zug": 3,
            },
            "bedrohung": {
                "eigene_schutzkarten": a["schluesselkarten"][:3],
                "gegner_overrides": threat_overrides(a, tags),
                "angriffs_fokus": "commander_schaden_buendeln",
                "zuerst_bedrohen": "spieler_mit_kuerzester_uhr",
            },
            "sequenzierung": sequencing(a, tags),
            "pakete": [{"id": f"{slug}-kern", "karten": a["schluesselkarten"][:8], "bonus": 0.4,
                        "komponente": "engine_development"}],
            "proxy": proxy_block,
        }
        out_json = ROOT / "guides" / f"{slug}.json"
        out_json.write_text(json.dumps(guide, indent=1, ensure_ascii=False), encoding="utf-8")
        (ROOT / "guides" / f"{slug}.md").write_text(
            text_guide(deck, a, tags, klasse, proxy_block), encoding="utf-8")
        coverage["guides"] += 1
        coverage["nach_klasse"][klasse] += 1
        coverage["unbekannte_karten_total"] += a["rollen_unbekannt"]
        if a["rollen_unbekannt"]:
            coverage["decks_mit_unbekannten"] += 1
        for t in tags:
            coverage["archetypen"][t] += 1
    coverage["nach_klasse"] = dict(coverage["nach_klasse"])
    coverage["archetypen"] = dict(coverage["archetypen"])
    (ROOT / "coverage.json").write_text(json.dumps(coverage, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(coverage, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
