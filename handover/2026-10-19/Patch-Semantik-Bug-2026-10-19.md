# KRITISCH: Fork-Patches verändern Spielsemantik
**Date:** 2026-10-19 21:05 CEST  
**Status:** BLOCKER für Fork-Push  
**Für:** Claude-Thread (Java-Debugging erforderlich)

## Befund

36-Seed-Vergleich JAR A (mit Patches) vs JAR B (Baseline 348b37db):

| Metrik | JAR A | JAR B |
|--------|-------|-------|
| Erfolgreich | 35/36 | 36/36 |
| Seed 10 | FAILED (ENGINE_FAILURE) | OK |
| Semantische Mismatches | — | 8 Seeds |

### Die 8 Mismatches (Seeds 5, 8, 17, 18, 21, 26, 28, 29)

Beispiele:
- **Seed 5:** A: 3980 decisions, Winner [3] | B: 5765 decisions, Winner [1]
- **Seed 17:** A: 6176 decisions, Winner [2] | B: 5735 decisions, Winner [1]
- **Seed 21:** A: 4324 decisions, Winner [2] | B: 3325 decisions, Winner [4]

Unterschiedliche Winner + unterschiedliche Decision-Counts = **die Patches verändern die Spiellogik**, nicht nur Performance.

### Seed 10 Bug
- JAR A: ENGINE_FAILURE (reproduzierbar, 2x)
- JAR B: OK
- → Bug ist definitiv in den Patches

## Verdächtige Patches

Alle auf Branch `perf-avoid-nested-playable-copy`:

1. **P1:** `GameState.getPlayersInRange()` Fast-Path
   - Sollte nur Performance sein
   - Wenn der Fast-Path falsche Spieler zurückgibt → falsche Targets → andere Spiele

2. **P2:** `CardImpl.getAbilities(Game)` Fast-Path
   - Sollte nur Performance sein  
   - Wenn der Fast-Path Abilities falsch filtert → fehlende/falsche Aktionen

3. **Nested-Copy-Fix** in `PlayerImpl`
   - Vermeidet verschachtelte Game-State-Copies
   - Wenn die Copy-Semantik falsch ist → State-Korruption

## Was zu tun ist

1. **Bisektion:** Welcher der 3 Patches verursacht die Mismatches?
   - Jeden Patch einzeln revertieren und 36-Seed wiederholen
   - Oder: Code-Review der 3 Patches auf Semantik-Fehler

2. **Seed 10 Debug:** Welche Aktion crasht?
   - Diagnostics SHA: 933943c612fd459d (JAR A), 6fabfa8fd0c8fb8d (Retest)
   - Bridge-Logs analysieren

3. **Fix + Retest:** Nach Fix erneut 36-Seed mit 0 Mismatches

## Evidenz
- `/tmp/compare_a.json` (JAR A, 35/36)
- `/tmp/compare_b.json` (JAR B, 36/36)
- JAR A: `engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar`
- JAR B: `~/workspace/tmp/xmage-engine-bridge-base-348b37db.jar`

## Blockiert
- Fork-Push
- Repin
- Alle davon abhängigen Tasks
