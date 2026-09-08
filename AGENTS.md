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
- `high` is the repository default and must be used for normal implementation;
- `xhigh` should be used for the hardest implementation work only when the current OpenCode model catalog actually exposes that exact variant;
- never invent or silently substitute an unavailable variant. If `xhigh` is unavailable, stay on `high`.

Muse is an implementation worker, not final authority for Magic rules, Architecture Freeze, final hidden-information/security admission, provider-vs-engine blame, or decision-critical qualification credit.

ChatGPT Work / Work chats are a secondary execution and review plane. Use them mainly for orchestration, independent review, decision-critical analysis, or capabilities that specifically require Work. Project policy is `WORK_CHAT_MINIMUM=TERRA_MEDIUM` when that configuration is available; do not intentionally use a lower Work configuration for substantive project work without explicit user approval.

## Contributor-Free data boundary — mandatory

Muse Spark 1.3 Contributor Free may receive project data that is safe for an external training-eligible endpoint.

Explicitly allowed:
- repository source/code/contracts/tests;
- generated project logs/evidence after secret screening;
- Magic card names, decklists, collection contents, owned-card counts, Commander preferences, game/test scenarios, and similar MTG data the user has explicitly declared non-sensitive.

Never send, read for model context, paste, attach, summarize, or expose to OpenCode/Muse:
- home/private addresses;
- personal phone numbers;
- government IDs, identity documents, tax/legal/medical/employment records;
- banking/payment/account data;
- passwords, API keys, access tokens, cookies, session tokens, SSH/private keys, signing keys, recovery codes, credential stores;
- private email/chat contents unrelated to the repository;
- browser profiles/password stores;
- private photos or unrelated personal files;
- documents from the host computer that are not explicit project inputs;
- sensitive personal data belonging to any other person.

Do not run broad host-data discovery such as home-directory scans, credential searches, environment dumps, browser-profile inspection, or unrelated Documents/Desktop traversal.

Do not read `.env` or private-key/credential files. `.env.example` is allowed if it contains placeholders only.

If a task appears to require forbidden data, stop that data access, mark the dependency, and ask for a sanitized/project-local substitute. Do not guess or redact only after disclosure.

Read `docs/operations/AI_EXECUTION_AND_PRIVACY_POLICY.md` for the operational boundary.

## Filesystem boundary

Operate from the exact repository/worktree. Treat access outside the active worktree as denied unless the active Workstream Contract explicitly requires a known non-sensitive build/cache path.

OpenCode tool permissions are defense in depth, not a complete shell sandbox. For a strict privacy boundary, run OpenCode in a dedicated WSL/container environment that contains only project material and non-sensitive build caches and does not expose Windows personal drives/directories.

Do not use shell commands as a workaround around denied file permissions.

## Workstream and Git discipline

Before material work:
- verify branch, HEAD, TREE, `git status`, active contract, and relevant persistent checkpoint;
- resume from the newest genuinely verified state;
- do not redo already-valid work without an invalidation reason.

Parallel workstreams require a fixed base, distinct branch, clear ownership, reproducible tests/evidence, and a completion handoff. Do not silently overwrite another workstream or mutate a canonical integration branch from an unrelated child scope.

Systemic engine gaps should be repaired systemically rather than by accumulating card-specific exceptions.

Local focused commits are encouraged for resumability. `git push`, force operations, destructive Git/filesystem actions, remote repository creation, paid services, or secret disclosure require the authorization specified by the active contract/user.

## Persistence and completion

Treat every agent/model session as interruptible. After each material validated milestone, persist enough state that a different provider can resume without reconstructing the conversation: exact branch/HEAD, objective, immutable inputs, changes, passing/failing commands, evidence identity, blocker classification, and exact next action.

Do not voluntarily stop at a technically remediable in-scope failure. Diagnose, repair, test, persist, and continue until the bounded objective is complete or a proven terminal blocker/authority boundary is reached.

For final handoffs report: Source Lock; Work Completed; New Findings; Changes; Tests/Evidence; PASS/FAIL/UNKNOWN with evidence classification; Remaining Blockers; Outputs; Dependencies Unblocked; Exact Next Action.
