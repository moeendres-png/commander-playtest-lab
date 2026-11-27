# `#1528` (Option A1): Positivkontrolle `P27` vs. `B36` bestanden (`360` rotierte Paare, `SIMULATED_RESULT`)

- **Datum:** 2026-11-27 · **Refs:** `#1528`, `#1167`, `#1521`, `#1524`, `#1589`, `#1590`
- **Vorab-Pläne:** [chulane_land_axis_plan_1528_20261124.md](chulane_land_axis_plan_1528_20261124.md), [chulane_land_axis_a1_plan_1528_20261127.md](chulane_land_axis_a1_plan_1528_20261127.md) (vor Spielbeginn auf `feat/chulane-land-axis-a1-1528` @ `c9613342f` gepusht), Vorgängerlauf [chulane_land_axis_controls_1528_20261125.md](chulane_land_axis_controls_1528_20261125.md) (`N36` `PASS`, `P27` bei `N = 80` `FAIL_CLOSED`)
- **Owner-Entscheid:** 2026-11-27 (`#1528` Kommentar `7214899130`, **Option A1**).
- **Einordnung:** **`SIMULATED_RESULT`** (`LOCAL_OBSERVED` am Owner-PC unter WSL2 in isoliertem Datenordner `<studio-data-dir>/runs_1528_a1/`, **kein Qualifikationsbeleg**; Gewicht in Tierliste `0`; `AGENTS.md` §1, §4).

---

## 1. Umgebung, Provenienz & Systemlast

- **Basis-Commit (`main`):** `f13666f2c2288ab242fba7e4681a15e55ea0466b` · **Paketpfad:** `/home/moeen/commander-playtest-lab/src/commander_lab/__init__.py`
- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`)
- **Bridge-JAR:** `xmage-engine-bridge.jar`, SHA-256 `33eead68b50b04ae68c966b130ffbb38b393e3eb9f2c279c55febb1d18f2802f`, Zustand **`BRIDGE_AHEAD_OF_QUALIFICATION`** (`covered_by_sealed_epoch = false`)
- **Laufzeitkonfiguration:** Java `21` + passendes AppCDS-Archiv, `--workers 6`, `--games-per-jvm 20`, `--rotate-seats` (`4` Sitze je Seed), `--look-every 360` (feste Stichprobe), `--record-pilot-audit` (`720/720` Partien mitgezeichnet), `COMMANDER_LAB_STUDIO_SERIES_POOL = 0` (`OFF`).
- **Pilot-Fingerabdruck:** `51818f6859adb2aef8d79f879934f1e7efe6564a0be8fad1d2c896f0242b4a9f`
- **Tisch & Decks:** `B36` (`custom/chulane`, `36` Länder, JSON SHA-256 `4ca6e965cbb7b179278cf8440b92bc10624d4a1d6da94a1740f4d0e494783d87`) vs. `P27` (`custom/chulane_p27`, `27` Länder, JSON SHA-256 `e3656db5c01fa0cc9f4de6854ce5fdc97058135c1e85f88ea312472b24490de8`) gegen `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`.
- **Systemlast (`uptime` / `free -m`) & Wandzeit:**
  - Vor Lauf (`2026-11-27T14:08:48+01:00`): `load average: 3.67, 2.50, 1.50`, `Mem available: 10677 MiB`, `Swap used: 172 MiB`.
  - Während Lauf (nach ~60 min bei `630/720`): `load average: 4.06, 4.07, 4.15`, `Mem available: 6609 MiB`, `Swap used: 687 MiB`.
  - Nach Lauf (`2026-11-27T15:18:41+01:00`): `load average: 1.04, 1.79, 2.99`, `Mem available: 12243 MiB`, `Swap used: 681 MiB`.
  - **Gesamtwandzeit:** **`4193 s`** (`69 min 53 s`) für `720` Partien (`~618 Partien/h`).
- **Lokale Artefakte (`<studio-data-dir>/runs_1528_a1/`, nicht im Repo):**
  - `p27_a1_summary.json`: SHA-256 **`4fde1b554156a3d76e12f93766043273a38b22c91b707a11c9ed369b8966005a`**
  - `identity_probe.json`: SHA-256 **`fcb3bf9c9693ca88a7430ad231020248b0ca6b0888d1f4a770d1cea7ad237962`**
  - `720/720` Spielprotokolle unter `games/` + `720/720` Pilot-Audit-Mitschnitte unter `pilot_audit/`.

---

## 2. Gepaarte Identitätsprobe (`scripts/check_studio_series_identity.py --mode paired`)

Vor dem Hauptlauf auf den ersten `5` frischen Seeds des A1-Blocks (`20000..20004`, `5` Paare = **`10` Partien**, je einmal einzeln in separater JVM und gepaart mit `workers=2`, `games_per_jvm=4`, `pool=null`):

- **Ergebnis:** **`10/10` identisch (`IDENTITY PASS`)** — alle `10` Partien mit exakt übereinstimmendem `semantic_transcript_sha256`, `winner_seats` und `decision_count`.
- **Durchsatz-Vergleich (nur Messung, kein Beleg):** Einzel-JVMs `235,6 s` Wall (`577,4 s` CPU) vs. gepaart `113,4 s` Wall (`281,1 s` CPU).

---

## 3. Hauptergebnis `P27` vs. `B36` (`N = 360` rotierte Paare = `90` Seed-Cluster)

| Kennzahl | Messwert (`n/N`, `SIMULATED_RESULT`) |
|---|---|
| **Seeds (disjunkt zum Vorlauf)** | `20000..20089` (`90/90` Seed-Cluster × `4` Startplätze) |
| **Paare abgeschlossen / zensiert** | **`360/360`** (`720/720` Partien regulär beendet, **`0/360` zensiert**, `0` Fehler) |
| **Basis-Siegrate (`B36`, `36` Länder)** | **`45/360` = `12,5 %`** (`95-%-Wilson [9,5 %; 16,3 %]`, `1.259.448` Entsch.) |
| **Varianten-Siegrate (`P27`, `27` Länder)** | **`25/360` = `6,9 %`** (`95-%-Wilson [4,8 %; 10,1 %]`, `1.227.198` Entsch.) |
| **Differenz (`P27 − B36`)** | **`−5,556 pp`** |
| **`95-%`-Cluster-t-Intervall (`df = 89`)** | **`[−9,980; −1,131] pp`** (`α = 0,05`, `status = DECIDED`, `answer = NOT_ABOVE`) |
| **Nachweisgrenze (`detectable_difference_pp`)** | **`6,308 pp`** (Vorlauf bei `N = 80`: `16,162 pp`) |
| **Diskordanz (`V : B`, gebunden)** | **`66/360` (`18,33 %`** vs. `17,71 %` unabh.), **`23 : 43`**, `294` gebunden |
| **Exakter Vorzeichentest (`p`)** | **`0,018657`** |
| **Cluster-Streuung (`#1590`)** | `sd_pair = 0,4251`, `sd_seed_mean = 0,2113`, `se_cluster = 2,23 pp` vs. `se_unclustered = 2,24 pp`, **`DEFF = 0,988`** |
| **Vorab-Urteil (`oberes CI < 0,0 pp`)** | **`PASS`** (`−1,131 pp < 0,0 pp`) |

- **Sitzaufschlüsselung `P27` vs. `B36` nach Chulane-Startplatz (`n = 90/90` Paare je Platz):**
  - Sitz `0`: `B36 = 10/90` (`11,1 %`) → `P27 = 3/90` (`3,3 %`)
  - Sitz `1`: `B36 = 15/90` (`16,7 %`) → `P27 = 5/90` (`5,6 %`)
  - Sitz `2`: `B36 = 10/90` (`11,1 %`) → `P27 = 9/90` (`10,0 %`)
  - Sitz `3`: `B36 = 10/90` (`11,1 %`) → `P27 = 8/90` (`8,9 %`)
  - Auf allen vier Startplätzen schneidet `P27` schlechter ab als `B36`.

---

## 4. Exakte hypergeometrische Gegenprobe (`first_dealt_hand`, `N = 99`, `n = 7`)

Auswertung über alle `720/720` abgeschlossenen Partien (`360` je Arm, ermittelt aus `games/*.jsonl.gz`):

| Arm | `K` Länder | Stichprobe (`n/N`) | Beobachteter Mittelwert (Erwartet, `z`) | Beobachtete SD (Erwartet) | `P(0–1 Land)` obs vs. exp | `P(2–4 Länder)` obs vs. exp | `P(5+ Länder)` obs vs. exp | `chi2 (df=2)` | `p` | Urteil |
|---|---:|---:|---|---:|---|---|---|---:|---:|---|
| **`B36`** | `36` | `360/360` | `2,5806` (`2,5455`, `z = +0,54`) | `1,2751` (`1,2332`) | `72/360` (`20,00 %` vs. `20,15 %`) | `262/360` (`72,78 %` vs. `74,03 %`) | `26/360` (`7,22 %` vs. `5,83 %`) | `1,284` | **`0,5262`** | **`PASS`** |
| **`P27`** | `27` | `360/360` | `1,8806` (`1,9091`, `z = −0,47`) | `1,1800` (`1,1417`) | `147/360` (`40,83 %` vs. `38,23 %`) | `206/360` (`57,22 %` vs. `60,23 %`) | `7/360` (`1,94 %` vs. `1,54 %`) | `1,572` | **`0,4557`** | **`PASS`** |

Beide Arme stimmen exakt mit der hypergeometrischen Erwartung überein (`p >= 0,4557 >= 0,01`).

---

## 5. Gültigkeitsblock (`validity_block`): Sitzkurve & Pilot-Auslassungen (`#1524`)

- **Sitzkurve (`720/720` Partien vs. Playgroup-Referenz `29,1 / 25,7 / 23,6 / 21,5 %`, `n = 300.240`, Casual/Selbstangabe/ohne Unentschieden):**
  - Sitz `1`: `191,0/720` = **`26,5 %`** `[23,4 %; 29,9 %]` (Ref. `29,1 %`)
  - Sitz `2`: `196,0/720` = **`27,2 %`** `[24,1 %; 30,6 %]` (Ref. `25,7 %`)
  - Sitz `3`: `159,0/720` = **`22,1 %`** `[19,2 %; 25,3 %]` (Ref. `23,6 %`)
  - Sitz `4`: `171,0/720` = **`23,8 %`** `[20,8 %; 27,0 %]` (Ref. `21,5 %`)
  *(Summe `717,0/720`; `3/720` Partien endeten ohne Einzelsieger/Unentschieden.)*
- **Objektive Pilot-Auslassungen (`720/720` Partien auditiert, `1.609.029` auditiert gezählte Anfragen / `2.486.646` Gesamtentscheidungen):**
  - Gesamt: **`308/28.619` (`1,08 %`)**
  - `land_play`: **`290/26.033` (`1,11 %`)**
  - `cast_commander` (`T <= 6`): **`18/2.586` (`0,70 %`)**

---

## 6. Gesamtbewertung Kontrolltor & nächste Schritte (`#1528`, `needs:owner`)

- **Kontrolltor komplett `PASS`:** Negativkontrolle `N36` (`0,0 pp`, `80/80` im Vorgängerlauf), Identitätsprobe A1 (`10/10` auf `20000..20004`), Positivkontrolle `P27` (`−5,556 pp`, `95-%-CI [−9,980; −1,131] pp < 0,0 pp`, `360/360`) und Hypergeometrie (`p = 0,5262` / `0,4557`) sind alle bestanden.
- **Offen (`NOT_RUN` / Owner-Entscheid):**
  - Die Hauptarme **`V38`** (`38` Länder) und **`V40`** (`40` Länder) auf Seeds `12000+` sind weiterhin **`NOT_RUN`**. Hinweis zur Budgetplanung (`#1590`): Mit `90` Seed-Clustern (`360` Paaren, ~`70 min`) wurde eine Nachweisgrenze von **`6,308 pp`** erreicht; für die im Vorab-Plan genannte Umbauschwelle `+3,0 pp` läge das grob erforderliche Budget bei vergleichbarer Streuung (`sd_seed_mean ~ 0,21`) im Bereich von ~`400` Seed-Clustern (~`1.600` Paaren) bzw. mehrstündigem Lauf (ohne `--reuse-baseline` bzw. mit `#1589` ca. Faktor `1,5×` gesamt für zwei Arme).
  - Der abschließende Owner-Satz **„sinnvoll / nicht sinnvoll“** (Akzeptanzkriterium 7) bleibt offen (`needs:owner`).
