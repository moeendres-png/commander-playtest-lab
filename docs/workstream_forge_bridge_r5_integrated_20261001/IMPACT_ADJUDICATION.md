# Forge bridge source rebind (forge#16): impact adjudication

- **Change:** the Forge **bridge/materialization** source moves from `e8b8aec60720aee218338754224721597b8c6ec5` (tree `6c49f100`, #11 + AF01 #13) to `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (tree `00006689`).
  - That commit is the forge#16 head.
  - The #11 qualification branch was fast-forwarded to it at 2026-10-01 08:18Z.
- **Unchanged:** the Rules-Core authority `bb0a740d2bef725194798383c2452213ecdd0b37` (R-1, #11 incl. #12). The two roles stay separate fields: `secondary_engine.commit` and `secondary_engine.bridge_source.commit`.
- **Lock:** `qualification/forge-bridge-r5-integrated-20261001/SUCCESSOR_SOURCE_LOCK.json`. The R-1 lock `qualification/forge-r1-candidate-authority-20260930/` keeps `e8b8aec6` as its bridge source.
- **Not:** Production Provider selection, Architecture Freeze, a denominator change, a Rules-Core change, or a merge to `forge/master`.

## Delta `e8b8aec6..20e3e1f7` (bridge only)

`bb0a740d..20e3e1f7` touches only `forge-protocol2-bridge/`: 0 Rules-Core files and 0 card-data files.

| Change | Behaviour |
|---|---|
| #15 no-default hardening | Multi-part cost payment order is an external decision. There is no silent negative Assist fallback. Unexpected mana and Delve requests are explicit unsupported faults. An optional multi-category decline continues to later categories. Unrepresented discard, exile and counter cost shapes fail closed before they are offered. |
| Cost order projection | The CR 601.2h cost order is a Protocol-2 `structural_decision` with `metadata.decision_subtype` (`cost_order` or `cost_order_next`) and `metadata.cost_order_indices`, the native CostPart indices. |
| Test pilots | Answer only explicit `ORDER_CHOICE` cost-order frames, by content. |

## Exact-head evidence (`20e3e1f7`)

| Evidence | Result |
|---|---|
| Test build, push run 36832184994 | Java 17 and Java 21 success |
| Test build, pull_request run 36832187844 | Java 17 and Java 21 success |
| iOS/MobiVM link audit, runs 36832185098 and 36832187847 | success |
| Local full `forge.bridge` suite (`mvn -o -pl forge-protocol2-bridge -am test`) | 356 run, 0 failures, 0 errors, 0 skipped |

## Evidence families

| Family | Disposition |
|---|---|
| Forge rows of the R-5 epoch `4cad91897216-a43e80d96595` (FULL107, AF00–AF11, hidden information, RNG/replay, cardinality, actual-card) | **HISTORICAL_ONLY**: bound to bridge `e8b8aec6` and not relabelled. |
| FULL107 and AF rows with multi-part costs (cost order now asked) | **REQUIRES_REQUALIFICATION**. The Lab driver answers with the declared `native_declared_cost_part_order` policy (#443), which selects only an engine-offered option by native index. |
| Rows that previously reached a silent default (Assist, multi-category decline, unrepresented cost shapes) | **REQUIRES_REQUALIFICATION**. A former pass through a default may now be an explicit fail-closed result. That outcome is honest and is not a regression. |
| Every other current-boundary Forge row | **REQUIRES_REQUALIFICATION** through the successor PB-03 epoch, like every row at a new source identity. |
| WSR20/WSR22 Forge evidence (`ef958ee9` lineage) | **HISTORICAL_ONLY**, unchanged. |

**INVALIDATED:** none.

**UNKNOWN:** the current Forge FULL107 standing at the new bridge source, until the successor epoch exists.
