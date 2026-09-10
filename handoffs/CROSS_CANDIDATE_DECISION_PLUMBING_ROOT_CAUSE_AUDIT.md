# TASK SPECIFICATION — CROSS-CANDIDATE-DECISION-PLUMBING-ROOT-CAUSE-AUDIT

Intended worker: OpenCode Go + `opencode-go/muse-spark-1.3-contributor` at `xhigh`
effort (evidence-based escalation: ambiguous engine-vs-adapter-vs-harness causality).
Single primary workstream. Do not execute inside any other workstream.

## Source Lock (freshly reverified 2026-09-10, DIRECTLY_VERIFIED via git ls-remote)

- Repository: `moeendres-png/commander-playtest-lab`
- Forge branch `ws48/forge-v1.0.5-successor-qualification`:
  HEAD `0799c008313f0dc97264090b4b4141be3dbfbffd`
  TREE `c237c646df4e29337a140f935b40c5fdb29abe42`
  (local and origin agree; Coordinator-observed `5889ab8c899daccbee4529074287c036ddaa174a`
  is an ancestor commit in this branch history)
- XMage branch `ws49/xmage-v1.0.5-successor-qualification`:
  HEAD `925d21a900dc769453f712f05b28c31ffd330a00`
  TREE `5ec4c515908b7f57943a7c41b78f3f111a365f8e`
  (local and origin agree; Coordinator-observed `44bff91a9cfa1a644b21b2f0b055f45fe5e07c07`
  predates this HEAD — reverify which commit it was before citing it)
- WS47 contract pin (immutable, from WS49 `WS49_SOURCE_LOCK.json` and WS48
  `WS48_CHECKPOINT_01_PREFLIGHT_PASS.json`, both agreeing):
  freeze commit `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`,
  freeze tree `f596c54d2cb229b9827c6c94a278175e8312c65c`,
  namespace `qualification/ws47` tree `12af73695c801a42a0193ee895d5fc0843d16b0c`,
  contract `commander-lab.semantic-fixture-materialization/1.0.5`,
  materialization SHA-256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`,
  bundle digest `631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01`,
  provider denominator 107
- Forge engine pin: commit `66caae16015bd403bc0a52fa6689afb5508f74d0`,
  tree `40fc8f29ce4de31a964972461db2b48b4221e07f`, version `2.0.15-SNAPSHOT`
- XMage engine pin: repo `moeendres-png/mage`,
  branch `foundry/ws39-commander-history-state-restore`,
  commit `0c1f455ea8c8fa48ab9d638ad5068ec242800428`,
  tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
- Reference run/artifact IDs (Coordinator-observed, NOT independently reverified —
  treat run status as UNKNOWN until you fetch it live):
  WS49 Full107 run `34408669945` (workflow reported completed/success; sealed
  Behavior artifact reportedly `0/107 Behavior Credit` — this does NOT mean XMage
  Engine FAIL); WS48 preflight run `34242094044`, job `102114587925`,
  artifact `10062572692` (`sha256:8143a745…fca3b69`).
- Governance base available on main-line successor branch
  `project/opencode-execution-system-consolidation-20260910` (AGENTS.md,
  opencode.json HIGH default, agents, skills, `tools/foundry/`); rebase or cherry-pick
  only the execution-system files, never WS48/WS49 semantics.
- Live-worktree caveat (2026-09-10): the local WS48 worktree
  (`/home/moeen/code/commander-ws48`) reported HEAD `9b1d457a` while the branch ref
  and origin both sat at `0799c008` — active work is in flight there. Reverify both
  branch refs and worktree HEADs before touching anything; the locks above are
  origin-verified, not worktree-verified.

## Objective

Trace the exact decision-plumbing chain on both candidates and classify every
break without reconstructing legality:

```text
Rules Engine
    ↓
authoritative legal Decision Options
    ↓
provider adapter
    ↓
canonical Decision Request
    ↓
fixture/pilot discretionary selection
    ↓
provider adapter
    ↓
natural engine continuation
```

Determine, per break: ENGINE_DEFECT, PROVIDER_ADAPTER_DEFECT, HARNESS_DEFECT,
FIXTURE_DEFECT, INFRASTRUCTURE_DEFECT, UPSTREAM_DEFECT, or UNKNOWN. Forge's
Decision/ability-routing blockers are not automatically Forge semantic defects;
the WS49 `0/107 Behavior Credit` seal is not automatically XMage Engine FAIL.
Probable categories include harness, adapter, fixture, engine, infrastructure, UNKNOWN.

## In Scope

- Read-only tracing of both branches at the locked HEADs above (or newer HEADs after
  explicit Source-Lock re-verification with recorded delta).
- Decision-Option emission points, adapter translation layers, canonical Decision
  Request schemas, fixture/pilot selection logic, and engine-continuation call sites.
- Live re-fetch of run `34408669945` status, jobs, and sealed artifacts.
- Minimal reproduction probes that do not alter provider, bridge, fixture, or engine semantics.
- Failure records in the canonical classes via `tools/foundry/cluster_failures.py`.

## Out of Scope

- Modifying provider behavior implementations, engine-bridge semantics, WS47 fixture
  semantics, WS48/WS49 qualification logic, or any engine source.
- Granting or revoking runtime credit, Architecture Freeze, or provider selection.
- Rewriting historical evidence or rerunning full campaigns for reassurance.

## Ownership and Dependencies

- Owns: a new audit branch and worktree (one workstream ↔ one branch ↔ one worktree),
  plus read-only inspection of the locked WS48/WS49 checkouts.
- Must not disturb the active WS48/WS49 worktrees, branches, or in-progress runs.
- Depends on: this handoff, live GitHub run/artifact state, exact engine pins above.

## Hard Gates

- Rules Authority preserved: no second hidden Rules Engine, no fallback legality.
- Unsupported production-reachable paths fail closed; no first/random/default/AI/GUI/
  silent-skip/parent fallbacks introduced by probes.
- UNKNOWN stays UNKNOWN; no credit imported from historical or predecessor artifacts.
- Every classification cites exact file/line/commit/run/artifact evidence.

## Forbidden Shortcuts

Same as `AGENTS.md` §2 plus: no requested-option filtering that reconstructs
legality; no manual outcome injection; no construction/parsing-only substitute for
runtime evidence; no equating green workflow with Qualification PASS.

## Evidence Requirements

- Sealed manifest per candidate: source SHA/tree, engine pin, commands, run/job/
  artifact IDs, artifact hashes, per-break classification with evidence pointers.
- Missing or unfetched evidence reported as UNKNOWN or NOT_RUN, never assumed.

## Stop Conditions

Stop only when every identified break is classified with cited evidence, or when a
genuine terminal blocker is proven (irreconcilable Source Lock, owner conflict,
Sol/Human authority requirement, destructive-consent requirement). Remediable
probe failures are diagnostic, not terminal.

## Persistence

After each validated milestone: coherent tree, scoped validation, state-file update,
focused local commit. End with the full handoff sections from `AGENTS.md` §13.

## Final Handoff

Source Lock; Work Completed; New Findings; Changes; Tests/Evidence with
classifications; PASS/FAIL/UNKNOWN per break; Remaining Blockers; Outputs;
Dependencies Unblocked; Exact Next Action (expected: targeted remediation contracts
per classified defect, or escalation to Sol High for Rules adjudication).
