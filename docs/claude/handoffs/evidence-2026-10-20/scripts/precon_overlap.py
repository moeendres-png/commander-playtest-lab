import json, re, sys, pathlib, unicodedata, collections
S = pathlib.Path(sys.argv[1])
pin = S / "mage-pin"
missing = set(json.loads(sys.argv[2] if False else open(sys.argv[3]).read()))
cards_dir = pin / "Mage.Sets/src/mage/cards"
impl = {}
for p in cards_dir.rglob("*.java"):
    impl[p.stem.lower()] = p
def klass(name):
    # XMage class naming: strip non-alphanumerics; for split/double-faced use first face
    first = name.split(" // ")[0]
    n = unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", n).lower()
decks = {}
for f in sorted((S / "precons/data/decks/precons").glob("*.json")):
    d = json.load(open(f))
    decks[f.stem] = {c["oracle_name"] for c in d["cards"]}
allnames = set().union(*decks.values())
absent = {n for n in allnames if klass(n) not in impl}
print("unique precon card names:", len(allnames))
print("names w/o a card class at pin (heuristic):", len(absent))
print("handover list size:", len(missing), " | handover ∩ heuristic-absent:", len(missing & absent), " | handover-only:", len(missing - absent), " | heuristic-only:", len(absent - missing))
per = {k: len(v & absent) for k, v in decks.items()}
print("decks with >=1 absent card (pin heuristic):", sum(1 for v in per.values() if v), "/", len(decks))
per_m = {k: len(v & missing) for k, v in decks.items()}
print("decks with >=1 card from handover-221 list:", sum(1 for v in per_m.values() if v), "/", len(decks))
print("decks with ZERO handover-221 cards:", [k for k, v in per_m.items() if v == 0][:10], "count", sum(1 for v in per_m.values() if v == 0))
print("per-deck missing (handover list) distribution:", sorted(collections.Counter(per_m.values()).items()))
json.dump({"absent": sorted(absent)}, open(S / "absent_at_pin.json", "w"))
