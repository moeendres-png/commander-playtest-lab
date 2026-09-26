# Cross-Repo Muse Operating Layer — Qualification Record 2026-09-10

Source lock: `moeendres-png/commander-playtest-lab` @
`c162871ba416c338d37f83a44fbd5b054e79ca0e` (tree `b75a51d3`),
branch `project/opencode-muse-cross-repo-hardening-v2-20260910`.
Baseline ledger: `.foundry/conformance-ledger-2026-09-10.json`
(Checkpoint A: 5 PASS / 7 PARTIAL / 8 FAIL). Final ledger: same file,
`checkpoint: G-FINAL`.

## 1. Architecture chosen (validated, not hypothesized)

Central injection without engine-tree mutation, using only supported mechanisms
(all verified against installed CLI 1.18.30 AND pinned CLI 1.18.29):

- `OPENCODE_CONFIG_CONTENT` — canonical model/permission lock; deep-merges and
  beats engine-local project config (experimentally proven).
- `OPENCODE_CONFIG_DIR` — snapshot of canonical agents/skills; loads after repo
  `.opencode` dirs (live resolution proven: model lock + push deny + canonical
  skills in an engine-like CWD).
- `OPENCODE_DISABLE_PROJECT_CONFIG=1` — only under explicit
  `--allow-suppressed-routing`; keeps stale engine `AGENTS.md` out at the cost
  of project discovery (logged degradation, never silent).
- Engine-local `AGENTS.md` cannot be overridden (sources combine, conflicts
  unresolved — official docs): drift check fails closed instead.
- Writer lock: kernel `flock`, XDG-anchored, held across the OpenCode child by
  the launcher. Metadata is diagnostic-only; stale bytes can never brick.
- Checkpoint push: narrow `safe_push` (no passthrough flags by construction) +
  branch-scoped pre-push hook (L3-partial) + remote branch protection
  (human-external recommendation).

## 2. Evidence per checkpoint (all local commits; see git log)

- A (50900f6d): source lock + read-first ledger + isolated-HOME CLI verification.
- B (b46aa5f6 + 968bb0fb): `writer_lock.py` (9 real-process concurrency tests:
  first-wins, second-refused, cross-worktree OK, SIGKILL release, stale-metadata
  survival, symlink-alias canonicalization, CWD scan incl. argv0-shape
  emulation, reader semantics) + state schema 2.0 (split identity, migration
  with zero fabricated credit, ancestry gates, CHECKPOINT_CLEAN termination —
  12 tests). Live reproduction: scan finds PID 59205 (`opencode --auto`, CWD =
  this worktree), invisible to the old inventory — the PR172 defect, now guarded
  (launcher refused the live tree until explicit allowance).
- C (a121896f + 4946aa73): threat model doc; 60-pattern deny hardening incl.
  `gh api` write-methods and pipe-to-shell; 72-probe battery against
  CLI-resolved rules (all destructive direct shapes DENIED; residuals
  BYPASSABLE/INSTRUCTION_ONLY declared); `safe_push` (15 adversarial tests on
  real file remotes + real lock ancestry: main/force/detached/dirty/forged/
  wrong-remote/non-FF/null-validated/rewritten rejected with remote untouched).
- D (9af7ea47 + 557f7339 + 1aea2f6f): cpl/mage/forge profiles (engine pins
  recorded); drift checker failing closed live on mage-d3q6
  (SUPERSEDED_BUT_REACHABLE WS33 AGENTS.md); bootstrap gate (BOOTSTRAP_PASS);
  launcher (init/launch/hold-across-exec proven by a stub child that verifies
  injection env AND verifies the lock is held; telemetry start/end records;
  branch-scoped hook blocks raw push, admits safe_push).
- E (e9414c00 + 1b70436e): provenance-classified metrics; `session_stats.py`
  over real 1.18.30 export shape (turns/tool-counts/tokens/cost AUTOCAPTURED;
  compaction count UNAVAILABLE, never inferred; raw exports LOCAL_ONLY);
  safe_push `--metrics`; deterministic test-impact mapper (contract override
  built in); two reconciled skills (component-change-review,
  rules-authority-escalation — routes to Sol High, never adjudicates Rules).
- F (61fb7120 + 2043c327): 1.18.29 isolated-binary comparison — zero verdict
  drift on 72 probes; .30 changes immaterial → CLI_UPGRADE_CANDIDATE=NO,
  CLI_PIN_CHANGE=NOT_AUTHORIZED; compaction keys identical; declarative
  session-compacting hook absent (unknown keys dropped) →
  COMPACTION_HOOK=INTENTIONALLY_DEFERRED.
- G (93d0c303 + this record): redaction battery (URL userinfo, secret-shaped
  session content, bundle secret-scan, plan-print hygiene); stale-routing sweep
  (CPL: zero production-reachable; engine: detected + failed closed);
  engine-pin reverification (below); full suite 117/117 + ruff + format +
  diff-check.

## 3. Final readiness matrix

| Requirement | Final | Basis |
|---|---|---|
| CPL_CONTROL_PLANE | PASS | config/agents/skills/tools/docs/launcher/profiles/drift/bootstrap/telemetry validated |
| MAGE_EXECUTION_PROFILE | PARTIAL | profile + drift + smoke proven; writer launch gated until stale file resolved (human-external) |
| FORGE_EXECUTION_PROFILE | PARTIAL | same; engine remote-only locally; WS50 covered by CPL policy |
| CROSS_REPO_POLICY_DRIFT_CHECK | PASS | checker + 8 tests + live mage proof |
| MODEL_LOCK / HIGH_XHIGH_ROUTING | PASS | resolved-config + battery proof on both CLIs |
| SAFE_AUTO | PARTIAL | direct shapes DENIED (72 probes, both CLIs); interpreter-bypass residuals R1–R3 declared, monitored, human-reviewed (platform limitation, not a workaround) |
| SINGLE_WRITER_ENFORCEMENT | PASS | 9 concurrency tests + live same-CWD reproduction now guarded |
| SOURCE_LOCK_AUTOMATION | PASS | BOOTSTRAP_PASS gate |
| WORKSTREAM_LAUNCHER | PASS | init/launch/hold/exec/telemetry proven; 3-profile smoke green |
| STATE_RESUMABILITY | PASS | 2.0 semantics + migration + CHECKPOINT_CLEAN + continuation skill |
| ARTIFACT_EVIDENCE_AUTOMATION | PASS | pre-existing, retained, green |
| SELECTIVE_TEST_TOOLING | PASS | deterministic mapper, contract override built in |
| FAILURE_CLUSTERING | PASS | pre-existing, retained, green |
| METRICS_AUTOCAPTURE | PASS | launcher/push/export autocapture + provenance; unavailable honestly marked |
| HIGH_XHIGH_BENCHMARK | PARTIAL | harness + spec + telemetry ready; NOT_RUN by design (deferred, not skipped) |
| COMPACTION_STRATEGY | PARTIAL | Git/state authority + deferred hook with verified reason; live loss-recovery drill not run |
| STALE_ROUTING | PARTIAL | CPL zero reachable; engine stale failed closed; file remediation human-external |
| ENGINE_PIN_INTEGRITY | PASS | PRESERVED (before/after below) |
| DEEP_RESEARCH_REQUIREMENTS | PARTIAL | all themes addressed; benchmark + hook intentionally deferred |
| **OPENCODE_MUSE_CROSS_REPO_READINESS** | **PARTIAL** | every mechanism proven; engine-side file remediation + benchmark execution remain |

## 4. Engine pin integrity (before → after, 2026-09-10)

- mage `mage-d3q6` HEAD: `a766f9006` → `a766f9006` (unchanged).
- mage remote HEAD: `ff09f542` → `ff09f542` (unchanged).
- forge remote HEAD: `8a41f4a1` → `8a41f4a1` (unchanged).
- WS50 worktree: `e636e705` → `e636e705` (untouched).
- Task 2B worktree: `a33d5d97` → `82d08f28` (advanced by its owner; external drift, not this workstream).
- No commit created in any engine repository by this workstream. This
  workstream's code lives in CPL only. `ENGINE_PIN_INTEGRITY = PRESERVED`.

## 5. Stale routing disposition

- CPL tree: Codex/Terra/Luna mentions exist ONLY in
  `GOVERNANCE_SUPERSESSION.md` (historical record) and drift-marker data —
  HISTORICAL_NONREACHABLE / detection signatures. Reachable surfaces (root
  AGENTS.md, opencode.json, agents, skills, `instructions`-referenced routing
  doc) are canonical. `STALE_ROUTING = ZERO_PRODUCTION_REACHABLE` inside CPL.
- Engine side: mage WS33 root AGENTS.md is SUPERSEDED_BUT_REACHABLE → drift
  FAIL → launcher refuses unattended start. Remediation (supersede/remove the
  stale file) is human-external; recommendations only, no engine mutation
  performed. Remote PR closure out of scope.

## 6. Declarations

- `SIMULATOR_SEMANTIC_IMPACT = NONE`
- `BEHAVIOR_CREDIT_CHANGE = 0`
- `COVERAGE_PROMOTION = FALSE`
- `PRODUCTION_PROVIDER = NOT SELECTED`
- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `PRODUCTION_REPOSITORY = NOT CREATED`
- `CLI_UPGRADE_CANDIDATE = NO`
- `CLI_PIN_CHANGE = NOT_AUTHORIZED`
- `HIGH_XHIGH_BENCHMARK = NOT_RUN` (harness ready; execution deferred)
- `COMPACTION_HOOK = INTENTIONALLY_DEFERRED`
- Push policy: no `git push` was used in this workstream until the final
  checkpoint, which goes exclusively through the validated safe-push path
  (narrow API, ancestor-held lock, branch-scoped hook armed).
