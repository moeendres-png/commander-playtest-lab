# Digest trace + recoverability record (2026-09-22)

## Leads examined

1. Imported subset `qualification/ws47/`: materialization (digests only),
   schema (digest = 64-hex pattern), lineage (predecessor digests), freeze
   result, validation, audits — no canonicalization algorithm. This scoping
   gap produced the earlier "unavailable" conclusion.
2. Frozen branch `origin/ws47/successor-contract-v1.0.5-freeze` full tree
   (1655 files): `qualification/ws32/REQUESTED_STATE_DIGEST_SPEC_v1_0_2.json`
   carries the exact spec — SHA-256 over UTF-8 bytes of canonical JSON
   (`ensure_ascii=false`, separators `,/:`, `sort_keys=true`) of the record
   projected to 15 named keys with absent keys omitted; gate
   `requested_state_digest == normalized_constructed_state_digest`.
3. Frozen history: digest lineage rows (predecessor digests stable where
   requested state unchanged) corroborate deterministic canonicalization.

## Recoverability verdict: RECOVERED without guessing

A Python reimplementation of the spec reproduces **135/135** frozen digests
(first omission-rule variant tested; the alternative scores 0/135).
Preimage resistance makes coincidence impossible: the algorithm +
preimage rule (omit absent keys) are exactly recovered. The earlier
field-level adjudication was therefore an incomplete reading of the
frozen contract, now superseded — the credit condition IS satisfiable.

## Implementation (this workstream)

- `XmageNativeStateRestoration`: spec-faithful canonicalizer
  (`canonicalJson`), `projectRecord`, `requestedDigest`,
  `constructedDigest`, plus `enumerateCommanderCastCost` support already
  merged. Java canonicalizer proven byte-identical to the Python
  reimplementation on sample records.
- `XmageDigestCreditTest` (9 tests): canonicalizer reproduces all 135
  frozen hexes; all six DIRECT fixtures' live constructed states digest to
  their frozen hexes (MULL pre-start+mulligan reads; NATIVE post-arrival
  reads); tampered-projection and modified-record negatives.
- Mapping: all six DIRECT reasons now claim digest equality (verified
  locally; CI proof from this PR's conformance lane at merge time).
- Guard: DIRECT reasons must contain the digest marker (anti-silent-
  replacement), alongside the register-EXACT and executed-subset rules.

## Per-key provenance (constructed projection)

Natively read: turn/life/lost/left/poison/library/hand counts, command-zone
and battlefield/graveyard/exile identities, cast counts, active/priority,
seed + explicit flag, stack emptiness, extra-turn absence, zone arithmetic.
Engine-enforced at import: deck/commander bindings, partner legality.
Harness inputs (asserted, documented): mode, starting life/seat, seed chain
(manifest → session arg → engine readback), pregame regime markers.
Descriptor mirrors with machine-checked bounds: knowledge (empty
permissions asserted + reveal-free script/card bounds), rules_randomness
(seed proven separately), setup_validation (implementation conformance),
partner relations (referential asserts, Partner-only or fail closed).
Commander damage matrices: empty by pre-combat temporal envelope
(CR 903.10 — commander damage only from combat damage; no combat reached).

## Residual

None on the digest gate: all six DIRECTs satisfy frozen-hex equality from
live runs. The uniform conditional stands for the future: any engine, pin,
contract, harness, or semantic change re-opens impact adjudication and
required requalification per AGENTS.md §4.
