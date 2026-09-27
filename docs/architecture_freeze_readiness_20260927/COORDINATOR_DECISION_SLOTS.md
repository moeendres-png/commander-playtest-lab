# WSR24 Coordinator Decision Slots — 2026-09-27

Scope: ONLY decisions that genuinely require Sol High authority.
Routine implementation choices are NOT in this file; they were decided
inside WSR24 and recorded in the readiness JSON packets.

Conventions per slot: QUESTION / WHY_COORDINATOR_AUTHORITY /
EXACT_EVIDENCE / AVAILABLE_OPTIONS / TECHNICAL_CONSEQUENCE_OF_EACH_OPTION.
No slot names a recommended winner. No slot ranks providers.

Freeze rule (binding, from `architecture_freeze_contract_v2.schema.json`):
`freeze_eligible=true` ONLY IF every required AF00–AF11 gate is PASS AND all
required capabilities are present. Neither candidate satisfies this on current
evidence (XMAGE: AF04 FAIL, AF11 FAIL, six UNKNOWNs; FORGE: AF11 FAIL, six
UNKNOWNs; both: missing required capability flags). No slot below can waive
that schema; slots that accept alternative evidence still require a PASS-grade
record, not a relabelled UNKNOWN.

---

## SLOT-01 — Provider selection

QUESTION: Which single candidate (XMage at
`b19596980f2734496ea1896504253e1bdd2756dd`, or Forge at
`ef958ee91ac6c9ce0152189f2654bf6e05abf273`) becomes the production Rules Core?

WHY_COORDINATOR_AUTHORITY: Provider selection is explicitly Coordinator-only
per the Workstream Contract. It also fixes the license posture (XMage MIT vs
Forge GPL-3.0), the engine pin, and which remediation DAG executes.

EXACT_EVIDENCE: `WSR22_EVIDENCE_INGEST.json` (AF verdicts, FULL107 counts,
comparison 25 SAME / 82 NON_COMPARABLE / 0 divergence, blocker register 0
blocking / 4 bounded / 4 unknown-impact); `XMAGE_FREEZE_READINESS.json`;
`FORGE_FREEZE_READINESS.json`.

AVAILABLE_OPTIONS:
- (a) Select XMage. Consequence: the minimum path is
  `REMEDIATION_DAG_XMAGE.md` (AF04 adapter shim + AF01 lane-consistent
  capabilities + 33-row injection seam or mechanism-equivalence ruling +
  hidden-channel campaign + 29-card corpus + replay twins + AF11 single-provider
  re-verification).
- (b) Select Forge. Consequence: the minimum path is
  `REMEDIATION_DAG_FORGE.md` (AF04 shim + capability-flag correction +
  build-derived commit binding or provenance-file ruling + probe-then-fill the
  7+2 injection rows + hidden-seam classification + 29-card corpus + replay
  twin + AF11 single-provider re-verification).

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Both paths converge on the same
production architecture (one provider process, provider-specific adapter,
candidate-neutral pilot); they differ only in which engine pin, which lane
quirks, and which row set must be executed. Neither path is shorter by policy;
the row counts differ (XMage 33 BLOCKED rows vs Forge 7+2) but the campaign
types are the same.

---

## SLOT-02 — PB-03 mechanism-equivalence admission (XMage 33 rows; Forge 7+2 rows)

QUESTION: For the BLOCKED rows whose obligations need a frozen mid-game
starting state (XMage: 33 rows listed in `XMAGE_FREEZE_READINESS.json`
gates[AF06]; Forge: MICRO_COPY, MICRO_COSTS, MICRO_MODES, MICRO_REPLACEMENT,
MICRO_ZONE_CHANGES, WS05-MP-BLOCK-4, WS05-MP-COMBAT-4), may
mechanism-equivalent causal-reconstruction evidence from the candidate's own
native harnesses satisfy the obligation, or is a starting-state injection seam
plus direct execution required?

WHY_COORDINATOR_AUTHORITY: This decides what counts as admission evidence for
AF06/AF08. Accepting non-identical evidence is a project-wide
evidence-policy change, which is Coordinator-only. WSR24 must not promote
adjacent-mechanism results into obligation PASS records on its own.

EXACT_EVIDENCE: `PROVIDER_BLOCKERS.json` PB-03 (WSR22, UNKNOWN_IMPACT);
`FULL107_XMAGE_RESULTS.json` (33 BLOCKED); `FULL107_FORGE_RESULTS.json`
(7 BLOCKED); XMage native suites (34+134 green, reaching adjacent mechanisms:
stack, control, elimination, commander damage); Forge native suites (150+67
green); Forge lane reports `starting_state_injection_supported=true` /
`scenario_injection_supported=true` (unprobed Lab-side).

AVAILABLE_OPTIONS:
- (a) Require direct execution via a starting-state injection seam.
  Consequence: a bounded injection workstream (provider/bridge repair + Lab
  execution path) must complete before AF06/AF08 can be PASS; schedule cost,
  but obligation-level runtime proof.
- (b) Accept mechanism-equivalent native-harness evidence for exactly the
  listed rows, with per-row mechanism mapping recorded. Consequence: no
  injection workstream; AF06/AF08 PASS records rest partly on native-harness
  evidence whose obligation-identity mapping must be reviewed row by row.
- (c) Split ruling: direct execution for a Coordinator-chosen subset,
  mechanism-equivalence for the remainder. Consequence: mixed evidence basis,
  must be recorded per row; requalification impact set is the direct-execution
  subset only.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Options (b) and (c) do not change the
schema (gates must still be PASS with evidence_refs); they change what the
evidence_refs may point at. The per-row mapping must be explicit either way;
a blanket ruling without a row list is not implementable.

---

## SLOT-03 — Provider-specific decision-identity shim under AF04/AF11

QUESTION: Does a provider-specific decision-identity shim in the Lab adapter —
mapping XMage's `decision_id` (sha256) + `action_id` pass, or Forge's
`revision` (long) + `actor_id` pass, into one Lab-internal field, with the
value always originating from the provider frame — satisfy AF04 and AF11 under
existing policy (adapter = protocol translation only; no legality
reconstruction)?

WHY_COORDINATOR_AUTHORITY: This is a shared-architecture interpretation (what
the adapter is allowed to own) with AF04/AF11 PASS implications. WSR24 may
design the shim but may not rule that it preserves the Rules-authority
boundary; that is Coordinator architecture authority.

EXACT_EVIDENCE: PB-02 (both candidates, BOUNDED_NON_BLOCKING); AF04 evidence
in both readiness packets (live external PRIORITY decision answered with an
engine-offered option on each lane; cross-shape rejection proven both ways:
XMage returns STALE_EXTERNAL_DECISION for revision-only; Forge structurally
requires revision).

AVAILABLE_OPTIONS:
- (a) Approve the shim as protocol translation. Consequence: the selected
  provider's DAG proceeds with adapter repair + fail-closed tests; AF04/AF11
  can reach PASS on runtime proof.
- (b) Reject the shim, requiring byte-identical decision-identity handling per
  provider with no normalizer. Consequence: the adapter must carry two
  disjoint submission paths; pilot code branches per provider; larger
  remediation surface and duplicated fail-closed tests.
- (c) Approve with conditions (e.g., provenance test that every submitted
  identity byte-matches the offering frame). Consequence: same as (a) plus a
  named conformance test that becomes part of AF04 evidence.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: All options keep legality inside the
Rules Core; the difference is adapter code shape and the exact AF04 test
surface. None of them fabricates options or falls back silently.

---

## SLOT-04 — PB-06 hidden-channel production reachability scope

QUESTION: Which per-scenario hidden-information channels (face-down exile,
look/top-of-library effects, controlled-player decisions, shuffle
invalidation, and the five historical Forge seams HIDDEN_05/06/08/11/12) are
production-reachable and therefore required AF05 proof, and which (if any) are
out of scope for Freeze?

WHY_COORDINATOR_AUTHORITY: Scoping a required gate's proof surface is an
evidence-policy and architecture decision (it fixes the observation contract
the production repository must implement). WSR24 must not narrow AF05 on its
own.

EXACT_EVIDENCE: PB-06 (both candidates, UNKNOWN_IMPACT); HIDDEN_INFO_XMAGE.json
(19 UNKNOWN rows incl. honeycard sentinel); HIDDEN_INFO_FORGE.json (8 UNKNOWN
rows); principal-scoped 4P reads PASS on both; native suites green (168/217).

AVAILABLE_OPTIONS:
- (a) All listed channels are production-reachable. Consequence: full
  scenario campaign on a channel-instrumented surface before AF05 PASS; the
  observation contract in `PRODUCTION_REPOSITORY_CONTRACT.md` must expose
  per-actor channel permissions.
- (b) A Coordinator-enumerated subset is required; the remainder is deferred
  post-Freeze as bounded limitations. Consequence: smaller pre-Freeze
  campaign; deferred channels must be recorded as explicit fail-closed
  unsupported paths, not silent gaps.
- (c) Defer the entire per-scenario surface post-Freeze. Consequence: AF05
  cannot be PASS at Freeze under the current catalog (UNKNOWN remains), so
  Freeze itself would have to wait or the catalog would have to change — and
  changing the catalog is out of scope for WSR24 and requires its own
  Coordinator action.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Options (a)/(b) keep the schema fixed
and size the campaign. Option (c) is recorded for completeness but is
incompatible with Freeze on the current schema.

---

## SLOT-05 — PB-05 Forge commit-to-build binding sufficiency for AF00

QUESTION: For a Forge Freeze record, is the env-supplied engine-commit binding
(`env:FORGE_ENGINE_SHA`, verified against the reference checkout HEAD/tree in
WSR22) sufficient AF00 evidence, or is a build-derived commit/tree in the
bridge version payload (or a container provenance file) required?

WHY_COORDINATOR_AUTHORITY: AF00 is the Freeze source-identity root; accepting
an operator-supplied binding as reproducible build identity is an
evidence-policy call with Freeze-record consequences.

EXACT_EVIDENCE: PB-05 (Forge, BOUNDED_NON_BLOCKING); AF01_FORGE.json
`engine_commit_source: env:FORGE_ENGINE_SHA`; WSR22 SOURCE_LOCK.json
(reference checkout HEAD/tree verified); container materialization writes an
equivalent provenance file.

AVAILABLE_OPTIONS:
- (a) Sufficient as-is (with the reference-checkout verification on record).
  Consequence: no bridge repair; AF00 stays PASS through remediation.
- (b) Require build-derived commit/tree emission from the Forge bridge.
  Consequence: bounded bridge repair + re-verification of AF00/AF01 only; no
  FULL107 rerun.
- (c) Require a container provenance file at Freeze time instead of bridge
  emission. Consequence: Freeze-procedure obligation rather than code repair;
  the file becomes part of the Frozen ADR's SOURCE_LOCK section.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: All three preserve the same pinned
commit (`ef958ee9…`); they differ in how strongly the commit is bound to the
built bytes. None affects Rules behavior.

---

## SLOT-06 — Capability-flag truthfulness correction without behavior change

QUESTION: Both candidates understate live capability (both report
`legal_actions_supported=false` / `action_submission_supported=false` while
live external decisions demonstrably work; XMage `seed_supported` and several
flags are lane-dependent). May the selected provider's bridge correct these
flags to describe the production lane truthfully — with no behavior change —
and have the corrected flags accepted as the Freeze capability record, and
which lane's flags govern?

WHY_COORDINATOR_AUTHORITY: Truthful-capability requirements sit at the AF01 /
freeze-schema boundary (`missing_or_unproven_required_capability_must_not_be_
promoted`; schema requires 11 capabilities true at eligibility). Accepting a
flag correction as the basis for required-capability presence is an
admission-evidence call.

EXACT_EVIDENCE: `WSR22_EVIDENCE_INGEST.json` capability_truth_table (three
lanes); WSR22 FINAL_HANDOFF material finding (manifest understates live
capability; reporting is lane-dependent); AF01 boundary
`truthful_capability_requirements`.

AVAILABLE_OPTIONS:
- (a) Accept flag correction on the designated production lane + rerun of the
  20 AF01 invariants there. Consequence: smallest path; capability record and
  behavior proven on the same lane.
- (b) Require behavior-level proof per flag beyond the handshake (e.g.,
  exercise each claimed decision class live). Consequence: larger AF04-linked
  campaign; stronger record.
- (c) Reject correction; treat reported `false` as binding. Consequence: the
  selected candidate cannot reach eligibility without a behavior change that
  makes the flags true — this contradicts the observed live decisions and is
  recorded only for completeness.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Options (a)/(b) both end with flags and
behavior agreeing on the production lane; (b) costs more runtime evidence.
Option (c) would force unnecessary provider changes against observed facts.

---

## SLOT-07 — AF01 single-lane PASS requirement (XMage)

QUESTION: If XMage is selected, must all 20 AF01 v2 invariants be PASS on one
designated production lane in a single run, or may the current split record
(compat lane 19 PASS + seed UNKNOWN; full-game lane PASS with
`seed_supported=true`) compose into AF01 PASS?

WHY_COORDINATOR_AUTHORITY: AF01 PASS semantics under the v2 boundary
(`af01_pass_requires`) with lane-dependent capability reporting is a
qualification-policy interpretation.

EXACT_EVIDENCE: AF01_XMAGE.json (UNKNOWN, seed invariant only); 
AF01_XMAGE_FULLGAME_LANE.json (PASS); PB-04 (BOUNDED_NON_BLOCKING).

AVAILABLE_OPTIONS:
- (a) Require a single production-lane all-PASS run. Consequence: rerun 20
  invariants on the production lane after the SLOT-06 flag correction; small,
  deterministic.
- (b) Accept composition with a lane-equivalence note. Consequence: no rerun;
  the Freeze record carries a two-lane evidence basis that every future
  requalification must reproduce exactly.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Option (a) produces a cleaner,
single-lane Freeze record and is the smaller long-term maintenance surface.
Option (b) saves one rerun now at the cost of a permanently two-laned record.

---

## SLOT-08 — PB-07 29-card corpus timing (pre-Freeze vs post-Freeze slice)

QUESTION: Must the effective 29-card actual-card corpus be individually
executed before Freeze (AF07 PASS pre-Freeze), or may Freeze proceed on
engine-validated 100-card deck import + CARD_02 PASS with the corpus campaign
as a named post-Freeze obligation of the first vertical slice?

WHY_COORDINATOR_AUTHORITY: This sets the AF07 admission bar — a required
gate's proof timing — which is evidence policy, not implementation choice.

EXACT_EVIDENCE: PB-07 (both, UNKNOWN_IMPACT); ACTUAL_CARD_XMAGE.json /
ACTUAL_CARD_FORGE.json (real-deck import engine-validated both; CARD_02 PASS
both); engine rejection probes (colour identity, unknown names) both.

AVAILABLE_OPTIONS:
- (a) Require the corpus pre-Freeze. Consequence: actual-card campaign on the
  selected lane before Freeze; AF07 PASS enters the Frozen ADR.
- (b) Defer the corpus to the first vertical slice as a blocking exit gate
  (slice cannot be declared complete without it). Consequence: Freeze rests on
  import-validation + CARD_02; the corpus becomes the slice's hardest
  qualification item with explicit failure semantics.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Both end with the corpus executed; they
differ in whether its proof is inside or outside the Freeze record. Under (b)
the Frozen ADR must record AF07's basis honestly (import + CARD_02) and the
slice contract must carry the corpus as a hard gate — both are already
structured that way in this packet.

---

## SLOT-09 — PB-08 replay-twin timing (pre-Freeze vs post-Freeze slice)

QUESTION: Must per-fixture clean-process replay twins be proven before Freeze
(AF09 PASS pre-Freeze), or may Freeze rest on engine-owned RNG binding +
same-seed twins + green native replay suites, with per-fixture clean-process
twins as a named post-Freeze obligation of the first vertical slice (which by
design runs one-game-per-process with decision/event/state-hash tapes)?

WHY_COORDINATOR_AUTHORITY: Same as SLOT-08: AF09 admission bar and proof
timing for a required gate.

EXACT_EVIDENCE: PB-08 (both, UNKNOWN_IMPACT); RNG_REPLAY_XMAGE.json /
RNG_REPLAY_FORGE.json (engine-owned RNG, requested_seed 424242, no
harness-injected outcomes; export_replay unsupported on both generic lanes);
native replay suites green and process-isolated.

AVAILABLE_OPTIONS:
- (a) Require per-fixture clean-process twins pre-Freeze. Consequence:
  replay-twin campaign (possibly needing bridge export support) before
  Freeze; AF09 PASS enters the Frozen ADR.
- (b) Defer per-fixture twins to the first vertical slice as a blocking exit
  gate. Consequence: Freeze rests on RNG attribution + same-seed twins; the
  slice — which is specified one-game-per-process precisely to make twins
  natural — produces the per-fixture proof.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Mirror of SLOT-08. Under (b) the slice
contract already carries replay twins as a hard exit gate
(`FIRST_PRODUCTION_VERTICAL_SLICE_CONTRACT.md`).

---

## SLOT-10 — Formal Architecture Freeze

QUESTION: After the selected-provider remediation completes and its
requalification evidence is presented, is Architecture Freeze claimed, binding
the Frozen ADR (Rules Core, provider, pin, protocol identity, topology,
player-count support, contracts, evidence, AF00–AF11 all-PASS)?

WHY_COORDINATOR_AUTHORITY: Architecture Freeze is explicitly Coordinator-only
and is the act this entire packet prepares but must not perform.

EXACT_EVIDENCE: The Frozen ADR draft (`ARCHITECTURE_FREEZE_ADR_TEMPLATE.md`
with Coordinator-fill locations marked); remediation requalification evidence
(future); this packet's readiness maps.

AVAILABLE_OPTIONS:
- (a) Claim Freeze on complete all-PASS evidence. Consequence: production
  repository bootstrap per `POST_FREEZE_BOOTSTRAP_PLAN.md` may begin.
- (b) Decline Freeze and direct further remediation. Consequence: a new
  bounded remediation workstream; no production repository.

TECHNICAL_CONSEQUENCE_OF_EACH_OPTION: Option (a) is only available when the
schema's own condition holds (all required gates PASS + all required
capabilities present); WSR24's validators enforce that no
`freeze_eligible=true` record can be constructed otherwise.

---

## Explicitly NOT decision slots (resolved inside WSR24)

- Test layout, JSON field names, file organization: WSR24 technical choice.
- Which remediation steps belong in which DAG: derived from evidence (PB
  register + gate verdicts), recorded symmetrically for both candidates.
- Production directory/module sketch: proposal in
  `PRODUCTION_REPOSITORY_CONTRACT.md`; binding choices belong to post-Freeze
  implementation, not to Sol now.
- Whether Forge 79 vs XMage 30 PASS implies anything: settled — it implies
  nothing about capability (evidence-build asymmetry, per WSR22 handoff and
  PB-03). Not a question.
