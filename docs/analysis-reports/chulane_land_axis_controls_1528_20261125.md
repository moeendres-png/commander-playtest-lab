# `#1528`: Echt-Engine-Kontrolltor Chulane Landzahl-Achse (`N36` `PASS`, Hypergeometrie `PASS`, `P27` Fail-Closed bei `N = 80`)

- **Datum:** 2026-11-25 · **Refs:** `#1528`, `#1167`, `#1524`, `#1589`, `#1590`
- **Vorab-Plan:** [chulane_land_axis_plan_1528_20261124.md](chulane_land_axis_plan_1528_20261124.md)
- **Einordnung:** **`SIMULATED_RESULT`** (lokale Echt-Engine-Messung unter Linux/WSL2 in einem isolierten Arbeitsordner außerhalb des Repositories `<studio-data-dir>/runs_1528_20261125/`, **kein Qualifikationsbeleg**; Ergebnisse fließen nicht in die Tierliste ein; `AGENTS.md` §1, §4).

## 1. Umgebung, Provenienz und Lauf-Konfiguration

- **Basisstand (`main`):** `af96fb760b7265d29e90ee96fa43cda063f7a113` (`HEAD^{tree}`: `5d6a09fb6f2bb243d38b92ac7dc821a685722e5a`)
- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`)
- **Bridge-JAR:** `xmage-engine-bridge.jar`, SHA-256 `ec53219322a25d0d7433e972051731d48115bcb4a9329b0a75713aeb3d10b938`, Zustand **`BRIDGE_AHEAD_OF_QUALIFICATION`** (`covered_by_sealed_epoch = false`)
- **Laufzeitumgebung:** Java 21 mit passendem AppCDS-Archiv (`322.064.384` B, `studio-doctor-1` `PASS` `8/8`), `workers = 6`, `games_per_jvm = 20`, `--rotate-seats` (`4` Sitze je Seed), `--record-pilot-audit` (`320/320` Partien mitgezeichnet), Pool-Schalter `OFF`
- **Pilot-Fingerabdruck:** `51818f6859adb2aef8d79f879934f1e7efe6564a0be8fad1d2c896f0242b4a9f`
- **Fester 4-Sitz-Tisch:** Chulane-Arm gegen `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`
- **Lokale Artefakte (`<studio-data-dir>/runs_1528_20261125/`):** `results/n36.json`, `results/p27.json`, `320/320` Spielprotokolle unter `games/`, `320/320` Pilot-Audit-Mitschnitte unter `pilot_audit/` (nichts davon im Repository)

---

## 2. Ergebnis des vorab registrierten Kontrolltors

Gemäß Abschnitt 2 und Abschnitt 4 des Vorab-Plans dürfen die Hauptarme `V38` (`38` Länder) und `V40` (`40` Länder) erst gestartet werden, wenn **alle drei** Kontrollbedingungen erfüllt sind: (1) Negativkontrolle `N36` schließt `0 pp` ein, (2) Positivkontrolle `P27` zeigt ein oberes `95-%-CI < 0,0 pp`, (3) exakte hypergeometrische Gegenprobe widerspricht nicht.

| Serie | Seeds (rotierend) | Paare (`ok / N`) | Zensiert / Fehler | Basis-Siegrate (`n/N`, 95-%-Wilson) | Varianten-Siegrate (`n/N`, 95-%-Wilson) | Differenz | 95-%-CI (Cluster-t) | Nachweisgrenze (`pp`) | Diskordanz (`V : B`, gebunden) | Vorzeichen-p | Wandzeit | Urteil |
|---|---|---:|---:|---|---|---:|---|---:|---|---:|---:|---|
| **`N36` vs. `B36`** (`chulane-1528-n36`) | `10000..10019` (`20/20`) | `80/80` (`160/160` Partien) | `0/80` (`0/160` / `0/160`) | `16/80` = `20,0 %` `[12,7 %; 30,0 %]` | `16/80` = `20,0 %` `[12,7 %; 30,0 %]` | **`0,0 pp`** | `None` (Nullstreuung) | `None` | `0/80` (`0 : 0`, `80/80` gleich) | `1,000000` | `16m 58,8s` | **`PASS`** |
| **`P27` vs. `B36`** (`chulane-1528-p27`) | `11000..11019` (`20/20`) | `80/80` (`160/160` Partien) | `0/80` (`0/160` / `0/160`) | `14/80` = `17,5 %` `[10,7 %; 27,3 %]` | `8/80` = `10,0 %` `[5,1 %; 18,5 %]` | **`−7,5 pp`** | **`[−18,951; +3,951] pp`** | `16,162 pp` | `16/80` (`5 : 11`, `64/80` gleich; `20,0 %` vs. `24,0 %` unabh.) | `0,210114` | `14m 00,8s` | **`FAIL_CLOSED`** (`+3,951 >= 0`) |
| **`V38` vs. `B36`** | `12000+` (`240` geplant) | `NOT_RUN` | — | — | — | — | — | — | — | — | — | **`NOT_RUN`** (Torstopp) |
| **`V40` vs. `B36`** | `12000+` (`240` geplant) | `NOT_RUN` | — | — | — | — | — | — | — | — | — | **`NOT_RUN`** (Torstopp) |

- **Sitzaufschlüsselung `P27` vs. `B36` nach Chulane-Startplatz (`n = 20/20` Paare je Platz):**
  - Sitz `0`: `B36 = 3/20` → `P27 = 1/20`
  - Sitz `1`: `B36 = 5/20` → `P27 = 4/20`
  - Sitz `2`: `B36 = 3/20` → `P27 = 1/20`
  - Sitz `3`: `B36 = 3/20` → `P27 = 2/20`
  - `P27` schneidet auf jedem der vier Startplätze schlechter ab als `B36` (`−7,5 pp` punktschätzend bzw. `−42,9 %` relativ), verfehlt mit den vorab festgelegten `80` Paaren (`20` Seed-Cluster) jedoch die statistische Schwelle (`oberes 95-%-CI = +3,951 pp >= 0,0 pp`).

---

## 3. Exakte hypergeometrische Gegenprobe (`first_dealt_hand`, `N = 99`, `n = 7`)

Auswertung über alle `320/320` abgeschlossenen Partien (`first_dealt_hand` aus `games/*.jsonl.gz`):

| Arm | `K` Länder | Stichprobe (`n/N`) | Beobachteter Mittelwert (Erwartet, `z`) | Beobachtete SD (Erwartet) | `P(0–1 Land)` obs vs. exp | `P(2–4 Länder)` obs vs. exp | `P(5+ Länder)` obs vs. exp | `chi2 (df=2)` | `p` | Urteil |
|---|---:|---:|---|---:|---|---|---|---:|---:|---|
| **`B36`** (`N36` + `P27`) | `36` | `160/160` | `2,6063` (`2,5455`, `z = +0,62`) | `1,1980` (`1,2332`) | `26/160` (`16,25 %` vs. `20,15 %`) | `125/160` (`78,12 %` vs. `74,03 %`) | `9/160` (`5,62 %` vs. `5,83 %`) | `1,580` | `0,4538` | **`PASS`** |
| **`N36`** | `36` | `80/80` | `2,4000` (`2,5455`, `z = −1,06`) | `1,2076` (`1,2332`) | `17/80` (`21,25 %` vs. `20,15 %`) | `61/80` (`76,25 %` vs. `74,03 %`) | `2/80` (`2,50 %` vs. `5,83 %`) | `1,621` | `0,4447` | **`PASS`** |
| **`P27`** | `27` | `80/80` | `2,0625` (`1,9091`, `z = +1,20`) | `1,2257` (`1,1417`) | `26/80` (`32,50 %` vs. `38,23 %`) | `51/80` (`63,75 %` vs. `60,23 %`) | `3/80` (`3,75 %` vs. `1,54 %`) | `3,408` | `0,1820` | **`PASS`** |
| **`V38` / `V40`** | `38` / `40` | `NOT_RUN` | — | — | — | — | — | — | — | **`NOT_RUN`** |

Die Engine teilt die erste Hand für alle geprüften Arme konsistent mit der exakten hypergeometrischen Verteilung (`p >= 0,1820`).

---

## 4. Cluster-Varianz, Trennschärfe (`#1590`) und Gültigkeitsblock (`#1524`)

### Cluster-Streuung bei `--rotate-seats` (Bezug `#1590`)
- Durch die Sitzrotation (`4` Paare je Seed) ist der **Seed** der unabhängige Cluster (`20/20` Cluster, `df = 19`):
  - **`N36` (`0`-Karten-Tausch):** `0/80` diskordante Paare (`sd_pair = 0,0000`, `disc_share = 0,000` vs. `0,320` unabhängig).
  - **`P27` (`9`-Länder-Raus / `9`-Kreaturen-Rein):** `16/80` diskordante Paare (`0,200` vs. `0,240` unabhängig), Paar-Streuung **`sd_pair = 0,4437`** (`44,37 pp`), Cluster-Mittel-Streuung **`sd_seed_mean = 0,2447`** (`24,47 pp`), Cluster-Standardfehler **`se_cluster = 5,47 pp`** gegenüber unclustert **`se_unclustered = 4,96 pp`** (Design-Effekt **`DEFF = 1,217`**).
- **Erklärte Ursache des Fail-Closed-Ergebnisses:** Bei `20` Seed-Clustern (`80` rotierte Paare) beträgt die Nachweisgrenze `detectable_difference_pp = 16,162 pp`. Ein realer Effekt von `−7,5 pp` benötigt bei `sd_seed_mean = 0,2447` etwa **`84` Seed-Cluster** (`~336` rotierte Paare, geschätzt `~58 min` auf diesem System), um mit `80 %` Trennschärfe (`α = 0,05`) sicher `< 0 pp` zu trennen. Analog hätte auch ein `240`-Paare-Hauptlauf (`60` Seed-Cluster) eine Nachweisgrenze deutlich oberhalb von `+3 pp` (ca. `~9 pp` bei vergleichbarer Cluster-Streuung).

### Sitzkurven (4 Sitze, alle `160` Partien je Serie; Playgroup-Referenz `29,1 / 25,7 / 23,6 / 21,5 %`, `n = 300.240`)
- **`N36` (`160/160` Partien):** Sitz 1 `32/160` (`20,0 %`), Sitz 2 `40/160` (`25,0 %`), Sitz 3 `42/160` (`26,2 %`), Sitz 4 `44/160` (`27,5 %`). *(Hinweis: `32+40+42+44 = 158/160`; `2/160` Partien ohne eindeutigen Einzelsieger/Unentschieden bzw. Auswertung gemäß `seat_curve`.)*
- **`P27` (`160/160` Partien):** Sitz 1 `47/160` (`29,4 %`), Sitz 2 `35/160` (`21,9 %`), Sitz 3 `43/160` (`26,9 %`), Sitz 4 `33/160` (`20,6 %`).

### Objektive Pilot-Auslassungen (`#1524`, `320/320` Partien mitgezeichnet, `740.250` Entscheidungen)
- **`N36` (`160/160` Partien, `400.028` Entscheidungen):** **`110/6.704`** (`1,64 %`) — davon `land_play`: `98/6.114` (`1,60 %`), `cast_commander` (`T <= 6`): `12/590` (`2,03 %`).
- **`P27` (`160/160` Partien, `340.222` Entscheidungen):** **`70/6.286`** (`1,11 %`) — davon `land_play`: `70/5.723` (`1,22 %`), `cast_commander` (`T <= 6`): `0/563` (`0,00 %`).

---

## 5. Entscheidungsoptionen für `#1528` und offene Grenzen (`UNKNOWN` / `NOT_RUN`)

- **Option A (Empfohlen, Vorab-Plan-konform):** Für den Nachweis der Positivkontrolle vorab ein größeres Budget (`320–400` rotierte Paare = `80–100` Seed-Cluster, ~`1 h`) oder eine schärfere Kontrastliste (z. B. `20` Länder) auf disjunkten frischen Seeds durch den Owner freigeben und erst nach bestandenem `P27` (`oberes 95-%-CI < 0 pp`) die Hauptarme `V38`/`V40` mit angepasstem Cluster-Budget starten.
- **Option B:** `V38` und `V40` (`240` Paare mit `--reuse-baseline` ab Seed `12000`) per Owner-Go ausdrücklich als explorativen Varianz-/Streuungs-Lauf freigeben (Dokumentation, dass `P27` bei `N = 80` unterpowert blieb).
- **`NOT_RUN` / `UNKNOWN`:**
  - `V38`, `V40`, die Holm-Bonferroni-Familie `{V38, V40}` sowie die reale `#1589`-Basis-Wiederverwendung in `#1528` sind `NOT_RUN` (`UNKNOWN`).
  - Reale Chulane-Paar-Streuung für kleine `2`- und `4`-Karten-Tausche (`V38`/`V40`, Bezug `#1590`) bleibt `UNKNOWN` (gemessen wurden nur `0`-Tausch `N36` mit `0,0000` und `9`-Länder-Kontrast `P27` mit `sd_pair = 0,4437`, `sd_seed_mean = 0,2447`).
  - Die manuelle 240-Entscheidungs-Kalibrierung aus `#1524` bleibt nach E15 Q8 `NOT_RUN` (die `320` lokalen Audit-Mitschnitte liegen jedoch unter `<studio-data-dir>/runs_1528_20261125/pilot_audit/` bereit).
