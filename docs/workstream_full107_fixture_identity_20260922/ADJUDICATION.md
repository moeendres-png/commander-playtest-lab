# Adjudication — seven NATURAL_GAME_START fixture identities (2026-09-22)

Frozen source: `qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`
(135 records, `materialization_version`
`commander-lab.semantic-fixture-materialization/1.0.5`; all
`materialization_status` `OBLIGATION_PRESERVED`).
Authority: common manifest `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json`
(`common_manifest_sha256`
`e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`).
Engine identity: xmage maven `1.4.61` (`engine-bridge/pom.xml`), source pin
`db134b97` (`FULL107_IDENTITY_BINDING.json`, gate runner `XMAGE_COMMIT`).

## 1. The `cmd:PN-A` contradiction — resolved

`M1_HANDOFF.md` claims all seven NATURAL fixtures "pin synthetic decks (99×
Mountain + mock commanders `cmd:PN-A`)" refused by the real-cards-only importer
(`UNKNOWN_CARD_NAME`). Frozen bytes refute this as stated:

- Across all 135 materialization records, the only `deck_state` card identities
  are `Mountain` and `Rograkh, Son of Rohgahh` — both real cards. No mock
  commander exists in any frozen `deck_state`.
- `cmd:P1-A` is a semantic `commander_id` (object-identity label in
  `commander_state` / `semantic_objects` / template `commander_ids`), never a
  card name. Feeding it to `resolveMechanicalCard` is a harness field-mapping
  error, not a fixture property.
- The common manifest carries no decks at all for these fixtures (only
  description, `player_count`, `seed`); nothing mock is pinned there either.

Valid core preserved: five fixtures use the template `deck_state` schema
(`commander_ids` + `library_template`, commander card unbound in
machine-readable `deck_state`; bound to Rograkh only in `scenario_notes` prose
and `semantic_objects`). A digest-exact construction claim for those five
cannot be mechanically demonstrated from `deck_state` alone today.

## 2. Per-fixture verdicts

### PLAYER_COUNT_2P / _3P / _4P / _5P — EQUIVALENT (DIRECT unsupported)

- Fixture binds: Rograkh + 99 Mountain per seat (notes + `semantic_objects`),
  opening hand 7, `rules_seed` 424242, scripted all-keep round 1,
  `required_events` game_created / commander_zones_initialized /
  libraries_shuffled / opening_hands_drawn / first_turn_started,
  forbidden `technical_20_life_start`, life 40.
- Cited evidence (`gate-{2,3,4,5}p.json`, PASS, replay MATCH) runs
  `scripts/run_external_full_game_conformance.py`: commander **Isamaru, Hound
  of Konda + 99 Plains** (`_deck()`), seeds **20260825/26/24/27**
  (`CARDINALITY_SEEDS`), full autopilot to game-over (2P: 12253 decisions),
  `source_path="synthetic:technical-conformance-only"`,
  `evidence_class="technical_conformance_only"`. Gate JSONs record no seed,
  no decks, no engine version, none of the required events.
- Deltas: different decks, different seeds, different procedure, required
  events unasserted. Player-count match alone does not prove fixture identity.
- Disposition: DIRECT → **SUPPORTING** (per-count live lane evidence, not a
  fixture rerun). Pointer kept; reason rewritten with the gap + residual
  (exact Rograkh/Mountain keep-hand runs at seed 424242 with required events).

### PILOT_MULLIGAN — FAMILY (SUPPORTING stands)

- 4P template-schema fixture; own script (mulligan P1 r1, keeps incl. P1 r2,
  `bottom_count:P1:0`) never executed as a fixture run. Gates observe the
  `mulligan` class; `XmageFullGameActionProjectionTest` covers projection.
- The WS05 4P run is behaviorally adjacent but belongs to another fixture
  (different deck binding, `mulligan_once` vs `mulligan` semantics). No credit
  transfer. SUPPORTING unchanged.

### WS05-CMD-MULL-2 / WS05-CMD-MULL-4 — EXACT (DIRECT stands)

- Fixture binds exact cards: commander `Rograkh, Son of Rohgahh` ×1,
  main `Mountain` ×99, `exact_card_count` 100, per seat; life 40; 2P/4P.
- Runtime (`XmageFullGameWs05MulliganTest`, bytes identical to merged main):
  same cards via real-cards-only importer (no mock path touched), seed
  `424242` (manifest seed; record uses `SCENARIO_SEED` binding), life 40,
  engine xmage 1.4.61. P1 takes exactly one mulligan (`mulligan_once`,
  exact-one-match fail-closed both directions), all other seats keep —
  matching `decision_script` + `pregame_decision_plan`. Asserts
  `mulligan_once:P1` plus London bottom counts (2P lib 93/hand 6 ⟺ not free;
  4P lib 92/hand 7 ⟺ free), entailing the `free_mulligan` required events.
- This is exact fixture execution, not a real-deck equivalent: `deck_state`
  card identities are identical, so the deviation prohibition does not apply.
- Documented harness notes (not semantic deviations): the engine-emitted
  starting-player prompt (absent from the fixture script) is answered by
  exact-one-match self-action to reach the mulligan phase; the
  `requested_state_digest` compare protocol has no in-repo implementation yet
  (no digest is fabricated) — Workstream 2 readback must re-confirm these two
  runs under the digest protocol.

## 3. Resulting mapping

DIRECT 6 → 2 (only WS05-CMD-MULL-2/4); SUPPORTING 9 → 13; UNKNOWN 57 and
NOT_RUN_BLOCKED 35 unchanged. Only the four PLAYER_COUNT entries plus derived
counts change.
