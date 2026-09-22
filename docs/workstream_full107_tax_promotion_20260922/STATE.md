# Workstream STATE — FULL107 TAX promotion (2026-09-22)

- Branch: `cpl/full107-tax-promotion-20260922`
- Worktree: `/home/moeen/code/ws-full107-tax-promotion-20260922`
- Base: `7a28b58116979e2f2c36dc82c483c1a2d8aea9e1`
- Frozen: `origin/ws47/successor-contract-v1.0.5-freeze@5a2e4f46`
- Evidence: executor TAX-2/TAX-4 executions (PR #220 merged)
- Verdicts: `FULL107=NOT_QUALIFIED` · `ARCHITECTURE_FREEZE=NOT_CLAIMED` ·
  `PRODUCTION_PROVIDER=NOT_SELECTED`
- Progress:
  - [x] Ownership established (branch/worktree/base verified, contract written)
  - [x] Register EXACT verdicts + generator TAX rule + mapping regen + guard
    (DIRECT 2→4, NOT_RUN_BLOCKED 35→33; guard 6/6 incl. negative control)
  - [x] Validate (mapping repro identical; predicates 47/47; WS17 manifests
    verify; ruff clean) + commit + push + PR
