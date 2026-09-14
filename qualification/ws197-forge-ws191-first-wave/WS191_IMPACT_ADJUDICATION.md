# WS197 WS191 Impact Adjudication

Tier: XHIGH technical adjudication (read-only `foundry-adjudicator` initial + implementer-owned continuation). No Authority Gate.

## WS191 delta vs aa5c (DIRECTLY_VERIFIED)

- Range `aa5c00aa..7360737b7f1`: exactly 2 commits (`77cca347908` bridge port, `7360737b7f1` identity-fixture binding).
- `diff --stat`: 35 files changed, 8446 insertions(+), 0 deletions meaningful (1-line root `pom.xml` module entry + 34 paths under `forge-protocol2-bridge/`).
- Semantic classes: bridge-only additive. No `forge-game/`, `forge-ai/`, `forge-gui/`, card, replacement, layer, or cost edits. `7360737b7f1` alone touches only `BridgeProtocolProcessTest.java` (4+/1- fixture binding).
- Dockerfile guard (`^(forge-protocol2-bridge/|pom\.xml$)`) satisfied by construction.

## Dual-identity promotion (minimum coherent)

- `secondary_engine.commit`: `a37a865a…` → `aa5c00aa…` (Rules-Core authority; never the bridge commit).
- `secondary_engine.repository`: `Card-Forge/forge.git` → `moeendres-png/forge.git` (aa5c is fork-only: WS40/WS45/WS59/WS76 remediation commits between a37a and aa5c exist only in the fork; Card-Forge cannot resolve aa5c).
- `secondary_engine.source_archive`: Card-Forge/a37a tarball → fork/aa5c tarball (mechanical, WS88 xmage pattern: commit plus archive together).
- `secondary_engine.bridge_source`: repo retained `moeendres-png/forge.git`; commit `4753bb7c…` → `7360737b…`; base `a37a865a…` → `aa5c00aa…` (resolver cross-wire guard `base == commit != bridge` holds).
- Unchanged by design (no invented metadata): `release forge-2.0.14` (bridge `VersionInfo.RELEASE` still 2.0.14; `test_phase85_bootstrap_files` expects 2.0.14; pom `2.0.15-SNAPSHOT` is build revision, not manifest release), `status PARTIAL`, `role`, `license GPL-3.0`, `production_ready false`, `provider_decision NO_PROVIDER_READY`, `current_runtime.provider_selected false`, `production_provider null`.
- Coherent consumers moved: `bootstrap_engine_linux.sh` / `bootstrap_engine_windows.ps1` forge defaults; `test_forge_bridge_h4f_live.FORGE_RULES_COMMIT`; `test_ws_a1d` canonical Forge + bridge commits; `test_ws_a1r` / `test_ws_arclose` pin assertions.
- Harness repair (Commander-Lab-owned, no Rules semantics): `test_forge_bridge_h4f_live` classpath derivation added `-am` (standalone `-pl` fails on `2.0.15-SNAPSHOT` `${revision}` sibling resolution; `-am` keeps the reactor; matches build invocation and reference `mvn -pl -am test`).

## Historical evidence impact

- `root_cause_class = UNKNOWN` (no WS197 runtime failure to classify).
- WS90 corrected authority: SURVIVES intact (semantic gates all PASS; see `WS90_INTEGRITY.md`). No auto-import of behavior credit (`behavior_credit_imported 0` preserved; `FORGE_RQC3_FIRST_WAVE` now freshly `0/15/0/0` BLOCKED, not NOT_RUN).
- WS65 `9/15` (superseded oracle): does NOT transfer; `REQUALIFICATION_REQUIRED` stands, now evidenced as 15x BLOCKED on the bounded H4F surface.
- WS60 rows: `ws60_production_edits_imported 0`; techniques reusable as patterns only.
- XMage `cfc36f` B4-D chain: UNAFFECTED (separate provider, direct-source path).
- Stock Forge `DIRECT_PILOT_BOUNDARY_FAIL`: never credit; H4F is the only compliant path.
- `validation_corpus`: `verify.py` + `test_ws_a1d` (50) + pin/authority/materialization/phase85 unit (43) + live H4F bounded proof (1) + WS197 15-slot harness (15 live transcripts).
- `GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN` (blocked until a future surface executes the First Wave with PASS + twin replay).
