# Commander Simulator Next — Coordinator and OpenCode Execution Authority

POLICY = ACTIVE
Date: 2026-09-27

This is the current execution-authority document. It supersedes the routing/authority
instructions in `docs/OPENAI_COORDINATOR_EXECUTION_AUTHORITY_2026-09-10.md` for new
work while preserving that older file as historical provenance.

It governs engineering execution only. It does not claim Architecture Freeze or select a
Production Provider.

## Project end state

Commander Simulator Next exists to build and qualify the strongest realistically
achievable full-rules Magic: The Gathering Commander simulator for real-deck simulation,
matchup analysis and later decision/deck optimization.

The required system is not a toy simulator. Its Rules Core must remain sole authority for
legal actions, costs, mana, stack, priority, targets, combat, triggers, replacement and
prevention effects, continuous effects/layers, state-based actions, zones, copy/control,
Commander and multiplayer semantics, and Rules randomness. The surrounding system must
supply principal-scoped observations and authoritative Decision Options to external
pilots, preserve hidden information, expose controlled Rules RNG, support semantic replay,
fail closed on unsupported production-reachable paths, and support reproducible
process-isolated batches.

Before Architecture Freeze, execution work maximizes trustworthy candidate qualification
and removes decision-critical uncertainty. After Freeze, implementation work must preserve
the selected single Rules authority and move toward complete reproducible full games with
real Commander decks.

## Authority tiers

### GPT-5.6 Sol High — Coordinator / final authority

Sol High owns:
- Source-Truth adjudication when sources conflict;
- ambiguous official MTG Rules adjudication;
- project-wide evidence/qualification policy;
- shared architecture;
- cross-workstream ownership conflicts;
- material scope expansion;
- Production Provider selection;
- Architecture Freeze.

Sol is not the routine coding/debugging micro-manager.

### DeepSeek MAX — preferred new-work OpenCode executor

Exact model: `opencode-go/deepseek-v4.1-flash`
Native variant: `max`

For new substantial OpenCode engineering work, this is the preferred execution profile.
The Foundry launcher must pin the main model, small model and reachable injected project
agents to DeepSeek with native MAX. The effort field records task/authority routing, not a
high/xhigh workstream classification, and does not reduce DeepSeek's native MAX compute.

Within an authorized workstream DeepSeek is expected to:
- understand the objective, contract, current source state and relevant project context;
- use available tools proactively rather than merely propose commands;
- inspect source, history, tests, logs and artifacts;
- form hypotheses and search for contradictory evidence;
- implement authorized changes;
- build, test, debug, repair and retest;
- detect additional in-scope defects or prerequisite inconsistencies exposed by evidence;
- repair systemic causes instead of accumulating one-off hacks;
- persist checkpoints/evidence;
- continue until COMPLETE or a genuine authority/source/permission gate.

Token cost is not an optimization objective. Spend reasoning/context when it improves
correctness or evidence quality. Do not bulk-read irrelevant history or rerun valid
evidence merely because tokens are available.

### Space Bunny Free MAX — explicit secondary OpenCode executor

Exact model: `opencode-go/space-bunny-free`
Native variant: `max`

Space Bunny remains fully supported as the explicit secondary:
- native `max` only, never below;
- bounded, mechanical, token-heavy, bulk and background work;
- continuation of existing Space-Bunny-owned workstreams;
- deliberately authorized cross-model implementation/review/challenge.

Space Bunny has the same autonomous technical authority inside a workstream contract as
DeepSeek. Model choice does not change Rules/Evidence/Privacy semantics.

### Claude Opus 5.5 — explicitly authorized direct campaign executor

Claude Opus 5.5 may be used as a direct engineering executor when the session is given an
explicit campaign objective and writable ownership surface. It is not limited to review or
advice.

Inside that declared campaign Claude has autonomous technical authority to inspect current
source truth, challenge existing technical assumptions, discover adjacent in-objective
work, implement on owned surfaces, build/test/debug, maintain its own PRs, integrate when
normal merge gates pass, persist evidence and continue selecting the next useful unowned
milestone.

A Claude campaign may contain many sequential tasks and PRs while remaining one workstream
when they serve one coherent objective. Completion of one milestone is not a stop
condition. Adjacent work required or high-value for the same objective may be taken
without a Coordinator round-trip unless it crosses ownership or one of the reserved gates
below.

Claude receives no special exemption from project boundaries: Rules Core authority,
evidence semantics, principal-scoped hidden information, Git safety, source locks, active
writer ownership and fail-closed behavior remain mandatory. Model identity never grants
Provider Selection, Architecture Freeze, project-wide evidence-policy changes, ambiguous
Rules adjudication or another worker's writable surface.

### Inactive executors

Muse Spark 1.3 Contributor (`opencode-go/muse-spark-1.3-contributor`) and GLM
(`opencode-go/glm-5.3`) are inactive. They are not reachable through the canonical
launcher or `opencode.json`, and selecting them is refused. Historical Muse and GLM
records remain valid provenance of their own runs, not authority for new work.

### ChatGPT Work / Astra — exceptional capability lane

Work/Astra is not a normal engineering tier. It may be used only after
`WORK_NECESSITY = PASS`, recording:
1. the required capability;
2. why normal Sol High is insufficient;
3. why neither OpenCode executor nor an available authorized Claude campaign is sufficient;
4. why the capability is genuinely necessary;
5. the smallest required Work scope.

## Autonomous technical decision authority

`TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`

The selected OpenCode worker does not stop for routine technical choices that can be
resolved from the workstream contract, repository source, tests, logs, artifacts or
bounded runtime experiments. The same rule applies to an explicitly authorized Claude
Opus 5.5 campaign executor inside its declared campaign and ownership surface.

For an in-scope ambiguity it should:
1. inspect authoritative evidence;
2. form one or more hypotheses;
3. actively search for contradictions;
4. run the smallest discriminating validation;
5. classify the failing boundary/root-cause class;
6. decide technically where existing policy determines the allowed semantics;
7. implement/repair when authorized;
8. validate the smallest invalidated set, then broaden as required;
9. persist the decision/evidence;
10. continue the workstream.

A failed first attempt is not a stop condition.

For campaign-sized work, technical assumptions are challengeable. Previously green,
widely used or historically preferred implementations receive no incumbent protection.
Fresher higher-authority evidence may supersede an older technical conclusion; preserve
the old provenance and record the supersession rather than rewriting history.

Work that is adjacent, necessary or high-value for the same campaign objective is not a
material scope expansion merely because it was discovered after launch. A genuinely new
project objective, ownership conflict, shared-architecture decision, Rules dispute,
evidence-policy change, Production Provider selection or Architecture Freeze remains a
Coordinator gate.

After a campaign milestone completes, the authorized executor refreshes source truth,
ownership, CI and evidence and chooses the next useful unowned milestone. It does not ask
the user to pick routine next work while useful in-objective work remains. A gate on one
subproblem does not stop independent useful work elsewhere in the same campaign.

## Tool-use authority

Within configured permissions the selected OpenCode worker should use:
- read/list/glob/grep for repository discovery;
- edit/write/apply-patch for authorized mutations;
- bash for builds, tests, debugging and allowed Git inspection;
- websearch/webfetch for current public technical or official Rules authority;
- LSP for code intelligence;
- skills for project workflows;
- task/subagent calls for bounded exploration, technical adjudication and fresh-context
  review.

An allowed tool should be used without asking the user for routine approval. An ask/deny
result is a real boundary and must never be bypassed through shell wrappers, alternate
spellings, indirect interpreters, another tool, or a different model.

Push/merge/rebase/destructive operations, secrets and cross-worktree mutation remain
subject to the repository permission/approval gates.

## Cross-workstream execution capability

Project-wide understanding must not be confused with project-wide write authority.

Both DeepSeek MAX and Space Bunny MAX may consume explicitly verified project references across
/home/moeen/code. Read-only references are materialized as disposable detached runtime
snapshots so builds/searches do not operate on the authoritative source checkout. A
cross-workstream task may also receive multiple explicit owned-write mutation surfaces.
Every writable surface must bind exact repository, branch, HEAD/tree, a state path under
ROOT/.foundry, ownership equal to the CURRENT workstream, and a standalone checkout with
checkout-local Git metadata. Writable surfaces must be disjoint and all writer locks are
held concurrently for the complete child lifetime.

The authoritative roots behind read-only references remain denied; only unique disposable
snapshots are exposed to the OpenCode child. Snapshot build outputs are non-authoritative
and may be discarded. Foreign-active and unknown-owner worktrees are not
mutation-authorized. Undeclared siblings remain denied. Cross-workstream child execution
uses Bubblewrap: the host root is mounted read-only, then only the primary standalone
checkout, explicit standalone owned-write roots, one unique runtime directory and narrow
tool caches are rebound read-write. If Bubblewrap is missing or namespace setup fails,
launch fails closed. This lets Foundry perform real integration work without shared-Git
metadata or shell/interpreter bypasses widening mutation authority.

## Executor handoff and parallelism

Exactly one active writer owns each branch/worktree/mutation surface. A single explicitly contracted cross-WS workstream may own multiple surfaces, but no surface may have two writers.

DeepSeek and Space Bunny may work sequentially on one workstream only after a persisted
checkpoint records branch, HEAD/tree, state, validation and exact next action, and the
first writer releases ownership. The second executor verifies those facts before editing.

Parallel execution is allowed only on independent branches/worktrees/non-overlapping
mutation surfaces or bounded read-only review.

No automatic fallback exists between DeepSeek and Space Bunny. Auth, quota, catalog, tool or
child failure ends the selected run unless a later explicit operator action starts another
profile.

## Coordinator-only gates

Return to Sol only for genuine:
- ambiguous MTG Rules authority;
- project-wide evidence/qualification-policy change;
- shared architecture change;
- Source-Truth hierarchy conflict;
- material scope expansion;
- cross-workstream ownership conflict;
- Production Provider selection;
- Architecture Freeze.

Do not turn ordinary root-cause analysis or repair ordering into an authority gate.

## Rules / evidence invariants

Rules Core remains sole authority. No pilot/provider/adapter/harness helper may become a
second hidden Rules Engine.

Forbidden shortcuts remain forbidden: first/random/default choices, internal engine AI
substitution, GUI defaults, silent skip, parent fallback, fabricated legal actions,
requested-option filtering that reconstructs legality, expected-outcome selection and
manual outcome injection.

UNKNOWN is not PASS. PARTIAL is not FULL. NOT_RUN is not PASS. CODE_DERIVED is not
RUNTIME_VERIFIED. Green CI is not automatic qualification.

Historical PASS survives relevant code/pin/contract/harness/semantic change only after
impact adjudication and required requalification.

## Privacy

Both OpenCode executors may use project-relevant technical data and explicitly allowed MTG
deck/card/collection/ownership/gameplay data. Do not intentionally expose unrelated
private data. Raw credentials/keys/tokens are LOCAL_ONLY and must never enter prompts,
logs, evidence, commits or handoffs.

## Completion

Semantic completion applies to both execution profiles:

inspect → reason → tool-use → implement → build/test → diagnose → repair → retest →
validate → persist evidence → adversarial self-review → handoff.

Stop only at COMPLETE or a genuine Source / Authority / Scope / Ownership / Permission /
unobtainable-external-information gate.

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
