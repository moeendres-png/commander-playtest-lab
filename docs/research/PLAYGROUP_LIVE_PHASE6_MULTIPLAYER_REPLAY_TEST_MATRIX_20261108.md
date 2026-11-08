# Phase 6 — Multiplayer/replay acceptance and threat matrix (24 scenarios)

**Date:** 2026-11-08 · **Status:** `DESIGN_ONLY — NOT EXECUTED` · **Parent specification:** [Phase-6 integration architecture](PLAYGROUP_LIVE_PHASE6_MULTIPLAYER_REPLAY_ARCHITECTURE_20261108.md).

Use 4P as the canonical starting configuration; separately requalify 6P. **Never launch 7+/8P operational games**. Every case records source locks, the pinned XMage engine, scenario seed, actor, pod, offered native action set, public event offsets, session epoch, resource budget and exact pass/fail observations. Never fabricate source/card data or a win.

## A. Authorization and privacy (8 scenarios)

| ID | Reproduction intent | Required acceptance oracle |
|---|---|---|
| A01 | Authenticated Chulane seat sees own hand and public boards at 4P | Own private faces; opponents hand **counts only**; no foreign private fields, source decklists or RNG seed |
| A02 | Unauthenticated spectator joins an explicitly public 4P session | Public board and event timeline only, no decision options, no actor UUIDs or raw replay export |
| A03 | Spectator guesses a session URL for a **private** game | Server denies join; response contains no private title, room metadata or card identity |
| A04 | Opponent uses Scry/Surveil, “look at top” or a temporary engine library grant | Only native-authorized viewer gets identity; spectator and other seats receive no name via events, error, metadata, image URL or reconnect snapshot |
| A05 | A face-down spell, Morph/Disguise and Gonti-style face-down exile crosses zones | No unauthorized identity before/after transition; reveal only on native permission; correct public event identity policy |
| A06 | A controlling-player effect changes `decider` while another seat's turn continues (CR 723) | Current controlling principal alone gets private actor view/native offer; other seat cannot submit based on the visible active-turn seat |
| A07 | Browser loses seat auth / session gets revoked or kicked; old socket remains connected | Old writer receives no private messages and cannot choose; websocket epoch invalidated; game is not silently conceded |
| A08 | Inspect full replay export and public event fields (incl. `data`/names) under hostile/fuzzed secrets | Zero decklist/hidden identity/raw private prompt/actor UUID leaks to spectator frames, analytics, logs, caches; failure is fail closed |

## B. Real-time ordering, interaction and session recovery (8 scenarios)

| ID | Reproduction intent | Required acceptance oracle |
|---|---|---|
| B01 | 4P start, capture public state, current decision and native stack | One worker controls engine; actor-bound legal options; monotonic gateway state_revision separate from native event cursor |
| B02 | Submit one legal native action and receive ack while a spectator watches | Exactly one XMage transition; matching decision ID, one ordered event burst, recipient-specific state; no premature optimistic rule-state change |
| B03 | Simulate duplicate `choose` requests with same nonce due to network retry | At most one native submission; repeated ack or safe rejection; never double-cast |
| B04 | Delayed old tab submits after active seat refresh with new session epoch | Rejected stale writer; new tab can answer **current** offer only |
| B05 | Out-of-turn seat submits a real but **other principal's** option ID | Denied before native submission; no observable private choice/option leak |
| B06 | Disconnect on one native decision, reauthenticate before remaining 120s deadline | Snapshot + ordered public event gap fill, new writer lease, **same still-valid decision**; no reset of engine deadline |
| B07 | Disconnect until native 120s timer fails, then reconnect | Engine reports failure; **no** auto-pass, arbitrary skipped turn, hidden hand recreation, free continuation or outcome fabrication |
| B08 | Spectator falls behind thousands of Chulane token/trigger events; client event cursor is too old | Bounded queue/CPU/RAM; safe fresh public snapshot and cursor reset; authenticated actors do not lose a native event or receive an older decision |

## C. Replay, lifecycle and 4P/6P limits (8 scenarios)

| ID | Reproduction intent | Required acceptance oracle |
|---|---|---|
| C01 | Export native bridge replay during parked decision | Restricted `scope=orchestration_only`, exact seed/decks protected, never accessible through spectator/public endpoints |
| C02 | Run a source-locked 4P fresh-process semantic tape replay | Compare native decision class, actor seat, legal offer, RNG/event digests, terminal state; show evidence only for exact HEAD |
| C03 | Attempt 6P WS218 semantic tape at current schema | Explicitly **unqualified/rejected** by current 2–5 schema, not silently PASS because other bridge replay works |
| C04 | Spectator requests completed replay without consent to reveal private hands | Public-only historical projection; no raw replay archive or retrospective private identity enrichment |
| C05 | Participant opts into own-seat timeline; another participant declines full reveal | Own-seat access only if the per-step historical authorization data were captured; global full reveal denied |
| C06 | Host loses connection / host-transfer requested while native decision pending | Session-admin authority changes only under policy; XMage current actor/priority/options remain unchanged |
| C07 | Player eliminated/concedes natively; moderator only kicks another player from lobby | Native lifecycle fully handles concession/leave; moderator kick is **not** implicit in-game concede or skip turn |
| C08 | Request game creation at 4P, 6P, 7P, 8P, 10P | 4P admitted subject to qualification; 6P admission may be allowed only in supported lanes; **7+/8+/10P denied before JVM allocation** |

## Evidence and implementation maturity

| Topic | Existing code / evidence | New functionality to implement / test |
|---|---|---|
| Native decision actor and offered options | `XmageFullGameDecisionController` (`CODE_DERIVED`) | Human-seat auth, lease and proper response adapter |
| Hidden info and protected snapshots | `XmageFullGameStateRedactor` (`CODE_DERIVED`) | Viewer-scoped arbitrary-time read + serialization audit |
| Public semantic events | `XmagePublicEventWatcher`, `eventLogPayload` | Public browser DTO, transport ordering and gap fill |
| Full technical replay | `replayExportPayload`, `XmageFullGameReplayVerifier` | Private storage/permissions; **do not** give archive to browser |
| WS218 versioned replay | `tape.py` 2–5 | Separate 6P qualification and secure browser timeline |
| Live multiplayer, spectators, reconnect | No equivalent browser gateway found in inspected current Lab | All stages M1–M6; zero E2E proof today |

## Security and failure gates

- **S1:** any unauthorized private identity/string appearance in a public payload, event log, error, cache, screenshot metadata or replay = **FAIL**.
- **S2:** any out-of-offer, stale/foreign/principal-invalid action accepted = **FAIL**.
- **S3:** native decision timeout or engine fault mislabeled as successful reconnect = **FAIL**.
- **S4:** altered/omitted/duplicated native decision or rule event due to cosmetic backpressure = **FAIL**.
- **S5:** any 7+/8P operational game creation and any unqualified 6P replay PASS claim = **FAIL**.
- **S6:** public game browser can download `scope=orchestration_only` replay, seed, decklist or decision tape = **FAIL**.
- **S7:** a code review or existing unit test without a new browser E2E does not grant a browser/spectator PASS.
- **S8:** no private Chulane deck, card collection, source secret or other player's hidden zones sent to Playgroup or arbitrary external systems.

### Proposed test harness

- Native fixture games with **public precon decks** (no `data/collections/**`); Chulane private candidate only once explicitly integrated and approved.
- 4P real game / fake authenticated gateway users / browser roles / network injector for reordering, duplicate, delay, drop, abort, socket takeover and stale epochs.
- 6P scenarios in independent qualification, using existing 6P engine support and measured RAM/CPU budgets; no assumptions from 4P.
- Compare public and actor-scoped redaction *byte-by-byte* for prohibited sentinel card identities; one intentionally restricted hand/exile card per actor, with temporary look grants.
- Strict source pin and independent review before any merge. No first-option or manual-pass fallback.

**All 24 scenarios = `NOT_RUN`.** This document contains test definitions, not results. Full acceptance requires executing them in a dedicated workstream with a real browser gateway, pinned JVM and evidence artifacts.
