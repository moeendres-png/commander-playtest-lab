# D1–D7 Final Architecture Reconciliation — Commander Simulator Next

Date (UTC): 2026-09-10 · Execution: OpenCode Go + `opencode-go/muse-spark-1.3-contributor` · Effort: XHIGH
Mode: READ-FIRST / ARCHITECTURE ADJUDICATION / RESEARCH PERSISTENCE
Branch: `research/d1-d7-final-architecture-reconciliation-20260910` (research/documentation only)

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`

This report answers: "What is now the shortest evidence-safe path from the current
project state to a trustworthy, maintainable, real-deck, full-rules Commander simulator,
and which Rules-Core architecture should be taken into Candidate Qualification next?"

No engine, workstream, harness, optimizer, execution framework, or prior investment has
incumbency protection in this adjudication. Rules Correctness dominates elegance,
performance, sunk cost, and convenience. Behavior credit anywhere in this report is
exactly 0 unless a cited qualification record states otherwise — and none does:
both successor lanes stand at behavior 0/107.

Companion outputs (same workstream):
- `research/d1-d7-final-reconciliation/evidence-index.json` — machine-readable evidence ledger (13 inputs; Checkpoint A, commit `81949a1d`)
- `docs/research/ARCHITECTURE_DISCRIMINATOR_MATRIX_2026-09-10.md` — superseding decision matrix
- `docs/research/CANDIDATE_QUALIFICATION_ROADMAP_2026-09-10.md` — qualification roadmap, ready-to-send workstreams, next ten actions

---

## 1. Source lock (freshly verified; outranks all expectations in the assignment)

- Repository: `moeendres-png/commander-playtest-lab`; origin verified.
- Branch/worktree: `research/d1-d7-final-architecture-reconciliation-20260910` @ `/home/moeen/code/d1-d7-final-architecture-reconciliation-20260910`.
- HEAD == origin/main == `c162871ba416c338d37f83a44fbd5b054e79ca0e` (post-PR172 merge; verified post-fetch 2026-09-10T04:43:56Z); tree `b75a51d3326f502f33f0af2ce5d897ac89d60cc5`; worktree clean.
- PR172 commit `454f114a9f7a612a34dd797c87338d2cdd329843` is an ancestor of HEAD and of origin/main: YES (both).
- Exclusive writer audit: exactly one OpenCode process (PID 34228) holds this worktree as CWD; `tools/foundry/worktree_inventory.py` reports `duplicate_writers: []`. Other project sessions exist only on disjoint worktrees/branches. No FAIL-CLOSED trigger.
- Engine-pin provenance note (applies everywhere below): Forge/XMage pins are commits in the `moeendres-png/forge` / `moeendres-png/mage` forks, whose objects are absent from this clone (`git cat-file -e` negative, as expected). Pin values are therefore recorded as REPORT_CITED, cross-agreed across four independent reports: Forge `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29…` (D1 runtime re-verified by driver; WS48); XMage `0c1f455ea8c8fa48ab9d638ad5068ec242800428` / tree `fdb8bf56…` (D2 cross-checked vs live worktree; WS49). phase.rs pin `a0f9c55d7aef13e4875ac8137c016948e5f66e12` is cited from the LOCAL_PRESERVED_REPORT only.

---

## 2. D1–D7 final adjudication (one verdict each; detail in evidence-index.json)

- **D1 — GENERAL_N_HYPOTHESIS_SUPPORTED** (architecture evidence, not qualification). Forge N=2..6: 55/55 native rows PASS at construction/ring/zone scope (DIRECTLY_VERIFIED); HIDDEN_INFO structural/CODE_DERIVED only. No `numPlayers==4` assumption in the pinned Forge Rules Core or WS48 provider; the 4P hard gates live in lab/XMage *driving* layers and must be RETAINED until a dedicated generalization workstream re-validates them. Live `game.start()`, per-count live play, hidden-visibility adversaries, RNG/replay: all still unqualified.
- **D2 — BOUNDED_REUSE.** XMage corpus removes ~40–45% of scenario-authoring work in the bounded 20-scenario study (11 DIRECT / 7 REWRITE / 1 UNUSABLE verdicts; inventory DIRECTLY_VERIFIED over 2021 test files). Reuse is scaffolding + differential/reference value; no outcome imported as truth. Corpus gap recorded: COMMANDER_DAMAGE has zero dedicated tests at the pin and must be authored fresh.
- **D3 — BUILD_CLEAN_ROOM_EQUIVALENT** (scaffolding only). 1000-row stratified prototype (SYNTHETIC): parsed 974 / structured 933 / skeleton 974 / manual-review-required 528 / unsupported 186 / ambiguous 26 / false-positive 36. A majority still needs manual review; behavior credit 0 by construction. Manabrew embedded reuse NOT_USABLE (AGPL-3.0-or-later); Manabrew docs/patterns REFERENCE_ONLY; tree-sitter MIT grammar is an external-isolated-tool candidate only.
- **D4 — ARCHITECTURE_REFERENCE_ONLY.** phase.rs at the cited pin is a well-shaped reference (typed legal actions, actor-authenticated reducer, viewer projections, seeded RNG, replay journal) with correctness UNKNOWN in all 14 probed cells. Coverage badges are parse-support metrics, disqualified as qualification truth by upstream's own 30-cause / 4,698-card silent-misparse backlog. LLM-authorship provenance is untrusted; single-maintainer continuity risk stands. Provenance of the D4 source is LOCAL_PRESERVED_REPORT (preserve path recorded in ledger), not REMOTE_VERIFIED. No broad requalification without genuinely decision-relevant new evidence.
- **D5 — KEEP_CUSTOM (confirmed).** Optuna-only probe (SYNTHETIC): no OSS arm beats the hand-written optimizer's mean hypervolume (8.906 vs 8.451 MOTPE vs 8.757 NSGA-II); hard blocker found (Optuna multi-objective studies lack intermediate report/prune, so racing stays custom); ~3518 LOC of optimizer machinery is Commander-specific semantics, not replaceable generic code. No migration authorized. Only door open: an additive, gated Optuna-sampler experiment behind unchanged legality/racing/QD/evidence gates, as a separate future task with real-simulator budget. pymoo/Ax/BoTorch/SMAC remain protocol-level UNKNOWN (judged on dependency/shape grounds, not benchmarked).
- **D6 — SIMPLIFY_CURRENT (confirmed).** Hardened stdlib-local executor satisfies all nine requirements with throughput parity (24/24 + same-seed retries; baseline ABORTED at 5/24; Ray 24/24 but +2 s startup tax, 263 MB env, daemons). K8s unjustified. KEEP_CURRENT explicitly not recommended. Production adoption is a separate authorized change (wire shared runner to real Structural callables + `tests/integration/test_structural_batch.py` + qualified-small real-sim cross-check). No Ray/Kubernetes migration.
- **D7 — LICENSE_TOPOLOGY CONCLUDED AS ARCHITECTURE INPUT (not clearance).** Retained source-verified claims: Forge GPL-3.0 class → all modeled production topologies LEGAL_REVIEW_REQUIRED (GPL-accepted component / separate-process wrap / differential-donor-only; embedding into a non-GPL core off the table); XMage MIT license-class advantage (packaging/transitive/data/IP/trademark review still required); phase.rs MIT OR Apache-2.0; Manabrew AGPL-3.0-or-later + Forge constraints, embedded reuse not cleared. Detailed D7 report provenance is incomplete (no dedicated D7 commit in repo); only the per-component claims above are retained. No legal clearance is provided here; the production-topology review is a HUMAN_AUTHORITY action on the roadmap.

---

## 3. Interim-matrix re-adjudication (§8: survived / strengthened / weakened / overturned / UNKNOWN)

Interim source: `research/architecture-discriminator-checkpoint-20260910 @ ba76ed6a` (treated as historical comparison evidence; superseded as decision analysis by the new matrix, provenance retained).

| Old claim | New verdict | Grounds |
|---|---|---|
| Leading hypothesis FORGE-CENTRIC HYBRID (provisional) | SURVIVED, STRENGTHENED (still provisional, still not selected) | D1 general-N construction scope + WS48 R1e native-repair momentum + D2 quantified donor value all point the same way; nothing falsified it |
| Forge constructs 107/107 natively; behavior 0/107 | SURVIVED | R1e keeps 0/107 (transcript probes only, credit explicitly false) |
| D2 "counts only, reusability UNKNOWN" | OVERTURNED → RESOLVED as BOUNDED_REUSE | 20-scenario probe executed after the checkpoint |
| D3 "unexecuted" | OVERTURNED → RESOLVED as BUILD_CLEAN_ROOM_EQUIVALENT | 1000-row prototype executed after the checkpoint |
| D5 "requirement-card stage" | OVERTURNED → RESOLVED as KEEP_CUSTOM | Optuna probe executed after the checkpoint |
| D6 "requirement-card stage" | OVERTURNED → RESOLVED as SIMPLIFY_CURRENT | Discriminator executed after the checkpoint |
| D4 "DEMOTED (WS-17)" | STRENGTHENED (ARCHITECTURE_REFERENCE_ONLY) | Independent D4 reality probe adds misparse-backlog, LLM-pipeline, and bus-factor evidence |
| D7 "concluded as input" | SURVIVED (conclusions unchanged; provenance completeness WEAKENED) | Component claims re-verified via D2/D3/D4; Manabrew AGPL added; no single D7 report file exists |
| D1 "unresolved; per-count smoke next" | RESOLVED at construction/ring scope; live-game scope still UNKNOWN | Terminal D1 delivered the bounded discriminator, not the hoped-for live smoke — scope note, not a demotion |
| Runner-up XMage-first; promotion trigger "D2 high reuse or GPL refusal" | SURVIVED (trigger NOT met) | D2 reuse is bounded, not high; GPL topologies still review-required |
| Greenfield DISFAVORED; 4P-specialized PROHIBITED; internal-AI barred; parity/parser-as-PASS barred | ALL SURVIVED | Mission policy now canonical (PR173, `docs/PROJECT_MISSION.md`); D1 confirms no 4P assumption in Forge engine |
| Checkpoint source locks (c391a761 base; PR172/173 open) | SUPERSEDED | Post-PR172/173 main `c162871b` governs; WS48/WS49/WS33-D heads all advanced |

---

## 4. Rules-Core candidate comparison (§9; A–L axes; correctness and real-card function dominate)

### FORGE-CENTRIC (leading hypothesis)
- A Rules-Core uncertainty: HIGH but shrinking. General-N construction proven natively (D1); live behavior 0/107.
- B Decision boundary: three distinct uncovered surfaces (declare_attacker; discardToMaximumHandSize; BLOCK-4 restore/adapter), each with R1-series momentum (R1e pattern: native-path repair, no fork). Not combinable without evidence.
- C Hidden-info: thin on the Forge side (D1 structural only) — must be proven in the discriminator.
- D RNG/replay: UNKNOWN — must be proven in the discriminator.
- E Multiplayer/Commander: Commander init per N proven at construction scope (D1); live Commander rules NOT_RUN.
- F Real-card behavior: CARD_02 transcript complete (TRANSCRIPT_PROBE, credit 0); Full107 NOT_RUN.
- G Arbitrary-state restore: BLOCK-4 classified STATE_RESTORE_OR_ADAPTER_DEFECT — harness-imposed hardness (see §7: overweighted as a *selection* gate).
- H Qualification machinery: WS33 Q6 path exists (36/884) + D2/D3 scaffolding quantified.
- I Production remediation: native-path repairs, engine-fork gate NOT triggered.
- J License/topology: GPL-3.0 class, LEGAL_REVIEW_REQUIRED (reverser §5-R3).
- K Maintenance: own-forge-fork continuity story required (same burden class as XMage fork).
- L Variable-N quality: STRONGEST in evidence (D1 N=2..6, engine fully general-N).

### XMAGE-CENTRIC (runner-up, live)
- A–F: implementation-complete remediation (Phases 0–5), 54/54 offline (CODE_DERIVED); ALL engine/runtime behavior UNKNOWN; Full107 NOT_RUN; 0/107. v1.0.4 88/107 is superseded provenance with zero import.
- G: potential structural advantage — the corpus ships engine state-restore/rollback infra (`rollback/*`) that Forge-side work must hand-build; unproven as a qualification asset until the runtime mirror runs.
- C/D: principal-scoped hidden battery (R-h) implemented observation-gated; RNG funnel partially proven (Library/flip/dice/starting-pick/getRandom via `RandomUtil.setSeed`) with production-reachable UNCOVERED channels (`putCards` Top/Bottom `Collections.shuffle`, RandomBoosterDraft, SwissPairing, `TokenRepository new Random(ID)`) — none in the 107 denominator, all UNKNOWN for per-channel completeness.
- J: MIT license-class advantage (packaging review still required). K: own-mage-fork continuity, same burden class.
- L: multiplayer/commander corpus exists (with the COMMANDER_DAMAGE gap); engine-level general-N proof weaker than D1.

### Hybrids
- FORGE + XMAGE TEST/DIFFERENTIAL HYBRID (recommended direction): Forge authoritative core; XMage corpus as scenario-authoring donor (D2) and differential reference (never truth). This is the leading hypothesis, not an averaging of two cores — exactly one Rules Core answers every ruling.
- XMAGE + FORGE TEST/DIFFERENTIAL HYBRID: symmetric fallback; becomes primary only via a decision reverser (§5).

### Rejected / disfavored (no incumbency protection cut the other way either)
- phase.rs near-term core: REJECTED (D4: 14/14 UNKNOWN + silent-misparse backlog + LLM provenance + continuity risk). Reference patterns remain reusable as ideas.
- Manabrew embedded core: REJECTED (AGPL-3.0-or-later + Forge constraints; NOT_USABLE). Docs/patterns stay REFERENCE_ONLY.
- Clean-room new general Rules Core: DISFAVORED (mission policy: do not build when a qualifiable existing solution may be better; zero evidence it beats reuse; zero code authorized).
- 4P-specialized Rules Core: PROHIBITED (mission: 2–5P mandatory conformance, 4P benchmark-only).
- Any architecture discovered from current evidence that is genuinely better: none found; the search obligation persists into qualification (mission: research must keep looking for end-to-end reuse that eliminates work).

---

## 5. What can still reverse the decision (§10)

Four realistic reversers (no others found in current evidence):
- **R1 — XMage runtime mirror traverses what Forge cannot.** If the bounded XMage mirror (secondary gate) drives real decision sequences while Forge stalls on engine-side defects, the ranking flips.
- **R2 — Forge engine-side stall.** If the primary slice exposes two or more *distinct engine-side* defects (not harness gaps) on production paths, the lead weakens to tied and the secondary gate becomes mandatory pre-selection.
- **R3 — GPL topology review forces donor-only.** If HUMAN legal review rules out GPL-accepted-component and separate-process-wrap postures, Forge drops to differential-donor and XMage-first becomes primary on topology burden regardless of behavior momentum.
- **R4 — Hidden-info/RNG disqualification.** A leak or non-replay finding against either candidate's production path disqualifies that path until remediated (fail closed).

No Full107-from-both is demanded; no complete Q6 coverage is demanded pre-selection; evidence quality is not lowered. The discriminator below is cheaper and more informative than broad Full107 because it attacks the exact uncertainty that separates the candidates — traversal of *authoritative multi-callback decision sequences on real cards* — instead of re-measuring 107 records of mostly-harness-bound behavior.

### PRIMARY REMAINING DISCRIMINATOR (exactly one)
**Forge production vertical slice with authoritative external decision-sequence traversal.**
- Hypothesis: on the WS48 line at `10a7f8f6` (+ only reviewed repairs), a natively constructed 4-player real-Commander game can traverse complete native decision sequences (TARGET_SELECTION → MANA_PAYMENT → attackers → …) with an external pilot selecting only among engine-offered options, principal-scoped observations captured per frame, and the traversed prefix deterministically replayed from seed + frame journal.
- Source locks: WS48 `10a7f8f6`; WS47 freeze `192e2b77` (denominator/records only, no restore requirement — see §7); Forge pin `66caae16`.
- Runtime path: native construction (R1e Token-DB path) → 4P Commander start → real casts driven to resolution through the sequence state machine (§6 design) → observation capture → seed+frame replay of the prefix.
- Success: one or more real casts resolve to terminal checkpoints with every discretionary choice externally selected from engine-offered options, zero fallback legality, fail-closed elsewhere. This is recommendation-grade evidence, not behavior credit: credit still accrues only per WS47-adjudicated record.
- Failure interpretation: engine-side stall → weakens Forge (R2, triggers secondary gate mandatorily); harness-side stall → feeds the §6 harness redesign without weakening Forge (classified HARNESS, as D4c was).
- Why cheaper than Full107: one production path proves the traversal capability that 107 harness-bound records cannot isolate; Full107 then becomes conformance confirmation, not discovery.

### SECONDARY GATE (strictly necessary, conditional)
**Targeted XMage bounded decision-sequence mirror on the same harness contract** (WS49 line at `1cd12765`; remediation Phases 0–5 already implemented, so the mirror is a CI-build + bounded run, not new remediation).
- Triggers (any one): (a) primary fails closed on engine-side evidence; (b) primary succeeds but Coordinator judges the margin too thin for selection without a live runner-up point; (c) R3 forces topology-driven re-ranking.
- Non-trigger means NOT_RUN stays NOT_RUN — the mirror must not become a second Full107 by drift.
- Additionally required before selection regardless of triggers: HUMAN legal-topology review (R3) and acknowledgment of the Vraska payment-leg queue.

Conclusion `NO_FURTHER_CROSS_CANDIDATE_DISCRIMINATOR_REQUIRED` is NOT supported by current evidence (0/107 both lanes; three Forge surfaces open; XMage runtime UNKNOWN).

---

## 6. D4c architecture lesson (§6: sequence/state-machine harness — design only, no implementation here)

The D4c falsification is accepted as a general design constraint: the real native decision chain is TARGET_SELECTION → MANA_PAYMENT → later discretionary decisions → …, so "one mechanic = one callback family" is the wrong scaling abstraction for the future Decision/Qualification harness. The harness must instead model an **authoritative SEQUENCE / STATE MACHINE of native decision callbacks**:

- The engine is the sole producer of typed decision frames (kind, offered options with native handles/provenance, min/max selection cardinality, cancel policy, acting principal, sequence position).
- The external pilot answers each frame with a selection drawn exclusively from the offered options (unique-match discipline per D4c Repair #2 and WS49 R-c); anything else fails closed.
- Unsupported frame kinds fail closed (the D4c MANA_PAYMENT gap becomes a visible unsupported-kind event, never a silent skip or AI answer).
- Semantic replay = recorded seed + frame journal; re-issue must reproduce the identical frame sequence (divergence ⇒ FAIL, per the WS33-D replay-divergence discipline).
- Observations are captured per frame under principal scope (WS49 R-h observation-gating generalized to every frame, including rejections and logs — the D4 leak-freedom concern).
- No internal engine AI is reachable from any pilot path (fenced by construction, with the phase.rs `fallback_action` caveat as the negative pattern to avoid); no fabricated options; no requested-option filtering that reconstructs legality.

This design preserves all six required invariants (authoritative options; fail-closed unsupported; no internal AI; no fabricated options; semantic replay; principal-scoped observations) and converts the next MANA_PAYMENT-class surprise from a terminal FAIL into a routed, reviewable frame kind. Detailed interface shaping belongs to the §12 scaffolding workstream, not here.

---

## 7. WS47 / Full107 role (§11)

- **WS47 immutable 107-record qualification remains: (a) mandatory pre-Architecture-Freeze conformance denominator and calibration/regression truth; (b) NOT architecture-selection critical path.** Selection needs the §5 discriminator, not 107/107. WS47 is TERMINATE_COMPLETE as a workstream; its authority is frozen and must not be modified, credited, or re-run from this reconciliation.
- **Full107 is post-selection conformance work with one pre-Freeze obligation:** the SELECTED core's Full107 must be executed and adjudicated (zero unexplained FAIL) before Freeze; the exact bar is Coordinator qualification policy, not set here. Runner-up Full107 CAN SAFELY FOLLOW FREEZE as regression. Neither lane's Full107 is demanded pre-selection (that would be the broad-double-Full107 the evidence does not require).
- **Arbitrary frozen-state restoration is partially overweighted as a selection criterion — adjudicated and persisted as a technical decision.** BLOCK-4-class restore hardness is harness-imposed (materialization convenience), not production-path-imposed: real games construct-then-play (the R1e/D1 pattern), while mid-game restore serves testing/resume. Disposition: restore is MUST-before-Production-Implementation (qualified, or fail-closed with replay-from-seed resume as the supported resume story) — NOT a provider-selection gate. The primary discriminator therefore uses native construction, not frozen-state restore, and no architecture conclusion in this report depends on restore capability. (TECHNICAL_DECISION, within contract; evidence: D1 native-construction scope + R1d classification + WS33-D forcing analysis.)

---

## 8. Q6 industrialization design (§12: D2 + D3 + D4c + WS33 gold standard)

Smallest scalable actual-card-driven Q6 path — automate the scaffolding, never the verdict:

| Step | Automate with | Never automate |
|---|---|---|
| Intake + inventory | D3 clean-room parser (provenance per row retained) | — |
| Mechanic/capability clustering | D3 family pre-tags × D2 corpus mapping | Final capability assignment (human/rules adjudication queue) |
| Test skeleton generation | D3 skeletons (974/1000-yield class) | Expected values (no `expected`/assert synthesis, per D2 validator rule) |
| Provenance | Per-record repo/branch/commit/tree/source/license blocks (D2 pattern) | — |
| Decision-surface pre-tagging | D2 strict-mode choice extraction × §6 frame kinds (TARGET/MANA/attackers/…) | Transport proof (must be log-evidenced per run, D4c lesson) |
| Witness generation | Transport logs + replay-divergence checks (runner) | PASS verdicts (adjudication queue only) |
| Replay checks | Seed + frame-journal re-issue in runner | — |
| Failure clustering | Existing `tools/foundry/cluster_failures.py` + frame-kind taxonomy | Root-cause classification without log evidence |
| Queues | Manual-review queue (D3's 528-class pattern) + rules-adjudication queue | — |

What can NEVER be promoted to behavior PASS: parsing/generation success (D3 boundary); reference parity with either engine (parity ≠ official-Rules validation); silent-support surprises — scenarios passing for the wrong reason (e.g. over-broad targets, D4 RC#1 class) count as FAIL; outcome-pinned-only choices (Vraska lesson: effect evidence stays supporting, the choice leg stays queued until transported).

Attack the remaining 884 as a **hybrid**: capability-family-first ordered by production frequency (mana payment → targets → attackers → costs/modes → triggers → replacement → continuous → hidden/RNG), instantiated as generated actual-card campaigns (D3 skeletons × D2 corpus adaptations), with adversarial sampling for known gaps (COMMANDER_DAMAGE first) and metamorphic seed/ordering variants where cheap. Path-by-path remains the certification unit (WS33 gold-standard calibration preserved); the denominator is never reduced by this audit.

---

## 9. Execution hardening design (§13: D6)

Minimum production-oriented hardening (all from the D6 discriminator, no Ray/Kubernetes — current evidence establishes no need):
process isolation (spawn); deterministic seed identity (`derive_*_seed` reused); retries with identical job_id + seed and incremented attempt; explicit CRASH/TIMEOUT/TRANSIENT/UNKNOWN classes; quarantine for exhausted retries; immutable run manifests (`run-manifest.json` + run_key resume, `storage/run_integrity.py` reused); duplicate suppression; terminal result hashes; structural crash-never-PASS (failed records carry failure_class and no result_hash).
Adoption vehicle (future authorized change, not here): one shared runner (~150–200 LOC hardened from the 236-line reference) consolidating the 162 LOC bespoke surface (`batch.py:36-43,95-148`; `campaign.py:319-339`; `experiments.py:325-351`; `robustness.py:589-600`; `scheduling.py` 40-line heuristic retained as runner policy), reusing `derive_*_seed`, manifest/quarantine primitives, and the `full_game_batch.py` resume/failure-class pattern (net ≈ 60–90 LOC deleted; four divergent failure behaviours collapse to one contract). Precondition: wire to real Structural callables behind seed-identity + semantic-hash + crash-never-PASS assertions, re-run `tests/integration/test_structural_batch.py`, plus a qualified-small real-sim cross-check.

---

## 10. Optimizer decision (§14: D5 confirmed)

**KEEP_CUSTOM — confirmed, no migration authorized.** Standing separation: project-semantic responsibilities (Commander legality/colour-identity/singleton/encoding/packages/mana-repair; simulation execution; paired-CRN evaluation; evidence logging/checkpoints; opponent/meta definition; screening proxy; racing/pruning; Pareto/QD/bandit machinery) stay custom — they are the product, not plumbing. Generic search-algorithm internals have no current equivalent to replace; the only rational future use of a generic library is an **additive MOTPE/NSGA-II proposal policy inside the existing search, behind the unchanged legality gate, racing budgets, QD admission, and evidence logging** — and that requires real-simulator-budget evidence first, as a separate task. (No optimizer migration workstream exists or is created here.)

---

## 11. Workstream portfolio reset (§15)

| Workstream | Disposition | Why / dependency / reactivation |
|---|---|---|
| WS33 historical path-by-path campaign | CONTINUE_BUT_NARROW | Certification unit for §8 Q6; D-family retained per impact gate (35 NO_IMPACT); D4c line terminated, no new single-target runs without fresh authority + MANA_PAYMENT-inclusive design |
| Vraska payment requalification | REQUALIFICATION_REQUIRED | Queued targeted re-transport under registered wiring with payment-choice intent; effect evidence stands supporting; needs future run authority |
| D4d/e/f | NEVER_START | D4c terminated FAIL CLOSED; any future single-target work needs fresh authority, not a D4d label |
| Batch-6 | PAUSE_AT_SAFE_CHECKPOINT | Not started; reactivates post-§6-harness-redesign under new authority |
| Forge Full107 (successor lane) | KEEP | Leader's pre-Freeze conformance vehicle; runs after primary discriminator + sequence-harness redesign, not before |
| XMage Full107 (successor lane) | PAUSE_AT_SAFE_CHECKPOINT | Sealed baseline retained; reactivates only via secondary-gate trigger or post-Freeze as regression |
| WS48 further decision-family work | CONTINUE_BUT_NARROW | Folded into the primary discriminator vertical slice; production-path order replaces family-by-family order |
| WS49 remediation/runtime run | PAUSE_AT_SAFE_CHECKPOINT | Implementation preserved at `1cd12765`; runtime run only via secondary-gate trigger or post-Freeze regression |
| phase.rs candidacy (near-term core) | SUPERSEDE | Superseded by D4 verdict; reactivation only on D4-§7 promotion criteria (14-scenario runtime vs our truth + fencing proof + N-player Commander + determinism + leak audit + misparse-sample fix + continuity position) |
| Manabrew embedded reuse | NEVER_START | AGPL + Forge constraints; reactivation only on relicense (docs stay REFERENCE_ONLY) |
| Optimizer migration | NEVER_START | KEEP_CUSTOM; the additive-sampler experiment is a distinct future proposal, not a migration |
| Ray/K8s migration | NEVER_START | SIMPLIFY_CURRENT; K8s only on demonstrated multi-node need with numbers |
| 4P-specialized Rules Core | NEVER_START | PROHIBITED by mission; 4P is benchmark-only |
| RL/pilot-strength work | PAUSE_AT_SAFE_CHECKPOINT | Strength cannot compensate for rules defects; reactivates after qualified core + conformance |
| Production Repository creation | NEVER_START | Before Freeze; reactivates as the first post-Freeze implementation step |
| D1/D2/D3/D5/D6 discriminator branches | TERMINATE_COMPLETE | Deliverables sealed; evidence integrated here; branches retained as provenance |
| WS33-D branch | TERMINATE_COMPLETE | Terminal FAIL + impact gate sealed and preserved |
| Interim-matrix branch | INTEGRATE_EVIDENCE_ONLY | Provenance retained; superseded as decision analysis |

No workstream is preserved merely because its number exists. No deletion is performed here (DELETE_AFTER_PRESERVATION appears nowhere — nothing meets its bar yet).

---

## 12. Goal-first dependency map (§16; counts are never progress proxies)

Read bottom-up; status is the weakest credible reading of current evidence.

| Layer | Status | Evidence anchor |
|---|---|---|
| Useful real-deck Commander decision output | UNKNOWN | No end-to-end decision output exists on a qualified core |
| Deck/matchup optimizer | PARTIAL | Semantics exist and are discriminator-tested (D5); unqualified end-to-end |
| Batch simulation | PARTIAL | Structural paths exist; hardened runner designed but not adopted (D6) |
| External pilot | PARTIAL | WS48 R1e advances pilot traversal; WS49 bindings implemented but runtime-UNKNOWN |
| Principal-scoped observations | PARTIAL | WS49 R-h observation-gated battery implemented; Forge-side thin; leak audits NOT_RUN |
| Authoritative Decision options | PARTIAL | Forge sequences partially traversed (R1e, D4c-Repair-#2 bounded); XMage natively bound, runtime-UNKNOWN |
| Semantic replay / Rules RNG | UNKNOWN | Tapes exist; per-channel completeness UNKNOWN (WS49 Phase 5 uncovered channels); no replay proof |
| Full real-game lifecycle | UNKNOWN | Construction proven (D1); live lifecycle NOT_RUN on successor lanes |
| Commander / multiplayer | PARTIAL | Construction-scope N=2..6 (D1); live Commander rules NOT_RUN |
| Actual-card behavior | PARTIAL | 36/884 WS33-D + CARD_02 transcript probe (credit 0); Full107 NOT_RUN both lanes |
| Qualified Rules Core | UNKNOWN | 0/107 both successor lanes |
| Candidate Qualification | IN_PROGRESS | This reconciliation is its doorway; discriminator defined |
| Architecture Freeze | NOT_RUN | NOT CLAIMED by this report |

The project sits at the qualification doorway with construction and scaffolding proven, traversal partially demonstrated, and every behavior claim still ahead. That is exactly what the §13 roadmap sequences.

---

## 13. Candidate qualification roadmap (§17: shortest evidence-safe route)

- **MUST HAVE BEFORE PROVIDER RECOMMENDATION:** this reconciliation (ledger + comparison) and the primary discriminator result (§5), classified per §3 semantics.
- **MUST HAVE BEFORE PROVIDER SELECTION:** secondary-gate resolution (run or principled non-trigger with Coordinator concurrence); HUMAN legal-topology review (R3); Vraska queue acknowledgment with a scheduled re-transport vehicle; no realistic decision-reversing uncertainty left open except the conformance campaign itself.
- **MUST HAVE BEFORE ARCHITECTURE FREEZE:** selected-core Full107 executed and adjudicated (zero unexplained FAIL; bar = Coordinator policy); per-count 2–5P conformance on the selected core (a 4P result never stands in for other counts); hidden-information leak audit; deterministic Rules-RNG/replay proof; restore-path disposition (qualified or fail-closed-with-replay-resume, §7 decision).
- **MUST HAVE BEFORE PRODUCTION IMPLEMENTATION:** shared hardened runner adopted (§9); sequence-harness implemented from the §6 design; Q6 scaffolding pipeline (§8) operational with adjudication queues staffed; 884-campaign underway (completion not required).
- **CAN SAFELY FOLLOW FREEZE:** runner-up Full107 as regression; Q6 campaign completion; additive optimizer-sampler experiment; RL/pilot-strength work; lab driving-layer N-generalization (the retained 4P gates); execution scale-out only on demonstrated need.

Nothing here requires every future card/mechanic before Freeze; nothing here freezes while a reverser (§5 R1–R4) remains live.

---

## 14. Architecture Freeze readiness (§18)

**ARCHITECTURE_FREEZE_READY_NOW = NO.** Minimal missing evidence: (1) primary discriminator result; (2) conditional secondary-gate outcome; (3) HUMAN legal-topology review; (4) selected-core Full107 adjudication; (5) 2–5P per-count conformance; (6) hidden-info leak audit; (7) RNG/replay proof; (8) restore-path disposition. The Coordinator-adjudicable Freeze bundle is exactly items 1–8 plus this reconciliation and the WS47 frozen contract. This assessment recommends only; Freeze authority stays with the Coordinator.

---

## 15. Decision recommendation (§19)

- **CURRENT_LEADING_RULES_CORE_HYPOTHESIS:** FORGE-CENTRIC HYBRID — Forge authoritative Rules Core; XMage corpus as scenario-authoring/differential donor (never truth); external pilot; hardened-local execution; custom optimizer; tool-assisted Q6 closure.
- **Why Forge leads:** general-N engine with the strongest structural evidence (D1 N=2..6, zero 4P assumptions in engine); native-path repair momentum without engine-fork pressure (R1e); retained transcript/anti-echo/fail-closed discipline; the Q6 scaffolding story composes naturally (D2 donor + D3 parser + WS33 calibration).
- **RUNNER_UP:** XMAGE-CENTRIC HYBRID — XMage authoritative core with Forge as donor. Keeps the MIT license-class advantage and a native rollback-infra story (G-axis); lacks all runtime verification (remediation is implementation-only) and engine-level general-N proof.
- **CONFIDENCE_QUALITATIVE:** provisional-moderate. The lead is built on construction, architecture-shape, and repair-momentum evidence — not on behavior, where both lanes are 0/107. It is the weakest lead that still justifies spending the next discriminator on Forge first.
- **DECISION_REVERSERS:** R1 (XMage mirror traverses what Forge cannot) · R2 (Forge engine-side stall ×2+) · R3 (GPL review forces donor-only) · R4 (hidden-info/RNG disqualification either side).
- **PRIMARY_REMAINING_DISCRIMINATOR:** Forge production vertical slice with authoritative decision-sequence traversal (§5).
- **SECONDARY_GATE_IF_ANY:** conditional XMage bounded mirror on the same harness contract (triggers §5) + HUMAN legal-topology review.

No fake-percentage confidence is stated. Ties are resolved by the discriminator, not by deliberation.

---

## 16. Validation performed here (§23)

- Every referenced commit/branch verified present (or classified local-only / REPORT_CITED / LOCAL_PRESERVED_REPORT) — see evidence-index.json; no blind trust in filenames.
- Report paths verified to exist (D1/D2/D3/D5/D6/WS48/WS49/WS33-D/WS47/interim-matrix sources all read via `git show` or worktree reads at exact commits).
- JSON validated (13 inputs). `git diff --check` clean at each checkpoint.
- Scanned for behavior-credit promotion: none — every behavior number is 0/107, 36/884, or explicitly credit-false; parse/construction/readback/green-CI boundaries restated in §§2, 8, 10.
- Scanned for Freeze/provider claims: none — NOT CLAIMED / NOT SELECTED stated at head and throughout; §14 answers NO with the missing-evidence list.
- Diff-surface check at persistence time: research/documentation outputs only (plus the workstream state file); no runtime/qualification source.
- Worktree ownership re-verified exclusive at each checkpoint; final HEAD based on post-PR172 main (it IS post-PR172 main plus this branch's research commits).
- No simulator test run (research-only documentation; no qualification rerun for reassurance, per instructions).

---

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
No Production Repository is created by this workstream.
