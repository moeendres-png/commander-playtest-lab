# MTGJSON cross-check of global_inclusion (Chulane pool)

**Date:** 2026-11-15 · **Issue:** #1367 (part of #1363) · **Class:** data quality finding, not a signal

MTGJSON is used here only to check the EDHREC-derived `global_inclusion` component from the
outside. It replaces no value and feeds no index. A unit test
(`tests/unit/test_mtgjson_not_in_index.py`) asserts that no module under
`src/commander_lab/studio` mentions MTGJSON. `edhrecSaltiness` is shown for information only.

## Provenance

| Item | Value |
|---|---|
| MTGJSON file | `https://mtgjson.com/api/v5/AtomicCards.json.gz` (public, plain GET, nothing sent) |
| MTGJSON build | date 2026-11-14, version 5.3.0+20261114 (`Meta.json`) |
| Last-Modified | Sat, 14 Nov 2026 06:13:26 GMT |
| Downloaded | 2026-11-15 10:14:05 UTC |
| Size / SHA-256 | 52,696,276 bytes / `81d14ea049a2a47e792373e947b223a68b4980142bdbc01264fd044d87bd8ede` |
| Our side | Studio store with the Chulane corpus (EDHREC global component of the strength index), `strength_view.compute`, first preset (Ausgewogen = default settings) |
| Script | `scripts/mtgjson_global_inclusion_check.py` (re-runnable, paths as arguments) |

The MTGJSON file was treated as untrusted data and parsed with `json` only. The per-card
`global_inclusion` value is the component share (numerator / denominator, see the table
column "share"); the 922 ranked cards are those with a tier other than N/U (5 cards are not
ranked under the default settings).

## Method

1. Match by oracle name, case-insensitive. MTGJSON keys multi-face cards by the full name
   with ` // `; the first face name is also indexed. If both faces carry a rank the better one
   is used.
2. Popularity = `-edhrecRank` (rank 1 is the most popular card), compared with our
   `global_inclusion` share.
3. Spearman rank correlation (Pearson on mean ranks, ties share the mean rank) for all matched
   cards, for spells and for lands.
4. Percentile = (mean rank - 1) / (n - 1) inside the matched cards of the same group (spells,
   lands), separately for both measures. A card is listed when
   **|share percentile - MTGJSON percentile| > 0.25** (threshold proposed in the issue, fixed
   before looking at the data).

## Result

- **Matched: 922 of 922 ranked cards** (no unmatched name).
- Spearman, all: **0.965** (n = 922); spells: **0.964** (n = 857); lands: **0.916** (n = 65).
- Median |Δ percentile| spells 0.033, lands 0.078; 90th percentile 0.139 (spells), 0.188 (lands);
  largest 0.381 (spells), 0.281 (lands).
- Cards above the threshold: **17** (16 spells, 1 land), listed below
  (Δ = share percentile - MTGJSON percentile; positive means our share ranks the card as more
  popular than the MTGJSON rank does).

| Card | Group | edhrecRank | edhrecSaltiness | MTGJSON pctl | share pctl | Δ | numerator / denominator |
|---|---|---:|---:|---:|---:|---:|---|
| Emergency Phytomedic // Seed Suture | spells | 20,633 | 0.04 | 0.293 | 0.674 | +0.381 | 2,155 / 348,372 |
| Tam's Resistance | spells | 24,108 | 0.04 | 0.175 | 0.549 | +0.374 | 1,080 / 365,009 |
| Vigorbloom Charm | spells | 10,972 | 0.24 | 0.535 | 0.908 | +0.373 | 11,768 / 348,372 |
| Swords to Plowshares | spells | 6,325 | 0.31 | 0.669 | 0.998 | +0.328 | 3,007,376 / 4,921,723 |
| Gardenize | spells | 11,441 | 0.4 | 0.522 | 0.811 | +0.289 | 10,968 / 682,008 |
| Transformative Commons | lands | 16,591 | 0.02 | 0.016 | 0.297 | +0.281 | 4,486 / 326,554 |
| Loot, the Nexus | spells | 14,971 | 0.34 | 0.443 | 0.720 | +0.277 | 5,991 / 691,864 |
| Prudent Fateseer // Peer Review | spells | 20,624 | 0.14 | 0.294 | 0.571 | +0.277 | 2,153 / 672,771 |
| Teyo, Lightshield Expert | spells | 16,362 | 0.11 | 0.409 | 0.675 | +0.266 | 4,742 / 764,431 |
| Plan for All Outcomes | spells | 12,750 | 0.11 | 0.488 | 0.754 | +0.265 | 8,484 / 761,645 |
| Flourishing Grapple | spells | 26,094 | 0.29 | 0.125 | 0.389 | +0.264 | 715 / 701,770 |
| Saheeli, Consul of Oversight | spells | 18,513 | 0.05 | 0.352 | 0.616 | +0.264 | 3,127 / 744,535 |
| Mindseeker Oculus | spells | 20,956 | 0.18 | 0.273 | 0.534 | +0.261 | 2,028 / 761,645 |
| Tethermage's Advantage | spells | 24,008 | 0.1 | 0.181 | 0.438 | +0.257 | 1,152 / 764,525 |
| Flickering Hound | spells | 6,802 | 0.72 | 0.648 | 0.903 | +0.255 | 24,603 / 764,431 |
| Inspired Tethermage | spells | 23,517 | 0.02 | 0.196 | 0.450 | +0.254 | 1,228 / 774,006 |
| Mind Meanderer | spells | 31,232 | 0.01 | 0.019 | 0.270 | +0.251 | 152 / 331,095 |

## Interpretation

The two sources agree strongly (rho = 0.96). A wrong scale, a swapped column or a broken
join in `global_inclusion` would have destroyed that agreement, so the component is plausible
as a data source.

All 17 deviations have a positive Δ: our share ranks them higher than the MTGJSON rank does,
and none goes the other way. They are not errors we can prove. Two plausible causes (not
tested here):

- **Different population.** The MTGJSON rank is one global order over all cards. Our share is
  a count over the decks of a colour identity (denominators here run from 326,554 to
  10,542,169 decks), so a card that is popular only inside its colours (Swords to Plowshares,
  3,007,376 of 4,921,723) is ranked higher by share than by the global rank.
- **Low counts.** Several deviating cards have a numerator of about 1,000 to 5,000. The ordering
  among such cards in the lower half is noisy.

No card deviates by more than 0.381 percentile, and no deviation pattern points to a fault in
the import. No value was changed.

## Limits

- One MTGJSON build, one commander pool, one point in time; ranks move daily.
- `edhrecRank` and our share both derive from EDHREC, so this is a consistency check of one
  upstream through two paths, not independent evidence of card strength.
- Percentiles are relative to the matched pool, not absolute.
- The threshold 0.25 is a documented convention, not a statistical test.
- The report holds pool card names and aggregate numbers only, no collection quantities.
