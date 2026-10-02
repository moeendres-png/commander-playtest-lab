# AF07 actual-card campaign — final handoff (Phase 1, post-#452 re-run)

Workstream `AF07-ACTUAL-CARD-CAMPAIGN-20261001`, issue #453, parent #255,
concurrency ruling #255 comment 5936731960.

## Source Lock

- Lab `main`: `6ae06efcdd2a894596d4c48d14b32632a6950c60` (tree
  `366a73100045a8ada93dfacf53c428968305a13a`), after #452 and #460 merged.
- Workstream branch: `hardening/af07-actual-card-campaign-20261001` (main merged).
- Runner identity of the recorded run: commit
  `0b61ab80a30638a4fda229d5be77a56c302017af`, clean tree; digest in
  `artifacts/CAMPAIGN_IDENTITY.json`.
- Effective contract `commander-lab.full107/1.0.10-successor`.
- XMage candidate `37e4df6c914f1e189e24f0ef59fa91734c922436`; provider-reported
  loaded artifact `mage-1.4.61.jar` sha256
  `e04062d2e180c8e322256bd92675c5cd49d73f5f6894140e5a86e45764661603`.
- Forge Rules-Core `bb0a740d2bef725194798383c2452213ecdd0b37`, Forge bridge
  `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (not executed in this phase).
- Matrix digest `3bbc18ce455812309ff6e0d15dcda195a392af305db7938550c4ab086987300e`.

## Work Completed

1. Ownership/drift census at `bf6323be`: #450 (draft) and #452 active; all
   Phase-1 AF07 surfaces verified new and disjoint.
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
   receipt credit/stale-digest control, matrix integrity, engine-named refusal
   attribution, foreign-owner routing).
5. Full 29-row execution recorded and re-executed after merging #452/#460 on the
   merged tree; artifacts committed under
   `docs/af07_actual_card_campaign_20261001/artifacts/`.
6. Impact adjudication of the merged bytes: #452/#460 changed HIDDEN fixtures and
   the bridge event watcher, not the CARD records; CARD-02/CARD-24 effective
   digests are byte-identical before and after the merge, and the re-run produced
   the same verdicts bound to the new runner/engine bytes.

## Per-card Matrix

The authoritative matrix is
`artifacts/AF07_ACTUAL_CARD_MATRIX.json` (schema
`commander-lab.af07-actual-card-campaign-matrix/1.0.0`). Summary:

- **DIRECT_PASS (2)**: CARD_02, CARD_24 — fresh current-boundary runtime,
  runner-bound positive receipts, engine build at the canonical pin.
- **DEPENDENCY_WAITING (16)**: 9 rows on the successor contract surface
  (`qualification/pre-freeze-successor/`, PR #462) and 7 rows on the midgame
  executor/probe surfaces (`midgame_rows.py`,
  `run_midgame_capability_probe.py`, PR #450).
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
  suggests: CARD_02 and CARD_24 fully verify; eleven rows fail at the
  restoration dimension, and the engine names the exact dimension in every case.
- Sixteen rows stop inside the qualification executor or the fixture contract:
  scripted actions (`announce_cast`, `cast_fused`, `activate`), unscripted
  decision frames (`target`, `choose_object`, `choice`), a combat arrival the
  probe does not traverse, and two causal-entry rows (CARD_13, CARD_20) whose
  position is causally reachable but whose obligation driver is not integrated.
- The `mage-1.4.61.jar` loaded-artifact digest is recorded per run, so a future
  re-run proves which engine bytes executed rather than trusting the pin constant.
- #452 merged between census and completion; the campaign re-ran on the merged
  tree and re-pointed successor-contract ownership to the live AF05 writer (#462)
  from live ownership, without editing any foreign surface.

## Changes

- `src/commander_lab/qualification/current_boundary/actual_card_campaign.py` (new)
- `scripts/run_actual_card_campaign.py` (new)
- `tests/qualification/test_actual_card_campaign.py` (new)
- `docs/af07_actual_card_campaign_20261001/**` (new)
- `.foundry/af07-actual-card-campaign-20261001.yaml` (state)
- Merge of current `main` (#452, #460) into the workstream branch.

No foreign-owned file was modified. `midgame_rows.py`,
`run_midgame_capability_probe.py`, `knowledge_projection.py`, `source_lock.py`,
the successor contract, the current-boundary runner/assembler and the global SHA
manifests are untouched.

## Tests / Evidence

- `pytest tests/qualification` on the merged tree — 871 passed, 13 skipped
  (`DIRECTLY_VERIFIED`).
- `pytest tests/qualification/test_actual_card_campaign.py` — 32 passed
  (`DIRECTLY_VERIFIED`, engine-free).
- `pytest tests/unit/test_current_pin_fanout_ratchet.py` — passes; the campaign
  tests resolve the live pin from the manifest, adding no literal copy
  (`DIRECTLY_VERIFIED`).
- `ruff check` and `ruff format --check` on all new files — clean
  (`DIRECTLY_VERIFIED`).
- `mypy --strict` on `src/commander_lab` — the campaign producer is clean; the
  first CI quality run caught ten strict-lane errors in it, which are fixed and
  the evidence re-run on the fixed module bytes (`DIRECTLY_VERIFIED` locally,
  CI re-run in flight).
- 29 live row executions — `FRESH_CURRENT_BOUNDARY_RUNTIME`; raw engine per-row
  documents in `artifacts/measurements/`, receipts for the two direct passes,
  matrix in `artifacts/AF07_ACTUAL_CARD_MATRIX.json`.
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

- **PR #462** (successor contract; succeeded #452 after it merged): records that
  do not script the discretionary frames the engine requires (`target`,
  `choose_object`, `choice`) for CARD_01, 04, 05, 06, 14, 17, 18, 23, 26.
- **PR #450** (`midgame_rows.py`, `run_midgame_capability_probe.py`): executor
  support for `announce_cast` / `cast_fused` / `activate` priority actions,
  declaration-class handling, combat arrival traversal to the record's
  checkpoint, and integration of the declared causal entries (CARD_13, CARD_20).

## Remaining Blockers

- Bridge restoration dimensions for `stack` objects, frozen partial `library`
  identity, and counters/tapped state (11 rows).
- Denominator/receipt integration for CARD rows so direct passes can earn AF07
  credit on the freed surfaces (Phase 2).
- #450 and #462 must become terminal before Phase 2 may integrate the shared
  qualification surfaces.

## Outputs

- `docs/af07_actual_card_campaign_20261001/README.md` and this handoff.
- `docs/af07_actual_card_campaign_20261001/artifacts/` (matrix, identity,
  29 measurements, 2 receipts).
- Draft PR #463 on `hardening/af07-actual-card-campaign-20261001`.

## Dependencies Unblocked

- CARD_02 and CARD_24 direct evidence is available for the Phase-2 assembler.
- Phase 2 can re-adjudicate each blocked row from its recorded mechanism without
  re-running the whole corpus.
- The campaign consumes the merged 1.0.10 successor contract; no AF07 work was
  lost or invalidated by #452/#460.

## Exact Next Action

Keep Draft PR #463 open while #450 and #462 remain active. When both are terminal:
fresh-fetch `main`, impact-adjudicate their exact merged bytes, rebuild the
foreign-owner map from live ownership, re-run every row whose
record/executor/dimension changed, and integrate the freed shared qualification
surfaces to place the CARD rows on the effective denominator and consume the
positive receipts — without overwriting historical epochs.

---

`AF07_ACTUAL_CARD_CAMPAIGN = PARTIAL`
`PRODUCTION_PROVIDER = NOT_SELECTED`
`ARCHITECTURE_FREEZE = NOT_CLAIMED`
`SAFE_TO_CLOSE_SESSION = YES`
