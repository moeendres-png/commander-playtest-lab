# WS220 Rejected / Refined Hypotheses

Every entry below was a live hypothesis that falsification evidence forced to
reject, refine, or downgrade. Hypotheses that survived unchanged are not
listed here — they live in FINDINGS.json.

## J1. REJECTED — "47 PASS-equivalents silently carried across repin+rewrite"

- Original form (H-EVID-02 strong): WS215 retains 47/135 fixtures, carrying
  behavior credit across the cfc36f44→db134b97 repin and the variable-player
  rewrite without fresh runtime.
- Falsification: CARD_29 and MICRO_13 were never runtime PASS anywhere
  (aggregate all-NOT_RUN; WS205/207 credit 0); rows carry NOT_RUN→NOT_RUN
  with deferral rationale and "zero behavior credit claimed". REPLAY_5 carry
  PARTIAL→PARTIAL with explicit absent-item lists. `harness.py aggregate()`
  admits only mandatory-PASS, so RETAINED cannot leak into admission.
- Status: REJECTED as stated. Replaced by two weaker, substantiated findings:
  F-EVID-04a (retention sentences literally inaccurate prose without machine
  predicates) and F-EVID-04b (4P-shaped retention unscoped for N≠4).

## J2. REFINED — "PASS rows rest on the UNKNOWN authority lock"

- Original form (H-QUAL-02 as first stated): fixtures citing AUTHORITY_LOCK_v1
  as authority_ref carry RUNTIME PASS on an UNKNOWN anchor.
- Falsification: no ws203–ws215 seal literally cites the lock; PASS rows rest
  on runtime-mechanism evidence, never on authority-chain claims.
- Precise surviving form: all 135 manifest fixtures declare
  `authority_refs: ["AUTHORITY_LOCK_v1"]` while the lock holds CR bytes
  unavailable + Oracle UNKNOWN with no usage semantics; no sealed artifact
  anywhere asserts domain freshness; aggregate G01=FAIL stands. Behavior
  PASSes are valid mechanism observations that contribute nothing to
  admission (G13 needs G00–G12) until G01 closes. (Finding F-QUAL-02.)

## J3. REFINED — "5 AF gates have no evidence"

- Original form: AF00/AF01/AF03/AF10/AF11 have zero fixtures → uncovered.
- Falsification (partial): zero *manifest fixtures* is verified, but
  non-fixture evidence exists in other shapes — AF00 (ENGINE_REPIN_PROOF +
  clean-room build logs + source manifest), AF01 (handshake/capability tests),
  AF03 (the Rules-authority body: controller/projection/redactor proofs +
  negative suites), AF10 (artifact indexes + VALIDATION conventions), AF11
  (Forge separate-process bridge evidence, thinnest).
- Precise surviving form: the gap is *rollup computability*, not absolute
  absence — heterogeneous evidence is never joined into sealed per-AF
  verdicts, so Freeze eligibility is uncomputable from sealed artifacts.
  (Finding F-QUAL-01.)

## J4. DISSOLVED — "raw_result_match should fail yet 11/12 strict TRUE"

- Puzzle: `raw_result_sha256 = sha256(full result)` where the result embeds
  per-process UUIDs (`engine_game_id`, UUID-derived `decision_id`s) should
  never match across fresh JVMs.
- Resolution: the 11/12 strict-TRUE figure compares the decision-row /
  canonical-transcript hash (no identities), not `raw_result_sha256`.
  `run_replay_gate` records `raw_result_match` (expected False) but nothing
  asserts it and `bit_exact` stays False. No false claim exists.
- Surviving form: design risk R10 for WS218 — if the replay contract ever
  normativizes raw equality, the hashed object must be pinned by field
  allowlist first. Risk, not defect.

## J5. DOWNGRADED — "engine pin unchanged" (CARD retention sentence)

- The sentence is literally inaccurate post-WS213-repin.
- Falsification of materiality: `ENGINE_REPIN_PROOF.json production_delta`
  enumerates exactly 3 engine-core files (Game.java, GameImpl.java,
  CombatGroup.java) — card implementations are untouched by the delta, so the
  material claim behind the sentence is sealed-evidence-backed.
- Status: P3 doc-precision defect (sentence invites misreading; a future
  repin touching card implementations could inherit it), not an
  evidence-integrity defect.

## J6. DOWNGRADED — stale 4P policy enforcement in `robustness.py`

- First reading: living code + living test enforce a mission-contradicting
  4P-only scope — P1 source-truth defect.
- Falsification of blast radius: enforcement is contained in the demoted
  Structural tournament lane (`run_policy_tournament` defaults,
  `build_robustness_registry.py`); the Next full-game lane is unaffected.
- Status: P2/P3 (stale error text misleads; test cements it; fix together
  with the ops-policy doc reconciliation).

## J7. DOWNGRADED — "`a37a865a` cited as superseded Forge pin"

- The probe initially labeled the J-P3 Forge pin "provenance only".
- Falsification: `config/rules_engines.json:47-58` still lists
  forge-2.0.14 @ a37a865a as the live secondary differential candidate;
  `bootstrap_engine_linux.sh:17` correctly defaults to it. Probe note
  corrected in-tree.
- Status: no finding; process note (pin labels must be checked against the
  manifest, which the probe now documents).

## J8. REJECTED — "broad test suite must be run to validate the audit"

- Considered running FULL suite / Maven builds / FULL107 for completeness.
- Rejected on decision value: tree unchanged since audit base; WS213/WS215
  seals fresh; one focused test file (11 pass/1 fail) answered the integrity
  question for ~0.5s of compute. Impact-first discipline held; no broad runs
  performed. (Method note, not a project finding.)

## Falsification method note

For each P0/P1 candidate the auditor searched for: existing mitigation,
superseding evidence, design rationale, existing coverage, lock confusion,
and artifact confusion — and where the candidate survived, narrowed it to
its precise defensible form before assigning severity. Severity was not
inflated: no P0 is claimed (no live behavior-correctness compromise proven;
the strongest defects concern evidence-model integrity and requirement
computability, i.e. P1).
