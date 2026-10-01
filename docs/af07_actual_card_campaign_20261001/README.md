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
| Runner identity | commit `49712fe563bc1611f12c68d151a64baf3bf6ac9a`, clean tree; digest in `artifacts/CAMPAIGN_IDENTITY.json` |
| Output matrix digest | `f00e47bc3b3261f99ec919d5522800eb60bfff32a910d8b6ea15c987df7227b5` |

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
  `artifacts/receipts/positive/CARD_02.json` (digest `c5975ab52454fb51…`).
- **CARD_24** Warstorm Surge — construction `EXACT`; `entering_creature_damage:P2:2`
  observed on the tape and P2 at 18 life on the engine's observation. Receipt
  `artifacts/receipts/positive/CARD_24.json` (digest `84a377c993794733…`).

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
