# FINAL-PREFREEZE-EVIDENCE-CLOSURE-20261001 (#441)

Source-bound deliverable packet for the single bounded pre-Freeze evidence-closure
workstream authorized by #255 comment 5925956587. Branch:
`hardening/final-prefreeze-evidence-closure-20261001`.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## What this workstream changed

### A — Forge AF04 reassembly (closed)

The assembler hard-coded Forge AF04 `UNKNOWN` on the premise that no decision
class beyond PRIORITY had been exercised, while the same-epoch
`PLAYER_CARDINALITY_FORGE.json` records externally answered STARTING_PLAYER,
MULLIGAN and PRIORITY frames at 2P–6P. #255 classified this as
`EVIDENCE_ASSEMBLY_GAP_PENDING_BOUNDED_REVALIDATION`.

`decision_boundary.derive_decision_boundary` now measures every recorded frame
against the engine-offered option domain, the engine's own executed-option
identity where it is reported, the engine's acceptance, actor/revision binding,
the keep-all mulligan progression and the artifact/runtime identity. A measured
contradiction is FAIL; an unmeasured element is UNKNOWN; PASS requires all of it.
The XMage gate is derived the same way, so the change strengthens both columns.

### B — causal-route direct execution (unchanged mechanism, now derived)

The mid-game lane's placement obligations already satisfy the clarified R-4
chain (Rules-Core construction → engine readback → engine-offered options only →
exact obligation from engine facts → receipt bound to candidate/runner/fixture/
requested-state/obligation). `CAUSAL_DIRECT_EXECUTION_LEDGER.json` enumerates
every admitted row and its checkpoint-equivalence proof; mechanism-equivalent
native harnesses remain supporting-only.

### C — fixture errata (closed as versioned records)

`FULL107_SUCCESSOR_CONTRACT_v1_0_7.json` re-applies every overlay to the same
1.0.5 historical base:

- **C1**: MICRO_MODES, NEGATIVE_FIRST_OPTION, NEGATIVE_GUI_DEFAULT,
  NEGATIVE_RANDOM_OPTION, NEGATIVE_SILENT_SKIP, PILOT_TARGET_AMOUNT and
  PILOT_MULTI_AMOUNT gain an explicit opening cast, reached through the
  engine-authored legal-action domain. The predecessor's inside-cast decision
  step and obligation are preserved; prose-derived action injection stays
  forbidden.
- **C2**: MICRO_COSTS is corrected so P2 is the active player at the same
  precombat-main checkpoint, making the scripted sorcery cast legal under
  CR 307.1. The cost/interaction obligation is unchanged.

Changed bytes create new evidence identities: `historical_digests` and
`supersedes_record_digest` preserve lineage, and no predecessor verdict
transfers.

### D — typed unsupported-discretionary-decision refusal (closed)

`refusal.refuse_pending_decision` is the explicit control-plane refusal. It
requires a real engine-authored frame with a non-empty offer set, submits
nothing, and records the no-mutation proof (unchanged public event offset and
unchanged pending decision identity) plus the transport window. The typed kind
`UNSUPPORTED_DISCRETIONARY_DECISION` is distinct from `DECISION_TIMEOUT`, and
the row verifier rejects a timeout relabelled as unsupported.

## Gate derivations

AF05–AF09 were hard-coded literals; they now derive from the same-epoch
artifacts and denominator rows (`gate_derivations.py`). AF04 also covers the
`ORDER_CHOICE` class introduced by the merged #443 cost-order policy.

## What remains open

See `REPLAY_TWIN_RESULTS.json`, `HIDDEN_CHANNEL_RESULTS.json`,
`ACTUAL_CARD_29_RESULTS.json` and `TYPED_UNSUPPORTED_DECISION_RESULTS.json` for
every remaining obligation and its exact mechanism. No denominator was shrunk,
no verdict was promoted without direct current-boundary evidence, and no
historical PASS was transferred.

## Packet

| File | Content |
|---|---|
| `WORKSTREAM_CONTRACT.json` | objective, scope, ownership, hard gates |
| `SOURCE_LOCK.json` | epoch identity, effective materialization, candidate identities |
| `OWNERSHIP_AND_DRIFT.json` | Gate 0 census, PR #440/#443/#444 adjudication |
| `FORGE_AF04_REASSEMBLY.json` | the discrepancy, derivation and proof conditions |
| `CAUSAL_DIRECT_EXECUTION_LEDGER.json` | admitted causal rows and their receipts |
| `FIXTURE_ERRATA_LEDGER.json` | the nine successor records and their digests |
| `TYPED_UNSUPPORTED_DECISION_RESULTS.json` | NEGATIVE_* rows and refusal mechanism |
| `HIDDEN_CHANNEL_RESULTS.json` | AF05 principal-scoping audit and residual channels |
| `ACTUAL_CARD_29_RESULTS.json` | the 29-card corpus coverage per candidate |
| `REPLAY_TWIN_RESULTS.json` | replay/RNG obligations and the twin contract |
| `VALIDATION.json` | FULL107 counts, AF00–AF10, PASS rows |
| `FINAL_HANDOFF.md` | the required handoff and exact next action |
