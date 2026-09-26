# Rules-engine JSONL bridge protocol

Phase 8 uses a persistent subprocess bridge instead of GUI automation. The Python process starts an XMage or Forge bridge command and communicates over standard input and output with one JSON object per line.

## Authority boundary

The external engine owns tactical state. The Python layer may:

1. load a deck;
2. request a Commander game or injected scenario;
3. read a normalized immutable state;
4. request legal actions;
5. submit one `ActionProposal` matching an engine-offered action;
6. read logs and a normalized result.

The Python agent cannot write life totals, zones, the stack, mana, or winners directly.

## Environment variables

```bash
export COMMANDER_LAB_XMAGE_BRIDGE_CMD='java -jar xmage-commander-lab-bridge.jar'
export COMMANDER_LAB_FORGE_BRIDGE_CMD='java -jar forge-commander-lab-bridge.jar'
```

The bridge command is parsed as an argument vector. Do not include shell redirection.

## Request envelope

```json
{
  "request_id": "uuid",
  "method": "get_legal_actions",
  "params": {"session_id": "session-1"}
}
```

## Response envelope

```json
{
  "request_id": "uuid",
  "ok": true,
  "result": {"actions": []}
}
```

Errors use:

```json
{
  "request_id": "uuid",
  "ok": false,
  "error": {"code": "illegal_action", "message": "..."}
}
```

## Required methods

| Method | Purpose |
|---|---|
| `probe` | Return backend version and capability flags. |
| `load_deck` | Parse and validate one 100-card Commander deck. |
| `start_commander_game` | Start a multiplayer game from decks and optional seed/starting state. |
| `create_scenario` | Inject a bounded tactical fixture. |
| `get_state` | Return the current normalized `GameState`. |
| `get_legal_actions` | Return engine-authoritative `LegalAction` objects. |
| `submit_action` | Validate and execute one `ActionProposal`. |
| `get_logs` | Return event/game logs. |
| `get_result` | Return the normalized final or scenario result. |
| `shutdown` | Close the bridge process cleanly. |

## Reproducibility

A backend must report separately whether it supports:

- direct seed injection;
- deterministic starting-state injection;
- neither.

A fixed starting state is acceptable for tactical differential tests even when the backend does not expose its random-number seed. The capability must not be overstated.

## Validation labels

- `structural_only`: only the high-volume abstraction covers the card or interaction.
- `tactical_oracle`: the local bounded tactical oracle passed.
- `external_rules_engine`: XMage or Forge returned a matching normalized result.

The local bridge in `scripts/tactical_rules_bridge.py` is a contract test and tactical oracle. It cannot produce `external_rules_engine` evidence.
