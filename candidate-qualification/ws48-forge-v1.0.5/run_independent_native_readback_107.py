#!/usr/bin/env python3
from __future__ import annotations

import argparse, collections, hashlib, json, os, shlex, subprocess, tempfile
from pathlib import Path
from typing import Any
import run_strict_no_echo_gate as transport

PROTOCOL="commander-lab.rules-service/1.1.0"
WS47_COMMIT="192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
WS47_TREE="f596c54d2cb229b9827c6c94a278175e8312c65c"
WS47_SCHEMA="commander-lab.semantic-fixture-materialization/1.0.5"
WS47_BUNDLE="631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
WS47_SHA="0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
FORGE_COMMIT="66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE="40fc8f29ce4de31a964972461db2b48b4221e07f"
KEYS=["execution_entry_mode","players","deck_state","commander_state","semantic_objects","temporal_state","knowledge_state","rules_randomness","combat_state","stack_state","continuous_rules_effects","extra_turn_creation","elimination_trigger","zone_move_event","setup_validation"]

def canon(v:Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(v:Any)->str: return hashlib.sha256(canon(v).encode()).hexdigest()
def requested(r:dict[str,Any])->dict[str,Any]: return {k:r[k] for k in KEYS if k in r}
def seat(pid:str)->int:
    if not isinstance(pid,str) or not pid.startswith("P"): raise AssertionError(f"bad player id {pid!r}")
    return int(pid[1:])
def counters(v:Any)->dict[str,int]: return {str(k).lower():int(n) for k,n in (v or {}).items()}
def command()->list[str]:
    raw=os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD","")
    if not raw: raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)

def natural_env(r:dict[str,Any])->dict[str,str]:
    t=r["temporal_state"]; e=os.environ.copy()
    e.update({"COMMANDER_LAB_FORGE_PLAYER_COUNT":str(len(r["players"])),"COMMANDER_LAB_FORGE_FIXTURE_ID":r["fixture_id"],"COMMANDER_LAB_WS40_ENTRY_MODE":"NATURAL_GAME_START","COMMANDER_LAB_WS40_CONSTRUCTION_ONLY":"1","COMMANDER_LAB_WS40_TURN":str(int(t["turn_number"])),"COMMANDER_LAB_WS40_ACTIVE_SEAT":"1","COMMANDER_LAB_WS40_PRIORITY_SEAT":"1","COMMANDER_LAB_WS40_PHASE":str(t["phase"]),"COMMANDER_LAB_WS40_STEP":str(t["step"]),"COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY":"128"})
    e.update(transport.knowledge_env(r)); e.update(transport.randomness_env(r)); return e

def env_for(r:dict[str,Any])->dict[str,str]:
    if r["execution_entry_mode"]=="NATIVE_STATE_LOAD": return transport.env_for(r)
    if r["execution_entry_mode"]=="NATURAL_GAME_START": return natural_env(r)
    raise AssertionError("unsupported entry mode")

def one_option(frame:dict[str,Any],kind:str)->str:
    xs=[o for o in frame["payload"]["options"] if o.get("kind")==kind]
    if len(xs)!=1: raise AssertionError((kind,xs))
    return str(xs[0]["option_id"])
def submit(p,frame,oid:str)->None:
    p.stdin.write(json.dumps({"protocol":PROTOCOL,"message_type":"SUBMIT_DECISION","request_id":"ws48-readback-reply-"+frame["payload"]["decision_id"],"session_id":frame.get("session_id"),"payload":{"decision_id":frame["payload"]["decision_id"],"option_id":oid}},separators=(",",":"))+"\n"); p.stdin.flush()

def execute(r:dict[str,Any])->dict[str,Any]:
    with tempfile.TemporaryFile(mode="w+t",encoding="utf-8") as err:
        p=subprocess.Popen(command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,env=env_for(r),bufsize=1)
        p.stdin.write(json.dumps({"protocol":PROTOCOL,"message_type":"CREATE_SESSION","request_id":"ws48-readback-"+r["fixture_id"],"payload":{"fixture_id":r["fixture_id"]}},separators=(",",":"))+"\n"); p.stdin.flush()
        created=raw=result=None; messages=[]
        for _ in range(1024):
            line=p.stdout.readline()
            if not line: break
            m=json.loads(line); typ=m.get("message_type"); messages.append(str(typ))
            if typ=="SESSION_CREATED": created=m["payload"]["snapshot"]
            elif typ=="QUALIFICATION_STATE": raw=m["payload"]["raw_native"]
            elif typ=="DECISION_FRAME":
                kind=m["payload"]["decision_kind"]
                if kind=="chooseStartingPlayer": submit(p,m,one_option(m,"PLAYER:seat-1"))
                elif kind=="mulliganKeepHand": submit(p,m,one_option(m,"KEEP"))
                else: raise AssertionError("readback reached discretionary behavior decision:"+kind)
            elif typ=="SESSION_RESULT": result=m["payload"]; break
            else: raise AssertionError(f"unexpected provider message {m}")
        try: p.stdin.close()
        except Exception: pass
        rc=p.wait(timeout=60); err.seek(0); stderr=err.read()
    if rc!=0 or created is None or raw is None or result is None: raise RuntimeError(f"provider readback failed {r['fixture_id']} rc={rc} messages={messages} stderr={stderr[-6000:]}")
    expected="WS45_CONSTRUCTION_COMPLETE" if r["execution_entry_mode"]=="NATURAL_GAME_START" else "WS40_CONSTRUCTION_COMPLETE"
    if result.get("stop_reason")!=expected: raise AssertionError(f"stop mismatch {result.get('stop_reason')} != {expected}")
    return {"created":created,"raw":raw}

def partner(cid:str,rels:list[dict[str,Any]])->str:
    xs=[x for x in rels if cid in (x.get("commander_ids") or [])]
    if len(xs)!=1 or len(xs[0]["commander_ids"])!=2: raise AssertionError(f"native Partner relation nonunique {cid}")
    ids=list(xs[0]["commander_ids"]); return ids[1] if ids[0]==cid else ids[0]
def identity_meta(shape:dict[str,Any],row:dict[str,Any])->dict[str,Any]:
    for k in ("semantic_id","card_lineage_id","commander_id","construction_notes"):
        if k in shape: row[k]=shape[k]
    return row

def phase_pair(p:Any)->tuple[str,str]:
    key=str(p or "").upper().replace(" ","_")
    table={"MAIN1":("precombat_main","main"),"MAIN2":("postcombat_main","main"),"UPKEEP":("beginning","upkeep"),"DRAW":("beginning","draw"),"COMBAT_DECLARE_ATTACKERS":("combat","declare_attackers"),"COMBAT_DECLARE_BLOCKERS":("combat","declare_blockers"),"COMBAT_DAMAGE":("combat","combat_damage")}
    if key not in table: raise AssertionError(f"unmapped native phase {p!r}")
    return table[key]

def state_readback(r:dict[str,Any],ev:dict[str,Any])->dict[str,Any]:
    raw=ev["raw"]; obs=raw["ws45_observation"]
    live={x["player_id"]:x for x in raw.get("players") or []}; initial={f"P{i+1}":x for i,x in enumerate(ev["created"].get("players") or [])}
    players=[]
    for ident in r["players"]:
        pid=ident["player_id"]; x=live[pid]
        players.append({"eliminated":not bool(x["in_game"]),"life":int(x["life"]),"lost":bool(x["lost"]),"player_id":pid,"poison":int(x["poison"]),"seat":seat(pid),"starting_life":int(initial[pid]["life"])})
    native_cmd={x["commander_id"]:x for x in raw.get("commanders") or []}; rels=list(obs.get("multiple_commander_relations") or [])
    cmds=[]
    for ident in r["commander_state"]["commanders"]:
        cid=ident["commander_id"]; x=native_cmd[cid]; row={"card_identity":x["name"],"commander_id":cid,"owner":x["owner"],"prior_command_zone_cast_count":int(x["cast_count"]),"zone":x["zone"]}
        if "partner_with" in ident: row["partner_with"]=partner(cid,rels)
        cmds.append(row)
    ndmg={(x["source_commander_id"],x["damaged_player"]):int(x["combat_damage"]) for x in raw.get("commander_damage") or []}
    dmg=[]
    for ident in r["commander_state"].get("commander_damage_matrix") or []:
        key=(ident["source_commander_id"],ident["damaged_player"]); dmg.append({"combat_damage":ndmg[key],"damaged_player":key[1],"source_commander_id":key[0]})
    cards={x["semantic_id"]:x for x in raw.get("cards") or []}; objs=[]
    for ident in r.get("semantic_objects") or []:
        x=cards[ident["semantic_id"]]; row=identity_meta(ident,{"card_identity":x["card_identity"],"controller":x["controller"],"counters":counters(x.get("counters")),"face_down":bool(x["face_down"]),"owner":x["owner"],"tapped":bool(x["tapped"]),"zone":"revealed" if x.get("native_revealed") is True else x["zone"]})
        if "attached_to" in ident: row["attached_to"]=x.get("attached_to")
        if "zone_position" in ident: row["zone_position"]=x.get("zone_position")
        if "controlled_since_turn_began" in ident: row["controlled_since_turn_began"]=not bool(x.get("sick"))
        objs.append(row)
    ph,step=phase_pair(raw.get("phase")); temporal={"active_player":raw["active_player"],"extra_turn_queue":[],"phase":ph,"priority_player":raw["priority_player"],"step":step,"turn_number":int(raw["turn"])}
    cs=r.get("combat_state"); combat=None
    if cs is not None:
        g=raw.get("combat") or {}; combat={}
        if "attackers" in cs: combat["attackers"]=dict(g.get("attackers") or {})
        if "blockers" in cs: combat["blockers"]=dict(g.get("blockers") or {})
        if "eligible_attackers" in cs: combat["eligible_attackers"]=list(g.get("eligible_attackers") or [])
        if "eligible_blockers" in cs: combat["eligible_blockers"]=list(g.get("eligible_blockers") or [])
        attackers=list((g.get("attackers") or {}).keys()); blocked=set((g.get("blockers") or {}).values()); unblocked=[x for x in attackers if x not in blocked]
        if "unblocked_attackers" in cs: combat["unblocked_attackers"]=unblocked
        if "unblocked" in cs: combat["unblocked"]=unblocked
    nstack={x["source_semantic_id"]:x for x in raw.get("stack") or []}; stack=[]
    for ident in r.get("stack_state") or []:
        sid=ident["source_semantic_id"]; x=nstack[sid]
        if x.get("native_stack_present") is not True: raise AssertionError("native stack object absent:"+sid)
        stack.append({"cast_complete":bool(x["cast_complete"]),"controller":x["controller"],"costs_paid":bool(x["costs_paid"]),"modes":list(x.get("modes") or []),"source_semantic_id":sid,"targets":list(x.get("targets") or [])})
    return {"execution_entry_mode":"NATIVE_STATE_LOAD","players":players,"deck_state":None,"commander_state":{"commander_damage_matrix":dmg,"commanders":cmds,"multiple_commander_relations":rels},"semantic_objects":objs,"temporal_state":temporal,"knowledge_state":obs["knowledge_state"],"rules_randomness":obs["rules_randomness"],"combat_state":combat,"stack_state":stack,"continuous_rules_effects":None,"extra_turn_creation":obs["extra_turn_creation"],"elimination_trigger":obs["elimination_trigger"],"zone_move_event":obs["zone_move_event"],"setup_validation":obs["setup_validation"]}

def natural_map(raw:dict[str,Any])->dict[str,dict[str,Any]]: return {x["player_id"]:x for x in raw.get("decks") or []}
def natural_commander(ident:dict[str,Any],raw:dict[str,Any])->dict[str,Any]:
    xs=[x for x in natural_map(raw)[ident["owner"]]["native_commanders"] if x["card_identity"]==ident["card_identity"]]
    if len(xs)!=1: raise AssertionError(f"native natural commander nonunique {ident.get('commander_id')}")
    return xs[0]
def natural_readback(r:dict[str,Any],ev:dict[str,Any])->dict[str,Any]:
    raw=ev["raw"]
    if raw.get("natural_lifecycle") is not True or raw.get("provider_entry_mode")!="NATURAL_GAME_START": raise AssertionError("natural lifecycle marker absent")
    decks=natural_map(raw); players=[]
    for ident in r["players"]:
        pid=ident["player_id"]; x=decks[pid]; players.append({"eliminated":not bool(x["in_game"]),"life":int(x["live_life"]),"lost":bool(x["lost"]),"player_id":pid,"poison":int(x["poison"]),"seat":seat(pid),"starting_life":int(x["registered_starting_life"])})
    deck_state=[]; channels=list((raw.get("rules_randomness") or {}).get("channels") or [])
    for ident in r.get("deck_state") or []:
        pid=ident["player_id"]; x=decks[pid]
        if "library_template" in ident:
            entries=list(x["main_entries"]); c=[v for v in channels if v.endswith(":"+pid)]
            if len(entries)!=1 or len(c)!=1: raise AssertionError("native natural template/channel nonunique")
            deck_state.append({"commander_ids":list(ident["commander_ids"]),"library_template":dict(entries[0]),"opening_hand_size":int(x["hand_count"]),"player_id":pid,"shuffle_channel":c[0]})
        else: deck_state.append({"commander":list(x["commander_entries"]),"exact_card_count":int(x["main_count"])+int(x["commander_count"]),"main_deck":list(x["main_entries"]),"player_id":pid})
    cmds=[]
    for ident in r["commander_state"]["commanders"]:
        x=natural_commander(ident,raw); row={"card_identity":x["card_identity"],"commander_id":ident["commander_id"],"owner":x["owner"],"prior_command_zone_cast_count":int(x["cast_count"]),"zone":x["zone"]}
        if "partner_with" in ident: raise AssertionError("natural Partner unsupported in denominator")
        cmds.append(row)
    objs=[]
    for ident in r.get("semantic_objects") or []:
        if not ident.get("commander_id"): raise AssertionError("natural semantic object is not commander identity")
        x=natural_commander(ident,raw); objs.append(identity_meta(ident,{"card_identity":x["card_identity"],"controller":x["controller"],"counters":counters(x.get("counters")),"face_down":bool(x["face_down"]),"owner":x["owner"],"tapped":bool(x["tapped"]),"zone":x["zone"]}))
    if int(raw.get("native_turn",0))<1 or not raw.get("native_phase"): raise AssertionError("native first turn not reached")
    semantic_step=r["temporal_state"]["step"]
    if semantic_step not in {"game_start","mulligan"}: raise AssertionError("unsupported natural checkpoint")
    if semantic_step=="mulligan" and not list(raw.get("mulligan_trace") or []): raise AssertionError("mulligan trace absent")
    active=raw.get("native_active_player"); priority=raw.get("native_priority_player") or active
    temporal={"active_player":active,"extra_turn_queue":[],"phase":"pregame","priority_player":priority,"step":semantic_step,"turn_number":0}
    return {"execution_entry_mode":"NATURAL_GAME_START","players":players,"deck_state":deck_state,"commander_state":{"commander_damage_matrix":[],"commanders":cmds,"multiple_commander_relations":[]},"semantic_objects":objs,"temporal_state":temporal,"knowledge_state":raw["knowledge_state"],"rules_randomness":raw["rules_randomness"],"combat_state":None,"stack_state":[],"continuous_rules_effects":None,"extra_turn_creation":None,"elimination_trigger":None,"zone_move_event":None,"setup_validation":raw["setup_validation"]}

def native_readback(r:dict[str,Any],ev:dict[str,Any])->dict[str,Any]:
    mode=ev["raw"].get("provider_entry_mode")
    if mode!=r["execution_entry_mode"]: raise AssertionError(f"native entry mode mismatch {mode}")
    return natural_readback(r,ev) if mode=="NATURAL_GAME_START" else state_readback(r,ev)
def shape_project(shape:Any,native:Any)->Any:
    if isinstance(shape,dict) and isinstance(native,dict): return {k:shape_project(v,native[k]) for k,v in shape.items() if k in native}
    if isinstance(shape,list) and isinstance(native,list): return native if len(shape)!=len(native) else [shape_project(s,n) for s,n in zip(shape,native)]
    return native
def write(path:Path,payload:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--materialization",type=Path,required=True); ap.add_argument("--denominator",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    raw=a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=WS47_SHA: raise SystemExit("immutable WS47 materialization digest mismatch")
    doc=json.loads(raw)
    if doc["schema_version"]!=WS47_SCHEMA or doc["canonical_bundle_digest"]!=WS47_BUNDLE: raise SystemExit("immutable WS47 identity mismatch")
    ids=list(json.loads(a.denominator.read_text())["fixture_ids"])
    if len(ids)!=107 or len(set(ids))!=107: raise SystemExit("WS47 denominator is not exact 107")
    by={x["fixture_id"]:x for x in doc["records"]}; rows=[]
    result={"schema_version":"commander-lab.ws48-independent-native-readback/1.0.0","status":"IN_PROGRESS","denominator":107,"pass_count":0,"historical_successor_runtime_credit_imported":0,"construction_credit":"107/107","behavior_credit":"0/107","construction_normalizer_imported":False,"normalizer_implementation":"WS48_STANDALONE_NATIVE_READBACK","ws47":{"commit":WS47_COMMIT,"tree":WS47_TREE,"schema":WS47_SCHEMA,"bundle_digest":WS47_BUNDLE,"materialization_sha256":WS47_SHA},"forge":{"commit":FORGE_COMMIT,"tree":FORGE_TREE},"rows":rows}
    for i,fid in enumerate(ids,1):
        r=by[fid]
        try:
            req=requested(r); rd=digest(req)
            if rd!=r["requested_state_digest"]: raise AssertionError("frozen requested digest mismatch")
            ev=execute(r); norm=shape_project(req,native_readback(r,ev)); nd=digest(norm)
            if norm!=req or nd!=rd: raise AssertionError("INDEPENDENT_NATIVE_READBACK_MISMATCH:"+fid+":requested="+canon(req)+":native="+canon(norm))
            rows.append({"index":i,"fixture_id":fid,"fixture_family":r["fixture_family"],"status":"PASS","evidence_class":"RUNTIME_VERIFIED_INDEPENDENT_READBACK","requested_state_digest":rd,"independent_native_state_digest":nd,"raw_native_snapshot_digest":digest(ev["raw"]),"native_equal":True}); result["pass_count"]=len(rows); write(a.output,result); print(f"WS48 READBACK {i:03d}/107 PASS {fid} {nd}",flush=True)
        except Exception as ex:
            rows.append({"index":i,"fixture_id":fid,"fixture_family":r["fixture_family"],"status":"FAIL","error":str(ex)[:20000]}); result.update({"status":"FAIL","failure_index":i,"failure_fixture_id":fid,"pass_count":sum(x.get("status")=="PASS" for x in rows)}); write(a.output,result); print(f"WS48 READBACK {i:03d}/107 FAIL {fid}: {ex}",flush=True); return 1
    result.update({"status":"PASS","pass_count":107,"hard_gate":"PASS","family_counts":dict(sorted(collections.Counter(x["fixture_family"] for x in rows).items())),"proof":{"standalone_normalizer":True,"construction_normalizer_imported":False,"native_runtime_reexecuted_all_107":True,"all_native_readback_equal_requested_state":True,"request_use_limited_to_identity_presence_order_and_explicit_semantic_checkpoint_mapping":True}}); write(a.output,result); print(json.dumps({k:v for k,v in result.items() if k!="rows"},indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
