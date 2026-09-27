# Selected-Provider Impact Template — what survives, what reruns, falsifiers

Purpose: after the Coordinator selects exactly one provider (SLOT-01), this
template scopes the remediation requalification precisely: which historical
evidence survives untouched, which must rerun, which must NOT rerun, and what
would falsify remediation success. Fill one copy for the selected candidate;
discard the other DAG's execution (keep both DAG files as record).

No provider is selected in WSR24. Fields marked 【COORDINATOR-FILL】 or
【REMEDIATION-OWNER-FILL】 are completed post-selection.

---

## 1. Selection binding

- Selected candidate: 【COORDINATOR-FILL: xmage | forge】
- Engine pin: 【COORDINATOR-FILL: commit + tree + artifact + SHA-256】
- Remediation DAG: 【REMEDIATION-OWNER-FILL: REMEDIATION_DAG_XMAGE.md or
  REMEDIATION_DAG_FORGE.md, with step check-boxes】

## 2. Historical evidence that SURVIVES (no rerun)

The following WSR22 evidence is invariant to the remediation surface and
survives by impact adjudication (no code/pin/contract/harness/semantic change
touches it):

- AF02 cardinality lifecycles (2P/3P/4P/5P + bounded 6P), unless the provider
  pin or lifecycle driver changes. Source:
  `PLAYER_CARDINALITY_{XMAGE,FORGE}.json`.
- AF03 Rules-authority probes (colour-identity rejection, unknown-name
  rejection, no fabricated options), unless deck-import or submission paths
  change.
- AF10 denominator accounting of the boundary run itself (historical record;
  the remediation rerun establishes its own AF10).
- START-2 v1.0.6 execution, unless START-2 semantics, the successor contract,
  or the start-of-game path changes.
- Native suites (XMage 34+134; Forge 150+67) as mechanism provenance, unless
  the engine pin changes. (They are provenance, not obligation PASS records.)
- The DIVERGENCE_PACKET (0 divergences) as a historical observation, not as a
  standing claim: any remediation that changes behavior re-opens divergence
  analysis for the touched rows.

## 3. What MUST rerun (requalification impact set)

【REMEDIATION-OWNER-FILL: check each item as its DAG step completes】

- [ ] AF01 20-invariant run on the designated production lane (both
  candidates: required after any capability-flag or lane change).
- [ ] AF04 decision-boundary probes on the production lane, including the
  new shim provenance tests (both candidates).
- [ ] AF11 single-provider topology re-verification (both candidates).
- [ ] PB-03 row set: XMage 33 BLOCKED rows, or Forge 7+2 rows — via injection
  seam or via the SLOT-02 mechanism-equivalence mapping (Coordinator-chosen).
- [ ] AF05 scenario campaign rows: XMage 19 rows, or Forge 8 rows (SLOT-04
  scope may narrow only by explicit ruling).
- [ ] AF07 29-card corpus (SLOT-08 timing: pre-Freeze or slice gate).
- [ ] AF09 clean-process twins (SLOT-09 timing: pre-Freeze or slice gate).
- [ ] AF10 re-established on every rerun (denominator-complete accounting,
  zero crash/timeout/protocol-failure).

## 4. What MUST NOT rerun

- FULL107 rows already PASS whose obligation, execution path, engine pin, and
  contract are all unchanged by the remediation. (Rerunning them "for
  reassurance" is forbidden by the Workstream Contract hard gates.)
- The WSR22 comparison packet (it is a historical record of that boundary;
  a new comparison, if needed, is a new artifact with a new identity).
- Rules-authority capture (CURRENT_RULES_AUTHORITY.json stands unless the
  official page target changes, which fails closed by its own test).

## 5. Falsifiers — what would prove remediation FAILED

Any one of these falsifies the remediation and returns the workstream to the
Coordinator:

1. Any FULL107 row returns FAIL (a Rules-visible failure where WSR22 recorded
   zero FAILs).
2. Any crash, timeout, or protocol failure appears in a rerun where WSR22
   recorded zero (AF10 regression).
3. A Rules-visible divergence appears between the remediated lane and the
   historical record on an unchanged obligation (divergence packet non-empty).
4. The shim provenance test fails: a submitted decision identity does not
   byte-match the offering provider frame (legality-boundary breach).
5. A honeycard leakage negative fails (hidden-information breach).
6. Harness-side randomness is detected on a production-reachable path
   (RNG-ownership breach).
7. Any `freeze_eligible=true` record validates against the schema while a
   gate is non-PASS or a required capability is missing (validator breach —
   this must be caught by the WSR24 validators before it reaches review).

## 6. Terminal condition

Remediation succeeds IFF: every item in §3 is checked with evidence refs,
no falsifier in §5 fired, the twelve AF verdicts are all PASS, all required
capabilities are present, and the schema validates `freeze_eligible=true`.
Then SLOT-10 (Formal Architecture Freeze) is ready for the Coordinator.
