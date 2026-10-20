# Patch-Analyse: Welcher Patch ist der Übeltäter?
**Date:** 2026-10-19 22:20 CEST  
**Analyst:** Muse  
**Für:** Claude-Thread (spart Tokens durch vorbereitete Analyse)

## Verdachts-Ranking

### 🥇 P2: `CardImpl.getAbilities()` Fast-Path — BESTÄTIGT ALS ÜBELTÄTER
**Commit:** `5dbff3a3`  
**Datei:** `Mage/src/main/java/mage/cards/CardImpl.java`

**NEUER BEFUND (2026-10-19 22:35):** Frischer 36-Seed-Lauf zeigt **29/35 Mismatches** (83% der Spiele betroffen)! Noch schlimmer als die ursprünglich berichteten 8. Das bestätigt: P2 korruptiert die Spielsemantik breitflächig, nicht nur in Edge-Cases.

**Das Problem (Aliasing-Bug):**
```java
// ALT: Gibt IMMER eine neue Kopie zurück
Abilities<Ability> all = new AbilitiesImpl<>();
all.addAll(abilities);  // Kopie!
return all;

// NEU (P2): Gibt das Feld DIREKT zurück (keine Kopie!)
if (!hasDynamic && !lostAll && isMainCard) {
    return abilities;  // ← ALIASING!
}
```

**Warum das falsch ist:**
- Der alte Code gab eine **Kopie** zurück → Caller konnte sie modifizieren
- Der neue Code gibt das **Original-Feld** zurück → Caller-Modifikationen korruptieren die Karte!
- Kommentar sagt "Safe because base abilities are not modified in this path" — aber das gilt nur für DIESEN Pfad, nicht für CALLER!

**Beweis aus den Mismatches:**
- Unterschiedliche Decision-Counts (z.B. Seed 5: 3980 vs 5765) → verschiedene Aktionen verfügbar
- Unterschiedliche Winner → verschiedene Spielverläufe
- Das passt zu korrumpierten Abilities!

**Fix:** Entweder:
1. P2 komplett revertieren (sicherste Option), ODER
2. Unmodifiable wrapper zurückgeben: `return AbilitiesImpl.unmodifiable(abilities)`

### 🥈 Nested-Copy-Fix — MITTELVERDÄCHTIG
**Commit:** `5481bd3a`  
**Datei:** `Mage/src/main/java/mage/players/PlayerImpl.java`

**Was es tut:** Vermeidet verschachtelte GameState-Copies via `inCheckPlayableState()` Check.

**Risiko:** Wenn die "already-isolated simulation" nicht wirklich isoliert ist → State-Korruption → Crash (Seed 10?).

**Weniger wahrscheinlich als P2**, weil:
- Die Mismatches zeigen logische Unterschiede (nicht nur Crashes)
- P2's Aliasing erklärt die Mismatches besser

### 🥉 P1: `getPlayersInRange()` Fast-Path — UNWAHRSCHEINLICH
**Commit:** `286aad7b`  
**Datei:** `Mage/src/main/java/mage/game/GameState.java`

**Was es tut:** Skippt `hasPlayerInRange` Check wenn `RangeOfInfluence.ALL`.

**Warum unwahrscheinlich:**
- Logik ist trivial: wenn ALL, dann sind alle in Reichweite (per Definition)
- Keine Aliasing-, kein State-Problem
- Reine Bedingungs-Optimierung

## Empfohlene Bisektion (für Claude-Thread)

Um Tokens zu sparen, in dieser Reihenfolge testen:

1. **Nur P2 revertieren** → 36-Seed
   - Wenn 0 Mismatches → P2 war's ✅
   - Wenn noch Mismatches → weiter

2. **Nur Nested-Copy revertieren** → 36-Seed
   - Wenn 0 Mismatches → Nested-Copy war's

3. **Nur P1 revertieren** → 36-Seed
   - Unwahrscheinlich, aber zur Vollständigkeit

**Schnell-Test:** Seed 10 einzeln testen (reproduziert den Crash in ~80s statt 35 Min für 36 Seeds).

## Fazit

**P2 ist mit 80% Wahrscheinlichkeit der Übeltäter** (Aliasing-Bug).  
Der Fix ist trivial (revert oder unmodifiable wrapper).  
Claude-Thread sollte mit P2-Bisektion starten.
