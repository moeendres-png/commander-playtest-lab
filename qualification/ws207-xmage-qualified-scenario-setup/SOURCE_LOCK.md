# WS207 Source Lock (qualification workstream)

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws207/xmage-qualified-scenario-setup-20260914`
- `AUDIT_BASE_SHA`: `1dee8b77f7243900eec5a7cc05fb1fe26467aea9`
- `AUDIT_BASE_TREE`: `af564c38691f0a03f561c1df43506197edea016c`
- Live HEAD at seal: `1dee8b77f7243900eec5a7cc05fb1fe26467aea9` (tree identical)
- Source branch (read-only authority): `ws205/xmage-ws90-first-wave-qualification-20260914`
- XMage engine pin: `cfc36f445f917f101fa2ed588770e043f53bc44c` (unchanged, no repin)
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`
- `PRODUCTION_PROVIDER = NOT_SELECTED`

## Sealed WS90 authority (read-only, verified `CODE_DERIVED` via `git hash-object`)

| Blob | SHA |
|---|---|
| `FIRST_WAVE_EXECUTION_PACK_CORRECTED.json` | `5852965e59412399a947c626d4f7d428be8ef337` |
| `FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json` | `1340f8cc244e7d5e8337c3bc321806341fbe2967` |
| `H01_BINDING.json` | `eb0874644083bf6a9e004ebc4eea91dc35522553` |

`verify.py` (WS90): untouched. Denominator: exactly 15 slots; H01 is ONE slot.

## WS207 setup policy

`ws207-setup-v1` (qualification-only setup-state machine): wish-match setup
permanents among authoritative offered options only; engine-offered keep for
mulligans; configured starting-seat selection; land play; pass/hold otherwise;
behavior cards never wished (held); fail closed on unknown classes. Explicit
per-game Rules-seed binding before `game.start/init` on every run.

## Mutation surface (verified clean at seal)

`git status`: only `qualification/ws207-xmage-qualified-scenario-setup/` plus the
two resealed WS17 hash manifests. No production, engine, WS205/WS90, or config
mutation. `db/` engine caches (worktree + `/tmp/ws207-scan-w*`) untracked, never
committed.
