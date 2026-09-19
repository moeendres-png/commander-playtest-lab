# Step A — Source lock & nonmutating audit (2026-09-19 packet)

Machine evidence: `source_audit_A.json`, `source_audit_A2.json`, `source_audit_A3.json`
(same directory). Scripts: `/tmp/pool_audit_A.py`, `/tmp/pool_audit_A2.py`, `/tmp/pool_audit_A3.py`
(re-runnable; read-only against the out-of-repo packet).

## 1. Source lock — ALL 19 SHA-256 recomputed OK vs `SOURCE_LOCK.json`

Snapshot date 2026-09-19, date-bound (not a live Drive readback). Raw line counts
match the lock exactly: identity 1413, lots 1480, candidates 1398, knowledge 1402
(1401 data + 1 schema row), semantics 1402 (1401 + 1 schema), target_identity 1056,
target_scope 1123, target_catalog 1057, target_semantics 1057, rogshai_context 829
(828 data + 1 schema row, `record_count: 828`), target_physical 1123.

## 2. Cross-join verification (all contract starting-point numbers reproduced)

- Identity: 1413 rows = 1401 `currently_physically_owned` + 12 historical nonphysical.
  Legality: 1412 `legal`, 1 `banned` (Crusade, `commander_legal: false`, alias Kreuzzug).
- Lots: 1480 = alen_box 240 + leon_box 783 + moritz_box 451 + unknown 6.
  Lower-bound copies: boxes 285+1068+489 = **1842**; unknown **206**.
  Available LB: boxes 284+1068+489 = **1841**; unknown **205** (Vernal Fen reserved, 0).
- Candidates: 1398 rows, all `commander_legal: True`, all `legality: legal`,
  all locations box-only. Per-commander flags: RogShai 828 / Chulane 791 / Koma 556 /
  Golgari 535. Identity: 1398 = box-available (1399) minus Crusade (banned).
  Box-available excludes Gaze of Granite (1 copy fully reserved) and Vernal Fen
  (only lot is unknown/reserved) — availability derived, never from raw flags.
- Knowledge/semantics cover all 1401 physical identities; 63 verified identities have
  full semantics + knowledge (0 missing). Oracle UUID status: 63
  `MTGJSON_VERIFIED_SCRYFALL_ORACLE_ID`, 1350 explicitly unresolved (missing UUID !=
  missing Oracle text).
- RogShai context: 828 data rows, all within WUR CI, all inside candidates; the 829th
  line is a `record_type: schema` header (`record_count: 828`, quality report agrees).

## 3. Material defects confirmed (lot-level forensics, not just card-level)

- `location:unknown` lots (6): Forest 37, Island 36, Mountain 40, Plains 47, Swamp 45 —
  all `currently_available_for_own_decks: true` / `pool_status: own_available`
  (**misleading raw flags**); plus Vernal Fen 1 (reserved, available 0).
- TARGET leakage at LOT granularity: Island/Mountain/Plains/Swamp unknown lots appear
  in EACH of `TARGET_CARD_SCOPE_CURRENT.jsonl` and `TARGET_PHYSICAL_CARD_IDENTITY_CURRENT.jsonl`
  (36+40+47+45 = **168 copies**); Forest's unknown lot is absent from both targets.
  Full-Pool Candidates correctly excludes unknown lots (verified via `locations` field).
- Quality Report provenance hashes: `source_rogshai_context_sha256` (`e208ea…`) and
  `source_target_semantics_sha256` (`78877a…`) are STALE vs actual file SHAs
  (`8e3b20…`, `79017b…`); identity/physical-registry hashes match. Invariant name
  `exact_physical_identity_coverage_1338` is stale (August count; now 1401).
  Manifest `records: 1401` counts data rows (schema rows excluded) — consistent.
- Quantitative note: candidates carry 5 unknown-location *card identities* (basic
  lands) but only via their box lots — not a leak at lot granularity.

## 4. Repository baseline (August vintage — stale, frozen, not overwritten)

- `data/sync/current_sources.json`: `data_as_of 2026-08-15`; inventory/opponents point
  at `data/canonical_import/2026-08-07/`; RogShai deck photo-verified 2026-08-15.
- `data/cards/FULL_PHYSICAL_CARD_KNOWLEDGE_MANIFEST_CURRENT.json`: generated
  2026-08-20, 1338 identities / 795 RogShai context rows (vs 1401 / 828 now).
- `data/cards/oracle_subset.json`: schema 0.2.0, `data_as_of 2026-08-07`,
  `authoritative_oracle_snapshot: False`, 195 cards (README claims 161 names — stale).
- `data/cards/rogshai_semantic_projection_current.zlib.b64` + optimizer manifests +
  dated simulator results: treat as stale until rebuilt (795-base simulations cannot be
  relabeled 828).
- Stale-consumer index: see `STALE_CONSUMER_INDEX.md`. No historical file was modified.

## 5. Step A verdict

Source lock PASS (19/19 SHAs, counts, cross-joins, defect forensics all reproduced).
Snapshot status: `DATE_BOUND_SNAPSHOT` (offline packet, no live Drive readback).
