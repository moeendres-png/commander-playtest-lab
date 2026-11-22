import gzip, json, sys
from commander_lab.engine.rules.frame_digest import normalize_frame
def frames(p):
    with gzip.open(p, "rt", encoding="utf-8") as h:
        return [e for e in map(json.loads, h) if e.get("kind") == "frame"]
def diff(a, b, path=""):
    if type(a) != type(b): return [(path, a, b)]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k), b.get(k), f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b): return [(path + ".len", len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)): out += diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [(path, a, b)]
a, b, n = frames(sys.argv[1]), frames(sys.argv[2]), int(sys.argv[3])
strip = lambda f: {k: v for k, v in f.items() if k != "n"}
x, y = normalize_frame(strip(a[n - 1])), normalize_frame(strip(b[n - 1]))
d = diff(x, y)
print("differences:", len(d))
for p, u, v in d[:12]: print(p, "|", json.dumps(u)[:120], "|", json.dumps(v)[:120])
fr = a[n-1]
print("turn/step/class:", json.dumps({k: fr.get(k) for k in ("turn", "step", "phase")})[:200])
req = fr.get("request") or fr
print(json.dumps(req.get("decision_class") if isinstance(req, dict) else None), json.dumps((req.get("prompt") if isinstance(req, dict) else ""))[:160])
# how many later frames differ
cnt = sum(1 for i in range(min(len(a), len(b))) if normalize_frame(strip(a[i])) != normalize_frame(strip(b[i])))
print("frames differing in total:", cnt, "of", len(a))
