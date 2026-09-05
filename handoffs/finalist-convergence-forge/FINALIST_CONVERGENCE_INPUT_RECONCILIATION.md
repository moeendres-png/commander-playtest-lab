# COMMANDER SIMULATION FOUNDRY
# FINALIST CONVERGENCE — COMPLETED INPUT RECONCILIATION

## Status

`INPUT_RECONCILIATION = COMPLETE`

This document integrates the two independently completed parallel inputs into the continuing Finalist Convergence Program. It creates no runtime PASS and does not supersede source-locked runtime evidence.

## Finalist Deep-Risk Audit

Canonical user-supplied handoff:

`FINALIST_CONVERGENCE_AUDIT_COMPLETE_REVERIFIED.md`

SHA256:

`7b061553f1e4ebf029b71518e9734546e244d073ed08e04a3a03f48f4b6cdcf1`

Status:

`COMPLETE / PASS`

All five required axes are terminally audited and must not be repeated merely for completeness:

1. Rules-RNG completeness
2. Hidden-information / omniscience exposure
3. Multiplayer / Commander hazards
4. Rules-Core / Pilot boundary static reachability
5. Native state-loader capability

Binding downstream findings:

- XMage actor-facing hidden physical handles are deterministic functions of deck/card identity and therefore are not admitted for production AF05. Remediate with opaque non-inferable actor-facing handles; keep privileged semantic lineage internal.
- Forge native Netplay/GameView delta transport is not an admitted external-pilot observation boundary. Preserve the dedicated actor-entitled GPL-side provider projection.
- Both pinned engines have process/JVM-global Rules RNG authority. Until per-session RNG is proven, use at most one active simulation session per engine process/JVM.
- Forge state construction is `PARTIAL_BROAD / NOT_FULL`; XMage WS-26 state construction is `PARTIAL_NARROW / NOT_FULL`.
- Unsupported canonical dimensions fail closed. No pilot-side Rules emulation.
- Direct Rules-core defects established by that audit: Forge 0, XMage 0.

## POST-135 Card Qualification Design

Canonical user-supplied ZIP:

`POST135_CARD_QUALIFICATION_COMPLETE.zip`

ZIP SHA256:

`72303539f9b713b4001878639c769cb3ca2a2e5534fd7aa54776274f30ae37a6`

Status:

`COMPLETE / PASS_CLOSED / DESIGN_ONLY`

All required 11 machine outputs are present. Important exact output digests include:

- `CARD_QUALIFICATION_DESIGN.json`: `ad727cf598fedca72e3736f833dbcaf4f9fd3e5eb3eace922f91b2dce71df9ca`
- `TIER_MANIFESTS.json`: `30cd44bfbc75aa530aa7bf09d2ce5195de9cdf257b6ef82408e0bb3f293422c9`
- `RISK_SCORE_MODEL.json`: `5c3bf281be096112270a31e20f8c9f22de71f2df323f8635c2d14fc6d88de991`
- `MINIMUM_DIAGNOSTIC_SET.json`: `ec5bd08d7053b264e9216e6a2879e6fae31385e364263316e8e5a70293705269`
- `COVERAGE_SATURATION.json`: `0874ade99fa2299f9c3976767b04ed6796371677f98282313f4f55de4a2e29f6`

Design outputs include:

- authoritative rules-path features: 58
- mechanic signatures: 1,034
- singleton signatures: 926
- authority-only singleton cover: 15 cards
- operational singleton diagnostic set: 18 cards
- high-risk pairwise augmented set: 27 cards / 115 pairwise interactions
- coverage shallow point: 33 cards
- physical representative tier: 62 cards
- deterministic High-Risk 100
- T0 Frozen29 / T1 RogShai87 / T2 Kaervek77 / T3 High-Risk100 / T4 physical representative / T5 full 1,385

Representative tiers are diagnostic/prioritization tools only. They do not create FULL runtime functionality credit for unexecuted cards.

## XMage Natural-Start Source Reconciliation

A fresh continuation audit found an apparent contradiction: the committed `XmageWs26QualificationSession.configureScenario` source still contains `options.testMode = true`, while successful convergence runtime evidence proves native opening hand / mulligan behavior.

This is now terminally explained by the exact CI path, not an unresolved runtime contradiction.

At convergence head `e1d19ff65ee08ce9fb1dcec846a38277b49fb5c8`:

- `candidate-qualification/finalist-convergence-xmage/apply_natural_start_overlay.py` removes the unconditional `testMode=true` assignment and replaces it with:
  - `options.testMode = !NATURAL_GAME_START.equals(executionEntryMode)`
  - `options.skipInitShuffling = !NATURAL_GAME_START.equals(executionEntryMode)`
- `.github/workflows/finalist-convergence-xmage.yml` explicitly applies this overlay before building the candidate bridge.

Therefore the successful run `33395818923` genuinely compiled and executed the natural-start qualification behavior with `testMode=false` for NATURAL_GAME_START, without changing the pinned XMage upstream repository.

`XMAGE_NATURAL_START_EXPLANATION = CLOSED / PASS`

Do not rediscover this issue in the next program phase unless source locks drift.

## Current Starter-18 Convergence

Forge runtime head:

`7e2525c7ee54af2da28aeca0d75e3a4009da2601`

XMage convergence head:

`e1d19ff65ee08ce9fb1dcec846a38277b49fb5c8`

Neutral v1.0.1 contract:

- head `9a8b8f5f5961466514eae6103be2d227324a27a8`
- bundle `ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee`

Exact same-record result:

- `DIFFERENTIAL_AGREEMENT_PASS = 5`
- `CANONICAL_SETUP_UNSUPPORTED_BOTH = 13`
- all direct disagreement/provider/contract failure counts = 0

The five verified agreements are player-count 2P/3P/4P/5P and `PILOT_MULLIGAN`.

## Next Program Use

Do not redo the completed audits, POST-135 design, v1.0.1 linter work, or the five verified Starter-18 lifecycle fixtures.

Next implementation should close the remaining 13 Starter-18 rows by shared native provider primitives, then execute the corrected Union-50, then expand through the 72 currently executable v1.0.1 records and AF04–AF08. The 63 remaining neutral contract defects should receive new immutable errata only when required, and every changed fixture must be rerun on both finalists before differential credit.
