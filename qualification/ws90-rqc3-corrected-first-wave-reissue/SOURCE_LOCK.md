# WS90 Source Lock — RQ-C3 Corrected First-Wave Reissue + XMage Harness Impact Audit

Repository: `moeendres-png/commander-playtest-lab`

Branch: `ws90/rqc3-corrected-first-wave-reissue-20260913`

Audit base / current CPL main at issuance: `8fe9a3eacd3c3a54ba07f2de034a3bd740fbec73`

This main already contains merged WS88 and therefore the current integrated XMage candidate: `cfc36f445f917f101fa2ed588770e043f53bc44c`

Historical RQ-C3 authority terminal: `897d72f0b57bb8febe045870acaa3d2dba4bde56`

Historical First-Wave execution-pack blob: `0db015ffee9dfcaabd2338da92c711d865059d81`

Historical First-Wave decision-requirements blob: `3707d8965e27ff823bea02b81b80ab13be396ed4`

Historical H01 scenario blob: `c4e742526670a2fdf86b0fcb9c048d8d584646c0`

Historical WS60 terminal: `731891ec5ed8e7611fc9a636bab5fc3c400108eb`

Historical WS60 frozen execution head: `2c30040f82e4c97b308535a592f4facd1e5ec42e`

Historical WS60 XMage engine: `7135d5e85ddb4c8aa4b49b4192ca51947c822704`

Current integrated XMage engine: `cfc36f445f917f101fa2ed588770e043f53bc44c`

Forge Rules-Core authority (future input): `aa5c00aa32dfd40e213f223f8fd400c43daabb24`

Forge bridge source successor: `<accepted future WS89 technical successor>` (not invented here; WAITING_FOR_WS89)

`config/rules_engines.json` is the sole machine-readable pin authority. Human-readable pins elsewhere cite it.

Historical authority objects are immutable provenance. Reads via `git show <terminal>:<path>` only. No historical file modified in WS90.

Operational WS90 state is external at `FOUNDRY_STATE_PATH`. `.foundry/WORKSTREAM_STATE.yaml` in-tree is not the WS90 state file and was not modified.

Scope: authority/harness preparation only. `CANDIDATE_BEHAVIOR=NOT_RUN`. No production engine/bridge edits. No Full107. No ranking restoration. `ARCHITECTURE_FREEZE=NOT_CLAIMED`. `PRODUCTION_PROVIDER=NOT_SELECTED`.
