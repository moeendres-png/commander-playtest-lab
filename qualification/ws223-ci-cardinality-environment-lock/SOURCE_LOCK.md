# WS223 Source Lock

*Workstream WS223 — Cardinality CI & Reproducible Environment Hardening.
Writer session on branch `ws223/ci-cardinality-environment-lock-20260915`.*

| Field | Value |
|---|---|
| Repository | `moeendres-png/commander-playtest-lab` |
| Branch | `ws223/ci-cardinality-environment-lock-20260915` |
| Audit base (terminal published WS218) | `3cdade1dfb16c820465690680b0b0be8af7007ef` |
| Audit base TREE | `0a249bf45fc1bba4871b92896c31a45ff9b99436` |
| Read-only design input WS220 | `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b` |
| WS220 TREE | `6bc707b37f8fb39950f4ade2db11e7ccef03dab6` |
| XMage production authority (inherited WS218/WS215) | `db134b9737e951367d65ef5806ad986319cc73ab` |
| `ARCHITECTURE_FREEZE` | `NOT_CLAIMED` |
| `PRODUCTION_PROVIDER` | `NOT_SELECTED` |

## Inherited terminal authority (do not requalify)

- WS215: `PLAYER_COUNT_2P/3P/4P/5P = PASS`, `PLAYER_COUNT_6P = NOT_SUPPORTED`.
- WS218: `SEMANTIC_REPLAY_STATUS = PASS`, `REPLAY_2P/3P/4P/5P = PASS`.
- WS223 prevents silent regression of the above and makes future evidence
  environmentally reproducible. It does not re-litigate 2–5P correctness or
  replay semantics.

## Owned WS220 inputs (only these; no unrelated findings absorbed)

- `S5 / F-CI-03`: living conformance path is 4P-shaped
  (`scripts/run_external_full_game_conformance.py` hardcodes `player_count=4`
  + `range(1, 5)`; `xmage-full-game-conformance.yml` has zero 2P/3P/5P steps
  and no trigger on `test_xmage_variable_player.py`).
- `S15 / F-CI-01`: environment version-recorded but not locked (ranges
  everywhere; 6-pin non-transitive `requirements/runtime.lock`; floating
  `eclipse-temurin:21`; JDK17-vs-21 skew; 12/16 lanes lack `PYTHONHASHSEED`;
  pip cache keys ignore lock identity).

## Mutation surface (this workstream only)

`scripts/run_external_full_game_conformance.py`,
`.github/workflows/xmage-full-game-conformance.yml`,
`src/commander_lab/engine/rules/full_game.py` (additive smoke entrypoint only),
`requirements/` (transitive hash-pinned lock), `docker/*/Dockerfile`
(digest pin only), deterministic-lane workflow `env` (hashseed),
workflow cache keys (lock binding), `scripts/write_environment_receipt.py`
(new), `tests/unit/test_ws223_*` (new regression/static gates),
`qualification/ws223-ci-cardinality-environment-lock/` (evidence namespace).

## Out of scope

Rules/pilot legality, numeric domain (S6), hidden-info honeycards (S7),
evidence vocabulary (WS221), G01 authority (WS222), replay redesign,
FULL107, Architecture Freeze, Production Provider selection.

## Sibling ownership

WS221 (evidence vocabulary / manifest integrity / source truth) and WS222
(G01 authority acquisition) own their qualification evidence/manifests/docs.
WS223 creates only its own namespace and never edits sibling-owned artifacts.
