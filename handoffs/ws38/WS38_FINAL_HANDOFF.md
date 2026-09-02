# COMMANDER SIMULATION FOUNDRY
# WS-38 FINAL HANDOFF — FORGE AF04 RULES-CORE REMEDIATION FEASIBILITY

**Workstream:** WS-38  
**Status:** `COMPLETE`  
**Feasibility verdict:** `FEASIBLE_BOUNDED_CORE_REMEDIATION`  
**Forge provider qualification:** `NOT_GRANTED`  
**AF04 PASS:** `NOT_GRANTED`  
**Architecture Freeze:** `NO`  
**New Forge runtime:** `NOT_RUN`

---

## Source Lock

Commander Lab:

- repository: `moeendres-png/commander-playtest-lab`
- fresh `main`: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- main tree: `551c0d55a171508618d2b7d29e0f49b19893f886`
- WS-38 branch: `ws38/forge-af04-remediation-feasibility`
- branch base: WS-33 terminal head `2c19f7e401aa5eb9b2f2313086424c1bf903b3bd`
- branch-base tree: `248fb1d284a75bf01ae0e5681a595fefd2951013`

Forge:

- WS-33 qualified pin: `1e604105f9e279331063824943b9222b6589f5d8`
- WS-33 tree: `994976e06aaf99b807646b60b1aa2ac9f7703df4`
- fresh default-branch head: `ef4c834dbbca21a099ae751fb52b2326abdf1e02`
- fresh tree: `abd80b8e9ba1178bcd8e8fb3147ed6df292b4597`
- version: `2.0.15-SNAPSHOT`
- license: GPL-3.0
- upstream delta: fresh head is 25 commits ahead of the WS-33 pin and 0 behind.

Best remediation base: `ef4c834dbbca21a099ae751fb52b2326abdf1e02`.

Reason: relevant AF04 boundary files (`Combat`, `PlayerController`, human combat-damage controller, desktop damage UI, AI damage allocator) did not change in the 25-commit delta, while upstream otherwise advanced.

Rules authority:

- current official Magic Comprehensive Rules;
- effective 2026-08-07;
- `https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt`.

Current CR 510.1c-d makes general Damage Assignment Order obsolete. CR 510.1e validates the player's **total** combat-damage assignment. CR 702.19b adds trample's blocker-lethal condition and counts other same-step assigned damage. CR 702.2c provides deathtouch lethal semantics.

---

## Work Completed

1. Freshly locked current Forge upstream and Commander Lab predecessor state.
2. Compared current Forge against the exact WS-33 pin.
3. Traced the complete relevant production combat-damage path from `PhaseHandler` through assignment, controller, GUI/AI and final damage application.
4. Located every material combat-damage legality predicate in current source.
5. Proved that current core does **not** independently validate the returned controller allocation before committing it.
6. Audited adjacent attack/block validation architecture and the same callback's noncombat reuse.
7. Compared four remediation shapes and rejected provider-side legality and complete brute-force enumeration.
8. Designed a core-owned incremental transaction + canonical validator API.
9. Quantified allocation-space growth.
10. Defined engine-level negative/positive/headless tests and complete future successor requalification requirements.
11. Created an isolated patch specification only; no Forge upstream modification or provider qualification was performed.

---

## WS-33 Terminal Defect Restatement

Inherited controlling defect:

`WS33-FORGE-PROVIDER-AF04-001`

Signature:

`COMBAT_DAMAGE_LEGALITY_LIVES_IN_CONTROLLER_GUI_NOT_RULES_CORE_LEGAL_OPTION_API`

WS-33 terminal result remains authoritative:

- `FAIL_TERMINAL_FORGE_PROVIDER_DEFECT`
- successor runtime PASS: `0 / 107`
- `CARD_02`: `NOT_RUN_AFTER_AF04_STOP_CONDITION`
- AF05/AF06/AF08/AF09 were not run after the AF04 stop.

WS-38 does not rewrite or supersede this result. Only a new repaired Forge source identity plus complete successor requalification can supersede it.

---

## Fresh Callgraph

Production path:

`PhaseHandler`
→ `Combat.assignCombatDamage(firstStrike)`
→ `Combat.assignAttackersDamage` / `assignBlockersDamage`
→ core determines source/defender/assigning player/net combat damage and runs AssignDealDamage replacement boundary
→ `PlayerController.assignCombatDamage(...)`
→ human: `PlayerControllerHuman` → `IGuiGame` → `VAssignCombatDamage`
**or**
→ AI: `PlayerControllerAi` → `ComputerUtilCombat.distributeAIDamage`
→ returned `Map<Card,Integer>`
→ `Combat` directly calls `addAssignedDamage` / `damageMap.put`
→ `Combat.dealAssignedDamage`
→ `GameAction.dealDamage` / replacement/prevention/state mutation.

First strike / double strike orchestration is already Rules Core-owned and produces separate damage steps.

---

## Where Combat-Damage Legality Actually Lives

### Already core-owned

Forge core already knows:

- current combat topology and defenders;
- assigning player under normal combat, banding/Defensive Formation cases;
- net combat damage;
- trample/deathtouch keywords;
- `Card.getLethalDamage`;
- marked/assigned damage bookkeeping;
- first/double-strike damage-step membership;
- optional legacy `orderCombatants` mode;
- subsequent damage replacement/prevention/application.

### Incorrectly controller/GUI/AI-owned or duplicated

`VAssignCombatDamage` contains legality-sensitive calculations/guards for:

- recipient progression;
- lethal amount;
- deathtouch;
- infect-related defender display/threshold behavior;
- trample;
- available total;
- auto-allocation.

`ComputerUtilCombat.distributeAIDamage` independently constructs allocations using lethal/trample/order logic mixed with tactical preference.

`PlayerControllerHuman` also performs forced/simple auto-assignment itself.

### Missing core authority

The returned allocation map is not comprehensively validated before `Combat` commits it. This means the terminal defect is both:

- `FORGE_CONTROLLER_BOUNDARY_DEFECT` / `FORGE_GUI_LEGALITY_DEFECT`; and
- `FORGE_RULES_CORE_VALIDATION_DEFECT`.

---

## Core Validation Findings

### A. Does Forge core already contain sufficient legality validation?

**NO.**

The core has important rule primitives, but no canonical `validateCombatDamageAssignment` equivalent is applied to controller submission.

Direct malformed submissions can reach the commit loop without a demonstrated comprehensive rejection boundary for:

- underassignment;
- overassignment;
- foreign recipient;
- illegal direct defender spill;
- trample spill before blocker lethal;
- deathtouch lethal misuse;
- legacy-order violation when enabled;
- shared-blocker same-step lethal accounting.

### B. Does legality exist only in GUI/AI?

**Material portions do.** The raw game facts exist in core, but GUI and AI currently combine those facts into the allocation legality procedure. That is not an acceptable Rules-Core/pilot boundary.

### C. Is this one instance of a wider controller pattern?

One directly adjacent reuse was found:

`DamageDealEffect.divideOnResolution` reuses `assignCombatDamage` for noncombat multi-target amount division and directly writes the returned map. It should not be accidentally inherited by the new combat API; if production-reachable, it needs a separate constrained core distribution decision.

In contrast, neighboring attack/block declarations already have core validators:

- `CombatUtil.validateAttackers`
- `CombatUtil.validateBlocks`

This is strong architectural precedent for a bounded remediation.

---

## Related Controller-Boundary Findings

1. `FORGE_CONTROLLER_BOUNDARY_DEFECT`: raw combat allocation map crosses from controller to state mutation.
2. `FORGE_GUI_LEGALITY_DEFECT`: desktop/mobile combat-damage UI encodes legal-assignment restrictions.
3. `FORGE_AI_LEGALITY_DUPLICATION`: AI allocator duplicates legality while optimizing tactics.
4. `FORGE_HEADLESS_API_GAP`: no engine-owned headless legal amount/recipient surface.
5. Adjacent `DamageDealEffect.divideOnResolution` callback reuse needs isolation/separate validation.
6. No `FORGE_RULES_DEFECT` is claimed. This workstream did not prove incorrect Magic outcome from a correctly constructed native runtime state.

---

## Remediation Options Considered

### 1. Complete legal-alternative enumeration

- architecture: enumerate every legal final allocation in core;
- correctness: potentially strong;
- complexity: moderate;
- performance: poor/combinatorial;
- integration: easy for pilot, expensive payload;
- maintenance: moderate-high;
- upstreamability: low-moderate;
- verdict: **reject as primary design**.

### 2. Final validator only

- architecture: let controller propose arbitrary map, then core validates;
- correctness: prevents illegal commit;
- complexity: low;
- performance: good;
- integration: small;
- maintenance: low;
- upstreamability: high;
- verdict: **insufficient** because headless provider/pilot would still need to reconstruct legality to discover a valid map.

### 3. Incremental core-constrained transaction + final validator

- architecture: core owns legal recipients/ranges/candidates and the full player/damage-step assignment transaction;
- correctness: strong and compatible with CR 510.1e + 702.19b;
- complexity: bounded/nontrivial;
- performance: good;
- integration: one shared GUI/AI/headless surface;
- maintenance: moderate;
- upstreamability: moderate-high;
- verdict: **RECOMMENDED**.

### 4. Provider-side legality

- architecture: Commander Lab computes assignments;
- correctness/architecture: forbidden second Rules engine;
- verdict: **FORBIDDEN**.

---

## Recommended Forge Rules-Core API

Use a Forge-core `CombatDamageDecision`/transaction plus canonical `CombatDamageAssignmentValidator` (names illustrative).

Critical design point: the transaction should cover one assigning player's complete assignment in one combat-damage step, not treat every source as an isolated independent legality universe. CR 510.1e validates total assignment, and CR 702.19b allows trample lethal to count damage from other creatures being assigned during that same step.

The core should expose incrementally:

- current source;
- legal recipients;
- core-derived legal amount range/candidates given current partial transaction;
- whether the source is complete;
- legal next source or forced progression;
- transaction completion.

The pilot chooses only among those core-authorized choices.

Before mutation, the canonical validator re-evaluates the complete assignment against live state. A stale/malformed response fails closed.

GUI and AI must migrate to the same surface. GUI becomes presentation; AI becomes tactical ranking among legal choices.

---

## Complexity Analysis

Unconstrained integer splits of damage `D` among `k` recipients are:

`C(D+k-1, k-1)`.

Examples:

- D=3, k=2: 4
- D=6, k=3: 28
- D=10, k=4: 286
- D=20, k=5: 10,626
- D=20, k=10: 10,015,005
- D=40, k=10: 2,054,455,634
- D=100, k=10: 4,263,421,511,271

Simultaneous combat groups multiply the state space. Therefore complete allocation enumeration is not a production-safe default representation.

Incremental core-derived ranges/candidates preserve correctness without moving legality outward.

---

## Prototype

**Implemented:** `NO`.

Reason:

- WS-38 did not establish a writable isolated Forge fork/branch plus compile/test execution path;
- user contract forbids silently modifying upstream Forge;
- the correct change spans core API plus GUI/AI consumer migration and should not be represented as runtime-proven by an uncompiled textual patch.

Produced instead:

`candidate-qualification/ws38-forge-af04/WS38_PATCH_DIFF_SPEC.md`

This is an exact engine-side patch specification, explicitly `NOT_IMPLEMENTED` / `NOT_COMPILED`.

Prototype tests: `NOT_RUN`.

---

## PASS / FAIL / UNKNOWN — Feasibility Only

| Gate | Result |
|---|---|
| G38-01 Fresh Forge lock | PASS |
| G38-02 Complete relevant callgraph | PASS |
| G38-03 Legality ownership proven | PASS |
| G38-04 No provider legality workaround | PASS |
| G38-05 No GUI/AI dependency in proposed production design | PASS |
| G38-06 Core validation included | PASS |
| G38-07 Pilot only chooses core-authorized discretion | PASS |
| G38-08 Complexity explicitly analyzed | PASS |
| G38-09 Future regression/requalification scope defined | PASS |
| G38-10 No qualification credit granted | PASS |

Machine verdict:

`FEASIBLE_BOUNDED_CORE_REMEDIATION`

This is **not** a Forge provider PASS.

---

## Defect Register

### `WS33-FORGE-PROVIDER-AF04-001`
- taxonomy: `FORGE_PROVIDER_ARCHITECTURE_DEFECT`
- status: OPEN pending repaired source + requalification.

### `WS38-FORGE-AF04-VALIDATION-001`
- taxonomy: `FORGE_RULES_CORE_VALIDATION_DEFECT`
- finding: controller allocation is committed without comprehensive independent core validation.

### `WS38-FORGE-AF04-BOUNDARY-001`
- taxonomy: `FORGE_CONTROLLER_BOUNDARY_DEFECT`
- finding: raw amount map requires controller to construct assignment.

### `WS38-FORGE-AF04-GUI-001`
- taxonomy: `FORGE_GUI_LEGALITY_DEFECT`
- finding: GUI contains lethal/deathtouch/trample/order-sensitive legality.

### `WS38-FORGE-AF04-AI-001`
- taxonomy: `FORGE_AI_LEGALITY_DUPLICATION`
- finding: AI duplicates legality while selecting tactical allocation.

### `WS38-FORGE-AF04-HEADLESS-001`
- taxonomy: `FORGE_HEADLESS_API_GAP`
- finding: no core-owned constrained headless damage-decision surface.

### `WS38-FORGE-RELATED-001`
- taxonomy: `FORGE_CONTROLLER_BOUNDARY_DEFECT`
- finding: noncombat `DamageDealEffect.divideOnResolution` reuses raw damage-map callback.

No `FORGE_RULES_DEFECT` and no `QUALIFICATION_INFRA_DEFECT` are claimed.

---

## Changes

Commander Lab only:

- created branch `ws38/forge-af04-remediation-feasibility` from WS-33 terminal head;
- added WS-38 source/callgraph/legality/validation/remediation/complexity/test/requalification evidence;
- added an isolated Forge patch specification;
- added this final handoff and checksum manifest.

Forge upstream: **unchanged**.

No merge performed.

---

## Tests / Evidence

Fresh source/callgraph/rules audit: `PASS`.

New Forge engine compile: `NOT_RUN`.

New Forge unit tests: `NOT_RUN`.

New successor 107 runtime: `NOT_RUN`.

No runtime qualification credit is inferred from source analysis.

Evidence is indexed in `qualification/ws38/WS38_EVIDENCE_INDEX.json`.

---

## Licensing / Integration Boundary

Forge remains GPL-3.0. The proposed Rules-Core API lives entirely inside the Forge GPL process/service.

The proprietary Commander Lab side consumes only the serialized provider-neutral decision frame and returns a discretionary selection. It does not embed Forge code and does not implement Magic legality.

This preserves the established WS-09 engineering topology. This handoff is technical engineering analysis, not legal advice.

---

## Remaining Blockers

1. Implement the proposed Rules-Core transaction/validator in an isolated Forge remediation branch/fork.
2. Compile and run the complete engine-level positive/negative/headless test plan.
3. Prove GUI and AI both consume the same core legality surface.
4. Prove there is no production-reachable raw allocation-map bypass.
5. Address/separate the adjacent `DamageDealEffect.divideOnResolution` reuse if production-reachable.
6. Produce a new exact Forge source identity.
7. Rebuild the Commander Lab Forge provider against that identity.
8. Rerun full exact WS-32 v1.0.2 successor qualification.

---

## Outputs

- `qualification/ws38/WS38_SOURCE_LOCK.json`
- `qualification/ws38/WS38_FORGE_UPSTREAM_DELTA_AUDIT.json`
- `qualification/ws38/WS38_AF04_CALLGRAPH.json`
- `qualification/ws38/WS38_LEGALITY_LOCATION_LEDGER.json`
- `qualification/ws38/WS38_CORE_VALIDATION_AUDIT.json`
- `qualification/ws38/WS38_RELATED_CONTROLLER_BOUNDARY_RISKS.json`
- `qualification/ws38/WS38_REMEDIATION_OPTIONS.json`
- `qualification/ws38/WS38_RECOMMENDED_RULES_CORE_API.md`
- `qualification/ws38/WS38_COMPLEXITY_ANALYSIS.json`
- `qualification/ws38/WS38_TEST_PLAN.json`
- `qualification/ws38/WS38_PATCH_FEASIBILITY_VERDICT.json`
- `candidate-qualification/ws38-forge-af04/WS38_PATCH_DIFF_SPEC.md`
- `qualification/ws38/WS38_FUTURE_REQUALIFICATION_PLAN.json`
- `qualification/ws38/WS38_EVIDENCE_INDEX.json`
- `qualification/ws38/WS38_SHA256SUMS`
- `handoffs/ws38/WS38_FINAL_HANDOFF.md`

---

## Dependencies Unblocked

A dedicated Forge engine-remediation + successor-requalification workstream is now technically justified.

What is unblocked is **implementation and requalification**, not AF04 PASS.

---

## Exact Next Action

Create a dedicated Forge engine-remediation + complete successor-requalification workstream.

First implement and engine-test the bounded Rules-Core `CombatDamageDecision` transaction + canonical validator at a new Forge source identity. Then rebuild the isolated Forge provider and rerun the entire exact WS-32 v1.0.2 **107-record denominator**.

**No WS-33 runtime credit may be inherited.**

`SOURCE PATCH != PROVIDER QUALIFIED`

`UNIT TEST PASS != SUCCESSOR RUNTIME PASS`

No Architecture Freeze.
