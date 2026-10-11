# Commander Simulator Next — project mission

## Outcome

Build a practical Magic: The Gathering Commander simulator that helps with real
deck-building decisions. It plays real 100-card Commander decks rules-correctly, so
that simulated games stand in for real games, and it lets us learn from gameplay and
matchup evidence: deck and card choices, matchups, pilot improvement and deck
optimization.

- Rules-correct play is required, but it is a means to realistic games, not a goal
  in its own right. Maximal rules correctness is not the top doctrine. Where full
  correctness for a rare interaction is unreachable or would mean chasing defects
  without end, record the gap, keep it visible, and move on.
- Coverage matters: simulate as many effects, abilities and therefore cards as
  possible, including cards the base XMage engine does not cover, so that real decks
  can be played as they are.
- Four players (one own deck, three opponents) is the usual game. Other player
  counts are supported where useful; there is no separate per-count conformance
  mandate.
- Perfect play or perfect prediction is not assumed or claimed.

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

Compare candidates on real card behavior and coverage, rules correctness, multiplayer
behavior, hidden-information isolation, determinism/replay, authoritative legal actions
and pilot/rules separation, testability, implementation simplicity, reuse and practical
costs. Document evidence, unknowns, displaced workstreams, remaining gaps and the
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

Architecture Freeze and production-provider status are recorded in `AGENTS.md` §1.

Architecture Freeze requires Candidate Qualification and explicit Coordinator
adjudication. Do not create a new Production Repository before Freeze. Research,
remediation and candidate qualification remain in existing repositories. This document
changes governance only: no simulator semantics, runtime admission, engine pins,
qualification credit, canonical decks, inventories or pilot capabilities are changed.
