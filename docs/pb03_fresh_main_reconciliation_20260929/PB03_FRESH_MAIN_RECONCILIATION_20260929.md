# PB-03 fresh-main reconciliation — current-main record

- **Workstream:** `PB03-FRESH-MAIN-RECONCILIATION-20260929`
- **Branch / PR:** `integration/pb03-fresh-main-reconciliation-20260929` / PR #381 (Draft)
- **Implementation base:** `origin/main` `24b355b7f864364f4c7a7e6137c1947d1b231c1b` (merged normally; no rebase)
- **Canonical engine pin:** `config/rules_engines.json` → `moeendres-png/mage@9375f35ac7c9a540ebcb8b262b8645b8c6b1b326` (tree `0fb7c2f9a038e471de3a6e56419244482a645218`)
- **Frozen WSR22 boundary identity:** `source_lock.XMAGE_CANDIDATE_COMMIT = b1959698…` remains historical and is **not repinned**
- `PRODUCTION_PROVIDER = NOT SELECTED`; `ARCHITECTURE_FREEZE = NOT CLAIMED`

## 1. What was consolidated

PR #333 (production-reachable XMage mid-game starting-state transport) was merged to
main by the Coordinator as `10a43d2c` with content byte-identical to the donor head.
This workstream keeps that lane and adds the PR #316 semantic layer on top:

```
production midgame transport (midgame lane, engine-only construction verdict)
  → record-aware dimension admission (live per-dimension manifest)
  → external decision execution (engine-authored option ids only)
  → causal observation (live engine stack / loss flags; no fabrication)
  → exact semantic obligation (explicit construction_verdict + terminal records)
  → current runner-bound native receipt (exact class+method, all-green, content digest)
  → qualification credit (zero unless FRESH_EXACT; never a FULL107 promotion)
```

No second starting-state system, receipt identity system, redaction layer,
Protocol-2 decision system, evidence assembler or runner framework was created.
The midgame lane reuses the canonical launch plan (`bridge_launcher` lane
`midgame`), the canonical session/decision controller, and the canonical
receipt/digest helpers.

## 2. Donor semantic ledger (summary)

Machine-readable ledger: `DONOR_SEMANTIC_LEDGER.json` in this directory.

| Donor | Unit | Disposition |
|---|---|---|
| #333 | `XmageMidgameJsonlBridge`, `XmageMidgameCausalBridge`, `Main` dispatch, colorless-commander Wastes fix, 4 Java tests | consumed (merged to main; Wastes + lane live) |
| #333 | `midgame_lane.py`, `run_midgame_capability_probe.py`, Python test | **port with adaptation** (canonical launch plan, receipt freshness, entry-mode fix, UUID removal, first-option removal, terminal records) |
| #333 | donor `MIDGAME_CAPABILITY_PROBE.json` (pin `b1959698`, raw principal UUIDs) | **rejected as credit**; requalified at the live pin; the donor file remains in-tree as provenance only |
| #333 | `WS17_SHA256SUMS` / `qualification/SHA256SUMS` hunk lines | rejected; manifests regenerated from the current tree |
| #316 | `dimension_admission.py` | port with adaptation (declared attribute dimensions now govern; 12/18) |
| #316 | `pb03_runtime.py` | port with adaptation (content digest + runner/candidate freshness) |
| #316 | runner/assembler hunks | port with adaptation (live canonical pin, digest coverage, auxiliary-artifact freshness, stale-report reset) |
| #316 | workflow | port with adaptation (live pin resolution, probe freshness assertion, matrix assertions) |
| #316 | `XmageFullGameJsonlBridge` capability hunk, PB-03 Java tests | ported |
| #316 | `.foundry` donor JSON, old 30-row matrix | provenance only |
| #285 | recovery point `4a56d179` | `NO_UNIQUE_PB03_SEMANTIC_VALUE`; only build plumbing (`cp-wsr22.txt` as a Maven build output) integrated. Current head `b4ea7751` is `REJECT_NEVER_MERGE`; branch kept as provenance |
| #304 | predecessor | closed, superseded by #333 + this successor |

## 3. Fresh runtime partition (midgame capability probe, engine `9375f35a`)

29 rows rederived on the canonical candidate; counts are runtime facts, not
historical copies:

| Outcome | Count | Rows (2026-09-30, after main's commander-object binding fix) |
|---|---|---|
| `ENGINE_NATIVE_REACHABLE` | 8 | COMBAT-4/5, CMD-ELIM-4, CMD-DMG-SPLIT, CMD-PARTNER-ZONE, CMD-TAX-2, MICRO_COMBAT, CARD_02 |
| `CAUSAL_ROUTE_REACHABLE` | 17 | BLOCK-4, ELIM-PRIO-3, MICRO_REPLACEMENT, PRIO-3/5, all eight `WS05-CMD-ZONE-*` rows, MICRO_ZONE_CHANGES, ELIM-OWNED-3, ELIM-TURN-3, ELIM-5 |
| `CAUSAL_ROUTE_MEASURED_BLOCKED` | 1 | TURN-5 |
| `CONSTRUCTION_MISMATCH` | 1 | ELIM-STACK-3 |
| `ENGINE_REJECTED` | 2 | CMD-DMG-CONTROL (`midgame_starting_state_rejected`), ELIM-CONTROL-3 (`midgame_causal_preparation_rejected`) |
| `TRANSPORT_FAILURE` | 0 | — |

`construction_verdict` is explicit on every arrival row: 6 `EXACT`,
2 `ALLOWED_VARIANCE` (the documented declaration-step priority mismatch, raw
engine bit still `false` and visible), 1 `MISMATCH`, 20 `None` (causal/transport
rows carry no construction verdict). Elimination rows record the engine's own
`victim_lost`/`victim_left` terminal.

## 4. Dimension admission and native runtime receipts (current boundary)

| Layer | Result |
|---|---|
| Admission | `TECHNICALLY_CONFORMANT`, **12 admitted / 18 blocked**, computed from the live `full_game_lane.state_restoration_dimensions` manifest + record events/zones/declared attributes. `starting_state_injection_supported` is never a fallback and stays `false`. |
| Native runtime ledger | **30/30 exact audited class+method testcases** green (`PASS`), content digest sealed |
| Native receipt | **`FRESH_EXACT`** (runner digest + canonical candidate commit match the assembling head) |
| Runtime credit | `EXECUTED_PASS` |
| Loaded engine artifact | provider-reported `file`, SHA-256 `e04062d2e180c8e322256bd92675c5cd49d73f5f6894140e5a86e45764661603`, 7,112,962 bytes (the mage jar the bridge loaded) |
| FULL107 credit | **`NONE_FROM_PB03_MATRIX`** — reachability never promotes a row |
| Blocked admission | never overridden by a runtime PASS |

Current boundary columns (sealed at the requalified head): XMage 5 PASS / 58
UNKNOWN / 44 BLOCKED (native 215 tests), Forge 5 PASS / 58 UNKNOWN / 44 BLOCKED
(native 217 tests). XMage hidden information is `PRINCIPAL_SCOPED` (four distinct
views, all requesters established) and the seed is acknowledged at the creation
transaction; the WSR22 "fully uncontrolled" position is retained only as
history.

## 5. Evidence-integrity defects found and repaired

1. **Runner digest was capture-time-dependent** (`built_utc` inside the digest):
   the runner and the assembler could never agree, so every real post-#344
   receipt was silently `stale_runner_excluded` and `native_runs` came back
   empty. The digest is now content-bound (commit, tree, dirty state, executed
   inputs) with `built_utc` kept as provenance.
2. **Digest coverage gap:** the PB-03 probe, `engine-bridge/pom.xml` and the Lab
   XMage bridge sources are now executed inputs (61 digests), so adapter/probe
   drift invalidates receipts even with an unchanged engine commit.
3. **Engine artifact identity:** the local Maven cache held the prior pin; the
   canonical candidate was built from a verified clean clone, and
   `XmageCandidateEngineFingerprintTest` is now bound into the native mechanism
   suite so the loaded artifact is part of the observed evidence.
4. **Stale-report risk:** the runner clears surefire reports before the native
   suites.
5. **Stale auxiliary artifact:** the assembler refuses to cite
   `AF01_XMAGE_FULLGAME_LANE.json` when it is bound to a different engine epoch.
6. **Admission overstatement:** `WS05-MP-ELIM-CONTROL-3` and
   `WS05-CMD-DMG-CONTROL` declare `owner != controller`; the manifest marks the
   divergence unsupported and the seam rejects both, so admission is 12/18.
7. **Probe honesty:** raw engine principal UUIDs removed, causal rejection
   entry-mode fixed, first-option discard fallback removed, and an unrecorded
   causal terminal is `MEASURED_BLOCKED` rather than credit.
8. **Loaded engine artifact identity (2026-09-30):** `XmageProvider` now reports
   the loaded engine artifact's kind, path, size and SHA-256, computed from the
   loaded `Game` code source. The runtime fingerprint test recomputes that digest
   independently. The PB-03 admission handshake validates a file-backed 64-hex
   digest and stores it; the runtime ledger and the midgame probe seal the same
   identity; the assembler cross-checks admission/runtime and reports
   `artifact_identity_consistent`; missing, malformed, directory or mismatched
   artifacts earn zero runtime credit.

## 6. Historical evidence invalidated (not transferred)

- The sealed WSR22 current-boundary receipts and PB-03 donor receipt (bound to
  `b1959698`; runner digests pre-repair).
- The donor 14 admitted / 16 blocked projection and the donor 29-row counts.
- The donor `WS17_SHA256SUMS` / `qualification/SHA256SUMS` hunks.
- All pre-merge XMage/Forge receipts and PB-03 documents (superseded by the
  requalified run at the current head).
- The XMage "fully uncontrolled" seed position and the shared-view
  hidden-information defect: requalified, recorded as history.

## 7. Tests

| Gate | Result |
|---|---|
| `pytest tests` | 2401 passed, 9 skipped, 0 failed |
| `pytest tests/qualification` | 505 passed, 5 documented skips |
| `mvn -o verify` (engine-bridge) | 787 tests, 0 failures, 0 errors, 5 skipped |
| `ruff check .` / `ruff format --check .` | clean |
| strict `mypy src/commander_lab` | clean on changed files (8 pre-existing missing-stub errors in unrelated modules) |
| PB-03 CI workflow | live pin resolution, probe freshness assertion, admission/runtime assertions, runner-digest equality |

## 8. Unresolved mechanisms

- The XMage "engine commit" is a declared constant; the loaded artifact's
  cryptographic identity is now provider-reported and bound through the PB-03
  evidence (admission, runtime ledger, probe, matrix). What remains open is only
  the general question of Maven build reproducibility, not identity binding.
- XMage AF01 remains `FAIL` on the generic compatibility lane and AF04 `FAIL`;
  AF05–AF09 and AF11 remain `UNKNOWN` for policy/per-scenario reasons.
- Forge native execution requires the documented `e15f37d6` bridge checkout;
  the default workspace moved to a divergent WSR20 branch whose bridge lacks the
  Commander-legality repair.
- `RUNTIME_VERIFIED` remains in some machine-readable contracts as legacy
  compatibility metadata (Coordinator decision); a future bounded
  schema-normalization workstream owns normalization.
- FULL107 rows stay uncredited until exact semantic-obligation bindings exist;
  no reachability promotion is claimed.
