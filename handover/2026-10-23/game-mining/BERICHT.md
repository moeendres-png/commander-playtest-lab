# Befundbericht: Mining des vollständigen M4-Spielkorpus (Muse, 2026-10-23)

Auftrag des Owners: aus den vollständigen Spieledaten Verbesserungen jeglicher Art
herausarbeiten. Korpus: **2.033 einzigartige Spiel-Transkripte** aus dem M4-Archiv
(`games_manifest.json` in `handover/2026-10-23/game-records/`), davon **1.971
abgeschlossen** und 62 Protokoll-Fehlschläge (die bekannten Bridge-Timeout-Records
vor ihren Retries). Alle Spiele: GenericCommanderPilot 1.0.0, Pin v11, Lab
`d48bbe5f2`, Tische RogShai/Chulane gegen den M4-Gegnertisch. Ausgewertet:
**~6,05 Mio. Entscheidungen** (jedes `decision_requested`/`decision_accepted`-Paar).
Reproduktion: `mine_m4.py` + `aggregates.json` in diesem Ordner. Zahlen sind
`LOCAL_OBSERVED`, Deutungen als `MODELED`/`CODE_DERIVED` markiert.

## Befunde Pilot-Verhalten

1. **Priorität: 93,0 % Pass.** Von 4.373.551 `priority`-Entscheidungen (72 % aller
   Entscheidungen überhaupt) enden 93,0 % mit Option 0 — die in der Stichprobe
   ausnahmslos (67.827/67.827) „Pass priority" ist. Der Pilot handelt in ~7 % der
   Prioritätsfenster. Das ist der größte einzelne Verhaltenshebel: Instant-Tempo
   und Reaktionen in fremden Zügen sind strukturell selten (`MODELED`: eine
   Phasen-Aufschlüsselung braucht einen zweiten Mining-Durchlauf).
2. **Target-Wahl: starke Erstziel-Konzentration.** `target`: Index 0 in 41,6 %
   bei Ø 7,24 Optionen (gleichverteilt wären ~15–20 %). Die Engine-Reihenfolge
   der Ziele entscheidet faktisch mit; ein Ziel-Scoring ist der konkreteste
   Pilot-Verbesserungsvorschlag (P1).
3. **Optional-Fähigkeiten: „Yes" in ~97 %.** `choose_use` (52.768, genau 2
   Optionen): Index 0 in 97,2 %; Stichprobe der Labels: „Yes" 522×, „No" 15×.
   May-Fähigkeiten werden praktisch immer genutzt — auch solche mit Kosten oder
   Nachteilen (`MODELED`, ohne Zustandsdaten nicht als Fehler wertbar; Audit-Liste P3).
4. **Mana-Zahlung: feste Positionspräferenz.** `mana_payment` (1.123.371 = 19 %
   aller Entscheidungen): Index 1 in 78,4 %, Index 0 nur 2,3 %, Ø 7,88 Optionen.
   Die Zahlungsreihenfolge folgt offenbar einer festen Regel statt einer
   Bewertung (`CODE_DERIVED`-Verdacht, Code-Lektüre durch Claude nötig).
5. **Startspieler: Der Wählende wählt immer sich selbst.** In allen 1.971
   abgeschlossenen Spielen wählte der Akteur der „Select a starting player"-
   Entscheidung den eigenen Sitz (454/512/534/471 je Sitz).
6. **Mulligan:** gepoolt 14.175 Entscheidungen (~1,7 je Spieler und Spiel inkl.
   Ketten): „Keep opening hand" 7.884, „Take mulligan" 6.291. Die
   First-Hand-Keeprate der beiden Fokus-Decks (69,3 %) steht im M4-Endbericht.
   Handqualität ist in den öffentlichen Frames nicht enthalten — eine
   Mulligan-Politik ist aus diesem Korpus nicht bewertbar (Instrumentierung P6).
7. **Kein Positions-Artefakt bei Angreifern:** `declare_attacker`-Indizes sind
   breit gestreut (29/18/22/26 % auf 0–3).

## Befunde Effizienz

8. **Entscheidungsvolumen:** Median 2.939, Mittel 3.070 Entscheidungen/Spiel;
   Wandzeit Median 44,7 s, Mittel 47,8 s, p90 71 s, max 184 s; ~15,1 ms je
   Entscheidung (Median über Spiele). Zwei Klassen dominieren alles:
   `priority` (72 %) + `mana_payment` (19 %) = **91 % aller Entscheidungen**.
9. **Die langsamsten Spiele sind nicht die entscheidungsreichsten.** Das
   langsamste Spiel (184 s) hat nur 2.013 Entscheidungen (~91 ms/Entscheidung,
   6× Median). Die Kosten je Entscheidung hängen stark vom Spielzustand ab
   (Boardgröße/Triggerlast, `MODELED`) — Profiling muss zustandsbezogen
   ansetzen, nicht an Rohzahlen (P5).
10. **Spiellänge:** Median 46 Züge (Engine-Zähler), Mittel 47,6, p90 62, max 99.

## Negativbefunde (geprüft, kein Effekt)

11. **Kein Startspieler-Vorteil messbar:** Sieger relativ zum Startspieler
    25,2 / 26,4 / 25,0 / 23,4 % (n=1.971) — trotz Befund 5 (Selbstwahl) ist die
    Startposition am Ergebnis nicht sichtbar. Eine Änderung der
    Startspieler-Regel ist mit dieser Evidenz nicht zu begründen.
12. Sanity: Die Familien-Siegquoten reproduzieren die M4-Ergebnisse
    (Baselines Chulane 8,0 %, RogShai 17,4 %).

## Priorisierte Verbesserungsvorschläge

| # | Vorschlag | Evidenz | Erwarteter Hebel |
|---|---|---|---|
| P1 | Ziel-Scoring statt Erstziel-Neigung im Piloten | Befund 2 | Spielqualität aller zielenden Effekte |
| P2 | Prioritäts-Politik: Phasen-Mining nachlegen, dann Heuristiken für Handeln in fremden Zügen prüfen | Befund 1 | Größter Verhaltenshebel (72 % der Entscheidungen, 93 % Pass) |
| P3 | `choose_use`-Audit: Klassen, in denen „Yes" Kosten/Nachteile hat, mit Defaults versehen | Befund 3 | Vermeidet systematische Fehlgriffe |
| P4 | Mana-Zahlungs-Fast-Path (feste Regel ohne volle Optionsbewertung) | Befunde 4+8 | Bis ~19 % weniger Entscheidungsvolumen |
| P5 | Zustandsbezogenes Kosten-Profiling (welche Boards/Trigger kosten 90 ms+) | Befund 9 | Effizienz der langen Läufe (p90/max) |
| P6 | Instrumentierung: Hand-/Zustandsmerkmale in künftigen Läufen mitschreiben | Befund 6 | Mulligan- und Target-Politik werden erst messbar |
| P7 | Kompaktes Transkript-Schema/Kompression beim Schreiben (Korpus: 7,7 GB für 2.033 Spiele) | Korpus | Speicher-/Transferkosten großer Kampagnen |

Grenzen: Ein Pilot, ein Pin, zwei Fokus-Decks, ein Gegnertisch — Verhaltensraten
sind für diesen Stand gemessen, nicht universell. Ob eine Wahl *falsch* war, ist
ohne Zustands- und Handdaten aus den öffentlichen Frames allein nicht
entscheidbar; die Vorschläge sind Mess- und Audit-Aufträge, keine Schuldsprüche.
