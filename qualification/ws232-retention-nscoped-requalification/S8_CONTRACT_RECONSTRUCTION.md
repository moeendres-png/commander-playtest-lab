# WS232 S8 Contract Reconstruction (from source, not summary)

Source: `research/project-audit/ws220/SUCCESSOR_PROPOSALS.json`
(schema `ws220-successor-1.0.0`), node S8.

## S8 exact proposal

- id: S8
- objective: "Machine-checked retention predicates + N-scoped rerun of retained-47"
- dependencies: ["S2", "S6", "S7"]
  (S2 AF/G rollup matrix; S6 numeric disposition; S7 name-canary negatives)
- evidence_requirements: "predicate tests green (retained-path stability
  machine-checked); N-scoped disposition sealed; CARD_29/MICRO_13/replay
  reruns at 2P/3P/5P sealed"
- forbidden_shortcuts: ["new prose-only retention",
  "4P-only reasoning for N!=4 rows", "behavior credit without runtime"]
- hard_gates: ["every RETAINED row carries a machine predicate or a rerun
  pointer", "disposition N-scoped; 47-row hole at 2/3/5P closed or
  explicitly UNKNOWN"]
- mutation_surface: "tests/unit predicate tests, disposition schema +
  rerun matrices (fresh JVM runs)"
- mission_value: "makes retention survive future repins; closes per-count
  AF02 hole"
- parallelism_constraints: "after S6/S7; largest JVM bill in the graph"
- recommended_effort: high

## Action graph position

Edges: S2->S8, S10->S8, S6->S8, S7->S8, S8->S9.
S8 is behavior-evidence, "Retention predicates + N-scoped reruns".
Phase gate: "135 disposition refreshed; AF02/AF06/AF07/AF08 closable per-count".
S8 -> S9 (trigger-rich multiplayer closers). S9 is out of scope for WS232.

## WS232 reading (hard gates operationalized)

1. Every RETAINED row (47): machine-checkable stability predicate OR exact
   current rerun pointer. Predicate binds the semantic premise retention
   rests on (engine commit, owning Lab/bridge blobs, fixture/scenario bytes,
   protocol, replay schema, RNG authority, player-count code paths); a hash
   alone is never the proof — the hashed path must own the semantics.
2. Disposition is N-scoped: every material row distinguishes 2P/3P/5P
   independently. 4P only where impact analysis shows positive decision
   value. No 4P-only reasoning for N != 4.
3. The inherited retained-47 hole at 2P/3P/5P is closed by current rerun
   evidence, or each unclosed cell stays explicitly UNKNOWN.
4. CARD_29 / MICRO_13 / replay_5 requalified at 2P/3P/5P with behavior
   evidence (construction/import/readback insufficient; XMage sole legality
   authority; no outcome injection).
5. WS229 U5 carry-forward: card-driven amount / multi_amount /
   target_amount fires; numeric-bearing semantic replay (record + independent
   replay); current 5P post-WS229 impact; 4P only on positive decision value.
6. 16 S9 UNKNOWN rows preserved (neither upgraded nor lost).
7. Standing changes only via the living generator; manifest integrity GREEN;
   FULL107 NOT_RUN; no Architecture Freeze / Provider claims.

Semantic Completion: every required cell terminally classified
(PASS/FAIL/UNKNOWN) with adequate evidence. UNKNOWN is not PASS.
Real FAILs fail the affected rows and charter remediation; they do not
force infinite looping.
