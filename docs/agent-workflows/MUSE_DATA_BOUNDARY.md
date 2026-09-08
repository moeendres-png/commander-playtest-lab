# Commander Simulation Foundry — Muse Data Boundary

**Status:** binding operational policy for OpenCode + Muse Spark 1.3 Contributor Free.

This document is subordinate to the newest direct user instruction, `AGENTS.md`, the active Workstream Contract, and fresh repository Source Truth.

## 1. Purpose

Muse Spark 1.3 Contributor Free is used as the Foundry's primary bounded implementation worker because it is well suited to long implementation/test/repair loops. It is **not** treated as a confidential-data processing boundary.

The project therefore distinguishes engineering data that may be sent to Muse from sensitive material that must remain outside Muse context.

## 2. Explicitly allowed data

Muse may receive and process:

- repository source code and tests intended for Foundry engineering;
- Magic card names, Oracle/card metadata, decklists, owned-card inventories, collection information, matchup/deckbuilding data, and other MTG-specific data supplied for this project;
- provider/engine source needed for the bounded engineering task when its license/process boundary permits it;
- qualification contracts, fixtures, runtime evidence, logs, traces, and build artifacts that do not contain forbidden sensitive data;
- public technical documentation and public web sources.

The user's MTG cards, decks, and owned-card information are **not classified as sensitive for this Muse policy**.

## 3. Forbidden data

Do not send, read, search for, print, copy, persist into prompts, or otherwise expose to Muse:

- passwords;
- API keys;
- access tokens, refresh tokens, bearer tokens, session tokens, cookies, OAuth secrets;
- SSH private keys, GPG private keys, private certificates, signing secrets;
- cloud/service credentials or password-manager exports;
- secret-bearing `.env` or local credential files;
- browser profiles, browser cookie stores, saved passwords, or unrelated browsing history;
- private email, calendar, contacts, private chat exports, or unrelated personal documents;
- banking/payment information, government/account identifiers, or other unrelated confidential personal/account data;
- secrets from another project merely because that project is reachable from the same WSL account.

If a file mixes allowed Foundry/MTG data with forbidden sensitive data, the file is forbidden until a sanitized copy containing only allowed information is produced outside Muse.

## 4. Fail-closed rule

If a Muse task materially requires forbidden data:

1. do not ask Muse to inspect it;
2. do not temporarily weaken the OpenCode privacy rules;
3. mark the affected subtask `MUSE_DATA_BOUNDARY_BLOCKED`;
4. route that subtask to an appropriate non-Muse authority/execution path or sanitize the required input first;
5. continue independent Muse-safe work when possible.

Sensitive data is never a valid reason to bypass the boundary for convenience.

## 5. Workspace boundary

The normal Muse workspace is the active Foundry checkout or an explicitly named sibling Foundry worktree.

`opencode.jsonc` denies arbitrary external-directory access and allows only the Foundry checkout/worktree family required for dual-lane continuation.

Do not keep unrelated secrets inside a Muse-enabled Foundry worktree.

If an external engine checkout is required for Muse, prefer placing it inside a gitignored area of the active Foundry worktree or another explicitly approved Foundry worktree rather than granting broad access to `~/code`, `$HOME`, or another project directory.

## 6. Search boundary

The built-in OpenCode `grep` tool is disabled for the Muse profile because it can search untracked workspace content.

Use `git grep` for normal tracked-source search. This has two advantages:

- the searched source is part of the repository source lock;
- untracked secret-bearing local files are not searched by default.

`glob` may be used for repository navigation, but discovering a forbidden filename is not permission to read its content.

## 7. Shell boundary

The Muse shell policy is allowlisted for common Foundry inspection/build/test/checkpoint commands and asks for unknown commands. Common credential/environment dump, arbitrary file-content dump, tunneling, shell-within-shell, and credential-management command classes are denied.

The agent must never use:

- variable assignment;
- shell indirection;
- a generated script;
- Python/Java/test code;
- a subprocess;
- encoded output;
- another agent;

as a way to obtain data that a direct OpenCode read would deny.

Approval of an unknown shell command is not an exception to the forbidden-data policy.

## 8. Environment hygiene

Start Muse/OpenCode from a terminal that does not intentionally export unrelated service secrets.

Do not put OpenAI, cloud, database, GitHub, email, payment, or other unrelated API credentials into the environment merely to make them convenient for unrelated tooling.

Where a workstream genuinely needs a credential for an external action, prefer performing that action outside Muse or through an execution path where the credential is not surfaced to Muse context.

## 9. Known limitation: OpenCode permissions are not a hard OS sandbox

OpenCode `read`, `edit`, `external_directory`, and shell permission rules are valuable defense in depth, but they do not create a cryptographic or operating-system isolation boundary.

A coding agent that can edit executable repository code and run tests shares the authority of the Unix account running those tools unless a stronger sandbox exists. Permission patterns can also have edge cases around shell indirection and command parsing.

Therefore:

- this repository policy does **not** claim that OpenCode configuration alone can make arbitrary same-user secrets technically unreachable under every adversarial condition;
- the project relies on keeping sensitive material outside the Muse workspace/context, restricting external paths, and narrowing shell access;
- if a task requires a hard confidentiality guarantee, run Muse inside a dedicated OS user/container/sandbox that mounts only the allowed Foundry workspace and required non-sensitive dependencies.

Do not claim `SENSITIVE_DATA_ISOLATION = PASS` solely because `opencode.jsonc` parses successfully.

## 10. Review checklist

Before a substantial Muse task, verify:

- active workspace is a Foundry checkout/worktree;
- no required input contains forbidden sensitive data;
- no broad external-directory exception has been added;
- no task prompt contains credentials/secrets;
- any logs/evidence expected to enter Muse context are sanitized;
- the task remains executable with the restricted shell/search profile.

At handoff, report any data-boundary exception request as `UNKNOWN`/blocked rather than silently weakening the policy.
