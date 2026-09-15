# Successor Recommendation (post-WS229 execution shape)

Evidence class: `MODELED` (sequencing judgment from mutation surfaces + dependencies, not habit).

## Recommended shape: THREE sequenced workstreams (not one combined)

Rationale: the three surfaces touch different files, need different runtimes, and have a strict dependency order. One combined workstream would mix XMage Python-facade edits, Forge JVM-adjacent consumption, and deployment/topology qualification in a single mutation surface — maximizing blast radius and review confusion.

### S-INT-1 — XMage AF01 facade (first)
- **Surface**: one new CPL Python module (`xmage_rsp_facade.py`) + tests; NO Java changes (option-A precedent); NO pin/authority edits.
- **Depends on**: WS229 terminal (delta predicates green) + this preflight.
- **Delivers**: RSP HELLO/DECISION/OBSERVE/SUBMIT/CLOSE over the full-game lane; `options_digest`; 9 negative classes; AF01 runtime evidence for XMage on declared topology (local child first).
- **Parallelism**: independent of S-INT-2 once both read this preflight (different files, different providers).

### S-INT-2 — Forge Lab consumer (second, parallelizable with S-INT-1)
- **Surface**: new CPL Python modules (`forge_rsp_facade.py`, `forge_process.py`, later `forge_replay_consumer.py`) + tests; NO Forge-repo edits; NO CPL authority edits.
- **Depends on**: this preflight + then-current Forge pin re-verification (dual SHAs) + stabilized CPL line (post-S8/S9 window; see `ROADMAP_IMPACT.md`).
- **Delivers**: RSP facade over Protocol 2.0.0 + SemanticReplay; fresh-JVM launcher with single-flight discipline; AF01 runtime evidence for Forge (bounded, honest 5P gap); LATER the Lab-side replay consumer + hidden-info campaign (separate milestones inside S-INT-2, not new workstreams).

### S-INT-3 — Topology qualification (last, per selected candidate)
- **Surface**: deployment records + topology test evidence + license-review receipts; minimal code (launcher/config notes only).
- **Depends on**: provider selection + S-INT-1/S-INT-2 evidence for the chosen candidate.
- **Delivers**: the G12/AF11 gate transition bundle (`G12_AF11_GATE_ANALYSIS.md` §3): declared model + interop runtime + isolation negatives + hidden-info-through-IPC evidence + license record. Only this workstream can move G12/AF11.

## Exact sequence

```
WS229 terminal → delta predicates → S-INT-1 ─┐
                                             ├→ provider selection → S-INT-3 (chosen candidate/topology)
WS229 terminal → stabilized line → S-INT-2 ──┘
(S8/S9 behavior path runs on production surfaces; S-INT-1/2 touch only NEW facade files + tests until integration point — see ROADMAP_IMPACT.md)
```

## Parallelism rules

- S-INT-1 ∥ S-INT-2: YES (disjoint files, disjoint providers, shared read-only preflight).
- S-INT-3 ∥ anything: NO (needs selection + prior evidence).
- None of S-INT-1/2/3 may race S8/S9 production surfaces (new files + tests only until the safest integration point).
