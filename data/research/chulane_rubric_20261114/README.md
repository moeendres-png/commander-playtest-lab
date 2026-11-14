# Chulane rating rubric (2026-11-14)

A structured, subjective card rating for the Chulane tier list. Each of the 922 rankable
cards of the Chulane pool has a holistic value H from 1 to 10 for one question: how much
better does a tuned Chulane deck (Bracket 3, 4 players) get when the card takes a slot?
The Owner allowed "a little subjectivity" in the ranking on 2026-11-14 on the condition that
every card is rated the same way, comparably, reliably and validly. This folder is that
rating and its evidence.

## Files

| File | Content |
|---|---|
| `GUIDE.md` | The frozen rating guide (version 1): purpose, rules, five criteria, H, fixed anchors. |
| `ratings.csv` | One row per card and rater: `card, rater, E, F, T, R, W, H, reason` (2,736 rows). |
| `summary.csv` | One row per card: `H_mean`, `H_sd`, `raters`, `anchor` and the criterion means (922 rows). |

## Method

- **Raters.** Three independent automated raters (language-model based), `R1`, `R2`, `R3`.
  They are not people. Each rater worked alone, without seeing the others.
- **Blind to usage.** Raters got the card's name, mana cost, type line and rules text only,
  plus the guide. They were told not to use or guess popularity. Popularity is measured
  elsewhere (counted deck lists, EDHREC) and is the yardstick for validity below. A model's
  general knowledge of popular cards cannot be removed completely; see the limits.
- **Criteria.** E efficiency, F fit with Chulane, T table impact with three opponents,
  R reliability, W win contribution, each 0 to 4, and the holistic value H from 1 to 10
  (H is not the average of the criteria).
- **Anchors.** Twelve spells and six lands with fixed values in the guide. The ten anchors
  that are in the pool keep their fixed values (`anchor = 1`, `raters = 0`, `H_sd = 0`).
- **Order and drift.** A pilot of 60 cards (stratified by counted share, lands included),
  then the other 852 cards in 15 batches in a random order (seed 1114). Three pilot cards
  were repeated in every batch to measure drift within a rater; only the first rating counts.
- **Score.** `H_mean` is the mean of the three raters. The index uses
  `(H_mean - 1) / 9`.

## Reliability

Intraclass correlation ICC(2,1) (one rater), ICC(2,3) (mean of three, the value used) with a
95 % bootstrap interval (500 resamples of cards), and Krippendorff's alpha (interval), over
all 912 rated cards:

| | ICC(2,1) | ICC(2,3) | 95 % interval | alpha |
|---|---|---|---|---|
| E | 0.77 | 0.91 | 0.90 to 0.92 | 0.77 |
| F | 0.71 | 0.88 | 0.87 to 0.89 | 0.70 |
| T | 0.76 | 0.91 | 0.89 to 0.92 | 0.76 |
| R | 0.76 | 0.91 | 0.90 to 0.92 | 0.76 |
| W | 0.74 | 0.89 | 0.87 to 0.91 | 0.74 |
| **H** | **0.84** | **0.94** | **0.93 to 0.95** | **0.84** |

H for lands (n = 50 in the main run) ICC(2,3) 0.94, for spells 0.93. Pairwise Spearman on H:
R1-R2 0.79, R1-R3 0.80, R2-R3 0.89. Repeats: 3 cards x 15 batches per rater (135 repeated H
values); 120 equal the rater's pilot value. The 15 others are all R1 on Irrigated Farmland:
6 in the pilot, then 5 eight times and 4 seven times (drift of 1 to 2 points on one land). Five cards have a rater spread (SD of H) of 2 or more, for
example Psychosis Crawler (7, 2, 3); `H_sd` is published for every card.

## Validity

- Spearman between `H_mean` and the card's share in the 2,823 counted Chulane deck lists:
  **0.62** over all 922 cards, 0.44 among the 162 cards in at least 1 % of the lists.
  High enough to show the rating measures the same thing as real deck choices, low enough to
  add information the counts do not have (756 pool cards are in no counted list at all).
- Spearman with global EDHREC inclusion 0.52.
- Spearman with the Playgroup win gap (n >= 200 games) -0.19: the Playgroup gap is not a
  strength signal, as already found in #1352.
- Criteria against H: E 0.92, R 0.90, F 0.74, T 0.50, W 0.50.

## Limits

- The raters share a model family, so part of their agreement can be a shared bias rather
  than truth. Validity against real deck lists is the check on that, and the index never uses
  the rubric alone.
- Raters judge rules text and play knowledge, not testing. A card whose value depends on a
  rare interaction can be under- or over-rated; `H_sd` and the reason column show where.
- The rubric covers Chulane only. For any other commander it is a missing source.
- Owner marks (favorites, exclusions, notes) and simulation results played no part.

Refs #1358
