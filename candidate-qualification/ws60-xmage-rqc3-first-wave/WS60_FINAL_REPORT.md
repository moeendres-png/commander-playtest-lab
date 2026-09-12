# WS60 Final Report — XMage RQ-C3 First-Wave Execution (Terminal Seal)

## Source Lock
- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws60/xmage-rqc3-first-wave-20260911`
- Frozen exec HEAD: `2c30040f82e4c97b308535a592f4facd1e5ec42e`
- Frozen exec tree: `6eb294a80eef75894cbd9111789b1b8591b35888`
- Audit base: `da4fa567312b6b0e4ef5cbfc7347748ca3c2dcd9` (ancestor; base tree `8f194ab8bc884025368a3667c217b86cb23a6ba8`)
- Commit chain: `da4fa56` → `ef9e2005` → `eb7b461b` → `4a1e19cc` → `f78557d7` → `940f1980` → `4857b4f4` → `4e0d068d` → `2c30040f` (state-only). No rewrite/rebase/amend.
- XMage successor (only accepted): `7135d5e85ddb4c8aa4b49b4192ca51947c822704`, tree `ea193e0d04493d53d962ed13ebd3b5d2f68838c7`. A deliberately invalid successor SHA appeared in the tasking and was NOT used.
- RQ-C3 authority: `897d72f0b57bb8febe045870acaa3d2dba4bde56` (closure-complete). Denominator verified exact: A03,A04,B01,C01,C03,D06,E01,E02,F01,G02,G03,G04,H01,I01,J02 (15). Decision-kind union verified 20/20 with no `may`, no generic ordering, no Damage Assignment Order.
- Evidence provenance tie: sealed evidence was generated on `4e0d068d` whose tree differs from the frozen HEAD by exactly one non-executable file (`WORKSTREAM_STATE.yaml`); executable code identical. Embedded provenance in all 30 files matches successor/tree/audit-base/authority pins.

## Work Completed
- Built the WS60 driver/pilot/tape/suite harness (new test-side code; no XMage engine edits) and executed all 15 corrected first-wave scenarios as actual-card 4-player Commander games on the WS56-qualified successor.
- Reached: 14 semantic PASS (each primary + twin replica + hidden-info + determinism), 1 designed structural UNKNOWN (B01), 0 FAIL.
- Full sweep `Ws60Rqc3FirstWaveTest` 15/15 green; full module 126/126 green, BUILD SUCCESS.
- Sealed 30 evidence JSONs byte-for-byte under `sealed-evidence/` with `WS60_EVIDENCE_MANIFEST.json` (SHA-256 per file, source==sealed) plus the two run-receipt logs.

## New Findings
- Delina creates the token on ANY d20 result (1–14 and 15–20); only 15–20 offers roll-again. Scenario completion therefore does not imply the band; the PASS is gated by the die journal (d20=[18], roll-again declined).
- Thrasios reveals are ~95% lands-to-battlefield in these decks; 1-of finding comes from scry-bottom selection, which motivated scry-dig caps for both seats in C01.
- The bridge projected key-mode `Choice` menus as zero options (silently cancelling alternative-cost casts) and sorted combat declaration frames by per-game UUID strings (50/50 twin flips). Both repaired at the adapter/projection layer with zero Rules impact; E02 realigned PASS ×4 including the sweep.
- C01's pitch exile arrives as `choose_object` (cost payment), not `target`; the capture predicate now accepts the engine's actual rendering.

## Changes
- Executable (frozen, audited in Phase 4): J02 token-defender map + piece-seek + bound/scan; C01 seeks/filter caps; `dieResults` tape parse; key-mode Choice projection with engine prompts; object-id/short-id projection redaction; content-ordered attacker/blocker frame sequences.
- Non-executable (this seal): sealed evidence + manifest + 7 audit JSONs + this report. No semantic code changed during AUDIT/SEAL.

## Tests / Evidence
- `Ws60Rqc3FirstWaveTest`: 15/15 green (14 PASS + B01 UNKNOWN-by-design). Full module: 126/126, BUILD SUCCESS (receipts `sealed-evidence/WS60_ws60-baseline.log`, `WS60_ws60-full3.log`).
- Structural re-verification from sealed files: 73,548 primary+replica frames, **0 out-of-option selections, 0 UNKNOWN selections**; all decks reconcile to exactly 100 cards; all 14 PASS rows fully PASS with zero REPLICA-DIVERGENCE.
- Manifest SHA-256: `20a03e89083a36c0e81a1840de48ee3ec5397971539982d1565bc81b6b2679d2`.

## PASS / FAIL / UNKNOWN
- `Ws60Rqc3FirstWaveTest` 15/15 green is a **test-suite** result, not the semantic count. Semantically: **PASS 14/15, FAIL 0/15, UNKNOWN 1/15** (B01's green test asserts UNKNOWN; that is not behavior credit).
- Per-scenario verdicts, principals, kinds, and evidence paths: `WS60_SCENARIO_MATRIX.json`.

## Behavior Credit
- **14/107** (`WS60_BEHAVIOR_CREDIT.json`): one credit per audited PASS; B01 contributes 0. 107 is the Full107 RQ behavior population (authority marks full107 NOT_RUN).

## Decision-Kind Runtime Coverage
- **19/20** directly exercised by PASS scenarios (`WS60_DECISION_KIND_COVERAGE.json`); `trigger ordering` is NOT_OBSERVED (required only by B01-UNKNOWN, zero `trigger_order` frames in its bounded logs). No `may`, generic ordering, or DAO reintroduced. E02's damage division is automatic compliant division per AG-3 (lethal-first, 4 rollover), verified, with no ordering choice offered or taken.

## Hidden Information
- Audit verdict **PASS** (`WS60_HIDDEN_INFO_AUDIT.json`): every PASS scenario's hidden rows pass; independent sealed-capture recheck shows strict principal scoping (each viewer sees only their own hand names; libraries counts-only outside entitled grant windows). C01 received special scrutiny after the Choice/redaction changes: pitch options carried exactly the single entitled card; cost texts carry no hidden identities; no option aliasing. No planted-negative control was run; none fabricated.

## Determinism / Replay
- Audit verdict **PASS** (`WS60_REPLAY_AUDIT.json`): all 14 PASS twins byte-identical on normalized logs (0 divergences; recomputed independently), same explicit Rules seeds, matching event multisets/views, zero replica assertion divergences. B01 twins mutually consistent but incomplete → UNKNOWN (no replay to bind, no divergence observed).

## B01 Disposition
- **B01 = UNKNOWN**, credit 0 (`WS60_B01_DISPOSITION.json`): bounded native assembly never reached the 5-Warden APNAP position, and nominal life totals are unreachable natively because each native Warden entry fires its own triggers. Taxonomy: FIXTURE_AUTHORITY_GAP + INSUFFICIENT_BEHAVIOR_EVIDENCE. No engine/transport/hidden/replay defect demonstrated; FAIL not supported.

## Remaining Blockers
- None for execution/audit/seal. Coordinator review of this terminal evidence is the next gate; remote persistence only if accepted.

## Outputs
- `sealed-evidence/` (30 JSONs + manifest + 2 run receipts), `WS60_EVIDENCE_MANIFEST.json`, `WS60_B01_DISPOSITION.json`, `WS60_HIDDEN_INFO_AUDIT.json`, `WS60_REPLAY_AUDIT.json`, `WS60_DECISION_KIND_COVERAGE.json`, `WS60_SCENARIO_MATRIX.json`, `WS60_BEHAVIOR_CREDIT.json`, `WS60_FAILURE_TAXONOMY.json`, this report.

## Dependencies Unblocked
- WS60-EXEC, WS60-AUDIT, WS60-SEAL complete on frozen HEAD `2c30040f`; Coordinator safe-push review unblocked.

## Exact Next Action
- Coordinator review of WS60 terminal evidence, then authorized safe_push actual only if accepted.

---
FULL107=NOT_RUN · ARCHITECTURE_FREEZE=NOT_CLAIMED · PRODUCTION_PROVIDER=NOT_SELECTED · REMOTE_PUSH=NOT_PERFORMED
