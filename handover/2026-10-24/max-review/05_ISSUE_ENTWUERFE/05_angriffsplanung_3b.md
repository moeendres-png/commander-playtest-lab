# Issue-Entwurf 05 — Angriffsplanung als Ganzes (Phase 3b)

Quelle: Max-Review R-07 (`03_VERBESSERUNGEN.md`), Symmetrie zu Phase 3a (#1006).
Status: Entwurf aus dem Max-Review 2026-10-24, nicht eingereicht. Refs: #1006.

## Objective

Angriffe wie Blöcke als Ganzes planen: Statt jeden Angreifer einzeln
zu bewerten, wird die Deklaration als Menge bewertet — inklusive
Crackback (was der Gegner zurückschlagen kann) und inklusive der
Frage, ob ein Angriff überhaupt lohnt. Symmetrie zu Phase 3a, die
Blöcke als Ganzes plant.

## Source lock

- Lab-main: `ee47312a7` (Stand Max-Review 2026-10-24)
- Engine-Pin: v13 `90f5c4d3f8`
- Ausgangspunkt: Angriffs-Score in `full_game_pilot_views.py:1466`
  („Imagine the Worst", Score ≤0 = halten), einzelne
  Angreifer-Bewertung ohne deklarationsweite Planung (Pass A)
- #1006-Body: „Angriffsentscheidungen unverändert (Phase 3b)";
  3a-Effekt (Body, 24 Spiele): Blockrunden mit tödlichem Rest 19→15
  (aufgezeichnet) bzw. 19→16 (echte Spiele)

## Read first

- #1006 (Phase 3a): Wie „Blöcke als Ganzes" implementiert und gemessen
  wurde — das Messprotokoll ist die Vorlage (aufgezeichnete Spiele +
  gepaarte Seeds, gleiche Signatur-Logik).
- `04_RECHERCHE.md` D2: **Keine belastbare externe Quelle für eine
  Commander-Bedrohungs-/Politik-Leiter gefunden.** Das
  Multiplayer-Aggregationsziel aus dem Pilot-Handoff (meinScore −
  maxGegner − λ·Mittel) ist damit **MODELED** (eigene Annahme), keine
  übernommene Theorie — im PR so zu kennzeichnen, nicht als
  „Standard" zu verkaufen.
- Die 3a-Lehre zur Metrik: „needless chumps" wurde durch
  Ganzes-Denken falsch — die Metrik muss mit der Änderung
  mitgezogen werden, sonst misst man Artefakte.

## Items

1. **Metrik zuerst:** Angriffs-Metriken definieren, die unter
   Ganzes-Planung sinnvoll bleiben (Angriffe, vergebliche Angriffe,
   Crackback-Schaden, erhaltene Angreifer). Alte Metrik auf 3a-
   Transkripten gegenrechnen, um den Artefakt-Effekt zu zeigen.
2. **Planung als Ganzes:** Deklarationsmenge gemeinsam bewerten
   (Schaden vs. Verlust vs. Crackback); Halten ist eine legitime
   Deklaration (leere Menge), kein „kein Angriff gefunden".
3. **Messung wie 3a:** 24 aufgezeichnete Spiele (Angriffsrunden auf
   gleichen Positionen zählen) + 24 gepaarte Real-Pod-Seeds.
   Signatur: Angriffe, vergebliche Angriffe, Sieger.
4. **Bericht:** Vorher/Nachher je Metrik + Sieger; MODELED-Annahmen
   (Aggregation, Crackback-Term) explizit benannt.

## Acceptance (mit Falsche-Grund-Kontrolle)

- **Akzeptanz:** Angriffs-Metrik verbessert sich, kein Maß
  verschlechtert sich (Holm über die bewegten Metriken).
- **Falsche-Grund-Kontrolle:** Die neue Metrik, auf Vor-3b-
  Transkripten berechnet, muss die 3a-Ära-Zahlen reproduzieren —
  sonst misst die neue Metrik etwas anderes als die alte und der
  Vergleich ist ungültig.
- **Kein Metrik-Trick:** Eine Verbesserung, die nur entsteht, weil
  die Metrikdefinition geändert wurde (ohne dass sich Angriffe
  geändert hätten), gilt als nicht erreicht — Angriffszählung auf
  gleichen Positionen ist die Kontrolle.
- Pilot-Änderung → 10-Seed-Echtspiel-Vergleich im PR +
  Dirigent-Review vor Merge.

## Test command

```
# Aufgezeichnete + gepaarte Spiele (Treiber-Muster wie Phase 4b, ab Worktree mit gebautem .runtime):
PYTHONPATH=<worktree>/src python3 <attack_compare.py> --seeds 1..24 --pod real
# Unit-Tests der geänderten Pilot-Stellen:
PYTHONPATH=<worktree>/src python3 -m pytest tests/unit/ -q -k "attack or combat or pilot"
```

## Stop condition

Stop nach dem 24-Paar-Vergleich + Bericht. Kein Ausbau zu
Politik-/Bedrohungsmodellen in diesem Issue (das ist ein eigenes
Thema, und es hat keine externe Quelle — s. Read first).

## Rules footer

XMage ist die einzige Rules Engine. Der Pilot wählt nur unter
Engine-angebotenen legalen Optionen; Angriffsplanung ändert keine
Regeln, nur die Wahl. Keine Sammlungsdaten lesen oder zitieren.
Neuer Code ohne `Any` (`object` nehmen).
