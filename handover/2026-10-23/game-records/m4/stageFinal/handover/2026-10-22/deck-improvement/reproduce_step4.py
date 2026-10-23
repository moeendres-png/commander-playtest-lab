#!/usr/bin/env python3
"""M4 Schritt 4: Reproduziert die Berichtszahlen aus den Aggregat-JSONs.
Liest NUR die Aggregate (Paar-Zaehlungen), leitet Effekt, 95%-Intervall
(Normalapproximation ueber die diskordanten Paare), Sign-Test und Verdikt ab.
Aufruf: reproduce_step4.py aggregate_rogshai.json aggregate_chulane.json"""
import json, sys, math
from math import comb

def sign_p(bonly, vonly):
    n = bonly + vonly
    if n == 0: return 1.0
    k = min(bonly, vonly)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

for path in sys.argv[1:]:
    agg = json.load(open(path))
    print(f"== {agg['deck']} (Baseline-Arm {agg['base_arm']})")
    base = agg['arms'][agg['base_arm']]
    print(f"   Baseline: {base['wins']}/{base['games']} Siege, Zuege {base['turns_mean']}, Mulligan-Spiele {base['mulligan_games']}")
    for arm, b in sorted(agg['bundles'].items()):
        n = b['pairs_analysed']
        eff = (b['variant_wins'] - b['baseline_wins']) / n
        hw = 1.96 * math.sqrt(b['discordant_pairs']) / n
        p = sign_p(b['baseline_only_wins'], b['variant_only_wins'])
        if p < 0.05 and eff > 0: verdict = 'VARIANT_BETTER'
        elif p < 0.05 and eff < 0: verdict = 'BASELINE_BETTER'
        else: verdict = f"UNDECIDED, could only see effects of at least {hw * 100:.1f} points"
        print(f"   {arm}: Paare {n}, Siege {b['variant_wins']}:{b['baseline_wins']}, diskordant {b['discordant_pairs']}, "
              f"Effekt {eff:+.3f}, 95%-KI [{eff - hw:+.3f}, {eff + hw:+.3f}], Sign-Test p={p:.3f} -> {verdict}")
