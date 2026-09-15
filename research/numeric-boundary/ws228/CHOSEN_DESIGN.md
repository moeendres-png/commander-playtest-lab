# Chosen Design: B — Range-Native Pilot Decision (WS228)

## Decision

S6 implements family B: the pilot receives an authoritative bounded
numeric-domain descriptor and returns one integer; the Lab validates exact
membership against the Core-supplied bounds before submission. No
enumeration, no fallback mapping, no second Rules engine.

## Exact shapes (provider-neutral; no XMage internals cross the boundary)

Scalar domain (announce_x, amount, target_amount companion):

```python
NumericDomain = {
    "kind": "contiguous_inclusive_int",  # only for the four proven classes
    "min": int,   # == context numeric_min (Core-authoritative)
    "max": int,   # == context numeric_max (Core-authoritative)
    "outcome": str,  # existing outcome hint (strategy only)
    "prompt": str,   # display only
}
```

Pilot contract addition (agents/pilots.py):

```python
def choose_number(self, state, domain: NumericDomain, rng) -> int: ...
```

- BasePilot.choose_number default: RAISE (fail closed — never default).
- Concrete pilots implement strategy (deterministic: outcome-aligned
  computation; stochastic: seeded draw + strategy). Strategy chooses;
  legality is never the pilot's question.
- Lab path (_decide_numeric replacement): build descriptor from context
  bounds (still requiring explicit numeric_min/numeric_max; reversed
  bounds still raise); call pilot.choose_number; validate
  min <= returned <= max else FullGameProtocolError (no clamp, no
  nearest, no fallback); return the int. Malformed (non-int) -> same
  malformed-decision error as today.

Joint vector (multi_amount — restores native single-decision semantics):

```python
MultiAmountDomain = {
    "kind": "joint_bounded_int_vector",
    "legs": [{"min": int, "max": int, "prompt": str}],
    "total_min": int,
    "total_max": int,
    "outcome": str,
}
def choose_numbers(self, state, domain, rng) -> list[int]: ...
```

Lab validates: length match, per-leg inclusive membership, total band —
the exact isGoodValues predicate, projected, not invented. Bridge
sequentializer (XmageFullGamePlayer:949-969) becomes a transport shim ONLY
if the DecisionController cannot carry a joint frame (U4); the
pilot-facing shape is joint regardless. Per-leg frames, if retained for
transport, carry the S6 scalar path (no narrowing) — never the old
{min,mid,max} collapse.

## Why this is not a second Rules engine

The Lab computes no legality: bounds arrive verbatim from Core; the
membership predicate (min <= v <= max; joint isGoodValues projection) is
identical to the downstream projection check and to native acceptance.
The Lab cannot authorize anything Core did not authorize, and cannot
refuse anything Core authorized (no cap, no truncation). Rejected
alternatives and the strict contiguity condition are in DESIGN_OPTIONS.md
and DOMAIN_AUTHORITY_ANALYSIS.md.

## Pilot-authority preservation (hard rules for S6)

- Core defines domain; adapter projects losslessly; pilot chooses within;
  native submission is final.
- Stale/malformed/out-of-domain -> fail closed (existing error taxonomy).
- No clamp-to-range / nearest-legal / midpoint / random / default-min-max.
- BasePilot numeric defaults raise; no silent strategy.

## Replay mapping (detail in REPLAY_IMPACT.md)

Record per numeric step: descriptor {min,max} (+ legs/totals for vectors)
and chosen value — exactly the TapeReplayStep fields that already exist
(numeric_min/numeric_max/numeric_choice). No schema change needed; S6 adds
no new tape semantics, only populates existing fields from the new path.

## Performance disposition (detail in PERFORMANCE_BOUNDARY.md)

O(1) views per numeric decision at any span. Pathological maxima (U1)
cannot inflate memory/time because nothing is materialized. Pilot
shortlist interaction disappears (no ranking funnel on the legality path).

## Backward compatibility

- Protocol frame unchanged (context numeric_min/max; response
  numeric_choice) — bridge untouched for scalars.
- PilotActionView flow untouched for all non-numeric classes.
- Deterministic-pilot behavior on small domains will CHANGE (strategy
  replaces ranking) — expected and intended; S6 re-baselines twin-stable
  expectations for numeric steps only (replay digests for numeric steps
  change shape: chosen value still recorded; offered-set digests must use
  the canonical descriptor, never materialized views).
