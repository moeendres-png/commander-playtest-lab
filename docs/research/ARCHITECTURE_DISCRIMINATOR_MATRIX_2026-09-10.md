# ARCHITECTURE DISCRIMINATOR MATRIX — Commander Simulator Next (Interim Checkpoint 2026-09-10)

STATUS = INTERIM_CHECKPOINT
D1_D7_PROGRAM_COMPLETE = NO

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
`LEADING_ARCHITECTURE_HYPOTHESIS = FORGE-CENTRIC HYBRID`
`CONFIDENCE = PROVISIONAL`

Coordinator adjudication: ACCEPTED as interim checkpoint. NOT the final D1–D7 program
result (D1 unresolved; D2/D3 unexecuted; D5/D6 at requirement-card stage; D4 demoted;
D7 concluded as decision input only).
Date (UTC): 2026-09-10 · Produced by: OpenCode Go + opencode-go/muse-spark-1.3-contributor
Report-only commit; no implementation code; no governance change; no qualification
evidence altered.

---

## 1. Source-lock table (freshly verified 2026-09-10, supersedes stale SHAs)

| Item | Lock |
|---|---|
| CPL `main` (branch base) | HEAD `c391a7616df98f66249ce00790904eb3015b340d` / tree `5dbd3c5e8fe058db11abb583ac53612c60c61a8f` |
| PR #173 (mission/governance input only, unmerged) | OPEN, MERGEABLE, head `aa772f9f083cd1c0f50c81a819546688682121c2` |
| PR #172 (execution consolidation, unmerged) | OPEN, MERGEABLE, head `5f6ef8e8a6ced2cbc7a63cef1ba7b92623a8b79f` |
| CPL `ws48/forge-v1.0.5-successor-qualification` | `c8d6f97b93cf383ec2b481d96f6fb33103db4ddd` — `FORGE_SUCCESSOR_PROVIDER_QUALIFIED = NO` |
| CPL `ws49/xmage-v1.0.5-successor-qualification` | `7c3e3d2af474cbf9cdda6f9dd694f68e5cdb2c10` — `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = NO` |
| WS47 v1.0.5 contract (immutable) | freeze `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`, denominator **107**, bundle `631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01` |
| Forge baseline (WS48 binding) | `moeendres-png/forge` @ `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29ce4de31a964972461db2b48b4221e07f`, v2.0.15-SNAPSHOT |
| XMage baseline (WS49 binding) | `moeendres-png/mage` @ `0c1f455ea8c8fa48ab9d638ad5068ec242800428` / tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649` |
| phase_rs lock (WS-17 adjudication) | `phase-rs/phase` 0.66.0 @ `92c67b872c2a7f69c4a2069f0d0c3cb1b6b0d4c6` |
| Forge LICENSE blob | `e72bfddabc15be5718a7cc061ac10e47741d8219` (GPL-3.0, fetched verbatim) |

Historical vs successor lanes: current WS48/WS49 behavior credit is 0/107 and neither
successor is presently qualified. This does not erase older evidence (e.g. WS46 v1.0.4
diagnostic 88/107; WS45 strict no-request-echo PASS as provenance), but zero
historical runtime PASS is imported into the v1.0.5 successor lanes.

---

## 2. D1–D7 current status (with exact evidence classifications)

### D1 — Forge 2/3/4/5/6-player native smoke → UNRESOLVED (in progress, owned by general-n session)
- Experiment: (a) G48-07 fresh construction 107/107 PASS + G48-08 independent native readback 107/107 PASS, GH run `34263710979`, artifact `sha256:f320fbac…` — **RUNTIME_VERIFIED**; (b) behavior transcript probe v1.6 maps `PLAYER_COUNT_2P/3P` to native `mulliganKeepHand/chooseStartingPlayer`, `NATURAL_GAME_START` — executed, credit 0/107 — **CODE_DERIVED**, credit explicitly disclaimed in checkpoint proof block.
- Result: Forge constructs all 107 qualifier states natively; live-game per-count smoke (2P–6P) not at PASS. No 5P/6P evidence exists.
- Contradicted: "Forge cannot construct qualifier states" (falsified); "readback PASS ≈ behavior PASS" (disclaimed).
- Workstream effect: KEEP Forge as Rules-Core candidate; SIMPLIFY overlays into reusable harness only after PASS.
- Next: execute bounded native game-start smoke per count 2,3,4,5,6 on the frozen Forge lock with per-count artifacts. A 4P result never stands in for other counts.

### D2 — XMage Commander/multiplayer corpus reuse → UNRESOLVED (unexecuted)
- Inventory **CODE_DERIVED** (indicative counts, re-lock before use): 32,154 card implementation files; 1,819 card-test files; 80 multiplayer/commander test paths. Counts confer zero behavior credit.
- Experiment: none executed; corpus branch at main+infra commits with zero trials.
- Contradicted: nothing yet — neither reusability nor unusability has evidence.
- Workstream effect: KEEP XMage as donor candidate and Rules-Core contender.
- Next (per coordinator correction): start with **20 deliberately diverse Commander/multiplayer scenarios** against a fresh build of frozen `0c1f455e`. Expand toward 50 only if the first 20 do not resolve corpus-reuse leverage.

### D3 — Forge-script / card-import automation → UNRESOLVED (unexecuted)
- Structure **CODE_DERIVED**: `forge-gui/res/cardsfolder` a–z sharding + `rebalanced/` + `upcoming/` verified at the foundry branch.
- Experiment: none (no parser trial, no recursive count).
- Workstream effect: no change; future success SIMPLIFYs card authoring but never grants behavior credit.
- Next: recursive script count + parser trial on a random 100-script sample with failure taxonomy. Hard boundary: parse success ≠ card-behavior credit.

### D4 — phase.rs third-oracle reality check → DEMOTED
- Adjudication record `qualification/evidence/candidates/phase_rs.json` — **DIRECTLY_VERIFIED**.
- Result: `BLOCKED_ORACLE_AND_BYTE_EXACT_CR`; common RSP 1.1 runtime NOT_RUN (no adapter); AF08 FAIL preserved on direct Changeling-Commander semantics; AF00–AF07/AF09–AF11 UNKNOWN.
- Contradicted: "phase_rs is a drop-in third oracle" (falsified).
- Workstream effect: DEMOTE to watchlist; DELETE from active oracle set until remediation lands.
- Next: minimal RSP 1.1 adapter + Changeling-Commander remediation at a fresh lock, then rerun the blocking fixture family; drop permanently if remediation exceeds 2 sprints of the Forge/XMage path.

### D5 — Optimizer OSS replacement → UNRESOLVED (requirement-card stage)
- No OSS optimizer evaluated; custom Optimizer-v2/v3 surface exists but is unmeasured.
- Next: write the optimizer requirement card (paired comparison, ablation, holdout, sensitivity, constrained optimization, calibration-first, evidence-safe promotion), then paper-score 2–3 named OSS candidates. No code until the card exists.

### D6 — Execution/orchestration OSS replacement → UNRESOLVED (requirement-card stage)
- Current GH-Actions + OpenCode stack (PR #172 consolidation in flight, CLI v1.18.29) never benchmarked against OSS orchestrators; it is load-bearing for all other discriminators.
- Next: codify execution requirements (deterministic replay, content-addressed artifacts, multi-engine matrix, failure attribution), cost the current stack, then trial one OSS alternative on a single non-qualification workflow.

### D7 — License / topology analysis → CONCLUDED as decision input
- Texts **DIRECTLY_VERIFIED**: Forge GPL-3.0; mage MIT; phase_rs MIT OR Apache-2.0 (bundle-pinned blobs).
- `XMAGE_LICENSE_CLASS_ADVANTAGE = permissive MIT license with no modeled copyleft/network-source trigger from the license class itself; production packaging/SBOM/data/IP review remains required.`
- `FORGE_PRODUCTION_TOPOLOGY = TECHNICALLY_VIABLE / LEGAL_REVIEW_REQUIRED`. No Forge topology has been legally cleared. Viable technical topologies: (a) GPL-accepted Rules-Core component, (b) separate-process wrap behind the authoritative Decision/Observation seam, or (c) differential/test-corpus donor only. Embedding Forge into a non-GPL core without clearance is off the table.
- Topology consequences are **CODE_DERIVED** engineering analysis, not legal advice.
- Re-verify only if a candidate re-locks to a different license.

---

## 3. Leading hypothesis (provisional, not selected)

`LEADING_ARCHITECTURE_HYPOTHESIS = FORGE-CENTRIC HYBRID`
`CONFIDENCE = PROVISIONAL`
`PRODUCTION_PROVIDER = NOT SELECTED`

Forge authoritative Rules Core + thin authoritative Decision/Observation seam + XMage
as differential/test-corpus donor + external pilot + mature OSS execution +
mature OSS optimizer + tool-assisted Q6 closure.

- Support: Forge 107/107 native construction+readback (**RUNTIME_VERIFIED**); XMage donor corpus exists (inventory only); outcome-first policy permits it.
- Missing: all behavior PASS; D2/D3/D5/D6 experiments; per-count 2–5P conformance; `FORGE_PRODUCTION_TOPOLOGY` legal review.
- Standing: weakest credible leader — leads by construction evidence, not rules correctness.

## 4. Runner-up (live)

XMage-first: XMage authoritative Rules Core + same thin seam + Forge as differential donor.
- Case: `XMAGE_LICENSE_CLASS_ADVANTAGE` (no copyleft class trigger); 88/107 v1.0.4 diagnostic provenance; 32,154 native card implementations.
- Promotion trigger: D2 20-scenario sample showing high reuse with small adapter surface, or refusal of GPL propagation into the core.

## 5. Demoted / rejected / prohibited candidates

| Candidate | Verdict | Reason |
|---|---|---|
| phase_rs as third oracle | DEMOTED (re-admit on remediation) | D4: adapter missing + Changeling-Commander direct FAIL |
| Greenfield general Rules Core | DISFAVORED | Outcome-first: no evidence it beats reuse; zero code until Forge/XMage adjudicated infeasible |
| 4P-specialized architecture | PROHIBITED | Mission policy: 2–5P conformance mandatory, 4P benchmark-only |
| Internal-engine AI as pilot correctness | PROHIBITED as evidence | Explicitly barred |
| Reference parity / parser success as PASS | PROHIBITED as promotion | D3 boundary restated |

## 6. Stop-starting decisions

1. New 4P-specialized harnesses, schemas, or data models.
2. New greenfield Rules-Core implementation work.
3. Broad v1.0.4 qualification continuations (WS-46 superseded; WS-45 closed).
4. Historical successor-runtime PASS imports (zero-import mandate stands).
5. New custom optimizer or execution-framework builds before D5/D6 requirement cards.
6. Any Production Repository creation before Architecture Freeze.
7. Writes to branches/worktrees owned by other sessions.

## 7. Unresolved discriminators

- D1: per-count 2–6P Forge smoke (owner: general-n session).
- D2: 20-scenario XMage corpus sample, expand to 50 only if unresolved (owner: corpus session).
- D3: Forge script count + 100-parse trial.
- D5/D6: requirement cards + paper scoring.
- R-gates: behavior 0/107 both lanes; per-count 2–5P conformance zero; pilot/rules separation unexecuted at v1.0.5; RNG/replay tapes lack verified producers; GPL topology review pending; no third oracle; optimizer/execution unqualified.

## 8. Exact next qualification DAG

```
[done] Mission governance input (PR #173, unmerged) ─┬─> [P0] D1: Forge 2–6P smoke per-count
                                                     ├─> [P0] D2: XMage 20-scenario sample (→50 iff unresolved)
                                                     ├─> [P1] D3: script count + 100-parse trial
                                                     ├─> [P1] D5/D6: requirement cards + paper scoring
                                                     ├─> [P1] FORGE_PRODUCTION_TOPOLOGY legal review
                                                     └─> [P2] phase_rs remediate-or-drop (time-boxed)
[P0 all] ──> [P2] WS48/WS49 v1.0.5 terminal adjudication
   ──> [P3] Leader confirmation on behavior + license evidence
   ──> [P3] Per-count 2–5P conformance on confirmed core
   ──> [P4] Serial cross-qualification + project reconciliation
   ──> [P5] Architecture Freeze adjudication (Coordinator) — NOT before all above
```

Parallelism: D1 ∥ D2 ∥ D3 ∥ D5/D6-cards. No new branches without Coordinator assignment.

---

*TURN_STATUS at matrix production: INTERRUPTED · TASK_COMPLETE = NO · Evidence classes: DIRECTLY_VERIFIED / RUNTIME_VERIFIED / CODE_DERIVED / UNKNOWN only; SYNTHETIC used nowhere.*
