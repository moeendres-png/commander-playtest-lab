# WS47 — CURRENT RULES AUTHORITY

## Source Lock

Authority was freshly checked during WS47 on 2026-09-08 against Wizards of the Coast primary rules sources.

- Official Magic rules page: `https://magic.wizards.com/en/rules`
- Current Comprehensive Rules linked by that page: `https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt`
- Effective date: **2026-08-07**

Provider behavior is **not** rules authority for this adjudication.

## Relevant Rules

- **CR 302.6** — Summoning sickness restricts attacking and `{T}`/`{Q}` activation as specified; it does not itself prohibit blocking.
- **CR 509.1a** — The defending player chooses which untapped creatures they control, if any, will block, subject to applicable legality constraints.
- **CR 509.1b** — Blocking restrictions are checked when declaring blockers.
- **CR 802.4a** — Under Attack Multiple Players, each defending player declares blockers for creatures attacking that player, a planeswalker they control, or a battle they protect, using creatures they control.
- **CR 802.4b** — When determining whether a defending player's blocks are legal, creatures attacking other players and blockers controlled by other defending players are disregarded as specified by the multiplayer blocking procedure.

## Frozen WS44 State Facts Used

Exact source: immutable `qualification/ws44/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json`, target `WS05-MP-BLOCK-4`, independently extracted and record-digest verified by WS47 run `34230220407`.

- `obj:P2-bears`: **Grizzly Bears**, owner `P2`, controller `P2`, zone `battlefield`, `tapped=false`, `face_down=false`, counters `{}`.
- `obj:mp-p2-blocker`: **Runeclaw Bear**, owner `P2`, controller `P2`, zone `battlefield`, `tapped=false`, `face_down=false`, counters `{}`.
- `continuous_rules_effects`: absent / no represented blocking restriction.
- WS44 `combat_state.eligible_blockers`: only `obj:mp-p2-blocker`.
- Frozen expected event: `legal_blocker_partition:P2`.
- Frozen terminal postcondition: P2 blocker options contain only attackers for which P2 is defending player.

## Adjudication

For the exact frozen state represented by `WS05-MP-BLOCK-4`, both declared untapped P2-controlled Bears belong in P2's represented legal blocker candidate surface in the absence of a blocking restriction. A creature controlled by P3 must not be included in P2's blocker surface merely because it is on another defender's battlefield.

Therefore WS44 v1.0.4 is semantically incomplete at:

`WS05-MP-BLOCK-4.combat_state.eligible_blockers`

The provider-neutral successor repair is:

- predecessor: `["obj:mp-p2-blocker"]`
- successor: `["obj:P2-bears", "obj:mp-p2-blocker"]`

This repair does **not** change the frozen obligation `Defender/blocker partition`; it completes the requested-state representation needed to test that obligation.

## Status

`G47-03_AUTHORITY_CLOSURE = PASS`

No provider runtime PASS is imported. No AF07 or Architecture Freeze credit is granted.
