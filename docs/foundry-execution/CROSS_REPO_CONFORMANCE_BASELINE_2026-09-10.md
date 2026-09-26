# Cross-Repo Conformance Baseline — 2026-09-10 (Checkpoint A)

Source lock: `moeendres-png/commander-playtest-lab` @
`c162871ba416c338d37f83a44fbd5b054e79ca0e`
(tree `b75a51d3…`), branch
`project/opencode-muse-cross-repo-hardening-v2-20260910`, clean tree.
Machine-readable ledger: `.foundry/conformance-ledger-2026-09-10.json`.

## 1. Audit surfaces (verified 2026-09-10, isolated HOME for experiments)

- `AUDIT_BASE_SHA=c162871b…`, `AUDIT_BASE_TREE=b75a51d3…` (origin/main, fetched).
- `CLI_INSTALLED_VERSION=1.18.30`, `CLI_PROJECT_PIN=1.18.29` (workflow asserts exact pin).
- `GLOBAL_CONFIG_SURFACE`: `~/.config/opencode/opencode.json` carries provider
  timeouts only — no model, no permissions, no instructions. Clean.
- `PROJECT_CONFIG_SURFACE`: root `opencode.json` resolves via
  `opencode debug config` with model lock, share disabled, full permission map.
- `ACTIVE_WORKTREES`: 16 CPL worktrees inventoried; WS50
  (`ws50/forge-decision-sequence-slice-20260910`, CPL remote) and Task 2B
  (`qualification/q6-capability-curation-20260910`, CPL remote) live — excluded
  surfaces, not to be touched. Mage clones (`mage-d3q6` @ `a766f9006…`,
  `mage-ws33*`) are `moeendres-png/mage` checkouts. No local Forge engine clone.
- `ACTIVE_OPENCODE_PROCESSES`: WS50 TUI (CWD ws50 worktree), Task 2B TUI (CWD q6
  worktree), and one `opencode --auto` with CWD=this worktree (own session).
  Same-CWD detection does not exist — this is the SINGLE_WRITER gap, not a stop:
  the occupying process is this workstream's own execution.

## 2. Current OpenCode capability verification (installed 1.18.30)

DIRECTLY_VERIFIED via isolated-`HOME` experiments (no real global config touched):

1. `--auto` = "auto-approve permissions that are not explicitly denied
   (dangerous!)". ASK auto-approves under `--auto`; only `deny` is a hard
   boundary. SAFE_AUTO=FAIL stands on platform fact, not suspicion.
2. Config precedence (official docs + reproduced): remote < global <
   `OPENCODE_CONFIG` < project `opencode.json` < `.opencode` dirs <
   `OPENCODE_CONFIG_CONTENT` < managed. Project dir config beats injected
   `OPENCODE_CONFIG`; inline `OPENCODE_CONFIG_CONTENT` beats project config and
   deep-merges (verified: added deny rule preserved sibling rules; overrode model).
3. `OPENCODE_CONFIG_DIR` (docs-sourced, experiment pending): extra
   agents/commands/skills directory loading after `.opencode` dirs.
4. `AGENTS.md` discovery (official docs): project-root file auto-loads for any
   CWD inside the project; global file also loads; sources are **combined,
   conflicts unresolved**. A stale engine-local `AGENTS.md` cannot be overridden
   by cleaner policy — it must be detected and failed closed. `instructions[]`
   arrays are NOT merged (closest config wins) and, on the V2 path, do not
   resolve into model instructions at all — CLI requalification must pin down
   which behavior 1.18.29 exhibits.
5. `OPENCODE_DISABLE_PROJECT_CONFIG=1` skips project `AGENTS.md` discovery
   (docs-sourced, experiment pending) — candidate stale-routing suppressor.
6. Telemetry sources exist: `opencode stats` (tokens/cost overview),
   `opencode export <sessionID>` (session JSON), `opencode session list`,
   `opencode run --format json --variant --agent --dir --session` (bounded
   non-interactive runs the launcher can drive and observe).
7. Invalid config fails closed at startup (wrong `share` value aborted
   `debug config` under isolated HOME).

## 3. Requirement ledger (summary; detail in JSON)

- PASS (5): `MODEL_LOCK`, `HIGH_XHIGH_ROUTING`, `ENGINE_PIN_INTEGRITY`,
  `FAILURE_CLUSTERING`, `ARTIFACT_EVIDENCE_AUTOMATION`.
- PARTIAL (6): `DEEP_RESEARCH_REQUIREMENTS`, `CPL_CONTROL_PLANE`,
  `SOURCE_LOCK_AUTOMATION`, `STATE_RESUMABILITY`, `SELECTIVE_TEST_TOOLING`,
  `HIGH_XHIGH_BENCHMARK` (spec only, NOT_RUN), `COMPACTION_STRATEGY`
  (hook intentionally deferred; Git/state authority).
- FAIL (7): `MAGE_EXECUTION_PROFILE`, `FORGE_EXECUTION_PROFILE`,
  `CROSS_REPO_POLICY_DRIFT_CHECK`, `SAFE_AUTO`, `SINGLE_WRITER_ENFORCEMENT`,
  `WORKSTREAM_LAUNCHER`, `METRICS_AUTOCAPTURE`, `STALE_ROUTING`.
- No `UNSUPPORTED_BY_CURRENT_PLATFORM` claimed yet; platform-limitation verdicts
  are deferred to implementation checkpoints with evidence.

## 4. Architecture direction chosen (to be validated in Checkpoint D)

Central injection without engine-tree mutation, using only supported mechanisms:

- Launcher sets `OPENCODE_CONFIG_CONTENT` (canonical model/permission lock,
  beats engine-local project config) + `OPENCODE_CONFIG_DIR` (canonical
  agents/skills) + isolated-HOME or global `AGENTS.md` overlay for canonical
  policy text.
- Stale engine-local `AGENTS.md` handled by drift check failing closed
  (possibly with `OPENCODE_DISABLE_PROJECT_CONFIG=1` for engine CWDs after
  verification that canonical policy still reaches the model).
- Writer lock via `flock(2)` held for the OpenCode process lifetime.
- Checkpoint push via narrow `foundry-safe-push` allowlist wrapper, never
  generic `git push` from the execution plane.

## 5. Engine pin integrity (baseline)

No engine commits by this workstream. Mage `mage-d3q6` HEAD `a766f9006…`
recorded. Forge engine remote-only locally. WS50/Task-2B surfaces untouched.
