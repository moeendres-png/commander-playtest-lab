# AI Execution and Privacy Policy

**Status:** project operating policy
**Policy epoch:** 2026-09-08
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

## 2. Why the Contributor-Free boundary exists

The OpenCode Zen documentation states that the Muse Spark 1.3 Contributor Free endpoint is offered at heavily discounted/free pricing in exchange for permission to use prompts and completions to train future Meta models.

Therefore, treat every prompt, tool result, attached file excerpt, generated completion, and command output that reaches Muse as potentially training-eligible external data.

The rule is not “never use Muse.” The rule is “Muse gets project-safe data only.”

## 3. Data classification

### ALLOWED_FOR_MUSE

The user explicitly permits the following project information to be processed by OpenCode/Muse:
- source code and repository text intended for this project;
- public or repository-pinned upstream source;
- tests, fixtures, contracts, manifests, and non-secret build metadata;
- generated project evidence and logs after secret/PII screening;
- Magic card names;
- decklists;
- owned-card/collection contents and card counts;
- Commander/deck preferences;
- gameplay and simulator scenarios;
- MTG collection facts the user explicitly treats as non-sensitive.

The MTG allowance does **not** automatically allow unrelated financial, shipping, location, identity, or account data that may happen to appear beside a card purchase/collection record.

### FORBIDDEN_FOR_MUSE

Never expose the following to Muse/OpenCode Contributor Free:
- residential/private addresses or precise private location;
- personal phone numbers;
- government ID numbers or scans;
- banking, card-payment, billing, tax, insurance, legal, medical, employment, or similar private records;
- passwords, passphrases, recovery codes;
- API keys, OAuth tokens, bearer tokens, session cookies, SSH/private keys, signing keys, certificates containing private material;
- credential/password stores;
- personal browser profiles/history unless a separately sanitized project artifact is explicitly required;
- unrelated private email, chat, calendar, contacts, or cloud-drive contents;
- private photos or identity documents;
- files under host Documents/Desktop/Downloads or similar personal folders unless the user has explicitly copied a sanitized project input into the worktree for this task;
- sensitive data of third parties;
- any private local file merely because the agent can technically access it.

## 4. Operational controls

### Worktree-only default

Start OpenCode from the exact project worktree. Repository-native `read`, `edit`, `glob`, and related operations must stay inside that worktree.

Project OpenCode configuration denies `external_directory` access and denies common environment/key/credential files. Session sharing is configured disabled.

### Shell caveat

OpenCode permission rules are not a complete host sandbox. The OpenCode V2 documentation explicitly notes that shell commands execute with the host user's filesystem/process/network authority and that path arguments are only best-effort scanned.

Therefore `external_directory=deny` alone is not enough to guarantee that a model-driven shell process cannot access host files.

For the strict interpretation of “private PC documents must never land at Muse,” run Muse in an isolation boundary where those documents are not present at all.

Preferred order:
1. dedicated devcontainer/container with only the repository/worktree and non-sensitive build caches mounted;
2. dedicated WSL distro/user containing only project material, with Windows drive automount disabled;
3. ordinary WSL only when the host mounts contain no sensitive material accessible to the agent and the user accepts the weaker boundary.

Do not run the training-eligible agent directly in a broad personal home directory.

### Commands that must not be used to gather model context

Do not perform broad host reconnaissance or secret extraction, including equivalents of:
- whole-home `find`/`rg`/`grep` scans;
- `env`, `printenv`, or full process-environment dumps for model inspection;
- reading `~/.ssh`, browser profiles, credential stores, password managers, or unrelated dotfiles;
- `gh auth token`, credential-helper dumps, cookie databases, cloud CLI credential files;
- copying unrelated host files into the repository just so Muse can read them.

Build tools may use credentials internally only when the credential value itself is not rendered into model-visible output. Prefer scoped credential helpers/secrets mechanisms rather than plaintext files.

## 5. Sanitization rule

If an otherwise useful project log contains a secret or forbidden personal value, create a sanitized project-local derivative **before** giving it to Muse.

A valid sanitized artifact:
- removes the original value rather than merely hiding it visually;
- preserves only the technical fields needed for debugging;
- is checked for accidental secrets/PII;
- records that it is a sanitized derivative when that matters to evidence provenance.

Never ask Muse to perform the first-pass redaction on raw forbidden data, because sending the raw data would already violate the boundary.

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

From the current worktree:

```bash
cd ~/code/commander-playtest-lab-muse-ws49
./scripts/open-foundry-opencode2.sh
```

or directly:

```bash
opencode2 --standalone ~/code/commander-playtest-lab-muse-ws49
```

The full-screen TUI is the same class of interface shown in the project screenshot. Verify the footer shows the Foundry implementer, Muse Spark 1.3 Contributor Free, and `high` before starting substantive work.

If `xhigh` is actually present for the current Muse catalog, use the TUI variant selector/cycle for the hardest work. If it is absent, stay on `high`.

Existing sessions may retain their previously selected agent/model rather than adopting a newly configured default. For an old session, explicitly verify the footer before continuing.

## 9. Version boundary

This repository configuration targets **OpenCode V2**, consistent with the project handbook. OpenCode V2 is currently a separate beta CLI (`opencode2`) and its configuration schema differs from OpenCode V1.

Do not silently convert the V2 `agents`/`permissions` schema to V1 `agent`/`permission` syntax. If the project later standardizes on V1 or V2 reaches stable and changes schema, re-verify current official documentation before migrating configuration.
