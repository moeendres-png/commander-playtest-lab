# Commander Simulation Foundry — Repository Agent Policy

This file contains durable repository instructions for coding agents working on
`moeendres-png/commander-playtest-lab`.

It is intentionally limited to stable architecture, source-truth, execution,
validation, and evidence rules. Do not place volatile workstream status, current
candidate scores, temporary source locks, model prices, or historical PASS matrices
here.

## 1. Project Objective

Build and qualify the technically strongest reproducible Magic: The Gathering
full-rules simulation system for real Commander deck decisions.

Correctness takes priority over preserving historical implementations, languages,
engines, or sunk work. Existing simulator code, Forge/XMage integrations, old reports,
and earlier workstreams are evidence and reuse sources, not automatically binding
architecture.

Optimization priority:

1. Rules correctness
2. Real card functionality
3. Relevant card coverage
4. Multiplayer correctness
5. Hidden information
6. Determinism / replay
7. Legal-action correctness
8. Pilot / Rules separation
9. Testability / debuggability
10. Performance
11. Pilot strength
12. Deckbuilding optimization

Performance never justifies a Rules shortcut.

## 2. Source Truth

When sources conflict, use this order:

1. newest direct user instruction;
2. freshly verified relevant repository / branch / commit state;
3. current canonical domain data;
4. current primary sources;
5. older reports, handoffs, chats, and historical artifacts only as provenance.

For software, verify the exact relevant repository, branch, commit, and where material,
tree/build identity. README claims and filenames such as `CURRENT` or `FINAL` do not
prove freshness.

For Magic semantics, current Comprehensive Rules plus official Oracle/rulings data
outrank engine behavior and secondary sources.

Hard evidence semantics:

- `UNKNOWN != PASS`
- `PARTIAL != FULL`
- `NOT_RUN != PASS`
- `CODE_DERIVED != RUNTIME_VERIFIED`
- import, parsing, construction, or card-source presence does not prove card behavior
- historical runtime credit is valid only for the exact behavior and source identity
  actually executed

## 3. Rules-Core / Pilot Authority Boundary

The full-game Rules Core exclusively determines:

- legal actions;
- costs and payments;
- mana;
- stack;
- priority;
- targets;
- combat;
- triggers;
- replacement effects;
- prevention;
- continuous effects and layers;
- state-based actions;
- zones;
- copy/control semantics;
- Commander rules;
- multiplayer rules;
- Rules randomness.

Pilots choose only discretionary player decisions from legal options supplied by the
Rules Core.

Do not implement a second hidden Rules engine in the pilot, provider wrapper,
qualification harness, or UI.

Forbidden fallback behavior for unsupported discretionary decisions:

- first option;
- random option;
- default yes/no;
- engine AI fallback;
- GUI default;
- silent skip;
- parent-class fallback;
- heuristic legality reconstruction outside the Rules Core.

Production-reachable unsupported paths must fail closed.

## 4. Commander and Multiplayer Scope

Official deck-decision evidence defaults to exactly four players:

- one own deck;
- exactly three opponents.

The technical Rules/provider layer must not assume a 4P-only engine architecture.
Production qualification should support 2P, 3P, 4P, and 5P where required by the
current contract; 6P is desirable when it can be supported without correctness loss.

A broader technical player-count result never substitutes for an exact decision
contract that requires 4P.

## 5. Workstream Discipline

Each substantial chat/workstream has one primary objective.

Before work begins, use or create a Workstream Contract containing:

- Objective
- Inputs
- Authority
- In Scope
- Out of Scope
- Dependencies
- Required Deliverables
- Hard Gates
- Evidence Requirements
- Stop Conditions

Do not silently broaden a workstream into a second major independent problem.

At closeout, produce a self-contained handoff containing:

- Source Lock
- Work Completed
- New Findings
- Changes
- Tests / Evidence
- PASS / FAIL / UNKNOWN
- Remaining Blockers
- Outputs
- Dependencies Unblocked
- Exact Next Action

Other workstreams may reuse a handoff, but decision-relevant mutable facts should be
reverified against canonical sources when needed.

## 6. Execution Resilience and Persistence

Assume every agent run can terminate immediately after the next completed step.

Make every material completed milestone resumable:

1. put the working tree into a coherent state;
2. run the smallest authoritative scoped validation;
3. persist machine-readable evidence where appropriate;
4. commit the verified checkpoint on the authorized branch;
5. record the exact resulting head / run / artifact identity.

Do not intentionally leave hours of verified work only in ephemeral reasoning or an
uncommitted working tree.

Do not stop voluntarily at a technically remediable intermediate failure when the
remaining repair is in scope. Stop only for a genuinely terminal blocker, and report
its exact proof.

## 7. Model / Agent Routing

The project uses a cost-aware but correctness-first routing policy.

### Normal GPT-5.6 Sol chat

Use for architecture, authority research, difficult root-cause analysis, MTG rules
adjudication, differential interpretation, implementation strategy, critical review,
and creation of precise repository-agent work packages.

### Codex Terra — default implementer

Use by default for normal repository implementation:

- multi-file features;
- provider/state-loader work;
- ordinary bugs;
- refactors;
- APIs and integration;
- test-suite expansion;
- implementation of an already-decided design.

### Codex Luna — mechanical work

Use only when intended semantics are already fixed, for example:

- formatting / lint cleanup;
- simple type repairs;
- documentation;
- repetitive refactors;
- straightforward tests following an existing pattern;
- renames and generated-file maintenance;
- running predefined validation and summarizing results.

Luna must not independently decide Magic rules semantics, architecture,
hidden-information policy, RNG authority, provider-vs-engine blame, qualification
PASS, or contract obligations.

### Codex Sol — escalation

Reserve for genuinely difficult repository reasoning, especially when one of these
applies:

- Terra has made two substantive unsuccessful attempts at the same blocker;
- foundational Rules-Core architecture changes;
- hard-to-reproduce nonlocal defects;
- concurrency / race conditions / RNG isolation;
- large central migrations;
- high-blast-radius correctness changes;
- cross-subsystem interaction that cannot be safely bounded first.

Whenever practical, analyze the problem in normal Sol first and give Codex Sol a
bounded remediation contract instead of an open-ended exploration request.

Model cost never changes the evidence standard.

## 8. Task Granularity

Do not issue vague requests such as "improve the simulator".

Prefer one independently understandable engineering objective with:

- a bounded change surface;
- explicit invariants;
- named starting files/APIs;
- direct validation;
- evidence requirements;
- a persistent terminal checkpoint.

Large features should normally be split into coherent, testable phases such as data
contract, core implementation, integration, tests, and validation. Do not split a
single correctness invariant into unsafe microtasks merely to reduce context.

Every substantive implementation task should define:

- Objective / Why
- Source Lock
- Authority
- In Scope / Out of Scope
- Hard Invariants
- Named Starting Points
- Required Changes
- Fail-Closed Requirements
- Tests
- Validation Commands
- Evidence
- Persistence Plan
- Acceptance Criteria
- Stop Conditions
- Final Handoff Schema

## 9. Repository Map

Primary durable areas on the current repository layout:

- `src/commander_lab/` — proprietary Python application and simulation/decision code
- `tests/` — Python unit, property, integration, golden, differential, and evaluation tests
- `qualification/` — qualification contracts, fixtures, provider evidence, and related material
- `engine-bridge/` — Java 17 / Maven external-engine bridge code
- `schemas/` — machine-readable contracts / schemas
- `scripts/` — project and qualification automation
- `data/` — current and historical project data; current-source rules still apply
- `artifacts/` — generated or persisted evidence/output
- `.github/workflows/` — CI and qualification workflows
- `vendor/` — third-party/vendor material; do not modify casually

Do not infer authority from directory names alone. Immutable or canonical status must
come from the current workstream/contract and exact source identity.

## 10. Standard Python Setup and Validation

Project metadata currently requires Python >=3.12.

Preferred setup:

```bash
python -m pip install -e '.[dev,api,openai]'
```

A repository task should run the smallest authoritative checks first, then broaden as
needed. The main CI quality gates are equivalent to:

```bash
ruff check .
ruff format --check .
mypy src/commander_lab
pytest -q
python -m compileall -q src tests
python -m pip wheel --no-deps --wheel-dir dist .
```

The README also supports a uv-based local path:

```bash
uv sync --extra dev
uv run pytest
```

Do not repair unrelated inherited generic CI merely because it is red unless it
blocks the authoritative evidence required by the current task.

## 11. Java / External Engine Work

`engine-bridge/` is Maven-based and currently targets Java 17.

Where the required external-engine dependencies are provisioned, the normal scoped
unit-test entry point is:

```bash
mvn -f engine-bridge/pom.xml test
```

Provider/engine qualification may require workstream-specific engine pins, fork
builds, GitHub Actions, artifacts, or commands beyond this generic entry point. Use the
exact task contract rather than assuming a generic Maven PASS proves provider or card
functionality.

Do not copy Rules semantics from an external engine into proprietary pilot logic as a
shortcut. Preserve required license and process boundaries defined by the current
interop architecture.

## 12. Hidden Information

Actor observations must contain only information the actor is entitled to know.

Do not expose omniscient engine object graphs to a pilot and rely on the pilot to
ignore hidden data.

Actor-facing identifiers for hidden objects must not leak identity through names,
deck-derived hashes, deterministic native handles, or other reversible side channels.
Privileged lineage/evidence identifiers may remain inside the trusted provider layer
when the current architecture allows it.

Tests for hidden information should assume an adversary may know the complete decklist.

## 13. RNG and Replay

Rules randomness belongs to the Rules Core / qualified engine RNG path.

Do not use pilot-side randomness to simulate Rules randomness.

A replay PASS must be backed by the exact contract-required decision tape, event/state
checkpoints, source/build identity, and fresh-process/session behavior. Different
engines do not need identical raw PRNG call streams unless an explicit contract says
so; compare semantic results/tapes at the required abstraction.

If a pinned engine exposes process/JVM-global Rules RNG, do not assume concurrent
same-process sessions are independently deterministic. Use the current qualified
isolation policy or prove a per-session RNG design before relaxing it.

## 14. Canonical State and Provider Construction

A provider mapping defect is not automatically an engine Rules defect.

A contract defect must be repaired neutrally before blaming a candidate provider.

When a canonical scenario requires state loading/construction:

- use native engine state or native causal setup;
- do not synthesize legality in the pilot;
- fail closed when the exact canonical state cannot be constructed;
- where the current contract requires it, prove requested semantic state equals the
  normalized constructed state before granting runtime behavior credit.

Natural game-start / pregame fixtures must not be silently injected as midgame state.
Use the execution-entry semantics defined by the current canonical contract.

## 15. Immutable Qualification Artifacts

If a workstream declares a materialization, manifest, contract, fixture set, checksum,
or evidence bundle immutable:

- never edit it in place;
- preserve it as provenance;
- create a superseding version/artifact when correction is required;
- generate a new digest;
- document why the semantic obligation was preserved or, if it was not, fail closed.

Never weaken a denominator, expected result, assertion, or semantic obligation merely
to make a provider pass.

## 16. Branches, PRs, and Writes

For numbered workstreams, prefer branches shaped like:

```text
wsNN/<short-purpose>
```

Repository-policy or maintenance work may use a focused `chore/...` branch.

Do not merge to `main` unless the user explicitly authorizes the merge.

When writes are authorized, prefer focused commits and Draft PRs for reviewable
workstream output. Do not combine unrelated semantic changes in the same commit just
to reduce PR count.

Before editing an existing file, verify its current branch/head and content. Do not
blindly overwrite a file based on chat history.

## 17. Definition of Done

A task is not complete merely because:

- code compiles;
- a test was added;
- a fixture imports;
- a card parses;
- an engine accepts a state;
- CI is green.

The contracted claim must be proven at the required evidence level.

For runtime semantic claims, the expected proof usually includes:

```text
correct source lock
+ correct canonical input
+ exact native construction / legal native causal path
+ strict Rules-Core / pilot separation
+ required assertions
+ runtime evidence
+ persisted result
```

No missing component may be silently replaced with inference.

At the end of each substantial task, inspect the final diff for unrelated semantic
changes, weakened assertions, new fallback behavior, hidden-information leakage, or
unintended API changes before claiming PASS.
