# WS228 Source Lock

Workstream: WS228 — Numeric Decision Boundary Preflight & S6 Implementation Design
Mode: RESEARCH ONLY. No S6 production changes in this workstream.

## Repository / branch

- Repository: moeendres-png/commander-playtest-lab
- Branch: ws228/numeric-boundary-preflight-20260915
- Worktree: /home/moeen/code/ws228-numeric-boundary-preflight (launcher-held)

## Audit base (immutable for WS228)

- WS223 commit: 48885e8e3c16ccdfd388a4378a5a05b6e81bb293
- WS223 tree: d02d6c0eb54b009c481cd79d642929011e9ce483
- Verified at session start: `git rev-parse HEAD` == audit base,
  `git rev-parse HEAD^{tree}` == expected tree, clean worktree.

## Read-only inputs (never mutated, never depended on unpublished state)

| Input | Commit | Role |
|---|---|---|
| WS220 audit | 1a6ffcdaa264bb64dbc32c9b32019092fc4a896b | F-RULES-02 + S6 primary authority (FINDINGS.json / SUCCESSOR_PROPOSALS.json / ACTION_GRAPH.json read via `git show`) |
| WS225 standing | 8b3ab80d07317f54debf913974eea91947ac0848 | Current-standing context input |
| WS226 terminal (post-lock, Coordinator-accepted) | fb156d2b4cf8c5c21d0c84e844a53160032c0992 / tree 52359f47eea7ddc1e4ec8187e89b67fa67d63616 | Delta-revalidation target; S6 base. Fetched from origin and identity-verified (HEAD and TREE match addendum exactly). |
| XMage engine pin | 1.4.61 (engine-bridge/pom.xml; local .m2 jars) | Native-semantics reference: HumanPlayer + Player interface + MultiAmountType bytecode |

Active siblings WS226 (before terminal publish) and WS227 were NOT consumed
while unpublished, per contract. WS226 was consumed only after the
Coordinator addendum published its terminal HEAD/TREE, read-only via
`git show` / `git rev-parse` / `git diff` against pinned SHAs.

## Policy flags

- ARCHITECTURE_FREEZE = NOT_CLAIMED
- PRODUCTION_PROVIDER = NOT_SELECTED
- PRODUCTION_CODE_MODIFIED = NO (only research/numeric-boundary/ws228/** touched)
- RULES_SEMANTICS_CHANGED = NO
- BEHAVIOR_CREDIT_CHANGE = 0
- FULL107 = NOT_RUN (explicitly out of scope; bounded validation only)

## Mutation surface (exclusive)

- research/numeric-boundary/ws228/** (outputs + probes/**)
- external Foundry state file (exact FOUNDRY_STATE_PATH)

Everything else (src/**, engine-bridge/**, tests/** outside the WS228
namespace, qualification/**, .github/**) is read-only in WS228. Verified by
final `git status` + diff inspection before publication.
