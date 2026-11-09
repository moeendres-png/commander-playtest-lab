# Why one deck wins so often in the pods: pod effect, round-robin of real precons (2026-11-09)

Refs #1070. Measurement only: no pilot, bridge, fork, pin, deck or sealed record changes, so nothing here needs
requalification or a new reference. Evidence class `LOCAL_OBSERVED`, exploratory, no CI credit, counts and
intervals that treat games as independent, not win-rate estimates: **the win rate stays UNDECIDED**.
Follows from section 3 of `PILOT_CALIBRATION_REAL_PLAYERS_2026-11-09.md` (Lorehold Spirit 12 of 24, The Hosts of
Mordor 6 of 12, against real precon rates of 27.3 % and 19.6 %).

## 1. Answer in short

1. **Part of the Lorehold Spirit gap is the table, not the deck.** In the Chulane pods Lorehold Spirit won 12 of
   24 (`mixed` 7 of 12 with Chulane, Kaervek, Animated Army; `precon` 5 of 12 with Chulane, Animated Army, Token
   Triumph). Against three other real precons it wins 14 of 48 games (29 %, real 27.3 %). The 21-point gap is
   about 1.7 standard errors: suggestive, not proven.
2. **Three decks stay away from their real rates**: The Hosts of Mordor 16 of 48 (33 %, real 19.6 %), Eldrazi
   Unbound 16 of 48 (33 %, real 24.7 %) and Token Triumph 5 of 48 (10 %, real 26.5 %). Token Triumph and Hosts of
   Mordor lie outside the 95 % interval, Eldrazi Unbound inside it.
3. **Games are decided by who is left alone**: in 33 of 36 recorded games the winner received the fewest attacks
   of the four seats, in none the most. That describes the games; it does not say which came first (below).

## 2. Round-robin of five real precons (no Chulane)

Decks: Lorehold Spirit, Animated Army, Token Triumph, Eldrazi Unbound, The Hosts of Mordor (the repository files
the other pods use). Five pods of four, each pod leaves one deck out, seeds 1-12, 60 games. The deck order of a
pod is shifted by `seed % 4`, so no deck keeps one seat index. `main` `cdda035af` (pilot of #1149), jar sha256
`36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`, pin `f4d12f6e80`, two games at a time. 60 of
60 games finished, no draw, mean 10.8 rounds. Data:
`measurements-2026-11-09/roundrobin5_precons_seeds1-12_cdda035af.json`.

| Deck | Wins in the round-robin | Share | Wilson 95 % | Real (4P-normalized) | Wins in the Chulane pods |
|---|---|---|---|---|---|
| Lorehold Spirit | 14 of 48 | 29.2 % | 18.2-43.2 % | 27.3 % | 12 of 24 |
| Animated Army | 9 of 48 | 18.8 % | 10.2-31.9 % | 21.6 % | 5 of 24 |
| Token Triumph | 5 of 48 | 10.4 % | 4.5-22.2 % | 26.5 % | 4 of 12 |
| Eldrazi Unbound | 16 of 48 | 33.3 % | 21.7-47.5 % | 24.7 % | 2 of 12 |
| The Hosts of Mordor | 16 of 48 | 33.3 % | 21.7-47.5 % | 19.6 % | 6 of 12 |

Wins per pod (12 games each):

| Pod (deck left out) | Animated Army | Lorehold | Token Triumph | Eldrazi | Hosts |
|---|---|---|---|---|---|
| without Lorehold | 2 | - | 0 | 7 | 3 |
| without Animated Army | - | 4 | 0 | 2 | 6 |
| without Token Triumph | 2 | 2 | - | 4 | 4 |
| without Eldrazi | 3 | 5 | 1 | - | 3 |
| without Hosts | 2 | 3 | 4 | 3 | - |

The intervals treat the 48 games of a deck as independent and the five pods overlap, so they are a guide to
the size of the noise, not a test. The real rates come from Playgroup's 4P-normalized precon list (pods of
whatever precons people met). How often a deck wins depends on who else sits at the table: Lorehold Spirit won
12 of 24 in the Chulane pods (with the pilot before #1149: 12 of 24 as well, 9 of 12 in `mixed` and 3 of 12 in
`precon`) and 14 of 48 here; The Hosts of Mordor won 6 of 12 in the Chulane `optimized` pod (10 of 12 before
#1149) and 16 of 48 here.

## 3. Behaviour signatures of the five decks (round-robin, per deck over its 48 games)

| Deck | Attacks per game | Blocks per game | Spells per own turn | Commander first cast (mean round) | Mulligans per game | Eliminated first |
|---|---|---|---|---|---|---|
| Lorehold Spirit | 20.9 | 11.4 | 1.48 | 4.6 | 1.3 | 19 of 60 games |
| Animated Army | 11.3 | 2.8 | 1.29 | 3.4 | 1.6 | 8 |
| Token Triumph | 14.5 | 4.9 | 1.25 | 2.6 | 1.3 | 20 |
| Eldrazi Unbound | 12.2 | 2.0 | 1.00 | 5.7 | 1.5 | 6 |
| The Hosts of Mordor | 13.7 | 2.0 | 1.09 | 7.7 | 1.6 | 7 |

(Commander round is over the games in which it was cast; Eldrazi Unbound did not cast it by round 8 or at all in
17 of 48 games and Hosts of Mordor in 21 of 48. Hosts of Mordor won 13 of the 27 games in which it cast the
commander in rounds 5-8 and 3 of the 21 in which it did not.) Mean finishing rank (1 first out, 4 winner, chance
2.5): Token Triumph 2.08, Lorehold Spirit 2.27, Animated Army 2.50, Hosts of Mordor 2.75, Eldrazi Unbound 2.90.
Lorehold Spirit is eliminated first about as often as Token Triumph and still wins 14 of 48, so its results are
spread wide.

Token Triumph casts its commander earliest (round 2.6) and still finishes behind: this is the signature to look at
first (tokens and their payoffs, chump blocks, how its attackers are met), not a card verdict.

## 4. Who is attacked (the 36 Chulane-pod games, all seats)

2076 attacker declarations against a living opponent, 1704 of them with at least two opponents alive. The games
ran on the draft branch of PR 1152 (bounce land after spells), which changes the pilot in that one respect;
targeting is not touched. Data: `measurements-2026-11-09/attack_targets_chulane_pods_36_games.json`.

- The attacked opponent was the one with the lowest life in 57.4 % of declarations, the one with the highest life
  in 32.6 %, the one with the largest board in 57.6 %. A pick of one named opponent at random would be 38.3 %.
- The design is "threat plus a bonus that grows as life gets low" (`focus_defender` in
  `full_game_pilot_views.py`), and attacks that a blocker cannot punish score higher (`attack_score`).
- The winner received the fewest attacks of the four seats in 33 of 36 games and the most in 0 (chance about 9
  each). Share of all attacks received per deck: Chulane 27.5 %, Kaervek 27.3 %, Eldrazi Unbound 26.1 %, Animated
  Army 25.7 %, Token Triumph 25.6 %, Lorehold Spirit 20.4 %, The Hosts of Mordor 19.5 % (fair: 25 %).

Reading: the two decks that are attacked least (Lorehold Spirit and Hosts of Mordor) are the two that won most in the
Chulane pods. A survivor is attacked less by construction (the dead stop being attacked), and a strong board makes
attacks unsafe, so a low share can be the cause or the consequence of winning. This data cannot tell which.

## 5. Not claimed, next

Not claimed: why Hosts of Mordor and Eldrazi Unbound win above and Token Triumph below their real rates; that the
pilot's targeting causes any of it; a win rate; a card verdict. Real-player data has no per-seat or per-deck
attack counts, so the targeting numbers have nothing to be set against.

Candidates for a next measurement, each cheap: the Token Triumph signature in games it loses early (tokens made,
blocks, which seat is attacked first); the same round-robin with attack targets recorded for all five decks; a
paired run of the round-robin with `focus_defender` switched to plain lowest life or plain threat, to see whether
the winner spread moves.
