# WS80 Adjudication — XMage Callback / Entrypoint Reachability

## Source

- Adjudicator task `ses_f68b3ae7bffelk6GWv0IZiCVJ2` (XHIGH, read-first, no edits).
- Observed branch `ws80/xmage-callback-reachability-20260912`, HEAD
  `d4f18d6c06d4226090f86f31b4706191385a72c5`, audit base `90f95c11`.
- Diff `90f95c1..HEAD` at adjudication time: only
  `qualification/ws80-xmage-callback-reachability/WORKSTREAM_STATE.yaml`.
- Config pin `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`, protocol `2.0.0`.

## Verdict

`FAIL` pre-fix: the B4 `external_control=true` compatibility path could reach
discretionary defaults while representing the operation as bounded supported.

- Root cause class: `PROVIDER_ADAPTER_DEFECT` (Lab-owned `XmageBridgePlayer`).
- First failing boundary: `XmageBridgePlayer` with non-null
  `ExternalDecisionController` (`XmageGameManager.java:262-273`, resume
  `358-387`, 64-decision loops). None of `XmageBridgePlayer.java:102-397`
  checked the controller; `submission_ready`
  (`ExternalDecisionController.java:158-161`) covers only targets/modal;
  `XmageActionExecutor.java:110-125` covers only
  `target_ids/selected_modes/choices`.
- Count pre-fix: 20 overridden discretionary stubs plus 5 inherited
  first-face/parent defaults reachable on the external path; full-game lane 0.

## Rejected hypotheses

1. Three families is filename folklore — rejected (`Main.java:23-40` three
   disjoint dispatches, distinct bridges/players, Python spawners, CI jobs).
2. Full-game is a flag preserving compat — rejected (separate
   `XmageFullGameJsonlBridge` class, disjoint message set, seed required,
   one-game/process, `human=true` blocking controller).
3. Bridge stubs unreachable on claimed B4 path — rejected (incomplete gates,
   64-pass loops, no invocation log; green B3/B4 assertions are `CODE_DERIVED`
   for non-invocation).
4. Full-game has hidden defaults via `chooseRingBearer/getMultiAmount/flip` —
   rejected (delegations audited safe via externalized `chooseUse` plus engine
   `RandomUtil` plus reflection test).
5. Python pilot reconstructs legality — rejected (engine queries only; Python
   ranks offered `option_id`s; Java re-validates allow-list, bounds, actor,
   staleness).
6. Capability inflation exists — rejected (`false` everywhere for compat
   production claims; tactical/phase85/fake hits are non-compat scopes).
7. Shuffle no-op is engine-owned randomness — rejected (compat no-op plus
   `seed_supported=false` plus null seed is explicitly not owned; full-game
   `super.shuffle` plus `setSeed` is owned).

## Recommended repair (adopted with one refinement)

Single fail-closed guard in `XmageBridgePlayer` when
`externalDecisionController != null`, called at the top of each discretionary
stub, plus explicit overrides for inherited `chooseAbilityForCast` and
`chooseLandOrSpellAbility`. Preserve null-controller B3/Phase6 behavior,
`priority`, `chooseMulligan`, `shuffleLibrary`, and GUI/out-of-scope methods.
Do not touch pins, capabilities, routing, the full-game lane, or pilot policy.
No `AUTHORITY_GATE` for this guard.

## Implementer refinement (evidence-driven)

An unconditional guard broke validated B4 start at `GameImpl.init:1409`:
`Select a starting player` (`TargetPlayer`, source null, phase null). The
bounded bridge honors the requested `starting_player_seat` by self-selecting
the choosing player. The guard was refined to a narrow
`isStartingPlayerInitChoice` exception (TargetPlayer, source null, phase null,
exact message/desc, min/max 1); every other externally controlled
discretionary callback still fails closed. Validated by
`XmageExternalDecisionTest`, `XmageActionSubmissionTest`, and
`XmageEventLogLifecycleTest` passing post-fix, plus new
`XmageBridgePlayerFailClosedTest` proving fail-closed with observable old
defaults.

## Hard-gate pre-verdicts (adjudicator) vs post-fix (implementer)

- `ENTRYPOINT_INVENTORY_COMPLETE`: `PASS` / `PASS`.
- `CALLBACK_INVENTORY_COMPLETE`: `PASS` / `PASS`.
- `CAPABILITY_REACHABILITY_CONSISTENT`: `FAIL` / `PASS`.
- `PRODUCTION_REACHABLE_DEFAULT_DECISIONS`: `20` / `0`.
- `FULL_GAME_EXTERNAL_DECISION_BOUNDARY`: `PASS` / `PASS`.
- `RULES_RANDOMNESS_ENGINE_OWNED`: `PASS` (full-game; compat explicitly not
  owned by design) / same.
- `UNSUPPORTED_PATHS_FAIL_CLOSED`: `FAIL` / `PASS`.
- `COMPATIBILITY_CAPABILITY_INFLATION`: `0` / `0`.
- `PILOT_RULES_LOGIC`: `0` / `0`.
- `ENGINE_PIN_CHANGE`: `0` / `0`.
