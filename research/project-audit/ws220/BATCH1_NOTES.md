# WS220 Batch-1 notes — integrity of what we claim

Status: investigation complete for H-EVID-01/02/03, H-QUAL-01/02,
H-FULL107-01, H-CARD-01 (composition), H-SRC-01 (initial).
Method: 2 read-only subagent surveys + auditor probes
(`probes/stale_source_scan.py`, P-SRC-01) + 1 focused test run.

## B1. Evidence vocabularies — drift is real (H-EVID-03 SUBSTANTIATED)

Four controlled vocabularies, no mapping document:
policy/index 7-term (`AGENTS.md:66-67`, `EVIDENCE_INDEX_REQUIREMENTS.md:31-33`)
vs machine `evidence_class` 5-term
(`normalized_evidence_v1.schema.json:45-52`) vs machine `classifications`
9-term (`candidate_result_v1.schema.json:43-55`) vs harness-synthesised 3-term
(`qualification/harness.py:111-120`) plus `tools/foundry/evidence.py` 5-term
verdict subset (missing UNSUPPORTED/NOT_APPLICABLE).
Concrete breaks: `DIRECTLY_VERIFIED` (seals' most-used provenance label) is not
in any machine enum — schema validation rejects it; `harness.py` default-fills
missing `evidence_class` as `RUNTIME_VERIFIED` for any PASS, silently upgrading
`CODE_DERIVED`-in-prose rows and erasing `CODE_DERIVED != RUNTIME_VERIFIED`;
WS79 ledger rows carry `evidence_class: UNKNOWN`, also schema-rejecting.
No ws213/ws215 top-level JSON carries an `evidence_class` key at all.

## B2. Stale rollup layer (H-EVID-01 SUBSTANTIATED, scoped)

`qualification/aggregate/*` + `evidence/candidates/*` + `BASELINE_COMMON_RESULTS`
last touched `bbe91739`/`9e5b787d` (2026-08-29), 148 commits / 17 days behind
the seals that supersede their subject matter; content is 0-PASS/NOT_RUN while
ws213/ws215 claim lifecycle PASS + 1 behavior credit. No living doc/code routes
readers there (P-SRC-01 + targeted grep), BUT no deprecation marker exists and
`tests/qualification/test_ws17_qualification.py` *pins* the stale shape
(all-NOT_RUN assertions). Two readers, two opposite false pictures; no
reconciling index exists in-tree.

## B3. Seal schema drift + retention gaps (H-EVID-02 supporting)

VALIDATION.json: UPPER_SNAKE (ws204/205/207/213) vs lower_snake (ws215);
schema tag present/absent/double (ws205 has two competing tags); FULL107 vs
full107 casing; annotated-string vs structured values. No common validator:
post-WS17 seals are human-read conventions. Retention: 0 of 6
`retention_anchor_*`/`retention_reason`/`retirement_approved_by` fields in
ws213/ws215 seals (policy requires 15 fields in `EVIDENCE_INDEX_REQUIREMENTS`);
ARTIFACT_INDEX satisfies only the artifacts+sha256 fragment (and the policy
explicitly warns SHA != RETENTION ANCHOR). ws215 index regressed from the
`evidence.py` contract (dropped run/source_sha columns); both indexes sweep
`.pyc` build artifacts; `qualification/SHA256SUMS` coverage lapsed (no
ws213/ws215 lines).

## B4. RED integrity gate on the WS215 line (new, runtime-verified)

`pytest tests/qualification/test_ws17_qualification.py` on HEAD: 11 passed,
1 FAILED — `test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts`:
root `WS17_SHA256SUMS` hash mismatch for
`qualification/ws207-.../tests/test_ws207_seed_binding.py`. Cause is legitimate
(WS213 `344deca4` revised the RandomUtil-only guard to the native Rules-seed
guard, documented in-code; sealed WS207 evidence untouched) but the manifest
was not refreshed, so the tamper-evidence gate is red. main (7725570b,
2026-09-14) predates the WS213/215 line — the red hits at merge time. A red
integrity gate trains operators to ignore red.
Recorded as candidate P1 (evidence-model integrity, not behavior).

## B5. G/AF duality (H-QUAL-01 CONFIRMED)

5 of 12 AF gates have ZERO fixtures (AF00, AF01, AF03, AF10, AF11); AF09 thin
(5 fixtures, all retained-not-rerun, replay PARTIAL). G01/G13/G14/G15 have no AF
home — all-AF-PASS still cannot establish production admissibility. No
per-AF-gate verdicts sealed anywhere post-WS17 (verified by grep over
ws203-ws215). Freeze eligibility is currently uncomputable from sealed
evidence. `QUALIFICATION_OBLIGATION_CATALOG_v1.json` is a flat list, not a
trace matrix.

## B6. Authority anchor (H-QUAL-02 REFINED)

Seals never literally cite the lock — the premise as first stated was wrong
(falsification recorded). The precise exposure: all 135 manifest fixtures
declare `authority_refs: ["AUTHORITY_LOCK_v1"]` while the lock holds
CR=`AUTHORITY_IDENTIFIED_BYTES_UNAVAILABLE` (sha null) + Oracle=`UNKNOWN` +
`secondary_sources_promoted: false`, and the lock defines no usage semantics.
No sealed artifact anywhere asserts domain freshness; aggregate G01=FAIL
stands unreconciled; G13 needs G00-G12 all PASS. Behavior PASS rows stand as
mechanism observations but contribute nothing to admission until G01 closes.

## B7. FULL107 (H-FULL107-01 ANSWERED: retire as unit, impact-select)

FULL107 = 107-scenario matrix under superseded materialization 1.0.5; credit
zeroed by WS73; absent from every live protocol/obligation/manifest contract;
full roster not recoverable. A run would cost multiples of a WS213-scale matrix
and remove none of the live blockers (G01, 16 UNKNOWNs, PARTIAL replay,
zero-fixture AF gates). Decomposed successors already exist (135-manifest with
disposition ledger + RQ-C3 requalification). Recommendation: retire the unit;
fund per-fixture impact-selected successors (setups, credited pilots, replay
contract, G01 re-acquisition).

## B8. Retained-47 sharpened (H-EVID-02 core)

Composition: 29 actual_card (the ENTIRE AF07 corpus) + 13 micro_rules (AF06
backbone) + 5 replay_rng (all of AF09), carried across engine repin
(cfc36f44->db134b97) + variable-player bridge rewrite on CODE_DERIVED +
adjudication, zero fresh runtime. The retained set is exactly the highest-risk
categories, and AF07 PASS would therefore rest 100% on retention. Audit of the
per-row rationales (completeness of the "touched-path" argument) is the
highest-value remaining evidence task; queued for batch-2/falsification.

## B9. Card corpus composition (H-CARD-01 factual)

29 identities catalogued by family. Triggers heavy (10+); replacement narrow
(3, no prevention/entry-copy/control-change/extra-turn); spell-copy only, no
permanent-copy; layers thinnest (equipment keyword-grant + Narset + P/T-set;
no humility/blood-moon/opalescence-type interaction, no control/type-change);
zones uneven (no tutor-shuffle, no face-down, no grave-hate, one land).
Micro fixtures exist for all five risk areas but MICRO_LAYERS /
MICRO_CONTINUOUS_EFFECTS were retained-not-rerun. Zero combo, extra-turn,
stax-beyond-Narset, sac-outlet, lifegain. 29 vs 1385-universe / 795-RogShai /
142 unknown opponent slots; no sampling rationale in manifest.

## B10. Source-truth staleness scoped (H-SRC-01 PARTIAL)

P-SRC-01 (committed probe, rerunnable): 102 CURRENT/FINAL/LATEST name-traps
(mostly artifacts/data history; living ones incl. DECISION_CONTRACT_CURRENT,
CARD_COVERAGE_CURRENT, CARD_KNOWLEDGE_POLICY_CURRENT must be verified per use).
Live 4P-only claims: `docs/OPERATIONAL_SIMULATION_POLICY.md` (stale, untouched
since 136afc8b), lane doc `:13` (internally contradicts its own :6-9),
`docs/architecture/deckbuilding-simulation-separation.md:247`,
`scripts/run_external_full_game_conformance.py:82` (hardcoded
`player_count=4`, `range(1,5)` on current pin db134b97),
`src/commander_lab/robustness.py:249-254,760` + `.../optimizer_v2_decision_runtime.py:109`
(ValueError "out of project scope"),
`tests/unit/test_operational_4p_policy.py` (a living test CEMENTING the stale
policy — fixing the policy requires updating this test).
Falsification bounding: robustness.py enforcement is contained in the demoted
Structural tournament lane (consumers: run_policy_tournament defaults,
build_robustness_registry.py) — not the Next full-game lane. So P2/P3, not P0.
BUT the CI conformance lane (`.github/workflows/xmage-full-game-conformance.yml`)
has zero 2P/3P/5P coverage and doesn't trigger on
`tests/unit/test_xmage_full_game.py`-adjacent `test_xmage_variable_player.py`
— WS215's headline capability has no CI gate. New hypothesis H-CI-03.
Superseded-pin citations outside seal provenance are benign except
`XMAGE_FULL_GAME_CLOSEOUT.md:11` (release-gate snapshot, do-not-repin-from)
and the living `a37a865a` Forge secondary pin (still current per manifest;
probe note corrected — falsification applied).
No ws218/ws219 remote branches: no POST_LOCK_DRIFT (checked 2026-09-15 via
fetch + for-each-ref; origin/main = 7725570b).

## Reprioritization after batch 1

- PROMOTE: retained-47 rationale audit (H-EVID-02 core); RED-gate remediation
  path (H-CI-02 new); CI 4P-only conformance gap (H-CI-03 new); AF rollup
  computability (H-QUAL-01 mechanism design, not just mapping).
- DEMOTE: H-FULL107-01 (answered); H-SRC-01 broad hunt (bounded; remaining
  items are doc-reconciliation successors); pin-confusion hunt (manifest
  authority + drift_check tooling work; residual is closeout-file hygiene).
- NEW: H-CI-02 (manifest-refresh discipline / red-gate normalization);
  H-CI-03 (variable-player CI coverage).
