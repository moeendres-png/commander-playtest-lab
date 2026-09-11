# WS65 — Source Lock (verified 2026-09-11 before material edits)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: `/home/moeen/code/ws65-forge-rqc3-first-wave`
- Branch: `ws65/forge-rqc3-first-wave-20260911`
- CPL audit base HEAD: `b303e6f18bbb937e977503e62273d4a72e26c2af` — VERIFIED (`git rev-parse HEAD`)
- CPL audit base TREE: `7c27dd7b621f5720acbfbf846d10e6263cda2faa` — VERIFIED (`git rev-parse HEAD^{tree}`)
- Working state at lock: clean tracked tree; untracked `candidate-qualification/ws65-forge-rqc3-first-wave/` only (bootstrap `WORKSTREAM_STATE.yaml`).
- WS64 terminal (audit base / descendant validated head `8cac11e9e5ec111a9d9901923f5a1c2d80165936`): behavior entry prerequisites only; `BEHAVIOR_CREDIT=0/107`.

## Forge engine pin (only engine pin; Forge source strictly READ-ONLY)

- ACCEPTED FORGE PIN: `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / tree `2c18327f79e330f2ed167067166ffd42d61b0849` / repository `moeendres-png/forge`
- Exact Forge checkout: `/tmp/ws65-forge-src-a9a95db` — VERIFIED (`git rev-parse HEAD` = pin; `HEAD^{tree}` = pin tree).
- Fresh offline compile in the exact checkout (`mvn -o -pl forge-core,forge-game -am -DskipTests compile`): BUILD SUCCESS (forge-core 149 sources, forge-game 817 sources). Only ignored `target/` output; no source edits.

## RQ-C3 authority (read-only research export, not a git checkout)

- Path: `/tmp/ws65-rqc3-authority-20260911/` (contains `COORDINATOR_RULES_GATES.md` + `research/candidate-qualification/common/rq-c3/`)
- RQ-C3 authority HEAD (per workstream task): `897d72f0b57bb8febe045870acaa3d2dba4bde56`
- Corrected manifest: 18 scenarios, First Wave = 15 (`A03 A04 B01 C01 C03 D06 E01 E02 F01 G02 G03 G04 H01 I01 J02`), decision-kind union = 20.
- WS65 reads the exact authority entries from `/tmp/ws65-rqc3-authority-20260911/research/candidate-qualification/common/rq-c3/scenarios/RQ-C3-*.json` + `RQ_C3_FIRST_WAVE_EXECUTION_PACK.json`.

## Policy authority

- Foundry policy authority and canonical tools: `/tmp/csn-policy-main-c1a760a/tools/foundry/state.py` and `safe_push.py` (accessed via subprocess; no hand-authored state).
- `AGENTS.md` is privileged repository instruction (not restated here).

## Standing state (preserved exactly)

- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `PRODUCTION_PROVIDER = NOT SELECTED`
- `BEHAVIOR_CREDIT = 0/107` (prior Forge RQ-C3 behavior credit 0/107)
- `FULL107 = NOT_RUN`
- Forge source remains strictly READ-ONLY. No engine edits. No provider semantic edits. No main repin.
- Evidence labels used: only DIRECTLY_VERIFIED, CODE_DERIVED, TECHNICALLY_CONFORMANT, EXTERNALLY_RULE_VALIDATED, MODELED, SYNTHETIC, UNKNOWN. Never RUNTIME_VERIFIED.
