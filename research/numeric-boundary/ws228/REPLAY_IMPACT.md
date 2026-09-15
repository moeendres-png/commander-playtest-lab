# Replay Impact (WS228 — design level; replay NOT modified)

WS218 semantic replay is PASS. The chosen design preserves it without
schema changes.

## Current tape facts (locked code, verified by read)

- TapeReplayStep already carries numeric_min, numeric_max, numeric_choice
  (tape.py:108-128, with invariant: bounds both-or-neither; choice within
  recorded bounds; choice requires bounds).
- recorder.py captures context numeric_min/max + response numeric_choice
  per step (lines 356-361, 420-422; drain path 463-468, 516-518).
- consumer.py re-validates context bounds equality (303-305) and replays
  numeric_choice (360-361); numeric-only steps submit empty selections.
- fingerprint.py treats target-like classes (incl target_amount) with
  target/choice semantics; event digests bind numeric_choice
  (recorder event_digest_for_step numeric_choice=...).
- Legal-set digest for numeric-only steps: legal options list is EMPTY
  (bridge sends zero options + bounds) — the digest therefore covers the
  bounds only insofar as _legal_options_of includes context. S6 must
  confirm the legal_set_digest binds (min,max[,legs,totals]); if it binds
  options-only today, S6 extends the digest input to the canonical
  descriptor (a recorder-side strengthening, not a semantic change).

## Required mapping (chosen design B)

| concept | tape representation |
|---|---|
| decision_class | unchanged (announce_x/amount/multi_amount/target_amount) |
| legal-set semantics | canonical descriptor: {min,max} scalar; {legs,totals} vector. NEVER the materialized member list (unbounded + twin-fragile). |
| semantic option identity | numeric domain descriptor digest (not per-value ids; `numeric:{v}` view ids disappear with the ranking funnel) |
| chosen semantic choice | numeric_choice int (scalar) / ordered int list (vector — ADD a vector field; scalar field stays for scalars) |
| duplicate/ambiguity | none: ints are self-identical; vector order = leg order |
| tape canonicalization | descriptor-first: digest = H(kind|min|max|...); chosen value bound in event digest as today |

## WS226/S6 integration impact

- WS226 consolidates WS218 replay PASS unchanged (replay files
  byte-identical WS223→WS226 — verified in delta revalidation).
- S6 must add exactly one tape affordance: ordered-vector choice for
  multi_amount (or encode as deterministic string — prefer a typed
  `numeric_choices: tuple[int,...]` field; scalar path untouched).
- Numeric-step replay digests WILL change shape (descriptor replaces view
  ids) — expected, versioned under the tape contract (v1 -> minor bump
  per WS218 contract rules; S6 follows the WS218 versioning procedure,
  no ad-hoc fields).
- Consumer bounds-equality check (303-305) extends naturally to legs/totals.
- No replay behavior credit is claimed by WS228; S6 re-runs the WS218
  dual-replay positives for numeric-bearing scenarios (see S6_TEST_PLAN.md).

## What S6 must NOT do

- Record materialized legal sets (performance + canary UUID risks).
- Record pilot-internal strategy (weights, shortlists) — replay binds
  domain + choice + digests, never deliberation.
- Weaken the bounds/choice invariant in tape.py (it is the exact
  machine-checked form of "Core defines domain, pilot chooses within").
