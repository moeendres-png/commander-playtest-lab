# Q6 Capability Inventory (Task 2B, actual-card census)

Scaffolding only. No behavior PASS is measured or awarded here. No behavior
credit. No coverage promotion.

Source: full pinned-corpus census (`evidence/corpus-inventory.json`,
`q6-forge-parser-0.2.0`, inventory content hash
`b8d0b2b4f274ea88...`; corpus `Card-Forge/forge@8c7e9afb`, 33,666 files).
Counts below are files exhibiting the mechanical signal. Families are
capability *hypotheses* (parser interpretation layer), never behavior
verdicts. Shapes name mechanical structure only.

## Capability families (classifier hypotheses)

| Family | Files | Note |
| --- | --- | --- |
| MANA_PAYMENT_CHOICE | 33,046 | mana costs / mana abilities / payments |
| ZONE_CHANGE | 19,569 | zone movements with timing questions |
| TRIGGERED_CHOICE | 14,429 | triggers incl. ability-carried conditions (49) and DelayedTrigger verbs |
| TARGET_SELECTION | 7,405 | ValidTgts/target signals |
| SBA_SENSITIVE | 7,739 | static/replacement presence |
| ADDITIONAL_ALTERNATIVE_COST | 9,083 | additional costs 9,051 files; alternative-cost modes 393 |
| REPLACEMENT_EFFECT | 1,725 | R: lines 1,628 + Replace-verb shapes (97) |
| COPY_CONTROL | 4,250 | copy/control verbs + text signals (cyclone/exchange-life fixed) |
| LAYER_CHARACTERISTIC | 1,496 | Animate 950, SetState 279, AnimateAll 133, AlterAttribute 105, ChangeText 12, others |
| HIDDEN_INFORMATION | 3,020 | reveal/look-at/face-down/morph/manifest/disguise/cloak |
| RANDOMNESS | 1,031 | coin 86, die 148, random-discard 111, random-select 633, random-order 393, unknown 17; shuffle 1,460 kept separate |
| MULTIPLAYER_OPPONENT_SELECTION | 3,182 | each-opponent/target-opponent/vote/monarch/council/team(each word-boundary matched) |
| COMMANDER_MECHANIC | 405 | commander/command-zone/partner/tax signals; commander-damage signals: 0 |
| MODAL_CHOICE | 892 | Charm verbs / AlternateMode:Modal faces / CanRepeatModes (A-line effect modes no longer count) |
| X_COST_VALUE | 2,661 | mana-cost X 553, numeric-slot X 2,275 (incl. SVar effect bodies), SVar-X defined 6,399 (of which Count-defined 4,468), condition refs 422 |
| COMBAT | 1,241 | combat-restriction statics + combat verbs (previously never assigned) |

## Verb shapes (registry `q6-verb-registry-0.2.0`, 198 verbs)

33 mechanical shapes, e.g. DAMAGE/MASS_DAMAGE, DESTROY/MASS_DESTROY,
DRAW, TOKEN, COUNTER/MASS_COUNTER, COPY_CONTROL, SEARCH, MANA, CHOICE,
ZONE_CHANGE/MASS_ZONE_CHANGE, LIFE, DISCARD, MILL, TAP, COMBAT, TURN,
TARGET_MOD, HIDDEN, RANDOM, TRIGGER, REPLACEMENT, LAYER, PREVENTION,
SHUFFLE, MODAL, SACRIFICE, OTHER_STRUCTURED. Unknown verbs on the census:
**0** (104 distinct / 1,667 file-occurrences before). Unknown tokens stay
exactly reported and route to manual review (tripwire preserved for future
mechanics).

Flagged verb sets (file counts from the AFTER census): copy-driving,
randomness-driving (coin/die/select), replacement-driving
(`ReplaceEffect`/`ReplaceCounter`/`ReplaceToken`), trigger-driving
(`DelayedTrigger`/`ImmediateTrigger`), layer-adjudication (1,496),
prevention-adjudication (Regenerate 269, PreventDamage 115, Protection 53,
Fog 34, ProtectionAll 10, Regeneration 3, HealDamage 2), curator-review
(`MakeCard` 176, `BecomeMonarch` 60, `RingTemptsYou` 49, `Venture` 45,
`LosesGame` 45, `Draft` 42, `WinsGame` 42, `TakeInitiative` 23, ...;
Subgame/RestartGame/ControlPlayer included).

## Trigger / mode census

- T-line trigger modes: all observed values registered
  (`q6-trigger-mode-registry-0.2.0`); unknown on census: **0** (114/1,724
  before). `Once`-variants recorded with their base mode, raw kept.
- S-line static modes: 76 registered in 6 classes (CONTINUOUS, COST_MOD,
  COST_CHOICE, COMBAT, RESTRICTION, OTHER); comma-separated multi-modes
  (Arrest shape) classify element-wise; unknown: **0**.
- A-line ability modes: 22 registered in 9 classes; only MODAL_META marks
  modal choice. Trigger-conditions (49 files), targeting/zone/random/
  transform/choice-procedure/control/characteristic selectors distinguished.
- SVar fragment kinds: EFFECT / STATIC / TRIGGER / COMPUTED / COST /
  REFERENCED_OTHER / OTHER (Abeyance-shape referenced statics
  distinguished from effect bodies; chaining still via SubAbility edges).

## Replacement / cost / target / SVar grammar (token observation)

- R-line events (34 distinct): Moved 957, DamageDone 218, Untap 156,
  Counter 117, Draw 37, CreateToken 32, AddCounter 32, ...; results
  Updated 838 / Replaced 4; ReplaceWith heads led by ETBTapped 615.
- Cost heads: T 3,027, SubCounter 697, Sac 426, AddCounter 409, tapXType
  135, Discard 98, PayLife 69, Waterbend 25, ... (generic mana/symbolic).
- Target keys: ValidCard 14,957, ValidTgts 7,746, TgtPrompt 3,597,
  ValidPlayer 2,755, Defined 2,171, ... (selectors, not legality).
- SVar: 25,335 files; heads DB 38,611 / Count 6,178 / Mode 2,482 / AB
  1,320 / ...; SubAbility refs 10,452, Remembered 3,358, Execute 1,642.
- Top-level keys: SVar 59,372 lines; A 18,443; T 16,962; S 7,089; R 1,693;
  bare ALTERNATE separators 875 (format, not ambiguity).

## Routing (capability hypotheses, full corpus)

AMBIGUOUS 11 · MANUAL_REVIEW_REQUIRED 1,243 ·
READY_FOR_RUNTIME_QUALIFICATION 10,815 ·
RULES_ADJUDICATION_REQUIRED 21,451 · UNSUPPORTED 146.
READY means mechanical prerequisites are ready for an authoritative
runtime qualifier; it is not card-behavior PASS.
