# Phase 7 — Chulane Card Insights: acceptance, instrumentation and statistical test matrix

**Date:** 2026-11-08 · **Status:** ALL CASES PROPOSED, NOT EXECUTED · **Primary specification:** [Phase-7 metric and quality design](PLAYGROUP_LIVE_PHASE7_CARD_INSIGHTS_METRICS_SPEC_20261108.md). Product standard **4P**, hard maximum **6P**. This is no permission to run 7/8P operational games or access data/collections/**.

Each test must capture exact lab/engine SHA, bridge JAR hash, Chulane deck snapshot/hash from approved source, pilot/policy version, seed, pod, actor seat, event-offset range, outcome/status, metric version and whether the source exposes the exact required event. No synthetic rule resolver, hidden-card peeking or fabricated native effect is permitted. A metric missing its required fact is **UNKNOWN**, not 0 or PASS.

## A. Card visibility, residence and cast truth

| ID | Scenario | Required observed result | Gate |
|---|---|---|---|
| A01 | Chulane 4P kept opening hand has seven known cards, while opponents are present | Own card instances assigned hand-entry index 0; other seats receive only hand counts; correct library size | P0 privacy |
| A02 | Draw a card normally and cast it during same own turn | One library→hand entry + one native cast reaching stack; hand dwell 0; exactly one drawn-to-cast numerator | P0 truth |
| A03 | Draw a counterspell, retain across two own turns and cast on opponent turn | Own-turn-index delta correct; counter is not “bad dead draw” because it was not cast on curve; native offer recorded | P0 truth |
| A04 | Creature returned to hand by Whitemane Lion, then recast | New **hand interval**, one original physical card, no new natural draw; multiple native casts recognized | P0 Chulane |
| A05 | Card discarded, exiled or shuffled from hand without a cast | Noncast competing exit; no cast-count inflation; reason and exposure status retained | P0 truth |
| A06 | Game ends while card remains in hand; early player elimination | Censored/unplayed classification and outcome reason separate; no invented no-value score | P0 statistics |
| A07 | Underlying card name has adventure, split or modal face; duplicate spell option appears | Canonical instance name and cast face linked; per-physical-card count not multiplied by spell options | P0 source |
| A08 | Card copied, manifested, tokenized or put onto battlefield without casting | Correct physical-vs-copy/token and enter-vs-cast distinctions | P0 source |

## B. Chulane mechanics, on-curve and attribution

| ID | Scenario | Required observed result | Gate |
|---|---|---|---|
| B01 | Nonland mana value 3 cast on own third turn; earlier through ramp; late on turn 5 | On/before MV, early and late bins unambiguous; denominator **first eligible native casts only** | P0 metric |
| B02 | Alternately costed or zero-MV/X/split/Adventure commander-tax cast | Versioned reference-MV rule and explicit exception/eligibility flag; no cheap-cast false curve score | P0 metric |
| B03 | Commander cast from command zone, removed and recast with tax | First commander cast tracked separately from library draw; command recast distinct, no phantom draw | P0 commander |
| B04 | Cast creature while Chulane is on board and his cast trigger resolves | Observe native cast trigger, real card drawn, optional land placed; no inferred additional draw if trigger countered/stifled | P1 attribution |
| B05 | Whitemane Lion bounce chain and multiple Chulane triggers | Real source-event links, separated repeated hand intervals and no duplicate effect counting | P1 Chulane |
| B06 | Academy Manufactor creates a Clue, Food and Treasure instead of normal single type | Native replacement and three actual token objects, not a text-based 3× heuristic; source link direct or UNKNOWN | P1 Chulane |
| B07 | Psychosis Crawler and/or Mechanized Production winline | Damage only if native damage/life event, alternate victory only if engine terminal event; card source unknown if not certifiable | P1 Chulane |
| B08 | Chulane creature-heavy battlefield suffers wipe and redeploys | Real lost permanents, protected pieces and own-turns-to-rebuild; Clues not treated as creatures | P1 resilience |

## C. Statistical denominators, sample limits and variant inference

| ID | Scenario | Required observed result | Gate |
|---|---|---|---|
| C01 | Draw-to-play with seven seen, three cast, one discarded, three in hand at finish | Show exact **3/7** only for this constructed fixture, and separately report exit/censor counts; not a real performance result | P0 metric |
| C02 | Same priority window offers card ten times before one cast | Distinct instance exposure not counted ten times; per-window cast rate shown separately with correct denominator | P0 metric |
| C03 | Raw report has failure, nonterminal decision cap and complete games | Publication reports attempted, valid terminal, failures and stop reasons, no silent selective deletion | P0 quality |
| C04 | 4P game vs 6P game with same number of Chulane wins | Rates and baseline 25% vs 16.67% stratified; not merged into 25% unlabelled winrate | P0 quality |
| C05 | Multiple Chulane seat rotations from identical seed/pod, paired variant A/B | Use seed/pod cluster as inference unit; do not count four rotations or thousands of decisions as independent games | P1 inference |
| C06 | Card cast correlates with survival but is not causal | Observable gap labelled CORRELATIONAL with time-to-cast/available-mana warning; no auto-add/cut recommendation | P0 inference |
| C07 | Candidate changes one card but study too small to detect 5pp gain | UNDERPOWERED / NO_CLEAR_DIFFERENCE, not proof of equal winrate; list detectable effect/CI | P1 inference |
| C08 | Compare many candidate cards and interim peeks across seed blocks | Prespecified primary endpoint, cluster-robust/paired interval, sequential and multiplicity adjustments as existing comparator requires | P1 inference |

## D. Security, repeatability, provenance, performance

| ID | Scenario | Required observed result | Gate |
|---|---|---|---|
| D01 | Spectator sees game while Chulane player draws, searches or reveals private hand | Zero unauthorized card names, art URLs, private prompts or orchestration replay contents in spectator/event payloads | P0 security |
| D02 | Another player's turn is controlled under native CR 723 | Only native-authorized deciding principal gets temporary private state; collector records correct authorized reader and expires grants | P0 security |
| D03 | Capture same locked 4P game in fresh process twice | Canonical metric counts and digest match for same exact recorded semantic choices; no forced RNG/choice injection | P0 reproducibility |
| D04 | Native public event has no reliable source-object match | EffectObservation.quality UNKNOWN; no fabricated Chulane trigger or damage contribution | P0 truth |
| D05 | Chulane 6P high-cardinality board/token/trigger game | Actor-private telemetry bounded to disk; engine does not block on analytics, measure per-game CPU/RSS/disk cost, no 7+ session | P1 performance |
| D06 | Browser/replay tries to obtain per-card private lifecycle and opponent hidden cards | Auth fail closed; public card summary contains **only** permissible aggregated outputs; no raw replay/seed/deck exposure | P0 security |
| D07 | External Playgroup page has stale count or different rounded denominator | Source URL, retrieved_at, metric cohort and original published value captured, external label/attribution; no false reconstructed n/N | P0 provenance |
| D08 | A/B Chulane active-deck PR unmerged, test configured with earlier main data | Fail source/deck hash gate; do not silently run RogShai or claim Chulane deck-qualified from an outdated branch | P0 project scope |

## Data-driven review gate

**Truth gate:** all candidate metrics M01–M17 must document their numerator/denominator; missing native identities, interrupted games and absent source links produce UNKNOWN/CENSORED rather than zeros.

**Privacy gate:** no observer/other seat sees private lifecycle card names, raw native IDs, decklists, seeds or cross-actor event content. Test actual serialized bytes/network frames after implementation, not merely a Python mock.

**Rules gate:** collector is read-only. XMage remains the only engine for cast, move, damage, trigger, combat, win, target and priority. Analytics may not create game actions or modify Rules RNG.

**Precision gate:** 4P matched A/B pods, seat rotation and seed clusters; sample and detectable effect disclosed. Playgroup aggregate metrics are external descriptive only. 6P requires separate runtime and report qualification; hard cap 6.

**Publication gate:** a promising but small observational card delta never directly edits the official Chulane deck or declares a card objectively bad.

## Sources

[Phase-7 definition](PLAYGROUP_LIVE_PHASE7_CARD_INSIGHTS_METRICS_SPEC_20261108.md) · [Playgroup Card Atlas](https://playgroup.gg/cards) · [Chulane aggregated stats](https://playgroup.gg/commanders/2143-chulane-teller-of-tales) · [Playgroup methodology](https://playgroup.gg/about) · [Existing deck variant workflow](../DECK_VARIANT_WORKFLOW.md) · scripts/pilot_decision_report.py · engine-bridge/src/main/java/org/commanderlab/xmage/XmagePublicEventWatcher.java · src/commander_lab/models/diagnostics.py.

**All 32 cases remain NOT_RUN.** This is a measurement plan and verification design, not a finished Card Insights feature.
