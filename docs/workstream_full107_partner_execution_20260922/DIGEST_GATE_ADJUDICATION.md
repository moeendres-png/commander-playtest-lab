# Evidence-integrity gate — digest equality vs field-level correspondence (2026-09-22)

Question: does the frozen contract require frozen-hex digest equality as an
independent mandatory assertion for construction credit, or is complete
field-level correspondence the authorized evidence standard?

## Frozen text examined

- `construction_validation.credit_condition`:
  `REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST`, `digest_spec`
  `commander-lab.requested-state-digest/1.0.0`, `on_mismatch`
  `CANONICAL_SETUP_UNSUPPORTED_PROVIDER_AND_NO_RUNTIME_CREDIT`,
  `provider_must_emit_normalized_constructed_state: true`, `required: true`.
- `setup_validation`: `compare_requested_vs_constructed: true`,
  `requested_vs_normalized_native_constructed_state_equality_required:
  true`, `on_mismatch: FAIL_CLOSED`, plus the record's `normalization`
  clause (`ignored_provider_local` excluded, `retained_semantic` compared).
- Schema pins the digest as `^[0-9a-f]{64}$` only. No file in
  `qualification/ws47/` (materialization, schema, lineage, validation,
  freeze result, audits) specifies the digest preimage, field selection,
  ordering, or encoding for `commander-lab.requested-state-digest/1.0.0`.

## Determination

1. The setup_validation equality clause IS satisfied: the provider emits a
   normalized constructed state (readback canonical JSON with provider-local
   identities excluded) and compares it field-by-field against the requested
   record (multiset + scalar equality, fail closed on any mismatch).
2. Frozen-hex reproduction is NOT satisfiable: the canonicalization is
   unspecified, so no computed hex can be claimed equal to the frozen hex
   without guessing the preimage. Computing a same-named digest over a
   different canonical form would be fabrication by name collision.
3. Therefore complete field-level correspondence under the record's own
   normalization rules is the authorized satisfiable standard. Our compare
   verdicts additionally carry evidence-grade digests of both canonical
   sides (distinct namespace, never compared to the frozen hex).

## Conditions (no silent weakening)

- Mapping reasons for executed fixtures state field-level evidence only;
  no digest equality is claimed.
- Reproducing the frozen hex remains blocked on the WS47 canonicalization
  spec — a coordinator/engine-authority follow-up, recorded here.
- If a future authority mandates frozen-hex equality, all six DIRECTs
  (MULL-2/4, TAX-2/4, PARTNER-ZONE/TAX pending this workstream) revert to
  UNKNOWN/NOT_RUN until re-verified under the digest protocol. This
  conditional is explicit and applies uniformly (MULL/TAX DIRECTs already
  rest on this standard per WS1/WS2/promotion records).
