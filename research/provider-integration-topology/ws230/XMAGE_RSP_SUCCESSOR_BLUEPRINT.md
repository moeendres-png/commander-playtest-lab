# XMage RSP Facade Blueprint (smallest path, thin lossless facade)

Evidence class: `MODELED`. No code changed by WS230. No qualified full-game semantics redesigned.

## 1. Principle

Prefer the thin lossless facade. The full-game lane already owns legality, RNG, observation, lifecycle, and failure semantics; the facade only aliases identifiers, adds the missing digest, and projects existing truth into the RSP envelope.

## 2. Facade work items (likely one new module: `src/commander_lab/engine/rules/xmage_rsp_facade.py`)

1. **Envelope**: accept/emit `commander-lab.rules-service/1.1.0` envelopes (`HELLO_REQUEST/RESPONSE`, `OPEN_SESSION/SESSION_OPENED`, `OBSERVE/OBSERVATION`, `NEXT_DECISION/DECISION_FRAME`, `SUBMIT_DECISION/DECISION_ACCEPTED`, `CLOSE_SESSION/SESSION_CLOSED`, `ERROR`); validate against `rules_service_protocol_v1.schema.json`; enforce `protocol` const (mismatch → typed failure).
2. **HELLO**: unify `get_provider_version` + `get_capabilities` into one `HELLO_RESPONSE` carrying provider (`xmage`), Core commit `db134b97…`, lane declaration (full-game vs B4-D), adapter identity, source/build reference (AF00), handshake schema hash, capability bound vector (17 families + 2P–5P + RNG/replay bounds), replay contract id, topology declaration. B4-D lane values MUST stay degraded-truthful (global legal/action flags false).
3. **Session**: `session_id = game_id` alias; `OPEN_SESSION` validates cardinality 2..5 (6 → `FULL_GAME_INVALID_PLAYER_COUNT`); binds orchestration seed → `setRulesSeed` + `requireExplicitSeed` (unchanged Java path).
4. **Decision**: `state_revision = decision_offset` alias; compute `options_digest = SHA-256(canonical sorted option fingerprints)` per parked frame (new, additive — Java side untouched; Python facade over the production JSONL lane per WS218 option-A precedent); carry `decision_class`/actor/seat/prompt/bounds/source metadata through; submit `DecisionResponse` unchanged (offered ids + numeric/ordering within bounds; unknown keys rejected).
5. **Observation**: `viewer_player_id = actor_id`; carry actor views + digests; windowed `granted_library` behavior unchanged; no privileged diagnostics into pilot fields.
6. **RNG/replay**: carry `rules_seed_binding` per payload; bind tape contract `semantic-replay-tape/1.0.0` + manifest id in handshake; replay via existing WS218 consumer path (no new tape format).
7. **Errors**: 1:1 map (`FULL_GAME_INVALID_PLAYER_COUNT`, `STALE_DECISION`, `DECISION_TIMEOUT`, `BRIDGE_PROTOCOL_ERROR`, unsupported-class, wrong-actor, version mismatch) into RSP `ERROR`. No new failure kinds; no silent PASS.
8. **Negatives**: implement all 9 `FAIL_CLOSED_NEGATIVE_MATRIX.json` classes as automated tests before claiming AF01.

## 3. What the facade MUST NOT do

Enumerate missing options, compute costs/targets, guess equivalence, repair unsupported choices, default decisions, predict RNG, inject state, synthesize outcomes — i.e., everything RSP forbids adapters from doing (see `RSP11_AUTHORITY_MODEL.md` §1 + neutral-facade rules in the task). Any such behavior is a second-Rules-engine violation and disqualifies the build.

## 4. WS229 dependency

WS229 (numeric/decision-boundary S6) is active and unpublished. The facade MUST be built against the WS229 **terminal** wire shapes, not the pre-WS229 shapes inventoried here. `POST_WS229_DELTA_REVALIDATION.json` defines the machine-checkable predicates; if any predicate yields `INVALIDATES_PREFLIGHT`, the facade design is re-derived from terminal source before implementation.
