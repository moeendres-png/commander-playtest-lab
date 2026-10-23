import json, copy, os
counts = json.load(open('/home/hatch/workspace/tmp/m4/collection_counts.json'))['cards']
decks = {}
for name in ('rogshai', 'chulane'):
    d = json.load(open(f'/home/hatch/workspace/tmp/m4/{name}.json'))
    decks[name] = {e['oracle_name']: int(e.get('quantity', 1)) for e in d['cards']}
def frei(n): return counts.get(n, 0) - decks['rogshai'].get(n, 0) - decks['chulane'].get(n, 0)

BUNDLES = {
 'rogshai_RA': ('rogshai', [('Adarkar Wastes', 'Temple of Epiphany'), ('Prairie Stream', 'Restless Spire'), ('Skycloud Expanse', 'Swiftwater Cliffs')]),
 'rogshai_RB': ('rogshai', [('Mana Geyser', "Pyromancer's Goggles"), ('Veyran, Voice of Duality', 'Rootha, Mercurial Artist'), ('Kediss, Emberclaw Familiar', 'Sram, Senior Edificer')]),
 'rogshai_RC': ('rogshai', [('Furygale Flocking', 'Goldspan Dragon'), ('Dig Through Time', "Jace's Ingenuity"), ('Mana Geyser', 'Izzet Signet')]),
 'chulane_CA': ('chulane', [('Mechanized Production', 'Simic Signet'), ('Noxious Newt', 'Azorius Signet'), ('Wilderness Reclamation', 'Talisman of Unity'), ('Azorius Chancery', 'Tranquil Cove')]),
 'chulane_CB': ('chulane', [('Whirler Rogue', 'Solemn Simulacrum'), ('Adrix and Nev, Twincasters', 'Alandra, Sky Dreamer'), ('Wood Elves', 'Selvala, Explorer Returned'), ('Wilderness Reclamation', "Teferi's Ageless Insight")]),
 'chulane_CC': ('chulane', [('Rampaging Baloths', 'Augur of Autumn'), ('Aerial Extortionist', 'Morska, Undersea Sleuth'), ('Psychosis Crawler', 'Mischievous Mystic')]),
}
os.makedirs('/home/hatch/workspace/tmp/m4/bundles', exist_ok=True)
ok = True
for bid, (deckname, swaps) in BUNDLES.items():
    base = json.load(open(f'/home/hatch/workspace/tmp/m4/{deckname}.json'))
    v = copy.deepcopy(base)
    for out_c, in_c in swaps:
        f = frei(in_c)
        flag = 'OK' if f >= 1 else 'FREI=0!'
        if f < 1: ok = False
        print(f"{bid}: {out_c} => {in_c} (frei vorlaeufig {f}) {flag}")
        hit = next((e for e in v['cards'] if e['oracle_name'] == out_c and e.get('zone') == 'main'), None)
        assert hit is not None, f"{bid}: {out_c} nicht im Deck"
        v['cards'].remove(hit)
        assert not any(e['oracle_name'] == in_c for e in v['cards']), f"{bid}: {in_c} schon im Deck"
        v['cards'].append({'oracle_name': in_c, 'quantity': 1, 'zone': 'main', 'physical_copy_ids': [], 'notes': f"M4-Buendel {bid}: ersetzt {out_c}"})
    total = sum(int(e.get('quantity', 1)) for e in v['cards'])
    assert total == 100, f"{bid}: {total} Karten"
    json.dump(v, open(f'/home/hatch/workspace/tmp/m4/bundles/{bid}.json', 'w'), indent=1)
print('Alle frei-Werte >= 1:', ok)
