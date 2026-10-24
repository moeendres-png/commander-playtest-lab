"""#999 M3: Power im gepaarten Design (McNemar). Validierung: Formel muss die
M4-Nachweisgrenzen (CI-Halbbreiten 3,4-4,8 Punkte bei 200 Paaren) zurueckgeben."""
import json, math
Z_A, Z_B = 1.959964, 0.841621  # alpha 5% zweiseitig, Power 80%
bundles = {}
for deck, fn in (('RogShai', 'aggregate_rogshai'), ('Chulane', 'aggregate_chulane')):
    d = json.load(open(f'/home/hatch/workspace/tmp/m4/{fn}.json'))
    for arm, b in d['bundles'].items():
        bundles[f"{deck}:{arm.split('#')[-1]}"] = b
rows = []
tot_disc = tot_pairs = 0
for name, b in bundles.items():
    n, disc = b['pairs_analysed'], b['discordant_pairs']
    tot_disc += disc; tot_pairs += n
    x = Z_A * math.sqrt(disc) / n
    rows.append({'bundle': name, 'pairs': n, 'discordant': disc, 'q': round(disc/n, 4),
                 'ci_half_reported': max(abs(b['ci95'][0]), abs(b['ci95'][1])),
                 'ci_half_formula': round(x, 4)})
q_pool = tot_disc / tot_pairs
def pairs_needed(delta, q):
    return math.ceil(((Z_A + Z_B) ** 2) * q / (delta ** 2))
out = {'validation_ci_halfwidths': rows,
       'known_m4_range_points': [3.4, 4.8],
       'formula_range_points': [round(min(r['ci_half_formula'] for r in rows)*100, 1),
                                round(max(r['ci_half_formula'] for r in rows)*100, 1)],
       'q_pooled': round(q_pool, 4), 'discordant_total': tot_disc, 'pairs_total': tot_pairs,
       'table_pooled': {f'{int(d*100)}_points': pairs_needed(d, q_pool) for d in (0.02, 0.03, 0.05)},
       'table_per_deck': {}}
for deck in ('RogShai', 'Chulane'):
    ds = [r for r in rows if r['bundle'].startswith(deck)]
    q = sum(r['discordant'] for r in ds) / sum(r['pairs'] for r in ds)
    out['table_per_deck'][deck] = {'q': round(q, 4),
        'pairs': {f'{int(d*100)}_points': pairs_needed(d, q) for d in (0.02, 0.03, 0.05)}}
json.dump(out, open('/home/hatch/workspace/tmp/999/m3.json', 'w'), indent=1)
for r in rows: print(r)
print('q pooled:', round(q_pool, 4), '| Formel-Spanne (Punkte):', out['formula_range_points'], 'vs bekannt [3.4, 4.8]')
print('Tabelle gepoolt:', out['table_pooled'])
print('Je Deck:', out['table_per_deck'])
