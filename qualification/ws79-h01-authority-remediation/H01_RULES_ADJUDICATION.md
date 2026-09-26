# H01 Rules Adjudication — Old Oracle Reconstruction, Supersession, Corrected Family

Status: binding Coordinator adjudication for WS79 (see task brief). This file
records what historical H01 claimed, why it is superseded, and the corrected
three-case authority. It grants no behavior credit and executes no engine.

Evidence classification of THIS file's claims is recorded in
`H01_AUTHORITY_PROVENANCE.json`. Rules-text verification below is
`EXTERNALLY_RULE_VALIDATED` as text provenance only; no candidate behavior
verdict follows from it.

## 1. Historical H01 claim — exact reconstruction (SUPERSEDED)

Source: `research/candidate-qualification/common/rq-c3/scenarios/RQ-C3-H01.json`
at historical terminal `897d72f0`
(blob `c4e742526670a2fdf86b0fcb9c048d8d584646c0`).

Setup: Humility already on the battlefield (P2), Runeclaw Bear on the
battlefield (P1), Clone in P0 hand. P0 casts Clone.

Old expected decision sequence (`expected_rules_events`):

1. `HUMILITY already on battlefield (established natively)`
2. `CAST Clone; COPY_CHOICE: enter as Runeclaw Bear`
3. `COPY_APPLIED in layer 1 (copies printed 2/2; timestamp-independent)`
4. `HUMILITY_APPLIED in layers 6/7b: loses all abilities, base 1/1`
5. `FINAL: Clone is a 1/1 creature with no abilities (an ability-less Bear copy)`

Old external decision script: P0 `copy choices` → "enter as copy of Runeclaw
Bear" with legal-set expectation "all battlefield creatures offered", then
pass to resolution.

Old terminal assertions (both classified `EXTERNALLY_RULE_VALIDATED` via the
item-10 packet):

- "Clone is 1/1 with no abilities on battlefield"
- "original Bear is 1/1 with no abilities (Humility)"

Old Rules citations (`authority_provenance.rules`):
`613.1a/f/g`, `613.4b`, `613.7`, `707.2`.

Old semantic objective: "Prove copy-before-Humility layering: Clone entering
as a Bear under Humility must end as an ability-less 1/1."

Correction source: `CARRY_FORWARD_UNCHANGED (item-10 promotion Q-H01)` —
prior Coordinator direction "No semantic correction: carry forward RQ-C1
semantics unchanged"; Sol High item-10 batch promotion applied to the exact
RQ-C2-verified claims.

### 1.1 Defects of the old oracle

- **CR 614.12 absent.** The cited rules cover layer ordering (613.x) and copy
  effects (707.2) but never the entry-replacement applicability rule that
  governs whether Clone's own copy replacement applies at all when Humility
  pre-exists. The applicability question precedes the layering question, and
  the old oracle never asked it.
- **Copy decision wrongly required.** The old sequence demands a `COPY_CHOICE`
  under a pre-existing Humility. Under CR 614.12, existing Humility must be
  considered when checking the would-be battlefield state: Clone would enter
  with no abilities, so its self copy-replacement ability has no applicable
  instance — no copy decision occurs.
- **Non-discriminating terminal.** "1/1 with no abilities" is produced both by
  the correct no-copy path (Clone enters as Clone, Humility makes it 1/1,
  ability-less) and by the incorrect copy-then-Humility path (Bear copy made
  1/1, ability-less). The old terminal cannot distinguish them, so a PASS
  against it proves nothing about the decision-occurrence question. The two
  paths diverge only after Humility leaves (Clone-as-Clone → printed 0/0 →
  dies to state-based actions; Bear-copy → 2/2 Bear).

Disposition: `H01_OLD_ORACLE = SUPERSEDED`. The old expected decision sequence
(copy choice under pre-existing Humility) is Rules-incorrect and must not be
used as an oracle for any current or future behavioral run. The old terminal
assertion set is rejected as a sufficient oracle (it remains a true visible
sub-state, but insufficient and non-discriminating).

## 2. Fresh official Rules provenance (verified 2026-09-12)

- **CR 614.12** (current text, via mtg.wiki CR mirror and the 2016-11-17
  Judge "Enters the battlefield replacement effects" article quoting it
  verbatim): "Some replacement effects modify how a permanent enters the
  battlefield. … Such effects may come from the permanent itself if they
  affect only that permanent (as opposed to a general subset of permanents
  that includes it). They may also come from other sources. To determine
  which replacement effects apply and how they apply, check the
  characteristics of the permanent as it would exist on the battlefield,
  taking into account replacement effects that have already modified how it
  enters the battlefield (see rule 616.1), continuous effects from the
  permanent's own static abilities that would apply to it once it's on the
  battlefield, **and continuous effects that already exist and would apply to
  the permanent**."
- **CR 614.12a**: a choice required by an entering-replacement is made before
  the permanent enters. (No choice is made when no applicable replacement
  requires one.)
- **Direct precedent — Meddling Mage under Humility** (same Judge article
  Q&A): Amy casts Reanimate on Meddling Mage while controlling Humility — "the
  game considers the characteristics of Meddling Mage as it would look on the
  battlefield, and once it's on the battlefield, Humility will make it lose
  its abilities. Because it won't have the 'name a card' ability on the
  battlefield, that replacement effect won't apply." Clone under pre-existing
  Humility is the same shape: the self copy-replacement will not be present
  in the would-be battlefield state, so it does not apply.
- **CR 613.x / 707.2** (layers; copy in layer 1 before Humility in layers
  6/7b) remain correct *conditional* authority: they govern the
  copy-then-Humility path (H01-B) once a copy identity exists. They do not
  create a copy decision in H01-A.
- Version note: a 2013 Judge article quotes an older 614.12 phrasing
  ("ignoring continuous effects from any other source"); the current text
  above (verified via two independent current-text sources) expressly includes
  already-existing continuous effects. The corrected oracle follows the
  current text.

## 3. Corrected three-case authority (binding)

Exactly three semantic cases (machine-readable: `H01_CORRECTED_CASES.json`).
No fourth case.

### H01-A — HUMILITY_FIRST (the corrected RQ-C3-H01 scenario)

Humility exists before Clone enters.

- Existing Humility is considered during CR 614.12 entry-replacement
  applicability.
- Clone has no applicable self copy-replacement ability in the would-be
  battlefield state.
- **No copy decision occurs** (no choice offered, none taken).
- Clone enters as Clone (not a copy of anything).
- Humility makes it 1/1 with no abilities.
- Discriminator: if Humility leaves afterward, Clone returns to its printed
  0/0 characteristics and dies to the applicable state-based action
  (toughness ≤ 0).
- Falsifier: any offered/taken copy choice for Clone in this ordering, or any
  post-Humility 2/2 Bear state, contradicts H01-A.

### H01-B — CLONE_FIRST

Clone enters while no Humility exists, copying Runeclaw Bear.

- Copy decision occurs; Bear-copy identity is established (layer 1).
- Later Humility makes it 1/1 with no abilities (layers 6/7b).
- Discriminator: after Humility leaves, it remains the Bear copy and is 2/2.
- Falsifier: loss of Bear-copy identity after Humility leaves, or absence of
  the copy decision at entry, contradicts H01-B.

### H01-C — NO_HUMILITY

Normal Clone copy behavior with no Humility involved at any point.

- Copy decision occurs; Clone enters as the chosen copy with that
  creature's copiable characteristics as modified by layer 1.
- Falsifier: suppression of the copy decision, or entry as a non-copy 0/0
  Clone that was never subject to Humility, contradicts H01-C.

## 4. Authority consequences

- `H01_THREE_CASE_AUTHORITY = PASS` (exactly HUMILITY_FIRST, CLONE_FIRST,
  NO_HUMILITY; machine-enforced by `validate_ws79_h01.py`).
- `H01_DISCRIMINATING_ASSERTIONS = PASS`: each case carries a
  post-Humility discriminating state plus a negative/falsifying expectation;
  the old lone "1/1 with no abilities" terminal is explicitly rejected as
  sufficient.
- Decision-requirement delta for downstream requalification: in the RQ-C3
  First-Wave contract, H01 no longer contributes a required `copy choices`
  decision for the HUMILITY_FIRST ordering (the historical decision script
  and `RQ_C3_FIRST_WAVE_DECISION_REQUIREMENTS.json` union entry for H01 are
  predicated on the superseded oracle).
- No engine execution belongs to this workstream; no behavior credit is
  granted (`BEHAVIOR_CREDIT_CHANGE = 0`).
