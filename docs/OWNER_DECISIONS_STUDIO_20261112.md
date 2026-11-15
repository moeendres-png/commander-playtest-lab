# Owner decisions: Commander Studio, state 2026-11-15

**Purpose.** One place for the Owner decisions taken between 2026-11-10 and 2026-11-15 on the
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
| A6 | By Owner decision 2026-11-13 (`data/research/collection_1655/`) and Owner relaxation 2026-11-15 (`AGENTS.md` §12), the former ban keeping collection, deck, and store card lists strictly local is lifted: collection/deck/store data may leave the Owner's machine, live in the working/private repository, and query external public MTG APIs/tools without local-only blocking. Only credentials, secrets, raw tokens, and unrelated personal/third-party names stay strictly redacted/local. | `AGENTS.md` §12, Owner instructions 2026-11-13 & 2026-11-15 |
| A7 | Several agents may work in parallel, each on its own issues. One issue has one working owner at a time; another active agent's open issue or pull request is not overwritten without handover, except that the Owner-appointed Development Lead may take over, review, integrate, and merge handed-over or completed items under `AGENTS.md` §8 and §10. | Owner messages 2026-11-11, 2026-11-12, and 2026-11-15 |
| A8 | A fork push, a repin, rewriting sealed qualification records (and touching `WS17_SHA256SUMS` outside S3 D5 root manifest regeneration for `pyproject.toml`), the release of five and six seats, publication and repository visibility each need their own Owner go. Java bridge changes for the Studio merge under the Studio bridge gate (`AGENTS.md` §10, `docs/STUDIO_PLAN_SIMULATOR.md`), and the Owner-appointed Development Lead holds full Coordinator/Lead decision and merge authority across `moeendres-png/commander-playtest-lab`. | Owner decision 2026-11-10, changed 2026-11-12 (evening) & 2026-11-15 |

## BUILD: Commander deck building

| # | Decision | Source |
|---|---|---|
| B1 | BUILD has the highest product priority. It works on the Owner's own collection (`collection_1655` in repo); purchase mode ("Zukauf-Feature") and card value/price signals are explicitly not needed for Chulane (Owner confirmation 2026-11-15). | Owner decisions 2026-11-10 & 2026-11-15 |
| B2 | Chulane, Teller of Tales stays the only active owner deck for optimization and the reference for every data step. | `docs/OWNER_DECK_FOCUS_CURRENT.md`, issue #1210 |
| B3 | More commanders are supported as data cohorts: Tam as the second cohort, then the other commander-capable cards of the collection. Source decks, published statistics and simulations are bound to one commander; figures of two commanders are never counted together, and "all" never means a mixed denominator. | Issues #1187, #1210 |
| B4 | Favorites, exclusions and notes are the Owner's own marks. They stay marked and can be filtered, but they are never a positive rating and never move a card up in the tier list. | Owner message 2026-11-11 |
| B5 | Evidence layers stay separate: facts and rule-derived features, observed in decks, observed in games, verified combos, simulation results. EDHREC inclusion and lift are never one field. A card that is absent from a known corpus is a missing observation, not a weak card. | Issue #1185 |
| B6 | The tier list is a parametrized function over objective signals: inclusion in the deck universe the Owner chose, co-occurrence, combo counts. Salt and price are separate markers only (price/value omitted for Chulane). Insufficient data gives tier U, never a guessed tier. | Issue #1205, Owner message 2026-11-15 |
| B7 | The Owner sets which decks count: deck universe profiles (source, bracket, theme, period, minimum sample) are a setting in every view that shows inclusion. | Issue #1205 |
| B8 | The corrected inventory workbook is the canonical inventory format. A difference between workbook and public card data is listed and decided by the Owner, never silently overwritten. | Issue #1208 |
| B9 | Pool membership of newly added cards is only a reliable state together with their engine status; a card the pinned engine does not know is `UNKNOWN` or `NOT_MEASURED`. | Issue #1209 |
| B10 | The tier list shall show card strength better, use the collected data, and give the Owner settings. It gets a strength index per card and commander: an estimate from usage signals (EDHREC inclusion per commander and bracket, counted deck lists, tournament lists, synergy, combo counts), each turned into a rank within the commander's pool and combined with weights the Owner sets. It always shows its components with numerator and denominator, is labelled as an estimate and not as a measured win rate, and gives "too little data" instead of a guessed tier. The outcome-based field stays unrated until games support it (B5, B6). Own marks never enter it (B4). Recommendation of the planning thread, placeholders the Owner may change (2026-11-13): minimum data situation 0.3 (setting `min_coverage`, shown as "Mindest-Datenlage"), a tier needs at least one signal specific to the commander (`require_commander_signal`), and the deck universe is chosen automatically (`universe_source` `auto`, see B12). Default cuts (currently `54/35/20/5` in `#1366` / PR `#1383`) are calibrated and decided by the Development Lead under `AGENTS.md` §8 (delegated 2026-11-15). | Owner messages 2026-11-12 & 2026-11-15 |
| B11 | Simulationsergebnisse zählen nicht in die Tierliste und werden dafür vorerst weder eingeholt noch verarbeitet. Das Gewicht `simulation` bleibt als Option bestehen und steht in Standard und allen Voreinstellungen auf 0. Auch die Anzahl vorhandener Schichten (Sortierung, Abdeckungsliste) zählt die Simulationsschicht nicht mit. | Owner decision 2026-11-12 |
| B12 | Gezählte Decklisten-Verbreitung zählt standardmäßig im Stärke-Index mit; 0 von N Decks ist ein echter Wert. Das Gewicht stellt der Owner ein, 0 schaltet es ab. Lokale Decklisten haben Vorrang vor der Zähldatei im Repo (Owner, 2026-11-13). | Owner decision 2026-11-13 |

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
| S5 | An engine look-ahead in Java may be built as a measured experiment under the Studio bridge gate; the measurement of 2026-11-11 (look-ahead by restart) left its benefit undecided. It becomes the default only if a paired series shows a benefit. | Issue #1168, Owner decision 2026-11-12 (evening) |
| S6 | No own rules engine in another language: XMage stays the rules authority (A2). Series are made faster around it: several games per JVM, parallel engine processes, a leaner exchange per decision, measured before and after. A draw and mana simulator without rules may answer hand and land questions. | Owner message 2026-11-12 (decision delegated), issue #1251 |

## PLAY: playing Commander oneself, 2 to 6 seats

| # | Decision | Source |
|---|---|---|
| P1 | One human picks a legal 100-card Commander deck and plays complete games against one to five AI seats. | Owner decision 2026-11-10, issue #1169 |
| P2 | No time limit for the human. AI turns run at an adjustable speed. | Issue #1169 |
| P3 | The AI always plays at full strength. A slider sets only its style, from aggressive to controlling. | Owner decision 2026-11-10 |
| P4 | No sandbox and no free undo. | Owner decision 2026-11-10 |
| P5 | In play mode the page receives only what the engine publishes to the human's seat. Hidden information of the AI seats is not delivered, not merely hidden. | Issue #1169, `AGENTS.md` §5 |
| P6 | Full card images are always shown; card names may go to the free public image source (`AGENTS.md` §12). | Owner decision 2026-11-10 & 2026-11-15 |
| P7 | Making the decision time limit of the bridge configurable is a Java change under the Studio bridge gate; the default stays two minutes. | Issue #1169, Owner decision 2026-11-12 (evening) |

## Open Owner decisions

1. The default weights and presets of the strength index (B10) are adjustable by the Development Lead within calibration bounds and by the Owner in the UI; the reading on B5 and B6 stays for the outcome-based field (tier cuts delegated to Development Lead under `AGENTS.md` §8, 2026-11-15).
2. (Decided 2026-11-12, evening: bridge changes for the Studio go through the Studio bridge gate.)
3. The one recorded fact difference of issue #1208 (workbook against public card data) if still unresolved outside `collection_1655`.
4. Release of five and six seats after their own qualification (A8).
5. Whether bracket 5 deck lists are harvested or only counted (issue #1210; currently parked with `#1210`), and whether Moxfield harvesting (without an official open API) is explicitly authorized for `#1388` step 3.
6. Fork pushes to `moeendres-png/mage`, engine repins (`#1093` / v16), and account-level actions (`#1108`: switching repos to private / Drive access).

The plan that follows from these decisions, with recommendations, is
`docs/STUDIO_ROADMAP_20261112.md`.
