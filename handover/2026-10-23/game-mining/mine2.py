"""Zweiter, vertiefter Durchlauf: Schnitte, die der erste Lauf nicht hatte."""
import glob, json, os, re
from collections import Counter, defaultdict

files = {}
for f in glob.glob('/home/hatch/workspace/tmp/m4/**/games/*.json', recursive=True):
    files.setdefault(os.path.basename(f), f)

prio_actor = defaultdict(lambda: {'n': 0, 'act': 0})     # je Akteur relativ zum Fokal-Sitz
prio_third = defaultdict(lambda: {'n': 0, 'act': 0})     # Sequenz-Drittel
target_idx0_kind = Counter()                              # Art des Index-0-Ziels / gewaehlten Ziels
target_sel_kind = Counter()
mana_idx = defaultdict(Counter)                         # Index -> Label-Typ
chooseuse_prompts = defaultdict(lambda: {'n': 0, 'yes': 0})
combat = Counter()
determinism = {}                                          # (case, seed) -> set(semantic hashes)
slow_mix = {'slow': Counter(), 'slow_n': 0, 'mid': Counter(), 'mid_n': 0}
win_by_len = defaultdict(Counter)

def mana_type(label):
    if label.startswith('Spend ') and 'from pool' in label:
        return 'pool_spend'
    if '{T}: Add' in label:
        return 'land_tap'
    if 'mana' in label.lower():
        return 'other_mana'
    return 'other'

for name, path in sorted(files.items()):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    rp = (d.get('result') or {}).get('result_payload') or {}
    sc = (d.get('result') or {}).get('scenario') or {}
    if d.get('status') != 'completed':
        continue
    key = (sc.get('candidate_id'), sc.get('seed'), sc.get('seat'))
    sem = (d.get('result') or {}).get('semantic_transcript_sha256')
    if sem:
        determinism.setdefault(key, set()).add(sem)
    t = rp.get('transcript') or []
    total_dec = max(rp.get('decision_count') or 1, 1)
    seq_i = 0
    req = None
    cls_game = Counter()
    for fr in t:
        if fr.get('kind') == 'decision_requested':
            req = fr
        elif fr.get('kind') == 'decision_accepted' and req is not None:
            seq_i += 1
            labels = req.get('legal_option_labels') or []
            sel = fr.get('selected_option_labels') or []
            cls = req.get('decision_class') or '?'
            cls_game[cls] += 1
            actor = fr.get('actor_seat')
            focal = sc.get('seat')
            if cls == 'priority':
                acted = not (sel and sel[0] == 'Pass priority')
                rel = 'focal' if actor == focal else 'other'
                prio_actor[rel]['n'] += 1
                prio_actor[rel]['act'] += acted
                third = min(seq_i * 3 // total_dec, 2)
                prio_third[third]['n'] += 1
                prio_third[third]['act'] += acted
            elif cls == 'target':
                def kind(lbl):
                    if lbl.startswith('Full Game Seat'):
                        return 'player'
                    return 'permanent'
                if labels:
                    target_idx0_kind[kind(labels[0])] += 1
                if sel:
                    target_sel_kind[kind(sel[0])] += 1
            elif cls == 'mana_payment':
                for s in sel:
                    if s in labels:
                        mana_idx[labels.index(s)][mana_type(s)] += 1
            elif cls == 'choose_use':
                p = req.get('prompt') or ''
                chooseuse_prompts[p]['n'] += 1
                if sel and sel[0] == 'Yes':
                    chooseuse_prompts[p]['yes'] += 1
            elif cls == 'declare_attacker':
                combat['attacker_decisions'] += 1
                combat['attacker_selected_total'] += len(sel)
                if not sel:
                    combat['no_attack'] += 1
            elif cls == 'declare_blocker':
                combat['blocker_decisions'] += 1
                if sel:
                    combat['block_assigned'] += 1
                else:
                    combat['no_block'] += 1
            req = None
    el = d.get('elapsed_seconds') or 0
    bucket = 'slow' if el >= 71 else 'mid'
    slow_mix[bucket + '_n'] = slow_mix.get(bucket + '_n', 0) + 1
    slow_mix[bucket].update(cls_game)
    turns = rp.get('turn_number') or 0
    q = 'kurz<=40' if turns <= 40 else ('mittel41-55' if turns <= 55 else 'lang>55')
    w = (d.get('result') or {}).get('winner_seats') or []
    if w and rp.get('starting_player_seat') is not None:
        win_by_len[q][(w[0] - rp['starting_player_seat']) % 4] += 1

out = {
    'prio_actor': {k: {'n': v['n'], 'act_rate': round(v['act'] / max(v['n'], 1), 4)} for k, v in prio_actor.items()},
    'prio_third': {str(k): {'n': v['n'], 'act_rate': round(v['act'] / max(v['n'], 1), 4)} for k, v in sorted(prio_third.items())},
    'target_idx0_kind': dict(target_idx0_kind),
    'target_sel_kind': dict(target_sel_kind),
    'mana_idx_types': {str(i): dict(c) for i, c in sorted(mana_idx.items())[:5]},
    'chooseuse_top': sorted(({'prompt': p, 'n': s['n'], 'yes_rate': round(s['yes'] / max(s['n'], 1), 3)}
                             for p, s in chooseuse_prompts.items()), key=lambda x: -x['n'])[:10],
    'combat': dict(combat),
    'determinism': {'keys': len(determinism),
                    'keys_multi_record': sum(1 for v in determinism.values() if True),
                    'hash_sets': Counter(len(v) for v in determinism.values())},
    'slow_vs_mid_mix': {b: {c: round(n / max(slow_mix[b + '_n'], 1), 1) for c, n in slow_mix[b].most_common(6)}
                        for b in ('slow', 'mid')},
    'win_by_len': {q: dict(c) for q, c in win_by_len.items()},
}
# Determinismus korrekt zaehlen: Gruppen mit mehreren Records brauchen die Rohdaten;
# hier: Anzahl Keys und Hash-Mengen-Groessen (1 = alle Records gleich)
out['determinism'] = {'distinct_case_seed_seat': len(determinism),
                      'hashset_sizes': dict(Counter(len(v) for v in determinism.values()))}
json.dump(out, open('/home/hatch/workspace/tmp/mining/aggregates2.json', 'w'), indent=1)
print(json.dumps(out, indent=1)[:3000])
