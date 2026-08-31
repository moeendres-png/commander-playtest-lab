#!/usr/bin/env python3
"""WS-31 official Gatherer acquisition for the exact actual-card domain.

Only ordinary public exact-name search/detail requests are used. Raw HTML is
hashed and discarded. Every selected project identity receives a terminal
PASS/UNKNOWN/FAIL_CLOSED record; no failed identity is removed from the shard.
"""
from __future__ import annotations
import argparse, hashlib, json, random, re, sys, time, unicodedata, zlib
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, build_opener

BASE="https://gatherer.wizards.com"
USER_AGENT=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/139.0 Safari/537.36 Commander-Simulation-Foundry-WS31/1.0")
DETAIL_RE=re.compile(r'href=["\'](?P<href>/[A-Za-z0-9]+/en-us/\d+/[^"\'#?]+)["\']',re.I)
LABELS=["Printed Oracle Card Name","Oracle Card Name","Card Name"]
TERMINAL={"PASS","UNKNOWN","FAIL_CLOSED"}


def now_utc(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def canon(s): return re.sub(r"\s+"," ",re.sub(r"\s*//\s*"," // ",unicodedata.normalize("NFC",s.strip())))
def norm(s): return unicodedata.normalize("NFKC",canon(s)).casefold()
def slug_norm(href): return norm(urlparse(href).path.rstrip("/").split("/")[-1].replace("-"," "))
def search_url(name): return f"{BASE}/search?searchTerm={quote(name,safe='')}"
def req(url): return Request(url,headers={"User-Agent":USER_AGENT,"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language":"en-US,en;q=0.8"})

def fetch(url,retries=4,base_delay=.45):
    last=None
    for attempt in range(retries):
        at=now_utc()
        try:
            with build_opener().open(req(url),timeout=60) as r:
                b=r.read(); h=r.headers
                return b,{"requested_url":url,"retrieved_at_utc":at,"attempt":attempt+1,"http_status":r.getcode(),"final_url":r.geturl(),"content_type":h.get("Content-Type"),"content_length":h.get("Content-Length"),"etag":h.get("ETag"),"last_modified":h.get("Last-Modified"),"raw_byte_count":len(b),"raw_html_sha256":sha256_bytes(b),"transport_error":None}
        except HTTPError as e:
            b=e.read(); h=e.headers
            last={"requested_url":url,"retrieved_at_utc":at,"attempt":attempt+1,"http_status":e.code,"final_url":e.geturl(),"content_type":h.get("Content-Type"),"content_length":h.get("Content-Length"),"etag":h.get("ETag"),"last_modified":h.get("Last-Modified"),"raw_byte_count":len(b),"raw_html_sha256":sha256_bytes(b) if b else None,"transport_error":f"HTTPError: {e.code} {e.reason}"}
            if e.code not in {408,425,429,500,502,503,504}: return b,last
        except (URLError,TimeoutError,OSError) as e:
            last={"requested_url":url,"retrieved_at_utc":at,"attempt":attempt+1,"http_status":None,"final_url":None,"content_type":None,"content_length":None,"etag":None,"last_modified":None,"raw_byte_count":None,"raw_html_sha256":None,"transport_error":f"{type(e).__name__}: {e}"}
        if attempt+1<retries:
            time.sleep(base_delay*(2**attempt)+random.random()*.15)
    return b"",last

def visible_text(b):
    s=b.decode("utf-8",errors="replace")
    s=re.sub(r'<img\b[^>]*\balt=["\']([^"\']*)["\'][^>]*>',lambda m:' '+unescape(m.group(1))+' ',s,flags=re.I)
    s=re.sub(r"<script\b[^>]*>.*?</script>"," ",s,flags=re.I|re.S)
    s=re.sub(r"<style\b[^>]*>.*?</style>"," ",s,flags=re.I|re.S)
    s=re.sub(r"<[^>]+>"," ",s)
    return " ".join(unescape(s).split())

def discover_detail(html,face):
    hrefs=list(dict.fromkeys(m.group("href") for m in DETAIL_RE.finditer(html.decode("utf-8",errors="replace"))))
    target=norm(face); toks=set(target.split())
    ranked=sorted(hrefs,key=lambda h:(slug_norm(h)==target,len(toks & set(slug_norm(h).split())),-abs(len(toks)-len(set(slug_norm(h).split())))),reverse=True)
    if not ranked: return None,[]
    best=ranked[0]; overlap=len(toks & set(slug_norm(best).split())); threshold=max(1,min(2,len(toks)))
    return (urljoin(BASE,best) if slug_norm(best)==target or overlap>=threshold else None),ranked[:12]

def extract_oracle_section(text,face):
    low=text.casefold(); starts=[low.find(m.casefold()) for m in LABELS if low.find(m.casefold())>=0]
    if not starts: return None
    start=min(starts)
    ends=[i for marker in ("Find Articles","Club Support") if (i:=low.find(marker.casefold(),start))>start]
    end=min(ends) if ends else min(len(text),start+50000)
    sec=text[start:end].strip()
    return sec if norm(face) in norm(sec) and "rules text" in sec.casefold() else None

def val_between(sec,start_labels,end_labels):
    low=sec.casefold(); starts=[]
    for lab in start_labels:
        p=low.find(lab.casefold())
        if p>=0: starts.append((p+len(lab),p))
    if not starts: return None
    st,_=min(starts,key=lambda x:x[1]); ends=[]
    for lab in end_labels:
        p=low.find(lab.casefold(),st)
        if p>=st: ends.append(p)
    en=min(ends) if ends else len(sec); v=sec[st:en].strip(" :-")
    return v or None

def parse_section(sec,expected_face):
    name=val_between(sec,LABELS,["Alternative Name","Mana Cost","Color Indicator","Type","Rarity","rules Text"])
    mana=val_between(sec,["Mana Cost"],["Color Indicator","Type","Rarity","rules Text"])
    color_indicator=val_between(sec,["Color Indicator"],["Type","Rarity","rules Text"])
    type_line=val_between(sec,["Type"],["Rarity","rules Text"])
    oracle=val_between(sec,["rules Text"],["Flavor Text","Artist","P/T","Loyalty","Defense","Set "])
    pt=val_between(sec,["P/T"],["Loyalty","Defense","Set ","Language","printings"])
    loyalty=val_between(sec,["Loyalty"],["Defense","Set ","Language","printings"])
    defense=val_between(sec,["Defense"],["Set ","Language","printings"])
    set_text=val_between(sec,["Set "],["Number","Language","printings"])
    collector=val_between(sec,["Number"],["Language","printings"])
    rulings=[]; rp=sec.casefold().find("rulings")
    if rp>=0:
        tail=sec[rp+len("rulings"):]
        for m in re.finditer(r"\(\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\s*\)\s*(.*?)(?=\(\s*[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}\s*\)|$)",tail,re.S):
            rulings.append({"date":m.group(1),"text":" ".join(m.group(2).split())})
    syms=re.findall(r"\{([WUBRGC])\}",mana or "",re.I); colors=sorted(set(x.upper() for x in syms if x.upper() in "WUBRG"))
    if color_indicator:
        for word,c in [("white","W"),("blue","U"),("black","B"),("red","R"),("green","G")]:
            if word in color_indicator.casefold(): colors=sorted(set(colors+[c]))
    complete=bool(name and norm(expected_face) in norm(name) and type_line and oracle is not None)
    return {"current_gatherer_card_name":name,"mana_cost":mana,"colors":colors,"color_indicator":color_indicator,"type_line":type_line,"oracle_text":oracle,"power_toughness":pt,"loyalty":loyalty,"defense":defense,"set_or_printing_used":set_text,"collector_number":collector,"official_rulings":rulings,"parse_complete":complete}

def printing_key(url):
    p=urlparse(url).path.strip('/').split('/'); return (p[0].upper(),p[2]) if len(p)>=4 else None

def same_printing_siblings(html,detail_url):
    key=printing_key(detail_url)
    if not key: return []
    out=[]
    for m in DETAIL_RE.finditer(html.decode("utf-8",errors="replace")):
        u=urljoin(BASE,m.group("href"))
        if printing_key(u)==key and u.rstrip('/')!=detail_url.rstrip('/'): out.append(u)
    return list(dict.fromkeys(out))

def face_name_from_url(u): return " ".join(x.capitalize() for x in urlparse(u).path.rstrip('/').split('/')[-1].split('-'))

def acquire_face(face,delay):
    sb,sm=fetch(search_url(face)); detail,cands=discover_detail(sb,face) if sm and sm.get("http_status")==200 else (None,[])
    out={"requested_face_name":face,"search":sm,"detail_candidates":cands,"official_gatherer_url":detail,"acquisition_status":"UNKNOWN","failure_reason":None}
    if not detail:
        out["failure_reason"]="NO_MATCHING_PUBLIC_GATHERER_DETAIL_URL"; return out,None,[]
    time.sleep(delay); db,dm=fetch(detail); out["detail_transport"]=dm
    if not dm or dm.get("http_status")!=200:
        out["failure_reason"]="GATHERER_DETAIL_HTTP_FAILURE"; return out,db,[]
    sec=extract_oracle_section(visible_text(db),face)
    if not sec:
        out["failure_reason"]="VALIDATED_ORACLE_SECTION_NOT_FOUND"; return out,db,same_printing_siblings(db,detail)
    fields=parse_section(sec,face); out.update(fields)
    out["oracle_section_sha256"]=sha256_bytes(" ".join(sec.split()).encode("utf-8")); out["currentness_status"]="CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL"; out["retrieval_timestamp_utc"]=dm.get("retrieved_at_utc"); out["raw_html_sha256"]=dm.get("raw_html_sha256"); out["raw_html_byte_count"]=dm.get("raw_byte_count")
    if fields["parse_complete"]: out["acquisition_status"]="PASS"
    else: out["failure_reason"]="OFFICIAL_PAGE_PRESENT_BUT_REQUIRED_FIELDS_INCOMPLETE"
    return out,db,same_printing_siblings(db,detail)

def structure_hints(text,type_line,face_count):
    t=(text or "").casefold(); ty=(type_line or "").casefold(); out=[]
    if face_count>1: out.append("MULTIFACE")
    if "adventure" in ty or "adventure" in t: out.append("ADVENTURE")
    if "meld" in t: out.append("MELD")
    if "aftermath" in t: out.append("AFTERMATH")
    if "fuse" in t: out.append("FUSE")
    if "saga" in ty and ("transformed" in t or "transform" in t): out.append("SAGA_TRANSFORM")
    if "transform" in t or "transformed" in t: out.append("TRANSFORM")
    return sorted(set(out))

def acquire_identity(rec,delay):
    identity=rec["project_card_identity"]; requested=[x.strip() for x in identity.split("//")]; faces=[]; sibling_urls=[]
    for face in requested:
        fr,db,sibs=acquire_face(face,delay); faces.append(fr); sibling_urls.extend(sibs); time.sleep(delay)
    if len(requested)==1 and faces and faces[0].get("official_gatherer_url"):
        known_urls={f.get("official_gatherer_url") for f in faces}
        for u in list(dict.fromkeys(sibling_urls))[:4]:
            if u in known_urls: continue
            time.sleep(delay); db,dm=fetch(u)
            if not dm or dm.get("http_status")!=200: continue
            txt=visible_text(db); candidate=face_name_from_url(u); sec=extract_oracle_section(txt,candidate)
            if not sec:
                for lab in LABELS:
                    p=txt.casefold().find(lab.casefold())
                    if p>=0:
                        tail=txt[p+len(lab):]; candidate=re.split(r"Alternative Name|Mana Cost|Color Indicator|Type|Rarity|rules Text",tail,maxsplit=1,flags=re.I)[0].strip(" :-"); sec=extract_oracle_section(txt,candidate); break
            if not sec: continue
            fields=parse_section(sec,candidate)
            if fields["parse_complete"]:
                faces.append({"requested_face_name":candidate,"search":None,"detail_candidates":[],"official_gatherer_url":u,"detail_transport":dm,**fields,"oracle_section_sha256":sha256_bytes(" ".join(sec.split()).encode()),"currentness_status":"CURRENT_OFFICIAL_GATHERER_AT_RETRIEVAL","retrieval_timestamp_utc":dm.get("retrieved_at_utc"),"raw_html_sha256":dm.get("raw_html_sha256"),"raw_html_byte_count":dm.get("raw_byte_count"),"acquisition_status":"PASS","failure_reason":None,"discovered_as_same_printing_sibling":True})
    statuses=[f["acquisition_status"] for f in faces]
    status="PASS" if faces and all(s=="PASS" for s in statuses) else ("FAIL_CLOSED" if any(s=="FAIL_CLOSED" for s in statuses) else "UNKNOWN")
    alltxt=" ".join((f.get("oracle_text") or "") for f in faces); type_line=" // ".join(f.get("type_line") or "" for f in faces); relation="SINGLE_FACE"
    if len(faces)>1: relation="EXPLICIT_PROJECT_MULTIFACE" if "//" in identity else "OFFICIAL_SAME_PRINTING_MULTIFACE_DISCOVERED"
    return {**rec,"acquisition_status":status,"terminal":status in TERMINAL,"current_gatherer_card_name":faces[0].get("current_gatherer_card_name") if faces else None,"faces":faces,"face_relation":relation,"special_structure_hints":structure_hints(alltxt,type_line,len(faces)),"authority_scope":"OFFICIAL_GATHERER_IDENTITY_AND_ORACLE_ONLY_NO_RUNTIME_CREDIT"}

def load_manifest(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def write_json(p,obj): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",required=True); ap.add_argument("--output",required=True); ap.add_argument("--checkpoint"); ap.add_argument("--shard-index",type=int,default=0); ap.add_argument("--shard-count",type=int,default=1); ap.add_argument("--delay",type=float,default=.12); a=ap.parse_args()
    m=load_manifest(a.manifest); records=m["records"]; selected=[r for i,r in enumerate(records) if i%a.shard_count==a.shard_index]; done={}
    if a.checkpoint and Path(a.checkpoint).exists():
        cp=json.loads(Path(a.checkpoint).read_text(encoding="utf-8")); done={r["semantic_identity"]:r for r in cp.get("records",[]) if r.get("terminal")}
    out=[]
    for n,rec in enumerate(selected,1):
        sid=rec["semantic_identity"]
        if sid in done: got=done[sid]
        else:
            try: got=acquire_identity(rec,a.delay)
            except Exception as e: got={**rec,"acquisition_status":"UNKNOWN","terminal":True,"faces":[],"face_relation":"UNKNOWN","special_structure_hints":[],"failure_reason":f"UNHANDLED_ACQUISITION_EXCEPTION:{type(e).__name__}:{e}","authority_scope":"OFFICIAL_GATHERER_IDENTITY_AND_ORACLE_ONLY_NO_RUNTIME_CREDIT"}
        out.append(got)
        if a.checkpoint and (n%10==0 or n==len(selected)): write_json(a.checkpoint,{"schema_version":"commander-lab.ws31.gatherer-checkpoint/1.0.0","shard_index":a.shard_index,"shard_count":a.shard_count,"records":out})
        print(f"[{a.shard_index}/{a.shard_count}] {n}/{len(selected)} {rec['project_card_identity']}: {got['acquisition_status']}",flush=True)
    report={"schema_version":"commander-lab.ws31.gatherer-shard/1.0.0","source":"current official public Gatherer","policy":"ordinary public exact-name search/detail GET only; raw HTML hashed then discarded","shard_index":a.shard_index,"shard_count":a.shard_count,"record_count":len(out),"terminal_count":sum(bool(r.get('terminal')) for r in out),"pass_count":sum(r.get('acquisition_status')=='PASS' for r in out),"unknown_count":sum(r.get('acquisition_status')=='UNKNOWN' for r in out),"fail_closed_count":sum(r.get('acquisition_status')=='FAIL_CLOSED' for r in out),"records":out}
    write_json(a.output,report)
    return 0 if report["terminal_count"]==len(out) else 3
if __name__=="__main__": raise SystemExit(main())
