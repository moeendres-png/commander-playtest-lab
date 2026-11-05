# Paid optional casts and cancellation diagnostics — 2026-11-05

## Problem and changes

The real 4-player pod, seed 2, offered Chandra's "Cast Talisman of Creativity? (You still
pay the costs)" with no mana sources left, and the same question for Fellwar Stone with
one source. Both Yes answers ended in observed payment cancellations. The pinned
`Mage.Sets/src/mage/cards/c/ChandraTorchOfDefiance.java` already handles a failed cast
and applies its damage correctly; these observations establish a pilot issue, not an
engine defect.

The pilot reuses its existing visible-mana estimate to prefer No on these exact paid-cast
questions when a plain printed cost exceeds the visible supply. Both engine boolean
options remain available to the pilot. The card feed's `Treasure` tag describes a token
created by Magma Opus and does not disable the estimate. Unknown funding, other keyword
mechanics, casting or payment instructions, multi-face cards and public cost reducers keep
the existing preference. XMage retains every legality, payment and outcome decision.

The decision report now excludes observed cancelled priority-cast attempts from cast,
first-cast, commander-cast, wipe and counter figures. It attributes resolution-time
payment cancellations directly from the engine's `source_object`, including those without
a prior priority selection. Source identities prevent an unrelated nested cancellation
from erasing a different spell selection. `per_card_version` increases from 3 to 4.

Standalone catalog entries also take precedence over prepare-spell aliases: Rampant Growth,
Raise Dead, Seething Song and Exsanguinate retain their own report identities.

## Source and reproduction

Baseline: Lab `c1183e487e122258a962046f9c810f4179633026` (includes #1120).
The engine stays at `primary_engine.commit` in `config/rules_engines.json`; neither the
fork nor the pin changes. The bridge and four changed runtime/report files are bound by
SHA-256 in [the measurement summary](measurements-2026-11-05/paid-cast-summary.json).

Only the four public deck snapshots listed in that summary were used. Private collection
trees were excluded. Final local tests and confirmation games used a local audit guard
rejecting reads of those trees. The default pod command, seeds and JVM options are recorded
in the summary; the raw decision dump remains outside the repository.

## Full-game observations

`DIRECTLY_VERIFIED` local observations: all three baseline and all three final games
completed. An additional final seed-2 game completed in a separate JVM and matched the
final seed-2 semantic transcript and decision count. The baseline seed-2 diagnosis was
also reproduced in a separate full game.

| Seed | Decisions, before → after | Priority cast selections | Casts / player round | Payment cancellations | Wall seconds |
|---|---:|---:|---:|---:|---:|
| 1 | 3892 → 3892 | 82 → 82 | 1.55 → 1.55 | 0 → 0 | 233.52 → 235.30 |
| 2 | 1928 → 2190 | 38 → 44 | 1.09 → 1.19 | 2 → 0 | 108.21 → 153.34 |
| 3 | 2628 → 2628 | 45 → 45 | 1.05 → 1.05 | 0 → 0 | 124.39 → 101.29 |

Seeds 1 and 3 preserve their semantic transcripts and winners. Seed 2 changes its
trajectory and winner; its cast selections rise from 38 to 44. This small, single-pod
sample establishes the observed cancellation reduction, not stronger play or a win-rate
improvement. Wall times were collected with concurrent validation work and do not establish
a causal performance improvement.

The final games have zero observed payment cancellations. A separately recorded intermediate
seed-2 game exposed the Magma Opus case: its pool was empty, only Chandra was untapped, and
its `Treasure` keyword tag had disabled the estimate. The fix distinguishes that known token
tag from unclassified mechanics, with controls for both unknown keywords and mixed tags.

Re-summarizing the same 1,928-decision baseline recording attributes both cancelled
payments to Talisman of Creativity and Fellwar Stone (previously neither had per-card
attribution). This is analysis of a real recording, not another game or semantic replay.

## Deterministic checks and limitations

The scoped local suite passed 677 tests, with the private collection-coverage test
explicitly deselected. A subsequent final selection passed 25 tests, including the
unknown-keyword and alternative-cost controls and Any-usage ratchet. Ruff lint/format and
strict mypy (`349` source files) passed. This is not a local full-suite or GitHub CI result.

Regression tests fail on the old implementation for cancelled casts, standalone/prepare
name collisions and unfunded paid-cast preferences. Controls cover funded pools and lands,
unreadable funding, cost reducers on either side, alternative-cost text, multi-face cards,
interleaved seats, repeated attempts, nested payments and preservation of both engine options.

The historical request fixture is unchanged: exactly 2 of 376 stateless answers change,
both Chandra paid-cast questions from Yes to No; all other answers match, with no raised
or illegal answers. The test asserts those exact changes and retains its independent
mutation control for detecting additional priority changes.

Cast figures remain priority spell selections minus observed payment cancellations.
They do not confirm stack entry or resolution, and successful casts during effect
resolution remain outside those counters. Reports with per-card versions 3 and 4 are
not interchangeable for per-card comparisons. No sealed qualification record is changed
or promoted by these local measurements. The existing 36-seed reference is not renewed.
