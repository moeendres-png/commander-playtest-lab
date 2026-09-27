# Hidden-Information Comparison — XMage vs Forge (FINAL-PROVIDER-CDQ-20260927)

## Method

Principal-scoped comparison only. No harness exposes hidden state to simplify
comparison. Per-fixture dispositions live in
`COMMON_FIXTURE_NORMALIZATION.json` (all 101 common fixtures NON_COMPARABLE
pending Forge packet ingest); this note records the dimension-level evidence.

Engine-local non-comparable fields (excluded from all semantic comparison):
UUIDs, object IDs, revision counters, internal option IDs, engine-specific
event IDs, internal serialization details.

## XMage evidence (reconciled authority `59332671…`)

- L7 hidden/replay integration 9/9: lossless complete-library restore,
  explicit typed single face-down restore, native Mage RG-06A mutation
  ownership, ambiguous old frozen records fail closed, sole principal-scoped
  redactor hardened for restored hidden identities, public/private actor-hash
  separation, transcripts omit private actor-state references, public and
  principal views proven non-oracles for opponent hidden library order /
  face-down identity, same-seed public semantic replay.
- 6-path prevalidation atomicity battery: all rejections prove zero mutation.
- `XmageFullGameHiddenInformationTest.java` + HIDDEN_INFORMATION_BOUNDARY_REPORT
  (supporting only at fixture level — see Gate B: all 20 HIDDEN_* rows stay
  UNKNOWN because no per-scenario exact rerun exists for each fixture's
  actor/principal, zone-movement, invalidation, and replay-boundary semantics).
- Readiness dimension `hidden_information`: TECHNICALLY_CONFORMANT (mechanism
  qualified; per-fixture exact runs absent).

## Forge evidence (ingested WSR20, tip `18bba95a…`)

- `HIDDEN_INFO_RESULTS.json`: 13 DIRECTLY_VERIFIED / 2 TECHNICALLY_CONFORMANT
  / 2 NOT_RUN_BLOCKED / 3 UNKNOWN (= 20). Method: live principal-scoped
  observation asserts across BridgeEngineTest, WsR15HiddenInfoFamilyTest,
  WsR16SixPlayerFamilyTest, WS216GapClosureTest, WS227 replay principal
  scoping, WS233 lifecycles, R20 reveal/exile/scry tests, wsc2a hidden-info
  opening/extended.
- Proven: no opponent library-order leak, no face-down identity leak, no
  private hash in public transcript (state_hash null to outsiders);
  permission inference confined to engine authority.
- HIDDEN_13 TC (pile-label channel residual: dedicated label audit);
  HIDDEN_19 TC (no direct omniscient-API-block test).
- Coordinator-listed residual seams, preserved explicitly (§14, remediation
  NOT authorized here):
  - HIDDEN_05 UNKNOWN — face-down exile permission persistence → STILL_UNKNOWN_FOR_READINESS
  - HIDDEN_06 UNKNOWN — face-down exile invalidation on zone change → STILL_UNKNOWN_FOR_READINESS
  - HIDDEN_11 UNKNOWN — shuffle/order-knowledge invalidation → STILL_UNKNOWN_FOR_READINESS
  - HIDDEN_08 NOT_RUN_BLOCKED — look-audience seam → STILL_UNKNOWN_FOR_READINESS
    (Forge seam missing and XMage exact evidence missing)
  - HIDDEN_12 NOT_RUN_BLOCKED — controlled-player decision seam → STILL_UNKNOWN_FOR_READINESS
- Readiness dimension `hidden_information`: Forge TECHNICALLY_CONFORMANT.

## Per-fixture hidden-info record (common set)

For every hidden-information fixture in the common set
(HIDDEN_01/02/03/04/07/09/10/13/14/15/16/17/18/19, HIDDEN_HONEYCARD_SENTINEL):

| Field | Status |
|---|---|
| actor/principal | denominator-bound (P1 viewer); engine proof pending both sides |
| authorized knowledge | XMage: generic redactor proof; exact per-fixture proof absent |
| unauthorized principals | XMage: non-oracle proofs (generic); Forge: UNKNOWN |
| public representation | comparable only after ingest (byte equality excluded for engine-local IDs) |
| private representation | principal-scoped; never compared across principals |
| zone-movement survival/invalidation | XMage UNKNOWN at fixture level; Forge HIDDEN_05/06/11 UNKNOWN (excluded seams, still unknown for readiness) |
| replay knowledge boundary | XMage generic same-seed public replay; Forge exactly-once twins + coordinates; fixture-level replay-boundary UNKNOWN on XMage |

## Leakage policy

No downgrade: any future observed leakage is a Rules-visibility failure, not
a cosmetic mismatch. Honeycard sentinel fixture
(HIDDEN_HONEYCARD_SENTINEL) stays UNKNOWN on both sides until a live
forbidden-sentinel scan runs fixture-correspondingly.
