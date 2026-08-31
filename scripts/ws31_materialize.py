#!/usr/bin/env python3
"""Materialize WS-31 terminal official-authority outputs from Gatherer shards."""
from __future__ import annotations
import argparse, hashlib, json, os, re, unicodedata, zlib
from pathlib import Path

EXPECTED_CR="9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c"
TERMINAL={"PASS","UNKNOWN","FAIL_CLOSED"}

def canon(s): return re.sub(r"\s+"," ",re.sub(r"\s*//\s*"," // ",unicodedata.normalize("NFC",(s or '').strip())))
def norm(s): return unicodedata.normalize("NFKC",canon(s)).casefold()
def htext(s): return hashlib.sha256(" ".join((s or "").split()).encode("utf-8")).hexdigest()
def hjson(o): return hashlib.sha256((json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")).hexdigest()
def read_json(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def load_zjson(p): return json.loads(zlib.decompress(Path(p).read_bytes()).decode("utf-8"))
def write_json(p,o): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
def all_oracle(rec): return "\n".join(f.get("oracle_text") or "" for f in rec.get("faces",[]))
def all_types(rec): return " // ".join(f.get("type_line") or "" for f in rec.get("faces",[]))
def add(evidence,path,kind,reason): evidence.append({"path":path,"classification":kind,"evidence":reason})

def derive_incidence(rec):
    ev=[]; text=all_oracle(rec); t=text.casefold(); ty=all_types(rec); tyl=ty.casefold(); mana=" // ".join(f.get("mana_cost") or "" for f in rec.get("faces",[]))
    add(ev,"object identity","AUTHORITY_DERIVED","official Gatherer identity record")
    if len(rec.get("faces",[]))>1: add(ev,"card faces","AUTHORITY_DERIVED","multiple official Gatherer faces locked")
    if mana.strip(): add(ev,"normal costs","AUTHORITY_DERIVED","official mana cost field present")
    rules=[
      (r"\badd (?:\{|one|two|three|four|five|six|seven|eight|nine|ten).*mana|\bmana ability\b","mana abilities"),(r"rather than pay|without paying (?:its|the) mana cost|alternative cost","alternative costs"),(r"as an additional cost","additional costs"),(r"\{x\}|\bx is\b|\bwhere x\b","variable / X costs"),(r"costs? .* more to cast","cost increases"),(r"costs? .* less to cast","cost reductions"),
      (r"\btarget\b","target legality"),(r"\btargets\b|up to (?:two|three|four|five) target","multiple targets"),(r"divided as you choose|divide .* among","distributed targets"),(r"change the target|new target","retargeting"),(r"choose (?:one|two|three|four)|choose one or more|choose two","modes"),(r"\bmay\b","optional `may` choices"),
      (r"\bwhenever\b|\bwhen\b|\bat the beginning\b|\bat end of combat\b|\bat the end step\b","normal triggers"),(r"at the beginning of the next|at the beginning of your next|at the beginning of that player's next","delayed triggers"),(r"\bif\b.*\bwhen\b|\bwhen\b.*\bif\b|\bwhenever\b.*\bif\b","intervening-if clauses"),(r"triggers? an additional time|triggers? twice","trigger multiplication / duplication"),
      (r"\binstead\b","replacement effects"),(r"\bprevent\b","prevention effects"),(r"\blibrary\b","library"),(r"\bhand\b","hand"),(r"\bbattlefield\b","battlefield"),(r"\bgraveyard\b","graveyard"),(r"\bexile\b|\bexiled\b","exile"),(r"\bcommand zone\b","command zone"),(r"search (?:your|their|that player's|its) library","search"),(r"\bshuffle\b","shuffle"),(r"\bmill\b","mill"),(r"\breveal\b","reveal"),(r"return .* from .*graveyard|from your graveyard to|from a graveyard to","recursion"),(r"exile .* then return|until .* leaves|card exiled with","linked objects"),
      (r"\battack(?:s|ing)?\b|declared as an attacker","declaring attackers"),(r"\bblock(?:s|ed|ing)?\b","blockers"),(r"\bflying\b|\bmenace\b|\breach\b|\btrample\b|can't be blocked","evasion"),(r"\bfirst strike\b","first strike"),(r"\bdouble strike\b","double strike"),(r"combat damage","combat damage assignment"),(r"deals? .* damage|damage to","noncombat damage"),(r"\bdeathtouch\b","deathtouch"),(r"\blifelink\b","lifelink"),(r"\bpartner\b","Partner"),(r"\bcommander\b","commander designation"),(r"each opponent","each player / each opponent"),(r"each opponent|opponents?","multiple opponents"),(r"\breveal\b|look at the top|look at .* hand","reveal boundaries"),(r"random(?:ly)?","random choices")]
    for pat,path in rules:
        if re.search(pat,t,re.I): add(ev,path,"AUTHORITY_DERIVED",f"explicit Oracle construct matched /{pat}/")
    if "saga" in tyl: add(ev,"Sagas","AUTHORITY_DERIVED","official type line contains Saga")
    if "planeswalker" in tyl: add(ev,"planeswalkers / loyalty abilities","AUTHORITY_DERIVED","official type line contains Planeswalker")
    if len(rec.get("faces",[]))>1:
        if "//" in rec.get("project_card_identity",""): add(ev,"split cards","HEURISTIC_DISCOVERY_ONLY","project identity uses //; exact special-form subtype requires rules/type adjudication")
        add(ev,"double-faced / transforming cards","HEURISTIC_DISCOVERY_ONLY","multiple official faces; subtype must be confirmed from explicit Oracle/rulings")
    if "transform" in t or "transformed" in t: add(ev,"double-faced / transforming cards","AUTHORITY_DERIVED","Oracle text explicitly says transform/transformed")
    if "adventure" in tyl or "adventure" in t: add(ev,"other special forms reachable in the actual-card universe","AUTHORITY_DERIVED","official field explicitly contains Adventure")
    if "meld" in t or "aftermath" in t or "fuse" in t: add(ev,"other special forms reachable in the actual-card universe","AUTHORITY_DERIVED","Oracle text explicitly names meld/aftermath/fuse")
    heur=[(r"\bdies\b","zone-change semantics"),(r"\bdraw\b","hidden library information"),(r"\bcounter on\b|\bcounters on\b","counters"),(r"attach|equipped|enchanted","attachments"),(r"copy (?:target|that|it|this)","copies"),(r"gets? [+-]\d|base power|base toughness","power/toughness layers")]
    existing={(x["path"],x["classification"]) for x in ev}
    for pat,path in heur:
        if re.search(pat,t,re.I) and (path,"AUTHORITY_DERIVED") not in existing: add(ev,path,"HEURISTIC_DISCOVERY_ONLY",f"discovery-only match /{pat}/")
    seen=set(); out=[]
    for x in ev:
        k=(x["path"],x["classification"])
        if k not in seen: seen.add(k); out.append(x)
    return out

def raw_source_digest(rec):
    vals=[f.get("raw_html_sha256") for f in rec.get("faces",[]) if f.get("raw_html_sha256")]
    return hashlib.sha256(("\n".join(vals)+"\n").encode()).hexdigest() if vals else None

def authority_digest(rec):
    obj={"semantic_identity":rec["semantic_identity"],"project_card_identity":rec["project_card_identity"],"status":rec.get("acquisition_status"),"faces":[{"name":f.get("current_gatherer_card_name"),"url":f.get("official_gatherer_url"),"mana_cost":f.get("mana_cost"),"colors":f.get("colors"),"color_indicator":f.get("color_indicator"),"type_line":f.get("type_line"),"oracle_text":f.get("oracle_text"),"power_toughness":f.get("power_toughness"),"loyalty":f.get("loyalty"),"defense":f.get("defense"),"rulings":f.get("official_rulings",[])} for f in rec.get("faces",[])]}
    return hjson(obj)

def merge_shards(shard_dir,manifest):
    by={}; files=sorted(p for p in Path(shard_dir).rglob("*.json") if "checkpoint" not in p.name.casefold() and "checkpoints" not in str(p).casefold())
    for p in files:
        try: d=read_json(p)
        except Exception: continue
        if d.get("schema_version")!="commander-lab.ws31.gatherer-shard/1.0.0": continue
        for r in d.get("records",[]):
            sid=r.get("semantic_identity")
            if sid in by: raise SystemExit(f"duplicate shard semantic identity: {sid}")
            by[sid]=r
    out=[]
    for src in manifest["records"]:
        sid=src["semantic_identity"]
        r=by.get(sid,{**src,"acquisition_status":"UNKNOWN","terminal":True,"faces":[],"face_relation":"UNKNOWN","special_structure_hints":[],"failure_reason":"NO_SHARD_RECORD_MATERIALIZED","authority_scope":"OFFICIAL_GATHERER_IDENTITY_AND_ORACLE_ONLY_NO_RUNTIME_CREDIT"})
        if r.get("acquisition_status") not in TERMINAL: r["acquisition_status"]="UNKNOWN"; r["terminal"]=True; r["failure_reason"]="NON_TERMINAL_SHARD_STATUS_FAIL_CLOSED_TO_UNKNOWN"
        out.append(r)
    if len(out)!=1385 or len({r["semantic_identity"] for r in out})!=1385: raise SystemExit("1,385 denominator/uniqueness failure")
    return out

def ws29_regression(records,baseline):
    by={norm(r["project_card_identity"]):r for r in records}; rows=[]
    for b in baseline["records"]:
        r=by.get(norm(b["card_name"])); issues=[]
        if b.get("authority_status")!="FULL_CURRENT_ORACLE_LOCK": issues.append("WS29_BASELINE_AUTHORITY_NOT_PASS")
        if b.get("discriminator_authority")!="PASS": issues.append("WS29_DISCRIMINATOR_BASELINE_NOT_PASS")
        if not r: issues.append("IDENTITY_MISSING")
        else:
            if r.get("acquisition_status")!="PASS": issues.append("CURRENT_AUTHORITY_NOT_PASS")
            nf={norm(f.get("current_gatherer_card_name") or f.get("requested_face_name") or ""):f for f in r.get("faces",[])}; want={norm(f["face_name"]):f for f in b["faces"]}
            if set(nf)!=set(want): issues.append("FACE_MAPPING_DRIFT")
            for k,w in want.items():
                f=nf.get(k)
                if not f: continue
                if htext(f.get("oracle_text"))!=w["oracle_text_sha256"]: issues.append(f"ORACLE_TEXT_DRIFT:{w['face_name']}")
                if htext(f.get("type_line"))!=w["type_line_sha256"]: issues.append(f"TYPE_LINE_DRIFT:{w['face_name']}")
        rows.append({"fixture_id":b["fixture_id"],"card_name":b["card_name"],"status":"PASS" if not issues else "FAIL","issues":issues})
    return {"schema_version":"commander-lab.ws31.ws29-regression/1.0.0","record_count":29,"pass_count":sum(x["status"]=="PASS" for x in rows),"discriminator_authority_pass_count":sum(1 for b in baseline["records"] if b.get("discriminator_authority")=="PASS"),"runtime_pass_lock":baseline.get("runtime_pass_lock"),"status":"PASS" if all(x["status"]=="PASS" for x in rows) else "FAIL","records":rows,"runtime_status_note":"Authority regression only. CARD_02/04/24 runtime classifications are frozen from WS-29 and are not promoted or re-adjudicated."}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",required=True); ap.add_argument("--shard-dir",required=True); ap.add_argument("--cr",required=True); ap.add_argument("--taxonomy",required=True); ap.add_argument("--ws29-baseline",required=True); ap.add_argument("--outdir",required=True); a=ap.parse_args()
    outdir=Path(a.outdir); outdir.mkdir(parents=True,exist_ok=True); manifest=read_json(a.manifest); records=merge_shards(a.shard_dir,manifest)
    for r in records: r["raw_source_digest"]=raw_source_digest(r); r["identity_authority_digest"]=authority_digest(r); r["rules_path_incidence"]=derive_incidence(r)
    full={"schema_version":"commander-lab.ws31.known-actual-card-oracle/1.0.0","authority_scope":"official Wizards authority/domain truth only; runtime_functionality_credit=0","record_count":1385,"records":records}; write_json(outdir/"KNOWN_ACTUAL_CARD_ORACLE_1385.json",full)
    write_json(outdir/"ACQUISITION_STATUS_MANIFEST.json",{"schema_version":"commander-lab.ws31.acquisition-status/1.0.0","record_count":1385,"records":[{"semantic_identity":r["semantic_identity"],"project_card_identity":r["project_card_identity"],"status":r["acquisition_status"],"failure_reason":r.get("failure_reason")} for r in records]})
    subsets={"PHYSICAL_CARD_ORACLE_1338.json":("physical",1338),"CURRENT_ROGSHAI_ORACLE.json":("current_rogshai",87),"CURRENT_KAERVEK_ORACLE.json":("current_kaervek",77)}; subset_stats={}
    for fn,(flag,count) in subsets.items():
        rs=[r for r in records if r.get("memberships",{}).get(flag)]
        if len(rs)!=count: raise SystemExit(f"subset {flag} denominator drift")
        d={"schema_version":f"commander-lab.ws31.{flag}-oracle/1.0.0","expected_count":count,"record_count":len(rs),"pass_count":sum(r["acquisition_status"]=="PASS" for r in rs),"unknown_count":sum(r["acquisition_status"]=="UNKNOWN" for r in rs),"fail_closed_count":sum(r["acquisition_status"]=="FAIL_CLOSED" for r in rs),"records":rs}; d["status"]="PASS" if d["pass_count"]==count else "UNKNOWN"; write_json(outdir/fn,d); subset_stats[flag]=d
    multiface=[r for r in records if len(r.get("faces",[]))>1 or "//" in r["project_card_identity"] or r.get("special_structure_hints")]; mf_rows=[]
    for r in multiface:
        expected=len([x for x in r["project_card_identity"].split("//") if x.strip()]) if "//" in r["project_card_identity"] else None; issues=[]
        if r["acquisition_status"]!="PASS": issues.append("IDENTITY_AUTHORITY_NOT_PASS")
        if expected and len(r.get("faces",[]))<expected: issues.append("EXPLICIT_FACE_UNRESOLVED")
        mf_rows.append({"semantic_identity":r["semantic_identity"],"project_card_identity":r["project_card_identity"],"face_relation":r.get("face_relation"),"face_count":len(r.get("faces",[])),"faces":[f.get("current_gatherer_card_name") or f.get("requested_face_name") for f in r.get("faces",[])],"special_structure_hints":r.get("special_structure_hints",[]),"status":"PASS" if not issues else "UNKNOWN","issues":issues})
    mf={"schema_version":"commander-lab.ws31.multiface-authority/1.0.0","record_count":len(mf_rows),"pass_count":sum(x["status"]=="PASS" for x in mf_rows),"unresolved_count":sum(x["status"]!="PASS" for x in mf_rows),"status":"PASS" if all(x["status"]=="PASS" for x in mf_rows) else "UNKNOWN","records":mf_rows}; write_json(outdir/"MULTIFACE_AUTHORITY.json",mf)
    taxonomy=read_json(a.taxonomy); allowed={p for c in taxonomy["categories"] for p in c["paths"]}; inc_rows=[]
    for r in records:
        auth=[x for x in r["rules_path_incidence"] if x["classification"]=="AUTHORITY_DERIVED" and x["path"] in allowed]; heur=[x for x in r["rules_path_incidence"] if x["classification"]=="HEURISTIC_DISCOVERY_ONLY" and x["path"] in allowed]; st="UNKNOWN" if r["acquisition_status"]!="PASS" or heur else "PASS"; inc_rows.append({"semantic_identity":r["semantic_identity"],"project_card_identity":r["project_card_identity"],"status":st,"authority_derived":auth,"heuristic_discovery_only":heur})
    inc={"schema_version":"commander-lab.ws31.rules-path-incidence/1.0.0","taxonomy_path_count":len(allowed),"record_count":1385,"unresolved_mapping_count":sum(x["status"]!="PASS" for x in inc_rows),"records":inc_rows}; inc["status"]="PASS" if inc["unresolved_mapping_count"]==0 else "UNKNOWN"; write_json(outdir/"CARD_RULES_PATH_INCIDENCE.json",inc)
    write_json(outdir/"WS11_HELPER_DELTA.json",{"schema_version":"commander-lab.ws31.ws11-delta/1.0.0","status":"UNKNOWN","reason":"UNKNOWN_EXACT_PRIOR_WS11_MATRIX_NOT_RECOVERED","added_paths":None,"removed_paths":None,"changed_multiface_mappings":None,"unresolved_mappings":inc["unresolved_mapping_count"],"note":"WS-11 helper matrix was SOURCE_DERIVED; no added/removed claims are fabricated without the exact prior card-by-card matrix."})
    baseline=load_zjson(a.ws29_baseline); reg=ws29_regression(records,baseline); write_json(outdir/"WS29_REGRESSION.json",reg)
    cr=read_json(a.cr); pdf=cr.get("sources",{}).get("pdf",{}); cr_status="PASS" if cr.get("official_cr_raw_bytes")=="PASS" and pdf.get("sha256")==EXPECTED_CR and pdf.get("http_status")==200 else "FAIL"; write_json(outdir/"CURRENT_CR_LOCK.json",{"schema_version":"commander-lab.ws31.current-cr-lock/1.0.0","status":cr_status,"expected_sha256":EXPECTED_CR,"observed_sha256":pdf.get("sha256"),"retrieved_at_utc":pdf.get("retrieved_at_utc"),"official_url":pdf.get("final_url")})
    terminal=sum(r.get("terminal") and r["acquisition_status"] in TERMINAL for r in records); passes=sum(r["acquisition_status"]=="PASS" for r in records); unknown=sum(r["acquisition_status"]=="UNKNOWN" for r in records); fails=sum(r["acquisition_status"]=="FAIL_CLOSED" for r in records); aggregate=hashlib.sha256(("\n".join(r["semantic_identity"]+" "+r["identity_authority_digest"] for r in sorted(records,key=lambda x:x["semantic_identity"]))+"\n").encode()).hexdigest()
    write_json(outdir/"ORACLE_INVALIDATION_MODEL.json",{"schema_version":"commander-lab.ws31.oracle-invalidation/1.0.0","identity_manifest_digest":manifest.get("name_set_sha256"),"aggregate_domain_digest":aggregate,"current_cr_digest":pdf.get("sha256"),"rule":"Any later changed per-card raw source digest, identity authority digest, aggregate domain digest, or current CR digest invalidates dependent runtime qualification PASS until rerun.","records":[{"semantic_identity":r["semantic_identity"],"raw_source_digest":r.get("raw_source_digest"),"identity_authority_digest":r["identity_authority_digest"],"retrieval_timestamps_utc":[f.get("retrieval_timestamp_utc") for f in r.get("faces",[]) if f.get("retrieval_timestamp_utc")]} for r in records]})
    coverage={"schema_version":"commander-lab.ws31.coverage/1.0.0","known_actual_identities":1385,"physical_identities":1338,"current_rogshai":87,"current_kaervek":77,"terminal_acquisition_records":terminal,"authority_pass":passes,"authority_unknown":unknown,"authority_fail_closed":fails,"gatherer_acquisition_failures":unknown+fails,"multiface_count":len(mf_rows),"multiface_unresolved_count":mf["unresolved_count"],"rules_path_incidence_unresolved_count":inc["unresolved_mapping_count"],"rogshai_pass":subset_stats["current_rogshai"]["pass_count"],"kaervek_pass":subset_stats["current_kaervek"]["pass_count"],"physical_pass":subset_stats["physical"]["pass_count"],"ws29_regression":reg["status"],"current_cr_lock":cr_status,"aggregate_domain_digest":aggregate,"runtime_functionality_credit":0}
    full_pass=(terminal==1385 and passes==1385 and coverage["rogshai_pass"]==87 and coverage["kaervek_pass"]==77 and mf["unresolved_count"]==0 and inc["unresolved_mapping_count"]==0 and reg["status"]=="PASS" and cr_status=="PASS"); hard_close=(terminal==1385 and coverage["rogshai_pass"]==87 and coverage["kaervek_pass"]==77 and mf["unresolved_count"]==0 and reg["status"]=="PASS" and cr_status=="PASS"); coverage["overall_authority_status"]="PASS" if full_pass else "UNKNOWN"; coverage["workstream_close_gate"]="PASS" if hard_close else "FAIL"; write_json(outdir/"COVERAGE.json",coverage)
    result={"schema_version":"commander-lab.ws31.result/1.0.0","workstream_status":"PASS_CLOSED" if full_pass else ("UNKNOWN_CLOSED" if hard_close else "OPEN"),"coverage":coverage,"source_lock_commit":manifest.get("source_lock_commit"),"no_rules_core_selected":True,"candidate_engine_changes":0}; write_json(outdir/"WS31_RESULT.json",result); full["overall_authority_status"]=coverage["overall_authority_status"]; full["aggregate_domain_digest"]=aggregate; full["runtime_functionality_credit"]=0; write_json(outdir/"KNOWN_ACTUAL_CARD_ORACLE_1385.json",full)
    sums=[f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in sorted(outdir.glob("*.json"))]; (outdir/"SHA256SUMS").write_text("\n".join(sums)+"\n",encoding="utf-8"); print(json.dumps(result,sort_keys=True))
    if os.environ.get("WS31_REQUIRE_CLOSE")=="1" and not hard_close: return 4
    if os.environ.get("WS31_REQUIRE_FULL_PASS")=="1" and not full_pass: return 5
    return 0
if __name__=="__main__": raise SystemExit(main())
