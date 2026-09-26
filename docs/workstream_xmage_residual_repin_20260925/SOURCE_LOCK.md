# XMage Residual Re-Pin / Lab Integration — Source Lock

## Workstream

Commander Simulator Next — residual Mage candidate re-pin, Lab integration and targeted requalification.

Branch: `sol/xmage-residual-repin-integration-20260925`

WORKTREE = NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

## Commander Lab source

- Repository: `moeendres-png/commander-playtest-lab`
- Base: `548167fa25b8345621d4638d7c140449fa73ac31`
- Base branch: `main`
- Base state: current main after DR-CLOSURE-01 merge.
- This workstream does not mutate `main` directly.

## Mage source

- Previous authoritative Lab pin: `db134b9737e951367d65ef5806ad986319cc73ab`
- Cumulative Mage residual candidate: `b19596980f2734496ea1896504253e1bdd2756dd`
- Candidate lineage: RG-02 -> RG-07 -> RG-08 -> RG-06A.
- The candidate is a direct descendant of the prior authoritative pin.
- Mage residual candidate was runtime-qualified before this Lab re-pin; this Lab workstream does not treat that as a substitute for Lab/bridge requalification.

## Authority

`config/rules_engines.json -> primary_engine.commit` is the sole machine-readable current XMage pin authority.

Sealed historical evidence bound to `db134b9737e951367d65ef5806ad986319cc73ab` remains historical and MUST NOT be rewritten to the new pin. In particular, WS218 semantic replay tapes, WS232 retention artifacts and prior workstream source locks/handoffs retain their original source identities.

ARCHITECTURE_FREEZE = NOT CLAIMED

PRODUCTION_PROVIDER = NOT SELECTED
