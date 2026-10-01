# Coordinator decision packet: PB-09, SLOT-02/03/07, provider gate

- **Date:** 2026-09-30.
- **Source:** `main` `3e3cd11a`, with #420 merged. The evidence tree of record is `qualification/final-current-boundary-20260927/`, requalified on `main` through `820a4642`. The documented #411 run is cited where it adds to that tree.
- **Author:** the Claude campaign lane, at the owner's request ("die wenigen echten Coordinator-Entscheidungen explizit adjudizieren").

## Decision record

**ACCEPTED by the repository owner on 2026-09-30:** R-1, R-2, R-3 and R-4. The acceptance is recorded on #255 (comment 5918493550), in the owner's words: "ja dann R-1 annehmen genauso wie R-2 bis R-4 etc und alles umsetzen".

Follow-ups executed:
- #297 and #299 are closed as `DONOR_EVIDENCE`.
- forge#11 (including #12) was admitted into the Forge candidate.
- The R-3 Forge bridge repair is delivered by forge#13, inside the integrated gate forge#16.

R-5 stays a finding, not a ruling. B1, SLOT-04/05/06/08/09, provider selection and Freeze are **not** decided by this record.

## Status of this packet

Under AGENTS.md §4/§8, Provider Selection, Architecture Freeze and evidence-policy rulings are Coordinator authority. They are not executor authority, so the rulings below are written as **binding texts ready for signature**:
- every ruling states its evidence;
- every ruling states its consequence;
- each one takes effect **only when the Coordinator/owner accepts it explicitly on #255**. Merging this file only records the proposal; a merge is not a signature.

Nothing here selects a provider or claims Freeze.

Two principles hold throughout:
- **No engine wins by test count.** Each candidate is judged against the same all-PASS rule of `architecture_freeze_contract_v2`, never against the other candidate.
- **UNKNOWN is never PASS.**

---

## R-1: PB-09, the Forge candidate identity

**Ruling.** The Forge provider candidate is the **Commander-Lab Forge fork**:
- Rules Core `ef958ee91ac6c9ce0152189f2654bf6e05abf273` (tree `fc3387bf…`);
- extended only by changes the Coordinator admits explicitly (today forge#11, and forge#12 on top of it).

Pristine upstream `a37a865a…` (tag `forge-2.0.14`) is **reference baseline only**. It is not a provider candidate, and no evidence transfers between the two identities in either direction.

**Evidence:**
- **The fork diverges in the Rules Core.** 47 commits touch `forge-game/src/main/java` between pin and fork. They include WS40 combat-damage legality, WS45 Commander relation history, the WS217 CR 601.2d chooser-divided seam and the WS234 Cleave/Aftermath fix (`docs/pre_freeze_completion_20260927/PB09_FORGE_CANDIDATE_IDENTITY.md` §3).
- **Pristine upstream fails a required gate: AF03.** It accepts an illegal Commander deck after a legal control import (#299, `qualification/pb09-pristine-upstream-20260929/` on that branch).
- **The Lab bridge does not compile against pristine upstream.** The WS40, WS217 and fork `MyRandom` seed APIs are fork-only (#255 checkpoint of 2026-09-29).
- **Every current-boundary Forge run executed the fork** (`SOURCE_LOCK.json` `forge_candidate`).

**Consequences:**
- Both candidates are Lab-maintained forks at exact pins: XMage `9375f35a` on `moeendres-png/mage`, Forge `ef958ee9` (+ admitted changes) on `moeendres-png/forge`. Fork maintenance and licence (MIT vs GPL-3.0) are reported dimensions only. They do not override Rules gates.
- Pristine upstream Forge would need a new bridge plus re-implementation of the fork's Rules-Core repairs just to reach AF03. That makes it a different project, not a cheaper candidate.
- **#297 and #299 become `DONOR_EVIDENCE`.** Their pristine counts differ: PASS 5/107 versus 1/107. They do not need reconciling, because neither count is consumed by any gate. Both stay recorded as reference-baseline observations.

---

## R-2: SLOT-03, the decision-identity shim (AF04/AF11)

**Ruling: option (c).** The provider-specific decision-identity shim is protocol translation. This applies to `game_driver.decision_identity_params`:
- XMage uses `decision_id` (sha256) plus the pass `action_id`;
- Forge uses `revision` (long) plus `actor_id`.

It is approved on one condition: a provenance conformance test must prove that every submitted identity byte-matches a value in the frame the provider just offered.

**Evidence:**
- **Condition satisfied by this packet.** `tests/qualification/test_current_boundary_decision_identity_provenance.py` (8 tests) asserts:
  - byte and type equality with the offering frame for both candidates;
  - the pass identity is the offered `pass_priority` option, never the first option;
  - identities follow each new frame and are never carried over;
  - the frame is not mutated;
  - a frame without an identity is not given one.
- **XMage's AF04 FAIL cites only the identity shape difference** (`AF00_AF11_XMAGE.json` AF04 evidence: "neither accepts the other's shape"; `blocking_rows: []`).

**Consequence:** XMage AF04 changes from FAIL to PASS at the next current-boundary requalification. Forge AF04 stays UNKNOWN until the same run exercises decision classes beyond PRIORITY on its lane.

---

## R-3: SLOT-07, the AF01 single-lane PASS and re-seal

**Ruling: option (a).** AF01 PASS requires all 20 v2 invariants to pass in **one run on one designated production lane**. For XMage that lane is the compatibility lane used by `run_current_boundary_qualification.py`.

**Evidence:**
- The requalified tree on `main` records `AF01_XMAGE` = PASS on that lane (`AF00_AF11_XMAGE.json`). A fresh single run at `9375f35a` also gave 20/20, including `unsupported_production_reachable_decision` (the #390 fix).
- **The re-seal for XMage is therefore done.** No composition of two lanes is needed or admitted.
- **Forge AF01 is FAIL** on exactly one invariant, `fail_closed_invariants.unsupported_production_reachable_decision`: "provider accepted a request for an unsupported decision class for a live game" (`AF01_FORGE.json`). This is the same defect XMage had before #390.

**Consequence:** Forge needs one bounded bridge repair in the Forge candidate lane, the analogue of #390, before its AF01 can pass. No policy question remains.

---

## R-4: SLOT-02, PB-03 mechanism equivalence

**Ruling: option (a).** Direct execution is required. Mechanism-equivalent adjacent evidence does not satisfy a FULL107 obligation.

**Evidence:**
- The reason for option (b) was that no starting-state seam existed. That reason no longer holds: #411 built the admitted seam and the receipt path.
  - The midgame placement lane executes exact placement obligations with engine-offered answers only.
  - Receipts are bound to candidate and runner.
  - The consumer verifies them fail-closed.
  - The documented run verified 9/9 rows on XMage.
- Crediting adjacent mechanisms would re-open the evidence-integrity defect class that #278 exposed, where upper-bound counts were read as PASS.

**Consequence:** every remaining BLOCKED/UNKNOWN FULL107 row is executed through the admitted seam, or it stays BLOCKED/UNKNOWN. Native harness tests remain supporting evidence without credit, as the Sol adjudication on #255 already set for #311–#315.

---

## R-5: which current gaps are provider-blocking

| Gap | Candidate | Provider-blocking? | Why |
|---|---|---|---|
| FULL107 rows without a verified current-boundary receipt: 93 XMage (14/107 PASS in the documented #411 run, 5 in the committed tree), 102 Forge (5/107) | both | **yes** | Freeze requires AF05–AF09 PASS, and their blocking rows are FULL107 rows. |
| XMage AF04 identity shape | XMage | no, after R-2 | Condition met by the provenance test. |
| Forge AF01 `unsupported_production_reachable_decision` | Forge | yes, bounded | A single invariant, analogous to #390. |
| `multi_amount` leaver unwind fail-closed (F-42 follow-up 3) | XMage | no | Fail-closed is the allowed behaviour for an unqualified class. The native unwind would violate CR 800.4a. |
| Find // Finality Aftermath discovery (PB-07, forge#9 inside #11) | Forge | no | Absent capability that fails closed. The pilot cannot fabricate the action. Remains PARTIAL. |
| AF11 single-provider re-verification | both | sequenced | It runs after selection, on the selected provider only. |

**Provider gate: NOT PASS.** No candidate satisfies the all-PASS rule today.

**The one named blocker:** *current-boundary execution of the FULL107 denominator through the admitted midgame seam (#411), with verified receipts.* Every UNKNOWN or BLOCKED required gate that remains (AF05, AF06, AF07, AF08, AF09) lists FULL107 rows as its blocking rows. Once R-2 through R-4 are signed, no required gate is blocked by anything else, except Forge's single AF01 invariant, which is a bounded bridge fix.

**The bounded workstream** this blocker authorizes, under #255's rule "at most one bounded remediation workstream":
1. Extend the #411 producer across the remaining row families. Row families come before candidates, and both candidates run through the same producer.
2. Requalify the boundary.
3. Present the per-candidate AF matrix.

Provider selection follows from the matrix: a candidate is eligible only if all of its gates PASS. A difference in counts between candidates is never the criterion.

---

## Not decided here (still open, not on the critical path until R-5's blocker moves)

- **SLOT-04** (hidden-channel scope), **SLOT-08** (29-card corpus timing) and **SLOT-09** (replay-twin timing). All three become concrete only after the denominator rows execute. The HIDDEN, CARD and REPLAY rows belong to the same FULL107 denominator.
- **SLOT-05 / SLOT-06.** These matter only if Forge or XMage respectively is selected.
- **Forge admission of forge#11/#12 production-code changes.** Covered by R-1's "admitted explicitly".

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED` · no denominator change · no pin change
