# Kartenverständnis-Raster v2: Rater-Prompt (prompt_template)

Entwurf. Der Prompt ist **englisch** (wie v1 und der Kartentext), die Spezifikation deutsch. Die ausführbare Fassung ist
`render_prompt.py` (`python3 scripts/render_prompt.py --card "<Name>"` druckt System- und Nutzerteil), das Schema ist
`output_schema.json`, ein Formatbeispiel mit einer **erfundenen** Karte (keine Poolkarte, keine Bewertung) ist `example_output.json`.

## 1. Aufbau

| Teil | Inhalt | Inhalt je Aufruf |
|---|---|---|
| **System** (statisch, cachebar) | `GUIDE_v2.md` ohne Anker-Region, dann die Anker-Tabellen aus `anchors.json` (leave-one-anchor-out, siehe 2), dann die Ausgaberegeln (`SCHEMA_HINT`) | gleich für alle Karten, außer dass bei einer v1-Ankerkarte genau diese Karte aus ihrer eigenen Tabelle fehlt |
| **Nutzer** (je Karte) | Satz "Rate this card ...", dann der **Kartenblock**: Fakten, Castability, Peers, Rulings, Muster-Treffer | nur diese Karte, keine früheren Karten, keine Zwischenergebnisse |

Anweisung an den Rater (steht im Guide, Regel 5): **Fakten und Muster sind Hinweise, das Urteil bleibt beim Rater.** Jeder
gezeigte Mustertreffer wird in `pattern_check` als correct/wrong/irrelevant beurteilt; Regelbehauptungen (Regel 3) gehören mit wörtlichem Zitat in
`rule_claims`; Unsicherheit steht in `uncertainty`, und `confidence` ist high, medium oder low.

Eine Karte je Aufruf, keine Stapel: Querbeeinflussung zwischen Karten (v1 musste sie per Regel verbieten) entfällt, und der
statische Systemteil wird gecacht. Kostenfolge in `calibration_plan.md`.

## 2. Anker ohne Abschreiben (leave-one-anchor-out)

Der Anker-Block ist in `anchors.json` (Quelle: `build_anchors.py`). Wird eine der zehn v1-Ankerkarten bewertet, fehlt
sie in ihrer eigenen Ankertabelle (`system_prompt(guide, anchors, leave_out=<Karte>)`); `render_prompt.py --check-leave-one-out`
prüft für alle 63 Pilotkarten im **gesamten** Systemteil (Guide-Text und Tabellen): keine Karte nennt sich selbst, und **keine**
Nicht-Anker-Pilotkarte kommt irgendwo vor. `build_anchors.py` bricht ab, wenn ein Anker nicht im Pool liegt, eine Nicht-v1-Ankerkarte Pilotkarte ist,
oder ein Wert kein Vielfaches von 5 ist. v1-Werte werden mit der Studio-Formel umgerechnet: E, F, T, R mal 25, H gleich
(H minus 1) durch 9 mal 100 (Sol Ring 100, Swords 89, Llanowar Elves 78, Counterspell 67, Farseek 56, Cultivate 44; Länder:
Command Tower 100, Simic Growth Chamber 78, Evolving Wilds 44, Selesnya Guildgate 22).

## 3. Systemteil (Auszug)

Der vollständige Text ist `GUIDE_v2.md`; die Ausgaberegeln am Ende des Systemteils lauten wörtlich:

> Output rules: scores are multiples of 5 from 0 to 100 for E, F, T, R, K, D, H (higher is better, D = low deck cost, H is your own judgement, not the mean); notes: one phrase (at most 15 words) per score; reason: 2 to 3 sentences, what the card really does and what follows; confidence: high|medium|low; uncertainty: text (empty only for high); rule_claims: list of {quote (literal from the card block), interaction, claim, basis}; pattern_check: one entry per pattern hit shown {rule_id, verdict: correct|wrong|irrelevant}; judged_as: land|spell; schema: rubric-v2-card-rating-1; oracle_id and card copied from the block.

## 4. Nutzerteil: Vorlage und gerenderte Beispielkarte

Der Kartenblock wird aus `facts.jsonl` und `patterns.jsonl` gerendert, nie aus `usage_holdout.jsonl` oder `pilot_sample.json`.
Beispiel (Shrieking Drake, nur als Darstellung der Form, **keine Bewertung**):

```
Rate this card. Answer with one JSON object that follows output_schema.json and nothing else.

CARD: Shrieking Drake
oracle_id: 2a8e14be-6f93-428d-a204-e2399dc93797
Mana cost: {U} | Mana value: 1 | Cost symbols (front face): U x1
Type line: Creature — Drake | Group: Creature | Colour identity: U
Power/toughness (front face): 1/1 | Keywords: Flying | Produces mana: none
Game Changer: no | Layout: normal
Oracle text:
  Flying
  When this creature enters, return a creature you control to its owner's hand.
Roles (labels from a tagger and a text rule; they can be wrong): bounce; evasion; mana_sink | main: bounce
On-time cast, reference mana base: turn 1: P(land drops met) 0.9762, P(colours met given lands) 0.8072, P(both) 0.788
Peers with role bounce (main): 33 other pool cards, median mana value 3 (quartiles 2 to 5); this card 1: 0 cheaper, 4 equal, 29 dearer
Peers with role evasion: 155 other pool cards, median mana value 3 (quartiles 2 to 5); this card 1: 0 cheaper, 13 equal, 142 dearer
Peers with role mana_sink: 29 other pool cards, median mana value 3 (quartiles 2 to 4); this card 1: 0 cheaper, 2 equal, 27 dearer
Peers of type group Creature: 477 other pool cards, median mana value 3; this card 1
Creature bodies at the same mana value: 37 peers, median power+toughness 2; this card 2: 5 smaller, 23 equal, 9 larger
Combo hint (combination database, not a popularity figure): 2 listed combination line(s) with Chulane contain this card
Rulings (shown 2 of 2):
  - 2024-06-07: You may return Shrieking Drake itself to its owner's hand as its triggered ability resolves. If you don't control any other creature, you must return it.
  - 2024-06-07: Shrieking Drake's ability doesn't target any creature. Therefore, no player may take actions between the time you choose the creature to return and the time you return it.
Pattern hits (rule-based hints; '~' stands for this card; check each in pattern_check):
  - bounce_own_creature: "when ~ enters, return a creature you control to its owner's hand."
  - etb_own: "when ~ enters, return a creature you control to its owner's hand."
```

Regeln des Renderers: Rulings höchstens 4, je 240 Zeichen; Peers bis zu 3 Rollen plus Typgruppe; "Combo hint" nur bei Wert über 0;
Länder bekommen die Zeile "Land facts" und die Land-Peer-Gruppe statt Rollen-Peers; Karten ohne Text zeigen
"(no rules text: a known fact, not missing data)".

## 5. Ausgabeschema und Beispiel

`output_schema.json` (JSON Schema 2020-12, `additionalProperties` falsch): Pflichtfelder `schema`, `oracle_id`, `card`, `judged_as`,
`scores` (E F T R K D H, ganzzahlig 0 bis 100, Schritt 5), `notes` (je Wert eine Phrase, höchstens 160 Zeichen), `reason`
(60 bis 900 Zeichen), `confidence`, `uncertainty` (bei medium/low mindestens 10 Zeichen), `rule_claims` (höchstens 6, je
`quote` wörtlich aus Kartenblock, `interaction` aus fester Liste, `claim`, `basis` card_text / ruling_shown / inferred_from_text),
`pattern_check` (je gezeigtem Treffer `rule_id` und `verdict`). Geprüft: Schema und Beispiel validieren mit `jsonschema` (Draft 2020-12).

```json
{
 "schema": "rubric-v2-card-rating-1",
 "oracle_id": "00000000-0000-0000-0000-000000000000",
 "card": "Example Cloudhopper (invented card, format example only)",
 "judged_as": "spell",
 "scores": {
  "E": 60,
  "F": 85,
  "T": 0,
  "R": 65,
  "K": 55,
  "D": 65,
  "H": 65
 },
 "notes": {
  "E": "2 mana body with a small ETB, average for its role",
  "F": "cast trigger plus ETB that Chulane's bounce can replay",
  "T": "no effect on opponents",
  "R": "ETB is useful with or without other creatures",
  "K": "replayable ETB, but each loop costs {3}",
  "D": "small body dies to sweepers, one blue pip",
  "H": "solid ETB creature for the loop"
 },
 "reason": "According to the card text the ETB draws a card and the body is a 2/2 flier, so it triggers Chulane when cast and again when Chulane's {3},{T} ability returns it to hand and it is cast again. The loop is slow at three mana per replay, so the value is one extra card now and a late-game engine. A sweeper kills the body but not the card already drawn.",
 "confidence": "medium",
 "uncertainty": "The value of replaying depends on spare mana; the invented text has no cheaper way to return it.",
 "rule_claims": [
  {
   "quote": "When this creature enters, draw a card.",
   "interaction": "etb_reuse",
   "claim": "each cast after a bounce draws another card",
   "basis": "card_text"
  }
 ],
 "pattern_check": [
  {
   "rule_id": "etb_own",
   "verdict": "correct"
  },
  {
   "rule_id": "etb_own_draw",
   "verdict": "correct"
  }
 ]
}
```

## 6. Aufruf-Parameter für den Pilot (vorab festgelegt)

- **Temperatur größer als 0** (Vorschlag 0,7), damit die Streuung zwischen Ratern echte Unsicherheit misst und kein
  deterministisches Duplikat; die Temperatur steht im Laufprotokoll.
- **Zustandslose Einzelaufrufe:** eine Karte je Aufruf, keine Chargen, kein Gespräch; zwei Läufe desselben Modells unterscheiden sich nur durch das
  Sampling. Ihr ICC misst Sampling-Konsistenz (obere Schranke), nicht die Unabhängigkeit von Ratern (siehe `calibration_plan.md`, Abschnitt 1).
- Der Systemteil ist für alle Rater desselben Laufs gleich; das Modell und die Version stehen im Protokoll.
- Antworten, die das Schema verletzen, werden einmal mit der Fehlermeldung wiederholt; die Wiederholungsrate wird berichtet.

## 7. Größe (Schätzung, Tokens)

Zeichen geteilt durch 3,5 als Schätzung (im ersten Pilotaufruf durch den Token-Zähler der API ersetzen):
Systemteil etwa **6.925** Tokens; Nutzerteil über alle 922 Karten Median **426,5**, Mittel 441, p90 642, p99 774,
Maximum 894 (größte Karten: Brigid, Clachan's Heart // Brigid, Doun's Mind, Prudent Fateseer // Peer Review, Kederekt Leviathan); Ausgabe etwa 420 Tokens je Karte (Annahme). Quelle: `data/prompt_token_stats.json`.
