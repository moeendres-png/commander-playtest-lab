# RQ-A1 — Argentum Hidden Information

Question: is protection structural, projection-based, serialization-based, server-redacted, UI-only, adapter-redacted, or UNKNOWN? Answer: **structural per-principal projection in the engine (`Visibility`), enforced by server-side redaction per viewer; Gym managed observations share the same authority. UI renders only what the server sends. Two caveats below.** Classification: `CODE_DERIVED` (no live-traffic leak test performed).

## 1. The authority: engine `Visibility`

`rules-engine/.../view/Visibility.kt` — KDoc: *"The engine's single source of truth for which card identities a player may see… Client state and decision masking, AI determinization, and Gym observations deliberately share this service."*

Rules (excerpt): `HAND` visible to owner, `actorFor`-routed viewer, teammates, and granted-reveal viewers (else hidden); `LIBRARY` hidden; `BATTLEFIELD/GRAVEYARD/STACK/EXILE/COMMAND` public; plus `isCardIdentityVisibleTo / isCardIdentityVisibleThroughCast` handling face-down permanents, `RevealedTo/MayLookAtInExile/LookAtTopOfLibrary/RevealTopOfLibrary/OpponentsPlayWithHandsRevealed` components, `playerWhoMayLookAtFaceDown`, face-down display names.

This is structural (a single engine service consulted by every projection path), not UI convention.

## 2. Server enforcement (per-viewer redaction, not UI-only)

- `ClientStateTransformer.transform(state, viewingPlayerId, isSpectator)` (`rules-engine/.../view/ClientStateTransformer.kt:77-109`): *"Masks hidden information (opponent's hand, libraries)"*, Rule-613-projected, per-zone `Visibility` checks + individually-revealed cards + opaque library slots (`:119-153`). Libraries send the full ordered entity-ID list (so the client renders a correctly sized stack) with details only for revealed cards — unrevealed slots are opaque IDs rendered as card backs.
- `GameSession.getClientState(playerId)` → per-player transform (`game-server/.../session/GameSession.kt:958-961`) with per-player delta cache (`lastSentState`) and per-viewer `StateUpdate`/`StateDeltaUpdate` (`:1001-1077`).
- `DecisionEnricher.enrich(decision, state, viewerId)` (`game-server/.../session/DecisionEnricher.kt:28-107`): masks face-down source names (`FACE_DOWN_DISPLAY_NAME`) and decision internals per viewer.
- `ClientEventTransformer.transform(events, playerId)`: per-viewer event projection (`GameSession.kt:1011`).
- Pending decisions: only `actorFor(playerId)` receives the question; others get `OpponentDecisionStatus` summary (`:1022-1049`).
- `SpectatorStateBuilder.buildState`: spectator view with every hand masked.
- Web client (`web-client/src/types/gameState.ts`): `ClientZone{cardIds, size, isVisible}`, `ClientCard{isFaceDown, faceDownMode}`; *"For hidden-zone targets, the name is generic ('a card in Opponent's hand') to avoid leaking hidden information."* The client renders server truth; no independent masking authority found in the client (grep hits are CSS/false positives plus these type comments).

## 3. Risk-area review

| Area | Finding |
|---|---|
| Hands / libraries | Masked by `Visibility` + transformer opaque slots; Gym zones carry known-subset only. |
| Temporary look permissions | First-class: `MayLookAtInExile`, `LookAtTopOfLibrary`, `RevealTopOfLibrary`, `RevealedTo` components consulted by `Visibility`. |
| Searches / reveals | `SearchCardInfo` embeds only what the searcher may know; reveal is a visibility side effect on the select/search flow. |
| Face-down (morph/disguise/manifest) | `playerWhoMayLookAtFaceDown`, face-down display names, `TurnFaceUp` procedure; public characteristics only to others. |
| Foretell | `ForetoldComponent`; foretell/variant enumerators (`ForetellEnumerator`) route through exile-with-visibility. |
| Hidden exile | `MayLookAtInExileComponent` per-viewer. |
| Secret choices | `NotedCreatureTypesComponent(secretTo)` (visible only to chooser; "Chosen (secret)" badge); secret numeric bids per-player. |
| Logs | Per-player persistent logs; noisy tap/untap/mana filtered (`GameSession.kt:1071-1076`). Content-level leak review not performed (see Unknown Ledger). |
| Errors | Engine errors return messages (`ExecutionResult.error`); error strings name entities generically — no audit for hidden-name leakage in error text (Unknown Ledger). |
| Events / replay | Transport events projected per viewer; stored `CompactReplay` holds full inputs (server-side, privileged). Replay viewers must go through the same projection (assumed, not verified — Unknown Ledger). |
| Object IDs | Opaque `e<N>` strings; library order visible as opaque ID sequences (positions, not identities). Order-position leakage is inherent to rendering a sized stack and is standard. |
| State hashes / digests | Gym `stateDigest` = SHA-256 over *canonical observable encoding* per perspective (`StateDigest.kt:7-20`) — digest is perspective-scoped, excludes `legalActions`/digest itself. No cross-perspective oracle by construction. |
| Gym observations | Masked (see §4). |

## 4. The Gym question — answered

**Does the Gym/agent interface receive information a human principal should not receive?** For the managed/remote path: **no** — `ObservationBuilder.build(state, perspectivePlayerId, legalActions, revealAll=false)` delegates identity visibility to engine `Visibility`; `ZoneView{hidden, size=true-count, cards=known-subset}`; `PlayerView` counts reflect the perspective; `ObservationVisibilityTest` pins the encoding (hidden zone reports true size, known identities only — unlike client opaque slots). `revealAll=true` is documented debug-only ("never for real self-play training"); `gym-self-play-testing.md` instructs `revealAll:true` for self-play explorations — that is a *methodology* caveat for training runs, not a default leak.

**Caveat (architecture-significant):** direct in-process `GameEnvironment.StepResult.state` exposes the **full `GameState`** to in-process callers. The masked contract lives in `GameGymEnv.observe()` / `MultiEnvService` observations. An in-process pilot that reads `StepResult.state` bypasses hidden-information protection structurally. Integration must pin the masked path; this is an integration-contract requirement, not a finding of leakage in the managed path.

Second caveat: in-process AI (`EngineAiPlayerController`) deliberately consumes the unmasked state. Acceptable as an engine-internal training/simulation consumer; it must never be cited as the external pilot observation.

## 5. Overall hidden-info verdict

Protection is **structural + server-redacted**: one engine authority, per-viewer server projection, masked managed Gym observations, UI rendering only. No UI-only or adapter-redacted dependence found. No-leak *property* (live traffic, logs, errors, replay viewers) remains `UNKNOWN` — the authorities exist, the adversarial verification does not.
