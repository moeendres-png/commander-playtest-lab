# XMage full-game speed: profile, measured levers, language question (2026-10-12)

Scope: where the time of one real XMage full game goes, which changes make it faster
without changing a single game, and whether a rewrite in another language would help.
Measured on a 4-core container, XMage pin `3cbf7741`, lab main `96c2e816`, JDK 21.

## 1. Where the time goes

JFR profile of one real 4P game (rogshai, kaervek, Hosts of Mordor, Lorehold; seed 1;
4,701 decisions; 4,239 CPU samples), attributed by the bridge call site:

| Share of CPU | What |
|---:|---|
| **69 %** | copying the whole game state (`GameImpl.copy` via `createSimulationForPlayableCalc`) |
| 33 % | `priority` -> `PlayerImpl.getPlayable` (one copy, plus one more inside `getManaAvailable`) |
| 14 % | `priority` -> `getManaAvailable` again (a third copy of the same state) |
| 11 % / 5 % | mana payment frame -> `getPlayable` / `getManaAvailable` (same pattern) |
| 12 % | `manaCostAffordable` (one copy per `{T}` mana ability with a mana cost) |
| 6 % | card repository scan at JVM start (about 90,000 single-row DB queries) |
| 5 % | `GameImpl.start` |
| about 5 % | bridge JSON (deep copies, `toString`, state hashes) |

Each game also pays 6.6-8.6 s of fixed cost (JVM start, class loading, card scan, deck
import, game start) before the first decision. Games are 25-80 s long, so that is 10-30 %.
The Python pilot was about 6 % of total CPU in the earlier profile of #759.

## 2. Levers, each checked for identical games

Bar for every lever: the semantic transcript of every game is byte-identical to main.
Test set: 14 games. 4 real pods (seeds 1-4) and 10 pods from the 18 owner-collection
coverage decks (5 pods, seeds 1-2; about 1,250 distinct cards).

| Lever | Where | Identical | Wall | CPU | Status |
|---|---|---:|---:|---:|---|
| Reuse the mana `getPlayable` already computed (#759) | bridge | 4/4 real pods | -18.2 % | -11.4 % | **this PR** |
| ... plus AppCDS class archive (`scripts/build_xmage_cds_archive.py`) | launch flags | **14/14** | **-19.3 %** | **-18.6 %** | **this PR** |
| ... plus card scanner with one query for all stored cards | XMage fork | 14/14 | -23 to -25 % | -22 to -26 % | needs a repin (Owner) |
| `getManaAvailable` without its second copy | XMage fork | **13/14** | about -24 % more | | **rejected** |
| Memo per mana source in `manaCostAffordable` | bridge | 4/4 | 0 % | 0 % | dropped (no gain) |

Wall and CPU are summed over the games of the test set and compared with main on the same
games. Fixed start-up cost per game: 8.6 s on main, 6.6 s with the bulk card scan, about
4.2 s with scan and AppCDS.

Single-worker throughput over the 14 games: 75 -> 93 games per hour. Batches are
CPU-bound and scale with cores, so the CPU reduction carries over to `--workers N`.

### Why the second copy stays

Within `getPlayable`, XMage computes available mana in a copy of its own playable copy.
That looks redundant (69 % of the CPU is copying), and removing it is about 24 % faster.
But one coverage game then played differently. The cause is `AddManaChosenColorEffect`:
the effect remembers the color on its own object while it produces mana (the source says
"buggy, but no other way"), and the rule text then gains a `{U}`. Without the second copy,
the mana calculation runs on the same ability objects that are then offered. Their rule
text changes, the bridge sorts options by rule text (F-36), and the pilot picks a
different option. Any effect with such state can leak into the offered abilities and into
their activation, so the copy protects real behaviour. Rejected.

### AppCDS: how to use it

```bash
python scripts/build_xmage_cds_archive.py   # once per bridge jar build, about 25 s
export COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD="<the command it prints>"
```

The archive (about 300 MB, mapped read-only and shared between parallel JVMs) belongs to
one jar. With a rebuilt jar the JVM refuses the archive and runs at normal speed. The
printed command routes JVM logging to stderr. Without that, the refusal warning lands on
stdout, which carries the bridge protocol, and the game fails closed (`INVALID_RESPONSE`).
Both cases were tested. A different command string means earlier batch records are not
reused (the batch execution identity digests the command), which is the safe direction.

## 3. Would a rewrite in Rust, Go or C++ make it faster?

Not in a way that pays off.

- **Python layer (pilots, orchestration).** Rewriting it could save at most its own share:
  the profile in #759 put the Python pilot at about 6 % of the CPU of a game.
- **Rules Core (XMage).** The time is spent inside XMage: 276,000 lines of engine and
  2.13 million lines in 32,123 card implementations. A rewrite in another language
  means re-implementing and re-validating every card the project plays. That works
  against the project's first goal (as many cards as possible, correctly), takes years,
  and restarts qualification from zero. A Rules Core change is also an Owner decision
  (Architecture Freeze, Provider selection). Java is not the bottleneck: the time goes to
  an algorithm that copies the whole game for every legality check. The same algorithm
  in Rust would still copy the whole game. A faster copy might be possible there, but it
  is also possible in Java (section 4, lever 2) without losing a single card.
- **GraalVM native image.** XMage creates cards by reflection. Native image would need
  reflection configuration for 32,000 classes, and it saves only start-up time, which
  AppCDS already covers for the most part.

Recommendation: stay on Java and Python. Keep shrinking the measured hotspot (game copies)
inside the fork, admitting only changes that are proven behaviour-identical. Use more cores
for batches: throughput scales about linearly with workers.

## 4. Next levers, in order

1. Repin to a fork commit with the bulk card scan (-2 s start-up per game, -3 to -6 % wall; one
   fork commit, `CardRepository` / `CardScanner`, saved as
   `xmage-card-scan-bulk-lookup.patch` next to this file; it applies to `3cbf7741`).
   Needs an Owner repin decision and the usual requalification.
2. Cheaper copies, for example sharing immutable card data between copies instead of
   deep-copying it. This is the only lever that addresses the 69 %, and it is deep
   engine work. Every step has to pass the identical-transcript bar above.
3. Bridge JSON (about 5 %): avoid deep copies and re-serialisation of unchanged frames.
