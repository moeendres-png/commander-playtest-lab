# Who is attacked in the round-robin of five real precons (2026-11-10)

Refs #1070. Measurement only: no pilot, bridge, fork, pin, deck or sealed record changes, so nothing here needs
requalification or a new reference. Evidence class `LOCAL_OBSERVED`, exploratory, no CI credit, counts that treat
games as independent, not win-rate estimates: **the win rate stays UNDECIDED**.
Follows from section 4 of `WIN_CONCENTRATION_2026-11-09.md` (attack targets recorded for the Chulane pods only) and
section 6 of `TOKEN_TRIUMPH_WIPES_2026-11-10.md` (wipes are not the lever for Token Triumph).

## 1. Answer in short

1. **Nobody attacks Token Triumph early.** In the first four rounds it receives about one attack declaration per game
   (0.7 to 1.1 by how it ended), as much as every other deck (0.7 to 0.9). Of the 595 declarations at it, 14 come on the
   attacker's own turns 1-3, 166 on turns 4-6, 415 on turn 7 or later.
2. **From round 5 it is the most attacked deck, together with Lorehold Spirit.** Declarations (with at least two living
   opponents of the attacker) received per game: Token
   Triumph 12.4, Lorehold Spirit 11.0, Animated Army 9.8, The Hosts of Mordor 8.5, Eldrazi Unbound 8.0. Against chance
   (each living opponent equally likely): 1.35, 1.36, 0.88, 0.87 and 0.69 times. Wins in these games: 5, 12, 9, 17, 17
   of 48.
3. **Token Triumph is picked because its board is the widest.** It has the most non-land permanents among the
   attacker's living opponents in 68 % of the cases (Lorehold Spirit 65 %, the other three 30 to 31 %) and the lowest
   life in 45 % (Lorehold Spirit 59 %). Such a candidate is picked 57 % of the time (Token Triumph and Lorehold Spirit
   alike), and a candidate with neither the most permanents, the lowest life nor the most power 13 to 24 %. The
   attacks at Token Triumph do not separate it from Lorehold Spirit, which is attacked almost as often (11.0 against
   12.4 per game) and wins 12 of 48.
4. **The games Token Triumph loses first show a pile-up from round 5.** When it went out first it received 11.5
   declarations per game in rounds 5-8 (in between 5.8, won 3.2; the other decks 3.9 to 6.2), and its life at the start
   of its own turn 6 was already 29.5 (in between 36.3, won 36.4; own turn 4: 38.5, 39.5, 40.8). Whether the attacks
   cause the exit or the weak position draws the attacks, these counts do not separate.

## 2. Method

The 60 games of the round-robin (`WIN_CONCENTRATION_2026-11-09.md` section 2) were played again with decision
records on `main` `62f4d80d8`, same jar (sha256 `36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`),
pin `f4d12f6e80`; the semantic hash of every game equals that of the wipe replay of `TOKEN_TRIUMPH_WIPES_2026-11-10.md`
(52 of 60 equal the original run on `cdda035af`, the others are the games the bounce-land change moves). 3073 attacker
declarations (one creature at one living defender); 2389 of them with at least two living opponents and used for
points 2 and 3 of section 1. The opponents' board is the public board at the start of the attacker's own turn (it does not
change before the declaration except by instants). Own-turn numbers count the seat's own turns, so they equal the
round for a seat that is alive. Data: `measurements-2026-11-10/attacks_roundrobin5_seeds1-12_62f4d80d8.json`; scripts
in the shared research folder.

## 3. Board development at the start of the own turn (mean over the 48 games of each deck, alive seats)

| Deck | Turn 4: creatures / power | Turn 6: life / creatures / power | Turn 8: life / creatures / tokens / power |
|---|---|---|---|
| Token Triumph | 1.2 / 2.3 | 33.5 / 2.3 / 3.7 | 28.1 / 4.2 / 2.8 / 8.9 |
| Lorehold Spirit | 0.6 / 0.9 | 32.2 / 1.7 / 4.2 | 24.3 / 4.6 / 2.1 / 13.8 |
| Animated Army | 0.9 / 1.9 | 35.5 / 1.3 / 3.6 | 32.2 / 2.1 / 0.8 / 6.5 |
| Eldrazi Unbound | 0.5 / 0.9 | 38.2 / 1.3 / 4.5 | 34.0 / 2.1 / 0.9 / 6.7 |
| The Hosts of Mordor | 0.4 / 0.7 | 34.1 / 1.0 / 2.5 | 27.2 / 2.5 / 0.9 / 11.3 |

Token Triumph has the widest board early and by turn 8 nearly as many creatures as Lorehold Spirit (4.2 against 4.6),
but about a fifth less power than The Hosts of Mordor (8.9 against 11.3) and a third less than Lorehold Spirit (13.8):
its board is made of small tokens (2.8 of 4.2 creatures). In the original run Lorehold Spirit blocked 11.4 times per
game against Token Triumph's 4.9 (`WIN_CONCENTRATION_2026-11-09.md` section 3).

## 4. Not claimed, next

Not claimed: that the pilot's targeting causes any win distribution (the two least attacked decks are the two with the
most wins, 17 each, but Animated Army at 0.88 times has 9 and Lorehold Spirit at 1.36 times has 12); that Token
Triumph should be attacked less; a win rate. Targets were not compared with a rule that does not use the board.

Next, cheap: a paired run of the same 60 games with `focus_defender` replaced in the measuring script (not in the
pilot) by plain lowest life and by plain threat, to see whether the spread of wins moves.
