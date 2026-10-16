# Phase 10 End-to-End Acceptance

Run:

```bash
commander-lab accept-phase10 \
  --iterations 12 \
  --workers 2 \
  --seed 20260805 \
  --root .
```

The workflow performs:

- deck import and validation;
- physical allocation check;
- structure inspection;
- four representative primary four-player pods;
- commander-denial stress test;
- card and package ablation;
- candidate screening and targeted swap matrix;
- Pareto evaluation;
- paired A/B comparison;
- holdout and sensitivity tests;
- tactical rules sample;
- red-team review;
- final non-applied recommendation.

A candidate can only receive `validated_upgrade` when the structural chain passes, physical constraints pass and a real external rules-engine sample passes. Tactical-oracle evidence alone is insufficient.

All simulation values are `structural_model_estimates`, not empirical win rates.
