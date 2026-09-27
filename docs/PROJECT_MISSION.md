# Commander Simulator Next — project mission

## Outcome

Research, qualify, implement and harden the best realistically achievable full-rules
Magic: The Gathering Commander simulator, maximizing Rules Correctness. Its end-to-end
purpose is reproducible simulation of real Commander decks, learning from gameplay and
matchup evidence, pilot improvement, and better deck construction and optimization.
Learning and deck optimization are explicit product outcomes; they never justify rules
shortcuts or promote an unqualified simulator into decision authority. Perfect play or
perfect prediction is not assumed or claimed.

## Player-count policy

- Four players (one own deck, three opponents) is the primary benchmark and decision
  mode. It is not an architecture anchor, a fixed-size data-model requirement, or a
  reason to exclude otherwise better candidates or research.
- Technical conformance for 2–5 players is mandatory. Record evidence for each count;
  a 4P result does not establish another count's correctness.
- Prefer 6+ or generally variable-player solutions when they improve Rules Correctness,
  simplicity, reuse, testability, or research/implementation. This preference must not
  weaken Rules Correctness or the required 2–5P conformance.
- A target player-count capability is not runtime evidence. Unsupported paths remain
  fail closed until qualified. Existing Structural decision contracts and bounded
  lanes retain their implemented limits until separately changed and validated.

## Outcome-first architecture and research

Greenfield means a new simulator project, not necessarily a new Rules Engine. No
engine, language, framework, architecture, candidate list or workstream has incumbency
rights. Assess existing engines, complete simulators and frameworks neutrally, including
solutions outside the current candidate set. Research must look for end-to-end reuse
and alternatives that eliminate work, not only repairs inside current workstreams.

Reuse, fork, wrap, embed, port, differential reference, hybrid architecture and subsystem
rewrite are options. An existing solution may replace one or several entire workstreams
when evidence shows a better path to the end goal. Do not build a new general Rules
Core when a qualifiable existing solution is objectively better; do not retain an
engine or planned work merely because effort has already been invested.

Compare candidates first on Rules Correctness, real card behavior and coverage,
multiplayer correctness, hidden-information isolation, determinism/replay, authoritative
legal actions and pilot/rules separation; then on testability, implementation simplicity,
reuse and practical costs. Performance and pilot strength cannot compensate for rules
defects. Document evidence, unknowns, displaced workstreams, remaining gaps and the
proposed integration order. Workstream replacement requires explicit Coordinator
adjudication and ownership reconciliation before implementation; research alone does
not authorize conflicting writes, cancellation, deletion or broader implementation.

## Preserved authority and qualification gates

The Rules Core alone determines legality, costs, mana, stack, priority, targets, combat,
triggers, replacement/prevention, continuous effects/layers, state-based actions, zones,
copy/control semantics, Commander/multiplayer rules and Rules randomness. Pilots receive
principal-scoped observations and authoritative legal Decision Options and choose only
discretionary alternatives. No second hidden Rules Engine or silent fallback is allowed.

Actual-card-driven behavioral qualification, official Rules authority, controlled Rules
RNG, reproducible semantic replay and fail-closed unsupported paths remain mandatory.
UNKNOWN is not PASS; construction is not behavior; green CI or reference-engine parity
is not full qualification. A replacement does not inherit PASS credit automatically:
relevant code/pin/contract/harness/evidence changes require impact adjudication and
targeted requalification. This policy does not rewrite immutable qualification bundles.

GitHub remains canonical for repository policy and technical state. Drive and ChatGPT
project instructions are coordination mirrors; historical filenames and workstream
numbers do not establish authority. Fresh source locks take precedence over stale
reports. Keep existing push/merge and cross-workstream ownership gates.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`

Architecture Freeze requires Candidate Qualification and explicit Coordinator
adjudication. Do not create a new Production Repository before Freeze. Research,
remediation and candidate qualification remain in existing repositories. This document
changes governance only: no simulator semantics, runtime admission, engine pins,
qualification credit, canonical decks, inventories or pilot capabilities are changed.
