#!/usr/bin/env python3
"""Card facts v2 ("facts-2") for the Chulane rating v3 (plan Bewertung v3, I1, G1-G4, G6-G11).

Copied from ``chulane_rubric_v2_20261118/scripts/extract_facts.py`` and changed. The v2 script
read a copy of the Studio store, which is not in the repository; this version therefore starts
from the committed v2 facts (``facts.jsonl``, built from that store) and applies the corrections
of the plan table I1 to them. The v2 files stay unchanged (they keep run 1 and run 2
reproducible). Inputs, all in the repository:

  chulane_rubric_v2_20261118/data/facts.jsonl            v2 facts (card order, oracle ids, rulings)
  chulane_rubric_v2_20261118/data/pool_benchmarks.json   reference land groups (castability)
  data/cards/xmage_card_facts.json                       planeswalker loyalty (G8)
  data/cards/pilot_card_knowledge.json                   Oracle text of referenced cards (G9)
  chulane_rubric_v3_20261123/face_overrides.json         back-face power/toughness (G7)
  chulane_rubric_v3_20261123/mechanics_glossary.json     glossary terms detected per card (G6, G10)
  src/commander_lab/studio/castability.py                castability and land classes (reuse)

Usage (from the repository root):

  PYTHONPATH=src python3 data/research/chulane_rubric_v3_20261123/extract_facts_v2.py \
      --repo . --out data/research/chulane_rubric_v3_20261123 [--disable G1,G2]

Every correction is a switch (``--disable``): with all of them disabled the facts render to the
v2 card blocks byte for byte (drift check in ``render_prompt_v2.py``). No timestamps, no
randomness: two runs give the same bytes. No usage, popularity, price or rating data is read.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Card = dict[str, Any]

FACTS_VERSION = "facts-2"
CORRECTIONS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12")
WUG = "WUG"
V2_DIR = "data/research/chulane_rubric_v2_20261118"
V3_DIR = "data/research/chulane_rubric_v3_20261123"
UNKNOWN = "UNBEKANNT"
# G2: only the hybrid cards are recomputed; every other spell keeps its facts-1 values. The
# Studio module has since changed for costs of two or more colours (one land pays one symbol,
# #1751), so a carried value of such a cost can be higher than today's module gives.
CARRIED = "facts-1 (carried; computed before the castability change of #1751)"
RECOMPUTED = "recomputed with src/commander_lab/studio/castability.py of this commit"
_SYMBOL = re.compile(r"\{([^}]+)\}")
_BASIC_COLOUR = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}

# Leak guard (as in v2): no key of a rater-visible record may name usage, popularity, price or a
# v1 rating. The extraction stops when one does. (Values are not scanned.)
LEAK_KEYS = re.compile(
    r"edhrec|deck_list|decklist|rubric|h_mean|h_sd|times_brought|playgroup|inclusion|price|usd|"
    r"usage|popular|v1|in_reference_deck|source_decks|win_?rate",
    re.IGNORECASE,
)

# G1: the v2 regex (extract_facts.py:378) and the wider land search of this version.
V2_FETCH = re.compile(r"search your library for[^.\n]*land")
_FETCH_SPEC = re.compile(
    r"search your library for ([^.]*?)\s*cards?\b[^.]*?onto the battlefield", re.IGNORECASE
)
_FETCHED_TAPPED = re.compile(r"onto the battlefield tapped", re.IGNORECASE)

# G3: alternative costs and self cost reduction in the rules text (the A2 detector, a2_inventory).
_ALT_COST = re.compile(
    r"\bconvoke\b|\baffinity\b|\bimprovise\b|\bdelve\b|costs? \{\d+\} less|costs? \{x\} less|"
    r"less to cast|without paying its mana cost|you may pay .* rather than pay|\bemerge\b|"
    r"\bevoke\b|\bdash\b|\bsurge\b|\bmiracle\b|\bmadness\b|\bforetell\b|\bblitz\b|\bprototype\b"
)
_ALT_COST_WORDS = (
    " this spell", "convoke", "affinity", "improvise", "delve", "rather than pay", "evoke", "dash",
    "foretell", "prototype", "blitz", "emerge",
)  # fmt: skip
_ALT_COST_STRICT = re.compile(
    r"\bconvoke\b|\baffinity\b|\bimprovise\b|\bdelve\b|costs? \{\d+\} less|rather than pay|\bevoke\b"
)

# G4: a ruling that is only a pointer to an article carries no rule.
ARTICLE_POINTER = re.compile(
    r"^For more information on [^.]*, see the [^()]* article \(https?://[^)\s]+\)\.$"
)

# G11: the creature enters with counters (the A2 detector, a2_inventory).
_ETB_PLUS = re.compile(
    r"(this creature|~|it) enters with (a|an|one|two|three|four|five|x|\d+) [^.]*\+1/\+1 counter"
    r"|^enters with|\benters with (x|\d+|a|an|one|two|three|four|five) \+1/\+1 counters?",
    re.MULTILINE,
)
_ETB_OTHER = re.compile(r"enters with [^.]*-1/-1 counter|enters with .* counters? on it")

# G9: a fixed card name in the rules text.
_NAMED = re.compile(r"\bnamed ")
_TOKEN_NAMED = re.compile(r"\btokens? named $")


@dataclass(frozen=True)
class Sources:
    """Repository card data the corrections read (loaded once)."""

    land_groups: list[tuple[frozenset[str], int]]
    nonland: int
    xmage: Mapping[str, Mapping[str, Any]]
    pck: Mapping[str, Mapping[str, Any]]
    overrides: list[Mapping[str, Any]]
    glossary: list[Mapping[str, Any]]


def assert_no_leak(obj: object, where: str = "") -> None:
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


def load_jsonl(path: Path) -> list[Card]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_sources(repo: Path) -> Sources:
    bench = json.loads((repo / V2_DIR / "data" / "pool_benchmarks.json").read_text("utf-8"))
    basis = bench["deck_basis_for_castability"]
    groups = [(frozenset() if c == "-" else frozenset(c), int(n)) for c, n in basis["land_groups"]]
    xmage = json.loads((repo / "data/cards/xmage_card_facts.json").read_text("utf-8"))["cards"]
    pck = json.loads((repo / "data/cards/pilot_card_knowledge.json").read_text("utf-8"))["cards"]
    overrides = json.loads((repo / V3_DIR / "face_overrides.json").read_text("utf-8"))["rows"]
    glossary = json.loads((repo / V3_DIR / "mechanics_glossary.json").read_text("utf-8"))["entries"]
    return Sources(groups, int(basis["nonland"]), xmage, pck, overrides, glossary)


def strip_reminder(text: str) -> str:
    pat = re.compile(r"\([^()]*\)")
    while True:
        new = pat.sub(" ", text)
        if new == text:
            return new
        text = new


def faces_text(card: Card) -> str:
    return "\n".join(str(face["oracle_text"]) for face in card["faces"])


# ----------------------------------------------------------------------------- G1 land facts


def fetch_info(card: Card) -> dict[str, Any]:
    """Whether the land's front text searches the library for a land, the deck colours the
    fetched land can make (by basic land type; 'basic land card' = every basic type), and how
    the fetched land enters. Reuses ``castability.classify_land`` and ``tapped_class`` (Studio,
    builder audit WP-2/WP-4); a search those do not read (for example one bound to a target)
    falls back to the spec text of the search."""
    from commander_lab.studio import castability

    front = card["faces"][0]
    text = str(front["oracle_text"] or "")
    row = {
        "oracle_text": text,
        "produced_mana": card["produced_mana"],
        "type_line": card["type_line"],
        "oracle_name": card["name"],
    }
    info = castability.classify_land(row)
    types: set[str] = set()
    found = False
    alternatives = info["search"]
    if info["class"] == castability.LAND_SEARCH and isinstance(alternatives, tuple):
        found = True
        for _basic, kinds in alternatives:
            types |= set(_BASIC_COLOUR) if kinds is None else set(kinds)
    else:
        for m in _FETCH_SPEC.finditer(strip_reminder(text)):
            spec = m.group(1)
            named = {t for t in _BASIC_COLOUR if re.search(rf"\b{t}\b", spec)}
            if re.search(r"\bbasic land\b|\bland\b", spec, re.IGNORECASE) or named:
                found = True
                types |= named or set(_BASIC_COLOUR)
    v2_flag = bool(V2_FETCH.search(text.lower()))
    fetches = v2_flag or found
    colours = sorted({_BASIC_COLOUR[t] for t in types} & set(WUG)) if found else []
    tapped = castability.tapped_class(row)["fetch_quote"] or _FETCHED_TAPPED.search(text)
    return {
        "fetches_land": fetches,
        "fetchable_wug_colours": colours,
        "fetched_land_enters": ("tapped" if tapped else "untapped") if fetches else None,
    }


def land_key(card: Card) -> str:
    ld = card["land"]
    return f"{len(ld['wug_colours_produced'])}col_{ld['enters_tapped']}" + (
        "_fetch" if ld["fetches_land"] else ""
    )


def apply_g1(cards: list[Card]) -> None:
    lands = [c for c in cards if c["is_land_front"] and c.get("land")]
    for c in lands:
        info = fetch_info(c)
        ld = c["land"]
        direct = sorted(set(c["produced_mana"] or "") & set(WUG))
        ld["fetches_land"] = info["fetches_land"]
        ld["fetchable_wug_colours"] = info["fetchable_wug_colours"]
        ld["wug_colours_produced"] = sorted(set(direct) | set(info["fetchable_wug_colours"]))
        ld["wug_colours_direct"] = direct
        ld["fetched_land_enters"] = info["fetched_land_enters"]
    by_key: dict[str, list[Card]] = defaultdict(list)
    for c in lands:
        by_key[land_key(c)].append(c)
    for c in lands:
        key = land_key(c)
        pb = c["peer_benchmark"]
        pb["land_peer_group"] = key
        pb["n_peers"] = sum(1 for x in by_key[key] if x["oracle_id"] != c["oracle_id"])


# ----------------------------------------------------------------------------- G2 / G3 castability


def hybrid_pips(mana_cost: str | None) -> tuple[dict[str, int], dict[str, int]]:
    """Front-face pips with hybrid symbols counted apart: (mono-coloured pips per colour,
    hybrid symbols per symbol text such as 'G/W'). Phyrexian symbols are not hybrid here."""
    mono = {c: 0 for c in "WUBRG"}
    hybrid: dict[str, int] = {}
    if not mana_cost:
        return mono, hybrid
    for sym in _SYMBOL.findall(mana_cost.split(" // ")[0]):
        if len(sym) == 1 and sym in "WUBRG":
            mono[sym] += 1
        elif "/" in sym and "P" not in sym.split("/"):
            hybrid[sym] = hybrid.get(sym, 0) + 1
    return mono, hybrid


def hybrid_castability(card: Card, src: Sources) -> dict[str, Any] | None:
    """Castability with each hybrid symbol counted as the option (one of its colours, or its
    generic part for {2/W}) that gives the highest P(both); ties go to the first option in
    symbol order. None for a cost without hybrid symbols."""
    from commander_lab.studio import castability

    cost = str(card["mana_cost"] or "")
    symbols = [s for s in _SYMBOL.findall(cost.split(" // ")[0]) if "/" in s and "P" not in s]
    if not symbols:
        return None
    base, _ = castability.requirement(cost)
    turn = max(1, int(card["mana_value"] or 0))
    best: tuple[float, list[str], dict[str, Any]] | None = None
    options = [[p if p in "WUBRG" else "generic" for p in s.split("/")] for s in symbols]
    for combo in itertools.product(*options):
        need = dict(base)
        for pick in combo:
            if pick != "generic":
                need[pick] = need.get(pick, 0) + 1
        res: dict[str, Any] = castability.colour_probability(
            src.land_groups, src.nonland + 1, need, turn
        )
        raw = res["p_on_curve"]
        p = float(raw) if raw is not None else -1.0
        if best is None or p > best[0]:
            best = (p, list(combo), res)
    assert best is not None
    _, choice, res = best
    return {
        "need": res["need"],
        "sources": res["sources"],
        "p_land_drops": res["p_land_drops"],
        "p_colours_given_lands": res["p_colours_given_lands"],
        "p_on_curve": res["p_on_curve"],
        "turn": turn,
        "hybrid_counted_as": [f"{s}->{c}" for s, c in zip(symbols, choice, strict=True)],
    }


def cost_reduction_in_text(card: Card) -> bool:
    if card["is_land_front"]:
        return False
    tlow = faces_text(card).lower()
    if not _ALT_COST.search(tlow) or not any(w in tlow for w in _ALT_COST_WORDS):
        return False
    if re.search(r"spells you cast have (improvise|convoke|affinity)", tlow):
        return False
    return not ("cascade" in tlow and not _ALT_COST_STRICT.search(tlow))


# ----------------------------------------------------------------------------- G7 / G8 faces


def keyword_faces(card: Card) -> dict[str, list[int]]:
    """Per keyword the 1-based faces whose text names it (empty: no face text names it)."""
    out: dict[str, list[int]] = {}
    for kw in card["keywords"]:
        probe = "cycling" if kw.lower().endswith("cycling") else kw.lower()
        out[kw] = [
            i
            for i, face in enumerate(card["faces"], 1)
            if probe in str(face["oracle_text"]).lower()
        ]
    return out


def mana_faces(card: Card) -> list[int]:
    """1-based faces whose text adds mana (only asked for multi-face cards)."""
    return [
        i
        for i, face in enumerate(card["faces"], 1)
        if re.search(r"\badd\b", str(face["oracle_text"]).lower())
    ]


def apply_g7(card: Card, src: Sources) -> None:
    if len(card["faces"]) < 2:
        return
    overrides = {
        (r["oracle_id"], int(r["face"])): r
        for r in src.overrides
        if r["field"] == "power_toughness"
    }
    for i, face in enumerate(card["faces"], 1):
        if "Creature" not in str(face["type_line"] or "").split("—")[0]:
            continue
        if i == 1 and card["power"] is not None:
            face["power_toughness"] = f"{card['power']}/{card['toughness']}"
            face["power_toughness_source"] = "card data (front face)"
        elif (card["oracle_id"], i) in overrides:
            row = overrides[(card["oracle_id"], i)]
            face["power_toughness"] = row["value"]
            face["power_toughness_source"] = f"face_overrides.json ({row['date']})"
        else:
            face["power_toughness"] = UNKNOWN
            face["power_toughness_source"] = "none in the repository"
    card["keyword_faces"] = keyword_faces(card)
    if card["produced_mana"]:
        card["produced_mana_faces"] = mana_faces(card)


def apply_g8(card: Card, src: Sources) -> None:
    if "Planeswalker" not in str(card["type_line"]).split(" // ")[0].split("—")[0]:
        return
    row = src.xmage.get(card["faces"][0]["name"]) or src.xmage.get(card["name"]) or {}
    value = row.get("loyalty")
    if value is not None:
        card["loyalty"] = str(int(value)) if float(value).is_integer() else str(value)
        card["loyalty_source"] = "data/cards/xmage_card_facts.json"
    else:
        card["loyalty"] = UNKNOWN
        card["loyalty_source"] = "none in the repository"


# ----------------------------------------------------------------------------- G9 references


def name_index(pck: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    """Canonical card names (and single face names) by first word, longest first."""
    names: set[str] = set()
    for key, row in pck.items():
        names.add(str(row["name"]))
        names.add(str(key))
    index: dict[str, list[str]] = defaultdict(list)
    for n in names:
        if n:
            index[n.split()[0]].append(n)
    for v in index.values():
        v.sort(key=lambda s: (-len(s), s))
    return dict(index)


def referenced_names(card: Card, index: Mapping[str, list[str]]) -> list[str]:
    """Card names that follow 'named ' in the rules text (also a list 'X and Y', 'X or Y',
    'X, Y'), not token names and not the card's own names."""
    own = {card["name"], *(str(f["name"]) for f in card["faces"])}
    text = faces_text(card)
    found: list[str] = []
    for m in _NAMED.finditer(text):
        if _TOKEN_NAMED.search(text[: m.end()]):
            continue
        pos = m.end()
        while True:
            rest = text[pos:]
            first = rest.split(" ", 1)[0].rstrip(".,;")
            hit = next(
                (
                    n
                    for n in index.get(first, [])
                    if rest.startswith(n) and not re.match(r"[\w']", rest[len(n) : len(n) + 1])
                ),
                None,
            )
            if hit is None:
                break
            if hit not in own and hit not in found:
                found.append(hit)
            pos += len(hit)
            sep = re.match(r"(?:,? and |,? or |, )", text[pos:])
            if not sep:
                break
            pos += sep.end()
    return found


def apply_g9(card: Card, src: Sources, index: Mapping[str, list[str]]) -> None:
    refs = []
    for n in referenced_names(card, index):
        row = src.pck[n]
        pt = f"{row['power']}/{row['toughness']}" if row.get("power") is not None else None
        refs.append(
            {
                "name": row["name"],
                "mana_cost": row.get("mana_cost") or "",
                "type_line": row.get("type_line") or "",
                "power_toughness": pt,
                "oracle_text": row.get("oracle_text") or "",
                "source": "data/cards/pilot_card_knowledge.json",
            }
        )
    if refs:
        card["referenced_cards"] = refs
    text = faces_text(card)
    if not refs and re.search(r"choose a card name|chosen name|choose any card name", text):
        card["referenced_cards_note"] = "no fixed card: the name is chosen during the game"


# ----------------------------------------------------------------------------- G6 / G10 glossary


def token_explained(tok: str, text: str) -> bool:
    parens = re.findall(r"\(([^)]*)\)", text)
    return any(re.search(rf"\b{tok}\b", pz) and "artifact" in pz for pz in parens) or bool(
        re.search(rf"\b{tok} tokens?[^()]{{0,3}}\(It", text)
    )


def glossary_terms(
    card: Card, glossary: Iterable[Mapping[str, Any]], wanted: set[str]
) -> list[str]:
    """Glossary entries that apply to the card. ``wanted`` holds the kinds switched on:
    'mechanic' (G6) and/or 'token' (G10)."""
    text = faces_text(card)
    kws = set(card["keywords"])
    front_types = str(card["type_line"]).split(" // ")[0].split("—")[0].split()
    out: list[str] = []
    for e in glossary:
        det = e["detect"]
        is_token = "token" in det
        if ("token" if is_token else "mechanic") not in wanted:
            continue
        hit = False
        if is_token:
            tok = det["token"]
            hit = bool(
                re.search(rf"\b{tok}\b(?: tokens?|,| or)", text)
                and not re.search(rf"\b{tok} token named", text)
                and not token_explained(tok, text)
            )
        else:
            hit = (
                bool(kws & set(det.get("keywords", [])))
                or card["layout"] in det.get("layouts", [])
                or any(w in front_types for w in det.get("type_words", []))
                or bool(det.get("text_regex") and re.search(det["text_regex"], text, re.I))
            )
        if hit:
            out.append(str(e["id"]))
    return out


# ----------------------------------------------------------------------------- build


def build_facts(v2_cards: list[Card], src: Sources, disabled: Iterable[str] = ()) -> list[Card]:
    """facts-2 records in v2 order. ``disabled`` switches corrections off (attribution, drift)."""
    off = set(disabled)
    unknown = off - set(CORRECTIONS)
    if unknown:
        raise ValueError(f"unknown corrections: {sorted(unknown)}")
    cards = [copy.deepcopy(c) for c in v2_cards]
    index = name_index(src.pck) if "G9" not in off else {}
    for c in cards:
        c["facts_version"] = FACTS_VERSION
        c["corrections_on"] = [g for g in CORRECTIONS if g not in off]
        if "G2" not in off:
            mono, hybrid = hybrid_pips(c["mana_cost"])
            c["mono_pips_front"] = mono
            c["hybrid_pips_front"] = hybrid
            cast = c.get("castability")
            res = hybrid_castability(c, src) if cast else None
            if cast:
                cast["values_from"] = CARRIED if not res else RECOMPUTED
            if cast and res:
                cast.update({k: v for k, v in res.items() if k != "hybrid_counted_as"})
                cast["hybrid_counted_as"] = res["hybrid_counted_as"]
                cast["colour_free_cost"] = not res["need"]
                cast["hybrid_or_phyrexian_left_out"] = c["pips_front"]["phyrexian_symbols"] > 0
                cast["call"] = (
                    "castability.colour_probability(land_groups, nonland+1, need, max(1, mana_"
                    "value)); need = requirement(mana_cost)[0] plus each hybrid symbol as the "
                    "option with the highest P(both)"
                )
        if "G3" not in off and c.get("castability"):
            c["castability"]["cost_reduction_in_text"] = cost_reduction_in_text(c)
        if "G4" not in off:
            kept = [r for r in c["rulings"] if not ARTICLE_POINTER.match(r["comment"].strip())]
            c["rulings_dropped_article_pointer"] = len(c["rulings"]) - len(kept)
            c["rulings"] = sorted(kept, key=lambda r: (r["published_at"] or "", r["comment"]))
            c["rulings_n"] = len(kept)
        if "G7" not in off:
            apply_g7(c, src)
        if "G8" not in off:
            apply_g8(c, src)
        if "G9" not in off:
            apply_g9(c, src, index)
        wanted = {k for g, k in (("G6", "mechanic"), ("G10", "token")) if g not in off}
        if wanted:
            c["glossary_terms"] = glossary_terms(c, src.glossary, wanted)
        if "G11" not in off and c["is_creature_front"]:
            tlow = faces_text(c).lower()
            c["enters_with_counters"] = bool(
                (_ETB_PLUS.search(tlow) and "each other" not in tlow)
                or (_ETB_OTHER.search(tlow) and "+1/+1" not in tlow)
            )
    if "G1" not in off:
        apply_g1(cards)
    for c in cards:
        assert_no_leak(c, c["name"])
    return cards


def dumps_jsonl(cards: list[Card]) -> str:
    return "".join(json.dumps(c, sort_keys=True, ensure_ascii=False) + "\n" for c in cards)


def land_peer_groups(cards: list[Card]) -> dict[str, int]:
    groups: dict[str, int] = defaultdict(int)
    for c in cards:
        if c["is_land_front"] and c.get("land"):
            groups[land_key(c)] += 1
    return dict(sorted(groups.items()))


def parse_disabled(text: str) -> list[str]:
    return [g.strip() for g in text.split(",") if g.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", required=True)
    ap.add_argument("--disable", default="", help="comma-separated corrections to switch off")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo / "src"))
    v2 = load_jsonl(repo / V2_DIR / "data" / "facts.jsonl")
    cards = build_facts(v2, load_sources(repo), parse_disabled(args.disable))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "facts_v2.jsonl").write_text(dumps_jsonl(cards), encoding="utf-8")
    print(json.dumps({"cards": len(cards), "land_peer_groups": land_peer_groups(cards)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
