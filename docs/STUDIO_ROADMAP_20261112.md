# Commander Studio: plan and recommendations, 2026-11-12

Plan for the three areas of the Studio. It follows the Owner decisions in
`docs/OWNER_DECISIONS_STUDIO_20261112.md` (cited as A1..P7) and names, per step, what is
recommended and what needs an Owner decision first. Planning document, not Source Truth:
Git, tests and issues win. Step names (M4, M5, ...) continue those of issue #1167.

## Where the Studio stands

| Area | In `main` | Open |
|---|---|---|
| BUILD | Store with revisions and variants, legal pool, data check, roles with origin, source-deck counts, EDHREC snapshots, Playgroup card atlas, six verified Chulane combo lines, own marks, commander binding of all source data (#1187), deck universes and counted tiers on the command line (#1205) | counted tiers in the tier page, coverage of the new collection cards (#1208, #1209), deck lists for more commanders (#1210), open deck-builder wishes (#1174) |
| SIMULATE | Full XMage games from the Studio, game log, series runner with paired seeds and interval, style slider and deck plan for the pilots | series bound to commander and deck revision in every view, five and six seats, stronger pilots in general, card view over a series |
| PLAY | Spectator view of a real game: table, stack, hand, log, combat, targets, exile, token images | the human seat (#1169), which needs a Java bridge change and therefore an Owner go |

## Recommended order

1. **Finish the data foundation of BUILD before more views.** Commander binding (B3) first,
   because every later count depends on it: once deck lists of more commanders are in the
   store, an unbound count mixes commanders. Then universes and counted tiers (B6, B7), then
   coverage of the new cards (B9).
2. **PLAY human seat next, as the one step that needs a decision now.** Everything except
   the merged bridge change can be prepared without a go (P7). Recommendation: give the go,
   because the change is small (one system property, default unchanged) and PLAY cannot
   exist without it; plan the requalification together with the next fork batch so that it
   runs once.
3. **SIMULATE: use what exists, measure, then decide on pilot strength.** Run real series for
   Chulane with the series runner, look at the logs, and only then choose where the pilots
   lose most. No micro series (S2).
4. **Five and six seats last**, after four-seat PLAY and SIMULATE are in daily use, with
   their own qualification (A8).

## BUILD: Commander deck building

| Step | Content | Recommendation |
|---|---|---|
| B-1 | Bind source decks, published statistics, neutral boards and simulation runs to one commander; choose the commander in deck builder and tier list (#1187 P0) | Done with store schema 10. A stored row without a commander is counted for nobody and shown as such. Existing stores are migrated once, because until now they held one commander. |
| B-2 | Deck universes and counted tiers (#1205; store and command line are in `main`) | Next: build the tier page on the evidence layers: the counted tier is one more column with its universe and denominator; the outcome-based field stays unrated (reading on B5 and B6). One setting for the universe, used by pool, card detail, tier list and comparison groups, so that two views can never show different denominators. |
| B-2a | Strength index in the tier page (B10): signal import (`import-signals`), weights, bracket, presets and saved profiles | Built. Next: add game outcomes per card (opening-hand comparison) as a component once a series is large enough, with its interval. |
| B-3 | Import path for the second commander (Tam, #1187) | One generic importer for "register plus card parts plus commander" that takes the commander as an argument, instead of a second special importer. Import into an isolated test store first, then the Owner imports locally. The REVIEW set stays out. |
| B-4 | New collection cards (#1208, #1209) | Recompute the pool and the gap matrix from the imported workbook; publish counts only. Cards the pinned engine does not know stay `UNKNOWN` and are listed, because they are the work list for card support. |
| B-5 | Engine check inside the deck builder (#1174 point 2) | A named second check next to the data check: "checked by the engine" with engine pin and time. Now possible because engine provisioning is in `main`. |
| B-6 | Combos in the deck, land advisor, archetype marks (#1174 points 4 to 6) | Combos first: the data and six verified lines exist. Land advisor as observation with comparison groups from the chosen universe, never as a rule. Archetype marks only from source tags, never assigned by an agent. |
| B-7 | Purchase mode (#1174 point 7) | Later, as decided (B1). Design the pool query now so that "owned" is a filter and not built into the data model. |

Risks: two agents changing the store schema at the same time (agree on the schema number in
the pull request before merging); private data in the public repository (A6).

## SIMULATE: automated Commander games, 2 to 6 seats

| Step | Content | Recommendation |
|---|---|---|
| S-1 | A first real Chulane series: at least 30 games, four seats, fixed pods, paired seeds for base and one variant | Do now with the existing runner. It is the first measured basis for every later choice. Report interval and "no reliable difference" plainly (S3). |
| S-2 | Bind every series to commander, deck revision, engine pin and pilot version; show it only under that commander | Part of B-1. A series of another deck revision is never shown as a result of the current list. |
| S-3 | Card view over a series: drawn, cast, in won and lost games, each with denominator | After S-1, from the logs that exist. Label as observation of this series, never as card strength. |
| S-4 | Pilot strength in general (S1) | Take the three most frequent loss patterns from the logs of S-1 and fix those, each with a paired series before and after. No look-ahead in Java without a go (S5). |
| S-5 | Opponents: fixed pods and seeded random pods from the precon pool | Keep both. Fixed pods for comparisons over time, random pods against overfitting to three opponents. |
| S-5a | Throughput (#1251, S6): measure where a game spends its time, then several games per JVM and parallel engine processes | Before S-3 and S-4, because card outcomes need thousands of games per deck. No own rules engine. |
| S-6 | Five and six seats | After S-1 to S-4. Needs its own qualification and the Owner's release (A8). Measure run time first: a four-seat game takes about a minute on four cores. |

Risk: series take long. Recommendation: several games per JVM, a resumable series with a
stored seed list, and a visible "x of n" in the page.

## PLAY: playing Commander oneself, 2 to 6 seats

| Step | Content | Recommendation |
|---|---|---|
| P-1 | Bridge: decision time limit through a system property, default unchanged (P7) | Merges under the Studio bridge gate (`AGENTS.md` §10, Owner decision 2026-11-12, evening); no new sealed epoch. |
| P-2 | Python: a policy that waits for the page for the human seat and asks the pilots for all other seats | Can be built and tested now against a fake engine, without the bridge change. |
| P-3 | Own read path for play mode (P5) | Build before the page. The log of a game contains the AI hands at their decisions; play mode must be served from the human seat's published view only. Test: no card of an AI hand appears in any play-mode response. |
| P-4 | Page: options as buttons and clickable cards, multiple choice with minimum and maximum, number input, pass only where the engine offers it; no undo (P4) | Reuse the spectator view; the page only shows options and returns the choice (A2). |
| P-5 | AI speed and style slider, concede | Pass the existing parameters through. |
| P-6 | Deck choice with engine check before the start | Uses B-5. A deck the engine cannot import does not start a game and says why. |
| P-7 | Five and six seats | With S-6. |

Done when the Owner plays one complete game with Chulane against three AI seats on his own
machine without a time limit, and the qualification runs with default values are unchanged
(issue #1169).

## Open decisions for the Owner

The list is in `docs/OWNER_DECISIONS_STUDIO_20261112.md`, section "Open Owner decisions".
The one that blocks most is the go for the bridge change (P-1).

## Checks and gates

Recommendations for CI are in `docs/CI_GATES_IMPROVEMENT_PLAN_20261112.md`.
