# FINAL_PREFREEZE_EVIDENCE_CLOSURE — handoff (#441)

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## Source Lock

| Role | Identity |
|---|---|
| Lab origin/main at packet | `a79257c23061e3f380afff5c288d96a26843e572`, tree `6473e05e3be3165f0bfcf41bb8b995b06fe1d4e7` |
| This branch | `hardening/final-prefreeze-evidence-closure-20261001` |
| Producing source of the epoch | `fac12a9b73b13c235ea1aa7f97e2696c5376d59d`, tree `3234e300d6990c9c7a570fab12bfd9ed927b3d27` |
| Successor evidence epoch | `qualification/current-boundary-epochs/fac12a9b73b1-3234e300d699/` (65 files, all verified against the CI-produced `CURRENT_BOUNDARY_SHA256SUMS`) |
| XMage candidate | `9375f35ac7c9a540ebcb8b262b8645b8c6b1b326` |
| Forge Rules-Core candidate | `bb0a740d2bef725194798383c2452213ecdd0b37` |
| Forge bridge/materialization source | `e8b8aec60720aee218338754224721597b8c6ec5` |
| Effective FULL107 contract | `commander-lab.full107/1.0.7-successor` (9 corrected fixtures) |
| Historical epoch (untouched) | `qualification/current-boundary-epochs/4cad91897216-a43e80d96595/` |

## Work Completed

1. **Gate 0 / ownership census** — #440 merged (953b231d) and #443 merged (a79257c2)
   were consumed by a normal merge; #444 (XMage repin v3) remains a foreign-active
   surface and was not touched or consumed. See `OWNERSHIP_AND_DRIFT.json`.
2. **A — Forge AF04 reassembly (CLOSED)** — the hard-coded UNKNOWN was replaced by a
   measured derivation over the same-epoch external decision frames.
   `AF04 = PASS` for both candidates, from 30 (Forge) / 25 (XMage) proven frames.
3. **C — fixture errata (CLOSED as versioned records)** — successor contract 1.0.7
   carries the seven inside-cast script errata and the MICRO_COSTS CR 307.1 fixture
   correction; digests recomputed; lineage preserved.
4. **D — typed unsupported-decision refusal (CLOSED)** — explicit control-plane
   refusal implemented and exercised: the four NEGATIVE_* rows are now PASS with
   well-formed refusals (`UNSUPPORTED_DISCRETIONARY_DECISION`, no submission, no
   state mutation), never timeouts.
5. **AF05–AF09 gate derivations** — the remaining hard-coded gate literals were
   replaced by derivations; AF04 now also measures the `ORDER_CHOICE` class added by
   the merged #443 policy.
6. **H — reassembly** — a fresh source-bound epoch was produced by the PB-03
   workflow on the exact branch head (run 36829423872, green), assembled and
   downloaded, its 65 digests verified byte-for-byte, and committed unchanged.

## New Findings

- **The Forge AF04 premise was false on the current evidence.** The same-epoch
  cardinality artifact answers STARTING_PLAYER, MULLIGAN and PRIORITY externally
  at 2P–6P with engine-recorded acceptance. The residual was an assembler literal,
  not missing evidence.
- **The corrected MICRO_COSTS fixture is now executable up to the decision.** The
  engine offers `Hex — Cast Hex` for P2 on the corrected checkpoint (it offered no
  cast under the CR 307.1-illegal predecessor), so the predecessor record was a
  fixture defect, exactly as the Coordinator ruled.
- **Two Lab-lane selectors are the only residual on three corrected rows**: the
  divided-damage `target_amount` frame is a multi-select `choose_targets` offer
  (`Select targets (selected 0 of 4) (damage)`) followed by the engine's assignment
  leg; the lane implements neither the `semantic_objects` list selector nor the
  `amount_assignment` selector. PILOT_MULTI_AMOUNT also needed the observed
  `multi_amount → target_amount` engine-class mapping (added).
- **Typed refusal works on the real production surface** for both mode and target
  frames, with the no-mutation proof recorded in the row execution.

## Changes

- `src/commander_lab/qualification/current_boundary/decision_boundary.py` (new):
  AF04 derivation from same-epoch external decision evidence.
- `src/commander_lab/qualification/current_boundary/gate_derivations.py` (new):
  AF05–AF09 derivations.
- `src/commander_lab/qualification/current_boundary/refusal.py` (new): explicit
  typed refusal with no-mutation proof.
- `src/commander_lab/qualification/current_boundary/midgame_rows.py`: fail-closed
  probe handling, `fail_closed:`/`decision_frame:`/`create_*_token:` verifiers,
  refusal evidence in receipts, five corrected rows registered, `multi_amount`
  engine-class mapping.
- `scripts/assemble_current_boundary_evidence.py`: AF04–AF09 derived; no gate
  verdict is a literal for those gates any more.
- `scripts/resolve_pre_freeze_contract.py`: per-record correction classes.
- `src/commander_lab/qualification/current_boundary/source_lock.py` and the
  qualification contracts: successor 1.0.7 wiring.
- `qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_7.json`,
  `SEMANTIC_FIXTURE_SCHEMA_v1_0_7_SUCCESSOR.json` (new); v1.0.6 preserved
  byte-for-byte.
- New epoch, packet JSONs and tests.

## Tests / Evidence

| Classification | Evidence |
|---|---|
| `DIRECTLY_VERIFIED` | PB-03 workflow run 36829423872 green on `fac12a9b`; 65/65 epoch digests verified |
| `DIRECTLY_VERIFIED` | 19 mid-game lane rows executed, 19 verified, each with an R-4 positive receipt bound to candidate/runner/requested-state/obligation |
| `DIRECTLY_VERIFIED` | 4 NEGATIVE_* rows PASS on well-formed typed refusals (`state_mutated=false`, `submissions_in_window=[]`) |
| `DIRECTLY_VERIFIED` | AF04 PASS for both candidates (30 / 25 proven frames) |
| `DIRECTLY_VERIFIED` | `python3 -m pytest tests -m "not external"` → 2953 passed, 11 skipped |
| `CODE_DERIVED` | AF05–AF09 residuals derived from the epoch artifacts |
| `MODELED` (non-credit) | local development runs against a machine-local XMage artifact, used only to validate lane mechanics before CI |
| `UNKNOWN` | AF05–AF09 on both candidates; see below |

## PASS / FAIL / UNKNOWN

| | XMage | Forge |
|---|---|---|
| FULL107 | **24 PASS / 0 FAIL / 44 UNKNOWN / 39 BLOCKED** | **5 PASS / 0 FAIL / 58 UNKNOWN / 44 BLOCKED** |
| AF00–AF04 | PASS | PASS |
| AF04 | **PASS (was PASS)** | **PASS (was UNKNOWN)** |
| AF05–AF09 | UNKNOWN (derived, exact mechanisms) | UNKNOWN (derived, exact mechanisms) |
| AF10 | PASS | PASS |
| AF11 | POST-SELECTION | POST-SELECTION |

Denominator 107 unchanged. No crash/timeout/protocol failure. No ranking.

## Historical Evidence Invalidated

- The sealed R-5 epoch `4cad91897216-a43e80d96595` remains byte-for-byte untouched
  and is still valid provenance for its own source identity; it is **not** current
  evidence for this branch.
- The nine corrected fixtures invalidate their predecessors' evidence identity:
  new requested-state digests, new materialization digests, and
  `supersedes_record_digest` records the predecessor. No predecessor verdict was
  transferred; WS05-CMD-START-2 and the eight errata rows were re-executed.
- Historical PASS on the five XMage lifecycle rows and the 14 mid-game rows was
  re-earned with current receipts, not carried forward.

## Remaining Blockers (exact mechanism)

1. **AF05 (both candidates)**: the 20 mandatory HIDDEN_* rows require a
   principal-scoped knowledge-projection observation channel (identities,
   face-down permissions, look audiences, controller authority, shuffle
   invalidation, honeycard sentinel). The mid-game lane exposes zone *counts* only
   and the generic lane exposes no per-scenario channel instrumentation. The
   fixtures are typed (`face_down` objects carry explicit types); the missing piece
   is the lane observation channel plus the `knowledge_projection:*` verifiers.
2. **AF07 (both candidates)**: 29 actual-card identities have no passing mandatory
   CARD_* row. The mid-game lane currently verifies 1 of them (CARD_02); the other
   28 need the same causal placement lane extended per card.
3. **AF09 (both candidates)**: `export_replay` is refused by both engines
   (XMage `unsupported_message`, Forge `unknown_message`). The obligation is a
   fresh-process twin with same-provider semantic tape/checkpoint equality; no
   twin executor exists yet, and the lane does not publish checkpoint state hashes.
4. **AF06/AF08**: every remaining UNKNOWN/BLOCKED row is enumerated with its
   mechanism in the epoch's `PROVIDER_READINESS_CURRENT.json` residual list.
5. **Three fixture rows still gated on Lab lane selectors**: MICRO_COSTS
   (`semantic_objects` list selector + a cost-charge verifier with a negative
   control), PILOT_TARGET_AMOUNT and PILOT_MULTI_AMOUNT (`amount_assignment`
   divided-damage selector over the engine's multi-select frame).
6. **PR #444 (foreign-active)**: if merged, the XMage pin moves to `4e59e8b9` and
   every XMage result in this epoch requires requalification on the new candidate.

## Outputs

- `qualification/current-boundary-epochs/fac12a9b73b1-3234e300d699/` (65 files,
  digests verified), including `FULL107_*_RESULTS.json`, `AF00_AF11_*`,
  `PROVIDER_READINESS_CURRENT.json`, `MIDGAME_ROW_EXECUTIONS.json`, positive
  receipts and native receipts.
- `docs/final_prefreeze_evidence_closure_20261001/` with
  WORKSTREAM_CONTRACT, SOURCE_LOCK, OWNERSHIP_AND_DRIFT, FORGE_AF04_REASSEMBLY,
  CAUSAL_DIRECT_EXECUTION_LEDGER, FIXTURE_ERRATA_LEDGER,
  TYPED_UNSUPPORTED_DECISION_RESULTS, HIDDEN_CHANNEL_RESULTS,
  ACTUAL_CARD_29_RESULTS, REPLAY_TWIN_RESULTS, VALIDATION and this handoff.
- `.foundry/final-prefreeze-evidence-closure-20261001.yaml` (resumable state).

## Dependencies Unblocked

- #255 can now adjudicate provider eligibility with a current, source-bound
  per-candidate matrix in which Forge AF04 is evidence-derived rather than
  hard-coded.
- The fixture-errata and typed-refusal deliverables remove two of the three
  Coordinator-flagged harness questions; the remaining one (three lane selectors)
  is enumerated by mechanism.

## Exact Next Action

Coordinator adjudication on #255 from `PROVIDER_READINESS_CURRENT.json`. The
single highest-value pre-Freeze implementation item left is the mid-game lane
extension: a `choose_targets` multi-select + divided-damage `amount_assignment`
selector (with a negative control) to close MICRO_COSTS, PILOT_TARGET_AMOUNT and
PILOT_MULTI_AMOUNT; then the hidden-projection observation channel for AF05.

FINAL_PREFREEZE_EVIDENCE_CLOSURE = PARTIAL
PRODUCTION_PROVIDER = NOT_SELECTED
ARCHITECTURE_FREEZE = NOT_CLAIMED
SAFE_TO_CLOSE_SESSION = YES
