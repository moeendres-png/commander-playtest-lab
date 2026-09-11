# WS49 R2 — Frame/Event Vocabulary Map (recorded BEFORE implementation)

Source Lock (WS49): commander-playtest-lab `ws49/xmage-v1.0.5-successor-qualification`
HEAD at mapping time: `74a246d74ee4c9063c0aa1951a095d947fc5c1aa`
(prior commit `925d21a900dc769453f712f05b28c31ffd330a00` = retained-run source).
XMage engine pin: `moeendres-png/mage@0c1f455ea8c8fa48ab9d638ad5068ec242800428`
(tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`), read-only inspection only.

Retained sealed runtime: Full107 behavior run `34412882569`
(job `102671104148`, conclusion `success`, behavior credit `0/107`,
statuses `FAIL_CLOSED_BEHAVIOR:70 / FAIL_CLOSED_BEHAVIOR_EVENTS:29 /
UNKNOWN_TERMINAL_PENDING:8`), executed on `925d21a9`.
Artifacts adjudicated locally (read-only): `WS49_FULL107_BEHAVIOR_PROBE.json`
(107 records), `WS49_BEHAVIOR_INVENTORY_107.json` (immutable obligations),
`QUALIFICATION_BRIDGE_OVERLAY.patch`, `XMAGE_QUALIFICATION_OVERLAY.patch`.
No Full107 launched for R2. No construction rerun. No credit promotion.

Defect class (WS50 Coordinator decision): semantic-equivalent native
Decision/event representations are not consistently transported/recognized
between the native producer (`engine-bridge/.../XmageFullGamePlayer.java`),
the observation/transport layer (`NativeEventLog.frame_events`,
`derive_settlement_outcomes`), and the G49-09 runner
(`run_full107_behavior_probe_v105.py` exact-equality routing at
`decision_family == decision_class`).

## PROVEN mappings (SAME_NATIVE_SEMANTIC_EVENT = PROVEN — implement)

### M1 — native decision_class `mode` ⇔ canonical family `choose_mode`
- Producer (sole site): `XmageFullGamePlayer.chooseMode` emits exactly one
  decision_class, `"mode"` (`request(game, "mode", ...)`). It serves XMage
  `Mode.chooseMode`: the modal-spell mode selection. No other producer emits
  `"mode"`; no other native method serves modal decisions.
- Consumer (sole family): WS47-derived inventory family `choose_mode`
  (procedure op `NATIVE_BEGIN_OR_CONTINUE_CAST_TO_MODE_DECISION`; rows
  `PILOT_CHOOSE_MODE`, `MICRO_MODES`, negatives `NEGATIVE_FIRST_OPTION`,
  `NEGATIVE_GUI_DEFAULT` requiring `decision_frame:choose_mode`).
- Transport defect: runner routes entries by exact
  `decision_family == decision_class` and derives frame events verbatim from
  the native class, so a native `mode` frame can never match a `choose_mode`
  entry and never satisfies `decision_frame:choose_mode` /
  `choose_mode_frame:P1` expectations.
- Runtime corroboration: retained run never surfaced a `mode` frame under ANY
  spelling (zero `mode_decision_frame` / `decision_frame:mode` /
  `choose_mode_*` emissions across 107 records) while `PILOT_CHOOSE_MODE`
  (engine adapter crash before cast) and `MICRO_MODES` (no cast entry; only
  priority passes) both stall before the modal frame — consistent with a
  deterministic routing miss, with no contradictory observation (no record
  shows modal decisions served under a different native class).
- Repair boundary (single authoritative transport normalization):
  canonicalize `mode`→`choose_mode` at the decision-read choke points;
  `frame_events` emits the canonical triple plus the raw-native triple when
  they differ (provenance preserved). Authoritative options untouched.

### M2 — frame spelling `{K}_frame:{A}` ⇔ `{K}_decision_frame:{A}`
- Producer: `NativeEventLog.frame_events` is the SOLE `_frame` emitter and
  emits only long forms `{klass}_decision_frame:{actor}` +
  `decision_frame:{klass}`, derived deterministically from the same native
  payload (`decision_class` + seat) that the contract short form names.
- Consumer: 14 distinct required short-form events
  (`choose_object_frame`, `target_amount_frame`, `choose_use_frame`,
  `choice_frame`, `pile_frame`, `mana_payment_frame`, `announce_x_frame`,
  `multi_amount_frame`, `replacement_effect_frame`, `trigger_order_frame`,
  `choose_mode_frame`, `choose_ability_frame`, `declare_attacker_frame`,
  `declare_blocker_frame`, each `:Px`) vs 7 long-form requirements.
  Correspondence proof: `target_decision_frame:P1` is required AND natively
  emitted with identical spelling for the same (target, P1) event, fixing the
  naming function; short forms differ only by the `_decision_` infix.
- Runtime corroboration: long forms observed (`mulligan` 27, `priority` 140,
  `mana_payment` 6, plus `target_*`/`choose_use_*` in decision-driven partial
  paths); short forms emitted NOWHERE by any code path (systematic absence).
  No fixture forbids any frame spelling; no ordering constraint references
  frame events (6 constraints checked) — additive aliasing cannot manufacture
  PASS (a frame alias is emitted iff the native frame occurred) and cannot
  flip a genuine absence into PASS.
- Repair boundary: `frame_events` additionally emits `{canon}_frame:{actor}`
  (lossless, provenance preserved — long forms retained).

### M3 — `creature_enters:{sid}` ⇔ `creature_entered:{sid}`
- Producer: `derive_settlement_outcomes` emits `creature_entered:{sid}` (+
  bare `creature_entered`) for each battlefield arrival, where `sid` is the
  semantic id from native `scenario_objects` (e.g. `obj:micro-enter`).
- Consumer: `MICRO_TRIGGERS` requires `creature_enters:obj:micro-enter` —
  identical sid scheme, identical semantic (battlefield arrival from the same
  terminal-diff derivation; the arriving object IS the scripted cast
  `obj:micro-enter`).
- Runtime corroboration: 236 `creature_entered*` emissions across the retained
  run; ZERO `creature_enters*` emissions anywhere (one-sided legacy spelling).
- Repair boundary: `derive_settlement_outcomes` emits the `creature_enters:`
  alias alongside the canonical emission (provenance preserved).

## REJECTED mappings (NOT same event — fail closed, later DAG nodes)
- R-a `choose_use` ⇔ `choice` ⇔ `replacement_effect`: source PROVES three
  distinct native methods/option sets (`chooseUse` booleans vs
  `choose(Choice)` value lists vs `chooseReplacementEffect` indexed map).
  Rows: `PILOT_REPLACEMENT_EFFECT`, `WS05-CMD-ZONE-*-{YES,NO}` (8).
  → cause-driven/terminal-inference node.
- R-b `choose_ability`: ZERO native producer sites (ability selection surfaces
  via `priority` offers). Contract models a frame the engine never emits →
  HARNESS_DEFECT (procedure + selector redesign). Row: `PILOT_CHOOSE_ABILITY`.
- R-c `semantic_player/object/stack_object` zero-matches: opaque native
  handles vs semantic ids (seat-label/profile matching is unvalidated v3
  identity work, out of scope) → SELECTOR_IDENTITY node.
- R-d mode-option semantic mapping (`create_devils` → native mode; metadata
  `mode_id` vs `mode`): needs object-identity work → SELECTOR_DESIGN node.
  (M1 intentionally stops at routing + frame events.)
- R-e `declare_attacker/blocker`, `target_amount`, `multi_amount`,
  `trigger_order` frames never surfacing (procedure ops unexecuted / cause
  never driven; `MICRO_MODES` has no cast entry) → CAUSE_FLOW node.
- R-f priority-pass-not-declared → AUTO_ADVANCE node (out of scope).
- R-g mana unsettled/undriven → MANA_ARMING node (out of scope).
- R-h hidden viewer-set mismatches (20 rows) → HIDDEN_IDENTITY node.
- R-i `damage_would_be` / `replacement_effect:` / `layer*` / `continuous_*` /
  `cost_determined:` / `commander_damage_*` / `extra_turn_*` / `next_turn:` /
  `resolve:obj:` / `zone_change:` → already UNKNOWN per unobservable taxonomy;
  no R2 action.
- R-j `PILOT_CHOOSE_MODE` first-submit engine crash
  (`COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER` + `PlayerList` NPE) →
  PROVIDER_ADAPTER_DEFECT (± NATIVE_ENGINE_DEFECT); R2 must not work around
  via name matching (prohibited).
- R-k `CARD_02` battlefield mismatch; commander tax/zone/extra-turn/elim
  derivations; `copy_*`; `scry_choice`; `knowledge_projection:*`;
  `legal_*`; `simultaneous_*`/`APNAP_*`; `rules_rng:*` events → their own
  derivation/terminal nodes. No aliasing (would invent lineage/identity).

## Validation plan (no Full107, no construction rerun, no credit change)
- Calibration subset (offline replay of sealed observations, no engine):
  `PILOT_CHOOSE_MODE`, `MICRO_MODES`, `NEGATIVE_FIRST_OPTION`,
  `NEGATIVE_GUI_DEFAULT`, `NEGATIVE_PARENT_CLASS_FALLBACK`, `MICRO_TRIGGERS`,
  plus a `target`-frame record (`MICRO_PRIORITY` partial path) and a
  `creature_entered` record.
- Prove per mapping: producer event → lossless normalized transport
  (canonical + raw retained) → authoritative options unchanged → scripted
  choice maps only to already-native-legal options (no engine submit in
  validation; native continuation remains UNPROVEN pending a future qualified
  Full107, which R2 alone does not authorize).
- Negative tests: `choose_use`/`choice`/`replacement_effect` never conflate;
  `creature_entered` never aliases to `zone_entered`/`damage`/etc.;
  `mode` never aliases to `choice`; unknown classes pass through unchanged;
  genuinely missing events still fail closed.
- Explicit non-goals: no seat/identity, hidden-bucket, mana, numeric,
  auto-advance, pass-advancement, selector-identity, cause-inference,
  evidence-credit, or Full107 changes.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.
`COVERAGE_PROMOTION = FALSE`. Behavior credit stays `0/107` by construction.
