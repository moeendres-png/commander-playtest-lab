# Engine-Effizienz — Zwischenstand der Mess-Lane (2026-10-24)

`RESEARCH.md` in diesem Ordner ist der externe Forschungsbericht (XMage-
Interna, JVM-Tuning, Vergleichs-Engines, Protokoll — mit Quellen und
Evidenzklassen). Das eigene Dossier der Mess-Lane (Repo-Befund an unserer
Bridge + JFR-Profil + Flag-Messungen + priorisierter Plan) folgt als
Nachtrag in diesen Ordner.

## Schon gemessen (LOCAL_OBSERVED, Details im Pilot-Handoff §8)

- Zeit-Zerlegung einer Simulation (Pod, 3.588 Entscheidungen, Pin v11):
  Engine (Java-Bridge) ~96 %, Pilot ~1 % (0,43 ms/Entscheidung),
  JSON/Protokoll ~0,2 %, Start/JVM-Boot ~3 % (batch-amortisiert ~0).
- Repo-Befund: `fast_jvm_options` existiert (Serial GC, gemessen −10 % CPU
  bei identischen Transkripten; Gegenprobe der Mess-Lane: −9 %). AppCDS ist
  von T-3 gemessen (−1,4 % Wand bei 1 Spiel/JVM, unter der 3-%-Schwelle)
  und läuft in `--fast`-Sweeps mit, sofern `<jar>.jsa` liegt; die Läufe der
  Mess-Lane hatten keins. Details und Korrektur-Einordnung: DOSSIER.md.
- Falle für Profiling: JVM-Logausgaben auf stdout (z. B. JFR-Starttext)
  vergiften das JSONL-Protokoll (INVALID_RESPONSE) — Recorder per jcmd
  an den laufenden Prozess hängen statt `-XX:StartFlightRecording`.
- Qualitäts-Gate für jede Änderung: feste Seeds, semantischer Hash muss
  bit-identisch bleiben (Golden-Run).
