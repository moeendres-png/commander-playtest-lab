# Forge Lab Consumption Blueprint (implementation-ready, NOT implemented)

Evidence class: `MODELED` (design from WS227 authority + CPL seams). No CPL or Forge code changed by WS230.

## 0. Boundary

- Consume WS227 **after the CPL writer line stabilizes** (post-WS229 terminal + S8/S9 sequencing; see `ROADMAP_IMPACT.md`).
- Lab consumes authoritative outputs only; never reproduces Forge rules; never turns the bridge into an in-process library; no Python legality reconstruction.
- Forge Lab replay consumer is explicitly NOT built in WS230 (tape seam identified in `REPLAY_MAPPING.md`).

## 1. Likely CPL files to change (new modules preferred; existing authority untouched)

| Area | Likely path (proposed) | Change |
|------|------------------------|--------|
| Provider adapter/facade | `src/commander_lab/engine/rules/forge_rsp_facade.py` (NEW) | RSP envelope ↔ Protocol 2.0.0 translation: HELLO unify (`get_provider_version` + `get_capabilities` + dual SHAs + schema hash + bound vector + topology declaration); OPEN/OBSERVE/DECIDE/SUBMIT/CLOSE mapping; `session_id=gameId`, `state_revision=frameSeq`, `options_digest=legalSetDigest` aliasing; typed error mapping 1:1 (never invent codes) |
| Process launcher | `src/commander_lab/engine/forge_process.py` (NEW; reuse `process_manager.py` patterns) | Fresh child JVM per game; `FORGE_ENGINE_SHA` bind via sysprop+env; DISPLAY removed; stdout-JSONL purity; stderr to operator logs only; single-flight seeded serialization (global `MyRandom` — orchestrator mutex, no concurrent seeded games) |
| Handshake | inside facade (above) | Implement `RSP11_HANDSHAKE_MATRIX.json` DERIVED fields + `handshake_schema_hash` + `bounded_family_capability_vector` + `replay_manifest_binding` + `process_lifecycle_declaration` |
| Source-lock binding | `src/commander_lab/engine/forge_source_lock.py` (NEW) or extend attestation | Bind provider SHA + replay-core SHA + bridge version + tape producer id per session; mismatch → refuse before execution (`SOURCE_LOCK_MISMATCH`) |
| Capability negotiation | inside facade | Five-state interpreter (`CAPABILITY_TRUTH_MODEL.md`); need⊄bound → typed `unsupported` before game start; post-handshake out-of-bound requests → typed `unsupported` |
| Observation mapping | inside facade | `viewer_player_id=actor pN`; carry `publicStateDigest`/`principalObservationDigest`; enforce actor-only (non-actor reads get empty/null + `WRONG_ACTOR` on submit); never pipe stderr/audit internals into pilot fields |
| Legal-action mapping | inside facade | Carry parked-set fingerprints + `forge:<kind>/1` classes + free-input bounds + divided total/min/upTo; submit provider-native selections only (opt-UUID / value / vector); exactly-once; digest-verified |
| Replay consumer mapping | `src/commander_lab/engine/rules/forge_replay_consumer.py` (NEW, second step) | Fresh-JVM replayer for `forge-semantic-replay/1.0.0` tapes (see `REPLAY_MAPPING.md` §5); refuse non-Forge tapes; unseeded tapes observational-only |
| Error taxonomy mapping | inside facade | 1:1 map of `FORGE_WS227_AUTHORITY.json` error taxonomy into RSP `ERROR` (incl sanitized `INTERNAL_ERROR`) |
| Tests | `tests/.../test_forge_rsp_facade.py`, `test_forge_handshake_negatives.py` (NEW, 9 negative classes), `test_forge_topology_*.py` (NEW per topology) | Positives (`AF01_RUNTIME_TEST_PLAN.json`) + negatives (`FAIL_CLOSED_NEGATIVE_MATRIX.json`) + topology plan |
| Docs/config | `docs/engine_setup.md` (additive note), manifest `bridge_environment.forge` (no pin change) | Document facade + topology declaration; NO pin/authority edits in WS230 scope |

## 2. Fresh-process runs required

- Record + replay children per mandatory cardinality reachable at the then-current Forge pin (today 2P–4P + documented 5P gap); each bound to dual SHAs; exit-0 + coordinate match required.
- Kill/timeout/desync/orphan/SHA-mismatch/privacy-refusal negatives on the declared topology.

## 3. 2P–5P implications

- RSP mandates independent 2P–5P. Forge WS227 `max_players=4`: 5P Commander is a genuine Forge-side gap (KNOWN_UNKNOWN), not a facade task. The facade advertises the proven bound; 5P qualification needs a Lab-side Forge campaign at a pin that supports it.

## 4. Forge 5P/Commander gaps that remain unrelated (not facade work)

- Natural-terminal 5P Commander replay; whole-boundary hidden-info campaign; whole-boundary legal-completeness remediation beyond the parked-set discipline (stock-path AF04 FAIL preserved until a Lab-side campaign proves otherwise); concurrent-seeded execution (documented single-flight, never re-architected).
