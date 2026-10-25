# R-12 — Deckbau-Antworten: M4-Protokoll mit Power-Plan + Finish-Order

Stand: 2026-10-25. Grundlage: M4 (alle 6 Bündel UNDECIDED bei 200 Paaren),
#890 (Finish-Order als zweites Ergebnis), #884 (Unsicherheits-Angaben),
#839 (sequentielles Stoppen), R-11 (dieses Paket). Kein neues Spiel, kein
Code — ein Protokoll-Dokument, das vor dem nächsten M4 stehen muss.

## 1. Was an M4 falsch war: nicht die Durchführung, die Fragestellung

M4 hat korrekt gespielt (1.200 Paare, saubere CIs) und trotzdem nichts
beantwortet: Bei 200 Paaren je Bündel sind nur Effekte ≥ ~5 Punkte
sichtbar (#999 M3). Die Bündel-Fragen („ist diese Karte besser?") waren
2–3-Punkte-Fragen. Das Protokoll hat die Frage nicht auf die Power
abgestimmt — es hat 200 Paare gespielt und gehofft.

**Regel für das nächste M4:** Keine Bündel-Frage ohne vorherigen
Power-Plan. Wer 2 Punkte sehen will, muss ~1.800 Paare (M4-ähnliche
Diskordanz) bis ~7.800 Paare (40 % Diskordanz) finanzieren (R-11,
Abschnitt 3) — oder die Frage ehrlich auf „deskriptiv" downgraden,
bevor das erste Spiel läuft.

## 2. Primärer Endpunkt: Finish-Order bei kleinen Effekten

Win-Share (Sign-Test auf Siege) ist bei kleinen Effekten das falsche
primäre Maß: Er wirft alle Nicht-Sieg-Information weg. #890 liefert
das zweite Ergebnis bereits: **Finish-Order** (mittlerer
Finishing-Score aus `place_scores`, im Aggregat als
`mean_finishing_score` vorhanden).

Protokoll-Regel:

- **Effekt ≥ 5 Punkte erwartet → primär Win-Share** (Sign-Test, wie
  bisher).
- **Effekt 2–3 Punkte erwartet → primär Finish-Order** (Mittelwert der
  Finishing-Scores, gepaarter Test auf den Score-Differenzen). Die
  Finish-Order nutzt auch 2./3./4. Plätze und hat bei kleinen Effekten
  mehr Power als der reine Sieg-Indikator — das ist der Grund, warum
  #890 sie eingeführt hat.
- **Beide Endpunkte werden immer berichtet**, aber nur der vorab
  gewählte primäre entscheidet das Verdict. Nachträgliches Wechseln
  („Win-Share war UNDECIDED, Finish-Order sieht gut aus") ist
  Endpunkt-Shopping und ungültig.

Caveat (aus #890-Body, ehrlich): Die Verdict-Logik (Sign-Test) blieb
unverändert; die Finish-Order ist ein Berichtswert, kein
Sign-Test-Ersatz. Ein gepaarter Test auf Scores braucht seine eigene
Power-Rechnung (Score-SD aus einem Vorlauf, nicht aus #912s 0,63 —
die gilt für Sieg-Differenzen, nicht für Scores). UNKNOWN, bis ein
Vorlauf Score-SDs liefert.

## 3. Power-Plan-Vorlage (vor jedem Bündel auszufüllen)

| Feld | Eintrag (Beispiel: nächste RogShai-Variante) |
|---|---|
| Deckpaar + geänderte Karten | RogShai-Basis vs. Variante (1 Karte getauscht) |
| Erwarteter Effekt | 2–3 Punkte (Annahme, zu begründen: warum so groß?) |
| Geschätzte Diskordanz q | 0,09 (M4-ähnlich, 1-Karten-Tausch) — sonst Vorlauf |
| Paare aus R-11-Tabelle | 790 (3 Punkte, q = 0,09) |
| Primärer Endpunkt | Finish-Order (Effekt klein) |
| Looks (R-11) | 12 / 24 / 48 — nein: Looks müssen zur Paare-Zahl passen! Bei 790 Paaren: Looks z. B. 200 / 400 / 790 mit OBF-Grenzen für Anteile 0,25 / 0,51 / 1,00 (z ≈ 3,92 / 2,75 / 1,96). Die 12/24/48-Looks aus R-11 gelten für 48-Paar-Phasenmessungen, nicht für M4. |
| Stopp-Regel (#839) | Stoppen, sobald alle Varianten am OBF-Niveau entschieden sind; sonst bis zur geplanten Paare-Zahl durchspielen, kein Nachlegen ohne neues Protokoll |
| Auswertung | Win-Share + Finish-Order + Divergenzrate (R-11) + 17 Maße; Gewinnrate nur, wenn die Power trägt, sonst „UNDECIDED, could only see effects of at least X" |

## 4. Stopp-Regel, präzisiert (#839 + R-11)

- Die Stopp-Regel steht vor dem Lauf fest (Looks + Grenzen + primärer
  Endpunkt).
- Ein Stopp vor der geplanten Paare-Zahl ist nur am definierten Look
  mit OBF-Grenze gültig.
- Nach Erreichen der geplanten Paare-Zahl ohne Verdict heißt das
  Ergebnis **UNDECIDED mit benannter Nachweisgrenze** („could only see
  effects of at least X points"), nicht „kein Effekt". M4s Fehler war
  nicht das UNDECIDED — das war korrekt — sondern dass die
  Nachweisgrenze erst nach dem Lauf klar wurde.

## 5. Was dieses Protokoll nicht löst (UNKNOWN)

- Score-SD für Finish-Order-Tests (braucht Vorlauf).
- Ob Finish-Order bei 2-Punkte-Effekten wirklich mehr Power hat als
  Win-Share (Behauptung aus #890s Motivation, nicht aus einer
  Power-Messung — die M4-Daten enthalten `place_scores` je Bündel;
  eine Nachrechnung der Score-Power aus M4 wäre der nächste Schritt
  und braucht keine neuen Spiele, ist aber in diesem Dokument nicht
  getan).
- Deckbau-Fragen jenseits von Karte-raus/rein (Mana, Kurve, Matchups,
  Combo-Linien): Das Protokoll beantwortet nur die
  Vergleichs-Frage. Für Kurven-/Mana-Fragen braucht es andere
  Auswertungen (M1-Lineal, per_card) — außerhalb dieses Dokuments.

## 6. Evidenzklassen

- M4-UNDECIDED, #999-Tabelle, #890-Existenz: DIRECTLY_VERIFIED
  (Aggregate + 01-Tabelle).
- Finish-Order-mehr-Power: MODELED (Motivation aus #890, kein
  Power-Beweis).
- Protokoll-Regeln, Looks, Stopp: Design (kein Messwert, sondern
  Festlegung für künftige Läufe).
