# Max-Review — 03_VERBESSERUNGEN.md (Pass C: Rangliste, Hebel × Prüfbarkeit / Risiko)

Stand: Lab-main `ee47312a7`, Engine-Pin `90f5c4d3f8`. Rangformel: (Hebel × Prüfbarkeit) / Risiko.
Hebel = wie viele Spiele/Entscheidungen oder wie viel Wandzeit die Änderung bewegt (mit Zahl, wo
gemessen, sonst als Spanne mit Unsicherheit). Prüfbarkeit = ob der Effekt mit den vorhandenen
Werkzeugen (gepaarte Seeds, Twin-Hash, 17 Maße, per_card) in ≤24–48 Spielen sichtbar wird.
Risiko = Wahrscheinlichkeit, dass die Änderung Verhalten unbeabsichtigt ändert oder Requalifizierung
braucht. Jede Verbesserung: Beleg aus Pass A/B, Effekt mit Unsicherheit, Messung, Risiko,
Abhängigkeiten, Fork-Push/Repin, Issue-Entwurf in `05_ISSUE_ENTWUERFE/`.
Alle sieben Felder aus Abschnitt 6 sind abgedeckt (Zuordnung je Verbesserung in Klammern).
„Body:" = Behauptung aus einem PR-Body, keine Verifikation. Was noch in Messung ist, steht als
„Messung läuft" da, nicht als Ergebnis.

## Rangliste (Kurzform)

1. R-01 Abort-Programm: Zahlungsabbrüche messen, Top-3-Ursachen schließen [Feld 1]
2. R-08 Guides statt Spezialisten: erst A/B, dann schrittweise [Feld 1, O6]
3. R-02 Sonderfall-Register mit Auslöse-Zählung [Feld 6]
4. R-10 Durchsatz E1+E3 (getPlayable-Kopien, Views cachen) [Feld 3]
5. R-07 Angriffsplanung als Ganzes (Phase 3b, Symmetrie zu 3a) [Feld 1]
6. R-05 Timing-Gates: Fenster-Modell für Casts/Aktivierungen [Feld 1]
7. R-06 Trigger-Reihenfolge nach Nutzen (APNAP + Wert) [Feld 1]
8. R-09 #992 OOM-Fix im Deck-Vergleichs-Runner [Feld 3]
9. R-13 Kartenabdeckungs-Priorisierung für #979 (ohne Fork durch Muse) [Feld 2]
10. R-03 conftest-Ehrlichkeit (41 Tests) + R-04 Fake-Fixture-Level [Feld 6]
11. R-11 Statistik: Plan-Zahlen an echten Deckpaaren kalibrieren [Feld 4]
12. R-12 Deckbau-Antworten: M4-Protokoll mit Power-Plan + Finish-Order [Feld 5]
13. R-14 Pod-Realismus: Real-Pod gegen reinen Precon-Pod kalibrieren [Feld 7]
14. R-16 P-A/P-B-Determinismus-Fixes in den #979-Batch (Go-Vorbehalt) [Feld 2]

## R-01 — Abort-Programm: Zahlungsabbrüche messen, Top-3-Ursachen schließen [Feld 1]

Beleg: Auftragszahl 136/3599 Zahlungen mit „Cancel mana payment" in den 24 Spielen von #1006;
Muses frühere Hypothese (Filterländer, eingeschränktes Any-Color) ist unbelegt (02_BEFUNDE.md B-05);
Phase 4b zeigte, dass eine einzige Zahlungs-Ursache (Engine-Ceiling) 15/15 Antworten stellte
(verifiziert, `~/workspace/tmp/phase4b/`).
Effekt (Unsicherheit): Cancel-Rate Real-Pod zuletzt 1,60/1000 Entscheidungen (134 Abbrüche, beide
Seiten identisch, Phase-4b-Messung); Ziel-Pods 3,90/1000 nach 4b (vorher 5,14). Jede geschlossene
Ursache senkt die Rate um ihren Anteil — Anteil unbekannt, bis die Kette ausgewertet ist. Hebel
hoch, weil jeder Abbruch ein Spiel-Signal vernichtet (verlorene Züge, Endlosschleifen-Verdacht).
Messung: **Baseline gemessen 2026-10-25 (02 B-05): 135 abgebrochene Casts / 85.982 Entscheidungen
= 1,57/1000 (24 Real-Pod-Seeds, Main ee47312a7, Pin v13, Jar `0fda80ec…`); 136/136 rohe Cancels
erzwungen (92 nur-Cancel, 44 nur nicht-zahlende Alternativen), 0 echte Wahlen — alte Hypothese
(Filterland/Any-Color) widerlegt, neuer Befund: Casts werden mit absoluter Mana-Unterdeckung
gestartet.** Nächster Schritt (vor Fixes): Code-Analyse, wo die Unterdeckung entsteht
(Pilot-Bezahlbarkeits-Schätzung vs. Engine-`getPlayable`) — erst dann je Ursache ein Fix mit
eigenem Akzeptanzkriterium; dann gleiche 24 Seeds mit Fix; Signatur: Cancel-Rate + 17 Maße +
Sieger (kein Siegerwechsel erwartet, wie bei 4b: 23/24 bit-identisch). Teststärke: 24 Paare tragen nur große Effekte (wie bei 4b: 7→0
sichtbar, 134→134 nicht) — pro Ursache ein eigenes Akzeptanzkriterium (z. B. „Filterland-Cancels
0 in 24 Seeds" statt „Rate sinkt um x %").
Risiko: niedrig (Pilot-only, kein Fork, kein Repin); jede Ursachen-Fix braucht 10-Seed-Echtspiel-
vergleich im PR (harte Regel).
Abhängigkeiten: Abort-Ketten-Auswertung (Pass B, läuft).
Issue-Entwurf: `05_ISSUE_ENTWUERFE/01_abort_programm.md`.

## R-08 — Guides statt Spezialisten: erst A/B, dann schrittweise [Feld 1, O6]

Beleg: O6 (Owner-Entscheidung, offen); Pass A: `agents/card_knowledge.py` (kuratierte Profile,
`structural_role_profiles.json`) vs. hartcodierte Einzelkarten-/Prompt-Fälle in
`full_game_pilot_views.py`/`choices.py` (B-16); Deck-Guides: 206 Paare, Neugenerierung 0/206 geändert
(2026-10-24, kein Neu-Push nötig).
Effekt (Unsicherheit): Unbekannt, ob Guides die Spezialisten ersetzen können, ohne Verhalten zu
verlieren — das ist genau die A/B-Frage. Hebel strategisch hoch (weniger Wartungsfläche, mehr
Deck-Wissen), aber erst nach Messung zu beziffern.
Messung: A/B auf denselben 24 Real-Pod-Seeds: Variante A = aktueller Pilot (Spezialisten),
Variante B = Pilot mit Guides anstelle der Spezialisten (nur die Fälle, die Guides abdecken);
Signatur: 17 Maße + Zielmetriken (falsche Seite, Geschenke, Abbrüche) + Sieger. Akzeptanz für
„ersetzen": kein Maß verschlechtert sich (Holm), kein Siegerwechsel-Muster; sonst: Guides nur als
Ergänzung, Spezialisten bleiben.
Risiko: mittel (Verhaltensänderung möglich, aber gepaart messbar); kein Fork/Repin (Pilot + Daten).
Abhängigkeiten: keine; O6-Entscheidung durch Hans (Empfehlung aus dem Auftrag: ja, schrittweise
nach Phase 2 — Phase 2 ist gemergt, 4b gemergt, 1/3a gemergt: Voraussetzung erfüllt).
Issue-Entwurf: `05_ISSUE_ENTWUERFE/02_guides_ab.md`.

## R-02 — Sonderfall-Register mit Auslöse-Zählung [Feld 6]

Beleg: B-16 (Pass A: zahlreiche hartcodierte Fälle in views/choices); Lehre aus #862 (Regel, die
in echten Spielen nie läuft, ist toter Code — #862 lief erst mit #868).
Effekt (Unsicherheit): Kein direktes Spiel-Verhalten, aber Entlarvung toter Regeln: Jeder Fall, der
in 100+ Spielen nie feuert, ist entweder tot (entfernen) oder falsch verdrahtet (reparieren, wie
#862/#868). Hebel: Wartung + Vertrauen in jede künftige Pilot-Änderung.
Messung (ohne neue Spiele, Schritt 1): Zähler in die Sonderfälle einbauen, dann vorhandene
Transkripte (Phase-2-/Phase-4b-/Abort-Ketten, ~150 Spiele) auszählen: Feuerrate je Fall.
Schritt 2 (mit Spielen): 24 Seeds, Zähler aktiv, Fälle mit 0 Feuern → eigene Issues.
Risiko: sehr niedrig (Zähler-only, kein Verhalten); kein Fork/Repin.
Abhängigkeiten: keine.
Issue-Entwurf: `05_ISSUE_ENTWUERFE/03_sonderfall_register.md`.

## R-10 — Durchsatz E1+E3: getPlayable-Kopien, Views cachen [Feld 3]

Beleg: Engine-Dossier `handover/2026-10-24/engine/` (E1 getPlayable-Kopien größter Hebel, E3 Views
cachen; Erwartung E1+E3: 15–30 % Wandzeit); Pilot-Anteil nur ~1 % (0,43 ms/Entscheidung), Engine
~96 % — Pilot-Optimierung ist der falsche Hebel, Engine ist es (Pilot-Handoff).
Effekt (Unsicherheit): 15–30 % Wandzeit ist eine Dossier-Schätzung, keine Messung; Spanne groß,
weil E1 (Kopien) und E3 (Cache) unterschiedlich wirken und Cache-Korrektheit erst bewiesen werden
muss. Hebel trotzdem hoch: Bei ~120 s/24 Spiele (Phase 2: 126 s) spart 20 % ca. 25 s je 24er-Lauf —
über hunderte Läufe gerechnet der größte Zeithebel überhaupt.
Messung: Twin-Hash-Gate (harte Regel: gleiche Transkript-Hashes, sonst kein Durchsatz-Claim);
ABBA interleaved, CPU vor Wall (REPIN_RUNBOOK-Regel); Akzeptanz: ≥5 % Wandzeit bei 36/36
identischen Hashes (sonst unter 3-%-Schwelle verworfen, wie T-1/AppCDS).
Risiko: hoch, wenn Bridge-Code geändert wird (Requalifizierung durch Claude-Thread nötig, PB-03);
mittel, wenn nur Engine-intern (Fork) — dann zusätzlich Fork-Push + Repin mit Hans' Go.
Abhängigkeiten: Keine Pilot-Änderung parallel (sonst Hash-Vergleich ungültig).
Issue-Entwurf: `05_ISSUE_ENTWUERFE/04_durchsatz_e1_e3.md`.

## R-07 — Angriffsplanung als Ganzes, Phase 3b [Feld 1]

Beleg: #1006-Body: „Angriffsentscheidungen unverändert (Phase 3b)"; #1006 (3a, Blöcke als Ganzes)
ist gemergt, aber von Muse nicht nachgemessen; Pass A: Angriffs-Score in
`full_game_pilot_views.py:1466` („Imagine the Worst", Score ≤0 = halten), einzelne Angreifer-
Bewertung ohne deklarationsweite Planung.
**Pass-D-Hinweis (04, D2):** Keine belastbare externe Quelle für eine Commander-
Bedrohungs-/Politik-Leiter gefunden — das Multiplayer-Aggregationsziel aus dem Pilot-Handoff
(meinScore − maxGegner − λ·Mittel) bleibt **MODELED** (eigene Annahme), keine übernommene
Theorie; in 05 so zu kennzeichnen.
Effekt (Unsicherheit): 3a senkte Blockrunden mit tödlichem Rest 19→15 (Body, 24 Spiele) bzw. 19→16
(echte Spiele) — ein symmetrischer Angriffs-Effekt (mehr Schaden, weniger vergebliche Angriffe)
ist plausibel, aber nicht beziffert. Hebel: Angriffe sind die zweithäufigste Kampf-Entscheidung
nach Blöcken; jede vermiedene Fehlattacke ist ein erhaltener Angreifer.
Messung: Wie 3a: 24 aufgezeichnete Spiele (Angriffsrunden auf gleichen Positionen zählen) + 24
gepaarte Real-Pod-Seeds; Signatur: Angriffe, vergebliche Angriffe (Crackback), Sieger. Akzeptanz:
Angriffs-Metrik verbessert sich, kein Maß verschlechtert sich (Holm).
Risiko: niedrig-mittel (Pilot-only, Kampf-Logik ist sensibel — 3a zeigt, dass die Metrik
„needless chumps" durch Ganzes-Denken falsch wird; die Metrik muss mit der Änderung mitgezogen
werden, sonst misst man Artefakte).
Abhängigkeiten: 3a-Reproduktion (Pass B, folgt) als methodische Vorlage.
Issue-Entwurf: `05_ISSUE_ENTWUERFE/05_angriffsplanung_3b.md`.

## R-05 — Timing-Gates: Fenster-Modell für Casts/Aktivierungen [Feld 1]

Beleg: Auftrag Abschnitt 6.1 (offene Phase); Pass A: `priority.py` filtert bereits (unbezahlbar,
X ohne Rest-Mana, selbst-defeatend), aber ohne explizites Fenster-Modell — jede Karte wird pro
Fenster neu bewertet, ohne zu wissen, ob das Fenster das richtige ist (z. B. Sorcery-tempo in
fremdem Zug, Combat-Tricks außerhalb des Kampfs).
Effekt (Unsicherheit): Nicht beziffert; plausibelster Effekt ist weniger „bad idle main with
castable spell" (eine der 17 Maße) und weniger vergebliche Aktivierungen. Hebel mittel.
Messung: 24 gepaarte Seeds; Signatur: bad_idle-Maße + Zauber/Zug + Sieger. Akzeptanz: bad_idle
sinkt, kein Maß steigt (Holm).
Risiko: niedrig (Filter-only, kein neues Verhalten, nur Zurückhaltung).
Abhängigkeiten: keine; lässt sich mit R-07 kombinieren, sollte aber separat gemessen werden.
Issue-Entwurf: kein eigener Entwurf in dieser Runde (Rang 6 — Entwurf folgt, wenn R-01/R-07 stehen).

## R-06 — Trigger-Reihenfolge nach Nutzen [Feld 1]

Beleg: Auftrag Abschnitt 6.1 (offene Phase); `trigger_order` ist eine der 17 Bridge-Klassen
(`XmageFullGameDecisionController.java:460-464`); in den gelesenen Pilot-Dateien (Pass A,
Schwerpunkt vollständig) wurde keine Nutzenbewertung für Trigger-Reihenfolge gefunden — das ist
ein Teilbefund (Rest nur teilweise gelesen), kein Beweis der Abwesenheit.
Effekt (Unsicherheit): Nicht beziffert; Trigger-Reihenfolge entscheidet Spiele (z. B. Ziehen vor
Opfern), aber die Häufigkeit, in der die aktuelle Reihenfolge falsch ist, ist unbekannt.
Messung (Schritt 1, ohne Spiele): Zählung in vorhandenen Transkripten, wie oft `trigger_order`
mit >1 Option vorkommt und ob die gewählte Reihenfolge je nach Board variiert. Schritt 2: 24
gepaarte Seeds mit Nutzen-Regel.
Risiko: niedrig-mittel (Pilot-only, aber Reihenfolge-Fehler sind spielentscheidend — Test mit
gezielten Pods nötig).
Abhängigkeiten: Schritt-1-Zählung vor dem Entwurf.
Issue-Entwurf: kein eigener Entwurf in dieser Runde (Vorarbeit: Zählung).

## R-09 — #992 OOM-Fix im Deck-Vergleichs-Runner [Feld 3]

Beleg: Issue #992 (offen, Label `agent:muse`): ~5,25 GB RSS bei 495 Records; sequentieller Runner
akkumuliert Records. Akzeptanz aus dem Auftrag: Peak-RSS bei 200 und 800 Spielen messen + posten;
Aggregat byte-identisch.
Effekt (Unsicherheit): Speicher sinkt von GB auf MB (Streaming statt Akkumulieren) — fast sicher,
weil die Ursache (Akkumulation) benannt ist; die genaue Zahl hängt von Record-Größe ab.
Messung: Peak-RSS (z. B. `/usr/bin/time -v`) bei 200 und 800 Spielen, vorher/nachher; Aggregat
byte-identisch als Gate (sonst kein Fix-Claim).
Risiko: sehr niedrig (Runner-only, kein Spiel-Verhalten); kein Fork/Repin.
Abhängigkeiten: keine. Hinweis: #992 ist Muse zugewiesen, aber NICHT BEGONNEN — dieser Entwurf
bereitet ihn nur vor; die Umsetzung braucht Hans' Go nicht (Muse-Lane), aber die Messung
(800 Spiele) braucht Laufzeit.
Issue-Entwurf: kein eigener Entwurf in dieser Runde (Muse-Lane, direkt umsetzbar nach Go).

## R-13 — Kartenabdeckungs-Priorisierung für #979 (ohne Fork durch Muse) [Feld 2]

Beleg: Pool 195 = 186 echt + 9 SYNTHETIC (#988); #979 (Fork, 31 Karten, Claudes Lane, „Not for
Muse"); per_card-Daten existieren (#843: Cast-Rate, verrottende Karten).
Effekt (Unsicherheit): Kein Spiel-Effekt durch Muse (kein Fork-Code) — der Effekt ist Priorisierung:
Welche der 31 Karten zuerst (Häufigkeit in den 9 Decks × Verrottungsrate × Spielrelevanz), damit
Claudes #979-Arbeit den größten Pool-Gewinn zuerst bringt.
Messung (ohne neue Spiele): per_card aus vorhandenen Transkripten (Phase-2-/4b-/Abort-Ketten):
Für jede der 31 Karten (Namen aus #979, nicht aus Sammlung): Auftritte, Cast-Rate, Verrottung.
Risiko: keiner (Analyse-only); Fork-Push/Repin: nein (Vorbereitung für Claudes Lane, die Go braucht).
Abhängigkeiten: Abort-Ketten-Transkripte als drittes Korpus.
Issue-Entwurf: kein eigener Entwurf (Vorbereitungs-Dokument, kein Code-Issue).

## R-03/R-04 — conftest-Ehrlichkeit + Fake-Fixture-Level [Feld 6]

Beleg: B-02 (`tests/conftest.py:73`, 41 Tests), B-03
(`tests/fixtures/fake_external_engine_bridge.py:27`, einziger Importeur
`tests/contract/test_phase85_protocol.py:52`).
Effekt: Kein Spiel-Verhalten; Effekt ist Ehrlichkeit der Suite (grün heißt dann, was es sagt).
Messung: R-03: 41 Tests entweder mit echter Prüfung oder mit Markierung „setzt sauberen Worktree
voraus" + Zähler (vorher/nachher: 41 markiert, 0 still-gepatcht). R-04: Fixture-Level auf `fixture`
geändert, Test-Name auf Protokoll-Test angepasst; Suite grün.
Risiko: sehr niedrig (Test-only); kein Fork/Repin.
Abhängigkeiten: keine. Zusammen in einem Entwurf, weil beide Test-Ehrlichkeit sind.
Issue-Entwurf: kein eigener Entwurf in dieser Runde (zwei kleine Änderungen, direkt umsetzbar).

## R-11 — Statistik: Plan-Zahlen an echten Deckpaaren kalibrieren [Feld 4]

Beleg: #884 (Intervall, erkennbare Differenz, benötigte Paare), #912 (Paar-SD 0,63, Annahme
unabhängiger Spiele), #839 (sequentielles Stoppen), M4 (alle 6 Bündel UNDECIDED bei 200 Paaren).
Effekt (Unsicherheit): #884/#912 liefern Plan-Zahlen unter Annahmen; ob die Annahmen für echte
Deckpaare (nicht nur RogShai/Chulane) tragen, ist ungeprüft. Kalibrierung an 3 echten Deckpaaren
(RogShai-Variante, Chulane-Variante, ein Precon-Paar) würde die Plan-Zahlen von Annahme zu Messung
machen. Hebel: Jede künftige Deckbau-Frage („wie viele Spiele brauche ich?") bekommt eine
belegte Antwort statt einer Annahme.
Messung: Für 3 Deckpaare je 100 gepaarte Spiele (vorhanden: M4-Daten für 2 Paare, 1 Paar neu);
Paar-SD + erkennbare Differenz je Paar; Vergleich mit #912-Annahme (0,63).
**Pass-D-Schärfung (04, Q6/Q9):** Gepaarte Seeds sind Common Random Numbers — aber jede
Pfadänderung verschiebt den Draw-Index aller Folgeereignisse (Buffalo et al., arXiv:2603.11084,
März 2026). Pflicht-Metrik künftig: **Divergenzrate** (Anteil Paare, die nach der ersten
abweichenden Entscheidung auseinanderlaufen); bei großen Effekten CRN-Annahme als verletzt
markieren. Zusätzlich: vorab definierte Looks (z. B. 12/24/48, O'Brien-Fleming-Grenzen,
Alpha-Spending nach Lan–DeMets 1983) statt „24 Seeds, dann schauen" — billiges Protokoll,
kein Code.
Risiko: keiner (Analyse + Messung, kein Verhalten); kein Fork/Repin.
Abhängigkeiten: M4-Daten (`~/workspace/tmp/m4/`, vorhanden).
Issue-Entwurf: kein eigener Entwurf in dieser Runde (Analyse-Arbeit, kein Code-Issue).

## R-12 — Deckbau-Antworten: M4-Protokoll mit Power-Plan + Finish-Order [Feld 5]

Beleg: M4 (alle UNDECIDED — das Protokoll konnte die Frage nicht beantworten); #890 (Finish-Order
als zweites Ergebnis); #884 (Unsicherheits-Angaben).
Effekt (Unsicherheit): M4s Problem war nicht die Durchführung, sondern die Fragestellung: Bei
kleinen Effekten ist Win-Share das falsche primäre Maß (zu wenig Power bei 200 Paaren). Finish-Order
+ Power-Plan vorab (aus R-11) würden das nächste M4 entscheidbar machen — oder ehrlich sagen,
dass es 1.000+ Paare braucht, bevor es startet.
Messung: Protokoll-Entwurf (keine Spiele): Für ein konkretes nächstes Deckpaar Power-Plan aus
R-11-Zahlen + Finish-Order als primären Endpunkt bei kleinen Effekten + Stopp-Regel (#839).
Risiko: keiner (Protokoll); kein Fork/Repin.
Abhängigkeiten: R-11.
Issue-Entwurf: kein eigener Entwurf in dieser Runde (Protokoll-Dokument).

## R-14 — Pod-Realismus: Real-Pod gegen reinen Precon-Pod kalibrieren [Feld 7]

Beleg: Mission (Pod-Profil casual/mid, nicht cEDH); Real-Pod = 4 feste Decks (darunter ein
optimiertes Deck neben Precons — Zusammensetzung aus `scripts/run_real_4p_full_game_smoke.py`,
REAL_DECK_PATHS, nur als Spiel-Input verwendet, Inhalt nicht zitiert).
Effekt (Unsicherheit): Unbekannt, ob der Real-Pod die Pilot-Messung verzerrt (optimiertes Deck
gewinnt systematisch? Sitz-3-Führung in Phase 2 beidseitig deutet auf Pod-Effekt, nicht
Pilot-Effekt). Wenn ja, sind alle Real-Pod-Vergleiche pod-verzerrt; wenn nein, ist der Real-Pod
ein valider Standard.
Messung: 24 Seeds Real-Pod vs. 24 Seeds reiner Precon-Pod (4 Precons, gleiche Seeds, gleiche
Engine) — aber: Die Decks unterscheiden sich, also ist das kein gepaarter Vergleich, sondern ein
Sensitivitäts-Vergleich (Sieg-Verteilung je Sitz, Entscheidungszahlen). Akzeptanz: Bericht, keine
Schwelle — die Frage ist, ob der Pod-Effekt größer ist als typische Pilot-Effekte.
Risiko: keiner (Messung); kein Fork/Repin.
Abhängigkeiten: keine.
Issue-Entwurf: kein eigener Entwurf in dieser Runde (Messung, kein Code-Issue).

## R-16 — P-A/P-B-Determinismus-Fixes in den #979-Batch (Go-Vorbehalt) [Feld 2]

Beleg: #1001-Bericht (Commit `654ee965`): P-A (`SacrificeAllEffect` HashSet→LinkedHashSet),
P-B (`ChaosMutationEffect` toSet→toList); Verträglichkeit gemessen (49 stabile Hashes unberührt);
Relay an Claude liegt bei Hans, Weiterleitung unbekannt.
Effekt (Unsicherheit): Nach dem Batch müssen pod-025 und P9 je in 10 Läufen 1 Hash zeigen (Abnahme
aus dem #1001-Bericht) — bis dahin ist der Effekt eine Vorhersage, keine Messung.
Risiko: Fork-Code (Claudes Lane) + Repin + PB-03 + Seal — braucht Hans' Go (Fork-Push, Repin,
versiegelte Qualifikation). Muse misst nur (M7-Twins + P9-Replays nach dem Batch).
Abhängigkeiten: Hans' Weiterleitung des Relays + Claudes #979-Batch.
Issue-Entwurf: kein neuer Entwurf (Relay existiert bereits; kein Doppel-Entwurf).

## Felder-Abdeckung (Kontrolle)

- Feld 1 Spielstärke/Pilot: R-01, R-05, R-06, R-07, R-08 — je mit Befund, Messung, Risiko.
- Feld 2 Kartenabdeckung/Regeltreue: R-13, R-16 — je mit Plan (Fork durch Claude, Priorisierung durch Muse).
- Feld 3 Durchsatz: R-09, R-10 — je mit Gate (byte-identisch / Twin-Hash).
- Feld 4 Statistik/Vergleichsmethodik: R-11 — mit Kalibrierungs-Plan.
- Feld 5 Deckbau-Nutzen: R-12 — mit Protokoll-Plan.
- Feld 6 Architektur/Tests/Qualität/Betrieb: R-02, R-03/R-04 — je mit Zähler/Markierung.
- Feld 7 Daten/Realismus: R-14 — mit Sensitivitäts-Messung.
- Kein Feld ohne Fund oder ohne Beleg, dass nichts Belastbares zu finden war: Für Feld 7 ist der
  Fund die offene Verzerrungsfrage (R-14), nicht „alles in Ordnung" — das wäre ohne Messung
  unbelegt.
