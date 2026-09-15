# WS226 SOURCE_LOCK — Consolidated Commander-Lab Authority Integration

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws226/consolidated-cpl-authority-integration-20260915`
- Audit base / production lineage (WS223 terminal, preserved exactly):
  - Commit: `48885e8e3c16ccdfd388a4378a5a05b6e81bb293`
  - Tree: `d02d6c0eb54b009c481cd79d642929011e9ce483`
  - Contains: WS218 semantic replay + S5 cardinality CI + S15 environment lock
- Read-only published integration sources (exact Git-object transfer only):
  - WS225 (standing/governance, ancestry WS220+WS221):
    - Commit: `8b3ab80d07317f54debf913974eea91947ac0848`
    - Tree: `e848fe95cec9ff9150ed6d0d11758490ee3e5624`
  - WS221 (foundation hardening, WS225 parent):
    - Commit: `189dcfc09e74bebbf22172e709b459428b25d583`
    - Tree: `4bb67f8c7412b20def4d2c16bc86d5c51426dd62`
  - WS222 (G01 authority re-acquisition):
    - Commit: `1dcfe898033865f52dd959f087635fad8541eecd`
    - Tree: `1f5382b17c623c532e266945a65f85e6807bc7cf`
  - WS224 (hidden-info name canary):
    - Commit: `f075ab7552567adae4d17bca3b8635a7387bc371`
    - Tree: `106a93cb658ec34c57c0f12469fae952d1c8ad13`
  - WS220 synthesis (via WS221/WS222 ancestry, preserved as provenance):
    - Commit: `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b`
- Divergence anchor (common ancestor of all four lines):
  - Commit: `67db0733` (WS215 ephemeral-cache ignore)
- XMage engine authority (unchanged pin): `db134b9737e951367d65ef5806ad986319cc73ab`
- Policy: `ARCHITECTURE_FREEZE = NOT_CLAIMED`, `PRODUCTION_PROVIDER = NOT_SELECTED`
- Rules/pilot behavior change authorized: NONE (`GLOBAL_BEHAVIOR_CREDIT_CHANGE = 0`)
- Method: semantics integration via exact Git-object/path/hunk transfer.
  No `merge`, no `rebase`, no `reset --hard`, no `clean`, no wholesale
  checkout, no blind cherry-pick of stale manifests. Living overlapping
  source reconciled semantically against the WS223 base; namespaced
  immutable evidence preserved blob-exact.
