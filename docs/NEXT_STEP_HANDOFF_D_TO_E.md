# NEXT_STEP_HANDOFF — D to E

`D_COMPLETE` is true only after the D PR has passed required CI and is merged (or the exact PR head is explicitly retained as the verified continuation point).

## D scope

- universal tool-run identity/provenance hardened
- run-identity drift rejection added
- policy eval current-deck hash guard added
- counterfactual evidence-level validation hardened
- external counterfactual execution fails closed until a real executor exists
- no deck/inventory/opponent-content changes

## E scope

Proceed only with reproducible bugs, especially:

1. `BUG-AUDIT-001`: read-only audit commands dirty tracked artifacts.
2. `BUG-PERF-001`: multiprocessing negative scaling / resource cleanup warnings.

Do not reopen D modeling boundaries as E bugs.
