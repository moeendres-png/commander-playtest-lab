# Laufprotokoll Welle 2, Repo-Fassung ohne Modellnamen (zweiter Bewertungslauf H, 622 Karten + Retest-Charge 8)

Diese Datei ist die Repo-Fassung des Laufprotokolls des Co-Leads (Plan §2: „im Repo nur eine Fassung ohne
Modellnamen“). Das Original liegt im Scratchpad des Co-Leads (SHA-256
`e4f57fb398baa93d2111cc9db73c054602003c21def929a7a041c5e77128d738`) und enthält die Modell-ID. Geändert
wurden nur: die Modell-ID und der Agent-Parameter (ersetzt durch den Hinweis unten) und der absolute
Rater-Pfad (ersetzt durch `<RATER_DIR>`). Alles andere ist inhaltlich übernommen; leere Felder des Originals
bleiben leer und sind unten als Lücke benannt. Die maschinenlesbare Eingabe für das Auswerteskript ist
`run_log.json` (gleicher Ordner).

## Vor dem Start

- Plan-Commit: Draft-PR #1761 (a3cd2b4af86ca195a207c625e4b04045ab541f0d; Eingaben byte-gleich zu bfff13b2), Squash-Merge 73c22de3cdeee4dcb3fdc234ac0ff8c4b6b0a768 (2026-11-22T16:41:48Z).
- SHA-256 Lauf-Anweisung (mit echtem Pfad): f440b7fab245831808ee51c1e5f660eed2e805f3e4fd1cb5004f356ca08f95f5; gleich der Repo-Kopie `rater/rr2_rater_instructions.md` (6932797d8a2fade356f39e4f108275894c4b80b9842ebb8bf92ed2f36d0e0bba) bis auf den Pfad statt `<RATER_DIR>` (nachgeprüft: Pfad ersetzt ergibt 6932797d…).
- SHA-256 Lauf-Manifest: bac9fb03c2318f225c411848ee8da29cf498ae40930621a7a5e3ed7472e3a41d (= `rr2_manifest.json` im Repo).
- Rater-Ordner: `<RATER_DIR>` (Elternordner enthielt nur `rater/`).
- SHA-256 der Eingaben und Guides vor dem Start gegen das Manifest geprüft: ja.
- Modell-ID und Agent-Parameter der Rater: **im Scratchpad-Protokoll, nicht im Repo**. Stufe/Aufwand: Voreinstellung des Agent-Aufrufs, nicht gesetzt (UNKNOWN). Gleiche Modell-ID wie Welle 1: unbekannt (Welle 1 hat kein Laufprotokoll).
- Modellfamilie gegenüber F1: unbekannt (A3). Gegenüber G1: unbekannt (B2 „unbelegt“).
- Werkzeuge und Dateizugriff: Agenttyp mit allen Werkzeugen (Bash, Read, Write, Edit, Glob, Grep, Web); Zugriff außerhalb des Rater-Ordners technisch möglich. Die Blindheit beruht auf der Anweisung und dem leeren Elternordner; dass keine Instanz weitere Dateien las oder das Web nutzte, beruht nur auf den Schlussantworten (Selbstauskunft, `final_replies_redacted.json`).
- Auftragssatz je Subagent: „Du bist Rater N=k. Lies `<Rater-Ordner>/rr2_rater_instructions.md` und folge ihr.“
- Retest-Charge 8: ja (Entscheid Co-Lead vor dem Start, 2026-11-22T16:45Z).

## Je Charge

Die Tabelle „Start / Ende / Unterbrechungen / Zeilen / Selbstprüfung / Schlussantwort“ ist im Original
**nicht ausgefüllt** (Lücke gegenüber Plan §2). Belegt ist stattdessen: Zeilen je Charge 89, 89, 89, 89,
89, 89, 88, 50 und „C True“ aller Selbstprüfungen (Freeze-Kommentar #1404 7082408782); die Schlussantworten
wörtlich in `final_replies_redacted.json`; keine A7-Abbrüche, kein A1-Nachlauf, kein Blindheitsverstoß laut
`run_log.json`. Start- und Endzeit je Charge sind nicht protokolliert; die Ausgabedateien wurden bis
16:52Z (Freeze) fertig.

## Einfrieren

- `sha256sum rr2_output_*.jsonl`: `rater/output_sha256.txt`, gepostet in #1404 Kommentar 7082408782 (2026-11-22T16:52:39Z).
- Auswerteskript-Commit: im Original leer (Lücke); belegt durch #1763, Squash 2987afc652f092a7a8b473e8ee3ca6a096ab9f4e (2026-11-22T20:44:27Z), vor dem ersten Lauf von `hits` (Kommentar 7085521227, 20:45:27Z).
