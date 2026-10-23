#!/usr/bin/env python3
"""M4: Speicherarme Streaming-Auswertung (ein Record nach dem anderen).
Liefert je Arm: Spiele, Siege, Zug-Schnitt, Mulligan-Anteil, Kommandanten-Cast-Anteil;
plus gepaarte Effekte der Varianten gegen die Baseline (erster Arm, ohne #)."""
import json, glob, sys, re, math
from collections import Counter, defaultdict

out_dir, deck_json = sys.argv[1], sys.argv[2]
deck = json.load(open(deck_json))
commanders = [e['oracle_name'] for e in deck['cards'] if e.get('zone') == 'commander']
split_alias = {}
for e in deck['cards']:
    n = e['oracle_name']
    if ' // ' in n:
        for h in n.split(' // '): split_alias[h] = n

arms = defaultdict(lambda: {'games': 0, 'wins': 0, 'turns': 0.0, 'mul_games': 0,
                             'cmdr': Counter(), 'paired': {}})
order = []
for f in glob.glob(out_dir + '/games/*.json'):
    d = json.load(open(f))
    cid = d['case_id']; arm = cid.split('|')[0]
    if arm not in order: order.append(arm)
    if d['status'] != 'completed': continue
    seed = int(cid.split('seed=')[1].split('|')[0]); seat = int(cid.split('seat=')[1])
    p = d['result']['result_payload']
    own = next(o for o in p['outcomes'] if o['seat'] == seat - 1)
    A = arms[arm]
    A['games'] += 1; A['wins'] += 1 if own['won'] else 0; A['turns'] += p['turn_number']
    A['paired'][(seed, seat)] = 1 if own['won'] else 0
    muls = 0; cast_here = set()
    for e in p['transcript']:
        if e.get('kind') != 'decision_accepted' or e.get('actor_seat') != seat - 1: continue
        if e.get('decision_class') == 'mulligan' and 'mulligan' in (e.get('selected_option_types') or []): muls += 1
        if e.get('decision_class') == 'priority':
            for lab in e.get('selected_option_labels', []):
                m = re.match(r'^(.*?) — (Cast|Play) ', lab)
                if m: cast_here.add(split_alias.get(m.group(1), m.group(1)))
    if muls: A['mul_games'] += 1
    for c in commanders:
        if c in cast_here: A['cmdr'][c] += 1
    del d

base_arm = next(a for a in order if '#' not in a)
print(f"Baseline-Arm: {base_arm} | Kommandanten: {commanders}")
for arm in order:
    A = arms[arm]; n = A['games']
    cmdr_str = ', '.join(f"{c}: {A['cmdr'][c]}/{n} ({A['cmdr'][c]/n:.0%})" for c in commanders)
    print(f"{arm}: Spiele {n}, Siege {A['wins']} ({A['wins']/n:.1%}), Zuege-Schnitt {A['turns']/n:.1f}, Mulligan-Spiele {A['mul_games']/n:.0%}, Cmdr-Cast: {cmdr_str}")
    if arm != base_arm:
        pairs = [(arms[base_arm]['paired'][k], A['paired'][k]) for k in A['paired'] if k in arms[base_arm]['paired']]
        diffs = [v - b for b, v in pairs]; nn = len(diffs); eff = sum(diffs) / nn
        sd = math.sqrt(sum((x - eff) ** 2 for x in diffs) / (nn - 1)); se = sd / math.sqrt(nn)
        lo, hi = eff - 1.96 * se, eff + 1.96 * se
        verdict = 'VARIANT_BETTER' if lo > 0.125 else ('BASELINE_BETTER' if hi < -0.125 else 'UNDECIDED')
        print(f"   gepaart: n={nn}, Effekt {eff:+.3f}, 95%-KI [{lo:+.3f}, {hi:+.3f}] -> {verdict}")
