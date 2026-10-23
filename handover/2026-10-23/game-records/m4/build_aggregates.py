#!/usr/bin/env python3
"""M4 Schritt 4: Baut die Aggregat-JSON aus den Game-Records (Streaming).
Dedup-Regel: pro case_id zaehlt der completed-Record; Mehrfach-Records eines
Cases werden auf Ergebnis-Gleichheit geprueft (Duplikat-Pruefung #976 Item 2a)."""
import json, glob, sys, re, math
from collections import Counter, defaultdict

out_dir, deck_json, label = sys.argv[1], sys.argv[2], sys.argv[3]
deck = json.load(open(deck_json))
commanders = [e['oracle_name'] for e in deck['cards'] if e.get('zone') == 'commander']
split_alias = {}
for e in deck['cards']:
    n = e['oracle_name']
    if ' // ' in n:
        for h in n.split(' // '): split_alias[h] = n

seen = {}          # case_id -> (won, turns, mul_game, cmdr_casts frozenset)
dup_checked = 0; dup_agree = 0
arm_of = {}
for f in glob.glob(out_dir + '/games/*.json'):
    d = json.load(open(f))
    cid = d['case_id']; arm = cid.split('|')[0]; arm_of[cid] = arm
    if d['status'] != 'completed': continue
    seed = int(cid.split('seed=')[1].split('|')[0]); seat = int(cid.split('seat=')[1])
    p = d['result']['result_payload']
    own = next(o for o in p['outcomes'] if o['seat'] == seat - 1)
    muls = 0; cast_here = set()
    for e in p['transcript']:
        if e.get('kind') != 'decision_accepted' or e.get('actor_seat') != seat - 1: continue
        if e.get('decision_class') == 'mulligan' and 'mulligan' in (e.get('selected_option_types') or []): muls += 1
        if e.get('decision_class') == 'priority':
            for lab in e.get('selected_option_labels', []):
                m = re.match(r'^(.*?) — (Cast|Play) ', lab)
                if m: cast_here.add(split_alias.get(m.group(1), m.group(1)))
    val = (1 if own['won'] else 0, p['turn_number'], 1 if muls else 0,
           frozenset(c for c in commanders if c in cast_here))
    if cid in seen:
        dup_checked += 1
        if seen[cid] == val: dup_agree += 1
    else:
        seen[cid] = val
    del d

arms = sorted(set(arm_of.values()))
base_arm = next(a for a in arms if '#' not in a)
def key(arm, seed, seat): return f"{arm}|seed={seed}|seat={seat}"
agg = {'deck': label, 'base_arm': base_arm, 'arms': {}, 'bundles': {},
       'duplicates_checked': dup_checked, 'duplicates_agree': dup_agree}
for arm in arms:
    recs = [v for c, v in seen.items() if arm_of[c] == arm]
    agg['arms'][arm] = {'games': len(recs), 'wins': sum(v[0] for v in recs),
                        'turns_mean': round(sum(v[1] for v in recs) / len(recs), 2),
                        'mulligan_games': sum(v[2] for v in recs),
                        'commander_cast_games': {c: sum(1 for v in recs if c in v[3]) for c in commanders}}
for arm in arms:
    if arm == base_arm: continue
    pairs = 0; bw = vw = bonly = vonly = 0
    for seed in range(1, 51):
        for seat in range(1, 5):
            b = seen.get(key(base_arm, seed, seat)); v = seen.get(key(arm, seed, seat))
            if b is None or v is None: continue
            pairs += 1; bw += b[0]; vw += v[0]
            if b[0] and not v[0]: bonly += 1
            if v[0] and not b[0]: vonly += 1
    diffs_disc = bonly + vonly
    eff = (vw - bw) / pairs
    hw = 1.96 * math.sqrt(diffs_disc) / pairs if pairs else 0.0
    # Sign-Test (zweiseitig, exakt ueber die diskordanten Paare)
    from math import comb
    n_d = diffs_disc; k = min(bonly, vonly)
    p_sign = min(1.0, 2 * sum(comb(n_d, i) for i in range(0, k + 1)) / 2 ** n_d) if n_d else 1.0
    agg['bundles'][arm] = {'pairs_planned': 200, 'pairs_analysed': pairs,
                           'baseline_wins': bw, 'variant_wins': vw,
                           'discordant_pairs': n_d, 'baseline_only_wins': bonly, 'variant_only_wins': vonly,
                           'effect': round(eff, 4), 'ci95': [round(eff - hw, 4), round(eff + hw, 4)],
                           'sign_test_p': round(p_sign, 4)}
print(json.dumps(agg, indent=1, ensure_ascii=False))
