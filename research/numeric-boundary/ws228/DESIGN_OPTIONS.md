# Design Options (WS228)

Common requirements for all families: Core defines domain; adapter
losslessly projects; pilot chooses within domain; native submission is
final authority; stale/malformed/out-of-domain fail closed; NO
clamp-to-range, nearest-legal, midpoint/random/min/max fallback, or default
choice. Pilot contract stays neutral (no XMage internals cross the
boundary — only ints, ids, labels, descriptors).

## A. FULL ENUMERATION

Lab expands a proven contiguous inclusive Core interval into all integer
PilotActionViews (today's span<=16 path extended to all spans).

- Correctness: CORRECT for the four proven classes (projection of a proven
  interval). Forbidden elsewhere without a new contiguity proof.
- Separation: good (pilot still picks among views; Lab validates membership).
- Fail-closed: unchanged (existing malformed/unknown handling).
- Replay: chosen value recorded; legal-set = canonical descriptor
  {min,max} (materializing full sets onto tape is wasteful — record the
  descriptor; see REPLAY_IMPACT.md).
- Hidden info: none added (ints carry no identity).
- Neutrality: full (ints only).
- Performance: UNBOUNDED RISK. Realistic X/life/token domains are small,
  but nothing today caps engine-supplied maxima (U1 UNKNOWN); a huge max
  materializes millions of views (memory/time) and interacts with pilot
  shortlist truncation (3-8), which would silently re-narrow a fully
  enumerated domain at the ranking stage. A span cap reintroduces
  narrowing — the very defect. REJECTED as preferred for this reason.
- Testability: offered-set assertions are easy.
- Compatibility: zero pilot-contract change.
- Burden: one-hunk change (delete the else branch).

## B. RANGE-NATIVE PILOT DECISION (preferred — see CHOSEN_DESIGN.md)

Pilot receives a bounded numeric-domain descriptor {kind, min, max} (+
outcome/prompt context) and returns one integer; Lab validates membership
against the exact authoritative bounds before submission (the projection
already does this downstream — Lab adds an early identical check).

- Correctness: CORRECT without any contiguity premise for the offered set
  (no enumeration); membership validation is proven projection.
- Separation: best — legality stays entirely in Core+projection; pilot
  gets a strategy-shaped API (choose a number, not rank N views).
- Fail-closed: identical + early membership rejection (same code, no
  fallback mapping).
- Replay: record (min, max, chosen); tape fields already exist.
- Hidden info: none. Neutrality: full (descriptor is engine-agnostic).
- Performance: O(1) at any span — pathological maxima are harmless.
- Testability: offered-descriptor assertions + boundary submissions.
- Compatibility: requires a pilot-contract addition
  (choose_number(state, domain, rng) -> int); deterministic pilots implement
  strategy (e.g. outcome-aligned extreme or computed lethal); default
  BasePilot implementation must FAIL CLOSED (raise), never default.
- Burden: medium (Lab branch + pilot method + validation + tests).

## C. LAZY / STRUCTURED DOMAIN

Semantic domain object supporting ranking/choice without materializing
(e.g. interval with sampling, quantiles, or strategy callbacks).

- Assessment: for single scalars, C collapses to B with extra machinery
  (no ranking problem exists once the pilot returns a number directly).
  For multi_amount vectors, the joint descriptor (legs + totals) IS the
  structured domain — adopted as part of B, not a separate family.
  REJECTED as a standalone family (unneeded complexity); its useful
  content is folded into B.

## D. KEEP {min,mid,max}

- Acceptable ONLY if Rules/Core restricted legality to those values.
  PROVEN FALSE: native callbacks accept every integer in [min,max]
  (HumanPlayer accept loops). Performance is never a legality argument.
  REJECTED unconditionally.

## Family × criterion summary

| criterion | A | B (preferred) | C | D |
|---|---|---|---|---|
| Rules correctness (proven classes) | yes | yes | yes | NO |
| no second engine | yes | yes | yes | n/a (defect) |
| fail-closed | same | same+early | same | silent narrowing |
| replay compat | descriptor | descriptor (fields exist) | descriptor | n/a |
| hidden info | none | none | none | none |
| provider neutrality | full | full | full | full |
| large-domain perf | UNBOUNDED | O(1) | O(1) | O(1) but wrong |
| testability | easy | easy | medium | n/a |
| compatibility | zero change | pilot method add | larger change | zero change |
| burden | trivial | medium | high | none |

Runner-up: A (correct but operationally unsafe at unbounded spans +
shortlist interaction). B wins on performance determinism and on removing
the ranking funnel from the legality path entirely.
