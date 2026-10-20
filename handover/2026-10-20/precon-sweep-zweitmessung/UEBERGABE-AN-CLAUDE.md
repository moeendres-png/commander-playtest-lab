# Übergabe M1 an Claude (von Muse, 2026-10-20, auf Hans' Anweisung)

Hans hat M1 (Precon-Pod-Sweep-Zweitmessung) bei Muse gestoppt und an Claude
übergeben. Stand und offene Reste stehen hier; alle Messdateien liegen in
diesem Ordner (`handover/2026-10-20/precon-sweep-zweitmessung/`).

## Erledigt und verifiziert (Schritte 0–2)

- **Setup:** Mage am Pin `043579bb` gebaut (BUILD SUCCESS), Bridge-`verify`
  1120/1124 — die 4 Fehler sind alle `XmageFullGameReplayExportTest`
  (`XMAGE_CARD_REPOSITORY_INIT_FAILED` in frischer JVM, auch isoliert;
  Surefire-Report: `surefire_replay_export.xml` im Ordner). Mess-JAR ohne
  Tests gebaut, sha256 `3dd27204…` (`jar_sha256.txt`, `versions.txt`).
- **Kalibrierung BESTANDEN:** Import 182/195 OK, 13 Decks an 31 Namen /
  33 Einträgen, Deck für Deck identisch zu `docs/PRECON_VALIDATION.md`
  (`imports.json` im Ordner).
- **Reproduktion p1g1 EXAKT:** 46 Pods, **37 ok / 9 failed**, alle
  `XMAGE_ACTION_EXECUTION_FAILED`, Fehlpod-Menge identisch zur Erstmessung
  (005, 008, 011, 027, 028, 035, 037, 040, 042), Abdeckung 146 / 36
  ebenfalls identisch. Alle 37 Semantic-Hashes in `sweep_p1g1.json`.
  Details + ok-/Failed-Tabellen im `BERICHT.md` (Zwischenbericht,
  Commit `cd63051b` auf `muse/claude-handover`).

## Offen (Schritte 3–6)

1. **Sweep p2g1 ist TEILSTAND:** `sweep_p2g1.json` in diesem Ordner enthält
  **31/46 Pods (26 ok / 5 failed)**, dann gestoppt. Failed: pod-003, -005,
  -015, -018 (alle `XMAGE_ACTION_EXECUTION_FAILED`) und **pod-020**
  (Ausreißer: `FullGameProtocolError`, nur `[ENGINE_FAILURE]`, wall_s
  150,9 — dafür ist nach der Sweep-Regel ein Solo-Replay fällig, beide
  Ergebnisse in den Fehlerkatalog). Zum Fertigfahren: Die Datei wird vom
  Skript inkrementell geschrieben; ein Neustart spielt alle 46 Pods neu
  (~45–75 Min bei workers 1 auf 2 Kernen). Ein Fortsetzungs-Treiber, der
  nur die Rest-Pods mit der Sweep-Maschinerie spielt und zusammenführt,
  liegt als `replay/continue_sweep.py` bei (für p1g1 nach einem
  Runtime-Restart so verwendet; Plan-Index anpassen).
2. **Sweep p3g1** (`--plan-seed 3 --game-seed 1`) komplett offen,
  optional p1g2 (`--plan-seed 1 --game-seed 2`).
3. **Schritt 4 Fehlerkatalog:** je failed Pod aus allen Läufen: Lauf,
  Pod-ID, 4 Decks, Fehlercode + Diagnostics-Schlüssel, wall_s,
  Entscheidungen-soweit-vorhanden; bekannt (Ursachen aus
  `docs/PRECON_VALIDATION.md`: Osgir 005, Grim Hireling 008+035,
  Collective Effort 011, Ruthless Radrat 027, Skeletal Scrying 028,
  Peerless Recycling 037, Imposter Mech 040, Marath 042) vs. neu markieren;
  neue Fälle per Wegwerf-Replay (bench._setup/bench._play) auf die Karte
  eingrenzen, sonst Nachspielschlüssel + Ursache UNKNOWN.
4. **Schritte 5–6:** ok-Pod-Tabellen je Lauf (Winners, Decisions, wall_s,
  semantic; Auffälligkeiten markieren) und Abdeckung der 182 Decks über
  alle Läufe. Keine Passquote, keine Hochrechnung — nur Zählungen.
5. **Endbericht:** `BERICHT.md` in diesem Ordner durch die Endfassung
  ersetzen (Zusammenfassung ≤ 1 Seite, dann Tabellen), plus alle
  `sweep_*.json` in den Ordner.

## Arbeitsregeln, die hier gegolten haben (bitten übernehmen)

- **PYTHONPATH-Falle:** `precon_pod_sweep.py` lädt `commander_lab` aus der
  installierten Venv — im Worktree immer mit
  `PYTHONPATH=<worktree>/src` starten, sonst bindet das Szenario den
  Engine-Pin des Haupt-Clones und jeder Pod scheitert im Handshake mit
  `ENGINE_FAILURE` (erster Versuch so verbrannt; Diagnose per
  Tee-Mitschnitt bewiesen).
- **CPU-Regel:** Während eines Sweeps keine andere JVM-Last; `--workers 1`
  auf dieser 2-Kern-VM. Timeout-Verdachtsfälle danach einmal allein
  nachspielen, beide Ergebnisse melden.
- **Lange Läufe sind fragil:** Die VM-Runtime startet gelegentlich neu und
  killt Hintergrundprozesse; die Sweep-Datei wird pro Pod geschrieben,
  Teilstände sind also verwertbar (so geschehen bei p1g1 nach Pod 027 und
  jetzt bei p2g1).
- Push auf diesen Branch läuft über das push-files-Verfahren; danach
  Remote gegen lokal per Blob-SHA diffen.
