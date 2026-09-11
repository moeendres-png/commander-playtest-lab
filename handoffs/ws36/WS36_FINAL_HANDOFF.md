# WS36 FINAL HANDOFF

## Source Lock

Commander Lab qualification runtime commit: `accda3a0641d4f425117ff1224411bf40dcde965`  
Tree: `70f6136cbcf409555d3315ea22e9ced34c7d67ac`  
XMage: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` / `f0a028b265f9c008ea0aedc4cec6b8f14500b69f`  
WS-32: `038d0f38635eecee4e331c99af41f148de267a26` / `0d160128119f2bad30b220a17c43419b50b7edbe`  
Contract: `commander-lab.semantic-fixture-materialization/1.0.2`  
Canonical materialization: `ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23`  
Workflow run: `33656641279`

## Work Completed

WS-34 UUID-domain, CARD_02 identity-domain, v1.0.2 RNG-schema and PILOT_CHOOSE_USE tapped-snapshot provider defects were root-caused and code-remediated where legal. The exact 107-record frozen denominator was re-censused. A pin-bound terminal capability audit established that the three mandatory commander-tax records require prior command-zone cast history as starting state but the retained XMage API exposes no non-event state-restore path for `CommanderPlaysCountWatcher`.

## New Findings

`CommanderPlaysCountWatcher` stores command-zone cast counts in private maps, mutates them only from native `SPELL_CAST` / `LAND_PLAYED` events from the command zone, and exposes read-only count access. The same watcher blob is present at the freshly observed upstream commit `8f8b9828a8e236ab1435b2ffe4c3023125763c4a`. Replaying fabricated historical casts/events is prohibited by WS-32/WS-36, and Commander Lab may not implement commander-tax semantics itself.

## WS-34 Defect Closure

See `WS36_WS34_DEFECT_REMEDIATION_LEDGER.json`. `WS34-XMAGE-CORE-UUID` is remediated and scoped-CI verified. The known-deck inversion privacy regression remains closed. CARD_02 identity, RNG schema and PILOT_CHOOSE_USE construction received code remediation but no full-record v1.0.2 runtime credit after the mandatory terminal stop condition. Setup/transaction coverage remains terminally blocked.

## Native Construction Results

Exact denominator: 107. Three mandatory records (`WS05-CMD-TAX-2`, `WS05-CMD-TAX-4`, `WS05-CMD-PARTNER-TAX`) cannot construct the frozen prior-command-zone-cast-count state with the retained native XMage API without either fabricated historical Rules events, private-state reflection, or an external commander-tax implementation. All are prohibited. No requested/constructed equality credit is granted.

## Runtime Results

107 records have one terminal accounting result: 3 `BLOCKED_XMAGE_PROVIDER_DEFECT_COMMANDER_CAST_HISTORY`; 104 `NOT_RUN_AFTER_MANDATORY_PROVIDER_STOP_CONDITION`. Runtime PASS: 0/107. Historical PASS imported: false.

## AF04

0/24 PASS. Final: FAIL_NOT_QUALIFIED.

## AF05

0/20 PASS. Narrow known-deck inversion regression remains PASS, but full AF05 was not promoted. Final: FAIL_NOT_QUALIFIED.

## AF06

0/17 PASS. Final: FAIL_NOT_QUALIFIED.

## AF08

0/36 PASS. Mandatory commander-tax records are within this denominator and establish the terminal provider blocker. Final: FAIL_NOT_QUALIFIED.

## AF09

0/5 successor PASS. `SCENARIO_SEED` infrastructure defect is code-remediated, but no historical or partial replay result is promoted. Final: FAIL_NOT_QUALIFIED.

## CARD_02

Code remediation for projection aliasing is present; complete v1.0.2 runtime record was not promoted after the terminal stop condition. Final: NO CREDIT.

## Changes

Commander Lab only. XMage source changed: **NO**. WS-32 changed: **NO**. WS-34/WS-35 changed: **NO**.

## Tests / Evidence

All machine-readable evidence is SHA-256 sealed in `WS36_SHA256SUMS` and independently revalidated after artifact download (`sha256sum -c`: all entries PASS).

Final GitHub Actions evidence:

- workflow run: `33656641279` — all four jobs SUCCESS;
- contract-probe job: `100336725400` — SUCCESS;
- terminal-capability-audit job: `100336725571` — SUCCESS;
- identity-regression job: `100336725867` — SUCCESS, including exact pinned XMage build;
- terminal-evidence job: `100336869999` — SUCCESS;
- final complete artifact: `9856999272`;
- artifact name: `ws36-final-complete-accda3a0641d4f425117ff1224411bf40dcde965`;
- artifact SHA-256: `50cfde91118c0703bc88a615689e19f7e8f1f3918ad15bdc2f27064d32b85d04`;
- capability artifact: `9856982823`, SHA-256 `8c2556a12ca5572c080d1df29374dee09fd400351e02acd93c5974e332a25ad6`;
- contract-probe artifact: `9856974643`, SHA-256 `d7b7bb38c35d43db2ffc63a0110541235d4290b4e92e3572444606aae8aa9ed0`;
- Draft PR: `#151`, `WS-36: XMage successor remediation — terminal fail-closed`, intentionally unmerged.

## PASS / FAIL / UNKNOWN

**COMPLETE / FAIL_NOT_QUALIFIED**. `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = false`. This is terminal for WS-36 under the current no-XMage-modification scope.

## Defect Register

- CONTRACT_DEFECT: none established.
- QUALIFICATION_INFRA_DEFECT: old `rules_seed` assumption remediated; prior WS-34 constructed-state echo cannot be used as v1.0.2 credit.
- XMAGE_PROVIDER_DEFECT: terminal `CommanderPlaysCountWatcher` state-restoration capability gap plus remaining unexecuted construction/transaction surfaces.
- XMAGE_RULES_DEFECT: none established.
- AUTHORITY_DEFECT: none established.

## Remaining Blockers

Minimum blocking change: XMage must expose a native state-restoration-safe API (or general serialized GameState restoration path) that restores per-commander/per-player command-zone cast counters without generating historical Rules events. WS-36 is not authorized to modify `moeendres-png/mage`.

## Outputs

Final artifact contains exactly the required WS-36 outputs:

1. `WS36_SOURCE_LOCK.json`
2. `WS36_XMAGE_UPSTREAM_DELTA_AUDIT.json`
3. `WS36_WS34_DEFECT_REMEDIATION_LEDGER.json`
4. `WS36_NATIVE_CONSTRUCTION_MATRIX_107.json`
5. `WS36_REQUESTED_CONSTRUCTED_DIGEST_RESULTS_107.json`
6. `WS36_DECISION_IDENTITY_MAPPING_AUDIT.json`
7. `WS36_TRANSACTION_COVERAGE_107.json`
8. `WS36_HIDDEN_INFORMATION_RESULTS.json`
9. `WS36_RNG_REPLAY_RESULTS.json`
10. `WS36_CARD02_RESULT.json`
11. `WS36_SUCCESSOR_RESULTS_107.json`
12. `WS36_AF_RESULTS.json`
13. `WS36_EVIDENCE_INDEX.json`
14. `WS36_VALIDATION.json`
15. `WS36_SHA256SUMS`
16. `WS36_FINAL_HANDOFF.md`

The complete GitHub Actions artifact is `9856999272` with SHA-256 `50cfde91118c0703bc88a615689e19f7e8f1f3918ad15bdc2f27064d32b85d04`.

## Dependencies Unblocked

A new Actual-Card runtime workstream **may not** consume XMage as a qualified successor provider. WS-35 remains unchanged and must not be reopened.

## Exact Next Action

Preserve the exact terminal blocker(s), do not weaken WS-32, and identify the minimum next provider- or engine-side remediation required. The minimum next engine-side remediation is the native commander-cast-history restoration capability described above; after such an authorized XMage change, start a new successor-provider remediation/requalification workstream rather than rewriting WS-36 evidence.
