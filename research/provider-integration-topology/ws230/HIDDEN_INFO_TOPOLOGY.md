# Hidden Information Across Topology and Handshake

Evidence class: `CODE_DERIVED` (mechanism inspection + sealed per-count proofs; no new runtime).
Rule: topology and handshake are part of the leakage boundary (G07: "all outbound fields are part of the leakage boundary").

## 1. What MAY be visible (neutral metadata, all principals + orchestrator)

- Provider identity (`xmage` / `forge`), release/version strings, protocol versions (`2.0.0` provider transports; `1.1.0` RSP envelope once the facade exists).
- Capability flags + bound descriptors (family lists, lanes, pins) — truth about *what is supported*, never card identities.
- Principal IDs in their native alphabet (XMage UUID strings; Forge `pN` seat principals) + seat map + turn/phase/step + active/priority player IDs (public game structure).
- Decision metadata: `decision_id`/`decision_offset`/`frameSeq`, `decision_class`, prompt text, min/max selection bounds, `options_digest`/`legalSetDigest` + sizes, RNG call counts (not RNG outputs), event offsets + digests, state digests (one-way hashes).
- Typed error codes (`STALE_DECISION`, `WRONG_ACTOR`, `CHOSEN_OPTION_MISSING`, …) — the code only, never hidden payloads. (Forge `WRONG_ACTOR`: "outsider learns only the code.")
- Logs/errors at the transport level (malformed request, version mismatch, timeout, crash facts). Privileged internal diagnostics stay privileged (below).

## 2. What REMAINS principal/private (never in other principals' views, tapes, or errors)

- Hand contents, library identities/order, face-down cards, mana-pool contents (XMage: only the actor entry carries `hand`/`mana_pool`; Forge: hands `<hidden>` + counts, libraries empty + sizes, face-down via `canBeShownTo`/`canFaceDownBeShownTo`).
- Opponent-derived identities in option labels/metadata/source/state (XMage oracle scan covers labels/metadata/source/state; Forge redaction strips object_ids/UUIDs/short-ids; digests are one-way).
- Native bindings (SpellAbility/Player object references, raw UUIDs) — never leave the provider process.
- Execution diagnostics bound to another actor's frame (Forge `isExecutionErrorBoundTo`: an execution error is exposed only in its own frame's context to its actor).
- Raw engine internals (memory addresses, process UUIDs, wall clock, unstable serialization) — excluded from semantic identity by RSP definition.

## 3. Privileged diagnostics are NOT pilot API

- XMage `engineErrorDiagnostics` / Forge stderr (`logInternal`) / bridge audit trails / `engine_event_offset` internals: visible to operators for debugging, never projected into `pilot_state`, `OBSERVATION` payloads, tapes, or error details.
- Do NOT convert them: no endpoint, flag, or "debug mode" may pipe privileged logs into pilot-visible fields. A successor that needs operator observability adds an operator-only channel with its own redaction review; the pilot contract is unchanged.
- Forge `export_event_log`/`get_event_log` refusal is the precedent: external event export is disabled for principal privacy even though an internal audit exists. XMage B4-D audit stream is likewise bounded to lifecycle/action boundaries, explicitly not an exhaustive internal tap.

## 4. Topology-specific boundaries

| Topology | Leakage-relevant properties |
|----------|------------------------------|
| Local child process (stdio JSONL) | OS-process boundary; stderr separated from stdout (protocol purity); per-game fresh JVM gives temporal isolation (no cross-game residue); parent temp dir writes atomic + `.incomplete` never sealed |
| Localhost service | Same as child + socket boundary: bind 127.0.0.1 only; no remote principals; port-reuse refused (fail closed per `EngineProcessManager.port_available`) |
| Containerized service | Image provenance (`/opt/engine-provenance.json`) verified against manifest at start; mismatch refuses start (prevents stale-engine leakage across builds); DISPLAY removed (Forge) |
| Packaged sidecar | Same as container + distribution carries license obligations (see `LICENSE_TOPOLOGY_MATRIX.json`); sidecar shares fate with Lab install but keeps process boundary |
| Remote service | NOT RECOMMENDED for hidden-info reasons: observations traverse a network; TLS/auth/redaction review required; no current authority supports it (see topology options: fatal blocker for Forge) |
| In-process embedding | FORBIDDEN for Forge (destroys the WS-09 separate-process boundary and GPL isolation); for XMage it would collapse the actor-projection boundary into shared memory — admissible only with a new hidden-info campaign, so WS230 does not recommend it |

## 5. Handshake leakage rules

- The handshake advertises capability truth and identity, never game state. No hand/library/seed values in handshake payloads (seed *support* is declared; per-game seeds travel only in `OPEN_SESSION`/launch bindings).
- A failed handshake leaks only the failure code + which identity field mismatched at the granularity needed to fix configuration (wrong protocol / wrong schema / wrong identity / unsupported cardinality / false capability / stale lock / malformed / missing field). It never echoes hidden game data (there is none yet) and never dumps full configs with secrets (secret files are never read by the handshake path).
