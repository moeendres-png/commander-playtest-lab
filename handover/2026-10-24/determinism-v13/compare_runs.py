"""Erste abweichende Stelle zwischen zwei Rate-Transkripten (Probe-Normalisierung)."""
import json, sys
sys.path.insert(0, '/home/hatch/workspace/github/wt-1001/scripts')
from determinism_probe import normalise

def load(p):
    d = json.load(open(p))
    return d['case'], d['semantic'], d['transcript']

def el_key(f):
    k = f.get('kind')
    if k == 'decision_requested':
        return ('req', f['decision_class'], f['actor_seat'], normalise(f['prompt']),
                tuple(f['legal_option_types']), tuple(normalise(f['legal_option_labels'])))
    if k == 'decision_accepted':
        return ('acc', f['decision_class'], f['actor_seat'], normalise(f['prompt']),
                tuple(f['selected_option_types']), tuple(normalise(f['selected_option_labels'])), f['numeric_choice'])
    return ('other', normalise(f))

def show(f, tag):
    if f.get('kind') == 'decision_requested':
        print(f"  {tag} seq={f['sequence']} {f['decision_class']} seat={f['actor_seat']} prompt={f['prompt']!r}")
        print(f"    options({len(f['legal_option_labels'])}): {f['legal_option_labels'][:14]}")
    elif f.get('kind') == 'decision_accepted':
        print(f"  {tag} seq={f['sequence']} {f['decision_class']} seat={f['actor_seat']} prompt={f['prompt']!r}")
        print(f"    selected: {f['selected_option_labels']}")
    else:
        print(f"  {tag} other frame: {json.dumps(f)[:400]}")

a_p, b_p = sys.argv[1], sys.argv[2]
ca, ha, ta = load(a_p); cb, hb, tb = load(b_p)
print(f'A: {ca} {ha[:16]} frames={len(ta)}')
print(f'B: {cb} {hb[:16]} frames={len(tb)}')
for i in range(min(len(ta), len(tb))):
    if el_key(ta[i]) != el_key(tb[i]):
        print(f'Erste Differenz: Frame-Index {i} (seq {ta[i].get("sequence", "?")})')
        for j in range(max(0, i-2), i):
            fj = ta[j]
            print(f"  Kontext {j}: seq={fj.get('sequence', '?')} {fj.get('kind')} {fj.get('decision_class', '')} seat={fj.get('actor_seat', '')} {str(fj.get('prompt', ''))[:70]!r}")
        show(ta[i], 'A'); show(tb[i], 'B')
        break
else:
    print('Keine Differenz im gemeinsamen Praefix; Laengen:', len(ta), len(tb))
