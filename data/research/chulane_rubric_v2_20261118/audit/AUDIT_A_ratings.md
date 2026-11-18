# Audit A: Karten-Rating Chulane (Raster v2, 922 Karten)

Grundlage: nur `GUIDE_v2.md`, `fullrun_ratings.jsonl` (n=922), `facts.jsonl`, `fulldrift_ratings.jsonl` (n=49).
Keine Nutzungs- oder Beliebtheitsdaten; beurteilt wurde die Funktion der Karte im Deck.

## 0. Kurzurteil
- Das Rating ist am unteren Ende sehr verlässlich, in der Mitte brauchbar, an der Spitze zu großzügig.
- Geprüft: 230 Karten. Zweifelhaft: 29 (12,6 %), davon 25 „H zu hoch", 2 „H zu niedrig", 2 Begründungsfehler.
- Zusätzlich 6 auffällige Karten außerhalb der Stichproben (aus der Klassenprüfung), 5 davon zu niedrig.
- Die Rangfolge der großen Klassen stimmt: Manakreaturen > Rocks, ETB-Kreaturen > Körper, Lebensgewinn unten.
- Ein Einzelwert trägt etwa ±7 bis 8 Punkte (1σ). Unterschiede unter 10 Punkten sind nicht belastbar.

## 1. Stichproben und Ergebnis
| Stichprobe | Definition | n | zweifelhaft | zu hoch / zu niedrig / Begründung |
|---|---|---|---|---|
| Top | H ≥ 60 (93) plus die ersten 7 mit H 55 nach Name | 100 | 20 | 18 / 1 / 1 |
| Boden | alle H 0 (20) plus die ersten 40 mit H 5 nach Name | 60 | 0 | 0 / 0 / 0 |
| Grenzbereich | H 40–55, nicht in Top; nach Name, zwei Reihen „jede 6." (Versatz 0 und 3) | 70 | 9 | 7 / 1 / 1 |
| Summe | | 230 | 29 | 25 / 2 / 2 |

Zur Grenzstichprobe: 209 Karten liegen in H 40–55 außerhalb der Top 100; jede 6. ergibt nur 35, deshalb
eine zweite Reihe mit Versatz 3 (zusammen 70 statt 60). Zweifelhaft heißt: Rater-H liegt mindestens
10 Punkte außerhalb meiner Spanne, oder die Begründung enthält einen Regel- bzw. Kartentextfehler.
Vorschlag und Beleg je Karte stehen in `OUT_audit_A_flagged.jsonl` (35 Zeilen, Zusatzfeld `sample`).

### 1.1 Top 100 (Rater-H → Vorschlag)
- Einmal-Effekte als Motor bewertet: Personify 65 → 30–45 (Blink, Kreatur wird nicht gewirkt, kein
  Chulane-Trigger); Into the Roil 65 → 40–50 (textgleiche Whoosh! steht bei 45); Call to Heel 60 → 40–50.
- Ein Token je Zug als Kernmotor bewertet: Detective of the Month 75 → 50–60; Mischievous Mystic 70 →
  45–55; Alandra 65 → 45–55 (UU); Nadir Kraken 70 → 50–60 (jedes Token kostet {1}, UU).
- Körper und Finisher ohne Chulane-Funktion: Lyra Dawnbringer 60 → 35–45 (WW, kein ETB, K10);
  Elspeth, Knight-Errant 60 → 35–45 (Planeswalker, löst nichts aus); Imperious Perfect 60 → 35–50;
  Arcanis 60 → 40–50 (6 Mana, UUU); Wolfbriar Elemental 60 → 40–50; Merfolk Looter 60 → 40–50;
  Whirler Rogue 70 → 45–55 (UU, Wiederholung kostet 7 Mana).
- Höher als der Funktionszwilling: Changeling Wayfinder 70 → 50–60 (Borderland Ranger 55);
  Foraging Wickermaw 60 → 40–50 (filtert nur; Three Tree Mascot 35); Eclipsed Kithkin 70 → 45–60
  (unsicherer Treffer; Zweitbewertung 40).
- Langsam: Primeval Bounty 70 → 45–60 (6 Mana, tut beim Ausspielen nichts).
- Zu niedrig: Command Tower 80 → 90–100 (Fixanker 100).
- Begründung falsch: Sylvan Ranger 65 (H plausibel), siehe 1.4.
- Übrige 80 plausibel. Leichte Fälle (5 Punkte, nicht gelistet): Koma 85, Vizier of the Menagerie 85,
  Great Forest Druid 80, Jolrael 70, Satyr Wayfinder 70, Serene Sleuth 70, Ethereal Investigator 70
  (alle eher 5 tiefer); Sol Ring 90 (Fixanker 100).

### 1.2 Boden 60: kein Befund
Alle 60 plausibel: Auren, Kampftricks, reiner Lebensgewinn, Artefakte ohne Deckbezug, symmetrische
Sweeper, Rule of Law, off-colour-Länder. Kein Kartentextfehler. Randfall: Skycoach Waypoint (H5) gilt
als „dead text", obwohl der Pool 7 Prepare-Kreaturen enthält; 5–15 bleibt vertretbar.

### 1.3 Grenzbereich 40–55 (Rater-H → Vorschlag)
- Zu niedrig: Reclamation Sage 45 → 55–65 (nützliches ETB, über {3},{T} wiederholbar; steht unter Körpern).
- Zu hoch, reine Körper ohne ETB: Protean Hydra 50 → 30–40; Shore Lurker 50 → 30–40;
  Storm Spirit 45 → 25–35; Wildvine Pummeler 40 → 20–30.
- Zu hoch, Text greift im Deck nicht: Treasure Mage 40 → 15–25 (keine Ziele; Rater: confidence low);
  Shimmer Dragon 40 → 20–30 und Kappa Cannoneer 40 → 20–30 (brauchen Artefakte).
- Begründung ungenau: Fabled Passage 50 (H plausibel), siehe 1.4.
- Leichte Fälle (5 Punkte): Selvala 50, Krosan Verge 40, Skyshroud Claim 40 (eher höher);
  Goldmeadow Harrier 50, Surrak 45, Merchant of Truth 45, Essence Scatter 40 (eher tiefer).

### 1.4 Regel- und Kartentextfehler
- Sylvan Ranger: „the land it fetches can be put onto the battlefield by that same trigger". Falsch:
  Chulanes Trigger entsteht beim Wirken und ist verrechnet, bevor das ETB das Land holt. Dieselbe
  Unschärfe bei Eclipsed Kithkin. Richtig formuliert bei Pilgrim's Eye und Satyr Wayfinder.
- Fabled Passage: „acts as a free ramp". Die Karte ersetzt sich nur selbst, es entsteht kein Zusatzland.
- Automatische Gegenprüfung über alle 922 (Stärke/Widerstandskraft und Manawert in der Begründung gegen
  `facts.jsonl`): 15 Treffer, 0 echte Fehler. `rule_claims`: 11 von 1708 Zitaten (0,6 %) nicht wörtlich.
- Die Kernregeln sind durchgehend richtig: Token, Blink und Reanimation lösen nicht aus, Nichtkreaturen
  lösen nicht aus, Abenteuer- und Prepare-Hälften werden korrekt getrennt.

## 2. Systematische Verzerrungen
1. **Körper und Finisher ohne Chulane-Funktion zu hoch (wichtigste Verzerrung).** H folgt fast nur E, F
   und R; D (Wrath-Anfälligkeit, Farbbelastung) wirkt praktisch nicht (siehe 3). 14 der 25 „zu hoch"-Fälle
   gehören hierher (7 in Top, 7 im Grenzbereich), z. B. Lyra 60, Elspeth 60, Arcanis 60, Protean Hydra 50,
   Storm Spirit 45. Kreaturen bis Manawert 2 ohne ETB oder aktivierte Fähigkeit: n=36, Median 20, 10 davon
   ≥ 30 (Loam Lion 40, Wild Nacatl 35), obwohl der Anker Storm Crow bei 0 liegt. Ab Manawert 3: n=82,
   Median 15 (passt).
2. **Einmal-Bounce und Einmal-Blink zu hoch.** n=10 Spontanzauber, Median 50, Maximum 65, F 65–80.
   Der Rater bewertet sie wie wiederholbare Bounce-Kreaturen; sie lösen Chulane nicht aus und kosten eine
   Karte. Vorschlag Median 35–40. Interne Sprünge: Into the Roil 65 gegen Whoosh! 45 (identischer Text),
   Personify 65 gegen Narrow Escape 30 und Unsummon 35.
3. **„Zweite gezogene Karte"-Zahler zu hoch.** n=6 Kreaturen, H 65–75, Median 70 (Detective of the Month
   75, Jolrael 70, Mischievous Mystic 70, Morska 70, Ethereal Investigator 70, Alandra 65), dazu Nadir
   Kraken 70. Ertrag: ein kleines Token je Zug, nur mit Chulane im Spiel. K 70–80 stellt das den
   Landfall-Motoren gleich, die mehrfach je Zug zahlen. Vorschlag 50–65.
4. **Reaktive Interaktion gestaucht und unter dem Anker.** Konter: n=23, Median 35, Maximum 50.
   Counterspell 45 bei Fixanker 67 (−22); Refute (3 Mana) 50 steht darüber, Mana Leak gleichauf.
   Artefakt-/Verzauberungs-Antworten: Nature's Claim 25 < Naturalize 30 < Disenchant 35; die billigste
   steht am tiefsten, gegnerischer Lebensgewinn zählt als Nachteil. Sonst kein Lebensgewinn-Hass:
   Rolle Lebensgewinn n=38, Median 10; reiner Lebensgewinn bei 0–10 ist richtig.
5. **Spitze gestaucht.** Anker ≥ 65: n=11, mittlere Abweichung −5,2 (Command Tower −20, Counterspell −22,
   Sol Ring −10, Kor Skyfisher +15). Anker < 65: n=13, Mittel +0,3. Kein Wert ≥ 95 (0 von 922).
6. **Kein Befund oder nur Streuung.** Nutzländer: farblose Länder mit Nebeneffekt n=12, H 5–15,
   anker-konform; auffällig nur Myriad Landscape 25 gegen Krosan Verge 40. Sweeper: n=5 (0, 0, 10, 25, 25),
   anker-konform. Ramp-Artefakte n=20, Median 42,5, gegen Manakreaturen n=20, Median 60: Richtung stimmt,
   2-Mana-Rocks wackeln um 10. Kartenvorteil ohne Chulane-Bezug: n=74 Nichtkreaturen, Median 30,
   plausibel. Kreaturen mit Land-ETB: n=15, Median 65, plausibel; Funktionszwillinge streuen um 15.

## 3. Konsistenz zwischen Kriterien und H, Verteilung
- Lineare Anpassung über alle 922:
  H ≈ −20,6 + 0,34·E + 0,31·F + 0,31·R + 0,19·K + 0,11·T + 0,02·D; R² = 0,905; Rest-Streuung 5,8.
  H ist faktisch eine Formel aus E, F, R. D hat kein Gewicht (Korrelation mit H 0,24), T wenig (0,33).
  Das erklärt Verzerrung 1: WW/UU/UUU und Sweeper-Risiko senken H kaum.
- H minus Mittel der sechs Teilwerte: Mittel −10,2, Streuung 9,1; H liegt bei 796 von 922 unter dem
  Mittel, weil D (Mittel 64,8) das Mittel hebt. Mehr als 25 Abstand: 8 Karten, alle nach unten, alle 8
  in `reason` begründet; die Leitfaden-Regel ist eingehalten. Kein H liegt mehr als 25 über dem Mittel
  (Maximum +24, Command Tower). Das Problem ist die Gewichtung, nicht ein einzelner Sprung.
- Verteilung H nach Leitfaden-Bändern:

| Band | 0–4 | 5–27 | 28–49 | 50–71 | 72–94 | 95–100 |
|---|---|---|---|---|---|---|
| n | 20 | 422 | 312 | 144 | 24 | 0 |
| Anteil | 2,2 % | 45,8 % | 33,8 % | 15,6 % | 2,6 % | 0 % |

- Median 30 und Mittel 30,7 sind für diesen Pool sinnvoll: er enthält viel Limited-Füllmaterial
  (105 Karten ohne Rolle, Median 15). Die untere Hälfte ist gut aufgelöst.
- Ungenutzt ist das obere Viertel: Maximum 90, nur 24 Karten ≥ 75. H nutzt 19 Stufen und liegt nur zu
  17 % auf den Ankerstufen 0/25/50/75/100; das ist gut.
- K und T klumpen entgegen Regel 7: K ist 252-mal 0 und 162-mal 25 (53 % auf Ankerstufen), T ist
  247-mal 25 und 101-mal 0 (44 %).
- Entscheidungsrelevant: 80 Karten liegen in H 55–65, 126 bei ≥ 55. Dort fällt die Deckauswahl, und
  dort ist die Auflösung kleiner als das Rauschen.

## 4. Unsicherheit eines Einzelratings
| Quelle | n | mittl. Betrag ΔH | RMS | Maximum |
|---|---|---|---|---|
| Drift, Zweitbewertung gleicher Leitfaden | 49 Paare | 5,1 | 7,1 | 30 |
| Textgleiche Karten im Hauptlauf | 10 Paare | 7,0 | 8,7 | 20 |
| Abweichung von den H-Ankern | 24 | 5,0 | 8,0 | 22 |

- Drift im Detail: 42 von 49 (86 %) innerhalb ±5, 46 (94 %) innerhalb ±10, 3 (6 %) bei ≥ 15;
  Korrelation 0,93; mittlere Verschiebung −1,2; Bandwechsel bei 4 von 49 (8 %). Ohne den Ausreißer
  Eclipsed Kithkin (70 gegen 40) RMS 5,8.
- Wiederholstreuung eines Einzelwerts daraus: etwa 5 Punkte (RMS/√2), bei textgleichen Karten etwa 6.
- Die Streuung wächst mit H und mit sinkender Sicherheit: H ≤ 25 mittl. Betrag 4,2 (n=24), H 30–45 5,0
  (n=14), H ≥ 50 7,3 (n=11); `confidence` high RMS 5,0 (n=21), medium 8,4 (n=28).
- Teilwerte: F am stabilsten (RMS 5,1; r 0,96), D am schwächsten (RMS 9,6; r 0,87; Maximum 45).
- Die Drift misst nur Wiederholbarkeit mit demselben Leitfaden, nicht Richtigkeit. Meine Prüfung zeigt
  zusätzlich Fehler von 10 bis 20 Punkten bei 27 von 230 Karten (11,7 %): Top 19 von 100,
  Grenzbereich 8 von 70, Boden 0 von 60.
- Gesamtschätzung für einen Einzelwert: 1σ etwa 7–8 Punkte, 90-%-Bereich etwa ±12.
  H ≤ 10: etwa ±5. H 40–55: etwa ±10, effektlose Körper eher 10–20 zu hoch.
  H ≥ 60: asymmetrisch, etwa −15 bis +5; die 18 „zu hoch"-Fälle der Top 100 liegen im Mittel
  12 Punkte über meiner Obergrenze (die Auswahl der höchsten Werte sammelt positive Ausreißer).

## 5. Empfehlungen
1. H nicht als Rangfolge innerhalb von 10 Punkten lesen; für die Deckauswahl den Bereich 50–70 zweitbewerten.
2. D wirksam machen: WW/UU/UUU und Sweeper-Risiko müssen H senken; reine Körper (K ≤ 25, F ≤ 55) bei etwa 45 kappen.
3. Zwei Anker ergänzen: ein Einmal-Bounce-Spontanzauber (Disperse, H etwa 40) und ein „zweite
   Karte"-Zahler (Jolrael, H etwa 60). Counterspell und Command Tower als Fixanker im Lauf erzwingen.
4. Funktionszwillinge als Prüfnetz nutzen: textgleiche Karten müssen gleiches H bekommen (derzeit bis 20 Abstand).
