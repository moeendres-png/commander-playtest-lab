# Implementation Decision — WS-CSN-CAPABILITY-DELTA-20260929

## 1. The selected cluster

**Production-reachable mid-game starting-state materialisation, plus the
per-dimension capability manifest consumer, on a new Protocol-2 `midgame` lane
that composes the engine seam the Lab already owns.**

Classification: `ENGINE_NATIVE_REUSE` (the Rules semantics) with
`EXTRACT_AND_GENERALIZE` for the manifest consumer. Not a port, not a new
implementation.

Delivered as:

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageMidgameJsonlBridge.java` (new)
- `engine-bridge/src/main/java/org/commanderlab/xmage/Main.java` (one added `midgame` lane branch)
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageMidgameLaneTest.java` (new)
- `src/commander_lab/qualification/current_boundary/midgame_lane.py` (new)
- `scripts/run_midgame_capability_probe.py` (new)
- `tests/qualification/test_current_boundary_midgame_lane.py` (new)
- `qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json` (new, runtime receipt)

## 2. Why this cluster outranked every alternative

The selection was made on the project's own reuse-first order, not on novelty.

**Step 1 — does the pinned Rules Core already implement it?** Yes. The Lab's own
bridge contains `XmageNativeStateRestoration`, which materialises an explicit
requested starting state through XMage public APIs, revalidates it with
engine-authoritative SBAs plus layers, and proves it with a strict native readback
compared field-by-field with SHA-256 digests. It was constructed from exactly one
production site, always with a `null` restoration.

**Step 2 — is there a qualified API we simply are not using?** Yes, and the
project had already written it down:
`docs/pre_freeze_completion_20260927/PB03_ROOT_CAUSE_AND_REMEDIATION.md` states
that the bridge publishes a machine-readable per-dimension manifest and that
"**Nothing consumes that manifest at the qualification boundary.**"
`dimensionsPayload()` had exactly one caller: a test.

**Step 3 — is the behaviour reachable through another native operation or game
type?** XMage's `CommanderDuel` / `CommanderFreeForAll` game types were already
used (CR 103.8a, merged in #294). They do not solve mid-game placement.

**Step 4 — does current upstream implement it?** Yes, and upstream has the same
route gap: `Mage/src/main/java/mage/game/Game.cheat(...)` and
`GameOptions {stopOnTurn, stopAtStep, skipInitShuffling, globalEmblemCards}` are
main-source production classes whose only verified upstream caller is
`CardTestPlayerAPIImpl` under `Mage.Tests`.

**Step 5 — did historical project code implement it?** Yes: the residual
closure campaign (L1-L7), RG-01/02/03/04/05/06A and the PB-03 tier suites all
built and runtime-proved it. `XmagePb03Tier1RowsTest` (12 methods),
`XmagePb03Tier2StackTest` (8), `XmagePb03Tier2CmdZoneTest` (10),
`XmagePb03Tier2ControlTurnTest` (2) and `XmageFull107ResidualRequalificationTest`
(3) map 1:1 onto the blocked fixture families.

**Step 6 — is there a valid implementation in our own history?** Yes, and it is
still on `main`. Nothing needs to be resurrected from an abandoned branch.

**Step 7 — does another engine contain a transferable generic mechanism?**
phase.rs ships a production `pub mod scenario` builder with `at_phase`,
`with_commander`, seeded construction and a `build() -> GameRunner` handle, and
its `apnap_order` is the right turn-order primitive. **Neither was used.** Both
are a different engine; taking their semantics would create a second Rules
engine, which `AGENTS.md` §2 forbids. Classification `REFERENCE_ONLY`.

**Step 8 — can a safe wrapper expose existing engine behaviour?** Yes. That is
exactly what was built. A new lane was chosen over editing an existing one so
that the change touches **no file owned by an open PR**.

**Step 9 — only then, new implementation?** Not required. Zero lines of new
Rules semantics were written.

## 3. Pareto ranking of the alternatives considered

| Candidate | Leverage | Native reuse | Licence risk | Ownership collision | Verdict |
|---|---|---|---|---|---|
| **Mid-game starting state + dimension manifest** (selected) | **one mechanism → 44 BLOCKED + 15 UNKNOWN of 107 rows** | total | none (own MIT-pinned engine) | none | **SELECTED** |
| Wire the causal stack reconstruction onto a lane | 8 zone rows + stack-response rows | total | none | would need `XmageFullGameSession.java` (PR #284) | next dispatch, after #284 |
| Per-scenario hidden-information channels (PB-06) | 20 rows | total | none | `hidden_obligations.py` is owned by #289 | blocked by ownership |
| Clean-process replay twin (PB-08) | 5 rows, but gates on RNG | none (no engine replay export) | medium | owned by #289 | blocked by ownership + CAP-08 |
| PB-09 pristine Forge identity | gates the whole comparison | n/a | GPL-3.0 | **PR #299 open, Coordinator-owned** | explicitly refused |
| Forge `PlayerController` parity port | high but no XMage relevance | would be a port | **GPL-3.0 into a proprietary project** | Forge lane | refused on licence |
| phase.rs scenario/commander semantics | high on paper | would be a port | permissive but wrong-engine | n/a | refused on Rules authority |
| `prepareControllableProxy` / turn-stealing | not in the 107-row denominator | total | none | none | separate write lane, low current value |
| Library-ordering / ring-bearer decisions | not in the denominator | total | none | none | folded into the CAP-08 dispatch |

A capability that unlocks ten blocked cases through one native abstraction
outranked every card-specific or lane-specific alternative, as the project's
prioritisation rule requires.

## 4. Design decisions and why

**A new lane rather than a new message on an existing lane.** `JsonlBridge.java`,
`XmageFullGameJsonlBridge.java`, `XmageFullGameSession.java` and
`XmageNativeStateRestoration.java` are all touched by open PRs (#300, #284, #294).
`Main.java` is not. Adding one lane branch to `Main.java` and one new bridge
class let the whole cluster land with zero overlap. This is the main reason the
cluster was deliverable today at all.

**Compose, do not edit.** The new lane constructs `XmageFullGameSession` with a
non-null restoration through the existing package-private constructor, and
reuses the existing `XmageFullGameDecisionController`, `XmageFullGamePlayer`,
`XmageFullGameStateRedactor` and `XmageFullGameActionProjection` unchanged. It
adds no Rules logic of its own.

**The coarse global bit stays `false`.** Flipping
`starting_state_injection_supported` to `true` would have been simpler and
would have "unblocked" the rows in one edit. It would also be false: the bit
describes a *globally complete* injection of arbitrary states, which nothing
here provides — stack placements, control divergence, tapped permanents,
counters and attachments are all still rejected with codes. The lane instead
publishes `starting_state_dimensions_supported = true` plus the manifest, and
its own lane block states
`global_starting_state_injection_claimed = false`. The rows were made reachable
by actually reaching them, not by relabelling.

**Arrival is a transport, and this workstream made that structural.**
`complete_midgame_arrival` performs only engine-side work: commander cast-count
restore, `revalidate` (applyEffects + checkStateAndTriggered), native readback
and the field-level compare. It answers no decision. The first implementation
risk was an internal arrival loop that answered mulligans and passes on the
pilot's behalf; that was rejected as a forbidden default and the design was
changed so **every** decision, including the mulligan, the choosing-player pick
and every priority pass, is submitted by the external caller over the same
protocol. While the engine is parked, `complete_midgame_arrival` is a pure query,
so the driver can poll the engine's live readback to find the record's
checkpoint without spending a decision.

**Commander colours from the engine, not a Lab table.** The native tests carry a
four-entry `COMMANDER_COLORS` map. A production surface must not depend on a
test table, so `XmageMidgameJsonlBridge.engineCommanderColors` reads
`CardRepository.instance.findCard(name, true).getColor()` after
`XmageDeckImporter.ensureRepositoryReady()`. This is strictly more correct: it
tracks the real card's mana colours for any commander, not the four names a
historical test happened to need. (Found and fixed by the first runtime run.)

**The declaration-step priority allowance is reported, not hidden.** During a
declaration step the engine does not hold priority the way the readback reports
it, so `priority_player` may read as the next seat. The project's own native
suite already documents this and tolerates exactly that field. The consumer
applies the allowance, but the receipt carries **both** the engine's raw
`engine_construction_match` bit and the explicit
`declaration_step_priority_allowance_applied` list, so a reviewer sees the raw
engine verdict and the classification side by side. Any mismatch outside that one
field prefix is a `CONSTRUCTION_MISMATCH`.

**Fail-closed is the default posture.** A new `midgame` lane that quietly
inferred a starting state would be a rules engine. `create_midgame_game` without
`requested_starting_state` returns `missing_requested_starting_state`;
`create_midgame_game` without `seed` returns `seed_required`; an unsupported
dimension returns `midgame_starting_state_rejected` with the engine's own code;
an unknown message returns `unsupported_message`; a decision before creation
fails with `MIDGAME_NOT_CREATED`. All five are asserted as tests.

**Numerics are sent only when the frame authorises them.** The engine rejects
`numeric_choices` on a frame whose `context` has no `numeric_legs` as schema
confusion. The Python client therefore omits both numeric fields unless the
pending frame's own context authorises them. (Found and fixed by the first
end-to-end probe run; the engine's rejection was correct and the client was
wrong.)

**`ENGINE_STATE_ACCEPTED` as its own outcome.** Three rows have their starting
state materialised but their own scripted obligation unexecuted by the probe.
Reporting those as "rejected" would misattribute an engine acceptance as an
engine refusal; reporting them as reachable would inflate the count. They get a
third outcome with `engine_accepted_starting_state: true`.

## 5. What was explicitly not done, and why

- **PB-09.** Forge identity is open and Coordinator-owned; PR #299 is live.
  Nothing in this workstream reads, re-attributes or repairs Forge evidence.
- **`game_driver.py` / `full107.py` / `bridge_launcher.py`.** Owned by #300,
  #289 and #299. The new lane is deliberately not wired into the current
  boundary yet; that wiring is a separate, smaller dispatch once ownership frees.
- **No promotion of any qualification row.** This workstream proves a
  *capability*. It does not re-run the 107-row denominator, does not change any
  `PASS`/`BLOCKED`/`UNKNOWN`, and does not touch
  `qualification/final-current-boundary-20260927/`. The current boundary keeps
  `BLOCKED 44 / UNKNOWN 59` until its owners rerun it.
- **No `NEW_IMPLEMENTATION_REQUIRED` without a source-level reason.** Only
  CAP-08 and CAP-11 carry that classification, and each carries a concrete
  reason: XMage has no replay export and its "in any order" library branch
  bypasses the seeded RNG; neither can be satisfied by wrapping an existing
  qualified API.
- **No engine fork, no branch on the engine, no PR to XMage or Forge.** One
  dispatch packet is issued instead (see `EXTERNAL_PROVENANCE_LEDGER.md` §8).

## 6. Evidence produced

| Evidence | Command | Result |
|---|---|---|
| Native lane suite | `mvn -o -Dtest=XmageMidgameLaneTest -DfailIfNoTests=false test` | 10 run, 0 failures, 0 errors — `PASS` |
| Native suite regression | `mvn -o test` | 412 run, 0 failures, 0 errors, 1 skipped — `PASS` |
| Protocol-2 process probe | `python scripts/run_midgame_capability_probe.py --out qualification/midgame-lane-20260929/MIDGAME_CAPABILITY_PROBE.json` | 16 rows; 8 `ENGINE_NATIVE_REACHABLE`, 3 `ENGINE_STATE_ACCEPTED`, 1 `CONSTRUCTION_MISMATCH`, 4 `ENGINE_REJECTED`; `engine_commit=b1959698…` |
| Python unit | `pytest tests/qualification/test_current_boundary_midgame_lane.py -q` | 14 passed — `PASS` |
| Lint | `ruff check`, `ruff format --check` | `PASS` |
| Types | `mypy --strict --python-version 3.12 src/commander_lab/qualification/current_boundary/midgame_lane.py` | `Success: no issues found` |

Actual-card evidence: `WS05-MP-COMBAT-4` drives a **four-player Commander**
mid-game state containing real `Grizzly Bears` and `Rograkh, Son of Rohgahh`, and
declares two obligate 2/2 attacks against two different opponents purely by
selecting the engine's own offered option labels, then proves the construction
against the frozen record's own spec digest
`8496df0e4d29b868872b947e095e890d8f61e17bd6ea82317238660334e85f64`.

`EXTERNALLY_RULE_VALIDATED` is **not** claimed for any row: no row was
adjudicated against the current official Comprehensive Rules text or Oracle text
in this workstream.
