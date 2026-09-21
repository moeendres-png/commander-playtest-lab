# Handoff — FULL107 executor M1: fixture-deck importability verdict (2026-09-22)

## Verdict: INFEASIBLE on current bridge without fixture deviation

All 7 NATURAL_GAME_START denominator fixtures pin synthetic decks
(99× Mountain + mock commanders `cmd:PN-A`). The bridge importer
(`XmageDeckImporter.importCommanderDeck`) is deliberately real-cards-only:

- `resolveMechanicalCard` → `CardRepository.instance.findCard(name, true)`;
  unknown names throw `UNKNOWN_CARD_NAME` (`cmd:P1-A` is not a real card).
- `Deck.load(lists, ignoreErrors=false, mockCards=false)` — mocks refused.
- XMage `Commander` validator additionally requires a real legendary
  creature as commander.

No code path exists to construct these fixture decks. Verified by source
(`XmageDeckImporter.java:243-264`, `:148-153`), no runtime probe needed
(the failure is deterministic by construction; a live probe would only
re-confirm the throw).

## Transport: PROVEN end-to-end (update)

- `XmageFullGameMulliganDriveTest` GREEN live: 4P RogShai, self-selected
  starting player + 4 scripted keeps via projected actions only
  (exact-one-match, fail-closed), explicit `next_actions_status` per
  submit, mulligan → priority advancement, executor-side event log
  (starting-player + per-seat keep events).
- Executor-side observation suffices for required_events (no engine audit
  export needed on the full-game lane; engine audit stays a nice-to-have).
- Bottom-count observability solved via new read-only public-zone-counts
  projection (counts only, no hidden leak).
- Transport finding: London bottoming surfaces as an explicit `target`
  bottom-selection decision (min=max=1 over the 7-card hand); answered by
  least-UUID rule among provably-identical Mountains (deck homogeneity
  by construction) with full-hand-completeness assertion.

Prior assessment below is superseded by the proven items above (kept for
provenance; terminal postconditions were operationalized per fixture in
the WS05 tests):

- decision_script → projected legal actions: FEASIBLE pattern exists
  (mulligan keep selection live-proven in
  `XmageFullGameGenericActionSubmissionTest`); match action_type+actor,
  fail closed on zero/multiple match; forbidden fallbacks prohibited.
- audit events → required/forbidden events: PARTIALLY OPEN (event
  granularity for rounds/bottom-counts unverified against the B4-D stream).
- terminal postconditions: natural language → needs per-fixture
  operationalization (state observation supports hand sizes/counts).

## Pivot options (exact)

- Option 1 — synthetic/mock-deck bridge extension: contradicts the
  deliberate real-cards-only design + Commander validator; needs Rules
  authority review (mock legality) and bridge-owner approval. NOT
  recommended unilaterally.
- Option 2 — real-deck equivalents (e.g., RogShai runtime decks): deviates
  from fixture `deck_state`/`requested_state_digest`; any PASS on
  substituted decks is NOT fixture evidence. Requires Coordinator
  adjudication on fixture deviation before a single run.
- Option 3 (recommended): Coordinator adjudicates Option 1 vs 2; until
  then, FULL107 execution stays NOT_RUN with this documented gate. The
  7 natural-start fixtures remain the ready queue once unblocked.

## State

No production code changed in this workstream (docs only). All findings
CODE_DERIVED from integrated main bytes (51c224a0). Nothing to integrate;
no PR opened.
