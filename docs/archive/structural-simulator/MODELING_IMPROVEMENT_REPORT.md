# Modeling Improvement Report — Audit G

Date: 2026-08-09
Estimate type: `structural_model_estimates`
Deck mutations: 0
Inventory/allocation mutations: 0
External rules-engine claims: 0

## Baseline problem

The pre-G simulator already had strong role coverage and specialist pilots, but several strategically different cards collapsed into the same role labels. This was most visible in commander dependence, table damage vs Commander damage, real rebuild, recurring token/sacrifice engines, and the value of holding stack interaction.

The pre-G pilot evaluated against the fixed G corpus scored:

- Development: 18/24;
- Holdout: 9/12.

## Structural change

G adds `StructuralMechanic` as an orthogonal layer to `CardRole` rather than replacing roles. Current mechanic tags include sacrifice cost/outlet/payoff, death triggers, token engines, repeatable token sources, land recursion, artifact engines, graveyard recursion, go-wide, table damage, Commander-damage support, rebuild, stack interaction, finisher compression, and commander dependence/independence.

### Mechanic-by-mechanic result

| Mechanic | Before | G change | Controlled consequence | Remaining limit |
|---|---|---|---|---|
| Sacrifice | roles conflated source/outlet/payoff | explicit mechanic tags | Korvold can value material, outlets and independent payoffs separately | no comprehensive rules timing |
| Token engines | token source only | repeatable/token-engine tags | independent material development receives proper value | token counts remain structural |
| Land recursion | generic recursion/land synergy | land-recursion + rebuild | graveyard-stocked post-wipe states prefer genuine rebuild | exact land text not rules-executed |
| Commander dependence | mostly strategy-specific heuristics | dependent/independent mechanics | offline axes lose/retain value appropriately | dependence remains heuristic |
| Table damage | finisher/payoff proxy | explicit table-damage tag | large-pod collateral/compressed reach scales separately | damage triggers not fully rules-simulated |
| Commander damage | combat payoff proxy | explicit Commander-damage support | Jeska support differs from Kediss collateral damage | exact combat legality remains outside structural model |
| Rebuild | recursion/draw proxies | rebuild + zone-specific recurrence | wipe recovery gets dedicated utility | not a full zone/rules engine |
| Artifact engines | generic engine | artifact-engine tag + opponent natives | Doom/Wakanda pressure is more visible | residual cards may be aggregate |
| Graveyard recursion | generic recursion | graveyard-recursion tag | graveyard-as-resource gets separate rebuild value | timing/targets structural only |
| Go-wide | token/combat proxy | go-wide tag | Morcant and token scaling better represented | no combat micro-simulation |
| Stack interaction | counter role only | stack-interaction tag + reserve behavior | RogShai correctly holds responses in high-threat windows | no actual priority engine |
| Finisher compression | generic finisher | compression tag | 5-player table-closing actions rise relative to value engines | no deterministic lethal proof |
| Multiplayer scaling | mostly generic opponent count/large-pod band | explicit 3/4/5 context + mechanic scaling | distinct pod-size scenarios are testable | not empirical pod-frequency weighting |

## Pilot decision remediation

During development the first mechanic-weighted attempt regressed to 17/24. That regression was retained as diagnostic evidence and corrected rather than hidden. Root causes were overvalued commander-dependent payoffs and insufficient reserve/protection value in high-threat windows.

The final changes are narrow:

- commander-dependent win progress is discounted when the relevant commander axis is offline;
- RogShai penalizes exposing Combat Research / Curiosity / Staggering Insight into severe threat windows when reserve is consumed;
- holding flexible interaction receives positive value under high opponent threat;
- Kediss is specifically penalized when Ishai is offline instead of being treated as independent Commander-damage reach;
- protection scenarios compare legal response choices rather than impossible proactive sorcery-speed alternatives.

## Before / after

| Corpus | Baseline | Post-G | Delta |
|---|---:|---:|---:|
| Development | 18/24 | 24/24 | +6 |
| Holdout | 9/12 | 12/12 | +3 |

The holdout was first opened only after development reached 24/24. No tuning was performed after seeing holdout outcomes.

## Regression boundary

G does not claim:

- empirical win-rate improvement;
- external XMage/Forge semantic validation;
- a full MTG rules engine;
- complete knowledge of Cosmic, final Morcant, or Doom upgrades;
- automatic deck superiority or any canonical deck change.

## Local performance sample

A deterministic local microbenchmark of 500 evaluations of the fixed 36-case G corpus measured 0.976 s with the pre-G pilot and 1.040 s with the final G pilot on this runtime (+6.55%, +0.064 s total). This is a narrow microbenchmark, not a universal simulator-performance claim.

## Runtime / validation boundary

`doctor`, rules-engine probing, one-iteration structural validation and Phase-8 tactical validation were executed locally after committing the G tree; the commands left the repository clean. XMage/Forge remained unavailable/not configured. Phase-8.6 audit returned its expected blocked exit because Ruff/Mypy are unavailable in this local runtime and real external-engine execution remains unavailable; final GitHub CI is therefore the independent static/platform gate. A wheel build passed with local build isolation disabled; isolated build dependency acquisition was unavailable from this runtime's package index.
