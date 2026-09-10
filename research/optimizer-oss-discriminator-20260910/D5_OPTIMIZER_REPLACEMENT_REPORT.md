# D5 Optimizer OSS Replacement Report

Date: 2026-09-10. Branch: `research/optimizer-oss-discriminator-20260910`.
Production paths untouched (probe lives in `research/optimizer-oss-discriminator-20260910/`,
production venv never got new dependencies).

## OSS selection (smallest fair combination)

- Installed: **Optuna 5.0.0 only**, in isolated `/tmp/oss-probe-venv` (pulls `numpy`
  only; no `scipy`/`torch`). One package covers MOTPE (`TPESampler` multivariate),
  NSGA-II/III (`NSGAIISampler`/`NSGAIIISampler`) and pruning (`MedianPruner`/`HyperbandPruner`).
- Deliberately NOT installed: `pymoo` (needs `scipy`/C extensions; its NSGA-II role is
  already covered by Optuna's `NSGAIISampler` reference arm), `Ax`/`BoTorch` (needs
  `torch`, GB-scale, GP-BO overkill for a discrete 100-singleton combinatorial space),
  `SMAC` (needs `sklearn`/`scipy`; justified only for expensive conditional HPO spaces,
  not ours). Their verdicts below are protocol-level (`UNKNOWN`), not benchmarked.

## Fair experiment

- Representative problem: synthetic Rogshai-like single-swap tuner. Baseline 60-slot
  mainboard (22 fixed lands, 3 locked anchors), 40-card pool with one off-identity card.
  Both arms search the **identical finite single-swap space** through **one shared
  legality oracle** (singleton, color identity, card count, locked cards, land count,
  mana-curve average, package minimum). Production multi-swap chaining is out of scope.
- Simulator: deterministic synthetic paired-CRN evaluator (same `(deck, seed)` gives the
  same observation; baseline-vs-variant deltas share seeds/scenarios, mirroring
  `run_paired_structural_comparison`). Objectives (maximize): robust placement
  improvement + economy. Fixed 3-archetype opponent rotation, identical for both arms.
- Budget: 400 simulator evaluations per arm per seed; master seeds 101/202/303.
  Metric: exact 2D hypervolume (ref `(-2.0, -2.0)`) + frontier size + evals consumed +
  wall-clock split (sim vs optimizer overhead) + reproducibility + restart drill.
- Harness: `research/optimizer-oss-discriminator-20260910/probe.py` (422 lines, stdlib
  except `optuna` in the OSS arm only). Raw traces: `results_current.json`,
  `results_motpe.json`, `results_nsga2.json` in the same directory.
- Truth boundary: synthetic structural-model analogue. A better optimizer score does
  NOT prove simulator correctness.

## Results

| arm | seed 101 HV | seed 202 HV | seed 303 HV | mean HV | sim evals | unique decks | wall (s) | sim-wall (s) |
|---|---|---|---|---|---|---|---|---|
| current (hand-written) | 8.782 | 8.629 | 9.306 | **8.906** | 400/400/400 | 101/101/101 | 0.020/0.021/0.020 | 0.006 |
| optuna MOTPE | 8.599 | 8.254 | 8.500 | 8.451 | 396/396/396 | 33/33/33 | 0.106/0.089/0.086 | 0.005 |
| optuna NSGA-II | 8.377 | 8.927 | 8.966 | 8.757 | 156/180/204 | 13/15/17 | 0.021/0.018/0.018 | 0.002 |

- Frontier sizes are comparable (3–8 across arms/seeds); no OSS arm beats current mean HV.
- Overhead (wall − sim-wall): current ≈ 0.014 s, MOTPE ≈ 0.09 s (~6×), NSGA-II ≈ 0.016 s.
- NSGA-II never spends its budget: trial cap (120) binds first because it resamples
  duplicates (103–107 of 120 trials pruned as duplicate/illegal). Duplicate avoidance
  would be custom code anyway.
- Hard blocker found: **Optuna multi-objective studies do not support intermediate
  `Trial.report`/`should_prune`** (`NotImplementedError`). MO pruning/racing cannot be
  outsourced to Optuna; any Successive-Halving-style racing stays custom code around
  complete trials. The MOTPE arm therefore pays full per-candidate cost (12 evals/deck
  vs current's 4-or-12 via racing).
- Restart drill: in-memory study loses all trials on crash (5 → 0); `sqlite` storage
  recovers all (5 → 5) with stable study name. So Optuna persistence is viable but
  requires operating a database; current `OptimizerCheckpointStore`/`OptimizerLock`
  JSON machinery has no such dependency.
- Reproducibility: current arm bit-identical across reruns (trace hashes match);
  Optuna MOTPE deterministic given fixed sampler seed (verified). Both PASS.
- Implementation LOC (probe): current arm ≈ 90 lines, Optuna arm ≈ 80 lines — no
  meaningful code-saving from outsourcing. Production generic machinery totals 3518
  lines across `optimization/{search,constraints,experiments,jp5}.py`,
  `whole_deck/{optimizer_v2,optimizer_search,optimizer_benchmark}.py`, `adaptive_budget.py`,
  most of it Commander-specific semantics, not replaceable generic code.

## Classification per current optimizer subsystem

| subsystem | verdict |
|---|---|
| Commander legality / colour identity (`evaluate_constraints`, color checks) | KEEP_CUSTOM |
| Singleton constraint | KEEP_CUSTOM |
| Deck encoding (`WholeDeckVariant.mainboard` tuple, variant/deck hashing) | KEEP_CUSTOM |
| Package constraints (incl. simultaneous allocation) | KEEP_CUSTOM |
| Mana-base / curve repair semantics (`search_mana_*`, `whole_deck/mana.py`) | KEEP_CUSTOM |
| Simulation execution (`StructuralSimulator`, `ProjectPairedEvaluator`, campaign orchestrator) | KEEP_CUSTOM |
| Paired common-random-number evaluation (`derive_paired_seed`, paired campaigns) | KEEP_CUSTOM |
| Evidence logging (manifests, partitions, cache identity, checkpoints, locks) | KEEP_CUSTOM |
| Opponent/meta ensemble definition | KEEP_CUSTOM |
| Screening proxy (`profile_score`, `screening_delta`, static deprioritize gate) | KEEP_CUSTOM |
| Racing / pruning (`RacingConfig`, `select_racing_survivors`, conservative budget plan) | KEEP_CUSTOM |
| Pareto handling (`dominates`, `pareto_front`, QD archive admission) | KEEP_CUSTOM |
| QD diversity / novelty archive (`QualityDiversityArchive`, `novelty_score`, hypothesis archive) | KEEP_CUSTOM |
| Bandit operator/policy learning (`update_learning_weights`, `normalize_learning_weights`) | KEEP_CUSTOM |
| Categorical proposal sampler (weighted operator/policy random proposals) | UNKNOWN |
| NSGA / MOTPE / BO internals (no current equivalent; would be additive) | UNKNOWN |
| Any subsystem → `REPLACE_WITH_PYMOO` | none (no justified mapping; NSGA reference already covered by Optuna arm) |
| Any subsystem → `REPLACE_WITH_BOTORCH_OR_SMAC` | none (dependency/shape mismatch; unjustified) |
| `DELETE` | none (no dead generic machinery identified) |

Notes on the two `UNKNOWN`s (not PASS, not REPLACE):

- Categorical sampler stays `UNKNOWN` (not `REPLACE_WITH_OPTUNA`): MOTPE/NSGA-II are
  credible *alternative samplers behind the existing custom legality + racing gates*
  (mean HV within ~5% on this probe), but they showed no win, ~6× overhead (MOTPE),
  worse budget efficiency (both), and an MO-pruning blocker. Replacement is unjustified
  on current evidence; a follow-up with multi-swap reach + real-simulator budget could
  revisit.
- NSGA/MOTPE/BO internals stay `UNKNOWN`: there is no current equivalent to replace;
  adoption would be additive new code (e.g. MOTPE as one more proposal policy inside
  `AdaptiveWholeDeckSearch`), explicitly out of scope for this no-migration task.

## Validity limits

- Synthetic surrogate objectives, not the real structural simulator; single-swap space
  only; 400-eval micro-budget; 3 seeds. Directional discriminator, not a qualification.
- `pymoo`/`Ax`/`BoTorch`/`SMAC` judged on dependency/shape grounds without benchmarking;
  if a future real-simulator study shows the sampler as the bottleneck, re-open with
  Optuna-only first (pymoo only if a second NSGA implementation is needed for
  cross-validation; BoTorch/SMAC only with a dedicated cost justification).

## Recommendation

No production migration. Keep the hand-written optimizer; the only OSS door left open
is an *additive, gated* Optuna-sampler experiment (MOTPE proposals subject to the
unchanged custom legality gate, racing budgets, QD admission, and evidence logging),
to be proposed — if ever — as a separate task with real-simulator budget.
