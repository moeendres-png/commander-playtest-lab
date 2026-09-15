# Protocol Layer Model (do not conflate versions)

Evidence class: `CODE_DERIVED` (source inspection). Verdict: the layering interpretation in the task is CORRECT.

## The three protocol layers (distinct version lines, distinct authorities)

```
+-------------------------------------------------------------+
| LAYER A — Neutral Lab qualification/service contract        |
| commander-lab.rules-service/1.1.0 (RSP 1.1.0)               |
| Authority: qualification/protocol/ws10r/* (CPL repo)        |
| Envelope schema: rules_service_protocol_v1.schema.json      |
| Messages: HELLO/OPEN_SESSION/OBSERVE/NEXT_DECISION/         |
|   SUBMIT_DECISION/RUN_FIXTURE/CLOSE_SESSION/ERROR           |
| Concepts: DECISION_FRAME(session_id, decision_id,           |
|   state_revision, options_digest), actor-aware observation,  |
|   Core-sole-authority, clean-process semantic replay        |
| Status: NORMATIVE but thin — envelope + semantics, no       |
|   field-level frame/handshake payload schemas yet           |
+-------------------------------------------------------------+
| LAYER B — Provider-native transports (one per provider)     |
|  B1: XMage lanes                                           |
|      - xmage-external-decision-protocol-1.0.0               |
|        (XmageFullGameDecisionController.PROTOCOL_VERSION)   |
|      - provider protocol 2.0.0                             |
|        (XmageProvider.PROTOCOL_VERSION; engine_adapter_     |
|        protocol.schema.json x-commander-lab-protocol-       |
|        version 2.0.0; EngineMessageType vocabulary)         |
|      - frames: decision_id (stable hash of game/offset/     |
|        actor/class), decision_offset, actor_id,             |
|        decision_class, prompt, context, min/max selections, |
|        legal_options, source_object, pilot_state actor view |
|  B2: Forge Protocol 2.0.0                                  |
|      - forge BridgeProtocol.PROTOCOL_VERSION = 2.0.0        |
|      - messages: start_engine/get_capabilities/            |
|        get_provider_version/import_deck/create_commander_   |
|        game/start_game/get_game_state/get_legal_actions/    |
|        submit_action/pass_priority/resolve_mulligan/        |
|        shutdown_game/shutdown_engine (+ narrow aliases)     |
|      - frames: DecisionFrame{revision=frameSeq, kind (30),  |
|        status, actorPlayerId pN, options (opaque UUID       |
|        optionIds or free-input/divided vectors), pre-state  |
|        hash}; WS227 additive: semantic_fingerprint/         |
|        semantic_key/decision_class + decision_class/        |
|        legal_set_digest/rng/event/observation bindings +    |
|        rng_binding/event_offset/digests/terminal_outcomes   |
+-------------------------------------------------------------+
| LAYER C — Replay tape contracts (consumer-neutral)          |
|  - semantic-replay-tape/1.0.0 (Lab-owned, WS218)            |
|  - forge-semantic-replay/1.0.0 over it (Forge-native        |
|    projection; WS227 TAPE_CONTRACT_MAPPING)                 |
|  - canonicalization semantic-canonical-1.0.0 (XMage lane) / |
|    forge-semantic-canonical/1.0.0 (Forge lane)              |
+-------------------------------------------------------------+
```

## Proof the layering is correct (not a version ladder)

1. **Different `$id`/authority**: RSP envelope `$id` is `.../rules_service_protocol_v1_1.schema.json` with `protocol` const `commander-lab.rules-service/1.1.0`; the engine adapter schema `$id` is `.../engine-adapter-protocol-2.0.0.json` with `x-commander-lab-protocol-version: 2.0.0`. Different identifiers, different owners, different message vocabularies (HELLO_* vs start_engine/get_legal_actions). A 1.1.0-vs-2.0.0 numeric comparison is meaningless.
2. **Different message sets, no overlap**: RSP has `DECISION_FRAME/SUBMIT_DECISION/OBSERVATION`; providers have `get_legal_actions/submit_action/get_full_game_decision/submit_full_game_decision`. No provider speaks RSP today (AF01 UNKNOWN for every candidate, symmetrically — WS226 standing).
3. **Provider protocols predate and ignore RSP**: XMage `XmageProvider.PROTOCOL_VERSION = 2.0.0` gates its own JSONL bridge (`protocol_version_mismatch` rejection); Forge `BridgeEngine.dispatch` requires `protocol_version == 2.0.0` (`PROTOCOL_VERSION_MISMATCH` otherwise). Neither checks `commander-lab.rules-service/1.1.0`. The Lab Python side (`EngineProcessManager`) handshakes on provider identity + `runtime_kind == external_rules_engine`, not on RSP.
4. **Decision-protocol sub-versions exist inside providers**: `xmage-external-decision-protocol-1.0.0` (decision frames) and `forge-decision-protocol/1.0.0` (opaque `forge:<kind>/1` classes) are nested inside their respective 2.0.0 transports — further proof that "protocol version" is per-layer.
5. **WS17 thin-adapter assessment agrees**: `qualification/evidence/candidates/xmage.json` `thin_adapter_assessment` states the XMage external-decision protocol "is not RSP 1.1; thin mapping is plausible" — i.e., providers sit underneath RSP, mapped by a facade, not renamed into it.

## Consequence for the successor (primary question 2 answered)

- **Neutral Lab service semantics** (Layer A): session/decision/observation/replay/RNG/failure semantics, cardinality rule, authority allocation, fail-closed negotiation. Candidate-neutral; frozen by RSP authority.
- **Provider-native transport details** (Layer B): message names, option-ID shapes (XMage `decision_id:option_id` + `:numeric` sentinel vs Forge opaque `opt-UUID` + `free-input` sentinel + divided vectors), revision counters (`decision_offset` vs `frameSeq`), capability flag names, error codes (`FULL_GAME_*`/`STALE_DECISION`/`DECISION_TIMEOUT` vs `PROTOCOL_VERSION_MISMATCH`/`STALE_REVISION`/`WRONG_ACTOR`/etc.), launch/topology mechanics. The facade normalizes envelopes, never semantics.
- The successor builds exactly one thin Layer-A facade per provider over the existing Layer-B transports. No provider is "upgraded to RSP 1.1" by relabeling its version.
