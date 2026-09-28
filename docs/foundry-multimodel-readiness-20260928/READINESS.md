# Four-Model OpenCode Go Readiness — 2026-09-28

## Verdict
**PREPARATION: PASS / RUNTIME ACTIVATION: BLOCKED_BY_ACTIVE_OWNERSHIP**

The canonical Lab operating layer is structurally suitable for model-neutral execution, but current main intentionally admits exactly Space Bunny MAX and Muse XHIGH. DeepSeek V4.1 Flash MAX and GLM 5.3 MAX must not be inserted into the live allowlist in isolation because the current launcher validates the exact two-model contract and would fail closed.

## Selected OpenCode Go profiles
| Profile | Exact model | Native effort | Intended project role | Runtime now |
|---|---|---|---|---|
| deepseek | `opencode-go/deepseek-v4.1-flash` | `max` | primary engineering workhorse candidate | BLOCKED pending launcher integration |
| muse | `opencode-go/muse-spark-1.3-contributor` | `xhigh` | long-horizon leader | ACTIVE |
| glm | `opencode-go/glm-5.3` | `max` | frontier root-cause / difficult review | BLOCKED pending launcher integration |
| space-bunny | `opencode-go/space-bunny-free` | `max` | free/bulk executor | ACTIVE |

Every project profile uses its highest supported OpenCode Go reasoning level. The profile, not a free-form per-turn model choice, owns the native variant.

## Cross-repository audit
- **Commander Lab** is the only canonical policy/config control plane.
- **Forge master** was freshly read at `ef958ee9...`; root `AGENTS.md`, `opencode.json`, and `.opencode/` are absent. This is correct: mirror master must not receive project-only policy files.
- **Mage master** was freshly read at `798b75e5...`; root `AGENTS.md`, `opencode.json`, and `.opencode/` are absent. This is correct for the same reason.
- Both engine forks consume canonical policy through Foundry launcher injection and Lab repo profiles. Do not reintroduce fork-root policy copies.

## DeepSeek usage policy
DeepSeek V4.1 Flash MAX is the preferred **future workhorse candidate**, not a new Rules authority. Route bounded implementation, Java/Python build-test-debug loops, qualification execution, CI remediation, harness/provider repairs, and multi-file engineering to it by default after activation.

Do not use automatic fallback when a Go quota/auth/catalog/upstream failure occurs. The run ends fail-closed; a later explicit profile may resume from the same branch + state + evidence after ownership is released.

For particularly long campaigns or context-heavy continuation, prefer Muse XHIGH. For difficult nonlocal root-cause analysis/cross-subsystem semantics, prefer GLM MAX. Use Space Bunny MAX for free/bulk/mechanical work and keep the GitHub `/oc` lane on Bunny unless a separately justified policy change is made.

## Runtime activation blocker
Open PR #280 declares `sbmax/full-completion` ownership of `tools/foundry/launcher.py` and its tests. The current branch also changes those files. WSR27 therefore does not co-edit them.

PR #280 additionally owns several canonical governance documents. Until those surfaces are released/serialized, WSR27 records the target policy but does not create a conflicting canonical rewrite.

## Exact activation delta after ownership clears
1. Re-lock fresh Lab main HEAD/tree and active-owner map.
2. Integrate/reconcile the current launcher owner's changes first.
3. Replace the dual-executor constants with a data-driven four-profile registry.
4. Expand launcher validation to exactly the four authorized model/native-variant pairs.
5. Expand `opencode.json` allowlist/models atomically with launcher support.
6. Pin every child run and injected agent to the selected profile's exact model/native variant.
7. Preserve no-fallback behavior and existing secret/Git/worktree permissions.
8. Add hermetic tests for all four profiles across CPL/Forge/Mage injection.
9. Run an authenticated bounded DeepSeek MAX smoke without exposing credentials.
10. Only after PASS, make DeepSeek the runtime default workhorse; keep GitHub `/oc` on Space Bunny MAX for quota economy unless separately changed.
