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
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="java -XX:+UseSerialGC -jar engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar full-game"
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
per-look level that spends the 5% Type I error over the planned looks like an
O'Brien-Fleming boundary (very small at the first looks, larger than 5% / looks
at the last; four looks of ten seeds decide at 0.0001, 0.0055, 0.018, 0.026).
A look of five seeds cannot decide with four seat rotations, so the default is
`--look-every 10`.

Reading the verdict: `VARIANT_BETTER` / `BASELINE_BETTER` — the paired games
decided it: the sign test over the pairs is decided and, when a seed holds more
than one pair, the cluster-robust t statistic (one cluster per seed) also
exceeds the t quantile of the same level, because the four seat rotations of a
seed share a shuffle and the pair test counts them as independent. With one
pair per seed the pair test stands alone. When only the pair test is decided,
the verdict is `NO_CLEAR_DIFFERENCE` and the summary names the pair verdict it
would have been. With two or more variants in one run the verdicts are also
corrected by Holm over the variants: a decided verdict stands only if its
adjusted p-value (`holm_adjusted_p_value`) is below the level, otherwise it
becomes `NO_CLEAR_DIFFERENCE` and `holm_withheld_verdict` and a NOTE line name
what it would have been. A variant tested in its own run is judged alone.
`NO_CLEAR_DIFFERENCE` — played out, no significant edge;
`INSUFFICIENT` — too few finished games to say anything. The report records
the sequential plan and how many seeds were actually played.

Every variant also prints a precision line: the paired win-share difference
with its 95% interval, the smallest difference the run could have detected,
and how many pairs a 0.10 or 0.05 difference would need. When the run was too
small to decide, the summary says `UNDERPOWERED` — then `NO_CLEAR_DIFFERENCE`
means the run could not have seen an effect, not that the decks play the same.
A single-card swap will not move win share at feasible game counts; judge it
by the structural filter in step 2 and per-card figures, not by win share.

Because the four seat rotations of one seed share the same library shuffle,
pairs within a seed are correlated rather than independent. The report
therefore includes both the i.i.d. paired interval and the one-way
cluster-robust interval (`cluster_difference_interval_95` and
`cluster_detectable_difference_80pct_power`), which treats each distinct seed
as one cluster ($G$ clusters) using the Liang-Zeger CR1 correction $G / (G - 1)$
and Student's $t$-quantiles with $G - 1$ degrees of freedom when $N > G$.

For upfront run planning (`power_table()`), the i.i.d. pair count and the
cluster-adjusted seed count for a 4-seat rotation ($m = 4$, assumed intracluster
correlation $\rho = 0.25$, design effect $\text{DEFF} = 1 + (m - 1)\rho = 1.75$)
follow:

$$N_{\text{iid}} = \left\lceil \left(\frac{(z_{0.975} + z_{0.80}) \cdot \sigma_d}{\Delta}\right)^2 \right\rceil, \qquad N_{\text{cluster}} = \left\lceil N_{\text{iid}} \cdot (1 + (m - 1)\rho) \right\rceil, \qquad G = \left\lceil \frac{N}{m} \right\rceil$$

where $z_{0.975} = 1.96$, $z_{0.80} = 0.8416$, and $\sigma_d$ is the assumed
per-pair standard deviation derived from the discordant pair share $q$
($\sigma_d = \text{round}(\sqrt{q}, 4)$ for $q \in \{0.09, 0.20\}$, and the
established planning anchor $\sigma_d = 0.63$ for $q = 0.40$):

| Win-share difference $\Delta$ | Discordant share $q$ | Assumed pair SD $\sigma_d$ | Pairs needed (i.i.d.) | Seeds needed (4 seats, i.i.d.) | Seeds needed (4 seats, $\rho = 0.25$) |
| --- | --- | --- | --- | --- | --- |
| 5 % (`0.05`) | `0.09` | `0.30` | 283 | 71 | 124 |
| 5 % (`0.05`) | `0.20` | `0.4472` | 628 | 157 | 275 |
| 5 % (`0.05`) | `0.40` | `0.63` | 1247 | 312 | 546 |
| 10 % (`0.10`) | `0.09` | `0.30` | 71 | 18 | 32 |
| 10 % (`0.10`) | `0.20` | `0.4472` | 157 | 40 | 69 |
| 10 % (`0.10`) | `0.40` | `0.63` | 312 | 78 | 137 |
| 20 % (`0.20`) | `0.09` | `0.30` | 18 | 5 | 8 |
| 20 % (`0.20`) | `0.20` | `0.4472` | 40 | 10 | 18 |
| 20 % (`0.20`) | `0.40` | `0.63` | 78 | 20 | 35 |

> **Planning note:** All numbers in this power table are prior planning values
> based on assumed discordant shares $q$ and an assumed intracluster correlation
> $\rho = 0.25$, not empirical measurements from a specific deck comparison.


The report also carries `pilot_readiness`: the state of every deck, and per variant the
cards it adds or removes that the pilot is not ready for. The pilot plays such a card as a
spell without cost or role, so when a variant differs from the baseline by one the summary
adds a `PARTIAL:` line under the verdict: the verdict compares that, not the card. Without
`--require-ready` the run still plays; the line is how the result says what it measured.
In a pilot report, `spell_offers_without_pilot_knowledge` counts the spell options for cards
without pilot knowledge (1.6 % on the real pod, 9 of 571 in two games; roughly half of the
card slots of the 195 precon decks have no pilot knowledge), and `compare` prints the share
of both arms and warns from 5 %. `bad_attacks_into_killer` and `bad_needless_chump_blocks`
are counted with the pilot's own score (0 of 928 attacks and 0 of 145 blocks in 24 real
games), so `compare` leaves them out.

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

A pilot change that is judged by this comparison follows four rules, because about twenty
metrics are compared at once and some interval excludes 0 by chance in most comparisons of two
identical pilots:

1. Name the metric the change is meant to move before the games are played, and compare with
   `--primary spells_cast` (or the metric you named). It is tested alone; the others are
   exploratory.
2. Take the seeds from a master seed written in the pull request, `--seeds hash:<master>:<N>`
   instead of `1-N`, so the seeds cannot be chosen after the result.
3. Read `CHANGED` (the adjusted p-value of the sign-flip test, Holm over the metrics that
   move) and not the interval alone; `ci only` is a hint, not a finding. The line `min` is the
   smallest mean change these pairs detect with 80 % power: a shift smaller than that is not
   excluded, it is invisible.
4. Paste `compare ... --markdown` into the pull request. Ten pairs detect only large shifts
   (several per cent of a count, tens of percentage points of a win rate); plan 20 or more
   pairs, and rotate the seats, because in 183 precon pods seat 1 won 38.8 % of the games and seat 4 10.4 %.

`pilot_decision_report.py calibrate report.json` shows the false-positive rate of the method on
a report you already have: it splits the games into two arms that differ in nothing and counts
how often a metric is flagged by its interval alone and after Holm.

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

"0 answers changed" counts only where a recorded request enters the changed code. Ask which of
your lines that is before you quote it:

```bash
python scripts/pilot_reach_report.py
```

It replays the corpus under the interpreter's line events and lists, for every function-body
line the working tree changed against the merge base, whether a request ran it and which
decision classes did. It exits 1 when a changed line is not reached: the footprint above says
nothing about that line, so it needs a unit test that enters the branch or a game that
reaches it. `--dump FILE` adds a full dump of whole games (`pilot_request_corpus.py record
--all`, replayed as played, several MB, kept out of the repository), `--whole` reports the
reach of the pilot as it is. In the five pilot fixes since #952 (measured 2026-10-22) the corpus alone reaches 86 of the
176 changed function-body lines, and two full games raise that to 96.

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
- `-XX:+UseSerialGC` in the command is deliberate: with several JVMs side by side the
  collector threads of the default G1 cost CPU (measured -12 % wall time, identical
  transcripts). It does not change a game.
- Resume a run by repeating the same `--out` — finished games are reused.
- Failed games are censored (excluded), not counted as losses; check the
  report for how many games actually finished.
- `tests/unit/test_docs_deck_variant_workflow.py` parses this page and fails
  if a command or flag on it stops existing. Keep the page and the scripts
  in sync.
