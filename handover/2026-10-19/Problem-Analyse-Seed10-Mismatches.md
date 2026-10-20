# Problem-Analyse: Was ist das Problem und was muss gefixt werden
**Date:** 2026-10-19 21:20 CEST  
**Status:** Analyse abgeschlossen, Fix benötigt Claude-Thread

## Das Problem (sauber definiert)

### 1. Seed 10 ENGINE_FAILURE (reproduzierbar)
- **Was:** Seed 10 crasht konsistent mit `ENGINE_FAILURE [XMAGE_ACTION_EXECUTION_FAILED]`
- **Wo:** JAR A (mit Patches), NICHT in JAR B (Baseline)
- **Reproduzierbarkeit:** 2x bestätigt (78s, 80s)
- **Was das bedeutet:** Einer der 3 Patches verursacht einen Crash bei einer spezifischen Aktion

### 2. 8 Semantische Mismatches
- **Was:** Bei Seeds 5, 8, 17, 18, 21, 26, 28, 29 produzieren JAR A und JAR B unterschiedliche Spiele
- **Beispiel Seed 5:** 
  - JAR A: 3980 Entscheidungen, Winner [3], 60.1s
  - JAR B: 5765 Entscheidungen, Winner [1], 95.7s
- **Was das bedeutet:** Die Patches verändern die Spiellogik, nicht nur Performance
- **Schwere:** KRITISCH — Performance-Patches dürfen niemals die Semantik ändern

## Die 3 verdächtigen Patches

Alle auf Branch `perf-avoid-nested-playable-copy` im `mage`-Fork:

### Patch 1: P1 `GameState.getPlayersInRange()` Fast-Path
**Was es tun sollte:** Performance-Optimierung für Spieler-Reichweiten-Berechnung  
**Was es möglicherweise falsch macht:** 
- Gibt falsche Spieler-Liste zurück → falsche Targets → andere Entscheidungen
- Oder: Cache wird nicht korrekt invalidiert → stale Daten

**Zu prüfen:** 
- Wird der Fast-Path unter allen Bedingungen korrekt?
- Gibt es Edge-Cases (z.B. Reichweite 0, alle Spieler tot)?

### Patch 2: P2 `CardImpl.getAbilities(Game)` Fast-Path  
**Was es tun sollte:** Performance-Optimierung für Abilities-Abruf  
**Was es möglicherweise falsch macht:**
- Filtert Abilities falsch → fehlende legale Aktionen → andere Spiele
- Oder: Gibt gecachte Abilities zurück die nicht mehr gültig sind

**Zu prüfen:**
- Werden alle Abilities korrekt zurückgegeben?
- Gibt es Timing-Probleme (Abilities ändern sich während des Spiels)?

### Patch 3: Nested-Copy-Fix in `PlayerImpl`
**Was es tun sollte:** Vermeidet verschachtelte Game-State-Copies (Performance)  
**Was es möglicherweise falsch macht:**
- Copy-Semantik ist falsch → State-Korruption → Crash (Seed 10!)
- Oder: Shared mutable state → Race Conditions

**Zu prüfen:**
- Ist die Copy wirklich äquivalent zur alten?
- Gibt es Stellen wo die alte (tiefe) Copy nötig war?

## Was gefixt werden muss

### Sofort (Blocker)
1. **Seed 10 Crash finden:** Welche Aktion? Welche Karte? Stack Trace?
2. **Bisektion:** Welcher der 3 Patches verursacht es?
   - Patch 1 revertieren → testen
   - Patch 2 revertieren → testen  
   - Patch 3 revertieren → testen
3. **Fix implementieren:** Den fehlerhaften Patch korrigieren oder entfernen

### Danach (Verifikation)
1. **36-Seed erneut:** 0 Mismatches, 0 Crashes erforderlich
2. **Requalifizierung:** PB-03 durch Claude-Thread
3. **Dann erst:** Fork-Push mit Owner-Go

## Was NICHT das Problem ist

- ❌ Nicht die neuen Karten (JAR B hat sie nicht, läuft aber)
- ❌ Nicht die Python-Pilot-Verbesserungen (JAR-Test, kein Python)
- ❌ Nicht flaky (Seed 10 reproduzierbar, 8 Mismatches konsistent)

## Evidenz
- `/tmp/compare_a.json` (VERLOREN durch /tmp-Wipe, wird neu generiert)
- `/tmp/compare_b.json` (VERLOREN, wird neu generiert)
- Dokumentiert in: `Patch-Semantik-Bug-2026-10-19.md`

## Für Claude-Thread
- Branch: `perf-avoid-nested-playable-copy` im `mage`-Fork
- 3 Patches zu reviewen (siehe oben)
- Test: `scripts/benchmark_xmage_full_games.py run --jar <jar> --seeds 10` (schneller Repro)
- Ziel: 36 Seeds, 0 Mismatches vs Baseline
