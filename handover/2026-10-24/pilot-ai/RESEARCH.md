# Commander Heuristic AI Pilot — Research Report

## Summary

**Design verdict (synthesis of the sources below):** At a low-millisecond budget, do not search the game tree. Every published / shipped Magic-like AI that searches budgets **seconds per decision** (Magarena, XMage, Forge/Neo Forge, Hearthstone competitions: 1–60 s). The only architecture demonstrated to rival search at trivial compute is **greedy 1-ply over pre-filtered options, scored by a hand-tuned linear delta-evaluation** — a SabberStone Hearthstone agent built exactly that way was runner-up (best ~6%, 2nd of 33) in the 2018 Hearthstone AI Competition against MCTS entrants. Layer on top: (1) hard timing/sequencing rules, (2) exact solvers only inside combat and mana payment, (3) threat-ranked target scoring, (4) fast paths that return `pass` / the sole legal option without evaluating anything.

**Evidence grading used throughout:** **[Measured]** = exact math, tracked data, or published/competition result. **[Shipped]** = documented behaviour of a real open-source AI. **[Opinion]** = expert/community consensus, no measurement behind it. Most of Topic A is [Opinion] — often unanimous, but opinion. Most concrete numbers in Topic B are [Measured]/[Shipped].

---

# SECTION A — How to play Commander well, as implementable rules

## A1. Mulligan strategy (London + free first mulligan)

**Mechanics [Measured — rules/math].** London: always draw 7, then bottom 1 card per *counted* mulligan taken. Multiplayer first mulligan is free (CR 103.5c/e), so the sequence is **7 → 7 → 6 → 5 → 4**. Sources: EDHREC guide quoting CR 103.5/103.5e, and ScrollVault's exact-math article quoting CR 103.5.
- https://edhrec.com/guides/the-edhrec-guide-to-mulligans-in-commander
- https://scrollvault.net/posts/mulligan-math-when-serum-visions.html

**Land-count floor [Measured — exact hypergeometric, 99-card library].** Defining "keepable" *only* as ending with 2–4 lands: with **36 lands**, P(keepable) = **74.0%** on the first 7, **93.3%** after the free mulligan, **98.6%** by 6 cards, **99.7%** by 5. With 33 lands those drop to 70.7% / 91.4% / 97.8% / 99.4%. London selection widens the raw range: a 6-card keep can start from 2–5 lands in the drawn 7 (bottom the 5th land), a 5-card keep from 2–6 — so *a London 6 is more land-stable than a fresh 7; what a mulligan costs is a spell, not mana stability.*
- https://scrollvault.net/posts/mulligan-math-when-serum-visions.html

**Tracked-data cross-check [Measured — observational].** Playgroup.gg's tracked games: **89% of 157,120 kept opening hands held 2–4 lands, averaging 2.96 lands**; it recommends 38–42 lands for casual decks — higher than the ~36-land EDHREC average reported by CoolStuffInc, so treat 36 as a floor, not an optimum, when calibrating a keep threshold.
- https://playgroup.gg/commander/how-many-lands
- https://www.coolstuffinc.com/a/how-many-lands-in-a-commander-deck-04272026

**Keep test — implement as a conjunction of five axes [Opinion — EDHREC guide, expert consensus].** Keep iff all hold:
1. **Lands/mana:** 2–4 lands (accept 2 only with a ≤2-mana ramp/draw piece or a land-fixing chain; reject 0–1 and usually 5+), *and* projected mana by turn 3–4 ≥ commander's cost minus ramp.
2. **Colour:** can produce the colours of the early spells + commander, or fixes them by the turn they're needed.
3. **Curve/sequence:** at least one playable action on ≥2 of turns 1–3 (ideally spells at 2, 3, 4 mana). A hand of payoffs with no enablers ("only one noncreature spell, rest payoffs — mulligan") fails even with a perfect curve.
4. **Plan:** the hand *does the deck's thing* — names a line (e.g. T1 foundry, T2 ramp, T3 commander A, T4 commander B), not just "lands and spells."
5. **Interaction (conditional):** if any opposing commander is kill-on-sight / the pod is fast, require either an early play *or* interaction/protection by the turn that commander lands; a purely proactive sequence is "not enough" in that pod.
Reject the "house of cards": e.g. a 2-land hand that only works if three specific nonland permanents all survive — EDHREC's worked example mulligans it despite a nominal sequence.
- https://edhrec.com/guides/the-edhrec-guide-to-mulligans-in-commander

**How the bar moves with each mulligan [Opinion, split by power level — flag the disagreement]:**
- *Casual/mid-power:* the bar **falls**. DraftSim: a keepable hand is one that "lets you play the first few turns"; "'good enough' is actually great… do not be greedy"; conventional wisdom is **never go below 5**. Pilot rule: at 7 (both looks) require all five axes; at 6 drop the interaction axis and accept 2 lands without fixing; at 5 require only lands 2–4 + one play by turn 2 + a route to the commander; at 4 keep anything with 2–3 lands and a spell.
  - https://draftsim.com/mtg-commander-mulligan-rules/
- *cEDH/fast pods:* the bar **stays high and mulligans are aggressive** — "most cEDH decks shouldn't be afraid to go all the way to five… why look at seven cards when you can look at 28?"; "a strong five with a dork, tutor and Pod line is better than an 'okay seven' doing nothing until turn three." Checklist: *Do I have a line? Do I have mana? Can I stop an early win?*
  - https://edhrec.com/guides/intro-to-cedh
  - https://feedbeater.com/cedh-database-mulligan-theory-for-fast-pods/
- *Why multiplayer licenses one extra mulligan vs 1v1 [Opinion with a math flavour — Commander's Herald / Goonhammer]:* with 4 players, one card matters less (fewer of your cards trade 1-for-1; the table polices itself), and 2nd/3rd/4th are all just losing, so variance-seeking is correct: Goonhammer argues you should average **more than one mulligan per game** and score hands by a point value, keeping only above a threshold.
  - https://commandersherald.com/how-many-lands-should-you-play-in-cedh/
  - https://www.goonhammer.com/commander-101-winning-a-negative-sum-game/

**Bottoming (which cards to put back) [Derived from London math + EDHREC examples]:** bottom, in order: (1) lands beyond 4, (2) the highest-cost card with no route to cast it by ~turn 5, (3) situational/dead cards (the guide flags Tainted Strike/Mirage Mirror-type cards as the acceptable losses), (4) duplicate ramp/engine pieces. Never bottom your only interaction in a fast pod, your only colour source for the commander, or your turn-1/2 play.

## A2. Threat assessment in 4-player games

**Rank permanents/players by time-to-win, not by size [Opinion — two independent guides agree on structure].**

AetherHub's ranked permanent categories (highest first) are directly encodable as a tier table:
**10** anything winning now/inevitably → **9** active mana engine → **8** card-draw engine → **7** powerful commander (deck built around it, always re-accessible) → **6** partial combo (one half in play — remove *proactively*, waiting only gives them time to find the other half) → **5** repeatable interaction → **4** wide board → **3** large creature *with protection* → **2** large creature with evasion → **1** stax piece (note: the article lists stax lowest in its numbering yet says answer it "sooner rather than later" because pieces accumulate — treat stax as *situational*: high if it locks *your* deck, low if you can play under it; EDHREC makes the same point about hate pieces).
- https://aetherhub.com/Article/Threat-Assessment-in-Commander-101-A-Guide-to-Survival

Player-level threat score [Opinion — DraftSim + Card Kingdom]: weight, in descending order, **(a) accessible card advantage (cards in hand + draw engines), (b) mana available next turn (lands + rocks + treasures), (c) board that can kill, (d) life total last** — "people with tons of mana and access to tons of cards are usually the biggest threats… life total is actually one of the least relevant reasons." Pre-game, seed each opponent's prior from their commander alone: low mana value, grants card advantage/mana, or is an obvious combo piece ⇒ high prior.
- https://draftsim.com/mtg-commander-mistakes/
- https://blog.cardkingdom.com/threat-assessment-in-commander/

**Clocks beat totals [Rules + Opinion].** Track three clocks per opponent and take the *minimum*: (i) **life clock** = ceil(their target's life / power they can attack with each turn), (ii) **commander-damage clock** = ceil((21 − commander damage already dealt by *that* commander) / that commander's power) — 21 combat damage from a *single* commander kills regardless of life total, is tracked per-commander, and life gain does not erase it, (iii) **combo clock** = pieces still missing (1 missing piece + a tutor/draw engine in play ≈ imminent).
- https://www.beckett.com/news/what-is-commander-damage-and-how-to-use-it-to-your-advantage/
- https://magic.wizards.com/en/news/feature/commander-2018-edition-release-notes-2018-07-27

**What changes vs 1v1 [Opinion/structural]:**
1. **A threat to the table ≠ a threat to you.** Prioritise threats that hit *your* plan: EDHREC's example — Rest in Peace is an emergency for the graveyard deck and irrelevant to others; "you can't rely on them to deal with it for you… save resources for cards that really impede YOUR gameplan."
   - https://edhrec.com/articles/beginner-content-threats-and-resource-management
2. **Someone else may pay.** With three opponents, the expected value of holding an answer rises: ask "do I have to deal with this now, or can I afford to wait and see if someone else will?" — especially follow in turn order and don't volunteer first (see A3).
3. **Can-kill-one ≠ can-kill-the-table.** Card Kingdom: midgame, discount a threat that "can only kill one player at a time — just make sure that person isn't you"; upgrade one that kills everyone at once.
4. **When you are the threat, invert the question** to "who stops me?" — the opponent with open mana / held interaction is your threat, regardless of their board.
   - https://blog.cardkingdom.com/threat-assessment-in-commander/

## A3. Targeting, removal, politics, and when NOT to act

**Fire rule [Opinion — unusually crisp consensus across three sources]:** Spend targeted removal/counters **iff the target wins (or locks you out) if it survives to its controller's next turn, or is a tier ≥7 engine/commander/combo piece (A2) whose value over a full turn cycle exceeds the removal's future value.** Canonical example: "Spending Swords to Plowshares on a 4/4 beater turn 3 is almost always wrong. Spending it on Thrasios is almost always right… Removal is finite. Don't spend it on the first interesting thing — spend it on the thing that ends the game if it sticks." Removal test in one line: *"Does this card win the game if I don't kill it? If yes, kill it. If no, hold the spell."*
- https://mtgcombotrainer.com/combo-guides/how-to-think-better-mtg

**Corollaries to encode:**
- **Efficiency vs saving:** prefer the *cheapest sufficient* answer whose timing window is closing (a protected/hexproof-soon target, a commander about to untap with it, a spell on the stack). If the window isn't closing, holding is free — the card can still be answered later at the same cost.
- **Wait for turn order / let others answer first [Opinion — CoolStuffInc + AetherHub]:** "Don't get too hasty… follow turn-order" and "be wary of being the sole responder to every problem" — in code: if a later-priority opponent is also threatened and plausibly holds interaction, downgrade your urgency by one step (act only if the threat is lethal-on-resolution). **But** never pass on a game-winning spell on the assumption someone else has it if you are last to act before it resolves.
  - https://www.Coolstuffinc.com/a/cashinds-seo-10232024-the-problem-with-removal-in-commander
  - https://aetherhub.com/Article/Threat-Assessment-in-Commander-101-A-Guide-to-Survival
- **Wipes over spot removal** when the summed tier-weighted value of opposing permanents it removes ≥ ~3 permanents / ≥2 opponents meaningfully set back, and your own board loss is smaller; wide boards (tier 4) are explicitly "simple to answer via a board wipe" rather than 1-for-1s.
- **Choose the target's owner by player-threat (A2), the permanent by tier** — not by who attacked you last. No spite/retaliation term: a Commander primer lists "no spite" and decisions "based on the game" as a core rule.
  - https://nullromo.github.io/kylekovacs/blog/commander-primer/

**Politics / deals / kingmaking — for a pilot with no negotiation channel [Opinion]:** Implement politics as *self-interested restraint only*:
- Deals framework (before any implicit deal): who is winning, who can stop them, does it help *me* more than the table, does helping expose me, does it make me the next target? Help another player **only if** (a) you're behind, (b) the leader wins without intervention, (c) helping doesn't expose you next turn.
  - https://mtgcombotrainer.com/combo-guides/how-to-think-better-mtg
- **Kingmaking ban as a hard rule:** kingmaking = a player who cannot realistically win making choices that determine who *does* win "without improving their own position"; politics is only legitimate when it increases your own win probability. So: **if an action does not increase your own win probability (e.g. spite-removing a non-threat's permanent when you are dead next turn anyway), take the no-op / the action that maximises your own survival instead.** Never spend resources purely to choose the winner.
  - https://cultureofgaming.com/mtg-commander-politics-deals-bribes-and-the-art-of-not-kingmaking/
- **Sandbagging / playing it cool [Opinion — EDHREC]:** don't become the visible threat early; let opponents "have a slugfest that expends their interaction" — in evaluation terms, discount plays that raise your *visible* threat (board + announced engines) without raising win probability this cycle, and hold win attempts until they are hard to stop.
  - https://edhrec.com/articles/the-art-of-playing-it-cool-in-commander

## A4. Combat in multiplayer

**Who to attack — priority order [Opinion — cEDH combat article + threat guides]:**
1. **Lethal / commander-damage lethal first** (finish a player: player removal is "one of the strongest pieces of interaction you have"; it also deletes their future interaction against you).
2. **The life-as-resource player:** "attack the naus player" — every point reduces Ad Nauseam / Necropotence / Bolas's Citadel / Sylvan Library yield; "there isn't a huge difference between a naus from 35 and from 30, but… eventually" it shuts the card off. Generalise: attack the opponent whose deck converts life into cards/mana.
3. **The long-game favourite / snowballing threat** (A2 player score), especially if they are **open** (no profitable blockers) — chip damage "will add up" and forces them to win early or spend resources defending.
4. **The blocker-of-your-win:** the interactive player whose countermagic/removal stops your combo — *but check the externality first*: "when thinking about killing one player who is playing a very interactive deck you should consider if you can stop the rest of the table without their help" and sometimes two opponents must be left alive to stop each other.
- https://commandersherald.com/combat-in-cedh/

**Attack mechanics to encode:**
- **Concentrate for commander damage, spread only for triggers/politics.** Commander damage is per-commander and needs 21 on *one* player (A2); splitting your commander's attacks across players resets progress on both. Non-commander attackers may be split (legal: declare each attacker against a different player) when e.g. drawing per-player combat triggers.
- **Open-shields test:** attack with X iff expected value (damage through + triggers) > expected loss (creatures dying to blocks + crackback, below). Prefer targets with no blockers that can trade up, tapped-down shields, or whose block costs them an engine piece.
- **Crackback check [Derived — standard combat logic, no single source states it as a formula]:** before declaring, sum the power each *other* opponent could attack you with next cycle (untapped/soon-untapped creatures + haste threat allowance) and your post-attack blockers (attackers tap and cannot block). Don't make an attack whose chip damage is smaller than the lethal-or-near-lethal swing it enables against you, and don't tap your last blocker to attack the *wrong* opponent while a third player is the real clock. *(Flag: this is synthesis, not a quoted rule.)*
- **Don't waste attacks on the non-threat:** "Do not attack the player with no board. Attack the player who is about to combo off."
  - https://scrollvault.net/guides/commander-deck-building.html

**Blocking / chump rules [Opinion — Reid Duke's *Level One* tradition via TCGPlayer]:**
- Life is **non-linear**: "your first three life points don't count for much, but your last three count for everything"; only 0 (and 21 commander / 10 poison) is intrinsically meaningful, but low life *constrains future options* (forced blocks, can't pay life).
- **Never chump early to save a few points:** "we shouldn't chump block to stop from going from 20 down to 17; we *have to* chump block to stop from going from three down to zero." (Scale to Commander: don't chump at 40→34; do at lethal.)
- **Chump iff:** (a) the damage is lethal (life or commander-damage lethal), **or** (b) you've projected you'll have to chump this attacker within the next cycle anyway and this blocker is your cheapest/lowest-future-value creature, **or** (c) chumping buys exactly the one turn your own win needs. Otherwise prefer, in order: profitable trade > double-block that kills the attacker > forcing a combat trick > taking the damage.
- **Block to kill, not to nick:** assign blockers to maximise tier-weighted value destroyed; don't block an attacker you can't kill or meaningfully shrink unless the chump conditions above hold.
- https://infinite.tcgplayer.com/article/robot/63764bf6-fab6-4008-9c56-6bdf55c62a04

## A5. Sequencing and timing

**Default order [Opinion — Wizards' own strategy features + sequencing guide, mutually consistent]:**
1. **Precombat main:** only things that change combat or that you need information from *before* attacking — haste creatures, anthems/lords, equipping the attacker, hand disruption (see their hand before choosing targets), removal of a blocker, a spell whose resolution decides whether you attack at all.
2. **Combat.**
3. **Postcombat main:** everything else — creatures (they couldn't attack anyway: summoning sickness), lands, planeswalkers (unless against blue and resolving the walker is the goal, in which case *also* postcombat, after combat has forced the opponent to spend mana), enchantments/artifacts with no combat impact. Rationale stated identically by both sources: conceal information, act with maximum information; a creature cast precombat tells the blocker "everything I'm going to do this turn."
- https://magic.wizards.com/en/news/feature/main-course-2017-08-03
- https://themythicmindset.com/articles/mtg-sequencing — lands: "play them in the post-combat main phase, unless you need them to cast something before"; creatures postcombat when you have attackers; draw spells on opponent's end step; sorcery removal usually precombat.

**Instant windows [Opinion — Wizards, *The Instances for Instants*]:**
- **Rule: cast at the last possible moment.** Draw/dig instants default to the **last opponent's end step**: you represented countermagic/removal all cycle, you decide with full information, and you untap immediately after.
- **Named exceptions (encode as overrides):**
  a. *You need the card now:* draw in your main phase if a drawn land/spell would be played this turn — "if you draw a land, you can play it… if you draw a creature you can cast, you can play it."
  b. *Opponent tapped out:* fire the instant on your turn rather than letting them untap into a counterspell.
  c. *Force action on their turn:* cast in their **upkeep** (before their draw) to make a counterspell cost them mana on *their* turn and deny them the new card for the fight.
  d. *Beat protection/tricks:* damage-based removal on your turn, before combat, if waiting risks a pump/hexproof/bounce in combat.
  e. *Bigger fish:* take the hit from a small attacker and keep removal for the larger threat they may cast postcombat.
  f. *Attack triggers:* removal at **beginning of combat**, before declare attackers, to deny "whenever this attacks" triggers.
- https://magic.wizards.com/en/news/feature/instances-instants-2017-06-08

**Mana efficiency vs playing around interaction [Synthesis of the above + A3]:** spend all mana *eventually* each cycle (unspent mana with a playable in hand is the biggest novice leak), but sequence the *order* to bait: cast the expendable spell first into open countermagic mana, the must-resolve spell after they've tapped / on the turn two opponents are tapped out. If no opponent can interact (all tapped / no cards), ignore "playing around" entirely and take the mana-efficient line.

**Commander recast timing & tax [Rules + Opinion]:** Tax = **+{2} per previous cast from the command zone** (tracked per commander); a 5-mana commander that has died twice costs **9**. Cheap commanders "recover faster" (2→4 is trivial, 6→8 is "devastating"). Judgment rule: **do not reflexively recast the moment it dies** — "assess the board state… could you better utilise your mana elsewhere? Sometimes, waiting a turn or two is the optimal play"; recast only if the commander generates value this cycle (attacks, engine triggers, blocks a lethal) that exceeds the best alternative spell + the increased future tax, and never recast into an obvious, held removal answer when you have another productive play.
- https://scrollvault.net/guides/commander-deck-building.html
- https://www.gameslearningsociety.org/wiki/how-much-does-it-cost-to-summon-a-commander/

## A6. Resource / X decisions, may-abilities, mana payment

**Sizing X [Opinion/thin evidence — flag: few sources give a general rule; use breakpoints].** Size X to the *next breakpoint*, not to "all remaining mana":
- **Lethal breakpoint:** X = target's life (or 21-minus-commander-damage analogue for burn that counts) — any more is waste unless playing around lifegain/counters.
- **Toughness/target breakpoint:** X = largest toughness to kill / number of targets to remove. Worked example [DraftSim]: Crackle with Power — 5 mana = 5 damage to 1 target, but **11 mana is "the sweet spot": 15 damage to each of 3 targets**, because every +3 mana adds 5 damage *and* a target — i.e. evaluate X at the card's own step-points, not continuously.
  - https://draftsim.com/x-spell-mtg/
- **Reserve breakpoint:** X = available mana − cost of the interaction you intend to hold (A3/A5), unless X at full size is lethal/winning this turn.
- **Draw/dig X:** cast only if X ≥ the threshold where the spell replaces itself plus a selection premium (as a floor, don't cast an X-draw for X < 2 unless desperate for a land — *[Derived floor, not sourced]*).
Magarena's shipped behaviour is a useful sanity check on the search side: it enumerates **all** legal X values (with X ≥ 1 "in most cases necessary to produce an effect") — a heuristic pilot should instead evaluate only the breakpoint candidates above (usually ≤4 values). See B4.
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax

**Kicker / multikicker / optional costs [Shipped pattern + synthesis]:** pay an optional cost iff the *incremental* effect's evaluation exceeds the best alternative use of that mana (including holding interaction). Multikicker: pay repeatedly only while each increment still hits a breakpoint (another target killed, lethal reached, another counter that crosses a power threshold). Magarena enumerates kicker 0…max-payable — again, breakpoint-prune instead.
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax

**"May" abilities — when to say no [Synthesis; Magarena notes yes/no is a real branching decision: "for no, only a single option… for yes, all combinations"]:** Default **yes** if the effect is free and strictly positive (draw, create, gain). Say **no** (or pay **no** on a "you may pay" trigger) when: paying costs mana reserved for interaction and the trigger's value < interaction's expected value (the classic: don't pay for Rhystic Study-type taxes *or* your own optional draws when it would tap you out before a known win attempt); drawing would deck you or feed an opponent's punish-draw effect; the action reveals information / makes you the threat (A3 sandbagging) with no clock gain; life payment would cross a clock threshold (put you within an opponent's one-turn lethal, or below an Ad Nauseam-style reserve you need yourself). Evaluate the may as a normal action with its true cost — never auto-yes.
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax

**Mana payment choices [Shipped — Magarena's payment solver is the model]:**
- **Deduplicate first:** payments that differ only in *which* identical source taps are one option (Magarena: paying {R} with ten Mountains = a single option). Never let the engine's raw payment permutations reach the evaluator.
- **Spend order:** colourless/generic sources and the *most abundant* colour first; preserve (i) the scarcest colour needed by cards in hand, (ii) colours of the interaction you are holding up, (iii) utility lands' activation mana, (iv) mana creatures that could block/attack (tap them last — and note Magarena must pre-commit such permanents each turn to "generate mana *or* tap to attack").
- **In search/evaluation, don't pay at all:** Magarena's *delayed payment* — inside the tree, merely check "could this combined cost still be paid?" and solve the actual optimal payment once, at the end of the turn. For a 1-ply pilot the analogue is: feasibility check per candidate action (can-pay bitmask over colours), exact assignment only for the chosen action.
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax

---

# SECTION B — Writing a strong, fast game AI for Magic-like card games (heuristics-first)

## B1. Existing open-source Magic AI — how each actually works

| Project | Architecture [Shipped] | Documented weaknesses |
|---|---|---|
| **Magarena** | Multiple AIs: Random, Monte Carlo, Vegas (simulation-based, nondeterministic), and the flagship **Minimax AI**: minimax tree + alpha-beta pruning + score caching, multithreaded, **iterative/incremental scoring**, plus bespoke solvers for mana payment, spell/ability play, targets/colours, attackers, blockers. Difficulty = **seconds of thinking per choice** / lookahead in main phases (max **6 main phases ≈ 3 turns**). | By its own docs: limited lookahead means "it will not try to hold back creatures or removal"; "does not work with fuzzy facts… will not bluff or take into account the hand and unused mana of the player"; scoring quirks "will sometimes result in choices a human would not generally make." Unknown opponent cards are modelled as a single dummy: an 8-mana 1/1 defender/shroud token. |
| **XMage** | Two families visible in source: the base `ComputerPlayer` (heuristic) and **`ComputerPlayerMCTS`**, which runs simulations on a thread pool bounded by `invokeAll(tasks, thinkTime, TimeUnit.SECONDS)` — i.e. a **seconds-scale** per-decision budget. Engine supports 28,000+ unique cards, so the AI must be card-agnostic. | No public design doc / postmortem found (see Could-not-verify). The seconds-scale MCTS budget is itself the lesson for a ms-budget pilot. |
| **Forge (Card-Forge)** | Rule-based/heuristic AI with per-card AI hints and per-ability AI classes (inferred from community/developer forum discussion; no architecture doc found). A current Forge fork (Neo Forge) exposes the budget directly: an AI thinking **>2 s** gets a "thinking" indicator, the setting is "**Max time the AI thinks per decision**" with options up to **60 s**, the limit covers spells, attacks *and* blocks, and on expiry "the AI goes with what it has." | Forum consensus (slightlymagic, "Card AI (Improvements) Requests"): **aggro is what it plays best** (linear: dump creatures); **combo fails** — it doesn't recognise two cards as a combo, can't time or protect it, some cards are marked unplayable-by-AI; **control fails** — "cannot distinguish between unharmful threats and dangerous threats," "cannot cherish its scarce win conditions," and "is not able to identify the 'threat' card(s)" like Aether Vial / Show and Tell. I.e. exactly the threat-assessment and hold-your-removal skills of §A2–A3 are the known gap in the shipped heuristic AIs. |

Sources:
- Magarena overview: https://github-wiki-see.page/m/magarena/magarena/wiki/AI-Overview
- Magarena minimax detail: https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax
- Magarena MCTS: https://github-wiki-see.page/m/magarena/magarena/wiki/AIMonteCarloTreeSearch
- XMage MCTS class / think-time: https://dev.to/pvsdev/lock-java-and-two-nulls-xmage-edition-57l4
- Forge AI weaknesses (community forum): https://slightlymagic.net/forum/viewtopic.php?t=7032&start=930
- Neo Forge per-decision time limit: https://dokkodolabs.itch.io/neo-forge/devlog/1711299/neo-forge-mtg-1025-pc-mac-linux-and-android-replays-of-your-games-see-when-the-ai-is-thinking-and-number-keys-for-choices

## B2. Evaluation-function design

**The proven shape: a linear delta-score over a small feature set, applied to the state *after* the candidate action [Measured — published, competition-validated].** García-Sánchez et al.'s SabberStone (Hearthstone) agent scores each legal action by the *change* it produces, with **21 weights** covering: hero health/armour difference, hero attack, minion health reduced / attack reduced / appeared / killed, secrets appeared/removed, and **mana consumed**; minions themselves are valued by a sub-function of attack, health and abilities. The agent is pure **greedy 1-step lookahead** (repeat best action until "end turn"), yet with evolutionarily tuned weights it was **runner-up of 33 (best ~6%) in the 2018 Hearthstone AI Competition and "performed remarkably well" against MCTS entrants**. Lesson for this mission: *weight quality beats search depth* when the budget is tiny — and hand-tuning 21 weights is feasible without ML infrastructure (the paper used coevolution offline; the pilot can hand-tune, then optionally self-play-tune later).
- https://arxiv.org/html/2410.19681v1

**Feature list for a Commander pilot (synthesis, each item traceable to §A or to the papers above):**
`score(state) = Σ wᵢ·featureᵢ`, computed per player, from:
- **Win/loss terminals** (infinite/very large, checked before any linear score).
- **Life — nonlinear.** Never a plain linear life term: a teaching implementation values life at 0.1/point next to 2.0 for a creature and immediately flags "there isn't a linear value to life" as a fault. Use a concave/clock-based transform: value life by *turns-to-lethal at current incoming power* (see A2 clocks), with a steep bonus for crossing out of an opponent's one-turn lethal and a steep penalty inside it.
  - http://magic.kevinleung.com/?cat=6
- **Board:** Σ permanent values, where a creature's value = f(power, toughness, evasion, keywords, tap status) + engine value (per-turn expected cards/mana it generates — this is what makes tier 7–9 permanents in A2 outscore vanilla stats), + commander bonus (re-accessible if killed, and commander-damage progress it carries).
- **Cards:** hand size (weighted by average card quality / presence of interaction), cards drawn this turn, library size only near decking.
- **Mana:** total mana available next turn (lands + untapped rocks/dorks), colour breadth, and *unspent-mana penalty* on your own turns (mana efficiency, A5).
- **Aggro-profile precedent [Published]:** SabberStone's built-in aggro heuristic "primarily optimises toward a large health difference," punishes states where the opponent has taunt blockers, and rewards having minions when the opponent has none — a reminder to keep *archetype profiles* (aggro/control/combo weight sets) and select by deck, as Forge's failures show one weight set plays aggro well and control badly.
  - (via) https://www.researchgate.net/publication/327637789_Exploring_the_hearthstone_deck_space

**Per-card ratings vs computed features:** Use computed features as the base (they generalise to 28k+ cards and to tokens/copies) and a **small per-card override table only for the exceptions features can't see**: combo pieces (value ≈ partner-present ? huge : moderate), kill-on-sight commanders, and cards whose text is pure engine. This mirrors practice: Magarena's scoring is feature/action-based with per-card *timing and priority metadata* layered on top, and Forge leans on per-card AI flags — whose failure mode (unmarked cards misplayed, combo unrecognised) is what the override table must be kept small enough to avoid.

**Multiplayer aggregation — the decision that most changes play [Synthesis + theory]:**
- 1v1 evaluation is `myScore − oppScore` (zero-sum). In 4-player FFA there is no single adversary: Berkeley CS188's general-games treatment replaces the scalar with a **utility tuple, each player maximising their own component** — a minimax that assumes all three opponents jointly minimise *you* is both wrong and paralysingly conservative.
  - https://inst.eecs.berkeley.edu/~cs188/textbook/games/general.html
- **Do not use pure sum** (`mine − Σ opponents`): it rewards spreading damage/removal evenly and over-values hurting the weakest player (who contributes the same sum as the leader).
- **Do not use pure max** (`mine − maxOpponent`): it ignores that the second opponent may kill you while you focus on the leader, and values eliminating no one.
- **Recommended:** `eval = myScore − maxOppScore − λ·(mean of other opponents' scores)`, λ ≈ 0.25–0.5, **plus hard overrides that sit above the linear score**: (i) any opponent with a win on the stack/next turn ⇒ game-loss unless answered (drives A3's fire rule); (ii) my lethal on any opponent ⇒ large bonus scaled by that opponent's threat rank (removing the *most threatening* player is worth more than removing the weakest — anti-sum behaviour); (iii) my own turns-to-lethal ≤1 ⇒ survival terms dominate. Because 2nd = 4th (A1), the scalar being maximised should approximate **P(win), not expected placement, life margin, or survival time** — a losing pilot should prefer high-variance lines, which a placement-shaped eval would suppress.

## B3. Search options and their real costs

**Why full search is off the table [Measured — worked example].** A Harvey Mudd MCTS-for-Magic write-up computes one ordinary turn's branching factor: choosing which creatures to play (C(7,4) = **35** sets) × which of 7 creatures attack (2⁷ = **128**) × how 8 blockers block (C(8,3) = **56**) = **250,880 branches for a single turn**; 100 simulations at depth 25 would touch **620,270,000** possibilities. They found **20 simulations the minimum for a "reasonable" AI**, observed that early-game MCTS played "only marginally better than a random player" (the sampled fraction is negligible) while late-game it matched expert expectations, in a *simplified creatures-and-lands-only* game.
- https://www.cs.hmc.edu/~jagajanian/cs151/

**Determinization / ISMCTS [Published — Cowling, Ward & Powley 2012; reviewed in Świechowski et al.].** The canonical Magic approach: sample completions of hidden information (opponents' hands, library order), run perfect-information MCTS on each, ensemble the result. Known defects, named in the review: **strategy fusion** (different determinizations recommend different moves in states you cannot distinguish), **non-locality**, and **splitting a fixed budget across many trees**. Mitigations that measurably helped in the original work: move pruning with domain knowledge and decomposing move generation into a **binary yes/no decision tree** (each atomic choice — play this card? attack with this creature? — becomes its own node). **ISMCTS** (Cowling, Powley & Whitehouse 2012) fixes strategy fusion structurally with one tree over information sets. All of this was demonstrated on **simplified variants with fixed decks / a limited card pool** (Ward & Cowling's test environment retained only a subset of card types, centred on creature combat) — no published result shows determinized MCTS playing full Commander, or playing at millisecond budgets.
- https://link.springer.com/article/10.1007/s10462-022-10228-y?error=cookies_not_supported&code=2d6034b8-34e4-4c9d-b613-ca8a5a1b6748
- https://www.researchgate.net/publication/224603720_Monte_Carlo_search_applied_to_card_selection_in_Magic_The_Gathering
- Secondary summary (Ward & Cowling split their agent: MCTS for card selection + a greedy generate-all-moves combat chooser): https://kot.rogacz.com/Supervising/Witkowski2020ImplementationOf.pdf

**The budget reality check [Measured/Shipped — every data point found]:**

| System | Per-decision budget |
|---|---|
| Magarena minimax/MCTS | **seconds** per choice (difficulty setting) |
| XMage `ComputerPlayerMCTS` | `thinkTime` in **seconds** |
| Forge / Neo Forge | up to **60 s** cap per decision; >2 s is "slow" |
| Hearthstone AI Competition (SabberStone) | **30 s per turn** |
| MCTS bots used to train a Hearthstone value net | **1 s per move** ("cheater" MCTS), 3.5M samples, value-net accuracy 0.76 |

- https://arxiv.org/pdf/1808.04794 (1 s/move MCTS data generation)
- Competition summary (30 s/turn; winners mostly ISMCTS / pruned BFS / rolling-horizon + eval; 2018 runner-up was the greedy coevolved agent of B2): https://www.researchgate.net/publication/376226950_Summarizing_Strategy_Card_Game_AI_Competition

**Conclusion for ~1–3 ms [Inference from the table above — no source claims ms-scale search works]:** at 1–3 ms you can afford, per decision, roughly: enumerate the (pre-filtered, deduplicated) legal options (typically ≤ tens after B5 pruning), apply each in-place with undo, compute an **incremental** delta-eval, and revert — i.e. **greedy 1-ply**. You cannot afford: any terminal rollout, more than a handful of determinizations, or minimax beyond a *single confined subgame* (combat, B4). Two affordable "search-like" upgrades: (1) **1-ply + opponent-best-reply check only for lethal** (for each of my candidate lethal/survival lines, does any single opponent action in their known/legal set refute it? — a bounded, threat-triggered check, not a tree); (2) **binary decomposition** of compound decisions (choose attackers one creature at a time with re-evaluation between, à la Cowling's binary move tree and Magarena's attacker generation) which turns an exponential choice into a linear number of greedy steps.

## B4. Decision-class specializations used in practice

Magarena's documentation is the clearest shipped blueprint — it does **not** run one general algorithm; it runs minimax *plus* a bespoke solver per choice type [Shipped]. Copy that decomposition:
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax

1. **Combat solver (exact, confined).** *Attackers:* sort candidates by power/toughness/abilities; force-include must-attack, drop power ≤ 0; generate **alpha-strike options** (all, then drop the worst repeatedly) plus all subsets up to a **cap on optional attackers** (worked example: cap 4 ⇒ 18 options from 7 candidates instead of 128). *Blockers:* per attacker, order candidate blockers (unkillable-by-attacker first by lethal-damage-needed, then by power); consider only: no block, each single non-lethal blocker, and minimal lethal combinations — worked example: **5 candidate assignments instead of 11**, and the gap explodes with board size. Score outcomes with **fast combat scoring** (power/toughness/abilities only, partially accurate) by default and **exact game-engine combat scoring** only at the root / when few attackers. Commander adaptation: run this solver per *defender* and add commander-damage clock deltas (A2) to the outcome score.
2. **Payment solver.** Delayed/abstract payment inside evaluation, exact assignment once for the chosen action; deduplicate equivalent sources (A6).
3. **Target scoring.** Label each spell's targets positive (own)/negative (opponents')/neutral and, below the root decision, use a **target picker that returns a single locally-best target** instead of branching on all targets (destroy-largest, buff-best-attacker, …). At the root, score targets by A2 tier × owner threat.
4. **Timing rules (a gate, not a search).** Every card/ability carries a *timing window* (Main / First-or-Second Main / Flash-on-opponent's-declare-attackers-or-end-step / Removal-in-main-or-declare-blockers-or-vs-opponent's-stack-item / Counter-only-vs-opponent's-spell) and a *priority/sequence number*; outside its window the option is never generated. This is also where §A5's sequencing defaults live.
5. **Pass / priority rule.** If the top of the stack is your own item, **always pass** and let it resolve — one line that eliminates a huge fraction of real decisions.
6. **Hybrid shape [Synthesis]:** rule gates decide *whether* a class of action is even a candidate (timing, A3 fire rule, A5 windows) → specialised solver enumerates *within* the class (combat, payment, targets, X-breakpoints) → greedy delta-eval (B2) arbitrates *between* classes (cast the removal or develop the engine?).

## B5. Speed engineering for decision-heavy loops

All techniques below are [Shipped] in Magarena unless noted — they are why it can search at all, and they matter *more* at 1–3 ms with no search:
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax

- **Incremental (delta) evaluation, never full rescoring.** Every state change is a recorded *action* that **returns its own score contribution**; a state's score is the accumulated sum, and undoing is reversing the action list — "much less memory and faster" than copying state per node. For a 1-ply pilot: score an option as `currentScore + Σ actionDeltas`, revert by undo. This is the single most important speed decision.
- **Score/state caching.** At phase boundaries (Magarena: First Main, End of Combat, Cleanup) hash the state to a **64-bit identifier** and memoise its best score in a cache **shared across threads**; hash collisions are accepted because "the speed benefit was so significant that this drawback is overshadowed." Pilot analogue: cache per-permanent values and per-player board subtotals, invalidated only by actions touching them; cache threat tiers per permanent (recompute only when it gains/loses abilities or a partner piece appears).
- **Option pre-filtering (the biggest multiplier).** Timing gates + priority ordering (B4.4); cap repeated activations per turn; if two permanents share an independent activated ability, generate only one; treat random-choice effects deterministically inside evaluation. Magarena is blunt: "limiting the number of choices that can be made has a big influence on the speed of the AI" and these filters cost optimality deliberately.
- **Root-vs-below asymmetry.** Enumerate fully **only at the root** (the real decision); below it, collapse each choice to its picker-best single option (targets, payments, blockers) — permutations collapse from product to sum.
- **Fast paths for forced/trivial decisions [Synthesis on shipped patterns]:** (i) exactly one legal option ⇒ return it, zero evaluation; (ii) priority pass with empty stack, no triggers, and no instant in hand whose timing window is open ⇒ pass immediately (in a real game this is the overwhelming majority of the "thousands of decisions"); (iii) own spell on top of stack ⇒ pass (B4.5); (iv) mandatory triggers with no choice ⇒ auto-yes/resolve; (v) damage assignment that is forced (only lethal ordering matters) ⇒ assign by rule. Measure the pilot by *median* decision time, not mean — the design goal is that only main-phase spell choices, combat, and stack responses ever reach the evaluator.
- **Adaptive depth/effort.** Magarena probes with a single-threaded first option to discover how much lookahead the position affords, stops on a permutation/time cap, and notes option *ordering* drives alpha-beta pruning efficiency (it admits it does **not** sort options first — an easy win for a new implementation: order candidates by delta-eval heuristic before any bounded reply-check in B3).
- **Parallelism is available but irrelevant at 1–3 ms** — Magarena/XMage parallelise across options/threads because their budgets are seconds; at ms scale, thread wake-up costs more than the work. Spend the budget on cache locality and avoiding allocation in the evaluate/undo loop instead. *[Inference]*

---

## Could not verify / open questions

- **Forge's internal architecture** (evaluation weights, any lookahead, per-card rating tables): no official design doc or postmortem was findable via the web index; the characterisation in B1 rests on a community forum thread and on a fork's release notes. Treat exact Forge claims as [Opinion]/anecdotal.
- **XMage's non-MCTS heuristic AI**: only the MCTS class's existence and seconds-scale `thinkTime` were verified from source excerpts; its heuristic player's design is undocumented in sources found.
- **No published system was found playing full 4-player Commander**, and none at millisecond budgets: all Magic AI results use simplified card pools, fixed decks, 1v1, and seconds per move. The 1–3 ms feasibility claims in B3/B5 are engineering inference from those measured costs, not a cited result.
- **X-spell / may-ability guidance** in Topic A6 is thin in the strategy literature (one worked breakpoint example + shipped AI behaviour); the breakpoint rules are presented as synthesis, flagged inline.
- **Crackback formula** (A4) is synthesis of standard combat logic; no source states it as an explicit formula.
- The mission did not specify the pilot's decks/power level (casual vs cEDH), which materially changes A1 (mulligan aggressiveness) and A2/A3 thresholds — both variants are given where they diverge.
- No page instructions were followed: all pages were treated as evidence only; nothing encountered attempted to redirect the research.

## Sources

**Topic A**
- https://scrollvault.net/posts/mulligan-math-when-serum-visions.html — London mulligan exact hypergeometric odds, CR 103.5/103.5c [opened]
- https://edhrec.com/guides/the-edhrec-guide-to-mulligans-in-commander — mulligan rules + curve/colour/plan/sequence/interaction keep axes [opened]
- https://edhrec.com/guides/intro-to-cedh — aggressive cEDH mulligans to 5, keep-a-plan [index]
- https://feedbeater.com/cedh-database-mulligan-theory-for-fast-pods/ — cEDH mulligan checklist, strong-5 vs okay-7 [index]
- https://draftsim.com/mtg-commander-mulligan-rules/ — casual keep standard, "good enough is great" [index]
- https://playgroup.gg/commander/how-many-lands — 157,120 tracked hands, 89% kept with 2–4 lands [index]
- https://www.coolstuffinc.com/a/how-many-lands-in-a-commander-deck-04272026 — ~36-land EDHREC average, 36–46 range discussion [index]
- https://commandersherald.com/how-many-lands-should-you-play-in-cedh/ — free mulligan + 4-player dynamics license low land counts / aggressive mulls [index]
- https://www.goonhammer.com/commander-101-winning-a-negative-sum-game/ — 2nd=3rd=4th, point-value hands, >1 mulligan/game [index]
- https://aetherhub.com/Article/Threat-Assessment-in-Commander-101-A-Guide-to-Survival — ranked threat tiers 1–10, ~12 spot + ~5 mass interaction, let others answer [opened]
- https://blog.cardkingdom.com/threat-assessment-in-commander/ — pregame/early/mid threat assessment, "who stops me" [opened]
- https://draftsim.com/mtg-commander-mistakes/ — threat = board + card advantage + mana, life least relevant [index]
- https://edhrec.com/articles/beginner-content-threats-and-resource-management — save removal for threats to your own plan [index]
- https://edhrec.com/articles/the-art-of-playing-it-cool-in-commander — sandbagging / not becoming the threat [index]
- https://mtgcombotrainer.com/combo-guides/how-to-think-better-mtg — removal fire rule, deals framework, kingmaking [index]
- https://cultureofgaming.com/mtg-commander-politics-deals-bribes-and-the-art-of-not-kingmaking/ — kingmaking definition [index]
- https://www.Coolstuffinc.com/a/cashinds-seo-10232024-the-problem-with-removal-in-commander — wait in turn order before answering [index]
- https://nullromo.github.io/kylekovacs/blog/commander-primer/ — don't waste removal, no spite [index]
- https://commandersherald.com/combat-in-cedh/ — attack the Naus player, long-game favourite, interactive-player externality [opened]
- https://www.beckett.com/news/what-is-commander-damage-and-how-to-use-it-to-your-advantage/ — 21 commander damage rule [index]
- https://magic.wizards.com/en/news/feature/commander-2018-edition-release-notes-2018-07-27 — commander damage rule text [index]
- https://scrollvault.net/guides/commander-deck-building.html — commander tax, attack the combo player, hold removal [index]
- https://infinite.tcgplayer.com/article/robot/63764bf6-fab6-4008-9c56-6bdf55c62a04 — chump blocking, non-linear life value [index]
- https://magic.wizards.com/en/news/feature/main-course-2017-08-03 — postcombat-main default, precombat exceptions [opened]
- https://magic.wizards.com/en/news/feature/instances-instants-2017-06-08 — last-moment instants, end-step draw, upkeep/tapped-out exceptions [opened]
- https://themythicmindset.com/articles/mtg-sequencing — per-card-type sequencing defaults [opened]
- https://www.gameslearningsociety.org/wiki/how-much-does-it-cost-to-summon-a-commander/ — commander tax, don't reflexively recast [index]
- https://draftsim.com/x-spell-mtg/ — X-spell breakpoints (Crackle with Power 5 vs 11 mana) [index]

**Topic B**
- https://github-wiki-see.page/m/magarena/magarena/wiki/AI-Overview — Magarena AI families, seconds-per-choice, known limits [opened]
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMinimax — incremental scoring, 64-bit cache, delayed payment, combat/target/timing solvers, attacker/blocker pruning [opened]
- https://github-wiki-see.page/m/magarena/magarena/wiki/AIMonteCarloTreeSearch — Magarena MCTS/Vegas, evaluation cut-off idea [index]
- https://dev.to/pvsdev/lock-java-and-two-nulls-xmage-edition-57l4 — XMage ComputerPlayerMCTS, thinkTime in seconds [opened]
- https://slightlymagic.net/forum/viewtopic.php?t=7032&start=930 — Forge AI weaknesses: threat ID, combo, control [index]
- https://dokkodolabs.itch.io/neo-forge/devlog/1711299/neo-forge-mtg-1025-pc-mac-linux-and-android-replays-of-your-games-see-when-the-ai-is-thinking-and-number-keys-for-choices — Forge fork: >2 s thinking UI, max-time-per-decision up to 60 s [index]
- https://www.cs.hmc.edu/~jagajanian/cs151/ — 250,880 single-turn branching factor, 20-simulation minimum, early-game MCTS ≈ random [opened]
- https://link.springer.com/article/10.1007/s10462-022-10228-y?error=cookies_not_supported&code=2d6034b8-34e4-4c9d-b613-ca8a5a1b6748 — MCTS review: determinization, strategy fusion, ISMCTS, Cowling et al. on Magic [index]
- https://www.researchgate.net/publication/224603720_Monte_Carlo_search_applied_to_card_selection_in_Magic_The_Gathering — Ward & Cowling 2009, Monte Carlo card selection [index]
- https://kot.rogacz.com/Supervising/Witkowski2020ImplementationOf.pdf — secondary summary: MCTS card selection + greedy combat in Ward/Cowling [index]
- https://arxiv.org/html/2410.19681v1 — SabberStone greedy agent, 21-weight delta evaluation, competition runner-up vs MCTS [opened]
- https://www.researchgate.net/publication/376226950_Summarizing_Strategy_Card_Game_AI_Competition — Hearthstone AI competition: 30 s/turn, search winners, greedy runner-up [index]
- https://www.researchgate.net/publication/327637789_Exploring_the_hearthstone_deck_space — SabberStone aggro heuristic features [index]
- https://arxiv.org/pdf/1808.04794 — MCTS at 1 s/move for value-net training data [index]
- https://inst.eecs.berkeley.edu/~cs188/textbook/games/general.html — general (non-zero-sum) multiplayer games, utility tuples [index]
- http://magic.kevinleung.com/?cat=6 — linear evaluation example, warning that life is not linear [index]
