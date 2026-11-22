<!-- Repo-Fassung des Laufprotokolls Welle 2 (Plan §2). Gegenüber dem Original (Scratchpad des Co-Leads, SHA-256 e4f57fb398baa93d2111cc9db73c054602003c21def929a7a041c5e77128d738) sind nur ersetzt: die Zeile mit Modell-ID und Agent-Parameter (→ „im Scratchpad-Protokoll, nicht im Repo“) und der absolute Rater-Pfad im Scratchpad (→ <RATER_DIR>). Leere Felder des Originals bleiben leer. Ergänzungen stehen nur im letzten Abschnitt. -->

# Laufprotokoll Welle 2 (zweiter Bewertungslauf H, übrige 622 Karten + optionale Retest-Charge 8)

Vom Co-Lead **vor und während** des Laufs auszufüllen. Plan: `docs/analysis-reports/rating_full_second_run_plan_20261122.md` (PR #1761 gemerged, Squash-Commit 73c22de3cdeee4dcb3fdc234ac0ff8c4b6b0a768, Stand 2026-11-22T16:45Z).
Dieses Protokoll bleibt im Scratchpad (darf Modell-IDs enthalten); ins Repo geht nur eine Fassung ohne Modellnamen (Plan §2, §10).

## Vor dem Start (Pflicht, sonst A3)
- Plan-Commit im Repo (SHA): a3cd2b4af86ca195a207c625e4b04045ab541f0d (Draft-PR #1761; Eingaben byte-gleich zu bfff13b2; danach Squash-Merge 73c22de3). Ändert das Review eine Eingabe, einen Guide oder die Anweisung, ist ein schon begonnener Lauf ungültig und startet auf den neuen Dateien neu.
- SHA-256 Lauf-Anweisung `blind_w2/rater/rr2_rater_instructions.md`: f440b7fab245831808ee51c1e5f660eed2e805f3e4fd1cb5004f356ca08f95f5 (gleich der Repo-Kopie bis auf den Pfad statt `<RATER_DIR>`; Repo-Kopie 6932797d8a2fade356f39e4f108275894c4b80b9842ebb8bf92ed2f36d0e0bba)
- SHA-256 Lauf-Manifest `costudio/rr2w2/rr2_manifest.json`: bac9fb03c2318f225c411848ee8da29cf498ae40930621a7a5e3ed7472e3a41d
- Rater-Ordner: `<RATER_DIR>/`
- SHA-256 der Eingaben vor dem Start = Manifest `per_chunk.*.input_sha256` / `guide_sha256` geprüft: ja (Pflichtprüfung unten vor dem Start)
- Modell-ID der Rater: im Scratchpad-Protokoll, nicht im Repo  Stufe/Aufwand: Voreinstellung des Agent-Aufrufs, nicht gesetzt (UNKNOWN)  gleiche Modell-ID wie Welle 1 (rr_output_1..3): unbekannt (kein Laufprotokoll für Welle 1)
- Modellfamilie gegenüber F1 (Vollauf): unbekannt (Quelle: Plan A3; F1 hat kein Laufprotokoll der Modell-ID)
- Werkzeuge und Dateizugriff der Subagenten (welche Tools, Zugriff außerhalb des Rater-Ordners technisch möglich?): Agenttyp general-purpose mit allen Werkzeugen (Bash, Read, Write, Edit, Glob, Grep, Web); Zugriff außerhalb des Rater-Ordners technisch möglich, Blindheit beruht auf der Anweisung und dem leeren Elternordner (nur `rater/`); Schlussantwort jeder Instanz nennt gelesene Pfade
- Auftragssatz je Subagent (wörtlich): „Du bist Rater N=k. Lies `<Rater-Ordner>/rr2_rater_instructions.md` und folge ihr.“
- Retest-Charge 8 gestartet: ja (Entscheid Co-Lead, vor dem Start, 2026-11-22T16:45Z)

## Je Charge
| N | Start (UTC) | Ende (UTC) | Unterbrechungen / Wiederaufnahme ab k | Zeilen | Selbstprüfung („C True“) | Schlussantwort (Blindheit, Tools) |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| 7 | | | | | | |
| 8 (optional) | | | | | | |

## Einfrieren (vor jedem Öffnen der Ausgaben)
- `sha256sum rr2_output_*.jsonl` (hier eintragen, dann als Kommentar in die Issue #1404 / den PR posten):
  siehe output_sha256.txt (gepostet in #1404, 2026-11-22T16:52Z)
- Auswerteskript-Commit (muss VOR dem Öffnen im Repo stehen, Plan §9): ____

## Anmerkungen der Repo-Fassung (nicht im Original)

- Lücken des Originals gegenüber Plan §2: Die Tabelle „Je Charge“ (Start, Ende, Unterbrechungen, Zeilen, Selbstprüfung, Schlussantwort) und die Zeile „Auswerteskript-Commit“ sind leer; Start- und Endzeit je Charge sind nicht protokolliert.
- Ersatzbelege: Zeilen je Charge 89, 89, 89, 89, 89, 89, 88, 50 und „C True“ aller Selbstprüfungen im Freeze-Kommentar #1404 7082408782 (2026-11-22T16:52:39Z); Schlussantworten in `final_replies_redacted.json`; A7/A1/Blindheit je Charge in `run_log.json`; Auswerteskript #1763, Squash 2987afc652f092a7a8b473e8ee3ca6a096ab9f4e (2026-11-22T20:44:27Z), vor dem ersten `hits`-Lauf (Kommentar 7085521227, 20:45:27Z).
- Nachgeprüft bei der Erstellung dieser Fassung: Die Lauf-Anweisung mit dem Pfad ersetzt durch `<RATER_DIR>` ergibt die SHA-256 der Repo-Kopie 6932797d8a2fade356f39e4f108275894c4b80b9842ebb8bf92ed2f36d0e0bba.
- Dass keine Instanz weitere Dateien las oder das Web nutzte, beruht nur auf den Schlussantworten (Selbstauskunft, A3).
