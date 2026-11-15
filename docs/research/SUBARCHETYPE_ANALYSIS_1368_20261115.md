# Sub-archetypes in the Chulane corpus — analysis for issue #1368

Date: 2026-11-15. Code stand: `main` at `585c9e2f2` (before issue #1364 is merged;
the corpus signals below are therefore computed here, from the corpus, under the
definitions the #1364 plan names — they are not read from a stored #1364 signal).
Evidence class: `DIRECTLY_VERIFIED` (every figure recomputed on a store built from
this repository; build acceptance numbers match the corpus README exactly).
Analysis only — no index input changes; the recommendation in §6 is a proposal,
nothing here is implemented into the index.

Reproduction:

```bash
python -m commander_lab.studio --data "<Studio-Datenordner>" import-all \
    --commander "Chulane, Teller of Tales" --from-repo \
    --scryfall "<oracle-cards.jsonl.gz>" --expect-pool 927
python scripts/subarchetype_analysis.py --data "<Studio-Datenordner>" \
    --out subarchetypes_1368.json
```

Tag rules and signal math live in `src/commander_lab/studio/subarchetypes.py`
(unit-tested on synthetic decks in `tests/unit/test_studio_subarchetypes.py`).

## 1. The canonical deck set

The counted universe of the tier list, resolved the way `universe.py` resolves it
(`resolve_universe` with the commander binding `{"commanders": ["Chulane, Teller of
Tales"]}`): **2,823 decks**. The unfiltered resolution gives 2,845; the difference
is exactly the 22 Archidekt lists that state another commander and carry no Chulane
binding (corpus README). Store acceptance: `corpus_deck` 3,004 (159 duplicates
marked), `corpus_deck_card` 266,539 rows, 266,366 with an `oracle_id` (99.94 %),
role claims 21,272 from the five repo role files plus 1,770 tagger-bulk claims,
legal pool 927 cards.

Bracket of a deck = its stored `bracket:N` cohort (the store's own assignment;
every canonical deck carries exactly one): B1 66, B2 645, B3 958, B4 889, B5 265.
The B4+B5 set behind `corpus_tuned` therefore holds 1,154 decks, the B2 set 645.

Composition basis of every share below: the deck's **distinct cards in the `main`
and `mainboard` sections** with quantity above zero (median 88 distinct cards, 63
of them nonland). The commander/companion sections are not part of a deck's
composition here — the commander is the same card in every deck and would only
shift denominators; this is a deliberate, disclosed deviation from the
`COUNTED_SECTIONS` of `deck_sets`, which does count them. Cards are keyed by
`oracle_id`; the 163 corpus card rows without an unambiguous `oracle_id` are kept
under a name key and count as plain nonland cards (unknown is never a theme card).
2 decks hold no nonland card in these sections; they receive no share tag.

## 2. Tag rules (all thresholds disclosed)

A share is always over the deck's distinct **nonland** cards. A deck may carry
several tags. Each threshold sits near the 80th–90th percentile of its measured
share distribution, so a tag marks a defining theme share, not a splash.

| Tag | Rule | Threshold | Share p50 / p90 | Decks |
|---|---|---|---|---|
| `landfall` | share of cards with role `landfall` or an Oracle text that lets the controller play an additional land | ≥ 0.10 | 0.046 / 0.148 | **545** (19.3 %) |
| `blink_bounce` | share of cards with role `flicker` or `bounce` | ≥ 0.04 | 0.018 / 0.048 | **471** (16.7 %) |
| `big_mana` | share of cards with mana value ≥ 6 ("Koma/Big-Mana") | ≥ 0.12 | 0.063 / 0.159 | **599** (21.2 %) |
| `clue_artifact` | share of cards that are artifacts or whose Oracle text creates Clue tokens / investigates | ≥ 0.15 | 0.095 / 0.182 | **515** (18.2 %) |
| `cedh_combo` | the deck holds **all cards of at least one listed two-card combo** of the commander's combo list (`combos.stored_combos`, the EDHREC combo list: 97 listed combos, 43 of them two-card; name matching by full name and front face, the `combos.py` discipline) | ≥ 1 complete | — | **1,520** (53.9 %) |

Sensitivity (decks at neighbouring thresholds): landfall 773 / 545 / 401 / 279 at
0.08 / 0.10 / 0.12 / 0.15; blink_bounce 1,161 / 471 / 163 / 14 at 0.03 / 0.04 /
0.05 / 0.08 (steep: shares cluster at 2–3 theme cards per deck, so this count is
threshold-sensitive); big_mana 825 / 599 / 335 at 0.10 / 0.12 / 0.15;
clue_artifact 894 / 515 / 209 at 0.12 / 0.15 / 0.20. Complete two-card combos per
deck: 0 in 1,303 decks, 1 in 290, 2 in 250, 3 in 230, 4 in 207, 5 in 159, ≥ 6 in
384 — the `cedh_combo` line at ≥ 2 would give 1,230 decks, at ≥ 3 it gives 980.

Tag multiplicity over the 2,823 decks: no tag 462 (16.4 %), one tag 1,327, two
tags 803, three tags 207, four tags 24, five tags 0.

## 3. Data coverage — where a tag is only partly derivable

Roles (`card_role`) cover 5,484 of the 9,041 distinct corpus cards (60.7 %); a
card without a role counts as a plain denominator card, so every share is a lower
bound of its theme, never an inflated one.

- **`blink_bounce` is only partly derivable — the flicker side is not in the
  data.** The stored roles name 154 corpus cards `landfall` and 30 `bounce`, but
  only **7 `flicker`** (127 decks hold even one flicker-role card, versus 2,236
  decks holding a bounce-role card). The tag therefore measures the bounce side;
  no threshold can fix a missing role, and none was invented. That the tag still
  isolates the intended archetype is visible in its top cards (§4): Shrieking
  Drake is in 97.9 % of tagged decks (corpus 57.0 %), Whitemane Lion in 94.9 %
  (corpus 48.4 %), Kor Skyfisher in 62.0 % (corpus 11.9 %).
- **`clue_artifact` is artifact-driven, and the pure clue theme is small.** 73
  corpus cards create Clues; 443 decks hold at least one clue maker, only 101
  hold two or more. The 0.15 share line mostly selects artifact-dense decks
  (median artifact share of a deck is 0.092 from mana rocks and utility
  artifacts alone). Read the tag as "artifact/clue-token shell", not as a pure
  clue archetype.
- **`cedh_combo` is broad by construction.** The EDHREC combo list also lists
  casual engine pairs (the classic Chulane bounce engines among them), so 53.9 %
  of all decks — including 168 bracket-2 decks — hold a complete two-card combo.
  The tag says "holds a listed two-card combo", not "is a cEDH deck"; its
  bracket profile (B4 692 + B5 247 of 1,520) does rise steeply with bracket.
  The curated `data/meta/spellbook_combos.json` was checked as an alternative
  source and is too thin for tagging: it holds 7 Chulane combos, only 2 of them
  two-card, both including the commander itself.

## 4. The archetypes

Deck counts and bracket profiles (B1/B2/B3/B4/B5), overlaps, and the inclusion
distribution of the 927 pool cards inside the archetype (share of archetype decks
listing the card; corpus reference: p50 0.001, p75 0.005, p90 0.042, max 0.927,
10 pool cards at ≥ 50 %, 358 pool cards in no canonical deck at all):

| Archetype | Decks | Brackets 1/2/3/4/5 | Incl. p75 / p90 / max | Pool cards ≥ 50 % |
|---|---|---|---|---|
| landfall | 545 | 3 / 149 / 241 / 145 / 7 | 0.004 / 0.040 / 0.969 | 20 |
| blink_bounce | 471 | 10 / 96 / 151 / 174 / 40 | 0.002 / 0.040 / 0.979 | 17 |
| big_mana | 599 | 20 / 217 / 230 / 127 / 5 | 0.007 / 0.057 / 0.955 | 7 |
| clue_artifact | 515 | 24 / 149 / 172 / 133 / 37 | 0.008 / 0.043 / 0.880 | 6 |
| cedh_combo | 1,520 | 9 / 168 / 404 / 692 / 247 | 0.002 / 0.033 / 0.953 | 12 |

Overlaps (decks carrying both tags): landfall∩blink_bounce 93,
landfall∩big_mana 192, landfall∩clue_artifact 63, landfall∩cedh_combo 274,
blink_bounce∩big_mana 50, blink_bounce∩clue_artifact 45,
blink_bounce∩cedh_combo 348 (of 471 blink_bounce decks — the bounce engine is
largely a combo engine), big_mana∩clue_artifact 121, big_mana∩cedh_combo 202,
clue_artifact∩cedh_combo 180.

Cards that define each archetype most (inclusion inside the archetype vs in the
whole corpus; pool card names only):

- **landfall:** Tatyova, Benthic Druid 0.835 vs 0.416; Tireless Provisioner 0.681
  vs 0.364; Rampaging Baloths 0.648 vs 0.197; Simic Growth Chamber 0.580 vs
  0.383; Felidar Retreat 0.519 vs 0.152.
- **blink_bounce:** Shrieking Drake 0.979 vs 0.570; Whitemane Lion 0.949 vs
  0.484; Elvish Mystic 0.709 vs 0.530; Kor Skyfisher 0.620 vs 0.119; Azorius
  Chancery 0.516 vs 0.340.
- **big_mana:** Tatyova, Benthic Druid 0.516 vs 0.416; Seaside Citadel 0.406 vs
  0.329; Rampaging Baloths 0.351 vs 0.197; Evolving Wilds 0.319 vs 0.228; Koma,
  Cosmos Serpent 0.127 vs 0.042 (the namesake card triples, from a small base).
- **clue_artifact:** Sol Ring 0.852 vs 0.732; Arcane Signet 0.711 vs 0.498;
  Talisman of Curiosity 0.208 vs 0.069; Talisman of Progress 0.196 vs 0.058;
  Fellwar Stone 0.165 vs 0.059 — mana artifacts, as §3 warns.
- **cedh_combo:** Shrieking Drake 0.822 vs 0.570; Llanowar Elves 0.751 vs 0.600;
  Avacyn's Pilgrim 0.700 vs 0.526; Whitemane Lion 0.694 vs 0.484; Elvish Mystic
  0.686 vs 0.530 — the fast-mana and bounce core of the high brackets.

## 5. Do the corpus signals diverge per archetype?

Definitions (computed here on stand `585c9e2f2`, before #1364; per deck set S and
pool card): `deck_universe` = inclusion share in S; `corpus_log_lift` =
ln(inclusion in S / `edhrec_global_inclusion`), unknown without a positive pair
(global inclusion is stored for all 927 pool cards; two-part cards are matched by
their front face, the repo's name discipline); `corpus_tuned` = inclusion share
in the B4+B5 decks of S; `corpus_bracket_slope` = tuned share − bracket-2 share
in S. Spearman rank correlation over the 927 pool cards (cards undefined on a
side — a log lift without a positive pair — drop out of that pair).

Against the whole-corpus vector:

| Signal | landfall | blink_bounce | big_mana | clue_artifact | cedh_combo |
|---|---|---|---|---|---|
| deck_universe | 0.830 | 0.790 | 0.887 | 0.894 | 0.858 |
| corpus_log_lift | 0.805 | 0.864 | 0.812 | 0.741 | 0.902 |
| corpus_tuned | 0.779 | 0.819 | 0.826 | 0.813 | 0.921 |
| corpus_bracket_slope | **0.539** | **0.560** | **0.523** | **0.715** | **0.654** |

Pairwise between archetypes, the ranges tell the same story: `deck_universe`
0.734–0.877, `corpus_log_lift` 0.627–0.843, `corpus_tuned` 0.744–0.844 — but
`corpus_bracket_slope` only **0.297–0.612** (lowest: big_mana vs blink_bounce
0.297, big_mana vs cedh_combo 0.356, landfall vs big_mana 0.404).

**Interpretation.** The prevalence-type signals do **not** diverge materially per
archetype: which cards are widespread is largely the same ranking inside every
archetype (ρ ≥ 0.74 against the corpus for deck_universe, log lift and tuned
alike). What genuinely reorders per archetype is the **bracket gradient**: the
slope is a difference of two shares, it is the noisiest of the four signals, and
its archetype rankings agree with the corpus ranking only moderately (ρ ≈
0.52–0.72) and with each other weakly (down to 0.30). In plain terms: archetypes
differ less in *which* cards they play than in *how strongly play concentrates
in the high brackets* — and even that difference is measured on the signal with
the smallest effective denominators (an archetype's B2 subset holds 96–217
decks, its B5 subset 5–247).

## 6. Recommendation: no index intervention

**Do not add an archetype filter (or per-archetype signals) to the index.**
Reasons, each tied to a measured figure above:

1. A filter would buy almost nothing for the prevalence signals: their rankings
   are archetype-stable (ρ ≥ 0.74 vs the corpus everywhere), so filtering the
   universe to 471–1,520 decks would mostly shrink denominators and add noise.
2. The one signal that does diverge — `corpus_bracket_slope` — is exactly the
   one whose per-archetype denominators collapse (archetype ∩ B5 as low as 5
   decks for big_mana, 7 for landfall). A per-archetype slope would be a
   difference of two shares over a handful of decks: not a measurement, a
   lottery. If #1364 gives the slope real index weight, the proportionate step
   is a *diagnostic* (report the slope per archetype next to the index, as this
   analysis does), not a filter.
3. Two of the five tags are not clean enough to gate an index on: `blink_bounce`
   cannot see its flicker side in the stored roles (7 cards), and
   `clue_artifact` selects artifact density more than a clue theme (101 decks
   hold ≥ 2 clue makers). `cedh_combo` at 53.9 % of the corpus discriminates
   too weakly to stratify an index by.

Keep the archetypes as what they are here: a descriptive stratification of the
corpus for reports like this one. Revisit only if (a) the role data gains real
flicker coverage, or (b) #1364's slope enters the index with material weight —
then re-run this script on the new stand and re-check §5 before deciding.
