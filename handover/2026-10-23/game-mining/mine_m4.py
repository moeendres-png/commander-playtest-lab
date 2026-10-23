"""Ein Durchlauf ueber alle einzigartigen M4-Spieltranskripte.
Erzeugt features.jsonl (eine kompakte Zeile je Spiel) und aggregates.json
(Entscheidungs-Statistik global + je Familie). Nur Lesezugriff."""
import glob, json, os, sys
from collections import Counter, defaultdict

OUT = '/home/hatch/workspace/tmp/mining'
files = {}
for f in glob.glob('/home/hatch/workspace/tmp/m4/**/games/*.json', recursive=True):
    files.setdefault(os.path.basename(f), f)
print(f'{len(files)} einzigartige Spiele', flush=True)

def fam_of(path):
    rel = os.path.relpath(path, '/home/hatch/workspace/tmp/m4')
    return rel.split(os.sep)[0]

# Aggregat-Strukturen
cls_stats = defaultdict(lambda: {'n': 0, 'opts': 0, 'idx': Counter(), 'multi': 0})
cls_stats_fam = defaultdict(lambda: defaultdict(lambda: {'n': 0, 'idx0': 0}))
prompt_stats = defaultdict(lambda: {'n': 0, 'idx0': 0, 'opts': 0})
mull = Counter()
startpick = Counter()
pass_stats = Counter()
rows = []

for i, (name, path) in enumerate(sorted(files.items())):
    if i % 250 == 0:
        print(f'{i}/{len(files)}', flush=True)
    try:
        d = json.load(open(path))
    except Exception as e:
        print('PARSE-FEHLER', name, e, flush=True)
        continue
    rp = (d.get('result') or {}).get('result_payload') or {}
    sc = (d.get('result') or {}).get('scenario') or {}
    fam = fam_of(path)
    focal_seat = sc.get('seat')
    winners = (d.get('result') or {}).get('winner_seats') or []
    row = {
        'file': name, 'family': fam, 'case': d.get('case_id'),
        'status': d.get('status'), 'failure_class': d.get('failure_class'),
        'seed': sc.get('seed'), 'focal_seat': focal_seat,
        'candidate': sc.get('candidate_id'),
        'winners': winners, 'focal_won': (focal_seat in winners) if winners else None,
        'turns': rp.get('turn_number'), 'decisions': rp.get('decision_count'),
        'elapsed_s': d.get('elapsed_seconds'),
        'starting_seat': rp.get('starting_player_seat'),
        'winner_rel_to_start': None,
    }
    if winners and rp.get('starting_player_seat') is not None:
        row['winner_rel_to_start'] = (winners[0] - rp['starting_player_seat']) % 4
    t = rp.get('transcript') or []
    req = None
    game_cls = Counter()
    for fr in t:
        if fr.get('kind') == 'decision_requested':
            req = fr
        elif fr.get('kind') == 'decision_accepted' and req is not None:
            labels = req.get('legal_option_labels') or []
            sel = fr.get('selected_option_labels') or []
            cls = req.get('decision_class') or '?'
            prompt = req.get('prompt') or ''
            idxs = []
            for s in sel:
                if s in labels:
                    idxs.append(labels.index(s))
            st = cls_stats[cls]
            st['n'] += 1
            st['opts'] += len(labels)
            if idxs:
                st['idx'][idxs[0]] += 1
                if idxs[0] == 0:
                    cls_stats_fam[fam][cls]['idx0'] += 1
                    prompt_stats[prompt]['idx0'] += 1
                if len(idxs) > 1:
                    st['multi'] += 1
            cls_stats_fam[fam][cls]['n'] += 1
            prompt_stats[prompt]['n'] += 1
            prompt_stats[prompt]['opts'] += len(labels)
            game_cls[cls] += 1
            pl = prompt.lower()
            if 'mulligan' in pl or 'keep' in [x.lower() for x in sel]:
                if 'mulligan' in pl:
                    mull[tuple(sel)] += 1
            if prompt == 'Select a starting player' and sel:
                startpick[(fr.get('actor_seat'), sel[0])] += 1
            if any(x.lower() == 'pass' for x in labels):
                pass_stats['mit_pass_option'] += 1
                if sel and sel[0].lower() == 'pass':
                    pass_stats['pass_gewaehlt'] += 1
                elif len(labels) > 1:
                    pass_stats['statt_pass_andere'] += 1
            req = None
    row['top_classes'] = game_cls.most_common(5)
    rows.append(row)

json.dump(rows, open(os.path.join(OUT, 'features.jsonl'), 'w'))
agg = {
    'games': len(rows),
    'cls_stats': {k: {'n': v['n'], 'mean_opts': round(v['opts'] / max(v['n'], 1), 2),
                      'idx_hist': {str(i): v['idx'][i] for i in sorted(v['idx'])[:8]},
                      'idx0_rate': round(v['idx'][0] / max(v['n'], 1), 4),
                      'multi': v['multi']} for k, v in cls_stats.items()},
    'cls_by_family': {f: {c: {'n': s['n'], 'idx0_rate': round(s['idx0'] / max(s['n'], 1), 4)}
                          for c, s in cs.items()} for f, cs in cls_stats_fam.items()},
    'top_prompts': sorted(({'prompt': p, 'n': s['n'], 'idx0_rate': round(s['idx0'] / max(s['n'], 1), 4),
                            'mean_opts': round(s['opts'] / max(s['n'], 1), 2)}
                           for p, s in prompt_stats.items()), key=lambda x: -x['n'])[:40],
    'mulligan_selections': {str(k): v for k, v in mull.most_common(10)},
    'startpick': {str(k): v for k, v in startpick.most_common(12)},
    'pass_stats': dict(pass_stats),
}
json.dump(agg, open(os.path.join(OUT, 'aggregates.json'), 'w'), indent=1)
print('FERTIG:', len(rows), 'Spiele ausgewertet')
