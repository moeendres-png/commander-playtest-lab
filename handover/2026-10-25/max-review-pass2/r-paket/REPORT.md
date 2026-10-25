# REPORT — R-Paket Max-Review Pass 2 (R-09, R-11, R-12, R-13, R-14)

Stand: 2026-10-25. Alle fünf Teile liegen in
`~/workspace/tmp/max-review/pass2-r/`. R-09 wurde verifiziert, nicht neu
erfunden; R-11 bis R-14 sind Analysen (keine neuen Spiele, keine
JVM-Ketten, kein Fork-Code, kein Push/PR/Merge). Evidenzklasse je
Aussage: DIRECTLY_VERIFIED / CODE_DERIVED / MODELED / UNKNOWN
(UNKNOWN ist niemals PASS).

## R-09 — OOM-Fix verifiziert, kein Repair nötig

- Commit `5fc7347be` (wt-992, Basis `217c34d95`, Baum sauber, kein
  Push/PR/Merge): `_slim_record_for_aggregate` ersetzt
  `result_payload` durch nur `outcomes` + `turn_number`; volle Records
  bleiben auf Platte. DIRECTLY_VERIFIED (Commit gelesen).
- Whitelist-Behauptung stimmt: `aggregate_comparison` liest nur
  Record-Felder, die vom Slimmen unberührt bleiben (`case_id`,
  `status`, `failure_class`, `winner_seats`,
  `semantic_transcript_sha256`, `decision_count`, `outcomes`,
  `turn_number`). CODE_DERIVED (Code gelesen, kein Vertrauen in den
  Docstring).
- Tests selbst gelaufen: Memory-Test 1 passed, Deck-Comparison 8,
  games_per_jvm 26 = 35 passed; Umkreis 112 grün. Ruff clean; Mypy 8
  Import-Fehler, keiner im neuen Code. DIRECTLY_VERIFIED.
- Negativkontrolle: alter Stand FAILT mit 86.276.510 Bytes Wachstum;
  Post-Fix 7.008.535 Bytes (7,0 MB), Schwellwert 10 MB liegt mit Abstand
  dazwischen. DIRECTLY_VERIFIED (eigene Messung, `/tmp`-Skript).
- Byte-Identität des Aggregats: Test-Assertion besteht.
  DIRECTLY_VERIFIED (synthetische Records).
- M4-Größenbehauptung exakt: 1,58 MB Payload in 2,30 MB Datei.
  DIRECTLY_VERIFIED (echte M4-Datei).
- Grenze: `combined.records` enthält geslimmte Records; heute kein
  anderer Konsument. CODE_DERIVED.
- **Offen (UNKNOWN):** RSS bei 200 und 800 echten Spielen (#992-
  Akzeptanz — braucht JVM-Ketten, Haupt-Thread); 5,25 GB @ 495 Records
  (Issue-Zahl, Mechanismus plausibel, nicht reproduziert); Byte-
  Identität am 800-Spiele-Echtlauf. Dateien: `R09_OOM_FIX.md`,
  `PR_BODY_R09.md` (copy-paste-fertiger PR-Body, Echtlauf-Akzeptanz
  als offen markiert).

## R-11 — Statistik: Paar-SD ist keine Konstante

- M4-Paar-SD gepoolt 0,301 (1.200 Paare, q = 0,0908), je Bündel
  0,245–0,343 — etwa halb so groß wie #912s Annahme 0,63.
  DIRECTLY_VERIFIED (aus `aggregate_*.json` nachgerechnet).
- Erklärung: SD = √(q − δ²); 0,63 ⟺ q ≈ 0,40; M4-Paare sind
  Fast-Zwillinge (1 Karte getauscht), Unabhängigkeits-Limit 0,707.
  MODELED (Formel) + DIRECTLY_VERIFIED (M4-Zahlen).
- McNemar-Tabelle erweitert (q = 0,09 / 0,20 / 0,40 × 2 / 3 / 5
  Punkte): 2 Punkte brauchen 1.779 bis 7.847 Paare je nach Diskordanz.
  MODELED (Formel reproduziert #999s gepoolte Spalte auf Rundung).
- Divergenzrate als Pflicht-Metrik (erster abweichender Frame-Index;
  > 50 % vor Entscheidung 100 ⇒ CRN-Annahme verletzt) + OBF-Looks
  12/24/48 (z = 3,92 / 2,77 / 1,96). Design, kein Code.
- Kalibrierung an 3 Deckpaaren: 2 aus M4 vorhanden, 1 Precon-Paar neu
  (≈ 3,5 h für 100 Paare). **Paar 3: UNKNOWN (nicht gespielt).**

## R-12 — M4-Protokoll: Frage an Power anpassen, nicht umgekehrt

- M4s Fehler war die Fragestellung (200 Paare sehen nur ≥ ~5 Punkte),
  nicht die Durchführung. DIRECTLY_VERIFIED (M4-Aggregate + #999).
- Finish-Order als primärer Endpunkt bei kleinen Effekten (2–3
  Punkte), Win-Share sekundär; beide immer berichtet, primärer
  Endpunkt vorab festgelegt (kein Endpunkt-Shopping). Design;
  Finish-Order-mehr-Power: MODELED (Motivation aus #890, kein
  Power-Beweis).
- Power-Plan-Vorlage + Stopp-Regel (#839 + OBF, Looks zur Paare-Zahl
  passend — 12/24/48 gilt für 48-Paar-Phasen, nicht für M4).
- **Offen (UNKNOWN):** Score-SD für Finish-Order-Tests (braucht
  Vorlauf); Score-Power-Nachrechnung aus M4-`place_scores` möglich
  ohne neue Spiele, hier nicht getan.

## R-13 — Kartenabdeckung: 10 von 31 an v13 vorhanden, 21 fehlen

- Klassen-Prüfung im Fork (exakte Dateien, Set-Nennungen zählen
  nicht): 10 vorhanden (Winter, Zinnia, Aminatou + alle 7 aus
  multiverse_reforged), 21 fehlen. CODE_DERIVED (statisch).
- Die 10 entsprechen exakt den 4 Decks aus dem Max-Review-v13-
  Vorbefund — zwei statische Signale, gleiche Aussage.
- Deck-Zuordnung (13 Decks, 195 Precon-Dateien): jede Karte in genau
  1 Deck, außer Psychic Paper (2) und Desert Warfare (2 Dateien).
  DIRECTLY_VERIFIED.
- Freischalt-Reihenfolge (Deck statt Karte): 1-Karten-Decks zuerst
  (Eye of Duskmantle, Desert Warfare), dann 2-, 3-, 4-, 8-Karten-Decks.
- Mechanik-Cluster aus Scryfall-Oracle-Texten (heute, exakte Namen):
  Face-down-Cyberman ×5 (1 Mechanismus), Villainous Choice (Missy),
  Goad (Immortal Obligation), Phasing ×3, Exchange of Words und
  Space Beleren als schwerste Einzelkarten, Susan Foreman braucht
  Planechase. DIRECTLY_VERIFIED (Scryfall).
- **Offen (UNKNOWN):** Laufzeit-Recount an v13 (Schritt 1 für Claudes
  Lane); Fork-Push/Repin/Seal brauchen Owner-Go; Stubs kein
  Endzustand. Analyse-only, kein Fork-Code.

## R-14 — Pod-Realismus: Vergleichsarm fehlt, Design steht

- Real-Pod-Sitzgewinne (47 Spiele, zwei Pilot-Stände gepoolt):
  RogShai 15, Kaervek 4, Hosts 15, Lorehold 13. Kaervek 4/47: Wilson
  [0,034, 0,199], Binomial-p 0,0039 (Bonferroni ×4 → 0,016).
  DIRECTLY_VERIFIED (ausgezählt) / MODELED (Statistik).
- Vorbehalte: Pilot-Versions-Mischung, n = 47, Sitz↔Deck nicht
  trennbar (Treiber rotiert nicht). Die Kaervek-Auffälligkeit ist
  Motivation für die Sensitivität, kein bewiesener Pod-Effekt.
- #978-„Precon-Pod" ist kein reiner Precon-Pod (8 Spiele, gemischte
  Varianten-Pods). DIRECTLY_VERIFIED (Sweep-Logs).
- Sensitivitäts-Design: 24 Seeds × Real-Pod vs. reiner Precon-Pod,
  gleiche Engine/Pilot, unpaired, Metriken (Sieganteile,
  Entscheidungen/Spiel, Spells/Spieler-Runde, Commander-Raten);
  Pod-Effekt > typischem Pilot-Effekt (~0,04 Spells/Spieler-Runde
  aus #1007, ~5 Punkte aus #999) ⇒ material. Kosten ≈ 50 Min.
  Laufzeit + ~1 h Auswertung. Design + Schätzung.
- **Pod-Verzerrungsurteil: UNKNOWN (Vergleichsarm fehlt).**

## Einhaltung der harten Grenzen

- Keine `data/collections/**`- oder `coverage_decks/collection/**`-
  Daten gelesen oder zitiert (nur Deck-Dateinamen und Pfade aus
  Treibern/Precons).
- Keine Änderungen an `engine-bridge/**`, Workflows, `config/`,
  `qualification/`; keine Dateien außerhalb `pass2-r/` und `wt-992`
  verändert; `wt-mage-v13` nur gelesen (Status leer), andere
  Worktrees nicht angefasst; kein Push/PR/Merge; kein neues `Any`.
- `wt-992` steht sauber auf `5fc7347be` (kein Repair-Commit nötig).

## Offene Punkte für den Parent (Übergabe)

1. #992-Echtlauf-Akzeptanz (RSS 200/800 Spiele) — Haupt-Thread /
   JVM-Ketten; PR-Body liegt bereit, Akzeptanz als offen markiert.
2. v13-Recount für #979 — Claudes Lane, nach Owner-Go.
3. R-11-Paar-3-Kalibrierung und R-14-Sensitivitäts-Lauf — neue Spiele,
   Kosten oben genannt, keine Go-Entscheidung in diesem Paket.
