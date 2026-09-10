# RQ-X1 — Architecture Reversers (CODE_DERIVED unless marked)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`. "Reverser" = a finding that
moves the Forge-vs-XMate decision needle WITHOUT a runtime mirror (cheapest
UNKNOWNs first). Forge comparison is by ARCHITECTURE FACTS, never by scalar
score (hard gate).

## 1. Reversers IN FAVOR of XMage (engine seam is cleaner than provider history suggested)

**R-1. Authoritative legal sets are engine-produced, wire-exposed, and
server-revalidated (not GUI/AI/adapter).** Every dialog: engine builds exact
set → wire carries it (`Set<UUID>`/`Map<UUID,String>`/`Choice`/min-max) →
client echoes member → server revalidates against CURRENT set → resolution
re-gates (`stillLegal`/ZCC). `possibleTargets.contains` ×5
(DIRECTLY_VERIFIED); simulation guard `canCallFeedback` (structural).
REVERSAL: the "adapter would reconstruct legality" fear is FALSE for a
UUID-echoing adapter. The seam an external pilot needs EXISTS natively.
Weight: HIGH — this was the central UNKNOWN of question 1, resolved
CODE_DERIVED (needs R-M1 runtime confirmation).

**R-2. Exact native binding by UUID+ZCC (WS48 lesson satisfied).**
Random-v4 UUIDs per object/ability/effect/mode/player/game/token-instance;
`MageObjectReference` id+zcc; `map.get/contains/id.equals` consumption;
`getFixedResponseUUID` verbatim except documented MDFC normalization;
`Choice` strings membership-checked. Label matching does NOT suffice and is
NOT needed. REVERSAL: selection→execution binding is PROVABLY EXACT at source
level. Weight: HIGH (needs R-M2 stale/duplicate runtime proof).

**R-3. Hidden info is server-redacted per-viewer projection, not UI-only.**
N distinct `GameView`s per recipient from `game.copy()`; `myHand`-only-own
(DIRECTLY_VERIFIED); counts-only library/hand; `canShowAsControlled` gates;
face-down/manifest/foretell/hidden-exile redaction with `ManifestTest`
in-process pins; per-recipient decision dialogs; no cheat-proof marketing
claims found (searched). REVERSAL: the "network-server ⇒ leak" fear is not
sustained at source level; projection is REAL SERVER LOGIC. Weight: MEDIUM —
tempered by UUID/set-number exposure + single-broadcast logs + zero
no-leakage suite (see counter-reversers).

**R-4. Variable player counts, not fixed-4.** `CommanderFreeForAllType`
min 3 / max 10 (DIRECTLY_VERIFIED); dynamic seat count from match init;
priority/APNAP/trigger-order/combat-defender/elimination/range machinery all
N-player general; no `getNumPlayers()` trust needed (stale field documented).
REVERSAL: no 4-player architecture anchor to fight; 2–5P conformance is a
TESTING obligation, not an architecture obstacle. Weight: MEDIUM.

**R-5. Test corpus as methodology asset.** 1957/1977 classes, 6851 strict
`@Test` (DIRECTLY_VERIFIED), strict scripted-choice discipline, 4P Commander
+ FFA + range + vote + leave-game patterns. REVERSAL: clean-room case design
starts from a large existence proof of WHAT to cover. Weight: LOW-MEDIUM
(methodology only, never authority).

**R-6. Historical FALSEs downgraded to provider-scope.** Engine HAS mulligan,
targets, modes, trigger ordering, per-decision legality+submission; LACKS
only global enumeration, unified submission, seed, replay. Four of eight
historical gaps are adapter-solvable without engine changes. Weight: MEDIUM.

## 2. Counter-reversers AGAINST XMage (mirror-cost raisers)

**C-1. No request/state identity; no stale rejection; no execution ack.**
`rg stateId|requestId` zero hits (DIRECTLY_VERIFIED). Late echoes validated
against CURRENT sets (fail-open retry, not fail-closed reject); first-option
fallbacks on non-response; no ack/identity envelope. An external pilot MUST
build idempotency/staleness itself and can NEVER prove no-missed-update from
engine evidence alone. Weight: HIGH.

**C-2. RNG is global, shared, unseeded in places, consumption-unstable.**
Single static `Random` (DIRECTLY_VERIFIED) + no-arg shuffles in Rules paths +
per-call SecureRandom + iteration-order draws + AI sharing the stream. No
per-game seed, no serialization, no reset. Deterministic multi-game
simulation and Semantic Replay are UNSUPPORTED without engine modification.
Weight: VERY HIGH — the single biggest structural weakness for a simulator
whose mission REQUIRES reproducible simulations.

**C-3. Replay is an outdated snapshot-stepper, self-declared unused.**
"Outdated and not used. TODO: delete" + "not working correctly yet"
(DIRECTLY_VERIFIED). No journal, no reexecution. A mirror must build
journaling (feasible, non-rules) AND RNG determinism (needs engine changes or
provably sufficient capture). Weight: HIGH.

**C-4. GUI preferences inside the HumanPlayer rules path + controller hijack
+ destructive leave + UUID tracking exposure.** External pilot must either
reuse HumanPlayer (drags GUI state into qualification) or reimplement the
dialog loop (re-host risk); must reimplement principal projection; must
snapshot before elimination; must accept UUID correlation. Weight: MEDIUM
(each solvable, jointly expensive).

**C-5. No global legal-action enumeration.** Playability is per-dialog and
per-priority-click-set; "list all legal actions now" is not an engine query.
A pilot that needs global enumeration (search, planning, pilot improvement)
must drive the seam dialog-by-dialog or compute from state (reconstruction
risk). Weight: MEDIUM-HIGH depending on pilot architecture.

## 3. Net assessment (no scalar score — qualitative, for Coordinator)

For a pilot architecture that (a) echoes UUIDs dialog-by-dialog, (b) accepts
adapter-built identity/staleness envelopes, (c) reimplements projection from
`GameView` semantics, and (d) does NOT require cross-game determinism from
the engine: XMage's seam is GENUINELY GOOD — R-1/R-2/R-3/R-4 jointly say the
narrow mirror has real information to gain, and the engine is cleaner than
provider history implied.

For a simulator whose mission REQUIRES reproducible simulations, seed
authority, and semantic replay: C-2/C-3 are structural and UNFIXABLE without
engine modification (a Rules-authority-boundary change). The mirror can
QUANTIFY the gap (falsify seed-replay in days) but cannot CLOSE it.

TheForge-centric lead reverses IFF the Coordinator's pilot architecture is
type-(a) AND the RNG/replay requirements can be satisfied adapter-side or
deferred. That conditional is an AUTHORITY decision (mission scope, provider
strategy), not a technical one — hence MEDIUM, not HIGH (see final audit).
