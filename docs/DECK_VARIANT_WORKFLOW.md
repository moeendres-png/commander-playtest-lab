# Deck-variant workflow: from an idea to a trustworthy answer

Project rule: the structural tools are a **filter** (cheap screening that rejects
bad ideas fast); real XMage full games are the **evidence** (they rank variants).
The verdict of `scripts/deck_variant_prefilter.py` says so itself: it is a filter,
not a ranking.

## Step 1 — Readiness: can the simulator play every card?

Answers: does the variant contain cards the simulator does not know yet?
Does **not** answer: whether the variant is any good.

```bash
python scripts/deck_readiness.py --deck data/decks/rogshai_current.json --deck /tmp/my_variant.json
```

Exit 0 means every deck is ready; exit 1 lists unknown cards. Fix those first
(add card data), otherwise the later steps silently measure "unknown card"
instead of the card.

## Step 2 — Prefilter and castability: is the variant worth real games?

Answers: card diff, mana-base deltas, commander cast-probability deltas, and
what a full comparison would cost. Does **not** answer: which variant wins games.

```bash
python scripts/deck_variant_prefilter.py \
    --baseline data/decks/rogshai_current.json \
    --variant /tmp/my_variant.json \
    --trials 20000 --seeds 1-25 --players 4
```

Verdict `BLOCKED` (exit 1) means the variant is not ready — stop here.
`WARN` means a commander lost cast probability (>0.05 on turns 3–6) or a colour
lost a source; `PASS_TO_GAMES` means the filter found nothing wrong. Both
`WARN` and `PASS_TO_GAMES` exit 0. The last lines print the planned game count
and a time estimate (22–56 games/hour on a 4-core host). Per-commander cast
probabilities alone:

```bash
python scripts/mana_castability_report.py --deck /tmp/my_variant.json --trials 20000
```

## Step 3 — Size the run with `--plan-only`

Answers: how many games the comparison will play, before spending any time.
Does **not** play games.

```bash
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
python scripts/run_full_game_deck_comparison.py \
    --baseline data/decks/rogshai_current.json \
    --variant /tmp/my_variant.json \
    --opponent data/decks/opponents/kaervek/current/deck.json \
    --opponent data/opponents/hosts_of_mordor_precon.json \
    --opponent data/opponents/lorehold_spirit_precon.json \
    --seeds 1-25 --out artifacts/deck-comparison/rogshai-vs-variant \
    --plan-only
```

## Step 4 — Real comparison with early stopping

Answers: which deck is better, on paired real games. This is the evidence step.

```bash
python scripts/run_full_game_deck_comparison.py \
    --baseline data/decks/rogshai_current.json \
    --variant /tmp/my_variant.json \
    --opponent data/decks/opponents/kaervek/current/deck.json \
    --opponent data/opponents/hosts_of_mordor_precon.json \
    --opponent data/opponents/lorehold_spirit_precon.json \
    --seeds 1-25 --out artifacts/deck-comparison/rogshai-vs-variant \
    --require-ready --stop-when-decided --look-every 5
```

Every contender plays the same pods (same seeds, opponents, seats), so the
comparison is paired. `--stop-when-decided` plays seeds in blocks of
`--look-every` and stops early once every variant has a decided verdict at a
Bonferroni-split per-look threshold (overall Type I error stays at 5%).

Reading the verdict: `VARIANT_BETTER` / `BASELINE_BETTER` — the paired games
decided it; `NO_CLEAR_DIFFERENCE` — played out, no significant edge;
`INSUFFICIENT` — too few finished games to say anything. The report records
the sequential plan and how many seeds were actually played.

## Step 5 — Pilot report (only for pilot or engine changes)

Answers: did the pilot get better or worse at playing, on real games?
Use at least 10 seeds; 4 are too noisy.

```bash
python scripts/pilot_decision_report.py run --jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar --out /tmp/before.json --seeds 1-10 --workers 2
python scripts/pilot_decision_report.py run --jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar --out /tmp/after.json --seeds 1-10 --workers 2
python scripts/pilot_decision_report.py compare /tmp/before.json /tmp/after.json
```

## Pitfalls

- `COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD` must point at the bridge jar
  built from the pinned engine (`config/rules_engines.json`), or step 4 fails.
- One worker needs about 2 GB RAM and one CPU core; more workers than cores
  is slower, not faster.
- Resume a run by repeating the same `--out` — finished games are reused.
- Failed games are censored (excluded), not counted as losses; check the
  report for how many games actually finished.
- `tests/unit/test_docs_deck_variant_workflow.py` parses this page and fails
  if a command or flag on it stops existing. Keep the page and the scripts
  in sync.
