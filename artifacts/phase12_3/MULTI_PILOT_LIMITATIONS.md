# Multi-Pilot System Limitations

- All benchmark outputs are `structural_model_estimates`, not empirical win rates.
- No XMage or Forge runtime was executed; the external differential test remains skipped.
- Pilot information is limited to `PilotStateView`, known cards and a declared plausible opponent-hand model. Hidden hands, future draws and library order are unavailable.
- Structural action metadata compresses full Magic rules and politics; political visibility is an explicit proxy based on hostile targeting and archenemy status.
- Four games per profile were used for the saved handoff benchmark. This is sufficient for a deterministic smoke benchmark, not for stable effect-size claims.
- `test_variant_across_pilots` evaluates registered structural deck versions and never applies a deck change.
- The recovered 1.2.0 repository omitted one generated replay referenced by two tests. Phase 12.3 moved that evidence to a tracked, immutable test fixture.
