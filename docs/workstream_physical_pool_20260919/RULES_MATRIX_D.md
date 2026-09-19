# Step D — Actual-card rules/interaction coverage (2026-09-19)

Engine pin: xmage-1.4.61 (`engine-bridge/pom.xml`). `PRODUCTION_PROVIDER=NOT_SELECTED`.
No engine execution was run in this workstream; no Forge/mage edits were made.

## 1. Population scoping (honest denominators)

- Source population: 1,401 physical identities. Import-level coverage is computed,
  not claimed as behavior: 1,363 with Oracle text + 38 vanilla (correctly textless),
  1,401 with structural semantics, 1,394 with single verified oracle_id, 7 UNKNOWN.
  Live gate: `tests/integration/test_physical_pool_coverage_live.py`.
- Behavior population: the 11 SOS prepare-relevant identities (all 63 photo cards are
  SOS; prepare appears on exactly these 11). Fixture:
  `tests/fixtures/physical_pool_prepare_sos.json` — true card objects with full
  faces, 10 required rule paths each, `observed_output: NOT_RUN`, verdict UNKNOWN.
- Chulane/Koma current-100s are NOT independently sourced in-repo (only
  `rogshai/current` Aug photo-verified + frozen `kaervek/current` exist), so no
  Chulane/Koma deck-behavior matrix is claimed. Opponent cards are not versioned
  here and stay out of the matrix.

## 2. Interaction matrix (prepare mechanics — all rows UNKNOWN, NOT_RUN)

| card | face exercised | required rule paths (10 each, see fixture) | engine+pin | test ref | expected | observed | verdict |
|---|---|---|---|---|---|---|---|
| Blazing Firesinger // Seething Song | enters-prepared + RRRRR copy | zone-independence, exile-copy creation, controller-only cast, cast-unprepares, cast-vs-copy triggers, cost-vs-value, zone-change reset, targets/fizzle, commander-tax N/A (non-commander), APNAP | xmage-1.4.61 | fixture | rule citations TBD (CR + SOS Release Notes) | NOT_RUN | UNKNOWN |
| Cheerful Osteomancer // Raise Dead | same pattern (B) | same | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Goblin Glasswright // Craft with Pride | same pattern (R, MV2) | same | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Spellbook Seeker // Careful Study | same pattern (U flyer) | same | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Studious First-Year // Rampant Growth | same pattern (G ramp!) | same + ramp-ordering relevance | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Sanar, Unfinished Genius // Wild Idea | enters-prepared legendary + tutor copy + Treasure gate | same + legend rule + activation condition | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Tam, Observant Sequencer // Deep Sight | landfall become-prepared | same + landfall trigger timing | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Inspired Skypainter // Maestro's Gift | ETB/token-damage become-prepared | same + token-damage trigger | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Dirgur Focusmage // Braingeyser | big-spell become-prepared + cost reduction | same + MV≥5-from-hand condition, cost-reduction interaction | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Biblioplex Tomekeeper | modal prepare/unprepare enabler | enabler targeting legality (only prepare-spell creatures) | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |
| Skycoach Waypoint | activated prepare enabler (land) | same + mana-ability vs activated-ability timing | xmage-1.4.61 | fixture | TBD | NOT_RUN | UNKNOWN |

High-risk notes for the qualifying run: cast-a-copy fires cast triggers (Ishai,
spellslinger) — must not be implemented as copy-a-spell; only the permanent's
controller casts; casting unprepares (state change, not a cost); zone changes and
ability loss interact with the exile copy; 4P APNAP for simultaneous triggers.
If engine defects surface, fix only on owned CPL surfaces; otherwise emit a
reproducible issue to the Forge/XMage owner (no cross-repo edits here).

## 3. Step D verdict

`RULES_COVERAGE=UNKNOWN` for all engine-behavior paths (explicit population: 11
prepare cards × 10 rule paths, 0 executed). Source coverage is separately
PASS-gated (see live tests). No behavior PASS is claimed from import, parsing,
construction, or fixture existence.
