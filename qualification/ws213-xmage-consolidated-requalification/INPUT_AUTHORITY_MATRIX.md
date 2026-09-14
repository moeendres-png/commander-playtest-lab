# WS213 INPUT_AUTHORITY_MATRIX

Read-first inspection (pre-mutation) plus reference-root verification.
Classification per row: DIRECTLY_VERIFIED (ran/read), CODE_DERIVED (source).

| # | Input | Authority / location | Finding |
|---|-------|----------------------|---------|
| 1 | Lab XMage pin (pre-WS213) | `config/rules_engines.json`, `XmageProvider.ENGINE_COMMIT`, `~/.m2` jars | `cfc36f44` (1.4.61); Maven-local install |
| 2 | Game construction/start/init order | `XmageFullGameSession` ctor + `runEngine`; `GameImpl.start:1140` | construct → players/decks → `start()` on engine thread → `init` → `play` |
| 3 | `RandomUtil.setSeed` uses | `XmageFullGameSession.java:90` (sole production use) | Process-global seed pre-construction; retired by WS213 (no non-Rules purpose retained) |
| 4 | `setRulesSeed` / `setRequireExplicitSeed` | WS212 `Game.java:308,333`, `GameImpl.java:299,321,1311` (DIRECTLY_VERIFIED in reference root) | Explicit replace-stream + fail-closed `init` gate (`WS54: game init requires an explicit Rules seed`); zero Rules consumption between construction and `start` |
| 5 | `seed_supported` reporting | `XmageFullGameJsonlBridge:373` (`true`, unearned); `XmageProvider:64` (`false`, B4 lane) | Rebound to live `rules_seed_binding` proof per run |
| 6 | Generic LegalAction/ActionProposal flow | `XmageFullGameActionProjection` (project/toDecisionResponse) + controller + session legal/submit | Decision-scoped; actor/revision/membership/type/bounds enforced; fail-closed; no filtering/AI/GUI/second-engine |
| 7 | Native concession availability/execution | WS211 `Game.canConcede` (`Game.java:515`, `GameImpl.java:1733`: not-ended + in-game, no priority/stack/turn-control) + `Game.concede` (`GameImpl.java:1743`: stale guard → inform → `PlayerImpl.concede` → queue + `lost`) | Bound via offer/submit with actor==subject==exact principal + one-shot token; `leave` on game thread |
| 8 | Combat numeric-decision projection | `XmageFullGamePlayer.getMultiAmountWithIndividualConstraints` + projection `multi_amount` → structural numeric | Seam signature unchanged by pin (`Player.java` untouched); WS206 `CombatGroup` trample/free seams call it with validation + bounded re-request + fallback |
| 9 | Principal-scoped observation | `XmageFullGameStateRedactor.actorView` | Actor-only hand/mana; opponents counts + public zones; grant-scoped library only |
| 10 | WS207 overlay/catalog/matrix | `qualification/ws207-xmage-qualified-scenario-setup/` | 5 qualified (A03/9788, C01/10704, C03/11412, D06/11912, F01/13405) + H01 CLONE_FIRST/16238, NO_HUMILITY/16859; 8 UNKNOWN + E02/G04 carried blocked; dual-fixed binding; qual-only hook retired by WS213 |
| 11 | WS208 root cause | `08658972` (in-clone history; ref worktree policy-denied, consumed via `git log/show`) | Offer nondeterminism isolated to engine GameRandom seeding (layer A) |
| 12 | WS212 LAB_SUCCESSOR_SPEC | `research/ws212-xmage-rules-rng-seed-authority/LAB_SUCCESSOR_SPEC.md` | Repin → bind `setRulesSeed`+`setRequireExplicitSeed` post-construction/pre-start → retire RandomUtil → truthful seed_supported → rerun batteries/twins/combat/concede/hidden-info, no auto credit |
| 13 | WS214 final handoff | `research/ws214-xmage-testplayer-rules-rng-harness/FINAL_HANDOFF.md` | 10/10 harness tests; `TestPlayer.java` test-sourceset only; `TESTPLAYER_PRODUCTION_REACHABLE=NO`; `D5_TWIN_EQUALITY=UNKNOWN` left to WS213; FULL107 NOT_RUN |

Impact map: see workstream state `impact_map` (lineage, materialization,
session binding, concession design, pin consumers, sealed-history rule).

Machine companion: `INPUT_AUTHORITY_MATRIX.json` (this table, abridged).
