#!/usr/bin/env python3
"""Card blocks v2 for the Chulane rating v3 (plan Bewertung v3, I1, G1-G12) and the facts manifest.

Copied from ``chulane_rubric_v2_20261118/scripts/render_prompt.py`` and changed. Only the card
block is rendered here; the system prompt (guide, anchors, schema hint) belongs to the guide v3
step and is not part of this script. The card order, the oracle ids and the block structure stay
as in v2 (first lines ``CARD:`` and ``oracle_id:``, same line order); corrections change line
contents or add lines:

  G1 land facts with fetchable colours and how the fetched land enters
  G2 hybrid symbols counted apart; castability with each hybrid symbol as its better option
  G3 castability notes: X counted as 0; cost reduction or alternative cost in text not modelled
  G4 all rulings in full, by date then text; article pointers left out
  G5 pattern hits without role-label evidence and without etb_own on non-creatures
  G6 'Mechanics (rules summary)' from mechanics_glossary.json
  G7 power/toughness per face; keywords and mana with their face
  G8 'Loyalty: N' for planeswalkers
  G9 'Referenced card: X' with the Oracle text of a card the text names
  G10 token entries of the glossary
  G11 body benchmark note 'printed P/T; enters with counters'
  G12 the commander line (Chulane's Oracle text from GUIDE_v2.md) in every block

Usage (from the repository root):

  PYTHONPATH=src python3 data/research/chulane_rubric_v3_20261123/render_prompt_v2.py --write
  PYTHONPATH=src python3 data/research/chulane_rubric_v3_20261123/render_prompt_v2.py \
      --card "Wilt-Leaf Liege"

``--write`` builds facts_v2.jsonl and patterns_v2.jsonl (via extract_facts_v2 and
extract_patterns_v2) and facts_v2_manifest.json (input and output SHA-256, counts, the
corrections that changed each card, the drift check against the committed v2 blocks, the A2
recount and prompt_token_stats). No timestamps: two runs give the same bytes.

Token counts are ESTIMATES (characters / 3.5, as in v2).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

Card = dict[str, Any]

HERE = Path(__file__).resolve().parent
V2_DIR = "data/research/chulane_rubric_v2_20261118"
V3_DIR = "data/research/chulane_rubric_v3_20261123"
CHARS_PER_TOKEN = 3.5
V2_RULINGS_SHOWN = 4
V2_RULING_CHARS = 240
USER_FIRST_LINE = (
    "Rate this card. Answer with one JSON object that follows output_schema.json and nothing else."
)
COMMANDER_MARK = "The commander (exact Oracle text):"
UNKNOWN = "UNBEKANNT"


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class RenderContext:
    """What a block needs besides the card's facts and patterns."""

    commander: str
    glossary: Mapping[str, Mapping[str, Any]]
    disabled: frozenset[str] = field(default_factory=frozenset)

    def on(self, g: str) -> bool:
        return g not in self.disabled


def commander_line(guide: str) -> str:
    """Chulane's Oracle text exactly as GUIDE_v2.md quotes it (the '>' lines after the mark)."""
    block = guide.split(COMMANDER_MARK, 1)[1].split("\n\n")[1]
    return " ".join(ln[1:].strip() for ln in block.splitlines() if ln.startswith(">"))


def est_tokens(text: str) -> int:
    return round(len(text) / CHARS_PER_TOKEN)


def load_jsonl(path: Path) -> list[Card]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def fmt_pips(f: Card, ctx: RenderContext) -> str:
    p = f["pips_front"]
    if ctx.on("G2") and "hybrid_pips_front" in f:
        mono = f["mono_pips_front"]
        parts = [f"{c} x{mono[c]}" for c in "WUBRG" if mono[c]]
        parts += [
            f"{s} x{n} (hybrid: each pays with either part)"
            for s, n in sorted(f["hybrid_pips_front"].items())
        ]
        if p["generic"]:
            parts.append(f"generic {p['generic']}")
        if p["X"]:
            parts.append("X")
        if p["phyrexian_symbols"]:
            parts.append(f"{p['phyrexian_symbols']} Phyrexian symbol(s)")
        return ", ".join(parts) if parts else "no mana cost"
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


def fmt_keywords(f: Card, ctx: RenderContext) -> str:
    if not f["keywords"]:
        return "none"
    faces = f.get("keyword_faces") if ctx.on("G7") else None
    if not faces:
        return ", ".join(f["keywords"])
    out = []
    for kw in f["keywords"]:
        where = faces.get(kw) or []
        label = f" (face {', '.join(str(i) for i in where)})" if where and 1 not in where else ""
        out.append(kw + label)
    return ", ".join(out)


def fmt_produced(f: Card, ctx: RenderContext) -> str:
    if not f["produced_mana"]:
        return "none"
    faces = f.get("produced_mana_faces") if ctx.on("G7") else None
    if faces and 1 not in faces:
        return f"{f['produced_mana']} (face {', '.join(str(i) for i in faces)})"
    return str(f["produced_mana"])


def castability_line(c: Card, ctx: RenderContext) -> str:
    notes = []
    if ctx.on("G2") and c.get("hybrid_counted_as"):
        notes.append(
            " (hybrid symbols counted as their better option for this mana base: "
            + ", ".join(c["hybrid_counted_as"])
            + ")"
        )
    elif c["colour_free_cost"]:
        notes.append(" (cost has no coloured symbol)")
    if (
        ctx.on("G2")
        and c.get("hybrid_counted_as") is not None
        and c["hybrid_or_phyrexian_left_out"]
    ):
        notes.append(" (Phyrexian symbols not counted)")
    if ctx.on("G3"):
        if c.get("x_cost"):
            notes.append(" (X counted as 0)")
        if c.get("cost_reduction_in_text"):
            notes.append(" (cost reduction or alternative cost in the text not modelled)")
    return (
        f"On-time cast, reference mana base: turn {c['turn']}: P(land drops met) {c['p_land_drops']}, P(colours met given lands) {c['p_colours_given_lands']}, "
        f"P(both) {c['p_on_curve']}" + "".join(notes)
    )


def land_line(f: Card, ctx: RenderContext) -> str:
    ld = f["land"]
    makes = "/".join(ld["wug_colours_produced"]) or "no"
    extra = ""
    tail = ""
    if ctx.on("G1") and "fetchable_wug_colours" in ld:
        if ld["fetches_land"]:
            fetchable = "/".join(ld["fetchable_wug_colours"]) or "none of the deck's colours"
            extra = f" (fetchable: {fetchable})"
        if ld["fetches_land"] and ld.get("fetched_land_enters"):
            tail = f" | fetched land enters: {ld['fetched_land_enters']}"
    return (
        f"Land facts: makes {makes} of the deck's colours{extra} | enters: {ld['enters_tapped']} | "
        f"any colour of the identity: {'yes' if ld['produces_any_colour'] else 'no'} | fetches a land: {'yes' if ld['fetches_land'] else 'no'}"
        + tail
    )


def face_head(f: Card, face: Card, i: int, ctx: RenderContext) -> str:
    head = f"Face {i}: {face['name']} | {face['type_line']} | {face['mana_cost'] or 'no cost'}"
    if ctx.on("G7") and face.get("power_toughness"):
        head += f" | Power/toughness: {face['power_toughness']}"
    return head


def mechanics_lines(f: Card, ctx: RenderContext) -> list[str]:
    terms = [
        t
        for t in f.get("glossary_terms") or []
        if ctx.on("G10" if t.startswith("token_") else "G6")
    ]
    if not terms:
        return []
    out = ["Mechanics (rules summary, quoted from public card data):"]
    for t in terms:
        e = ctx.glossary[t]
        s = e["source"]
        out.append(f"  - {e['term']}: {e['text']} [{s['type']}, {s['card']}, {s['date']}]")
    return out


def reference_lines(f: Card, ctx: RenderContext) -> list[str]:
    if not ctx.on("G9"):
        return []
    out = []
    for r in f.get("referenced_cards") or []:
        head = f"Referenced card: {r['name']} — {r['mana_cost'] or 'no cost'} | {r['type_line']}"
        if r["power_toughness"]:
            head += f" | {r['power_toughness']}"
        text = str(r["oracle_text"]).strip() or "(no rules text)"
        out.append(head + ":\n  " + text.replace("\n", "\n  "))
    if f.get("referenced_cards_note"):
        out.append(f"Referenced card: none fixed ({f['referenced_cards_note']})")
    return out


def rulings_lines(f: Card, ctx: RenderContext) -> list[str]:
    out: list[str] = []
    if ctx.on("G4") and "rulings_dropped_article_pointer" in f:
        dropped = f["rulings_dropped_article_pointer"]
        note = f"; {dropped} ruling(s) that only point to an article left out" if dropped else ""
        if f["rulings_n"]:
            out.append(f"Rulings (all {f['rulings_n']}, by date{note}):")
            out += [
                f"  - {r['published_at']}: " + r["comment"].replace("\n", " ") for r in f["rulings"]
            ]
        elif dropped:
            out.append(f"Rulings: none with rule content{note}")
        return out
    if f["rulings_n"]:
        shown = sorted(f["rulings"], key=lambda r: (r["published_at"] or "",))[:V2_RULINGS_SHOWN]
        out.append(f"Rulings (shown {len(shown)} of {f['rulings_n']}):")
        for r in shown:
            t = r["comment"].replace("\n", " ")
            out.append(
                f"  - {r['published_at']}: "
                + (t if len(t) <= V2_RULING_CHARS else t[: V2_RULING_CHARS - 1] + "…")
            )
    return out


def card_block(f: Card, pat: Card | None, ctx: RenderContext) -> str:
    L = [f"CARD: {f['name']}", f"oracle_id: {f['oracle_id']}"]
    L.append(
        f"Mana cost: {f['mana_cost'] or '(none)'} | Mana value: {int(f['mana_value'] or 0)} | Cost symbols (front face): {fmt_pips(f, ctx)}"
    )
    L.append(
        f"Type line: {f['type_line']} | Group: {f['type_group']} | Colour identity: {f['colour_identity'] or 'colourless'}"
    )
    pt = f"{f['power']}/{f['toughness']}" if f["power"] is not None else "none"
    L.append(
        f"Power/toughness (front face): {pt} | Keywords: {fmt_keywords(f, ctx)} | Produces mana: {fmt_produced(f, ctx)}"
    )
    L.append(f"Game Changer: {'yes' if f['game_changer'] else 'no'} | Layout: {f['layout']}")
    if ctx.on("G8") and f.get("loyalty"):
        L.append(f"Loyalty: {f['loyalty']} (starting loyalty)")
    for i, face in enumerate(f["faces"], 1):
        head = face_head(f, face, i, ctx) if len(f["faces"]) > 1 else "Oracle text"
        text = face["oracle_text"].strip() or "(no rules text: a known fact, not missing data)"
        L.append(f"{head}:\n  " + text.replace("\n", "\n  "))
    L += reference_lines(f, ctx)
    L += mechanics_lines(f, ctx)
    if f["is_land_front"] and f.get("land"):
        L.append(land_line(f, ctx))
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
        L.append(castability_line(c, ctx))
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
            note = (
                " [printed P/T; this card enters with counters, see its text]"
                if ctx.on("G11") and f.get("enters_with_counters")
                else ""
            )
            L.append(
                f"Creature bodies at the same mana value: {b['n_peers']} peers, median power+toughness {b['median_power_plus_toughness']:g}; this card {b['this']}: {s['smaller']} smaller, {s['equal']} equal, {s['larger']} larger"
                + note
            )
    elif pb.get("kind") == "land":
        L.append(f"Land peer group {pb['land_peer_group']}: {pb['n_peers']} other pool lands")
    if f.get("combo_hint_spellbook_shells_with_chulane"):
        L.append(
            f"Combo hint (combination database, not a popularity figure): {int(f['combo_hint_spellbook_shells_with_chulane'])} listed combination line(s) with Chulane contain this card"
        )
    L += rulings_lines(f, ctx)
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
    if ctx.on("G12"):
        L.append(f"Commander (the deck's commander, for rule checks): {ctx.commander}")
    return "\n".join(L)


def user_prompt(f: Card, pat: Card | None, ctx: RenderContext) -> str:
    """v2 wrapper (first line unchanged); used only for the size estimate here."""
    return USER_FIRST_LINE + "\n\n" + card_block(f, pat, ctx) + "\n"


# ----------------------------------------------------------------------------- build and manifest


@dataclass
class Build:
    facts: list[Card]
    patterns: list[Card]
    blocks: dict[str, str]


def make_context(repo: Path, disabled: Iterable[str] = ()) -> RenderContext:
    guide = (repo / V2_DIR / "GUIDE_v2.md").read_text(encoding="utf-8")
    entries = json.loads((repo / V3_DIR / "mechanics_glossary.json").read_text("utf-8"))["entries"]
    return RenderContext(commander_line(guide), {e["id"]: e for e in entries}, frozenset(disabled))


def build(repo: Path, disabled: Iterable[str] = (), sources: Any = None) -> Build:
    ef = _load("extract_facts_v2")
    ep = _load("extract_patterns_v2")
    off = list(disabled)
    v2 = load_jsonl(repo / V2_DIR / "data" / "facts.jsonl")
    src = sources if sources is not None else ef.load_sources(repo)
    facts = ef.build_facts(v2, src, off)
    patterns = ep.build_patterns(facts, off)
    ctx = make_context(repo, off)
    pats = {p["oracle_id"]: p for p in patterns}
    blocks = {f["oracle_id"]: card_block(f, pats.get(f["oracle_id"]), ctx) for f in facts}
    return Build(facts, patterns, blocks)


def committed_v2_blocks(repo: Path) -> dict[str, str]:
    """The card blocks of run 2 (wave 1 and wave 2 inputs) by oracle id."""
    rub = repo / V2_DIR
    paths = sorted((rub / "second_run_20261122").glob("rr_input_*.jsonl")) + sorted(
        (rub / "second_run_full_20261122" / "rater").glob("rr2_input_*.jsonl")
    )
    out: dict[str, str] = {}
    for p in paths:
        for r in load_jsonl(p):
            out.setdefault(r["oracle_id"], r["card_block"])
    return out


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


INPUTS = (
    f"{V2_DIR}/data/facts.jsonl",
    f"{V2_DIR}/data/patterns.jsonl",
    f"{V2_DIR}/data/pool_benchmarks.json",
    f"{V2_DIR}/GUIDE_v2.md",
    "data/cards/xmage_card_facts.json",
    "data/cards/pilot_card_knowledge.json",
    "data/research/deckbuilder_1655/card_rulings_1655.jsonl",
    f"{V3_DIR}/face_overrides.json",
    f"{V3_DIR}/mechanics_glossary.json",
    f"{V3_DIR}/extract_facts_v2.py",
    f"{V3_DIR}/extract_patterns_v2.py",
    f"{V3_DIR}/render_prompt_v2.py",
    f"{V3_DIR}/a2_recount_v2.py",
    "data/research/chulane_rubric_v3_20261123/phaseA_scripts/A2/a2_inventory.py",
    "src/commander_lab/studio/castability.py",
    "src/commander_lab/studio/roles.py",
)


def token_stats(rows: list[tuple[int, str]]) -> dict[str, Any]:
    toks = sorted(round(c / CHARS_PER_TOKEN) for c, _ in rows)

    def q(p: float) -> int:
        return toks[min(len(toks) - 1, int(p * len(toks)))]

    return {
        "n_cards": len(toks),
        "min": toks[0],
        "median": statistics.median(toks),
        "mean": round(statistics.mean(toks)),
        "p90": q(0.9),
        "p99": q(0.99),
        "max": toks[-1],
        "sum": sum(toks),
        "largest_cards": [n for _, n in sorted(rows, reverse=True)[:5]],
    }


def castability_note(facts: list[Card], src: Any) -> Card:
    """Which carried facts-1 castability values today's Studio module would compute differently
    (an open decision for the lead: recomputing them is not in the G table)."""
    from commander_lab.studio import castability

    differ: list[tuple[str, float]] = []
    for f in facts:
        c = f.get("castability")
        if not c or c.get("hybrid_counted_as"):
            continue
        need, _ = castability.requirement(f["mana_cost"] or "")
        res = castability.colour_probability(src.land_groups, src.nonland + 1, need, c["turn"])
        if (
            res["p_on_curve"] != c["p_on_curve"]
            or res["p_colours_given_lands"] != c["p_colours_given_lands"]
        ):
            new_p = res["p_on_curve"]
            assert isinstance(new_p, float)
            differ.append((f["name"], round(float(c["p_on_curve"]) - new_p, 4)))
    hybrid_multi = sum(
        1
        for f in facts
        if (f.get("castability") or {}).get("hybrid_counted_as")
        and len(f["castability"]["need"]) >= 2
    )
    return {
        "rule": "G2 recomputes only the hybrid cards with today's module; all other spells carry "
        "their facts-1 values (field castability.values_from)",
        "carried_values_today_module_differs": len(differ),
        "carried_values_differ_cards": sorted(n for n, _ in differ),
        "largest_p_on_curve_overstatement": max((d for _, d in differ), default=0.0),
        "hybrid_cards_with_need_of_two_or_more_colours": hybrid_multi,
        "decision_open": "recomputing all spells would be a deviation from the G table (plan "
        "section 9); to be settled before facts_v2 enters the pilot inputs",
    }


def unknown_values(facts: list[Card]) -> list[dict[str, str]]:
    out = []
    for f in facts:
        for i, face in enumerate(f["faces"], 1):
            if face.get("power_toughness") == UNKNOWN:
                out.append({"card": f["name"], "field": f"face {i} power/toughness"})
        if f.get("loyalty") == UNKNOWN:
            out.append({"card": f["name"], "field": "loyalty"})
    return out


def manifest(repo: Path, full: Build, out_files: Mapping[str, bytes]) -> Card:
    ef = _load("extract_facts_v2")
    rc = _load("a2_recount_v2")
    src = ef.load_sources(repo)
    v2_blocks = committed_v2_blocks(repo)
    order = [f["oracle_id"] for f in full.facts]
    names = {f["oracle_id"]: f["name"] for f in full.facts}
    all_off = build(repo, ef.CORRECTIONS, src)
    drift = [o for o in order if all_off.blocks[o] != v2_blocks.get(o)]
    changed_by: dict[str, list[str]] = {o: [] for o in order}
    per_g: dict[str, int] = {}
    for g in ef.CORRECTIONS:
        alt = build(repo, [g], src)
        hit = [o for o in order if alt.blocks[o] != full.blocks[o]]
        per_g[g] = len(hit)
        for o in hit:
            changed_by[o].append(g)
    changed = [o for o in order if full.blocks[o] != v2_blocks.get(o)]
    unattributed = [o for o in changed if not changed_by[o]]
    pats = {p["oracle_id"]: p for p in full.patterns}
    v2_pats = {p["oracle_id"]: p for p in load_jsonl(repo / V2_DIR / "data" / "patterns.jsonl")}
    v2_ctx = make_context(repo, ef.CORRECTIONS)
    v2_facts = {f["oracle_id"]: f for f in load_jsonl(repo / V2_DIR / "data" / "facts.jsonl")}
    v2_rows = [(len(user_prompt(v2_facts[o], v2_pats.get(o), v2_ctx)), names[o]) for o in order]
    ctx = make_context(repo)
    v3_rows = [(len(user_prompt(f, pats.get(f["oracle_id"]), ctx)), f["name"]) for f in full.facts]
    st_v2, st_v3 = token_stats(v2_rows), token_stats(v3_rows)
    recount = rc.recount(repo, full.facts, full.patterns, full.blocks)
    cast_note = castability_note(full.facts, src)
    orphan = sorted(
        p["name"]
        for p in full.patterns
        if "etb_own_draw" in p["hits"]
        and not next(f for f in full.facts if f["oracle_id"] == p["oracle_id"])["is_creature_front"]
    )
    return {
        "facts_version": ef.FACTS_VERSION,
        "plan": "docs/analysis-reports/rating_v3_plan_20261123.md, I1 (G1-G12), step 2 of section 8",
        "cards": len(order),
        "card_order": "v2 order (oracle_id ascending), oracle ids unchanged",
        "inputs_sha256": {p: sha256_file(repo / p) for p in INPUTS},
        "outputs_sha256": {n: sha256_bytes(b) for n, b in sorted(out_files.items())},
        "drift_check_all_corrections_off": {
            "compared_with": "card_block of rr_input_*.jsonl and rr2_input_*.jsonl (run 2)",
            "cards_equal": len(order) - len(drift),
            "cards_differ": len(drift),
        },
        "counts": {
            "cards_changed_against_v2_block": len(changed),
            "cards_changed_per_correction": per_g,
            "cards_changed_without_single_attribution": len(unattributed),
            "lands_fetching": sum(
                1 for f in full.facts if f.get("land") and f["land"]["fetches_land"]
            ),
            "hybrid_cost_cards": sum(1 for f in full.facts if f.get("hybrid_pips_front")),
            "x_cost_cards": sum(
                1 for f in full.facts if (f.get("castability") or {}).get("x_cost")
            ),
            "cost_reduction_in_text_cards": sum(
                1 for f in full.facts if (f.get("castability") or {}).get("cost_reduction_in_text")
            ),
            "rulings_shown_total": sum(f["rulings_n"] for f in full.facts),
            "rulings_article_pointers_left_out": sum(
                f.get("rulings_dropped_article_pointer", 0) for f in full.facts
            ),
            "patterns_hidden_hits_cards": sum(1 for p in full.patterns if p.get("hidden_hits")),
            "glossary_cards": sum(1 for f in full.facts if f.get("glossary_terms")),
            "faces_with_power_toughness": sum(
                1 for f in full.facts for x in f["faces"][1:] if x.get("power_toughness")
            ),
            "planeswalkers_with_loyalty": sum(
                1 for f in full.facts if f.get("loyalty") not in (None, UNKNOWN)
            ),
            "cards_with_referenced_card": sum(1 for f in full.facts if f.get("referenced_cards")),
            "cards_enters_with_counters": sum(
                1 for f in full.facts if f.get("enters_with_counters")
            ),
            "land_peer_groups": ef.land_peer_groups(full.facts),
            "glossary_entries": len(src.glossary),
            "face_overrides_rows": len(src.overrides),
        },
        "unknown_values": unknown_values(full.facts),
        "castability_method": cast_note,
        "open_points": {
            "etb_own_draw_on_noncreatures_still_shown": orphan,
            "note": "G5 as in the plan hides only etb_own on non-creatures; etb_own_draw stays",
        },
        "prompt_token_stats": {
            "chars_per_token_assumed": CHARS_PER_TOKEN,
            "note": "estimates of the v2 user prompt (first line plus card block); the system prompt is not part of this step",
            "v2_blocks": st_v2,
            "v2prime_blocks": st_v3,
            "growth_sum_tokens": st_v3["sum"] - st_v2["sum"],
            "growth_median_tokens": st_v3["median"] - st_v2["median"],
        },
        "a2_recount": recount,
        "changed_by_card": [
            {"oracle_id": o, "name": names[o], "changed_by": changed_by[o]} for o in order
        ],
    }


def dumps_json(obj: object) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def write_all(repo: Path, out: Path) -> dict[str, bytes]:
    ef = _load("extract_facts_v2")
    full = build(repo)
    files = {
        "facts_v2.jsonl": ef.dumps_jsonl(full.facts).encode("utf-8"),
        "patterns_v2.jsonl": "".join(
            json.dumps(p, sort_keys=True, ensure_ascii=False) + "\n" for p in full.patterns
        ).encode("utf-8"),
    }
    files["facts_v2_manifest.json"] = dumps_json(manifest(repo, full, files)).encode("utf-8")
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out / name).write_bytes(data)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default=None, help="default: the folder of this script")
    ap.add_argument("--card")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--disable", default="")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo / "src"))
    if args.card:
        b = build(repo, [g.strip() for g in args.disable.split(",") if g.strip()])
        oid = next(f["oracle_id"] for f in b.facts if f["name"] == args.card)
        print(b.blocks[oid])
    if args.write:
        files = write_all(repo, Path(args.out) if args.out else HERE)
        print(json.dumps({n: sha256_bytes(d) for n, d in files.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
