import json, re
counts = json.load(open('/home/hatch/workspace/tmp/m4/collection_counts.json'))['cards']
pool_names = set(counts)
cat = json.load(open('/home/hatch/workspace/github/wt-m4/data/cards/xmage_card_facts.json'))
facts = cat['cards']
SYM = re.compile(r'\{([WUBRG])\}')
def ident(f):
    s = set(SYM.findall(f.get('mana_cost') or ''))
    for r in f.get('rules') or []: s |= set(SYM.findall(str(r)))
    return s
def show(deckfile, ident_set, label):
    deck = json.load(open(deckfile))
    in_deck = {e['oracle_name'] for e in deck['cards']}
    cand = []
    for n in pool_names - in_deck:
        f = facts.get(n)
        if not f: continue
        if not ident(f) <= set(ident_set): continue
        cand.append((f.get('mana_value') or 0, n, '/'.join(f.get('types') or []), counts[n]))
    cand.sort()
    print(f"== {label}: {len(cand)} Pool-Karten mit Facts, farblegal, nicht im Deck ==")
    for mv, n, tl, k in cand: print(f"  MV{mv:g} x{k} {n} [{tl}]")
show('/home/hatch/workspace/tmp/m4/rogshai.json', 'WUR', 'RogShai (WUR)')
show('/home/hatch/workspace/tmp/m4/chulane.json', 'GWU', 'Chulane (GWU)')
