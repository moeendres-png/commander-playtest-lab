# PR #304 Review Remediation and Closure — 2026-09-29

Workstream: `research/csn-engine-capability-delta-20260929` (PR #304)
Remediation branch: `pb03/304-remediation-on-dafe2ac6`
Worktree: `/home/moeen/code/lab-pb03-remediation2-20260929`

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 0. Why this document exists

Six review findings on PR #304 were unresolved, and the exact-head Production
Qualification lane failed its WS17 artifact/hash integrity test. This document is
the authoritative record of what each finding required, what changed, how it was
proven, and what was explicitly **not** changed. Everything here is additive; no
historical observation is rewritten to look as though it happened at a later head.

## 1. Source identity

| Field | Value |
|---|---|
| Base (PR #304 head at remediation start) | `8a7e8e303cdb5f45d971d35c9ded4af25863385b` |
| Main at task authoring | `234318cf83b29420a20d2e9878aa86b7110af55e` |
| **Main actually integrated** | `83a547f739cc1a7072798c55e10829032df8fe88` (main advanced past the authoring lock: PR #315 was `234318cf`, then PR #318 at `83a547f7`) |
| Local continuation head (merge of current main) | `1b7727061c797ffb527b582038a3316f5750b34d` (tree `0cc581f306d5e49bf9f4477455e5af815b5b0a7e`) |
| **PR #304 head this remediation was integrated onto** | `dafe2ac6d903ed55c774841fbfa25cb7584f52d6` ("PR #304 causal completion: remaining rows measured") |

**Concurrent-writer integration.** While this remediation was in flight, another
session of the same workstream pushed `dafe2ac6`, which committed the causal
completion *and* a first-generation copy of this remediation's Python work (it had
been editing the same worktree concurrently; the later generation of that work is
what this branch adds). The remediation was therefore **rebased onto `dafe2ac6`**
rather than pushed over it, and only the genuinely missing pieces were re-applied:
the Java remediation in full, the `failure_verdict` single mapping, the arrival
acceptance fix, the additional wrong-reason/transport/receipt controls, the
observation field rename in the probe, and the WS17 manifest coverage. Nothing of
`dafe2ac6` was reverted.
| XMage engine pin (unchanged) | `b19596980f2734496ea1896504253e1bdd2756dd` (`org.mage:mage:1.4.61`) |
| Remediation worktree tree at start | `0cc581f306d5e49bf9f4477455e5af815b5b0a7e`, clean |

**Main drift adjudication.** Main moved past the task's stated lock while the task
was being executed. The delta was inspected rather than inherited: no file in the
#304-owned surface was edited by main between the earlier merge-base and
`83a547f7`, so the local merge of current main is a fast-forward-style content
merge with no overlapping edits. The intervening main commits are the
multiplayer-lane PRs (#311–#318), which touch the full-game lane
(`XmageFullGamePlayer`), not the mid-game lane. No pre-update PASS evidence was
carried forward on trust: every suite below was re-executed on this head.

## 2. Review finding dispositions (all six)

### F1 — P1: hidden-information leak in `complete_midgame_arrival` — **RESOLVED**

*Required:* stop returning the raw restoration readback (whose `seats[*].hand`
arrays carry every principal's card names), use the existing principal-scoping
authority, return only what the requester may legitimately observe plus
construction/evidence data with no hidden opponent information, and prove it with
positive and negative tests. Do not solve it by deleting useful internal
verification.

*Change:* `XmageMidgameJsonlBridge.completeMidgameArrival` now runs the engine's
field-level compare over the **full** readback exactly as before (that compare, its
verdict and its mismatch list are unchanged and remain authoritative), then
returns a `principalScopedObservation` instead of the raw readback. The projection
follows the policy already established by `XmageFullGameStateRedactor.actorView`
(own hand full, every other principal counts-only) and is a projection of the
engine's own readback, not a second observation layer. New fields:

| Field | Meaning |
|---|---|
| `observation` | the principal-scoped constructed state (replaces `readback`) |
| `observation_scope` | `principal_scoped`, or `principal_neutral_opponent_hands_counts_only` when no requester is named |
| `constructed_state_digest` | digest **over the redacted observation**, so an exposed digest never commits to a hidden identity |
| `constructed_state_digest_scope` | `principal_scoped_observation` |

The requester is bound by `payload.actor_id` and may name either the
requested-state label (`P1`) or the native session principal id for the same
seat; both resolve to the same seat so a caller cannot believe it asked for its
own hand while receiving a fully redacted view. An unrecognized binding fails
closed. No `readback` key is emitted.

*Proof:* `XmageMidgameReviewRemediationTest` —
`unboundArrivalNeverReturnsTheRawReadbackOrAnyHandIdentities` (no `readback` key;
zero seats carry a hand; counts still present),
`aBoundRequesterSeesOnlyItsOwnHandIdentity` (exactly one seat carries a hand; it is
the requester's),
`onePrincipalCannotObtainAnotherPrincipalsHandIdentities` (a P1-bound observation
has no `hand` on P2's seat; an unknown requester fails closed),
`theReportedDigestCoversTheRedactedObservationAndNotHiddenState` (recomputing the
digest over the delivered observation reproduces the reported value). End-to-end:
`TestReceiptCarriesNoHiddenIdentity` asserts the persisted receipt contains no hand
identity array.

### F2 — P1: negative construction verdict ignored — **RESOLVED**

*Required:* `construction_match == false` must not become `ENGINE_NATIVE_REACHABLE`
because a mismatch list is missing, empty, malformed or unrecognized. Wrong-reason
tests for false+empty, false+missing, false+unknown kind and malformed response.

*Change:* `midgame_lane.classification_from_arrival` no longer uses `bool(...)` or
`arrival.get("mismatches") or ()`. A strict boolean reader and a strict
mismatch-list reader are used; a non-boolean flag or a non-list mismatch value is
uninterpretable and fails closed as `UNRECOGNIZED_CONSTRUCTION_VERDICT` with
`engine_accepted_starting_state = False`. `ENGINE_NATIVE_REACHABLE` now requires
either the JSON boolean `true` with no mismatches, or `false` where **every**
reported mismatch is a recognized, explicitly modeled disposition (the documented
declaration-step priority allowance) — the only case the contract permits a
negative raw bit to keep its bounded classification. A `true` flag beside
mismatches is self-contradictory and fails closed. The engine's own raw bit is
still reported verbatim. The same strictness was applied to
`classification_from_causal_verdict` (previously `bool("false")` was true), and its
`engine_accepted_starting_state` is now derived from the outcome instead of being
constant — a construction mismatch no longer claims acceptance.

*Proof:* eight new tests in
`tests/qualification/test_current_boundary_midgame_lane.py::TestRowClassification`
covering false+empty, false+missing, false+null, false+string, false+unknown kind,
non-boolean flags, true+real mismatch, true+allowance-only, and the
causal-verdict equivalent. The pre-existing test that codified the contradictory
result (`test_a_false_match_flag_with_no_mismatch_listing_is_not_promoted`, which
asserted reachability from `false`) was replaced by its negation — it was the
review's cited example of the defect, so it asserted the bug rather than
preventing it.

### F3 — P1: advertised request timeout not enforced — **RESOLVED**

*Required:* the timeout must actually bound the wait; a stalled or deadlocked
child must not block the qualification process; reuse the repository's established
deadline/process-read mechanism; on expiry terminate/reap the child, classify as a
transport failure, preserve diagnostics without leaking hidden data, and never
silently retry into a PASS. Add a deterministic timeout regression.

*Change:* `MidgameLaneClient.request` now reads through
`_read_line_with_deadline`, which uses the mechanism already established for the
current boundary in `bridge_launcher.BridgeProcess._read_line_with_deadline`: the
read runs on a daemon thread joined against `timeout_s` (a thread, not `select`,
because the stream is a buffered `TextIOWrapper` whose fd readiness does not imply
a whole line). On expiry the applied deadline and a `TIMEOUT` classification are
recorded on the tape, the child is killed and reaped, and `MidgameLaneTimeout` is
raised. The mechanism is mirrored rather than imported because the established
helper is a private method in a module four concurrent PRs are editing; the
classification vocabulary and shape are shared, and no independent transport model
was introduced.

*Proof:* `TestTransportDeadlineAndClassification.test_a_stalled_child_times_out_and_is_reaped`
is deterministic — the child is a local one-liner that reads the request then
sleeps 600 s; the test uses a 1 s deadline, asserts the timeout, the recorded tape
entry (deadline + `TIMEOUT`), that the child was reaped (`_process is None`), and
that no shutdown request was sent to a dead child.

### F4 — P2: transport failures converted into `ENGINE_STATE_ACCEPTED` — **RESOLVED**

*Required:* broken pipe, malformed JSON, child termination, rejected submission,
failed arrival readback, timeout and protocol violation must keep an appropriate
transport/protocol classification with zero reachability credit. Only explicitly
recognized semantic unsupported-obligation cases may receive their bounded
disposition.

*Change:* `midgame_lane` now has a typed failure hierarchy —
`MidgameLaneTransportError`, `MidgameLaneTimeout`, `MidgameLaneProtocolError`, all
under `MidgameLaneError` so existing fail-closed handlers still catch them — and
every transport failure mode raises the right type (stdin failure, closed stdout,
non-JSON, non-object). One function, `failure_verdict`, maps a failure to its row
verdict so no caller can reclassify; it raises `TypeError` for anything that is not
a lane error rather than converting it. The probe's two blanket
`except ml.MidgameLaneError` handlers (which rewrote everything, including
`CAUSAL_TRANSPORT_FAILURE`, into `ENGINE_STATE_ACCEPTED`) now call `failure_verdict`,
so timeouts/protocol/transport become `TRANSPORT_FAILURE` with
`engine_accepted_starting_state = False`, and only a recognized obligation case
becomes `ENGINE_STATE_ACCEPTED` (still not a pass). The receipt gained
`transport_failure` and `unrecognized_construction_verdict` counters.

*Proof:* `TestTransportDeadlineAndClassification` covers timeout, closed child,
non-JSON, non-object, broken pipe, the accepted-obligation case, the refusal to
convert an unrelated exception, and a call with no live child. Each transport case
asserts `TRANSPORT_FAILURE` and `engine_accepted_starting_state is False`.

### F5 — P2: concession protocol schema divergence — **RESOLVED**

*Required:* align the mid-game lane with the existing Protocol-2/full-game
concession contract, invent no second schema, verify both offer and submission
representations, and exercise the standard client payload against the mid-game
lane.

*Change:* `getConcedeOffer` now reads `payload.player_id` (was `actor_id`) and
`submitConcede` now reads `payload.proposal` (was a nonexistent nested `payload`,
which passed `null` to the authoritative implementation). The established consumer
`src/commander_lab/semantic_replay/consumer.py::_replay_concede` uses exactly
`{"player_id": principal}` for the offer and
`{"proposal": {"actor_id": principal, "player_id": principal}}` for the submission,
so the lane is now byte-compatible with the contract that already exists.

*Proof:* `concedeOfferAndSubmissionUseTheEstablishedProtocol2Schema` drives the
standard payload through the mid-game lane: the offer reports
`concede_available` from `Game.canConcede` with `concede_action.actor_id` bound to
the requesting principal, the standard proposal reaches the authoritative
submission, and the retired shapes (`actor_id` for the offer, nested `payload` for
the submission) plus a foreign proposal (`actor != subject`) all fail closed. A
documented package-private `nativePrincipalIdAtSeat` was added for the
native-namespace `player_id`; it is not reachable over the wire.

### F6 — P2: colorless commanders rejected — **RESOLVED**

*Required:* do not reject a legal colorless Commander because its color set is
empty; use legal colorless scaffolding (e.g. Wastes) through the same
engine-authoritative import path; prove valid scaffold construction, no fabricated
colored identity, and no relaxation of Commander legality.

*Change:* the `engineCommanderColors` empty-set throw was removed (an empty set is
a legitimate answer — a colorless commander has no colored component), and
`XmageNativeStateRestoration.scaffoldingFiller` now falls back to the game's
colorless basic land (`COLORLESS_BASIC_LAND = "Wastes"`) instead of throwing.
Wastes is not merely permissive here, it is the **only legal** choice: a colored
basic land is outside a colorless commander's color identity, so the previous
behavior made an otherwise supported colorless Commander starting state
unreachable. The scaffold still goes through the engine's real-cards-only
Commander import, which remains the single legality authority.

*Proof:* `aColorlessCommanderScaffoldsWithTheColorlessBasicLand` (Wastes only, no
colored basic), `aColoredCommanderScaffoldIsUnchanged` (colored commanders keep
their previous deterministic scaffold, never Wastes),
`aColorlessCommanderDeckImportsThroughTheEngineAuthority` (99 Wastes plus a
colorless commander import successfully through `importCommanderDeck`),
`theColorlessScaffoldIsRejectedForAColoredCommanderSlotOnlyByTheEngine` (an unknown
card still fails closed in the engine, so legality was not relaxed Lab-side).

## 3. CI failure: WS17 artifact/hash integrity — **REPAIRED**

*Cause.* `tests/qualification/test_ws17_qualification.py::test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts`
requires `WS17_SHA256SUMS` to list exactly the three named root files plus **every**
file under `qualification/`, and `qualification/SHA256SUMS` to list every file
under `qualification/` except itself. The continuation added
`qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json` but never
registered it in either manifest, so the manifests no longer covered the changed
artifact set.

*Repair (existing mechanism, no weakening).* Both manifests were repaired through
their canonical construction: the new artifact was appended with its real SHA-256
to both, and the root manifest's entry for `qualification/SHA256SUMS` was
re-hashed because that file legitimately changed. Nothing was excluded, no digest
was bypassed, no assertion was weakened, and the artifact was not deleted. Exact
churn:

```
qualification/SHA256SUMS  +1 line  (the new artifact)
WS17_SHA256SUMS            1 hash updated (qualification/SHA256SUMS) + 1 line added
```

*Independent proof.* `pytest tests/qualification/test_ws17_qualification.py` →
12 passed, which independently re-verifies every digest against its file.

## 4. Continuation impact adjudication (phase A+B work at the base head)

The base head added `causal_stack`, `causal_elimination`,
`XmageMidgameCausalBridge` and the causal tests, and expanded the probe from the
original 16-row description to 17 rows. Assessed against this remediation:

| Question | Finding |
|---|---|
| Does it obey the six remediations? | Yes after this remediation. The causal path had its own transport→`ENGINE_STATE_ACCEPTED` conversion (finding F4) and its own `bool()` causal flag (finding F2); both are fixed. |
| Does causal entry introduce a second rules engine? | No. Causal entry places a pre-causal position and then *verifies* the engine's stack/loss/leave state and survivor set. It performs no legality, cost, target, mode or division computation. |
| Do stack/priority/zone/elimination outcomes stay engine-authoritative? | Yes. `completeCausalReconstruction` reads the engine's own stack and loss/leave flags; a route the engine did not produce fails closed with the engine's mismatches. |
| Does every pilot decision come only from engine-generated legal options? | Yes. The causal drivers submit only option ids present in the engine's own `legal_options`; the probe refuses an unrecognized decision class rather than guessing. |
| Is hidden state still principal-scoped? | Yes, and now more strictly: the arrival observation is principal-scoped and the receipt contains no hand identity. |
| Can its classification turn transport/construction failure into reachability? | No. After F2/F4, transport/protocol/timeout failures are `TRANSPORT_FAILURE` and an uninterpretable construction verdict is `UNRECOGNIZED_CONSTRUCTION_VERDICT`; both carry zero reachability credit. |

**No FULL107 row was promoted.** The 17-row probe partition is unchanged by this
remediation (see §5): the change is to how the consumer classifies and redacts,
not to what the engine can do.

## 5. Probe partition before/after (regenerated at this head)

The receipt was regenerated against the pinned engine (`engine_commit=b1959698…`)
because F1 changed what `constructed_state_digest` covers, which made every
previously recorded digest unreproducible. The row set is the causal-completion
set: 29 rows.

| | before remediation | after remediation |
|---|---|---|
| probed | 29 | 29 |
| `ENGINE_NATIVE_REACHABLE` | 8 | 8 |
| `CAUSAL_ROUTE_REACHABLE` | 9 | 9 |
| `CAUSAL_ROUTE_MEASURED_BLOCKED` | 10 | 10 |
| `ENGINE_REJECTED` | 2 | 2 |
| `ENGINE_STATE_ACCEPTED` (obligation not executed) | 0 | 0 |
| `CONSTRUCTION_MISMATCH` | 0 | 0 |
| `UNRECOGNIZED_CONSTRUCTION_VERDICT` (new counter) | — | 0 |
| `TRANSPORT_FAILURE` (new counter) | — | 0 |

The partition is **identical**: this remediation changed how the consumer
classifies and redacts, not what the engine can do. No row moved and no row was
promoted. `constructed_state_digest` changed for the rows that reach construction,
because it now covers the redacted observation; every pre-remediation digest is
superseded rather than silently reused.

Row-count history for the record: 16 rows at the original HANDOFF, 17 after the
phase A+B continuation, 29 after `dafe2ac6` measured the remaining causal rows.

## 6. Documentation reconciliation

The 16-row wording in `HANDOFF.md`, `IMPLEMENTATION_DECISION.md` and
`ENGINE_CAPABILITY_REUSE_MATRIX.md` was the earlier state; the current receipt has
17 rows. Those lines are corrected with a pointer here rather than being rewritten
as though the 17-row result existed at the earlier head.
