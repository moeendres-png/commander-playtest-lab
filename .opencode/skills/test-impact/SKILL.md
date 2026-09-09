---
name: test-impact
description: Determine conservative affected test and evidence surfaces after a change, requiring requalification when impact is uncertain.
---

# Test Impact

## Procedure

1. List every file changed in the working tree and recent commits.
2. Map each change to the test and evidence surfaces that exercise it (unit, regression,
   qualification, workflow, contract, and artifact surfaces).
3. Apply the conservative rule: never infer unaffected semantics merely to save
   runtime. When impact is uncertain, classify the surface as requiring
   requalification rather than assuming safety.
4. Historical PASS may be retained only after explicit impact adjudication against
   the exact changed surface and pinned dependencies. Record what was retained, what
   was rerun, and why.
5. Never order a full historical qualification campaign merely for reassurance; rerun
   the smallest surface that covers the adjudicated impact, then broaden only on failure.

## Rules

- A green subset never qualifies an unrun surface. Unrun stays `NOT_RUN`.
- Material source, pin, contract, harness, or semantic-model changes invalidate
  dependent historical PASS until requalified.
- Impact adjudication (what to retain, what to rerun) is a technical decision:
  make it from evidence and persist the reasoning. Changing what counts as
  qualification credit would be a policy decision — that is an `AUTHORITY_GATE`,
  not yours to ratify.
