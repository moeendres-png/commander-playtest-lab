# E-B0 + E-B1: AF05 Forge matrix corrections (#561)

Lab-only batch. It corrects gap labels in the Forge AF05 hidden-information matrix
(`docs/forge_af05_hidden_20261003/FORGE_AF05_MATRIX.json`). It executes no row, writes no
receipt and moves no verdict. All 20 rows stay `PROVIDER_ADAPTER_GAP`, and Forge AF05 stays
`UNKNOWN`. `PRODUCTION_PROVIDER = NOT_SELECTED`. `ARCHITECTURE_FREEZE = NOT_CLAIMED`.

## Definitions used

The most specific definitions are in capability-E report part 1, §3 (the E-B0…E-B8 plan).
That part was never posted as an issue comment. It survives only in the log of the bunny
run that produced memo 6004666781 (Actions run 37381666718, job 112004916280):

| Batch | Definition (part 1 §3) |
|---|---|
| **E-B0** | Retain the bridge's stderr in `BridgeProcess.close`. Update `LAB_CAPTURE_ASSERTIONS` and the gap text in the same commit. Closes the `transport_diagnostics` Lab capture gap on 20/20 rows. |
| **E-B1** | Move `action_cost_state` to the Lab bucket so that `forge_hidden_information` agrees with `forge_residuals`. Add the name→semantic-id map with an exactly-one rule for exile, and retire the `zone:exile` UNOBSERVABLE finding. |

Memo 6004666781 says E-B0 + E-B1 + E-B2 "together correct 56 gap entries". E-B2
(`face_down` in `ScenarioBootstrap`) is out of scope here. See "Definition conflicts" below.

## Entries changed

Baseline: committed matrix, re-run with `scripts/run_forge_hidden_census.py` at
`b236008` and found byte-identical. Every row has 20 entries in each list below unless noted.

| # | Entry | Before | After | Rows | Why |
|---|---|---|---|---|---|
| E-B0 | `lab_capture.transport_diagnostics` | `lab_execution_gaps` | removed | 20 (all) | `BridgeProcess` now drains stderr on a daemon thread into a retained in-memory capture, from launch to EOF. The gap text ("BridgeProcess.close discards it") is no longer true. The channel itself stays `PRESENT_UNAUDITED`: retention is not an audit, and the row's scan still has to run. |
| E-B1a | `action_cost_state` | `provider_construction_gaps`, channel `cost_state_construction` | `lab_execution_gaps` (`basis: LAB_EXECUTION_GAP`) | 14 (`HIDDEN_05`…`HIDDEN_18`) | Mid-cast cost state is caused by casting and paying on the engine's own frames. No engine fills it from a bootstrap field (XMage uses a live decision class). `forge_residuals._CONSTRUCTION["action_cost_state"]` already files it as `LAB_EXECUTION_GAP`, and a test now holds the two modules in agreement. |
| E-B1b | `semantic_objects.zone:exile` | `unobservable_checkpoint_dimensions` | `provider_construction_gaps`, new channel `exile_construction` | 20 (all) | The bootstrap cannot place a card in exile. It reads no exile field, and the lane only builds battlefield, hand and command-zone placements, so the first missing mechanism is construction, not readback. The readback does name every face-up exiled card to every principal (`StateProjection.exileZone` → `shownName`, CR 406.3), which a new `exile_name_readback` channel asserts. A Lab exactly-one binder (`bind_exile_identities`) maps those names to semantic ids. The UNOBSERVABLE finding is retired only when every requested exile object would bind exactly once. Otherwise it is kept beside the construction gap. |

`semantic_objects.zone:library` (UNOBSERVABLE, 20 rows) is unchanged. A library is never
projected (`library_contents` ABSENT).

### Before/after counts per gap class (all 20 rows)

| Gap class / entry | Before | After |
|---|---|---|
| provider: `semantic_objects.face_down` (`face_down_construction`) | 20 | 20 |
| provider: `temporal_checkpoint.exact_hand_after_draw` (`library_construction`) | 20 | 20 |
| provider: `knowledge_state` (`knowledge_construction`) | 12 | 12 |
| provider: `action_cost_state` (`cost_state_construction`) | 14 | **0** |
| provider: `semantic_objects.zone:exile` (`exile_construction`) | 0 | **20** |
| **provider total** | 66 | 72 |
| lab: `decision_execution.*` | 39 | 39 |
| lab: `lab_capture.transport_diagnostics` | 20 | **0** |
| lab: `action_cost_state` | 0 | **14** |
| **lab total** | 59 | 53 |
| unobservable: `semantic_objects.zone:library` | 20 | 20 |
| unobservable: `semantic_objects.zone:exile` | 20 | **0** |
| **unobservable total** | 40 | 20 |
| missing principal channels (event_log 20, replay 20, library_contents 4, reveal_look ×2) | 48 | 48 |
| unaudited principal channels (decision_frames, message_surface, transport_diagnostics) | 60 | 60 |
| classifications | 20 `PROVIDER_ADAPTER_GAP` | 20 `PROVIDER_ADAPTER_GAP` |
| AF05 Forge / pass | `UNKNOWN` / 0 | `UNKNOWN` / 0 |

Corrected entries: 20 (E-B0) + 14 (E-B1a) + 20 (E-B1b) = **54**. Nothing became PASS, no
classification changed, and no channel moved to `SUPPORTED` on a principal surface.
`exile_name_readback` is a new SUPPORTED fact about the projection. No obligation requires
it, so it satisfies no row, and the binder is used only to decide the label.

## Channel table changes

- `exile_construction`: ABSENT, bootstrap. Absent tokens `ZoneType.Exile` and `"exile`,
  plus the closed `BOOTSTRAP_FIELDS` set. If a bootstrap gains an exile field, that is drift.
- `exile_name_readback`: SUPPORTED, projection. It asserts that the zone is wired in
  `zones.add("exile", … exileZone(player, observerView))` and that `exileZone` writes only
  `shownName(card, observerView)` per card. A raw `card.getName()` would be drift.
- `cost_state_construction` stays as an asserted fact, because the bootstrap still has no
  cost field. Its meaning now says no row files a gap against it.
- `transport_diagnostics` meaning: the Lab now retains stderr. The scan is still not run.

## Lab capture ratchet (E-B0)

`LAB_CAPTURE_GAPS` is empty. `LAB_CAPTURE_RETAINED["transport_diagnostics"]` states the
retention. `LAB_CAPTURE_ASSERTIONS` now binds that claim to the launcher code: the stderr
pipe, the drain thread, the bounded append and the EOF flag must be present, and there must
be no direct `.stderr.read` racing the drain. A channel must be in exactly one of
GAPS or RETAINED. A launcher that stops retaining stderr raises `HiddenChannelDrift`. It
cannot silently keep the gap closed.

Capture contract (`BridgeProcess.stderr_capture()`):
- `complete` is true only after the drain reached EOF;
- `truncated` is true when the retention cap was exceeded;
- `scannable` is `complete and not truncated`. A scan over an unscannable capture must
  fail closed (UNKNOWN), never PASS.

Privacy: the capture is held in memory on the process object. It never enters
`transcript`, which is persisted, and nothing in this batch writes it to evidence. Before
this change the stderr pipe was never drained, so a chatty child could fill the pipe and
stall. Draining removes that stall, and a test covers it.

## Red/green evidence

The tests were written first and run against the unchanged source (`b236008`). Command:
`pytest tests/qualification/test_forge_eb0_eb1_reclassification.py
tests/qualification/test_forge_hidden_information.py`.

- **Red, before the source change:** 30 failed, 73 passed.
  - 24 failures are new tests in `test_forge_eb0_eb1_reclassification.py`: every
    `stderr_capture` test, the retained-not-gap test, launcher-drift edits 0/3/4, the
    both-listed guard, cost-state as a Lab gap, the module-agreement test, all binder
    tests, exile as a construction gap, unbindable exile and the exile-channel binding.
  - 6 failures are updated tests in `test_forge_hidden_information.py`: construction gaps,
    the universal surface, cost-state on the engine frames, two new exile capability-drift
    cases, and stderr retained but unaudited.
  - `test_a_chatty_child_does_not_stall_on_an_undrained_pipe` failed with
    `BridgeTimeout ... no response to handshake within 15.0s`. This confirms the latent
    stall: an undrained stderr pipe blocks a child that writes more than 64 KiB.
- **Green, after the change and the census re-run:** the same two files, plus
  `test_current_boundary_bridge_deadline.py` and `test_forge_residuals.py`, gave
  138 passed. `test_the_committed_matrix_is_current` passes against the regenerated matrix.
  A second census run is byte-identical to the committed matrix.

Tests that pinned the old labels were changed in the same commit. Each change is a
reclassification named above, not a weakening:
- `test_cost_state_follows_the_lane_construction_finding` became
  `test_cost_state_is_caused_on_the_engine_frames`;
- `test_stderr_is_a_lab_capture_gap_until_the_lab_retains_it` became
  `test_stderr_is_retained_but_the_scan_is_still_unaudited`;
- the lab-capture assertion in `test_every_row_needs_the_universal_principal_surface`
  is inverted;
- `test_construction_gaps_are_the_lane_model_findings` now also requires
  `exile_construction`.

## Mutation-kill evidence

Each mutant was applied by hand to a copy of the source and run against its named test,
and the source was then restored. The driver script is in the session scratchpad and is
not committed. 23/23 mutants were killed.

| Mutant | Change | Killed by |
|---|---|---|
| M1 | `LAB_CAPTURE_GAPS` non-empty again | `test_transport_diagnostics_is_retained_not_a_lab_gap` |
| M2 | the drain thread is never started | `test_the_launcher_retains_the_whole_stderr_stream` |
| M3 | over-cap lines are dropped without setting `truncated` | `test_an_over_limit_capture_is_marked_truncated_and_unscannable` |
| M4 | the cap is ignored (append past the limit) | `test_an_over_limit_capture_is_marked_truncated_and_unscannable` |
| M5 | `scannable` ignores `truncated` | `test_an_over_limit_capture_is_marked_truncated_and_unscannable` |
| M6 | `complete` starts true (a live capture looks complete) | `test_a_live_capture_is_incomplete_and_unscannable` |
| M7 | stderr copied into the persisted transcript | `test_stderr_never_enters_the_persisted_transcript` |
| M8 | ratchet drops the "no direct `.stderr.read`" fragment | `test_a_launcher_that_stops_retaining_stderr_is_drift` |
| M9 | gap-and-retained overlap no longer raises | `test_a_channel_cannot_be_both_gap_and_retained` |
| M10 | `_LAB_DIMENSIONS` empty (cost state unmapped) | `test_cost_state_is_a_lab_execution_gap` |
| M11 | cost state back in `_PROVIDER_DIMENSIONS` | `test_both_modules_file_cost_state_the_same_way` |
| M12 | Lab entry basis says `PROVIDER_ADAPTER_GAP` | `test_cost_state_is_a_lab_execution_gap` |
| M13 | requested-name count `== 1` → `>= 1` | `test_the_binder_refuses_anything_but_exactly_one` (two requested, one readback case) |
| M14 | readback count `== 1` → `>= 1` | `test_the_binder_refuses_anything_but_exactly_one` |
| M15 | face-down objects may bind | `test_the_binder_refuses_anything_but_exactly_one` |
| M16 | redaction placeholders may bind | `test_the_binder_refuses_anything_but_exactly_one` |
| M17 | readback matched across all owners | `test_the_binder_refuses_anything_but_exactly_one` |
| M18 | exile finding dropped instead of moved | `test_public_exile_is_a_construction_gap_not_a_readback_limit` |
| M19 | UNOBSERVABLE always retired, even unbound | `test_an_unbindable_exile_keeps_the_unobservable_finding` |
| M20 | UNOBSERVABLE never retired | `test_public_exile_is_a_construction_gap_not_a_readback_limit` |
| M21 | "all bound" weakened to "any bound" | `test_an_unbindable_exile_keeps_the_unobservable_finding` |
| M22 | `exile_construction` loses its absent tokens | `test_a_new_capability_is_drift` |
| M23 | `exile_name_readback` loses its absent token | `test_a_new_capability_is_drift` |

On the first pass M13 survived, because no binder case had two requested objects with
only one readback card. That case was added. The final table comes from one fresh run of
all 23 mutants, with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared. Restoring a
source file with an equal size and mtime second can otherwise leave a stale mutant `.pyc`
in place. The named tests also pass on the unmutated source in that run (107 passed). On its first form, M7
was killed but stalled pytest's assertion diff over megabytes of stderr. The test now
compares booleans.

## Definition conflicts and open questions

1. **Coordinator record 6005365186 relabels E-B0…E-B2** as "the event-tape skeleton
   under G4-P/G4-C1..C3". It also says the main writer claimed them (6007555350). That
   conflicts with part 1 §3 (stderr capture and reclassification) and with plan table
   6004286215 ("E-B0 + E-B5: stderr capture and `action_cost_state` reclassification").
   The record does not define what the batches contain, and this session's brief puts the
   G4-P tape out of scope, so this batch follows part 1 §3. If the Coordinator meant the
   tape, this work is the Lab-only labelling pass that every later tape batch's reason
   text is computed against, and the tape still needs its own batch.
2. **Numbering drift.** In 6004035468/6004286215, "B5" means the `action_cost_state`
   reclassification. In part 1, the reclassification is E-B1 and E-B5 is the bridge
   cost-context batch. This batch uses part 1's numbering.
3. **"56 gap entries" is 54.** Part 1 counts `cost_state_construction` as 16/20
   ("05–18"), but HIDDEN_05…HIDDEN_18 is 14 rows, and the matrix has 14. 20 + 14 + 20 = 54.
   (Part 1's `knowledge_construction` count of 10 is also 12 in the matrix.)
4. **Exile.** Part 1 says to add the binder and "retire `zone:exile` UNOBSERVABLE". Doing
   only that would drop a real gap: the bootstrap cannot place a card in exile. So the
   entry becomes a provider construction gap. The binder decides only whether the
   readback half is a limit. It is not wired into any verdict path, because no row can
   construct an exile object.
5. **Still disagreeing, out of scope:**
   - `temporal_checkpoint.exact_hand_after_draw` is `library_construction`, a provider
     gap, here, but `LAB_EXECUTION_GAP` in `forge_residuals`. This depends on G2.
   - `forge_residuals._UNOBSERVABLE["semantic_objects.zone:exile"]` still says
     "names only, with no identity". No residual-scope row has an exile object.
   - The graveyard has the same name-only readback as exile, and it was not touched.
6. **D2 interaction.** If batch D2 makes `action_cost_state` CAUSED in the lane, it leaves
   `hard_unsupported`, and the Lab entry here disappears on its own.
