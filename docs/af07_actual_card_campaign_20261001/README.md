# AF07 actual-card campaign — Phase 1 current-boundary producer and 29-row matrix

Workstream: `AF07-ACTUAL-CARD-CAMPAIGN-20261001` (GitHub #453, parent #255).
Concurrency authority: #255 comment 5936731960.
`PRODUCTION_PROVIDER = NOT_SELECTED`, `ARCHITECTURE_FREEZE = NOT_CLAIMED`.

## What this is

A reusable, candidate-neutral producer for the frozen 29-card actual-card corpus at
the current qualification boundary. It derives the corpus and every obligation from
frozen source, executes each identity on the production midgame lane with
engine-authored decisions only, and classifies every identity that does not pass
with exactly one blocker class, surface and owner.

Phase 1 adds only dedicated AF07 surfaces. Shared qualification surfaces
(`midgame_rows.py`, `run_midgame_capability_probe.py`, the successor contract,
`knowledge_projection.py`, `source_lock.py`, the current-boundary runner/assembler
and the global SHA manifests) were read, never edited, while another writer was
active on them.

## Source lock

| Identity | Value |
|---|---|
| Lab `main` | `6ae06efcdd2a894596d4c48d14b32632a6950c60` (tree `366a73100045a8ada93dfacf53c428968305a13a`), after #452 and #460 merged |
| Effective contract | `commander-lab.full107/1.0.10-successor` |
| XMage candidate | `37e4df6c914f1e189e24f0ef59fa91734c922436` |
| Loaded engine artifact | `mage-1.4.61.jar`, sha256 `e04062d2e180c8e322256bd92675c5cd49d73f5f6894140e5a86e45764661603` (provider-reported) |
| Forge Rules-Core | `bb0a740d2bef725194798383c2452213ecdd0b37` |
| Forge bridge | `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` |
| Runner identity | commit `0b61ab80a30638a4fda229d5be77a56c302017af`, clean tree; digest in `artifacts/CAMPAIGN_IDENTITY.json` |
| Output matrix digest | `3bbc18ce455812309ff6e0d15dcda195a392af305db7938550c4ab086987300e` |

Impact note: #452/#460 changed HIDDEN fixtures and the bridge event watcher, not
the CARD records. The effective CARD-02/CARD-24 required-state and obligation
digests are byte-identical before and after the merge; the campaign was re-run on
the merged tree so the receipts bind the current runner and engine bytes.

## Derivation chain (nothing restated locally)

- **Identities** — `qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json`
  `regression_corpus_29`, in manifest order.
- **Fixture ownership** — `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json`
  (`CARD_01`…`CARD_29`). Derivation fails closed unless the fixture→identity map is a
  bijection with the frozen corpus.
- **Effective records** — `materialization.load_effective_materialization()` (the
  canonical successor-contract resolver). Every row binds the effective record's
  `requested_state_digest`, `obligation_digest`, materialization version and digest.
- **Credit route** — the effective provider denominator (107) plus the frozen
  `qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json` exclusion decision. In the
  current denominator only `CARD_02` has its own row; the other 28 CARD fixtures are
  in the frozen exclusion list, so their AF07 credit has no denominator row yet.

## Execution method

Each identity is executed as itself on a fresh production midgame-lane process in a
run-scoped runtime directory (`ENGINE_RUNTIME_DIRECTORY`), using this worktree's
`engine-bridge` build only:

1. the engine constructs the record's exact requested state and reports its own
   construction verdict and, on refusal, the mechanism it refused;
2. the generic production executor (`midgame_rows.execute_row`, read-only reuse)
   answers only from the record's own `decision_script`, engine-offered options and
   declared mana sources;
3. required-event tokens are verified against the engine's own public event tape;
4. a `DIRECT_PASS` additionally requires a campaign **obligation plan** that covers
   exactly the record's `terminal_postconditions`, with every proof held on the
   engine's own tape or observation, and the engine-reported build equal to the
   canonical pin. A plan is stale the moment the effective record's postconditions
   or required events change, and a row without a complete plan can never pass;
5. direct passes persist a runner-bound positive fixture receipt in the current
   receipt schema (`artifacts/receipts/positive/`), so Phase 2 can consume them.

## Result — 2 of 29 directly proven, 27 terminally classified

| Fixture | Identity | Verdict | Blocker class | Surface | Owner |
|---|---|---|---|---|---|
| CARD_01 | Ishai, Ojutai Dragonspeaker | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_02 | Rograkh, Son of Rohgahh | DIRECT_PASS | — | `—` | — |
| CARD_03 | Esior, Wardwing Familiar | BLOCKED | DEPENDENCY_WAITING | `src/commander_lab/qualification/current_boundary/midgame_rows.py` | PR #450 |
| CARD_04 | Kediss, Emberclaw Familiar | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_05 | Veyran, Voice of Duality | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_06 | Harmonic Prodigy | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_07 | Narset, Parter of Veils | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_08 | Jeska, Thrice Reborn | BLOCKED | DEPENDENCY_WAITING | `src/commander_lab/qualification/current_boundary/midgame_rows.py` | PR #450 |
| CARD_09 | Magma Opus | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_10 | Wash Away | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_11 | Wear // Tear | BLOCKED | DEPENDENCY_WAITING | `src/commander_lab/qualification/current_boundary/midgame_rows.py` | PR #450 |
| CARD_12 | Dig Through Time | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_13 | Flare of Duplication | BLOCKED | DEPENDENCY_WAITING | `scripts/run_midgame_capability_probe.py` | PR #450 |
| CARD_14 | Vandalblast | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_15 | Finale of Revelation | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_16 | Psychosis Crawler | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_17 | Kaervek the Merciless | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_18 | Shriekmaw | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_19 | Butcher of Malakir | BLOCKED | DEPENDENCY_WAITING | `src/commander_lab/qualification/current_boundary/midgame_rows.py` | PR #450 |
| CARD_20 | Syphon Mind | BLOCKED | DEPENDENCY_WAITING | `scripts/run_midgame_capability_probe.py` | PR #450 |
| CARD_21 | Gratuitous Violence | BLOCKED | DEPENDENCY_WAITING | `scripts/run_midgame_capability_probe.py` | PR #450 |
| CARD_22 | Bolt Bend | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_23 | Makeshift Mannequin | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_24 | Warstorm Surge | DIRECT_PASS | — | `—` | — |
| CARD_25 | Basilisk Collar | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_26 | Burn Down the House | BLOCKED | DEPENDENCY_WAITING | `qualification/pre-freeze-successor/` | PR #462 |
| CARD_27 | Path of Ancestry | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_28 | Find // Finality | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |
| CARD_29 | Boseiju Reaches Skyward // Branch of Boseiju | BLOCKED | PROVIDER_ADAPTER_DEFECT | `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java` | — |

`AF07_ACTUAL_CARD_MATRIX.json` is authoritative; the table is a derived view.

### Directly proven rows

- **CARD_02** Rograkh, Son of Rohgahh — construction `EXACT`; the engine's cast and
  resolve observed on the tape; `Rograkh is on P1 battlefield`, commander cast count
  `1`, and no mana payment. Receipt
  `artifacts/receipts/positive/CARD_02.json` (digest `e77cea9d290f726d…`).
- **CARD_24** Warstorm Surge — construction `EXACT`; `entering_creature_damage:P2:2`
  observed on the tape and P2 at 18 life on the engine's observation. Receipt
  `artifacts/receipts/positive/CARD_24.json` (digest `48ba77319c6fcf7d…`).

Both receipts are scoped to the canonical candidate identity, the current runner
digest and the effective record digests; the assembler's
`positive_fixture_credit` accepts them (proven by test) and rejects a digest drift.

### Blocker mechanisms

- **PROVIDER_ADAPTER_DEFECT (11 rows)** — the engine itself refused the requested
  starting state and named the dimension: `stack` objects (CARD_07/10/16/22),
  frozen partial `library` identity (CARD_09/12/15/27/29) and unsupported counters
  (CARD_22/25/28). The attribution binds the engine's own refusal token to a
  dimension the record actually declares and to the bridge's own published
  unsupported-dimension manifest.
- **DEPENDENCY_WAITING — successor contract (9 rows)** — the engine offered a
  discretionary decision class the effective record does not script
  (`target`, `choose_object`, `choice`). Surface
  `qualification/pre-freeze-successor/`, currently owned by PR #462.
- **DEPENDENCY_WAITING — production executor/probe (7 rows)** — scripted actions
  the generic executor cannot express (`announce_cast`, `cast_fused`, `activate`),
  a scripted declaration class it does not answer (`declare_attacker` at the wrong
  script position), a combat arrival the probe does not traverse to the record's
  checkpoint, and the two causal-entry rows (CARD_13, CARD_20) whose position the
  probe can reach causally but whose obligation driver is not integrated.

No row is `UNKNOWN`: every non-PASS row has a live engine observation or a live
decision frame that identifies its first blocker.

## Evidence semantics

- `DIRECT_PASS` — `FRESH_CURRENT_BOUNDARY_RUNTIME`, engine-observed, receipt-bound.
- `BLOCKED` — `FRESH_CURRENT_BOUNDARY_RUNTIME` for the refusal or decision-frame
  observation; the unexecuted obligation stays UNKNOWN and earns nothing.
- Native `XmageActualCardCorpusTest` evidence was **not** consulted and **not**
  promoted. Import/construction/native-green is never AF07 credit.
- No external CR/Oracle/Rulings authority was needed: every classification here is
  an execution-seam observation, not a Rules dispute. External rules evidence, when
  a future row needs it, belongs in a separate document from runtime proof.

## Files

- `src/commander_lab/qualification/current_boundary/actual_card_campaign.py` — producer.
- `scripts/run_actual_card_campaign.py` — isolated runtime runner.
- `tests/qualification/test_actual_card_campaign.py` — 32 adversarial, engine-free tests.
- `artifacts/AF07_ACTUAL_CARD_MATRIX.json` — machine-readable 29-row matrix.
- `artifacts/CAMPAIGN_IDENTITY.json` — runner/candidate/workspace identity.
- `artifacts/measurements/CARD_*.json` — per-row engine evidence.
- `artifacts/receipts/positive/CARD_{02,24}.json` — runner-bound positive receipts.

## Phase 2 (after the active midgame and AF05 writers are terminal)

Fresh-fetch `main`, impact-adjudicate the merged bytes of #450 and the live AF05
writer (#462), rebuild the foreign-owner map from live ownership, re-run every row
whose effective record or executor surface changed, consume the merged
selector/contract changes, then add the CARD rows to the current-boundary
denominator/receipt route only on the freed surfaces — without overwriting
historical epochs.

## Phase 2a: adapter and fixture closure (Claude lane, after #452/#460/#462)

#452, #460 and #462 are merged, so the successor contract has no foreign
writer any more. #450 (`midgame_rows.py`, the capability probe) was still
active while this step was built; it merged before the final run, and this
step does not edit its surfaces. This step closes everything the campaign
attributed to the Lab adapter or to lossy fixtures that does not need the #450
surfaces. It changes no executor and no provider denominator (107).

### Fixture errata (contract 1.0.12)

CARD_09, 12, 15, 27 and 29 name only the top library cards their obligation
uses and nothing else. Under SLOT-04 (#255 comment 5925956587) a partial library
request fails closed: this is the `UNSUPPORTED_ZONE: library` the campaign
measured.

`LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04` declares instead:
- the complete checkpoint library (the requested objects on top in their order,
  then the 99-Mountain template convention);
- complete checkpoint hands.

Objects, script and obligation digests are unchanged. The five rows are outside
the provider denominator, which keeps 86 unchanged rows.

### Lab adapter (engine-bridge)

Every change below is verified engine-direct and covered by
`XmageCheckpointStateRestorationTest`; the fail-before is shown locally.

- **Libraries at the checkpoint.** The lossless plan placed a requested library
  at the first arrival completion. The driver issues that completion at earlier
  priorities too, so the active player's first-turn draw took the requested top
  card (`INCOMPLETE_LIBRARY_ORDER`). Libraries are now placed once the game
  stands at the requested turn, phase and step.
- **Pinned library objects.** A requested library object that shares its
  identity with the template (a Mountain on Mountains) holds its own position.
- **Tapped state and counters** (+1/+1 and -1/-1, on requested battlefield
  permanents) are checkpoint state, because an untap step would undo a
  pre-start tap.
  - They are set silently through the game-load path at the checkpoint and
    verified as the lossless check kinds `tapped` and `counters`.
  - Other counter types, counters on commanders or off the battlefield,
    attachments and stack spells still fail closed. The dimension manifest and
    the admission tokens say exactly that.
- **Transforming double-faced cards.** A card requested as "Front // Back" is
  the engine card named after its front face. It resolves to that name only if
  the engine reports exactly that back face.
- **Regression found and fixed in the same step.** Before the checkpoint, every
  arrival response listed each requested library object as "not placed", which
  named `obj:hidden-lib-0`. The AF05 knowledge-projection run caught it as a
  demonstrated leak on all twelve HIDDEN rows. A pre-checkpoint arrival now
  reports one coded mismatch, and the twelve rows verify again.

### Campaign attribution

- A discretionary frame the effective record does not script is now a
  `FIXTURE_DEFECT` on the contract surface, not a dependency on a finished
  writer.
- Counters and tapped state are no longer listed as unsupported.
- A requested token object (`Soldier Token`) is attributed as a token the
  card-vehicle restoration cannot load.

### Result: fresh 29-row run after #450 merged (`83c32903`, clean tree, XMage `37e4df6c`)

Main was merged normally after #450 landed (multi-select targets and divided
amounts in the executor). No surface has a foreign writer any more, so every
blocker is now this campaign's own to close. Matrix digest `67bbf838d7f5bfd0c7e88bb69bcced2b34b6f327a790bf761da60954acfb090c`.

| Outcome | Rows |
|---|---|
| DIRECT_PASS (2) | CARD_02, CARD_24 |
| FIXTURE_DEFECT (10) | CARD_01, 04, 05, 06, 09, 14, 17, 18, 23, 26: the record does not script a target, object choice or choice the engine requires (CARD_09 now passes its divided-damage legs and stops at the unscripted tap targets) |
| HARNESS_DEFECT (10) | CARD_03, 08, 11, 13, 15, 19, 20, 21, 27, 28: executor priority actions (`announce_cast`, `cast_fused`, `activate`, `activate_mana`, `cast_split_half`), unscripted frames, the combat arrival, causal entries |
| PROVIDER_ADAPTER_DEFECT (5) | CARD_07, 16, 22 (stack spells); CARD_10 (commander spell on the stack); CARD_25 (token object) |
| UNKNOWN (2) | CARD_12, CARD_29: construct and execute through the whole script; their required event tokens (`delve_exile`, `look_top`, `Saga_I`, ...) are not in the executor's token vocabulary and no obligation plan covers them yet |

Six rows moved from a construction refusal to execution (CARD_09, 12, 15, 27, 28,
29). No row waits on another writer.

AF07 stays **UNKNOWN**. 27 identities are not directly proven, and the CARD rows
outside the denominator still need the Coordinator's credit route.

### Next

1. **Fixture errata.** Script the missing discretionary steps for the ten
   FIXTURE_DEFECT rows, each target chosen so that it leaves the obligation
   untouched.
2. **Executor.** Now that #450 is merged, extend the executor actions and the
   token vocabulary, add obligation plans, and re-run.
3. **Adapter.** Stack spells and tokens need a causal-entry or effect-created
   route, not a load.
4. **Coordinator.** Decide the AF07 credit route for CARD rows outside the 107-row
   denominator. Changing the denominator is a Coordinator gate.

## Phase 2b: decision-script errata, executor and plan vocabulary

### Fixture errata (contract 1.0.13)

The new class `ACTUAL_CARD_DECISION_SCRIPT_ERRATUM` applies to rows outside the
denominator, with the obligation digests unchanged. Each erratum adds, reorders
or retypes only the steps that answer a discretionary decision the Rules Core
itself asks. The probe of each row showed which decision that was.

| Row | Defect | Correction |
|---|---|---|
| CARD_01 | The Bolt's target was unscripted. | P2 targets P3. Targeting Ishai would kill the observed permanent. |
| CARD_04 | Bruse Tarl's own attack trigger was unscripted. The record also had a P2 block step the engine never offers, because P2 has no creature. | The trigger targets Kediss, which does not attack. Targeting Bruse Tarl would give double strike and change the obligated 3 damage. The block step is dropped. |
| CARD_05 | The Bolt target and the order of two identical magecraft instances were unscripted. | Target P2. The order step lists the ability once per instance. |
| CARD_09 | "Tap two target permanents" was scripted as an untargeted object set. | It is now scripted as the targeted multi-select it is (CR 601.2c). The 1.0.12 lossless-library overlay is carried inside the erratum. |
| CARD_18 | The trigger order is asked before the destroy target (CR 603.3b/d). The abilities were named by free text. | The steps follow the engine's order. Each trigger is named by its source plus a fragment of its rules text. The stack order is unchanged. |
| CARD_23 | Targets were folded into the cast actions, and the Bolt could be cast while Mannequin was still on the stack. | Explicit target steps. The Bolt carries `timing: empty_stack`. |
| CARD_26 | The note says P1 casts Burn Down the House, but the script held only the mode, and no payment was declared. | Cast step plus the five placed Mountains as explicit payment. |

### Executor (`midgame_rows.py`)

- **Ambiguous casts.** When the engine offers several casts of one card (normal and overload, an adventure, a split half), the row now fails closed unless the record names the alternative cost. The old path took the first spell offer, a hidden first-option pick. A named cost matches the engine's own alternative offer or its later cost choice ("Cast with Evoke alternative cost").
- **Timing.** `timing: empty_stack` makes a scripted cast start its own event. It passes priority until the stack has resolved. Steps without a timing behave as before.
- **Trigger order.** Identical instances of one ability of one source are accepted only when the record lists them once per instance. `trigger:<source>|<text>` names one of several abilities of one source. Every other ambiguity fails closed.
- **Token bindings.** An obligation plan binds each free-text record token, per fixture, to an explicit check:
  - an engine event pattern (exact fields, name prefix, exact or minimum count);
  - a scripted engine-offer label;
  - an engine-observed permanent state.

  An unbound unknown token stays unobserved.
- **New terminal checks:**
  - `events`, `selected_frame`, `no_frame`;
  - `not_on_battlefield` (needs the observed seat);
  - `power_toughness`, `counters`, `keyword`, `colors`, each holding for every permanent of the identity.

### Lab adapter readback

Battlefield permanents now read back their counters, evergreen keywords and colors. Each field appears only when present, so other permanents read back unchanged. A Java test (`XmageCheckpointStateRestorationTest`) covers this.

### Result: 29-row run on `814234ea` (clean tree, XMage `37e4df6c`)

Matrix digest `ff525d5265739e1180222b5b1c4d7b16ef654975eefc1659081285bdfa0422cd`.

| Outcome | Rows |
|---|---|
| DIRECT_PASS (10) | CARD_01, 02, 04, 05, 09, 14, 17, 18, 23, 24 |
| FIXTURE_DEFECT (1) | CARD_06 (see below) |
| HARNESS_DEFECT (10) | CARD_03, 08, 11, 13, 15, 19, 20, 21, 27, 28: executor actions (`announce_cast`, `cast_fused`, `activate`, `activate_mana`, `cast_split_half`), combat arrival, causal entries |
| PROVIDER_ADAPTER_DEFECT (5) | CARD_07, 16, 22 (stack spells); CARD_10 (commander spell on the stack); CARD_25 (token object) |
| UNKNOWN (3) | CARD_12, CARD_29 (token vocabulary and plan); CARD_26 (see below) |

Every DIRECT_PASS holds a runner-bound positive receipt in `artifacts/receipts/positive/`.

**CARD_06: the obligation conflicts with the card (Coordinator question).**
- The postcondition is "exactly two Docent of Perfection trigger instances". Harmonic Prodigy doubles triggered abilities of Shamans and other Wizards. Docent of Perfection is an Insect Horror, so its trigger is not doubled.
- The engine correctly puts one Docent trigger and one Prodigy prowess trigger on the stack.
- Scripting this row would demonstrate the obligation false, not prove it. A fixture whose doubled trigger belongs to a Wizard (for example Talrand, Sky Summoner) changes the obligation text, so it needs a Coordinator decision.

**CARD_26: one postcondition fact is not observable.**
- The cast, the Devil mode, the three red 1/1 Devil tokens and their haste all execute.
- "each with printed death trigger" names an ability the readback does not expose, so no plan is onboarded and the row earns no credit.

AF07 stays **UNKNOWN**. 19 identities are not directly proven, and the CARD rows outside the denominator still need the Coordinator's credit route (#453).

## Phase 2c: card parts, activations, cost choices (contract 1.0.14)

### Fixture errata (contract 1.0.14)

The class is `ACTUAL_CARD_DECISION_SCRIPT_ERRATUM`. All rows are outside the denominator and their obligation digests are unchanged.

| Row | Defect | Correction |
|---|---|---|
| CARD_08 | Jeska stays in hand; the script starts with her loyalty ability and declares no payment. | Cast her with the three placed Mountains, then activate her 0 ability once she resolved, target the Bears, attack P2. |
| CARD_11 | The fused cast folds both targets into the cast action. | Each half's target is its own step, in the engine's order. |
| CARD_15 | X is announced before the cast that asks for it (CR 601.2b), and the untap is named with an unsupported set selector. | Cast, then X=10, then the engine's multi-select untap frame. The lossless-library overlay is carried. |
| CARD_21 | The checkpoint sits inside combat damage, but no attack is declared, and an attacking creature cannot be loaded. | Start at precombat main and script the attack on P2. |
| CARD_27 | The scry is a select-up-to-one frame, not a yes/no; Keldon Marauders' own enter trigger asks a target. | Empty scry selection, Marauders targets P2. The lossless-library overlay is carried. |

CARD_19 and CARD_28 need no erratum. Their scripts were already correct; they needed executor actions.

### Executor and adapter

- **Card parts.** The Lab adapter's option metadata now names `source_parent_object_id` for a part of a card: a split half, an adventure, or a modal face. A Java test covers it.
  - `cast_split_half` selects the placed card's part by the half's name.
  - `cast_fused` selects the engine's fused offer.
  - A plain cast of such a card fails closed, because the record must say which part to cast.
- **Activations.** `activate` and `activate_mana` select by source and a fragment of the ability's rules text. `activate_mana` must hit a mana ability.
- **Owed cost choices.** The record's own step names them: `sacrifice_cost` (an object) and `color` (a mana color). Each is answered on the engine's own frame.
- **Empty selection.** `semantic_objects: []` is accepted only when the engine frame's own minimum is 0.
- **New checks:**
  - `events_precede` (simultaneity and ordering);
  - `in_graveyard`;
  - `frame_count`;
  - `pool_spend`;
  - `untapped_count`;
  - `hand_count_min`;
  - `no_frame` filtered by principal and prompt.

  A token may also bind to several checks, all of which must hold.
- **Observable no maximum hand size (CARD_15).** P1 reaches turn 2 holding at least 8 cards, and the engine never asked P1 to discard.

### Result: 29-row run on `064d45a9` (clean tree, XMage `37e4df6c`)

Matrix digest `6e2cb87daf6a7dcbb62ff4affa9cd29c0e57f4e4cf87e2093901ce69eba61eb8`.

| Outcome | Rows |
|---|---|
| DIRECT_PASS (17) | CARD_01, 02, 04, 05, 08, 09, 11, 14, 15, 17, 18, 19, 21, 23, 24, 27, 28 |
| FIXTURE_DEFECT (1) | CARD_06 (obligation conflicts with the card; Coordinator question on #453) |
| HARNESS_DEFECT (4) | <ul><li>CARD_03: `announce_cast` with a cost-increase obligation. Probing it raised a bridge "concurrent pending decision".</li><li>CARD_13, CARD_20: causal stack entries.</li><li>CARD_29: the cast now executes; the Saga chapter target is still unscripted.</li></ul> |
| PROVIDER_ADAPTER_DEFECT (5) | CARD_07, 16, 22 (stack spells); CARD_10 (commander spell on the stack); CARD_25 (token object) |
| UNKNOWN (2) | CARD_12 (delve and look tokens); CARD_26 (printed death trigger not observable) |

Regression on the same tree:
- AF05 HIDDEN rows: 12/12 verified.
- FULL107 midgame rows: 22/22 verified.

AF07 stays **UNKNOWN**: 12 identities are not directly proven, and the Coordinator's credit route (#453) is still open.
