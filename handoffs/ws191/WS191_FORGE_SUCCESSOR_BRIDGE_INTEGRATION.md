# WS191 — Forge successor + H4F bridge integration

Status: `PREPARED / EXECUTION_NOT_STARTED`

This is the current Coordinator task packet that closes the unresolved WS90 `WAITING_FOR_WS89` dependency without rewriting WS90 history. It does not itself repin an engine, grant behavior credit, select a Production Provider, or claim Architecture Freeze.

## Source Lock

### Commander Lab authority

- Repository: `moeendres-png/commander-playtest-lab`
- Audit base / current `main` at issuance: `7725570b6b8690daed6e645dc1611f5e196de8c5`
- Tree: `8b926c73cf35468c6110d64615c5f5e863ac2aa1`
- Coordinator branch: `ws191/forge-successor-integration-coordinator-20260914`
- Sole machine-readable current engine-pin authority: `config/rules_engines.json`
- Current Forge Rules-Core pin: `a37a865a53280dd8ad6fad3384d69611e8c5a42f`
- Current Forge bridge/materialization source: `moeendres-png/forge@4753bb7c72ea60d653121e0bab989077b4009f9c`
- Current Forge bridge tree: `4cd539f1c56876590b8679dc1534d4632560c66d`
- Current selection truth: `provider_decision=NO_PROVIDER_READY`, `current_runtime.provider_selected=false`, `current_runtime.production_provider=null`.

### Corrected Forge successor authority

- WS90 corrected First-Wave package: `qualification/ws90-rqc3-corrected-first-wave-reissue/`
- WS90 readiness verdict: `FORGE_FIRST_WAVE_EXECUTION_READINESS = WAITING_FOR_WS89`
- WS90 required future Forge Rules-Core authority: `aa5c00aa32dfd40e213f223f8fd400c43daabb24`
- Forge tree at `aa5c00aa...`: `8aed9d8754a4b3bedfc57d2a2b47d997bcff4dec`
- `aa5c00aa...` is the clean WS76 successor carrying the corrected H01 Clone/Humility oracle and immediate-concession hardening. Fresh evidence on its WS77 line records H01 `3/3`, WS76 `5/5`, combined/regression `18/18`, and zero in-scope checkstyle violations; Full107 remains `NOT_RUN` and behavior credit remains `0/107`.

### Fresh lineage finding

Direct GitHub comparison at issuance proves:

- `4753bb7c...` is 16 commits ahead of `a37a865a...` and contains the H4F Protocol-2 bridge line.
- `aa5c00aa...` is 275 commits ahead of `a37a865a...`.
- `4753bb7c...` and `aa5c00aa...` are `diverged`; their merge base is `a37a865a...`.

Therefore the current H4F bridge source is **not** a descendant of the WS90-required Rules-Core authority. Treating `4753bb7c...` as WS90-ready would conflate two different Rules-Core lineages and is forbidden.

## Objective

Produce one clean, technically qualified Forge integration candidate that:

1. preserves `aa5c00aa32dfd40e213f223f8fd400c43daabb24` as the Rules-Core semantic base;
2. ports the qualified H4F Protocol-2 bridge onto that lineage as an additive provider/bridge surface rather than replacing or undoing the Rules Core;
3. revalidates the bridge and the affected Rules regressions on the integrated source; and
4. returns an exact repository / commit / tree / Rules-Core-base identity suitable for a later Coordinator repin and fresh WS90 First-Wave execution.

This workstream fulfills the technical dependency that WS90 called “future WS89”; it does not rename or rewrite the historical WS90 artifact.

## Inputs

- Current H4F bridge source: `moeendres-png/forge@4753bb7c72ea60d653121e0bab989077b4009f9c`.
- Target Rules-Core semantic base: `moeendres-png/forge@aa5c00aa32dfd40e213f223f8fd400c43daabb24`.
- H4F current truth in `forge-protocol2-bridge/WS-A1D-H4F-STATE.md` at `4753bb7c...`.
- WS77 clean-successor evidence on branch `ws77/forge-clean-ws76-successor-20260912`.
- WS90 corrected authority package in Commander Lab.
- Current Lab Protocol 2.0.0 and current Foundry governance from the source-locked Lab main above.

## Authority

- Rules behavior: Forge Rules Core on the target lineage plus current official Magic rules where adjudication is required.
- Current engine pins: Commander Lab `config/rules_engines.json` only.
- WS90 corrected First-Wave semantic requirements: WS90 package only.
- Technical decisions inside this bounded port: OpenCode Muse XHIGH may decide implementation details that preserve this contract.
- Any new Rules semantics, engine-pin promotion, qualification-policy change, Production Provider selection, or Architecture Freeze remains Coordinator authority.

## In Scope

- Create an isolated Forge branch/worktree from `aa5c00aa...` (or a state/evidence-only descendant proven byte-equivalent on production source).
- Port the H4F bridge delta from the old `a37a865a... -> 4753bb7c...` line onto the target lineage.
- Preserve the bridge as a separate-process Protocol-2 provider surface.
- Resolve compile/API drift only where necessary for the bridge to compile and behave equivalently.
- Re-run the bridge unit/process tests and the real four-message handshake.
- Re-run the H01 and WS76 batteries affected by the target Rules-Core lineage.
- Verify hidden-information/principal scoping, fail-closed decision handling, exact actor/action/revision binding, and conservative capability reporting.
- Seal evidence and produce a final handoff with exact commit/tree identities and an impact adjudication.

## Out of Scope

- Editing Commander Lab `config/rules_engines.json` or otherwise repinning the canonical Forge identity in this workstream.
- WS90 First-Wave execution itself.
- Full107 provider qualification.
- Expanding the bridge to combat, targets, modes, X, full mana payment, replay/RNG, partners, non-4P, London tuck, or any other unsupported class merely to make tests pass.
- Production-provider selection or Architecture Freeze.
- Rewriting historical WS90 / H4F / WS77 evidence.
- Porting Forge AI/GUI decision heuristics into the provider.

## Dependencies

- `aa5c00aa...` remains reachable and its source identity is reverified before execution.
- `4753bb7c...` remains reachable and its H4F bridge surface is reverified before porting.
- Current Lab Protocol 2.0.0 remains compatible; any material contract drift is a stop condition requiring impact adjudication.
- OpenCode/Forge build environment is available for runtime validation. No historical PASS may substitute for the required fresh integrated-source runs.

## Required Deliverables

1. Exact Forge integration branch, commit and tree.
2. Proof that the integrated source descends from / preserves the `aa5c00aa...` Rules-Core base.
3. Exact changed-path list against `aa5c00aa...` and explanation of every non-additive path.
4. Fresh bridge unit/process test results.
5. Fresh real separate-process Protocol-2 handshake evidence.
6. Fresh H01 + WS76 regression evidence on the integrated source.
7. Capability/hidden-information/fail-closed regression evidence.
8. Impact adjudication covering retained evidence invalidation and the later Lab repin requirement.
9. Final handoff with `PASS / FAIL / UNKNOWN`, blockers, outputs and exact next action.

## Hard Gates

- **G1 Source identity:** exact source locks reverified before mutation; no branch ambiguity.
- **G2 Rules lineage:** integrated candidate must have `aa5c00aa...` in its ancestry or prove an explicitly Coordinator-approved byte-equivalent semantic base. The old `a37a865a...` H4F line may not become the Rules authority by merge accident.
- **G3 Minimal delta:** expected production delta is the additive `forge-protocol2-bridge/**` surface plus the minimal reactor/module wiring. Any required Forge Rules-Core source edit outside that boundary is `AUTHORITY_GATE` / stop, not an automatic compatibility patch.
- **G4 No heuristic legality:** legal action exposure remains sourced from native Forge legality; no `AvailableActions`, AI controller, first/random/default option, or requested-option filtering.
- **G5 No fabricated discretion:** unsupported discretionary decisions remain explicit unsupported/fail-closed paths.
- **G6 Principal scoping:** observations and decision metadata remain principal-scoped; no hidden-information widening.
- **G7 Capability truth:** global `legal_actions_supported`, `action_submission_supported`, and `event_log_supported` remain false unless separately and comprehensively qualified. Bounded success must not inflate global capability claims.
- **G8 Bridge runtime:** all integrated bridge tests pass and the separate-process four-message handshake passes on the exact candidate.
- **G9 Rules regressions:** corrected H01 family and WS76 immediate-concession battery pass freshly on the exact integrated candidate; no historical result is imported as runtime credit.
- **G10 Evidence:** evidence is sealed against the exact candidate commit/tree; UNKNOWN/NOT_RUN stay explicit.
- **G11 No credit inflation:** `BEHAVIOR_CREDIT_CHANGE=0`, `FULL107=NOT_RUN` in this integration workstream.
- **G12 No freeze/selection:** `ARCHITECTURE_FREEZE=NOT_CLAIMED`, `PRODUCTION_PROVIDER=NOT_SELECTED`.

## Forbidden Shortcuts

- Merging/cherry-picking `4753bb7c...` in a way that silently restores `a37a865a...` Rules-Core state.
- Manually injecting expected game outcomes.
- Using Forge AI/GUI defaults as player decisions.
- Auto-paying nonzero mana or inventing mana choices.
- Partial legal-action lists when a required class is unsupported.
- Hidden-information broadening to simplify projection.
- Treating construction/handshake success as behavior qualification.
- Importing WS77/H4F historical runtime PASS as fresh integrated-source PASS.
- Repinning Lab authority before Coordinator impact adjudication.

## Evidence Requirements

Classify every claim as `DIRECTLY_VERIFIED`, `CODE_DERIVED`, `TECHNICALLY_CONFORMANT`, `EXTERNALLY_RULE_VALIDATED`, `MODELED`, `SYNTHETIC`, or `UNKNOWN`. Construction and compile success are never behavioral credit. Runtime PASS must bind the exact candidate SHA/tree and exact command/test selection. Any retained historical evidence must receive explicit impact adjudication after the integration delta.

## Stop Conditions

Stop fail-closed and return evidence if any of the following occurs:

- target/source ancestry cannot be proven;
- bridge port requires a Rules-Core semantic edit outside the bounded allowed delta;
- H01 or WS76 regresses;
- principal scoping or fail-closed decision semantics regress;
- bridge tests/handshake cannot be reproduced on the exact candidate;
- required upstream/network/build inputs are unavailable and cannot be satisfied without changing scope;
- a current authority source contradicts this contract.

Do not widen scope to “make Forge pass”.

## Branch and Ownership

- Coordinator preparation branch (Lab): `ws191/forge-successor-integration-coordinator-20260914`.
- Execution repository: `moeendres-png/forge`.
- Execution branch recommendation: `ws191/forge-aa5c-h4f-integration-20260914`.
- Ownership: one Forge implementation worker only; Lab remains read-only during Forge porting.
- Effort: `XHIGH` because the two source lines diverged and the task is a nonlocal bridge-port/integration with Rules-boundary risk.

## PASS / FAIL / UNKNOWN at issuance

```ini
WS191_PREPARATION=PASS
FORGE_INTEGRATED_SUCCESSOR=NOT_RUN
FORGE_RULES_TARGET=aa5c00aa32dfd40e213f223f8fd400c43daabb24
H4F_SOURCE=4753bb7c72ea60d653121e0bab989077b4009f9c
SOURCE_LINES_DIVERGED=DIRECTLY_VERIFIED
BEHAVIOR_CREDIT_CHANGE=0
FULL107=NOT_RUN
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
```

## Exact Next Action

When the execution plane is available, bootstrap one XHIGH Forge workstream from the exact locks above, port only the H4F bridge/materialization delta onto `aa5c00aa...`, run G1-G12, seal the exact integrated-source evidence, and return the Required Handoff. Do **not** run WS90 First Wave or edit Lab engine pins until the Coordinator accepts that integrated technical successor.

## Required Handoff

The execution worker must return exactly these sections:

- Source Lock
- Work Completed
- New Findings
- Changes
- Tests / Evidence
- PASS / FAIL / UNKNOWN
- Remaining Blockers
- Outputs
- Dependencies Unblocked
- Exact Next Action
