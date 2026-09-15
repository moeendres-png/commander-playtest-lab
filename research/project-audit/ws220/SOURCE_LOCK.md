# WS220 Source Lock

- repository: `moeendres-png/commander-playtest-lab`
- branch: `ws220/autonomous-project-coherence-audit-20260915`
- audit base (HEAD at lock): `67db073367853da7295ae06642f38a73db464dba`
- audit base tree: `a41ad3959caee03db59ffa15bdd44413d58ca766`
- audit base identity: exact published WS215
  (`67db0733` "WS215: ignore ephemeral XMage card-DB bootstrap (local JVM runtime cache)").
- working tree at orientation: clean (`git status` clean, verified 2026-09-15).

## Read-only Forge reference (declared, never mutated)

- label: `ws217-forge-authoritative-divided-allocation`
- root: `/home/moeen/code/ws217-forge-authoritative-divided-allocation`
- commit: `e152688a33bf69a840b74ae86149d881e64538ec`
- tree: `b51387a5d195476b02ec5c319fd7f538b3a7ee70`
- Forge Rules/controller authority commit (historical note):
  `c4d67145a6f9902e031a11dde5c33c60f51ed08d`
  (tree `09585e30d6caf974a00742dbb41737704561d934`).

## Terminal invariants (unchanged by WS220)

- `ARCHITECTURE_FREEZE = NOT_CLAIMED`
- `PRODUCTION_PROVIDER = NOT_SELECTED`

## Parallel-work discipline

- WS218 owns Semantic Replay implementation/production replay surfaces.
- WS219 owns Quorune + Argentum freshness qualification.
- WS220 does not duplicate that scope and treats no uncommitted/in-flight
  output from those sessions as authority.
- If WS218/WS219 publish remotely mid-run: record as `POST_LOCK_DRIFT`,
  do NOT move this source lock; leave impact adjudication to the Coordinator.

## Mutation ownership

- WS220 may modify ONLY `research/project-audit/ws220/**` plus the external
  Foundry workstream state via canonical tooling.
- Everything else (src, engine-bridge, tests, qualification, config,
  manifests, contracts, pins, tooling, workflows, history, Forge) is
  read-only. Findings there become successor recommendations, never edits.
