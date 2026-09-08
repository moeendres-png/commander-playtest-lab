# AI Execution and Privacy Policy

**Status:** project operating policy
**Policy epoch:** 2026-09-08 revision 2
**Scope:** Commander Simulation Foundry repository engineering, OpenCode/Muse execution, ChatGPT Work routing, and handling of local/user data.

This policy does not override a stricter active Workstream Contract, current Magic authority, or fresh repository Source Truth.

## 1. Execution routing

### Primary implementation plane

Use OpenCode with `Muse Spark 1.3 Contributor Free` for the majority of implementation work while the endpoint remains available.

Default effort is **High**. Use **XHigh** for particularly difficult long-horizon implementation only if the current OpenCode catalog exposes `xhigh` for this exact Muse model. OpenCode variants are model-specific; absence of `xhigh` is not an error condition and must not be worked around by inventing a variant. In that case remain on High.

Good Muse workloads include:
- bounded multi-file implementation;
- compilation/test/fix loops;
- engine adapters and provider plumbing after architecture decisions;
- qualification harnesses and evidence serialization;
- actual-card-driven regression expansion;
- systemic refactors with executable acceptance tests;
- repository exploration for technical implementation questions;
- long resumable campaigns with checkpoint commits.

Muse is not sufficient by itself for final Magic Rules adjudication, Architecture Freeze, final hidden-information/security admission, decision-critical provider/engine blame, or final qualification credit with high architectural blast radius.

### ChatGPT Work / Work chats

Work is secondary rather than the default implementation plane. Use it where it materially helps: orchestration, independent review, connected-app/browser workflows, decision-critical analysis, or tasks that require a stronger independent review layer.

User-selected project policy:
`WORK_CHAT_MINIMUM=TERRA_MEDIUM`

Use Terra Medium or a stronger available Work configuration for substantive project work. Do not intentionally downgrade below this floor without explicit user approval. This repository policy records the routing preference; it cannot itself change the user's ChatGPT product/model selector.

## 2. Core privacy principle

Muse Spark 1.3 Contributor Free is a training-eligible external model endpoint. The project should still use it aggressively for engineering, but the privacy boundary is **personal/private data**, not ordinary project data.

Operational rule:

> If information is genuinely needed to build, test, qualify, debug, reproduce, or operate Commander Simulator Next and is not personal/private data or a raw secret value, it may be used by Muse/OpenCode.

Do not reduce project capability by blanket-blocking harmless configuration, build metadata, logs, caches, worktrees, or tooling.

## 3. Data classes

### ALLOWED_PROJECT_DATA

Muse/OpenCode may process project-relevant information including:
- source code, repository text, contracts, Workstream state, ADRs, handoffs, tests, fixtures, manifests, generated evidence, artifacts, stack traces, and technical logs;
- public or repository-pinned upstream source and documentation;
- build/runtime configuration and non-secret `.env` values;
- targeted project environment variables such as engine/provider paths, Java/JDK/Maven/Gradle settings, test flags, and qualification configuration;
- Git branches, commits, diffs, worktrees, repository metadata, and automation;
- Maven/Gradle caches, package caches, temporary build directories, toolchains, containers/devcontainers, and CI data;
- external project worktrees or repositories such as XMage/Forge checkouts when required by the active task;
- project-related web research and project subagents;
- Magic card names, Oracle/rules material, decklists, collection contents, owned-card counts, Commander/deck preferences, gameplay scenarios, card prices used for project decisions, and other MTG collection facts the user has explicitly declared non-sensitive.

The MTG allowance does **not** automatically include unrelated shipping, billing, location, account, or identity data that may happen to appear beside purchase or collection records.

### LOCAL_ONLY_SECRET_DATA

Some project operations require credentials or secret material. These values may be used by authorized local tools but should not be exposed to Muse itself.

Examples:
- Git/GitHub credentials;
- API keys or bearer tokens;
- private SSH keys;
- signing keys;
- registry credentials;
- passwords or service credentials.

Allowed handling:
- a local command authenticates through an existing credential helper;
- a process consumes a secret through an environment variable or secret store without printing it;
- a build tool reads its credential configuration internally;
- Muse receives only the success/failure/result needed for the project.

Forbidden handling:
- printing a raw token/key/password into model-visible output;
- asking Muse to read a private key or password store;
- copying raw secrets into prompts, evidence, or committed files.

If a project `.env` or config file mixes non-secret configuration with secrets, expose the required non-secret subset or create a sanitized derivative. The filename itself is not a reason to block the whole file.

### FORBIDDEN_PERSONAL_DATA

Do not intentionally expose personal/private information that is not required project material, including:
- residential/private addresses or precise private location;
- personal phone numbers;
- private email/chat contents, personal contact lists, private calendar contents, or personal account/profile data unrelated to the project;
- government ID numbers or identity documents;
- banking/payment/billing, tax, insurance, medical, legal, employment, or similar private records;
- personal browser profiles/history, password stores, cookie/session databases, and private cloud-drive contents;
- private photos and unrelated personal documents;
- sensitive personal information belonging to third parties;
- unrelated host files merely because the tool can technically access them.

Ordinary repository author metadata may exist as part of project history. Do not deliberately mine or aggregate personal contact details from it unless that information is genuinely required for project operation.

## 4. Operational controls

### Project-relevant external paths are allowed

OpenCode may access paths outside the current worktree when the active task needs them, including:
- sibling project worktrees;
- engine/upstream source checkouts;
- Maven/Gradle/package caches;
- JDK/toolchain locations;
- temporary build/test directories;
- container mounts used for project execution.

Do not traverse unrelated personal directories or scan the full home directory without a concrete project reason.

### Shell and environment access

Shell access is part of the primary implementation workflow and should be broadly available for project work: builds, tests, Git inspection, worktree management, code generation, qualification tooling, containers, package managers, and diagnostics.

Targeted environment inspection is allowed when useful for project debugging. Prefer commands that query only the required variables or configuration. Avoid indiscriminate full-environment dumps because they can accidentally print credentials or unrelated personal values.

Subagents and web access are permitted when they serve the project and comply with the same privacy/authority rules.

### Destructive/external actions remain gated

The privacy relaxation does not weaken repository safety. Continue to require confirmation/authorization for materially destructive or external actions according to the active contract, including push/force/reset/clean/rebase/merge where applicable, remote repository creation/deletion, destructive filesystem operations, paid services, or intentional secret disclosure.

### Shell caveat

OpenCode permissions are not a full host sandbox. Shell commands run with the host user's process/filesystem/network authority, and path analysis is necessarily imperfect.

For the strongest practical guarantee that unrelated personal files never reach a training-eligible endpoint, prefer a dedicated project WSL/container environment that contains the repositories, worktrees, caches, and toolchains needed for the simulator but does not mount unrelated personal directories.

This isolation is a privacy hardening measure, not a requirement to cripple project tooling.

## 5. Sanitization rule

If an otherwise useful project log or configuration contains a raw secret or forbidden personal value, create or extract a sanitized project-local derivative **before** giving that material to Muse.

A valid sanitized artifact:
- removes the forbidden value rather than merely hiding it visually;
- preserves the technical information needed for debugging;
- is checked for accidental secrets/PII;
- records that it is a sanitized derivative when provenance matters.

Never ask Muse to perform first-pass redaction on raw forbidden personal data or raw secrets, because transmitting the raw value would already violate the boundary.

## 6. Source and qualification authority

Provider routing does not change qualification semantics.

Muse-generated code/evidence must still satisfy the project's evidence classes and gates. Muse does not promote `UNKNOWN` to PASS by reasoning alone. A Muse-on-Muse review is useful but is not independent model-family or official-Rules evidence.

For decision-critical Rules/Architecture conclusions, produce a complete review package and obtain the required independent adjudication.

## 7. Persistence and quota policy

Do not optimize around an invented Contributor Free quota. Use Muse generously for bounded engineering while it is available, but make interruption cheap:
- persist each material validated milestone;
- prefer focused checkpoint commits;
- keep branch-local workstream state when appropriate;
- retain exact commands/evidence identities;
- resume rather than reconstruct.

The Git checkpoint, not the conversation transcript, is the recovery unit.

## 8. Opening the project

For OpenCode V2, the committed project config selects `foundry-implementer` with Muse Spark 1.3 Contributor Free `#high` by default.

From a project worktree:

```bash
cd ~/code/commander-playtest-lab-muse-ws49
./scripts/open-foundry-opencode2.sh
```

or directly:

```bash
opencode2 --standalone ~/code/commander-playtest-lab-muse-ws49
```

Verify the footer shows the Foundry implementer, Muse Spark 1.3 Contributor Free, and `high` before substantive work.

If `xhigh` is actually present for the current Muse catalog, use the TUI variant selector/cycle for the hardest work. If it is absent, stay on `high`.

Existing sessions may retain their previously selected agent/model rather than adopting a newly configured default. For an old session, explicitly verify the footer before continuing.

## 9. OpenCode V2 permission strategy

The project config is intentionally permissive for normal engineering:
- repository read/edit/search: allowed;
- shell for project work: allowed;
- web access: allowed;
- subagents: allowed;
- external project directories: allowed;
- `.env` and environment access: not blanket-denied;
- session sharing: disabled.

Safety is enforced by project instructions plus explicit confirmation rules for destructive/external actions and by the personal/private-data boundary above.

OpenCode V2's own defaults ask before `.env` reads and external-directory access. This project overrides those defaults for the Foundry implementer so long-running work is not interrupted by harmless project configuration or dependency paths. The agent remains responsible for not reading unrelated personal data or printing raw secrets.

## 10. Version boundary

This repository configuration targets **OpenCode V2**. V2 uses ordered `permissions` rules with actions such as `shell`, `subagent`, and `external_directory`, and agent definitions under `agents`.

Do not silently convert this V2 schema to V1 syntax. Re-verify current official OpenCode documentation when the project upgrades OpenCode or changes its model/provider configuration.
