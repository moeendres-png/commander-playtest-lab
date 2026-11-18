# GUIDE v2.2 Delta (Entwurf) zu den Audit-A-Verzerrungen 1, 2, 3, 5
Einfügen: Block unverändert nach „## Special cases“. Er nennt absichtlich keinen Kartennamen (kein Leck); die Schemata sind Kartenformen mit veränderten Werten.

<!-- DELTA BEGIN -->
## v2.2 additions (they override v2 wherever the two differ)
Score E, F, T, R, K, D first, then run these checks before you fix H. "Schema" lines describe card shapes, not cards.

### A. Function test, body ceiling, D brake
- **A1 Function.** A card has a Chulane function only if you can name an F component other than "it is a creature spell": a useful ETB or cast trigger of its own, mana,
  lands or landfall, repeatable return of own creatures, cheaper or extra creature casts, protection of the board, real card gain. Not functions: power and toughness,
  keywords, combat abilities, tokens not tied to casts, lands or draws, and minor riders (scry or surveil 1, a little life, looting, a counter).
- **A2 Dead text is no text.** An ability that needs artifacts, Auras, a tribe, a graveyard or life gain which this deck does not supply counts as blank. Rate what remains.
- **A3 F without function.** The cast trigger alone is F 25 to 50 (50 only at mana value 2 or less), as for cards without rules text. F above 50 needs a component from A1.
- **A4 Body ceiling.** Creature, planeswalker or token maker without function: H ≤ 25 at mana value 2 or less, H ≤ 35 above that, H ≤ 45 only if it dominates combat at a
  four-player table (T ≥ 50); no ceiling if T ≥ 75. High E does not lift it: stats draw no cards. Peer check: it ends at least 10 below a creature of the same mana value
  that has a useful ETB, a mana ability or a land effect.
- **A5 D brake (spells; lands keep the land table).** A high D is no reason for a high H; a low D is a ceiling: D ≤ 25: H ≤ 35. D 30 to 45: H ≤ 50. D 50 to 60: H ≤ 65. One
  row higher only if K ≥ 75 or T ≥ 75. Inside the ceiling, of two cards equal on E, F, T, R, K the one with D 20 lower gets H at least 5 lower. `notes.H` says what D did
  ("D 45: ceiling 50", "D 80: no effect").

### B. Bounce and blink: who repeats?
- **B1.** Chulane's {3},{T} is open to every creature in the deck. Its credit (K 50 level) belongs to the creature that owns a useful ETB. It is never credit for a card
  that returns or flickers something once, nor for a creature without an ETB or cast trigger: "Chulane can replay it" alone raises neither F nor K.
- **B2 Repeatable** (F up to 100, K 75 to 100): a creature whose own ETB returns a creature you control (recast it: Chulane draws again, it returns something again); a
  permanent that returns or flickers every turn or for a small activation cost; a spell that comes back to the hand by itself.
- **B3 One-shot, single target** (instant, sorcery, or a permanent that does it once and is gone): not a creature spell, costs a card, re-uses one ETB once. K ≤ 30. F ≤ 60
  if the creature goes to the hand (its recast triggers Chulane once), F ≤ 50 if it is flickered (not cast: no Chulane trigger). H 30 to 40; 45 if it can also return any
  opponent's nonland permanent at instant speed; 50 at most if it also draws a card. Never above a creature that has the same effect as an ETB.
- **B4 Same text, same scores.** Rate the rules text, not the name: identical cost and text get identical scores.

### C. Draw-count payoffs ("second card each turn")
- **C1 Count.** Your draw step is card 1 of your own turn. While Chulane is on the battlefield every creature spell you cast draws one more: the first creature spell of
  your turn is card 2, the next is card 3. An opponent's turn has no draw step of yours, so two draws are needed there. Without Chulane on the battlefield the count
  normally stays at 1.
- **C2 Timing (given by this guide; quote it as basis in `rule_claims`).** Chulane's trigger resolves before the creature spell that caused it: the creature being cast does
  not see that draw, and a land found by its ETB comes too late for that trigger's land drop.
- **C3 "Whenever you draw your second card each turn"** pays at most once per turn, in practice once per own turn, and only with the commander out. It is not a per-land or
  per-spell engine: K ≤ 55, F ≤ 75. H follows the one payoff: 1/1 token or counters 45 to 55, bigger token 50 to 60, up to 65 only with a second real function (A1). A
  "third", "fourth" or "fifth card" clause needs that many draws in one turn: a rare bonus, not part of the rate.
- **C4 "Whenever you draw a card" / "each card except the first"** pays per draw, so per creature spell, and may reach K 75. If every payoff costs mana: K ≤ 60 (it competes
  with casting creatures). If the payoff is only size on a body: A4 applies.

### D. The top of the scale
- **D1.** 90 to 100 are real ratings. Rule 7 ("take the lower level") settles one doubt between two adjacent levels; it is not a general discount and never moves a card out
  of a band whose test it passes. F 50 does not block the top.
- **D2.** H ≥ 90 is allowed, and then expected, in exactly three cases; everything else is 89 or lower: (i) a mana source that gives back more mana than it cost from the
  next turn on, with R ≥ 90 and D ≥ 85: 95 to 100; (ii) a land that enters untapped, makes all three colours and has no cost or condition: 95 to 100; (iii) a core engine
  with F 100 and K ≥ 90 at mana value 2 or less, R ≥ 70, D ≥ 70: 90.
- **D3 Anchors are fixed points.** A card that does an H anchor's job at an equal or better rate is not below that anchor; a card that does it worse is not above.

### E. Check schemas
| | schema | check | result |
|---|---|---|---|
| A | 1 mana 2/1 with one combat keyword | A1: cast trigger only | F ≤ 50, K 0, H ≤ 25 |
| A | 5 mana, two pips of one colour, 6/6 vigilance, no ETB | no function, T 50, D ≤ 50 | H ≤ 45 |
| A | 4 mana 3/3 that grows for each Aura attached to it | A2 dead text, the body remains | H ≤ 35 |
| A | 3 mana 2/2, ETB: fetch a basic land | function: no ceiling, ends above the three bodies | H 50 to 60 |
| B | cheap instant: return one creature to its owner's hand | B3, to hand | F ≤ 60, K ≤ 30, H 30 to 40 |
| B | 2 mana instant: exile your creature, return it to the battlefield | B3, not cast | F ≤ 50, K ≤ 30, H 30 to 40 |
| B | 3 mana instant: return a nonland permanent, draw a card | B3, flexible, replaces itself | H 45 to 50 |
| B | 2 mana 2/1, ETB: return another creature you control to hand | B2 | F 90+, K 75+ |
| C | 3 mana 2/2: second card each turn makes a 1/1 token | C3: once per own turn | K ≤ 55, F ≤ 75, H 45 to 55 |
| C | 4 mana, two pips of one colour: second card makes a 2/2, bonus on the fourth | fourth = draw step + 3 casts; A5 | H 50 to 55 |
| C | Chulane out, own turn, three creature spells | cards 2, 3, 4 | "second card" pays once, "each card after the first" 3 times |
| C | opponent's turn, one flash creature | card 1 only | no payoff |
| D | artifact that makes more mana each turn than it cost | D2 (i) | 95 to 100 despite F 50 |
| D | 2 mana artifact that makes one mana | E high, but mana equals cost: not (i) | 89 or lower |
| D | 4 mana engine creature, F 90, K 75 | not (iii) | 75 to 89 |
<!-- DELTA END -->

## (b) Stellen im v2-Guide, die dem Delta widersprechen können (anpassen oder den Vorrangsatz stehen lassen)
1. Regel 7 „take the lower one“ drückt die Spitze; D1 begrenzt sie auf ein Zögern zwischen zwei Nachbarstufen.
2. H „Weigh the criteria yourself; not their average“ und die 25-Punkte-Regel: die Deckel A4/A5/B3/C3 gehen vor; es entstehen mehr Abstände > 25.
3. F „A cheap creature is a cheap trigger“ gegen A3 (F ≤ 50 ohne Funktion); der Vanilla-Absatz (25–50) passt und gilt nun breiter.
4. F „a card that returns an own creature more cheaply (own bounce, blink) is worth more still“ gegen B3; dazu Special cases „A flicker or bounce that makes you cast …“ (Flicker wirkt nie neu).
5. K: „pays again each turn“ = 75 gegen C3 (einmal je Zug, K ≤ 55); K 50 „ETB replayed by Chulane's {3}“ gilt nur mit eigenem ETB (B1).
6. „All seven scores point the same way“ und D 100: hohes D ist kein Bonus (A5). Land-Anker mit D 50 bei H 75–78: deshalb Länder ausgenommen.
7. H-Bänder (72–94, 95–100) gegen D2: 90–94 nur noch über (iii). Anker mit D 50–60 und H ≥ 70 brauchen die A5-Ausnahme (K/T ≥ 75).
8. Regel 3 (Regelaussagen nur aus Kartentext, XMage ist Autorität) gegen C2: `quote` um „v2.2 C2“ erweitern, C2 vorab gegen XMage prüfen. Regel 6 gegen B4/A4-Peer-Check.
9. D2 (i)/(ii) beschreiben faktisch die beiden 100-Fixanker; sauberer: Fixanker per Regel setzen statt bewerten, dann (i)/(ii) streichen.

## (c) Empfehlung Neubewertung (aus fullrun_ratings.jsonl, n=922)
- Empfohlen, 407 Karten (44 %): alle mit H ≥ 40 (309, davon 22 Länder), dazu alle Kreaturen mit H 30–35 (91; dort greift der Deckel 25/35) und 7 Klassenkarten darunter:
  Nichtkreaturen, die Kreaturen/Permanents zurückholen oder flickern (Klasse 16), und Karten mit „second card“- oder „whenever you draw a card“-Text (Klasse 13).
- Sparvariante, 180 Karten: H ≥ 50 (168) plus beide Klassen; sie lässt die Körper bei H 30–45 unkorrigiert.
- Unter den Schwellen binden die neuen Deckel nicht; die übrigen 515 Werte bleiben auf derselben Skala vergleichbar.
- A5 allein bindet im jetzigen Lauf nur bei 5 Karten (Karten mit niedrigem D stehen meist schon tief); die Wirkung kommt aus A1–A4 und der Paarregel in A5.
- Die Pilotliste lag mir nicht vor, daher keine Namen. Audit-Punkt 4 (Konter gestaucht) ist nicht Teil des Deltas.
