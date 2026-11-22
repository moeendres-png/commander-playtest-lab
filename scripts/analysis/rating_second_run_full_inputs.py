#!/usr/bin/env python3
"""Blind rater inputs for wave 2 of the second rating run of H (Chulane, rubric v2.1, Refs #1404).

Wave 1 (PR #1758) rated 300 stratified cards of the 922-card pool a second time. Wave 2 covers the
other 622 cards with the same input form (the original rater's card block), the same guide v2.1 and
the same rater instructions, so that every card can later carry two independent ratings. The
evaluation rules are fixed beforehand in
``docs/analysis-reports/rating_full_second_run_plan_20261122.md``; this script only writes inputs.

What it writes:

  <out>/rr2_manifest.json            analyst file: every card with oracle_id, name, stratum, chunk,
                                     seq; seed, source commit, source hashes, n/N, per-chunk anchor
                                     leave-out. Never give this file or its folder to a rater.
  <rater-dir>/ (the only folder a rater is pointed to; its parent must hold no analyst file)
    rr2_input_{k}.jsonl              blind input of chunk k, one card block per line
    rr2_guide_{k}.md                 guide v2.1 system text with chunk k's anchor cards taken out of
                                     the anchor tables (leave-one-anchor-out per chunk)
    rr2_output_schema.json           copy of output_schema.json
    rr2_rater_instructions.md        the wave-1 instructions, changed only in N, the card count,
                                     the file names and the final line-count check

Chunks 1 to 7 hold the 622 pool cards (at most 100 each, every stratum dealt round-robin, order
shuffled inside a chunk). Chunk 8 is the OPTIONAL retest chunk: 50 wave-1 primary cards rated again
blind; it is never pooled and only estimates the repeat noise of the second rater (plan section 7).

The prior ratings (card_understanding_v2_1.jsonl) are read ONLY to rebuild the wave-1 strata
(top 20 % of H); they never go into an input, a guide or the manifest.

Usage:
  python3 scripts/analysis/rating_second_run_full_inputs.py --repo . \\
      --out <analyst dir> --rater-dir <rater dir> [--path-in-instructions '<RATER_DIR>']
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import re
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SEED = 20261124  # wave 2; wave 1 used 20261122 (sample) and 20261123 (claim sample)
SEED_WAVE1 = 20261122  # only to rebuild the wave-1 top-20 tie draw exactly
POOL_SIZE = 922
WAVE1_SIZE = 300
MAX_CHUNK = 100
RETEST_PLAN = (("top20", 20), ("rest", 20), ("land", 10))  # optional chunk, 50 cards
WAVE1_STRATUM = {
    "flagged": "flagged",
    "top20": "top20",
    "rest": "rest",
    "rest_fill": "rest",
    "land": "land",
}
DEAL_ORDER = ("anchor_land", "anchor_spell", "top20", "land", "rest")
RUB = Path("data") / "research" / "chulane_rubric_v2_20261118"
WAVE1_DIR = RUB / "second_run_20261122"
PRIOR = Path("data") / "card_understanding" / "card_understanding_v2_1.jsonl"
SOURCE_FILES = (
    RUB / "data" / "facts.jsonl",
    RUB / "data" / "patterns.jsonl",
    RUB / "anchors.json",
    RUB / "GUIDE_v2.md",
    RUB / "output_schema.json",
    RUB / "scripts" / "render_prompt.py",
    RUB / "scripts" / "build_anchors.py",
    RUB / "audit" / "audit_A_flagged.jsonl",
    PRIOR,
    WAVE1_DIR / "rr_sample_manifest.json",
)
CRITERIA = ("E", "F", "T", "R", "K", "D", "H")
PLACEHOLDER = "<RATER_DIR>"


class LeaveOut:
    """Set of card names removed from the anchor tables (same trick as make_batches.LeaveOut)."""

    def __init__(self, names: Iterable[str]) -> None:
        self.names = set(names)

    def __bool__(self) -> bool:
        return bool(self.names)

    def __eq__(self, other: object) -> bool:
        return other in self.names

    __hash__ = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- pure helpers


def remaining_ids(all_ids: Iterable[str], wave1_ids: Iterable[str], pool_size: int) -> list[str]:
    """Pool cards not rated in wave 1, sorted. Wave 1 must be a subset of the pool."""
    pool = set(all_ids)
    done = set(wave1_ids)
    if len(pool) != pool_size:
        raise ValueError(f"pool has {len(pool)} cards, expected {pool_size}")
    if not done <= pool:
        raise ValueError(f"{len(done - pool)} wave-1 cards are not in the pool")
    return sorted(pool - done)


def top_set(h: Mapping[str, int], share_pct: int, rng: random.Random) -> set[str]:
    """Top ``share_pct`` % of H by rank; the tie group at the cut is drawn with ``rng`` (wave 1 rule)."""
    ids = sorted(h)
    n_top = -(-len(ids) * share_pct // 100)
    ranked = sorted(ids, key=lambda o: (-h[o], o))
    cut = h[ranked[n_top - 1]]
    top = [o for o in ranked if h[o] > cut]
    tie = [o for o in ranked if h[o] == cut]
    top += sorted(rng.sample(tie, n_top - len(top)))
    return set(top)


def wave2_stratum(is_anchor: bool, is_land: bool, in_top: bool) -> str:
    """Stratum of a wave-2 card. Anchor cards first (their guide differs), then lands, top, rest."""
    if is_anchor:
        return "anchor_land" if is_land else "anchor_spell"
    if is_land:
        return "land"
    return "top20" if in_top else "rest"


def n_chunks_for(n: int, max_size: int) -> int:
    if n <= 0 or max_size <= 0:
        raise ValueError("n and max_size must be positive")
    return -(-n // max_size)


def deal(
    members: Mapping[str, Sequence[str]], order: Sequence[str], n_chunks: int, rng: random.Random
) -> list[list[tuple[str, str]]]:
    """Deal every stratum round-robin over the chunks with one running counter, then shuffle each
    chunk. Chunk sizes differ by at most 1; so do the counts of each stratum per chunk."""
    unknown = set(members) - set(order)
    if unknown:
        raise ValueError(f"strata without a deal position: {sorted(unknown)}")
    chunks: list[list[tuple[str, str]]] = [[] for _ in range(n_chunks)]
    i = 0
    for stratum in order:
        group = sorted(members.get(stratum, ()))
        rng.shuffle(group)
        for o in group:
            chunks[i % n_chunks].append((o, stratum))
            i += 1
    for c in chunks:
        rng.shuffle(c)
    return chunks


def name_hits(names: Iterable[str], text: str) -> list[str]:
    """Card names that occur in ``text`` as a whole phrase (no letter or digit right before or after),
    so a short name like "Opt" does not hit "optional"."""
    hits = []
    for n in sorted(set(names)):
        if re.search(r"(?<![0-9A-Za-z])" + re.escape(n) + r"(?![0-9A-Za-z])", text):
            hits.append(n)
    return hits


def removed_anchor_rows(
    anchors: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]], names: set[str]
) -> dict[str, int]:
    """How many anchor rows per criterion (spell and land tables together) a leave-out removes."""
    out = {}
    for crit in CRITERIA:
        n = sum(
            1
            for t in ("spell", "land")
            for r in anchors.get(t, {}).get(crit, [])
            if r["card"] in names
        )
        out[crit] = n
    return out


def retest_pick(
    wave1_cards: Sequence[Mapping[str, Any]], plan: Sequence[tuple[str, int]], rng: random.Random
) -> list[tuple[str, str]]:
    """Optional retest chunk: per wave-1 primary stratum (flagged cards never), a seeded draw."""
    picked: list[tuple[str, str]] = []
    for stratum, k in plan:
        pool = sorted(c["oracle_id"] for c in wave1_cards if WAVE1_STRATUM[c["stratum"]] == stratum)
        if len(pool) < k:
            raise ValueError(f"retest stratum {stratum}: {len(pool)} cards, {k} wanted")
        picked += [(o, stratum) for o in sorted(rng.sample(pool, k))]
    rng.shuffle(picked)
    return picked


def instructions(path_text: str, sizes: Mapping[int, int], retest_chunk: int) -> str:
    """Wave-1 rater instructions; changed only in N, card counts, file names and the final check."""
    p = path_text.rstrip("/")
    if retest_chunk not in sizes or sorted(sizes) != list(range(1, len(sizes) + 1)):
        raise ValueError("chunks must be numbered 1..n and include the retest chunk")
    table = "\n".join(f"| {k} | {sizes[k]} |" for k in sorted(sizes))
    return INSTRUCTIONS_TEMPLATE.format(P=p, TABLE=table, NMAX=max(sizes))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


INSTRUCTIONS_TEMPLATE = """# Rater instructions: independent card rating (Chulane, Teller of Tales), rubric v2.1

You are an independent rater. Your job: rate the Magic: The Gathering cards in your input file, one at a time,
for how much each card improves a tuned Commander deck led by Chulane, Teller of Tales (4 players, Bracket 3),
exactly as the rating guide below defines it. Your number **N** (1 to {NMAX}) is in the message that sent you here.
Your input file has **C** cards; C for your N is in this table:

| N | C (cards in your input file) |
|---|---|
{TABLE}

All paths below are absolute.

| What | Path |
|---|---|
| The rating guide for your N (read it completely first; see below) | `{P}/rr2_guide_N.md` |
| Your cards, C lines | `{P}/rr2_input_N.jsonl` |
| Your output file (you create it) | `{P}/rr2_output_N.jsonl` |
| Output schema (optional, you may read it) | `{P}/rr2_output_schema.json` |

## 1. Blindness rules (hard)

1. You may read **only** these files: this file, `rr2_guide_N.md` (your own N), `rr2_input_N.jsonl` (your own N),
   and the schema. You may write **only** `rr2_output_N.jsonl`. Do not list directories, do not open any other file,
   do not read the repository, do not search the disk, the web or any tool for card ratings, tier lists, popularity,
   prices or "earlier numbers". Do not look at other `rr2_guide_*`, `rr2_input_*` or `rr2_output_*` files.
2. Never use, look up or guess how often a card is played, how popular, how expensive or how well-rated it is.
   If you think "this is a staple", that is popularity: write what the card does instead (guide, rule 1).
3. If any tool result ever shows you a rating, score, tier or note that someone else made for one of your cards,
   do not use it: stop, finish nothing further, and report in your final reply which file or output showed it.
4. Rate **each card on its own and independently**, as if you saw only that card. Do not compare a card with
   the other cards in your file, do not calibrate against cards you rated earlier, do not try to spread values
   across the file. The only references are the guide's anchor tables and the peer benchmarks in the card block.
   You never compare two cards with each other; every card gets its own absolute scores.

## 2. What you receive

`rr2_input_N.jsonl` has C lines. Each line is one JSON object:
`{{"seq": 1..C, "oracle_id": "...", "card": "<name>", "card_block": "<text>"}}`.
The `card_block` is the only card information you get. It contains, as far as they exist for the card: name,
oracle_id, mana cost, mana value, cost symbols, type line, type group, colour identity, power/toughness,
keywords, mana produced, Game Changer flag, layout, the Oracle text of every face, land facts (lands),
roles (labels that can be wrong), the on-time castability for the reference mana base (spells), peer
benchmarks (how many pool cards of the same role or type are cheaper, equal, dearer), a combination-database
hint, up to four rulings, and rule-based pattern hits (hints that can be wrong; you judge them).
The commander's text and the deck description are in the guide. There is no usage data, no price, no earlier
rating, no note and no label from anyone, and you must not ask for any.

## 3. The guide

Read `{P}/rr2_guide_N.md` (your own N) completely before the first card. It is the rating guide version 2.1
(the heading says "version 2"; the file is the full system text with anchor tables and output rules). Follow
it exactly: the order of questions in rule 2, scores 0 to 100 in steps of 5 for E, F, T, R, K, D, H, H is your
own judgement and not the mean, the criteria definitions, the special cases for lands, cards without rules text,
double-faced cards, and the anchors. Everything you need about the commander and the deck is there.

## 4. Procedure

1. Read your input file in blocks of 10 lines (for example with the Read tool and offset/limit, or
   `sed -n '1,10p'`), never the whole file at once. Rate those 10 cards one by one.
2. After **every 10th card** (seq 10, 20, ...) and after your **last card** (seq C) **append** the finished JSON
   lines to `{P}/rr2_output_N.jsonl` (for example `cat >> {P}/rr2_output_N.jsonl <<'EOF' ... EOF` with one JSON
   object per line; N is your number). Append only; never rewrite or delete lines already written. Do not write
   a JSON array, no markdown fence, no comments.
3. If `rr2_output_N.jsonl` already exists when you start, count its lines k (`wc -l`), check that those lines
   are your cards 1..k in order, and continue with card k+1. Never re-rate a card that is already written.
4. Output order = input order, one output line per input line, exactly C lines at the end.
5. At the end run this check on your own file (replace N by your number). If a line is not valid JSON or a score
   breaks the rules, rewrite only that one line; otherwise leave written lines alone and mention the problem in
   your final reply:
   `python3 -I -c "import json,sys; L=[json.loads(x) for x in open(sys.argv[1])]; print(len(L), all(set(r['scores'])=={{'E','F','T','R','K','D','H'}} and all(isinstance(v,int) and 0<=v<=100 and v%5==0 for v in r['scores'].values()) for r in L))" {P}/rr2_output_N.jsonl`
   It must print `C True` (C from the table above).

## 5. Output format: one JSON object per card (schema `rubric-v2-card-rating-1`)

```
{{"schema": "rubric-v2-card-rating-1",
 "oracle_id": "<copied exactly from the card block>",
 "card": "<name, copied exactly from the card block>",
 "judged_as": "spell" | "land",
 "scores": {{"E": int, "F": int, "T": int, "R": int, "K": int, "D": int, "H": int}},
 "notes": {{"E": str, "F": str, "T": str, "R": str, "K": str, "D": str, "H": str}},
 "reason": str,
 "confidence": "high" | "medium" | "low",
 "uncertainty": str,
 "rule_claims": [{{"quote": str, "interaction": str, "claim": str, "basis": str}}],
 "pattern_check": [{{"rule_id": str, "verdict": "correct" | "wrong" | "irrelevant", "why": str}}]}}
```

Constraints:

- `scores`: all seven keys E, F, T, R, K, D, H, always, integers from 0 to 100, **multiples of 5**. D means
  low deck cost (100 = no risk). Unknown is never written as 0: use `confidence` and `uncertainty`.
- `notes`: all seven keys, one phrase each (at most 15 words), naming what decided that score.
- `reason`: 2 to 3 sentences, 60 to 900 characters: what the card really does and what follows (timing,
  symmetry, dependencies, interaction with the Chulane cast trigger and the bounce). Write "according to the card
  text" where the text is the basis. If H is more than 25 away from the mean of E, F, T, R, K, D, say why.
- `confidence`: high, medium or low. `uncertainty`: what is unclear; empty string only when confidence is high,
  at least 10 characters otherwise (at most 400).
- `rule_claims`: every rules interaction your rating relies on, at most 6. `quote` is a **literal** piece of the
  card block (card text or a shown ruling) or of Chulane's Oracle text as written in the guide. `interaction` is a
  short label (preferred: chulane_cast_trigger, chulane_bounce_replay, etb_reuse, landfall, land_drop, mana,
  symmetry, wrath_exposure, self_damage, timing, targeting, combo_loop, other). `claim` says what follows.
  `basis` is card_text, ruling_shown or inferred_from_text (inferred claims must say "according to the card
  text" and be named in `uncertainty`). Never state a rules fact that is not in the text or a shown ruling.
- `pattern_check`: one entry for **every** pattern hit listed in the card block (its `rule_id`), none for hits
  that are not listed; `why` optional, at most 160 characters. If the block says "Pattern hits: none", use `[]`.
- Judge lands as lands against the land anchors (`judged_as` = "land"); everything else as spells.
- English, short and plain. No text outside the JSON objects.

Format example with an **invented** card (a format illustration only, not a rating of any real card):

```
{{"schema":"rubric-v2-card-rating-1","oracle_id":"00000000-0000-0000-0000-000000000000","card":"Example Cloudhopper (invented card, format example only)","judged_as":"spell","scores":{{"E":60,"F":85,"T":0,"R":65,"K":55,"D":65,"H":65}},"notes":{{"E":"2 mana body with a small ETB, average for its role","F":"cast trigger plus ETB that Chulane's bounce can replay","T":"no effect on opponents","R":"ETB is useful with or without other creatures","K":"replayable ETB, but each loop costs {{3}}","D":"small body dies to sweepers, one blue pip","H":"solid ETB creature for the loop"}},"reason":"According to the card text the ETB draws a card and the body is a 2/2 flier, so it triggers Chulane when cast and again when Chulane's {{3}},{{T}} ability returns it to hand and it is cast again. The loop is slow at three mana per replay, so the value is one extra card now and a late-game engine. A sweeper kills the body but not the card already drawn.","confidence":"medium","uncertainty":"The value of replaying depends on spare mana; the invented text has no cheaper way to return it.","rule_claims":[{{"quote":"When this creature enters, draw a card.","interaction":"etb_reuse","claim":"each cast after a bounce draws another card","basis":"card_text"}}],"pattern_check":[{{"rule_id":"etb_own","verdict":"correct"}},{{"rule_id":"etb_own_draw","verdict":"correct"}}]}}
```

## 6. Final reply (at most 5 lines)

State: how many lines are in `rr2_output_N.jsonl`; the result of the check in step 4.5; the `seq` numbers of cards
where you could not rate properly (if any); whether you saw anything that broke the blindness rules (section 1);
which tools you used. Do not paste ratings into the reply.
"""


# --------------------------------------------------------------------------- build


def _load_render(repo: Path) -> Any:
    path = repo / RUB / "scripts" / "render_prompt.py"
    spec = importlib.util.spec_from_file_location("render_prompt_rr2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_commit(repo: Path) -> str:
    """Last commit that touched a source file (stable across later commits; UNKNOWN without git)."""
    cmd = ["git", "-C", str(repo), "log", "-1", "--format=%H", "--", *map(str, SOURCE_FILES)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return out.stdout.strip() or "UNKNOWN"


def build(
    repo: Path, out: Path, rater_dir: Path, path_in_instructions: str | None
) -> dict[str, Any]:
    # a live rater folder (any path other than the placeholder in the instructions) must not sit in
    # or be the analyst folder, and its parent must hold nothing but the rater folder itself; only the
    # repository record (placeholder path) keeps rater/ next to the manifest on purpose
    live = path_in_instructions != PLACEHOLDER
    if live and (
        rater_dir.resolve() == out.resolve() or out.resolve() in rater_dir.resolve().parents
    ):
        raise ValueError("the rater folder must not be the analyst folder or lie inside it")
    rp = _load_render(repo)
    rub = repo / RUB
    facts = {r["oracle_id"]: r for r in jl(rub / "data" / "facts.jsonl")}
    pats = {r["name"]: r for r in jl(rub / "data" / "patterns.jsonl")}
    anchors = json.loads((rub / "anchors.json").read_text(encoding="utf-8"))
    prior = {r["oracle_id"]: r for r in jl(repo / PRIOR)}
    w1 = json.loads((repo / WAVE1_DIR / "rr_sample_manifest.json").read_text(encoding="utf-8"))
    w1_cards = w1["cards"]
    if set(prior) != set(facts):
        raise ValueError("prior ratings and facts cover different cards")
    anchor_names = {
        x["card"] for t in ("spell", "land") for rows in anchors[t].values() for x in rows
    }
    flagged = {r["card"] for r in jl(rub / "audit" / "audit_A_flagged.jsonl")}

    w1_ids = [c["oracle_id"] for c in w1_cards]
    if len(set(w1_ids)) != WAVE1_SIZE:
        raise ValueError("wave-1 manifest does not list 300 distinct cards")
    rest_ids = remaining_ids(facts, w1_ids, POOL_SIZE)
    if len(rest_ids) + len(w1_ids) != POOL_SIZE:
        raise ValueError("wave 1 and wave 2 do not add up to the pool")

    # wave-1 card blocks must render byte-identically today (same input form in both waves)
    w1_blocks = {}
    for k in (1, 2, 3):
        for r in jl(repo / WAVE1_DIR / f"rr_input_{k}.jsonl"):
            w1_blocks[r["oracle_id"]] = r["card_block"]
    drift = [
        o for o, b in w1_blocks.items() if rp.card_block(facts[o], pats.get(facts[o]["name"])) != b
    ]
    if drift:
        raise ValueError(f"{len(drift)} wave-1 card blocks no longer render identically")

    h = {o: prior[o]["scores"]["H"] for o in prior}
    top = top_set(h, 20, random.Random(SEED_WAVE1))
    w1_top = {c["oracle_id"] for c in w1_cards if c["stratum"] == "top20"}
    if not w1_top <= top:
        raise ValueError("rebuilt top-20 set does not contain the wave-1 top20 stratum")

    members: dict[str, list[str]] = {}
    for o in rest_ids:
        f = facts[o]
        if f["name"] in flagged:
            raise ValueError(f"flagged card {f['name']} not in wave 1")
        s = wave2_stratum(f["name"] in anchor_names, bool(f["is_land_front"]), o in top)
        members.setdefault(s, []).append(o)
    composition = {s: len(v) for s, v in sorted(members.items())}

    rng = random.Random(SEED)
    n_chunks = n_chunks_for(len(rest_ids), MAX_CHUNK)
    chunks = deal(members, DEAL_ORDER, n_chunks, rng)
    retest_chunk = n_chunks + 1
    retest = retest_pick(w1_cards, RETEST_PLAN, rng)

    rater_dir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    if live:
        others = sorted(
            p.name for p in rater_dir.resolve().parent.iterdir() if p.name != rater_dir.name
        )
        if others:
            raise ValueError(
                f"the parent of the rater folder must hold only the rater folder: {others}"
            )
    guide_src = (rub / "GUIDE_v2.md").read_text(encoding="utf-8")
    shutil.copy(rub / "output_schema.json", rater_dir / "rr2_output_schema.json")

    all_chunks = [*chunks, retest]
    sizes = {k: len(c) for k, c in enumerate(all_chunks, 1)}
    cards_out: list[dict[str, Any]] = []
    per_chunk: dict[str, Any] = {}
    for k, rows in enumerate(all_chunks, 1):
        names = {facts[o]["name"] for o, _ in rows}
        left_out = sorted(names & anchor_names)
        if k == retest_chunk:
            # the retest sees exactly the wave-1 guide (its leave-out list), checked byte for byte below
            left_out = sorted(w1["meta"]["pool"]["anchors_left_out_of_guide_tables"])
        lo = LeaveOut(left_out) if left_out else None
        system = rp.system_prompt(guide_src, anchors, lo)
        table = rp.BA.anchor_block(anchors["spell"], lo, "Spells") + rp.BA.anchor_block(
            anchors["land"], lo, "Lands (judge a land as a land)"
        )
        leaks = name_hits(names, table)
        if leaks:
            raise ValueError(f"chunk {k}: rated cards still in the anchor tables: {leaks}")
        prose_hits = name_hits(names, system.replace(table, ""))
        if k == retest_chunk and system != (
            repo / WAVE1_DIR / "rr_guide_v2_1_rendered.md"
        ).read_text(encoding="utf-8"):
            raise ValueError("retest guide differs from the wave-1 guide")
        (rater_dir / f"rr2_guide_{k}.md").write_text(system, encoding="utf-8")
        with open(rater_dir / f"rr2_input_{k}.jsonl", "w", encoding="utf-8") as fh:
            for pos, (o, stratum) in enumerate(rows, 1):
                f = facts[o]
                block = rp.card_block(f, pats.get(f["name"]))
                fh.write(
                    json.dumps(
                        {"seq": pos, "oracle_id": o, "card": f["name"], "card_block": block},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                cards_out.append(
                    {
                        "oracle_id": o,
                        "name": f["name"],
                        "role": "retest" if k == retest_chunk else "pool",
                        "stratum": stratum,
                        "chunk": k,
                        "seq": pos,
                        "is_land": bool(f["is_land_front"]),
                        "is_anchor_card": f["name"] in anchor_names,
                    }
                )
        per_chunk[str(k)] = {
            "n": len(rows),
            "role": "retest (optional, never pooled)" if k == retest_chunk else "pool",
            "strata": dict(sorted(Counter(s for _, s in rows).items())),
            "anchors_left_out": left_out,
            "anchor_rows_removed": removed_anchor_rows(anchors, set(left_out)),
            "card_names_in_guide_prose": prose_hits,
            "guide_sha256": sha256(rater_dir / f"rr2_guide_{k}.md"),
            "input_sha256": sha256(rater_dir / f"rr2_input_{k}.jsonl"),
        }

    instr = instructions(path_in_instructions or str(rater_dir.resolve()), sizes, retest_chunk)
    (rater_dir / "rr2_rater_instructions.md").write_text(instr, encoding="utf-8")

    pool_cards = [c for c in cards_out if c["role"] == "pool"]
    if len(pool_cards) != len(rest_ids) or {c["oracle_id"] for c in pool_cards} != set(rest_ids):
        raise ValueError("chunks do not cover the 622 remaining cards exactly once")
    anchor_rows_total = sum(len(rows) for t in ("spell", "land") for rows in anchors[t].values())
    meta = {
        "wave": 2,
        "seed": SEED,
        "seed_wave1_tie_rebuild": SEED_WAVE1,
        "source_commit_last_touching_sources": _source_commit(repo),
        "source_sha256": {str(p): sha256(repo / p) for p in SOURCE_FILES},
        "n_pool_wave2": len(rest_ids),
        "n_wave1": WAVE1_SIZE,
        "N_pool": POOL_SIZE,
        "n_retest_optional": len(retest),
        "max_chunk": MAX_CHUNK,
        "chunks_pool": n_chunks,
        "retest_chunk": retest_chunk,
        "composition_wave2": composition,
        "anchor_names_in_tables": len(anchor_names),
        "anchor_rows_in_tables": anchor_rows_total,
        "per_chunk": per_chunk,
        "schema_sha256": sha256(rater_dir / "rr2_output_schema.json"),
        "note": (
            "strata: anchor_land/anchor_spell = cards in the guide anchor tables (left out of their own "
            "chunk's guide); top20 = top 20 % of prior H rebuilt with the wave-1 rule; rest = everything "
            "else. Chunk "
            f"{retest_chunk} is the optional retest of wave-1 primary cards, never pooled."
        ),
    }
    manifest = {"meta": meta, "cards": sorted(cards_out, key=lambda c: (c["chunk"], c["seq"]))}
    (out / "rr2_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="analyst folder (manifest)")
    ap.add_argument("--rater-dir", type=Path, required=True, help="the only folder a rater sees")
    ap.add_argument(
        "--path-in-instructions",
        default=None,
        help=f"path written into the instructions, e.g. {PLACEHOLDER}",
    )
    a = ap.parse_args(argv)
    meta = build(a.repo.resolve(), a.out, a.rater_dir, a.path_in_instructions)
    print(
        json.dumps(
            {
                k: meta[k]
                for k in ("n_pool_wave2", "chunks_pool", "retest_chunk", "composition_wave2")
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
