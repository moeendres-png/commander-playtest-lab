# M4 — Prefilter-Wiederholung nach Merge von Lab-PR #968

Neuer Stand: Lab main `981a4f8f738f` (Merge #968, 2026-10-22 20:00 CEST).
Die Spiele (Baselines und laufende Buendel-Laeufe) bleiben auf dem
M4-Source-Lock `d48bbe5f2` gemessen - #968 aendert nur die Analyse-Schicht
(card_facts/xmage_calibration), nicht Engine, Pilot oder Pin; der Diff
gegen `d48bbe5f2` umfasst exakt die drei #968-Dateien.

## Neue Deltas (Prefilter auf main 981a4f8f7)

- R1 (Irrigated Farmland => Temple of Epiphany): colored_delta jetzt
  {R: +1, W: -1} (vorher falsch U -1, W -1, flex -1). WARN bleibt -
  allein wegen des echten W-Quellen-Verlusts, wie in Nachtrag 1 §5
  vorhergesagt.
- R6 (Adarkar Wastes => Restless Spire): colored_delta {R: +1, W: -1},
  WARN bleibt (gleicher Grund).
- Buendel R-A (Manabasis): colored_delta {R: +3, W: -3}; WARN bleibt
  wegen Ishai-Castwahrscheinlichkeit T4 play 0,589 -> 0,536 (Delta -0,053)
  - der W-Verlust ist der Messgegenstand des Buendels.
- Buendel R-B: vorher WARN (R -1) -> jetzt PASS_TO_GAMES,
  colored_delta {} - die alte Warnung war ein Zaehl-Artefakt des Bugs.
- Buendel R-C: PASS (unveraendert). Chulane-Buendel: alle PASS;
  C-A-Delta jetzt {G: +1, U: +2, W: +2}, flexible +3.

## Korrigierte Chulane-Castability (mit Farbpruefung)

E[Cast] Chulane jetzt play 6,03 / draw 5,71 (vorher ohne Pip-Bedingung
6,24 / 5,93). Der Fix fuellt gleichzeitig die Landfarben aus den Facts;
das ueberkompensiert die neu hinzukommende Pip-Bedingung. P(T5, play)
0,45 -> 0,503. RogShai unveraendert (Ishai play 4,72). Rohdaten:
castability_chulane_968.json, castability_rogshai_968.json,
prefilter_bundles_*_968.json, prefilter_r1r6_968.json in diesem Ordner.
