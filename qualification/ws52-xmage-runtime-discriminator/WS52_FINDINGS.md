# WS52 — Runtime Discriminator Findings

Terminal verdict: `XMAGE_RUNTIME_DISCRIMINATOR_MIXED`

- M1 (native decision extraction): PASS within the claimed boundary.
- M2 (selection → native → execution): PASS within the claimed boundary.
- M3 (stale/invalid/ambiguous rejection): PASS within the claimed boundary
  (one documented envelope gap: no separate state-revision field).
- M4 (principal-scoped hidden information): PASS within the claimed boundary.
- M5 (Rules RNG / reexecution): FAIL — production-critical architecture
  blocker (`XMAGE_ENGINE`), demonstrated at runtime.

All runtime facts below are `DIRECTLY_VERIFIED` by the WS52 JUnit suite
(`engine-bridge/src/test/java/org/commanderlab/xmage/Ws52*.java`, 24 tests,
all passing) unless marked `CODE_DERIVED` (source inspection) or `UNKNOWN`.

## M1 — Native Decision Extraction: PASS (bounded)

- Priority/pass + cast/activate: the complete credited priority option set
  EQUALS the live engine `getPlayable` set exactly (oracle recomputation,
  set equality, pass offered exactly once). Representative: Rograkh
  commander-cast option alongside pass and land plays.
- Target: the credited target set EQUALS engine `possibleTargets`
  (complete, no filtering, no fabrication); pilot-visible ids are opaque
  `obj-` handles, never native UUIDs.
- Mode: FAILS CLOSED BY DESIGN — mode UUIDs carry no ledger identity, so
  `XmageDecisionOptionIdentity.externalize` raises
  `COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER` and terminates the channel. No
  mode option can cross the production boundary. "Target OR mode" is
  satisfied via targets; modes are a recorded `CPL_ADAPTER` boundary
  (remediable adapter-side with opaque mode handles; no engine change
  needed; NOT implemented in WS52).
- Bonus: the opening "Select a starting player" frame is natively
  extracted (engine-computed player set, `choose_object`).
- Natural-play survey (seed 5201, rogshai 2P): priority reached with pass
  and non-pass options (`evidence/m1-survey.json`).
- No hidden-zone identity token from the ledger's own forbidden set
  appears in any credited frame.

## M2 — Selection → Native → Execution: PASS (bounded)

- Non-first Rograkh cast selected in game A; pass selected at the
  twin's frame in game B. Post-state: A has exactly the commander on the
  stack (name-verified) with the decision advanced and the acceptance
  transcribed; B has an empty stack (`evidence/m2-selection-execution.json`).
- Target companion: first vs last opaque option bind different native
  players; the bound target is exactly one live engine player.
- Selection travels as the frame-local exact option id through the
  per-frame binding map; nothing is re-resolved by label. The WS48
  label-rematch failure mode is structurally impossible on this path
  (a mis-bound execution could not produce the observed divergence
  pattern: correct commander on exactly one twin's stack).

## M3 — Stale / Invalid / Ambiguous Rejection: PASS (bounded)

Fail-closed proofs (typed errors, no rematching, no fallback, no default):

- Stale `decision_id` → `STALE_DECISION` (transport + controller).
- Replayed consumed frame → `STALE_DECISION` (frame confusion collapses
  to stale rejection; there is NO separate decision-kind field — the kind
  is bound implicitly by `decision_id`. Recorded boundary, still
  fail-closed).
- Wrong `actor_id` → wrong-actor rejection.
- Fabricated/unoffered option → `ILLEGAL_ACTION`.
- Duplicate selection (within bounds, 0..2 target frame) → duplicate
  rejection. (On 1..1 frames the bounds check fires first; ordering
  documented.)
- Empty/over-count selection → bounds rejection.
- Out-of-range numeric (`announceX` 1..6, submit 7) → range rejection;
  valid numeric resolves exactly.
- Missing response / non-JSON / wrong protocol version → transport
  rejection.
- Second game in one JVM process → `full_game_process_already_used`.
- Zero native binding / collapsing bindings → 
  `COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER` (binding-gate units).
- ENVELOPE GAP (recorded, not hidden): no explicit state-revision / state-
  hash field exists; `decision_offset` + `decision_id` serve as frame
  identity. A stale frame is still rejected, but a state hash is not
  asserted. Future envelope work could add pre/post-state fingerprints
  (allowed non-Rules envelope material).

## M4 — Principal-Scoped Hidden Information: PASS (bounded)

Disjoint sentinel decks (seat 0: Islands/Ishai; seat 1: Mountains/Rograkh):

- Own hand fully visible (7 named cards); opponent hand key ABSENT
  (not a redacted array); opponent hand/library names absent from every
  viewer-0 response; mirrored for viewer 1.
- `known_library` / remembered composition empty pre-reveal; public zones
  (command, battlefield, graveyard, stack, counts) visible to all.
- Pending decision frames carry no opponent identity.
- Cross-viewer positive control: each forbidden name IS visible to its
  owner (checks are live, not vacuous).
- Planted-leak control at the exact enforcement point
  (`XmageFullGameObservationGateway.validate`): opponent private name in
  prompt → `HIDDEN_INFORMATION_LEAK`; same name for the owner passes
  (no false positive).
- NOT exercised (remain `UNKNOWN`): face-down/morph identity, face-down
  exile, lookAt/reveal windows, multi-card reveal flows, `GameView`
  source-level redaction (not claimed as runtime PASS).

## M5 — Rules RNG / Reexecution: FAIL (architecture blocker)

Separating the five RNG sub-questions:

1. Engine determinism (control flow): HOLDS for the opening — same seed
   reproduces the exact decision class/seat/bounds sequence
   (`choose_object,mulligan,mulligan,priority*10`).
2. Controlled Rules RNG: the `RandomUtil` global stream repeats after
   `setSeed` (primitive control, DIRECTLY_VERIFIED) — but it is a
   JVM-global manual reset, not per-game seed authority.
3. RNG isolation: ABSENT — any in-process consumer between seed and
   shuffle perturbs the outcome (proven unconfounded on fixed inputs);
   the bridge enforces one-game-per-process by refusal
   (`full_game_process_already_used`), but cross-process equality was NOT
   verified (`UNKNOWN`).
4. Reproducible reexecution: BLOCKED at setup. `PlayerImpl.useDeck:417`
   fills the library from `Deck.getMaindeckCards()`, which collects to
   `Collectors.toSet()` (HashSet, identity-hash order over per-run fresh
   Card objects). Library LOAD order therefore varies per run; the seeded
   Fisher-Yates `Library.shuffle` shuffles different inputs at the same
   seed. Runtime proof: identical construction, same seed → different
   98-card preload orders → different dealt hands
   (`evidence/m5-setup-order-divergence.json`,
   `evidence/m5-control-flow-vs-identities.json` with `"hands_equal":false`).
   Fixing this requires an ENGINE change (deterministic load order),
   forbidden in WS52 (engine read-only). Classification: `XMAGE_ENGINE`.
5. Semantic Replay: UNSUPPORTED — additionally, no-arg
   `Collections.shuffle()` (production-reachable: `PlayerImpl:1061,1204`
   plus card effects) ignores `setSeed` by construction, and
   `bookmarkState`/`restoreState` rewind game state but NOT the RNG
   stream (proven: order restored, stream advanced), so a snapshot alone
   cannot reexecute.

M5 real Rules-random events exercised: game-start setup shuffle
(`GameImpl:1314-1317` → `player.shuffleLibrary`) and a mid-game
`Library.shuffle` (snapshot test). No pilot randomness substituted.

## Engine / Adapter / Harness classification

- `XMAGE_ENGINE`: M5 setup load-order nondeterminism; unseeded no-arg
  shuffles; global RNG without per-game stream/serialization; snapshot
  without RNG position. All production-reachable; all require engine
  redesign for full deterministic reexecution.
- `CPL_ADAPTER` (boundary, fail-closed by design, future remediation
  candidate): mode frames cannot cross (no ledger identity for mode
  UUIDs); no state-revision hash in the envelope. No existing adapter
  file was modified in WS52.
- `CPL_HARNESS` (found and repaired during WS52, test-owned only):
  engine thread must carry the `THREAD_PREFIX_GAME` name
  (`ThreadUtils.ensureRunInGameThread`, 18 violations → player loss
  before the fix); pilot submits need an advance barrier
  (stale-read race, mirrored from `XmageFullGameSession`);
  direct witnesses require per-seat controllers on a parked engine
  (pre-start range checks reject direct calls; phantom non-participant
  rejected).
- Evidence hygiene note (not a defect): `XmageProvider.ENGINE_COMMIT`
  declares `77d7646d` while WS52 built/ran `0c1f455e`; the complete
  inter-pin delta is 6 commander-history/restore files, none consumed by
  any exercised lane (verified by import grep). Behavior on consumed
  surfaces is identical; both pins' trees re-verified.

## Production-readiness consequences

- The authoritative external-pilot slice (observe → legal options →
  select → native bind → execute → ack, fail-closed) WORKS at runtime
  for priority/cast/activate/target/boolean/numeric classes.
- Production-quality controlled Rules RNG and deterministic reexecution
  REQUIRE a material XMage engine redesign (deterministic setup load
  order, per-game RNG authority, RNG state serialization, elimination of
  unseeded Rules-reaching sources). This is a successful discriminator
  outcome and must not be hidden behind an adapter.
