# Causal Continuation — PR #304 Phase A+B (2026-09-29)

Continuation of `research/csn-engine-capability-delta-20260929` (PR #304).
Base for this continuation: `5bf43604` (merge of current `main` `128e9118`).
Executor: `opencode-go/muse-spark-1.3-contributor` at `XHIGH`.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Source truth at continuation start

| Field | Observed |
|---|---|
| PR #304 | OPEN, not merged, head `960ed1b6caded95a52b24ecafd037acb6704d89f` |
| `origin/main` | `128e91185b66df92e4bec726abb89c7c20fbbb11` |
| Relationship | #304 ahead by 2, behind by 20, merge base `2e28866f…` |
| Intervening commits touching #304's 14 paths | **none** |
| Adjacent changes | `XmageFullGameActionProjection.java` (+1 tier mapping), `XmageFullGamePlayer.java` (+19 special-mana actions) — additive, non-breaking |
| Open PRs | 45; #300/#299/#289/#284 live; all 14 #304 paths touched only by #304 |
| Merge | normal merge commit, no rebase/squash/rewrite |
| Post-merge regression | 68/68 incl. lane + drift-affected tests |

Exclusive #304 ownership held for the whole session. No second writer.

## 2. What was built

One generic mechanism — **causal entries on the existing `midgame` lane** —
servicing stack reconstruction, priority-sensitive scenarios, Commander zone
transitions, micro zone changes and causal elimination. No new Rules semantics.
No new transport. No edits to any file owned by another PR and no edits to the
causal source classes themselves (composition only).

### New files

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageMidgameCausalBridge.java`
  — `prepareCausalStack` (reuses `XmageCausalStackReconstruction.prepare`),
  `planCausalElimination` (reuses `planFromFrozenRecord` + `validatePlan`),
  `verifyCausalStack` (stack order/controller/identity/targets/modes from live
  engine state), `verifyCausalElimination` (victim lost/left, survivor set,
  life totals; codes mirror the native suite's own codes).
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageMidgameCausalTest.java`
  — 10 native tests over the real Protocol-2 surface.

### Extended (#304-owned) files

- `XmageMidgameJsonlBridge.java` — `entry_mode` (`placement` default,
  `causal_stack`, `causal_elimination`), declared `fuel` / `elimination`
  specs, `complete_causal_reconstruction {mode}`. The placement path is
  byte-for-byte the previous behaviour, refactored into `createPlacement`.
- `midgame_lane.py` — `CAUSAL_ROUTE_REACHABLE` /
  `CAUSAL_ROUTE_MEASURED_BLOCKED` outcomes, `classification_from_causal_verdict`,
  `entry_mode` + `causal_verdict` on every row.
- `run_midgame_capability_probe.py` — causal drivers, default row set extended
  with `WS05-MP-PRIO-5`, receipt carries the new partition.
- `test_current_boundary_midgame_lane.py` — 3 new classifier tests (17 total).

## 3. Design decisions forced by evidence

**Fuel and instruments are declared, never inferred.** Every card that exists
only to make the route executable arrives in the request, is placed through the
engine seam and is published in the plan. The native tier suites already do
this (`FuelLand`); the lane makes it a protocol field.

**Victim life substitution is published, not hidden.** The engine re-derives
starting life during game start, so a recorded 0 becomes the recorded starting
life at placement and the recorded value is reachable only by real damage. The
substitution (`P2: recorded 0 → placed 40`) is part of the elimination plan
payload.

**Mana is matched as a set, not a position.** The engine offers its untapped
fuel in its own order and never re-offers a tapped land. Matching one specific
mountain fails as soon as the engine offers another first; matching the
declared set consumes fuel exactly once each. Found by a failing probe run,
fixed in both the probe and the JUnit pilot.

**Resolution is detected by life drop, not by counting passes.** After each
bolt the pilot polls the engine's own life totals (a pure query while parked)
and stops at the first observed drop. The pilot therefore never passes with an
empty stack: combat never starts, cleanup never discards the remaining
ammunition, and all fourteen casts happen in precombat main. A fixed pass count
advanced the game into combat and then into a cleanup discard that would have
destroyed the ammunition — diagnosed, not papered over.

**The CMD-ZONE choice absence is measured, not fixed.** The in-repo
characterization (setup copy lacks commander status; the ledger lives on the
authoritative identity) reproduces exactly on the production lane: Doom Blade
genuinely on the stack, resolves, game reaches cleanup, zero choice classes in
the trace. The row is `CAUSAL_ROUTE_MEASURED_BLOCKED` with the trace in the
receipt — a measured BLOCKED, not a pass.

**Numerics discipline from #304 still holds.** No change needed; the causal
decisions use the same option/select shapes.

## 4. Evidence

| Evidence | Command | Result |
|---|---|---|
| Native causal suite | `mvn -o -Dtest=XmageMidgameCausalTest test` | 10 run, 0 failures — `PASS` |
| Full native regression | `mvn -o test` | **439 run, 0 failures, 0 errors, 1 skipped** — `PASS` |
| Protocol-2 probe | `python scripts/run_midgame_capability_probe.py --out qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json` | 17 rows probed |
| Python unit | `pytest tests/qualification/test_current_boundary_midgame_lane.py -q` | 17 passed — `PASS` |
| Lint/types | `ruff check`, `ruff format --check`, `mypy --strict` | `PASS` |

Probe partition (17 rows, `engine_commit=b1959698…`):

| Outcome | Rows |
|---|---|
| `ENGINE_NATIVE_REACHABLE` (8) | `WS05-MP-COMBAT-4`, `WS05-MP-COMBAT-5`, `WS05-CMD-ELIM-4`, `WS05-CMD-DMG-SPLIT`, `WS05-CMD-PARTNER-ZONE`, `WS05-CMD-TAX-2`, `MICRO_COMBAT`, `CARD_02` |
| `CAUSAL_ROUTE_REACHABLE` (4) | `WS05-MP-PRIO-3`, `WS05-MP-PRIO-5`, `MICRO_ZONE_CHANGES`, `WS05-MP-ELIM-PRIO-3` |
| `ENGINE_STATE_ACCEPTED` (3) | `WS05-MP-BLOCK-4`, `WS05-MP-TURN-5`, `MICRO_REPLACEMENT` |
| `CAUSAL_ROUTE_MEASURED_BLOCKED` (1) | `WS05-CMD-ZONE-GY-YES` (duality trace in receipt) |
| `ENGINE_REJECTED` (1) | `WS05-CMD-DMG-CONTROL` (`UNSUPPORTED_CONTROL_DIVERGENCE`) |
| `CONSTRUCTION_MISMATCH` | 0 |

Actual-card proofs: `Lightning Bolt` ×14 dealing 42 through engine SBAs to
eliminate P2 (`life 40 → -2`, survivors `{P1, P3}`); `Doom Blade` genuinely
resolving on a `Rograkh, Son of Rohgahh` copy; `Lightning Bolt` resolving to
graveyard as a new object incarnation.

`EXTERNALLY_RULE_VALIDATED` remains unclaimed for every row.

## 5. What is still out of scope (unchanged)

PB-09, PB-06, PB-08, CAP-08 RNG remediation, CAP-11 replay, Forge surfaces,
provider selection, Architecture Freeze, merging #304. The current-boundary
denominator still reads its own values; nothing was promoted and no runner was
wired.

## 6. Worktree-integrity incident (2026-09-29, during this session)

During final pre-commit verification, three files showed uncommitted
modifications authored by an unknown writer, present in this worktree but in no
branch, no commit and no stash:

- `engine-bridge/.../XmageNativeStateRestoration.java` (+19: `COLORLESS_BASIC_LAND
  = "Wastes"` colorless-commander filler)
- `engine-bridge/.../XmageMidgameJsonlBridge.java` (+135: principal-scoped
  `observation` redaction replacing raw `readback` in `completeMidgameArrival`,
  plus colorless-guard removal)
- `engine-bridge/.../XmageMidgameLaneTest.java` (+4: `readback` → `observation`)

Preserved as evidence (not committed) at `/tmp/opencode/foreign_changes/`
(278 diff lines across three files). The content is coherent
(colorless-commander support + hidden-info redaction in the arrival response)
and matches no open-PR file set reviewed; authorship and intent are UNKNOWN.

Disposition, per the ownership and provenance gates:

1. All three files were reverted to HEAD (`1b772706`) before commit. In
   particular `XmageNativeStateRestoration.java` is owned by other active
   workstreams and could never have carried an unattributed change from this
   session.
2. This session's own new code had been written against the worktree's
   `observation` shape (read during investigation after the foreign change
   landed). It was ported back to HEAD's `readback` API — a key rename only,
   no logic change — and re-verified to green (JUnit 35/35, probe partition
   identical at 8/9/10/2/0).
3. This session's consumption reads only turn/phase/step/active, seat ids and
   life totals from the arrival response — never hand identities — so no
   hidden-information handling in this workstream depends on the reverted
   redaction.
4. Observation for the lane owners: HEAD's `complete_midgame_arrival` returns
   the raw engine readback including opponent hand identities. Whether that is
   an accepted design or a leak awaiting the redaction above is not this
   workstream's call; it is recorded here so the hidden-information owners
   (#289, PB-06) can adjudicate with the foreign diff as input if its author
   steps forward.

No evidence was destroyed: the foreign diffs are preserved verbatim outside
the repository, and nothing from them was copied, adapted or committed.

## 7. Terminal hardening successor (single-writer campaign, 2026-09-29)

Three-way adjudication of the terminal-hardening lineage, then a successor
branch based on the parallel session's increment 2.

- merge-base: `dafe2ac6` (causal completion).
- remote-only delta: `08d23aa4` (reviewed six-finding remediation + WS17 seal).
- parallel-session delta: `1b69c31f` (hardening increment 2: mismatch
  redaction, causal credit gate, arrival rejection, two-colorless regression)
  plus handover docs `1098f365`, `e31f4936`. This is the successor base.
- superseded local delta (`f1613146`): its redactor-based observation design,
  probe/Python changes and blanket-withhold mismatch sanitizer were
  **SUPERSEDED** by the reviewed remediation and increment 2 and were not
  re-created. Two hunks were **UNIQUE_AND_REQUIRED** and are carried here.

### 7.1 Decision frames removed from verification payloads (recorded vector closed)

Increment 2 recorded an open leak vector: `complete_midgame_arrival` and
`complete_causal_reconstruction` embedded `pending_decision` unconditionally,
and a pending decision's `legal_options` labels can name the acting
principal's own hand cards. Both embeds are removed. These payloads are now
pure observations; the only decision channel is `get_midgame_decision`,
addressed to the acting principal. `XmageMidgamePrivacyTest` proves the
absence and that the decision channel still serves decisions.

### 7.2 Opaque native ids removed from hidden-hand diagnostics

Increment 2's `redactMismatch` removes the card identity from
`hand subset <owner>|HAND|<card>…` for every principal except the owner, but
left `hand injected object missing: <owner> native_id=<uuid>` untouched.
`redactNativeIds` replaces that per-game card handle with the same
`<hand-identity-redacted>` placeholder for every requester; the owner seat and
the diagnostic fact survive. Direct controls live in `XmageMidgamePrivacyTest`.

### 7.3 Adversarial honeycard control is provable, and proven

Increment 2 recorded that an end-to-end honeycard control "is not provable
with the current frozen corpus" and treated it as an authorization question.
That conclusion is **falsified**. The lane accepts a caller-supplied requested
starting state and `zone: hand` is a supported placement dimension, so a test
can add hidden hand objects to any placement-supported record without
modifying the frozen corpus. `XmageMidgamePrivacyTest` plants Runeclaw Bear,
Serra Angel and Sol Ring in P2/P3/P4 hands on the `WS05-CMD-DMG-SPLIT` record
and scans whole response lines across unbound arrival, principal-scoped
arrival (native-id and requested-state-label bindings), `get_midgame_state`,
causal verification and error payloads, and the pending P1 decision. No
honeycard name appears, and only the requesting principal's seat carries a
hand array. No fixture authorization is required because the corpus is not
touched.

### 7.4 Validation completed by the successor

Increment 2 explicitly left the full 29-row probe re-derivation and the
complete engine-bridge and repository suites outstanding. The successor
re-derived the partition at successor content with the causal credit gate and
arrival-rejection classification active; results are in
`HANDOFF_PB03_304_TERMINAL_HARDENING_20260929.md` and the final handoff.
