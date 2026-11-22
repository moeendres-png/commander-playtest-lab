import gzip, json, sys, re, collections
from commander_lab.engine.rules.frame_digest import normalize_frame
def frames(p):
    with gzip.open(p, "rt", encoding="utf-8") as h:
        return [e for e in map(json.loads, h) if e.get("kind") == "frame"]
def diff(a, b, path=""):
    if type(a) != type(b): return [path]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)): out += diff(a.get(k), b.get(k), f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b): return [path + ".len"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)): out += diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path]
a, b = frames(sys.argv[1]), frames(sys.argv[2])
strip = lambda f: {k: v for k, v in f.items() if k != "n"}
kinds = collections.Counter(); n = 0
for x, y in zip(a, b):
    d = diff(normalize_frame(strip(x)), normalize_frame(strip(y)))
    if d:
        n += 1
        for p in d: kinds[re.sub(r"\[\d+\]", "[]", p)] += 1
print(json.dumps({"frames": len(a), "differing_frames": n, "paths": dict(kinds.most_common(8))}))
