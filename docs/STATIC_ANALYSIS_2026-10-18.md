# Statische Code-Analyse: Effizienz-Findings

**Datum:** 2026-10-18
**Methode:** Manuelle Code-Review der Hot Paths (kein laufendes Profiling möglich,
Bridge-JAR vom alten Pin startet nicht)

## Python Hot Paths

### Geprüft: `full_game_pilot/priority.py`

**`_decide_priority()`** wird bei jedem Priority-Fenster aufgerufen.

**Findings:**
1. **Fingerprint-Bildung (Zeilen 40-65):** Baut Tuple aus sortierten Listen bei
   jedem Aufruf. Notwendig für No-Progress-Guard. Kosten: O(n log n) für Sortierung
   von Stack + Optionen. Bei typisch <20 Optionen vernachlässigbar.

2. **Set-Lookups (Zeilen 209, 222):** `id(o) not in capped_ids` – `capped_ids` ist
   ein Set (korrekt), O(1) Lookup. ✅ Kein Problem.

3. **`_available_mana()` (payment.py:238):** Iteriert über alle Battlefield-Permanents
   bei jedem Aufruf. Wird in Zeile 214 von priority.py aufgerufen (bei failed payments).
   Kosten: O(battlefield_size), typisch <50. Vernachlässigbar.

**Fazit Python:** Keine signifikanten Ineffizienzen gefunden. Der Pilot ist 2,6%
der Wall-Time; selbst 50% Speedup hier wären <1,5% Gesamtspeedup.

### Geprüft: `bridge.py`

**`request()`** (Zeile 184): JSON-Serialisierung pro Bridge-Call.

**Findings:**
- UUID-Generierung pro Request (`uuid.uuid4()`): Vernachlässigbar.
- JSON-Dumps/Loads: Notwendig für Prozess-Isolation (D17).
- Lock pro Request (`with self._lock`): Notwendig für Thread-Safety.

**Fazit:** Keine Optimierung ohne Architekturänderung möglich. Die Isolation ist
eine bewusste Designentscheidung (Security).

## Java Hot Paths (aus Subagent-Audit)

Siehe `AUDIT_2026-10-18.md` für Details. Zusammenfassung:

| # | Datei | Problem | Risiko | Status |
|---|-------|---------|--------|--------|
| 1 | TriggeredAbilities:107 | ArrayList-Copy pro Event | Hoch (Concurrency) | Dokumentiert, nicht angefasst |
| 2 | CardImpl:253 | getAbilities realloc | Mittel | Dokumentiert für Review |
| 3 | Battlefield:258 | Stream-Collect pro Call | Mittel | Dokumentiert für Review |
| 4 | PlayerImpl:3603 | Varargs-Array | Niedrig | ✅ Implementiert (singleton) |
| 5 | GameState:766 | PlayerList-Rebuild | Niedrig | Dokumentiert (braucht Cache-Invalidierung) |
| 6 | AbilitiesImpl:151 | canActivate ohne Short-Circuit | Niedrig | Geprüft, bereits optimal |
| 7 | ContinuousEffects:764 | Nested Loops | Mittel | Dokumentiert für Review |

## Empfehlungen

### Umgesetzt
- ✅ Nested-Copy-Fix (eliminiert 1 von 2 GameState-Copies)
- ✅ AbilitiesImpl.singleton() (vermeidet Varargs-Alloc)

### Für Claude-Review dokumentiert
- CardImpl-Caching (braucht Version-Tracking)
- Battlefield-Caching (braucht Invalidierung bei Änderung)
- ContinuousEffects-Index (braucht Pre-Index-Struktur)
- TriggeredAbilities (Concurrency-Guard, nicht anfassen ohne Beweis)

### Nicht empfohlen
- Python-Mikrooptimierungen (kein Hebel: 2,6% Anteil)
- Bridge-Protokoll ändern (bricht Isolation)
- Copy-on-Write für GameState (hohes Risiko, unklarer Nutzen)
