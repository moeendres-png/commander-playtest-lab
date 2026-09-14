# WS205 Source Lock (qualification workstream)

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws205/xmage-ws90-first-wave-qualification-20260914`
- `AUDIT_BASE_SHA`: `5994019b4da59e27a388eec47e6805404bd98df9`
- `AUDIT_BASE_TREE`: `0ccbc2e327515932bcd1f745902e4515b433a6fd`
- Source branch (immutable authority): `ws204/xmage-b4d-action-submission-20260914`
- XMage engine pin: `cfc36f445f917f101fa2ed588770e043f53bc44c` (1.4.61)
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`
- `PRODUCTION_PROVIDER = NOT_SELECTED`

## Sealed WS90 authority (read-only, verified `CODE_DERIVED` via `git hash-object`)

| Blob | SHA |
|---|---|
| `FIRST_WAVE_EXECUTION_PACK_CORRECTED.json` | `5852965e59412399a947c626d4f7d428be8ef337` |
| `FIRST_WAVE_DECISION_REQUIREMENTS_CORRECTED.json` | `1340f8cc244e7d5e8337c3bc321806341fbe2967` |
| `H01_BINDING.json` | `eb0874644083bf6a9e004ebc4eea91dc35522553` |

- `verify.py`: `VALIDATION_PASS` (zero behavior credit, no execution).
- Denominator: exactly 15 slots; H01 is ONE slot (A/B/C family).

## WS205 pilot policy

`ws205-pilot-v1` (versioned qualification-only successor of the sealed WS204
`ExternalPilotDecisionPolicy` semantics): rank/select ONLY among authoritative
offered actions; deterministic; fail closed on unknown classes and on
requested-result filtering. See `METHOD.md`.
