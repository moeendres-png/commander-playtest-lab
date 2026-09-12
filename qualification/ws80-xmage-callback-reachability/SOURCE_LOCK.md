# WS80 Source Lock — XMage Callback / Entrypoint Reachability

- Repository: `moeendres-png/commander-playtest-lab`
- Audit base SHA: `90f95c117b190d6b21704ca7639198e3ac0a2dc2`
- Audit-base tree: `ed83951226f52f528953e7cdb0dec0b12e6eabcc`
- Branch: `ws80/xmage-callback-reachability-20260912`
- Bootstrap HEAD: `d4f18d6c06d4226090f86f31b4706191385a72c5` (WS80 bootstrap, state-only)
- Runtime authority: `config/rules_engines.json` (sole machine-readable pin authority)
- Primary engine pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` (`xmage-1.4.61`, protocol `2.0.0`)
- Engine repin: NOT AUTHORIZED (`ENGINE_PIN_CHANGE` must stay `0`)
- Worktree: `/home/moeen/code/ws80-xmage-callback-reachability`
- State file: `qualification/ws80-xmage-callback-reachability/WORKSTREAM_STATE.yaml`

## Authority

- `config/rules_engines.json:8,12` pins `primary_engine.commit` and `repository`.
- `config/rules_engines.json:39-42` declares `missing_required_capabilities = [legal_actions_supported, action_submission_supported]`.
- `config/rules_engines.json:88,98` declares `production_provider = null`, `provider_decision = NO_PROVIDER_READY`.
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.
- No Full107, RQ-C3, or provider-wide qualification credit is claimed by this workstream.

## Pre-fix defect (CODE_DERIVED, then RUNTIME_VERIFIED by failing tests)

- `XmageBridgePlayer` on the B4 `external_control=true` path silently defaulted on
  every non-priority discretionary callback (20 overridden plus inherited
  first-face defaults) instead of failing closed.
- First failing boundary: `XmageGameManager.java:262-273` constructs
  `XmageBridgePlayer` with non-null `ExternalDecisionController`,
  `XmageGameManager.java:358-387` resumes to a real priority pause, then
  64-decision `GET_LEGAL_ACTIONS` loops drive `game.resume()` through combat,
  triggers, and in-resolution choices with silent defaults active.
- Unconditional fail-closed guard initially broke validated B4 start at
  `GameImpl.init:1409` (`Select a starting player`, `TargetPlayer`, source null,
  phase null). Refined to a narrow init-phase exception that honors the
  requested `starting_player_seat` by self-selecting; all other externally
  controlled discretionary callbacks fail closed.

## Post-fix boundary (this workstream)

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageBridgePlayer.java`:
  single `failIfExternallyControlled` guard plus explicit `chooseAbilityForCast`
  and `chooseLandOrSpellAbility` overrides; narrow `isStartingPlayerInitChoice`
  exception for `GameImpl.init` starting-player selection.
- Null-controller B3 and Phase6 behavior preserved byte-identically.
- No `Main` routing, capability, pin, full-game lane, or pilot-policy change.
