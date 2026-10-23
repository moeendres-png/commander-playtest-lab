#!/usr/bin/env python3
"""M4 Schritt 2: Aggregiert die Vergleichs-Records eines Baseline-Laufs."""
import json, glob, sys, re
from collections import Counter, defaultdict

out_dir, deck_json = sys.argv[1], sys.argv[2]
deck = json.load(open(deck_json))
deck_cards = Counter()
for e in deck['cards']:
    if e.get('zone') == 'main':
        deck_cards[e['oracle_name']] += int(e.get('quantity', 1))
commanders = [e['oracle_name'] for e in deck['cards'] if e.get('zone') == 'commander']

arms = defaultdict(list)
for f in glob.glob(out_dir + '/games/*.json'):
    d = json.load(open(f))
    cid = d['case_id']  # deck_id|seed=N|seat=M
    arm = cid.split('|')[0]
    arms[arm].append(d)

def seat_of(d): return int(d['case_id'].split('seat=')[1])
def seed_of(d): return int(d['case_id'].split('seed=')[1].split('|')[0])

split_alias = {}
for c in deck_cards:
    if ' // ' in c:
        for half in c.split(' // '):
            split_alias[half] = c
report = {'arms': {}, 'commanders': commanders}
for arm, recs in sorted(arms.items()):
    wins_seat = Counter(); games_seat = Counter(); turns = []
    mul_games = 0; mul_total = 0; casts = Counter(); cmdr_cast_games = Counter()
    decisions = []; fallbacks = 0; eng_errors = 0; failed = 0
    for d in recs:
        if d['status'] != 'completed':
            failed += 1; continue
        seat = seat_of(d); r = d['result']; p = r['result_payload']
        games_seat[seat] += 1
        own = next(o for o in p['outcomes'] if o['seat'] == seat - 1)
        if own['won']: wins_seat[seat] += 1
        turns.append(p['turn_number']); decisions.append(r['decision_count'])
        if r.get('fallback_used'): fallbacks += 1
        eng_errors += p.get('engine_error_count', 0)
        muls = 0; cast_here = set()
        for e in p['transcript']:
            if e.get('kind') != 'decision_accepted' or e.get('actor_seat') != seat - 1:
                continue
            if e.get('decision_class') == 'mulligan' and 'mulligan' in (e.get('selected_option_types') or []):
                muls += 1
            if e.get('decision_class') == 'priority':
                for lab in e.get('selected_option_labels', []):
                    m = re.match(r'^(.*?) — (Cast|Play) ', lab)
                    if m:
                        name = split_alias.get(m.group(1), m.group(1))
                        casts[name] += 1; cast_here.add(name)
        mul_total += muls
        if muls: mul_games += 1
        for c in commanders:
            if c in cast_here: cmdr_cast_games[c] += 1
    n = sum(games_seat.values())
    report['arms'][arm] = {
        'games': n, 'failed': failed,
        'wins_by_seat': {s: wins_seat[s] for s in sorted(games_seat)},
        'games_by_seat': {s: games_seat[s] for s in sorted(games_seat)},
        'win_share_by_seat': {s: round(wins_seat[s] / games_seat[s], 3) for s in sorted(games_seat)},
        'win_share_total': round(sum(wins_seat.values()) / n, 3) if n else None,
        'mean_turns': round(sum(turns) / len(turns), 1) if turns else None,
        'mulligan_games_share': round(mul_games / n, 3) if n else None,
        'mulligans_per_game': round(mul_total / n, 2) if n else None,
        'mean_decisions': round(sum(decisions) / len(decisions)) if decisions else None,
        'fallback_games': fallbacks, 'engine_errors': eng_errors,
        'commander_cast_games': dict(cmdr_cast_games),
        'casts': dict(casts.most_common()),
        'dead_cards': sorted([c for c in deck_cards if casts.get(c, 0) == 0]),
        'rare_cards_le2': sorted([c for c in deck_cards if 0 < casts.get(c, 0) <= 2]),
    }

# Twin-Abgleich: Baseline-Arm vs. Varianten-Arm (identische Decks)
ids = sorted(arms)
if len(ids) == 2:
    a, b = ids
    ha = { (seed_of(d), seat_of(d)): d['result']['semantic_transcript_sha256'] for d in arms[a] if d['status'] == 'completed' }
    hb = { (seed_of(d), seat_of(d)): d['result']['semantic_transcript_sha256'] for d in arms[b] if d['status'] == 'completed' }
    pairs = set(ha) & set(hb)
    diff = [k for k in pairs if ha[k] != hb[k]]
    report['twin_check'] = {'pairs': len(pairs), 'hash_mismatch': len(diff), 'mismatch_cases': [str(k) for k in diff[:10]]}
print(json.dumps(report, indent=1))
