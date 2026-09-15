# WS223 Final Handoff — Cardinality CI & Reproducible Environment Hardening

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws223/ci-cardinality-environment-lock-20260915`
- Audit base: `3cdade1dfb16c820465690680b0b0be8af7007ef` (TREE `0a249bf4…`)
- WS220 design input: `1a6ffcda…` (S5/F-CI-03, S15/F-CI-01 only)
- XMage authority: `db134b97…` (unchanged) · `ARCHITECTURE_FREEZE = NOT_CLAIMED` · `PRODUCTION_PROVIDER = NOT_SELECTED`

## Work Completed

**S5 — Cardinality CI.** `XmageFullGameRunner.run_smoke()` added (reuses
validation/handshake/policy; `run()` semantics preserved via shared `_drive`);
conformance script parametrized (4P default gate byte-identical in behavior;
2/3/5P bounded smoke; 6P fail-closed probe); lane rewritten (2/3/5 live +
4P full + 6P closed, unified triggers, WS218 replay adjudication, cost bound
documented); 32-test regression battery (constants, layers 1–4, mapping,
smoke integrity, lane structure).

**S15 — Reproducible environment.** `requirements/lock.in → lock.txt`
(117 pins, 1945 hashes; pip-tools 7.6.1 + win32 appendix + verifier +
provenance); locked installs + lock-bound caches + `PYTHONHASHSEED: "0"` in
15/16 lanes (documented windows/opencode exceptions); digest-pinned
Temurin bases; JDK matrix contract (CI 17 / containers 21, floor
`release=17`); receipt script + ci/conformance steps; 11-test identity
battery. Guard updates: WS-A1D digest domain-split, WS17R install pattern.

**Proofs.** Live 2P/3P/5P smoke PASS (targets calibrated {25,25,45}; 5P@25
correctly fails), 4P full gate PASS (3105 decisions, replay match), 6P
FAIL_CLOSED, clean A==B identity, offline explicit-failure, identical
regeneration. Full `tests/unit` 871 green on clean tree.

## New Findings

1. 5P needs 45 bounded decisions (mulligans + opening choices consume ~25).
2. pip-compile prunes non-matching markers → win32 closure needs a generated
   appendix (colorama, pywin32).
3. `pip freeze` omits pip itself; `boolean.py` canonical name uses a dot —
   comparison tooling must normalize (recorded).
4. WS-A1D HEX40 guard vs base-image digests: different authority domains;
   narrowed with prohibition preserved.
5. F-CI-02 integrity gate is RED AT HEAD (ws213/ws218 files uncovered;
   manifests byte-identical to HEAD) — set-theoretic proof in handoff;
   WS223 leaves manifests untouched (F-CI-02 successor owns refresh).
6. `ruff check .` / `mypy` findings confined to untouched WS218-stack files
   (pre-existing; CI mypy step is advisory — no pipefail).
7. Dirty-tree gates: 44+8 tests/unit failures under a dirty tree were 100%
   tree-cleanliness artifacts (871 green after commit).

## Changes

See checkpoint `3e6d170f` + follow-up (test_ws17r fix, evidence files):
15 workflows, 2 Dockerfiles, conformance script, `full_game.py`,
requirements lock trio, 3 lock/receipt scripts, 2 new test batteries,
WS-A1D + WS17R guard updates, `qualification/ws223-…` namespace (30 files).

## Tests / Evidence

`EVIDENCE_SEAL.json` (29 artifacts + run verdicts). Classifications:
live runs/lock/installs = DIRECTLY_VERIFIED; base-red proof, trigger
analysis = CODE_DERIVED; longitudinal recheck = FUTURE_ADVISORY; FULL107 =
NOT_RUN. No weakened assertions; no Rules/pilot behavior changed
(`RULES_SEMANTICS_CHANGED = false`).

## PASS / FAIL / UNKNOWN (hard gates)

1. 2–5P live smoke in merge lane — PASS (lane written; local-equivalent green)
2. 6P fail-closed — PASS (4 layers, probe green, no 6P claim)
3. Variable-player triggers — PASS (unified PR/push, static tests)
4. Cost bounded + documented — PASS (single job, 3×bounded + 1 pair)
5. Transitive identity lock — PASS (117 pins, 1945 hashes)
6. Two clean resolutions identical — PASS (`b6ec216c` == `b6ec216c`)
7. Java identity pinned/coherent — PASS (matrix contract + receipt)
8. Container identity immutable — PASS (digest + labels + contract)
9. Hashseed policy — PASS (15/16 + exemption + test)
10. Cache keys bound — PASS (explicit lock keys + tests)
11. Receipts — PASS (script + 2 lanes + schema/identity tests)
12. No Rules/pilot change — PASS (additive only; guards green)
13. Impacted guards green — PASS except base-red F-CI-02 gate (proven
    pre-existing; documented, not introduced)

## Remaining Blockers

- F-CI-02 refresh (owns WS17 manifest updates incl. WS223's workflow +
  namespace files) — successor/integration scope, not WS223.
- Remote CI execution (3.12 locked install, JVM lanes) — post-merge
  observation; local-equivalent evidence sealed.
- Container 21→17 evaluation trial — future advisory.

## Outputs

`qualification/ws223-ci-cardinality-environment-lock/` (contracts, live
summaries, lock digests, clean-resolution freezes + comparison, validation,
seal, this handoff); `requirements/lock.{in,txt}` + `LOCK_PROVENANCE.json`;
`scripts/{verify_dependency_lock,generate_lock_appendix,write_environment_receipt}.py`.

## Dependencies Unblocked

- Any successor needing reproducible Python envs (lock + receipt + cache keys).
- Cardinality-sensitive work (S6 numerics, future player-count changes) now
  guarded by CI + regression battery.
- F-CI-02 refresh has the exact WS223 file list (this namespace + workflow).

## Exact Next Action

Commit follow-ups → final validation sweep → same-session publication via
`tools/foundry/safe_push.py` (`--dry-run`, then actual) with
`--expected-audit-base-ref ws218/semantic-replay-tape-v1-20260915`; verify
HEAD/TREE equality with origin; emit terminal fields.

## Terminal Fields

- WS223_CI_CARDINALITY_ENVIRONMENT_LOCK: COMPLETE (pending remote CI observation)
- CI_PLAYER_COUNT_2P: PASS · CI_PLAYER_COUNT_3P: PASS · CI_PLAYER_COUNT_4P: PASS
  · CI_PLAYER_COUNT_5P: PASS · CI_PLAYER_COUNT_6P_FAIL_CLOSED: PASS
- CI_VARIABLE_PLAYER_TRIGGER_COVERAGE: PASS
- PYTHON_TRANSITIVE_LOCK: PASS (117 pins) · PYTHON_LOCK_HASHES: PASS (1945)
- CLEAN_RESOLUTION_A: PASS · CLEAN_RESOLUTION_B: PASS · CLEAN_RESOLUTION_EQUALITY: PASS
- JDK_IDENTITY: PASS (matrix) · CONTAINER_IDENTITY: PASS (digest-pinned)
- PYTHONHASHSEED_POLICY: PASS · CACHE_KEY_IDENTITY: PASS · ENVIRONMENT_RECEIPT: PASS
- ENVIRONMENT_LOCK_IMPLEMENTATION: PASS · CLEAN_RESOLUTION_REPRODUCIBILITY: PASS
- LONGITUDINAL_AVAILABILITY_RECHECK: NOT_RUN / FUTURE_ADVISORY
- RULES_SEMANTICS_CHANGED: false · BEHAVIOR_CREDIT_CHANGE: none
- FULL107: NOT_RUN · RAW_GIT_PUSH_USED: false
- ARCHITECTURE_FREEZE: NOT_CLAIMED · PRODUCTION_PROVIDER: NOT_SELECTED
