# R-14 — Pod-Realismus: Real-Pod gegen reinen Precon-Pod kalibrieren

Stand: 2026-10-25. Grundlage: Mission (Pod-Profil casual/mid, nicht
cEDH), Real-Pod-Definition, vorhandene Spieldaten. Keine neuen Spiele —
wo die vorhandenen Daten nicht reichen, steht Design + Kostenschätzung
statt einer Messung.

## 1. Was der Real-Pod ist (Dateinamen, keine Deck-Inhalte)

`scripts/run_real_4p_full_game_smoke.py`, `REAL_DECK_PATHS` (Reihenfolge
= Sitzreihenfolge in den Real-Pod-Ketten; der Treiber
`phase4b_play.py` rotiert nicht):

1. `data/decks/rogshai_current.json` (Sitz 1)
2. `data/decks/opponents/kaervek/current/deck.json` (Sitz 2)
3. `data/opponents/hosts_of_mordor_precon.json` (Sitz 3)
4. `data/opponents/lorehold_spirit_precon.json` (Sitz 4)

Ein optimiertes Deck (Sitz 1) neben einem Gegner-Deck (Sitz 2) und zwei
Precons (Sitz 3, 4). Sitzgewinne in den Real-Pod-Dateien sind damit
Deckgewinne — Sitz- und Deck-Effekt sind in diesen Daten nicht
trennbar. (Deck-Inhalte wurden nicht gelesen und werden hier nicht
zitiert; es geht nur um die Sitz↔Deck-Zuordnung.)

## 2. Was vorhandene Daten zeigen (DIRECTLY_VERIFIED, mit Vorbehalt)

### Real-Pod, zwei Stichproben (verschiedene Pilot-Stände!)

| Stichprobe | Spiele | Sitz 1 (RogShai) | Sitz 2 (Kaervek) | Sitz 3 (Hosts) | Sitz 4 (Lorehold) |
|---|---|---|---|---|---|
| Abort-Kette, Main ee47312a7 | 24 | 8 | 3 | 5 | 8 |
| Phase-2-Main, älterer Pilot | 23 entschieden | 7 | 1 | 10 | 5 |
| **Gepoolt** | **47** | **15** | **4** | **15** | **13** |

Quellen: `~/workspace/tmp/max-review/abort24/*.json` (Feld `winners`),
`~/workspace/tmp/phase2/games_main_merged.json` (24 Spiele, davon 23 mit
genau einem Sieger).

**Auffälligkeit:** Kaervek gewinnt 4/47 (8,5 %). Wilson-95 %-Intervall
[0,034, 0,199] schließt den Gleichwert 0,25 aus; einseitiger
Binomial-p = 0,0039 (×4 Sitze Bonferroni → 0,016, weiter < 0,05).
**Vorbehalte (wichtig):** (a) Die beiden Stichproben stammen von
verschiedenen Pilot-Ständen (Phase 2 vs. ee47312a7 mit Phasen 1/3a/4b) —
Pooling ist nur als Pod-Signal lesbar, wenn der Pod-Effekt die
Pilot-Änderungen dominiert, was gerade die Frage ist. (b) n = 47 ist
klein; ein einzelner Ausreißer-Seed verschiebt das Bild. (c) Die
Phase-2-„Sitz-3-Führung beidseitig" (Base + PR) aus dem Vorbericht
deutet auf Deck/Sitz statt Pilot — hier nur als Vorbefund zitiert,
die PR-Seite wurde in diesem Dokument nicht neu ausgezählt.

### Precon-Pod-Stichprobe: nicht vorhanden in brauchbarer Form

Die #978-Sweep-Logs (`~/workspace/tmp/978/sweep_plan*.log`) enthalten 8
Spiele (4 Pods × 2 Pläne), Sitzgewinne {1:3, 2:2, 3:1, 4:2} — aber die
Pods tragen Varianten-Decks (Beispiel pod-000: Symbiotic Swarm,
Timey Wimey, Vampiric Bloodlust, Tricky Terrain Collector's Edition —
zwei davon sind blockierte Decks, die als Varianten gespielt wurden).
Das ist **kein reiner Precon-Pod** und n = 8 hat keine Power. Eine
saubere Precon-Pod-Stichprobe (4 Precons, mehrere Seeds, gleiche
Engine) liegt in den vorhandenen Daten nicht vor.

**Fazit aus vorhandenen Daten:** Der Real-Pod zeigt eine interne
Schiefe (Kaervek-Schwäche), aber ob der Real-Pod als Messinstrument
verzerrt, ist damit NICHT entschieden — der Vergleichsarm fehlt.
Das ist der Fund (offene Verzerrungsfrage), nicht „alles in Ordnung".

## 3. Sensitivitäts-Design (keine neuen Spiele in diesem Dokument)

**Frage:** Ist der Pod-Effekt größer als typische Pilot-Effekte? Wenn
ja, sind alle Real-Pod-Vergleiche pod-verzerrt und brauchen
pod-gematchte Baselines; wenn nein, ist der Real-Pod ein valider
Standard.

**Design:**

- Arm A: Real-Pod, Seeds 1–24 (vorhanden: Abort-Kette, ee47312a7 —
  muss bei Pilot-Änderungen neu gespielt werden, sonst vergleicht man
  Pilot-Stände, keine Pods).
- Arm B: Reiner Precon-Pod (4 Precons, die an v13 sauber importieren,
  ohne SYNTHETIC-Anteil), gleiche Seeds 1–24, gleiche Engine (Pin v13),
  gleicher Pilot-Stand wie Arm A, Sitz↔Deck-Zuordnung je Spiel
  protokolliert.
- **Kein gepaarter Vergleich:** Die Decks unterscheiden sich, also ist
  das kein Paar-Vergleich, sondern ein Sensitivitäts-Vergleich.
  Metriken je Arm: Gewinnanteile je Sitz und je Deck, Entscheidungen
  pro Spiel, Spells pro Spieler-Runde, Commander-Cast-Raten,
  bad_*-Raten (aus `pilot_decision_report.py compare`).
- **Auswertung:** Pod-Effekt = Differenz der Arm-Kennzahlen, verglichen
  mit typischen Pilot-Effekten als Referenzgröße: #1007 meldet
  −0,036 Spells pro Spieler-Runde (95 %-Intervall −0,074 bis +0,003)
  als Phasen-Effekt; #999 meldet ~5 Punkte als Nachweisgrenze bei 200
  Paaren. Wenn die Pod-Differenz diese Größenordnungen überschreitet
  (z. B. Gewinnanteils-Verschiebung > 5 Punkte oder
  Spells/Spieler-Runde-Verschiebung > 0,04), ist der Pod-Effekt
  material und muss in jedem künftigen Real-Pod-Vergleich als
  Kovariate oder per Pod-Matching kontrolliert werden.
- **Akzeptanz:** Bericht, keine Schwelle — die Frage ist, ob der
  Pod-Effekt größer ist als typische Pilot-Effekte (s. o.).

**Kosten (Schätzung aus der Abort-Kette: 1.481 s / 24 Spiele ≈ 62 s
pro Spiel, sequenziell):** 48 Spiele ≈ 50 Minuten Laufzeit + ca. 1 h
Auswertung. Keine Fork-/Repin-Abhängigkeit.

## 4. Was dieses Dokument nicht behauptet (UNKNOWN)

- Ob Kaervek wirklich schwach ist oder die 47 Spiele Rauschen sind
  (die CIs sprechen dagegen, aber Pilot-Versions-Mischung + kleine n
  lassen Raum).
- Ob ein reiner Precon-Pod „fairer" wäre (kein Fairness-Begriff
  definiert; casual/mid ist ein Profil, keine Gleichverteilung).
- Ob Sitz- oder Deck-Effekte dominieren (ohne Sitz-Rotation nicht
  trennbar — das Design muss die Zuordnung protokollieren).

## 5. Evidenzklassen

- Sitzgewinne, Pod-Zusammensetzungen, 978-Logs: DIRECTLY_VERIFIED
  (aus den genannten Dateien ausgezählt).
- Kaervek-CIs/p-Werte: MODELED (Standard-Statistik auf den
  ausgezählten Gewinnen).
- Sensitivitäts-Design, Kosten: Design + Schätzung (Abort-Ketten-Rate).
- Pod-Verzerrungsurteil: UNKNOWN (Vergleichsarm fehlt — genau das
  soll das Design schließen).
