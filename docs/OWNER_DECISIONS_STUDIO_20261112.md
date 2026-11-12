# Owner decisions: Commander Studio, state 2026-11-12

**Purpose.** One place for the Owner decisions taken between 2026-11-10 and 2026-11-12 on the
three areas of the Commander Studio: **BUILD** (Commander deck building), **SIMULATE**
(automated Commander games, 2 to 6 seats) and **PLAY** (playing Commander oneself, 2 to 6
seats). It adds to `docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md` and does not
replace it. Governance only: no code, engine pin, sealed evidence, canonical deck or
inventory changes with this document.

**How to read it.** Every decision names its source. Sources are the Owner's own
instructions: his project messages of the named day, or an issue he opened as an Owner
assignment. Where a line is a reading by an agent and not the Owner's own words, it says so.
When a later Owner instruction differs, the later instruction wins and this file is updated.

## Applies to all three areas

| # | Decision | Source |
|---|---|---|
| A1 | One free, local application with three areas that share decks, card data, rules and game states. No hosted service, no paid service. | Owner decision 2026-11-10 |
| A2 | XMage is the sole rules authority. Neither the web page nor Python decides a rule. | Owner decision 2026-11-10, `AGENTS.md` §2 |
| A3 | Two to six seats, four by default. This holds for PLAY and for SIMULATE. | `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`, Owner message 2026-11-12 |
| A4 | Only objective data with provenance: counts, published source values, engine measurements. No opinions, no invented weights, no estimated win rates. `UNKNOWN` is never 0 and never PASS. | Issues #1185, #1187, #1205 |
| A5 | Every count carries its denominator. Cohorts are never added together. A REVIEW data set never silently becomes ACTIVE. | Issues #1185, #1187 |
| A6 | Collection, deck and ownership data stay outside the public repository; only code and counted results are committed. Nothing about the Owner's decks or collection goes to an external service. Card or commander names may be fetched by plain GET, triggered manually, cached locally. | `AGENTS.md` §12, issues #1205, #1208 |
| A7 | Several agents work in parallel, each on its own issues. One issue has one working owner at a time; another agent's open issue or pull request is not touched without a handover. Research is handed over as issues. | Owner messages 2026-11-11 and 2026-11-12 |
| A8 | A change to the Java bridge, a fork push, a repin, a change to sealed qualification records, the release of five and six seats, publication and repository visibility each need their own Owner go. | Owner decision 2026-11-10 |

## BUILD: Commander deck building

| # | Decision | Source |
|---|---|---|
| B1 | BUILD has the highest product priority. It works on the Owner's own collection first; a purchase mode for cards he does not own comes later. | Owner decision 2026-11-10 |
| B2 | Chulane, Teller of Tales stays the only active owner deck for optimization and the reference for every data step. | `docs/OWNER_DECK_FOCUS_CURRENT.md`, issue #1210 |
| B3 | More commanders are supported as data cohorts: Tam as the second cohort, then the other commander-capable cards of the collection. Source decks, published statistics and simulations are bound to one commander; figures of two commanders are never counted together, and "all" never means a mixed denominator. | Issues #1187, #1210 |
| B4 | Favorites, exclusions and notes are the Owner's own marks. They stay marked and can be filtered, but they are never a positive rating and never move a card up in the tier list. | Owner message 2026-11-11 |
| B5 | Evidence layers stay separate: facts and rule-derived features, observed in decks, observed in games, verified combos, simulation results. EDHREC inclusion and lift are never one field. A card that is absent from a known corpus is a missing observation, not a weak card. | Issue #1185 |
| B6 | The tier list is a parametrized function over objective signals: inclusion in the deck universe the Owner chose, co-occurrence, combo counts. Salt and price are separate markers only. Insufficient data gives tier U, never a guessed tier. | Issue #1205 |
| B7 | The Owner sets which decks count: deck universe profiles (source, bracket, theme, period, minimum sample) are a setting in every view that shows inclusion. | Issue #1205 |
| B8 | The corrected inventory workbook is the canonical inventory format. A difference between workbook and public card data is listed and decided by the Owner, never silently overwritten. | Issue #1208 |
| B9 | Pool membership of newly added cards is only a reliable state together with their engine status; a card the pinned engine does not know is `UNKNOWN` or `NOT_MEASURED`. | Issue #1209 |

**Reading by the agents on B5 and B6 (to be confirmed by the Owner).** A counted tier
describes how often a card is observed in the chosen deck universe. It is shown with its
universe, numerator and denominator and is not a statement about card strength. A strength
tier backed by game outcomes still needs a validated outcome model; until one exists that
field stays unrated.

## SIMULATE: automated Commander games, 2 to 6 seats

| # | Decision | Source |
|---|---|---|
| S1 | The pilots are made strong in general: always the best available legal play, including waiting. A game plan per deck never outranks winning or avoiding a loss. | Owner decision 2026-11-10 |
| S2 | No new pilot micro measurement series. Evaluation means game logs and win rates over many games. | Owner decision 2026-11-10 |
| S3 | Results are observations of one series: with denominator and uncertainty range, base against variant only paired on the same seeds, and "no reliable difference" shown plainly. Aborted or failed games are reported separately and are not losses. | Issue #1170 |
| S4 | XMage's own AI players are not used as seats. | Owner decision 2026-11-10 |
| S5 | A stronger pilot through an engine look-ahead in Java is not built without an Owner go; the measurement of 2026-11-11 left its benefit undecided. | Issue #1168 |

## PLAY: playing Commander oneself, 2 to 6 seats

| # | Decision | Source |
|---|---|---|
| P1 | One human picks a legal 100-card Commander deck and plays complete games against one to five AI seats. | Owner decision 2026-11-10, issue #1169 |
| P2 | No time limit for the human. AI turns run at an adjustable speed. | Issue #1169 |
| P3 | The AI always plays at full strength. A slider sets only its style, from aggressive to controlling. | Owner decision 2026-11-10 |
| P4 | No sandbox and no free undo. | Owner decision 2026-11-10 |
| P5 | In play mode the page receives only what the engine publishes to the human's seat. Hidden information of the AI seats is not delivered, not merely hidden. | Issue #1169, `AGENTS.md` §5 |
| P6 | Full card images are always shown; card names may go to the free public image source. | Owner decision 2026-11-10 |
| P7 | Making the decision time limit of the bridge configurable is a Java change: it may be prepared, but it is merged only after the Owner's go and is followed by a requalification. | Issue #1169 |

## Open Owner decisions

1. Confirm or correct the reading on B5 and B6 above (counted tier next to an unrated strength
   field).
2. Go for the Java bridge change of P7 (human seat).
3. The one recorded fact difference of issue #1208 (workbook against public card data).
4. Release of five and six seats after their own qualification (A8).
5. Whether bracket 5 deck lists are harvested or only counted (issue #1210).

The plan that follows from these decisions, with recommendations, is
`docs/STUDIO_ROADMAP_20261112.md`.
