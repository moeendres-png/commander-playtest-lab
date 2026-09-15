# WS224 SOURCE_LOCK

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws224/hidden-info-name-canary-20260915`
- Audit base (WS218 terminal): `3cdade1dfb16c820465690680b0b0be8af7007ef`
- Audit base tree: `0a249bf45fc1bba4871b92896c31a45ff9b99436`
- Read-only WS220 audit: `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b`
  (consumed via `git show` object identity; no sibling-worktree access)
- Pinned engine (unchanged): XMage `db134b9737e951367d65ef5806ad986319cc73ab`
  (`1.4.61`), bridge `xmage-engine-bridge-0.1.0-SNAPSHOT`
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`
- `PRODUCTION_PROVIDER = NOT_SELECTED`

Production files unchanged: no `src/**`, no `engine-bridge/src/main/**`, no
deck, manifest, protocol, or historical-evidence writes. Mutation surface is
new tests (`engine-bridge/src/test/...NameCanaryTest`,
`tests/unit/test_ws224_name_canary.py`) plus the new evidence namespace
`qualification/ws224-hidden-info-name-canary/**` (evidence + driver only).
