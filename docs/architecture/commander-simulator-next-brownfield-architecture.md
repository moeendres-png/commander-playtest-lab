# Architecture — Commander Simulator Next

**Mode:** Brownfield architecture over existing Commander Playtest Lab + candidate-engine repositories  
**Intent:** [Commander Simulator Next PRD](../commander-simulator-next.prd.md)  
**Architecture status:** PROPOSED / pre-Freeze  
**Brownfield source baseline:** Lab `main` at `010e58220dd64f8c3ceb3b86149190ce95437d9f` / tree `af287661fbfdb6a68d3442371e518aeffebce49b`  
**PRD source:** `product/commander-simulator-next-prd-20261005@991d2ed6e74873e1ffdb24cad57305c4c5836cc6`  
**Date:** 2026-10-05

This document chooses a **high-level architectural direction**, not a Production Provider
and not an implementation plan.

`PRODUCTION_PROVIDER = NOT_SELECTED`  
`ARCHITECTURE_FREEZE = NOT_CLAIMED`  
`PRODUCTION_REPOSITORY = NOT_CREATED`

---

## 1. Problem & goals

Commander Simulator Next must make real Commander deck decisions from large numbers of
games without allowing simulation volume to dilute Rules Correctness.

The product must combine:

- a full-rules authority that alone owns legality, costs, targets, stack, priority,
  combat, triggers, replacement/prevention, layers, state-based actions, zones,
  copy/control semantics, Commander/multiplayer rules and Rules randomness;
- intelligent, deck-aware pilots that choose only among authoritative legal decisions;
- principal-scoped hidden information;
- semantic replay that binds decisions, Rules RNG, material events and terminal state;
- process-isolated batch execution;
- reproducible comparison studies over real decks;
- explicit uncertainty and qualification standing rather than naked win-rate claims;
- enough throughput to run large studies without changing the semantics that make those
  studies trustworthy;
- 4P as the primary decision mode, 2–5P technical conformance, and a variable-player
  shape that makes 6P feasible when the chosen Rules Core supports it correctly;
- eventual public/open-source use by other people.

The existing Lab already proves that substantial pieces of this are reusable:
external-engine process management, Protocol-2-style provider boundaries, principal
observation work, source/run identities, actual-card qualification, semantic replay,
structural/optimizer layers, batch records, and extensive evidence infrastructure.

The architecture must reuse those assets selectively rather than promote the whole Lab
repository into Production by inertia.

---

## 2. First principles

Every architecture option is rejected unless it can preserve these invariants.

### 2.1 One Rules authority

Only the selected Rules Core may decide legal game behavior.

The orchestrator, pilot, reporting layer, optimizer, replay consumer, and provider adapter
may not independently recreate legality.

### 2.2 Pilot is a chooser, not a judge

A pilot receives:

1. a principal-scoped observation;
2. an authoritative `DecisionFrame`;
3. the authoritative legal option/domain supplied by the Rules Core.

It returns a choice from that domain. The Rules Core validates and applies it.

There is no first-option, random-option, default yes/no, silent-skip, GUI-default,
internal-engine-AI fallback, requested-option filtering, or manually injected outcome.

### 2.3 Unsupported means non-result

A production-reachable unsupported decision or rules path must fail closed.

Large batch size can reduce statistical uncertainty. It can never turn unsupported
semantics into evidence.

### 2.4 Exact identity is part of the result

A game result is incomplete without the identities of:

- Rules provider source/build;
- orchestrator source/build;
- decks;
- pod and seats;
- pilot implementation/profile;
- decision protocol;
- Rules-RNG/replay contract;
- experiment definition.

### 2.5 Variable players by shape, not special cases

No Production model should encode "four players" as a structural constant.

Seats, principals, turn order, priority order, targeting domains and elimination state are
N-sized collections. Product qualification remains explicit per cardinality.

---

## 3. Approaches considered

### Option A — Provider-process hybrid with a Python control plane

**Shape**

A small Python orchestration/experiment layer controls a separately built Java Rules
provider through a versioned typed process protocol. The selected engine remains the sole
Rules authority. Pilots, experiment design, replay/evidence, analysis and reporting remain
outside the engine.

The selected Production Provider is one exact engine lineage after #255. The other
candidate may remain a differential/reference backend, but never a transparent runtime
fallback.

**Brownfield reuse**

High:

- existing process isolation and bridge lifecycle concepts;
- Protocol 2 semantics;
- current run/source identity;
- semantic replay model;
- current qualification/evidence concepts;
- structural screening and optimizer/statistics where still valid;
- pilot API concepts;
- content-addressed batch records.

**Advantages**

- strongest separation between Rules authority and decision/analysis logic;
- XMage and Forge can both be evaluated behind the same conceptual boundary before
  selection;
- Java engine internals remain native instead of being reimplemented;
- Python remains a productive environment for experiments, statistics, pilots and reports;
- process isolation naturally supports fail-closed crashes and batch workers;
- a GPL engine can remain a separately built provider component rather than being copied
  into the Python control plane, although exact distribution obligations still require
  legal review;
- easier to test pilots independently of Rules semantics.

**Costs / risks**

- provider bridge must expose every required discretionary decision family without
  becoming a second Rules Engine;
- IPC and fresh-process startup have throughput cost;
- cross-language schemas require disciplined versioning;
- the selected provider must expose controllable Rules RNG and replay-worthy semantics.

**Assessment:** **RECOMMENDED.**

---

### Option B — Engine-centric Java product

**Shape**

Choose XMage or Forge and implement most orchestration, pilot integration, replay,
batching and analysis directly in or adjacent to the selected Java engine.

**Advantages**

- fewer cross-process calls inside a game;
- direct engine object access;
- potentially lower serialization overhead;
- some game-state and replay hooks may be easier to implement.

**Costs / risks**

- much stronger coupling to the selected engine before Provider Selection is final;
- pilot/analysis code gains easier accidental access to hidden/full state;
- a larger fork surface makes upstream synchronization harder;
- statistical/analysis and experiment tooling would either move to Java or need a second
  boundary anyway;
- engine-specific implementation can make differential qualification harder;
- with Forge, public distribution/licensing becomes more tightly coupled to GPL-covered
  engine code.

**Assessment:** viable only if process-boundary control proves technically incapable of
supporting required decision/replay semantics. Current evidence does not justify paying
this coupling cost.

---

### Option C — New/ported general Rules Core

**Shape**

Implement or port a new general Commander Rules Core in Python, Rust, or another language
and make it the native Production engine.

**Advantages**

- maximum control over API, state representation, determinism and batch performance;
- no provider bridge needed once complete;
- architecture can be designed exactly around simulator needs.

**Costs / risks**

- recreates the most difficult and correctness-sensitive part of Magic;
- discards a very large amount of real-card behavior already present in mature engines;
- imposes enormous actual-card, multiplayer, replacement/layer/copy/control and
  Commander-rules qualification burden;
- likely delays useful deck decisions dramatically;
- violates the project's reuse-first principle unless both existing candidates are proven
  objectively unsuitable.

**Assessment:** **REJECT AS DEFAULT.** Reconsider only if the selected-candidate process
spike proves a fundamental unfixable barrier that outweighs the cost of rebuilding a
Rules Core.

---

## 4. Recommended approach

Use **Option A: a provider-process hybrid**.

The eventual Production system should be a deliberately smaller composition than the
current Lab:

```text
                         ┌──────────────────────────┐
                         │  Experiment / Study API  │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │      Orchestrator         │
                         │ run identity / scheduling │
                         └───────┬───────────┬───────┘
                                 │           │
                  authoritative │           │ principal-scoped
                     game I/O   │           │ decision frames
                                 │           │
                    ┌────────────▼───┐   ┌───▼────────────────┐
                    │ Rules Provider │   │   Pilot Boundary    │
                    │ selected core  │   │ deck-aware chooser  │
                    │ separate proc  │   │ no Rules authority  │
                    └──────┬─────────┘   └─────────┬──────────┘
                           │                       │ chosen option
                           └───────────┬───────────┘
                                       │
                         ┌─────────────▼────────────┐
                         │ Replay / Evidence Writer │
                         └─────────────┬────────────┘
                                       │
                      ┌────────────────▼────────────────┐
                      │ Batch Analytics / Comparison    │
                      │ uncertainty / robustness / QoE  │
                      └─────────────────────────────────┘
```

The Rules provider is selected only after the current #441 → #255 evidence/adjudication
path is terminal.

The architecture does **not** require both XMage and Forge in Production. Keeping the
second engine available for differential/reference testing is useful, but a runtime
failure must not trigger silent switching to the other engine.

---

## 5. Brownfield reuse disposition

### REUSE / EXTRACT

| Existing capability | Architectural disposition |
| --- | --- |
| Engine process lifecycle | **EXTRACT_AND_GENERALIZE** — retain fail-closed external-process control and exact build identity |
| Protocol-2 decision boundary | **EXTRACT_AND_GENERALIZE** — preserve typed/versioned request/response semantics, but freeze Production schema only after provider adjudication |
| Principal-scoped observations | **REUSE CONCEPT + REQUALIFY IMPLEMENTATION** |
| Source/run identity | **REUSE_AS_FOUNDATION** |
| Semantic replay tapes/fingerprints | **EXTRACT_AND_GENERALIZE** after provider-specific RNG/replay closure |
| Current-boundary qualification model | **REFERENCE + SELECTIVE REUSE**; Production qualification should not carry the historical research tree wholesale |
| Structural simulator | **KEEP AS OPTIONAL SCREENING/SEARCH LAYER**, never Rules authority |
| Optimizer / paired comparison statistics | **EXTRACT SELECTIVELY** after impact review against the final run/result model |
| Existing deterministic pilots | **BASELINE/TEST ASSETS**, not assumed sufficient as Production-strength pilots |
| Actual-card qualification fixtures | **REUSE/PORT AS QUALIFICATION ASSETS**, source-bound and impact-adjudicated |
| Evidence classifications and fail-closed semantics | **REUSE AS POLICY** |
| Historical workstream documents/artifacts | **REFERENCE_ONLY** unless current impact adjudication admits them |

### DO NOT CARRY FORWARD BY DEFAULT

- historical phase/workstream topology;
- duplicated "CURRENT/FINAL" files as authorities;
- Lab-specific tactical/structural fallbacks in a Production full-rules path;
- candidate-specific assumptions inside generic orchestration;
- any test or qualification PASS whose source/pin/contract/harness identity changes.

---

## 6. Key decisions

## 6.1 Stack & libraries

### Control plane

**Decision:** Python, initially the current Python 3.12-compatible ecosystem.

Why:

- current orchestration, qualification, analysis and experiment code already exists in
  Python;
- the product needs statistics, data analysis, experiment control and pilot iteration more
  than ultra-low-latency request handling;
- keeping the control plane out of the Java Rules Core reinforces authority separation;
- it minimizes a needless rewrite.

**Core boundary library:** Pydantic 2-style strict models / JSON Schema at external trust
boundaries. Internal hot paths may use leaner native structures where profiling proves
validation overhead material.

### Rules provider

**Decision:** the later-selected mature Java Rules Engine runs as a separate provider
process from an exact source/build identity.

Do not choose XMage or Forge in this document.

### Provider transport

**Decision:** retain versioned newline-delimited JSON over stdin/stdout for v1 unless a
measured spike proves it is a meaningful throughput bottleneck.

Alternatives considered:

- gRPC/Protobuf: stronger generated schemas and streaming, but materially more integration
  complexity across engine forks;
- embedded JNI/JVM bridge: lower IPC, but weakens isolation and coupling boundaries;
- sockets/HTTP: useful for distributed deployment but unnecessary for the local-first MVP.

Game simulation cost is expected to dominate small control messages; therefore replacing
the current transport without evidence is not justified.

### Analytics storage

**Decision:** two storage planes:

1. **canonical evidence/replay objects:** immutable, content-addressed JSON/NDJSON or other
   explicitly versioned portable artifacts;
2. **derived high-volume analytical tables:** Parquet queried locally with DuckDB.

Rationale:

- canonical evidence stays inspectable and hashable;
- Parquet is a compressed columnar format suited to bulk analytical results;
- DuckDB can query Parquet directly and supports filter/projection pushdown, fitting a
  local-first open-source simulator without requiring a database service.

A database service is **not** required for v1.

### CLI / product surface

**Decision:** CLI + Python API first.

A web UI is a later reversible product layer. It must not become a prerequisite for core
simulation correctness.

---

## 6.2 Major data model

These are conceptual entities, not database tables.

### Immutable inputs

**DeckSnapshot**
- deck identity/content hash;
- commander configuration;
- exact card identities needed for execution.

**PilotProfile**
- pilot implementation/version;
- deck identity;
- deck strategy/primer knowledge;
- policy parameters.

**PodSpec**
- N seats;
- one DeckSnapshot + PilotProfile per seat;
- player count;
- seat/starting-player treatment.

**ProviderBuild**
- provider identity;
- exact source/build hash;
- protocol/capability identity.

### Game execution

**GameRunManifest**
- ProviderBuild;
- orchestrator build;
- PodSpec;
- experiment/study identity;
- Rules RNG contract;
- replay contract.

**PrincipalObservation**
- exactly the information one acting principal is permitted to observe.

**DecisionFrame**
- decision class;
- actor/principal;
- authoritative revision;
- legal option/domain identities;
- any engine-authored semantic descriptors required to choose.

**DecisionRecord**
- frame identity;
- pilot identity;
- selected option/domain member;
- acceptance/result.

**RulesRngRecord**
- provider-controlled Rules randomness needed for reproducibility.

**SemanticEvent / ReplayCheckpoint**
- material externally observable semantic transition and hashes/fingerprints.

**GameResult**
- terminal reason/state;
- player ordering/outcomes;
- failure/unsupported classification;
- replay/evidence references.

### Experiment layer

**DecisionStudy**
- baseline and challenger definitions;
- frozen pod;
- pairing/seat/randomness policy;
- stopping/precision contract;
- admitted evidence requirements.

**StudyResult**
- effect estimate;
- uncertainty interval;
- sample size;
- robustness slices;
- invalid/unsupported rate;
- evidence/qualification identity;
- decision status.

No mutable "current result" overwrites historical run evidence.

---

## 6.3 Decision classes

The Production interface should use a **small generic family taxonomy**, not card-specific
callbacks.

Required v1 families:

1. **ACTION** — priority/pass/cast/activate/special-action choice.
2. **TARGET** — player/permanent/spell/card/object target selection.
3. **MODE_OPTION** — spell/ability modes and engine-defined option sets.
4. **AMOUNT_VECTOR** — X, scalar numbers, multi-count allocation.
5. **PAYMENT** — among engine-generated legal payment/cost alternatives.
6. **OPTIONAL** — yes/no / may-use choices.
7. **ORDERING** — player-controlled trigger/replacement/other order choices.
8. **MULLIGAN_KEEP** — keep/mulligan/bottom choices as engine-authored domains.
9. **COMBAT** — attacker/blocker/assignment choices.
10. **OBJECT_SELECTION** — cards/objects chosen from an engine-defined non-target domain,
    including looked/revealed/piles.
11. **PLAYER_SELECTION** — opponent/player choices that are not Rules targets.
12. **PARTITION_DISTRIBUTION** — piles, splits and assignments.

A provider may represent these differently internally. The adapter's job is lossless
projection of the native authoritative domain, not inventing legality.

Unknown decision family in a reachable game:

`UNSUPPORTED -> FAIL CLOSED`.

---

## 6.4 Pilot architecture

### Boundary

Pilot code is replaceable and versioned independently from the Rules provider.

The pilot receives only:

- PrincipalObservation;
- DecisionFrame;
- PilotProfile.

It returns only a selection over the supplied legal domain.

### Deck knowledge

A PilotProfile should carry deck-specific strategic knowledge:

- commander/deck identity;
- game plan and role;
- key engines/synergies;
- interaction priorities;
- resource priorities;
- matchup heuristics.

This knowledge can be authored manually, compiled from a primer, learned, or generated by a
model. It cannot create legal actions.

### Pilot implementations

Support multiple implementations behind one interface:

- deterministic baseline for qualification/regression;
- fast deck-aware production policy for bulk simulation;
- stronger model-backed policy for experimentation or policy improvement;
- future learned/self-play policy.

**Do not freeze one AI model as part of the architecture.**

For a DecisionStudy, pilot identity/version is frozen. Baseline and challenger deck
variants must not receive different pilot intelligence unless pilot difference is the
question under test.

### Isolation

For Production-strength model-backed or untrusted pilots, prefer a process/message
boundary so the pilot cannot inspect full hidden engine state.

In-process baseline pilots may exist for tests if they receive the exact same scoped API
and cannot be used as evidence for a stronger isolation claim.

---

## 6.5 Batch execution & concurrency

### Correctness baseline

Default v1 contract:

**one game = one isolated provider process**.

This provides the clearest state/RNG/lifecycle isolation and is already aligned with the
strongest existing replay evidence.

### Parallelism

Throughput comes from running multiple isolated games concurrently, not from sharing one
mutable game engine across games.

A scheduler chooses worker concurrency from CPU/RAM capacity. Every game has an independent
run identity and artifact directory.

### Persistent-process optimization

Reusing one provider JVM across sequential games is an optional later optimization only if
a dedicated equivalence spike proves:

- no state leakage;
- identical qualification semantics;
- deterministic cleanup;
- replay equivalence;
- failure containment;
- materially useful throughput improvement.

If the default fresh-process architecture already meets the provisional 1,000-game
overnight target, keep the simpler design.

---

## 6.6 Replay & Rules RNG

Semantic replay is a **Production capability**, not merely a debugging feature.

A replay-qualified run must bind:

- exact input decks/pod;
- actor-scoped decisions;
- authoritative legal-domain fingerprints;
- selected options;
- provider Rules RNG inputs/results or equivalent authoritative RNG tape;
- material semantic events/checkpoints;
- terminal state/outcome;
- all relevant software/build identities.

The selected Rules provider must expose sufficient control/observation to reproduce the
semantic game. If a candidate cannot do so without recreating Rules randomness outside the
Rules Core, that is a Provider Selection disadvantage or blocker.

Bit-exact JVM/internal object replay is not required unless it becomes the simplest
reliable solution. **Semantic outcome replay is required.**

---

## 6.7 Study/statistical layer

The Product question is not "what was the win rate?" but "is this decision supported by
the admitted evidence?"

For the RogShai one-card MVP:

- freeze baseline and challenger;
- freeze opponent pod;
- use balanced seat/starting-player treatment;
- pair or otherwise control randomness where the Rules provider supports a valid
  reproducible comparison;
- use sequential/precision-aware comparison rather than an arbitrary fixed game count;
- run large batches up to the needed precision, with 1,000 games as an initial practical
  scale rather than an evidentiary magic number.

The existing paired/sequential optimizer concepts are strong brownfield donors but require
impact review against the final GameResult and replay semantics before Production reuse.

---

## 6.8 User-facing result states

Every DecisionStudy reports one of exactly three top-level product states:

### `SUPPORTED_DECISION`

The admitted evidence supports a directional decision under the frozen study contract.

Display together:

- recommendation/direction;
- effect estimate;
- uncertainty interval;
- games/admitted samples;
- robustness by seat/opponent/pilot-relevant slices;
- qualification level;
- replay/run identity;
- known limitations.

### `INCONCLUSIVE`

The run is valid but evidence does not separate the alternatives sufficiently.

This is a legitimate result, not a failure to be hidden.

### `INVALID_OR_UNSUPPORTED`

A required Rules/pilot/replay/identity path was unsupported, contradictory, stale or failed
closed.

Do not compute a user-facing recommendation from invalid games.

A green CI icon is never a fourth product state.

---

## 6.9 Player-count architecture

Data structures and protocols are variable-N.

### Required

- 2P;
- 3P;
- 4P;
- 5P.

Each receives separate technical conformance evidence.

### Desired stretch

6P.

5P/6P are not "just slower":

- more priority holders;
- larger APNAP/order domains;
- more simultaneous triggers;
- more possible targets/opponents;
- more principal-scoped hidden-information relationships;
- more elimination/control edge cases;
- larger pilot decision/state space.

Therefore 6P is enabled only when the selected Rules provider and qualification evidence
support it. The architecture itself must not make 6P artificially difficult through
fixed-size assumptions.

---

## 6.10 Public/open-source distribution

The user's intended direction is public reusable code.

### Repository boundary

After Architecture Freeze:

- create the new Production repository according to the frozen ADR;
- initially it may remain private during code-origin/license cleanup;
- publish once its license and third-party boundaries are verified.

### Licensing direction

Preferred for original Production orchestration code: a permissive open-source license
such as **Apache-2.0** or **MIT**, subject to a code-origin and dependency audit.

Provider components retain their own upstream license obligations:

- the current XMage lineage is MIT-licensed;
- the current Forge lineage is GPL-3.0-licensed.

The separate-process architecture creates a clean technical component boundary, but this
document makes **no legal claim** that process separation alone resolves every GPL,
distribution, card-data, trademark or other IP obligation.

A public-release license/IP audit is therefore a one-way-door gate before publication.

---

## 6.11 Security, privacy & secrets

This is a local-first simulator, not initially a multi-tenant service.

Required posture:

- no raw API credentials in run artifacts/replays;
- external model credentials are process-local secrets;
- pilot requests contain only principal-scoped state;
- run/replay artifacts are treated as potentially containing private deck information;
- public artifact publication is opt-in and separately scrubbed;
- no remote service is required for Rules execution.

If a future hosted multi-user product is desired, authentication/tenant isolation becomes a
separate architecture workstream rather than being guessed into v1.

---

## 7. Missing pieces

The recommended architecture depends on the following still-unresolved building blocks.

### Provider / Rules

- #441 terminal evidence closure;
- #255 provider adjudication;
- complete generic decision-domain coverage on the selected provider;
- deterministic/observable Rules RNG sufficient for semantic replay;
- complete multi-turn/game-end autonomous control;
- 2–5P qualification and explicit 6P standing.

### Pilot

- a deck-knowledge representation suitable for RogShai and opponents;
- a Production-strength deck-aware policy;
- pilot-quality benchmark corpus that distinguishes legal-but-bad from strategically useful;
- isolation for model-backed pilots.

### Batch / performance

- measured end-to-end full-game throughput;
- concurrency/resource scheduler;
- bounded failure/retry semantics;
- proof that parallelism does not alter semantic results.

### Experiment / reporting

- Production DecisionStudy contract;
- final statistical stopping/precision contract;
- robustness slicing;
- `SUPPORTED_DECISION / INCONCLUSIVE / INVALID_OR_UNSUPPORTED` reporting;
- comparison artifact suitable for the RogShai one-card MVP.

### Open-source release

- code-origin inventory;
- selected provider distribution model;
- production-repo license decision;
- third-party/card-data/IP review.

---

## 8. Spikes & experiments

## Spike A — Provider release/adjudication

**Question:** Which current candidate can satisfy the full Product Rules boundary with the
least new Rules/adapter work?

**Spike:** do **not** create a duplicate experiment. Consume the already-authoritative
#441 → #255 qualification/adjudication campaign.

**Decision rule:** select a Production Provider only if its exact current source satisfies
the required Rules/decision/hidden-info/RNG/replay/player-count gates with no hidden
fallback. If neither does, Architecture Freeze remains blocked and the gaps are remediated
or candidate search reopens.

---

## Spike B — 1,000-game throughput under isolation

**Question:** Does one-fresh-provider-process-per-game meet the product's provisional
overnight-scale batch target?

**Spike:** after provider selection, run a representative full 4P RogShai pod at bounded
parallel worker counts and measure end-to-end completed valid games/hour, RAM, CPU,
startup share, failure rate and replay consistency.

**Decision rule:**
- if >=1,000 admitted games fit roughly within 8–12 hours on one modern consumer
  workstation, keep fresh-process isolation;
- if not, test persistent-worker reuse;
- persistent reuse is accepted only if cleanup/replay/qualification equivalence PASS and
  the speedup is material.

---

## Spike C — Pilot-quality gate

**Question:** Can a high-throughput pilot make strategically useful RogShai/opponent
decisions rather than merely legal ones?

**Spike:** build a deck-aware benchmark set of real decision states with reviewed
preferences/acceptable choice sets for RogShai and the MVP opponents. Compare the
deterministic baseline, the proposed fast policy, and at least one stronger reference
policy on the same engine-authored legal domains.

**Decision rule:** the bulk policy must materially outperform the baseline on strategic
decision quality without Rules leakage and without systematic deck/game-plan blindness.
If not, improve/replace the policy before using simulation volume for deck recommendations.

---

## Spike D — Public distribution/license audit

**Question:** What may be redistributed in the public Production release?

**Spike:** after provider selection and before public Production publication, inventory
the exact source provenance of Production code, provider bridge, engine binaries/source,
card data and bundled assets.

**Decision rule:** publish only with an explicit compatible license plan and all required
notices/source obligations. If the selected packaging model creates unresolved licensing
risk, change packaging/distribution rather than silently ship.

---

## 9. Open architectural questions

These remain deliberately unresolved because current evidence, not preference, should
settle them.

- [ ] **Production Provider:** XMage, Forge, or another objectively superior qualified
  engine? Settled by #441/#255 and any required successor qualification.
- [ ] **Exact Production protocol schema:** retain Protocol 2 bytes or create a smaller
  successor contract after Provider Selection? Settled by lossless-gap analysis.
- [ ] **Rules RNG mechanism:** seed, event tape, provider-native RNG abstraction, or another
  authoritative mechanism? Settled by selected-provider capability.
- [ ] **Bulk pilot implementation:** heuristic, model-backed, learned, or hybrid? Settled by
  Spike C and throughput evidence.
- [ ] **Public Production license:** Apache-2.0 vs MIT or another compatible choice?
  Settled by Spike D and code-origin audit.
- [ ] **6P Production admission:** include in v1 release or expose only after separate
  qualification? Settled by selected-provider evidence and measured cost.
- [ ] **Persistent provider workers:** unnecessary unless Spike B shows fresh-process
  startup is a material bottleneck.

---

## 10. Architecture decision summary

### Recommended

**Provider-process hybrid:**
- mature selected external Rules Core;
- Python orchestration/experiment plane;
- strict principal-scoped pilot boundary;
- generic engine-authored DecisionFrames;
- process-isolated games;
- semantic replay;
- content-addressed evidence;
- Parquet/DuckDB derived analytics;
- public/open-source Production code after Freeze and license audit.

### Explicitly not decided

- XMage vs Forge;
- final Production Provider;
- Architecture Freeze;
- exact Production repository;
- exact pilot model;
- exact Rules-RNG implementation;
- exact public license.

### Why this is the strongest Brownfield choice

It preserves the most valuable already-built evidence and infrastructure while keeping
the most important architectural freedom: **the Rules provider can still be selected on
qualification evidence rather than incumbency**.

It also keeps the user-facing product centered on trustworthy deck decisions rather than
on any particular engine, research workstream, or historical repository structure.
