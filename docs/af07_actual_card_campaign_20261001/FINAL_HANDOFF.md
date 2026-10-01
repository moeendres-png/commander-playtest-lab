# AF07 actual-card campaign — final handoff (Phase 1)

Workstream `AF07-ACTUAL-CARD-CAMPAIGN-20261001`, issue #453, parent #255,
concurrency ruling #255 comment 5936731960.

## Source Lock

- Lab `main`: `bcd903f20d511c4aad0a8ebfbfbe89d801219ec9` (tree
  `b7d44a0b49222fde62157a6a18867b34b6a39552`).
- Workstream branch: `hardening/af07-actual-card-campaign-20261001`.
- Runner identity of the recorded run: commit
  `bd65a2ffa19b4c8cd9538aa79fa2280d7f278356`, clean tree, digest in
  `artifacts/CAMPAIGN_IDENTITY.json`.
- XMage candidate `37e4df6c914f1e189e24f0ef59fa91734c922436`; provider-reported
  loaded artifact `mage-1.4.61.jar` sha256
  `e04062d2e180c8e322256bd92675c5cd49d73f5f6894140e5a86e45764661603`.
- Forge Rules-Core `bb0a740d2bef725194798383c2452213ecdd0b37`, Forge bridge
  `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (not executed in this phase).
- Effective contract `commander-lab.full107/1.0.8-successor`; matrix digest
  `e8afffa31783c482444bbb3befc5624ca070dad3c3358e495724661defc6ab56`.

## Work Completed

1. Ownership/drift census at `bf6323be`: #450 (draft, `1e9619a1`) and #452
   (`ca92a2e8`) both active; all Phase-1 AF07 surfaces verified new and disjoint.
2. Dedicated producer `actual_card_campaign.py`:
   - derives the 29 identities from `ACTUAL_CARD_DOMAIN_v1.json` and the
     fixture→identity bijection from `COMMON_FIXTURE_MANIFEST_v1.json`, failing
     closed on any drift;
   - loads every effective CARD record through the canonical successor resolver
     and binds requested-state/obligation digests;
   - derives per-row starting-state dimensions, executor requirements and the
     credit route (effective denominator vs frozen exclusion) from source;
   - executes rows through the production midgame lane with engine-authored
     decisions only, using the generic production executor read-only;
   - `DIRECT_PASS` requires an obligation plan covering exactly the record's
     postconditions, every proof held on engine tape/observation, construction
     accepted, and the engine build equal to the canonical pin.
3. Isolated runner `scripts/run_actual_card_campaign.py`: run-scoped
   `ENGINE_RUNTIME_DIRECTORY`, one engine process per row, this worktree's
   `engine-bridge` build only, runner-bound positive receipts, machine-readable
   29-row matrix.
4. 32 engine-free adversarial tests (derivation, plan staleness, verdict coupling,
   receipt credit/stale-digest control, matrix integrity).
5. Full 29-row execution recorded; artifacts committed under
   `docs/af07_actual_card_campaign_20261001/artifacts/`.

## Per-card Matrix

The authoritative matrix is
`artifacts/AF07_ACTUAL_CARD_MATRIX.json` (schema
`commander-lab.af07-actual-card-campaign-matrix/1.0.0`). Summary:

- **DIRECT_PASS (2)**: CARD_02, CARD_24 — fresh current-boundary runtime,
  runner-bound positive receipts, engine build at the canonical pin.
- **DEPENDENCY_WAITING (16)**: CARD_01, 03, 04, 05, 06, 08, 11, 13, 14, 17, 18,
  19, 20, 21, 23, 26 — first blocker on an active foreign writer's surface
  (`midgame_rows.py` / `run_midgame_capability_probe.py`: PR #450;
  `qualification/pre-freeze-successor/`: PR #452).
- **PROVIDER_ADAPTER_DEFECT (11)**: CARD_07, 09, 10, 12, 15, 16, 22, 25, 27, 28,
  29 — the engine refused the requested state and named `stack`, frozen partial
  `library` identity, or counters; the record requires that dimension and the
  bridge's own manifest lists it unsupported.
- **UNKNOWN (0)** — every blocked row has a live engine observation.

## New Findings

- The effective provider denominator contains only `CARD_02` of the 29 CARD
  fixtures; `WS47_PROVIDER_DENOMINATOR_107.json` explicitly excludes the other 28.
  AF07 credit for them requires both direct execution and a denominator/receipt
  route, which is a Phase-2 integration act.
- The production midgame lane already reaches more rows than the denominator
  suggests: CARD_02 and CARD_24 fully verify today; eleven rows fail at the
  restoration dimension, and the engine names the exact dimension in every case.
- Sixteen rows stop inside the qualification executor or the fixture contract:
  scripted actions (`announce_cast`, `cast_fused`, `activate`), unscripted
  decision frames (`target`, `choose_object`, `choice`), a combat arrival the
  probe does not traverse, and two causal-entry rows (CARD_13, CARD_20) whose
  position is causally reachable but whose obligation driver is not integrated.
- The `mage-1.4.61.jar` loaded-artifact digest is now recorded per run, so a
  future re-run can prove which engine bytes executed rather than trusting the
  pin constant.

## Changes

- `src/commander_lab/qualification/current_boundary/actual_card_campaign.py` (new)
- `scripts/run_actual_card_campaign.py` (new)
- `tests/qualification/test_actual_card_campaign.py` (new)
- `docs/af07_actual_card_campaign_20261001/**` (new)
- `.foundry/af07-actual-card-campaign-20261001.yaml` (state)

No foreign-owned file was modified. `midgame_rows.py`,
`run_midgame_capability_probe.py`, `knowledge_projection.py`, `source_lock.py`,
the successor contract, the current-boundary runner/assembler and the global SHA
manifests are untouched.

## Tests / Evidence

- `pytest tests/qualification/test_actual_card_campaign.py` — 32 passed
  (`DIRECTLY_VERIFIED`, engine-free).
- `ruff check` and `ruff format --check` on all new files — clean
  (`DIRECTLY_VERIFIED`).
- 29 live row executions — `FRESH_CURRENT_BOUNDARY_RUNTIME`; raw engine
  per-row documents in `artifacts/measurements/`, receipts for the two direct
  passes, matrix in `artifacts/AF07_ACTUAL_CARD_MATRIX.json`.
- No native `XmageActualCardCorpusTest` credit was used or promoted
  (`SUPPORTING ONLY`, not consulted).
- No external CR/Oracle/Rulings evidence was needed for these classifications;
  none is claimed.

## PASS / FAIL / UNKNOWN

- Per-row: 2 PASS (CARD_02, CARD_24), 0 FAIL, 27 BLOCKED with terminal
  classification, 0 UNKNOWN.
- **AF07 overall: UNKNOWN** — 27 of 29 mandatory identities are not directly
  proven at the current boundary, and 28 have no effective denominator row.

## Dependencies Waiting

- **PR #450** (`midgame_rows.py`, `run_midgame_capability_probe.py`): executor
  support for `announce_cast` / `cast_fused` / `activate` priority actions,
  declaration-class handling, combat arrival traversal to the record's
  checkpoint, and integration of the declared causal entries (CARD_13, CARD_20).
- **PR #452** (successor contract): records that do not script the discretionary
  frames the engine requires (`target`, `choose_object`, `choice`) for CARD_01,
  04, 05, 06, 14, 17, 18, 23, 26.

## Remaining Blockers

- Bridge restoration dimensions for `stack` objects, frozen partial `library`
  identity, and counters/tapped state (11 rows).
- Denominator/receipt integration for CARD rows so direct passes can earn AF07
  credit on the freed surfaces (Phase 2).
- AF07 overall cannot be COMPLETE until every identity is directly proven or
  terminally classified and the credit route exists; today every non-PASS row is
  terminally classified, but the two directly proven rows are not yet on the
  effective denominator.

## Outputs

- `docs/af07_actual_card_campaign_20261001/README.md` and this handoff.
- `docs/af07_actual_card_campaign_20261001/artifacts/` (matrix, identity,
  29 measurements, 2 receipts).
- Draft PR on `hardening/af07-actual-card-campaign-20261001`.

## Dependencies Unblocked

- CARD_02 and CARD_24 direct evidence is available for the Phase-2 assembler.
- Phase 2 can re-adjudicate each blocked row from its recorded mechanism without
  re-running the whole corpus.

## Exact Next Action

Keep the Draft PR open while #450 and #452 remain active. When both are terminal:
fresh-fetch `main`, impact-adjudicate their exact merged bytes, rebuild the
foreign-owner map, re-run every row whose record/executor/dimension changed, and
integrate the freed shared qualification surfaces to place the CARD rows on the
effective denominator and consume the positive receipts — without overwriting
historical epochs.

---

`AF07_ACTUAL_CARD_CAMPAIGN = PARTIAL`
`PRODUCTION_PROVIDER = NOT_SELECTED`
`ARCHITECTURE_FREEZE = NOT_CLAIMED`
`SAFE_TO_CLOSE_SESSION = YES`
