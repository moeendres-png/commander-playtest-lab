# `#1528`: Vorab abgelegter Serienplan – Chulane Landzahl-Achse (`36 / 38 / 40` Länder) mit Kontrollen

- **Datum:** 2026-11-24 · **Refs:** `#1528`, `#1167`, `#1521`, `#1524`, `#1589`
- **Owner-Bestätigung:** 2026-11-24 (`#1528` Kommentar 4, Bestätigung von Kommentar 3) und 2026-11-24 (`Option 5A`, Vorab-Plan jetzt ablegen; großer Nachtlauf nach Merge von `#1589`).
- **Einordnung:** Vorab-Plan (`CODE_DERIVED` / Planung vor dem ersten Spiel; noch keine Partien gelaufen → alle Messwerte sind `NOT_RUN`). Spätere Ergebnisse tragen `SIMULATED_RESULT`, sind kein Qualifikationsbeleg und fließen nie in die Tierliste ein (`AGENTS.md` §1, §4).
- **Basisstand & Engine-Pin:** `main` @ `aa7a4b57e21d8c350ae4b75f5bf504f935881f19`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), Bridge-Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`.

## 1. Vorab festgelegte Fragestellung und Entscheidungsschwelle

- **Frage:** Verbessert eine Erhöhung der Landzahl in Chulane, Teller of Tales von `36` auf `38` oder `40` Länder die simulierte Siegrate am festen 4-Sitz-Tisch?
- **Erwartete Richtung:** Höhere Konsistenz bei frühen Land-Drops (weniger `0–1`-Land-Starthände); ob die zusätzliche Manasicherheit die geringere Kartendichte überwiegt, ist offen (`36` vs. `38` vs. `40`).
- **Änderungsschwelle („bei welchem Ergebnis ändere ich das Deck?“):** Umbau auf `38` oder `40` Länder nur dann, wenn:
  1. das 95-%-Konfidenzintervall der Differenz (Variante − Basis `36`) vollständig über `0 pp` liegt **und** die Punktschätzung mindestens `+3 pp` beträgt, **und**
  2. Negativkontrolle (`36` vs. `36`), Positivkontrolle (`27` Länder) und die exakte hypergeometrische Gegenprobe alle bestehen.
  - „Kein nachweisbarer Unterschied bei `n = …`; nachweisbar wären `y pp`“ ist ausdrücklich ein voll gültiges Ergebnis.

## 2. Deck-Arme (Basis, Varianten, Kontrollen)

Alle Karten stammen aus `data/decks/chulane_current.txt` / `data/decks/deckbau/chulane_current.json` (100 Karten, 36 Länder: 8× Forest, 8× Island, 4× Plains, 16 Nonbasics) sowie `data/research/collection_1655/` (nur eigene Sammlung, ohne Preise).

| Arm | Länder | Änderung gegenüber Basis (`36`) | Zweck |
|---|---:|---|---|
| **Basis (`B36`)** | `36` | unverändert (`chulane_current.json`) | Vergleichsbasis |
| **Negativkontrolle (`N36`)** | `36` | inhaltsgleiche Kopie von `B36` | Erwartung: Differenz ~`0 pp`, 95-%-CI schließt `0` ein; misst echte Diskordanz |
| **Arm A (`V38`)** | `38` | **Raus (2):** `Mechanized Production`, `Open the Armory` · **Rein (2):** `Glacial Fortress`, `+1 Forest` | Hauptarm 1 (`+2` Länder) |
| **Arm B (`V40`)** | `40` | **Zusätzlich raus (2):** `Tezzeret, Betrayer of Flesh`, `Tangletrove Kelp` · **Zusätzlich rein (2):** `Adarkar Wastes`, `+1 Forest` | Hauptarm 2 (`+4` Länder, kumulativ zu `V38`) |
| **Positivkontrolle (`P27`)** | `27` | **Raus (9 Basics):** `4× Forest`, `3× Island`, `2× Plains` · **Rein (9 MV-4-Kreaturen ohne Ramp):** `Abbey Griffin`, `Arbalest Elite`, `Aven Fisher`, `Aven Fleetwing`, `Azure Drake`, `Bladed Sentinel`, `Blightwidow`, `Briarhorn`, `Clockwork Condor` | Erwartung: klar schlechter als `B36` (oberes 95-%-CI `< 0 pp`); sonst Frage unbeantwortet |

## 3. Exakte hypergeometrische Gegenprobe (7-Karten-Starthand aus 99-Karten-Bibliothek)

Für jeden Arm müssen die beobachteten Länder in der zuerst ausgeteilten 7-Karten-Hand (`first_dealt_hand`) mit der exakten hypergeometrischen Verteilung (`N = 99`, `n = 7`, `K ∈ {27, 36, 38, 40}`) übereinstimmen (kein signifikanter Widerspruch, sonst wird die Serie verworfen):

| Arm | `K` Länder | `E[Länder]` | Standardabweichung | `P(0–1 Land)` | `P(2–4 Länder)` | `P(5+ Länder)` |
|---|---:|---:|---:|---:|---:|---:|
| `P27` | `27` | `1,9091` | `1,1417` | `38,23 %` | `60,23 %` | `1,54 %` |
| `B36` / `N36` | `36` | `2,5455` | `1,2332` | `20,15 %` | `74,03 %` | `5,83 %` |
| `V38` | `38` | `2,6869` | `1,2467` | `17,10 %` | `75,51 %` | `7,39 %` |
| `V40` | `40` | `2,8283` | `1,2579` | `14,40 %` | `76,39 %` | `9,21 %` |

## 4. Serien-Zuschnitt, Seed-Blöcke und Startbefehle (Owner-PC)

- **Tisch:** Fester 4-Sitz-Tisch (`pod = precon`: `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`), volle Sitzrotation (`rotate_seats = true`, 4 Sitze je Seed).
- **Pilot-Audit-Zähler (`#1524`):** `--record-pilot-audit` optional für Auslassungszählung im Gültigkeitsblock aktivieren.
- **Disjunkte Seed-Blöcke (kein Seed-Recycling zwischen Erkundung und Bestätigung):**
  1. **Negativkontrolle (`N36` vs. `B36`):** `budget_pairs = 80` (`160` Partien), `first_seed = 10000`, `purpose = control`.
  2. **Positivkontrolle (`P27` vs. `B36`):** `budget_pairs = 80` (`160` Partien), `first_seed = 11000`, `purpose = control`.
  3. **Hauptvergleich 1 (`V38` vs. `B36`):** `budget_pairs = 240` (`480` Partien, nach Merge von `#1589` Basis-Partien wiederverwendbar), `first_seed = 12000`, `purpose = confirmation`, Holm-Familie über `V38` und `V40`.
  4. **Hauptvergleich 2 (`V40` vs. `B36`):** `budget_pairs = 240` (`480` Partien), `first_seed = 12000` (gemeinsame Zufallszahlen auf derselben Basis nach `#1589`, sonst disjunkter Block `13000`), `purpose = confirmation`.
- **Startreihenfolge am Owner-PC (nach Merge von `#1589`):**
  1. Zuerst `N36` und `P27` ausführen und zusammen mit der hypergeometrischen Gegenprobe prüfen.
  2. Nur wenn beide Kontrollen und die Gegenprobe bestehen, `V38` und `V40` über `POST /api/experiments` (oder `python -m commander_lab.studio compare-decks`) starten.
  3. Vollständige Auswertung mit `n/N`, 95-%-CI, Holm-korrigiertem `p`, `y_pp`, Gültigkeitsblock (`seat_curve`, `pilot_omissions`, `bridge_jar_sha256`, `BRIDGE_AHEAD_OF_QUALIFICATION`) in `#1528` dokumentieren und Owner-Urteil einholen.

## 5. Grenzen und `NOT_RUN` / `UNKNOWN`

- Alle vier Serien sind derzeit **`NOT_RUN`**; echte Laufzeit, Diskordanz und Effektstärken auf diesem Tisch sind **`UNKNOWN`**.
- Das Ergebnis gilt nach dem Lauf ausschließlich für diesen 4-Sitz-Precon-Tisch, den aufgezeichneten `pilot_fingerprint`, den Engine-Pin `f4d12f6e…` und das eingesetzte Bridge-JAR (`SIMULATED_RESULT`).
