# RogShai Pre-Simulation Enrichment Audit — Phases A–F

Generated: `2026-08-13T21:33:00+02:00`

## Baseline

- Repository: `moeendres-png/commander-playtest-lab`
- main: `a9712fea4d3869380f817d74e2cf8cb2ce5c0a9a`
- tree: `39fc84fa032e035d1394ee528907c9395a750357`
- package: `1.18.1`; structural engine: `structural-0.6.0`
- RogShai canonical control: 100 cards / 36 lands / unchanged hash `7b7d03aa16be6586df8f8a4e9f1acd30f85ad2e8e45e7889e700353a6f19c126`.

## Phase A — Fresh coverage audit

| Measure | Fresh count |
|---|---:|
| Physical inventory identities | 1,338 |
| Physically available, legal RogShai candidates | 795 |
| Candidates without legacy roles | 356 |
| Candidates without legacy synergy hooks | 325 |
| Candidates without existing RogShai package relation | 596 |
| Candidates without enriched package relation | 528 |
| Candidates with zero current local threat-axis coverage | 710 |
| Candidates with zero current local opponent coverage | 710 |
| Candidates with verified external Oracle UUID | 0 |

Role/package sparsity is preserved as uncertainty; no missing role was force-filled merely to raise coverage.

## Capability map

| Feature | Search | Mana | Mulligan | Structural | Tactical | External rules |
|---|---|---|---|---|---|---|
| mana_value | full | full | full | full | partial | none |
| colored_source_quality | partial | full | partial | proxy | partial | none |
| untapped_source_quality | partial | partial | proxy | proxy | partial | none |
| card_selection | full | none | full | full | partial | none |
| card_advantage | full | none | full | full | partial | none |
| cheap_interaction | full | partial | full | full | partial | none |
| stack_interaction | full | partial | full | full | partial | none |
| removal | full | none | full | full | partial | none |
| protection | full | partial | full | full | partial | none |
| boardwipe | full | none | full | full | partial | none |
| graveyard_hate | full | none | full | full | partial | none |
| commander_synergy | full | none | full | full | partial | none |
| commander_dependence | partial | none | partial | partial | partial | none |
| multiplayer_scaling | partial | none | proxy | partial | partial | none |
| rebuild | partial | none | partial | partial | partial | none |
| role_compression | partial | none | proxy | proxy | partial | none |
| package_dependency | partial | none | proxy | partial | partial | none |
| finish_compression | partial | none | proxy | partial | partial | none |
| conditionality | partial | partial | proxy | proxy | partial | none |
| modal_flexibility | partial | none | proxy | proxy | partial | none |
| tempo | partial | partial | proxy | proxy | partial | none |
| recursion | full | none | partial | full | partial | none |
| political_visibility | partial | none | none | none | none | none |
| exact_rules_interaction | none | none | none | none | partial | none |

External rules engine remains `NO_PROVIDER_READY`; this registry never promotes tactical/structural evidence to external-engine evidence.

## Phase B — Identity / Oracle / legality facts

- Normalized identity/fact rows: **795 / 795** candidates.
- Verified external Oracle UUIDs: **0 / 795**. They remain null; IDs are not inferred from names or Scryfall page URLs.
- Current Wizards Commander format page and live Banned & Restricted page were checked on 2026-08-13.
- Named Commander-ban intersection with the current RogShai candidate pool: **0**.
- Special-category bans remain covered by the existing canonical `commander_legal` field rather than being guessed from names.
- Multi-face names recognized conservatively: **8**; exact layout is left unspecified where no verified layout field exists.

## Phase C — Card feature enrichment

- Multidimensional `CardFeatureVector` materialized for **795 / 795** candidates.
- No universal objective power score is generated.
- Each feature carries fact/derived/inferred/unknown provenance.
- `unknown` is distinct from `false`.
- Recipient-aware mana semantics separate own resources from opponent/target-player resources.
- Existing legacy role tags remain available as provenance but are not automatically authoritative over recipient-aware facts.

Concrete correction example: `An Offer You Can't Refuse` is no longer safe to count as reliable own ramp merely because its text contains Treasure mana; the recipient is the countered spell's controller.

## Phase D — Mana-source enrichment

- Mana-relevant candidate profiles: **121**.
- Reliable/self mana producer classification: **113**.
- Recipient/condition unresolved: **7**.
- Explicit non-self/no-self-mana result among mana-relevant rows: **1**.
- W/U/R/C production, Commander-identity fixing, tapped/conditional tapped, T1/T2/T3 source quality, fetchability/basic types, Ishai W/U support, burst vs repeatable mana are separated.
- Land count and basic count remain separate design axes.
- Exact conditional ETB/rules evaluation remains outside the structural model.

## Phase E — Package graph

- Enriched RogShai package nodes: **14** (11 existing functional packages + 3 new evidence-backed search packages).
- New search packages: `low_curve_velocity`, `recursion_rebuild`, `trigger_multiplier`.
- Existing package-connected candidates: **199**; enriched package-connected candidates: **267**.
- Package relations include enables/pays-off/protects/creates-resource/amplifies-trigger/supports-rebuild.
- Package membership is descriptive/search evidence only; it creates no include prior or reservation.

## Phase F — Current meta research / functional profiles

- Existing general meta latest remains `meta-2026-08-05-phase12-1`; it is not overwritten.
- New dedicated research snapshot: `meta-2026-08-13-rogshai-research-1`.
- Two direct 2026 tournament-winning RogShai lists are retained as verified decklist references: Summer Classic 3 (206 players) and Misplay on the Lake (264 players).
- Current EDHTop16 and EDHREC are stored as aggregator context, not local-meta truth.
- A related Ishai/Jeska Optimized EDHREC reference is stored as high-power structural context with an explicit different-partner transfer limitation.
- Functional profile metrics are distributions where possible. Direct sample size is only n=2 and is marked small-sample.
- Functional-meta distance excludes unknown dimensions and renormalizes remaining weights. `OWNED_POOL_NEUTRAL` has exactly zero meta weight.
- cEDH remains a structural/card-quality/sequencing benchmark, not a blueprint for the local normal-four-player environment.

## Critical remaining information gaps

1. Real final Morcant 100 remains high-EVI user/real-world evidence.
2. Real Cosmic Spider-Man 100 remains high-EVI user/real-world evidence.
3. Real deviations/upgrades from Doom, Blight, Dance and Wakanda remain useful but are not required to proceed with whole-deck search.
4. External Oracle UUID coverage remains intentionally zero until a verifiable bulk/API source is actually ingested.
5. External rules engine remains `NO_PROVIDER_READY` and is not a blocker for the next structural whole-deck phase.

## Governance result

- canonical RogShai changed: **false**
- inventory changed: **false**
- allocation changed: **false**
- purchases changed: **false**
- opponent observations changed: **false**
- Kaervek changed: **false**

## Phase boundary

Phases A–F are enrichment only. No official whole-deck optimization campaign or canonical deck decision is included in this work.
