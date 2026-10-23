import json, copy, os
cands = json.load(open('/home/hatch/workspace/tmp/m4/candidates.json'))
os.makedirs('/home/hatch/workspace/tmp/m4/variants', exist_ok=True)
for deck, lst in cands.items():
    base = json.load(open(f'/home/hatch/workspace/tmp/m4/{deck}.json'))
    for c in lst:
        v = copy.deepcopy(base)
        cards = v['cards']
        hit = None
        for e in cards:
            if e['oracle_name'] == c['out'] and e.get('zone') == 'main':
                hit = e; break
        assert hit is not None, f"{c['id']}: {c['out']} nicht im Deck"
        assert int(hit.get('quantity', 1)) == 1, f"{c['id']}: {c['out']} quantity != 1"
        cards.remove(hit)
        assert not any(e['oracle_name'] == c['in'] for e in cards), f"{c['id']}: {c['in']} schon im Deck"
        cards.append({'oracle_name': c['in'], 'quantity': 1, 'zone': 'main', 'physical_copy_ids': [], 'notes': f"M4-Swap {c['id']}: ersetzt {c['out']}"})
        json.dump(v, open(f"/home/hatch/workspace/tmp/m4/variants/{deck}_{c['id']}.json", 'w'), indent=1)
        print(c['id'], deck, ':', c['out'], '=>', c['in'], '| Karten gesamt:', sum(int(e.get('quantity', 1)) for e in v['cards']))
