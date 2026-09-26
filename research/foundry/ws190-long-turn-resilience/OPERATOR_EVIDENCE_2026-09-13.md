# WS190 Operator Evidence — 2026-09-13

## Direct runtime findings

1. Foundry TUI launch uses the parent launcher process to `subprocess.run()` OpenCode in the same terminal. Closing/interrupting the child with Ctrl+C can surface terminal escape sequences in the parent terminal; this is not evidence of repository mutation.
2. Current `tools/foundry/launcher.py` has an interrupt-path defect: `rc` is assigned only after `subprocess.run()` returns. If `KeyboardInterrupt` occurs during the child, the `finally` telemetry block references uninitialized `rc`, causing `UnboundLocalError` and masking the original interrupt.
3. Canonical `opencode.json` currently restricts execution to `enabled_providers: ["opencode-go"]` and an experimental `provider.use` policy that denies `*` then allows only `opencode-go`. Therefore OpenCode Zen is intentionally hidden/unusable inside canonical Foundry sessions even if Zen credentials exist.
4. Operator reports OpenCode Go balance exhaustion and requests an explicit, temporary OpenCode Zen `muse-spark-1.3-contributor-free` HIGH execution path. This must be an auditable provider substitution, never a silent fallback, and must not claim canonical-provider qualification.

## Required resilience implications

- Fix interrupt-safe launcher telemetry (`rc` initialized / KeyboardInterrupt handled explicitly) without weakening writer-lock release or fail-closed semantics.
- Treat TUI child lifetime/terminal ownership explicitly; avoid misleading post-TUI output where possible while preserving launcher-held writer lock and end telemetry.
- Add an explicit operator-authorized execution-provider override contract that can permit a bounded alternate provider/model while preserving permissions, agent, HIGH floor, state/source lock, evidence rules, and telemetry.
- Provider override must be opt-in, recorded in launch context and metrics, and rejected if not explicitly allowed by the workstream/operator.
- Never auto-fallback from OpenCode Go to Zen on quota/transport failures.
