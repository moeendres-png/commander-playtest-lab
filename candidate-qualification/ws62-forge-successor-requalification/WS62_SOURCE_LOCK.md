# WS62 — Source Lock (verified 2026-09-11 before any semantic edit)

- Repository: `moeendres-png/commander-playtest-lab`
- Worktree: `/home/moeen/code/ws62-forge-successor-requalification`
- Branch: `ws62/forge-successor-requalification-20260911`
- CPL audit base HEAD: `e39c7de053573625e51006b917bef43468161752` — VERIFIED (`git rev-parse HEAD`)
- CPL audit base TREE: `2a94ca9212b27c25231ba8ecacdb592508187d22` — VERIFIED (`git rev-parse HEAD^{tree}`)
- Working state at lock: clean except untracked `candidate-qualification/ws62-forge-successor-requalification/` (bootstrap `WORKSTREAM_STATE.yaml` only).
- Remote source branch (read-only audit base ref): `ws55r/forge-rqc3-impact-closure-20260911` (expected FETCH_HEAD `e39c7de053573625e51006b917bef43468161752`; verified at safe_push time, not here).

## Forge engine pins

- OLD FORGE PIN (read-only, never reused as runtime): `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29ce4de31a964972461db2b48b4221e07f`
- NEW PRODUCTION FORGE SUCCESSOR (only engine pin to adopt): `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / tree `2c18327f79e330f2ed167067166ffd42d61b0849` / repository `moeendres-png/forge`
- Exact read-only successor checkout: `/tmp/ws62-forge-src-a9a95db` — VERIFIED (`git rev-parse HEAD` = successor; `HEAD^{tree}` = successor tree; `git log --oneline -1` = WS59 remediation commit on top of old pin).
- WS59R qualification head `c8f30969fd002b06b5e962afac67d801cf090977` and terminal `85f03824229cbfc0a93bdf85d3554a92b5351884` are NOT engine pins (verified present in successor checkout as post-successor test/evidence commits; production files byte-identical between `a9a95db` and `c8f30969`).

## Policy authority

- Current Foundry policy authority: `c1a760af21469fc1358dbdb9b821f79dcdfaf2db` / tree `061135e2a90fb1b1a6289e6ea508db4da132bd9c`
- Canonical tools (read-only): `/tmp/csn-policy-main-c1a760a/tools/foundry/state.py` and `safe_push.py` (accessed via subprocess; no hand-authored state).

## WS59/WS59R accepted facts (inputs, not re-adjudicated here)

- A04 engine remediation PASS.
- C01 bounded PASS: variant enumeration DIRECTLY_VERIFIED; alternate-cost selection DIRECTLY_VERIFIED; target callback DIRECTLY_VERIFIED; target binding DIRECTLY_VERIFIED; hidden pitch choice TECHNICALLY_CONFORMANT/NOT_RUN; payment/life/exile NOT_RUN; resolution/counter outcome NOT_RUN.
- G04 engine-native concession seam PASS (`PlayerController.canConcede()` / `concede()`).
- Behavior credit remains 0/107.

## Standing state (preserved exactly)

- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `PRODUCTION_PROVIDER = NOT SELECTED`
- `BEHAVIOR_CREDIT = 0/107`
- `FULL107 = NOT_RUN`
- Global current-main manifest `config/rules_engines.json` and Docker/H4 authority are OUT OF SCOPE (never repinned here).
- Forge source remains strictly READ-ONLY. No engine edits. No main repin.
