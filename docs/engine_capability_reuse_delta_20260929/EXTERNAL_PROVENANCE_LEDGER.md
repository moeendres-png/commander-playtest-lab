# External Provenance Ledger — WS-CSN-CAPABILITY-DELTA-20260929

Every external influence on this workstream, with its exact identity and its
licensing disposition. Nothing from a copyleft donor was copied,
transliterated or adapted.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`

## 1. Summary

| Donor | Licence | Influence on this workstream | Disposition |
|---|---|---|---|
| `moeendres-png/mage` (pinned fork) | MIT | Native dependency; the mid-game lane calls the pinned engine's `Player` callbacks through the Lab's own session | `REUSE_AS_IS` / `ENGINE_NATIVE_REUSE` — API usage only, no copying |
| `magefree/mage` (upstream) | MIT | Read-only analysis: `Game.cheat`, `GameOptions`, `RandomUtil`, `PlayerImpl`, `TestPlayer`, `GameController.saveGame`/`GameReplay` | `REFERENCE_ONLY` — no code taken |
| `Card-Forge/forge` (pristine `a37a865a…`) | GPL-3.0 | Read-only analysis: `PlayerController`, `Combat`, `GameSnapshot`, `GameState` text format, `MulliganService`; issue titles `#10142`, `#9156`, `#6389` | `REFERENCE_ONLY` — **no code copied, no port performed** |
| `witchesofthehill/manabrew` | **AGPL-3.0-or-later** | Read-only analysis of the parity harness; four techniques recorded as methodology | `REFERENCE_ONLY` — **no code copied, no transliteration, no adaptation** |
| `phase-rs/phase` | dual MIT OR Apache-2.0 | Read-only analysis of `scenario.rs`, APNAP, trigger-ordering tests, filed issues | `REFERENCE_ONLY` — **no code copied** |
| `Cockatrice`, `mtg-python-engine`, `mtg-forge-ts`, `forgeSim` | GPL-2.0 / MIT / GPL-3.0 | Screened and rejected; recorded for completeness | `REFERENCE_ONLY` |
| Official Magic Comprehensive Rules (2026-09-25, sha256 `8d860e45…`) | Wizards IP | Rule references named in the records themselves | Reference only; **no independent official adjudication was performed in this workstream** |

## 2. XMage — the engine actually executed

| Field | Value |
|---|---|
| Pinned commit | `b19596980f2734496ea1896504253e1bdd2756dd` |
| Repository | `https://github.com/moeendres-png/mage.git` |
| Licence | MIT (`config/rules_engines.json → primary_engine.license`) |
| Artifact executed | `org.mage:mage:1.4.61` |
| Runtime proof | `get_provider_version` on both the `main` lane and the new `midgame` lane returned `engine_version=1.4.61`, `engine_commit=b1959698…`, `xmage_code_source=file:/home/moeen/.m2/repository/org/mage/mage/1.4.61/mage-1.4.61.jar` |
| Upstream counterpart | `magefree/mage` master, MIT, read-only |
| Relationship | The pinned commit is a Commander-Lab **compatibility fork** of upstream, `release: "compatibility-fork-unreleased"`. It is **not** pristine upstream, and no result here may be reported as an upstream XMage result. |

**Symbols consumed (called, not copied):**

| Symbol | Where | What is used |
|---|---|---|
| `mage.players.Player` decision callbacks | via `XmageFullGamePlayer` | `priority`, `chooseMulligan`, `choose`, `chooseTarget`, `chooseUse`, `announceX`, `getAmount`, `getMultiAmountWithIndividualConstraints`, `chooseMode`, `chooseTriggeredAbility`, `chooseReplacementEffect`, `selectAttackers`, `selectBlockers`, `playMana` |
| `mage.game.Game.cheat(...)` | inside `XmageNativeStateRestoration` | mid-game placement |
| `mage.game.GameOptions` | `XmageFullGameSession` | `rollbackTurnsAllowed` |
| `mage.game.GameCommanderImpl` | `XmageFullGameSession` | game construction, `setRulesSeed` |
| `mage.watchers.CommanderPlaysCountWatcher` | `XmageNativeStateRestoration` | commander cast-count restore |
| `mage.watchers.CommanderInfoWatcher` | `XmageNativeStateRestoration` | commander damage restore |
| `mage.cards.repository.CardRepository` / `CardInfo` / `ObjectColor` | **new** in `XmageMidgameJsonlBridge.engineCommanderColors` | commander colours read from the engine's own registry, so the scaffolding filler needs no Lab colour table |

**New Lab code written against those symbols (all original):**
`XmageMidgameJsonlBridge.java`, plus the `midgame` branch in `Main.java`, plus
`midgame_lane.py`, plus the probe script and the two test files. No XMage source
was modified and no XMage file was vendored.

## 3. Forge — read-only, GPL-3.0, nothing transferred

| Field | Value |
|---|---|
| Pinned Rules Core | `a37a865a53280dd8ad6fad3384d69611e8c5a42f` (`forge-2.0.14`) |
| Repository | `https://github.com/Card-Forge/forge.git` |
| Licence | GPL-3.0 |
| Files read | `forge-game/src/main/java/forge/game/player/PlayerController.java`, `.../combat/Combat.java`, `.../combat/AttackingBand.java`, `.../GameSnapshot.java`, `.../GameState.java`, `forge-ai/src/main/java/forge/ai/PlayerControllerAi.java`, `.../mulligan/MulliganService.java` |
| Issues read | `#10142`, `#9156`, `#6389` (titles and state only) |
| Code copied | **none** |
| Transliterated | **none** |
| Adapted | **none** |
| Classification | `REFERENCE_ONLY` |

The one Forge design that could tempt a transfer is the `GameState` text
per-card attribute grammar (`|IsCommander`, `|Damage:<n>`, `|SummonSick`,
`|Counters:`) as a scenario-file shape. It is recorded as a **design reference
in prose only**. GPL-3.0 is incompatible with copying it into a
`LicenseRef-Proprietary` project without a licence-authority decision, and no
such decision exists. `DEEP_RESEARCH_IMPLEMENTATION_LEDGER.md` already records
`EC-MANABREW-DIFF-03` as `IMPLEMENTED_AND_RUNTIME_VERIFIED` from methodology
alone; the same posture is preserved here.

**PB-09 note.** Forge behaviour was not attributed to the pinned commit at any
point in this workstream, because the executed Forge evidence in the repository
comes from a Lab fork (`ef958ee9…`) rather than from `a37a865a…`. PB-09 remains
`OPEN` and Coordinator-owned.

## 4. Manabrew — AGPL-3.0-or-later, methodology only

| Field | Value |
|---|---|
| Repository | `https://github.com/witchesofthehill/manabrew` |
| Licence | **AGPL-3.0-or-later** (`LICENSE.md`; GitHub API reports `NOASSERTION` because the file is composite) |
| Status | pre-release; 57 stars; 115 open issues; pushed 2026-09-28 |
| Files read | `.gitmodules`, `forge-harness/.../common/CountingRandom.java`, `.../parity/DeterministicController.java`, `.../common/ParityOrder.java`, `parity/README.md` |
| Code copied / transliterated / adapted | **none** |

The Rust engine is additionally *"a Rust rewrite of Forge"*, so it is AGPL-3.0-or-later
**by derivation from GPL-3.0 Forge as well as by its own licence**. Copying
anything from `manabrew-rs/crates/parity/**`, `parity-debugger/**` or
`forge-harness/**` into this `LicenseRef-Proprietary` project would create an
AGPL-3.0-or-later obligation across the whole work. Nothing was.

**Techniques recorded as methodology, for independent reimplementation only:**

1. Pin the reference engine as a **submodule at an exact SHA** (the Lab
   already pins both engines this way).
2. Instrument the seeded RNG with a **per-call ordinal counter** and an opt-in
   backtrace triggered by a specific bound value, so a divergent draw can be
   localised to a rules layer. Directly applicable to CAP-08.
3. Replace object identity with a **stable cross-engine `parityId`** and
   canonically order every choice space, so two independently implemented
   engines can be compared positionally instead of by pointer.
4. **Snapshot-by-snapshot diff** against a persisted baseline
   (`regression.json` / `parity_ignore.json`) with a first-mismatch reporter and
   a minimising GUI reproducer.
5. **Matrix mode with a master seed** for reproducible fuzzing.

None of these is implemented in this workstream. They are recorded so the
follow-up dispatch does not have to re-derive them.

## 5. phase.rs — dual MIT OR Apache-2.0, reference only

| Field | Value |
|---|---|
| Repository | `https://github.com/phase-rs/phase` |
| Licence | **both** `LICENSE-MIT` and `LICENSE-APACHE` at the tree root; README: "Dual-licensed under MIT or Apache 2.0, at your option" |
| Status | active; 292 stars; pushed 2026-09-29T02:36Z; heavily agent-generated |
| Files read | `crates/engine/src/game/scenario.rs`, `.../mod.rs`, `.../commander.rs`, `.../turns.rs`, `.../players.rs`, `.../visibility.rs`, `.../replay.rs`, `crates/engine/tests/integration/rules/{combat,sba,layers,replacement}.rs`, `.../triggers_ordering_parity_tests.rs`, `crates/server-core/src/persist.rs`, `crates/engine/src/types/game_state.rs` |
| Code copied | **none** |

Licence-wise a transfer *would* be permitted. It was nevertheless not done, for
a substantive reason rather than a licensing one: phase.rs is a different
engine with 92% Commander coverage, and taking its scenario or rule semantics
would create a second Rules engine — forbidden by `AGENTS.md` §2. phase.rs stays
`REFERENCE_ONLY` for independent bug and test intelligence, which is its
documented project posture.

`crates/engine/src/game/scenario.rs` is nonetheless the most valuable external
*design* found in this audit (declarative `at_phase`, seeded construction,
explicit summoning-sickness field, `with_commander`, a `build() -> GameRunner`
handle). It is recorded as prose. The Lab's frozen materialization records
already follow the same shape, so nothing needed to change.

## 6. Other screened projects

| Project | Licence | Screened | Outcome |
|---|---|---|---|
| `Baldugar/mtg-forge-ts` | GPL-3.0 | claims programmatic headless API + save/load + deterministic replay | `HYPOTHESIS` only; 0 stars; no source read; no code taken |
| `Cockatrice/Cockatrice` | GPL-2.0 | tabletop, not a rules engine | rejected |
| `wanqizhu/mtg-python-engine` | MIT | dormant CR attempt | rejected as an authority |
| `thelamesaucegit/forgeSim` | GPL-3.0 | headless AI-vs-AI CLI | rejected, no extra rule semantics |
| `manaflow-ai/manaflow` | MIT | **false positive** — coding-agent tooling | rejected |
| `manaflow`/`managore`/`lands`/`magentic-ui`/`cardflow`/`swordfish`/`mse`/`open-spellbook`/`helios`/`vent`/`magic-ts` | — | **could not be verified to exist** | no claim made |

## 7. Locally duplicated semantics — audit result

The assignment asks explicitly where Lab code duplicates native Rules-Core
semantics so it can be deleted or simplified. Result:

- **No Rules-semantic duplication was found and none was deleted.** The Lab's
  semantic surface is a blocking decision controller, a principal-scoped
  redactor, a decision-scoped option projection, and a typed composition of
  engine restoration APIs. Removing any of them would remove the
  external-decision seam, not a duplicate.
- **One reporting duplication was found and addressed.** Both capability
  payloads published a coarse `starting_state_injection_supported = false`
  while the engine seam published a per-dimension truth beside it. The new lane
  publishes the per-dimension manifest while deliberately leaving the coarse
  bit untouched, because the coarse bit is a truthful statement about a
  *globally complete* injection of arbitrary states, which nothing claims.
- **Recommended follow-up (not done here):** once the current-boundary
  pipeline classifies against the manifest, `config/rules_engines.json` and both
  capability payloads can stop treating the coarse bit as the starting-state
  truth. That is an evidence-semantics change and belongs with the PB-03/PB-09
  owners, not with this workstream.

## 8. Engine-side change gate

No engine-side (XMage or Forge) source change was made and no engine-side
branch was opened. One capability genuinely requires an upstream change and is
therefore issued as a dispatch packet rather than co-edited:

**CAP-08 — Rules RNG split and per-game isolation.**
`repo: magefree/mage` · `files/symbols: Mage/src/main/java/mage/util/RandomUtil.java`
(one process-wide static `Random`), `Mage/src/main/java/mage/game/GameState.java`
(no per-game RNG field), `Mage/src/main/java/mage/players/PlayerImpl.java`
`putCardsOnTopOfLibrary(..., anyOrder=true)` (bare `Collections.shuffle`).
Defect: "in any order" library placements and the opening shuffle are not
seed-controlled, and per-game seed isolation does not hold under concurrency,
so seeded traces are not bit-reproducible. Rules: CR 1.3, CR 103.3, CR 702.91a.
Expected fail-before: two runs at the same seed diverge on library order.
Expected fix-after: both branches route through a per-game RNG owned by
`GameState`. Regression set: seeded duplicate-run determinism plus a
library-order assertion. Lab consumption dependency: PB-08, `RNG_RULES_TAPE`,
`REPLAY_*`, and the new lane's own `rules_seed` claim.

Interim Lab-side mitigation, available today and **not yet applied**:
`GameOptions.skipInitShuffling` plus deterministic library pinning.
