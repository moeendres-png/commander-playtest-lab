# Commander Simulation Foundry — Muse Data Boundary

**Status:** binding operational policy for OpenCode + Muse Spark 1.3 Contributor Free.

This document is subordinate to the newest direct user instruction, `AGENTS.md`, the active Workstream Contract, and fresh repository Source Truth.

## 1. Purpose

Muse Spark 1.3 Contributor Free is the Foundry's primary bounded implementation worker. It must be able to use everything materially required for project engineering.

The boundary therefore protects **unrelated personal/private data and raw credentials**, not ordinary Foundry project information.

Do not treat project data as sensitive merely because it belongs to the user or is locally stored.

## 2. Explicitly allowed project data

Muse may receive, inspect, search, transform, test, and reason over all project-relevant technical material, including:

- Commander Simulation Foundry repository source, tests, scripts, schemas, docs and configuration;
- qualification contracts, immutable materializations, fixtures, runtime evidence, traces, logs, build artifacts and machine-readable results;
- Forge, XMage, Manabrew, phase.rs, Arcana, Argentum and other engine/provider source or build trees needed for current research/implementation, subject to their license/process constraints;
- local build caches and generated project artifacts when useful for diagnosis;
- Magic card names, Oracle/card metadata, decklists, owned-card inventories, collection information, matchup/deckbuilding data and other MTG-specific data supplied for this project;
- public technical sources and current primary-source research;
- project-specific non-personal settings and metadata necessary to compile, test, debug, qualify or reproduce the simulator.

The user's MTG cards, decks, collection and owned-card information are explicitly **not sensitive for this Muse policy**.

Project data must not be withheld merely because it is detailed, proprietary-looking, historical, machine-generated or large. Source Truth and scope rules still determine whether it is authoritative.

## 3. Personal/private data that stays outside Muse context

Do not deliberately send, search for, quote, persist, or expose unrelated personal/private information such as:

- home/postal addresses;
- private telephone numbers;
- personal email addresses when they are not materially required for repository operation, and especially private email message content;
- private calendar/contact/address-book data;
- private chats or unrelated conversation exports;
- government identifiers, banking/payment information or unrelated account records;
- browser profiles, saved passwords, personal browsing history or personal documents unrelated to Foundry;
- comparable information whose primary purpose is to describe or identify the user as a private person rather than the project.

Normal repository metadata, public GitHub identities, commit SHAs, branch/PR data and technical attribution may be used when required for Source Truth. Do not unnecessarily surface personal contact details from such metadata.

If a file mixes required Foundry data with unrelated personal/private data, prefer a project-only/sanitized view when practical. Do not block the entire engineering task if the required project information can be accessed without exposing the personal portion.

## 4. Raw credentials: may be used indirectly, not exposed

Credentials are operational secrets rather than project evidence. They may be necessary for project tooling, but the model does not need to see their raw values.

Examples:

- passwords;
- API keys;
- access/refresh/bearer/session tokens;
- OAuth secrets/cookies;
- SSH/GPG/private keys;
- cloud/service credentials;
- secret-bearing `.env` files;
- password-manager exports.

Policy:

1. Muse may run project tools that use already-configured authentication or inherited environment credentials.
2. Muse may invoke authenticated Git/provider/build/test workflows when the credential value itself is not printed into model context.
3. Do not inspect, echo, dump, copy, commit or persist raw credential values.
4. If a credential itself must be created/rotated/read/edited, perform that credential-management step outside the Muse model context, then let Muse continue using the configured tool normally.

This distinction is important: **credential use is allowed when needed for the project; credential disclosure to Muse is not required or desired.**

## 5. Workspace and external-engine access

Muse should normally work in the active Foundry checkout/worktree, but it may also access project-related external source/build trees required for the current task.

`opencode.jsonc` explicitly allows common Foundry and engine checkout families and approval-gates other external directories rather than denying them globally.

A new external path is acceptable when it is genuinely project-related. Do not approve unrelated personal directories merely for convenience.

## 6. Search and inspection

Normal engineering search must remain available.

Muse may use:

- OpenCode `grep`;
- `git grep`;
- `rg`/`grep`/`find`/`sed`/`awk` and equivalent project inspection tools;
- normal file reads within project-relevant trees.

Do not deliberately redirect those tools into unrelated personal locations or credential stores.

## 7. Shell and tooling

Muse needs ordinary shell autonomy for real coding work, including:

- Python/Java/Maven/build tools;
- repository scripts;
- source search and text processing;
- dependency/source acquisition;
- compile/test/fix loops;
- evidence generation;
- local checkpoint commits.

Do not weaken project execution merely to avoid normal shell use.

Remote/destructive Git and filesystem actions remain approval-gated by `opencode.jsonc`.

Environment/credential dump commands remain denied because they are rarely required for engineering and can expose unrelated secrets. Already-configured credentials can still be consumed indirectly by the tools that need them.

## 8. Fail-closed rule for personal data / raw credential disclosure

If a subtask would require Muse to inspect unrelated personal data or reveal a raw credential value:

1. stop only that disclosure path;
2. use an authenticated tool, sanitized input or non-Muse credential-management step instead;
3. continue all independent project work;
4. do not reinterpret the privacy boundary as a simulator/qualification blocker unless the project truly cannot proceed without disclosure.

The privacy boundary is not a reason to withhold ordinary project source, evidence, logs, card data or engine code.

## 9. Known limitation: OpenCode permissions are not a hard OS sandbox

OpenCode permissions are defense in depth, not an operating-system isolation boundary.

A coding agent that can execute repository code shares substantial authority with the Unix account running that code. Therefore policy and workspace discipline remain necessary even when file patterns are denied.

For Foundry this means:

- normal project engineering remains enabled;
- unrelated personal files should remain outside project workspaces;
- raw credentials should be consumed by configured tools without being printed;
- if a future task requires a hard confidentiality guarantee, use a dedicated OS user/container/sandbox that mounts only the required project trees.

Do not claim `PERSONAL_DATA_ISOLATION = PASS` solely because `opencode.jsonc` parses successfully.

## 10. Practical review checklist

Before substantial Muse work, verify:

- the active task is a Foundry engineering task;
- required project/engine data is available rather than unnecessarily blocked;
- prompts/evidence do not contain unrelated personal data;
- raw credentials are not being printed or persisted;
- project-related external paths can be accessed or approved;
- normal search/build/test/debug tooling remains usable.

At handoff, report only genuine privacy blockers. Ordinary project data access is expected and allowed.
