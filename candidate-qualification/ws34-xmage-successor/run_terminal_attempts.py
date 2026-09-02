#!/usr/bin/env python3
"""Terminally attempt every WS-34 runtime-ready record not owned by core-9.

No row receives runtime PASS from this probe.  For records without a dedicated
successor executor it starts a clean provider process, constructs the exact
record, enters native execution, records the first native decision/state, then
fails closed as EXECUTION_ADAPTER_UNSUPPORTED.  CARD_02 additionally attempts
its exact commander cast and explicit priority passes.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent
FC=HERE.parents[0]/"finalist-convergence-xmage"
WS26=HERE.parents[0]/"ws26-xmage"
sys.path[:0]=[str(HERE),str(FC),str(WS26)]
import run_canonical_starter18 as legacy
import run_ws26_gate as gate

CORE={"PLAYER_COUNT_2P","PLAYER_COUNT_3P","PLAYER_COUNT_4P","PLAYER_COUNT_5P","PILOT_MULLIGAN","WS05-CMD-MULL-2","WS05-CMD-MULL-4","PILOT_PRIORITY","PILOT_TARGET"}
READY={"PILOT_TARGET_AMOUNT","PILOT_CHOOSE_USE","PILOT_ANNOUNCE_X","PILOT_MULTI_AMOUNT","PILOT_CHOOSE_MODE","NEGATIVE_FIRST_OPTION","NEGATIVE_RANDOM_OPTION","NEGATIVE_GUI_DEFAULT","NEGATIVE_SILENT_SKIP","RNG_RULES_TAPE","REPLAY_DECISION_TAPE","REPLAY_EVENT_TAPE","REPLAY_CLEAN_PROCESS","REPLAY_STATE_HASHES","MICRO_TARGETS","MICRO_MODES","MICRO_TRIGGERS","MICRO_CONTINUOUS_EFFECTS","MICRO_LAYERS","MICRO_STATE_BASED_ACTIONS","CARD_02","WS05-MP-TRIG-3","WS05-MP-TRIG-5"}
SCHEMA="xmage-qualification-scenario/1.1.0"

def meta(option:dict[str,Any])->dict[str,Any]:
    x=option.get("metadata"); return x if isinstance(x,dict) else {}

def unique(decision:dict[str,Any], pred, label:str)->dict[str,Any]:
    m=[o for o in decision.get("legal_options",[]) if pred(o)]
    if len(m)!=1: raise RuntimeError(f"SEMANTIC_OPTION_MATCH_NOT_UNIQUE:{label}:matches={len(m)}")
    return m[0]

def p1_has_rograkh(obs:dict[str,Any])->bool:
    for p in obs.get("players",[]):
        seat=p.get("seat")
        if seat not in (0,1): continue
        for c in p.get("battlefield") or []:
            if c.get("name")=="Rograkh, Son of Rohgahh": return True
        if seat==0: return False
    return False

def attempt(record:dict[str,Any])->dict[str,Any]:
    row={"fixture_id":record["fixture_id"],"record_digest":record["materialization_digest"],"requested_state_digest":record["requested_state_digest"],"runtime_credit":"WITHHELD","status":"FAIL_CLOSED"}
    try:
        decks,scenario=legacy.deck_and_scenario(record,SCHEMA)
        with gate._RawFullGameClient(gate.command(),request_timeout_seconds=90.0) as client:
            client.request("start_engine")
            handles=gate.import_decks(client,decks)
            client.request("create_full_game",{"game_id":f"WS34-ATTEMPT-{record['fixture_id']}","deck_handles":handles,"starting_player_seat":0,"starting_life":40,"seed":record["rules_randomness"]["rules_seed"]})
            configured=client.request("configure_qualification_scenario",{"scenario":scenario})
            row["configured_entry_mode"]=configured.get("execution_entry_mode")
            client.request("start_full_game")
            decision=client.request("get_full_game_decision").get("decision")
            state=client.request("get_qualification_state")
            row["native_execution_entered"]=True
            row["first_decision_class"]=decision.get("decision_class") if isinstance(decision,dict) else None
            row["rules_rng_operation_count"]=(state.get("rules_rng_tape") or {}).get("operation_count")
            if record["fixture_id"]!="CARD_02":
                row["terminal_reason"]="EXECUTION_ADAPTER_UNSUPPORTED_FOR_V1_0_2_CANONICAL_TRANSACTION"
                return row
            row["card02_cast_attempted"]=True
            if not isinstance(decision,dict) or decision.get("decision_class")!="priority":
                raise RuntimeError("CARD02_EXPECTED_P1_PRIORITY")
            cast=unique(decision,lambda o:o.get("option_type")=="activated_ability" and meta(o).get("source_name")=="Rograkh, Son of Rohgahh","cast_commander")
            gate.submit_one(client,decision,[str(cast["option_id"])])
            row["card02_cast_option_submitted"]=True
            for _ in range(32):
                obs=client.request("get_full_game_observation",{"viewer_seat":0,"decision_subject_seat":0})["observation"]
                if p1_has_rograkh(obs):
                    row["card02_behavior_result"]="PASS_R0_COMMANDER_RESOLVED_TO_BATTLEFIELD"
                    row["terminal_reason"]="BEHAVIOR_PASS_BUT_SUCCESSOR_FULL_CONSTRUCTION_PROOF_NOT_INDEPENDENTLY_NATIVE"
                    return row
                d=client.request("get_full_game_decision").get("decision")
                if not isinstance(d,dict): raise RuntimeError("CARD02_NO_PENDING_DECISION_BEFORE_RESOLUTION")
                if d.get("decision_class")!="priority": raise RuntimeError("CARD02_UNSCRIPTED_DECISION:"+str(d.get("decision_class")))
                ps=unique(d,lambda o:o.get("option_type")=="pass_priority","explicit_priority_pass")
                gate.submit_one(client,d,[str(ps["option_id"])])
            raise RuntimeError("CARD02_RESOLUTION_TIMEOUT")
    except Exception as exc:
        row["terminal_reason"]="RUNTIME_ATTEMPT_FAILED_CLOSED"
        row["error_type"]=type(exc).__name__
        row["error"]=str(exc)
        return row

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--contract",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    c=json.loads(a.contract.read_text()); by={r["fixture_id"]:r for r in c["records"]}
    missing=READY-set(by); assert not missing,missing
    rows=[attempt(by[x]) for x in sorted(READY)]
    out={"schema_version":"commander-lab.ws34-terminal-attempts/1.0.0","candidate_commit":os.environ.get("GITHUB_SHA","LOCAL"),"record_count":len(rows),"records":rows}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"terminal_attempts":len(rows),"card02":next(r for r in rows if r["fixture_id"]=="CARD_02")["terminal_reason"]},sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
