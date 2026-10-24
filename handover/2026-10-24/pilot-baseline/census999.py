"""#999 M1-Zensus: gleiche Kennzahlen wie census.json, parametrisiert aufs Spiele-Verzeichnis.
Kontrolle + neue Baseline nutzen dasselbe Skript (Wrong-Reason-Schutz)."""
import glob, json, os, sys
from collections import Counter, defaultdict

pattern = sys.argv[1]
out_path = sys.argv[2]
files = {}
for f in glob.glob(pattern, recursive=True):
    files.setdefault(os.path.basename(f), f)

cls = defaultdict(lambda: {'n': 0, 'idx0': 0, 'one_option': 0})
total = 0
games_done = games_aborted = 0
abort_causes = Counter()
mull_by_pos = defaultdict(lambda: {'keep': 0, 'total': 0})
announce_x = Counter()
choose_use_prompts = defaultdict(lambda: {'yes': 0, 'total': 0})
cancelled_payments = 0
for name, path in sorted(files.items()):
    try:
        d = json.load(open(path))
    except Exception:
        games_aborted += 1; abort_causes['unlesbar'] += 1; continue
    if d.get('status') != 'completed':
        games_aborted += 1; abort_causes[str(d.get('status'))] += 1; continue
    games_done += 1
    t = (d.get('result') or {}).get('result_payload', {}).get('transcript') or []
    req = None
    mull_seen = defaultdict(int)
    for fr in t:
        if fr.get('kind') == 'decision_requested':
            req = fr
        elif fr.get('kind') == 'decision_accepted' and req is not None:
            total += 1
            labels = req.get('legal_option_labels') or []
            sel = fr.get('selected_option_labels') or []
            c = req.get('decision_class') or '?'
            s = cls[c]; s['n'] += 1
            if len(labels) == 1: s['one_option'] += 1
            if sel and labels and sel[0] == labels[0]: s['idx0'] += 1
            if c == 'mulligan':
                actor = fr.get('actor_seat')
                pos = mull_seen[actor]; mull_seen[actor] += 1
                m = mull_by_pos[pos]; m['total'] += 1
                if sel and sel[0] == 'Keep opening hand': m['keep'] += 1
            if c == 'announce_x' and sel:
                announce_x[sel[0]] += 1
            if c == 'choose_use':
                p = req.get('prompt') or ''
                cu = choose_use_prompts[p]; cu['total'] += 1
                if sel and sel[0] == 'Yes': cu['yes'] += 1
            if c == 'mana_payment':
                if fr.get('cancelled') or (sel and any('cancel' in str(x).lower() for x in sel)):
                    cancelled_payments += 1
            req = None

out = {
  'games_files': len(files), 'games_completed': games_done, 'games_aborted': games_aborted,
  'abort_causes': dict(abort_causes), 'decisions_total': total,
  'classes': {c: {'n': s['n'], 'idx0_rate': round(s['idx0']/s['n'], 4) if s['n'] else None,
                  'one_option_rate': round(s['one_option']/s['n'], 4) if s['n'] else None}
              for c, s in sorted(cls.items(), key=lambda kv: -kv[1]['n'])},
  'mulligan_by_position': {str(p): {'keep': m['keep'], 'total': m['total'],
                  'keep_rate': round(m['keep']/m['total'], 4) if m['total'] else None}
                  for p, m in sorted(mull_by_pos.items())},
  'announce_x_top': announce_x.most_common(15),
  'choose_use_top10': [{'prompt': p, 'yes': v['yes'], 'total': v['total'],
                  'yes_rate': round(v['yes']/v['total'], 4)}
                  for p, v in sorted(choose_use_prompts.items(), key=lambda kv: -kv[1]['total'])[:10]],
  'cancelled_payments': cancelled_payments,
  'cancelled_per_1000': round(cancelled_payments / total * 1000, 3) if total else None,
}
json.dump(out, open(out_path, 'w'), indent=1)
print('Spiele:', games_done, 'abgebrochen:', games_aborted, '| Entscheidungen:', total)
pr = out['classes'].get('priority', {})
print('KONTROLLE priority idx0:', pr.get('idx0_rate'))
mk = sum(m['keep'] for m in mull_by_pos.values()); mt = sum(m['total'] for m in mull_by_pos.values())
print('KONTROLLE mulligan Keep gesamt:', round(mk/mt, 4) if mt else None, f'({mk}/{mt})')
print('cancelled/1000:', out['cancelled_per_1000'])
