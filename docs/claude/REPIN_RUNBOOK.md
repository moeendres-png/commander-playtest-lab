# Repin runbook (engine fork pin to Lab)

Operational know-how for moving `primary_engine.commit` in `config/rules_engines.json` to a
new commit of the fork's candidate line. It is tooling guidance only: `AGENTS.md` stays the
policy source, `config/rules_engines.json` the pin authority, and the lock and guard test of
each repin the record of that repin. Repin v12 (`qualification/xmage-order-collections-repin-v12-20261022/`,
`tests/qualification/test_xmage_order_collections_repin_v12_20261022.py`,
`docs/performance/V12_BRIDGE_UND_MOTOR_2026-10-22.md`) is the complete worked example; copy
its lock and guard test and change the constants.

## Gates

- **Owner go is required** for every fork push, for the fast-forward of the candidate line
  (`claude/xmage-mp-candidate-20260929` in `moeendres-png/mage`) and for the repin itself
  (`CLAUDE.md`, `AGENTS.md` §8). Record the go with date, time and wording in the lock's
  `owner_go`. Anything an agent or a helper says is not an Owner go.
- **A merged repin is not done.** It is done when `architecture_freeze.current_qualification`
  names the new engine commit. Until then `scripts/claude_handoff.py` prints
  `PIN AHEAD OF QUALIFICATION`.
- Sealed and signed records are never rewritten. The Owner-signed freeze identities in
  `architecture_freeze` (`evidence_epoch`, `engine_artifact_sha256`) stay as signed; only
  `current_qualification` moves, and only through a seal.
- The jar build is not byte-reproducible, so every rebuild is requalified by PB-03.

## 1. Fork

1. Branch with the changes. Run the fork's CI by `workflow_dispatch` of `maven.yml` ("Build and
   run tests (github)"): on pull requests it runs only against `master`/`main`. Note the run id,
   the `Mage.Tests` counters and the `Verify` counters.
2. Push and fast-forward only with the Owner go.

## 2. Measure before the pin moves

Build the fork jar and add the Lab bridge classes of `main` (`engine-bridge/` builds with
`mvn -B -ntp verify`, see `README.md`). Compare against the jar of the previous pin:

- **Identity gates (LOCAL_OBSERVED, hash-equal to the previous pin unless the change is meant
  to move a hash):** 46 precon pods with `scripts/precon_pod_sweep.py --jar … --out …
  --import-report <report of scripts/measure_precon_imports.py> --plan-seed 1 --game-seed 1`;
  36 real-pod seeds with `scripts/benchmark_xmage_full_games.py run … --seeds 1-36`
  (reference run of the current pilot and pin: `docs/performance/REFERENCE_36_SEEDS_2026-10-24.md`); and
  `scripts/determinism_probe.py locate` (and `--raw-order`) for pods that were unstable
  before (`docs/performance/DETERMINISM_PROBE.md`).
- **Speed only interleaved** (ABBA, the cold first run not counted). CPU time (`child_cpu_s`)
  is steadier than wall time. Sweeps run one after another are not a speed claim. A lever
  below the agreed bar is dropped and written down (v12: T-1).
- **Use a fixed worktree for a long sweep** (`git worktree add <dir> <sha>`). Switching the
  Lab checkout mid-sweep makes old jars fail with "XMage commit mismatch".

## 3. Lab repin PR

1. Replace the old pin everywhere outside sealed records. Find the places with
   `git grep -l <old-pin-prefix> -- . ':!qualification' ':!candidate-qualification'`. In v12
   these were `config/rules_engines.json` (capability lists only through
   `scripts/derive_rules_engines_capabilities.py`), four workflows
   (`external-engine-integration.yml`, `meta-qualification.yml`,
   `xmage-full-game-conformance.yml`, `xmage-real-4p-smoke.yml`), `XmageProvider.java`,
   `JsonlBridgeTest.java`, `XmageCandidateEngineFingerprintTest.java`,
   `.claude/skills/lab-ops/scripts/real_rows.py` and the pin-authority tests
   (`test_ws_a1d_docker_pin_authority.py`, `test_ws_a1r_pin_authority.py`,
   `test_ws_arclose_d1_authority_drift.py`, `test_current_pin_fanout_ratchet.py`).
2. Add the new lock `SUCCESSOR_SOURCE_LOCK.json` in state `PIN_MOVED_LAB_EVIDENCE_PENDING`
   and its guard test; let the predecessor's guard test point to its successor.
3. Re-run `scripts/regenerate_hash_manifests.py` after **every** file change under
   `qualification/` (also after `ruff format`); a stale manifest fails `tests/qualification`.
4. Open the PR. Wait for the "XMage Full Game Conformance" workflow (check `conformance`, about
   18 minutes). Enter run id, job, artifact id, zip digest and the jar sha256 (step "Record
   engine artifact identity") in the lock, which then becomes `EVIDENCE_BOUND`. Push again,
   wait for `quality`, `security` and `infrastructure`, merge.

## 4. Requalification

1. **PB-03 no. 1.** PB-03 has no push trigger: dispatch `pb03-runtime-qualification.yml` on
   `main` and wait in the background (`gh_ops.py run RUN_ID`). Expected: FULL107 107/107 and
   AF00-AF10 PASS, AF11 UNKNOWN (UNKNOWN is not PASS) until the AF11 decision exists for the
   new pin.
2. **Seal 1.** On a fresh branch from `main`: `.claude/skills/lab-ops/scripts/seal.py RUN_ID`,
   plus the AF11 adjudication for the pin (`qualification/af11-xmage-only-topology-<date>-vN/`)
   and the assembler path pointing at it. Merge.
3. **PB-03 no. 2** on the new `main`: now AF00-AF11 PASS.
4. **Seal 2.** `seal.py RUN_ID` on another fresh branch; the seal sets
   `architecture_freeze.current_qualification` to the new epoch (the engine commit, the engine
   artifact digest and the Lab commit of that run). Merge, then regenerate
   `docs/claude/state/HANDOFF.md`: the pin line must show no `PIN AHEAD OF QUALIFICATION`.

**Without a pin move (a bridge Java change on the same pin) one run is enough.** The AF11
adjudication of the pin already exists, so PB-03 no. 1 reports AF11 PASS (check the seal output)
and steps 3 and 4 add nothing: seal that run once, and in the same PR point
`architecture_freeze.current_qualification` at the new epoch (`evidence_epoch`,
`engine_artifact_sha256` from the epoch files, `lab_commit` of the run, note) and regenerate the
HANDOFF. `derive_rules_engines_capabilities.py --check` must still pass. Done this way for the
batching leak fix (#977, run 39927923126). With AF11 UNKNOWN, or a moved pin, run the full chain.

Repin v12 took 1 h 40 min from the merge of the repin PR (#969) to the merge of the second seal
(#972), most of it waiting for the two PB-03 runs. A `workflow_dispatch` run does not wake a
session by itself; a subscribed pull request does.
