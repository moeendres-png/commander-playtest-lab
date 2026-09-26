---
name: component-change-review
description: Review one changed component against its tests, evidence, and contract surface before validation credit.
---

# Component Change Review

Use when a component (tool, config, skill, doc with normative force) changed
and needs review before its commit earns `validated_head` credit.

## Procedure

1. Identify the exact changed surface (`git diff` / `git status`).
2. Map it to tests with `tools/foundry/test_impact.py --base <sha>`; run at
   least the mapped minimum plus every contract-required suite.
3. Verify no weakened assertions, no narrowed denominators, no relaxed
   expected semantics introduced to obtain green.
4. Verify no new production-reachable legality, fallback, or default crept in
   (Rules authority stays in the Rules Core; see `AGENTS.md` §2).
5. Verify evidence classifications are honest (`UNKNOWN` stays `UNKNOWN`).

## Rules

- `AGENTS.md` is already privileged instruction; do not restate it.
- A green subset never qualifies an unrun surface.
- If impact is uncertain, require requalification — never assume safety.
- Record the review as a `technical_decisions` entry; validation credit lands
  in `validated_head` only after the mapped tests actually pass.
