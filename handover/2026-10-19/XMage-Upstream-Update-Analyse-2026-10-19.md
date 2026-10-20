# XMage Upstream-Update Analyse: 108 Commits
**Date:** 2026-10-19 23:10 CEST  
**Von:** Pin 348b37db (1.4.61V1) → upstream/master (bb0ed0f7)

## Übersicht

- **108 Commits** hinter upstream (Hans sagte 644 — GitHub UI zählt evtl. anders, tatsächlich 108)
- **29** neue Karten-Implementierungen
- **49** Bug-Fixes
- **30** sonstige (Tests, Dev, Sets, etc.)

## Kategorien

### Neue Karten (29)
Hauptsächlich neue Sets (MDD, MSC, ECL, TRK). Relevant für Precon-Coverage, aber nicht kritisch.

### Bug-Fixes (49)
Wichtigste:
- `1afc0c2f` Mana abilities — improved 605.1a support (Selvala etc.)
- `ede3b063` Triggers an additional time — Panharmonicon Combo-Support (50+ Karten)
- `54463f0b` Elesh Norn, Mother of Machines — game error fix
- `0311c352` Additional costs — Convoke/Blitz fix
- `713a740f` Party count — StackOverflowError fix

### KRITISCH: Konflikte mit Fork-Patches

Diese upstream-Commits ändern **exakt die Dateien**, die unsere Patches modifizieren:

| Datei | Unsere Patches | Upstream-Commits | Konflikt-Risiko |
|-------|---------------|------------------|-----------------|
| `GameImpl.java` | getRulesSeed (Fork-API) | b784414c (memory leaks) | **HOCH** |
| `GameState.java` | P1 getPlayersInRange | 5915cee5, 2115a3da | **HOCH** |
| `CardImpl.java` | P2 getAbilities | 2115a3da | **HOCH** |
| `PlayerImpl.java` | Nested-Copy-Fix | b784414c | **HOCH** |
| `AbilitiesImpl.java` | singleton() | 2115a3da | **MITTEL** |

## Fork-spezifische APIs (müssen re-applied werden)

Diese existieren NUR in unserem Fork, nicht in upstream:
- `getRulesSeed()` in GameImpl (Bridge braucht das!)
- P1: `getPlayersInRange` Fast-Path
- P2: `getAbilities` Fast-Path (**BUG — muss zuerst gefixt werden!**)
- Nested-Copy-Fix in PlayerImpl
- Jace-Fix (`CanBeYourCommanderAbility`)
- ~45 neue/simplified Karten

## Empfohlene Reihenfolge

1. **ZUERST:** P2-Bug fixen (Claude-Thread) — sonst ist der Fork instabil
2. **DANN:** 36-Seed mit 0 Mismatches verifizieren
3. **DANN:** Upstream-Update als eigenes Projekt:
   a. Neuen Branch `update-upstream-2026-10` von upstream/master
   b. Fork-Patches cherry-picken/re-applien
   c. Konflikte in den 5 kritischen Dateien manuell lösen
   d. Bridge testen (getRulesSeed etc.)
   e. Vollständige Requalifizierung (PB-03)
   f. 36-Seed Abnahme
4. **ERST DANN:** Repin in config/rules_engines.json

## Aufwandsschätzung

- Analyse: ✅ fertig (dieses Dokument)
- Cherry-pick + Konflikte: 2-4 Stunden (Claude-Thread, Java)
- Bridge-Anpassung: 1-2 Stunden (falls APIs sich geändert haben)
- Requalifizierung: 1-2 Stunden
- 36-Seed: ~35 Minuten
- **Total: ~1 Arbeitstag**

## Für Claude-Thread

Branch: `update-upstream-2026-10` (noch zu erstellen)
Basis: upstream/master @ bb0ed0f7
Fork-Patches zum re-applien: siehe Liste oben
Kritische Dateien: 5 (Tabelle oben)
Abnahme: 36-Seed, 0 Mismatches, Bridge-JAR baut
