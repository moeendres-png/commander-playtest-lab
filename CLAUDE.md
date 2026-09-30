# CLAUDE.md: Claude Code sessions on Commander Simulator Next

Durable instructions for Claude Code sessions (cloud and local) on this repository and its engine repositories
(`moeendres-png/mage`, `moeendres-png/forge`).
- **Stable rules only.** No SHAs, counts or run IDs. Volatile state lives in the ledgers, handoffs and PRs.
- **`AGENTS.md` is the shared project policy.** Mission, Rules authority, Source Truth, evidence semantics, hidden information / RNG / replay, the reuse-first gate, persistence. Where it names OpenCode executors, the same rules bind Claude sessions, unless this file grants more.
- **`docs/PROJECT_MISSION.md`** governs player-count and architecture direction.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`. Claude never claims or changes either.

## 1. Authority

The owner granted Claude sessions broad technical autonomy. Default: act, don't ask. Ask only for the owner-reserved decisions below.

### Autonomous (no confirmation needed)

- **Find and fix simulator defects** in the Lab bridge (`engine-bridge/`) and the Forge bridge (`forge-protocol2-bridge/`). This covers bridge logic, decision projection, fail-closed gaps, leaver/concession handling, hidden-information projection and lane availability. Each fix is shipped as a fix PR with a fail-before / fix-after test.
- **Write probes, tests, findings docs and ledger rows.** Choose finding numbers as described in §4.
- **Lab PRs Claude opened: open, update and merge them** once the merge gate in §2 holds.
- **Engine repositories (`mage`, `forge`): create donor branches and PRs.** Claude may merge its own follow-up PRs into a candidate *integration* branch (never `master`) when the change:
  - only adds tests,
  - or makes an unsupported path fail closed,
  - or fixes a defect proven by a fail-before test and a CR/Oracle citation.
  After such a merge, record the new candidate head on the candidate PR for the Coordinator. The Lab's pinned engine commits (`source_lock.py`, the XMage pin) stay unchanged.
- **Repository hygiene:**
  - close superseded PRs with a comment naming the successor, keeping the branch;
  - close fixed issues with evidence;
  - keep `docs/project_health_*/LEDGER.md` current;
  - fix CI/workflow defects;
  - add static gates, such as ratchets against forbidden shortcuts.
- **Coordination:**
  - comment on any PR or issue, including the owner's lane PRs, with findings or proposals;
  - post fact updates to the Coordinator tracker (#255);
  - file issues for defects in another lane's area.
- **Scheduling:** schedule check-ins, subscribe to PR activity, run long suites in the background.

### Reserved for the owner / Coordinator (ask, or put it in #255)

- Production Provider selection, Architecture Freeze, the decision slots in `docs/architecture_freeze_readiness_*/COORDINATOR_DECISION_SLOTS.md`.
- Evidence policy: what earns boundary credit (receipt rules, mechanism equivalence), FULL107 denominator changes, re-sealing a sealed boundary.
- Changing a Lab engine pin (XMage repin, Forge bridge evidence commit), or merging into the branch that holds a pinned evidence commit.
- A change to a *supported* Rules path of a candidate engine that alters game outcomes without a CR/Oracle-proven defect.
- Repository settings: branch protection, rulesets, secrets, workflow registrations.

### Never

- **No history rewriting.** No force push in any spelling, no rebase of shared branches, no `reset --hard` on pushed work.
- **No direct push** to `main`/`master`, and no committing while on them.
- **Branches:** never delete one that holds evidence or another lane's work.
- **Other lanes:** never push to another lane's active branch. Comment or open a PR against it instead.
- **Forbidden shortcuts** (AGENTS.md §2) are never allowed in production-reachable code: first/random option, default yes/no, silent skip, fabricated actions, outcome injection. `UNKNOWN != PASS`.
- **No secrets.** Don't read credential stores or tokens. Treat `Datenpaket_*` directories as the owner's private data: don't read them into commits, move them or delete them.

## 2. Merge gate for Claude-owned PRs

Merge (plain merge commit, `expectedHeadSha`) only when all of these hold:

1. **Reviews:** every review, review thread and comment on the **exact head** is read. Checks alone are not enough, and a green PR merged over an unread blocking review is a defect.
2. **CI:** every check on the exact head is green, including `h4-xmage` and `pb03-runtime`. Scope-skipped checks are fine.
3. **Drift adjudicated semantically.** If `main` moved since the tests ran:
   - merge `main` into the branch;
   - re-run the affected suites locally, and a full suite when production code changed;
   - push, and wait for CI again.
   - A textually clean merge can still break tests. A seat-order change once broke tests that nobody had adapted.
4. **Local full suite:** for production changes, the local full suite on the final tree has 0 failures and 0 errors.

After merging, reset the working branch to the new `main` and push it. Delete the check-in routine or re-point it.

## 3. How to work effectively here

- **Priorities.** Work that moves the project, in order:
  1. correctness defects in the lanes (wrong game outcomes, hidden-information leaks);
  2. lane-availability gaps (fail-closed paths that stop ordinary games);
  3. decision-class and multiplayer coverage;
  4. evidence and CI hygiene.
  Batch several probes into one PR to save CI cycles, and validate locally before pushing.
- **Probe discipline:**
  - Expected values come from Oracle text and the Comprehensive Rules, never from engine parity.
  - Every probe needs a control assertion, proving the scenario reached the decision under test, and an assertion that would change if the defect existed.
  - For fixes, show red before, green after, and a mutation check where cheap.
- **Leaver / concession rule** (`XmageFullGameDecisionController.DEPARTED_CANCELLABLE`):
  - A departed player's frame is never answerable.
  - A qualified class unwinds with XMage's own `HumanPlayer` no-response value (read it in the pinned engine source), unless that value would itself break a rule. Trigger ordering is the example: answer "none" so the departed player's abilities never reach the stack.
  - Unqualified classes fail closed. Qualify a class only with a probe showing the game goes on correctly at 4P/5P.
- **Commands and timing** (Lab engine bridge):
  - Targeted run, from the repo root: `mvn -o -q -f engine-bridge/pom.xml test -Dtest='ClassA,ClassB' -Dsurefire.failIfNoSpecifiedTests=false`.
  - The full suite takes about 25 minutes; run it in the background and read `engine-bridge/target/surefire-reports/*.txt`.
  - Never run two Maven builds on the same `target/` at once.
  - Twin replay: `-Dtest=XmageFullGameReplayTwinTest -Dtwin.seeds=4:SEED,... [-Dtwin.variant=1]`.
- **Commands and timing** (Forge bridge): `mvn -o -q -pl forge-protocol2-bridge -am test` takes about 27 minutes. Checkstyle only rejects unused and redundant imports.
- **Scenario helpers:**
  - `XmageMultiplayerScenario.start(...)` restores a board at turn 1 precombat main. It takes an optional per-seat library list.
  - `XmageActualCardCorpusTest` has the helpers for choose-by-name, target-amount, attack and payment.
  - Libraries can't be restored as objects; they fail closed with `UNSUPPORTED_ZONE`.
- **Where things live:**
  - findings: `docs/multiplayer_findings/F-NN_*.md`;
  - health ledger: `docs/project_health_*/LEDGER.md`;
  - boundary: `qualification/final-current-boundary-*` (sealed, not Claude's to re-seal);
  - provider blockers: `PROVIDER_BLOCKERS.json`;
  - Coordinator tracker: issue #255.

## 4. Conventions

- **Finding numbers are shared across parallel lanes.** Before using `F-NN`, check every remote branch:
  `git for-each-ref refs/remotes/origin --format='%(refname:short)' | xargs -I{} git ls-tree --name-only {} docs/multiplayer_findings/`.
  Take the next free number, and renumber at once if you collide.
- **Commits:** focused, with a message explaining the defect, the rule and the evidence. End every commit message with the attribution lines from the session's system reminder. Never put model identifiers in commits, PRs or code.
- **PR bodies:** English, structured as defect → rule → fix → tests (before/after) → validation, closing with the `ARCHITECTURE_FREEZE` / `PRODUCTION_PROVIDER` line.
- **GitHub comments** end with the Claude Code footer.
- **Talking to the owner:** they write German, so reply in German. Be concise: what was done, what it means, what is waiting on them.
