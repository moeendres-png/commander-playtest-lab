#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, io, json, math, os, re, urllib.request, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_BRANCH = "runs/rogshai-48-structural-12opp-20260825"
EVIDENCE = "structural_model_estimates"
FOCUS = {"C011","C020","C029","C030","C043","C044","C048"}

def api_json(url, token):
    req=urllib.request.Request(url, headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req) as r: return json.load(r)

def api_bytes(url, token):
    req=urllib.request.Request(url, headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req) as r: return r.read()

def list_artifacts(repo, token):
    out=[]; page=1
    while True:
        d=api_json(f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&page={page}",token)
        a=d.get("artifacts",[]); out.extend(a)
        if len(a)<100: break
        page+=1
    return [x for x in out if not x.get("expired",False)]

def choose_artifact(artifacts, patterns):
    hits=[]
    for a in artifacts:
        n=a["name"]
        if any(re.fullmatch(p,n) for p in patterns):
            wr=a.get("workflow_run") or {}
            if wr.get("head_branch") in (None, REPO_BRANCH): hits.append(a)
    if not hits: raise RuntimeError(f"No live artifact matches {patterns}")
    hits.sort(key=lambda a:(a.get("created_at",""),a["id"]), reverse=True)
    return hits

def extract_candidate_artifact(candidates, repo, token, target, label):
    import shutil
    errors=[]
    for a in candidates:
        try:
            blob=api_bytes(f"https://api.github.com/repos/{repo}/actions/artifacts/{a['id']}/zip",token)
            with zipfile.ZipFile(io.BytesIO(blob)) as z: z.extractall(target)
            game_files=list(target.rglob("GAME_RESULTS.jsonl")); report_files=list(target.rglob("RUN_REPORT.json")); sched_files=list(target.rglob("SEED_SCHEDULE.json"))
            if len(game_files)!=1 or len(report_files)!=1 or len(sched_files)!=1: raise RuntimeError(f"expected one GAME_RESULTS/RUN_REPORT/SEED_SCHEDULE, got {len(game_files)}/{len(report_files)}/{len(sched_files)}")
            report=json.loads(report_files[0].read_text())
            assert report["evidence_class"]==EVIDENCE
            assert report["candidate_count"]==48 and report["games_per_candidate"]==16
            assert report["target_game_count"]==768 and report["completed_game_count"]==768 and report["aborted_game_count"]==0
            assert report["pre_gameplay_candidate_elimination"]==0 and report["pairwise_rows"]==1128 and report["pod_size"]==4 and len(report["opponent_ids"])==12
            rows=[json.loads(line) for line in game_files[0].read_text().splitlines() if line.strip()]
            assert len(rows)==768
            return a,rows,json.loads(sched_files[0].read_text()),report
        except Exception as e:
            errors.append((a["id"],a["name"],repr(e)))
            for p in list(target.iterdir()): shutil.rmtree(p) if p.is_dir() else p.unlink()
    raise RuntimeError(f"No valid artifact for {label}: {errors}")

def getv(row,names,required=True):
    for n in names:
        if n in row:return row[n]
    if required: raise KeyError(f"none of {names} in row keys {sorted(row)}")
    return None

ID_KEYS=["candidate_id"]; SEAT_KEYS=["candidate_seat"]; SEED_KEYS=["master_seed","seed","scenario_seed"]
PLACEMENT_KEYS=["candidate_placement","placement"]; FIRST_KEYS=["candidate_first_place","structural_first_place","first_place","place_1"]
DAMAGE_KEYS=["candidate_damage","damage","total_damage","damage_dealt"]; DRAW_KEYS=["candidate_cards_drawn","cards_drawn"]; TURN_KEYS=["turns","game_turns","turn_count"]
EXCLUDE_NUMERIC_FRAGMENTS=("seed","seat","index","id","hash","count","size","version","max_turn","game_number","scheduled","completed","aborted")
def numeric_metrics(row):
    out={}
    for k,v in row.items():
        if isinstance(v,bool): continue
        if isinstance(v,(int,float)) and math.isfinite(float(v)) and not any(f in k.lower() for f in EXCLUDE_NUMERIC_FRAGMENTS): out[k]=float(v)
    return out

def mean(xs): return sum(xs)/len(xs) if xs else float("nan")
def sign(x,tol=1e-12): return 1 if x>tol else (-1 if x<-tol else 0)
def write_csv(path,rows,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo",required=True); ap.add_argument("--output",required=True); args=ap.parse_args()
    token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token: raise RuntimeError("GH_TOKEN/GITHUB_TOKEN required")
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True); temp=out/"_recovered"; temp.mkdir(exist_ok=True)
    artifacts=list_artifacts(args.repo,token); selected=[]; allrows=[]
    specs=[("R1",1,[r"rogshai-structural-12opp-block-1-repair-[0-9a-f]+"]),("R1",2,[r"rogshai-structural-12opp-block-2-repair-v2-[0-9a-f]+"])]
    specs += [("R1",b,[rf"rogshai-structural-12opp-block-{b}-[0-9a-f]+"]) for b in range(3,9)]
    specs += [("R2",b,[rf"rogshai-structural-12opp-replication2-block-{b}-[0-9a-f]+"]) for b in range(9,17)]
    for rep,b,patterns in specs:
        d=temp/f"{rep}_B{b:02d}"; d.mkdir(parents=True,exist_ok=True)
        a,rows,schedule,report=extract_candidate_artifact(choose_artifact(artifacts,patterns),args.repo,token,d,f"{rep} B{b}")
        selected.append({"replication":rep,"block":b,"artifact_id":a["id"],"artifact_name":a["name"],"created_at":a.get("created_at"),"game_rows":len(rows)})
        for r in rows: r=dict(r); r["_replication"]=rep; r["_block"]=b; allrows.append(r)
    assert len(allrows)==12288
    ids=sorted({str(getv(r,ID_KEYS)) for r in allrows}); assert ids==[f"C{i:03d}" for i in range(1,49)]
    assert set(Counter(str(getv(r,ID_KEYS)) for r in allrows).values())=={256}
    assert set(Counter((str(getv(r,ID_KEYS)),int(getv(r,SEAT_KEYS))) for r in allrows).values())=={64}
    eclasses={r.get("evidence_class") for r in allrows if "evidence_class" in r}
    if eclasses: assert eclasses=={EVIDENCE}
    sample=allrows[0]
    id_key=next(k for k in ID_KEYS if k in sample); seat_key=next(k for k in SEAT_KEYS if k in sample)
    seed_key=next((k for k in SEED_KEYS if k in sample),None); placement_key=next((k for k in PLACEMENT_KEYS if k in sample),None); first_key=next((k for k in FIRST_KEYS if k in sample),None)
    damage_key=next((k for k in DAMAGE_KEYS if k in sample),None); draw_key=next((k for k in DRAW_KEYS if k in sample),None); turn_key=next((k for k in TURN_KEYS if k in sample),None)
    if not seed_key or not placement_key or not first_key: raise RuntimeError(f"Required fields absent; keys={sorted(sample)} resolved seed={seed_key} placement={placement_key} first={first_key}")
    common_metrics=set(numeric_metrics(sample))
    for r in allrows[1:]: common_metrics &= set(numeric_metrics(r))
    for k in (damage_key,draw_key,turn_key):
        if k and all(isinstance(r.get(k),(int,float)) and not isinstance(r.get(k),bool) for r in allrows): common_metrics.add(k)
    common_metrics.discard(placement_key); common_metrics.discard(first_key); metrics=sorted(common_metrics)
    scenario_groups=defaultdict(list)
    for r in allrows: scenario_groups[(r["_replication"],r["_block"],r[seed_key],int(r[seat_key]))].append(r)
    assert len(scenario_groups)==256 and not [(k,len(v)) for k,v in scenario_groups.items() if len(v)!=48]
    for rows in scenario_groups.values(): assert len({r[id_key] for r in rows})==48
    idx={}
    for r in allrows:
        sk=(r["_replication"],r["_block"],r[seed_key],int(r[seat_key])); key=(str(r[id_key]),sk); assert key not in idx; idx[key]=r
    pairseat=[]; pairclass=[]; cc={c:Counter() for c in ids}; focus_pairs=set()
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            sr=[]
            for seat in (1,2,3,4):
                scenarios=sorted(k for k in scenario_groups if k[3]==seat); assert len(scenarios)==64
                pd=[]; fd=[]; md={m:[] for m in metrics}; rd={"R1":[],"R2":[]}; wins=ties=losses=0
                for sk in scenarios:
                    ra=idx[(a,sk)]; rb=idx[(b,sk)]; pa=float(ra[placement_key]); pb=float(rb[placement_key]); pd.append(pa-pb)
                    if pa<pb:wins+=1
                    elif pa>pb:losses+=1
                    else:ties+=1
                    fd.append(float(ra[first_key])-float(rb[first_key])); rd[sk[0]].append(pb-pa)
                    for m in metrics: md[m].append(float(ra[m])-float(rb[m]))
                pdelta=mean(pd); padv=-pdelta
                row={"candidate_a":a,"candidate_b":b,"seat":seat,"n_paired":64,"a_minus_b_placement":pdelta,"placement_advantage_a":padv,"paired_placement_wins_a":wins,"paired_placement_ties":ties,"paired_placement_losses_a":losses,"a_minus_b_first_place":mean(fd),"r1_placement_advantage_a":mean(rd["R1"]),"r2_placement_advantage_a":mean(rd["R2"]),"replication_sign_agreement":sign(mean(rd["R1"]))==sign(mean(rd["R2"])),"evidence_class":EVIDENCE}
                for m in metrics: row[f"a_minus_b_{m}"]=mean(md[m])
                pairseat.append(row); sr.append(row)
            signs=[sign(r["placement_advantage_a"]) for r in sr]; nz=[s for s in signs if s]; absvals=[abs(r["placement_advantage_a"]) for r in sr]; conc=max(absvals)/sum(absvals) if sum(absvals)>0 else 0.0
            if 1 in signs and -1 in signs: cls="sign-reversing"
            elif not nz: cls="unresolved"
            elif len(nz)<4: cls="seat-dependent"
            else: cls="seat-consistent"
            single=conc>=0.60 and sum(absvals)>0
            direction="A" if nz and all(s>=0 for s in signs) and 1 in signs else ("B" if nz and all(s<=0 for s in signs) and -1 in signs else "mixed_or_none")
            pc={"candidate_a":a,"candidate_b":b,"classification":cls,"direction_if_nonreversing":direction,"seat1_placement_advantage_a":sr[0]["placement_advantage_a"],"seat2_placement_advantage_a":sr[1]["placement_advantage_a"],"seat3_placement_advantage_a":sr[2]["placement_advantage_a"],"seat4_placement_advantage_a":sr[3]["placement_advantage_a"],"single_seat_concentration":conc,"single_seat_driven_ge_0_60":single,"replication_sign_agreement_seats":sum(bool(r["replication_sign_agreement"]) for r in sr),"evidence_class":EVIDENCE}
            pairclass.append(pc)
            if cls=="seat-consistent":
                if direction=="A": cc[a]["seat_consistent_favorable"]+=1; cc[b]["seat_consistent_unfavorable"]+=1
                elif direction=="B": cc[b]["seat_consistent_favorable"]+=1; cc[a]["seat_consistent_unfavorable"]+=1
            elif cls=="sign-reversing": cc[a]["sign_reversing"]+=1; cc[b]["sign_reversing"]+=1
            elif cls=="seat-dependent": cc[a]["seat_dependent"]+=1; cc[b]["seat_dependent"]+=1
            else: cc[a]["unresolved"]+=1; cc[b]["unresolved"]+=1
            if single: cc[a]["single_seat_driven_pairs"]+=1; cc[b]["single_seat_driven_pairs"]+=1
            if a in FOCUS or b in FOCUS: focus_pairs.add((a,b))
    assert len(pairseat)==4512 and len(pairclass)==1128
    write_csv(out/"PAIRWISE_SEAT_MATRIX.csv",pairseat,list(pairseat[0])); write_csv(out/"PAIR_CLASSIFICATION.csv",pairclass,list(pairclass[0]))
    csum=[]
    for c in ids:
        x=cc[c]; csum.append({"candidate_id":c,"seat_consistent_favorable_pairs":x["seat_consistent_favorable"],"seat_consistent_unfavorable_pairs":x["seat_consistent_unfavorable"],"sign_reversing_pairs":x["sign_reversing"],"seat_dependent_pairs":x["seat_dependent"],"unresolved_pairs":x["unresolved"],"single_seat_driven_pairs_ge_0_60":x["single_seat_driven_pairs"],"total_pairs":47,"evidence_class":EVIDENCE})
    write_csv(out/"CANDIDATE_SEAT_CONSISTENCY_SUMMARY.csv",csum,list(csum[0]))
    write_csv(out/"FOCUS_PAIRWISE_SEAT_MATRIX.csv",[r for r in pairseat if (r["candidate_a"],r["candidate_b"]) in focus_pairs],list(pairseat[0]))
    write_csv(out/"FOCUS_PAIR_CLASSIFICATION.csv",[r for r in pairclass if (r["candidate_a"],r["candidate_b"]) in focus_pairs],list(pairclass[0]))
    write_csv(out/"CONTROL_COMPARISONS_C043_C048.csv",[r for r in pairseat if r["candidate_a"] in {"C043","C048"} or r["candidate_b"] in {"C043","C048"}],list(pairseat[0]))
    meta={"generated_at":datetime.now(timezone.utc).isoformat(),"analysis_type":"seat_stratified_pairwise_reanalysis_existing_games_only","new_games_generated":False,"selected_artifacts":selected,"total_existing_game_rows":12288,"replications":{"R1":6144,"R2":6144},"candidates":48,"pairs":1128,"pairwise_seat_rows":4512,"games_per_candidate":256,"games_per_candidate_per_seat":64,"pairing_key":["_replication","_block",seed_key,seat_key],"resolved_fields":{"candidate_id":id_key,"seat":seat_key,"seed":seed_key,"placement":placement_key,"first_place":first_key,"damage":damage_key,"cards_drawn":draw_key,"turns":turn_key},"additional_numeric_metrics":metrics,"classification":{"sign-reversing":"at least one seat favors A and at least one favors B on mean paired placement advantage","unresolved":"all four seat mean paired placement advantages are exactly zero","seat-dependent":"only one placement direction is observed, but at least one seat is exactly zero","seat-consistent":"all four seats have the same nonzero direction","single_seat_driven_ge_0_60":"separate descriptive flag: one seat contributes >=60% of total absolute seat-wise mean placement advantage; not a significance threshold"},"placement_sign":"placement_advantage_a = mean(B placement - A placement); positive means A placed better","first_sign":"a_minus_b_first_place = mean(A first indicator - B first indicator); positive means A more firsts","other_metric_sign":"a_minus_b_<metric> = mean(A - B)","evidence_class":EVIDENCE,"fidelity_limits":["Historical Structural simulator evidence only; not empirical Commander win rate.","The source simulator failed a later structural seat-symmetry audit (0/24 permutation comparisons equivariant before fix).","Seat stratification diagnoses robustness to the observed seat artifact but cannot statistically repair or erase the underlying technical bias.","No overall candidate rank is produced.","Common-seed pairing controls scenario randomness only within the frozen historical design; it does not establish an external rules-engine CRN guarantee."]}
    (out/"ANALYSIS_MANIFEST.json").write_text(json.dumps(meta,indent=2,sort_keys=True)); (out/"RAW_ROW_SCHEMA.json").write_text(json.dumps({"keys":sorted(sample),"sample_types":{k:type(v).__name__ for k,v in sample.items()}},indent=2,sort_keys=True)); (out/"SELECTED_ARTIFACTS.json").write_text(json.dumps(selected,indent=2))
    cls_count=Counter(r["classification"] for r in pairclass); mc=sorted(csum,key=lambda r:(-r["seat_consistent_favorable_pairs"],r["candidate_id"])); ms=sorted(csum,key=lambda r:(-r["single_seat_driven_pairs_ge_0_60"],r["candidate_id"]))
    lines=["# Seat-stratified pairwise reanalysis","","**Evidence class:** `structural_model_estimates`  ","**New games generated:** `FALSE`  ","**Existing rows consumed:** `12,288`","","## Pair classification counts",*[f"- {k}: {cls_count[k]}" for k in ("seat-consistent","seat-dependent","sign-reversing","unresolved")],"","## Candidates with most seat-consistent favorable pair relations","Descriptive counts only; this is not an overall rank.","","|Candidate|Seat-consistent favorable|Seat-consistent unfavorable|Sign-reversing|Seat-dependent|Single-seat-driven|","|---|---:|---:|---:|---:|---:|"]
    for r in mc[:15]: lines.append(f"|{r['candidate_id']}|{r['seat_consistent_favorable_pairs']}|{r['seat_consistent_unfavorable_pairs']}|{r['sign_reversing_pairs']}|{r['seat_dependent_pairs']}|{r['single_seat_driven_pairs_ge_0_60']}|")
    lines += ["","## Candidates with most single-seat-concentrated pair relations","The >=0.60 concentration flag is descriptive only, not a statistical significance rule.","","|Candidate|Single-seat-driven pairs|Seat-consistent favorable|Sign-reversing|","|---|---:|---:|---:|"]
    for r in ms[:15]: lines.append(f"|{r['candidate_id']}|{r['single_seat_driven_pairs_ge_0_60']}|{r['seat_consistent_favorable_pairs']}|{r['sign_reversing_pairs']}|")
    lines += ["","## Fidelity limits",*["- "+x for x in meta["fidelity_limits"]]]; (out/"REPORT.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"status":"PASS","rows":12288,"pairwise_seat_rows":4512,"classification_counts":dict(cls_count),"metrics":metrics},indent=2))
if __name__=="__main__": main()
