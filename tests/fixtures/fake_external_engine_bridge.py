#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone

PROTOCOL = "2.0.0"
for raw in sys.stdin:
    req = json.loads(raw)
    rid = req.get("request_id", "unknown")
    method = req.get("message_type") or req.get("method")
    payload = {}
    success = True
    errors = []
    if req.get("protocol_version") != PROTOCOL:
        success = False
        errors = [{"code":"protocol_version_mismatch","message":"bad version","retryable":False,"details":{}}]
    elif method == "engine_hello":
        payload = {"engine":"xmage","engine_version":"fixture-not-real","validation_level":"external_rules_engine"}
    elif method in {"engine_capabilities", "get_capabilities"}:
        payload = {"capabilities": {
          "commander_supported":True,"partner_supported":True,"multiplayer_supported":True,
          "max_players":4,"headless_supported":True,"seed_supported":True,
          "deck_import_supported":True,"legal_actions_supported":True,
          "action_submission_supported":True,"event_log_supported":True,
          "replay_supported":True,"stack_visible":True,"priority_visible":True,
          "commander_damage_visible":True,"commander_tax_visible":True,
          "starting_state_injection_supported":True,"scenario_injection_supported":True,
          "healthcheck_supported":True,"target_selection_supported":True,
          "mode_selection_supported":True,"trigger_order_supported":True,
          "mulligan_supported":True,"concede_supported":True,
          "game_shutdown_supported":True,"engine_shutdown_supported":True,
          "runtime_kind":"external_rules_engine","notes":["test fixture"]
        }}
    elif method in {"shutdown_game", "shutdown_engine"}:
        payload = {"shutdown":True}
    else:
        success = False
        errors = [{"code":"unsupported_message","message":str(method),"retryable":False,"details":{}}]
    out = {
      "protocol_version":PROTOCOL,"request_id":rid,
      "timestamp":datetime.now(timezone.utc).isoformat(),"success":success,
      "status":"ok" if success else "error","payload":payload,"warnings":[],
      "errors":errors,"engine_event_offset":0
    }
    print(json.dumps(out), flush=True)
    if method in {"shutdown_game", "shutdown_engine"}: break
