# Commander Simulation Foundry — Project Agent Instructions

These instructions apply repository-wide unless a deeper `AGENTS.md` or an active Workstream Contract adds stricter rules.

## Mission and authority

Build and qualify a practically usable full-rules Magic: The Gathering Commander simulator with high Rules fidelity, authoritative legal actions/costs/mana/stack/priority/targets/combat/triggers/replacement and continuous effects/SBAs/zones/Commander rules, principal-scoped hidden information, explicit RNG, semantic replay, multiplayer support, process isolation, fail-closed unsupported paths, and reproducible evidence.

Source Truth priority is:
1. newer explicit user instruction;
2. fresh repository/Git state and active Workstream Contract;
3. current immutable run/job/artifact evidence and exact code;
4. exact pinned external-engine state;
5. current official Magic Comprehensive Rules, Oracle, and rulings for semantic adjudication;
6. historical reports or chat summaries.

`UNKNOWN` is not PASS. `PARTIAL` is not FULL. A green workflow alone is not qualification credit.

## Rules / pilot boundary

The Rules Core owns legality and rule resolution. Pilots receive only actor/principal-scoped observations and authoritative legal Decision Options and make discretionary choices only.

Never introduce prompt/UI rules heuristics, a second hidden Rules Engine in a pilot/adapter, silent `first/default/random/pass/cancel/AI` fallback, manual outcome injection, card-name production hacks, or a construction/parsing-only substitute for production-reachable runtime evidence.

Unsupported production-reachable paths fail closed.

## Default execution routing

OpenCode + Muse Spark 1.3 Contributor Free is the default implementation plane for bounded repository engineering, test/fix loops, qualification harness work, evidence plumbing, repetitive systemic refactors, and long-running implementation campaigns.

Preferred Muse effort:
- `high` is the repository default and should be used for normal implementation;
- `xhigh` should be used for the hardest implementation work only when the current OpenCode model catalog actually exposes that exact variant;
- never invent or silently substitute an unavailable variant. If `xhigh` is unavailable, stay on `high`.

Muse is an implementation worker, not final authority for Magic rules, Architecture Freeze, final hidden-information/security admission, provider-vs-engine blame, or decision-critical qualification credit.

ChatGPT Work / Work chats are a secondary execution and review plane. Use them mainly for orchestration, independent review, decision-critical analysis, or capabilities that specifically require Work. Project policy is `WORK_CHAT_MINIMUM=TERRA_MEDIUM` when that configuration is available; do not intentionally use a lower Work configuration for substantive project work without explicit user approval.

## Muse data boundary — project data is broadly allowed

The privacy boundary is about personal/private data, not about restricting normal engineering context.

Muse/OpenCode may use any data, file, directory, tool output, repository, dependency, cache, environment information, or worktree that is genuinely relevant to Commander Simulator Next and is not personal/private data or a raw secret value.

Explicitly allowed project data includes:
- repository source, tests, contracts, fixtures, manifests, reports, evidence, artifacts, generated logs, stack traces, and build output;
- project configuration, including non-secret `.env` values and targeted project environment variables;
- Git metadata, branches, commits, diffs, worktrees, and repository-local automation;
- Maven/Gradle caches and configuration, Java/JDK/Maven/Gradle tooling, containers/devcontainers, CI configuration, and temporary build directories;
- vendored or separately checked out engine/upstream sources such as XMage/Forge when required by the active workstream;
- project-related external worktrees/directories and project-specific local tooling;
- web research and subagents used for project work, subject to the active workstream authority;
- Magic card names, Oracle/rules material, decklists, collection contents, owned-card counts, Commander/deck preferences, prices used for project decisions, gameplay scenarios, and similar MTG data the user has explicitly declared non-sensitive.

Do not artificially block project work merely because a relevant file is outside the current worktree or has a normally sensitive-looking filename. Determine whether the content is project-relevant and safe before exposing it to Muse.

## Personal/private data — forbidden for Muse

Do not intentionally read into model context, paste, attach, summarize, transmit, or expose personal/private data that is not required project material, including:
- residential/private addresses or precise private location;
- personal phone numbers;
- private personal email/chat contents, contact lists, calendar contents, or account/profile data unrelated to the project;
- government IDs and identity documents;
- banking/payment/billing, tax, insurance, medical, legal, employment, or similar private records;
- private photos and unrelated personal documents;
- browser profiles/history, password stores, credential stores, cookies, session databases, recovery material, and unrelated cloud-drive contents;
- sensitive personal data belonging to another person;
- unrelated files from Documents/Desktop/Downloads or other host locations merely because they are technically accessible.

Repository metadata that already belongs to the project may contain ordinary author names or commit metadata. Do not deliberately extract, aggregate, or surface personal contact details from it unless the project genuinely requires that information.

Do not perform broad host-data discovery such as whole-home scans, unrelated Documents/Desktop traversal, browser-profile inspection, credential searches, or mass collection of personal files.

## Secrets: local use is allowed; model disclosure is not

Project execution may require credentials, tokens, SSH keys, signing material, or other secrets for local tools. Local processes may use those secrets when required by the project and authorized by the active contract.

The raw secret value must not be intentionally rendered into Muse-visible prompts, model context, logs, summaries, evidence, or command output. Prefer credential helpers, environment injection, secret stores, or commands that consume a secret without printing it.

Examples:
- allowed: `git`, `gh`, Maven, Docker, or another project tool authenticates locally using an existing credential without printing the credential value;
- allowed: inspect a project `.env` for known non-secret configuration or extract only specifically required non-secret keys/values;
- forbidden: `gh auth token`, printing a private key, dumping a password manager, or sending a raw API token to Muse.

If a project file mixes useful configuration with raw secrets, expose only the required non-secret subset or a sanitized derivative. Do not make `.env` or similar filenames globally unusable; protect secret values, not harmless project configuration.

Read `docs/operations/AI_EXECUTION_AND_PRIVACY_POLICY.md` for the operational boundary.

## Filesystem and tool boundary

Operate purposefully on project-relevant paths. Access outside the active worktree is allowed when required for the project, including known project worktrees, dependency/engine checkouts, build caches, temporary build directories, and toolchains.

Do not use project permissions as a pretext to inspect unrelated personal host data. OpenCode tool permissions are defense in depth, not a complete shell sandbox. For the strongest guarantee, run Muse in a dedicated WSL/container environment that contains project material and required build caches but does not expose unrelated personal directories.

Targeted environment inspection for project debugging is allowed. Avoid indiscriminate full-environment dumps when a smaller query is sufficient, because environments may contain unrelated credentials or personal values.

## Workstream and Git discipline

Before material work:
- verify branch, HEAD, TREE, `git status`, active contract, and relevant persistent checkpoint;
- resume from the newest genuinely verified state;
- do not redo already-valid work without an invalidation reason.

Parallel workstreams require a fixed base, distinct branch, clear ownership, reproducible tests/evidence, and a completion handoff. Do not silently overwrite another workstream or mutate a canonical integration branch from an unrelated child scope.

Systemic engine gaps should be repaired systemically rather than by accumulating card-specific exceptions.

Local focused commits are encouraged for resumability. `git push`, force operations, destructive Git/filesystem actions, remote repository creation, paid services, or raw secret disclosure require the authorization specified by the active contract/user.

## Persistence and completion

Treat every agent/model session as interruptible. After each material validated milestone, persist enough state that a different provider can resume without reconstructing the conversation: exact branch/HEAD, objective, immutable inputs, changes, passing/failing commands, evidence identity, blocker classification, and exact next action.

Do not voluntarily stop at a technically remediable in-scope failure. Diagnose, repair, test, persist, and continue until the bounded objective is complete or a proven terminal blocker/authority boundary is reached.

For final handoffs report: Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN with evidence classification; Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.
