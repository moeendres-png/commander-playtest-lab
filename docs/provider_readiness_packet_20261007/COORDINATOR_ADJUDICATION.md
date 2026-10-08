# Coordinator adjudication — provider readiness (issue #255)

Decision document for the Owner. It adjudicates the section-F evidence; it does **not** select a
provider. `PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` ·
`PRODUCTION_REPOSITORY = NOT_CREATED`. Production Provider selection is Owner-only (AGENTS.md §8).

## Source lock

- Sealed epoch `qualification/current-boundary-epochs/ff688b58359f-42c21a3659cd/` (#614), produced
  from main `ff688b58359f7ec3cbace344322989c18e58886a` (tree
  `42c21a3659cdf73ca15d1baaf62bbfed9003c797`), effective contract
  `commander-lab.full107/1.0.24-successor`, pins XMage `b479fe74`, Forge Rules-Core
  `bb0a740d`, Forge bridge `31cbae12` — all IDENTICAL to the sealed evidence. The epoch's
  effective contract equals the current pointer (`qualification/CURRENT_PRE_FREEZE_CONTRACT.json`,
  1.0.24), so the packet records the fixture contract as IDENTICAL; this epoch executed the
  1.0.22 → 1.0.24 errata, including the bounded-6P record-declared starting seat.
- Section-F packet: `docs/provider_readiness_packet_20261007/PROVIDER_READINESS.{json,md}` (#597),
  independently reviewed on #596 (no P0/P1); both P2 findings and three P3 notes fixed in #597.

## AF gate state (sealed)

| Gate | XMage | Forge |
| --- | --- | --- |
| AF00 / AF01 / AF02 / AF03 / AF10 | PASS | PASS |
| AF05 hidden information | PASS | UNKNOWN (20 hidden rows unexecuted: HIDDEN_01–19 and the honeycard sentinel) |
| AF07 actual-card corpus | PASS | UNKNOWN (CARD_02; 29 identities unexecuted) |
| AF09 Rules RNG / semantic replay | PASS | UNKNOWN (5 replay rows) |
| AF06 general rules correctness | UNKNOWN — 106/107 PASS, 1 UNKNOWN (`NEGATIVE_PARENT_CLASS_FALLBACK`) | UNKNOWN — 20/107 PASS, 33 BLOCKED, 54 UNKNOWN |
| AF08 commander / multiplayer | PASS | UNKNOWN — 21 rows |
| AF04 decision boundary | PASS | PASS |
| AF11 interop / licence topology | UNKNOWN | UNKNOWN |

Neither candidate passes AF00–AF11. Neither is freeze-ready.

## Findings

1. **No Rules divergence is established.** All 107 comparison rows are `NON_COMPARABLE`
   (0 `SAME_SEMANTICS`, 0 adjudicated differences). The evidence ranks *measured coverage*, not
   demonstrated Rules quality. Forge's gap is not evidence that Forge is Rules-worse.
2. **Forge's gap is dominated by unexecuted work, not engine defects.** Forge's row states are
   unchanged from epoch `b1c8f54a999a-2d13b953a82c` (20 PASS / 33 BLOCKED / 54 UNKNOWN). Of the 87
   non-PASS Forge rows:
   grouped by the leading clause of `failure_reason`, 54 are fixtures corrected by the successor
   contract and not yet re-executed on Forge, 23 are `LAB_EXECUTION_GAP` (21 at construction,
   2 at execution), 5 `PROVIDER_ADAPTER_GAP`, 1 `CONTRACT_AUTHORITY_GAP`, 2 missing per-shortcut
   negatives, 1 London bottom (MULL-2) and 1 without a current-boundary execution path. Counted
   across all recorded missing mechanisms, however, **36 rows name a `PROVIDER_ADAPTER_GAP`** (for
   example the pinned bridge exports no event log, or the readback lacks the card owner), 31 of
   them among the 54 corrected rows. Forge therefore carries real provider-side work, not only
   Lab execution. Wave 2 (#592) owns these rows.
3. **XMage is one row from AF06.** MULL-2 now passes on the real engine: the generic Protocol2
   lane publishes the London bottom as a decision, and the Lab answers it only from the record's
   script (#603). With that, XMage AF08 passes. The remaining row is `NEGATIVE_PARENT_CLASS_FALLBACK`.
   Building its execution seam showed that the record itself was unreachable. It put P2's
   sorcery on the stack in turn 1, which CR 307.1 forbids. Three errata fixed that:
   - 1.0.24: turn 2, P2 active, cast from hand, a paid cost, and empty hands for P3/P4
     (CR 101.4).
   - 1.0.25: P1's forced turn-1 cleanup discard, CR 103.8c / 514.1.
   - 1.0.26: the whole pre-checkpoint history declared explicitly, so the Lab never chooses
     for a player (#592). This one is in progress.

   The bridge supports the turn-2 checkpoint and refuses unreachable states fail-closed. The row
   has run locally on the real engine, but that is LOCAL_OBSERVED and not credit. It needs the
   1.0.26 round to merge and a new epoch.
4. **AF04 now passes for both candidates.** The bounded 6P record carries an authoritative starting
   seat (contract 1.0.23, #604). Both candidates run 6P without a Lab seat default. The sealed
   decision boundary has no gap and no contradiction.
5. **AF11 cannot be adjudicated to PASS now.** The observed qualification topology is
   separate-process for both candidates, but the catalog obligation binds the *actual* integration
   topology ("Actual integration topology satisfies WS-09; Forge remains a genuine separate
   process/service", `qualification/pre-freeze-successor/architecture_freeze_gate_catalog_v2.json`,
   AF11). The freeze-readiness records name the missing proof as a single-provider production
   topology in which the adapter serves exactly the selected candidate
   (`docs/architecture_freeze_readiness_20260927/FORGE_FREEZE_READINESS.json:253`,
   `XMAGE_FREEZE_READINESS.json:302`). That topology does not exist before selection. In addition,
   the Owner has instructed the Coordinator that the D17 in-JVM residual risk (Forge-fork
   workstream, #498 / forge#18) is **not accepted**. AF11 stays `UNKNOWN`; it is re-adjudicated
   against the production topology after the Owner's selection. Recorded licence metadata
   (XMage MIT, Forge GPL-3.0) is not a legal conclusion.

## Coordinator assessment

On the sealed evidence, **XMage is the evidence-leading candidate**. It passes 10 of 12 AF gates,
against 6 of 12 for Forge, and 106 of 107 FULL107 rows, against 20 of 107. Its only open
qualification gate that a selection does not depend on is AF06. AF06 waits on the single row
`NEGATIVE_PARENT_CLASS_FALLBACK`, whose remaining work is bounded and in progress. AF11 can only be
adjudicated after a selection. This is an assessment of measured readiness. It is not a
selection, and it is not a Rules verdict against Forge.

## Options for the Owner

| Option | What it means | Consequence |
| --- | --- | --- |
| A — select now | Owner selects a provider on current evidence | Freeze still requires XMage AF06 (one row) and the post-selection AF11 adjudication |
| B — defer until XMage AF06 closes (Coordinator-recommended) | No selection yet; the Coordinator lands the 1.0.26 round, re-runs PB-03 and seals | A decision on a candidate with only AF11 open; no capability is lost by waiting |
| C — defer until Forge wave 2 completes | Both candidates are measured to comparable depth first | Longest path: wave 2 covers 87 rows, 36 of them with provider-adapter gaps |

Recommendation: **B**. The remaining distance is one row. Selecting now gains nothing, because
Freeze needs the same gate anyway. Forge wave 2 continues, limited to items that change a gate, so
option C stays available.

## What the Coordinator will do next (no Owner action needed)

1. Land the `NEGATIVE_PARENT_CLASS_FALLBACK` chain (contract 1.0.26, explicit pre-checkpoint
   history; bridge turn-2 checkpoint; #592) after an independent review.
2. Re-run PB-03 on that main, seal the epoch, and re-issue this adjudication.

The Owner decision requested in #255 is the choice among A, B and C (or a direct selection).
