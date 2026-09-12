# RQ-C3-B01 Authority Adjudication (WS66, research/authority only)

- Source lock: CPL base `7796619e69b0434cd232de8335ff5cab3c5d08e5`;
  RQ-C3 authority `897d72f0b57bb8febe045870acaa3d2dba4bde56`;
  WS60 terminal `731891ec5ed8e7611fc9a636bab5fc3c400108eb`.
- No engine/provider/harness semantic edits. No behavior reruns. No behavior
  credit from this workstream. Read-only sealed-artifact parsing only.

## 1. The contradiction (exact)

RQ-C3-B01 simultaneously asserts:

1. `native_setup_boundary: NATURAL_GAME_START` with `execution_entry_mode`
   natively progressed from game start;
2. neutral fixture state: five Soul Wardens on the battlefield
   (P0x2, P1x1, P2x1, P3x1) **at life 40/40/40/40**;
3. terminal assertion: **absolute** life totals 42/41/41/41 after P0 casts
   Llanowar Elves (i.e. exactly +2/+1/+1/+1 from 40);
4. fixture notes: "Wardens established through native plays."

Soul Warden oracle text: "Whenever another creature enters, you gain 1 life."
Each natively entering Warden (after the first) is "another creature" entering
as seen by every previously-entered Warden, so native construction of five
Wardens fires setup triggers before the Elves event. The conjunction
(2)+(3) with (1)+(4) is therefore unsatisfiable under correct Rules
implementation: life cannot still be 40/40/40/40 when the fifth Warden is in
play, and the absolute 42/41/41/41 terminal cannot follow a lawful native
setup.

## 2. Mechanical unavoidability proof (order-independent total)

Number the five native Warden entries in arrival order 1..5. When Warden k
enters, exactly the k-1 previously-entered Wardens each trigger once (the
entering Warden does not trigger on its own entry; each earlier Warden sees
exactly one other creature enter). Setup trigger total = 0+1+2+3+4 = **10**,
independent of seating/cast order. Per-player distribution is order-dependent,
but no order keeps all four players at 40: at minimum the controller(s) of the
earliest Wardens gain life. (Simultaneous entry does not escape either: each
Warden still sees each other entering creature.) Hence the fixture's
life-40-with-five-Wardens neutral state is unreachable by native play, and the
absolute terminal 42/41/41/41 is unreachable with it.

Sealed confirmation (read-only parse of WS65 B01 journal, 385 frames):
life ledger 40/40/40/40 -> 41/40/40/40 -> 42/41/40/40 -> 43/42/41/40 ->
44/43/42/41 across five native Warden casts (exactly 10 setup life-steps at
revs 64,107,111,154,158,162,205,209,213,217); native tape shows setup Zone
Changer triggers 4+3+2+1 = 10 for Wardens (8)/(314)/(208)/(107). Pre-Elves
life is 44/43/42/41, never 40/40/40/40.

## 3. Disposition

**B01_AUTHORITY_DISPOSITION=CORRECTION_REQUIRED.**

- Not VALID_AS_WRITTEN: the as-written conjunction is unsatisfiable (Section 2).
  WS60's bounded native attempt honestly stopped UNKNOWN at the decision bound
  against this fixture; WS65's native construction proved the offset
  (pre-Elves 44/43/42/41) rather than the absolute terminal.
- Not UNKNOWN: the defect location and the minimum repair are both directly
  supported by Rules-mechanical derivation plus sealed frame evidence. The
  Rules semantics under test (simultaneous-trigger creation, APNAP stacking,
  same-controller ordering, top-down resolution, per-trigger life gain) are
  fully intact; only the terminal life assertion's absolute form is defective.
- Failure class: **FIXTURE_DEFECT** (fixture-expectation unsatisfiable as
  written). Not ENGINE_DEFECT, PROVIDER_ADAPTER_DEFECT, or HARNESS_DEFECT: no
  Rules, transport, or runner misbehavior is evidenced by the offset.

## 4. Minimum correct authority (option (a); (b) rejected)

**B01_CORRECTED_REQUIREMENT (relative-delta form, NATURAL_GAME_START retained):**

> From any lawful pre-Elves life totals (L0/L1/L2/L3) with five Wardens in play
> (P0x2, P1x1, P2x1, P3x1) reached by native progression: P0 casts Llanowar
> Elves; its ETB creates exactly five Soul Warden triggers; the triggers stack
> in APNAP order (P0's two at the bottom, then P1, P2, P3 on top); P0
> externally orders exactly its own two triggers; all five resolve top-down
> with an empty stack at end; terminal lives are exactly
> L0+2 / L1+1 / L2+1 / L3+1; Llanowar Elves is on the battlefield under P0.

Concretely the correction strikes only the absolute terminal assertion
("P0 life 42, P1/P2/P3 life 41") and replaces it with the relative assertion
("P0 +2, P1/P2/P3 +1 from lawful pre-Elves totals, stack empty, five triggers
resolved in APNAP order"). `expected_rules_events` (CAST, 5-trigger ETB,
APNAP stacking, controller ordering, top-down resolution, LIFE +2/+1/+1/+1)
are carried forward **verbatim** -- the LIFE line was already relative. No
executable semantics change.

Why (a) and not (b):

- (b) (declare the board pre-established, blame NATURAL_GAME_START) rewrites an
  authority identity field (`native_setup_boundary`), contradicts the fixture's
  own notes ("Wardens established through native plays"), and invents a
  pre-establishment permission absent from RQ-C3 -- a broader rewrite, not the
  minimum.
- (a) preserves every sealed behavior observation (trigger count, ordering
  offer, resolution order, delta, replay) and changes only the unsatisfiable
  absolute-life form. WS60's secondary construction limit (Commander-singleton
  second-P0-Warden assembly) is a harness/deck-construction concern, untouched
  by and orthogonal to this authority correction.
- The choice follows the evidence, not the beneficiary: (a) is the unique
  repair under which both candidates' sealed records remain exactly what they
  are (WS60: no Elves event reached; WS65: full relative behavior proved).

## 5. What WS65 proved against the corrected authority (no rerun)

Read-only parse of sealed WS65 B01 artifacts
(`RQ-C3-B01/journal.json.gz`, `replay.json.gz`, `adjudication.json`):

- Elves-95 cast (rev 349); exactly five Elves-ETB Warden triggers created and
  resolved (native tape: 5x cast + 5x resolved
  `[Zone Changer: Llanowar Elves (95)]`).
- Exactly one `trigger_order` frame (rev 355, seq 356) with exactly two
  engine-offered permutations (MINTED-3-first vs MINTED-8-first); external
  single-match pick [3,8].
- APNAP top-down resolution evidenced by five sequential +1 life steps
  (revs 360,364,368,372,376: P4, P3, P2, P1, P1) from 44/43/42/41 to
  46/44/43/42: exact delta +2/+1/+1/+1.
- Stack empty (combat proceeds; COMBAT_DECLARE_ATTACKERS at rev 384);
  hidden-info PASS; semantic replay PASS with 0 divergences.
- Setup ledger (10 native setup triggers; pre-Elves 44/43/42/41) documented
  with the unavoidability proof; absolute offset explained, never passed off
  as a match.

Every element of the corrected requirement is directly evidenced. The
correction changes no executable semantics, so the historical PASS survives
impact adjudication (see WS65_IMPACT.json).
