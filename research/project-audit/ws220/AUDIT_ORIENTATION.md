# WS220 Audit Orientation

HEAD `67db0733` (published WS215), tree clean. Orientation built from three
parallel read-only surveys plus direct verification probes by the auditor.
Current source beats history throughout; historical reports are provenance only.

## 1. What the project currently is

Commander Simulator Next is a **qualification-first, engine-wrapping** program:
no new general Rules Core is being built. The live integration is a pinned XMage
compatibility fork (`db134b97`, via `config/rules_engines.json` — the sole
machine-readable pin authority) driven through a full-game JSONL lane
(`src/commander_lab/engine/rules/full_game.py` + `engine-bridge/` Java) with
Our Pilots as external discretionary controllers behind a blocking typed
fail-closed decision controller. Structural/Tactical simulators are demoted to
diagnostic-only. `ARCHITECTURE_FREEZE = NOT_CLAIMED`,
`PRODUCTION_PROVIDER = NOT_SELECTED`, `provider_decision: NO_PROVIDER_READY`.

Mission (`docs/PROJECT_MISSION.md`, PR #173 line) is outcome-first and
player-count neutral: 4P is the primary benchmark/decision mode, **not** an
architecture anchor; 2–5P technical conformance is mandatory with per-count
evidence. WS215 generalized the lane to authoritative 2–5P FFA with fail-closed
cardinality (2P/3P/4P/5P lifecycle PASS, 6P NOT_SUPPORTED, replay PARTIAL,
behavior credit 0 that round; WS213 holds the single +1 credit, H01-NO_HUMILITY).

## 2. Qualification and evidence shape

- Dual gate models coexist with **no published mapping**: G00–G15 (production
  admission, `FULL_RULES_REQUIREMENTS_CONTRACT_v1.json`) and AF00–AF11
  (Architecture Freeze, `architecture_freeze_gate_catalog_v1.json`). Freeze
  needs all 12 AF PASS on identical denominators + authority lock + fixtures.
- Canonical denominators: **135** common fixtures (4 player_count + 36
  multiplayer_commander + 17 pilot_boundary + 7 negatives + 20 hidden_info +
  5 replay_rng + 17 micro_rules + 29 actual_card), **29**-card frozen corpus,
  **15** First-Wave slots, historical provider **107** (uniformly NOT_RUN in
  WS203–WS215 seals; `ws90/verify.py` already guards 107/15 conflation).
- De-facto seal = co-located convention (`SOURCE_LOCK`, `VALIDATION.json`,
  `FINAL_HANDOFF`, `ARTIFACT_INDEX.json`, `INPUT_AUTHORITY_MATRIX`,
  `COMMON_FIXTURE_DISPOSITION`, `BEHAVIOR_CREDIT_LEDGER`), not one envelope
  schema. Three evidence vocabularies coexist (policy 7-term, machine-schema
  5-term, workstream mixed prose) — automated cross-checks will misjoin.
- WS215 disposition (directly verified): 72 RERUN_REQUIRED / 47
  RETAINED_AFTER_IMPACT_ADJUDICATION / 16 UNKNOWN of 135. The 47 retained rows
  ride on an impact-adjudication completeness argument across an engine repin
  and a bridge rewrite — the single largest evidence-integrity surface.
- `qualification/aggregate/` (PRODUCTION_ADMISSION, GATE_RESULTS, coverage
  matrix) is **WS17-era stale** (last touched `9e5b787d`/`bbe91739`) and was
  not refreshed by WS213/WS215. Readers of `aggregate/` see 0 PASS; readers of
  `ws215/` alone over-claim. No index reconciles the layers.

## 3. Source-truth topology (verified)

Authority order that actually holds: `config/rules_engines.json` (pins) >
`docs/PROJECT_MISSION.md` (mission) > lane docs + code (modulo WS215 lag) >
migration/closeout/J-P3/Phase-8.5 reports (frozen provenance) >
`docs/OPERATIONAL_SIMULATION_POLICY.md` (2026-08-20, 4P-only — stale, file
untouched since `136afc8b`, contradicts mission + WS215 code MIN 2/MAX 5).

Internal contradiction inside the living lane doc:
`docs/architecture/xmage-full-game-external-pilots.md` cites the 2–5P mission
minimum (:6-9) then reasserts exactly-4P scope (:13).

Other staleness confirmed: `XMAGE_FULL_GAME_CLOSEOUT.md` pins `cfc36f44`
(superseded by `db134b97` per manifest :116); migration reports cite package
1.24.0 vs living 1.25.0 (benign provenance); `config/structural.yaml` says
`structural-0.3.0` vs code `structural-0.6.1`; J-P3/Phase-8.5 pins are frozen
provenance (`xmage_1.4.60V3`, `forge-2.0.14`), not current.

## 4. Test / CI / Foundry shape

- 201 test files (146 unit, 20 integration, 9 foundry-tooling, 5 property,
  4 golden, 4 contract, …). Markers thinly applied; gating mostly by path +
  skipif. Fuzz uses unseeded `random` (header-level signal, to verify).
- Deps are **range-pinned** (`pyproject.toml`) with only 6 exact direct pins
  and no transitive lock/hashes; floating Docker base tags, `setup-python`
  3.12 floating patch, floating runners (xmage lane excepted). CI installs from
  ranges on fresh runners; no committed per-run freeze except the security-job
  artifact. Local green ≠ CI green across dep drift.
- Foundry machinery (launcher, safe_push 11 gates, schema-2.0 state, writer
  flock, reference roots, drift check, test-impact, evidence helpers) is
  substantive and fail-closed; residual notes: pre-push hook is L3-partial
  (bypassable via `--no-verify`, real gates are safe_push + branch protection),
  `bash: ask` under `--auto` leans on model discipline, ~70 live worktrees make
  the exactly-one-owner gate operationally brittle, secret scan is narrow
  patterns, `protected_cards.json` is 3 bytes (verify intentional).

## 5. First-pass Rules-authority signals (probes, not verdicts)

- `grep` over `src/` for classic fallback shapes (`sa.resolve`,
  `AbilitySub`, `random.choice/random/shuffle/randint`, default-yes,
  first-option, pilot-fallback) returned **no hits** — positive hygiene signal.
- Pilot RNG is keyed `seed+seat+offset+class` (`full_game.py:1098`), independent
  of engine UUIDs; transcript drops private `pilot_state`. Tactical lane uses
  `random.Random(request.seed)` (seeded). Full probes (decision-kind census vs
  inventory, redaction audit, Java-side legality reconstruction scan) remain in
  the backlog.

## 6. What orientation deliberately deferred

- No broad test-suite runs (impact-first; historical seals are fresh and the
  tree is unchanged since the audit base).
- No Forge deep work (WS219 owns Quorune/Argentum freshness; WS220 uses only
  the declared read-only WS217 reference root for process-level comparison).
- No replay implementation review (WS218 owns it; WS220 audits the requirement
  and contract shape only).

## 7. Audit map (where the value is)

Highest expected value: (a) evidence-model integrity — retained-47
justification, stale aggregates, vocab drift, G↔AF mapping, FULL107 decision
value; (b) source-truth reconciliation — stale 4P policy/docs vs mission;
(c) Rules-authority boundary verification by probe, not by reading claims;
(d) hidden-information assurance across logs/transcripts/errors;
(e) CI reproducibility (range-pins, the reported environmental failures);
(f) Foundry/workstream efficiency — sizing model, autonomy utilization,
roadmap order. Exploratory phase reserved for unknown unknowns (metric
analysis: what does any current number actually optimize?).
