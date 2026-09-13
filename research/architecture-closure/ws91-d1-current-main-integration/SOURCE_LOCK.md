# WS91 — D1 Current-Main Integration: Source Lock

Repository: `moeendres-png/commander-playtest-lab`

Workstream branch: `ws91/d1-current-main-integration-20260913`

## Current-main audit base (canonical, authoritative for WS78/WS88/WS90)

- `CURRENT_MAIN_BASE = 4f69aa36405957a97f538ea55145740bf127ec34`
- Tree: `7335e0b6b23f88001afead676d45e36697be753c`
- Verified: `git rev-parse HEAD` == audit base; `git status` clean at entry.
- Includes: WS78 token-economy tooling, WS88 XMage integrated successor,
  WS90 corrected RQ-C3 First-Wave authority.

## D1 source (historical, pre-WS78/WS88/WS90 line)

- Original D1 base: `f89c824e93664b8285b0b44e4445118bd99b9f98`
- Validated technical head: `D1_VALIDATED_SOURCE = 8d0f68494b54be9405f6372543cc721788cbdd88`
- Tree: `09e52ea1ac603ccd5fdaa3bd0c849dec1ad0fc60`
- Terminal seal: `cf7b21c747018fba2b68d7166d0b37f7df037393`
- Verified: `cf7b21c` differs from `8d0f6849` ONLY in
  `research/architecture-closure/ws-arclose-d1-current-authority-drift/WORKSTREAM_STATE.yaml`
  (state-only seal). `D1_TECHNICAL_AUTHORITY = 8d0f6849`.
- Local D1 branch `ws-arclose/d1-current-authority-drift-20260913` currently at
  `bcd579b0` (post-D1 WS88-merge + seals); implementation credit stays at `8d0f6849`.

## Current-main authority under preservation

- `config/rules_engines.json` blob at audit base: `6471495eaeabbe361b49ec1d80afaf5e52cd0574`
- `CURRENT_XMAGE_PIN = cfc36f445f917f101fa2ed588770e043f53bc44c`
- `provider_selected = false`, `production_provider = null`,
  `provider_decision = NO_PROVIDER_READY`
- Supersession boundary (byte-identical at terminal):
  `config/rules_engines.json`, `qualification/ws79-h01-authority-remediation/**`,
  `qualification/ws88-xmage-integrated-successor-promotion/**`,
  `qualification/ws90-rqc3-corrected-first-wave-reissue/**`,
  `qualification/SHA256SUMS`, `WS17_SHA256SUMS`
- Root operational state at audit base: `.foundry/WORKSTREAM_STATE.yaml`
  blob `6cf09d17cc141215efc8d1c06c5c0845b5f201ef` (historical WS-A1D-H4 bytes).

## Method

No merge / rebase / cherry-pick of the D1 branch. Semantic path/hunk
integration only. `config/rules_engines.json` is never copied from D1
(`CONFIG_RULES_ENGINES_BLOB_CHANGED = 0`).
