#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, quote
from urllib.request import Request, urlopen

RULES_PAGE='https://magic.wizards.com/en/rules'
UA='Mozilla/5.0 Commander-Simulation-Foundry-WS37/1.1'
RULE_REFS=['101.4','107.1','107.3','115.1','115.3','401','508.1b','601.2b','601.2c','601.2d','601.2f','603.10','603.10a','603.3b','603.3d','603.5','608.2b','608.2d','613.7','700.2','701.20e','701.22a','702.124d','802.3','903.10a','903.3','903.8','903.9a','903.9b']

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def safe_url(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.netloc,quote(p.path,safe='/%:@'),p.query,p.fragment))
def get(url, accept='*/*'):
    url=safe_url(url)
    req=Request(url,headers={'User-Agent':UA,'Accept':accept,'Accept-Language':'en-US,en;q=0.8'})
    t=now()
    with urlopen(req,timeout=60) as r:
        b=r.read(); return b,{'requested_url':url,'final_url':r.geturl(),'http_status':r.getcode(),'retrieved_at_utc':t,'raw_byte_count':len(b),'sha256':sha(b),'content_type':r.headers.get('Content-Type'),'last_modified':r.headers.get('Last-Modified'),'etag':r.headers.get('ETag')}

def norm(s): return ' '.join((s or '').split())
def semnorm(s):
    s=norm(s).casefold().replace('’',"'").replace('‘',"'").replace('“','"').replace('”','"').replace('–','-').replace('—','-')
    return s
def rule_block(text, ref):
    lines=text.replace('\r\n','\n').replace('\r','\n').split('\n')
    if '.' not in ref:
        # Comprehensive Rules TXT files contain a table of contents before the
        # normative rules body. Anchor section-level references on the first
        # numbered subrule (for example 401.1.), not the earlier TOC heading.
        body_pat=re.compile(r'^'+re.escape(ref)+r'\.1\.\s')
        start=next((i for i,l in enumerate(lines) if body_pat.match(l)),None)
        if start is None: return None
        nxt=str(int(ref)+1)
        end=next((i for i in range(start+1,len(lines)) if re.match(r'^'+re.escape(nxt)+r'\.\s',lines[i])),len(lines))
        return norm(' '.join(lines[start:end]))
    if ref[-1].isalpha():
        pat=r'^'+re.escape(ref)+r'\s'
        start=next((i for i,l in enumerate(lines) if re.match(pat,l)),None)
        if start is None: return None
        end=start+1
        numbered=re.compile(r'^\d{3}\.\d+(?:[a-z])?(?:\.|\s)')
        while end<len(lines) and not numbered.match(lines[end]): end+=1
        return norm(' '.join(lines[start:end]))
    pat=r'^'+re.escape(ref)+r'\.\s'
    start=next((i for i,l in enumerate(lines) if re.match(pat,l)),None)
    if start is None: return None
    prefix=ref
    end=start+1
    sibling=re.compile(r'^\d{3}\.\d+\.\s')
    while end<len(lines):
        l=lines[end]
        if sibling.match(l) and not l.startswith(prefix+'. '): break
        end+=1
    return norm(' '.join(lines[start:end]))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); a=ap.parse_args()
    page,pm=get(RULES_PAGE,'text/html,*/*;q=0.8')
    html=page.decode('utf-8',errors='replace')
    hrefs=[unescape(x) for x in re.findall(r'href=["\']([^"\']+)["\']',html,re.I)]
    links=[]
    for h in hrefs:
        u=urljoin(pm['final_url'],h)
        if re.search(r'MagicCompRules[^?#]*\.txt(?:$|[?#])',u,re.I): links.append(safe_url(u))
    uniq=list(dict.fromkeys(links))
    if not uniq: raise SystemExit('AUTHORITY_DEFECT:NO_CURRENT_CR_TXT_LINK_ON_OFFICIAL_RULES_PAGE')
    if len(uniq)!=1: raise SystemExit('AUTHORITY_DEFECT:AMBIGUOUS_CURRENT_CR_TXT_LINKS:'+json.dumps(uniq))
    raw,rm=get(uniq[0],'text/plain,*/*;q=0.8')
    text=raw.decode('utf-8-sig',errors='replace')
    if not text.startswith('Magic: The Gathering Comprehensive Rules'): raise SystemExit('AUTHORITY_DEFECT:CURRENT_CR_IDENTITY_PREFIX_MISMATCH')
    m=re.search(r'These rules are effective as of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',text,re.I)
    if not m: m=re.search(r'effective\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',text[:5000],re.I)
    if not m: raise SystemExit('AUTHORITY_DEFECT:CURRENT_CR_EFFECTIVE_DATE_UNPARSEABLE')
    # WS-37 validates the live current rules semantically, not by depending on a
    # superseded raw file that Wizards may remove. Each predicate is the minimum
    # current rules meaning actually relied on by the curated contract.
    anchors={
      '101.4':[['active player','nonactive players'],['actions happen simultaneously']],
      '107.1':[['only numbers','integers']],
      '107.3':[['letter x','placeholder'],['controller choose','value of x']],
      '115.1':[['spells and abilities','one or more targets'],['putting the spell or ability on the stack']],
      '115.3':[["same target can't be chosen multiple times",'one instance of the word \"target\"']],
      '401':[['single face-down pile'],["players can’t look at or change the order"]],
      '508.1b':[['active player announces','each of the chosen creatures is attacking']],
      '601.2b':[['spell is modal','announces the mode choice'],['alternative or additional costs','announces their intentions'],['variable cost','announces the value']],
      '601.2c':[['choice of an appropriate object or player','each target'],['variable number of targets','announces how many targets']],
      '601.2d':[['divide or distribute an effect','one or more targets'],['each of these targets must receive at least one']],
      '601.2f':[['determines the total cost'],['additional or alternative costs'],['cost increases','cost reductions']],
      '603.3b':[['multiple abilities have triggered','apnap order'],['puts each triggered ability they control','stack']],
      '603.3d':[['process for putting a triggered ability on the stack','identical to the process for casting a spell'],['no legal choices can be made','removed from the stack']],
      '603.5':[["triggered abilities’ effects are optional",'may'],['choice is made when the ability resolves']],
      '603.10':[['objects that exist immediately after an event','trigger conditions']],
      '603.10a':[['zone-change triggers look back in time'],['leaves-the-battlefield abilities'],['sacrifices a permanent']],
      '608.2b':[['specifies targets','checks whether the targets are still legal'],['last known information']],
      '608.2d':[['offers any choices','player announces these while applying the effect'],["can’t choose an option that’s illegal or impossible"]],
      '613.7':[['timestamp system'],['earlier timestamp','later timestamp']],
      '700.2':[['spell or ability is modal'],['each of those options is a mode']],
      '701.20e':[['instruct a player to look at one or more cards'],['shown only to the specified player']],
      '701.22a':[['scry n'],['look at the top n cards'],['bottom of your library'],['rest on top of your library']],
      '702.124d':[['two commanders function independently'],['ignore how many times your other commander has been cast'],['damage from each of your two commanders separately']],
      '802.3':[['attacking player declares each attacking creature'],['choose a defending player']],
      '903.3':[['designated as its commander'],['creature card']],
      '903.8':[['cast a commander they own from the command zone'],['additional {2}','each previous time']],
      '903.9a':[['commander is in a graveyard or in exile'],['state-based action'],['put it into the command zone']],
      '903.9b':[["commander would be put into its owner’s hand or library"],['put it into the command zone instead'],['replacement effect']],
      '903.10a':[['21 or more combat damage'],['same commander'],['loses the game']],
    }
    records=[]; defects=[]
    for ref in RULE_REFS:
        cur=rule_block(text,ref)
        if cur is None:
            defects.append({'rule_ref':ref,'code':'RULE_REFERENCE_NOT_EXTRACTABLE'}); continue
        low=semnorm(cur)
        checks=[]
        for group in anchors[ref]:
            ok=all(semnorm(term) in low for term in group)
            checks.append({'required_terms':group,'status':'PASS' if ok else 'FAIL'})
        passed=all(x['status']=='PASS' for x in checks)
        records.append({'rule_ref':ref,'current_normalized_sha256':sha(cur.encode()),'semantic_predicates':checks,'status':'PASS' if passed else 'FAIL_CLOSED'})
        if not passed: defects.append({'rule_ref':ref,'code':'CURRENT_RULE_SEMANTIC_PREDICATE_FAILED','failed_predicates':[x for x in checks if x['status']!='PASS']})
    comp={'status':'PASS' if not defects and len(records)==len(RULE_REFS) else 'FAIL_CLOSED','validation_mode':'CURRENT_RULE_SEMANTIC_PREDICATES','prior_ws31_cr_sha256_provenance':'9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c','required_rule_ref_count':len(RULE_REFS),'comparison_count':len(records),'match_count':sum(x['status']=='PASS' for x in records),'records':records,'defects':defects}
    out={'schema_version':'commander-lab.ws37.current-cr-acquisition/1.2.0','rules_page':pm,'current_cr':rm,'effective_date_text':m.group(1),'authority_scope':'CURRENT_OFFICIAL_WIZARDS_COMPREHENSIVE_RULES','raw_rules_bytes_committed':False,'relevant_rule_semantic_validation':comp}
    p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'current_cr_url':rm['final_url'],'sha256':rm['sha256'],'effective_date_text':out['effective_date_text'],'relevant_rule_semantic_status':comp['status'],'relevant_rule_match_count':comp['match_count'],'defects':comp['defects']},sort_keys=True))
    return 0 if comp['status']=='PASS' else 4
if __name__=='__main__': raise SystemExit(main())
