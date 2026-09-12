# WS72 Final Report — Cross-Candidate Actual-Card Availability Preflight

## Objective

Determine, mechanically and reproducibly, whether every actual card required
by the RQ-C3 scenario population is present/resolvable in the exact accepted
Forge and XMage candidate pins. Preflight only — zero behavior credit.

## Work completed

1. Resolved both exact candidate pins in existing local repositories using
   read-only object operations (no new checkout/clone/worktree; both engine
   trees verified clean afterwards). Pin/tree/remote all match the contract
   and are corroborated by WS65 (Forge) and WS56 (XMage) qualification evidence.
2. Derived the defined scenario population from exact RQ-C3 authority:
   40 unique scenarios (RQ-C1 A01–K02 with the 18 RQ-C3 corrected overlays
   preferred; 15 first-wave + 25 non-first-wave).
3. Extracted 55 unique actual cards with authority names, oracle IDs where
   authority supplies them (47/55; 8 state-only cards such as basic lands
   carry no authority oracle ID and none was invented), per-scenario roles,
   and state zones. One non-card placeholder
   (`Noncreature Spell (noncreature nonland)`, RQ-C3-F02 hand) excluded with reason.
4. Ran exact-pin lookups for all 55 cards in both engines
   (`ws72_card_preflight.py`, deterministic, rerun byte-identical).
5. Produced scenario matrix, missing-card clusters, and availability summary.

## Results (defined corpus; CODE_DERIVED; NOT behavior)

- Unique actual cards (defined corpus): **55**
- Forge: **FOUND 55 / NOT_FOUND 0 / AMBIGUOUS 0 / UNKNOWN 0**
- XMage: **FOUND 55 / NOT_FOUND 0 / AMBIGUOUS 0 / UNKNOWN 0**
  (XMage FOUND = REGISTERED_OR_RESOLVABLE: SetCardInfo + impl class both present;
  7 cards carry class-name normalization notes, e.g. `Rest in Peace` →
  `mage.cards.r.RestInPeace`.)
- First-wave 15 scenarios with complete card corpus found: **Forge 15/15, XMage 15/15**
- Defined non-first-wave 25 scenarios with complete card corpus found:
  **Forge 25/25, XMage 25/25**
- Missing-card clusters: **none** (empty; no card-name hacks applied).
- Independent cross-checks: all 55 corpus names present in the Forge
  cardsfolder `^Name:` census (34,613 lines); every XMage impl traces to a
  set-file class reference (zero guess-only resolutions); both engines'
  per-card evidence verified single-impl, registered.

## Population gap (source blocker, not a failure of lookup)

- RQ-C3 authority enumerates 40 unique scenarios. No authority artifact
  enumerates 107 scenarios or the "remaining 92" (verified by exhaustive
  `git grep`/`ls-tree` over the authority tree and post-authority refs
  available in-repo; WS71 has no commits yet).
- Therefore: `FORGE_REMAINING92_ALL_CARDS_FOUND=UNKNOWN/92`,
  `XMAGE_REMAINING92_ALL_CARDS_FOUND=UNKNOWN/92`.
  The 67 Full107-minus-40 slots are `AUTHORITY_ABSENT`, classified UNKNOWN
  per the hard gate. Nothing was invented to fill them.

## Verdict

- `WS72_CARD_PREFLIGHT=PARTIAL` — complete ALL_FOUND preflight for the
  authority-defined 40-scenario / 55-card corpus in both exact pins;
  Full107-level preflight blocked on the undefined 67 slots.
- No scenario is called READY: card presence says only that behavior execution
  is mechanically worth attempting for the defined corpus.

## Handoff numbers

- `FULL107_UNIQUE_ACTUAL_CARDS=55` (defined corpus; 67 Full107 slots AUTHORITY_ABSENT)
- `FORGE_FOUND=55` `FORGE_NOT_FOUND=0` `FORGE_AMBIGUOUS=0` `FORGE_UNKNOWN=0`
- `XMAGE_FOUND=55` `XMAGE_NOT_FOUND=0` `XMAGE_AMBIGUOUS=0` `XMAGE_UNKNOWN=0`
- `FORGE_REMAINING92_ALL_CARDS_FOUND=UNKNOWN/92`
- `XMAGE_REMAINING92_ALL_CARDS_FOUND=UNKNOWN/92`
- `BEHAVIOR_CREDIT=0/107` `FULL107=NOT_RUN`
  `ARCHITECTURE_FREEZE=NOT_CLAIMED` `PRODUCTION_PROVIDER=NOT_SELECTED`

## Outputs (all under `candidate-qualification/ws72-cross-candidate-card-availability-preflight/`)

`ws72_card_preflight.py`, `WS72_SOURCE_LOCK.md`,
`WS72_ACTUAL_CARD_CORPUS.json`, `WS72_FORGE_CARD_PREFLIGHT.json`,
`WS72_XMAGE_CARD_PREFLIGHT.json`, `WS72_SCENARIO_CARD_MATRIX.json`,
`WS72_MISSING_CARD_CLUSTERS.json`, `WS72_CARD_AVAILABILITY_SUMMARY.json`,
`WS72_FINAL_REPORT.md`, `WORKSTREAM_STATE.yaml`.

## Exact next action

Coordinator decision required on the Full107 population gap: either (a) point
WS72 at the authority artifact enumerating the remaining 92 scenarios, after
which `ws72_card_preflight.py` extends mechanically; or (b) accept PARTIAL
scoped to the authority-defined 40 and let WS71 define/clear the 92.
