# Deckbuilding / Simulation Separation

Status: architecture contract for package 1.24.0  
Candidate runtime: `candidate-pipeline-1.0.0`  
Candidate-set schema: `deck-candidate-set-1.0.0`

## OLD ARCHITECTURE

The historical whole-deck/Optimizer-v2 stack mixed five responsibilities:

1. deck generation from the owned pool;
2. heuristic/search ranking and proposal acceptance;
3. Structural evaluation and mechanics-fidelity routing;
4. QD/frontier/finalist selection and Structural racing;
5. confirmatory comparison/decision.

A legal deck could therefore disappear before any future full-rules gameplay for reasons unrelated to Commander legality or physical feasibility. Relevant mechanisms included constructive/diversified starts, Current-anchored mutations, `objective_prior`, contextual utility, meta distance, mana/package soft scores, bounded archives, finalist limits, mechanics-fidelity `decision_safe`, QD elite admission, Structural racing survival and an eight-entry confirmatory shortlist.

Those mechanisms were useful for a finite Structural search, but they do **not** define the candidate universe for the gameplay architecture.

## NEW ARCHITECTURE

```text
DECKBUILDING WORKER
        ↓
DECK_CANDIDATE_SET
        ↓
HARD VALIDATION
        ↓
ALL VALID UNIQUE CANDIDATES
        ↓
SIMULATION_CANDIDATE_QUEUE
        ↓
┌─────────────────────────────┐
│ FUTURE: XMAGE + OUR PILOTS  │
└─────────────────────────────┘
        ↓
GAMEPLAY EVIDENCE
        ↓
RACING / COMPARISON
        ↓
DECISION
```

The productive pre-simulation path is `commander_lab.candidates`, not Whole-Deck Search or Optimizer-v2 search. Legacy search code remains available for diagnostics, regression tests and deckbuilding reference, but is deprecated as a source of simulation admission.

The machine invariant is:

```text
for every input candidate:
    if hard_validity == PASS and duplicate_identical_deck == FALSE:
        simulation_required == TRUE
        candidate_must_reach_gameplay_queue == TRUE
        no_pre_simulation_heuristic_can_remove == TRUE
```

`SimulationCandidateQueue` additionally fails closed unless the hard-valid unique input count equals the output queue count and the exact Candidate-ID sets match.

## DECKBUILDER CONTRACT

Deck generation occurs outside the simulation stack. The deckbuilder/work chat is responsible for supplying **complete Commander decks**, not candidate cards to be assembled by simulation code.

The external deckbuilder may use any documented design concept, including:

- `CURRENT_CONTROL`
- `OWNED_POOL_NEUTRAL`
- `META_LIGHT`
- `META_MEDIUM`
- `META_HIGH`
- `MAX_FEASIBLE_META_SHAPE`
- `LOW_LAND_HIGH_VELOCITY`
- `RESILIENT_COMMANDER_INDEPENDENT`
- `INTERACTION_HEAVY_LOCAL_META`

These are design metadata and deckbuilding knowledge. They are not gameplay-admission policies.

A deckbuilding worker may submit 40–60 or more candidates in one set. The pre-simulation stack has no finalist cap, QD cap, search budget or Structural-fidelity reduction.

## CANDIDATE SET CONTRACT

`DECK_CANDIDATE_SET` is versioned as `deck-candidate-set-1.0.0` and includes:

- candidate-set identity and creation time;
- source/builder identity;
- target commander color identity;
- exact candidate count;
- candidate ID and label;
- complete commander list and complete mainboard quantities;
- canonical deck hash, supplied or derived;
- optional physical-printing provenance;
- optional design policy/philosophy/hypothesis;
- optional land/package/metadata diagnostics;
- `current_control` marker;
- hard-validity and simulation-required annotations after validation.

No rank and no objective are required.

Canonical hashing uses only normalized deck identity: sorted commander names and sorted mainboard `(oracle_name, quantity)` pairs. Descriptive metadata cannot change deck identity.

Normalization does not add, remove or swap cards.

## HARD VALIDATION

Pre-game blocking is limited to objective invalidity. The validator uses read-only project truth for the selected active target and may emit only documented hard-fail codes:

- `PHYSICAL_AVAILABILITY_INVALID`
- `DECK_SIZE_INVALID`
- `COMMANDER_COUNT_INVALID`
- `COMMANDER_IDENTITY_INVALID`
- `COLOR_IDENTITY_INVALID`
- `COMMANDER_LEGALITY_INVALID`
- `CARD_LEGALITY_INVALID`
- `BANNED_CARD_INVALID`
- `SINGLETON_INVALID`
- `PHYSICAL_QUANTITY_INVALID`
- `ACTIVE_ALLOCATION_CONFLICT`
- `UNKNOWN_REQUIRED_CARD`
- `MALFORMED_CARD_IDENTITY`
- `PARTNER_PAIRING_INVALID`
- `DUPLICATE_IDENTICAL_DECK`

Exact duplicate deck identities are deduplicated after hard validity. Duplicate source IDs are retained as provenance on the queued representative. A duplicate is not a heuristic rejection.

The active target deck's own allocated copies are released **virtually and read-only for candidate validation** because each candidate is an alternative to that target, not an additional simultaneous allocation. Allocations of other active own decks remain conflicts.

Optional `physical_printings` is provenance, not a completeness gate. Canonical inventory quantities remain the physical-availability authority.

The following are explicitly **not** hard gates: objective prior, card utility, meta distance, policy mismatch, land preference/corridor, mana soft score, package coherence, Structural score, Structural decision safety, fidelity tier, Tactical/External routing, Screening-Only status, QD/archive/elite/frontier/finalist membership, Current distance and coverage-debt status.

## LOSSLESS HANDOFF

`SIMULATION_CANDIDATE_QUEUE.json` contains every hard-valid unique candidate with its complete deck payload, canonical hash and source provenance.

For each queued candidate:

```text
validation_status = PASS
simulation_required = true
simulation_queue_status = QUEUED
pre_simulation_elimination_reason = null
```

The queue builder rejects an artifact if either:

- `INPUT_HARD_VALID_UNIQUE_COUNT != OUTPUT_SIMULATION_QUEUE_COUNT`; or
- the exact expected and queued Candidate-ID sets differ.

This makes hidden pre-simulation filtering an invariant violation rather than a permissible optimization.

## STRUCTURAL NEW ROLE

Structural simulation remains useful for:

- unit/regression testing;
- feature and simulator diagnostics;
- software sanity checks;
- historical analysis;
- optional descriptive metadata.

It has no official decision authority:

```text
STRUCTURAL_SIMULATION_DECISION_AUTHORITY = FALSE
STRUCTURAL_SIMULATION_REQUIRED_BEFORE_GAMEPLAY = FALSE
STRUCTURAL_SIMULATION_CAN_ELIMINATE_CANDIDATE = FALSE
STRUCTURAL_SIMULATION_CAN_DECLARE_OFFICIAL_WINNER = FALSE
```

No new work should attempt to evolve the Python Structural simulator into a complete Magic rules engine.

## FIDELITY NEW ROLE

Mechanics fidelity remains diagnostic engine-capability metadata. `STRUCTURAL`, `TACTICAL`, `EXTERNAL`, `SCREENING_ONLY` and `UNSUPPORTED` may describe old-engine coverage, but none can remove a hard-valid candidate from `SIMULATION_CANDIDATE_QUEUE`.

In the target architecture, an `EXTERNAL_RULES_REQUIRED`/unsupported Structural mechanic is evidence that full-rules gameplay must use XMage; it is not a reason to omit gameplay.

## TACTICAL ORACLE NEW ROLE

Tactical rules/oracle code remains available for bounded unit tests, diagnostics, differential tests and pilot/bridge validation. It is not an alternative official decision authority and does not control candidate admission.

```text
TACTICAL_DECISION_AUTHORITY = FALSE
```

## CURRENT CONTROL NEW ROLE

Current is a comparison arm. `current_control = true` may identify it in a candidate set, but Current is not:

- a mandatory search start;
- a search parent;
- a prior;
- a default elite/frontier member;
- a distance anchor used for admission.

Other candidates are never penalized or dropped because they are far from Current.

## POLICIES NEW ROLE

Whole-deck design policies are retained as deckbuilding vocabulary and diagnostic metadata. They no longer determine whether a candidate gets gameplay evidence.

**POLICY = CANDIDATE DESCRIPTION, not SIMULATION ADMISSION GATE.**

Legacy `search_gate` policy/land corridors therefore do not participate in `commander_lab.candidates.validation`.

## LEGACY SEARCH / OPTIMIZER DISPOSITION

Legacy whole-deck generation and search APIs remain in-tree because they encode useful deckbuilding/diagnostic knowledge and historical reproducibility. Their status for the simulation path is `DEPRECATED_FOR_SIMULATION_INPUT`.

Notable dispositions:

- constructive starts / local mutations / search acceptance / bounded archive / finalists: deprecated for simulation input;
- objective/card utility/meta/mana/package features: diagnostic/reference only;
- mechanics fidelity: metadata/diagnostic only for admission;
- Structural evaluation: diagnostic only for official deck decisions;
- pre-game QD/frontier/racing/shortlisting: not permitted as candidate-kill gates;
- post-game QD/racing: retained as a future evidence-allocation concept.

The authoritative inventory is `PRE_SIMULATION_FILTER_INVENTORY.json`.

## FUTURE XMAGE + OUR PILOTS ARCHITECTURE

The target authority split is explicit:

```text
XMAGE                = RULES EXECUTION AUTHORITY
OUR PILOTS           = DECISION POLICY
LAB                  = EXPERIMENT / EVIDENCE CONTROLLER
Structural Simulator = DIAGNOSTIC ONLY
Tactical Oracle      = BOUNDED DIAGNOSTIC / TEST SUPPORT
```

This reset does **not** implement an autonomous XMage 4-player game loop or produce fake XMage evidence.

The prepared future scenario contract (`future-xmage-scenario-contract-1.0.0`) requires, per scenario:

- `candidate_id`
- `deck_hash`
- exactly three `opponent_deck_ids`
- `player_count = 4`
- `seat`
- `scenario_id`
- `seed`
- `xmage_commit`
- `bridge_version`
- `pilot_identity`
- `pilot_version`
- `decision_policy_version`

This is an interface contract only. No gameplay result is fabricated.

## POST-SIMULATION RACING

Adaptive budgets, Pareto selection and QD remain useful **after every hard-valid unique candidate has received an initial full-rules gameplay budget**.

Target sequence:

```text
N hard-valid unique candidates
    ↓
N candidates receive initial XMage gameplay screening
    ↓
GAMEPLAY evidence exists for every candidate
    ↓
post-simulation racing / QD / comparison
    ↓
additional budget for informative/strong candidates
    ↓
decision
```

The present reset stops before the XMage execution and post-game racing implementation.

## HISTORICAL LIMITATIONS RECORDED

Historical Structural optimizer results must be interpreted within their actual candidate-generation/evidence contracts:

- whole-deck search explored only a small fraction of the legal physical deck space;
- the approximately 133-candidate universe was budget/construction constrained, not an exhaustive legal-deck universe;
- heuristic construction influenced which full decks ever became candidates;
- Current-anchored mutations could create local-search bias;
- External/Tactical queues did not provide a complete decision-return path for all candidates;
- Structural mana behavior has rules-fidelity limits;
- Structural combat, wipes and removal are abstractions;
- “Current remained winner” under historical runs is not proof of global deck optimality.

## NON-MUTATION / EVIDENCE BOUNDARY

This architecture reset does not mutate canonical deck, inventory, allocation, purchase or opponent truth. It consumes no official gameplay evidence and opens no sealed holdout.

```text
OFFICIAL_GAMEPLAY_SIMULATION = FALSE
XMAGE_FULL_GAME_CAMPAIGN = FALSE
STRUCTURAL_OFFICIAL_CAMPAIGN = FALSE
TACTICAL_OFFICIAL_CAMPAIGN = FALSE
HOLDOUT_OPENED = FALSE
```
