import json, sys
def load(p):
    d = {}
    for line in open(p):
        line = line.strip()
        if line.startswith("{") and '"seed"' in line:
            try: r = json.loads(line)
            except: continue
            d[r["seed"]] = r
    return d
a, b = load(sys.argv[1]), load(sys.argv[2])
common = sorted(a.keys() & b.keys())
diff = [s for s in common if a[s]["status"] != "ok" or b[s]["status"] != "ok" or a[s]["semantic"] != b[s]["semantic"]]
print(f"{sys.argv[1].split('/')[-1]} done={len(a)} | {sys.argv[2].split('/')[-1]} done={len(b)} | compared={len(common)} identical={len(common)-len(diff)} different={diff}")
for s in diff: print("  seed", s, a[s]["status"], a[s].get("decisions"), a[s].get("winners"), "vs", b[s]["status"], b[s].get("decisions"), b[s].get("winners"))
