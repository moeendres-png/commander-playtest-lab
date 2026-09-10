# WS48-R1f Repair-01 — Selection→Execution Integrity Remediation Report

- repair: WS50-ADAPTER-REPAIR-01 ported into the canonical WS48 provider overlay
- class: ADAPTER_BINDING (NOT a Forge Rules-Core defect; no engine change)
- branch: `ws48/repair01-selection-execution-integrity-20260910`
- base: WS48 R1e `10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d`
- verdicts: WS48_REPAIR01 = PASS — SELECTION_EXECUTION_INTEGRITY = PASS

## 1. Source lock (freshly verified)

| item | value |
|---|---|
| repo | `moeendres-png/commander-playtest-lab` (`https://github.com/moeendres-png/commander-playtest-lab.git`) |
| this branch HEAD at start | `10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d` / tree `89e3208aa0f5206641850704d7d116880faa02e1` |
| origin WS48 R1e HEAD/TREE | identical (match) |
| origin WS50 terminal HEAD/TREE | `e636e7055478709010cbd778846683065e31655b` / `59a08ba105a4f666e735c36cd8cd7c8c17ca1fd3` (match) |
| WS48 ancestor-of WS50 | yes, exactly 4 commits |
| canonical main at issuance | `c162871ba416c338d37f83a44fbd5b054e79ca0e` (drift noted, R1e base intentional) |
| WS47 contract | `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`, SHA `0e47b792…940b3`, 107/107 (read-only; untouched) |
| Forge engine pin | `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29…` (unchanged; `FORGE_ENGINE_PIN_CHANGED = FALSE`) |
| working tree at start | clean; exactly one writer (this session); sibling workstreams (Task 2B, cross-repo hardening) in other worktrees, untouched |

## 2. Defect (WS50 finding, re-verified — not re-investigated from scratch)

The WS48 behavior-provider overlay replaced the base provider's
`labels.add("FORGE_LEGAL_ACTION")` with a block starting with an extra
`nativeOptions.add(sa)`. The base already adds once per seen SpellAbility, so
the materialized provider contained, per SA: **2 nativeOptions entries / 1 ACT
label**. `Broker.choosePriority` returns `nativeOptions.get(idx-1)` for opaque
id `o<idx>`, so every non-first ACT selection executed a shifted neighbor
ability while transcripts still completed. WS50 runtime proof: external
selection o8 Play-land MINTED-22 executed as MINTED-77 (WS50_C_RUN10 frames
15–16). First-option selections bind `nativeOptions[0]`, identical under both
mappings — which is why R1e transcripts completed.

## 3. Pre-fix reproduction (SELECTION_EXECUTION_INTEGRITY = FAIL)

`ws48_r1f_selection_execution_gate.py` on exact R1e source, corroborated
against the retained R1e built provider
(`/home/moeen/.ws48-r1e/ev/generated/.../Ws23ForgeVerticalProvider.java`
lines 243–245):

- base generator (`scripts/ws23_generate_forge_vertical_provider.py` seen-block):
  1× `nativeOptions.add(sa)` + 1× label — proven single-add origin;
- overlay `PRIORITY_LABEL_NEW`: 1× `nativeOptions.add(sa)` + 1× ACT label —
  the second add;
- materialized R1e provider: 2 adds / 1 label in `if (seen.add(sa))`;
- mechanism simulation (N=4): L1 binds (SA1→SA1); L2 wants SA2 gets SA1; L3
  wants SA3 gets SA2; L4 wants SA4 gets SA2 — non-first ACT always misbinds;
- gate exit 2 with `SELECTION_EXECUTION_INTEGRITY=FAIL`
  (artifact `WS48_R1F_PREFIX_GATE.json`);
- focused pytest pre-fix: 8 repair-dependent failures incl. all gate tests;
  negative control (synthesized double-add flagged) passed pre-fix, proving
  the gate non-vacuous.

## 4. Repair-01 port (WS48-owned files only)

`candidate-qualification/ws48-forge-v1.0.5/ws48_behavior_provider_overlay.py`:

1. Removed the extra `nativeOptions.add(sa);` from `PRIORITY_LABEL_NEW` — the
   replacement now projects exactly one ACT label per native option and adds
   zero native entries (base adds once). One native SA ↔ one ACT label ↔ one
   opaque id restored.
2. Durable runtime gate in generated `Broker.choosePriority`:
   - cardinality assertion `nativeOptions.size()+1 == labels.size()`, else
     `ControlledStop WS48_SELECTION_EXECUTION_CARDINALITY_MISMATCH`;
   - opaque-index range check, else `WS48_SELECTION_EXECUTION_INDEX_OUT_OF_RANGE`;
   - `priority_binding` NATIVE_EVENT per ACT selection binding selected
     idx + selected label identity to the RETURNED native host id (additive;
     PASS short-circuits before it; ignored by drivers not consuming it).
   - Note: the PASS branch reads `return null` (not `List.of()`) because the
     ws25 generation layer rewrites it before this overlay runs last; the
     binding anchor matches the materialized text.
3. `required`-markers extended so the overlay fails loudly if guards go missing.
4. No unrelated WS50 functionality copied (no frame journals, observations,
   RNG metadata, sequence runner, scenario logic).

Post-fix materialized provider: 1 add / 1 label (line 244), guards present
(lines 255/259/265), `javac` clean, forbidden-pattern grep clean
(no `forge.ai/gui`, no AI controller, no first-candidate defaults, no RNG).
Provider digest `ca969302…`; state digest unchanged from R1e (`b6b0870f…`).

## 5. Selection→execution integrity gate (permanent)

- Static: `ws48_r1f_selection_execution_gate.py` (overlay zero-add check,
  base single-add proof, provider check, cardinality simulation,
  parallel-structure audit, `--mutate-check` negative control). Post-fix:
  `verdict PASS`, `SELECTION_EXECUTION_INTEGRITY=PASS`
  (`WS48_R1F_SELECTION_EXECUTION_GATE.json`;
  `WS48_R1F_POSTFIX_STATIC_GATE.json` incl. materialized-provider check).
- Runtime: cardinality/index fail-closed assertions + per-selection binding
  records, verified live (every post-fix ACT selection emitted exactly one
  `priority_binding`; PASS-only rows emitted none).
- Regression: `tests/qualification/test_ws48_repair01_selection_execution.py`,
  14/14 PASS (cardinality, exact non-first mapping, mutation detection,
  first-ACT, sentinel offsets, zero/ambiguous/unsupported fail-closed on live
  driver code, no-AI/no-fallback, idempotence).

## 6. Parallel-structure audit

23 WS48 transports inspected. Post-fix: **20 INVARIANT_PROVEN, 3
NOT_APPLICABLE** (pure arithmetic/fixed-size mappings with no parallel list),
0 TARGETED_REPAIR_REQUIRED, 0 UNKNOWN. Pre-fix, `Broker.choosePriority` was
the single TARGETED_REPAIR_REQUIRED entry. No second same-class bug found; no
scope expansion. Full table in the gate JSON (`parallel_structure_audit`).

## 7. Historical evidence inventory (exact artifact state)

- R1e: retained 10-row probe `WS48_R1E_FULL10_PROBE.json` (local validation of
  commit `10a7f8f6`) + WS50 pre/post-repair 6-row regression probes
  (read-only, WS50 branch) + WS47 materialization (scripts only).
- R1b/R1c: commit `0a302235` (cost visitor, terminal emitter) + overlay source.
- R1d: `WS48_R1D_DISCRIMINATOR.json` + `run_r1d_discriminator.py` +
  `r1d_discriminator_template.java` (hand-built native, no provider).

## 8. R1b / R1c / R1d / R1e impact (per-unit ledger `WS48_R1F_HISTORICAL_IMPACT_LEDGER.json`)

Method per unit: choosePriority reached? ACTs offered? which index selected?
(derived from WS47 scripts under exact retained driver semantics — ACT is
selected ONLY via matching priority/choose_ability entries, else structural
PASS o0). First-ACT? Mechanism rule: PASS never indexes; o1 binds exactly even
when broken; only non-first ACT could misbind.

- **R1e (10 rows): all NO_IMPACT.** Scripted ACT picks are all first-ACT o1:
  PILOT_PRIORITY/PILOT_TARGET obj:pilot-bolt (rank 1/3), PILOT_CHOOSE_MODE
  obj:burn (1/7), MICRO_PRIORITY obj:micro-growth (1/2), CARD_02 cmd:P1-A
  (1/1). All other frames structural PASS. PILOT_MULLIGAN / PLAYER_COUNT_2P /
  HIDDEN_01 / WS05-MP-BLOCK-4 never select ACT (no priority script; PASS-only
  or PASS-answered, incl. later 8–9 Mountain frames). NEGATIVE_FIRST_OPTION
  never reaches priority (0 frames). No per-frame execution witness existed
  (TRANSCRIPT_COMPLETE is not execution proof — the learned lesson), but
  mechanism proof covers first-ACT/PASS exactly. WS50 6/6 pre/post-repair rows
  byte-identical (verdict/frames/consumed/offered_digest) corroborate.
  Post-fix binding records independently confirm idx=1 on all 5 scripted picks.
- **R1b (cost surfaces): NO_IMPACT** — visitor branches never touch
  choosePriority nativeOptions; corroborating rows first-ACT per above.
- **R1c (terminal emitter): NO_IMPACT** — operates on stop_reason/snapshot only.
- **R1d (variants A/B): NO_IMPACT** — hand-built native combat; choosePriority
  never executes; NPE presence/absence verdict independent of priority binding.

## 9. Impact ledger totals

- NO_IMPACT = 14
- TARGETED_REQUALIFICATION_REQUIRED = 0
- INVALIDATED = 0
- UNKNOWN = 0

No rerun of NO_IMPACT evidence was performed for reassurance (one bounded
validation run only, per policy).

## 10. Non-first ACT runtime witness (`WS48_R1F_REPAIR01_RUNTIME_WITNESS.json`)

PILOT_MULLIGAN natural-start session, witness-controlled priority:

1. Frame d15 offered 10 options / 9 ACTs; 8 identical-sa ("Play land") options
   with distinct hosts — multiple ACTs offered ✓;
2. external intent selected the LAST one, o8 MINTED-22, ACT rank 8/8, by strict
   host identity — non-first ✓ (mirrors WS50_C_RUN10 frame 15 exactly);
3. exactly one native option bound; Java record:
   `idx=8:label=WS48:ACT:host=MINTED-22:…:hostId=22` — returned object is
   MINTED-22 ✓;
4. next same-actor frame: MINTED-22 absent from "Play land", present offering
   battlefield `{T}: Add {R}` (MINTED-100 commander alongside) — the selected
   card moved hand→battlefield and the engine accepted it ✓.

Negative control (`WS48_R1F_NEGATIVE_WITNESS.json`): historical double-add
reintroduced (guards neutralized to reproduce silent mode) → witness FAILs:
binding `idx=8:…MINTED-22…:hostId=77`, MINTED-77 on battlefield, MINTED-22
nowhere — byte-exact recurrence of the WS50 MINTED-22/77 misbinding, now
machine-caught. Gate proven non-vacuous at runtime.

## 11. Post-fix bounded R1e regression (`WS48_R1F_POSTFIX_R1E_REGRESSION.json`)

ONE full-10 probe post-fix (Full107 NOT run): verdicts/frames/consumed/
offered_digests **identical to R1e on all 10 rows** (5× TRANSCRIPT_COMPLETE,
3× BLOCKED_AT, 1× EXPECTED_FAIL_CLOSED_PASS, 1× retained PROBE_FAIL
WS05-MP-BLOCK-4). Anti-echo PILOT_PRIORITY mutation invariance PASS
(`WS48_R1F_POSTFIX_R1E_MUTATED.json`; digest `ffe16b80…` matches R1e CI).
No behavior/progress-taxonomy change; anti-echo and fail-closed intact
(incl. NEGATIVE_FIRST_OPTION EXPECTED_FAIL_CLOSED_PASS).

## 12. Rules / pilot boundary; Forge pin

Forge sole legality authority preserved: provider projects identities over
Forge-native options only. No legality reconstruction, filtering, fabrication,
forced outcome, manual execution, name-only comparison, or internal AI
(static test + CI forbidden-pattern grep). `FORGE_ENGINE_PIN_CHANGED = FALSE`;
classification stays ADAPTER_BINDING.

## 13. WS50 / WS47 / coverage (unchanged)

WS50 untouched (terminal evidence retained: PRIMARY_SLICE PASS, R2 NOT_FIRED,
0 engine-side production stalls, 0/107 credit). WS47 immutable (denominator,
books, credit untouched). BEHAVIOR_CREDIT = 0/107, COVERAGE_PROMOTION = FALSE,
FULL107 = NOT_RUN. No Freeze, no provider selection.

## 14. Tests / runtime evidence summary

- `tests/qualification/test_ws48_repair01_selection_execution.py`: 14/14 PASS.
- Static gate post-fix PASS (+ provider check + mutate-check).
- Witness PASS + runtime negative FAIL (as required).
- Bounded R1e 10/10 identical + anti-echo PASS.
- Existing WS48 overlay tests: none pre-existed; no unrelated suites rerun.

## 15. Outputs (under `candidate-qualification/ws48-forge-v1.0.5/`)

`WS48_R1F_REPAIR01_REPORT.md` (this file),
`WS48_R1F_HISTORICAL_IMPACT_LEDGER.json`,
`WS48_R1F_REPAIR01_RUNTIME_WITNESS.json`,
`WS48_R1F_NEGATIVE_WITNESS.json`,
`WS48_R1F_POSTFIX_R1E_REGRESSION.json`,
`WS48_R1F_POSTFIX_R1E_MUTATED.json`,
`WS48_R1F_SELECTION_EXECUTION_GATE.json`,
`WS48_R1F_POSTFIX_STATIC_GATE.json`,
`WS48_R1F_PREFIX_GATE.json`,
`ws48_r1f_selection_execution_gate.py`,
`ws48_r1f_impact_audit.py`,
`ws48_r1f_nonfirst_act_witness.py`;
plus `tests/qualification/test_ws48_repair01_selection_execution.py`.
No immutable historical artifact mutated. Heavy build trees live outside the
repo (`/tmp/r1f-ev`, `/tmp/r1f-ev-neg`); provider digest `ca969302…`.

## 16. Terminal adjudication

- WS48_REPAIR01 = PASS (adapter-integrity remediation; not Forge qualification)
- SELECTION_EXECUTION_INTEGRITY = PASS (pre-fix FAIL evidenced)
- BEHAVIOR_CREDIT = 0/107; COVERAGE_PROMOTION = FALSE; FULL107 = NOT_RUN
- WS50_PRIMARY_SLICE = RETAINED; R2_TRIGGER = NOT_FIRED
- ARCHITECTURE_FREEZE = NOT CLAIMED; PRODUCTION_PROVIDER = NOT SELECTED

Remaining blockers: none in scope. Exact next action: coordinator review of
this branch; no PR/merge/X-Mage/Full107 from this workstream.
