# RSP 1.1 Authority Model (reconstructed from current contracts)

Evidence class of this document: `CODE_DERIVED` (reconstruction from normative files) unless a row cites runtime evidence.
Nothing here is runtime proof. No gate verdict is changed by this file.

## 1. Normative sources (exact)

| # | Artifact | What it normatively establishes |
|---|----------|----------------------------------|
| 1 | `qualification/protocol/ws10r/RULES_SERVICE_PROTOCOL_V1.md` | Protocol identity `commander-lab.rules-service/1.1.0`; authority separation (Core decides, pilots choose among offered options, adapters translate only); 2P–5P mandatory cardinality (6P SHOULD); actor-aware observation (`viewer_player_id` vs decision subject vs decision authority distinct); `DECISION_FRAME` binding (`session_id`, `decision_id`, `state_revision`, SHA-256 `options_digest`); exact-option-ID or typed numeric/assignment submission; stale rejection; terminal unsupported paths (no first/random/default/AI/GUI/parent fallback); replay/RNG separation (`ReplayManifest`, `RulesRngTape`, `DecisionTape`, semantic `EventTape`, checkpoints/state hashes; clean-process semantic replay; semantic identity excludes process UUIDs/memory addresses/wall clock/unstable serialization); typed failures, no silent PASS |
| 2 | `qualification/protocol/ws10r/rules_service_protocol_v1.schema.json` | Envelope schema: required `protocol` (const `commander-lab.rules-service/1.1.0`), `message_type`, `request_id`, `payload`; optional `actor_id`, `session_id`, `state_revision`; 15 `message_type` values (`HELLO_REQUEST/RESPONSE`, `OPEN_SESSION/SESSION_OPENED`, `OBSERVE/OBSERVATION`, `NEXT_DECISION/DECISION_FRAME`, `SUBMIT_DECISION/DECISION_ACCEPTED`, `RUN_FIXTURE/FIXTURE_RESULT`, `CLOSE_SESSION/SESSION_CLOSED`, `ERROR`); `payload` is an unconstrained object at envelope level (frame/handshake field detail lives in docs + successor implementation, NOT in this envelope schema) |
| 3 | `qualification/protocol/ws10r/architecture_freeze_gate_catalog_v1.json` | AF00–AF11 all `required: true`; AF01 = "Exact RSP 1.1 protocol/schema handshake and truthful capabilities"; AF11 = "Actual integration topology satisfies WS-09; Forge remains a genuine separate process/service" |
| 4 | `qualification/protocol/ws10r/ARCHITECTURE_FREEZE_CONTRACT_V1.md` | Only `PASS` satisfies; `UNKNOWN/NOT_RUN/PARTIAL/UNSUPPORTED/FAIL` block; `NOT_APPLICABLE` invalid for AF gates; green builds/imports/CI do not substitute; `architecture_winner = false` |
| 5 | `qualification/obligations/FULL_RULES_REQUIREMENTS_CONTRACT_v1.json` | G00–G15; G12 = "technical interoperability and licensing compatibility for actual integration/distribution model" with semantics "Forge must remain across genuine separate-process/service boundary under WS-09"; G02/AF02 cardinalities 2P–5P mandatory; G05/G06 (Core sole authority, complete legal set, fail-closed); G07 (actor-scoped state, all outbound fields are leakage boundary); G08/G09 (RNG attribution + clean-process semantic replay); G11 (no crash/hang/timeout/desync/corruption) |
| 6 | `qualification/ws226-consolidated-cpl-authority-integration/G_AF_MAPPING.json` | G/AF are NOT one-to-one: AF01 is AF-only (no G home; adjacent to G00 identity but a runtime handshake, not a lock record); G12/AF11 share one direct bundle with zero fixtures ("actual topology" standard applies symmetrically to every candidate; WS217 separate-process seam is supporting, not satisfying); AF != admission boundary |
| 7 | `config/rules_engines.json` | Sole machine-readable pin authority; XMage `primary_engine` (MIT, B4-D degraded, `legal_actions_supported` + `action_submission_supported` missing globally); Forge `secondary_engine` (GPL-3.0, PARTIAL, dual identity: `commit` = Rules-Core authority, `bridge_source` = materialization source); `provider_decision = NO_PROVIDER_READY`; truth boundary for B4-D lane |
| 8 | `docs/engine_setup.md` + `integrations/forge/README.md` | Operational topology today: external bridge processes over JSONL stdin/stdout; Forge is a separate-process GPL-3.0 differential backend, no Forge runtime in CPL tree; bounded Protocol-2.0.0 bridge; global legal/action/event flags stay false (truthful bounded state); container path resolves identity from manifest at build time |

## 2. What RSP 1.1 requires from a production-capable provider handshake (answer to primary question 1)

The handshake is the runtime binding of identity + version + capability truth before any game evidence counts.
Reconstructed minimum (see `RSP11_HANDSHAKE_MATRIX.json` for NORMATIVE/DERIVED/OPTIONAL/PROPOSED classification):

1. **Protocol identity**: envelope `protocol == commander-lab.rules-service/1.1.0` on every message (schema-const; mismatch = typed failure).
2. **Schema identity**: the envelope validates against `rules_service_protocol_v1.schema.json`; frame/handshake payload semantics conform to `RULES_SERVICE_PROTOCOL_V1.md` (the envelope schema alone does not define frame fields — a successor MUST define and hash the frame/handshake payload schemas it implements).
3. **Provider identity**: which provider (`xmage` / `forge` / other) plus its exact release/version string.
4. **Rules-Core identity**: exact upstream commit (and tree where applicable) the running Core was built from — XMage `db134b97…` today; Forge Rules-Core commit distinct from bridge-source commit (dual identity, never conflated).
5. **Adapter identity**: exact bridge/adapter build (XMage `engine-bridge` full-game lane vs B4-D lane; Forge `forge-protocol2-bridge` + Protocol 2.0.0); adapter reports, never decides.
6. **Source/build identity**: reproducible source + build provenance (AF00 scope; handshake binds or references it so a stale/mismatched build fails closed).
7. **Capability declarations**: truthful per-capability flags (see `CAPABILITY_TRUTH_MODEL.md`): player-count support (independent 2P/3P/4P/5P), legal-action support, observation support, hidden-information guarantees, Rules-RNG support, semantic-replay support, process-isolation/topology identity, failure/unsupported semantics. False claims fail closed; `UNKNOWN`/`NOT_RUN` never satisfy.
8. **Cardinality binding**: which of 2P/3P/4P/5P this provider instance actually supports (each independently proven; 6P SHOULD, explicitly out of mandatory scope).
9. **Failure/unsupported semantics**: typed errors for malformed/stale/impossible/unavailable/unsupported/provider-failure cases; unsupported discretionary paths terminal; no silent PASS.

## 3. Deliberately NOT required by current RSP 1.1 text

- No wire format beyond "envelope + payload object" is normatively fixed (JSONL transport is current practice, not RSP-1.1-mandated bytes).
- No specific hash algorithm for `options_digest` beyond SHA-256 (stated for the digest itself).
- No mandated session-lifecycle primitives beyond the OPEN/OBSERVE/DECIDE/SUBMIT/CLOSE message pairs and their stated semantics.
- No mandated capability-flag vocabulary (the current engine flags in `EngineCapabilityHandshake.schema.json` are the de-facto surface a successor handshake MUST truthfully project, but RSP 1.1 text does not enumerate flag names — hence several handshake fields are DERIVED_REQUIRED, not NORMATIVE_REQUIRED).

## 4. Open authority gaps WS230 does NOT fill

- The WS-10 original bundle is unrecoverable (byte identity with 1.0.0 UNKNOWN); 1.1.0 is a rematerialization. A successor must not claim 1.0.0 compatibility.
- WS-09 canonical handoff bytes are referenced only by hash (`WS17_SOURCE_LOCK.json`); WS230 reconstructs WS-09 solely as "Forge across a genuine separate-process/service boundary + licensing compatibility for the actual model" from G12/AF11 normative text. Any stronger WS-09 claim would be invented.
- Frame/handshake payload schemas (field-level) do not exist yet as protocol authority; the successor MUST author them (proposed, not normative).
