#!/usr/bin/env python3
"""Deterministic card facts for the Chulane rubric v2 (design draft, see facts_spec.md).

Reads a COPY of the Studio store (read-only sqlite) and the Studio code (castability, roles) and
writes, per Oracle id of the 922 pool cards:

  facts.jsonl            rater-visible facts (no usage, no popularity, no price, no v1 rating)
  usage_holdout.jsonl    usage counts, popularity and the v1 rubric: NEVER part of a rater prompt
  pool_benchmarks.json   pool-wide peer tables (role -> MV distribution, type group -> MV, body size)
  facts_manifest.json    counts, versions, input fingerprints (no timestamps: the run is repeatable)

Usage (PYTHONPATH points at the checkout whose studio code defines castability and roles):

  PYTHONPATH=<checkout>/src python3 extract_facts.py \
      --store <copy-of-store-dir> --repo <checkout> --out <out-dir> \
      [--deck-revision chulane-current@41f393530bb16ee9]

The store is opened read-only (sqlite URI mode=ro); nothing is written to it. The pool is the 922
cards of ``data/research/chulane_rubric_20261114/summary.csv`` (the same set as the 922 ranked
cards of ``strength_view.compute`` for the commander; checked by the manifest field
``pool_matches_summary``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

FACTS_VERSION = "facts-1"
COMMANDER = "Chulane, Teller of Tales"
DECK_REVISION = "chulane-current@41f393530bb16ee9"
DU_SIGNAL = "decklist_universe:corpus:1-5"
WUG = "WUG"
RUBRIC_DIR = "data/research/chulane_rubric_20261114"

# Main role = first role of the card in this order (deterministic; the order is a convention of
# this draft: mana first, then interaction, then card flow, then the rest).
PRIMARY_ROLE_ORDER = (
    "mana_dork", "mana_rock", "land_ramp", "ramp", "board_wipe", "counterspell", "removal",
    "tutor", "card_advantage", "card_draw", "cantrip", "bounce", "flicker", "recursion",
    "protection", "token_production", "landfall", "cost_reduction", "copy", "untapper", "tapper",
    "anthem", "counters", "evasion", "lifegain", "sacrifice_outlet", "mana_sink", "tax", "hate",
    "graveyard_hate", "mill", "combat_trick", "card_selection", "utility_land",
)  # fmt: skip
TYPE_GROUP_ORDER = ("Land", "Creature", "Planeswalker", "Battle", "Artifact", "Enchantment",
                    "Instant", "Sorcery")  # fmt: skip
_SYMBOL = re.compile(r"\{([^}]+)\}")
_PT = re.compile(r"^-?\d+$")


# Leak guard: no key of a rater-visible record may name usage, popularity, price or a v1 rating.
# The extraction stops when one does. (Values are not scanned: card text may use any word.)
LEAK_KEYS = re.compile(
    r"edhrec|deck_list|decklist|rubric|h_mean|h_sd|times_brought|playgroup|inclusion|price|usd|"
    r"usage|popular|v1|in_reference_deck|source_decks|win_?rate",
    re.IGNORECASE,
)


def assert_no_leak(obj, where: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if LEAK_KEYS.search(str(k)):
                raise SystemExit(
                    f"leak guard: key {where}/{k} looks like usage, popularity, price or v1"
                )
            assert_no_leak(v, f"{where}/{k}")
    elif isinstance(obj, list):
        for v in obj:
            assert_no_leak(v, where)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_faces(fact: dict) -> list[dict]:
    """Faces of a card. card_fact stores the faces joined with ' // ' (name, cost, type line) and
    '\\n//\\n' (text). When the counts disagree the card keeps ONE entry with the joined strings
    and ``faces_parse_ok`` false (nothing is guessed)."""
    names = (fact["oracle_name"] or "").split(" // ")
    costs = (fact["mana_cost"] or "").split(" // ") if fact["mana_cost"] else []
    types = (fact["type_line"] or "").split(" // ")
    texts = (fact["oracle_text"] or "").split("\n//\n")
    n = len(names)
    ok = len(types) == n and len(texts) == n and (len(costs) in (0, 1, n))
    if n == 1 or not ok:
        return (
            [
                {
                    "name": fact["oracle_name"],
                    "mana_cost": fact["mana_cost"],
                    "type_line": fact["type_line"],
                    "oracle_text": fact["oracle_text"] or "",
                }
            ]
            if n == 1
            else [
                {
                    "name": fact["oracle_name"],
                    "mana_cost": fact["mana_cost"],
                    "type_line": fact["type_line"],
                    "oracle_text": fact["oracle_text"] or "",
                    "unsplit": True,
                }
            ]
        )
    faces = []
    for i in range(n):
        faces.append(
            {
                "name": names[i],
                "mana_cost": costs[i]
                if len(costs) == n
                else (costs[0] if costs and i == 0 else None),
                "type_line": types[i],
                "oracle_text": texts[i],
            }
        )
    return faces


def pips(mana_cost: str | None) -> dict:
    """Mana symbols of the FRONT face cost: coloured pips per colour (a hybrid symbol counts
    for each of its colours, flagged), generic amount, X, colourless {C}, Phyrexian."""
    out = {"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 0, "generic": 0, "X": 0,
           "hybrid_symbols": 0, "phyrexian_symbols": 0}  # fmt: skip
    if not mana_cost:
        return out
    for sym in _SYMBOL.findall(mana_cost.split(" // ")[0]):
        if sym in "WUBRG" and len(sym) == 1:
            out[sym] += 1
        elif sym == "C":
            out["C"] += 1
        elif sym == "X":
            out["X"] += 1
        elif sym.isdigit():
            out["generic"] += int(sym)
        elif "/" in sym:
            parts = sym.split("/")
            if "P" in parts:
                out["phyrexian_symbols"] += 1
            else:
                out["hybrid_symbols"] += 1
            for p in parts:
                if p in "WUBRG" and len(p) == 1:
                    out[p] += 1
    return out


def type_group(front_type: str) -> tuple[str, list[str]]:
    head = front_type.split("—")[0]
    types = [w for w in head.split() if w not in ("Legendary", "Basic", "Snow", "World", "Token")]
    for g in TYPE_GROUP_ORDER:
        if g in types:
            return g, types
    return "Other", types


def pt_total(power, toughness) -> int | None:
    if (
        power is not None
        and toughness is not None
        and _PT.match(str(power))
        and _PT.match(str(toughness))
    ):
        return int(power) + int(toughness)
    return None


def enters_tapped_class(text: str) -> str:
    t = text.lower()
    hits = [s for s in re.split(r"[.\n]", t) if re.search(r"enters(?: the battlefield)? tapped", s)]
    if not hits:
        return "untapped"
    if any(
        re.search(r"\bunless\b|\bif you\b|\bif you control\b|\bif an opponent", s) for s in hits
    ):
        return "conditional"
    return "tapped"


def quantiles(values: list[float]) -> dict:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return {"n": 0}
    q = statistics.quantiles(s, n=4, method="inclusive") if n >= 2 else [s[0]] * 3
    return {"n": n, "median": statistics.median(s), "p25": q[0], "p75": q[2], "min": s[0],
            "max": s[-1]}  # fmt: skip


def rank_text(value: float, peers: list[float]) -> dict:
    return {
        "cheaper": sum(1 for p in peers if p < value),
        "equal": sum(1 for p in peers if p == value),
        "dearer": sum(1 for p in peers if p > value),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, help="directory holding studio.sqlite3 (a COPY)")
    ap.add_argument("--repo", required=True, help="checkout (for summary.csv and src/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--deck-revision", default=DECK_REVISION)
    args = ap.parse_args()

    repo = Path(args.repo)
    sys.path.insert(0, str(repo / "src"))
    from commander_lab.studio import castability

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.store) / "studio.sqlite3"
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    summary_path = repo / RUBRIC_DIR / "summary.csv"
    v1 = {r["card"]: r for r in csv.DictReader(summary_path.open(encoding="utf-8"))}
    facts_by_name = {r["oracle_name"]: dict(r) for r in db.execute("SELECT * FROM card_fact")}
    pool = sorted(v1)
    missing = [n for n in pool if n not in facts_by_name]
    if missing:
        raise SystemExit(f"pool cards without card_fact: {missing[:5]} ...")

    # ---- roles (card_role = role set; claims give the origin per role) ----
    role_set: dict[str, set[str]] = defaultdict(set)
    for r in db.execute("SELECT oracle_id, role FROM card_role"):
        role_set[r["oracle_id"]].add(r["role"])
    role_origin: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in db.execute("SELECT DISTINCT oracle_id, role, role_origin FROM card_role_claim"):
        role_origin[(r["oracle_id"], r["role"])].add(r["role_origin"])

    # ---- rulings ----
    rulings: dict[str, list[dict]] = defaultdict(list)
    for r in db.execute(
        "SELECT oracle_id, ordinal, published_at, ruling_source, comment FROM card_ruling "
        "ORDER BY oracle_id, published_at, ordinal"
    ):
        rulings[r["oracle_id"]].append(
            {
                "published_at": r["published_at"],
                "source": r["ruling_source"],
                "comment": r["comment"],
            }
        )

    # ---- signals: split into rater-visible combo hint and holdout ----
    signals: dict[tuple[str, str], sqlite3.Row] = {}
    for r in db.execute(
        "SELECT commander_name, signal, card_name, value, numerator, denominator FROM card_signal "
        "WHERE signal IN (?, 'edhrec_global_inclusion', 'spellbook_shells') "
        "AND (commander_name = ? OR commander_name = '')",
        (DU_SIGNAL, COMMANDER),
    ):
        signals[(r["signal"], r["card_name"])] = r
    bracket_signals: dict[str, dict] = defaultdict(dict)
    for r in db.execute(
        "SELECT signal, card_name, numerator, denominator FROM card_signal "
        "WHERE signal LIKE 'decklist_universe:corpus:%' AND commander_name = ?",
        (COMMANDER,),
    ):
        bracket_signals[r["card_name"]][r["signal"].split(":", 2)[2]] = [
            r["numerator"], r["denominator"]
        ]  # fmt: skip
    deck_total = db.execute(
        "SELECT MAX(denominator) FROM card_signal WHERE signal = ? AND commander_name = ?",
        (DU_SIGNAL, COMMANDER),
    ).fetchone()[0]
    atlas = {
        r["oracle_id"]: dict(r)
        for r in db.execute(
            "SELECT oracle_id, times_brought, decks_running, live_inclusion_pct "
            "FROM playgroup_card_atlas WHERE format_mode = 'multiplayer'"
        )
    }

    # ---- reference deck: land base for castability ----
    deck_rows = db.execute(
        "SELECT k.zone, k.quantity, f.* FROM deck_revision_card k JOIN card_fact f USING (card_id) "
        "WHERE k.revision_id = ?",
        (args.deck_revision,),
    ).fetchall()
    if not deck_rows:
        raise SystemExit(f"deck revision {args.deck_revision} not in store")
    groups: Counter = Counter()
    lands = nonland = 0
    ref_names: set[str] = set()
    for r in deck_rows:
        ref_names.add(r["oracle_name"])
        if r["zone"] == "commander":
            continue
        row = dict(r)
        if "Land" in (row["type_line"] or "").split(" // ")[0]:
            lands += r["quantity"]
            col = castability.land_colours(row)
            groups[col if col is not None else frozenset()] += r["quantity"]
        else:
            nonland += r["quantity"]
    land_groups = sorted(groups.items(), key=lambda it: ("".join(sorted(it[0])), it[1]))
    deck_basis = {
        "revision": args.deck_revision,
        "lands": lands,
        "nonland": nonland,
        "candidate_added": 1,
        "land_groups": [["".join(sorted(c)) or "-", n] for c, n in land_groups],
    }

    # ---- per card facts (first pass) ----
    cards: list[dict] = []
    for name in pool:
        f = facts_by_name[name]
        oid = f["oracle_id"]
        faces = split_faces(f)
        front = faces[0]
        group, types = type_group(front["type_line"] or "")
        is_creature = "Creature" in (front["type_line"] or "").split("—")[0]
        is_land = group == "Land"
        p = pips(f["mana_cost"])
        need, hybrid_skipped = castability.requirement(f["mana_cost"] or "")
        keywords = json.loads(f["keywords"]) if f["keywords"] else []
        rset = sorted(role_set.get(oid, ()))
        primary = next((r for r in PRIMARY_ROLE_ORDER if r in rset), None)
        produced = f["produced_mana"] or ""
        card = {
            "facts_version": FACTS_VERSION,
            "oracle_id": oid,
            "name": f["oracle_name"],
            "layout": f["layout"],
            "faces": faces,
            "faces_parse_ok": not any(x.get("unsplit") for x in faces),
            "mana_cost": f["mana_cost"],
            "mana_value": f["mana_value"],
            "type_line": f["type_line"],
            "type_group": group,
            "types_front": types,
            "is_creature_front": is_creature,
            "is_land_front": is_land,
            "colour_identity": f["color_identity"] or "",
            "off_colour_identity": sorted(set(f["color_identity"] or "") - set(WUG)),
            "pips_front": p,
            "colours_in_cost": [c for c in "WUBRG" if p[c]],
            "colour_pips_total": sum(p[c] for c in "WUBRG"),
            "power": f["power"],
            "toughness": f["toughness"],
            "pt_total": pt_total(f["power"], f["toughness"]),
            "keywords": keywords,
            "produced_mana": produced,
            "game_changer": bool(f["game_changer"]),
            "has_oracle_text": bool((f["oracle_text"] or "").strip()),
            "roles": [{"role": r, "origins": sorted(role_origin.get((oid, r), ()))} for r in rset],
            "primary_role": primary,
            "rulings_n": len(rulings.get(oid, ())),
            "rulings": rulings.get(oid, []),
            "combo_hint_spellbook_shells_with_chulane": (
                signals[("spellbook_shells", name)]["value"]
                if ("spellbook_shells", name) in signals
                else None
            ),
            "_need": need,
            "_hybrid_skipped": hybrid_skipped,
            "_oracle_front": front["oracle_text"],
        }
        if is_land:
            card["land"] = {
                "enters_tapped": enters_tapped_class(front["oracle_text"]),
                "wug_colours_produced": sorted(set(produced) & set(WUG)),
                "produces_any_colour": len(set(produced) & set("WUBRG")) == 5,
                "fetches_land": bool(
                    re.search(r"search your library for[^.\n]*land", front["oracle_text"].lower())
                ),
            }
        cards.append(card)

    # ---- castability (Karsten, reference deck, same call as the Studio's own measurement) ----
    for c in cards:
        if c["is_land_front"]:
            c["castability"] = None
            continue
        turn = max(1, int(c["mana_value"] or 0))
        res = castability.colour_probability(land_groups, nonland + 1, c["_need"], turn)
        c["castability"] = {
            "call": "castability.colour_probability(land_groups, nonland+1, requirement(mana_cost)[0], max(1, mana_value))",
            "turn": turn,
            "need": res["need"],
            "sources": res["sources"],
            "p_land_drops": res["p_land_drops"],
            "p_colours_given_lands": res["p_colours_given_lands"],
            "p_on_curve": res["p_on_curve"],
            "colour_free_cost": not c["_need"],
            "hybrid_or_phyrexian_left_out": c["_hybrid_skipped"],
            "x_cost": c["pips_front"]["X"] > 0,
            "condition": res["condition"],
        }

    # ---- peer tables over the pool ----
    nonland_cards = [c for c in cards if not c["is_land_front"]]
    by_role: dict[str, list[dict]] = defaultdict(list)
    for c in nonland_cards:
        for r in c["roles"]:
            by_role[r["role"]].append(c)
    by_group: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        by_group[c["type_group"]].append(c)
    creatures = [c for c in cards if c["is_creature_front"]]
    body_by_mv: dict[float, list[int]] = defaultdict(list)
    for c in creatures:
        if c["pt_total"] is not None:
            body_by_mv[c["mana_value"]].append(c["pt_total"])
    land_cards = [c for c in cards if c["is_land_front"]]

    def land_key(c: dict) -> str:
        ld = c["land"]
        return f"{len(ld['wug_colours_produced'])}col_{ld['enters_tapped']}" + (
            "_fetch" if ld["fetches_land"] else ""
        )

    land_by_key: dict[str, list[dict]] = defaultdict(list)
    for c in land_cards:
        land_by_key[land_key(c)].append(c)

    for c in cards:
        peers: list[dict] = []
        if c["is_land_front"]:
            key = land_key(c)
            others = [x for x in land_by_key[key] if x["oracle_id"] != c["oracle_id"]]
            c["peer_benchmark"] = {
                "kind": "land",
                "land_peer_group": key,
                "n_peers": len(others),
                "note": "Länder haben keinen Manawert; verglichen wird in der Gruppe "
                "(Zahl WUG-Farben, tapped-Klasse, Fetch). Gruppen klein = Vorsicht.",
            }
            continue
        for r in c["roles"]:
            others = [
                x["mana_value"] for x in by_role[r["role"]] if x["oracle_id"] != c["oracle_id"]
            ]
            if not others:
                continue
            q = quantiles(others)
            peers.append(
                {
                    "role": r["role"],
                    "is_primary": r["role"] == c["primary_role"],
                    "n_peers": q["n"],
                    "median_mv": q["median"],
                    "p25_mv": q["p25"],
                    "p75_mv": q["p75"],
                    "this_mv": c["mana_value"],
                    "peers_cheaper_equal_dearer": rank_text(c["mana_value"], others),
                    "small_group": q["n"] < 8,
                }
            )
        gpeers = [x for x in by_group[c["type_group"]] if x["oracle_id"] != c["oracle_id"]]
        gq = quantiles([x["mana_value"] for x in gpeers])
        pb = c["peer_benchmark"] = {
            "kind": "nonland",
            "by_role": sorted(peers, key=lambda d: (not d["is_primary"], d["role"])),
            "type_group": {
                "group": c["type_group"],
                "n_peers": gq["n"],
                "median_mv": gq["median"],
                "this_mv": c["mana_value"],
            },
        }
        if c["is_creature_front"] and c["pt_total"] is not None:
            same = [
                v
                for x in creatures
                if x["oracle_id"] != c["oracle_id"]
                and x["mana_value"] == c["mana_value"]
                and x["pt_total"] is not None
                for v in [x["pt_total"]]
            ]
            if same:
                pb["body_same_mv"] = {
                    "n_peers": len(same),
                    "median_power_plus_toughness": statistics.median(same),
                    "this": c["pt_total"],
                    "peers_smaller_equal_larger": {
                        "smaller": sum(1 for v in same if v < c["pt_total"]),
                        "equal": sum(1 for v in same if v == c["pt_total"]),
                        "larger": sum(1 for v in same if v > c["pt_total"]),
                    },
                }

    # ---- write ----
    pool_bench = {
        "role_mv": {
            r: quantiles([c["mana_value"] for c in cs]) for r, cs in sorted(by_role.items())
        },
        "type_group_mv": {
            g: quantiles([c["mana_value"] for c in cs]) for g, cs in sorted(by_group.items())
        },
        "creature_body_by_mv": {
            str(int(mv)): quantiles([float(v) for v in vs]) for mv, vs in sorted(body_by_mv.items())
        },
        "land_groups": {k: len(v) for k, v in sorted(land_by_key.items())},
        "pool_size": len(cards),
        "nonland": len(nonland_cards),
        "lands": len(land_cards),
        "creatures_front": len(creatures),
        "deck_basis_for_castability": deck_basis,
    }
    (out / "pool_benchmarks.json").write_text(
        json.dumps(pool_bench, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    cards.sort(key=lambda c: c["oracle_id"])
    with (
        (out / "facts.jsonl").open("w", encoding="utf-8") as fh,
        (out / "usage_holdout.jsonl").open("w", encoding="utf-8") as uh,
    ):
        for c in cards:
            for k in [k for k in c if k.startswith("_")]:
                del c[k]
            assert_no_leak(c, c["name"])
            fh.write(json.dumps(c, sort_keys=True, ensure_ascii=False) + "\n")
            name = c["name"]
            du = signals.get((DU_SIGNAL, name))
            gl = signals.get(("edhrec_global_inclusion", name))
            ps = atlas.get(c["oracle_id"])
            v = v1[name]
            hold = {
                "oracle_id": c["oracle_id"],
                "name": name,
                "RATER_VISIBLE": False,
                # No signal row = counted zero: the source-deck corpus is counted completely
                # (Studio component status ZERO_COUNT), so the absence is a finding, not unknown.
                "deck_list_count": du["numerator"] if du else 0,
                "deck_list_total": du["denominator"] if du else deck_total,
                "deck_list_zero_by_absence": du is None,
                "deck_list_by_bracket": bracket_signals.get(name, {}),
                "edhrec_global_inclusion": [gl["numerator"], gl["denominator"]] if gl else None,
                "scryfall_edhrec_rank": facts_by_name[name]["edhrec_rank"],
                "playgroup_times_brought": ps["times_brought"] if ps else None,
                "playgroup_decks_running": ps["decks_running"] if ps else None,
                "in_reference_deck": name in ref_names,
                "v1": {
                    "H_mean": float(v["H_mean"]),
                    "H_sd": float(v["H_sd"]),
                    "raters": int(v["raters"]),
                    "anchor": v["anchor"] == "1",
                    **{k: float(v[k + "_mean"]) for k in "EFTRW"},
                },
            }
            uh.write(json.dumps(hold, sort_keys=True, ensure_ascii=False) + "\n")

    zero_n = sum(
        1
        for line in (out / "usage_holdout.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["deck_list_count"] == 0
    )
    manifest = {
        "facts_version": FACTS_VERSION,
        "cards": len(cards),
        "pool_matches_summary": len(cards) == len(v1),
        "store_sha256": sha256_file(db_path),
        "summary_csv_sha256": sha256_file(summary_path),
        "deck_basis": deck_basis,
        "counts": {
            "with_oracle_text": sum(c["has_oracle_text"] for c in cards),
            "without_oracle_text": sum(not c["has_oracle_text"] for c in cards),
            "lands": len(land_cards),
            "creatures_front": len(creatures),
            "multi_face": sum(len(c["faces"]) > 1 for c in cards),
            "faces_parse_failed": sum(not c["faces_parse_ok"] for c in cards),
            "with_role": sum(bool(c["roles"]) for c in cards),
            "without_role": sum(not c["roles"] for c in cards),
            "castability_defined": sum(
                bool(c["castability"]) and c["castability"]["p_on_curve"] is not None for c in cards
            ),
            "game_changer": sum(c["game_changer"] for c in cards),
            "rulings_cards": sum(c["rulings_n"] > 0 for c in cards),
            "off_colour_identity": sum(bool(c["off_colour_identity"]) for c in cards),
            "zero_source_decks": zero_n,
        },
        "outputs_sha256": {
            n: sha256_file(out / n)
            for n in ("facts.jsonl", "usage_holdout.jsonl", "pool_benchmarks.json")
        },
    }
    (out / "facts_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
