# `#1528`: Ergebnisbericht Hauptarme – Chulane Landzahl-Achse (`V38` & `V40` vs. `B36`, `240` Paare je Arm, 2026-11-27)

Refs #1528, #1167, #1589, #1871.

Alle Zahlen sind lokale Echt-Engine-Messungen am Owner-PC (`SIMULATED_RESULT`, Gewicht `simulation = 0`, kein Qualifikations- oder CI-Beleg, Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).

## 1. Umgebung, Provenienz & Vorab-Plan-Bindung

- **Vorab-Plan (Vertrag vor dem ersten Spiel):** [`chulane_land_axis_plan_1528_20261124.md`](chulane_land_axis_plan_1528_20261124.md)
- **Kontrolltor-Basis:** `N36` + Identitätsprobe (`chulane_land_axis_controls_1528_20261125.md`) sowie geschärfte Positivkontrolle Option A1 (`P27` vs. `B36`, `360` Paare, PR `#1871`, oberes `95-%`-CI `-1,131 pp < 0 pp` → alle Kontrollen `PASS`)
- **`origin/main` vor Laufbeginn & Bericht:** `f13666f2c2288ab242fba7e4681a15e55ea0466b`
- **`commander_lab.__file__`:** `$HOME/code/cpl-serien/src/commander_lab/__init__.py`
- **Engine-Pin (`config/rules_engines.json`):** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage `1.4.62`)
- **Bridge-JAR (`release-artifacts.yml` Lauf `45995268152`, 2026-11-27):** SHA-256 `b184148260a46865092bb105bf1fd566af1cc9e349c173ebe19c39394dc38d5f` (AppCDS aktiv)
- **System & Einstellungen:** Linux WSL2, `AMD Ryzen 7 7700` (`16` logische CPUs), `COMMANDER_LAB_STUDIO_SERIES_POOL=0`, `--workers 6 --games-per-jvm 20 --rotate-seats --record-pilot-audit --reuse-baseline`
- **Datenordner (außerhalb des Repos):** `$HOME/studio-serien/runs_1528_main` (`v38_summary.json` SHA-256 `f63bcb53a0a90e6699887ceef201882568cc774ffdcda4f909aea7210db24dd0`, `v40_summary.json` SHA-256 `32cba59b3e355243fb82bac2644e8db2fc078ae2cd466bb5c0382a2b510eccbd`, `main_arms_analysis.json` SHA-256 `41ee7a4a58b05298f07b4c7c1d813d9d0005cbf2e1143fadb648c216b625449b`)

## 2. Gepaarte Hauptarme (`Seeds 12000..12059`, `60` Cluster × `4` Sitze = `240` Paare je Arm)

Tisch: `custom/chulane-{b36,v38,v40}` gegen `precon/2026/lorehold_spirit`, `precon/2024/animated_army`, `precon/2022/token_triumph`.
Pilot-Fingerabdruck über alle Partien: `51818f6859adb2aef8d79f879934f1e7efe6564a0be8fad1d2c896f0242b4a9f`.

| Kennzahl | Arm A (`V38`: `38` Länder vs. `B36`) | Arm B (`V40`: `40` Länder vs. `B36`) |
|---|---|---|
| **Status / Stoppgrund** | `NOT_DECIDED` (`BUDGET_EXHAUSTED`) | `NOT_DECIDED` (`BUDGET_EXHAUSTED`) |
| **Paare abgeschlossen (`n/N`, zensiert)** | `240/240` (`0` zensiert, `0/480` Partiefehler) | `240/240` (`0` zensiert, `0/480` Partiefehler) |
| **Basis-Siegrate `B36` (`95-%`-Wilson-CI)** | `33/240 = 13,75 %` (`[9,96 %; 18,68 %]`) | `33/240 = 13,75 %` (`[9,96 %; 18,68 %]`) |
| **Varianten-Siegrate (`95-%`-Wilson-CI)** | `27/240 = 11,25 %` (`[7,85 %; 15,87 %]`) | `45/240 = 18,75 %` (`[14,32 %; 24,17 %]`) |
| **Differenz (`Variante − B36`)** | **`−2,500 pp`** | **`+5,000 pp`** |
| **`95-%`-Cluster-t-CI (`df = 59`)** | `[−8,289; +3,289] pp` | `[−2,014; +12,014] pp` |
| **Cluster-t-Statistik / `p` (zweiseitig)** | `t = −0,8642`, `p = 0,390980` | `t = +1,4264`, `p = 0,159037` |
| **Holm-Bonferroni-`p` (`2`-Arm-Familie)** | **`0,390980`** | **`0,318074`** |
| **Nachweisgrenze (`detectable_difference_pp`)** | `8,241 pp` | `9,986 pp` |
| **Streuung & Clustering** | `sd_pair = 0,4380`, `sd_seed_mean = 0,2241`, `SE_cluster = 2,893 pp`, `DEFF = 1,047` | `sd_pair = 0,5069`, `sd_seed_mean = 0,2715`, `SE_cluster = 3,505 pp`, `DEFF = 1,148` |
| **Diskordante Paare (`share` vs. `indep`)** | `46/240 = 0,1917` vs. `0,2191` (`20 V : 26 B`, Vorzeichen-`p = 0,461391`) | `62/240 = 0,2583` vs. `0,2734` (`37 V : 25 B`, Vorzeichen-`p = 0,161881`) |
| **`--reuse-baseline` (`#1589`)** | `0` reused, `240` played | `216` reused (`chulane-1528-v38`), `24` nachgespielt, `24/24` Stichproben `PASS` (`0` failed) |
| **Wandzeit & Last (`1 min`)** | `2895 s` (`Load 0,27 → 1,04`) | `1786 s` (`Load 0,74 → 1,08`) |

### Sitzaufschlüsselung (`n = 60` Paare je Startplatz)

| Startplatz (`seat`) | `B36` Siege | `V38` Siege (`Diff`) | `V40` Siege (`Diff`) |
|---|---:|---:|---:|
| `0` | `10/60` | `9/60` (`−1,67 pp`) | `17/60` (`+11,67 pp`) |
| `1` | `7/60` | `4/60` (`−5,00 pp`) | `9/60` (`+3,33 pp`) |
| `2` | `6/60` | `10/60` (`+6,67 pp`) | `12/60` (`+10,00 pp`) |
| `3` | `10/60` | `4/60` (`−10,00 pp`) | `7/60` (`−5,00 pp`) |

## 3. Exakte hypergeometrische Gegenprobe (`first_dealt_hand`, `N = 99`, `n = 7`)

Aus den ersten Mulligan-Frames (`hand_count = 7`, `library_count = 92`) aller `240` Partien je Deck (`0-1`, `2-4`, `5+` Länder):

| Deck (`K`) | Geprüfte Hände | Mittel beob. / erw. | `z` | Beob. `{0–1 / 2–4 / 5+}` | Erw. `{0–1 / 2–4 / 5+}` | `chi2 (df=2)` | `p`-Wert | Status |
|---|---:|---:|---:|---|---|---:|---:|---|
| `B36` (`36`) | `240/240` | `2,7500 / 2,5455` | `+2,570` | `39 / 186 / 15` | `48,35 / 177,66 / 13,98` | `2,2743` | `0,3207` | `PASS` |
| `V38` (`38`) | `240/240` | `2,8833 / 2,6869` | `+2,441` | `27 / 188 / 25` | `41,05 / 181,22 / 17,73` | `8,0458` | `0,0179` | `PASS` |
| `V40` (`40`) | `240/240` | `2,9583 / 2,8283` | `+1,602` | `24 / 188 / 28` | `34,56 / 183,34 / 22,10` | `4,9166` | `0,0856` | `PASS` |

## 4. Gültigkeitsblock (`validity_block`)

- **Sitzkurve (`V38`, `480/480` Partien):** Sitz `1–4` = `26,2 %` (`126/480`), `24,4 %` (`117/480`), `25,6 %` (`123/480`), `23,3 %` (`112/480`).
- **Sitzkurve (`V40`, `480/480` Partien):** Sitz `1–4` = `25,8 %` (`124/480`), `24,4 %` (`117/480`), `24,0 %` (`115/480`), `25,6 %` (`123/480`).
- **Pilot-Auslassungen (`--record-pilot-audit`):**
  - `V38` (`480/480` auditiert, `1.144.832` Entsch.): **`236/19.748` (`1,20 %`)** (`land_play`: `231/17.991` = `1,28 %`, `cast_commander T<=6`: `5/1.757` = `0,28 %`).
  - `V40` (`480/480` auditiert, `1.147.317` Entsch.): **`226/19.836` (`1,14 %`)** (`land_play`: `224/18.079` = `1,24 %`, `cast_commander T<=6`: `2/1.757` = `0,11 %`).
- **Gültigkeitsgrenze:** Gilt ausschließlich für diesen festen 4-Sitz-Precon-Tisch, die eingesetzten KI-Piloten (`51818f68…`), Engine-Pin `f4d12f6e…` und Bridge-JAR `b1841482…` (`SIMULATED_RESULT`); keine Aussage über menschliches Spiel.

## 5. Bewertung gegen die Vorab-Entscheidungsschwelle (`needs:owner`)

- **Vorab-Schwelle (`chulane_land_axis_plan_1528_20261124.md` §1):** Umbau nur, wenn sowohl das `95-%`-CI vollständig über `0 pp` liegt **als auch** die Punktschätzung `>= +3 pp` erreicht.
- **Befund:**
  - **`V38` (`38` Länder):** Punktschätzung `−2,500 pp`, `95-%`-CI `[−8,289; +3,289] pp` (Holm `p = 0,391`) → **kein nachweisbarer Vorteil gegenüber `B36` (`n = 240`, nachweisbar wären `8,24 pp`)**.
  - **`V40` (`40` Länder):** Punktschätzung **`+5,000 pp`** (liegt deskriptiv über `+3 pp`), aber `95-%`-CI **`[−2,014; +12,014] pp`** schließt `0` noch ein (Holm `p = 0,318`) → **bei `n = 240` Paaren statistisch `NOT_DECIDED` (nachweisbar wären `9,99 pp`)**.
- **Folgeschritt (`needs:owner`):** Akzeptanzkriterium 7 („sinnvoll / nicht sinnvoll“) sowie Entscheidung offen, ob das `240`-Paare-Ergebnis (`V38` negativ/null, `V40` `NOT_DECIDED` mit `+5,0 pp`-Signal) so stehen bleibt oder `V40` vs. `B36` auf einem höheren disjunkten Seed-Block verlängert werden soll.
