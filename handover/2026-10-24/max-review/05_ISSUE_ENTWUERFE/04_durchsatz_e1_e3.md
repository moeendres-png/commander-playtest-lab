# Issue-Entwurf 04 — Durchsatz E1+E3: getPlayable-Kopien, Views cachen

Quelle: Max-Review R-10 (`03_VERBESSERUNGEN.md`), Engine-Dossier
`handover/2026-10-24/engine/` (E1, E3).
Status: Entwurf aus dem Max-Review 2026-10-24, nicht eingereicht.
**Lane-Vorbehalt:** Bridge-/Fork-Code → Claudes Lane; Muse misst.
Fork-Push, Repin und Seal brauchen Hans' Go. Bridge-Änderungen brauchen
Requalifizierung durch einen Claude-Thread (PB-03 → Seal).

## Objective

Die Wandzeit je Spiel um ≥5 % senken, ohne einen einzigen
Transkript-Hash zu verlieren — über die beiden größten Engine-Hebel
aus dem Dossier: E1 (getPlayable-Kopien) und E3 (Views cachen).
Pilot-Optimierung ist ausdrücklich nicht Teil dieses Issues
(Pilot-Anteil ~1 %, Engine ~96 %).

## Source lock

- Lab-main: `ee47312a7` (Stand Max-Review 2026-10-24)
- Engine-Pin: v13 `90f5c4d3f8`
- Dossier: `handover/2026-10-24/engine/` (Erwartung E1+E3: 15–30 %
  Wandzeit — Dossier-Schätzung, keine Messung)
- Referenzlauf: 24 Spiele ≈ 126 s Wandzeit (Phase-2-Messung)

## Read first

- Engine-Dossier (E1, E3, E4-Blockade durch O5): Was genau kopiert
  wird, wo Views entstehen, warum E4 (Transkriptformat) blockiert ist.
- `04_RECHERCHE.md` D5: Warum HashSet-Ordnung keine
  Performance-Ausrede ist (Reihenfolge ist unspezifiziert — Caching
  darf keine Ordnung einführen, die es vorher nicht gab).
- REPIN_RUNBOOK-Regel (aus Pass A/B): CPU vor Wall, ABBA interleaved.

## Items

1. **Profiling (kein Verhalten):** Wo entstehen getPlayable-Kopien und
   Views je Entscheidung? Zahlen je 24-Spiel-Lauf (Aufrufe, Bytes,
   Anteil an Wall). Ohne Profiling keine E1/E3-Aussage.
2. **E1 + E3 implementieren:** Kopien vermeiden, wo die Engine es
   zulässt; Views cachen, wo die Cache-Korrektheit bewiesen ist
   (Invalidierung bei jeder Zustandsänderung — sonst falsche
   Entscheidungen, kein Durchsatz-Claim).
3. **Twin-Hash-Gate:** 36/36 identische semantische Hashes
   (36-Seed-Referenz, #1005) mit/ohne Änderung. Jede Abweichung =
   kein Durchsatz, sondern Verhaltensänderung → Stopp.
4. **ABBA-Messung:** Interleaved-Läufe (A-B-B-A), CPU-Zeit vor
   Wandzeit, ≥5 % Wandzeit als Akzeptanz, unter 3 % = verworfen
   (T-1/AppCDS-Schwelle aus Pass B).

## Acceptance (mit Falsche-Grund-Kontrolle)

- **Akzeptanz:** ≥5 % Wandzeit bei 36/36 identischen Hashes.
- **Falsche-Grund-Kontrolle:** Ein Lauf mit Profiling an, aber
  Änderung aus, muss die Ausgangs-Wandzeit reproduzieren — sonst misst
  das Profiling (Overhead), nicht die Änderung. Kein paralleler
  Pilot-Change während der Messung (sonst Hash-Vergleich ungültig).
- **Cache-Korrektheit:** Ein Test, der bei falscher Invalidierung
  fehlschlägt (Zustand ändert sich, View muss sich ändern) — ohne
  diesen Test kein Cache-Claim.
- Bei Bridge-Änderung: Requalifizierung durch Claude-Thread;
  bei Fork-Änderung: Hans' Go für Push + Repin + Seal. Ohne Go:
  Analyse-only, kein Push.

## Test command

```
# Twin-Hash + ABBA (ab Worktree mit gebautem .runtime, sequenziell):
PYTHONPATH=<worktree>/src python3 <twin_abba.py> --seeds 1..36 --jar <neu> --jar <alt>
# Bridge-/Engine-Tests der geänderten Stellen:
<entsprechender Maven-/Pytest-Befehl je Lane, im PR zu nennen>
```

## Stop condition

Stop bei ≥5 % mit 36/36 Hashes, oder bei Verwerfen unter 3 %,
oder bei Hash-Abweichung (dann: Verhaltens-Issue statt Durchsatz-Issue).
E4 gehört nicht hierher (blockiert durch O5).

## Rules footer

XMage ist die einzige Rules Engine. Durchsatz ändert keine Regeln:
Gleiche Hashes sind die Bedingung, nicht das Ziel. Keine
Sammlungsdaten lesen oder zitieren. Neuer Code ohne `Any`
(`object` nehmen). Engine-`bridge/**`-Änderungen durch Muse sind
ausgeschlossen (nur Befund).
