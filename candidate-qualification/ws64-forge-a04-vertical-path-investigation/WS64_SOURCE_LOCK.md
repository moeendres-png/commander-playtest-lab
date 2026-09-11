# WS64 — Source Lock (verified 2026-09-11 before material edits; re-verified at each checkpoint)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: `/home/moeen/code/ws64-forge-a04-vertical-path-investigation`
- Branch: `ws64/forge-a04-vertical-path-investigation-20260911`
- CPL audit base HEAD: `63930f13e8308c8a1d17fff5fd5a82c62ef5519d` — VERIFIED (`git rev-parse HEAD` at session start; `git status` clean except untracked WS64 dir)
- CPL audit base TREE: `e9eb007cc24bae8b0f35afae83f87ae4cadbde38` — VERIFIED (`git rev-parse HEAD^{tree}`)
- Working state at lock: clean tracked tree; untracked `candidate-qualification/ws64-forge-a04-vertical-path-investigation/` only.
- Remote source branch lineage ref: `ws62/forge-successor-requalification-20260911` (expected source head `63930f13e8308c8a1d17fff5fd5a82c62ef5519d`; verified at safe_push dry-run time, not here).

## Forge engine pins (unchanged by WS64; Forge source strictly READ-ONLY)

- ACCEPTED FORGE PIN (only engine pin; runtime for all WS64 runs): `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / tree `2c18327f79e330f2ed167067166ffd42d61b0849` / repository `moeendres-png/forge`
- Read-only successor checkout: `/tmp/ws62-forge-src-a9a95db` (consumed read-only; only ignored `target/` build output from required fresh `mvn -o` compiles; no source edits in credited runs; temporary diagnostic edits during investigation were fully reverted and rebuilt clean before validation)
- Diagnostic terminal `17945295b8dddd5c41ea471432d3c03d581ed16a` and validated diagnostic/code head `3347084d222266fb55fc9490e42ae80663589b09` are DIAGNOSTIC AUTHORITY ONLY (WS63). NOT engine pins. NOT adopted.
- No new Forge pin. No Forge edits in validated state.

## Policy authority

- Foundry policy authority and canonical tools: `/tmp/csn-policy-main-c1a760a/tools/foundry/state.py` and `safe_push.py` (accessed via subprocess; no hand-authored state).
- `AGENTS.md` is privileged repository instruction (not restated here).

## Standing state (preserved exactly)

- `ARCHITECTURE_FREEZE = NOT_CLAIMED`
- `PRODUCTION_PROVIDER = NOT_SELECTED`
- `BEHAVIOR_CREDIT = 0/107`
- `FULL107 = NOT_RUN`
- First Wave: NOT executed here (fixed denominator 15/20 reported as readiness only).
- Evidence labels used: only DIRECTLY_VERIFIED, CODE_DERIVED, TECHNICALLY_CONFORMANT, EXTERNALLY_RULE_VALIDATED, MODELED, SYNTHETIC, UNKNOWN. Never RUNTIME_VERIFIED.
