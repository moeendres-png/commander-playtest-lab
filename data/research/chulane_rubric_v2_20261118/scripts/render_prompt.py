#!/usr/bin/env python3
"""Renders the rater prompt of the rubric v2 and measures its size (design draft).

  python3 render_prompt.py --card "Shrieking Drake"                   # print one prompt
  python3 render_prompt.py --stats                                    # size over all 922 cards
  python3 render_prompt.py --check-leave-one-out                      # anchors vs pilot A cards

Inputs: <dir>/GUIDE_v2.md, <dir>/anchors.json, <dir>/data/facts.jsonl, <dir>/data/patterns.jsonl.
Nothing from usage_holdout.jsonl or pilot_sample.json is ever read into a prompt (the pilot file is
read only by --check-leave-one-out to know which cards are stratum A).

Token counts are ESTIMATES (characters / CHARS_PER_TOKEN, a conservative English/MTG-symbol ratio);
replace them with the API's token counter in the first pilot call.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_anchors as BA

CHARS_PER_TOKEN = 3.5
RULINGS_SHOWN = 4
RULING_CHARS = 240
USER_FIRST_LINE = (
    "Rate this card. Answer with one JSON object that follows output_schema.json and nothing else."
)
SCHEMA_HINT = (
    "Output rules: scores are multiples of 5 from 0 to 100 for E, F, T, R, K, D, H (higher is better, D = low deck cost, "
    "H is your own judgement, not the mean); notes: one phrase (at most 15 words) per score; reason: 2 to 3 sentences, "
    "what the card really does and what follows; confidence: high|medium|low; uncertainty: text (empty only for high); "
    "rule_claims: list of {quote (literal from the card block), interaction, claim, basis}; pattern_check: one entry per "
    "pattern hit shown {rule_id, verdict: correct|wrong|irrelevant}; judged_as: land|spell; schema: rubric-v2-card-rating-1; "
    "oracle_id and card copied from the block."
)


def est_tokens(text: str) -> int:
    return round(len(text) / CHARS_PER_TOKEN)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def system_prompt(guide: str, anchors: dict, leave_out: str | None = None) -> str:
    """GUIDE_v2.md with the anchor region replaced by the rendered anchors (leave-one-anchor-out)."""
    block = (
        BA.anchor_block(anchors["spell"], leave_out, "Spells")
        + "\n"
        + BA.anchor_block(anchors["land"], leave_out, "Lands (judge a land as a land)")
    )
    pre, _, rest = guide.partition("<!-- ANCHORS:BEGIN -->\n")
    _, _, post = rest.partition("<!-- ANCHORS:END -->\n")
    note = ""
    if leave_out:
        note = "(The card you are rating is not in the anchor tables.)\n\n"
    return (
        pre
        + "<!-- anchors -->\n"
        + note
        + block
        + "\n"
        + post.split("\nThe four checks")[0]
        + "\n"
        + SCHEMA_HINT
        + "\n"
    )


def fmt_pips(f: dict) -> str:
    p = f["pips_front"]
    parts = [f"{c} x{p[c]}" for c in "WUBRG" if p[c]]
    if p["generic"]:
        parts.append(f"generic {p['generic']}")
    if p["X"]:
        parts.append("X")
    if p["hybrid_symbols"]:
        parts.append(f"{p['hybrid_symbols']} hybrid symbol(s)")
    if p["phyrexian_symbols"]:
        parts.append(f"{p['phyrexian_symbols']} Phyrexian symbol(s)")
    return ", ".join(parts) if parts else "no mana cost"


def card_block(f: dict, pat: dict | None) -> str:
    L = [f"CARD: {f['name']}", f"oracle_id: {f['oracle_id']}"]
    L.append(
        f"Mana cost: {f['mana_cost'] or '(none)'} | Mana value: {int(f['mana_value'] or 0)} | Cost symbols (front face): {fmt_pips(f)}"
    )
    L.append(
        f"Type line: {f['type_line']} | Group: {f['type_group']} | Colour identity: {f['colour_identity'] or 'colourless'}"
    )
    pt = f"{f['power']}/{f['toughness']}" if f["power"] is not None else "none"
    L.append(
        f"Power/toughness (front face): {pt} | Keywords: {', '.join(f['keywords']) or 'none'} | Produces mana: {f['produced_mana'] or 'none'}"
    )
    L.append(f"Game Changer: {'yes' if f['game_changer'] else 'no'} | Layout: {f['layout']}")
    for i, face in enumerate(f["faces"], 1):
        head = (
            f"Face {i}: {face['name']} | {face['type_line']} | {face['mana_cost'] or 'no cost'}"
            if len(f["faces"]) > 1
            else "Oracle text"
        )
        text = face["oracle_text"].strip() or "(no rules text: a known fact, not missing data)"
        L.append(f"{head}:\n  " + text.replace("\n", "\n  "))
    if f["is_land_front"] and f.get("land"):
        ld = f["land"]
        L.append(
            f"Land facts: makes {'/'.join(ld['wug_colours_produced']) or 'no'} of the deck's colours | enters: {ld['enters_tapped']} | "
            f"any colour of the identity: {'yes' if ld['produces_any_colour'] else 'no'} | fetches a land: {'yes' if ld['fetches_land'] else 'no'}"
        )
    if f["roles"]:
        L.append(
            "Roles (labels from a tagger and a text rule; they can be wrong): "
            + "; ".join(r["role"] for r in f["roles"])
            + (f" | main: {f['primary_role']}" if f["primary_role"] else "")
        )
    else:
        L.append("Roles: none labelled")
    c = f.get("castability")
    if c:
        extra = " (cost has no coloured symbol)" if c["colour_free_cost"] else ""
        L.append(
            f"On-time cast, reference mana base: turn {c['turn']}: P(land drops met) {c['p_land_drops']}, P(colours met given lands) {c['p_colours_given_lands']}, "
            f"P(both) {c['p_on_curve']}{extra}"
        )
    pb = f.get("peer_benchmark", {})
    if pb.get("kind") == "nonland":
        for r in pb["by_role"][:3]:
            d = r["peers_cheaper_equal_dearer"]
            L.append(
                f"Peers with role {r['role']}{' (main)' if r['is_primary'] else ''}: {r['n_peers']} other pool cards, median mana value {r['median_mv']:g} "
                f"(quartiles {r['p25_mv']:g} to {r['p75_mv']:g}); this card {r['this_mv']:g}: {d['cheaper']} cheaper, {d['equal']} equal, {d['dearer']} dearer"
                + (" [small group]" if r["small_group"] else "")
            )
        tg = pb["type_group"]
        L.append(
            f"Peers of type group {tg['group']}: {tg['n_peers']} other pool cards, median mana value {tg['median_mv']:g}; this card {tg['this_mv']:g}"
        )
        if "body_same_mv" in pb:
            b = pb["body_same_mv"]
            s = b["peers_smaller_equal_larger"]
            L.append(
                f"Creature bodies at the same mana value: {b['n_peers']} peers, median power+toughness {b['median_power_plus_toughness']:g}; this card {b['this']}: {s['smaller']} smaller, {s['equal']} equal, {s['larger']} larger"
            )
    elif pb.get("kind") == "land":
        L.append(f"Land peer group {pb['land_peer_group']}: {pb['n_peers']} other pool lands")
    if f.get("combo_hint_spellbook_shells_with_chulane"):
        L.append(
            f"Combo hint (combination database, not a popularity figure): {int(f['combo_hint_spellbook_shells_with_chulane'])} listed combination line(s) with Chulane contain this card"
        )
    if f["rulings_n"]:
        shown = sorted(f["rulings"], key=lambda r: (r["published_at"] or "",))[:RULINGS_SHOWN]
        L.append(f"Rulings (shown {len(shown)} of {f['rulings_n']}):")
        for r in shown:
            t = r["comment"].replace("\n", " ")
            L.append(
                f"  - {r['published_at']}: "
                + (t if len(t) <= RULING_CHARS else t[: RULING_CHARS - 1] + "…")
            )
    hits = pat["hits"] if pat else {}
    if hits:
        L.append(
            "Pattern hits (rule-based hints; '~' stands for this card; check each in pattern_check):"
        )
        for rid in sorted(hits):
            h = hits[rid][0]
            L.append(
                f'  - {rid}: "{h["line"]}"'
                + (f" (+{len(hits[rid]) - 1} more)" if len(hits[rid]) > 1 else "")
            )
    else:
        L.append("Pattern hits: none")
    return "\n".join(L)


def user_prompt(f: dict, pat: dict | None) -> str:
    return USER_FIRST_LINE + "\n\n" + card_block(f, pat) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="folder with GUIDE_v2.md and data/ (default: above scripts/)")
    ap.add_argument("--card")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--check-leave-one-out", action="store_true")
    args = ap.parse_args()
    d = Path(args.dir) if args.dir else Path(__file__).resolve().parent.parent
    guide = (d / "GUIDE_v2.md").read_text(encoding="utf-8")
    anchors = json.loads((d / "anchors.json").read_text(encoding="utf-8"))
    facts = {r["name"]: r for r in load_jsonl(d / "data" / "facts.jsonl")}
    pats = {r["name"]: r for r in load_jsonl(d / "data" / "patterns.jsonl")}

    if args.card:
        print(
            system_prompt(
                guide,
                anchors,
                args.card
                if args.card
                in {
                    a["card"]
                    for t in (anchors["spell"], anchors["land"])
                    for rows in t.values()
                    for a in rows
                    if a["kind"] == "v1_fixed"
                }
                else None,
            )
        )
        print("=" * 30 + " USER " + "=" * 30)
        print(user_prompt(facts[args.card], pats.get(args.card)))
    if args.check_leave_one_out:
        pilot = json.loads((d / "pilot_sample.json").read_text(encoding="utf-8"))["cards"]
        bad = []
        for c in pilot:
            sp = system_prompt(guide, anchors, c["name"] if c["stratum"] == "A" else None)
            in_block = sp.split("<!-- anchors -->")[1]
            if c["stratum"] == "A" and re.search(rf"\| [^|]*\b{re.escape(c['name'])} \(", in_block):
                bad.append(("A card still in its own anchor table", c["name"]))
            if c["stratum"] != "A" and c["name"] in in_block:
                bad.append(("pilot card named in the anchor tables", c["name"]))
            # whole system prompt (guide text included): a card never names itself, and no
            # non-anchor pilot card is named anywhere
            if c["name"] in sp:
                bad.append(("rated card named in its own system prompt", c["name"]))
            for other in pilot:
                if other["stratum"] != "A" and other["name"] in sp:
                    bad.append(
                        (f"pilot card {other['name']} named in the system prompt of", c["name"])
                    )
        print("leave-one-out check:", bad or "OK")
    if args.stats:
        sys_chars = len(system_prompt(guide, anchors))
        users = []
        for n, f in facts.items():
            users.append((len(user_prompt(f, pats.get(n))), n))
        toks = sorted(round(c / CHARS_PER_TOKEN) for c, _ in users)
        q = lambda p: toks[min(len(toks) - 1, int(p * len(toks)))]  # noqa: E731
        stats = {
            "chars_per_token_assumed": CHARS_PER_TOKEN,
            "note": "estimates, replace with the API token counter in the first pilot call",
            "system_prompt_tokens": est_tokens("x" * sys_chars),
            "user_prompt_tokens": {
                "n_cards": len(toks),
                "min": toks[0],
                "median": statistics.median(toks),
                "mean": round(statistics.mean(toks)),
                "p90": q(0.9),
                "p99": q(0.99),
                "max": toks[-1],
            },
            "largest_cards": [n for _, n in sorted(users, reverse=True)[:5]],
            "output_tokens_assumed_per_card": 420,
            "output_tokens_basis": "example_output.json is about 330 tokens at this ratio; 420 allows a longer reason and up to 3 rule claims",
        }
        (d / "data" / "prompt_token_stats.json").write_text(
            json.dumps(stats, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
