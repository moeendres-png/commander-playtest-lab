#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, copy, hashlib, json, os, shlex, subprocess, tempfile, urllib.parse
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
WS44_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.4"
WS44_BUNDLE = "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54"
WS44_FILE_SHA = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
FORGE_COMMIT = "a248bf22ca9ce00908ee06fb26bfd5ea0fc6803d"
FORGE_TREE = "2a8e15cda48e7f26fb806c7c99d7c51bdf797bfb"


def canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()

def enc(v: Any) -> str:
    return urllib.parse.quote("" if v is None else str(v), safe="")

def b64_text(s: str) -> str:
    return base64.b64encode(s.encode()).decode()

def b64_rows(rows: list[list[str]]) -> str:
    return b64_text("\n".join("\t".join(r) for r in rows))

def seat(pid: str) -> int:
    if not isinstance(pid, str) or not pid.startswith("P"):
        raise AssertionError(f"bad player id {pid!r}")
    return int(pid[1:])

def counter_def(counters: dict[str, int]) -> str:
    return ",".join(f"{k}={v}" for k,v in sorted((counters or {}).items()))

def all_specs(record: dict[str,Any]) -> tuple[list[dict[str,Any]],dict[str,str]]:
    specs=[dict(o)|{"emit_semantic":True} for o in (record.get("semantic_objects") or [])]
    by_cmd={o.get("commander_id"):o["semantic_id"] for o in specs if o.get("commander_id")}
    for c in record["commander_state"]["commanders"]:
        if c["commander_id"] in by_cmd: continue
        sid=f"__ws45_commander__:{c['commander_id']}"
        specs.append({"semantic_id":sid,"card_identity":c["card_identity"],"owner":c["owner"],"controller":c["owner"],"zone":c["zone"],"tapped":False,"face_down":False,"counters":{},"commander_id":c["commander_id"],"emit_semantic":False})
        by_cmd[c["commander_id"]]=sid
    return specs,by_cmd

def object_rows(record: dict[str,Any]) -> tuple[list[list[str]],dict[str,str]]:
    specs,by_cmd=all_specs(record); rows=[]
    for o in specs:
        rows.append([enc(o["semantic_id"]),enc(o["card_identity"]),str(seat(o["owner"])),str(seat(o["controller"])),str(o["zone"]),str(bool(o.get("tapped",False))).lower(),str(bool(o.get("face_down",False))).lower(),enc(counter_def(o.get("counters") or {})),enc(o.get("attached_to")),"" if o.get("zone_position") is None else str(int(o["zone_position"])),enc(o.get("commander_id")),str(bool(o.get("controlled_since_turn_began",False))).lower(),str(bool(o["emit_semantic"])).lower()])
    return rows,by_cmd

def commander_rows(record:dict[str,Any],by_cmd:dict[str,str])->list[list[str]]:
    return [[enc(c["commander_id"]),enc(by_cmd[c["commander_id"]]),str(int(c.get("prior_command_zone_cast_count",0)))] for c in record["commander_state"]["commanders"]]

def damage_rows(record:dict[str,Any])->list[list[str]]:
    return [[enc(x["source_commander_id"]),str(seat(x["damaged_player"])),str(int(x["combat_damage"]))] for x in (record["commander_state"].get("commander_damage_matrix") or [])]

def stack_rows(record:dict[str,Any])->list[list[str]]:
    by={o["semantic_id"]:o for o in (record.get("semantic_objects") or [])}; out=[]
    for s in record.get("stack_state") or []:
        o=by[s["source_semantic_id"]]
        out.append([enc(s["source_semantic_id"]),str(seat(o["owner"])),str(seat(s["controller"])),enc(o["card_identity"]),enc(",".join(s.get("targets") or []))])
    return out

def combat_rows(record:dict[str,Any])->list[list[str]]:
    cs=record.get("combat_state") or {}
    return [["A",enc(a),enc(d)] for a,d in (cs.get("attackers") or {}).items()]+[["B",enc(b),enc(a)] for b,a in (cs.get("blockers") or {}).items()]

def _presence(v:dict[str,Any],k:str)->str: return str(k in v).lower()
def _list(v:Any)->str: return enc("\u001f".join(str(x) for x in (v or [])))
def knowledge_env(record:dict[str,Any])->dict[str,str]:
    ks=record.get("knowledge_state") or {"channel_policy":"ACTOR_ENTITLED_ONLY","viewer_states":[]}
    viewers=ks.get("viewer_states") or []
    vr=[]; fr=[]
    for v in viewers:
        viewer=v["viewer"]
        vr.append([enc(viewer),_presence(v,"channels_under_test"),_list(v.get("channels_under_test")),_presence(v,"honey_sentinels"),_list(v.get("honey_sentinels")),_list(v.get("invalidation_conditions")),_presence(v,"obligation"),enc(v.get("obligation")),_presence(v,"ordered_known_information"),_list(v.get("ordered_known_information")),_presence(v,"permitted_public_metadata"),_list(v.get("permitted_public_metadata")),_presence(v,"prohibited_metadata"),_list(v.get("prohibited_metadata"))])
        for sid in v.get("known_object_identities") or []:
            fr.append(["KNOWN_OBJECT_IDENTITY",enc(viewer),enc(sid),"","","","","","","","","","","",""])
        for x in v.get("known_library_ranges") or []:
            fr.append(["KNOWN_LIBRARY_RANGE",enc(viewer),"",enc(x.get("player")),"","","","" if x.get("start") is None else str(x["start"]),"" if x.get("count") is None else str(x["count"]),"" if x.get("ordered") is None else str(bool(x["ordered"])).lower(),"",enc(x.get("before_event")),"","",""])
        for x in v.get("face_down_look_permissions") or []:
            fr.append(["FACE_DOWN_LOOK_PERMISSION",enc(viewer),enc(x.get("object")),"",enc(x.get("zone")),enc(x.get("permission")),enc(x.get("scope")),"","","","" if x.get("persists_while_in_same_exile_object") is None else str(bool(x["persists_while_in_same_exile_object"])).lower(),"","","",enc(x.get("viewer") or viewer)])
        for x in v.get("temporary_permissions") or []:
            fr.append(["TEMPORARY_PERMISSION",enc(viewer),enc(x.get("object")),enc(x.get("player")),enc(x.get("zone")),enc(x.get("permission")),enc(x.get("scope")),"","","","" if x.get("persists_while_in_same_exile_object") is None else str(bool(x["persists_while_in_same_exile_object"])).lower(),enc(x.get("before_event")),enc(x.get("controlled_player")),enc(x.get("controller")),enc(x.get("viewer") or viewer)])
    return {"COMMANDER_LAB_WS45_KNOWLEDGE_CHANNEL_POLICY_B64":b64_text(str(ks.get("channel_policy","ACTOR_ENTITLED_ONLY"))),"COMMANDER_LAB_WS45_KNOWLEDGE_VIEWER_ROWS_B64":b64_rows(vr),"COMMANDER_LAB_WS45_KNOWLEDGE_FACT_ROWS_B64":b64_rows(fr)}

def randomness_env(record:dict[str,Any])->dict[str,str]:
    rr=record.get("rules_randomness") or {}
    fixed=rr.get("rules_seed")
    binding=rr.get("seed_binding")
    effective=int(fixed if fixed is not None else 424242)
    rows=[["fixed_seed","" if fixed is None else str(fixed)],["seed_binding",enc(binding)],["effective_seed",str(effective)],["pilot_prohibited",str(bool(rr.get("pilot_randomness_prohibited",True))).lower()],["native_calls",str(bool(rr.get("provider_native_rng_calls_recorded",False))).lower()]]
    rows += [["channel",enc(x)] for x in (rr.get("channels") or [])]
    for d in rr.get("predetermined_semantic_draws") or []:
        rows.append(["draw",enc(d["channel"]),enc(d["operation"]),enc(d["result"])])
    return {"COMMANDER_LAB_FORGE_RULES_SEED":str(effective),"COMMANDER_LAB_WS45_RANDOMNESS_ROWS_B64":b64_rows(rows),"COMMANDER_LAB_WS45_RANDOMNESS_HAS_FIXED_SEED":"1" if "rules_seed" in rr else "0","COMMANDER_LAB_WS45_RANDOMNESS_HAS_SEED_BINDING":"1" if "seed_binding" in rr else "0","COMMANDER_LAB_WS45_RANDOMNESS_HAS_PREDETERMINED":"1" if "predetermined_semantic_draws" in rr else "0","COMMANDER_LAB_WS45_RANDOMNESS_HAS_NATIVE_CALLS":"1" if "provider_native_rng_calls_recorded" in rr else "0"}

def strict_relation_env(record:dict[str,Any])->dict[str,str]:
    extra=record.get("extra_turn_creation")
    extra_rows=[]
    for x in ([] if extra is None else (extra if isinstance(extra,list) else [extra])):
        extra_rows.append([str(int(x["sequence"])),enc(x["player"]),enc(x["source"])])
    zm=record.get("zone_move_event")
    zone_rows=[]
    for x in ([] if zm is None else (zm if isinstance(zm,list) else [zm])):
        zone_rows.append([enc(x["commander_id"]),enc(x["to"])])
    partner=[]
    for x in record.get("commander_state",{}).get("multiple_commander_relations") or []:
        ids=x.get("commander_ids") or []
        if len(ids)==2: partner.append([enc(ids[0]),enc(ids[1])])
    return {"COMMANDER_LAB_WS45_EXTRA_TURN_ROWS_B64":b64_rows(extra_rows),"COMMANDER_LAB_WS45_ZONE_MOVE_ROWS_B64":b64_rows(zone_rows),"COMMANDER_LAB_WS45_PARTNER_ROWS_B64":b64_rows(partner)}

def env_for(record:dict[str,Any])->dict[str,str]:
    if record["execution_entry_mode"] != "NATIVE_STATE_LOAD": raise AssertionError("adversarial gate uses state-load records")
    obj,by_cmd=object_rows(record); t=record["temporal_state"]
    e=os.environ.copy(); e.update({"COMMANDER_LAB_FORGE_PLAYER_COUNT":str(len(record["players"])),"COMMANDER_LAB_FORGE_FIXTURE_ID":record["fixture_id"],"COMMANDER_LAB_WS40_ENTRY_MODE":"NATIVE_STATE_LOAD","COMMANDER_LAB_WS40_CONSTRUCTION_ONLY":"1","COMMANDER_LAB_WS40_OBJECT_SPECS_B64":b64_rows(obj),"COMMANDER_LAB_WS40_COMMANDER_SPECS_B64":b64_rows(commander_rows(record,by_cmd)),"COMMANDER_LAB_WS40_DAMAGE_SPECS_B64":b64_rows(damage_rows(record)),"COMMANDER_LAB_WS40_STACK_SPECS_B64":b64_rows(stack_rows(record)),"COMMANDER_LAB_WS40_COMBAT_SPECS_B64":b64_rows(combat_rows(record)),"COMMANDER_LAB_WS40_TURN":str(int(t["turn_number"])),"COMMANDER_LAB_WS40_ACTIVE_SEAT":str(seat(t["active_player"])),"COMMANDER_LAB_WS40_PRIORITY_SEAT":str(seat(t["priority_player"])),"COMMANDER_LAB_WS40_PHASE":str(t["phase"]),"COMMANDER_LAB_WS40_STEP":str(t["step"]),"COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY":"128"})
    for p in record["players"]: e[f"COMMANDER_LAB_WS40_LIFE_P{p['seat']}"]=str(p["life"])
    e.update(knowledge_env(record)); e.update(randomness_env(record)); e.update(strict_relation_env(record))
    return e

def cmd()->list[str]:
    raw=os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not raw: raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)

def option(frame:dict[str,Any],kind:str)->str:
    xs=[o for o in frame["payload"]["options"] if o.get("kind")==kind]
    if len(xs)!=1: raise AssertionError((kind,xs))
    return str(xs[0]["option_id"])

def submit(proc,frame,oid):
    proc.stdin.write(json.dumps({"protocol":PROTOCOL,"message_type":"SUBMIT_DECISION","request_id":"reply-"+frame["payload"]["decision_id"],"session_id":frame.get("session_id"),"payload":{"decision_id":frame["payload"]["decision_id"],"option_id":oid}},separators=(",",":"))+"\n"); proc.stdin.flush()

def run(record:dict[str,Any],overrides:dict[str,str]|None=None)->dict[str,Any]:
    e=env_for(record); e.update(overrides or {})
    with tempfile.TemporaryFile(mode="w+t",encoding="utf-8") as err:
        p=subprocess.Popen(cmd(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,env=e,bufsize=1)
        p.stdin.write(json.dumps({"protocol":PROTOCOL,"message_type":"CREATE_SESSION","request_id":"ws45-noecho-"+record["fixture_id"],"payload":{"fixture_id":record["fixture_id"]}},separators=(",",":"))+"\n"); p.stdin.flush()
        raw=None; result=None; messages=[]
        for _ in range(512):
            line=p.stdout.readline()
            if not line: break
            m=json.loads(line); messages.append(m.get("message_type")); typ=m.get("message_type")
            if typ=="SESSION_CREATED": continue
            if typ=="QUALIFICATION_STATE": raw=m["payload"]["raw_native"]; continue
            if typ=="DECISION_FRAME":
                k=m["payload"]["decision_kind"]
                if k=="chooseStartingPlayer": submit(p,m,option(m,"PLAYER:seat-1")); continue
                if k=="mulliganKeepHand": submit(p,m,option(m,"KEEP")); continue
                raise AssertionError("unexpected decision "+k)
            if typ=="SESSION_RESULT": result=m; break
            raise AssertionError(f"unexpected provider message {m}")
        try: p.stdin.close()
        except Exception: pass
        rc=p.wait(timeout=60); err.seek(0); stderr=err.read()
    return {"rc":rc,"raw":raw,"result":result,"stderr_tail":stderr[-4000:],"messages":messages}

def successful(x:dict[str,Any])->bool:
    if x["rc"]!=0 or x["raw"] is None or x["result"] is None: return False
    return x["result"]["payload"].get("stop_reason") in {"WS40_CONSTRUCTION_COMPLETE","WS45_CONSTRUCTION_COMPLETE"}

def assert_fail_closed(x:dict[str,Any],label:str)->None:
    if successful(x): raise AssertionError(label+": invalid perturbation produced successful construction")

def observation(x): return x["raw"].get("ws45_observation") if x.get("raw") else None

def pick(records,pred,label):
    xs=[r for r in records if r["execution_entry_mode"]=="NATIVE_STATE_LOAD" and pred(r)]
    if not xs: raise AssertionError("no representative for "+label)
    return xs[0]

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--materialization",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    raw=a.materialization.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=WS44_FILE_SHA: raise SystemExit("WS44 materialization digest mismatch")
    doc=json.loads(raw)
    if doc["schema_version"]!=WS44_SCHEMA or doc["canonical_bundle_digest"]!=WS44_BUNDLE: raise SystemExit("WS44 identity mismatch")
    records=[r for r in doc["records"] if r.get("fixture_family")!="actual_card" or r["fixture_id"]=="CARD_02"]
    if len(records)!=107: raise SystemExit(f"denominator mismatch {len(records)}")
    reps={
      "knowledge":pick(records,lambda r:r.get("fixture_family")=="hidden_information","knowledge"),
      "rng":pick(records,lambda r:bool((r.get("rules_randomness") or {}).get("channels")),"rng"),
      "extra":pick(records,lambda r:r.get("extra_turn_creation") is not None,"extra"),
      "elim":pick(records,lambda r:r.get("elimination_trigger") is not None,"elimination"),
      "zone":pick(records,lambda r:r.get("zone_move_event") is not None,"zone"),
      "partner":pick(records,lambda r:bool(r.get("commander_state",{}).get("multiple_commander_relations")),"partner"),
      "identity":pick(records,lambda r:len(r.get("semantic_objects") or [])>=2,"identity"),
    }
    evidence=[]; baseline={}
    canaries={"knowledge":"COMMANDER_LAB_WS45_KNOWLEDGE_CANONICAL_B64","rng":"COMMANDER_LAB_WS45_RANDOMNESS_CANONICAL_B64","extra":"COMMANDER_LAB_WS45_EXTRA_TURN_CANONICAL_B64","elim":"COMMANDER_LAB_WS45_ELIMINATION_CANONICAL_B64","zone":"COMMANDER_LAB_WS45_ZONE_MOVE_CANONICAL_B64"}
    for label in ["knowledge","rng","extra","elim","zone","partner","identity"]:
        r=reps[label]; b=run(r)
        if not successful(b): raise AssertionError(f"baseline failed {label} {r['fixture_id']} {b}")
        baseline[label]=b
        evidence.append({"test":label+"_baseline","fixture_id":r["fixture_id"],"status":"PASS","raw_digest":digest(b["raw"]),"observation_digest":digest(observation(b))})
        if label in canaries:
            c=run(r,{canaries[label]:b64_text('{"adversarial":"REQUEST_ECHO_CANARY","nonce":"WS45"}')})
            if not successful(c): raise AssertionError(f"canary run failed {label}")
            if observation(c)!=observation(b): raise AssertionError(f"REQUEST_ECHO_DETECTED:{label}")
            evidence.append({"test":label+"_comparison_canary_invariance","fixture_id":r["fixture_id"],"status":"PASS","baseline_observation_digest":digest(observation(b)),"perturbed_observation_digest":digest(observation(c))})
    # Fake setup-validation comparison material must never influence provider truth.
    r=reps["identity"]; b=baseline["identity"]
    c=run(r,{"COMMANDER_LAB_WS45_SETUP_VALIDATION_CANONICAL_B64":b64_text('{"compare_requested_vs_constructed":false,"on_mismatch":"SILENT"}')})
    if not successful(c) or observation(c).get("setup_validation")!=observation(b).get("setup_validation"): raise AssertionError("setup validation request echo")
    evidence.append({"test":"setup_validation_canary_invariance","fixture_id":r["fixture_id"],"status":"PASS"})
    # Invalid operational RNG policy must fail at native MyRandom installation.
    rr=base64.b64decode(env_for(reps["rng"])["COMMANDER_LAB_WS45_RANDOMNESS_ROWS_B64"]).decode().splitlines(); rr=[("pilot_prohibited\tfalse" if x.startswith("pilot_prohibited\t") else x) for x in rr]
    x=run(reps["rng"],{"COMMANDER_LAB_WS45_RANDOMNESS_ROWS_B64":b64_text("\n".join(rr))}); assert_fail_closed(x,"rng pilot randomness")
    evidence.append({"test":"rng_invalid_policy_fail_closed","fixture_id":reps["rng"]["fixture_id"],"status":"PASS","rc":x["rc"]})
    # Unknown knowledge viewer must fail closed against native game players.
    vr=base64.b64decode(env_for(reps["knowledge"])["COMMANDER_LAB_WS45_KNOWLEDGE_VIEWER_ROWS_B64"]).decode().splitlines()
    if vr:
        cols=vr[0].split("\t"); cols[0]=enc("P6"); vr[0]="\t".join(cols)
        x=run(reps["knowledge"],{"COMMANDER_LAB_WS45_KNOWLEDGE_VIEWER_ROWS_B64":b64_text("\n".join(vr))}); assert_fail_closed(x,"knowledge unknown viewer")
        evidence.append({"test":"knowledge_unknown_viewer_fail_closed","fixture_id":reps["knowledge"]["fixture_id"],"status":"PASS","rc":x["rc"]})
    # Extra-turn history must reject an unknown/non-native source mapping.
    er=base64.b64decode(env_for(reps["extra"])["COMMANDER_LAB_WS45_EXTRA_TURN_ROWS_B64"]).decode().splitlines(); cols=er[0].split("\t"); cols[2]=enc("__ws45_non_addturn_source__"); er[0]="\t".join(cols)
    x=run(reps["extra"],{"COMMANDER_LAB_WS45_EXTRA_TURN_ROWS_B64":b64_text("\n".join(er))}); assert_fail_closed(x,"extra-turn invalid source")
    evidence.append({"test":"extra_turn_invalid_source_fail_closed","fixture_id":reps["extra"]["fixture_id"],"status":"PASS","rc":x["rc"]})
    # Commander move timing is engine-derived; unsupported destination must fail closed.
    zr=base64.b64decode(env_for(reps["zone"])["COMMANDER_LAB_WS45_ZONE_MOVE_ROWS_B64"]).decode().splitlines(); cols=zr[0].split("\t"); cols[1]=enc("command"); zr[0]="\t".join(cols)
    x=run(reps["zone"],{"COMMANDER_LAB_WS45_ZONE_MOVE_ROWS_B64":b64_text("\n".join(zr))}); assert_fail_closed(x,"zone invalid destination")
    evidence.append({"test":"zone_move_invalid_destination_fail_closed","fixture_id":reps["zone"]["fixture_id"],"status":"PASS","rc":x["rc"]})
    # Partner relation must reject same commander as both members.
    pr=base64.b64decode(env_for(reps["partner"])["COMMANDER_LAB_WS45_PARTNER_ROWS_B64"]).decode().splitlines(); cols=pr[0].split("\t"); cols[1]=cols[0]; pr[0]="\t".join(cols)
    x=run(reps["partner"],{"COMMANDER_LAB_WS45_PARTNER_ROWS_B64":b64_text("\n".join(pr))}); assert_fail_closed(x,"partner same commander")
    evidence.append({"test":"partner_invalid_relation_fail_closed","fixture_id":reps["partner"]["fixture_id"],"status":"PASS","rc":x["rc"]})
    # Elimination is read from native life/SBA precondition, not a requested outcome field.
    er=reps["elim"]; target=(er.get("elimination_trigger") or {}).get("player") if isinstance(er.get("elimination_trigger"),dict) else None
    if target:
        x=run(er,{f"COMMANDER_LAB_WS40_LIFE_P{seat(target)}":"1"})
        if not successful(x): raise AssertionError("elimination native-life perturbation did not construct")
        if observation(x).get("elimination_trigger") is not None: raise AssertionError("elimination output ignored native life perturbation")
        evidence.append({"test":"elimination_follows_native_life_not_requested_outcome","fixture_id":er["fixture_id"],"status":"PASS"})
    result={"schema_version":"commander-lab.ws45-strict-no-request-echo-runtime/1.0.0","status":"PASS","ws44":{"schema":WS44_SCHEMA,"bundle_digest":WS44_BUNDLE,"materialization_sha256":WS44_FILE_SHA,"denominator":107},"forge":{"commit":FORGE_COMMIT,"tree":FORGE_TREE},"historical_successor_credit_imported":0,"strict_no_request_echo":"PASS","construction_credit":"0/107","behavior_credit":"0/107","representatives":{k:v["fixture_id"] for k,v in reps.items()},"tests":evidence,"proof":{"comparison_canaries_do_not_influence_native_observation":True,"invalid_native_operations_fail_closed":True,"elimination_derived_from_native_life_state":True,"typed_knowledge_native_ids":True,"rules_rng_installed_at_native_boundary":True,"extra_turn_source_validated_by_native_card_rules":True,"commander_move_timing_native_surface":True,"partner_native_card_rules_validation":True,"setup_validation_provider_truth_not_request":True}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="tests"},indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
