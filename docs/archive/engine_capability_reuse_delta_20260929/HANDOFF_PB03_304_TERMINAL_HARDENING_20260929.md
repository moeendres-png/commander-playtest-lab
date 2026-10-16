# COORDINATOR HANDOFF — PB03-304-TERMINAL-HARDENING

> **Document identity note.** This file is a *documentation-only* addition written
> immediately after the reviewed implementation state. The reviewed implementation
> identity is **`1098f365485cea949e456f04bec81216b84aaa73`** (tree
> `7ad98dba398a6fc1ae282ca1f60eb8702a0a1b61`). This handoff file itself lives in a
> later docs-only commit on the same branch; nothing in the implementation changes
> because of it.

## Source Lock

| Item | Value |
|---|---|
| Worktree | `/home/moeen/code/lab-pb03-remediation2-20260929` |
| Local branch | `pb03/304-remediation-on-dafe2ac6` |
| **Persisted donor branch** | **`donor/pb03-304-terminal-hardening-20260929`** |
| **Final HEAD** | **`1098f365485cea949e456f04bec81216b84aaa73`** |
| **Final tree** | **`7ad98dba398a6fc1ae282ca1f60eb8702a0a1b61`** |
| Local == remote | **verified, 1098f365 both** |
| merge-base vs origin/main | `83a547f739cc1a7072798c55e10829032df8fe88` |
| origin/main (at stop) | `92ac1cecd3a46628a77e9f58a4ddc46baffdf634` |
| PR #304 remote head | `08d23aa44c721d0825d8be9f1b9c5d2af58cb91c` |
| PR #316 / Muse donor | untouched, not integrated |
| State file | `.foundry/pb03-304-terminal-hardening-20260929.yaml` (committed on the donor branch) |

## Relationship to PR #304

`dafe2ac6` **is an ancestor** of this work — a clean continuation, no history
rewrite. The donor branch carries three commits above it: `08d23aa4` (already
pushed to #304 earlier in this session, before the stop), `1b69c31f` and
`1098f365` (local + donor branch only, **not** on #304). I did **not** modify #304
or main during this increment.

## F1–F8 disposition

| | Status |
|---|---|
| **F1** principal-scoped arrival | **DONE** — internal full-readback compare kept; response carries a principal-scoped `observation` (own hand only, others counts-only, none when unbound); digest covers the redacted view; **mismatch/diagnostic hand identities now redacted** for non-owners and unbound callers. **2 OPEN ITEMS** below. |
| **F2** negative construction verdict | **DONE** — strict boolean + strict mismatch list; empty/missing/null/string/unknown/non-boolean all fail closed as `UNRECOGNIZED_CONSTRUCTION_VERDICT`; no `ENGINE_NATIVE_REACHABLE`/`CAUSAL_ROUTE_REACHABLE` from a negative or malformed verdict. |
| **F3** timeout/lifecycle | **DONE** — reuses the established `bridge_launcher` deadline-read shape (no competing subsystem); child killed + reaped; `TIMEOUT` recorded on the tape; deterministic 1 s regression. |
| **F4** transport classification | **DONE** — typed hierarchy + single `failure_verdict`; transport/protocol/timeout granted zero credit; non-lane exceptions refused rather than converted. |
| **F5** concession | **RETAINED as bounded schema alignment** — the lane advertises `concede_supported: true`, so a wrong request schema was a defect on an advertised surface; now `payload.player_id` / `payload.proposal` matching `semantic_replay/consumer.py`. Rules Core authoritative; no injected outcome. **Successor should confirm this adjudication.** |
| **F6** colorless commander | **DONE** — empty color identity accepted; Wastes scaffold; no card-name special case in production code; regression now covers **two** colorless Commanders. |
| **F7** causal credit gating | **DONE** — `causal_credit_gate` requires the engine's real arrival verdict before any causal credit; the three drivers propagate a withheld verdict instead of discarding it; a placement entry no longer fabricates `{"causal_match": true}`. |
| **F8** WS17 manifest | **DONE at `08d23aa4`** — both manifests sealed by appending the receipt with its real digest and re-hashing the nested manifest; test not weakened, no exclusion, artifact kept. **Must be re-sealed if the receipt is regenerated.** |

## New Findings (for the successor)

1. **🔴 OPEN P1 — `pending_decision` leak vector.** `completeMidgameArrival` still
   adds `requireSession().pendingDecisionPayload()` unconditionally. That frame is
   for whoever holds priority and its `legal_options` labels can name that
   principal's hand cards, so a caller bound to a *different* principal can still
   learn the acting principal's hand identity. Same class as F1, **not fixed**.
   Suggested repair in the state file (gate on `decision.actor_id` == native
   principal at the requester's seat).
2. **End-to-end honeycard control is not provable with the current frozen corpus.**
   `HIDDEN_HONEYCARD_SENTINEL` (P2 holds `Demonic Tutor`) is rejected as
   `UNSUPPORTED_ZONE … requests library`; the only other lane-supported records
   with a hand identity (`WS05-MP-PRIO-3/5`, `Giant Growth`) are rejected as
   `UNSUPPORTED_ZONE … requests stack`. A lane-supported hand-planted sentinel
   fixture is Lab qualification data → authorization question. Recorded in the
   test file as a documented gap, not silently accepted.
3. The placement-obligation path previously derived its outcome from a
   **hardcoded** `{"causal_match": true}`; that fabrication is now removed and
   replaced by a classifier that claims only the measured obligation.

## Tests / Evidence at the final head

| Check | Result |
|---|---|
| engine-bridge focused (lane 10, causal 25, remediation 12) | **47/47, 0F/0E, BUILD SUCCESS** |
| `test_current_boundary_midgame_lane.py` | **50 passed** |
| `test_ws17_qualification.py` | **12 passed** |
| `ruff check .` / `ruff format --check .` | **All checks passed / 1084 formatted** |

**NOT run after the final increment** and therefore **UNKNOWN** for `1098f365`: the
29-row probe runtime re-derivation, full engine-bridge suite, full repository
pytest, mypy strict, and any exact-head workflow (no PR was opened for this
increment). The earlier full validation and green exact-head CI belong to
`08d23aa4`, not to `1098f365`.

## PASS / FAIL / UNKNOWN

**PASS** for the committed, locally validated increments. **UNKNOWN** for the
outstanding runtime re-derivation, full suites, mypy, and remote CI at `1098f365`.
No row was promoted; the last measured 29-row partition was unchanged by the F1/F7
work in this increment, but that is a claim from the prior run, not a
re-measurement.

## Remaining Blockers

The two F1 items above, plus re-derivation/re-seal and the full validation sweep.
Nothing blocks the successor from starting — the state is green and coherent at the
persisted head.

## Outputs

- `donor/pb03-304-terminal-hardening-20260929` @ `1098f365` (donor-only; **must not
  be merged** without review).
- `.foundry/pb03-304-terminal-hardening-20260929.yaml` — full state, open leak
  vector, incomplete work, validation ledger.
- Earlier preserved foreign/local work: `/tmp/opencode/foreign-preserve` (hashed
  copies + 1519-line patch).

## Dependencies Unblocked

The successor can take a green, coherent, principal-scoped, fail-closed, causally
honest tree with explicit open items, rather than reconstructing this session's
reasoning.

## Exact Next Action

Fetch `donor/pb03-304-terminal-hardening-20260929` @
`1098f365485cea949e456f04bec81216b84aaa73`, review the three commits above
`dafe2ac6`, then **first** close the `pending_decision` leak vector
(highest-severity open item), then decide whether to continue #304 or open a
successor PR, then re-run the probe + full suites and re-seal WS17 before claiming
terminal state.

**PRODUCTION_PROVIDER = NOT_SELECTED** · **ARCHITECTURE_FREEZE = NOT_CLAIMED**
