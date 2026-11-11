#!/usr/bin/env python3
"""Audit 63 public Oracle IDs against official Scryfall Tagger Oracle Tags bulk data.

Output is dated provenance, never a strength score or a silent replacement
for the Oracle-text-derived (DERIVED_DESCRIPTIVE) classification.
"""
import argparse, csv, gzip, hashlib, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROLES={"ramp":"ramp","mana_rock":"mana-rock","mana_dork":"mana-dork",
"land_ramp":"land-ramp","card_draw":"draw","card_advantage":"card-advantage",
"cantrip":"cantrip","tutor":"tutor","removal":"removal","board_wipe":"board-wipe",
"counterspell":"counterspell","bounce":"bounce","flicker":"flicker",
"recursion":"recursion","protection":"protection","graveyard_hate":"graveyard-hate","lifegain":"lifegain"}
UA="CommanderStudioRoleAudit/1.0 (public source independent verification)"

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,application/gzip"})
    for i in range(5):
        try:
            with urllib.request.urlopen(req,timeout=90) as r:return r.read()
        except urllib.error.HTTPError as ex:
            if ex.code not in (429,500,502,503,504) or i==4:raise
            time.sleep(min(15,2**i+2))
    raise RuntimeError("unreachable")

def records(raw):
    data=gzip.decompress(raw) if raw[:2]==bytes.fromhex("1f8b") else raw
    if data.lstrip().startswith(b"["):return json.loads(data)
    return [json.loads(line) for line in data.splitlines() if line.strip()]

def slugify(label):
    return re.sub(r"[^a-z0-9-]+","-",label.lower().strip()).strip("-")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ids",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--bulk",default=None)
    a=p.parse_args()
    ids=[x.strip().lower() for x in Path(a.ids).read_text().splitlines() if x.strip()]
    if len(ids)!=63 or len(set(ids))!=63 or any(not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",x) for x in ids):
        raise ValueError("expected 63 unique valid oracle IDs")
    if a.bulk:
        meta={};source=Path(a.bulk).absolute().as_uri();raw=Path(a.bulk).read_bytes()
    else:
        meta=json.loads(get("https://api.scryfall.com/bulk-data/oracle_tags"))
        if meta.get("type")!="oracle_tags":raise ValueError("wrong Scryfall bulk type")
        source=meta.get("jsonl_download_uri") or meta.get("download_uri")
        loc=urllib.parse.urlsplit(str(source))
        if loc.scheme!="https" or loc.hostname!="data.scryfall.io" or "/oracle-tags/" not in loc.path:
            raise ValueError("unexpected bulk download URL")
        raw=get(source)
    sha=hashlib.sha256(raw).hexdigest()
    tag_records=records(raw)
    if not tag_records:raise ValueError("empty tag data")
    names=set(); members=defaultdict(set); tag_details=defaultdict(list); taggings_count=0
    for tag in tag_records:
        if not isinstance(tag,dict):continue
        label=tag.get("slug") or tag.get("label") or tag.get("name")
        if not isinstance(label,str) or not label.strip():continue
        key=slugify(label); names.add(key)
        t=tag.get("taggings")
        t=t if isinstance(t,list) else ([tag] if isinstance(tag.get("oracle_id"),str) else [])
        for link in t:
            if not isinstance(link,dict) or not isinstance(link.get("oracle_id"),str):continue
            taggings_count+=1
            oid=link["oracle_id"].lower()
            if oid in ids:
                members[oid].add(key)
                tag_details[oid].append({"label":label,"slug":key,"tag_id":tag.get("id"),"weight":link.get("weight")})
    if taggings_count==0:raise ValueError("no readable Oracle taggings; schema incompatible")
    if not names.intersection(ROLES.values()):raise ValueError("Studio 17 slugs not found in bulk corpus")
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    cols=["oracle_id","studio_role","tagger_slug","tagger_status","snapshot_updated_at","bulk_sha256"]
    matrix=[]; positives=[]; totals=Counter()
    for oid in ids:
        for role,slug in ROLES.items():
            status="TAG_SLUG_ABSENT_FROM_BULK" if slug not in names else ("TAGGER_CONFIRMED" if slug in members[oid] else "NOT_TAGGED_IN_SNAPSHOT")
            row=dict(zip(cols,[oid,role,slug,status,meta.get("updated_at") or "",sha]))
            matrix.append(row)
            if status=="TAGGER_CONFIRMED":
                positives.append(row);totals[role]+=1
    for name,rows in [("role63_tagger_17x63_matrix.csv",matrix),("role63_tagger_confirmed.csv",positives)]:
        with (out/name).open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
    (out/"role63_tagger_observed_labels.json").write_text(json.dumps(tag_details,ensure_ascii=False,indent=2)+"\n")
    result={"status":"OFFICIAL_BULK_VALIDATED" if not a.bulk else "OFFLINE_BULK_VALIDATED",
      "fetched_utc":datetime.now(timezone.utc).isoformat(),"bulk_updated_at":meta.get("updated_at"),
      "bulk_url":source if not a.bulk else None,"bulk_sha256":sha,
      "bulk_bytes":len(raw),"tag_records":len(tag_records),"taggings":taggings_count,
      "target_oracle_ids":len(ids),"tagger_labels_on_target_count":sum(bool(members[x]) for x in ids),
      "studio_role_positive_cards":sum(any(s in members[x] for s in ROLES.values()) for x in ids),
      "studio_role_positive_pairs":len(positives),"per_role_positive":dict(totals),
      "missing_studio_slugs":{r:s for r,s in ROLES.items() if s not in names},
      "absence_interpretation":"No tag at this snapshot is not proof of lack of card function"}
    (out/"role63_tagger_snapshot_metadata.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"tag_records":len(tag_records),"taggings":taggings_count,
          "positive_pairs":len(positives),"missing_slugs":result["missing_studio_slugs"]}))

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("TAGGER_NOT_VERIFIED: "+str(e),file=sys.stderr)
        raise
