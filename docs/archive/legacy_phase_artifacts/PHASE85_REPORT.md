# Phase 8.5 – External rules-engine runtime

## Final status

```text
external_runtime_prepared_but_not_executed
external_engine_validation_pending=true
```

The restricted acceptance path is complete. No XMage or Forge result was executed
or labelled as external evidence in the current runtime.

## 1. Root cause

The repository and Phase-8 adapter were inspected before modification. Phase 8
already contained:

- a bounded Tactical Oracle;
- a persistent Phase-8 JSONL subprocess client;
- XMage and Forge adapter classes;
- 73 local tactical interaction fixtures;
- a three-level legacy card registry;
- fake/fixture external-adapter tests;
- no provider-specific XMage or Forge bridge binary.

The current environment diagnosis found:

- OpenJDK and `javac` 21.0.10 available;
- Git 2.47.3 and Python 3.13.5 available;
- Maven, Gradle, Docker and Docker Compose absent;
- DNS failure for GitHub, raw GitHub content and Maven Central;
- HTTPS `curl` failures with exit code 6;
- repository and subprocess execution writable/functional;
- 5 visible CPU cores and about 38.8 GiB free storage;
- ports 17171, 17172 and 9090 available; 8080 occupied.

Real bootstrap attempts were made for both providers. Each failed at `git clone`
with `Could not resolve host: github.com`. No source or binary was treated as
present after that failure.

## 2. Primary engine decision

XMage remains the primary target. Its documented Commander multiplayer, AI and
special test mode fit the tactical-validation use case. Forge remains a
separate-process differential fallback. This decision is provisional with
respect to runtime capabilities because neither provider was executed here.

Pinned identities:

| Provider | Release | Commit | Role |
|---|---|---|---|
| XMage | `xmage_1.4.60V3` | `06d166b098ad36b277edef01116472203d5a047e` | primary |
| Forge | `forge-2.0.13` | `852066bf4f761b302ed17cb011999d8a8fe08ad6` | differential fallback |

## 3. Implemented runtime path

### Process manager

`src/commander_lab/engine/process_manager.py` now provides:

- start, stop, restart and status;
- dependency/source preflight;
- timeout-aware health checks;
- PID and persisted state;
- protocol/provider/version identity;
- capability storage;
- controlled termination;
- stdout/stderr bridge log capture;
- all required status values.

`healthy` is possible only after a versioned handshake reports the configured
provider, `runtime_kind=external_rules_engine`, and the required Commander,
multiplayer, deck import, legal-action, action-submission and event-log
capabilities.

### JSONL protocol

Protocol `1.0.0` defines all required message types and request/response fields.
The generated JSON Schema is stored at
`schemas/engine_adapter_protocol.schema.json`. Protocol errors, unknown messages,
timeouts and request-ID mismatches are deterministic failures.

### Capability gating

No capability is inferred from the string `xmage` or `forge`. Missing
capabilities cause degradation or an explicit protocol error. The Tactical
Oracle identifies as `runtime_kind=tactical_oracle` and cannot become healthy as
an external runtime.

### Replay

The strict replay reducer requires an internal state snapshot for every event
until a typed reducer exists. Unknown events cannot be silently discarded. It
compares zones/player state, life, Commander cast counters, Commander damage,
turn, phase, priority, stack and event sequence through the internal `GameState`
schema.

## 4. Installation paths

Prepared paths:

- direct Linux source build;
- macOS wrapper;
- Windows PowerShell bootstrap;
- project-local Maven 3.9.16 with official SHA-512 verification;
- XMage and Forge Dockerfiles;
- Docker Compose profiles;
- devcontainer configuration;
- offline source and binary directories;
- environment-based external paths;
- idempotent start, stop, verify and log-collection scripts.

The scripts verify pinned Git commits when a repository checkout is supplied.
An offline unpacked source requires an explicit identity file. An offline binary
is not accepted as validated until the real capability handshake succeeds.

## 5. Current build and start status

| Item | Current runtime |
|---|---|
| XMage source acquisition | failed: DNS |
| XMage build | not started |
| XMage bridge start | not configured |
| Forge source acquisition | failed: DNS |
| Forge build | not started |
| Forge bridge start | not configured |
| Docker build | unavailable: Docker absent |
| Offline source | not supplied |
| Offline binary | not supplied |
| External handshake | not executed |

## 6. Integration tests

The required real tests remain pending:

- external handshake;
- engine-side Commander deck import;
- three-/four-player game;
- legal action query and submission;
- event log;
- illegal action rejection.

No local fixture was substituted for those results.

The local Tactical Oracle contract test passed, but it is labelled
`tactical_oracle`, not `external_rules_engine`.

## 7. Project scenarios

All ten required external scenarios are present in the validation output. Their
current status is `manual_review_required`, and none is marked
`rules_engine_validated`:

1. Commander from command zone;
2. Commander tax after removal;
3. partner commanders;
4. Commander damage per opponent;
5. Kediss normal damage;
6. Jeska combat-damage tripling;
7. boardwipe;
8. countering a Commander;
9. protection response;
10. cast trigger after the triggering spell is countered.

## 8. Contract and replay results

- 14 required protocol message types represented and envelope-tested;
- unknown message rejected;
- protocol/provider mismatch rejected;
- timeout reported as failure;
- tactical bridge cannot pass external health;
- strict replay passed for the reference fixture;
- replay without a state snapshot rejected;
- process lifecycle tested with a clearly labelled fake external fixture;
- 130 tests passed, one real-engine differential test skipped, zero failed.

## 9. Validation-level boundary

Runtime outputs use:

- `structural_only`;
- `tactical_oracle`;
- `external_rules_engine`.

The final level is unavailable in this runtime. Legacy card-registry terms remain
for backward compatibility but do not override the runtime evidence level.

## 10. Remaining manual step

On a machine with GitHub/Maven access or a verified offline source/binary:

1. run the relevant bootstrap;
2. provide a provider-specific XMage JSONL bridge implementing protocol 1.0.0;
3. set `ENGINE_START_COMMAND`;
4. run `scripts/verify_engine.sh`;
5. run `commander-lab validate-engine-phase85`;
6. retain the handshake, event log, replay and scenario evidence.

Building the upstream engine alone is not sufficient. The provider-specific
bridge must actually bind its game/test APIs to the protocol.

## 11. Phase-9 decision

Phase 9 may begin only with:

```text
external_engine_validation_pending=true
```

It is safe to continue work that does not claim external rule validation.
Rules-engine-validated statements and release-gate promotion remain blocked until
a later real XMage or Forge execution passes the external acceptance suite.
