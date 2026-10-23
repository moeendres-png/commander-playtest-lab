# Vertiefung zum Game-Mining (Muse, 2026-10-23, zweiter und dritter Durchlauf)

Ergänzt `BERICHT.md` (gleicher Ordner, gleiches Korpus: 2.033 Transkripte,
1.971 abgeschlossene Spiele, Pin v11). Skripte `mine2.py`/`mine3.py`, Aggregate
`aggregates2.json`/`aggregates3.json`, `cast_correlation_fixed.json` hier im
Ordner. Zwei Aussagen des Erstberichts werden unten **korrigiert** (P2-Effizienz,
P4) — die Vertiefung ersetzt sie.

## P1–P7, vertieft

- **P1 Ziel-Scoring — präzisiert.** Index-0-Ziele sind zu 90 % Permanents
  (104.801 von 116.674); Spieler werden seltener gewählt, als sie an erster
  Stelle angeboten werden (Spieler an Index 0: 11.873×, Spieler insgesamt
  gewählt: 9.554×). Ein Scoring muss also vor allem die **Permanent-Reihenfolge**
  bewerten; die Spielerwahl zeigt bereits eine schwache Eigenlogik.
- **P2 Prioritäts-Politik — Verhaltensbefund geschärft, Effizienzteil korrigiert.**
  Handlungsrate je Spieldrittel: 5,4 % → 6,6 % → 9,7 % (der Pilot wird spät
  aktiver); Fokal-Sitz 6,96 % vs. übrige Sitze 7,06 % — die Passivität ist
  gleichmäßig, kein Sitz-Effekt. **Korrektur:** Pässe lassen sich protokollseitig
  nicht zusammenfassen — jedes Pass ist ein eigenes legales Fenster der Engine;
  eine Einsparung kann nur über die Kosten je Entscheidung (Bridge-Round-Trip)
  kommen, nicht über weniger Entscheidungen. Der Verhaltensvorschlag (Heuristiken
  für fremde Züge) bleibt bestehen.
- **P3 choose_use-Audit — konkrete Liste.** „Pay {1} and 1 life and draw a
  card?": 1.317×, Ja-Rate 100 %. Multikicker-Inkonsistenz: „Pay 1 time
  Multikicker {2}?" Ja 100 % (1.026×), „Pay 2 times Multikicker {2}?" Ja nur
  40,9 % (1.026×) — dieselbe Fähigkeit, zwei willkürlich wirkende Schwellen.
  „Put a land card from your hand onto the battlefield?" Ja 100 % (6.600×,
  plausibel). Die Top-10-Promptliste steht in `aggregates2.json`.
- **P4 Mana-Fast-Path — präzisiert.** Index 0 ist ein Sondertyp („other_mana",
  26.010 Wahlen, immer dieser Typ); die effektive Wahl fällt auf das erste
  „echte" Zahlungsmittel an Index 1 (Pool-Verbrauch 525.130×, Land-Tappen
  348.712×). Ein Fast-Path würde exakt dieses beobachtete Verhalten als feste
  Regel kodifizieren (Pool zuerst, dann erstes Land) — Wert: entfallene
  Optionsbewertung; Risiko gering, weil keine neue Logik entsteht.
- **P5 Zustands-Profiling — zwei Faktoren getrennt.** Langsame Spiele (≥71 s)
  haben von **allen** Klassen mehr Entscheidungen je Spiel (priority 2.586 vs.
  2.176, mana_payment 736 vs. 551, target 75 vs. 57) **und** höhere Kosten je
  Entscheidung (Erstbericht: bis ~91 ms vs. 15,1 Median). mana_payment wächst
  überproportional (+34 % vs. +19 % bei priority). Profiling muss Volumen- und
  Kosteneffekt getrennt messen.
- **P6 Instrumentierung — durch P9/P11 und die Cast-Korrelation (unten)
  zusätzlich begründet.**
- **P7 Transkript-Schema — unverändert.**

## Neue Befunde und Vorschläge

- **P8 Kampf-Politik (neu).** Von 44.419 Blocker-Entscheidungen enden nur
  12.737 (28,7 %) mit einem Block; 71,3 % blocken nicht. Jede der 115.581
  Angreifer-Deklarationen wählt exakt **ein** Label (Summe der Wahlen =
  Anzahl der Entscheidungen) — Angriffe werden einzelgesteuert deklariert;
  die Angreiferzahl pro Kampf ist aus diesem Schnitt nicht ableitbar
  (Folgemessung). Vorschlag: Kampf-Audit (Block-Schwellen, Tauschlogik) als
  eigenes Pilot-Thema nach P1/P2.
- **P9 Determinismus-Replikation (neu, Messauftrag).** Von 1.627 mehrfach
  aufgezeichneten Spielen mit identischer Szenario-Identität (Kandidat, Seed,
  Sitz, Gegner-Deckmenge) haben **147 (9,0 %) unterschiedliche semantische
  Hashes** (146× zwei Hashes, 1× drei). Das widerspricht M4 nicht (dort:
  Ergebnisgleichheit der Duplikate) — aber Ergebnis ≠ Transkript. Kandidaten:
  Aufnahmekontext (Batch-Position/JVM) oder die Iterationsreihenfolge-Klasse
  aus dem M3-Zensus. Vorschlag: dieselben Keys gezielt auf Pin v13 replizieren
  (dort sind die M3-Ursachen gefixt); erst das Ergebnis entscheidet, ob ein
  Defekt vorliegt. Bis dahin: Befund offen, keine Schuldzuweisung.
- **P10 X-Wert-Politik (neu).** `announce_x` (2.926 Entscheidungen mit
  Zahlenwahl): häufigster Wert ist **0** (843), dann 1 (547), 2 (322), 3 (226),
  4 (173) — plus Spitzen bei 40 (157) und 38 (100), die nach einzelnen Karten
  aussehen. X=0 ist für viele X-Zauber wirkungsarm; ein Audit der betroffenen
  Karten/Prompts und eine einfache X-Heuristik (max. bezahlbar minus Reserve)
  sind der Vorschlag. Ohne Zustandsdaten nicht als Fehler wertbar.
- **P11 Mulligan-Regel (neu).** Gepoolte Ketten (7.884 Spieler-Eröffnungen):
  Keep an Position 0 nur 52,1 %; nach einem Mulligan Keep nur 47,1 % — 25,3 %
  aller Eröffnungen gehen auf 5 Karten, 6,7 % auf 4. Position 3: 100 % Keep
  (Kettenende). Ob die Regel zu streng ist, ist ohne Handdaten nicht
  entscheidbar (P6) — aber eine Eröffnungs-Keeprate von ~52 % ist der
  auffälligste einzelne Verhaltenswert des Korpus und verdient den Audit.

## Geprüft und verworfen (mit Evidenz)

- **Verpasste Land-Drops: kein Problem.** In nur 138 von 87.008
  Prioritätsfenstern mit spielbarem Land wurde gepasst (0,16 %). Kein
  Vorschlag.
- **Cast-Sieg-Korrelation der Fokus-Decks: kein verwertbares Signal.**
  Methodenwarnung zuerst: Ohne Decklisten-Filter produziert die naive
  Auswertung Phantom-Effekte von ±15 Punkten — das sind Karten der Gegner
  (Diebstahl-/Kopie-/Reanimations-Effekte lassen den Fokal-Sitz fremde Karten
  wirken; verifiziert an Einzelspielen). Mit Filter (nur eigene Deckliste,
  n ≥ 40): größtes |Δ| = +5,3 Punkte (Scorched Geyser, RogShai, n=174) —
  innerhalb des Binomial-Rauschens dieser Stichprobengrößen. **Keine
  Deck-Entscheidung aus dieser Statistik.** Wer Kartenwirkung messen will,
  braucht das M4-Paar-Design, keine Korrelation.
- **Abwurf-Verhalten: unauffällig.** Am häufigsten abgeworfen werden
  Basis-Länder (Swamp 635, Mountain 432) — spät im Spiel plausibel.
- **Spiellänge × Sitz (schwach, nur Notiz):** Kurze Spiele (≤40 Züge) gewinnt
  überproportional der Sitz relativ +1 (31 %), lange (>55) der Sitz +3
  (30 %); kleine Zellen, `MODELED` — kein Vorschlag.
