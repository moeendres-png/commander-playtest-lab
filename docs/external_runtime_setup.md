# External runtime execution checklist

Phase 8.5 in the build container ended with
`external_runtime_prepared_but_not_executed`.

## Manual execution on a normal local machine

1. Install JDK 21 and Git.
2. Ensure GitHub and Maven Central are reachable.
3. Run `scripts/bootstrap_engine_linux.sh`, the macOS wrapper, or the PowerShell script.
4. Build or install a provider-specific bridge implementing protocol 2.0.0.
5. Set `ENGINE_START_COMMAND` to that bridge.
6. Run `scripts/verify_engine.sh`.
7. Run `commander-lab validate-engine-phase85`.
8. Preserve `artifacts/engine_setup` and collect logs.

## Acceptance sequence

A real run must prove:

- external handshake and exact version;
- legal Commander deck import;
- three- or four-player game creation;
- reproducible seed or starting state, if advertised;
- legal-action query and successful submission;
- event log retrieval;
- deterministic rejection of an illegal action;
- ten project scenarios;
- replay into the internal model without silently discarded events.

Until that sequence succeeds, start Phase 9 only with:

```text
external_engine_validation_pending=true
```

No rule-validated claim may rely on the Tactical Oracle.
