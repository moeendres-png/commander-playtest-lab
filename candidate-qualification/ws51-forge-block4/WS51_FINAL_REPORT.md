# WS51 — FORGE BLOCK-4 RESTORE DISPOSITION — TERMINAL REPORT

- Branch: `ws51/forge-block4-restore-disposition-20260910`
- Source base: CPL `f8bd8b2d582627202a462ae7c7adf9fd5af83a57` / tree `fcb7fc009bea6527e410eb88f67549ca16cc8ea4` (verified MATCH before mutation)
- Forge pin: `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29ce4de31a964972461db2b48b4221e07f` (verified MATCH; full tree derived locally via `rev-parse`)
- Principal disposition: **RESTORE_PATH_REJECTED** (scoped — see §9)
- `BEHAVIOR_CREDIT = 0/107`, `FULL107 = NOT_RUN`, `ARCHITECTURE_FREEZE = NOT CLAIMED`, `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Work completed (semantic completion rule, end to end)

1. **Source lock + writer gate.** CPL HEAD/TREE match the contract; tree clean; Forge pin checked out read-only from GitHub into scratch (`/tmp/opencode/ws51-forge-pin`, detached HEAD) and HEAD/TREE re-derived locally — both match. Push remote is disabled. Writer gate: `/proc` cwd inspection of every `opencode` process — exactly one (this session's host) holds this worktree; no git locks. `WS51_WRITER_COUNT = 1`.
2. **Located the authoritative failure.** Retained BLOCK-4 = fixture `WS05-MP-BLOCK-4` (frozen v1.0.5 record extracted via read-only `git show` of the WS47 freeze and digest-verified: sha256 `0e47b792…940b3`, schema/bundle match): turn 1, combat/declare_blockers, P1 active, P2 priority; attackers `obj:mp-a2→P2`, `obj:mp-a3→P3`; eligible P2 blockers `[obj:P2-bears, obj:mp-p2-blocker]`; **no pre-declared blocks**; scripted `declare_blocker blocker_assignment {obj:mp-p2-blocker → obj:mp-a2}` with exactly-one/fail-closed semantics; native_procedure `[NATIVE_ENTER_DECLARE_BLOCKERS_STEP, NATIVE_DECLARE_BLOCKERS]`; required events include `blocker_declared:obj:mp-p2-blocker->obj:mp-a2`. The retained R1e behavior row verdict is `PROBE_FAIL` ("1 scripted decisions unconsumed"): 59 frames (1 starting-player + 4 mulligan + 54 priority, **zero declare frames**), 44 native events (**zero declare-related**), session lurched to turn 4 DRAW and returned.
3. **Reproduced from source lock (Gate 2).** Re-ran the committed R1d discriminator against **freshly compiled pin-source classes** (`mvn -o compile`, forge-core+forge-game, rc=0): variant A NPEs byte-identically (`AttackingBand.isBlocked() is null` at `Combat.assignAttackersDamage(Combat.java:873)`), variant B returns — `STATE_RESTORE_OR_ADAPTER_DEFECT`, all fields identical to the committed JSON (108 stubs). Stronger provenance than the original (m2-class) run: fresh-build `assignAttackersDamage` disassembly is sha-identical to the m2 jar (both major v61).
4. **Traced the native lifecycle (pin source).** `AttackingBand.blocked` defaults null and is set exactly once per combat by `fireTriggersForUnblockedAttackers` (flag computation + `AttackerUnblocked`/`AttackerUnblockedOnce` triggers). Restore sequencing: `match.startGame(game, hook)` → natural pre-game → `setupFirstTurn` → hook (`applyNativeState`: `GameState.applyToGame`, then `devModeSet`, then `applyCombat` injection) → `mainGameLoop` runs **priority in the restored step, then the next step's entry**. `devModeSet` skips entry effects by documented design. The restored step's `onPhaseBegin` turn-based actions therefore **never execute** (call-site enumeration: entry actions run only from advance paths).
5. **Built the WS51 BLOCK-4 witness** (`ws51_block4_witness_template.java` + `run_ws51_block4_witness.py`): hand-built BLOCK-4-shaped combat (2 attackers, 2 P2 blockers mirroring the frozen eligible pair, loader-exact `devModeSet→new Combat→addAttacker→addBlocker→updateCombatForView` order), six variants A–F, driver-adjudicated with a textual formula-parity gate against the shipped provisional mirror. Verdict `RESTORE_DECISION_GAP_PROVEN`, replay-stable across independent runs, negative control (mutated mirror → fail-closed, no output) verified.
6. **Diagnosed two silent gaps the mirror does not close** (both on the witness, both also explaining the retained probe session):
   - *Trigger loss* (D vs E): mandatory `AttackerUnblocked` (Abyssal Nightstalker) silently absent with the mirror (`sim false→false`), natively enqueued (`false→true`). (Method note: fired triggers land in the simultaneous-entry holding list, not the main stack — established via source + throwaway reflection diag, kept out of committed evidence.)
   - *Silent blocked-combat damage loss* (B/C vs F, **vanilla cards**): the skipped `orderBlockers/orderAttackersForDamageAssignment` leaves both order maps null, so `assignAttackersDamage`/`assignBlockersDamage` register **no sources** for blocked bands — blocked attackers and blockers deal zero, only unblocked attackers hit, with no exception/consult/event. Ledgers: B `bearA_taken=0, runeclaw_taken=0, p2_life=18` vs F `bearA_taken=4, runeclaw_taken=2, p2_life=18`.
7. **Identity integrity (Gate 4).** Variant F (exact skipped pipeline tail in pipeline order) reaches the native division consult with source == injected bearA id and recipients == exactly the two injected blocker ids (`identity_match=true`), engine-validated (`CombatDamageAssignmentValidator` runs natively; the harness-role stub returns first-recipient-full). Identity is NOT the failure layer — the objects are right, the lifecycle is missing.
8. **No repair implemented — deliberately.** The missing effects (declare decision, triggers, ordering) cannot be synthesized CPL-side without a second Rules engine. The provisional mirror is WS48-owned, load-bearing, and crash-preventing; WS51 recharacterizes it (crash-prevention-only) without touching it.
9. **Dispositions recorded:** RNG `NONE` (fixture channels empty; no RNG in the declare pipeline or GameState path; witness deterministic across reruns); hidden-info `NO_IMPACT` (additive-only delta; no observation surfaces touched); historical impact 15× `NO_IMPACT` / 0 / 0 / 0 (no shared-file mutation; no reruns for reassurance).

## 2. New findings (architecture-relevant)

- **F1. The restore defect is structural, not parametric.** Any restore frozen AT a step whose entry pipeline carries Rules-relevant effects cannot continue trustworthily: the engine considers the step entered. BLOCK-4 is the proving instance because its required behavior (the declaration) IS the skipped entry effect and its fixture correctly contains no pre-declared blocks.
- **F2. The provisional mirror masks more than it fixes.** It converts a loud, diagnosable NPE into silent forward-lurch: no triggers, no ordering, blocked combat dealing zero — while transcripts complete and games advance turns. Any future reliance on "the game continued" as evidence must be re-examined through this lens (the Repair-01 lesson generalizes: continuation ≠ correctness).
- **F3. The fixture is coherent; the architecture contradicts it.** `NATIVE_ENTER_DECLARE_BLOCKERS_STEP` + scripted declaration + required `blocker_declared` event cannot be honored by devModeSet-positioned restore. The fixture asks for native declaration.
- **F4. The engine needs no change.** R1d-B clean, devModeSet documented, validator fail-closed (`FORGE_COMBAT_DAMAGE_*` guards hold). Not `ENGINE_DEFECT_REQUIRED`.
- **F5. The replacement exists and is demonstrated.** WS50 traversed `declare_attacker`/`declare_blocker` natively from natural start (587 frames, 9 decision kinds, read-only reference). Restore-seeded native progression (restore strictly before the first decision step, engine enters decisions) is the smallest sound replacement — recommended, not implemented (Coordinator architecture decision).
- **F6 (adjacent caveat, untested).** `applyStack` rebinds semantic ids to fresh `fromPaperCard` hosts rather than aliasing battlefield objects — relevant if stack-bearing restores are ever used for continuation. Recorded as `UNKNOWN`, out of scope.

## 3. Changes (WS51-owned; additive only)

- `candidate-qualification/ws51-forge-block4/ws51_block4_witness_template.java` (new): hand-built BLOCK-4 witness, variants A–F.
- `candidate-qualification/ws51-forge-block4/run_ws51_block4_witness.py` (new): driver with Forge-lock check, 108-stub mechanical controller generation, formula-parity gate, restore-contamination guard, 7-check adjudication.
- Evidence: `WS51_SOURCE_LOCK.json`, `WS51_R1D_FRESH_RERUN.json`, `WS51_BLOCK4_WITNESS.json`, `WS51_LIFECYCLE_IDENTITY_MATRIX.json` (10 invariants), `WS51_NATIVE_VS_RESTORE.json` (core-question answer), `WS51_RNG_DISPOSITION.json`, `WS51_HIDDEN_INFO_DISPOSITION.json`, `WS51_HISTORICAL_IMPACT_LEDGER.json`, `WS51_DISPOSITION.json`, `WS51_FINAL_REPORT.md` (this file).
- Zero modifications to existing files (verified by `git status`/`git diff`).

## 4. Tests / evidence (all runtime on pin classes unless noted)

| Command | Result | Evidence |
|---|---|---|
| `run_r1d_discriminator.py --forge <pin> --classpath-file <fresh-build cp>` | A NPE@873, B RETURNED → `STATE_RESTORE_OR_ADAPTER_DEFECT`; identical to committed JSON | `WS51_R1D_FRESH_RERUN.json` (DIRECTLY_VERIFIED) |
| `run_ws51_block4_witness.py` (×3 runs: initial, stability rerun, post-control sanity) | `RESTORE_DECISION_GAP_PROVEN`, 7/7 checks, ledgers/flags/identity stable across runs | `WS51_BLOCK4_WITNESS.json` (DIRECTLY_VERIFIED) |
| Negative control: mirror formula mutated → driver | `WS51_MIRROR_FORMULA_MISSING_FROM_WITNESS`, no output; file restored via `git checkout`, tree clean | shell receipt §1.5 (DIRECTLY_VERIFIED) |
| `mvn -o -pl forge-core,forge-game -am compile` at pin | rc=0; `assignAttackersDamage` disassembly identical to m2 artifact | source-lock JSON (DIRECTLY_VERIFIED) |
| Retained R1e BLOCK-4 row (read-only re-analysis) | 59 frames, 0 declare frames, 44 events/0 declare-related, script unconsumed, turn-4 return | committed `WS48_R1F_POSTFIX_R1E_REGRESSION.json` (DIRECTLY_VERIFIED, retained) |
| Pin source traces (Combat/PhaseHandler/GameAction/TriggerHandler/MagicStack/GameState) | invariant matrix rows 1–10 | matrix JSON (CODE_DERIVED) |
| WS50 slice (read-only) | native declare traversal exists; restore left OPEN by WS50 | WS50 D summary (TECHNICALLY_CONFORMANT) |

## 5. Causal classification

- **RESTORE/HARNESS — PRIMARY (joint).** devModeSet-positioned injection + priority-then-advance continuation structurally skips the restored step's entry pipeline.
- **ARCHITECTURAL_UNSUPPORTED — PRIMARY (joint).** No CPL-side completion exists short of a second Rules engine; arbitrary restore at decision-bearing steps is the wrong abstraction.
- **PROVIDER/ADAPTER — CONTRIBUTING.** The provisional flag mirror trades a loud NPE for silent semantic loss.
- **FIXTURE — NO.** Coherent record asking for native declaration.
- **FORGE_ENGINE — NO.** Engine correct as designed; no mutation required or requested.

## 6. Native lifecycle / identity findings

See matrix (`WS51_LIFECYCLE_IDENTITY_MATRIX.json`): rows 1–6 NOT_PRESERVED (flags-establishment w/o mirror, both trigger families, both order maps, declare decisions, declare-side cleanup); row 7 PRESERVED (identity — F binds injected ids); row 8 POSITION_ONLY; row 9 PRESERVED (commit path); row 10 UNKNOWN/out-of-scope (stack aliasing caveat).

## 7. RNG / replay

`RULES_RNG_IMPACT = NONE` for the BLOCK-4 question (fixture channels empty; no RNG in declare/GameState-restore paths; witness seed 510051 stable across reruns). Pre-hook natural-start RNG is orthogonal and unchanged.

## 8. Hidden information

`HIDDEN_INFO_IMPACT = NO_IMPACT` (additive-only; no observation/snapshot/frame surfaces touched; outputs contain only ephemeral ids, public card names, verdicts).

## 9. Historical evidence impact

`NO_IMPACT = 15`, `TARGETED_REQUALIFICATION_REQUIRED = 0`, `INVALIDATED = 0`, `UNKNOWN = 0`. Every non-trivial retained family enumerated in the ledger JSON; none touched, none rerun.

## 10. PASS / FAIL / UNKNOWN

Principal disposition: **RESTORE_PATH_REJECTED** — scoped: (a) REJECTED for continuation via restore at/after decision-bearing steps (BLOCK-4 proving instance); (b) restore-as-construction/readback explicitly PRESERVED (G48-07/G48-08 stand); (c) all other restore uses stay UNKNOWN/fail-closed, nothing claimed safe.

`BEHAVIOR_CREDIT = 0/107` · `FULL107 = NOT_RUN` · `ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED` · `R2_TRIGGER = NOT_FIRED` · XMage PARKED.

## 11. Remaining blockers

None in WS51 scope. Genuine next-owner items live in §13 (Coordinator architecture decision).

## 12. Outputs

All under `candidate-qualification/ws51-forge-block4/` (committed, local only — no push performed): 2 source files + 10 evidence/report JSONs/MD (see §3). Local commits: `ea2155bb` (witness template + driver) and the follow-up evidence/report commit sealing this report (see `git log`).

## 13. Dependencies unblocked

Forge Full107 on the restore-continuation architecture must NOT be authorized — this disposition closes the WS50-left-open `restore_path: OPEN / PRE-FREEZE_REQUIRED` item against that architecture. What unblocks behavior qualification instead: Coordinator approval + implementation of restore-seeded native progression (restore strictly pre-decision; scripts extended to natively-driven declarations), followed by fresh targeted (never imported) behavior evidence.

## 14. Exact next action

**Coordinator:** adjudicate `RESTORE_PATH_REJECTED` (scoped per §10) and decide whether to authorize the recommended replacement architecture (restore-seeded native progression with extended decision scripts) as pre-Freeze work; on approval, commission it as a new workstream with fresh (zero-imported) behavior evidence. No Full107, no credit, no Freeze, no provider selection follows from WS51.
