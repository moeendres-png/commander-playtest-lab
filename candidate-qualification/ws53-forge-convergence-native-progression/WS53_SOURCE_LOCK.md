# WS53 — Source Lock (Milestone A, verified 2026-09-10 before any semantic edit)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: `/home/moeen/code/ws53-forge-convergence-native-progression`
- Branch: `ws53/forge-convergence-native-progression-20260910`
- CPL starting HEAD: `66d5aa44a45cb574cabba2853de149c032e7942e` — VERIFIED (`git rev-parse HEAD`)
- CPL starting TREE: `3025858d8de706029fa3a9a27920ace51ba35cd0` — VERIFIED (`git rev-parse HEAD^{tree}`)
- Working state: clean except untracked `candidate-qualification/ws53-forge-convergence-native-progression/`
  (bootstrap `WORKSTREAM_STATE.yaml` placeholder, now replaced with contract objective/scope)
- WS48 canonical: HEAD `f8bd8b2d582627202a462ae7c7adf9fd5af83a57` / TREE `fcb7fc009bea6527e410eb88f67549ca16cc8ea4`
  — TREE VERIFIED via `git rev-parse <sha>^{tree}`
- WS50 donor: HEAD `e636e7055478709010cbd778846683065e31655b` / TREE `59a08ba105a4f666e735c36cd8cd7c8c17ca1fd3`
  — TREE VERIFIED via `git rev-parse <sha>^{tree}`
- WS50 fork point: `10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d` (pre-Repair-01 WS48 state;
  WS50 lineage never contained WS48 Repair-01 in WS48-owned files)
- WS51 terminal = starting HEAD (`66d5aa44…`, WS51 additive-only over WS48 canonical:
  `git diff --stat f8bd8b2d..66d5aa44` = 12 files, all new under
  `candidate-qualification/ws51-forge-block4/`, zero modifications to existing files)
- Forge pin: HEAD `66caae16015bd403bc0a52fa6689afb5508f74d0` / TREE `40fc8f29ce4de31a964972461db2b48b4221e07f`
  — VERIFIED in dedicated checkout `/tmp/ws53-forge-src` (READ-ONLY by contract; no mvn, no writes)
- Forge prebuilt classes (read-only reuse): `/home/moeen/.ws48-r1e/forge-66caae16015bd403bc0a52fa6689afb5508f74d0/…/target/classes`
  present (`forge/`), plus `/home/moeen/.ws48-r1e/ev/dependency-classpath.txt`
- Control plane (NOT qualification evidence): donor tree `215611ac8d1ea93353c2fcc4c8d7e06dabb4ca51`;
  `--allow-suppressed-routing` intentional (candidate lineage predates merged execution plane);
  no execution-policy changes will be copied into the candidate lineage
- Writer gate: `git worktree list` shows exactly one worktree on this branch
  (`/home/moeen/code/ws53-forge-convergence-native-progression` @ `66d5aa44`);
  no other worktree holds this branch; no git locks observed
- Standing state preserved: `ARCHITECTURE_FREEZE = NOT CLAIMED`,
  `PRODUCTION_PROVIDER = NOT SELECTED`, `BEHAVIOR_CREDIT = 0/107`, `FULL107 = NOT_RUN`

## Lineage divergence summary (read-only `git diff` / `git show`, no history operations)

- `git diff --name-only f8bd8b2d..e636e705` (WS48-canonical → WS50-donor): 40 files.
  Implementation-bearing deltas: exactly one shared-file modification
  (`ws48_behavior_provider_overlay.py`, absence-of-Repair-01 artifact) + 5 new WS50-owned
  files (`ws50_provider_overlay.py`, `ws50_sequence_runner.py`, `ws50_static_gates.py`,
  2 build scripts) + WS50 evidence JSONs. Apparent "deletions" of WS48 R1f files/test are
  fork artifacts (never existed in WS50 lineage), not semantic reversions.
- No changes in WS50 lineage outside `candidate-qualification/` + the one test path.
  `scripts/`, `engine-bridge/`, `src/`, `qualification/` providers: untouched by WS50.
- Base API compatibility for runner port: `run_behavior_transcript_probe.py` (current tree)
  provides `Driver` (with `script/consumed/priority_script/ps_cursor/structural_passes/
  ritual_answers/frames/events/raw_lines/decode_errors/result_seen/setup_stage_seen/
  actor_pid/options`), `answer_frame`, `ref_identity`, `dec_label`, `Blocked`,
  `behavior_env`, `command`, `digest` — all VERIFIED present.
- WS47 frozen contract staged per-run via read-only `git show 192e2b77…:qualification/ws47/…`
  (sha256 `0e47b792…940b3`); never copied into the repo.
