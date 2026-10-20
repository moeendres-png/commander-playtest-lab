# Fork-Patches: Lesehilfe und korrigierte Verdächtigen-Rangfolge (Muse, 2026-10-20)

**Basis:** Pin `348b37db5cf64f4ed503e8d37b776d5edc70e6d5`
**Head:** `10931648` (lokaler Branch `perf-avoid-nested-playable-copy`, 35 Commits)
**Gesamt:** 70 Dateien, 2119 Insertions, 162 Deletions

## Dateien

- `fork-patch-core.patch` — alle Engine-Core-Änderungen (Mage/src/main/java), 8,6 KB.
  **Das ist der semantisch relevante Teil — hier zuerst bisecten.**
- `fork-patch-cards-a-m.patch` — neue Karten A–M (Mage.Sets), 26,9 KB
- `fork-patch-cards-n-z.patch` — neue Karten N–Z (Mage.Sets), 47,8 KB
- `fork-patch-sets-review.patch` — Set-Registrierungen + PERF_OPTIMIZATION_REVIEW.md, 44,2 KB

Anwenden: `git apply` auf einen Checkout des Pins, oder als Referenz zum Lesen.

## Korrektur zur ursprünglichen Patch-Analyse (2026-10-19)

Die Analyse nannte P2 (CardImpl.getAbilities) als ~80%-Übeltäter. Mit dem echten Diff
in der Hand ist die Rangfolge differenzierter. Claudes Einwände sind teilweise korrekt
und hier eingearbeitet:

1. **PlayerImpl nested-copy avoidance (Commits 087bc55e, 5481bd3a) — Hauptverdächtiger.**
   `getManaAvailable()` und `getPlayable()` arbeiten jetzt auf dem übergebenen Game,
   wenn `inCheckPlayableState()` gesetzt ist, statt auf einer Simulations-Kopie.
   Die Kopie war laut Original-Kommentar ein "workaround to fix a triggers list
   modification bug (game must be immutable on playable calculations)". Fällt die
   Kopie weg, können Mutationen während der Playable-Kalkulation in den geteilten
   Simulations-State durchschlagen. Das erklärt breite Hash-Abweichungen (29/35)
   besser als jeder andere Hunk.

2. **CardImpl.getAbilities fast-path (P2, Commit 5dbff3a3) — realer Unterschied zum Pin,
   aber anderer Fix.** Claude hat recht: `MageObjectImpl.getAbilities()` gibt auch am Pin
   direkt zurück, und ein unmodifiable wrapper scheidet aus (176 mutierende Aufrufstellen).
   Aber: Die überschreibende Methode in CardImpl baute am Pin IMMER eine frische
   aggregierte Liste (`all`). Der Fast-Path gibt jetzt die interne `abilities`-Liste
   selbst zurück — Aufrufer-Mutationen verändern damit permanent die Karte statt einer
   Wegwerf-Aggregation. Korrekter Fix: Fast-Path entfernen oder defensive Kopie der
   Basis-Liste zurückgeben (nicht Wrapper).

3. **TriggeredAbilities.checkTriggers pre-check (Commit 407fd99a) — unverifizierte Annahme.**
   Der Kommentar behauptet, `checkEventType()` sei "pure (no state mutation)".
   Das wurde nie belegt (AGENTS.md: unverifizierte Engine-Annahme = Blocker).
   Zusätzlich überspringt der Pre-Check bei `!anyMatch` den gesamten restlichen
   try-Block, nicht nur die Kopie.

4. **GameState.getPlayersInRange fast-path (P1, Commit 286aad7b) — weniger verdächtig.**
   Bei RangeOfInfluence.ALL wird `hasPlayerInRange` übersprungen. Nur dann falsch,
   wenn hasPlayerInRange mehr prüft als die Range (z. B. Leave-/Effekt-Zustände).

5. **AbilitiesImpl.singleton (Commit 5481bd3a) — unverdächtig.**
   Ersetzt den Varargs-Konstruktor durch add() auf frischer Liste; semantisch gleich.

## Bisektions-Vorschlag

Reihenfolge 1 → 2 → 3 oben, Orakel: Seed 10 (Crash) + ein Mismatch-Seed (z. B. Seed 5).
Pro Schritt nur einen Hunk zurücknehmen, dann 36-Seed-Lauf gegen Baseline.
