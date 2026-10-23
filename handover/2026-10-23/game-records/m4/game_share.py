#!/usr/bin/env python3
"""M4 Nachtrag 2.2/2.3: Spielanteil je Karte + Angeboten-aber-nicht-gespielt-Analyse."""
import json, glob, sys, re
from collections import defaultdict

out_dir, deck_json = sys.argv[1], sys.argv[2]
deck = json.load(open(deck_json))
main_cards = []
for e in deck['cards']:
    if e.get('zone') == 'main': main_cards.append(e['oracle_name'])
alias = {}
for c in set(main_cards):
    if ' // ' in c:
        for h in c.split(' // '): alias[h] = c

def norm(label):
    m = re.match(r'^(.*?) — (Cast|Play) ', label)
    if not m: return None
    return alias.get(m.group(1), m.group(1))

games = [f for f in glob.glob(out_dir + '/games/*.json')]
recs = []
for f in games:
    d = json.load(open(f))
    if d['status'] != 'completed': continue
    if '#variant' in d['case_id']: continue
    recs.append(d)
print(f"Baseline-Arm: {len(recs)} Spiele", file=sys.stderr)

cast_games = defaultdict(set); offered_games = defaultdict(set)
for gi, d in enumerate(recs):
    seat = int(d['case_id'].split('seat=')[1]) - 1
    seed = d['case_id'].split('seed=')[1].split('|')[0]
    cast_here, offered_here = set(), set()
    for e in d['result']['result_payload']['transcript']:
        if e.get('actor_seat') != seat: continue
        if e.get('kind') == 'decision_requested':
            for lab in e.get('legal_option_labels', []):
                n = norm(lab)
                if n: offered_here.add(n)
        elif e.get('kind') == 'decision_accepted' and e.get('decision_class') == 'priority':
            for lab in e.get('selected_option_labels', []):
                n = norm(lab)
                if n: cast_here.add(n)
    for n in cast_here: cast_games[n].add(gi)
    for n in offered_here: offered_games[n].add(gi)
    if 'Irrigated Farmland' in offered_here and 'Irrigated Farmland' not in cast_here:
        pass

rows = []
for c in sorted(set(main_cards)):
    rows.append({'card': c, 'cast_games': len(cast_games.get(c, ())), 'offered_games': len(offered_games.get(c, ()))})
rows.sort(key=lambda r: (r['cast_games'], r['offered_games']))
print(json.dumps({'games': len(recs), 'rows': rows}, indent=1))
