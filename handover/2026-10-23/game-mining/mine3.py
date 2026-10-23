"""Dritter Durchlauf: neue Kandidaten + Determinismus-Nachpruefung."""
import glob, json, os, re
from collections import Counter, defaultdict

files = {}
for f in glob.glob('/home/hatch/workspace/tmp/m4/**/games/*.json', recursive=True):
    files.setdefault(os.path.basename(f), f)

land_missed = Counter()          # Prioritaet: Land spielbar, aber Pass gewaehlt
x_choices = defaultdict(Counter) # Klasse -> numeric_choice-Verteilung
multi_sel = Counter()            # Mehrfachauswahl: gewaehlte Anzahl
mull_chain = defaultdict(Counter)  # Position in der Kette -> Keep/Mulligan
det = defaultdict(set)           # (candidate, seed, seat, opponents) -> hashes
det_loose = defaultdict(set)     # (candidate, seed, seat) -> hashes
casts = defaultdict(lambda: {'games': 0, 'wins': 0})  # Karte (Fokal-Deck) -> Spiele/Siege
fam_games = Counter(); fam_wins = Counter()
discards = Counter()

for name, path in sorted(files.items()):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    rp = (d.get('result') or {}).get('result_payload') or {}
    sc = (d.get('result') or {}).get('scenario') or {}
    if d.get('status') != 'completed':
        continue
    opps = tuple(sorted(sc.get('opponent_deck_ids') or []))
    key = (sc.get('candidate_id'), sc.get('seed'), sc.get('seat'), opps)
    sem = (d.get('result') or {}).get('semantic_transcript_sha256')
    if sem:
        det[key].add(sem)
        det_loose[(sc.get('candidate_id'), sc.get('seed'), sc.get('seat'))].add(sem)
    cand = sc.get('candidate_id') or ''
    is_focal_deck = cand.startswith('custom/rogshai') or cand.startswith('custom/chulane')
    focal_seat = sc.get('seat')
    winners = (d.get('result') or {}).get('winner_seats') or []
    focal_won = focal_seat in winners
    game_casts = set()
    mull_pos = defaultdict(int)
    t = rp.get('transcript') or []
    req = None
    for fr in t:
        if fr.get('kind') == 'decision_requested':
            req = fr
        elif fr.get('kind') == 'decision_accepted' and req is not None:
            labels = req.get('legal_option_labels') or []
            sel = fr.get('selected_option_labels') or []
            cls = req.get('decision_class') or '?'
            prompt = req.get('prompt') or ''
            if cls == 'priority':
                playable_land = any(' — Play ' in l for l in labels)
                if playable_land:
                    if sel and sel[0] == 'Pass priority':
                        land_missed['land_spielbar_pass_gewaehlt'] += 1
                    else:
                        land_missed['land_spielbar_andere_wahl'] += 1
                if is_focal_deck and fr.get('actor_seat') == focal_seat and sel:
                    s = sel[0]
                    if ' — ' in s and not s.startswith('Pass'):
                        game_casts.add(s.split(' — ')[0])
            if fr.get('numeric_choice') is not None:
                x_choices[cls][fr['numeric_choice']] += 1
            if len(sel) > 1:
                multi_sel[len(sel)] += 1
            if cls == 'mulligan':
                actor = fr.get('actor_seat')
                pos = mull_pos[actor]; mull_pos[actor] += 1
                mull_chain[pos][sel[0] if sel else '?'] += 1
            if prompt == 'Select a card to discard' and sel:
                discards[sel[0]] += 1
            req = None
    if is_focal_deck:
        fam = 'rogshai' if 'rogshai' in cand else 'chulane'
        fam_games[fam] += 1
        fam_wins[fam] += focal_won
        for c in game_casts:
            casts[(fam, c)]['games'] += 1
            casts[(fam, c)]['wins'] += focal_won

out = {
    'land_missed': dict(land_missed),
    'x_choices': {k: dict(v.most_common(8)) for k, v in x_choices.items()},
    'multi_sel_counts': dict(multi_sel.most_common(8)),
    'mull_chain': {str(p): dict(c) for p, c in sorted(mull_chain.items())},
    'determinism_strict': {'keys': len(det), 'hashset_sizes': dict(Counter(len(v) for v in det.values()))},
    'determinism_loose': {'keys': len(det_loose), 'hashset_sizes': dict(Counter(len(v) for v in det_loose.values()))},
    'discard_top': discards.most_common(10),
    'fam_baseline': {f: {'games': fam_games[f], 'win_rate': round(fam_wins[f] / max(fam_games[f], 1), 4)} for f in fam_games},
    'cast_correlation': {},
}
for fam in ('rogshai', 'chulane'):
    base = out['fam_baseline'].get(fam, {}).get('win_rate', 0)
    rows = []
    for (f2, card), s in casts.items():
        if f2 == fam and s['games'] >= 40:
            rows.append({'card': card, 'games_cast': s['games'],
                         'win_rate_when_cast': round(s['wins'] / s['games'], 4),
                         'delta_vs_deck_baseline': round(s['wins'] / s['games'] - base, 4)})
    out['cast_correlation'][fam] = sorted(rows, key=lambda r: -abs(r['delta_vs_deck_baseline']))[:12]
json.dump(out, open('/home/hatch/workspace/tmp/mining/aggregates3.json', 'w'), indent=1)
print('land:', out['land_missed'])
print('x:', out['x_choices'])
print('det_strict:', out['determinism_strict'], 'det_loose:', out['determinism_loose'])
print('mull_chain:', out['mull_chain'])
print('discard_top:', out['discard_top'][:5])
print('cast rogshai:', out['cast_correlation']['rogshai'][:6])
print('cast chulane:', out['cast_correlation']['chulane'][:6])
