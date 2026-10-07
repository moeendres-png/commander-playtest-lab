# Coordinator adjudication — provider readiness (issue #255)

Decision document for the Owner. It adjudicates the section-F evidence; it does **not** select a
provider. `PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` ·
`PRODUCTION_REPOSITORY = NOT_CREATED`. Production Provider selection is Owner-only (AGENTS.md §8).

## Source lock

- Sealed epoch `qualification/current-boundary-epochs/b1c8f54a999a-2d13b953a82c/` (#593),
  contract `commander-lab.full107/1.0.22-successor`, pins XMage `b479fe74`, Forge Rules-Core
  `bb0a740d`, Forge bridge `31cbae12` — all IDENTICAL to the sealed evidence (no drift).
- Section-F packet: `docs/provider_readiness_packet_20261007/PROVIDER_READINESS.{json,md}` (#597),
  independently reviewed (no P0/P1; both P2 findings fixed in #597).

## AF gate state (sealed)

| Gate | XMage | Forge |
| --- | --- | --- |
| AF00 / AF01 / AF02 / AF03 / AF10 | PASS | PASS |
| AF05 hidden information | PASS | UNKNOWN (19 HIDDEN rows unexecuted) |
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
   54 are fixtures corrected by the successor contract and not yet re-executed on Forge, 23 are
   `LAB_EXECUTION_GAP` (the Lab cannot yet construct the scenario), 5 `PROVIDER_ADAPTER_GAP`,
   1 `CONTRACT_AUTHORITY_GAP`, 2 missing per-shortcut negatives, 1 London bottom (MULL-2) and
   1 without a current-boundary execution path. Wave 2 (#592) owns them.
3. **XMage is two rows from AF06 and one row from AF08.**
   - `WS05-CMD-MULL-2`: the generic Protocol2 lane has no London-bottom decision (#595 finding);
     the bridge projection is in progress (#592). The Lab never chooses the card.
   - `NEGATIVE_PARENT_CLASS_FALLBACK`: the runner lacks the per-shortcut negative control; this is
     Lab work, not an engine capability question.
4. **AF04 is open for both** because the decision boundary is measured only for the decision
   classes the 2P–5P rows actually reach (XMage: MULLIGAN, PRIORITY; Forge: additionally
   STARTING_PLAYER), and the 6P runs stop at the record's missing starting seat (a record-authority
   gap; the Lab supplies no seat default). Closing AF04 needs broader externally answered decision
   classes on the 2P–5P rows, not an Owner ruling.
5. **AF11 cannot be adjudicated to PASS now.** The observed qualification topology is
   separate-process for both candidates, but the catalog obligation binds the *actual production
   integration topology* ("Forge remains a genuine separate process/service"; single-provider
   adapter serving exactly the selected candidate). That topology does not exist before selection,
   and the D17 in-JVM residual risk is **not accepted**. AF11 stays `UNKNOWN`; it is re-adjudicated
   against the production topology after the Owner's selection. Recorded licence metadata
   (XMage MIT, Forge GPL-3.0) is not a legal conclusion.

## Coordinator assessment

On the sealed evidence, **XMage is the evidence-leading candidate** (8/12 AF gates PASS versus
5/12; 105/107 versus 20/107 FULL107 rows). Its remaining gates are closable by bounded Lab and
bridge work. This is an assessment of measured readiness, not a selection and not a Rules verdict
against Forge.

## Options for the Owner

| Option | What it means | Consequence |
| --- | --- | --- |
| A — select now | Owner selects a provider on current evidence | Freeze still requires AF04/AF06/AF08 and the post-selection AF11 adjudication |
| B — defer until XMage closes AF04/AF06/AF08 (Coordinator-recommended) | No selection yet; Coordinator drives MULL-2, the parent-class negative and AF04 decision-class coverage, then re-seals | A decision on a candidate with only AF11 open; no capability is lost by waiting |
| C — defer until Forge wave 2 completes | Both candidates measured to comparable depth first | Longest path; wave 2 is 87 rows |

Recommendation: **B**. Selecting now gains nothing, because Freeze needs the same gates anyway, and
B gives the Owner a decision against a candidate with no open qualification gate other than the
topology adjudication that only a selection can enable. Forge wave 2 continues bounded to items that
change a gate, so option C stays available without blocking B.

## What the Coordinator will do next (no Owner action needed)

1. Land the XMage generic-lane London-bottom projection and the Lab answer path (#592), then re-run
   PB-03 and seal.
2. Implement the per-shortcut negative for `NEGATIVE_PARENT_CLASS_FALLBACK`.
3. Extend externally answered decision classes on the 2P–5P rows for AF04 (both candidates).
4. Re-issue this adjudication against the new epoch.

The Owner decision requested in #255 is the choice among A, B and C (or a direct selection).
