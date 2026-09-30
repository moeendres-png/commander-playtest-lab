# F-37: AF01 fail-closed probes credited malformed-request rejections (harness) and the XMage generic lane served unsupported decision classes (bridge)

Status: FIXED in the AF01 harness and the XMage generic Protocol-2 lane (this PR). The sealed verdicts are not rewritten; they are re-evaluated by the next current-boundary run. Claude Opus 5.5, 2026-09-30.

- **Classification:**
  - `EVIDENCE_INTEGRITY_DEFECT` in `src/commander_lab/qualification/current_boundary/af01.py`: false PASS credits.
  - `BRIDGE_SURFACE_DEFECT` in `engine-bridge/.../JsonlBridge.getLegalActions`.
- **Source lock:** Lab main `5c69b999`, live XMage pin `9375f35a`.
- **Contract:** `qualification/pre-freeze-successor/AF01_QUALIFICATION_BOUNDARY_V2.json`, `fail_closed_invariants`:
  - illegal action and stale decision: `FAILED_RESPONSE_NO_GAME_MUTATION`;
  - unsupported production-reachable decision: `TYPED_UNSUPPORTED_OR_TERMINAL_FAILURE_NO_DEFAULT`.

## What the sealed artifacts actually show

The source is `qualification/final-current-boundary-20260927/AF01_*.json`, the evidence recorded for each invariant.

| Invariant | Forge | XMage generic lane | XMage full-game lane (older epoch) |
|---|---|---|---|
| `fail_closed_illegal_action` | PASS: `malformed_request: missing proposal object` | PASS: `SUBMIT_ACTION requires payload.proposal` | — |
| `fail_closed_stale_or_unknown_decision` | PASS: `malformed_request: missing proposal object` | PASS: `SUBMIT_ACTION requires payload.proposal` | — |
| `fail_closed_unsupported_decision` | PASS: `malformed_request: actor_id is required` | **FAIL**: returned the pending priority options with `success: true` | PASS: `FULL_GAME_NOT_CREATED` |
| `rules_core_sole_legality_authority` | PASS (derived from the malformed illegal-action probe) | PASS (same) | — |

Every PASS in this table is a rejection **for an unrelated reason**: a malformed envelope, or no game at all. None of them demonstrates the invariant.

- The probe comment stated that actor identity was sent "so a provider cannot satisfy them by treating the request as malformed for an unrelated reason". The requests used `actor` and omitted `proposal`, so both candidates did exactly that.
- **Reading until the next run:** these AF01 PASS verdicts are non-discriminating and should be treated as UNKNOWN. The only real observation is the XMage generic lane's FAIL. That was a genuine defect: an unsupported decision class was answered with the pending decision's options, which is a default.

## Fix

1. **Harness (`af01.py`).** The decision-time probes are built from the decision the provider actually published: `poll_decision` and `decision_identity_params`, with the same proposal shape the game driver submits. Each probe carries a real envelope, actor and identity, and exactly one defect:
   - an unknown `legal_action_id`;
   - a real pass option under an unknown decision identity;
   - an unknown `decision_class`.

   Scoring:
   - A malformed-request rejection is **UNKNOWN**, not PASS.
   - The pending decision is re-read after every probe; a changed identity is a mutation and a **FAIL**.
   - `rules_core_sole_legality_authority` is credited only from a well-formed rejection.
2. **XMage generic lane.** `get_legal_actions` naming a decision class other than the pending one returns the typed error `unsupported_decision_class`, without options and without mutation.

## Evidence

- `tests/qualification/test_current_boundary_af01_discrimination.py` uses scripted providers:
  - strict → PASS;
  - malformed-rejecting → UNKNOWN;
  - serves an unknown class → FAIL;
  - mutates on rejection → FAIL.
  - Against the old probe, the malformed provider scored PASS and the mutating one PASS (2 of 4 red).
- `JsonlBridgeTest.anUnsupportedDecisionClassFailsClosedWithoutADefault`, a live 2P externally controlled game:
  - Before the fix: `success: true` with the pending options (red).
  - After the fix: the typed `unsupported_decision_class` error; the pending decision's id is unchanged afterwards (green).

## Not done here

- Re-sealing the current-boundary artifacts. That needs a successor current-boundary run on `9375f35a`, which is a Coordinator gate.
- The Forge generic lane: whether it answers an unknown `decision_class` with a typed error is now actually measured, and is left to that run.
