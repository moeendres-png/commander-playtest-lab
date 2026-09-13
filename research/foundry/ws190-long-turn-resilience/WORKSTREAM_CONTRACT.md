# WS190 Workstream Contract

- Objective: interrupt-safe launcher plus explicit operator-selected Zen execution.
- Repository: moeendres-png/commander-playtest-lab.
- Audit base/main: `6eea80fb33746257e8434fd4e1c906765d8f22e9`.
- Audit tree: `3a3ca37639d6cb30864bda0fa60bb35d3d7b94c5`.
- Branch: `ws190/opencode-zen-provider-override-20260913`.
- Owner: WS190 / user-authorized Astra Medium bounded implementation.
- Worktree: isolated `work/ws190` checkout in the current Commander project workspace.
- State: this directory's `WORKSTREAM_STATE.yaml`, explicitly addressed.
- Authority: direct user WS190 implementation/test/branch-push authorization;
  canonical AGENTS.md otherwise applies. No PR or merge authorized.
- Inputs: the task's read-first file list and unchanged operator evidence.
- Scope: launcher, necessary metrics allowlist extension, launcher regressions,
  concise Foundry documentation and this evidence directory.
- Out of scope: simulator, engines/pins, qualification, data, canonical provider
  replacement, credential access, paid/model requests, automatic fallback.
- Dependencies: existing Foundry bootstrap, writer-lock, canonical config and
  agent/skill/command snapshot; qualified CLI 1.18.30.
- Hard gates: unchanged Go default; explicit sole Zen provider/model; no permission
  weakening or below-HIGH request; identity/context/metrics binding; interrupt 130,
  end telemetry and lock release; WS78 preservation; no semantic/qualification change.
- Validation: test-first regression, four requested modules, full Foundry suite
  due shared launcher/metrics impact, Ruff; optional isolated offline CLI inspection.
- Evidence: test/config distinction; authenticated Zen runtime NOT_RUN.
- Persistence: coherent technical commit, evidence/state seal, authorized branch
  push only; no force/rebase/merge. Preserve operator evidence byte-for-byte.
- Stop conditions: source-lock mismatch, conflicting ownership, invariant weakening,
  or genuine unavailable required capability; routine failures must be repaired.
