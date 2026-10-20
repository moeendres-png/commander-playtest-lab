# Claude Review Package — Commander Simulator Next
**Date:** 2026-10-19 19:10 CEST  
**From:** Muse  
**To:** Claude (review)  
**Purpose:** Complete fixes/improvements/update package for review before merging

## Executive Summary

All local work is now on GitHub. 5 PRs open (#914-918). One CI failure fixed (K5). 
This package contains all fixes, improvements, and status for your review.

## 1. Fixes Applied

### K5 (PR #917): CI Quality Gate Failure — FIXED ✅
**Problem:** `ruff check` failed on `src/commander_lab/verification/scenario_harness.py`
- Unused import: `from pathlib import Path` (line 16)
- Import sorting issue in test file
- Formatting issue

**Fix:** Removed unused import, fixed sorting, ran `ruff format`
**Commit:** `59f9f0452a73c965ab04644f452cac3549cbf661` on `muse/k5-scenario-harness`
**Verification:** `ruff check` passes, `mypy` passes, 6 tests pass

### Precon Branch: Unwanted File Changes — REVERTED ✅
**Problem:** Local commits included unwanted changes to:
- `config/rules_engines.json` (222 lines, just key reordering)
- `scripts/import_deck.py` (mode change, 0 content changes)

**Fix:** Reverted these files, pushed only the 3 intended files:
- `src/commander_lab/engine/rules/full_game_pilot/state.py` (Any→object)
- `src/commander_lab/engine/rules/full_game_pilot_views.py` (pilot wiring + comments)
- `tests/unit/test_pilot_wiring.py` (new tests)

**Branch:** `muse/precon-pilot-improvements` (now on GitHub)

## 2. PR Status (All 5)

| PR | Title | Head | CI Status | Merge Ready? |
|----|-------|------|-----------|--------------|
| #914 | Precon pilot improvements | e1512f19 (updated) | pending/0 | NO (Draft, needs pilot comparison) |
| #915 | K3: PrincipalView | 8878dab1 | pending/0 | NO (CI not run) |
| #916 | K4: Mana conformance | b60cf625 | pending/0 | NO (CI not run) |
| #917 | K5: Scenario harness | 59f9f045 (fixed) | pending/0* | NO (CI not run yet) |
| #918 | K6: Event tap | 57e7cb34 | pending/0 | NO (CI not run) |

*K5 was failing, now fixed. CI needs to re-run.

**Note:** All PRs show "pending/0" — CI hasn't reported. This is unusual for #914 (2 hours old). 
May need manual workflow trigger or investigation.

## 3. Improvements Implemented

### Code Reviewability (per Hans's request)
**File:** `src/commander_lab/engine/rules/full_game_pilot_views.py`

**Synergy wiring** (lines ~720-735):
- Explained scaling (0.3 factor), cap (2.0), example (+0.09)
- Documented design rationale (Hans spec 2026-10-18)
- Explained why synergy is a tiebreaker, not dominant

**BREAD wiring** (lines ~736-745):
- Documented all weights (Bombs 1.5 … Duds 0.8)
- Explained formula: `(weight-1.0)*0.3`
- Justified `max()` for multi-role cards

**Desperation wiring** (lines ~1128-1145):
- Listed all 3 conditions (life≤10, tempo<-0.3, threat≥20)
- Cited Hans: "Tempo-Effekt generell schwächer, nur in echten Desperation-Situationen stark"
- Explained actor_id pattern and defensive check

**Review Guide:** `~/workspace/your_files/Code-Review-Guide-for-Agents.md`
- What was done, design decisions, code locations
- Verification commands, negative controls
- Improvement suggestions for each area

## 4. Improvements Identified (Not Yet Implemented)

### From Source-Lock & Ownership Inventur
1. **PR Queue:** 5 open PRs → merge #915-918 after CI green (reduces to 1)
2. **Precon Issue:** Create P1 issue for ENGINE_FAILURE (blocks precon validation)
3. **Connector Check:** Add to pre-push ritual (verify via API before push)
4. **CPU Scheduling:** Run 36-seed at night, not parallel to other work
5. **Merge Cadence:** Merge small PRs immediately, don't batch
6. **Precon Smoke Test:** Add 1-2 precon decks to CI (catches ENGINE_FAILURE early)
7. **Branch Hygiene:** Delete feature branches after merge

### From H1-H3 Measurements
1. **H1 (/tmp):** Automate cleanup — pytest fills 512MB tmpfs → Maven fails
   - Set `TMPDIR=~/workspace/tmp` in CI or add cleanup hook
2. **H1 (CPU):** Don't run Maven + pytest in parallel on 2 CPUs
   - Schedule sequentially
3. **H3 (68s/test):** JVM startup is 33s of 68s
   - Reuse JVM via Surefire fork reuse (~50% savings)
   - Start K5 corpus with 5-10 cards, not 20-50
   - Shard tests across runners

## 5. Current Blockers

1. **36-seed running** (~30 min left) — blocks JAR B comparison and pilot comparison
2. **CI not reporting** on PRs #914-918 — needs investigation
3. **Precon ENGINE_FAILURE** — needs P1 issue and root cause analysis

## 6. Files Changed (This Session)

### Pushed to GitHub
- `muse/k5-scenario-harness`: 59f9f045 (ruff fixes)
- `muse/precon-pilot-improvements`: 3 files (pilot wiring, Any fix, comments)

### Local Only (Documentation)
- `~/workspace/your_files/Source-Lock-Ownership-Inventur-2026-10-19.md`
- `~/workspace/your_files/Phase-A-Project-Audit-Report.md`
- `~/workspace/your_files/Code-Review-Guide-for-Agents.md`
- This file

## 7. What Needs Your Review

1. **K5 fix:** Verify ruff/mypy/tests pass in CI (after re-run)
2. **Pilot wiring:** Review the implementation and comments
   - Are the 0.3 multipliers reasonable?
   - Is desperation logic correct?
   - Should tempo affect other decisions?
3. **PR #914:** Still Draft — needs ≥10-seed pilot comparison (blocked on 36-seed)
4. **CI issue:** Why are checks not reporting? (especially #914, 2 hours old)
5. **Improvements list:** Which should be prioritized?

## 8. Next Actions (After Your Review)

1. Wait for 36-seed completion
2. Run JAR B comparison
3. Run pilot ≥10-seed comparison
4. Update PR #914 (remove Draft)
5. Merge #915-918 (after CI green + your review)
6. Create precon ENGINE_FAILURE issue
7. Implement prioritized improvements

---
**All code is on GitHub. Nothing is local-only (except documentation).  
Ready for your review.**

## 10. Update 2026-10-19 22:40 — /oc-zai Lane + Patch-Bug bestätigt

### /oc-zai Lane (NEU)
**Status:** Workflow erstellt, wartet auf Push-Freigabe (Hans)

Zwei neue Lanes mit Z.ai GLM-4.7-Flash (kostenlos, $0 in/out):
- `/oc-zai` — Implementation-Lane (foundry-implementer, writable)
- `/oc-zai-review` — Read-only Review-Lane (foundry-reviewer)

**Dateien:**
- `commander-playtest-lab/.github/workflows/opencode-zai.yml` (bereit, Branch `muse/oc-zai-lane`)
- `mage/.github/workflows/opencode-zai.yml` (bereit, noch nicht gepusht)

**Config:** Z.ai Provider via `OPENCODE_CONFIG_CONTENT` (OpenAI-kompatibel, `https://api.z.ai/api/paas/v4`), Key aus `ZAI_API_KEY` Secret (von Hans in beiden Repos angelegt). VARIANT: max. Gleiches Hardening wie opencode.yml (pinned CLI v1.18.30, SHA256, Preflight, Quota-Watchdog, Rescue).

**Verifiziert:**
- YAML/JSON valide
- Z.ai Endpoint erreichbar (401 bei invalidem Key = korrekt)

**Zweck (Owner):** Nur für unabhängige Reviews und mechanische Tasks, die Muse nicht ausführen kann. KEINE Architektur-Entscheidungen (GLM-4.7-Flash ist ein schnelles Modell, kein Reasoner).

### Patch-Semantik-Bug: BESTÄTIGT, schlimmer als gedacht
**Neuer Befund:** Frischer 36-Seed-Lauf (JAR A vs JAR B):
- JAR A: 35/36 OK (Seed 10 FAILED, reproduzierbar)
- JAR B: 36/36 OK
- **29/35 vergleichbare Seeds haben unterschiedliche Semantic Hashes** (83%!)

**Analyse:** `Patch-Analyse-2026-10-19.md` — **P2 (`CardImpl.getAbilities()` Fast-Path) ist der Übeltäter** (Aliasing-Bug: gibt `abilities`-Feld direkt zurück statt Kopie → Caller korruptieren Karten-State).

**Für dich (Claude-Thread):**
1. P2 revertieren (oder unmodifiable wrapper)
2. 36-Seed erneut → 0 Mismatches erforderlich
3. Dann Fork-Push (Skript: `~/workspace/tools/fork-push.sh`, braucht Hans-Go)
4. Requalifizierung (PB-03)

### Offene PRs — Status
| PR | Inhalt | Status |
|----|--------|--------|
| #914 | Precon pilot improvements | Draft, wartet auf Pilot-Vergleich |
| #915 | K3 PrincipalView | Offen |
| #916 | K4 Mana-Konformanz | Offen |
| #917 | K5 Scenario-Harness | CI-Fix gepusht (59f9f045), Re-Run ausstehend |
| #918 | K6 Event-Tap | Offen |
| NEU | /oc-zai Lane | Branch bereit, Push wartet auf Freigabe |

### Noch zu tun (vor Claude-Übergabe)
1. ✅ /oc-zai PRs erstellt: CPL #919 + mage #62 (Hans, 2026-10-19 23:14)
2. ✅ Precon-Issue erstellt: #920 (Hans, 2026-10-19 23:14)
3. ⏳ Pilot-Vergleich (12 Seeds wired vs unwired) — UNWIRED fertig (12/12), WIRED läuft
4. ⏳ Precon-Sweep (195 Decks) — Issue #920 als Tracking
5. ⏳ Improvements-PR reparieren (`muse/improvements-tmp-jvm-smoke`)
6. ⏳ PRs #915-918 — Claude-Review vor Merge (Hans-Anweisung 2026-10-19 22:44)

## 11. XMage Upstream-Update (Hans-Anweisung 2026-10-19 23:08)

**Status:** Analyse fertig, wartet auf P2-Fix

**Befund:** 108 Commits hinter upstream/master (bb0ed0f7). Details in `XMage-Upstream-Update-Analyse-2026-10-19.md`.

**Kritisch:** 5 upstream-Commits ändern exakt die Dateien unserer Fork-Patches (GameImpl, GameState, CardImpl, PlayerImpl, AbilitiesImpl) → **Konflikte garantiert**.

**Reihenfolge (verbindlich):**
1. P2-Bug fixen (sonst ist der Fork instabil)
2. 36-Seed mit 0 Mismatches
3. Upstream-Update als eigenes Projekt (Branch `update-upstream-2026-10`)
4. Requalifizierung (PB-03)
5. Repin

**Aufwand:** ~1 Arbeitstag (Claude-Thread für Java-Merges)

**NICHT ohne Hans-Go mergen** — Repin braucht Owner-Freigabe.

## 9. Verbesserungen (alle 10 Punkte)

Siehe: `Verbesserungen-2026-10-19.md` für Details.

**Implementiert (3):**
1. Connector-Health-Check in AGENTS.md
2. K5 CI-Fix (59f9f045)
3. Code-Kommentare für Reviewbarkeit

**Vorgeschlagen (7):**
4. Precon ENGINE_FAILURE Issue (P1) — braucht Hans (manuell, MCP kann kein Issue erstellen)
5. /tmp-Cleanup in CI — braucht dein Review (Workflow-Änderung)
6. CPU-Scheduling — Dokumentation, kein Code
7. JVM-Reuse (Surefire) — braucht dein Review + Requal (engine-bridge)
8. Precon Smoke Test in CI — braucht dein Review (Workflow-Änderung)
9. Merge-Kadenz — Prozess, nach CI-grün
10. Branch-Hygiene — nach Merges
