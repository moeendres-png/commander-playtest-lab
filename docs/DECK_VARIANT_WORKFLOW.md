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

### A card the catalog does not know

The effective catalog is `data/cards/oracle_subset.json` plus the deck overlays
`data/decks/*_card_catalog_overrides.json`: a card in both with another
representation is a "duplicate conflicting card identity", so the importer
counts overlay cards as known and skips them. Add the Oracle data of the
missing cards on demand — with a deck file, one `--name` (repeatable) or
`--names-file` (one name per line); nothing is imported in bulk. `--dry-run`
prints what would be added and writes nothing:

```bash
python scripts/import_oracle_cards.py /tmp/my_variant.json --dry-run
python scripts/import_oracle_cards.py --name "Mind Stone" --dry-run
```

Importing a card does not make it playable: the engine facts decide that.

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
`WARN` and `PASS_TO_GAMES` exit 0. The last lines print the planned game count,
a time estimate at the host's games/hour (`--games-per-hour`, default 40 —
measure once on the host, speed depends on the machine), and the win-share
difference the planned pairs can detect at 80% power. For reference, on one
host (4 cores, measured 2026-10-17 and 2026-10-18) the comparison runner played 24 games on 4 workers
in 6.4 minutes — about 225 games/hour on an idle host — and
`pilot_decision_report.py run --workers 4` played 48 games in 973 s —
178 games/hour including the decision recording. Per-commander cast
probabilities alone:

```bash
python scripts/mana_castability_report.py --deck /tmp/my_variant.json --trials 20000
```

## Step 3 — Size the run with `--plan-only`

Answers: how many games the comparison will play, how long that takes at the
host's games/hour, and what win-share difference the planned pairs can detect
at 80% power — before spending any time. Does **not** play games. The planned
figure assumes independent games (per-pair sd 0.63); pairs that end identically
make the real figure smaller, and the run prints its own figure at the end.

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

Every variant also prints a precision line: the paired win-share difference
with its 95% interval, the smallest difference the run could have detected,
and how many pairs a 0.10 or 0.05 difference would need. When the run was too
small to decide, the summary says `UNDERPOWERED` — then `NO_CLEAR_DIFFERENCE`
means the run could not have seen an effect, not that the decks play the same.
A single-card swap will not move win share at feasible game counts; judge it
by the structural filter in step 2 and per-card figures, not by win share.

Faster runs: `--games-per-jvm N` plays up to N games in one bridge process (default 1).
On 36 seeds of the real pod, N=4 gave the same transcript hashes and winners as one
game per JVM and took about 25 % less time (89 to 119 games/hour at the same worker
count, 4 cores, 2026-10-17). It is opt-in and exists for this comparison only: the
report then says `one_isolated_jvm_per_executed_game: false` (state isolation rests on
the game shutdown, not on a process boundary; the runner does not compare twin hashes
itself, the 36-seed twin result above was a separate local run), the setting is part
of the execution identity so a resumed run never mixes batch sizes, and the decision
gates and evidence lanes keep one game per JVM. Games played this way carry no
per-decision record for `pilot_decision_report.py`.

Faster still: start the bridge with serial GC and an AppCDS class archive (both
change only how the JVM runs, not a game):

```bash
python scripts/build_xmage_cds_archive.py        # once per jar build, prints the command
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="<the command it prints>"
python scripts/run_full_game_deck_comparison.py ... --games-per-jvm 6
```

Measured on 4 cores (2026-10-21), 24 two-player games (2 contenders x 6 seeds x 2 seats,
4 workers): 286 s with one game per JVM, 158 s with `--games-per-jvm 4`, 114 s with
`--games-per-jvm 6` and the archive command (302 -> 758 games/hour, 64 % less CPU). All 24
transcript hashes were identical in the three runs. Set `--games-per-hour` to the
figure you measure on your host. Method and sweep numbers:
`docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`.

## Step 5 — Pilot report (only for pilot or engine changes)

Answers: did the pilot get better or worse at playing, on real games?
Use at least 10 seeds; 4 are too noisy.

```bash
python scripts/pilot_decision_report.py run --jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar --out /tmp/before.json --seeds 1-10 --workers 2
python scripts/pilot_decision_report.py run --jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar --out /tmp/after.json --seeds 1-10 --workers 2
python scripts/pilot_decision_report.py compare /tmp/before.json /tmp/after.json
```

Before the games, a pilot change gets a first look that needs no JVM and takes seconds:

```bash
python scripts/pilot_request_corpus.py diff
```

It answers 400+ requests that real games of the real pod put to the pilot
(`tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz`) and counts, per decision class,
the answers that differ from the recorded ones. It exits non-zero when the pilot raises or
gives an illegal answer on a real request shape. Quote its last line next to the report
comparison: it shows where a change acts, not whether the change is good. Record a new
corpus after a bridge change (`pilot_request_corpus.py record --jar ... --seeds 1-2`).

Reading the per-card and per-seat figures of a report (`per_card_version` 3):

- `cast_rate` is the casts inside a counted window per counted window, so it never
  exceeds 1. `cast_share` is the share of games with a counted offer in which the card
  was cast; use it for a card that is held for several turns. A split card counts once
  under its combined name ("Wear // Tear").
- `first_cast_round`, `mean_first_cast_round` and `commander_first_cast_round` are the
  1-based round of the seat's own turn. `commander_first_cast_turn` is the game turn
  counter and depends on the seat; `commander_first_cast_round_by_name` keeps partner
  commanders apart.
- The counters at the top of a game row add up all seats of the pod. `by_seat` (per
  game), `totals_by_seat` (per report) and `cards.by_seat` give one seat's figures; a
  statement about one deck needs that seat.
- Per-card figures of different `per_card_version` values are not compared.
- `rounds_own_turns` is the game length in own turns (max over seats); after
  eliminations it exceeds `rounds`. `mean_rounds_own_turns` is its mean.

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
