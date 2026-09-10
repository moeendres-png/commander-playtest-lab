# Bounded Actual-Card Validation Sample (tooling validation only)

14 real Forge card scripts at pin `8c7e9afb8e6caee88644b94e25da5852e36f8928`
(`Card-Forge/forge.git`, `forge-gui/res/cardsfolder/...`; per-file sha256
in `tests/q6_scaffolding/fixtures/inputs.json`). Chosen to stress distinct
capability families plus adversarial classes; D2-studied shapes (commander
tax replacement, multiplayer vote, target-after-death handling) are
represented by analogous real cards.

No behavior credit is awarded to any card below. States describe
preparation progress only.

## Routing results (`evidence/routing-table.json`)

| Card | State | Capability under test |
| --- | --- | --- |
| Lightning Bolt | READY_FOR_RUNTIME_QUALIFICATION | TARGET_SELECTION |
| Divination | READY_FOR_RUNTIME_QUALIFICATION | MANA_PAYMENT_CHOICE |
| Altar's Reap | READY_FOR_RUNTIME_QUALIFICATION | ADDITIONAL_ALTERNATIVE_COST |
| Boros Charm | READY_FOR_RUNTIME_QUALIFICATION | MODAL_CHOICE |
| Force of Will | READY_FOR_RUNTIME_QUALIFICATION | TARGET_SELECTION |
| Soul Warden | RULES_ADJUDICATION_REQUIRED | TRIGGERED_CHOICE |
| Council's Judgment | RULES_ADJUDICATION_REQUIRED | MULTIPLAYER_OPPONENT_SELECTION |
| Braids, Arisen Nightmare | RULES_ADJUDICATION_REQUIRED | MULTIPLAYER_OPPONENT_SELECTION |
| Willbender | RULES_ADJUDICATION_REQUIRED | HIDDEN_INFORMATION |
| Frenetic Efreet | RULES_ADJUDICATION_REQUIRED | RANDOMNESS |
| Fierce Guardianship | RULES_ADJUDICATION_REQUIRED | COMMANDER_MECHANIC |
| Fireball | RULES_ADJUDICATION_REQUIRED | TARGET_SELECTION (X-value question) |
| Sundering Eruption | RULES_ADJUDICATION_REQUIRED | REPLACEMENT_EFFECT |
| Gisela, the Broken Blade | UNSUPPORTED | COPY_CONTROL (`topkey:MeldPair`) |

Coverage of required stress classes: simple deterministic (Divination),
target choice (Lightning Bolt), modal choice (Boros Charm, Sundering
Eruption), payment/additional cost (Altar's Reap), alternative cost
(Force of Will), X value (Fireball), trigger (Soul Warden, Braids),
multiplayer-sensitive (Council's Judgment vote, Braids each-opponent),
hidden information (Willbender morph), randomness (Frenetic Efreet coin
flip), Commander-relevant (Fierce Guardianship), unsupported
(Gisela meld).

Queue totals for the sample: MANUAL_SCENARIO_REVIEW 11,
RULES_ADJUDICATION 10, RUNTIME_QUALIFICATION_READY 5,
UNSUPPORTED_CAPABILITY 1, AMBIGUOUS_PARSE 0, PROVENANCE_REVIEW 0
(27 items; see `evidence/queues.json`).

## Determinism evidence

Committed manifest: `evidence/manifest.json`
(`manifest_id: q6-bounded-sample-14`).
Re-running the six CLI steps over `tests/q6_scaffolding/fixtures/inputs.json`
reproduces intake IDs, tags, skeleton identities, queue assignments,
ordering, and the manifest hash exactly (`validate` recomputes and
compares; mismatch fails closed). Cross-run reproduction is additionally
proven by `test_manifest_reproducible_across_runs` (89-test suite).

## Parser-accuracy notes (mechanical, not behavior claims)

Adjudicated during implementation from authoritative corpus bytes at the
pin (ordinary in-scope technical decisions, recorded here):

1. Bare `ALTERNATE` face separators are documented format, not ambiguity.
2. `Mode$` on non-Trigger records is modal/static-mode signal, not a
   trigger mode (Force of Will `AlternativeCost` static mode is a payment
   choice).
3. X-value detection requires a standalone X token in a numeric slot or
   mana cost; SVar cross-references named X (Braids) do not count.
4. Tutor `shuffle` is recorded as `has_shuffle`, not Rules randomness.
5. `AI:` hint lines are benign metadata (D3 §5 decomposition), allowlisted.
6. Primary capability selects the most distinctive family
   (multiplayer/commander/hidden/random/copy/trigger first), so skeletons
   name what makes each card interesting.
