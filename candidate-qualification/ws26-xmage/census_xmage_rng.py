#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "vendor/engine-source/xmage")
patterns = {
    "new_random": re.compile(r"\bnew\s+Random\s*\("),
    "thread_local_random": re.compile(r"\bThreadLocalRandom\b"),
    "math_random": re.compile(r"\bMath\.random\s*\("),
    "secure_random": re.compile(r"\bSecureRandom\b"),
    "collections_shuffle": re.compile(r"\bCollections\.shuffle\s*\("),
}
findings=[]
for path in sorted(root.rglob("*.java")):
    rel=path.relative_to(root).as_posix()
    if "/target/" in f"/{rel}/":
        continue
    text=path.read_text(errors="replace")
    for lineno,line in enumerate(text.splitlines(),1):
        for kind,rx in patterns.items():
            if rx.search(line):
                findings.append({"kind":kind,"path":rel,"line":lineno,"text":line.strip()[:300]})
classified=[]
for item in findings:
    rel=item["path"]
    if rel == "Mage/src/main/java/mage/util/RandomUtil.java":
        classification="RULES_RNG_AUTHORITY"
    elif any(part in rel for part in ("Mage.Tests/", "Mage.Client/", "Mage.Server.Plugins/", "Mage.Plugins/")):
        classification="NON_QUALIFIED_SURFACE"
    else:
        classification="REQUIRES_REACHABILITY_REVIEW"
    classified.append({**item,"classification":classification})
out={
    "schema_version":"ws26-xmage-rng-census/1.0.0",
    "root":str(root),
    "findings":classified,
    "counts":{},
}
for item in classified:
    key=item["classification"]+":"+item["kind"]
    out["counts"][key]=out["counts"].get(key,0)+1
Path("qualification/evidence/ws26-xmage").mkdir(parents=True, exist_ok=True)
Path("qualification/evidence/ws26-xmage/XMAGE_RNG_CENSUS.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(json.dumps(out["counts"],sort_keys=True))
