# Audit D: Regelprüfung von 100 rule_claims (Rater F1, Commander Chulane)

Quellen: nur `fullrun_ratings.jsonl` (922 Bewertungen, 1708 rule_claims, alle Rater F1) und
`facts.jsonl` (Oracle-Text, Typzeile, Manawert, Rulings). Kein Web. Maßstab: Kartentext,
gezeigte Rulings, Comprehensive Rules.

## Ergebnis

| Urteil  | Anzahl | Anteil |
|---------|--------|--------|
| richtig | 100    | 100 %  |
| falsch  | 0      | 0 %    |
| offen   | 0      | 0 %    |

Wilson-95-%-Intervall für den Anteil richtig: **96,3 % bis 100 %** (k = 100, n = 100).
Nur die 78 gehaltvollen Claims (ohne 22 reine Typzeilen-Claims): 78/78, Wilson 95,3 % bis 100 %.

Die Stichprobe enthält keinen falschen und keinen offenen Claim. Die Obergrenze der
Fehlerquote liegt damit bei etwa 3,7 % (alle Claims) bzw. 4,7 % (gehaltvolle Claims).

## Stichprobe

- `random.Random(2026)`; je Stratum gemischt, dann Claims mit Interaktionsbezug
  (Chulane, Trigger, Bounce, Landfall, Token, Blink, Stapel, Flash, Enttappen) vorgezogen.
- Höchstens 2 Claims je Karte erlaubt; gezogen wurde jeweils höchstens 1 (100 Karten).
- Strata per Stichwortregel auf `interaction` + `claim`, erste passende Regel gewinnt.

| Stratum                                   | n  | richtig | davon trivial |
|-------------------------------------------|----|---------|---------------|
| ETB-Wiederverwendung per Bounce           | 18 | 18      | 0             |
| Landfall / zusätzlicher Landdrop          | 16 | 16      | 5             |
| Kreaturenzauber vs. Token/Blink/Nichtkr.  | 18 | 18      | 10            |
| Flash / Kosten / Timing                   | 14 | 14      | 0             |
| Symmetrie / Sweeper                       | 12 | 12      | 0             |
| Farbbelastung / Produktion                | 10 | 10      | 0             |
| Sonstiges                                 | 12 | 12      | 7             |

Einschränkung: Die Stichwortregel hat 22 Claims der Art „ist (k)ein Kreaturenzauber, löst
Chulane (nicht) aus“ durchgelassen. Sie sind korrekt, aber prüfen kaum Regelwissen. Das
Stratum „Landfall“ enthält deshalb 5 Claims, die nur den optionalen Landeffekt von
Chulanes Trigger nennen.

## Falsche und offene Fälle in der Stichprobe: keine

## Richtig, aber unscharf formuliert (5 Fälle, Urteil bleibt richtig)

| Karte | Claim (Kern) | Präzisierung |
|-------|--------------|--------------|
| Hada Freeblade | Wirken löst „optional land drop“ aus | Chulanes Effekt ist kein Landspiel (CR 305.4); inhaltlich korrekt, an anderer Stelle (Augur of Autumn, Explore) trennt der Rater das sauber. |
| Molder Beast | „draw and land drop“ | Das Land ist optional („may“) und braucht eine Landkarte auf der Hand. |
| Tam, Observant Sequencer | jedes Land macht Tam „prepared“ | Ist Tam schon vorbereitet, entsteht keine zweite Kopie (Ruling). |
| Mindseeker Oculus | 4 Marken = ein Ziehen plus ein Surveil | Nur eine Loyalitätsfähigkeit je Zug (CR 606.3); der Wert verteilt sich auf zwei Züge. |
| Strixhaven Skycoach | Bounce nur nach Crew 2 | Stimmt für die Karte allein; Chulane selbst kann nicht bemannen und danach noch {T} zahlen. |

## Zusatzprobe außerhalb der Stichprobe (nicht zufällig, nicht im Intervall)

Weil die Stichprobe fehlerfrei ist, habe ich rund 280 weitere Claims gezielt nach
riskanten Mechaniken gefiltert und gesichtet (Evoke, Cascade, Kopien, Prepare, Phasing,
Ersatzeffekte, Convoke/Affinity, Stun-/Loyalitätsmarken, Fluchsicherheit/Shroud,
Kommandozone, Token-Bounce, Zeitpunkt im gegnerischen Zug). Diese Sichtung ist weniger
streng als die Stichprobe (Abgleich mit Oracle-Text nur bei Auffälligkeit).

| Karte | Claim | Urteil | Korrektur |
|-------|-------|--------|-----------|
| Wavesifter (#0) | Evoziert: Trigger ermittelt zweimal, „before the sacrifice leaves no creature to bounce“ | falsch | Das Opfern bei Evoke ist eine ausgelöste Fähigkeit (CR 702.74a). Mit ihr auf dem Stapel kann Chulane für {3},{T} Wavesifter auf die Hand zurückholen. Die `reason` wiederholt den Fehler („cannot be bounced“). |
| Appeal to Eirdu (#0) | Convoke: Kreaturen zahlen „{1} or {W}“ | unscharf | {W} zahlt nur eine weiße Kreatur; sonst {1} (CR 702.51). |

Bemerkenswert: Bei Crumbling Colossus beschreibt derselbe Rater den Bounce als Antwort
auf den Opfer-Trigger korrekt. Der Wavesifter-Fehler ist also eine Inkonsistenz, kein
durchgängiges Missverständnis.

Gezielt geprüft und korrekt (Auswahl): Cascade wirkt die Karte und löst Chulane aus
(Captured Sunlight, Ardent Plea, Stormcaller's Boon); Prepare-Kopien sind Hexereien und
lösen nicht aus; Unearth plus Bounce führt ins Exil (Brackwater Elemental); Phantasmal
Bear wird beim Anzielen geopfert; Fluchsicherheit blockt den eigenen Bounce nicht, Shroud
(Lightning Greaves) schon; Leonin Relic-Warder gibt die exilierte Karte beim Bounce zurück;
Groundswell und Mysteries of the Deep prüfen Landfall bei Verrechnung; frisch gewirkte
Kreaturen dürfen für Convoke getappt werden; Token-Kopien (Esix) lösen ETBs, aber nicht
Chulane aus; Bounce-Länder (Simic Growth Chamber) mit Chulanes Landeffekt.

## Fehlermuster

- In der Zufallsstichprobe gibt es kein Fehlermuster, weil es keine Fehler gibt.
- Einziger gefundener Sachfehler (Zusatzprobe): **Stapel-Timing bei Opfer-Triggern**
  (Evoke). Verwandt und daher am ehesten fehleranfällig: verzögerte Opfer-/Exil-Trigger,
  „in response“-Fenster, Kombination mehrerer ETB-Trigger.
- Zweite, schwächere Schwachstelle: **Bezahlregeln im Detail** (Convoke-Farbe) und
  **Terminologie** („land drop“ für einen Effekt, der kein Landspiel ist).
- Stark: Wirken vs. Ins-Spiel-Bringen (Token, Blink, Undying, Unearth, Cascade),
  Landfall mit Chulanes Landeffekt, Zonenwechsel (neues Objekt, Marken weg, Aura fällt ab),
  Farbidentität und Manaproduktion, Rulings werden korrekt zitiert und angewandt.
- Der Rater markiert eigene Unsicherheit ausdrücklich („not engine-checked“, „I assume“);
  die 16 per Stichwort gefundenen Claims dieser Art sind regeltechnisch korrekt.

## Auswirkung auf die H-Bewertung

- Stichprobe: keine Fehler, also keine Änderung. Die fünf unscharfen Formulierungen
  ändern keine Bewertung.
- Wavesifter (H 60, K 50): Richtung leicht nach oben bei K, H praktisch unverändert
  (höchstens +5). Evoke {G}{U} plus Bounce {3} kostet fünf Mana, genau wie das normale
  Wirken; der Trick bringt die Karte auf die Hand statt den 3/2-Flieger ins Spiel und
  spart beim nächsten Durchlauf die {3} für den Bounce.
- Briarhorn (H 55): gleiche Lücke in der `reason` („evoked mode loses the body“), aber
  Evoke {1}{G} plus {3} ist teurer als das normale Wirken für vier Mana. Keine Änderung.
- Appeal to Eirdu: keine Änderung (Nichtkreaturzauber, Detail ohne Einfluss).

## Grenzen

- Ein Rater (F1), ein Prüfer; keine Zweitprüfung.
- Geprüft ist die Regelrichtigkeit der Claims, nicht die Höhe der Scores und nicht, ob
  wichtige Interaktionen fehlen (Auslassungen sind in einem Claim-Audit unsichtbar; der
  Wavesifter-Fall zeigt, dass sie vorkommen).
- Karten aus neuen Sets (Prepare, Empower Jace, Vivid, Blight, Behold) habe ich nur gegen
  Text und Rulings in `facts.jsonl` geprüft.

## Dateien

- `OUT_claims_D.jsonl`: 100 Zeilen, Felder `card`, `rater`, `interaction`, `verdict`, `why`,
  zusätzlich `stratum`, `claim_idx`, `trivial`, `precision_note`.
