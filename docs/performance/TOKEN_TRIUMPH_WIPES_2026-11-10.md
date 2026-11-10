# Board wipes in the round-robin of five real precons, and Token Triumph (2026-11-10)

Refs #1070. Measurement only: no pilot, bridge, fork, pin, deck or sealed record changes, so nothing here needs
requalification or a new reference. Evidence class `LOCAL_OBSERVED`, exploratory, no CI credit, counts that treat
games as independent, not win-rate estimates: **the win rate stays UNDECIDED**.
Follows from section 3 of `WIN_CONCENTRATION_2026-11-09.md` (Token Triumph 5 wins in 48 games against 26.5 % real,
and a lead that opposing board wipes might explain it).

## 1. Answer in short

1. **Wipes do not explain Token Triumph's low count as measured.** The earlier lead (1.6 opposing wipes per game
   when Token Triumph went out first, 1.0 otherwise) reproduces on the original data (1.60 / 1.04 / 0.80 for first
   out / in between / won), but it counted the whole game, including the rounds after Token Triumph was gone, and
   three cards that do nothing when cast (Steel Hellkite, Perilous Vault, Merciless Executioner). Counted per
   sweeper spell cast while Token Triumph was still alive it is 0.65 / 0.52 / 0.40 per game, with at least one such
   wipe in 11 of 20, 10 of 23 and 2 of 5 games.
2. **When a sweeper does come, Token Triumph loses the most.** 19 of the 25 times a sweeper spell met a Token Triumph
   board with a creature on it, every creature died (median 3 of 3; mean 3.5 of 3.8 without one 35-creature board,
   93 %). The other decks lose 53 % (Lorehold Spirit) to 81 % (Eldrazi Unbound). Token Triumph's creature power goes
   from 13.5 to 0.2 on average, the others' to 1.5 to 6.2. It was the opponent with the most creatures in 20 of 27
   sweepers cast by another deck (9.3 expected if the caster picked among its opponents by chance), so the
   sweepers are cast at it.
3. **But the hits are not frequent, and the games after them are not worse.** A sweeper took at least 3 Token
   Triumph creatures at once in 15 of its 48 games. It went out first in 7 of those 15 (47 %) and in 13 of the other
   33 (39 %), won 1 and 4: no difference these counts can show. Elimination came 3 to 42 game turns after the hit
   (median 18, four turns are one round), so a hit is not a direct cause.
4. **The wipes themselves are cast sensibly.** In 65 sweeper spells the caster was never ahead in creature power
   (0), and at or below its weakest opponent in 36. A sweeper killed 6.3 opposing creatures for 1.0 of the caster's
   own; 2 of 65 killed no opponent creature. Median cast: the caster's own turn 7 (quartiles 5 and 9). Nothing to
   build in the pilot from this.

## 2. Method

The 60 games of the round-robin (`WIN_CONCENTRATION_2026-11-09.md` section 2: five pods of four real precons,
seeds 1-12, deck order shifted by `seed % 4`) were played again with decision records, on `main` `62f4d80d8` (the
pilot with the bounce-land order of #1152), same jar (sha256 `36167ba71e480c6c85f95df3bd24feac5a75c94d0752e71f25544a861c9064a7`),
pin `f4d12f6e80`, two games at a time. 52 of the 60 games have the semantic hash of the original run on `cdda035af`;
the other 8 (pod, seed: 0-4, 0-7, 1-2, 2-2, 2-3, 4-1, 4-3, 4-4) are the games the bounce-land change moves, and the
winner differs in 3 of them. Wins in the replay: Eldrazi Unbound 17 of 48, The Hosts of Mordor 17, Lorehold Spirit
12, Animated Army 9, Token Triumph 5 (before: 16, 16, 14, 9, 5). Counts, not estimates.

For every spell a seat chose to cast whose card has the `WIPE` role (and that was not a cancelled cast) the public
board of the four players was taken at the cast and at the first later decision with an empty stack (the spell has
resolved or was countered; always on the same turn). Wipes per seat equal the pilot decision report's `wipes_cast`
in all 52 games with an unchanged hash. A creature is a token when its name is not a card of the five decks.
Data: `measurements-2026-11-10/wipes_roundrobin5_seeds1-12_62f4d80d8.json`; scripts in the shared research folder.

## 3. What the 92 casts were

| Cast | Casts | Cards (casts) |
|---|---|---|
| Sweeper spell, effect on resolution | 65 | Blasphemous Act 16, Citywide Bust 15, Hour of Reckoning 7, Tragic Arrogance 7, Calamity of the Titans 5, Ceaseless Conflict 5, All Is Dust 4, Starstorm 4, Languish 2 |
| Role `WIPE`, nothing happens on cast | 27 | Steel Hellkite 13 (a creature, its ability needs combat damage), Perilous Vault 7 (an artifact, exiles when activated), Merciless Executioner 7 (each player sacrifices one creature) |

Sweeper spells by caster, per game of the deck (48 games each): Token Triumph 22 (0.46; Citywide Bust and Hour of
Reckoning, which spare the small and the token creatures; it lost 0.4 of its own creatures per cast and killed 3.4 of
the others'), The Hosts of Mordor 12, Lorehold Spirit 12, Animated Army 10, Eldrazi Unbound 9 (0.19 to 0.25).

## 4. Who loses what to a sweeper spell (cast by another seat, victim alive with a creature)

| Deck | Cases | Creatures before | Lost | Share | Tokens before | Lost | Power before to after |
|---|---|---|---|---|---|---|---|
| Token Triumph | 25 | 5.0 (median 3) | 4.8 (median 3) | 95 % | 2.8 | 2.6 | 13.5 to 0.2 |
| Lorehold Spirit | 26 | 5.0 (median 4) | 2.7 (median 1) | 53 % | 2.1 | 0.8 | 14.2 to 6.2 |
| Eldrazi Unbound | 35 | 2.8 | 2.3 | 81 % | 0.8 | 0.7 | 12.3 to 1.5 |
| The Hosts of Mordor | 35 | 2.6 | 1.9 | 72 % | 0.9 | 0.6 | 10.5 to 2.9 |
| Animated Army | 33 | 3.3 | 2.2 | 67 % | 1.2 | 0.7 | 10.9 to 2.2 |

Token Triumph's mean is lifted by one board of 35 creatures (26 tokens, power 150) that Ceaseless Conflict cleared
on game turn 35 (pod 4, seed 3); without it 3.8 before, 3.5 lost, 93 %.

## 5. Token Triumph by how it ended (48 games, sweeper spells only)

| Ended | Games | Sweepers by others while it was alive, per game | Games with at least one | Whole game, all `WIPE` casts by others (the old count) |
|---|---|---|---|---|
| First out | 20 | 0.65 | 11 | 1.60 |
| In between | 23 | 0.52 | 10 | 0.96 (original run 1.04) |
| Won | 5 | 0.40 | 2 | 1.00 (original run 0.80) |

Games with a sweeper hit of at least 3 Token Triumph creatures: 15 (first out 7, in between 7, won 1); the other 33:
first out 13, in between 16, won 4. Cards in the 15 hits: Blasphemous Act 7, Calamity of the Titans 2, Tragic
Arrogance 2, Starstorm, Languish, Ceaseless Conflict, All Is Dust 1 each; creatures lost 3 to 9, once 35. In 13 of the 20
games in which it went out first, no sweeper had taken 3 of its creatures.

## 6. Not claimed, next

Not claimed: why Token Triumph stays at 5 of 48 (the wipes are not the lever these counts show); that a wipe
never matters (2 of 5 wins and 11 of 20 first-outs had one); that the pilot's wipe timing is right in every game
(only whether the caster was behind and what the cast killed); a win rate; a card verdict. The `WIPE` role is the
catalog's, three cards of it do not sweep when cast.

Next, each cheap: the same round-robin with attack targets recorded for all five decks (who attacks Token Triumph in
the first rounds, at what life), which is the part of its early exits these counts leave open; a paired run with
`focus_defender` switched to plain lowest life or plain threat.
