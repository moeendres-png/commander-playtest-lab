# Does the rule for who is attacked move the wins? Round-robin of five real precons (2026-11-10)

Refs #1070. Measurement only: no pilot, bridge, fork, pin, deck or sealed record changes (the target rule is replaced
inside the measuring script, the repository code is untouched), so nothing here needs requalification or a new
reference. Evidence class `LOCAL_OBSERVED`, exploratory, no CI credit, counts that treat games as independent, not
win-rate estimates: **the win rate stays UNDECIDED**.
Follows from `ATTACK_TARGETS_ROUNDROBIN_2026-11-10.md` (Token Triumph and Lorehold Spirit are attacked about 1.35 times
chance; the decks attacked least win most) and section 5 of `WIN_CONCENTRATION_2026-11-09.md`.

## 1. Answer in short

1. **The win counts do not move detectably.** The same 60 games with two other rules for the opponent to concentrate on
   give wins of 48 games per deck (Lorehold Spirit, Animated Army, Token Triumph, Eldrazi Unbound, Hosts of Mordor):
   unchanged pilot 12, 9, 5, 17, 17; plain lowest life 16, 7, 9, 14, 14; plain threat 11, 12, 7, 15, 15. No deck differs
   from the unchanged pilot by more than 4 (one count is +-3, a difference of two arms +-4.2), and the spread of wins over the
   decks is not different (chi-square 2.5 and 1.1, 4 degrees of freedom, p about 0.64 and 0.90).
2. **Who goes out first does move with plain lowest life.** First exits of the 60 games, unchanged pilot: Lorehold Spirit
   20, Animated Army 8, Token Triumph 20, Eldrazi Unbound 6, Hosts of Mordor 6. Plain lowest life: 7, 14, 12, 13, 14
   (chi-square 15.7, p about 0.003). Plain threat: 22, 7, 19, 7, 5 (no difference, p about 0.99). So the pile-up of early exits on the
   two decks with the widest boards comes from the threat part of the rule, and it is not what decides the wins: the exit
   order spreads out and the win counts stay inside the noise.
3. **Token Triumph stays below its real rate in all three arms** (5, 9, 7 of 48; real 26.5 %, about 13 of 48), Eldrazi Unbound
   and The Hosts of Mordor above theirs (14 to 17 in every arm against real 24.7 % and 19.6 %, about 12 and 9 of 48). The shares are nearer to the real
   precon rates under both other rules (sum of the absolute gaps over the five decks 47.8 points for the unchanged pilot, 34.8 and
   37.9), but sampling noise alone puts a perfectly matching model at about 25 points, and each deck's change is inside the
   noise: not a result.
4. **Neither the target rule nor the wipes moves the wins by an amount these runs can see.** With 48 games per deck
   and arm, a shift of about 8 wins for one deck would show; smaller effects are not excluded
   (`TOKEN_TRIUMPH_WIPES_2026-11-10.md` is the same finding for the wipes). The gaps to the real rates sit in something
   these runs do not vary.

## 2. Method

The 60 games of the round-robin (`WIN_CONCENTRATION_2026-11-09.md` section 2: five pods of four, seeds 1-12, deck order shifted by
`seed % 4`) were played again on `main` `9de18e267` (pilot code as `62f4d80d8`), same jar (sha256
`36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`), pin `f4d12f6e80`, two games at a time. The baseline
arm is the replay of `ATTACK_TARGETS_ROUNDROBIN_2026-11-10.md`. In the two other arms `focus_defender` (full_game_pilot_views.py:
"threat, plus a bonus that grows as a player's life gets low", used by `attack_score` to favour attacks at that player)
is replaced in the measuring script by: **life**, the living opponent with the lowest life (ties to the player id); **threat**,
the living opponent with the highest `player_threat`, without the low-life bonus. Nothing else differs. Games diverge as
soon as one choice differs: with the life rule 1 of 60 games is identical to the baseline (32 of the other 59 have another
winner), with the threat rule 38 of 60 are identical (8 of the other 22 have another winner), so the arms are compared as
counts, not as pairs. Data: `measurements-2026-11-10/targetrule_{life,threat}_roundrobin5_seeds1-12_9de18e267.json`; scripts in the shared research
folder.

## 3. Table

| | Unchanged | Plain lowest life | Plain threat |
|---|---|---|---|
| Wins of 48: Lorehold Spirit / Animated Army / Token Triumph / Eldrazi Unbound / Hosts of Mordor | 12 / 9 / 5 / 17 / 17 | 16 / 7 / 9 / 14 / 14 | 11 / 12 / 7 / 15 / 15 |
| First exits of 60 (same order) | 20 / 8 / 20 / 6 / 6 | 7 / 14 / 12 / 13 / 14 | 22 / 7 / 19 / 7 / 5 |
| Token Triumph first out / in between / won (of 48) | 20 / 23 / 5 | 12 / 27 / 9 | 19 / 22 / 7 |
| Declarations at Token Triumph per game, attacker's own turns 1-4 / 5-8 / 9+ | 0.9 / 7.9 / 6.9 | 0.6 / 4.4 / 10.4 | 0.9 / 7.9 / 6.7 |
| Mean length (rounds) | 10.8 | 10.6 | 11.0 |
| Wipe-role casts per game | 1.53 | 1.37 | 1.57 |

## 4. What stays open, not claimed

Not claimed: that any target rule is nearer to real play (real data has no elimination order or attack counts), that
the pilot's rule should change (any pilot change needs the Owner's go; nothing here argues for one), a win rate, a card verdict.
Open: why Eldrazi Unbound and The Hosts of Mordor win above and Token Triumph below their real rates. Leads in the
pilot decision report (round-robin, per game of the deck): Eldrazi Unbound has 3.0 cancelled mana payments and 1.3 main
phases passed with a castable spell, the most of the five (the others 0.1 to 0.8 and 0.1 to 0.4); Token Triumph has 0.8
needless chump blocks, the most (Lorehold Spirit 0.65, the others 0.06 to 0.23), which for a deck of tokens may be the
report's definition more than a mistake. Neither is a finding; each needs its own look at the windows.
