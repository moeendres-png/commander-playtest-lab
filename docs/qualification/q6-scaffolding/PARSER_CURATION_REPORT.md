# Q6 Parser / Capability Curation Report (Task 2B)

Scaffolding only. `BEHAVIOR_PASS = NOT_MEASURED` · `BEHAVIOR_CREDIT = 0` ·
`COVERAGE_PROMOTION = FALSE` · `FULL107 = NOT_RUN` · `FORGE_RUNTIME = NOT_RUN`
· `XMAGE_RUNTIME = NOT_RUN` · `ARCHITECTURE_FREEZE = NOT CLAIMED` ·
`PRODUCTION_PROVIDER = NOT SELECTED`.

## 1. Source lock (re-verified 2026-09-10, before any Task-2B edit)

- Base branch `qualification/q6-scaffolding-pipeline-20260910`:
  HEAD `a33d5d97cef4df46129e543707886e4a42e64f4c`,
  tree `b7e640cbb9b5cb957ec9e46055817a2a778b2d04` — matches contract.
- D3 research branch `research/d3-q6-import-automation-20260910` (in
  `/home/moeen/code/mage-d3q6`): HEAD `a766f9006c006feed9b05e336f4ba2d07cdb8ea9`,
  tree `6c429f6876c5d5ed60aa36512b99901e15e34c0e` — matches contract.
- Forge corpus pin `8c7e9afb8e6caee88644b94e25da5852e36f8928`
  (`Card-Forge/forge.git`, "Fix Nori, Teller of Tales"): resolves in
  `/home/moeen/forge-corpus`; `ls-tree -r <pin> -- forge-gui/res/cardsfolder`
  counts **33,666** `.txt` files. Corpus is read streaming-only via
  `git ls-tree` + `git cat-file --batch`; it is never vendored.

## 2. D3 historical facts (re-verified, NOT promoted)

Read directly from `research/d3-q6-import-automation/results_summary.json`
and `aux_census.json` at the D3 HEAD above. These are historical research
evidence; Task-2B recomputes everything it uses as a result.

| D3 claim | Re-verified value |
|---|---|
| corpus population | 33,666 scripts |
| stratified prototype sample | 1000 |
| parsed / structured / skeleton | 974 / 933 / 974 |
| manual-review / unsupported / ambiguous | 528 / 186 / 26 |
| false-positive probes | 36 |
| ability-verb gap (unknown verbs) | 70 distinct / 443 files |
| trigger gap (unknown modes) | 15 distinct / 46 files (`tmode_unknown_files`) |
| trigger files total | 183 (`tmode_files`) |

Note: D3's 186 unsupported files were dominated by `topkey:AI` (180).
Task-2A allowlisted `AI:` hint lines as benign metadata, so the Task-2B
full-corpus recount starts from a different (documented) baseline.

## 3. Task-2B BEFORE measurements (Task-2A baseline, full pinned corpus)

Tool: `tools/q6_scaffolding/corpus_inventory.py`, note
`before;q6-forge-parser-0.1.0;task2A-baseline`.
Evidence: `docs/qualification/q6-scaffolding/evidence/corpus-inventory-before.json`
(content inventory hash `b8d0b2b4f274ea88`, 33,666/33,666 files readable).

Output layers are kept separate: TOKEN OBSERVATION (raw regex counts, no
parser) / PARSER INTERPRETATION (current parser features) / CAPABILITY
HYPOTHESIS (classifier + router; hypotheses only).

| Metric | BEFORE (full corpus) |
|---|---|
| PARSE_RATE (no blocking `missing_colon`/`svar_missing_name_sep`) | 1.0000 (33,666/33,666) |
| STRUCTURED_RATE (≥1 param record) | 0.9467 (31,870) |
| SKELETON_ELIGIBLE_RATE | 1.0000 (33,666) |
| MANUAL_REVIEW_RATE (`MANUAL_REVIEW_REQUIRED`) | 0.0428 (1,442) |
| RULES_ADJUDICATION_RATE (`RULES_ADJUDICATION_REQUIRED`) | 0.6382 (21,483) |
| UNSUPPORTED_RATE | 0.0051 (171) |
| AMBIGUOUS_RATE | 0.0003 (11) |
| READY_FOR_RUNTIME_QUALIFICATION | 10,559 (0.3137; prerequisites ready, NOT behavior PASS) |
| UNKNOWN_VERB distinct / file-occurrences | 104 / 1,667 |
| UNKNOWN trigger-mode distinct / file-occurrences | 114 / 1,724 |
| Observed verb distinct / observed trigger-mode distinct | 152 / 137 |
| False-positive probes (ability without typed signals) | 682 |
| Commander-damage signal files | 0 (absence retained; cf. D2 XMage finding) |

Ambiguity gap vs D3 (26/1000 sample vs 11/33,666 census): D3's sample was
stratified toward trigger/svar-heavy scripts; the census number is the
Task-2B measurement. Both stay historical-vs-current separated.

Remaining unsupported topkeys (files): `HandLifeModifier` 106,
`Draft` 24, `CopyFaceFrom` 23, `MeldPair` 14, `SETCOLORID`/`Lights`/
`DBCleanup`/`ODeckHints` 1 each. Diagnostics: `unknown_topkey` 197,
`duplicate_param` 13. Bare `ALTERNATE` face separators: 875 (documented
format, not ambiguity).

## 4. Gap ranking (Pareto backlog; frequency × breadth × relevance × ambiguity risk × locality × Rules-risk)

Ranked highest value first. "Safe" = closable with mechanical shape labels
plus adjudication routing, without encoding Rules semantics.

1. **Verb registry expansion (P0).** 104 unknown distinct verbs, 1,667
   file-occurrences. Head: `DamageAll` 174, `DestroyAll` 161,
   `CopyPermanent` 91, `SetState` 82, `PutCounterAll` 71, `AnimateAll` 60,
   `PeekAndReveal` 59, `CopySpellAbility` 47, `DigUntil` 45, `NameCard` 40,
   `ChooseColor` 38, `GenericChoice` 36, `AddTurn`/`Reveal` 33,
   `RevealHand` 32, `PermanentCreature`/`UntapAll` 30. Fix: data-driven
   verb registry (verb → mechanical shape + narrow flags); unknown verbs
   stay exactly reported with no catch-all "supported".
2. **Trigger-mode registry (P0).** 114 unknown distinct modes, 1,724
   file-occurrences. Head: `DamageDoneOnce` 202, `ChaosEnsues` 139,
   `AttackerBlocked` 126, `ChangesZoneAll` 122, `BecomesTarget` 115,
   `SetInMotion` 84, `TapsForMana` 64, `AttackerBlockedByCreature` 63,
   plus `ValidMode$`-only references (`RoomEntered`, `BecomesTargetOnce`).
   Fix: explicit registry = observed `T/Mode$` ∪ `ValidMode$` values;
   `Once`-variants recorded as first-time-only markers, raw values kept.
3. **Ability/static mode taxonomy (P1).** `A/Mode$` today all imply
   modal choice, but corpus shows trigger-conditions (`SpellCast`,
   `Phase`, `ChangesZone` on `DelayedTrigger` abilities), targeting
   selectors (`TgtChoose` 133), zone selectors (`Hand` 42), randomness
   selectors (`Random`, cf. Flay), transform modes (`Transform` 68).
   `S/Mode$` has 38 distinct values (cost mods, combat/cast restrictions,
   `AlternativeCost` 148); only `AlternativeCost` is interpreted today and
   the `COMBAT` capability family is never assigned. Fix: mode registries
   with mechanical classes; generalize cost-choice detection; map
   combat-restriction statics to `COMBAT` hypotheses.
4. **Multiplayer signal precision + coverage (P1).** Substring `vote`
   matches 68 files vs 42 word-boundary (`devoted`/`devotion` false
   positives); `team` 94 vs 39 (`steam` etc.). Parser misses `target
   opponent` (538+284 hits), `chosen opponent`, `attack each/a different`,
   `starting with you` (15). Fix: word-boundary matching + added generic
   phrases (grammar constructs, not card names).
5. **Randomness sub-taxonomy (P1).** Raw variants: `random` 3,030,
   `shuffle` 1,473, `dice` 154, `flip` 109, `coin` 94, `flip a coin` 74.
   Preserve: shuffle ≠ discretionary randomness. Add mechanical kinds
   (shuffle / coin / die / random-discard / random-select / unknown).
6. **Replacement-form inventory surfacing (P2).** `R/Event$` head: `Moved`
   957, `DamageDone` 218, `Untap` 156, `Counter` 117, `Draw` 37, ... (34
   distinct); `ReplacementResult$`: `Updated` 838, `Replaced` 4;
   `ReplaceWith$` heads led by `ETBTapped` 615, `LandTapped` 126,
   `Exile` 70. Structure: hypotheses + skeleton prerequisites +
   adjudication requirements only; no replacement/layer semantics in the
   parser (hard STOP line).
7. **Topkey curation (P2).** `DBCleanup:` (1 file) is an SVar-like
   `DB$ Cleanup` record — parse generically. `CopyFaceFrom:` (23) is a
   split-face copy marker — face-class record. `ODeckHints:` (1) matches
   the benign deck-hint shape — allowlist with reason. `HandLifeModifier`
   (106, Vanguard/avatar stats), `Draft` (24, draft context),
   `SETCOLORID` (1, deck-construction choice), `Lights` (1, Un-set
   variant) stay UNSUPPORTED with registry entries.
8. **Shape-driven flags (P1, with verb work).** Registry shapes drive
   existing flags generically: copy shapes → `COPY_CONTROL`;
   coin/die/random-select shapes → `RANDOMNESS`; `ReplaceEffect` →
   `REPLACEMENT_EFFECT`; `DelayedTrigger`/`ImmediateTrigger` →
   `TRIGGERED_CHOICE`; characteristic-setting verbs
   (`Animate`/`AnimateAll`/`SetState`/`ChangeText`/`AlterAttribute`) and
   prevention verbs (`Fog`/`PreventDamage`/`Regenerate`/`Protection`) →
   Rules-adjudication questions (no semantic encoding).
9. **SVar fragment kinds + cost-head observability (P2).** 2,482 SVar
   blocks headed by `Mode$` (referenced static/trigger fragments, e.g.
   Abeyance) vs `DB$` effect bodies (38,611) vs `Count$` computed values
   (6,178). Record fragment-kind counts (no routing change; `nested_svar`
   review covers). Cost heads (`T` 3,027, `SubCounter` 697, `Sac` 426,
   `AddCounter` 409, `tapXType` 135, `Waterbend` 25, ...) stay observed.

## 5. Automation ceiling (correctly NOT automated)

- Exotic verbs (`Subgame`, `RestartGame`, `ControlPlayer`, `WinsGame`,
  `LosesGame`, `BidLife`, `AssembleContraption`, ...) register with an
  explicit curator-review flag: known token, but always `MANUAL_REVIEW`.
- Full replacement/prevention/layer/copy/control Rules: never encoded.
  Richer interpretation stops at adjudication routing.
- Variant-game directives (`HandLifeModifier`, `Draft`, `SETCOLORID`,
  `Lights`) stay `UNSUPPORTED` (need human/variant setup).
- Commander-damage support: 0 script signals; absence recorded, never
  inferred.
- The 10 Task-2A `RULES_ADJUDICATION` queue items are not resolved here;
  Task-2B only improves their machine-readable context.

## 6. Task-2B AFTER measurements (same corpus, curated parser)

Tool: same `corpus_inventory.py`, note listing `q6-forge-parser-0.2.0` plus
all three grammar registries. Evidence:
`docs/qualification/q6-scaffolding/evidence/corpus-inventory.json`
(same content inventory hash `b8d0b2b4...`: the corpus did not change, the
parser did). Metrics sealed in `evidence/parser-before-after.json`.

| Metric | BEFORE | AFTER |
|---|---|---|
| PARSE_RATE | 1.0000 | 1.0000 |
| STRUCTURED_RATE | 0.9467 | 0.9467 |
| SKELETON_ELIGIBLE_RATE | 1.0000 | 1.0000 |
| MANUAL_REVIEW_RATE | 0.0428 (1,442) | 0.0369 (1,243) |
| RULES_ADJUDICATION_RATE | 0.6381 (21,483) | 0.6372 (21,451) |
| UNSUPPORTED_RATE | 0.0051 (171) | 0.0043 (146) |
| AMBIGUOUS_RATE | 0.0003 (11) | 0.0003 (11) |
| UNKNOWN_VERB distinct / occurrences | 104 / 1,667 | **0 / 0** |
| UNKNOWN_CONSTRUCT (verbs+modes) | 218 | **0** |
| READY_FOR_RUNTIME_QUALIFICATION | 10,559 | 10,815 |

BEHAVIOR_PASS = NOT_MEASURED · BEHAVIOR_CREDIT = 0 ·
COVERAGE_PROMOTION = FALSE. Parser-rate improvement is mechanical
preparation quality, never simulator correctness.

Composition notes: READY +256 comes from resolved unknowns with no
remaining adjudication need (vanilla mass removal/turn spells) while 199
manual items moved into more precise states; adjudication holds ~steady
because layer/prevention/multiplayer questions were added where the
mechanics genuinely need them (COMBAT 1,241 and LAYER_CHARACTERISTIC 1,496
families newly populated; X_COST_VALUE 1,307→2,661 via SVar-body numeric
slots; multiplayer 2,354→3,182 via new phrases minus devoted/steam false
positives; randomness 3,432→1,031 after hint-line/shuffle separation with
kinds SHUFFLE 1,460 / SELECT 633 / ORDER 393 / DIE 148 / DISCARD 111 /
COIN 86 / UNKNOWN 17).

## 7. Review-queue impact (55-card stratified sample, before→after routing)

Every observed transition moves into a *more precise* state; no item is
silently claimed as supported. Examples of every transition class:

- UNSUPPORTED → RULES_ADJUDICATION_REQUIRED: Bind/Liberate
  (`CopyFaceFrom` now a face record; copy question), Spirit of Resilience
  (`DBCleanup` now parsed; copy+trigger questions).
- MANUAL → RULES_ADJUDICATION: Artificial Evolution (ChangeText →
  layers question), Fog (prevention question).
- MANUAL → READY: Wrath of God (DestroyAll shaped, generic prereqs
  complete), Time Warp (AddTurn shaped).
- MANUAL reasons narrowed: Aggravate keeps `nested_svar_chain`, drops the
  unknown-verb reason.
- ADJUDICATION → MANUAL (more precise): Aethersnatch (ControlSpell needs
  curator design, not just copy adjudication).
- READY → ADJUDICATION (under-claim fixed): Aggressive Sabotage
  (target-opponent signal).
- Questions added: Ajani/Vial Smasher (+X_COST_VALUE), Rest in Peace
  (−spurious RANDOMNESS from the `AI:RemoveDeck:Random` hint line).

Full-corpus MANUAL 1,442→1,243 (−199) decomposes into unknowns resolved
to READY (+256 net with other flows) and unknowns/manual-verbs routed to
precise MANUAL/ADJUDICATION reasons. REVIEW-queue totals for the
55-sample: MANUAL_SCENARIO_REVIEW 57, RULES_ADJUDICATION 50,
RUNTIME_QUALIFICATION_READY 14, UNSUPPORTED_CAPABILITY 4,
AMBIGUOUS_PARSE 0, PROVENANCE_REVIEW 0.

## 8. Pass-impossibility regression (extended, all green)

179/179 `tests/q6_scaffolding` tests pass; `ruff check` and `ruff format
--check` clean. New structural proofs: registries and both inventory
documents validate clean under the output gate; contaminated
registry-shaped input is rejected; a script smuggling `behavior_pass$`
fails closed at `classify` (exit 2, no partial output); intake stays
byte-opaque (content gates live downstream); unknown tripwires never route
READY; manual-review and new-question artifacts carry no credit fields.
All Task-2A pass-impossibility tests remain green unchanged in intent.

## 9. Automation ceiling (confirmed, not crossed)

Subgame/RestartGame/player-control/game-outcome/variant-track verbs are
known tokens that always route to curator review. Replacement, prevention,
layer, copy/control interpretation stops at hypotheses plus adjudication
questions; the parser records no timestamps, layer orders, outcomes, or
legal options. Variant-game directives stay UNSUPPORTED. Commander damage:
0 corpus signals; absence recorded. The 10 Task-2A RULES_ADJUDICATION
items are not resolved here; their machine-readable context improved
(exact construct, verb/mode values, witness requirements).
