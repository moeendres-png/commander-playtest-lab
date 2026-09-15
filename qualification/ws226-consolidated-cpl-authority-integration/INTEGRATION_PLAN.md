# WS226 INTEGRATION_PLAN — safest systemic method, ordered steps

Constraint: integrate SEMANTICS, not stale branch state. No merge/rebase/
reset-hard/clean/wholesale-checkout/blind-cherry-pick. Exact
Git-object/path/hunk transfer; blob-exact for immutable namespaces.

## Step 0 — Pre-mutation records (this commit batch, before any living edit)

SOURCE_LOCK, LINEAGE_GRAPH, PATH_OWNERSHIP_MATRIX, OVERLAP_MATRIX,
INTEGRATION_PLAN (this file) + EVIDENCE_RETENTION_IMPACT skeleton.
Verify: `git status` clean, HEAD `48885e8e`, tree `d02d6c0…`.

## Step 1 — WS220 provenance (blob-exact, once)

Transfer `research/project-audit/ws220/*` (24 files) from `189dcfc0`
(equivalently `1dcfe898`; prove `git diff 189dcfc0 1dcfe898 --
research/project-audit/ws220` empty before write). Method: python
Git-object extractor (`git show <rev>:<path>` bytes → worktree path,
exact, no newline mangling). Verify per-file sha256 equals source blob.

## Step 2 — WS221 living governance (semantic reconcile = take sibling;
## base has no competing change, proven empty diff)

Transfer exactly from `189dcfc0`:
`qualification/evidence_vocab_v1.py`,
`qualification/evidence/evidence_legacy_map_v1.json`,
`qualification/evidence/candidate_result_v1.schema.json`,
`qualification/evidence/normalized_evidence_v1.schema.json`,
`qualification/harness.py`, `docs/OPERATIONAL_SIMULATION_POLICY.md`,
`docs/architecture/deckbuilding-simulation-separation.md`,
`docs/architecture/xmage-full-game-external-pilots.md`,
`src/commander_lab/robustness.py`,
`tests/qualification/test_ws221_evidence_vocab.py`,
`tests/unit/test_operational_4p_policy.py`,
`qualification/ws221-foundation-integrity-source-truth/*`.
Post-check: `grep` proves no `RUNTIME_VERIFIED" if verdict in {"PASS"` 
coercion remains in `harness.py`; vocab tests import clean.

## Step 3 — WS222 authority (blob-exact + living migration)

3a. Transfer `qualification/ws222-g01-authority-reacquisition/*` (72 files,
including 977 kB CR + 30 Oracle pages + B&R + receipts + tooling) + 
`tests/qualification/test_ws222_authority.py` from `1dcfe898` blob-exact.
3b. Living migration (new WS226 bytes, not a sibling overwrite):
- `qualification/manifests/AUTHORITY_LOCK_v2.json` = EXACT byte copy of
  `qualification/ws222-g01-authority-reacquisition/AUTHORITY_LOCK_v2.json`
  (v1 untouched; verify `cmp` equal; offline verify with
  `--ns qualification/ws222-g01-authority-reacquisition --lock
  qualification/manifests/AUTHORITY_LOCK_v2.json` → PASS).
- Do NOT rewrite `COMMON_FIXTURE_MANIFEST_v1.json` authority_refs (WS222
  deferred to S2 rollup; 135-row rewrite out of scope; standing G01 is
  direct-gate, not fixture-joined).
- Do NOT generalize bounded Oracle (frozen 29 only); document scope in
  AUTHORITY_V2_INTEGRATION. `REQUALIFICATION_REQUIRED` stays empty.
- Update standing inputs (Step 6) to consume v2 for xmage G01 PASS scoped.

## Step 4 — WS224 privacy (blob-exact; production untouched)

Transfer from `f075ab75` blob-exact:
`engine-bridge/src/test/java/org/commanderlab/xmage/XmageFullGameNameCanaryTest.java`,
`qualification/ws224-hidden-info-name-canary/*` (33 + driver),
`tests/unit/test_ws224_name_canary.py`.
Post-check: `git diff --name-only` proves no `src/commander_lab/**`,
no `src/commander_lab/engine/rules/full_game.py` touched by this step;
`ENGINE_INTERNAL_LOG_STATUS` stays UNKNOWN (no upgrade).

## Step 5 — WS225 governance (blob-exact, frozen as history)

Transfer from `8b3ab80d` blob-exact:
`qualification/reporting/ws225/*` (37),
`qualification/aggregate/WS225_ROLLUP_STATUS.json`,
`tests/qualification/test_ws225_standing.py`.
Do NOT hand-edit any `ws225/*_STANDING.json` verdict. They remain the
WS225-lock historical view (G01 FAIL).

## Step 6 — WS226 standing recompute (deterministic, no hand verdicts)

6a. Copy `qualification/reporting/ws225/standing_generator.py` →
`qualification/ws226-consolidated-cpl-authority-integration/standing_generator.py`
(method: exact copy then minimal WS226 adaptation: ROOT-relative inputs
point at WS226 namespace; WS225_COMMIT constant updated; no verdict logic
changed — diff must show ONLY path/lock constants).
6b. Author WS226 inputs as machine-readable companions (derived, not
hand verdicts):
- `GATE_DIRECT_EVIDENCE_WS226.json`: exact copy of WS225 direct evidence
  EXCEPT xmage G01 FAIL→PASS (scoped) with v2 provenance
  (`qualification/manifests/AUTHORITY_LOCK_v2.json` +
  `qualification/ws222-g01-authority-reacquisition/VALIDATION.json` +
  offline `verify_authority.py` PASS). All other gates byte-identical.
- `EVIDENCE_OVERRIDES_WS226.json`: exact copy of WS225 overrides
  (fixture behavior unchanged, BEHAVIOR_CREDIT 0). No row hand-flipped.
- `CANDIDATE_FACTS_WS226.json` + `ADMISSION_STAGE_CONTRACT` (copy; stage
  decided by generator, not by hand; S5-cardinality ≠ S5-admission noted).
6c. Run generator twice; prove byte-reproducible outputs
(`XMAGE_STANDING_WS226.json` etc. + `G_AF_CURRENT_VIEW.json` +
`OPEN_BLOCKERS_WS226.json` + `G01_STATUS_WS226.json` + VALIDATION digest).
Adjudicate G01/G02/G07/G09/G10/G11/G13 + AF01/AF02/AF05/AF07/AF08/AF09/
AF10/AF11 for XMage from exact traces; preserve Forge/Quorune/Argentum
dispositions.

## Step 7 — Manifest repair + F-CI-02 closure (terminal, after bytes stable)

After ALL semantic bytes + generated standing are stable:
- Recompute `WS17_SHA256SUMS` (root coverage: pyproject + prod-qual workflow
  + test_ws17_qualification.py + all `qualification/**`) and
  `qualification/SHA256SUMS` (all `qualification/**` except itself) with
  current bytes; preserve WS221 same-commit invariant (repair in the same
  commit series as the final tree, before terminal validation).
- Prove: byte hashes verify, coverage sets equal expected, deliberate
  single-byte mismatch still fails (negative control).
- F-CI-02 (`test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts`)
  must be GREEN on the final tree.

## Step 8 — Impact-selected validation (no blind 135-rerun)

Minimum (ordered smallest-first):
1. `test_ws221_evidence_vocab.py` (vocab + reject-not-coerce negatives)
2. `test_ws222_authority.py` + `verify_authority.py` offline (v2)
3. `test_ws17_qualification.py` full file (manifest integrity F-CI-02)
4. `test_ws223_environment_identity.py` + `test_ws223_cardinality_regression.py`
5. `test_semantic_replay_tape.py` (WS218 guards)
6. `test_ws224_name_canary.py` (UUID+name canaries; Java canary via Maven
   ONLY if tree context changed — record NOT_RUN with reason if JVM absent)
7. `test_ws225_standing.py` (generator/regen/negatives, on frozen ws225 inputs)
8. WS226 generator determinism + `test_ws17r_exact_main_runtime.py` +
   `test_operational_4p_policy.py` + hidden-info Java suite if touched
9. 2P/3P/4P/5P bounded smoke + 6P fail-closed ONLY where impact requires
   (full_game.py untouched → rely on WS223 seals + cardinality regression;
   do not rerun 135 fixtures without impact reason).
Preserve all OPEN UNKNOWNs (APNAP, extra-turn, CR800.4, damage thresholds,
Partner tax/damage, zone branches, other G10/AF08 16; AF01/G12/AF11) unless
sealed evidence actually proves them. FULL107 stays HISTORICAL_REGRESSION_ARTIFACT.

## Step 9 — Seal + publication (same launcher-held writer session)

VALIDATION + FINAL_HANDOFF in `ws226/` namespace → focused local commits per
milestone → `state.py --state <FOUNDRY_STATE_PATH>` COMPLETE + validated_head
→ clean worktree → worktree-local `safe_push --dry-run` → actual `safe_push`
→ `git fetch origin --prune` → HEAD==remote HEAD, TREE==remote TREE, clean →
final handoff (Source Lock/Work Completed/New Findings/Changes/Tests/
PASS-FAIL-UNKNOWN/Blockers/Outputs/Dependencies/Exact Next Action).
No raw push, no PR, no merge, no main mutation, no history rewrite.
