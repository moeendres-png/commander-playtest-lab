# Candidate Qualification Roadmap — Commander Simulator Next (2026-09-10)

Parent analysis: `docs/research/D1_D7_FINAL_ARCHITECTURE_RECONCILIATION_2026-09-10.md`
Decision matrix: `docs/research/ARCHITECTURE_DISCRIMINATOR_MATRIX_2026-09-10.md`
Evidence ledger: `research/d1-d7-final-reconciliation/evidence-index.json`

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
No Production Repository is created by anything in this roadmap.

---

## 1. Gate sequence (shortest evidence-safe route; see parent report §§13–14 for the full table)

1. **Recommendation inputs:** this reconciliation + PRIMARY discriminator result (§4, Task 1 below).
2. **Selection inputs:** secondary-gate resolution + HUMAN legal-topology review + Vraska queue acknowledgment.
3. **Freeze inputs:** selected-core Full107 adjudication + 2–5P per-count conformance + hidden-info leak audit + RNG/replay proof + restore-path disposition + WS47 frozen contract.
4. **Pre-implementation inputs:** hardened-runner adoption + sequence-harness implementation + Q6 scaffolding pipeline operational.
5. **Post-Freeze:** runner-up regression, Q6 completion, additive sampler experiment, pilot strength, N-generalization, scale-out on need.

---

## 2. Ready-to-send OpenCode assignments (drafted, NOT executed; Coordinator assigns)

### TASK 1 — FORGE PRODUCTION VERTICAL SLICE (primary discriminator)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: NEW isolated worktree (Coordinator-assigned path; must NOT reuse `/home/moeen/code/commander-ws48` or any active worktree)
- Branch: NEW `ws50/forge-decision-sequence-slice-*` (Coordinator-assigned name; must NOT write `ws48/forge-v1.0.5-successor-qualification`)
- Source Lock: WS48 `10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d` (base) · WS47 freeze `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` (denominator/records only; frozen-state restore NOT required — native construction per §7 decision) · Forge pin `66caae16015bd403bc0a52fa6689afb5508f74d0` · parent analysis (this reconciliation + matrix + ledger)
- Objective: Traverse complete authoritative native decision sequences (TARGET_SELECTION → MANA_PAYMENT → attackers → …) in a natively constructed 4-player real-Commander game at the R1e headless Token-DB path, with an external pilot selecting only among engine-offered options, per-frame principal-scoped observations, and seed + frame-journal replay of the traversed prefix. Attack the three open surfaces (declare_attacker, discardToMaximumHandSize, BLOCK-4 restore/adapter) strictly in production-path order.
- Authority: Rules Core alone determines legality/costs/mana/stack/targets/combat/triggers/replacement/layers/SBA/zones/copy-control/Commander/multiplayer/RNG. `TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`; genuine Rules/evidence-policy/architecture/scope/provider/freeze questions are AUTHORITY_GATEs for Sol High.
- In Scope: native 4P Commander construction; sequence-frame transport (unique-match discipline); fail-closed unsupported kinds; observation capture per frame; replay proof of traversed prefix; HARNESS-vs-ENGINE failure classification with log evidence; terminal PASS/FAIL/UNKNOWN per traversed cast (recommendation-grade evidence, NOT behavior credit).
- Out of Scope: behavior-credit awards; Full107; frozen-state-restore qualification (fail-closed acceptable, replay-resume documented); Q6 reruns; WS47 mutation; other branches/worktrees; provider/Freeze claims; production implementation.
- Ownership: sole-writer session on the new branch/worktree; verify via process-level CWD audit + `tools/foundry/worktree_inventory.py` before writing.
- Dependencies: WS48 `10a7f8f6` (read base; do not move that branch); WS47 immutable contract; §6 sequence-harness design in parent report.
- Hard Gates: zero fallback legality (no first/random/default/AI/GUI/silent-skip/parent-filtering/fabrication/injection/resolution-shortcut); engine-side vs harness-side classification evidenced per stall (D4c precedent: harness gaps do not weaken the engine); replay divergence ⇒ FAIL; credit stays 0/107.
- Forbidden Shortcuts: all production-reachable shortcuts in §2 of the assignment lineage; requested-option filtering that reconstructs legality; manual outcome injection.
- Evidence Requirements: per-cast frame journals + terminal verdicts; seed + replay artifacts; observation captures; failure-class log exhibits; evidence classes per §3 semantics (UNKNOWN != PASS).
- Persistence: `.foundry/WORKSTREAM_STATE.yaml` per session; checkpoint commits on the task branch; sealed handoff.
- Stop Conditions: engine-side stall on 2+ distinct surfaces (report R2 + trigger secondary gate, do not grind); scope COMPLETE (traversal verdict reached); AUTHORITY_GATE; another owner's surface; destructive/remote gates.
- Final Handoff: Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN; traversal verdict with success/failure interpretation per §5 of parent report; R2 assessment; Exact Next Action.
- Route: **OPENCODE_MUSE_XHIGH** (engine-vs-harness causality adjudication on live paths).

### TASK 2 — SEQUENCE-HARNESS + Q6 SCAFFOLDING IMPLEMENTATION

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree/Branch: NEW isolated pair (Coordinator-assigned; disjoint from Task 1 and all active worktrees)
- Source Lock: origin/main at assignment time (record SHA/tree) · parent report §§6/8 designs · D2 `bf2c4711` + D3 `a766f900` tooling patterns · `tools/foundry/cluster_failures.py` (reuse) · WS33 gold-standard books (read-only calibration reference)
- Objective: Implement the authoritative decision-sequence state machine (§6 design) as qualification harness machinery plus the Q6 scaffolding pipeline (D3 intake/parser-equivalent clean-room tooling, D2-style corpus adaptation with valueless checklists, provenance blocks, frame-kind pre-tagging, witness/replay utilities, failure clustering, manual-review + rules-adjudication queues). Scaffolding only: the pipeline must be structurally incapable of emitting behavior PASS (no expected-value synthesis; parity never promoted; silent-support surprises routed to FAIL).
- Authority/Ownership/Dependencies/Hard Gates/Forbidden Shortcuts/Evidence/Persistence/Stops: same pattern as Task 1, scoped to harness/tooling: no engine-behavior claims; no coverage promotion (`COVERAGE_PROMOTION=FALSE`); no canonical-book mutation; 884 denominator untouched; no qualification reruns for reassurance.
- Final Handoff: implemented surface inventory; PASS-incapability argument (structural, reviewed); queue operating procedure; integration points for Task 1 / Full107; Exact Next Action.
- Route: **OPENCODE_MUSE_HIGH** (well-scoped tooling implementation from a fixed design).

### TASK 3 — XMAGE BOUNDED DECISION-SEQUENCE MIRROR (PARKED; TRIGGER-GATED)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree/Branch: NEW isolated pair (Coordinator-assigned; must NOT write `ws49/xmage-v1.0.5-native-remediation`)
- Source Lock: WS49 `1cd1276524cf60dcb2e5f84276b57dc45a5c8bd5` (Phases 0–5 already implemented) · XMage pin `0c1f455ea8c8fa48ab9d638ad5068ec242800428` · Task 1's harness contract (same frame semantics) · WS47 freeze (denominator only)
- Objective (ONLY when a trigger fires): CI-build the bridge at the pin and run the SAME bounded decision-sequence traversal as Task 1 against XMage, to produce the live runner-up data point for R1/R2/R3 adjudication. NOT a second Full107; NOT new remediation (report gaps as findings, do not re-remediate without fresh authority).
- Triggers (Coordinator verifies one before start): (a) Task 1 fails closed on engine-side evidence; (b) Task 1 succeeds but margin judged too thin for selection; (c) legal-topology review forces re-ranking. Non-trigger ⇒ stays parked (NOT_RUN is the correct state).
- Authority/Ownership/Hard Gates/Forbidden Shortcuts/Evidence/Persistence/Stops: same pattern as Task 1, XMage-side: native-option authority (R-c/R-g), observation-gating (R-h), no global-seed completeness claim (Phase 5 boundary), bridge-runtime UNKNOWN until built, per-channel RNG attribution required for any RNG claim.
- Final Handoff: mirror verdict (traversal comparison vs Task 1, same frame taxonomy); ranking implication (R1/R2 assessed, not decided — decision stays Coordinator); Exact Next Action.
- Route: **OPENCODE_MUSE_XHIGH** (cross-candidate causality adjudication). Do NOT route to Astra/Work.

---

## 3. Next ten actions (strict dependency/priority order; exactly one owner each)

1. Adjudicate this reconciliation; authorize Task 1 (+ park Task 3 with triggers; schedule legal review) — **SOL_HIGH**
2. Production-topology legal review (Forge GPL / XMage MIT / Manabrew AGPL postures; R3) — **HUMAN_AUTHORITY**
3. Execute Task 1: Forge production vertical slice (primary discriminator) — **OPENCODE_MUSE_XHIGH**
4. Execute Task 3 IFF a trigger fires (XMage bounded mirror) — **OPENCODE_MUSE_XHIGH**
5. Execute Task 2: sequence-harness + Q6 scaffolding (from §§6/12 designs) — **OPENCODE_MUSE_HIGH**
6. Selected-core Full107 adjudicated run (post-selection conformance) — **OPENCODE_MUSE_XHIGH**
7. Per-count 2–5P conformance + hidden-info leak audit + RNG/replay proof + restore disposition — **OPENCODE_MUSE_XHIGH**
8. Vraska payment-leg re-transport (registered wiring, payment-choice intent) — **OPENCODE_MUSE_HIGH**
9. Shared hardened-runner adoption (D6 precondition chain) — **OPENCODE_MUSE_HIGH**
10. Provider-selection + Architecture-Freeze adjudication on the §§13–14 bundle — **SOL_HIGH**

No busywork is listed. RL/pilot-strength, lab N-generalization, runner-up regression, and scale-out follow Freeze and are therefore not in the ten.
