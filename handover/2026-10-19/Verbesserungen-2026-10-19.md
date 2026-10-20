# Implementierte und identifizierte Verbesserungen
**Date:** 2026-10-19 19:25 CEST  
**Status:** Vor Claude-Review

## ✅ Implementiert

### 1. Connector-Health-Check (AGENTS.md)
**Was:** Schritt 10 im Pre-Push-Ritual hinzugefügt
**Wo:** `~/AGENTS.md`, Zeile ~93
**Text:** "Vor jedem API-Push einen Read-Call testen. Wenn 404/timeout: Push verschieben."
**Grund:** Connector war 2026-10-19 13:00-16:30 in 404-Phase. Blinde Pushes schlagen fehl.

### 2. K5 CI-Fix
**Was:** Unused import entfernt, Format gefixt
**Wo:** `muse/k5-scenario-harness` branch, Commit 59f9f045
**Verifikation:** ruff ✅, mypy ✅, 6 Tests ✅

### 3. Code-Kommentare (Reviewbarkeit)
**Was:** Erklärende Kommentare für Synergy/BREAD/Desperation
**Wo:** `full_game_pilot_views.py` (3 Stellen)
**Grund:** Hans: "andere agents sollen code verstehen und reviewen können"

## 📋 Identifiziert (brauchen Umsetzung/Review)

### 4. Precon ENGINE_FAILURE Issue (P1)
**Problem:** Precon-Decks crashen mit ENGINE_FAILURE trotz erfolgreichem Import (195/195)
**Status:** Dokumentiert in WS2-Handoff, aber kein GitHub-Issue erstellt
**Blocker:** MCP bietet `create_issue` nicht an
**Nächster Schritt:** Hans erstellt Issue manuell, oder via Web-UI
**Priorität:** P1 (blockiert Precon-Validierung)

### 5. /tmp-Cleanup in CI
**Problem:** pytest füllt /tmp (512MB tmpfs) → Maven-Downloads schlagen fehl mit "No space left"
**Evidenz:** H1-Messung 2026-10-19 (165 Failures durch /tmp voll)
**Lösung:** In `.github/workflows/ci.yml` hinzufügen:
```yaml
env:
  TMPDIR: ${{ runner.temp }}/pytest-tmp
```
Oder Cleanup-Step vor Maven:
```yaml
- name: Clean /tmp
  run: rm -rf /tmp/pytest-of-root/*
```
**Risiko:** Niedrig (nur Temp-Dateien)
**Braucht:** Claude-Review (Workflow-Änderung)

### 6. CPU-Scheduling (keine parallelen Heavy-Jobs)
**Problem:** Maven + pytest parallel auf 2 CPUs → beide langsam + flaky (H1)
**Lösung:** In CI-Workflow `concurrency` bereits vorhanden, aber lokal:
- Dokumentieren in `~/workspace/tools/README.md`: "Keine parallelen Maven+pytest"
- Oder Wrapper-Skript mit Lock-File
**Risiko:** Keins (nur Dokumentation/Prozess)

### 7. JVM-Reuse für Surefire (50% Zeitersparnis)
**Problem:** Jeder Mage-Test startet neue JVM (33s von 68s)
**Evidenz:** H3-Messung (101s wall, 67.8s test)
**Lösung:** In `engine-bridge/pom.xml` hinzufügen:
```xml
<configuration>
    <forkCount>1</forkCount>
    <reuseForks>true</reuseForks>
    ...
</configuration>
```
**Ersparnis:** ~33s pro Test → bei 50 Tests ~27 Min gespart
**Risiko:** Mittel (Test-Isolation! Tests müssen fork-safe sein)
**Braucht:** Claude-Review + Requalifizierung (engine-bridge Änderung)

### 8. Precon Smoke Test in CI
**Problem:** ENGINE_FAILURE wird erst bei manuellen Runs entdeckt
**Lösung:** Neuer Workflow-Job mit 2 Precon-Decks (schnell, <5 Min):
```yaml
- name: Precon smoke
  run: python scripts/benchmark_xmage_full_games.py run --jar ... --seeds 1 --decks data/decks/precons/2024_blame_game.json
```
**Risiko:** Niedrig (nur Test, kein Prod-Code)
**Braucht:** Claude-Review (Workflow-Änderung)

### 9. Merge-Kadenz (Prozess)
**Problem:** 5 PRs offen → Stau, Review-Overhead
**Lösung:** Kleine PRs (K3-K6) sofort nach CI-grün mergen, nicht sammeln
**Status:** Wartet auf CI (alle pending) + Claude-Review

### 10. Branch-Hygiene (Prozess)
**Problem:** Alte Branches bleiben liegen (z.B. K2-Branch wurde manuell gelöscht)
**Lösung:** Nach Merge: Branch löschen (GitHub UI oder API)
**Status:** Wartet auf Merges

## Zusammenfassung

| # | Verbesserung | Status | Risiko | Owner |
|---|--------------|--------|--------|-------|
| 1 | Connector-Check | ✅ Implementiert | Keins | Muse |
| 2 | K5 CI-Fix | ✅ Implementiert | Keins | Muse |
| 3 | Code-Kommentare | ✅ Implementiert | Keins | Muse |
| 4 | Precon Issue | 📋 Dokumentiert | Keins | Hans (manuell) |
| 5 | /tmp-Cleanup | 📋 Vorgeschlagen | Niedrig | Claude (Review) |
| 6 | CPU-Scheduling | 📋 Dokumentiert | Keins | Alle |
| 7 | JVM-Reuse | 📋 Vorgeschlagen | Mittel | Claude (Review+Requal) |
| 8 | Precon Smoke | 📋 Vorgeschlagen | Niedrig | Claude (Review) |
| 9 | Merge-Kadenz | 📋 Prozess | Keins | Hans |
| 10 | Branch-Hygiene | 📋 Prozess | Keins | Nach Merges |

**3 implementiert, 7 dokumentiert/vorgeschlagen.**
**Alle sind im Claude-Review-Paket enthalten.**
