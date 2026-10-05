# Commander Simulator Next — Product Requirements Document

**Status:** Product intent baseline for architecture work  
**Evidence baseline:** Commander Playtest Lab `main` at `010e58220dd64f8c3ceb3b86149190ce95437d9f` / tree `af287661fbfdb6a68d3442371e518aeffebce49b`  
**Date:** 2026-10-05

This document defines **what problem Commander Simulator Next should solve and why**.
It deliberately does **not** select a Rules Core, provider, programming language,
repository topology, runtime protocol, storage model, or implementation architecture.

`PRODUCTION_PROVIDER = NOT_SELECTED`  
`ARCHITECTURE_FREEZE = NOT_CLAIMED`  
`PRODUCTION_REPOSITORY = NOT_CREATED`

---

## 1. Problem Statement

A technically demanding Commander player who wants to improve a real deck, understand
matchups, compare card or policy changes, and learn from repeated games cannot currently
get all of the following from one trustworthy decision workflow:

- real Commander rules behavior rather than a coarse approximation;
- multiplayer behavior that remains correct when player count and board complexity change;
- discretionary play decisions that are separated from Rules legality;
- hidden information that is not leaked to the decision-maker;
- reproducible randomness and replayable outcomes;
- enough repeated play to compare decks, matchups, mulligans, policies, and card changes;
- evidence that is strong enough to distinguish a real gameplay conclusion from a
  simulator defect, unsupported mechanic, or accidental default.

The present alternative is fragmented: manual games and goldfishing provide realism but
poor repeatability and throughput; lightweight simulators provide speed but not enough
rules fidelity; bounded tactical or structural models answer only some questions; full
rules engines can execute more of the game but do not automatically provide a trustworthy
decision-analysis workflow.

The cost of leaving this unsolved is that deck and pilot decisions continue to depend on a
mixture of intuition, small samples, manual rules reconstruction, partial models, and
evidence that is difficult to reproduce or compare. The user cannot reliably tell whether
an observed advantage came from the deck, the pilot, the matchup, randomness, or a
simulation limitation.

---

## 2. Evidence

### Direct project evidence

| Evidence | What it supports |
| --- | --- |
| [Project Mission](PROJECT_MISSION.md) | The explicit project outcome is a maximally rules-correct Commander simulator for real decks, matchup analysis, pilot improvement, learning, and deckbuilding optimization. Rules Correctness outranks performance and convenience. |
| [README](../README.md) | The existing Structural simulator is explicitly an approximation layer and cannot establish full external-rules behavior. The project already separates structural, tactical, and external-rules evidence. |
| [Issue #255](https://github.com/moeendres-png/commander-playtest-lab/issues/255) | Provider selection remains unresolved because current evidence must be reconciled on a common denominator before a production decision is trustworthy. |
| [Issue #441](https://github.com/moeendres-png/commander-playtest-lab/issues/441) | A large pre-Freeze campaign is still closing real decision, hidden-information, replay, multiplayer, and actual-card evidence gaps rather than assuming construction or green CI implies correctness. |
| [Issue #479](https://github.com/moeendres-png/commander-playtest-lab/issues/479) | Considerable work has been required to prevent false-positive qualification, silent test omission, stale evidence, unsafe fallbacks, and misleading CI signals. This demonstrates that evidence integrity is itself part of the user problem. |
| Current Lab source | The project already contains structural simulation, optimization, pilots, external-engine adapters, current-boundary qualification, provenance, and semantic replay subsystems. This proves substantial reusable capability exists, but not that the current composition is the final product architecture. |

### Historical supporting evidence

Earlier project handoffs and automation research repeatedly identified coordination,
qualification, evidence-persistence, and reproducibility overhead. These are supporting
signals, not current technical authority; fresh GitHub state supersedes their old source
locks.

### Assumptions that still need validation

- **Assumption:** the primary user's current workaround is sufficiently painful that a
  trustworthy simulator would replace a meaningful portion of manual goldfishing and
  ad-hoc analysis.
- **Assumption:** other advanced Commander deckbuilders have the same need strongly enough
  to become future users.
- **Assumption:** a sufficiently rules-correct simulator can produce useful decision
  evidence at a practical enough cost and latency for repeated deck iteration.

These assumptions must not be promoted to facts merely because the technical project can
build toward them.

---

## 3. Thesis — Why Build This

Commander Simulator Next is worth building if it turns Commander testing from
**"play or approximate, then interpret manually"** into **"run a rules-trustworthy,
reproducible decision study and know exactly what the result does and does not prove."**

The differentiation is not merely more simulations, stronger AI, or a larger card
database. The product should be meaningfully better than the current workaround because
it combines four outcomes that are usually separated:

1. **Rules trust:** the simulated game behaves like Commander on the admitted surface,
   and unsupported behavior does not silently become an answer.
2. **Decision usefulness:** the system can compare real deck, matchup, mulligan, and pilot
   choices rather than merely execute a game.
3. **Reproducibility:** a conclusion can be traced back to the exact game conditions,
   decisions, randomness, and evidence and can be reproduced.
4. **Learning:** repeated evidence can improve later deck construction and play decisions
   without allowing optimization logic to redefine the rules.

### Why now

The project has moved beyond speculative engine research. It now has substantial
qualification infrastructure, real candidate-engine execution, replay/provenance work,
actual-card scenarios, and explicit pre-Freeze gates. That creates a useful moment to
state the product intent **before** historical implementation effort hardens into product
requirements by inertia.

The PRD therefore exists to give Architecture Freeze a product target: later technical
decisions should be accepted because they best satisfy this intent, not because a
particular subsystem already consumed the most engineering effort.

---

## 4. Hypothesis

> **We believe** that giving a technically demanding Commander deckbuilder a
> rules-trustworthy, reproducible way to run real multiplayer decks and compare concrete
> deck, matchup, mulligan, and pilot choices **will cause** that user to replace a
> meaningful share of intuition-only, manual-goldfish, and fragmented-simulator analysis
> with evidence-backed decision studies, **resulting in** higher-confidence deck and play
> decisions and faster learning from repeated games.
>
> **We'll know we're RIGHT if**, during the first qualified real-deck decision cycle,
> the system can produce at least one reproducible decision result that the primary user
> considers sufficient to make, reject, or confidently preserve a real deck or pilot
> choice without requiring a separate manual reconstruction of the relevant game rules.
>
> **We'll know we're WRONG if** the first qualified decision cycle still requires manual
> rules reconstruction to trust the conclusion, if unsupported mechanics routinely make
> real decks unusable, if replay cannot reproduce the semantic result from the same
> recorded inputs, or if the primary user still prefers the existing manual/fragmented
> workflow because the simulator's evidence is too slow, opaque, or untrustworthy.

**Timeframe:** the first qualified end-to-end real-deck decision cycle after the MVP
acceptance slice is available. A calendar-duration target is **TBD — needs validation**.

---

## 5. Target User & Jobs To Be Done

### Primary user

A technically engaged Commander player/deckbuilder who:

- owns or maintains real 100-card Commander decks;
- cares about card-selection, matchup, mulligan, and gameplay decisions;
- is willing to trade some convenience for materially higher Rules Correctness and
  evidence quality;
- needs to understand why a result is trustworthy, not merely receive a recommendation.

The initial primary user is the project owner. Broader market demand is not yet established.

### Primary JTBD

> **When** I am deciding whether a real Commander deck, card change, mulligan policy,
> matchup plan, or play policy is actually better,  
> **I want to** test it repeatedly under trustworthy Commander rules with controlled and
> reproducible conditions,  
> **so I can** make the decision from evidence rather than from small samples, simulator
> shortcuts, or intuition alone.

### Secondary JTBD

> **When** a surprising result appears,  
> **I want to** replay and inspect the relevant game and decision sequence,  
> **so I can** distinguish a genuine gameplay interaction from randomness, pilot behavior,
> unsupported mechanics, or a simulator defect.

### Future / unvalidated users

Potential future users include advanced Commander deck tuners, matchup analysts, and
developers evaluating pilot policies.

**Status:** assumption only — demand outside the primary user is **TBD — needs validation**.

### Explicit non-users

- users who only want a lightweight goldfish tool and do not need evidence-grade rules
  fidelity;
- users seeking an official judge ruling or an official Wizards game client;
- users who require the simulator to substitute for sanctioned competitive play or
  authoritative tournament adjudication.

---

## 6. MVP — Thinnest End-to-End Proof of Value

The MVP is a **hypothesis test**, not the finished production simulator and not
Architecture Freeze.

The thinnest useful end-to-end slice is:

1. use one real 100-card own Commander deck and three real opponent decks;
2. run complete four-player games on a product-admitted rules surface without manual game
   outcome injection;
3. expose discretionary decisions to the acting pilot without granting information that
   player should not know;
4. preserve the randomness and decisions needed to reproduce the semantic result;
5. repeat enough comparable games to evaluate **one concrete real decision**, such as a
   deck variant, matchup choice, mulligan policy, or pilot-policy difference;
6. produce an evidence package that states the result, uncertainty, known limitations,
   and exactly what was or was not supported;
7. demonstrate that the primary user can act on that result without separately
   reconstructing the relevant rules by hand.

### MVP acceptance

The MVP succeeds only if the value hypothesis can be judged from this complete loop.
A partial demo that imports decks, constructs games, or executes isolated mechanics does
not satisfy the MVP.

### Product-readiness constraints beyond the MVP

The project mission separately requires:

- four players as the primary benchmark and decision mode;
- technical conformance for **2–5 players** before product readiness;
- preference for 6+ / variable-player capability when it improves the product without
  reducing required correctness;
- real Commander decks, not only synthetic micro-scenarios;
- fail-closed treatment of unsupported production-reachable behavior.

Therefore a successful 4-player MVP proves potential value; it does **not** by itself
establish production readiness.

---

## 7. Success Metrics

| Metric | Target | How measured |
| --- | --- | --- |
| **End-to-end decision utility** | At least one real deck/matchup/mulligan/pilot decision is made, rejected, or confidently preserved from simulator evidence in the first qualified MVP decision cycle without separate manual rules reconstruction | Record the decision question, pre-registered comparison, evidence package, user disposition, and whether external manual rules reconstruction was required |
| **Real-deck game usability** | 100% of the initial MVP acceptance pod's admitted game paths complete or fail closed with an explicit unsupported reason; no silent fallback | End-to-end runs over the frozen MVP deck/pod set |
| **Rules trust on admitted surface** | 0 known unresolved Rules contradictions in any behavior represented as product-valid | Current qualification evidence plus official Rules adjudication for the admitted surface |
| **Semantic reproducibility** | 100% of replay-qualified MVP acceptance runs reproduce the recorded semantic outcome from the recorded inputs/decisions/randomness | Replay comparison against the frozen acceptance corpus |
| **Hidden-information integrity** | 0 known cross-principal information leaks in the admitted MVP decision workflow | Adversarial hidden-information qualification and replay inspection |
| **Player-count readiness** | Explicit technical conformance at 2P, 3P, 4P, and 5P before product-ready status | Source-bound conformance evidence per player count; 4P evidence cannot substitute for another count |
| **Unsupported-path honesty** | 0 unsupported production-reachable paths silently converted into legal actions, default choices, fabricated outcomes, or PASS evidence | Negative controls, qualification findings, and runtime refusal evidence |
| **Decision-study practicality** | **TBD — needs validation** | Measure wall-clock time, compute cost, operator effort, and useful comparisons per decision study once the MVP loop is real |
| **Repeat-use value** | **TBD — needs validation** | Track whether the primary user voluntarily uses the simulator for subsequent real deck/pilot decisions rather than returning to the prior workaround |

The first seven metrics determine whether the system is trustworthy enough to test the
product thesis. The final two determine whether it is useful enough to become a product
rather than only a research artifact.

---

## 8. Non-goals

Commander Simulator Next is **not** intended to:

- become an official Magic rules authority or judge service;
- optimize for maximum simulation speed at the expense of Rules Correctness;
- claim that a constructed/imported card or a green workflow proves correct runtime card
  behavior;
- provide perfect play, perfect opponent prediction, or objectively optimal Commander
  strategy;
- hide uncertainty or convert unsupported behavior into a guessed result;
- require one particular existing engine, repository, language, framework, or current Lab
  subsystem simply because it already exists;
- preserve an incumbent architecture because of sunk engineering cost;
- make pilot or optimization logic a second source of Rules legality;
- treat reference-engine parity as a substitute for official Rules validation;
- mutate a user's physical deck, collection, purchase plan, or canonical deck definition
  merely because a simulation produced a recommendation;
- serve primarily as a consumer game client, graphical replacement for tabletop play, or
  social Commander platform;
- select a Production Provider or claim Architecture Freeze inside this PRD.

---

## 9. Open Questions

### Value / user questions

- [ ] **Primary decision order:** Which user decision should be the first product-value
  demonstration: card swap, matchup plan, mulligan policy, pilot policy, or another real
  decision?
- [ ] **Switch threshold:** What level of evidence makes the primary user actually prefer
  this workflow over manual games/goldfishing for that decision?
- [ ] **Repeat-use threshold:** How many useful decision studies are needed before we
  consider the product valuable rather than a one-off research success?
- [ ] **Broader demand:** Do other advanced Commander players/deckbuilders have the same
  problem strongly enough to use the product? **TBD — needs validation.**

### Practicality questions

- [ ] What wall-clock time per full game or per decision study remains useful?
  **TBD — needs validation.**
- [ ] What compute/operating cost per useful decision study is acceptable?
  **TBD — needs validation.**
- [ ] How much setup effort can the primary user tolerate when importing or updating real
  decks and matchup assumptions? **TBD — needs validation.**
- [ ] What level of pilot strength is "good enough" for decision usefulness without
  confusing pilot weakness with Rules correctness? **TBD — needs validation.**

### Product-scope questions

- [ ] What frozen real-deck pod should serve as the first MVP acceptance set?
  **TBD — must use current authorized deck truth, not historical snapshots.**
- [ ] Which classes of deckbuilding decisions must be supported in v1 beyond the first MVP
  experiment?
- [ ] Which matchup/meta inputs are required for useful conclusions, and how current must
  they be?
- [ ] Is 6+ player support valuable enough for v1, or should it remain a post-readiness
  capability unless it falls out naturally from a variable-player design?
- [ ] What product-facing explanation of uncertainty and evidence is sufficient for the
  primary user to understand the limits of a recommendation?

### Viability / distribution questions

- [ ] Is the intended product private/personal, shared with a small group, or eventually
  distributable to a wider audience? **TBD — needs validation.**
- [ ] What licensing, data, and intellectual-property constraints would apply to that
  intended distribution model? **TBD — requires separate legal/viability review.**

### Hand-off to architecture

The following are intentionally **not answered here** and belong to
`plan-architecture`:

- which Rules Core/provider to use;
- reuse vs fork vs wrap vs embed vs port vs hybrid vs rewrite;
- what existing Lab subsystems move into the eventual product;
- process/runtime topology;
- repository topology;
- interfaces/protocols;
- storage/data models;
- security/isolation mechanisms;
- testing architecture;
- deployment;
- performance engineering;
- exact batch/concurrency implementation.

Those decisions must be derived from this product intent plus current Brownfield evidence,
not smuggled into the PRD.
