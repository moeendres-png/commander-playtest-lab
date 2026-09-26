# Phase 8.5.1: external-provider execution boundary

Real external rules-engine validation remains **pending** until an actual external provider is built, started, controlled programmatically, and validated with raw evidence.

Tactical Oracle, mocks, fixtures, handshake-only probes, or structural simulations do not satisfy this boundary.

## Current provider strategy

No production provider has been selected.

The active sequence is:

1. reliability and structural/modeling quality first;
2. external-engine feasibility preparation;
3. run an equivalent XMage spike;
4. run an equivalent Forge spike;
5. compare both providers against the same acceptance criteria;
6. select one primary production bridge only after evidence supports the choice.

Current provider status:

```text
external_engine_provider_status = INSUFFICIENT_EVIDENCE_RUN_BOTH_SPIKES
```

## Required evidence for either provider spike

A provider spike must preserve the same truth boundaries and, where technically supported, exercise the same core contract:

- pinned/provider-identifiable source or binary;
- process start and bounded shutdown;
- capability handshake;
- deck import;
- multiplayer Commander setup;
- deterministic/reproducible seed handling where supported;
- legal-action retrieval;
- programmatic action submission;
- event/replay evidence;
- critical Commander/rules scenarios;
- raw logs and provider/runtime attestation.

A provider-specific spike may be rejected early if a documented knock-out criterion is met. A failed or incomplete spike must not be reported as external rules-engine validation.

## Execution environment

Run future provider spikes only from a network/build environment that can actually obtain and build the selected pinned provider source and its bridge dependencies. Do not use an obsolete historical branch checkout as the active starting point; begin from the currently verified `main` state and isolate spike work in a dedicated future J-P3 branch/worktree.

The final project status may change from `external_engine_validation_pending` only after real external evidence exists and the corresponding acceptance gate is satisfied.
