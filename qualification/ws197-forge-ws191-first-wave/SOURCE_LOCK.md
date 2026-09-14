# WS197 Source Lock — Forge WS191 Promotion + WS90 RQC3 First-Wave Runtime

Repository: `moeendres-png/commander-playtest-lab`

Branch: `ws197/forge-ws191-promotion-ws90-first-wave-20260914`

Audit base (Commander-Lab): `7725570b6b8690daed6e645dc1611f5e196de8c5`
Audit base tree: `8b926c73cf35468c6110d64615c5f5e863ac2aa1`

Phase A commit (promotion + harness repair): `edad66c83f2c83e67afb3e35b2d91c50af13c128`
Runtime executed against Phase A tree (see `WS197_SUMMARY.json` bindings).

Forge Rules-Core authority (production): `aa5c00aa32dfd40e213f223f8fd400c43daabb24`
Forge Rules-Core tree: `8aed9d8754a4b3bedfc57d2a2b47d997bcff4dec`
Forge bridge/materialization source: `7360737b7f1f3580eb51b7aca49bd1c0e72d9bff`
Forge bridge tree: `378cec5d90d847aeb38d69165f7eff97a0c4d146`
Bridge source Rules-Core base: `aa5c00aa32dfd40e213f223f8fd400c43daabb24`
Ancestry: `aa5c -> 77cca347908 (WS191 bridge port) -> 7360737b7f1 (WS191 identity fixture)`; delta 35 files, 8446 insertions, bridge-only additive (`forge-protocol2-bridge/` + root `pom.xml` module entry). Zero production Rules change.

Reference root (read-only): `/home/moeen/code/ws191-forge-aa5c-h4f` (`ws191-forge-qualified-candidate`, remotely published `origin/ws191/forge-aa5c-h4f-integration-20260914`).

XMage identity unchanged: `cfc36f445f917f101fa2ed588770e043f53bc44c`.

WS90 authority package (sealed, unmutated): `qualification/ws90-rqc3-corrected-first-wave-reissue/` (denominator 15, H01 one-slot family, 20-kind decision union). Validator `verify.py` (stdlib only).

WS196 (`691dbe504b8626a7e6e7a59cf994cc43777a8abf`) branches from this audit base but is NOT merged here; provenance only.

`ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`. `FULL107 = NOT_RUN`.
