# PB-03 fresh-main reconciliation — final handoff (2026-09-29)

## Source Lock

- Implementation base at merge: `origin/main` `174696d15d1a7b33c6fd2cba4d9e4c4f16f4c61c`
- Worktree: `/home/moeen/code/lab-pb03-fresh-main-reconciliation-20260929`
- Branch: `integration/pb03-fresh-main-reconciliation-20260929`
- PR: #381 (Draft, base `main`)
- Source-lock chain: `72665dce` (audit base) → `7cb9e56a` → `12d3e1ac` → `23977253` → `b126249e` → `174696d15` (all merged normally, never rebased)
- State file: `.foundry/pb03-fresh-main-reconciliation-20260929.yaml`

## Terminal Main Lock

- Observed `origin/main` at handoff production: `174696d15d1a7b33c6fd2cba4d9e4c4f16f4c61c`
- Re-fetch before merge; if main advanced, re-adjudicate overlap (engine-bridge,
  `src/commander_lab/qualification/current_boundary/**`, `config/rules_engines.json`
  are runner-digest inputs and require requalification when touched).

## Donor Locks

- PR #304 head `08d23aa44c721d0825d8be9f1b9c5d2af58cb91c` — CLOSED (historical predecessor)
- PR #333 head `20b52958b43a3b373cdcb5e9e19bf706bcd2feeb` — MERGED to main as `10a43d2c` (content byte-identical)
- PR #316 head `662db683bd43bab106d61c2b5af9fab6406fdcb0` — OPEN; semantic value ported here
- PR #285 recovery point `4a56d17981e72c5afececd4b88d91a7eba67e379` — READ-ONLY donor; current head `b4ea7751` is `REJECT_NEVER_MERGE`

## Work Completed

- Ported PR #316's record-aware dimension admission and exact native-runtime
  receipt binding onto the current-main #333 midgame lane, preserving post-#344
  runner-identity freshness.
- Fixed the latent runner-digest defect (`built_utc` inside the digest) that made
  every real post-#344 receipt stale.
- Extended digest coverage to the PB-03 probe, `engine-bridge/pom.xml` and the
  Lab XMage bridge sources; bound the runtime engine fingerprint into the native
  mechanism suite; cleared surefire reports before the suites.
- Requalified the current boundary on the canonical engine pin `f79e4168` and on
  the documented Forge bridge checkout `e15f37d6` (Rules Core trees proven
  identical to `ef958ee9`).
- Repaired all material findings from a fresh-context adversarial review.

## Donor Semantic Ledger

See `DONOR_SEMANTIC_LEDGER.json` in this directory (machine-readable) and
`PB03_FRESH_MAIN_RECONCILIATION_20260929.md` §2. Headline: #333 consumed,
#316 ported with adaptation, #285 `NO_UNIQUE_PB03_SEMANTIC_VALUE` except build
plumbing (integrated), #304 closed as superseded.

## Architecture / Mechanism

`production midgame transport → record-aware admission → external decision
execution → construction truth → causal observation → exact semantic obligation
→ runner-bound native receipt → qualification credit`. No hidden shortcut: a
later layer never rescues an earlier failure, admission is not runtime proof,
reachability is not FULL107 credit, and blocked admission is never overridden by
a positive receipt.

## Exact Changes

See the PR #381 file list. Core surfaces:
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageMidgame*.java` (main's #333 lane; one review comment corrected)
- `src/commander_lab/qualification/current_boundary/{midgame_lane,dimension_admission,pb03_runtime,bridge_launcher,receipts}.py`
- `scripts/{run_midgame_capability_probe,run_current_boundary_qualification,assemble_current_boundary_evidence}.py`
- `tests/qualification/test_current_boundary_{midgame_lane,dimension_admission,pb03_runtime,receipts}.py`, `test_wsr22_current_boundary.py`, `test_current_boundary_readiness_packet.py`, `test_current_boundary_redaction_placeholders.py`
- `.github/workflows/pb03-runtime-qualification.yml`
- `qualification/final-current-boundary-20260927/**`, `qualification/pb03-fresh-main-reconciliation-20260929/MIDGAME_CAPABILITY_PROBE.json`
- `docs/pre_freeze_completion_20260927/PROVIDER_READINESS_PACKET_20260928.md`
- `engine-bridge/pom.xml` (classpath manifest as a build output)

## Fresh Midgame Partition (engine `f79e4168`)

8 `ENGINE_NATIVE_REACHABLE`, 9 `CAUSAL_ROUTE_REACHABLE`,
9 `CAUSAL_ROUTE_MEASURED_BLOCKED`, 1 `CONSTRUCTION_MISMATCH`, 2 `ENGINE_REJECTED`,
0 transport failures, 0 unrecognized verdicts. Construction verdicts:
6 `EXACT`, 2 `ALLOWED_VARIANCE`, 1 `MISMATCH`, 20 not-applicable.

## Dimension Admission Results

`TECHNICALLY_CONFORMANT`; **12 admitted / 18 blocked** from the live
`state_restoration_dimensions` manifest plus record events, zones and declared
object attributes. `starting_state_injection_supported` stays `false` and is
never used as a fallback. Admission grants no runtime or FULL107 credit.

## Native Receipt Results

**`FRESH_EXACT`**: the runtime ledger binds the exact audited class+method per
row, all-green, a content receipt digest, the executing Lab runner digest and the
canonical engine candidate commit. 30/30 executed and passed; runtime credit
`EXECUTED_PASS`; every matrix row keeps `full107_credit:
NONE_FROM_PB03_MATRIX`.

## Current-Boundary Results

Sealed at the requalified head: XMage 5 PASS / 58 UNKNOWN / 44 BLOCKED (native
213 tests), Forge 5 / 58 / 44 (native 217 tests). XMage hidden information
`PRINCIPAL_SCOPED` (4 distinct views, all requesters established), seed
acknowledged at the creation transaction; AF01 `FAIL`, AF04 `FAIL`, AF11
`UNKNOWN` for XMage; AF04 `UNKNOWN`, AF11 `UNKNOWN` for Forge.

## Privacy Evidence

- Java honeycard controls (`XmageMidgamePrivacyTest`,
  `XmageMidgameReviewRemediationTest`) plant distinct opposing-hand identities
  and scan create/arrival/get-state/causal/error/pending-decision surfaces; no
  foreign hand identity crosses, no decision frame is embedded in an observation.
- The persisted probe receipt contains no hand identities and no engine
  principal UUIDs (only the run nonce).
- The fresh XMage current-boundary hidden-information artifact is
  `PRINCIPAL_SCOPED` with content-only distinctness.

## Evidence Freshness Evidence

- Content-bound runner digest with a regression test proving time-independence
  and content sensitivity.
- Digest coverage: 61 executed inputs including the probe and bridge sources.
- `runtime_execution_freshness` returns `FRESH_EXACT` only for matching runner
  digest + candidate commit + all-green; otherwise `STALE` / `MISSING` /
  `INVALID` with zero credit.
- The midgame probe receipt and the runtime ledger share the same runner digest
  (same-run binding test).

## Tests / CI

| Gate | Result |
|---|---|
| `pytest tests` | 2401 passed, 9 skipped, 0 failed |
| `pytest tests/qualification` | 505 passed, 5 documented skips |
| `mvn -o verify` | 787 tests, 0 failures, 0 errors, 5 skipped |
| `ruff check` / `ruff format --check` | clean |
| strict mypy | clean on changed files |
| GitHub CI on PR #381 | see PR checks (pb03-runtime, conformance, quality, security, real-4p-smoke, h4-*, integrity) |

## Independent Review

Fresh-context adversarial review returned `MATERIAL_FINDINGS_PRESENT`; all
material findings were repaired (construction-verdict explicitness, admission
attribute derivation, stale auxiliary artifact citation, probe/bridge digest
coverage, unrecorded terminal, first-option fallback, surefire reset, exact-pin
guard, derived seed text, state-file currency). Residuals are recorded as
unresolved mechanisms (loaded-jar cryptographic identity; `RUNTIME_VERIFIED`
compatibility debt).

## PASS / FAIL / UNKNOWN

- PASS: dimension admission projection, native runtime execution (30/30),
  runner-identity freshness, privacy controls, midgame transport honesty,
  full repository Python suite, full engine-bridge suite, static gates.
- FAIL: none introduced by this workstream. Pre-existing boundary failures
  remain recorded (XMage AF01/AF04; Forge AF04) with no historical transfer.
- UNKNOWN: AF05–AF09 and AF11 policy/per-scenario gates; FULL107 row credit;
  loaded-jar cryptographic engine identity.

## Historical Evidence Invalidated

Sealed WSR22 receipts and PB-03 donor receipt (pre-repair digests, prior pin),
the donor 14/16 admission projection and 29-row counts, donor manifest hunks,
the "XMage fully uncontrolled" seed position, and the XMage shared-view
hidden-information defect. None transferred.

## Remaining Blockers (grouped by mechanism)

- **Engine artifact identity:** declared constant + runtime fingerprint; no
  cryptographic jar identity recorded.
- **Boundary gates:** XMage AF01/AF04, Forge AF04; AF05–AF09/AF11 policy and
  per-scenario gaps.
- **Forge environment:** native execution requires the `e15f37d6` bridge
  checkout; the default workspace is on a divergent WSR20 branch.
- **FULL107 promotion:** exact semantic-obligation bindings do not yet exist;
  reachability is deliberately uncredited.
- **Vocabulary:** `RUNTIME_VERIFIED` legacy marker normalization deferred.

## PR / Commit / Tree

- PR: #381 (Draft)
- Branch tip at handoff production: `ebb49813ccb7` (final artifact commit adds
  docs only)
- Pushed via `tools/foundry/safe_push.py` (sanctioned path)

## Donor Retirement

- #304: CLOSED (historical predecessor).
- #333: MERGED to main (`10a43d2c`); PR closed by merge.
- #316: OPEN — to be closed with a provenance comment after PR #381 merges and
  the ported value is proven preserved. Branches are never deleted.

## Dependencies Unblocked

- The PB-03 mechanism is production-reachable on XMage and evidence-bound; a
  future obligation-credit workstream can build on the admission × runtime
  matrix without redesigning transport or receipts.
- The runner-digest repair unblocks honest native-suite credit for every
  current-boundary consumer.
- The `e15f37d6` Forge checkout is identified for the Forge requalification
  workstream.

## Exact Next Action

1. `git fetch origin --prune`; if main advanced, inspect overlap and merge
   normally; requalify if any runner-digest input changed.
2. Confirm all required PR #381 checks are green on the exact head.
3. Merge PR #381 through the normal GitHub PR merge path if every merge-gate
   condition holds; otherwise leave open and report the exact blocker.
4. After merge: close PR #316 with the provenance comment; verify main HEAD/tree
   and persist the terminal receipt.

---

PB03_FRESH_MAIN_RECONCILIATION = PARTIAL
HISTORICAL_PASS_TRANSFERRED = NO
PR304_DISPOSITION = CLOSED_HISTORICAL_PREDECESSOR_SUPERSEDED_BY_333_AND_FRESH_MAIN_SUCCESSOR
PR333_DISPOSITION = MERGED_TO_MAIN_AS_10A43D2C_SEMANTIC_DONOR_CONSUMED
PR316_DISPOSITION = OPEN_SEMANTIC_VALUE_PORTED_TO_PR381_PENDING_RETIREMENT_AFTER_MERGE
PRODUCTION_PROVIDER = NOT_SELECTED
ARCHITECTURE_FREEZE = NOT_CLAIMED
