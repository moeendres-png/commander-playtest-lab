# WS218 SOURCE_LOCK

Repository: `moeendres-png/commander-playtest-lab`
Branch: `ws218/semantic-replay-tape-v1-20260915`
Audit base: `67db073367853da7295ae06642f38a73db464dba` (tree `a41ad3959caee03db59ffa15bdd44413d58ca766`)
XMage production authority: `db134b9737e951367d65ef5806ad986319cc73ab` (engine 1.4.61)
Forge divided core (read-only reference): `c4d67145a6f9902e031a11dde5c33c60f51ed08d`
WS217 reference: `e152688a33bf69a840b74ae86149d881e64538ec` (replay NOT CLAIMED)
`ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

Tape source_lock binds: lab repository/commit/tree, provider `xmage`,
engine repository/commit/version (`1.4.61`), adapter
`xmage-engine-bridge full-game lane`, transport protocol `2.0.0`,
decision protocol `xmage-external-decision-protocol-1.0.0`, protocol schema
digest (SHA-256 over `schemas/engine_adapter_protocol.schema.json` +
`schemas/engine_protocol/*`), rules authority `xmage`, oracle snapshot
`xmage-<commit>:card-db-live`, commander authority `xmage-commander-ffa`.
Engine tree is None in this lane (live observer cannot hash the external
Maven artifact; recorded None==observed None; any recorded value must match).

Domain lock binds: deck content digests (`deck_content_digest` over
deck_id + sorted commanders + sorted mainboard), player count, seat map,
commander identities, starting life 40, starting contract
(`seed_mod_N chooser + native CR103.2 choice`), mulligan contract (London
free-first), rules seed, pilot derivation, process isolation
(one_game_per_process fresh JVM).

Enforcement: `verify_source_lock` + manifest content recomputation occur
BEFORE any game execution in the consumer; any material mismatch raises
`SOURCE_LOCK_MISMATCH`/`DOMAIN_LOCK_MISMATCH` without touching engine
state. `TAMPER_SOURCE/PROTOCOL/DECK/COUNT/SEED` prove refuse-before-execution.

Machine companion: tapes carry the lock; `runs/WS218_RUN_SUMMARY.json` seals it.
