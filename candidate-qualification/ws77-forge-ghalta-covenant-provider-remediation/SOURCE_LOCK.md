# WS77 Source Lock

Binding sources (verified, read-only where applicable):

- CPL audit base: `5cc646a08397c6a3d40fbe9da92e7b1e426eb8ec`
  (tree `3a7d549757dfc913d8eaaaae94efc1dedae3e2c8`), branch
  `ws77/forge-ghalta-covenant-provider-remediation-20260912`.
- Accepted Forge pin: `a9a95db6662c2d28814390a9c0c2f986e39aa8b4`
  (tree `2c18327f79e330f2ed167067166ffd42d61b0849`).
- Forge checkout consumed: `/home/moeen/ws77-forge-src-a9a95db`
  (verified HEAD/tree/clean-identical to the accepted pin; read-only except
  ignored `target/` build output from the required fresh `mvn -o` compile;
  no source edits — `git status` clean on tracked files).
- WS68 source lineage: `ws68/forge-provider-transport-remediation-20260912`
  (expected audit base `5cc646a08397c6a3d40fbe9da92e7b1e426eb8ec`).
- WS67 engine causality (read-only):
  `/tmp/ws77-ws67-authority-20260912/ws67-ws65-engine-remediation-evidence/`
  (`GHALTA_CAUSALITY.md`, `COVENANT_X_CAUSALITY.md` — engine-direct PASS,
  no Forge fix required; WS77 owns provider/harness transport only).
- Materialization: `/tmp/ws62-material.json` (WS47 v1.0.5, immutable).
- Dependency classpath: `/home/moeen/.ws48-r1e/ev` (`dependency-classpath.txt`;
  old pin absent).
- Provider EV dir (WS77-owned build): `/home/moeen/ws77-ev`
  (digests in `BUILD_RECEIPT.json`).

Ownership: WS77 writes only under
`candidate-qualification/ws77-forge-ghalta-covenant-provider-remediation/`.
Untouched: Forge source, `tools/foundry`, shared provider production source,
WS68/WS67/WS74/WS75/WS-A1D-H4F files, other workstreams' `/tmp` data.
