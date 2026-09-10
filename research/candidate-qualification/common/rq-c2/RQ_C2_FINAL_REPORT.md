# RQ-C2 Final Report — Official Rules / Oracle Authority Verification Pack

## 0. Terminal verdict

**`RULES_AUTHORITY_PACK_READY_FOR_SOL`**

Rationale: every one of the 37 RQ-C1 packets is source-complete for Sol
adjudication — current Oracle text verified, current CR sections
verified line-anchored in one coherent baseline, official rulings
collected where applicable, stale references corrected, direct-vs-
interpretive separated, and the smallest exact questions framed. Six
scenario amendments plus one fixture-design approval must still be
DIRECTED BY SOL before candidate execution, but none of them prevents
meaningful adjudication now (directing them IS part of the queued Sol
task). No official first-party source was inaccessible, so the
with-source-blockers variant does not apply; the pack is not blocked.

## 1. Source lock

- RQ-C1 parent HEAD `714ad417c1c090eb4ddf1ccd0828a2e869a80a74`, TREE
  `709a5944c9826dbaaa433052f3538425c8f0573b`, branch
  `research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910`,
  disposition `NEUTRAL_CORPUS_READY_PENDING_RULES_ADJUDICATION`.
- RQ-C2 branch `research/rules-authority-verification-rq-c2-20260910`,
  worktree `/home/moeen/code/rq-c2-rules-authority-verification`.
- Official CR baseline: effective **2026-08-07**, retrieved 2026-09-10
  from `media.wizards.com` (sha256 `4381ad1b…f527423`).
- Gatherer Oracle/rulings retrieved 2026-09-10 (11 direct pages);
  Scryfall 49/49 + Ornithopter secondary crosscheck same day.
- RQ-C1 tree verified UNMODIFIED (validator check 9 green).

## 2. Work completed (all contract §26 outputs persist)

`RQ_C2_SOURCE_LOCK.md`, `RQ_C2_AUTHORITY_BASELINE.md`,
`RQ_C2_ORACLE_INDEX.json` (50 cards), `RQ_C2_RULE_REFERENCE_INDEX.json`
(40 provisions + 5 stale-reference mappings), `RQ_C2_PACKET_STATUS.json`
(37 packets), `RQ_C2_FIRST_WAVE_AUTHORITY_STATUS.json` (15),
`RQ_C2_EXPECTED_ASSERTION_REVIEW.json` (117 items over 40 scenarios),
`RQ_C2_HIDDEN_INFO_AUTHORITY.md`, `RQ_C2_RNG_AUTHORITY.md`,
`RQ_C2_SETUP_BOUNDARY_REVIEW.md`, `RQ_C2_CORRECTION_LEDGER.json/.md`
(18 entries), `Q_G04_SOL_ADJUDICATION_PACKET.md`,
`Q_K02_SOL_ADJUDICATION_PACKET.md`, `RQ_C2_SOL_ADJUDICATION_QUEUE.md`,
`validate_rqc2.py` (24/24 green), `WORKSTREAM_STATE.yaml`, this report.

## 3. New findings (beyond RQ-C1)

1. **All three Oracle flags RESOLVED VERIFIED** (Gatherer-direct):
   Murder `{1}{B}{B}` Instant "Destroy target creature" (0 rulings);
   Cultivate full text + 2010 single-land ruling; Ornithopter 0/2
   artifact creature Flying `{0}` (0 rulings). No substitutions needed.
2. **Five stale RQ-C1 rule citations** corrected to current numbers
   (702.13→701.19, 702.36→702.37, 602→118.9/601.2b,
   701.19b→701.23b, 704.5c→903.10a) plus three supplied numbers
   (701.38a, 700.2, 701.9b).
3. **C01 uncastable as specified** (first-wave BLOCKING): Island is
   colorless (105.2+305.6); no 3UU either. Fixture amendment required.
4. **H02 PATH_A contradicted**: both Growth/Frog orders yield 4/4
   (613.4b/c + 6 official Frog rulings). Objective must be reframed.
5. **F02 hidden-info contradicted**: Duress reveals to ALL (701.20a);
   retained knowledge stays usable. Amendment required.
6. **E02/A03 nonexistent decisions**: no blocker-ordering step exists
   in current CR (510.1c is free division); no may/decline shield
   application (701.19a automatic). Scripts must drop those offers.
7. **G04/K02 prepared as direct authority** (800.4a verbatim example;
   704.5j + 700.4) — Sol promotes; no genuine ambiguity found.
8. Official rulings secured for 8 cards (Turn to Frog 6, Council's
   Judgment 6, Delina 3, Humility 3, Doubling Season 5 distinct,
   Mana Crypt 1, Braids 1, Kokusho 0, Murder 0, Ornithopter 0).

## 4. Oracle verification (explicit)

- Murder: `ORACLE_TEXT_VERIFIED`. Cultivate: `ORACLE_TEXT_VERIFIED`.
  Ornithopter: `ORACLE_TEXT_VERIFIED` (fixture descriptor confirmed;
  flying/`{0}` immaterial to D06).
- Index totals: 11 `ORACLE_TEXT_VERIFIED` (Gatherer-direct), 39
  `SCRYFALL_CROSSCHECK_CONSISTENT`, 0 mismatch, 0 blocked.
- Runeclaw Bear: vanilla, no Oracle rules text; "(Vanilla 2/2.)" is an
  accurate neutral descriptor (2/2, `{1}{G}`, Creature — Bear).

## 5. Rules authority baseline

Single coherent baseline for all 37 packets: CR effective 2026-08-07
(newest published as of 2026-09-10). No mid-workstream update occurred.
Every packet citation verified line-anchored; every external record
carries provenance; Scryfall never cited as authority.

## 6. First-wave authority status (15)

- Ready pending Sol (10): A04, B01, C03, D06, E01, F01, G02, H01, I01,
  J02.
- Amendable (2): A03 (minor — drop may offer), E02 (moderate — drop
  ordering, offer compliant divisions).
- Blocked correction (1): C01 (fixture uncastable).
- Gated (2): G03 (ledger-legitimacy design question), G04 (direct
  recommendation awaiting promotion).

## 7. Q-G04 / Q-K02

- G04: `SOL_REVIEW_RECOMMENDED_DIRECT_AUTHORITY`. 800.4a + verbatim
  Mind Control example decide every §9 point: Aura leaves with P0,
  Bear under P1, no gap, no triggers, SBAs resume. Full packet filed.
- K02: (1) cross-controller coexistence + zero triggers mechanical
  (704.5j condition fails). (2) Same-controller transit = dies
  (700.4, no exception) → Artist fires once; competing readings (a)/(b)
  recorded with rejections. Sol promotes/authorizes. Full packet filed.

## 8. Complete 37-packet status

30 `AUTHORITY_TEXT_VERIFIED` (incl. G04/K02 with direct-authority
recommendations), 6 `AUTHORITY_REFERENCE_CORRECTION_REQUIRED` (A03, C01,
E02, F02, F03, H02), 1
`AUTHORITY_TEXT_VERIFIED_INTERPRETATION_REQUIRED` (G03), 0 blocked, 0
duplicates, 0 unknown. Preparation only — no evidence promotion.

## 9. Expected-assertion review (117 items)

107 SUPPORTED_DIRECTLY, 2 SUPPORTED_WITH_INTERPRETATION (G03 ledger-
dependent terminals), 2 OVERASSERTED (A03 may, E02 ordering), 1
UNDERASSERTED (E02 division breadth), 5 CONTRADICTED (C01 x3, F02
rest-privacy, H02 PATH_A), 0 AUTHORITY_UNKNOWN. RQ-C1 text unmutated;
amendments live in the ledger.

## 10. Hidden-information authority

40/40 scenarios reviewed. One correction (F02 reveal-to-all + retained
knowledge). J03 confirmed as the correct no-reveal contrast case. F01,
F03, B02 and all public-stack scenarios supported. Provider must encode
the F02 amendment before F02 executes.

## 11. Rules-RNG authority

F01/J01/J02/J03 Rules semantics verified (701.24a, 705.1/705.2 +
ruling, 706.1/706.3 + Delina rulings, 701.9b). Journal = engineering
contract, explicitly separated from Rules requirements in all four
cases. No chooser may be offered for J03; J01/J02 outcomes journaled.

## 12. Native setup boundary review

35 NATURAL_GAME_START: capable. 4 PRE_STEP_NATIVE_PROGRESSION
(E01/E02/E03/J02): capable (all decisions post-setup, native).
G03 PRE_DECISION_CONSTRUCTION: capable, Sol-confirms-legitimacy (ledger
is pre-game history, not an executed transition).
`SETUP_BOUNDARY_REDESIGN_REQUIRED` not raised anywhere.

## 13. Correction ledger

18 entries (5 reference, 6 amendment-required, 3 supplied numbers, 1
flag-resolution, 3 informational) with impact + recommendation +
revalidation flags. Machine-readable JSON + human MD both persist.

## 14. Sol adjudication queue

9 gate/correction/design decisions (C01 + H02 execution-blocking) + 1
batch promotion (29 direct packets) + 1 no-question confirmation (A02,
C02, F04) + recorded non-questions. Bounded adjudication, no repeated
discovery.

## 15. Tests / evidence

- `validate_rqc2.py`: 24/24 PASS (coverage 40/37/15/3-flags,
  provenance, citation shape, queue completeness, no Muse-awarded
  EXTERNALLY_RULE_VALIDATED, RQ-C1 immutability, no candidate
  authority, ledger completeness, deterministic recounts 114/117/37).
- Evidence classes: RQ-C2 holds DIRECTLY_VERIFIED (retrieval facts
  only). No scenario outcome carries EXTERNALLY_RULE_VALIDATED.
- Behavior credit, Full107, freeze, provider: unchanged (see §17).

## 16. PASS / FAIL / UNKNOWN

`RULES_AUTHORITY_PACK_READY_FOR_SOL` (per §0 rationale).

## 17. Remaining blockers (for Sol, not for pack completeness)

Sol must direct items 1–9 of the queue (notably C01/H02 amendments and
G03/G04/K02 promotions) before candidate execution of affected
scenarios. No technical blocker remains on RQ-C2's side.

`BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`.
`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## 18. Outputs (17 files in `rq-c2/`)

Source lock, authority baseline, oracle index, rule index, packet
status, first-wave status, expected-assertion review, hidden-info
review, RNG review, setup review, correction ledger (JSON+MD), G04
packet, K02 packet, Sol queue, validator, state file, final report.

## 19. Dependencies unblocked

`FIRST_WAVE_RULES_AUTHORITY_READY_FOR_SOL = YES` — the full 15-scenario
first wave is source-complete for Sol adjudication (10 ready-pending-
promotion, 2 amendable per queue, 1 blocked-pending-amendment, 2
gated). Candidate execution would become rules-ready AFTER Sol
adjudication + directed amendments. RQ-C2 does NOT authorize candidate
execution.

## 20. Exact next action (smallest Coordinator action only)

Sol High: work `RQ_C2_SOL_ADJUDICATION_QUEUE.md` items 1–9 in order
(C01 amendment first), then batch-promote item 10; return promotion +
amendment directions to the execution lane.
