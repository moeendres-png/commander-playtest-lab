# Übergabe an Claude — 2026-10-19

Dieser Ordner enthält das vollständige Übergabe-Paket von Muse (Python-/Verifikations-Agent)
an Claude (leitender Entwickler/Koordinator) für das Commander Playtest Lab.

## Lesereihenfolge

1. **Claude-Uebergabe-Komplett-2026-10-19.md** — Hauptübergabe: Projektstand, P0-Blocker,
   offene PRs, Source Lock, priorisierte nächste Schritte. ZUERST lesen.
2. **Patch-Analyse-2026-10-19.md** — Root Cause des P2-Semantik-Bugs (CardImpl.getAbilities Aliasing)
   inkl. Fix-Optionen und Bisektions-Anleitung.
3. **Patch-Semantik-Bug-2026-10-19.md** — Messdaten: 29/35 Seeds mit abweichenden Semantic Hashes.
4. **Problem-Analyse-Seed10-Mismatches.md** — Seed-10-Crash-Analyse.
5. **XMage-Upstream-Update-Analyse-2026-10-19.md** — 108 Upstream-Commits, 5 kritische Konflikte,
   verbindliche Reihenfolge für das Update.
6. **fehlende-karten-221.json** — Die 221 Karten, die im Mage-Fork noch fehlen
   (Ursache für Issue #920: alle 195 Precon-Decks crashen mit ENGINE_FAILURE).
7. **Claude-Review-Package-2026-10-19.md** — Review-Paket inkl. PRs #915–#918.
8. **Simplified-Cards-Documentation.md** — Die ~95 vereinfachten Karten (Status: SYNTHETIC).
9. **Verbesserungen-2026-10-19.md** — Umgesetzte Verbesserungen (Connector-Health-Check,
   CI-Fixes, Pilot-Kommentare).

## Messdaten

- **pilot_unwired.json / pilot_wired.json** — 12-Seed-Vergleich: 11/12 Seeds mit unterschiedlichem
  Spielverlauf → die Pilot-Verbesserungen wirken (kein toter Code).
- **precon_crash_results.json** — Precon-Sweep: 195/195 ENGINE_FAILURE (Test-Skript:
  `scripts/test_precon_crash.py` auf Branch `muse/precon-pilot-improvements`).

## Workstream-Handoffs (Architektur-Transfer)

- **WS1-Handoff-2026-10-19.md** — Performance-Hypothesen H1–H3 (gemessen)
- **WS2-Handoff-2026-10-19.md** — Twin-Determinismus, RNG, Hidden-Info (PASS)
- **K2-Handoff-2026-10-19.md** — K2-Befund

## Hinweis

- Source Lock und alle SHAs stehen in der Hauptübergabe — verifiziere den Live-Stand
  (PRs, CI) selbst auf GitHub, dieses Paket ist ein Snapshot vom 2026-10-19 abends.
- Die vollständige Kartenliste aller Precon-Decks (6350 Karten, 164 KB) liegt nicht hier
  (API-Limit) — sie lässt sich aus `data/decks/precons/*.json` auf Branch
  `muse/precon-pilot-improvements` regenerieren; die relevante Teilmenge ist
  fehlende-karten-221.json.
