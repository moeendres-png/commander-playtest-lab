# Four-Model OpenCode Go Readiness — 2026-09-28

## Verdict
**PREPARATION: PASS / RUNTIME ACTIVATION: BLOCKED_BY_ACTIVE_OWNERSHIP**

The canonical Lab operating layer is structurally suitable for model-neutral execution, but current main intentionally admits exactly Space Bunny MAX and Muse XHIGH. DeepSeek V4.1 Flash MAX and GLM 5.3 MAX must not be inserted into the live allowlist in isolation because the current launcher validates the exact two-model contract and would fail closed.

## Selected OpenCode Go profiles
| Profile | Exact model | Native effort | Runtime now |
|---|---|---:|---|
| deepseek | `opencode-go/deepseek-v4.1-flash` | `max` | BLOCKED pending launcher integration |
| muse | `opencode-go/muse-spark-1.3-contributor` | `xhigh` | ACTIVE |
| glm | `opencode-go/glm-5.3` | `max` | BLOCKED pending launcher integration |
| space-bunny | `opencode-go/space-bunny-free` | `max` | ACTIVE |

Every project profile uses its highest authorized OpenCode Go reasoning level.

## Selection semantics
The repository does **not** assign task classes, preferred uses, frequency, or model ranking. The operator selects the execution profile explicitly for each run through the invocation/prompt workflow. Foundry is responsible only for binding that selected profile to the exact model identity and authorized native effort, preserving provenance, enforcing permissions, and failing closed rather than silently switching models.

## Cross-repository audit
- **Commander Lab** is the only canonical policy/config control plane.
- **Forge master** was freshly read at `ef958ee9...`; root `AGENTS.md`, `opencode.json`, and `.opencode/` are absent. This is correct: mirror master must not receive project-only policy files.
- **Mage master** was freshly read at `798b75e5...`; root `AGENTS.md`, `opencode.json`, and `.opencode/` are absent. This is correct for the same reason.
- Both engine forks consume canonical policy through Foundry launcher injection and Lab repo profiles. Do not reintroduce fork-root policy copies.

## Failure and resume semantics
No automatic fallback is permitted when a Go quota/auth/catalog/upstream failure occurs. The run ends fail-closed. A later run may explicitly select any authorized profile and resume from the same branch + state + evidence. The repository does not decide which profile the operator should choose.

## Runtime activation blocker
Open PR #280 declares `sbmax/full-completion` ownership of `tools/foundry/launcher.py` and its tests. The current branch also changes those files. WSR27 therefore does not co-edit them.

PR #280 additionally owns several canonical governance documents. Until those surfaces are released/serialized, WSR27 records the target technical execution contract but does not create a conflicting canonical rewrite.

## Exact activation delta after ownership clears
1. Re-lock fresh Lab main HEAD/tree and active-owner map.
2. Integrate/reconcile the current launcher owner's changes first.
3. Replace the dual-executor constants with a data-driven four-profile registry.
4. Expand launcher validation to exactly the four authorized model/native-variant pairs.
5. Expand `opencode.json` allowlist/models atomically with launcher support.
6. Pin every child run and injected agent to the explicitly selected profile's exact model/native variant.
7. Preserve no-fallback behavior and existing secret/Git/worktree permissions.
8. Add hermetic tests for all four profiles across CPL/Forge/Mage injection.
9. Run an authenticated bounded smoke for every newly activated profile without exposing credentials.
10. Mark a newly added profile runtime `ACTIVE` only after its activation smoke and exact-head validation pass.
