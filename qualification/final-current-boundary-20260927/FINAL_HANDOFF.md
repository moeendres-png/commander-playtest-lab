# WSR22 Final Handoff — FINAL-CURRENT-BOUNDARY-FREEZE-QUALIFICATION-20260927

## Source Lock

- Lab repository `moeendres-png/commander-playtest-lab`, branch
  `wsr22/final-current-boundary-freeze-qualification-20260927`, worktree
  `/home/moeen/code/wsr22-final-current-boundary-freeze` (sole writer).
- Dispatch main `c5f9418e755a02ffec0e02c34b4a739baf10f5f0`, tree
  `610f93d81e3b7154731d95472be6dcac05057eac` — verified at session start, no
  drift. `origin/main` still at `c5f9418e` (PR #261 governance branch is NOT
  merged and was NOT touched; no source drift was observed during the run).
- Workstream HEAD after the evidence commit: recorded in
  `WORKSTREAM_STATE.yaml` and in every packet's `runtime_identity`.
- Qualification boundary `commander-lab.pre-freeze-qualification/2.0.0`;
  transport Protocol `2.0.0`; contract schema blob
  `ea8651f75a1461ecc41dc1f24586c00bff97fee5` (matches the AF01 v2 pin).
- Frozen FULL107 source `5a2e4f462fd45bba25f2271153212aab9faf09f5`, 107 rows,
  `denominator_decreased_to_bypass_blocker: false`, immutable.
- Effective denominator contract `FULL107_SUCCESSOR_CONTRACT_v1_0_6`,
  contract id `commander-lab.full107/1.0.6-successor`, canonical bundle digest
  in `EFFECTIVE_FULL107_MANIFEST.json`.
- XMage candidate `b19596980f2734496ea1896504253e1bdd2756dd`; Lab runtime
  authority `593326713faeddb8c90df2fdc5e5bafbe1fccf1b`; Mage master NOT
  substituted.
- Forge candidate `ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree
  `fc3387bf37aab19d780b2939a235309ed32b0492`; WSR20 evidence tip
  `18bba95a4528f6ab5910633f1f87f603b8c4ddf8` (read-only reference; built and
  executed, never edited, byte-clean at that SHA after every run).
- Full blob/sha256 bindings: `SOURCE_LOCK.json`.

## Current Official Rules Authority

**Resolved by direct official capture — the repository's recorded
`FRESHNESS_CONFLICT_FAIL_CLOSED` is closed.**

- Official page: `https://magic.wizards.com/en/rules`
- Page→TXT link captured from the page's own HTML:
  `https://media.wizards.com/2026/downloads/MagicCompRules 20260925.txt`
  (DOCX, PDF and TXT all resolve to 20260925)
- Resolved TXT URL:
  `https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt`
- Retrieval UTC `2026-09-27T14:05:23Z`; bytes `977752`; SHA-256
  `8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca`
- Stated in the TXT: "These rules are effective as of September 25, 2026."
- Rule 103.8a exact text: "103.8a In a two-player game, the player who plays
  first skips the draw step (see rule 504, "Draw Step") of their first turn."
- The previously recorded official artifact (2026-08-07) now returns
  **HTTP 404**. The page links something newer than 2026-08-07.
- Capture-pipeline self-validation: re-capturing the 2026-08-19 TXT produced
  sha256 `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`,
  exactly the value the repository's own `AUTHORITY_LOCK_V2` records.
- Qualification-relevant diff 2026-08-19 → 2026-09-25: rules 103.8a/103.8b/
  103.8c, 504.1, 800.4a, 800.4j, 508.8, 109.5b are **byte-identical**; the only
  changes are combat-timing renumbering 506.7a–g → 506.8a–g (text identical),
  a new 111.10x token definition, and a new 701.71a Jace empower. None is
  referenced by any of the 107 rows.
- Impact: `WS05-CMD-START-2` semantics **confirmed still current**; rule 103.8c
  confirms 3P+ does not skip, so `WS05-CMD-START-3` remains correct.
  `NOT_SOURCE_CONTRACT_DRIFT`: the successor contract blob is unchanged; only
  its external citation date is superseded. The receipt was resealed with the
  capture and a fail-closed test that rejects any resolution claimed without a
  direct capture.

## Effective Contract

- FULL107 successor v1.0.6 changes **exactly one** row: `WS05-CMD-START-2`.
- Mechanically proven, not asserted: 106/106 other rows are byte-identical
  between the frozen v1.0.5 materialization and the effective v1.0.6 bundle
  across 14 obligation-relevant fields
  (`SUCCESSOR_INHERITANCE_PROOF.json`).
- `WS05-CMD-START-2` new obligation: 2P, P1 starts, P1 skips the ENTIRE
  first-turn draw step, no draw-step checkpoint, no draw event, no priority
  inside that step, first observable checkpoint is precombat main, hand/library
  unchanged by a first-turn draw. New effective
  `requested_state_digest` `bc01a714…`.
- `FRESH_CURRENT_BOUNDARY_EXECUTION_REQUIRED_ALL_107` honoured: no historical
  verdict was carried into any current-boundary count.

## Work Completed

1. Gate 0 source/contract/build lock (22 blob bindings + runtime identities).
2. Gate 1 direct official Rules-authority capture and freshness-conflict
   resolution.
3. Successor-inheritance mechanical proof.
4. New candidate-neutral qualification package
   `src/commander_lab/qualification/current_boundary/` (launcher, source lock,
   effective materialization, AF01 executor, Protocol-2 game driver, FULL107
   executor) plus two runner scripts. It contains no Rules logic.
5. AF01 v2 executed freshly on both candidates (20 invariants each), plus a
   second XMage pass on its full-game lane.
6. Real Commander lifecycles executed at 2P/3P/4P/5P/6P for both candidates
   through one shared candidate-neutral code path, with external discretionary
   choices bound to engine-offered options.
7. `WS05-CMD-START-2` executed under the v1.0.6 successor on both candidates.
8. Hidden-information, RNG/replay and actual-card probes executed live.
9. Native FULL107-decision-critical suites executed fresh: XMage 34 + 134;
   Forge 150 + 67. All green.
10. AF00–AF11 matrix (12 explicit verdicts per candidate), 107-row comparison,
    divergence packet, provider-blocker register.
11. Seven harness defects found and repaired at their actual layer (see
    `VALIDATION.md`); none weakened an expectation.
12. 14-test packet reconciliation suite + updated contract suite (27 passed);
    `ruff check` and `ruff format --check` clean.

## Reuse / Donor Work Used

- `scripts/resolve_pre_freeze_contract.py` — the canonical successor overlay
  and digest spec, loaded (not reimplemented) by the new materialization
  module. `REUSE_AS_IS`.
- `JsonLineBridgeClient` wire form — the canonical Protocol-2 envelope carries
  the body under both `payload` and `params`; the new launcher mirrors it.
  `REUSE_AS_IS` (the first failure proved this was mandatory).
- `XmageNativeStateRestoration.frozenRecord` pattern and the 24 native harness
  classes — reused unchanged as the current-boundary native evidence source.
- Forge WSR20 `FULL107_FORGE_MAPPING.json` — ingested to derive the
  Forge native fixture→suite binding from the packets themselves rather than
  from memory. `REFERENCE_ONLY` for verdicts; no verdict transferred.
- `tests/integration/test_forge_bridge_h4f_live.py` — the game-driving shape
  (deck import → `create_commander_game` → `start_game` → external decision).
- Historical: WSR20 (Forge evidence tip), WSR21 (comparison packet), L1–L7
  (XMage harnesses). All provenance/donor only.

## Changes

New:
- `src/commander_lab/qualification/current_boundary/{__init__,source_lock,
  bridge_launcher,materialization,af01,game_driver,full107}.py`
- `scripts/run_current_boundary_qualification.py`
- `scripts/assemble_current_boundary_evidence.py`
- `tests/qualification/test_wsr22_current_boundary.py`
- `qualification/final-current-boundary-20260927/` (evidence tree, 22 files)

Modified (qualification infrastructure only):
- `qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json` — resealed
  with the direct capture; all prior fields preserved verbatim.
- `tests/qualification/test_pre_freeze_contract_successor.py` — the freshness
  test now enforces the **post-resolution** invariants and adds three
  fail-closed negatives (no capture, contradicting capture, mirror promoted to
  authority). Strictly stronger than before; nothing weakened.
- `.gitignore` — ignore `engine-bridge/db/` (test-run card DB) and the
  generated `engine-bridge/target/cp-wsr22.txt` classpath manifest.

Unchanged: no engine file, no pin, no Architecture Freeze gate, no fixture
record, no existing expectation.

## Tests / Runtime Evidence

| Run | Result |
|---|---|
| XMage native FULL107-executors (9 classes) | 34/34 PASS, BUILD SUCCESS |
| XMage native mechanisms (15 classes) | 134/134 PASS, BUILD SUCCESS |
| Forge native denominator + families (15 classes) | 150/150 PASS, BUILD SUCCESS |
| Forge native process/negation (8 classes) | 67/67 PASS, BUILD SUCCESS |
| Protocol-2 lifecycles | 2P/3P/4P/5P PASS on both; 6P bounded on both |
| START-2 v1.0.6 | PASS on both (no draw-step checkpoint on either) |
| AF01 v2 | XMage compat UNKNOWN (seed not exposed), XMage full-game PASS, Forge PASS |
| Lab tests | 27 passed |
| ruff check / format | clean |
| mypy | NOT_RUN (module absent in this environment) |

## XMage FULL107

PASS 30 / FAIL 0 / UNKNOWN 44 / BLOCKED 33 / CRASH 0 / TIMEOUT 0 /
PROTOCOL_FAILURE 0 — **TOTAL 107**.
Native promotions 25 (only for rows whose effective record is byte-identical to
the frozen record its harness loads, proven in the inheritance proof).

## Forge FULL107

PASS 79 / FAIL 0 / UNKNOWN 21 / BLOCKED 7 / CRASH 0 / TIMEOUT 0 /
PROTOCOL_FAILURE 0 — **TOTAL 107**.
Native promotions 74.

## XMage AF00–AF11

AF00 PASS · AF01 UNKNOWN · AF02 PASS · AF03 PASS · AF04 **FAIL** · AF05 UNKNOWN ·
AF06 UNKNOWN · AF07 UNKNOWN · AF08 UNKNOWN · AF09 UNKNOWN · AF10 PASS ·
AF11 **FAIL**

## Forge AF00–AF11

AF00 PASS · AF01 PASS · AF02 PASS · AF03 PASS · AF04 UNKNOWN · AF05 UNKNOWN ·
AF06 UNKNOWN · AF07 UNKNOWN · AF08 UNKNOWN · AF09 UNKNOWN · AF10 PASS ·
AF11 **FAIL**

## Current-Boundary Comparison

All 107 rows explicitly classified:
SAME_SEMANTICS 25 / NON_COMPARABLE 82 / RULES_VISIBLE_DIVERGENCE 0 /
ENGINE_CAPABILITY_GAP 0 / HARNESS_OR_ADAPTER_GAP 0 /
UNKNOWN_PENDING_RULES_ADJUDICATION 0.

**The PASS asymmetry (Forge 79 vs XMage 30) is an evidence-build asymmetry, not
a measured Rules-capability difference.** Forge's WSR20 work already built 150
native denominator tests; the Lab XMage harness covers 30 rows. Every row
either candidate executed, both executed successfully. The asymmetry is
classified as PB-03 `UNKNOWN_IMPACT` with a concrete remediation, not as a
capability claim.

## Rules Divergences

**None.** No Magic Rules-visible behavioural divergence was observed on any of
the 107 rows. `DIVERGENCE_PACKET.json` is empty by evidence, not by absence of
input: both candidates were executed freshly under the current boundary and
compared per row. The cross-engine differences found are **protocol/interface
shape**, recorded as PB-01/PB-02/PB-05, not Rules disagreements. The Coordinator
performs final independent Rules adjudication.

## Provider-Blocking Gaps

Register: 0 `PROVIDER_BLOCKING`, 4 `BOUNDED_NON_BLOCKING`, 4 `UNKNOWN_IMPACT`.
This is a gap classification, not a provider selection.

- **PB-03 (XMage, UNKNOWN_IMPACT — the decision-critical one):** 33 denominator
  rows are BLOCKED because their effective obligation needs a frozen mid-game
  starting state and the Lab path exposes no generic starting-state injection
  (bridge reports `starting_state_injection_supported=false`). XMage's own
  causal-reconstruction harnesses reach adjacent mechanisms but not these exact
  obligations. Remediation: a starting-state injection workstream, or a
  Coordinator ruling that mechanism-equivalent causal reconstruction suffices.
- **PB-06 (both, UNKNOWN_IMPACT):** the five historical Forge hidden-information
  seams (HIDDEN_05/06/08/11/12) could not be freshly classified as reachable or
  unreachable on the shared surface; per-scenario channel instrumentation is not
  exposed there. They must NOT be dismissed as non-blocking.
- **PB-07 (both, UNKNOWN_IMPACT):** the effective 29-card actual-card corpus was
  not individually executed.
- **PB-08 (both, UNKNOWN_IMPACT):** the clean-process twin half of each
  `REPLAY_*`/`RNG_*` obligation is unproven per fixture.
- **PB-01 (XMage, BOUNDED_NON_BLOCKING):** `external_control=true` is required
  at `create_commander_game` or the decision surface fails closed. A conforming
  adapter sets it; this workstream did.
- **PB-02 (both, BOUNDED_NON_BLOCKING):** decision-identity divergence
  (`decision_id`+`action_id` vs `revision`+`actor_id`); each rejects the other.
  A provider-specific shim in the Lab adapter is required.
- **PB-04 (XMage, BOUNDED_NON_BLOCKING):** `seed_supported` differs by lane.
- **PB-05 (Forge, BOUNDED_NON_BLOCKING):** the reported engine commit comes from
  `FORGE_ENGINE_SHA`, so the commit-to-build binding is operator-supplied.

Additional material finding: XMage's manifest advertises
`legal_actions_supported=false`, but the live compat lane with
`external_control=true` **does** expose a complete external PRIORITY decision.
The manifest's global flags understate live capability, and capability reporting
is lane-dependent. This must be corrected before any capability-based gating.

## PASS / FAIL / UNKNOWN

- **PASS:** Gate 0 source lock; Gate 1 direct official Rules authority;
  successor inheritance proof; AF01 v2 on both; cardinality 2P/3P/4P/5P both
  (6P bounded); START-2 v1.0.6 both; all 385 fresh native tests green; AF00,
  AF02, AF03, AF10 both; zero CRASH/TIMEOUT/PROTOCOL_FAILURE; 107/107
  denominator accounting on both; 27 Lab tests; ruff clean.
- **FAIL:** zero rows failed on either candidate. AF04 (XMage) and AF11 (both)
  are gate-level FAILs recorded above.
- **UNKNOWN:** 44 XMage rows, 21 Forge rows; AF05/AF06/AF07/AF08/AF09 on both;
  mypy NOT_RUN.

## Remaining Blockers

1. **Publication permission.** `git push` is denied by the root tool policy.
   The branch is complete and validated locally; one exact safe command is
   given below. No PR exists yet.
2. **PB-03** starting-state injection seam (XMage) — needs a Coordinator
   decision on whether the FULL107 denominator is required admission evidence.
3. **PB-06/07/08** — the per-scenario hidden-information, 29-card corpus and
   per-fixture replay-twin campaigns.

## Validation

See `VALIDATION.md`: exact commands, fresh run results, consistency totals, the
seven harness defects found and repaired at their actual layer, and the honest
NOT_RUN list (mypy only).

## Self-Review Findings

See `SELF_REVIEW.md` (17 adversarial attacks). Material outcomes: no vacuous
test accepted as PASS; no construction-only claim; no inherited PASS (mechanically
bounded); no player-count inference; START-2 predecessor semantics not reused;
Rules authority re-captured, not assumed; no hidden fallback; the four initial
`PLAYER_COUNT_*` FAILs were repaired at the classifier layer rather than
downgraded; the Forge PASS asymmetry is explicitly classified as an
evidence-build asymmetry, not a capability ranking.

## Outputs

`qualification/final-current-boundary-20260927/`:
`WORKSTREAM_CONTRACT.md` (this tree's contract summary is in `SOURCE_LOCK.json`
and the repository contract), `SOURCE_LOCK.json`,
`CURRENT_RULES_AUTHORITY.json`, `SUCCESSOR_INHERITANCE_PROOF.json`,
`EFFECTIVE_FULL107_MANIFEST.json`, `AF01_XMAGE.json`,
`AF01_XMAGE_FULLGAME_LANE.json`, `AF01_FORGE.json`,
`FULL107_XMAGE_RESULTS.json`, `FULL107_FORGE_RESULTS.json`,
`FULL107_XMAGE_RUNTIME_LOG_INDEX.json`, `FULL107_FORGE_RUNTIME_LOG_INDEX.json`,
`PLAYER_CARDINALITY_XMAGE.json`, `PLAYER_CARDINALITY_FORGE.json`,
`HIDDEN_INFO_XMAGE.json`, `HIDDEN_INFO_FORGE.json`,
`RNG_REPLAY_XMAGE.json`, `RNG_REPLAY_FORGE.json`,
`ACTUAL_CARD_XMAGE.json`, `ACTUAL_CARD_FORGE.json`,
`AF00_AF11_XMAGE.json`, `AF00_AF11_FORGE.json`,
`CURRENT_BOUNDARY_COMPARISON.json`, `DIVERGENCE_PACKET.json`,
`PROVIDER_BLOCKERS.json`, `VALIDATION.md`, `SELF_REVIEW.md`,
`FINAL_HANDOFF.md`, `WORKSTREAM_STATE.yaml`, `wsr20-ingest/`.

## Remote Branch / HEAD / TREE

- Local branch `wsr22/final-current-boundary-freeze-qualification-20260927`.
- Local HEAD/TREE: recorded in `WORKSTREAM_STATE.yaml` (updated at the final
  checkpoint commit).
- Remote: NOT PUBLISHED in this session — `git push` is denied by the root tool
  policy. No force push, no rebase, no tag, no settings change was attempted.

## PR / CI

- PR: NONE yet (publication gate, see below).
- Remote CI on the published tip: not triggered, because publication did not
  occur. All local validation is green.

## Dependencies Unblocked

The Coordinator can now adjudicate without guessing:

- the Rules-authority freshness conflict is closed with a direct official
  capture and a rule-level diff;
- both candidates have fresh current-boundary AF01, 2–5P cardinality, and
  START-2 v1.0.6 runtime evidence;
- all 107 rows are explicitly classified per candidate and per comparison, with
  zero crashes/timeouts/protocol failures;
- every non-PASS condition is classified PROVIDER_BLOCKING /
  BOUNDED_NON_BLOCKING / UNKNOWN_IMPACT with a concrete smallest remediation;
- the largest open question (PB-03) is stated precisely enough for a single
  yes/no Coordinator ruling.

## Exact Next Action

Publication, then Coordinator adjudication. Exact safe command (single
fast-forward push, no force, no tags, authorized branch only):

```
git push --no-follow-tags origin \
  HEAD:refs/heads/wsr22/final-current-boundary-freeze-qualification-20260927
```

Then open exactly ONE pull request against `main` and inspect the CI triggered
by the published tip. Do not merge.

`ARCHITECTURE_FREEZE = NOT CLAIMED`
`PRODUCTION_PROVIDER = NOT SELECTED`
