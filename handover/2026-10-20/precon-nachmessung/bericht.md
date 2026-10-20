# Precon-Nachmessung: Fehlende Karten (Muse, 2026-10-20)

## Ergebnis zuerst

**Beide alten Zahlen sind widerlegt.** Gemessen über den produktiven Import-Pfad:

| Stand | Import OK (wie vorliegend) | Fehlende Karten | Sonstige Blocker |
|---|---|---|---|
| Baseline (Pin `348b37db`) | **173/195** | **53 distinkte Karten** in 18 Decks | 4 Decks: Commander-Name in „A // B"-Form |
| Fork-Head `10931648` | **191/195** | **0** | nur dieselben 4 Namens-Decks |

Mit dem Daten-Fix der 4 Commander-Namen (Frontform) importieren Baseline 177/195
und Fork **195/195**. Evidenzklasse: DIRECTLY_VERIFIED.

## Methode

- Produktiver Pfad: Python `ExternalRulesAdapter.import_deck()` (JSONL) →
  Java `XmageDeckImporter` (CardRepository-Auflösung + Commander-Validierung).
  **Keine Spiele** — mein alter Sweep (Benchmark-Spielpfad, wall_s=0.0) war methodisch
  wertlos; seine „195/195 Crash"-Aussage ist hiermit zurückgenommen.
- Beide JARs, je ein frisches Arbeitsverzeichnis (frische Card-DB — keine stale Rows).
- Vertiefung: Der Importer meldet pro Aufruf nur die erste unbekannte Karte. Für jedes
  fehlgeschlagene Deck wurde iterativ in Diagnose-Varianten (Originale unverändert)
  die gemeldete Karte durch einen Füller ersetzt (Plains bzw. Platzhalter-Commander),
  bis die Auflösung sauber war. Vollständigkeit: Der Importer löst erst alle Karten
  auf und validiert danach — sobald der Fehler auf Validierung wechselt (Farbidentität
  des Füllers), ist die Enumeration abgeschlossen.
- Skripte: `measure_precon_imports.py`, `measure_precon_imports_deep.py` (dieser Ordner).
- Rohdaten: `imports_base.json`, `imports_fork.json`, `deep_base.json`,
  `deep_fork.json`, `deep_base_mv.json`.

## Befunde im Detail

1. **53 distinkte Karten fehlen am Pin** (nicht 221). Verteilung: Ichor Elixir in
   5 Decks, Desert Warfare und Psychic Paper in je 2, der Rest in je 1 Deck.
   Schwerpunkte: Doctor-Who-Decks (Susan Foreman, The Pandorica, Missy, Osgood u. a.),
   die „Path of the …"-Reihe (5 Karten), 2026_multiverse_reforged allein mit 19 Karten
   (darunter Commander **Jace, Multiverse Architect** — die Notiz der früheren
   Hintergrund-Research war in diesem Punkt korrekt).
2. **Der Fork deckt alle 53 ab** (48 neue Kartendateien, vgl. Bisektion) — am Fork
   scheitert kein Deck an einer fehlenden Karte.
3. **4 Decks scheitern an Deck-Daten, nicht an der Engine:** `commander.commanders`
   enthält „Vorderseite // Rückseite", der Importer löst die Frontform auf →
   `CARD_IDENTITY_MISMATCH` (2022_heads_i_win, 2023_angels, 2023_from_cute_to_brute,
   2024_raining_cats_and_dogs). Mit Frontnamen importieren alle 4 auf beiden JARs.
4. **Heuristik-Autopsie:** Von meinen 221 „fehlenden" Karten waren ~200 falsch-positiv
   (Dateinamen-Abgleich ignoriert Registrierungen, Split-Namen und Diakritika), und
   ~32 der echt fehlenden 53 standen nicht auf der Liste. Die Zahl 221 darf nicht
   mehr zitiert werden.
5. **PR #914 („192/195, 0 fehlende Karten") nicht reproduziert:** Fork misst 191/195
   wie vorliegend (195/195 nach Namens-Fix); „0 fehlende Karten" gilt nur für den
   Fork, nicht für die Baseline (53).
6. **Abgrenzung:** Import-Erfolg ≠ Spiel-Erfolg. Die in WS2 beobachteten
   ENGINE_FAILUREs in echten Spielen (z. B. importiert 2011_counterpunch sauber,
   scheiterte aber im Spiel) sind ein separates, weiter offenes Problem (Issue #920,
   Runtime-Ursache UNKNOWN).

## Konsequenzen

- Issue #920 kann mit diesen Zahlen korrigiert werden (Korrekturtext schlägt Muse vor).
- Daten-Fix: 4 Commander-Namen in `data/decks/precons/` auf Frontform bringen
  (kleiner Fix auf dem Precon-Branch).
- Karten-Arbeit am Pin ist abgeschlossen: Es fehlen keine weiteren Karten für die
  195 Precons; der Fork-Stand ist importseitig vollständig.
