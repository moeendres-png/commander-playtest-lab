# WS220 Architecture Audit

Question: does the project currently have a technically coherent architecture?

## Verdict: COHERENT, with 4 bounded defects

The layering is sound and actually enforced: Rules Core (pinned XMage fork)
owns all legality; Our Pilots choose only among engine-offered options through
a blocking typed fail-closed controller; Structural/Tactical are demoted to
diagnostic-only with `structural_model_estimates` labeling; no second Rules
engine was found in any production-reachable path (static scan + controller /
projection / redactor reads: see BATCH2_NOTES.md C1).

Coherence evidence:
- Decision inventory ≡ policy classes ≡ callback inventory (17 classes).
- Authority split hardcoded in result payloads (`xmage_rules_authority=True`,
  `commander_lab_pilot_decision_authority=True`, structural/tactical False).
- Variable-player generalization (WS215) touched only cardinality plumbing;
  per-class transport paths for retained micro classes are behavior-identical
  at N=4 (verified by diff 592f23c9..67db0733).

Defects (all P1/P2, none structural):
1. F-RULES-02 (P1): numeric-domain narrowing (span>16 → {min,mid,max}) is the
   only observed engine-domain narrowing; undispositioned, untested.
2. F-RULES-03 (P2): five pilot-scope narrowings/defaults (single-offer
   bypass, mulligan cap, mana withhold, pool shortcut, prompt-sniff) need
   disposition; none expands legality.
3. F-HIDE-02/F-HIDE-03 (P1/P2): hidden-info assurance is XMage-lane-only and
   name-blind; structural/fixture surfaces unscoped.
4. F-REPLAY-01 (P1): replay contract XMage-taxonomy-bound, 12 risks open.

No architecture choice was found to be wrong at the layering level. The
candidate-neutral engine-wrapper strategy, fail-closed posture, and
demotion of Structural/Tactical all survive challenge. Do NOT redesign the
lane; disposition the narrowings, close the replay contract, keep the shape.
