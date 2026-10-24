# Issue-Entwurf 01 — Abort-Programm: Zahlungsabbrüche messen, Top-3-Ursachen schließen

Quelle: Max-Review R-01 (`03_VERBESSERUNGEN.md`), Befund B-05 (`02_BEFUNDE.md`).
Status: Entwurf aus dem Max-Review 2026-10-24, nicht eingereicht. Refs: #1006, #1003 (Phase 4b).

## Objective

Die Zahlungsabbruch-Rate („Cancel mana payment") im Real-Pod von der
Max-Review-Baseline aus senken, indem die tatsächlichen Ursachen gemessen
und die drei häufigsten je einzeln geschlossen werden — nicht durch eine
neue Hypothese, sondern durch Zählung in echten Transkripten.

## Source lock

- Lab-main: `ee47312a7` (Stand Max-Review 2026-10-24)
- Engine-Pin: v13 `90f5c4d3f8`
- Mess-JAR: `bridge_maxreview.jar` (sha256 `0fda80ec…5fddb9`, selbst gebaut)
- Baseline: 24 Real-Pod-Seeds, Main + Pin v13 (Kette `abort24/`, Max-Review Pass B)
- Auftragszahl zum Start: 136 von 3.599 Zahlungen enden mit „Cancel mana
  payment" (24 Spiele, #1006-Body — Body-Behauptung, keine Verifikation)

## Read first

- `02_BEFUNDE.md` B-05: Warum die alte Hypothese (Filterländer +
  eingeschränktes Any-Color als Hauptursachen) UNBELEGT ist.
- `~/workspace/tmp/phase4b/phase4b_check.py`: Detektor-Vorbild (Antwort
  „Cancel mana payment" in `mana_payment`, 1× je Cast; Zahlen aus
  `numeric_choice` lesen, nicht aus Labels — Phase-4b-Lehre).
- Phase-4b-Befund: Eine einzige Ursache (Engine-Ceiling 2147483647) stellte
  15/15 Antworten — Ursachen sind einzeln schließbar.

## Items

**Stand 2026-10-25 (Max-Review): Item 1 erledigt — Baseline 135 abgebrochene Casts /
85.982 Entscheidungen = 1,57/1000, 136/136 rohe Cancels erzwungen (92 nur-Cancel, 44 nur
nicht-zahlende Alternativen), 0 echte Wahlen; alte Hypothese (Filterland/Any-Color)
widerlegt. Start bei Item 2 (Code-Analyse des Entstehungsorts).**

1. **Baseline auswerten (kein neuer Code):** Cancel-Rate der 24
   Abort-Ketten-Spiele neu zählen (Detektor wie oben) + Ursachen
   klassifizieren. Klassifikationsregel aus echten Transkripten ableiten
   (welches Land/welche Kosten standen an, was bot die Engine an) — die
   Klassen nicht vorab annehmen.
2. **Pro Ursache ein Fix, pro Fix ein Akzeptanzkriterium:** z. B.
   „Filterland-Cancels 0 in 24 Seeds" statt „Rate sinkt um x %".
   24 Paare tragen nur große Effekte (Phase-4b-Lehre: 7→0 sichtbar,
   134→134 nicht) — kleine Ratenänderungen sind kein Akzeptanzkriterium.
3. **Je Fix ein gepaarter 24-Seed-Vergleich** (gleiche Seeds, gleiche JAR,
   gleiche Pods) mit Signatur: Cancel-Rate + 17 Maße + Sieger. Kein
   Siegerwechsel erwartet (wie bei 4b: 23/24 bit-identisch).
4. **Bericht:** Ursachen-Ranking mit Anteilen, je Fix Vorher/Nachher,
   offene Rest-Ursachen mit Anteil.

## Acceptance (mit Falsche-Grund-Kontrolle)

- Der Detektor reproduziert auf den #1006-Transkripten (soweit verfügbar)
  bzw. auf der Baseline die Größenordnung der Auftragszahl — sonst ist
  der Detektor falsch, nicht die Rate gesunken.
- Ein Fix, der Cancels nur in eine andere Prompt-Klasse verschiebt
  (z. B. von `mana_payment` nach `amount`), gilt als **nicht geschlossen**:
  Gesamt-Abbruchrate über alle Zahlungsklassen muss sinken.
- Jeder Fix braucht den 10-Seed-Echtspiel-Vergleich im PR (harte Regel
  für Pilot-Änderungen) + Dirigent-Review vor Merge.
- Evidenzklassen je Zahl (DIRECTLY_VERIFIED / CODE_DERIVED / MODELED /
  UNKNOWN); UNKNOWN ist niemals PASS.

## Test command

```
# Detektor + Baseline (nach Kettenende, ab Worktree mit gebautem .runtime):
PYTHONPATH=<worktree>/src python3 <abort_analyse.py> ~/workspace/tmp/max-review/abort24/
# Unit-/Vertragstests der geänderten Pilot-Stellen:
PYTHONPATH=<worktree>/src python3 -m pytest tests/unit/test_pilot_x_and_pay_amount.py -q
```

## Stop condition

Stop nach den Top-3-Ursachen, oder früher, wenn alle Rest-Ursachen je
unter 1 % der Zahlungen liegen. Kein Scope-Creep in andere Abbruchklassen
(X=0, Kickerketten — bereits Phase 4b).

## Rules footer

XMage ist die einzige Rules Engine. Der Pilot wählt nur unter
Engine-angebotenen legalen Optionen; keine erfundenen Aktionen, keine
stillen Skips, keine manuellen Outcome-Injektionen. Keine
Sammlungsdaten (`data/collections/**`, `data/coverage_decks/collection/**`)
lesen oder zitieren. Neuer Code ohne `Any` (`object` nehmen).
