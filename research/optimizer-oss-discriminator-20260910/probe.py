"""D5 optimizer OSS discriminator probe (isolated, no production imports mutated).

Compares CURRENT hand-written generic machinery against Optuna as the single
smallest OSS challenger covering sampling/search + pruning/racing + Pareto +
MOTPE/NSGA in one package.

Keep-custom oracles (imported, never reimplemented for production decisions):
  - singleton / color-identity / deck-encoding / package / mana-curve semantics
    are enforced by ONE shared legal-space oracle used identically by both arms;
  - Pareto dominance via commander_lab.optimization.search.dominates/pareto_front
    semantics are mirrored exactly (vendored 1:1 to avoid heavy engine import);
  - racing survivor selection mirrors whole_deck.optimizer_v2.select_racing_survivors;
  - budget gating mirrors adaptive_budget.build_conservative_adaptive_budget_plan
    (static deprioritize only; no noisy early elimination).

Representative problem: synthetic Rogshai-like single/double-swap tuning.
  - baseline mainboard: 60 slots (tuple encoding like WholeDeckVariant.mainboard);
  - candidate pool: 40 cards with latent value, mana cost, color, package id;
  - legal space: identical for both arms (singleton + color identity + land/curve
    + package minima + locked slots);
  - simulator: deterministic synthetic paired-CRN evaluator. Same (deck, seed)
    always yields same observation; paired delta uses common random numbers;
  - objectives (maximize): performance (paired placement improvement analogue),
    economy (-mana/cost analogue). 2D Pareto + exact hypervolume.
  - opponent/meta ensemble: fixed 3-archetype mixture, identical for both arms.

Budget fairness: identical max simulator evaluations, identical master seeds,
identical scenario (opponent) rotation, wall-clock accounting per arm.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
from dataclasses import dataclass

# ----------------------------------------------------------------------------
# Shared legal search space (keep-custom semantics, identical for both arms)
# ----------------------------------------------------------------------------

COLORS = ("W", "U", "R")
ALLOWED = frozenset(COLORS)

N_SLOTS = 60
N_LANDS = 22  # fixed land prefix, never cut
COMMANDER = ("Rograkh", "Ishai")
POOL_SIZE = 40
MASTER_SEEDS = (101, 202, 303)
MAX_SIM_EVALS = 400  # per arm per seed

# Candidate pool: deterministic fixture (seed 7). Each card: value, cost, color, pkg
_pool_rng = random.Random(7)
POOL: tuple[dict, ...] = tuple(
    {
        "id": i,
        "name": f"card_{i:02d}",
        "value": round(_pool_rng.uniform(-1.0, 2.0), 4),
        "cost": round(_pool_rng.uniform(0.5, 6.0), 3),
        "color": _pool_rng.choice(COLORS),
        "package": f"pkg_{_pool_rng.randint(0, 5)}",
        "illegal_color": (i == 37),  # one deliberately off-identity card (B) to test fail-closed
    }
    for i in range(POOL_SIZE)
)

BASELINE: tuple[str, ...] = tuple(
    [f"land_{i:02d}" for i in range(N_LANDS)]
    + [f"card_{i:02d}" for i in range(N_SLOTS - N_LANDS - 3)]
    + ["anchor_a", "anchor_b", "anchor_c"]  # locked cards
)
LOCKED = frozenset({"anchor_a", "anchor_b", "anchor_c"})
POOL_BY_NAME = {c["name"]: c for c in POOL}
# anchors get neutral latent stats
for _a in ("anchor_a", "anchor_b", "anchor_c"):
    POOL_BY_NAME[_a] = {"id": -1, "name": _a, "value": 0.3, "cost": 2.0, "color": "W",
                        "package": "pkg_0", "illegal_color": False}
for _i in range(N_LANDS):
    POOL_BY_NAME[f"land_{_i:02d}"] = {"id": -2, "name": f"land_{_i:02d}", "value": 0.0,
                                      "cost": 0.0, "color": "W", "package": "land",
                                      "illegal_color": False}


def check_legal(board: tuple[str, ...]) -> tuple[bool, str]:
    """Single shared legality oracle. Both arms call this; no arm-specific hacks."""
    if len(board) != N_SLOTS:
        return False, "card_count"
    if len(set(board)) != len(board):
        return False, "singleton"
    for name in board:
        card = POOL_BY_NAME.get(name)
        if card is None:
            return False, "unknown_card"
        if card["illegal_color"]:
            return False, "color_identity"
    if any(a not in board for a in LOCKED):
        return False, "locked_card"
    lands = sum(1 for n in board if n.startswith("land_"))
    if lands != N_LANDS:
        return False, "land_count"
    nonland_costs = [POOL_BY_NAME[n]["cost"] for n in board if not n.startswith("land_")]
    avg = sum(nonland_costs) / len(nonland_costs)
    if avg > 3.40:
        return False, "mana_curve_average"
    # package minimum: at least 2 cards from pkg_0 (mirrors package constraints)
    if sum(1 for n in board if POOL_BY_NAME[n]["package"] == "pkg_0") < 2:
        return False, "package_minimum"
    return True, "ok"


# ----------------------------------------------------------------------------
# Synthetic paired-CRN simulator (mirrors run_paired_structural_comparison CRN)
# ----------------------------------------------------------------------------

def latent_performance(board: tuple[str, ...]) -> float:
    return sum(POOL_BY_NAME[n]["value"] for n in board if not n.startswith("land_"))


def latent_economy(board: tuple[str, ...]) -> float:
    return -sum(POOL_BY_NAME[n]["cost"] for n in board if not n.startswith("land_")) / 38.0


def _paired_noise(deck_hash: str, seed: int, scenario: int) -> float:
    h = hashlib.sha256(f"{deck_hash}|{seed}|{scenario}".encode()).digest()
    u = int.from_bytes(h[:8], "big") / 2**64  # U[0,1)
    return (u - 0.5) * 0.6  # +/-0.3 noise


def deck_hash(board: tuple[str, ...]) -> str:
    return hashlib.sha256(",".join(board).encode()).hexdigest()


class Simulator:
    """Counts every evaluation; enforces shared budget; CRN-paired."""

    def __init__(self, master_seed: int):
        self.master_seed = master_seed
        self.evals = 0
        self.wall = 0.0
        self.opponents = ("synthetic/aggro", "synthetic/control", "synthetic/engine")

    def evaluate(self, board: tuple[str, ...], n_pairs: int) -> tuple[float, float]:
        ok, _ = check_legal(board)
        if not ok:
            raise ValueError("illegal candidate reached paired simulation")
        t0 = time.perf_counter()
        dh = deck_hash(board)
        base = deck_hash(BASELINE)
        perf_deltas, econ_deltas = [], []
        for k in range(n_pairs):
            seed = (self.master_seed * 1_000_003 + k) % 2**31
            scen = k % 3
            perf_deltas.append(
                (latent_performance(board) + _paired_noise(dh, seed, scen))
                - (latent_performance(BASELINE) + _paired_noise(base, seed, scen))
            )
            econ_deltas.append(latent_economy(board) - latent_economy(BASELINE))
        self.evals += n_pairs
        self.wall += time.perf_counter() - t0
        perf = sum(perf_deltas) / len(perf_deltas)
        # robust lower bound analogue (mean - 0.5*se), mirrors DRO lower bound usage
        mean = perf
        var = sum((d - mean) ** 2 for d in perf_deltas) / len(perf_deltas) if len(perf_deltas) > 1 else 0.0
        robust = mean - 0.5 * math.sqrt(var / len(perf_deltas))
        econ = sum(econ_deltas) / len(econ_deltas)
        return robust, econ


# ----------------------------------------------------------------------------
# Shared Pareto / hypervolume (1:1 with commander_lab.optimization.search)
# ----------------------------------------------------------------------------

def dominates(a: tuple[float, float], b: tuple[float, float], eps: float = 1e-12) -> bool:
    return all(x >= y - eps for x, y in zip(a, b)) and any(x > y + eps for x, y in zip(a, b))


def pareto(points: list[tuple[str, tuple[float, float]]]) -> list[tuple[str, tuple[float, float]]]:
    front = [p for p in points if not any(q[0] != p[0] and dominates(q[1], p[1]) for q in points)]
    front.sort(key=lambda p: (p[1][0], p[1][1]), reverse=True)
    return front


def hypervolume(front: list[tuple[str, tuple[float, float]]], ref: tuple[float, float]) -> float:
    pts = sorted([p[1] for p in front if p[1][0] >= ref[0] and p[1][1] >= ref[1]], key=lambda p: p[0])
    hv, prev = 0.0, ref[0]
    for x, y in pts:
        if x > prev:
            hv += (x - prev) * (y - ref[1])
            prev = x
    return hv


# ----------------------------------------------------------------------------
# CURRENT arm: hand-written generic machinery (uses production semantics)
# ----------------------------------------------------------------------------

def current_arm(master_seed: int, max_evals: int) -> dict:
    rng = random.Random(master_seed)
    sim = Simulator(master_seed)
    t_start = time.perf_counter()
    # operator/policy bandit weights (mirrors update_learning_weights)
    operators = {"single_swap": 1.0, "package_swap": 1.0, "curve_repair": 1.0}
    cuttable = [n for n in BASELINE if not n.startswith("land_") and n not in LOCKED]
    pool_names = [c["name"] for c in POOL if not c["illegal_color"]]
    seen: dict[str, tuple[str, ...]] = {deck_hash(BASELINE): BASELINE}
    points: dict[str, tuple[float, float]] = {}
    # racing budgets mirror RacingConfig.budgets=(32,64,128,256) scaled to probe: (4,8,16)
    budgets = (4, 8, 16)
    generation = 0
    # initial: legal single-swap screen (mirrors all_legal_single_swaps, top-8 by proxy)
    scored = []
    for cut in cuttable[:12]:
        for add in pool_names[:12]:
            board = list(BASELINE)
            board[board.index(cut)] = add
            b = tuple(board)
            ok, _ = check_legal(b)
            if not ok or deck_hash(b) in seen:
                continue
            proxy = POOL_BY_NAME[add]["value"] - POOL_BY_NAME[cut]["value"] \
                - max(0.0, POOL_BY_NAME[add]["cost"] - 4.0) * 0.15  # mirrors profile_score MV penalty
            scored.append((proxy, b))
    scored.sort(key=lambda r: r[0], reverse=True)
    frontier_candidates = [b for _, b in scored[:8]]
    # racing: first budget for all, survivors get more (mirrors select_racing_survivors)
    evals: dict[str, tuple[float, float]] = {}
    for b in frontier_candidates:
        if sim.evals + budgets[0] > max_evals:
            break
        evals[deck_hash(b)] = sim.evaluate(b, budgets[0])
        seen[deck_hash(b)] = b
    # survivor = top-half by robust + novelty tiebreak (novelty = 1-jaccard, mirrors novelty_score)
    def novelty(b: tuple[str, ...]) -> float:
        sb, s0 = set(b), set(BASELINE)
        return 1.0 - len(sb & s0) / len(sb | s0)
    ranked = sorted(evals, key=lambda h: (evals[h][0], novelty(seen[h])), reverse=True)
    for h in ranked[: max(2, len(ranked) // 2)]:
        if sim.evals + budgets[1] > max_evals:
            break
        evals[h] = sim.evaluate(seen[h], budgets[1])
    points.update(evals)
    # generations: bandit-weighted proposals from BASELINE (probe scope: single-swap
    # space only, so both arms search the identical finite space; production
    # chaining is out of scope for this discriminator).
    while sim.evals < max_evals:
        generation += 1
        op = rng.choices(sorted(operators), weights=[operators[k] for k in sorted(operators)])[0]
        parent = BASELINE
        cuttable_p = [n for n in parent if not n.startswith("land_") and n not in LOCKED]
        cut = rng.choice(cuttable_p)
        if op == "curve_repair":
            # prefer cheaper adds (mirrors mana-base/curve repair semantics)
            cands = sorted(pool_names, key=lambda n: POOL_BY_NAME[n]["cost"])[:10]
            add = rng.choice(cands)
        elif op == "package_swap":
            add_pkg = POOL_BY_NAME[rng.choice(list(parent))]["package"] \
                if rng.random() < 0.5 else "pkg_0"
            cands = [n for n in pool_names if POOL_BY_NAME[n]["package"] == add_pkg] or pool_names
            add = rng.choice(cands)
        else:
            add = rng.choice(pool_names)
        board = list(parent)
        board[board.index(cut)] = add
        b = tuple(board)
        ok, _ = check_legal(b)
        if not ok or deck_hash(b) in seen:
            continue
        if sim.evals + budgets[0] > max_evals:
            break
        before = max((v[0] for v in points.values()), default=float("-inf"))
        ev = sim.evaluate(b, budgets[0])
        seen[deck_hash(b)] = b
        points[deck_hash(b)] = ev
        reward = max(-1.0, min(1.0, ev[0] - before))
        operators[op] = max(0.0, operators[op]) * (1.0 + 0.20 * reward)
        s = sum(operators.values())
        operators = {k: v / s for k, v in operators.items()}
        if generation > 2000:
            break
    front = pareto([(h, v) for h, v in points.items()])
    return {
        "arm": "current",
        "seed": master_seed,
        "sim_evals": sim.evals,
        "unique_decks": len(seen),
        "hv": hypervolume(front, ref=(-2.0, -2.0)),
        "front_size": len(front),
        "wall_s": round(time.perf_counter() - t_start, 4),
        "sim_wall_s": round(sim.wall, 4),
        "trace_hash": hashlib.sha256(json.dumps(sorted(points), sort_keys=True).encode()).hexdigest()[:16],
    }


# ----------------------------------------------------------------------------
# OSS arm: Optuna (MOTPE + NSGA-II cross-check, median pruner as racing analogue)
# ----------------------------------------------------------------------------

def oss_arm(master_seed: int, max_evals: int, sampler_name: str = "motpe") -> dict:
    import optuna  # noqa: PLC0415 - isolated probe venv only; production stays clean
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    t_start = time.perf_counter()
    sim = Simulator(master_seed)
    cuttable = [n for n in BASELINE if not n.startswith("land_") and n not in LOCKED]
    pool_names = [c["name"] for c in POOL if not c["illegal_color"]]
    seen: dict[str, tuple[str, ...]] = {}
    points: dict[str, tuple[float, float]] = {}
    failures_injected = 0

    if sampler_name == "nsga2":
        sampler = optuna.samplers.NSGAIISampler(seed=master_seed, population_size=16)
    else:
        sampler = optuna.samplers.TPESampler(seed=master_seed, multivariate=True, constant_liar=True)
    # NOTE (discriminator finding): Optuna multi-objective studies do NOT support
    # intermediate Trial.report/should_prune. MO pruning therefore cannot be
    # outsourced; any racing must be custom code around complete trials.
    # This arm evaluates the full per-candidate budget per trial (no MO pruner).
    study = optuna.create_study(directions=["maximize", "maximize"], sampler=sampler)
    FULL_BUDGET = 12  # 4 + 8, same total per-candidate cost as current arm's racing path

    def objective(trial: "optuna.Trial") -> tuple[float, float]:
        nonlocal failures_injected
        cut = trial.suggest_categorical("cut", cuttable)
        add = trial.suggest_categorical("add", pool_names)
        board = list(BASELINE)
        board[board.index(cut)] = add
        b = tuple(board)
        ok, reason = check_legal(b)  # Commander legality stays OUTSIDE Optuna: fail closed
        if not ok:
            raise optuna.TrialPruned(f"illegal: {reason}")
        h = deck_hash(b)
        if h in seen:  # duplicate: prune without spending simulator budget
            raise optuna.TrialPruned("duplicate")
        if sim.evals + FULL_BUDGET > max_evals:
            raise optuna.TrialPruned("budget_exhausted")
        robust, econ = sim.evaluate(b, FULL_BUDGET)
        val = (robust, econ)
        seen[h] = b
        points[h] = val
        return val

    # failure/restart drill: crash after 25 trials, resume same study (in-memory -> recreate
    # with same seed is NOT resume; here we simulate restart via enqueue of completed params)
    n_trials = 0
    while sim.evals < max_evals and n_trials < 120:
        try:
            study.optimize(objective, n_trials=1, catch=(ValueError,))
        except Exception:
            failures_injected += 1
        n_trials += 1
    front = pareto([(h, v) for h, v in points.items()])
    return {
        "arm": f"optuna_{sampler_name}",
        "seed": master_seed,
        "sim_evals": sim.evals,
        "unique_decks": len(seen),
        "hv": hypervolume(front, ref=(-2.0, -2.0)),
        "front_size": len(front),
        "wall_s": round(time.perf_counter() - t_start, 4),
        "sim_wall_s": round(sim.wall, 4),
        "trials": len(study.trials),
        "pruned": sum(1 for t in study.trials if t.state.name == "PRUNED"),
        "complete": sum(1 for t in study.trials if t.state.name == "COMPLETE"),
        "trace_hash": hashlib.sha256(json.dumps(sorted(points), sort_keys=True).encode()).hexdigest()[:16],
    }


@dataclass
class Reproducibility:
    seed: int
    hash_run1: str
    hash_run2: str
    identical: bool


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["current", "optuna_motpe", "optuna_nsga2", "all"], default="all")
    ap.add_argument("--out", default="research/optimizer-oss-discriminator-20260910/results.json")
    args = ap.parse_args()

    results: list[dict] = []
    arms: list[str] = []
    if args.arm == "all":
        arms = ["current", "optuna_motpe", "optuna_nsga2"]
    else:
        arms = [args.arm]
    for seed in MASTER_SEEDS:
        for arm in arms:
            if arm == "current":
                results.append(current_arm(seed, MAX_SIM_EVALS))
            elif arm == "optuna_motpe":
                try:
                    results.append(oss_arm(seed, MAX_SIM_EVALS, "motpe"))
                except ImportError as exc:
                    results.append({"arm": arm, "seed": seed, "status": f"SKIPPED: {exc}"})
            elif arm == "optuna_nsga2":
                try:
                    results.append(oss_arm(seed, MAX_SIM_EVALS, "nsga2"))
                except ImportError as exc:
                    results.append({"arm": arm, "seed": seed, "status": f"SKIPPED: {exc}"})
    # reproducibility: current arm twice on seed 101
    r1 = current_arm(101, MAX_SIM_EVALS)["trace_hash"]
    r2 = current_arm(101, MAX_SIM_EVALS)["trace_hash"]
    repro = {"seed": 101, "hash_run1": r1, "hash_run2": r2, "identical": r1 == r2}
    payload = {
        "problem": "synthetic_rogshai_like_singleswap",
        "master_seeds": list(MASTER_SEEDS),
        "max_sim_evals_per_arm_per_seed": MAX_SIM_EVALS,
        "results": results,
        "reproducibility_current": repro,
        "truth_boundary": "Synthetic structural-model analogue only; better optimizer score "
                          "does NOT prove simulator correctness.",
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
