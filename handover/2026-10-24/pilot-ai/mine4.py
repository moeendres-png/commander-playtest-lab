"""Vollzensus: JEDE Entscheidungsklasse, Trivialitaets-Anteile, Kampf-Rekonstruktion."""
import glob, json, os
from collections import Counter, defaultdict

files = {}
for f in glob.glob('/home/hatch/workspace/tmp/m4/**/games/*.json', recursive=True):
    files.setdefault(os.path.basename(f), f)

cls = defaultdict(lambda: {'n': 0, 'opts_hist': Counter(), 'idx': Counter(), 'one_option': 0,
                           'sel_labels': Counter(), 'prompts': Counter()})
combats = Counter()          # Angreifer je Kampf (zusammenhaengende Deklarationen eines Akteurs)
total = 0
for name, path in sorted(files.items()):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    if d.get('status') != 'completed':
        continue
    t = (d.get('result') or {}).get('result_payload', {}).get('transcript') or []
    req = None
    run_actor, run_len = None, 0
    for fr in t:
        if fr.get('kind') == 'decision_requested':
            req = fr
        elif fr.get('kind') == 'decision_accepted' and req is not None:
            total += 1
            labels = req.get('legal_option_labels') or []
            sel = fr.get('selected_option_labels') or []
            c = req.get('decision_class') or '?'
            s = cls[c]
            s['n'] += 1
            s['opts_hist'][len(labels)] += 1
            if len(labels) == 1:
                s['one_option'] += 1
            if sel and sel[0] in labels:
                s['idx'][labels.index(sel[0])] += 1
            if len(s['sel_labels']) < 4000:
                s['sel_labels'][tuple(sel)] += 1
            s['prompts'][req.get('prompt') or ''] += 1
            if c == 'declare_attacker':
                a = fr.get('actor_seat')
                if a == run_actor:
                    run_len += 1
                else:
                    if run_len:
                        combats[run_len] += 1
                    run_actor, run_len = a, 1
            req = None
    if run_len:
        combats[run_len] += 1

out = {'total_decisions': total, 'classes': {}}
for c, s in sorted(cls.items(), key=lambda x: -x[1]['n']):
    n = s['n']
    out['classes'][c] = {
        'n': n, 'share': round(n / total, 4),
        'one_option_rate': round(s['one_option'] / n, 4),
        'mean_opts': round(sum(k * v for k, v in s['opts_hist'].items()) / n, 2),
        'idx0_rate': round(s['idx'][0] / max(sum(s['idx'].values()), 1), 4),
        'top_prompts': s['prompts'].most_common(4),
        'top_selections': [(list(k), v) for k, v in s['sel_labels'].most_common(4)],
    }
out['attackers_per_combat_run'] = dict(sorted(combats.items()))
json.dump(out, open('/home/hatch/workspace/tmp/mining/census.json', 'w'), indent=1)
print('Gesamt-Entscheidungen (completed):', total)
print('Klassen:', len(out['classes']))
trivial = sum(v['n'] * v['one_option_rate'] for v in out['classes'].values())
print(f"Trivial (genau 1 Option): {trivial:.0f} = {trivial/total:.1%}")
print('Angreifer je Deklarations-Lauf:', out['attackers_per_combat_run'])
