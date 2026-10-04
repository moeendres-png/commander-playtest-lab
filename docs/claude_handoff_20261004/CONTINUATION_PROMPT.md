# Continuation prompt — Claude lane (#441 / #255), Commander Playtest Lab

> Paste the block below into the continuing Claude session. Fresh GitHub state outranks
> every statement in it. Re-verify each claim before acting on it.

---

You continue the Commander Playtest Lab pre-Freeze campaign as the **sole writer of the
Claude lane**:
- #441 (final pre-Freeze evidence closure), with its Forge/XMage residual-mechanism work;
- the #255 eligibility packet.

Work autonomously and end to end. Escalate to the Owner only for real architecture, scope, policy, risk-acceptance or irreversible decisions.

## 0. Start-up (always first)

1. Read `AGENTS.md`, `CLAUDE.md`, the execution-authority document `AGENTS.md` names, and `docs/claude_handoff_20261004/README.md` on branch `handoff/claude-local-evidence-20261004` (it is not merged).
2. Fresh-lock before any mutation:
   - `git fetch` on all three repos;
   - list open PRs and issues in `moeendres-png/commander-playtest-lab`, `moeendres-png/mage` and `moeendres-png/forge`;
   - read the latest comments on #441, #255 and #479.
3. Re-check ownership. If another session has posted a newer writer note on #441 or #255, do not write in that lane; coordinate instead. **Single active writer, baton passing, no collisions.**

## 1. Hard boundaries

- **Codex owns the whole CI / check / gate lane (#479).** That covers:
  - Lab #490, #492, #512 and #526;
  - Mage #493–#497 with PRs #43, #44 and #45;
  - Forge #498–#504 and #528 with PRs #18, #20 and #21.

  There you make **no changes, pushes or merges**. You only add evidence or review read-only. New write work needs an explicit baton from the Owner.
- **D17:** the in-JVM residual risk is **not** accepted. Codex pursues the safe solution.
- **Global non-claims, never change them:**
  - `PRODUCTION_PROVIDER = NOT_SELECTED`
  - `ARCHITECTURE_FREEZE = NOT_CLAIMED`
  - `PRODUCTION_REPOSITORY = NOT_CREATED`

  The #255 packet presents per-candidate eligibility evidence. It **never selects** a provider.
- **Evidence discipline:**
  - UNKNOWN ≠ PASS. LOCAL_OBSERVED is never credit. Only PB-03 on an exact head and a sealed epoch give credit.
  - Never fabricate options or defaults. Fail closed.
  - Never map a record family to an engine surface silently: semantic bindings need either a reviewed sibling precedent or Coordinator adjudication.
  - Rules questions are decided by the CR text, not by engine behaviour.
- **Git safety:**
  - No force push, no `reset --hard`, no `clean -fd`, no history rewrite, no pushes to main/master.
  - Merge the base INTO branches. Do not delete other agents' worktrees or branches.
  - Commit trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` plus your `Claude-Session:` line.
  - Every GitHub comment ends with the Claude Code footer.
  - No model identifiers go into repository content.
- **CI:**
  - `ci-definition-integrity-shadow` is red **by design** (CI-02). Never weaken it. Comment once per PR that it is not the PR's failure.
  - Codex review may be usage-limited. Its P1/P2 findings are bug reports, so verify and fix them.
- **No local-only terminal state.** Every material artifact ends up in one of four states:
  - PERSISTED (pushed);
  - REPRODUCIBLE_AND_DOCUMENTED;
  - INTENTIONALLY_DISCARDED;
  - BLOCKED (recorded on GitHub).

  Checkpoint to #441 after each milestone. When budget is low, do STABILIZE → PERSIST → VERIFY → HANDOFF.

## 2. State at handoff (2026-10-04, verify fresh)

- **Lab main:** `5583d687`. Today's merges:
  - #523, #524 (PILOT_CHOICE), #525 (loyalty + PILOT_CHOOSE_ABILITY), #527 (scripted pregame; PILOT_MULLIGAN UNKNOWN by design).
  - XMage mid-game lane local regression: 66/66 rows verified.
- **Forge free-mulligan tuck fix.** Two branches exist:
  - the writer's `hardening/forge-free-mulligan-tuck-20261004`;
  - a superseded reference, `hardening/forge-bridge-free-mulligan-tuck-20261004`, which has a 2P owed-card test.

  Land **one** of them as a Forge PR into `claude/forge-unified-successor-20260929`. Gate it on its exact-head Forge CI (Java 17/21, iOS) plus the full local `forge.bridge` suite. Then re-pin the Lab `secondary_engine.bridge_source` and `engine_identity_pb09.bridge_source` only, never the Rules-Core `commit`. Follow Lab commit `9defd733`: a successor source lock, an impact adjudication, a pb09 identity test update and the SHA256SUMS. Delete the superseded branch afterwards.
- **Blocker: epoch sealing.**
  - GitHub artifact downloads (`*.blob.core.windows.net`) are denied by this environment's network policy. Read the environment documentation (`read_documentation`, `environment.network`) and ask the Owner to allow the host.
  - Once it is allowed, seal the current-boundary epoch from the PB-03 run of the newest main into `qualification/current-boundary-epochs/<epoch>/`, using the a3bf338c pattern.
  - Inspect the replay-twin rejection ("not bound to this column and runner").
  - Build the **per-candidate AF00–AF11 matrix** and the **#255 eligibility packet**.

## 3. Pending decisions (ask the Owner/Coordinator; do not decide yourself)

1. **#441 comment 5979655574.** PLAYER_COUNT_2P–5P and WS05-CMD-START-2 are credited PASS on the generic lane without record decks or construction equality. Options: (a) downgrade, (b) keep as an adjudicated limitation, (c) build a generic-lane construction proof. Recommended: (a) now, then (c).
2. **#441 comment 5979206791, errata:**
   - E1: a known library top card without `deck_state`;
   - E2: scry is a card selection, not `choose_use`;
   - E3: PILOT_PILE `revealed` objects with Fact or Fiction still on the stack.
3. **WS05-MP-TURN-3/5:** Nexus of Fate is requested in the graveyard against its own text, and the extra turns contain combat the record never specifies. See `docs/af456_xmage_residuals_20261003/README.md`.
4. **WS05-CMD-MULL-2/4:** round 1 only; Forge's LondonMulligan decision order (#441 comment 5981490500). **RNG_RULES_TAPE:** contract v1.0.20 erratum. **MICRO_LAYERS:** semantic adjudication.

## 4. Autonomous work queue, highest value first

1. Finish the Forge free-mulligan fix, its PR and the Lab re-pin (section 2), and drive them to green and merged.
2. Once the network is unblocked, do epoch sealing, then the per-candidate AF matrix, then the #255 packet. Post the packet on #255 as eligibility evidence only.
3. **Forge ScenarioBootstrap capability program.** Batch it into Forge bridge PRs, each followed by one Lab re-pin. Local baseline: 20 rows attempted, 12 observed, 7 `UNSUPPORTED_DIMENSION`. In order of rows unlocked:
   - stack injection, or a declared causal-stack route like XMage's;
   - combat_state and combat-step temporal points;
   - mid-cast cost state;
   - adopting the shared mid-game selector surface. The selectors live in `midgame_rows.py`; do not build a second generic selector.

   Re-run `forge_scenario_lane.execute_and_persist` locally after each batch, and classify every residual with its first missing mechanism.
4. **Option (c), only after the decision:** a generic-lane constructed-state proof on both providers. This restores PLAYER_COUNT/START-2 credit and lets PILOT_MULLIGAN pass.
5. Apply adjudicated errata, then implement the affected rows (PILOT_CHOOSE_USE, NEGATIVE_DEFAULT_YES_NO, PILOT_PILE, MP-TURN-3/5, MULL-2/4) with wrong-reason controls.

## 5. How to work

- **For every row change:**
  - make a local engine run through the real producer;
  - add wrong-reason controls (another object, another player, another question, a second ask, another amount, an unscripted or unoffered answer);
  - run ruff, ruff format, mypy and the qualification tests;
  - for Java, run the full bridge suite;
  - before pushing, re-read your diff adversarially.
- **Engine bridge changes:**
  - update the capability manifest, and any fail-closed tests that used the old boundary as their example;
  - run the full mid-game row regression (about 60 min) before pushing a restoration change.
- **Toolchain:** Python ≥ 3.12 venv. Engine setup is in the handoff README "Reproduction" section, including the isolated m2, absolute bridge workspace paths, Xvfb for Forge, and building Forge with `-pl forge-protocol2-bridge -am`.
- **Disk:** the allowance is limited; clean only your own reproducible build outputs.
- **PRs you open:**
  - subscribe to their activity and drive them to green;
  - answer every review thread, fix the root cause, and resolve the threads you addressed;
  - post the shadow-check note once per PR;
  - merge under the merge discipline, or let the Owner's auto-merge do it.

Begin with step 0, then section 4 item 1.
