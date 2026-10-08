# Coordinator adjudication — provider readiness (issue #255)

Decision document for the Owner. It adjudicates the section-F evidence; it does **not** select a
provider. `PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` ·
`PRODUCTION_REPOSITORY = NOT_CREATED`. Production Provider selection is Owner-only (AGENTS.md §8).

## Source lock

- Sealed epoch `qualification/current-boundary-epochs/b1c8f54a999a-2d13b953a82c/` (#593),
  contract `commander-lab.full107/1.0.22-successor`, pins XMage `b479fe74`, Forge Rules-Core
  `bb0a740d`, Forge bridge `31cbae12` — all IDENTICAL to the sealed evidence (no drift).
- Section-F packet: `docs/provider_readiness_packet_20261007/PROVIDER_READINESS.{json,md}` (#597),
  independently reviewed on #596 (no P0/P1); both P2 findings and three P3 notes fixed in #597.

## AF gate state (sealed)

| Gate | XMage | Forge |
| --- | --- | --- |
| AF00 / AF01 / AF02 / AF03 / AF10 | PASS | PASS |
| AF05 hidden information | PASS | UNKNOWN (20 hidden rows unexecuted: HIDDEN_01–19 and the honeycard sentinel) |
| AF07 actual-card corpus | PASS | UNKNOWN (CARD_02; 29 identities unexecuted) |
| AF09 Rules RNG / semantic replay | PASS | UNKNOWN (5 replay rows) |
| AF06 general rules correctness | UNKNOWN — 105/107 PASS, 0 BLOCKED | UNKNOWN — 20/107 PASS, 33 BLOCKED |
| AF08 commander / multiplayer | UNKNOWN — 1 row (`WS05-CMD-MULL-2`) | UNKNOWN — 21 rows |
| AF04 decision boundary | UNKNOWN | UNKNOWN |
| AF11 interop / licence topology | UNKNOWN | UNKNOWN |

Neither candidate passes AF00–AF11. Neither is freeze-ready.

## Findings

1. **No Rules divergence is established.** All 107 comparison rows are `NON_COMPARABLE`
   (0 `SAME_SEMANTICS`, 0 adjudicated differences). The evidence ranks *measured coverage*, not
   demonstrated Rules quality. Forge's gap is not evidence that Forge is Rules-worse.
2. **Forge's gap is dominated by unexecuted work, not engine defects.** Of 87 non-PASS Forge rows:
   grouped by the leading clause of `failure_reason`, 54 are fixtures corrected by the successor
   contract and not yet re-executed on Forge, 23 are `LAB_EXECUTION_GAP` (21 at construction,
   2 at execution), 5 `PROVIDER_ADAPTER_GAP`, 1 `CONTRACT_AUTHORITY_GAP`, 2 missing per-shortcut
   negatives, 1 London bottom (MULL-2) and 1 without a current-boundary execution path. Counted
   across all recorded missing mechanisms, however, **36 rows name a `PROVIDER_ADAPTER_GAP`** (for
   example the pinned bridge exports no event log, or the readback lacks the card owner), 31 of
   them among the 54 corrected rows. Forge therefore carries real provider-side work, not only
   Lab execution. Wave 2 (#592) owns these rows.
3. **XMage is two rows from AF06 and one row from AF08.**
   - `WS05-CMD-MULL-2`: the generic Protocol2 lane has no London-bottom decision (#595 finding);
     the bridge projection is in progress (#592). The Lab never chooses the card.
   - `NEGATIVE_PARENT_CLASS_FALLBACK`: the runner lacked an execution seam for this negative.
     Building it (#601, #605, #606) showed that the 1.0.22/1.0.23 record itself is unreachable:
     it puts P2's sorcery Syphon Mind on the stack in turn 1 while P1 is active, which CR 307.1
     forbids. The bridge now refuses that state fail-closed (`UNSUPPORTED_RESUME_TIMING`, #606).
     Contract erratum 1.0.24 (#607) corrects the record: turn 2, P2 active, cast from hand, a
     paid cost, and P3/P4 with empty hands (CR 101.4). The corrected record still needs bridge
     support for qualified checkpoints after turn 1. Until then the row stays UNKNOWN. This is
     Lab/bridge work, not an engine capability question.
4. **AF04 is open for both for one recorded reason: the bounded 6P run.** On 2P–5P every frame
   is clean and `contradictions` is empty (XMage answers MULLIGAN and PRIORITY externally, Forge
   additionally STARTING_PLAYER). The only recorded gaps are the three 6P gaps: the 6P record
   declares no starting seat, XMage's create channel requires one and Forge offers a
   STARTING_PLAYER decision, and the Lab supplies no seat default, so the run stops before any frame or priority decision
   (`src/commander_lab/qualification/current_boundary/decision_boundary.py` turns any
   bounded-secondary gap into UNKNOWN). Closing AF04 needs an authoritative starting seat in the
   6P record (a contract erratum of the START-2 kind), which is Coordinator qualification design,
   not an Owner ruling (`owner_ruling` R-2 is already verified for both candidates). Broader
   decision-class coverage would be a separate, new qualification requirement and is not what
   keeps AF04 open today.
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

On the sealed evidence, **XMage is the evidence-leading candidate** (8/12 AF gates PASS versus
5/12; 105/107 versus 20/107 FULL107 rows). Its open AF06 and AF08 gates are closable by bounded
Lab and bridge work, AF04 by a 6P record erratum; AF11 can only be adjudicated after a selection. This is an assessment of measured readiness, not a selection and not a Rules verdict
against Forge.

## Options for the Owner

| Option | What it means | Consequence |
| --- | --- | --- |
| A — select now | Owner selects a provider on current evidence | Freeze still requires AF04/AF06/AF08 and the post-selection AF11 adjudication |
| B — defer until XMage closes AF04/AF06/AF08 (Coordinator-recommended) | No selection yet; Coordinator drives MULL-2, the parent-class negative and the 6P starting-seat erratum, then re-seals | A decision on a candidate with only AF11 open; no capability is lost by waiting |
| C — defer until Forge wave 2 completes | Both candidates measured to comparable depth first | Longest path; wave 2 is 87 rows |

Recommendation: **B**. Selecting now gains nothing, because Freeze needs the same gates anyway, and
B gives the Owner a decision against a candidate with no open qualification gate other than the
topology adjudication that only a selection can enable. Forge wave 2 continues bounded to items that
change a gate, so option C stays available without blocking B.

## What the Coordinator will do next (no Owner action needed)

1. Land the XMage generic-lane London-bottom projection and the Lab answer path (#592), then re-run
   PB-03 and seal.
2. Qualify turn-2 resume checkpoints in the XMage bridge so the corrected
   `NEGATIVE_PARENT_CLASS_FALLBACK` record (1.0.24) can run.
3. Issue a contract erratum giving the bounded 6P record an authoritative starting seat (AF04, both
   candidates), executed through the existing starting-player channels (#574).
4. Re-issue this adjudication against the new epoch.

The Owner decision requested in #255 is the choice among A, B and C (or a direct selection).
