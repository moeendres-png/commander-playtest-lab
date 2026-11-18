import json, random, sys
from pathlib import Path
P=Path("/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/pilot_run")
R=Path("/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/rubric_v2")
sys.path.insert(0,str(R))
import render_prompt as RP
guide=(R/"GUIDE_v2.md").read_text(encoding="utf-8")
anchors=json.loads((R/"anchors.json").read_text(encoding="utf-8"))
anchor_names={a["card"] for t in (anchors["spell"],anchors["land"]) for rows in t.values() for a in rows if a["kind"]=="v1_fixed"}
class LO:
    def __init__(s,names): s.n=set(names)
    def __bool__(s): return bool(s.n)
    def __eq__(s,o): return o in s.n
    __hash__=None
idx=json.load(open(P/"index.json")); byname={x["name"]:x for x in idx}
pilot=json.load(open(R/"pilot_sample.json")); retest=[byname[n]["id"] for n in pilot["retest_cards"]]
facts={r["name"]:r for r in RP.load_jsonl(R/"data/facts.jsonl")}; pats={r["name"]:r for r in RP.load_jsonl(R/"data/patterns.jsonl")}
name_of={x["id"]:x["name"] for x in idx}
HEAD=("\n\n# CARDS TO RATE (BATCH)\n\nBelow are several cards. Rate EACH card independently, as if you saw it alone: "
"do not compare cards with each other and do not calibrate one card against another in this batch, only against the anchors and the guide. "
"Write ONE JSON object per card (schema as in the output rules); put all objects, in the order given, in ONE JSON array in the output file.\n\n")
def sysp(cards):
    lo=[c for c in cards if c in anchor_names]
    return RP.system_prompt(guide,anchors,LO(lo) if lo else None)
man=[]
sel=set(retest)|{byname[c['name']]['id'] for c in pilot['cards'] if c['v1_is_anchor']}|{byname["Tam's Resistance"]['id']}
ids=sorted(sel)
for rater in ("T1","T2"):
    order=ids[:]; random.Random(f"1118-{rater}").shuffle(order)
    chunks=[order[i:i+6] for i in range(0,len(order),6)]
    for bi,ch in enumerate(chunks):
        names=[name_of[c] for c in ch]
        body=sysp(names)+HEAD
        for k,c in enumerate(ch,1):
            n=name_of[c]; body+=f"## Card {k} of {len(ch)}\n\n"+RP.user_prompt(facts[n],pats.get(n)).strip()+"\n\n"
        pid=f"{rater}_b{bi:02d}"
        (P/"batches21"/f"{pid}.md").write_text(body,encoding="utf-8")
        man.append({"batch":pid,"rater":rater,"cards":names,"retest":False})
json.dump(man,open(P/"batches21_manifest.json","w"),indent=1,ensure_ascii=False)
print(len(man),"batches")
