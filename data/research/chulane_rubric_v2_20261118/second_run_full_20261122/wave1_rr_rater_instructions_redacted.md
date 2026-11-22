# Rater instructions: independent card rating (Chulane, Teller of Tales), rubric v2.1

You are an independent rater. Your job: rate 100 Magic: The Gathering cards, one at a time, for how much
each card improves a tuned Commander deck led by Chulane, Teller of Tales (4 players, Bracket 3), exactly
as the rating guide below defines it. Your number **N** (1, 2 or 3) is in the message that sent you here.

All paths below are absolute.

| What | Path |
|---|---|
| The rating guide (read it completely first; see below) | `<RATER_DIR>/rr_guide_v2_1_rendered.md` |
| Your cards, 100 lines | `<RATER_DIR>/rr_input_N.jsonl` |
| Your output file (you create it) | `<RATER_DIR>/rr_output_N.jsonl` |
| Output schema (optional, you may read it) | `<RATER_DIR>/rr_output_schema.json` |

## 1. Blindness rules (hard)

1. You may read **only** these files: this file, the guide, `rr_input_N.jsonl` (your own N), and the schema.
   You may write **only** `rr_output_N.jsonl`. Do not list directories, do not open any other file, do not read
   the repository, do not search the disk, the web or any tool for card ratings, tier lists, popularity,
   prices or "earlier numbers". Do not look at other `rr_input_*` or `rr_output_*` files.
2. Never use, look up or guess how often a card is played, how popular, how expensive or how well-rated it is.
   If you think "this is a staple", that is popularity: write what the card does instead (guide, rule 1).
3. If any tool result ever shows you a rating, score, tier or note that someone else made for one of your cards,
   do not use it: stop, finish nothing further, and report in your final reply which file or output showed it.
4. Rate **each card on its own and independently**, as if you saw only that card. Do not compare a card with
   the other cards in your file, do not calibrate against cards you rated earlier, do not try to spread values
   across the file. The only references are the guide's anchor tables and the peer benchmarks in the card block.
   You never compare two cards with each other; every card gets its own absolute scores.

## 2. What you receive

`rr_input_N.jsonl` has 100 lines. Each line is one JSON object:
`{"seq": 1..100, "oracle_id": "...", "card": "<name>", "card_block": "<text>"}`.
The `card_block` is the only card information you get. It contains, as far as they exist for the card: name,
oracle_id, mana cost, mana value, cost symbols, type line, type group, colour identity, power/toughness,
keywords, mana produced, Game Changer flag, layout, the Oracle text of every face, land facts (lands),
roles (labels that can be wrong), the on-time castability for the reference mana base (spells), peer
benchmarks (how many pool cards of the same role or type are cheaper, equal, dearer), a combination-database
hint, up to four rulings, and rule-based pattern hits (hints that can be wrong; you judge them).
The commander's text and the deck description are in the guide. There is no usage data, no price, no earlier
rating, no note and no label from anyone, and you must not ask for any.

## 3. The guide

Read `<RATER_DIR>/rr_guide_v2_1_rendered.md` completely before the first card. It is the rating guide version 2.1
(the heading says "version 2"; the file is the full system text with anchor tables and output rules). Follow
it exactly: the order of questions in rule 2, scores 0 to 100 in steps of 5 for E, F, T, R, K, D, H, H is your
own judgement and not the mean, the criteria definitions, the special cases for lands, cards without rules text,
double-faced cards, and the anchors. Everything you need about the commander and the deck is there.

## 4. Procedure

1. Read your input file in blocks of 10 lines (for example with the Read tool and offset/limit, or
   `sed -n '1,10p'`), never the whole file at once. Rate those 10 cards one by one.
2. After **every 10th card** (seq 10, 20, ..., 100) **append** the 10 finished JSON lines to
   `<RATER_DIR>/rr_output_N.jsonl` (for example `cat >> <RATER_DIR>/rr_output_N.jsonl <<'EOF' ... EOF` with 10 lines, one JSON object
   per line; N is your number). Append only; never rewrite or delete lines already written. Do not write a JSON
   array, no markdown fence, no comments.
3. If `rr_output_N.jsonl` already exists when you start, count its lines k (`wc -l`), check that those lines
   are your cards 1..k in order, and continue with card k+1. Never re-rate a card that is already written.
4. Output order = input order, one output line per input line, exactly 100 lines at the end.
5. At the end run this check on your own file (replace N by your number). If a line is not valid JSON or a score
   breaks the rules, rewrite only that one line; otherwise leave written lines alone and mention the problem in
   your final reply:
   `python3 -I -c "import json,sys; L=[json.loads(x) for x in open(sys.argv[1])]; print(len(L), all(set(r['scores'])=={'E','F','T','R','K','D','H'} and all(isinstance(v,int) and 0<=v<=100 and v%5==0 for v in r['scores'].values()) for r in L))" <RATER_DIR>/rr_output_N.jsonl`
   It must print `100 True`.

## 5. Output format: one JSON object per card (schema `rubric-v2-card-rating-1`)

```
{"schema": "rubric-v2-card-rating-1",
 "oracle_id": "<copied exactly from the card block>",
 "card": "<name, copied exactly from the card block>",
 "judged_as": "spell" | "land",
 "scores": {"E": int, "F": int, "T": int, "R": int, "K": int, "D": int, "H": int},
 "notes": {"E": str, "F": str, "T": str, "R": str, "K": str, "D": str, "H": str},
 "reason": str,
 "confidence": "high" | "medium" | "low",
 "uncertainty": str,
 "rule_claims": [{"quote": str, "interaction": str, "claim": str, "basis": str}],
 "pattern_check": [{"rule_id": str, "verdict": "correct" | "wrong" | "irrelevant", "why": str}]}
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
{"schema":"rubric-v2-card-rating-1","oracle_id":"00000000-0000-0000-0000-000000000000","card":"Example Cloudhopper (invented card, format example only)","judged_as":"spell","scores":{"E":60,"F":85,"T":0,"R":65,"K":55,"D":65,"H":65},"notes":{"E":"2 mana body with a small ETB, average for its role","F":"cast trigger plus ETB that Chulane's bounce can replay","T":"no effect on opponents","R":"ETB is useful with or without other creatures","K":"replayable ETB, but each loop costs {3}","D":"small body dies to sweepers, one blue pip","H":"solid ETB creature for the loop"},"reason":"According to the card text the ETB draws a card and the body is a 2/2 flier, so it triggers Chulane when cast and again when Chulane's {3},{T} ability returns it to hand and it is cast again. The loop is slow at three mana per replay, so the value is one extra card now and a late-game engine. A sweeper kills the body but not the card already drawn.","confidence":"medium","uncertainty":"The value of replaying depends on spare mana; the invented text has no cheaper way to return it.","rule_claims":[{"quote":"When this creature enters, draw a card.","interaction":"etb_reuse","claim":"each cast after a bounce draws another card","basis":"card_text"}],"pattern_check":[{"rule_id":"etb_own","verdict":"correct"},{"rule_id":"etb_own_draw","verdict":"correct"}]}
```

## 6. Final reply (at most 5 lines)

State: how many lines are in `rr_output_N.jsonl`; the result of the check in step 4.5; the `seq` numbers of cards
where you could not rate properly (if any); whether you saw anything that broke the blindness rules (section 1);
which tools you used. Do not paste ratings into the reply.
