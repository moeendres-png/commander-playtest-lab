# WS-46 CHECKPOINT 01E — TRIGGER-VECTOR REPAIR-MATRIX BINDING

Status: `PERSISTENT / RESUMABLE / RECONCILIATION_REMEDIABLE`

## Exact rerun

The exact corrected-lineage reconciliation run advanced beyond the previous `MICRO_STATE_BASED_ACTIONS` lineage failure and exposed the next independent validator defect.

- Commander Lab head: `c58982ddad9d6c684fcc89ffb1254c561a9f3f3e`
- tree: `c8956202426df140be0a2756e07bdc977a9db06f`
- workflow: `WS46 XMage v1.0.4 Contract Reconciliation`
- run: `34064876095`
- job: `101571768701`
- conclusion: `FAIL`
- artifact ID: `9998677854`
- artifact name: `ws46-v104-reconciliation-c58982ddad9d6c684fcc89ffb1254c561a9f3f3e`
- artifact ZIP SHA-256: `d06c3fab9142736962e5c6a091da04bf78246d8d2a28b08cc7b98fc05d1dde3c`

Passing steps before the new blocker:

1. immutable WS-44 source-lock verification — PASS;
2. Python compile — PASS;
3. independent exact 107-record denominator reconstruction — PASS;
4. all requested-state digests independently recomputed equal — PASS.

The previous `MICRO_STATE_BASED_ACTIONS:card_lineage_id` failure did not recur.

## Exact new failure

`WS46_REPAIR_PATH_VALUE_MISMATCH:WS05-MP-TRIG-3:native_procedure[2]`

## Root cause from immutable WS-44 repair authority

The frozen repair-matrix row is:

- fixture: `WS05-MP-TRIG-3`
- kind: `AMBIGUOUS_MULTI_SOURCE_TO_EXACT_IDENTITY_VECTOR`
- path: `native_procedure[2]`
- old subset:
  - `source_object = "Soul Warden"`
  - `details.count = 3`
- new subset:
  - `source_objects = ["obj:soulwarden-1", "obj:soulwarden-2", "obj:soulwarden-3"]`
  - `details.count = 3`

The immutable builder `scripts/ws44_build_successor_v2.py` proves the exact precondition and transformation: it requires `step.get("source_object") == "Soul Warden"` and `step.get("details", {}).get("count") == 3`, removes the scalar `source_object`, and adds the exact three-element `source_objects` vector.

The matrix deliberately serializes the nested assertion as the flattened relative key `details.count`. The current WS-46 `contains_subset()` incorrectly treats `details.count` as a literal dictionary key, so it rejects the valid frozen nested structure before reaching provider qualification.

## Narrow remediation authority

Adjust only repair-matrix subset binding so a matrix key containing `.` is resolved as an exact relative nested dictionary path when no exact literal key exists. Preserve literal-key precedence and require every declared segment to exist. No fuzzy matching, provider inference, omitted assertion, or additional excluded field is authorized.

All immutable/digest/delta/provider-neutrality gates remain unchanged.

## Credit accounting

- reconciliation: `FAIL / REMEDIABLE`
- historical successor runtime credit: `0`
- construction: `0/107`
- behavior: `0/107`
- AF07: `NOT GRANTED`
- Architecture Freeze: `NOT GRANTED`

## Exact next action

Implement exact dotted-relative-path subset binding, rerun the exact reconciliation workflow, and inspect the resulting job and artifact before any reconciliation PASS is granted.
