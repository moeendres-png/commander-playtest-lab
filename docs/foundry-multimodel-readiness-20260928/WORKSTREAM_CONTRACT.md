# WSR27 — OpenCode Go Four-Model Foundry Readiness

## Objective
Prepare Commander Simulator Next for one model-neutral OpenCode Go execution layer centered on DeepSeek V4.1 Flash MAX, Muse Spark 1.3 XHIGH, GLM 5.3 MAX, and Space Bunny MAX without breaking the currently qualified dual-executor runtime.

## Source Lock
- Commander Lab main: `933d5df564b5dc77d678935bc79c6554459c347b`
- tree: `3eee0692ff075dc5175795aea8da9f1e86696dfb`
- Forge master: `ef958ee91ac6c9ce0152189f2654bf6e05abf273` / tree `fc3387bf37aab19d780b2939a235309ed32b0492`
- Mage master: `798b75e582270aaec5cacf953b6e8cc09d2f59a3` / tree `e94a3b7bdcd855925a70e0834a94aa1b78e02d7c`

## Authority
Latest user instruction > fresh repository state > current tests/source > exact engine pins > official Rules sources. Rules Core remains sole gameplay authority. Model routing never changes evidence or Rules authority.

## In Scope
- machine-readable four-model profile authority;
- highest-supported native-effort locks;
- model provenance fields in durable workstream state;
- current cross-repo injection/readiness audit;
- hermetic regression tests for the preparation surfaces;
- exact follow-up contract for runtime activation.

## Out of Scope
- co-editing `tools/foundry/launcher.py` or `tests/foundry/test_launcher.py` while owned by `sbmax/full-completion`;
- editing PR #280-owned governance files;
- widening `opencode.json` before launcher support exists;
- modifying Forge or Mage mirror masters;
- Production Provider selection or Architecture Freeze;
- any simulator Rules/qualification-semantic change.

## Ownership
Branch `wsr27/multimodel-foundry-readiness-20260928`. Owned surfaces are new WSR27 docs/tests/registry plus non-conflicting state schema/repo-profile metadata only.

## Dependencies / Hard Gates
- Active launcher ownership must be released or serially integrated before runtime activation.
- DeepSeek/GLM must not be added to the live allowlist until launcher validation supports all four profiles.
- No automatic model fallback.
- Authenticated DeepSeek MAX smoke is required before changing the runtime default.

## Forbidden Shortcuts
No partial allowlist widening, silent fallback, lower-effort substitution, historical PASS promotion, fork-master policy copies, secret inspection, or Rules/evidence weakening.

## Evidence Requirements
Fresh exact repository identities, machine-readable profile registry, schema acceptance tests, current fork-root governance observation, and exact activation blocker/next action.

## Stop Condition
This preparation workstream is COMPLETE when safe non-overlapping readiness work is persisted and the remaining launcher/config activation is isolated behind the active ownership gate. Runtime four-model activation remains BLOCKED until that gate clears.
