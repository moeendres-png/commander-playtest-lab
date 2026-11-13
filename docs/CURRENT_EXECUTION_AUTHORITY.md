# Commander Simulator Next — Current Execution Authority

Status: **CANONICAL / CURRENT**. Effective 2026-10-16 (Owner instruction: models are
selected manually; previous revision 2026-10-12).

## Executors

The Owner selects the tool and model for each session manually. The rules for every
executor are in `AGENTS.md` §6–§8. Calls to another model name the Owner-selected model
explicitly, never a tool default.

- There is no automatic fallback: a quota, auth, catalog or tool failure ends the run; it never re-resolves to another executor.
- Historical executor names in dated records are provenance only and create no migration
  or governance work by themselves. Do not rewrite old evidence to pretend the current
  executor produced it.

## Authority boundaries

A pushed WIP is never qualification PASS.

Executor choice never changes Rules authority, evidence semantics, hidden-information
rules, fail-closed requirements, Source Truth, provider-selection or Freeze authority.
Production Provider selection and Architecture Freeze remain separate Owner gates, with the other Owner-only items in `AGENTS.md` §8.

The Claude Opus Coordinator delegation (effective 2026-10-05) is defined in `AGENTS.md`
§8, "Claude Opus 5.5 Coordinator authority".

`PRODUCTION_PROVIDER = XMAGE` (D5 runtime switch done, `provider_decision = XMAGE_SELECTED`).
`ARCHITECTURE_FREEZE = CLAIMED` (2026-10-10, Owner-signed:
`docs/architecture_freeze_20261010/ARCHITECTURE_FREEZE_ADR.md`).
