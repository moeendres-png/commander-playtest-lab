# Hardware-Durchsatz-Baseline (2P, 4P, 6P, 8P) auf echter XMage-Engine (2026-11-27)

Refs #1167, #1858.

Alle Zahlen sind lokale Messungen auf dem Owner-PC (`SIMULATED_RESULT`, Gewicht `simulation = 0`, kein Qualifikations- oder CI-Beleg, Zustand `BRIDGE_AHEAD_OF_QUALIFICATION`, `covered_by_sealed_epoch: false`).

## 1. Umgebung & Provenienz

- **Basis-Commit (`origin/main`):** `f13666f2c2288ab242fba7e4681a15e55ea0466b` (per `git fetch origin` unmittelbar vor Laufbeginn geprüft)
- **Paketpfad (`commander_lab.__file__`):** `/home/moeen/code/cpl-serien/src/commander_lab/__init__.py`
- **Engine-Pin (`config/rules_engines.json`):** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (XMage `1.4.62`)
- **System / Hardware:** Linux WSL2 (`6.6.87.2-microsoft-standard-WSL2 x86_64`), `AMD Ryzen 7 7700 8-Core Processor` (`16` logische CPUs), `15 GiB` RAM, Python `3.12.14`, OpenJDK `21.0.13.1`
- **Pool-Schalter:** `COMMANDER_LAB_STUDIO_SERIES_POOL=0` (AUS)
- **Kohorten-Trennung:** Die eigenen `2P`/`4P`-Messungen (Bridge-JAR aus `release-artifacts.yml` Lauf `45995268152`, SHA-256 `b184148260a46865092bb105bf1fd566af1cc9e349c173ebe19c39394dc38d5f`) und die `6P`/`8P`-Grenzproben aus `#1858` Kommentar `7218241325` (Bridge-JAR SHA-256 `33eead68b50b04ae68c966b130ffbb38b393e3eb9f2c279c55febb1d18f2802f`) werden als getrennte Messreihen geführt und nicht gemischt.

## 2. `2P` und `4P` Batch- & Paired-Durchsatz (`n = 5/5` Wiederholungen je Zelle)

- **Datenordner (außerhalb des Repos):** `$HOME/studio-serien/meas_e3` (mit AppCDS-Archiv zu JAR `b1841482…`)
- **Decks:** `custom/chulane-b36` (`36` Länder) vs. `custom/chulane-v38` (`38` Länder) gegen Precons (`2026_lorehold_spirit`, `2024_animated_army`, `2022_token_triumph`)
- **Modi:**
  - `studio play-batch`: sequenziell in `1` Bridge-JVM (`2P`: `4` Partien/Wdh. = `20/20` Partien; `4P`: `8` Partien/Wdh. = `40/40` Partien)
  - `studio compare-decks --rotate-seats --workers 4 --games-per-jvm 8`: `4` parallele Worker (`2P`/`4P`: je `4` Paare = `8` Partien/Wdh., jeweils `20/20` Paare = `40/40` Partien, `0` zensiert)
- **Rohbericht (lokal):** `$HOME/studio-serien/meas_e3/e3_baseline_report.json` (`SHA-256: 6ddc0b7264756479cfb0196bdf03c5d19f33b92ca4cfcaa88ebab367c4414d6d`)

### Zusammenfassung (`n = 5/5` je Zeile, `0` Fehler, `0` Zensuren)

| Modus & Sitze | Umfang / Wdh. | Wandzeit Median (`s`) | Wandzeit Mittel ± SD (`s`) | Min–Max (`s`) | Durchsatz Median | Durchsatz Mittel ± SD | Min–Max Durchsatz | Load-Bereich (`1 min`) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **Batch `2P`** (`1` JVM) | `4` Partien (`n = 5/5`, `20/20` Partien) | `32,443` | `35,138 ± 6,451` | `30,399–45,981` | `443,9 Partien/h` (`8,11 s/P`) | `419,48 ± 66,064 Partien/h` | `313,2–473,7 Partien/h` | `0,26 → 4,41` |
| **Batch `4P`** (`1` JVM) | `8` Partien (`n = 5/5`, `40/40` Partien) | `158,311` | `162,055 ± 16,502` | `139,260–181,922` | `181,9 Partien/h` (`19,79 s/P`) | `179,24 ± 18,729 Partien/h` | `158,3–206,8 Partien/h` | `4,41 → 2,16` |
| **Paired `2P`** (`4` Worker) | `4` Paare (`n = 5/5`, `20/20` Paare) | `19,178` | `20,751 ± 3,348` | `16,910–24,320` | `750,8 Paare/h` (`4,80 s/Paar`) | `708,44 ± 112,846 Paare/h` | `592,1–851,6 Paare/h` | `2,16 → 5,83` |
| **Paired `4P`** (`4` Worker) | `4` Paare (`n = 5/5`, `20/20` Paare) | `84,514` | `75,106 ± 15,108` | `53,288–87,630` | `170,4 Paare/h` (`21,13 s/Paar`) | `199,04 ± 45,871 Paare/h` | `164,3–270,2 Paare/h` | `5,83 → 6,71` |

### Einzelmessungen (`2P` & `4P`)

| Modus | Sitze | Wdh. | Geplant / Fertig | Wandzeit (`s`) | s / Einheit | Durchsatz / h | Load vor → nach | Artefakt SHA-256 (Kürzel) |
|---|---:|---:|---|---:|---:|---:|---|---|
| Batch | `2` | `1` | `4/4` (`0` err) | `45,981` | `11,495 s/Partie` | `313,2 Partien/h` | `0,26 → 1,99` | `6a122688…` (Log `s60100`) |
| Batch | `2` | `2` | `4/4` (`0` err) | `30,399` | `7,600 s/Partie` | `473,7 Partien/h` | `1,99 → 2,14` | `4d988b65…` (Log `s60200`) |
| Batch | `2` | `3` | `4/4` (`0` err) | `30,847` | `7,712 s/Partie` | `466,8 Partien/h` | `2,14 → 2,79` | `3f45c5f6…` (Log `s60300`) |
| Batch | `2` | `4` | `4/4` (`0` err) | `36,018` | `9,004 s/Partie` | `399,8 Partien/h` | `2,79 → 3,48` | `905e9706…` (Log `s60400`) |
| Batch | `2` | `5` | `4/4` (`0` err) | `32,443` | `8,111 s/Partie` | `443,9 Partien/h` | `3,48 → 4,41` | `8f4c1bcc…` (Log `s60500`) |
| Batch | `4` | `1` | `8/8` (`0` err) | `158,311` | `19,789 s/Partie` | `181,9 Partien/h` | `4,41 → 2,60` | `a4ff17cb…` (Log `s61100`) |
| Batch | `4` | `2` | `8/8` (`0` err) | `139,260` | `17,407 s/Partie` | `206,8 Partien/h` | `2,60 → 2,08` | `acce41ff…` (Log `s61200`) |
| Batch | `4` | `3` | `8/8` (`0` err) | `173,720` | `21,715 s/Partie` | `165,8 Partien/h` | `2,08 → 2,32` | `419c257b…` (Log `s61300`) |
| Batch | `4` | `4` | `8/8` (`0` err) | `157,062` | `19,633 s/Partie` | `183,4 Partien/h` | `2,32 → 2,32` | `58c86fc1…` (Log `s61400`) |
| Batch | `4` | `5` | `8/8` (`0` err) | `181,922` | `22,740 s/Partie` | `158,3 Partien/h` | `2,32 → 2,16` | `7697d26b…` (Log `s61500`) |
| Paired | `2` | `1` | `4/4` (`0` cens) | `19,178` | `4,795 s/Paar` | `750,8 Paare/h` (`1501,7 P/h`) | `2,16 → 3,78` | `9c249b9b…` (`out_json`) |
| Paired | `2` | `2` | `4/4` (`0` cens) | `24,240` | `6,060 s/Paar` | `594,1 Paare/h` (`1188,1 P/h`) | `3,78 → 4,06` | `8f091860…` (`out_json`) |
| Paired | `2` | `3` | `4/4` (`0` cens) | `16,910` | `4,227 s/Paar` | `851,6 Paare/h` (`1703,1 P/h`) | `4,06 → 4,94` | `9f4cbd62…` (`out_json`) |
| Paired | `2` | `4` | `4/4` (`0` cens) | `24,320` | `6,080 s/Paar` | `592,1 Paare/h` (`1184,2 P/h`) | `4,94 → 5,07` | `abdf0c8f…` (`out_json`) |
| Paired | `2` | `5` | `4/4` (`0` cens) | `19,109` | `4,777 s/Paar` | `753,6 Paare/h` (`1507,2 P/h`) | `5,07 → 5,83` | `f2c02bf3…` (`out_json`) |
| Paired | `4` | `1` | `4/4` (`0` cens) | `84,836` | `21,209 s/Paar` | `169,7 Paare/h` (`339,5 P/h`) | `5,83 → 5,70` | `494d23ce…` (`out_json`) |
| Paired | `4` | `2` | `4/4` (`0` cens) | `87,630` | `21,908 s/Paar` | `164,3 Paare/h` (`328,7 P/h`) | `5,70 → 5,09` | `a5ce82d6…` (`out_json`) |
| Paired | `4` | `3` | `4/4` (`0` cens) | `84,514` | `21,129 s/Paar` | `170,4 Paare/h` (`340,8 P/h`) | `5,09 → 4,73` | `72dba112…` (`out_json`) |
| Paired | `4` | `4` | `4/4` (`0` cens) | `53,288` | `13,322 s/Paar` | `270,2 Paare/h` (`540,5 P/h`) | `4,73 → 5,78` | `c080879b…` (`out_json`) |
| Paired | `4` | `5` | `4/4` (`0` cens) | `65,262` | `16,315 s/Paar` | `220,6 Paare/h` (`441,3 P/h`) | `5,78 → 6,71` | `46c586f7…` (`out_json`) |

## 3. Referierte `6P`- und `8P`-Grenzproben (`#1858`, eigene Kohorte — nicht wiederholt)

Quelle: `#1858` Kommentar `7218241325` (`main` `f13666f2c2288ab242fba7e4681a15e55ea0466b`, Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`, Bridge-JAR SHA-256 `33eead68b50b04ae68c966b130ffbb38b393e3eb9f2c279c55febb1d18f2802f` mit AppCDS, Systemlast `0,80 → 2,07 → 1,08`, `Swap`: `130 → 129 MiB`):

| Probe | Pfad / Setup | Umfang (`n/N`) | Wandzeit / Mittel | Median | Peak RSS max | Anmerkungen / `NOT_RUN` |
|---|---|---|---:|---:|---:|---|
| **`6P`** | `studio play` (`chulane_current` + 5 Precons, sequenzielle Einzel-JVMs, Seeds `1–5`) | `5/5 finished` (`0` err) | Mittel `37,30 s/Partie` | `35,46 s/Partie` | `1096,95 MiB` | Interaktiver PLAY-Sitz in Web-UI: `NOT_RUN` |
| **`8P`** | `studio play-batch` (`chulane_current` + 7 Precons, `1` JVM mit `SerialGC` + `AppCDS`, Seeds `1–5`) | `5/5 finished` (`0` err) | Gesamt `278,78 s` · Mittel `55,38 s/Partie` | `59,21 s/Partie` | `1135,58 MiB` | `0..7` Sitze spielbar; Batch-Web-UI `#1858`: `NOT_RUN` |
