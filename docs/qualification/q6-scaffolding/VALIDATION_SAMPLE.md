# Bounded Actual-Card Validation Sample (tooling validation only)

55 real Forge card scripts at pin `8c7e9afb8e6caee88644b94e25da5852e36f8928`
(`Card-Forge/forge.git`, `forge-gui/res/cardsfolder/...`; per-file sha256
in `tests/q6_scaffolding/fixtures/inputs.json`). Stratified by
grammar/capability family plus adversarial edge classes — not the easiest
cards. Strata: common recognized families (Wrath of God DestroyAll,
Llanowar Elves, Doom Blade, Counterspell, Giant Growth, Rampant Growth);
newly registered verbs (Aggravate DamageAll, Clone, Fog prevention,
Contagion Clasp proliferate, Dreadhorde Invasion amass, Artificial
Evolution ChangeText, Metamorphic Alteration); trigger/mode forms
(Adaptive Training Post DelayedTrigger+condition, Strict Proctor
AbilityTriggered, Archangel of Thune PutCounterAll, Spirit of Resilience
ChangesZoneAll+Clone+DBCleanup); X/SVar edges (Fireball, Ajani Unrelenting
Count-defined X, Astral Cornucopia, Finale of Devastation, Braids SVar-X
name); randomness variants (Frenetic Efreet coin, Mana Crypt coin,
Karplusan Minotaur coin, Delina die, Flay random-discard, Sundering
tutor-shuffle); Commander/multiplayer (Command Tower, Vial Smasher
partner, Council's Judgment vote, Braids each-opponent, Aggressive
Sabotage target-opponent, Fierce Guardianship); replacement/prevention
(Rest in Peace, Doubling Season Replace-verbs, Teferi's Protection);
copy/control (Clone, Phantasmal Image, Aethersnatch ControlSpell→manual);
turn structure (Time Warp); modal (Boros Charm, Cryptic Command);
combat-restriction statics (Propaganda); ST-container static ability
(Circling Vultures); unsupported (Gisela MeldPair, Akroma HandLifeModifier,
Aether Searcher Draft, Cryptic Spires SETCOLORID, Bind/Liberate
CopyFaceFrom faces).

No behavior credit is awarded to any card below. States describe
preparation progress only.

## Routing results (`evidence/routing-table.json`)

34 RULES_ADJUDICATION_REQUIRED · 14 READY_FOR_RUNTIME_QUALIFICATION ·
4 UNSUPPORTED · 3 MANUAL_REVIEW_REQUIRED · 0 AMBIGUOUS. Per-card states,
reasons, capability hypotheses, pre-tags, and question kinds are in the
routing table; before→after transition analysis (every move toward a more
precise state) is in `PARSER_CURATION_REPORT.md` §7.

Queue totals for the sample: MANUAL_SCENARIO_REVIEW 57,
RULES_ADJUDICATION 50, RUNTIME_QUALIFICATION_READY 14,
UNSUPPORTED_CAPABILITY 4, AMBIGUOUS_PARSE 0, PROVENANCE_REVIEW 0
(125 items; see `evidence/queues.json`).

## Determinism evidence

Committed manifest: `evidence/manifest.json`
(`manifest_id: q6-stratified-sample-55`, hash
`3805ea0d59d4cc4da2f6bc570719602a29bfed65f429d84d269b623e38bc6026`).
Re-running the six CLI steps over `tests/q6_scaffolding/fixtures/inputs.json`
reproduces intake IDs, tags, skeleton identities, queue assignments,
ordering, and the manifest hash exactly (`validate` recomputes and
compares; mismatch fails closed). Cross-run reproduction is additionally
proven by `test_manifest_reproducible_across_runs` (179-test suite).

## Parser-accuracy notes (mechanical, not behavior claims)

Adjudicated during implementation from authoritative corpus bytes at the
pin (ordinary in-scope technical decisions, recorded here):

1. Bare `ALTERNATE` face separators are documented format, not ambiguity.
2. `Mode$` on non-Trigger records is an effect/trigger modifier, never an
   automatic modal choice: `AlternativeCost`/`OptionalCost` statics are
   payment choices; `DelayedTrigger` abilities carry trigger conditions;
   `TgtChoose`/`Hand`/`Random`/`Transform`/choice-procedure modes modify
   their ability; only Charm verbs, `AlternateMode:Modal` faces, and
   `CanRepeatModes` mark modal choice. Comma-separated multi-modes
   classify element-wise.
3. X-value detection requires a standalone X token in a numeric slot
   (ability records and SVar effect bodies) or mana cost; SVar
   cross-references named X (Braids) do not count. SVar-X definitions are
   recorded by kind (Count-defined state variables vs condition refs).
4. Library `shuffle` is recorded as SHUFFLE, never discretionary
   randomness; coin/die/random-discard/random-select/random-order are
   separated (word-boundary matching; `troll`/`would die`/flip-cards and
   `AI:RemoveDeck:Random` hint lines excluded).
5. `AI:`/`ODeckHints:` hint lines and `DeckHas`/`DeckNeeds`/`DeckShuffles`
   lines are benign deckbuilding metadata, excluded from game-text
   signals. `DBCleanup:` is an SVar-like effect record; `CopyFaceFrom:`
   is a face-class record.
6. Multiplayer phrases match multi-word constructs; single words
   (vote/monarch/council/team/shared) match on word boundaries
   (`devoted`/`steam` excluded). `target opponent`, `chosen opponent`,
   `attack each/a different`, `starting with you` detected.
7. SVar blocks classify as EFFECT/STATIC/TRIGGER/COMPUTED/COST/OTHER
   fragments; chaining still via SubAbility/Execute edges. SVar-headed
   verbs (Cleanup, Replace*) use the same verb registry.
8. Primary capability selects the most distinctive family; COMBAT and
   LAYER_CHARACTERISTIC families are now assigned (previously COMBAT
   never was). Exotic verbs (Subgame, player control, game outcomes,
   variant tracks) are known tokens that always route to curator review.
