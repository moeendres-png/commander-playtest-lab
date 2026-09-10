# RQ-C3 Coordinator Adjudication (Binding Transcription)

Source: RQ-C3 contract §3 (Coordinator / Sol High authority). Muse implements mechanically; no reinterpretation, broadening, or additional Rules authority.

## C01 — AMEND_REQUIRED

RQ-C1 fixture invalid: Island is colorless and cannot be exiled as Force of Will's required blue card. Corrected C01 preserves architecture question with both payment routes genuinely legal: (1) normal `3UU`; (2) alternate 1 life + exile blue card from hand. Corrected fixture: enough untapped mana sources for `3UU`; Force of Will in P0 hand; separate genuinely BLUE NONLAND card in P0 hand; P1 casting valid target spell; no external legality reconstruction. Five untapped Islands acceptable as mana sources (NOT pitch). Simplest suitable blue nonland support card whose color/Oracle identity already officially verified in RQ-C2 selected (Turn to Frog; if none existed, add minimal support card with direct official Oracle provenance). No support card with additional semantics relevant to scenario. Execution script distinguishes `NORMAL_COST_AVAILABLE` and `ALTERNATE_COST_AVAILABLE` then chooses alternate. Pitch-card selection is hidden-zone decision until exiled. Every assertion stating Island itself is blue retired.

## H02 — REFRAME

Old 1/1-versus-4/4 divergence not preserved. Giant Growth and Turn to Frog resolve into different sublayers: Turn to Frog base P/T layer 7b; Giant Growth modification layer 7c. +3/+3 applies after base-setting irrespective of timestamps. Both orders yield `4/4 blue Frog` (no other effects). H02 is now reverser for `LAYER_SUBLAYER_PRECEDENCE_OVERRIDES_TIMESTAMP_ACROSS_7B_7C`, not timestamp-divergence. PATH_A=1/1 retired. No replacement card invented to retain divergence.

## F02 — AMEND_REQUIRED

Duress reveals chosen player's hand public to ALL while it occurs. Checkpoints: before reveal target hand private except owner/authorized; during reveal public; after effect hand hidden again; legitimately acquired knowledge remains usable and must NOT be classified as provider leak merely because observers remember it. Do not claim only Duress controller sees revealed hand.

## A03 — AMEND_REQUIRED

Fabricated second `may`/yes-no Decision for applying already-created regeneration shield removed. Discretionary choice is activation + cost payment. Once valid regeneration effect exists and destruction would occur, replacement applies per Rules. Removed `yes, apply shield at destruction` and expectation both apply/decline offered at destruction. Retained: activation, mana/payment, priority/pass, target/cast of opposing spell. Replacement application not turned into external pilot Decision.

## E02 — AMEND_REQUIRED

Obsolete blocker-ordering Decision removed completely. No blocker-ordering step, two permutations, or externally selectable blocker-order option required/asserted. Preserved: declare attacker/defender, declare blockers, combat damage assignment where current Rules require player assignment, priority/pass. For Carnage Tyrant/Bear/Elves, assignment 2 to Bear, 1 to Elves, 4 to defending player may remain as concrete tested legal assignment if supported by RQ-C2 authority. No obsolete ordered-blocker prerequisite claimed.

## G03 — APPROVED WITH FIXTURE BOUNDARY

Pre-existing 12 commander damage may be `PRE_DECISION_CONSTRUCTION` fixture state. Seeded ledger receives `BEHAVIOR_CREDIT = 0`. Candidate later receives credit only for post-boundary native behavior: native attack, native block/pass, native combat damage, ledger increment, crossing 21 threshold, Rules loss, resulting native leave-game transition insofar as asserted. No commander damage injected during combat. Seeded prior 12 not claimed as simulated.

## G04 — PROMOTE

Only exact RQ-C2-documented G04 assertions supported directly by CR 800.4a packet promoted to `EXTERNALLY_RULE_VALIDATED`. Scope not broadened. Candidate behavior untested.

## K02 — PROMOTE

Only exact RQ-C2-documented K02 assertions supported by documented current CR 704.5j/700.4 packet promoted to `EXTERNALLY_RULE_VALIDATED`. Scope not broadened. Candidate behavior untested.

## ORACLE FLAGS

Murder: `ORACLE_TEXT_VERIFIED`. Cultivate: `ORACLE_TEXT_VERIFIED`. Ornithopter: `ORACLE_TEXT_VERIFIED`. Adopt RQ-C2 official Gatherer-direct results. No substitution for those three.

## RULE NUMBER CORRECTIONS

Adopt RQ-C2 corrections: 702.13 -> 701.19; 702.36 -> 702.37; 602 -> 118.9/601.2b where RQ-C2 mapped affected assertion; 701.19b -> 701.23b; 704.5c -> 903.10a. Also supplied mappings where RQ-C2 places them: 701.38a; 700.2; 701.9b. No global search/replace of unrelated references. Apply only to assertions identified in RQ-C2.

## RQ-C2 QUEUE ITEM 10

Exact item 10 in `RQ_C2_SOL_ADJUDICATION_QUEUE.md`: batch-promote only exact claims RQ-C2 classified as ready (29 packets: Q-A01, Q-A04, Q-B01, Q-B02, Q-B03, Q-B04, Q-C03, Q-C04, Q-D01, Q-D02, Q-D03, Q-D04, Q-D05, Q-D06, Q-E01, Q-E03, Q-F01, Q-F03, Q-G01, Q-G02, Q-G05, Q-H01, Q-I01, Q-I02, Q-I03, Q-J01, Q-J02, Q-J03, Q-K01). Those exact claims may become `EXTERNALLY_RULE_VALIDATED` (Sol High approved). Do NOT promote adjacent assertions, candidate behavior, implementation assumptions, fixture convenience, or setup mechanics not covered by official authority.
