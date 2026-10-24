# Issue-Entwurf 03 — Sonderfall-Register mit Auslöse-Zählung

Quelle: Max-Review R-02 (`03_VERBESSERUNGEN.md`), Befund B-16 (`02_BEFUNDE.md`).
Status: Entwurf aus dem Max-Review 2026-10-24, nicht eingereicht.

## Objective

Jeder hartcodierte Einzelkarten-/Prompt-Sonderfall im Piloten bekommt
einen Zähler. Fälle, die in 100+ echten Spielen nie feuern, werden
sichtbar — und dann je einzeln entfernt (tot) oder repariert (falsch
verdrahtet, wie #862 erst mit #868). Kein Verhalten ändern, nur messen.

## Source lock

- Lab-main: `ee47312a7` (Stand Max-Review 2026-10-24)
- Engine-Pin: v13 `90f5c4d3f8`
- Betroffene Stellen (Pass A): hartcodierte Fälle in
  `full_game_pilot_views.py` / `choices.py` (B-16, genaue Stellen aus
  `00_ABDECKUNG.md` zu übernehmen)

## Read first

- `02_BEFUNDE.md` B-16: Umfang der Wartungsfläche.
- Die #862-Lehre: Eine Regel, die in echten Spielen nie läuft, ist
  toter Code — identische Vergleichsergebnisse bedeuten dann „kein
  Effekt", nicht „bestätigt".
- Vorhandene Transkripte: Phase-2-, Phase-4b- und Abort-Ketten
  (~150 Spiele, `~/workspace/tmp/phase2/`, `~/workspace/tmp/phase4b/`,
  `~/workspace/tmp/max-review/abort24/`).

## Items

1. **Inventar:** Alle Sonderfälle mit Datei:Zeile + Auslösebedingung
   in ein Register (Tabelle im Issue/PR, nicht nur im Code).
2. **Zähler einbauen (kein Verhalten):** Jeder Fall zählt seine
   Auslösungen; Zähler landen im Transkript/Report, sonst nirgends.
   Der Diff darf keine Entscheidungslogik berühren.
3. **Schritt 1 ohne neue Spiele:** Zähler-Stand aus vorhandenen
   Transkripten rekonstruieren, soweit die Transkripte das hergeben;
   sonst: 24 Seeds mit Zählern neu spielen und auszählen.
4. **Schritt 2:** Fälle mit 0 Feuern in ≥100 Spielen → je ein eigenes
   Folge-Issue (entfernen vs. reparieren, mit Beleg, warum der Fall
   je gedacht war).

## Acceptance (mit Falsche-Grund-Kontrolle)

- **Verhaltens-Identität:** 24 gepaarte Seeds mit/ohne Zähler sind
  bit-identisch (Twin-Hash). Jede Hash-Abweichung = der Zähler hat
  Verhalten geändert → PR abgelehnt.
- **Falsche-Grund-Kontrolle:** Ein Zähler, der auf Transkripten 0 zeigt,
  auf denen der Fall nachweislich feuern müsste (konstruiertes
  Beispielspiel mit der Karte/dem Prompt), ist falsch verdrahtet —
  der Zähler selbst braucht dann einen Test, der ohne ihn fehlschlägt.
- **Keine Sammel-Löschung:** Tote Fälle werden je einzeln entfernt,
  mit eigener Begründung — kein „alle 0-Feuer-Fälle raus"-PR.

## Test command

```
# Verhaltens-Identität (Twin-Hash, ab Worktree mit gebautem .runtime):
PYTHONPATH=<worktree>/src python3 <twin_run.py> --seeds 1..24 --with-counters --without-counters
# Unit-Tests:
PYTHONPATH=<worktree>/src python3 -m pytest tests/unit/ -q
```

## Stop condition

Stop, wenn das Register vollständig ist und jeder 0-Feuer-Fall ein
Folge-Issue hat. Die Folge-Issues selbst gehören nicht in dieses Issue.

## Rules footer

XMage ist die einzige Rules Engine. Zähler sind Beobachtung, keine
Regeln: Der Pilot wählt weiterhin nur unter Engine-angebotenen legalen
Optionen. Keine Sammlungsdaten lesen oder zitieren. Neuer Code ohne
`Any` (`object` nehmen).
