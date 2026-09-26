# Statistical decision protocol

Every paired variant comparison reports requested, started, valid, failed and discarded runs; actual sample size; deterministic seeds; worker count; validation level; paired status; effect size; deterministic bootstrap interval; holdout definition; worst-case result; scenario and pilot weights; multiple-testing policy; and rounding policy.

Implemented methods:

- paired placement and mean differences;
- deterministic paired percentile bootstrap (2,000 resamples);
- standardized paired effect;
- Bayesian shrinkage toward a neutral prior;
- Holm family-wise correction when a family of p-values is supplied;
- Pareto ranking;
- worst-case and quantile summaries;
- distributionally robust lower bound;
- seed, scenario, pilot and provider sensitivity fields.

No universal win-rate threshold is used. Practical role, mana, rebuild, commander-dependence, package and large-pod trade-offs remain separate decision dimensions. Technical samples below 100 paired games cannot receive a robust recommendation status.
