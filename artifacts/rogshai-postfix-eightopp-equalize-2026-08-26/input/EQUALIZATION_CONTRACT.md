# RogShai Post-Fix Eight-Opponent Cumulative Equalization — Decision Contract

Status: **PREPARED / NOT LAUNCHED**

## Purpose

Close the post-fix opponent-exposure imbalance for the established C001–C048 population without changing canonical deck, inventory, allocation, purchase, or opponent truth.

This campaign is `structural_model_estimates`. It is not empirical Commander win rate and not Rules Authority.

## Frozen source

Campaign branch starts from the exact post-fix head `ff60f43cb61070a51cb867a17805777b04d030a8`, whose prior 5,120-game Near-Neighbor workflow completed the full quality gate and exact Structural seat-symmetry gate before gameplay.

The campaign itself must re-prove the gate on its own source head before any gameplay.

## Candidate population

Exactly C001–C048. All 48 hard-valid unique candidates are admitted. No heuristic, Structural-score, current-nearness, QD, Pareto, or prior-performance admission gate is allowed.

N001–N016 are prior targeted theorycrafts with a different opponent-exposure history and are not part of this cumulative-equalization contract. Their exclusion is population definition, not performance filtering.

## Opponent identities and evidence classes

- `cosmic` → `opponent/cosmic-spiderman-midbudget` → `partially_observed_synthetic_completion_public_deck_proxy`.
  - Canonical supporting baseline identifies the Jonathan Escusa public Cosmic Spider-Man deck as the current proxy.
  - This run does not promote the proxy to an observed full real deck.
- `morcant` → `opponent/morcant-elves` → `partially_observed_synthetic_completion_pool_constrained`.
- `kaervek` → `kaervek/current` → verified full frozen opponent.
- `blight`, `dance`, `lorehold`, `doom`, `wakanda` → official-precon-based current opponent baselines with their existing evidence qualifiers.

## Cumulative equality target

Per established candidate before this run:

- Cosmic: 0
- Morcant: 192
- Kaervek: 232
- Blight: 232
- Dance: 232
- Lorehold: 232
- Doom: 232
- Wakanda: 232

The minimum exact-equality schedule satisfying distinct-opponent 4P pods is 320 scenarios per candidate.

New appearances per candidate:

- Cosmic +318
- Morcant +126
- each of Kaervek / Blight / Dance / Lorehold / Doom / Wakanda +86

After the campaign every identity is exactly **318 cumulative post-fix appearances per C001–C048 candidate**.

Total gameplay target: **48 × 320 = 15,360 games**.

## Balance and randomness

- four-player Commander only;
- 320 fresh master seeds, disjoint from prior relevant Structural schedules;
- no replacement seeds after gameplay failure;
- same scenario/seed schedule for every candidate;
- candidate seat: 80 each;
- starting player: 80 each;
- candidate-seat × starting-seat: 20 each;
- opponent physical-seat imbalance: at most one appearance;
- opponent relative-position imbalance: at most one appearance;
- all opponent triplets contain three distinct opponents;
- pair/triplet frequencies are allowed to be nonuniform because exact cumulative appearance equality is the primary hard constraint.

## Failure handling

Any hard-gate, preflight, materialization, seed-overlap, schedule-balance, abort, or aggregate invariant failure stops the campaign. No silent fallback and no replacement seeds.

## Interpretation boundary

Overall mixed-evidence ranking is descriptive only. Cosmic- and Morcant-conditioned outputs remain sensitivity/hypothesis-generating. Because exact equalization requires Cosmic in 318/320 new scenarios, this run is not a replacement for the prior clean six-opponent post-fix evidence. Strong real-deck recommendations must be synthesized with the 7,680-game clean opponent-equalization campaign, the 5,120-game matched Near-Neighbor campaign, seat robustness, worst-case behavior, and evidence-class-conditioned results.
