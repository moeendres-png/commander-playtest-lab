# Step B — Oracle facts, locale, printing, semantics (2026-09-19)

Method: dated batch join of lot `printing_ref` (SET#NUM[|finish|lang]) against
`api.scryfall.com/cards/collection` + single-card fallback. Guards: exact
set+number (+lang where available); Scryfall name must equal the lot oracle name
or exactly one `//`-separated face; multi-hit and name-mismatch printings stay
UNKNOWN. Oracle UUIDs are never inferred from bare names.
Machine evidence: `/tmp/pool_scryfall_join_2026-09-19.json` (outside repo —
contains third-party response payloads; keyed by printing triple, no inventory
semantics beyond refs already in the packet).

- Fetched 2026-09-19T20:07Z; batch retry 20:27Z; face/number recovery 20:28Z (UTC).
- 1,455 unique printing triples from 1,466 parseable lot refs (14 unparseable/custom).

## Lot coverage (1,480 lots)

| Status | Lots | Meaning |
|---|---|---|
| VERIFIED | 1239 | exact set+number+lang+name |
| VERIFIED_FACE_MATCH | 5 | 5 SOS prepare DFCs, front-face name exact |
| VERIFIED_NUMBER_VARIANT | 1 | CMR#194/361 → CMR 194 Portent of Betrayal (`/361` annotation flagged) |
| VERIFIED_ORACLE_ID_LANG_MISMATCH | 23 | oracle_id verified, requested lang absent (locale UNKNOWN) |
| VERIFIED_ORACLE_ID_LANG_RELAXED | 193 | oracle_id verified without lang constraint (locale UNKNOWN) |
| UNKNOWN | 5 | XMH2#381, SCH#189, XDMC#68de, XCMR#456, XCMR#472 (custom codes, not on Scryfall) + J25#115de |
| UNPARSEABLE_REF | 14 | `unknown`/custom refs incl. all 6 unknown-location lots |

## Identity coverage (1,401 physical identities)

- **1,394 resolve to exactly one oracle_id, 0 conflicting identities.**
- 7 identities have no verified lot (custom-code printings only) → UNKNOWN retained.
- The 63 registry-verified UUIDs agree 63/63 with the join (5 SOS cards confirmed
  via face-match recovery — no contradiction anywhere).
- German-locale printings: oracle identity verified via en fallback where applicable,
  but **locale/printing stays UNKNOWN** without exact-lang confirmation (≈30 cases
  class). Finish variants (`finish_unknown`) likewise retained as uncertain.
- Legality re-check (Scryfall `legalities.commander` on verified printings): no
  conflict with registry `legality_status` except the known Crusade ban (registry
  already `banned`). Full per-printing legality diff is in the cache file.

## Semantics note

Structural roles/taxonomy were NOT re-derived: 1,358 role-bearing + 13 explicitly
roleless + review queue per Quality Report; parsing is not behavior (see Step D).
The join supplies oracle identity only — no executable coverage is claimed from it.
