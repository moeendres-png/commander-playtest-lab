#!/usr/bin/env python3
"""Compare the engine's rules text with the printed Oracle text.

Writes REPORT.md and report.json into --out-dir. Output is byte-identical
across runs (sorted keys, sorted card order, no timestamps).

Scope: card names come only from data/decks/*.json,
data/decks/opponents/*/current/deck.json, data/opponents/*_precon.json,
data/opponents/official_precon_profiles.json and
data/cards/official_precon_oracle_cards.json. Never the collection.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from commander_lab.engine.card_text_drift import (
    CardDrift,
    compare_card,
    is_basic_land,
)
from commander_lab.engine.structural.card_facts import engine_lookup_key

# Scope globs: card names for the report. Deliberately excludes
# data/collections/** and data/coverage_decks/collection/**.
NAME_GLOBS = (
    "data/decks/*.json",
    "data/decks/opponents/*/current/deck.json",
    "data/opponents/*_precon.json",
    "data/opponents/official_precon_profiles.json",
    "data/cards/official_precon_oracle_cards.json",
)


def _names_in(value: object) -> list[str]:
    """Extract card names from a decoded JSON value (mirrors the export)."""
    out: list[str] = []
    if isinstance(value, dict):
        name = value.get("oracle_name")
        if isinstance(name, str):
            out.append(name)
        for key in ("commanders",):
            names = value.get(key)
            if isinstance(names, list):
                out.extend(i for i in names if isinstance(i, str))
        for item in value.values():
            out.extend(_names_in(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_names_in(item))
    return out


def collect_names(root: Path) -> list[str]:
    """Sorted unique card names from the scope globs."""
    names: set[str] = set()
    for pattern in NAME_GLOBS:
        for path in sorted(root.glob(pattern)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            names.update(_names_in(data))
    return sorted(names)


def load_data(root: Path) -> tuple[dict, dict]:
    with open(root / "data/cards/pilot_card_knowledge.json") as f:
        oracle = json.load(f)["cards"]
    with open(root / "data/cards/xmage_card_facts.json") as f:
        facts = json.load(f)["cards"]
    return oracle, facts


def run_comparison(root: Path) -> tuple[list[CardDrift], list[str], list[str]]:
    """Compare all in-scope cards. Returns (drifts, excluded, missing)."""
    oracle, facts = load_data(root)
    oracle_by_key = {engine_lookup_key(n): n for n in oracle}
    facts_by_key = {engine_lookup_key(n): n for n in facts}

    drifts: list[CardDrift] = []
    excluded: list[str] = []
    missing: list[str] = []
    for name in collect_names(root):
        if is_basic_land(name):
            excluded.append(name)
            continue
        key = engine_lookup_key(name)
        o_key = oracle_by_key.get(key)
        f_key = facts_by_key.get(key)
        if o_key is None or f_key is None:
            missing.append(name)
            continue
        o_entry = oracle[o_key]
        f_entry = facts[f_key]
        keywords = [str(k) for k in (o_entry.get("keywords") or [])]
        drifts.append(compare_card(o_entry, f_entry, known_keywords=keywords))
    drifts.sort(key=lambda d: d.name)
    return drifts, sorted(excluded), sorted(missing)


def _excerpt(text: str, limit: int = 120) -> str:
    one_line = " ".join(text.split())
    if len(one_line) > limit:
        return one_line[:limit] + "…"
    return one_line


def _triage(drift: CardDrift, oracle_text: str, engine_rules: list[str]) -> tuple[str, str, str]:
    """Return (oracle_excerpt, engine_excerpt, class, reason).

    Classes: WORDING | EXPORT_GAP | DIFFERENT | UNSURE.
    DIFFERENT means "candidate implementation difference": the normalized
    texts disagree on an effect number, keyword or structural field in a way
    no known noise pattern explains. Never a proven engine bug from text
    alone; each DIFFERENT card gets a proposed in-game check.
    """
    o_ex = _excerpt(oracle_text)
    e_ex = _excerpt(" ".join(engine_rules))
    if drift.tier == "EXPORT_GAP":
        return (
            o_ex,
            e_ex,
            "EXPORT_GAP",
            "engine facts export has null for a field the printed card defines",
        )
    if drift.tier == "A":
        fields = ", ".join(s.field for s in drift.structural)
        # Variable P/T (*) exported as 0 is a known export convention.
        if any(s.field in ("power", "toughness") and s.engine == "0" for s in drift.structural):
            return o_ex, e_ex, "EXPORT_GAP", f"variable P/T exported as 0 ({fields})"
        # Exact structural fields (mana cost/value, power, toughness,
        # loyalty) are compared literally: a diff here is a candidate.
        if all(s.field != "types" for s in drift.structural):
            return (
                o_ex,
                e_ex,
                "DIFFERENT",
                f"structural field differs: {fields}",
            )
        return o_ex, e_ex, "UNSURE", f"structural field differs: {fields}; needs a rules check"
    if drift.tier == "B":
        bits = []
        if drift.numbers_only_oracle or drift.numbers_only_engine:
            bits.append(
                f"numbers only in oracle {list(drift.numbers_only_oracle)} / "
                f"only in engine {list(drift.numbers_only_engine)}"
            )
        if drift.keywords_only_oracle or drift.keywords_only_engine:
            bits.append(
                f"keywords only in oracle {list(drift.keywords_only_oracle)} / "
                f"only in engine {list(drift.keywords_only_engine)}"
            )
        detail = "; ".join(bits)
        if drift.numbers_only_oracle or drift.numbers_only_engine:
            o_vals = set(drift.numbers_only_oracle)
            e_vals = set(drift.numbers_only_engine)
            if o_vals != e_vals:
                # Different numeric values (e.g. +1/+1 vs +2/+2): candidate.
                return o_ex, e_ex, "DIFFERENT", f"number multiset differs: {detail}"
            # Same values, different counts: duplication noise.
            return o_ex, e_ex, "WORDING", f"number counts differ, same values: {detail}"
        return o_ex, e_ex, "UNSURE", f"keyword set differs: {detail}"
    # Tier C: low similarity, no structural/number/keyword diff.
    return o_ex, e_ex, "WORDING", "same effect, different phrasing or ordering"


def _in_game_check(name: str, klass: str, reason: str) -> str:
    if klass == "DIFFERENT":
        return (
            f"Cast {name} in a real game and observe whether the listed "
            f"ability/number/condition behaves as printed."
        )
    if klass == "EXPORT_GAP":
        return (
            f"Re-run scripts/export_xmage_card_facts.py and check whether "
            f"the field is present for {name}."
        )
    return ""


def write_report(root: Path, out_dir: Path) -> None:
    drifts, excluded, missing = run_comparison(root)
    oracle, facts = load_data(root)
    oracle_by_key = {engine_lookup_key(n): n for n in oracle}
    facts_by_key = {engine_lookup_key(n): n for n in facts}

    counts = Counter(d.tier for d in drifts)

    # Listed cards: all A and B, plus the 40 lowest-similarity C cards.
    c_sorted = sorted((d for d in drifts if d.tier == "C"), key=lambda d: (d.similarity, d.name))
    listed = [d for d in drifts if d.tier in ("A", "B", "EXPORT_GAP")]
    listed += c_sorted[:40]
    listed.sort(key=lambda d: ({"A": 0, "EXPORT_GAP": 1, "B": 2, "C": 3}[d.tier], d.name))

    # ---- report.json (only listed cards, stays well under 128 KB) ----
    json_payload = {
        "tiers": {t: counts.get(t, 0) for t in ("A", "B", "C", "OK", "EXPORT_GAP")},
        "excluded_basic_lands": excluded,
        "missing": missing,
        "listed": [
            {
                "name": d.name,
                "tier": d.tier,
                "similarity": round(d.similarity, 4),
                "structural": [
                    {"field": s.field, "oracle": s.oracle, "engine": s.engine} for s in d.structural
                ],
                "numbers_only_oracle": list(d.numbers_only_oracle),
                "numbers_only_engine": list(d.numbers_only_engine),
                "keywords_only_oracle": list(d.keywords_only_oracle),
                "keywords_only_engine": list(d.keywords_only_engine),
            }
            for d in listed
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(json_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # ---- REPORT.md ----
    lines = [
        "# Card text drift report",
        "",
        "Engine rules text vs printed Oracle text for precon, opponent and",
        "real-deck cards (basic lands excluded).",
        "",
        "## Counts",
        "",
        f"- A (structural field differs): {counts.get('A', 0)}",
        f"- B (numbers or keywords differ): {counts.get('B', 0)}",
        f"- C (similarity < 0.8): {counts.get('C', 0)}",
        f"- OK: {counts.get('OK', 0)}",
        f"- EXPORT_GAP (facts export lacks the field): {counts.get('EXPORT_GAP', 0)}",
        f"- Excluded basic lands: {len(excluded)} ({', '.join(excluded)})",
        f"- Missing from a data file: {len(missing)}",
        "",
        "Classes: WORDING = same effect, different phrasing; EXPORT_GAP = the",
        "facts export lacks or mangles the field; DIFFERENT = candidate",
        "implementation difference (never a proven engine bug from text alone);",
        "UNSURE = needs a closer look. Each DIFFERENT card gets a proposed",
        "in-game check.",
        "",
        "## Triage",
        "",
        "| card | tier | class | oracle | engine | reason | in-game check |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in listed:
        key = engine_lookup_key(d.name)
        o_entry = oracle.get(oracle_by_key.get(key, ""), {})
        f_entry = facts.get(facts_by_key.get(key, ""), {})
        o_ex, e_ex, klass, reason = _triage(
            d,
            str(o_entry.get("oracle_text") or ""),
            list(f_entry.get("rules") or []),
        )
        check = _in_game_check(d.name, klass, reason)
        # Escape pipes for the markdown table.
        cells = [d.name, d.tier, klass, o_ex, e_ex, reason, check]
        cells = [c.replace("|", "\\|") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare engine rules text with printed Oracle text."
    )
    parser.add_argument(
        "--out-dir",
        default="docs/card_text_drift",
        help="Directory for REPORT.md and report.json",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    write_report(root, root / args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
