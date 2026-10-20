# Claude-Übergabe: Commander Playtest Lab — Vollständiger Stand 2026-10-19

## Executive Summary

**Projekt:** Commander Playtest Lab mit XMage-Fork als Rules Engine  
**Ziel:** Praktischer Commander-Simulator für Deckbuilding-Entscheidungen  
**Status:** Kernfunktionalität läuft, aber **zwei kritische Blocker** verhindern Precon-Support und Fork-Stabilität

### Kritische Blocker (P0)

1. **P2 Patch-Semantik-Bug** — Fork-Patches verändern Spielsemantik (29/35 Seeds mit unterschiedlichen Hashes)
   - Root Cause: `CardImpl.getAbilities()` gibt `abilities`-Feld direkt zurück (Aliasing-Bug)
   - Fix: Revert oder unmodifiable wrapper
   - Blockiert: Fork-Push, Requalifizierung, Upstream-Update

2. **Precon-Decks: 221 fehlende Karten** — 195/195 Decks mit ENGINE_FAILURE
   - 316 Karten fehlen im Baseline-Fork
   - Nur 95 wurden als "vereinfacht" implementiert
   - **221 fehlen immer noch** → alle Decks crashen bei Validierung
   - Liste: `/tmp/still_missing_fork.json`

---

## Was wurde erreicht (2026-10-19)

### ✅ Pilot-Vergleich (UNWIRED vs WIRED)
- **12 Seeds** mit Baseline-JAR (348b37db)
- **Ergebnis: 11/12 Seeds mit unterschiedlichem Spielverlauf**
- Die Pilot-Verbesserungen (tempo/desperation/synergy/bread) WIRKEN
- Kein toter Code — Wiring greift in 92% der Spiele
- Files: `~/workspace/tmp/pilot_unwired.json`, `~/workspace/tmp/pilot_wired.json`

### ✅ Precon-Sweep (195 Decks)
- **Ergebnis: 195/195 ENGINE_FAILURE**
- Alle Decks scheitern SOFORT (wall_s=0.0) bei Java-Bridge-Validierung
- Root Cause identifiziert: 221 fehlende Karten im Fork
- Test-Skript: `scripts/test_precon_crash.py` (funktionsfähig)

### ✅ CI-Fixes gepusht
- **PR #914** (Precon Pilot): Ruff SIM118 Fix → Commit `1034151ab6e7` gepusht
- **PR #917** (K5 Scenario Harness): Any-Ratchet Fix (2190→2189) → Commit `07eb0f5008ba` gepusht
- Beide PRs sollten jetzt grün werden

### ✅ /oc-zai Lane implementiert
- **CPL PR #919**: Workflow für Z.ai GLM-4.7-Flash (kostenlos)
- **Mage PR #62**: Gleicher Workflow für Mage-Repo
- 2 Lanes: `/oc-zai` (writable) + `/oc-zai-review` (read-only)
- Secrets `ZAI_API_KEY` in beiden Repos angelegt
- Noch nicht getestet (warten auf Merge)

### ✅ Analysen erstellt
- **Patch-Analyse**: P2 als Übeltäter identifiziert (29/35 Mismatches, 83%)
- **XMage Upstream**: 108 Commits analysiert, 5 kritische Konflikte dokumentiert
- **Fehlende Karten**: 316 → 95 vereinfacht → 221 fehlen noch

---

## Offene PRs

| PR | Titel | Status | Blocker |
|----|-------|--------|---------|
| #914 | Precon Pilot Improvements | CI läuft neu | Warten auf grün, dann aus Draft |
| #915 | K3 PrincipalView + Leak-Test | Offen | Claude-Review vor Merge |
| #916 | K4 Mana-Konformanz | Offen | Claude-Review vor Merge |
| #917 | K5 Scenario-Harness | CI läuft neu | Warten auf grün |
| #918 | K6 Event-Tap-Test | Offen | Claude-Review vor Merge |
| #919 | /oc-zai Lane (CPL) | Offen | Testen nach Merge |
| mage #62 | /oc-zai Lane (mage) | Offen | Mergen |

---

## Issues

### #920 [P1] Precon decks crash with ENGINE_FAILURE
- **Status:** Offen, Root Cause identifiziert
- **Ursache:** 221 fehlende Karten im Fork
- **Lösung:** Entweder 221 Karten implementieren ODER Decks filtern
- **Dateien:** `/tmp/still_missing_fork.json` (221 Karten), `/tmp/precon_all_cards.json` (6350 Karten)

---

## Technische Details

### Source Lock (verbindlich)
- **CPL `origin/main`**: `f994bd1aa38e94ed6df6583ef7340c196d45b1d0` (K1-Merge PR #913)
- **Mage `master`**: `10a739229aa470a42720a5f57082ac61f1486fc6`
- **Pin**: `348b37db5cf64f4ed503e8d37b776d5edc70e6d5` (alleinige Autorität: `config/rules_engines.json`)

### JARs
- **Baseline** (stabil): `~/workspace/tmp/xmage-engine-bridge-base-348b37db.jar` (75M)
  - 36/36 Seeds OK, keine Mismatches
- **Fork** (mit Patches + vereinfachte Karten): `engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar` (76M)
  - 35/36 OK, Seed 10 FAILED
  - 29/35 semantische Mismatches (P2-Bug)

### P2-Bug Details
- **Datei:** `mage/Mage/src/main/java/mage/cards/CardImpl.java`
- **Methode:** `getAbilities()`
- **Problem:** Gibt `abilities`-Feld direkt zurück statt Kopie
- **Effekt:** Caller-Modifikationen korruptieren Karten-State
- **Fix-Optionen:**
  1. Revert des P2-Commits (`5dbff3a3`)
  2. Unmodifiable wrapper: `return AbilitiesImpl.unmodifiable(...)`
- **Bisektion:** Seed 10 einzeln testen (~80s) zur Bestätigung

### Fehlende Karten (221)
Kategorien (Stichprobe):
- **Universes Beyond**: Ant-Man, Captain Mar-Vell, Cloud Ex-SOLDIER, April O'Neil
- **Commander-Spezifisch**: Akiri Line-Slinger, Anafenza Kin-Tree Spirit, Athreos Shroud-Veiled
- **Neue Mechaniken**: C.A.M.P., Big Apple 3 a.m., Bottle-Cap Blast

Vollständige Liste: `/tmp/still_missing_fork.json`

---

## Nächste Schritte (priorisiert)

### Sofort (P0)
1. **P2-Fix** im Fork (Java)
   - `CardImpl.getAbilities()` fixen
   - 36-Seed-Verifikation: 0 Mismatches erforderlich
   - Dann Fork-Push (braucht Owner-Go)

2. **221 fehlende Karten** — Entscheidung erforderlich:
   - **Option A:** Alle 221 implementieren (großer Aufwand, ~1-2 Wochen)
   - **Option B:** Decks filtern auf verfügbare Karten (schnell, aber unvollständig)
   - **Option C:** Nur die häufigsten fehlenden Karten implementieren (Pareto)

### Danach (P1)
3. **Requalifizierung** (PB-03) nach P2-Fix
4. **XMage Upstream-Update** (108 Commits, 5 kritische Konflikte)
   - Reihenfolge: P2-Fix → 36-Seed 0 Mismatches → Update → Requal → Repin
5. **Precon-Sweep wiederholen** mit vollständigem Fork

### Parallel
6. **PRs #915-918** reviewen und mergen
7. **/oc-zai testen** nach Merge von #919
8. **PR #914** aus Draft holen nach CI-grün

---

## Dateien & Artefakte

### Analysen
- `~/workspace/your_files/Patch-Analyse-2026-10-19.md` — P2-Bug Root Cause
- `~/workspace/your_files/Patch-Semantik-Bug-2026-10-19.md` — 29/35 Mismatches
- `~/workspace/your_files/XMage-Upstream-Update-Analyse-2026-10-19.md` — 108 Commits
- `~/workspace/your_files/Problem-Analyse-Seed10-Mismatches.md` — Seed 10 Crash

### Test-Ergebnisse
- `~/workspace/tmp/pilot_unwired.json` — 12 Seeds, vor Wiring
- `~/workspace/tmp/pilot_wired.json` — 12 Seeds, nach Wiring
- `~/workspace/tmp/precon_crash_results.json` — 195/195 ENGINE_FAILURE
- `/tmp/precon_all_cards.json` — 6350 unique Karten
- `/tmp/still_missing_fork.json` — 221 fehlende Karten
- `/tmp/missing_cards.json` — 316 fehlende (Baseline)

### Code
- `scripts/test_precon_crash.py` — Precon-Test-Skript (funktionsfähig)
- `scripts/benchmark_xmage_full_games.py` — Benchmark-Skript

### Workflows
- `.github/workflows/opencode-zai.yml` — /oc-zai Lane (in PRs #919, mage #62)

---

## Regeln & Constraints

### Rules-Autorität
XMage ist die einzige Rules Engine. Keine zweite/versteckte Rules Engine in Pilot/Provider/Adapter/Orchestrierung.

### Evidenz-Standard
- `DIRECTLY_VERIFIED` / `CODE_DERIVED` / `TECHNICALLY_CONFORMANT` / `EXTERNALLY_RULE_VALIDATED` / `MODELED` / `SYNTHETIC` / `UNKNOWN`
- `UNKNOWN` ist niemals PASS
- Die 95 vereinfachten Karten sind **SYNTHETIC**

### Merge-Policy
- Eigene PRs dürfen nach Dirigent-Review selbst gemergt werden (CI grün, kein Konflikt)
- Fork-Pushes, Repins, signierte Qualification-Records brauchen Owner-Go
- Pilot-Änderungen brauchen ≥10-Seed Real-Game-Vergleich vor Merge

### Java-Scope
- Java nur wenn Issue es zuweist
- `engine-bridge/**` Änderungen brauchen Requalifizierung durch Claude-Thread
- Nie selbst-started

---

## Kontakt & Referenzen

- **GitHub:** moeendres-png
- **Repos:** commander-playtest-lab, mage (beide public)
- **Issues:** #920 (Precon P1)
- **PRs:** #914-#919, mage #62

---

**Erstellt:** 2026-10-19 23:35 CEST  
**Von:** Muse (Python/Verifikation) für Claude (Java/Builds)
