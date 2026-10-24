# Issue-Entwurf 02 — Guides statt Spezialisten: erst A/B, dann schrittweise

Quelle: Max-Review R-08 (`03_VERBESSERUNGEN.md`), offene Owner-Entscheidung O6.
Status: Entwurf aus dem Max-Review 2026-10-24, nicht eingereicht.
**Voraussetzung: O6-Go durch Hans** (Empfehlung aus dem Auftrag: ja,
schrittweise nach Phase 2 — Phase 2, 4b, 1 und 3a sind gemergt, die
Voraussetzung ist erfüllt; die Entscheidung selbst liegt bei Hans).

## Objective

Klären, ob die kuratierten Deck-Guides die hartcodierten
Einzelkarten-/Prompt-Sonderfälle im Piloten ersetzen können, ohne
Verhalten zu verlieren — gemessen, nicht behauptet. Bei negativem
A/B-Ergebnis bleiben die Spezialisten und die Guides nur Ergänzung.

## Source lock

- Lab-main: `ee47312a7` (Stand Max-Review 2026-10-24)
- Engine-Pin: v13 `90f5c4d3f8`
- Guides: 206 Paare, `handover/2026-10-24/deck-guides/` (Neugenerierung
  gegen #997-Katalog am 2026-10-24: 0 von 206 inhaltlich geändert)
- Spezialisten-Seite: `agents/card_knowledge.py` (kuratierte Profile,
  `structural_role_profiles.json`) vs. hartcodierte Fälle in
  `full_game_pilot_views.py` / `choices.py` (Befund B-16)

## Read first

- Pass A (Bridge/Kern): Wo die Spezialisten sitzen und was sie abdecken
  (Datei:Zeile aus `00_ABDECKUNG.md`).
- `02_BEFUNDE.md` B-16: Wartungsfläche der hartcodierten Fälle.
- Deck-Guides (Handover): Welche Fälle Guides überhaupt abdecken —
  nur diese Fälle dürfen in Variante B ersetzt werden.

## Items

1. **Abdeckungskarte:** Jeder Spezialisten-Fall → abgedeckt durch Guide
   (ja/nein) + Guide-Quelle. Nicht abgedeckte Fälle bleiben in beiden
   Varianten unangetastet.
2. **Variante B:** Pilot, der für die abgedeckten Fälle Guides statt
   Spezialisten nutzt (Schalter, kein Löschen der Spezialisten im
   selben PR — sonst ist A/B nicht rückholbar).
3. **A/B auf denselben 24 Real-Pod-Seeds:** A = aktueller Pilot,
   B = Guide-Variante. Signatur: 17 Maße + Zielmetriken (falsche Seite,
   Geschenke, Abbrüche) + Sieger.
4. **Entscheidung dokumentieren:** „ersetzen" (nur abgedeckte Fälle) oder
   „nur ergänzen" + Begründung mit Zahlen. Schrittweises Vorgehen:
   kein Big-Bang-Ersatz aller Fälle auf einmal.

## Acceptance (mit Falsche-Grund-Kontrolle)

- **Akzeptanz für „ersetzen":** Kein Maß verschlechtert sich (Holm über
  die bewegten Metriken), kein Siegerwechsel-Muster. Sonst: nur ergänzen.
- **Falsche-Grund-Kontrolle (die #862-Lehre):** Variante B muss die
  Guides tatsächlich nutzen — Zähler: Guide-Treffer > 0 in den 24
  Spielen. Ein B, das zu A bit-identisch läuft, beweist nichts (Regel
  läuft nie = toter Code, kein A/B-Ergebnis).
- Pilot-Änderung → 10-Seed-Echtspiel-Vergleich im PR + Dirigent-Review
  vor Merge. Kein Fork, kein Repin (Pilot + Daten only).

## Test command

```
# A/B-Kette (Treiber-Muster wie Phase 4b, ab Worktree mit gebautem .runtime):
PYTHONPATH=<worktree>/src python3 scripts/run_full_game_deck_comparison.py --help
# Unit-Tests der geänderten Pilot-Stellen:
PYTHONPATH=<worktree>/src python3 -m pytest tests/unit/ -q -k "pilot or guide or knowledge"
```

## Stop condition

Stop nach der dokumentierten A/B-Entscheidung. Kein Weiterbau von
Guide-Inhalten in diesem Issue (das ist Guide-Pflege, kein Pilot-Issue).

## Rules footer

XMage ist die einzige Rules Engine. Guides sind Wissen über Karten,
keine Regeln: Der Pilot wählt nur unter Engine-angebotenen legalen
Optionen. Keine Sammlungsdaten lesen oder zitieren. Neuer Code ohne
`Any` (`object` nehmen).
