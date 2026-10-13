import collections
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    d = json.load(handle)
ev = d["recording"]["events"]


def short(x):
    p = x.split(".")
    return ".".join(p[-2:])


def frames(e):
    st = e["values"]["stackTrace"]
    if not st:
        return []
    return [
        (f["method"]["type"]["name"] + "." + f["method"]["name"]).replace("/", ".")
        for f in st["frames"]
    ]


N = len(ev)
bucket = collections.Counter()
copyc = collections.Counter()
copytot = 0
for e in ev:
    fs = frames(e)
    if not fs:
        bucket["<nostack>"] += 1
        continue
    # deepest (closest to leaf) bridge frame and the mage frame it calls
    idx = [i for i, f in enumerate(fs) if f.startswith("org.commanderlab")]
    if idx:
        i = idx[0]
        callee = fs[i - 1] if i > 0 else "(self)"
        bucket[short(fs[i]) + " -> " + short(callee)] += 1
    else:
        bucket["(no bridge frame) " + short(fs[-1])] += 1
    for i, f in enumerate(fs):
        if (
            f.endswith("GameImpl.createSimulationForPlayableCalc")
            or f.endswith("GameImpl.copy")
            or f.endswith("GameCommanderImpl.copy")
            or f.endswith("CommanderFreeForAll.copy")
        ):
            copytot += 1
            j = i + 1
            while j < len(fs) and (
                (fs[j].endswith(".copy") and fs[j].startswith("mage.game"))
                or fs[j].endswith("createSimulationForPlayableCalc")
            ):
                j += 1
            copyc[" <- ".join(short(x) for x in fs[j : j + 3])] += 1
            break
print("samples", N)
print("\nBY BRIDGE CALL SITE (deepest bridge frame -> callee)")
for k, v in bucket.most_common(30):
    print(f"{100 * v / N:5.1f}% {k}")
print("\nGAME COPY total %.1f%%" % (100 * copytot / N))
for k, v in copyc.most_common(15):
    print(f"{100 * v / N:5.1f}% {k}")
