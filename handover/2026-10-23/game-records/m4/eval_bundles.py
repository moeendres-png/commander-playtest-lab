#!/usr/bin/env python3
"""M4 Schritt 4: Gepaarte Auswertung eines Buendel-Laufs (Baseline vs. Varianten)."""
import json, glob, sys, math
from collections import defaultdict

out_dir, names = sys.argv[1], sys.argv[2].split(',')
def load(arm_filter):
    res = {}
    for f in glob.glob(out_dir + '/games/*.json'):
        d = json.load(open(f))
        cid = d['case_id']
        arm = cid.split('|')[0]
        if arm != arm_filter: continue
        seed = int(cid.split('seed=')[1].split('|')[0]); seat = int(cid.split('seat=')[1])
        if d['status'] != 'completed': res[(seed, seat)] = None; continue
        p = d['result']['result_payload']
        own = next(o for o in p['outcomes'] if o['seat'] == seat - 1)
        res[(seed, seat)] = (1 if own['won'] else 0, p['turn_number'])
    return res

base = load(names[0])
print(f"Baseline {names[0]}: {sum(1 for v in base.values() if v is not None)} Spiele, WR {sum(v[0] for v in base.values() if v)/max(1,sum(1 for v in base.values() if v is not None)):.3f}")
for arm, label in zip(names[1:], ('R-A/C-A', 'R-B/C-B', 'R-C/C-C')):
    var = load(arm)
    pairs = [(base[k][0], var[k][0]) for k in base if base.get(k) and var.get(k)]
    n = len(pairs)
    diffs = [v - b for b, v in pairs]
    eff = sum(diffs) / n
    var_d = sum((x - eff) ** 2 for x in diffs) / (n - 1)
    se = math.sqrt(var_d / n)
    lo, hi = eff - 1.96 * se, eff + 1.96 * se
    disc = sum(1 for x in diffs if x != 0)
    verdict = 'VARIANT_BETTER' if lo > 0.125 else ('BASELINE_BETTER' if hi < -0.125 else 'UNDECIDED')
    print(f"{arm} ({label}): Paare {n}, diskordant {disc}, Effekt {eff:+.3f}, 95%-KI [{lo:+.3f}, {hi:+.3f}] -> {verdict}")
    print(f"   Siege Baseline-Seite {sum(b for b, v in pairs)}, Varianten-Seite {sum(v for b, v in pairs)}")
