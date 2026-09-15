# WS220 Efficiency Audit

Constraint honored throughout: efficiency subordinate to correctness; every
item below is a safe improvement, never a shortcut.

## Findings

1. Compute: workstream Maven rebuilds justified (bridge changed each time);
   full source builds rare + lineage-proofed. Sink = CI repetition ×
   floating deps (fix via S15 lock, not via fewer builds).
2. Runs: neutral RQ-C3 games with 16/17 zero-offer constructions re-driven
   3–4×. Fix = dealing/budget policy per WS207 S-MECH-3 (tutor/draw suites),
   not fewer workstreams.
3. Prompts: ~2–4KB dedup headroom (implementer↔AGENTS↔ROUTING); dynamic
   context already optimal (/work+capsule). No authority prose cut.
4. Selection: `test_impact.py` advisory-only, zero CI consumers. Wire as
   non-gating CI advisory comment; keep contract suites authoritative.
5. Evidence bulk: 6.6M lines across 10k files, human-unreviewable. Fix =
   integrity predicates (S8) + reconciled rollup (S2), not less evidence.
6. FULL107: correctly NOT_RUN; retire-as-unit needs ratification (S14/S2).
7. Research rediscovery: P-SRC-01 probe now committed and rerunnable —
   future source-truth questions start from machine output, not re-reading.

## Explicitly NOT worth doing

- Broad-suite green-chasing across lanes before env lock (meaningless green).
- Prompt-stripping authority doctrine (saves cached bytes, risks nothing
  except everything).
- Pruning evidence bulk for aesthetics (bulk is the audit trail; index it).
- Running FULL107 "because it exists" (decision value negative).
- 6P implementation before architecture review (mission-sufficient at 2–5P
  + fail-closed).
