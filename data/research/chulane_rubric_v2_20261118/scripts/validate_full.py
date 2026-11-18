import json,sys
man=json.load(open("full_manifest.json"));ok=0;bad=[]
for m in man:
    b=m["batch"]
    try:d=json.load(open(f"out_full/{b}.json"))
    except FileNotFoundError: continue
    except Exception: bad.append((b,"json"));continue
    if [x.get("card") for x in d]!=m["cards"]: bad.append((b,"cards"));continue
    if any(any((x["scores"].get(k) is None or x["scores"][k]%5) for k in "EFTRKDH") for x in d): bad.append((b,"scores"));continue
    ok+=1
print("fertig+gültig",ok,"von",len(man),"; Probleme",bad)
