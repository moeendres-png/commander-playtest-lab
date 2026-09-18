#!/usr/bin/env python3
"""Fetch the frozen WS-29 29-card corpus from public official Gatherer pages.

Ordinary public GET requests only. Raw HTML is hashed then discarded; the evidence
retains transport metadata plus bounded extracted Oracle-facing text. Split and
transforming cards are locked face-by-face.
"""
from __future__ import annotations
import hashlib, json, re, sys, time, unicodedata
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, build_opener

USER_AGENT=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36 Commander-Simulation-Foundry-WS29/1.0")
BASE="https://gatherer.wizards.com"
CORPUS=[
("CARD_01","Ishai, Ojutai Dragonspeaker"),("CARD_02","Rograkh, Son of Rohgahh"),
("CARD_03","Esior, Wardwing Familiar"),("CARD_04","Kediss, Emberclaw Familiar"),
("CARD_05","Veyran, Voice of Duality"),("CARD_06","Harmonic Prodigy"),
("CARD_07","Narset, Parter of Veils"),("CARD_08","Jeska, Thrice Reborn"),
("CARD_09","Magma Opus"),("CARD_10","Wash Away"),("CARD_11","Wear // Tear"),
("CARD_12","Dig Through Time"),("CARD_13","Flare of Duplication"),
("CARD_14","Vandalblast"),("CARD_15","Finale of Revelation"),
("CARD_16","Psychosis Crawler"),("CARD_17","Kaervek the Merciless"),
("CARD_18","Shriekmaw"),("CARD_19","Butcher of Malakir"),("CARD_20","Syphon Mind"),
("CARD_21","Gratuitous Violence"),("CARD_22","Bolt Bend"),("CARD_23","Makeshift Mannequin"),
("CARD_24","Warstorm Surge"),("CARD_25","Basilisk Collar"),("CARD_26","Burn Down the House"),
("CARD_27","Path of Ancestry"),("CARD_28","Find // Finality"),
("CARD_29","Boseiju Reaches Skyward // Branch of Boseiju")]
DETAIL_RE=re.compile(r'href=["\'](?P<href>/[A-Za-z0-9]+/en-us/\d+/[^"\']+)["\']',re.I)

def now_utc(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def normalize(s):
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode("ascii").lower().replace("//"," ")
    return re.sub(r"[^a-z0-9]+"," ",s).strip()
def slug_norm(href): return normalize(urlparse(href).path.rstrip("/").split("/")[-1])
def req(url): return Request(url,headers={"User-Agent":USER_AGENT,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"en-US,en;q=0.8"})
def fetch(url):
    at=now_utc()
    try:
        with build_opener().open(req(url),timeout=60) as r:
            b=r.read(); h=r.headers
            return b,{"requested_url":url,"retrieved_at_utc":at,"http_status":r.getcode(),"final_url":r.geturl(),"content_type":h.get("Content-Type"),"content_length":h.get("Content-Length"),"etag":h.get("ETag"),"last_modified":h.get("Last-Modified"),"raw_byte_count":len(b),"sha256":sha256_bytes(b),"transport_error":None}
    except HTTPError as e:
        b=e.read(); h=e.headers
        return b,{"requested_url":url,"retrieved_at_utc":at,"http_status":e.code,"final_url":e.geturl(),"content_type":h.get("Content-Type"),"content_length":h.get("Content-Length"),"etag":h.get("ETag"),"last_modified":h.get("Last-Modified"),"raw_byte_count":len(b),"sha256":sha256_bytes(b) if b else None,"transport_error":f"HTTPError: {e.code} {e.reason}"}
    except URLError as e:
        return b"",{"requested_url":url,"retrieved_at_utc":at,"http_status":None,"final_url":None,"content_type":None,"content_length":None,"etag":None,"last_modified":None,"raw_byte_count":None,"sha256":None,"transport_error":f"URLError: {e.reason}"}
def visible_text(b):
    s=b.decode("utf-8",errors="replace")
    s=re.sub(r"<script\b[^>]*>.*?</script>"," ",s,flags=re.I|re.S); s=re.sub(r"<style\b[^>]*>.*?</style>"," ",s,flags=re.I|re.S); s=re.sub(r"<[^>]+>"," ",s)
    return " ".join(unescape(s).split())
def discover_detail(html,face):
    hrefs=list(dict.fromkeys(m.group("href") for m in DETAIL_RE.finditer(html.decode("utf-8",errors="replace"))))
    target=normalize(face); toks=set(target.split())
    ranked=sorted(hrefs,key=lambda h:(slug_norm(h)==target,len(toks & set(slug_norm(h).split())),-abs(len(toks)-len(set(slug_norm(h).split())))),reverse=True)
    if not ranked: return None,[]
    best=ranked[0]; overlap=len(toks & set(slug_norm(best).split())); threshold=max(1,min(2,len(toks)))
    return (urljoin(BASE,best) if slug_norm(best)==target or overlap>=threshold else None),ranked[:10]
def extract_oracle_section(text,face):
    low=text.lower(); markers=["printed oracle card name","oracle card name","card name"]
    starts=[low.find(m) for m in markers if low.find(m)>=0]; start=min(starts) if starts else -1
    if start<0:
        n=low.find(face.lower().split(" // ")[0].lower()); excerpt=text[max(0,n-250):n+2500] if n>=0 else text[:2500]
        return {"oracle_section_present":False,"oracle_section":None,"diagnostic_excerpt":excerpt,"expected_name_present":normalize(face) in normalize(text),"rules_text_label_present":"rules text" in low,"rulings_label_present":"rulings" in low}
    ends=[i for i in (low.find("find articles",start),low.find("club support",start)) if i>start]; end=min(ends) if ends else min(len(text),start+14000)
    sec=text[start:end].strip(); seclow=sec.lower()
    return {"oracle_section_present":True,"oracle_section":sec[:14000],"diagnostic_excerpt":None,"expected_name_present":normalize(face) in normalize(sec),"rules_text_label_present":"rules text" in seclow,"rulings_label_present":"rulings" in seclow,"oracle_label_present":True,"oracle_label_observed":next((m for m in markers if m in seclow),None)}
def search_url(name): return f"{BASE}/search?searchTerm={quote(name,safe='')}"
def fetch_face(face):
    su=search_url(face); sb,sm=fetch(su); detail,cands=discover_detail(sb,face) if sm.get("http_status")==200 else (None,[])
    out={"face_name":face,"search":sm,"detail_candidates":cands,"detail":None,"status":"AUTHORITY_BLOCKED","blocker":None}
    if not detail:
        out["blocker"]="No matching public Gatherer detail URL discovered from face-name search."; return out
    time.sleep(.08); db,dm=fetch(detail); ex=extract_oracle_section(visible_text(db),face) if dm.get("http_status")==200 else {"oracle_section_present":False,"expected_name_present":False,"rules_text_label_present":False,"rulings_label_present":False,"oracle_section":None,"diagnostic_excerpt":None}
    dm["extracted"]=ex; out["detail"]=dm
    if dm.get("http_status")==200 and ex.get("oracle_section_present") and ex.get("expected_name_present") and ex.get("rules_text_label_present"):
        out["status"]="FULL_CURRENT_ORACLE_LOCK"
    else: out["blocker"]="Public Gatherer detail page did not expose a complete validated Oracle section for this face."
    return out

def main():
    outdir=Path(sys.argv[1] if len(sys.argv)>1 else "artifacts/ws29/gatherer"); outdir.mkdir(parents=True,exist_ok=True); records=[]
    for fid,name in CORPUS:
        faces=[x.strip() for x in name.split("//")]
        face_records=[]
        for face in faces:
            fr=fetch_face(face); face_records.append(fr); time.sleep(.08)
        full=all(fr["status"]=="FULL_CURRENT_ORACLE_LOCK" for fr in face_records)
        rec={"fixture_id":fid,"card_name":name,"faces":face_records,"search":face_records[0]["search"],"detail_candidates":face_records[0]["detail_candidates"],"detail":face_records[0]["detail"],"current_oracle_fetch_status":"FULL_CURRENT_ORACLE_LOCK" if full else "AUTHORITY_BLOCKED","blocker":None if full else "; ".join(f"{fr['face_name']}: {fr['blocker']}" for fr in face_records if fr['status']!="FULL_CURRENT_ORACLE_LOCK")}
        records.append(rec); print(f"{fid}: {rec['current_oracle_fetch_status']} faces={','.join(fr['status'] for fr in face_records)}",flush=True)
    report={"schema_version":"ws29-gatherer-corpus/1.2.0","retrieved_by":"public Gatherer face-name search -> public Gatherer detail page","authority_statement":"FULL_CURRENT_ORACLE_LOCK requires every relevant card face to return HTTP 200 with a validated current Oracle section from official Gatherer. Gatherer currently renders that section under either Printed Oracle Card Name or Card Name. This is authority only, never runtime evidence.","policy_note":"Ordinary public GET requests only; no authentication, CAPTCHA bypass, private API, reverse-engineered endpoint, or anti-bot circumvention. Raw HTML is hashed then discarded.","card_count":len(records),"full_current_oracle_lock_count":sum(r["current_oracle_fetch_status"]=="FULL_CURRENT_ORACLE_LOCK" for r in records),"records":records}
    p=outdir/"GATHERER_29_CARD_ORACLE_LOCK.json"; p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); dig=sha256_bytes(p.read_bytes()); (outdir/"SHA256SUMS").write_text(f"{dig}  {p.name}\n",encoding="utf-8")
    print(json.dumps({"card_count":len(records),"full_current_oracle_lock_count":report["full_current_oracle_lock_count"],"sha256":dig})); return 0
if __name__=="__main__": raise SystemExit(main())
