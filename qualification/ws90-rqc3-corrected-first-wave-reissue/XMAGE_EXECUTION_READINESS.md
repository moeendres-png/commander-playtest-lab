# XMage First-Wave Execution Readiness (current pin)

Current integrated XMage: `cfc36f445f917f101fa2ed588770e043f53bc44c` (WS88-integrated successor; `config/rules_engines.json:primary_engine.commit`).

WS88 proved bounded current runtime and corrected H01 engine behavior (engine-internal `WS81H01CorrectedTest`: A/B/C pass on `cfc36f`). That does NOT grant RQ-C3 behavior credit.

## Verdict

`XMAGE_FIRST_WAVE_EXECUTION_READINESS = BLOCKED_BY_BOUNDARY`

## Why blocked

- `capability_truth: legal_actions_supported false, action_submission_supported false` (`VALIDATION.json`, WS88).
- `missing_required_capabilities: [legal_actions_supported, action_submission_supported]` (`config/rules_engines.json`).
- Truth boundary: `Globally complete legal-action enumeration and action submission remain unproven because target, mode, choice and combat classes are incomplete. Mulligan, seed-control, replay and complete production game-loop coverage remain unproven.`
- Historical WS60 production functionality D1–D5 (`granted_library` binding, look-window, ledger views, key-mode Choice projection + redaction, content-ordered attacker/blocker frames) is `STILL_REQUIRED_FOR_EXECUTION` but `ABSENT` on current main (see `WS60_HARNESS_IMPACT.json`). Even with D1–D5 restored, the bridge as-qualified on `cfc36f` remains a B4-D lifecycle bridge, not a full First-Wave executor.
- Missing qualified decision classes (from 20-kind union): `targets`, `modes`, `choice-family (copy choices, generic choice)`, `hidden-zone selection/search`, `attackers/defender per attacker/blockers/combat damage assignment (full combat)`, `X`, `replacement/trigger ordering`, `activate`, `alternate cost`, `mana payment/source (beyond bounded bills)`, `Commander movement`, `concession`, globally complete `cast`. Only bounded `pass` (plus bounded targetless/nonmodal submission including Rograkh cast) is qualified.

## Future route (not implemented here)

1. Systemically re-implement D1–D5 functionality on `cfc36f` (no verbatim cherry-pick, no engine edits, no second Rules logic) with WS80 fail-closed boundary preserved.
2. Close B4-D gaps for every required First-Wave decision class through current Rules-Core-generated legal decisions only (engine-authoritative frames; pilot selects within offered set; unmapped fails closed).
3. Apply WS66 B01 relative-delta provenance alongside corrected H01 family.
4. Fresh twin First-Wave execution on `cfc36f` under `FIRST_WAVE_EXECUTION_PACK_CORRECTED.json` + `FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json`, with hidden-info, RNG journaling, and replay re-proof sealed anew.
5. No `14/15` restoration until fresh H01 slot requalification passes every REQUIRED discriminator.

## What WS90 does not do

No remediation implemented. No First Wave run. `XMAGE_RQC3_FIRST_WAVE = NOT_RUN`. `BEHAVIOR_CREDIT_CHANGE = 0`.

## Exact next action for XMage

A future execution workstream (not WS90) owns steps 1–4 above against the WS90 corrected authority, starting from current main + `cfc36f` + WS90 pack/requirements/validator.
