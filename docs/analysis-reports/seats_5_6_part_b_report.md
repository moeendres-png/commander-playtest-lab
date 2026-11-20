# 5 und 6 Sitze, Teil B (`#1661`): Echt-Engine-Läufe (B0–B7) am Owner-PC (WSL2)

- **Datum:** 2026-11-20 · **Refs:** `#1661`, `#1656`, `#1612`, `#1652`, `#1698`, `#1628`, `#1715`
- **Einordnung:** `SIMULATED_RESULT` (lokale Owner-PC-Echt-Engine-Messung unter WSL2, Rohlogs außerhalb des Repos, **kein Qualifikationsbeleg**; `AGENTS.md` §4).
- **Keine Freigabe:** `launch.MAX_RELEASED_SEATS = 4` (`src/commander_lab/studio/launch.py:39`), `OPPONENT_COUNTS = [1, 2, 3]` (`src/commander_lab/studio/static/partie.js:12`), `PAIRED_RELEASED_SEATS = 4` (`src/commander_lab/studio/static/paired.js:16`) und die Serien-/`compare-decks`-Sperre bleiben unverändert. Für alle `5`- und `6`-Sitz-Läufe mit `compare-decks` wurde `--allow-unreleased-seats` ausschließlich lokal auf der CLI gesetzt.
- **Basisstand & Engine-Pin:** Alle `313` Echt-Engine-Läufe auf `main` @ `5b406c86562cb9010584aed6d4e8433f5a33ecec` (Branch ohne Bridge- oder Pin-Änderung auf aktuellen `main` nachgezogen), Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json`), Release-Bridge-JAR `840e50abefdaa023072c8c03953e8689a6189a96d3837c5f0c72baf6f8086f6f` (lokaler Owner-PC-Build), Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (gesiegelte Epoche `5bd29ab6f318-c6942825587a`).
- **Gerät, Bridge-Start & lokale Ergebnis-Digests (WSL2):** `AMD Ryzen 7 7700 8-Core Processor` (`8C/16T`, `3792,8 MHz`), `15.992,19 MB` (`15,6 GiB`) WSL2-RAM, `8,0 GiB` Swap, `Linux 6.6.87.2-microsoft-standard-WSL2`, `OpenJDK 21.0.13.1`, `Python 3.14.4`. Alle `313/313` Partien liefen mit `SerialGC`, `-Dh2.bindAddress=127.0.0.1`, AppCDS (`xmage-engine-bridge.jsa`, `308 MB`, SHA-256 `f36ee5ed47382681d54be2949e1fb1e136bdbe74dd72dfeaa9585547b892ea87`) und `-Dcommanderlab.fullGame.skipForcedDecisions=true` identisch zwischen `play-batch` (`FAST`/`FAST12`) und `compare-decks` (`series_engine`, Standard `gamesPerJvm=16`). Nativer Windows-Host: `UNKNOWN` / `NOT_RUN`. Rohlogs (`.jsonl.gz`) wurden nach lokaler Aggregation verworfen (kein separates Rohlog-Archiv im Repo); SHA-256 der gesicherten Owner-PC-Zusammenfassungen und Auswertungs-JSONs:
  - `aggregated_summary.json`: `dd374be3f9039cc80a02d75d0bbe02d4b2726b954aec35b0247b8086d6d38461`
  - `b2_results.jsonl`: `cb05a761f535b4fb4d39d8be4c94a1e611adf78bfcc701f444fc7a5ffa0ccdff` · `b5_exact.json`: `c68216f8d3b650bac090d6f931c1c89204827e9df2f610f3c484da867498e25e`
  - `summary_b3a.json`: `aa6fdada1f83d5e74efa2b51cc3ad502f0c0814627875298f431b6d0d19f37fa` · `summary_b3b.json`: `51c8465b92adde06a46af51e8fff83ec5b504710f93462c491dd59c8f6ca936e`
  - `summary_b6.json`: `6213b0754cbef758692692927f8d2fa4a14ff812ac5bb974aaf2e3b63405752c` · `f8-5.json`: `a7849cff3cc82655666e9d365d481a9972422f89e616190579bdf3407fb085b5` · `f8-6.json`: `f44901a14f600c6ddb2f639ca9b8cb90f43a5fa9c003ce6e471541213ed45e93`
- **Gesamtbilanz Echt-Engine (`313/313` Partien regulär beendet):** B0 (`3/3`) + B2 (`60/60`: `12` × `A4`, `12` × `A5`, `12` × `B5`, `12` × `A6`, `12` × `B6`) + B3a (`48/48`) + B3b (`80/80`) + B6 (`122/122`), `0` Spielabbrüche, `0` B7-Fork-Defekte, Swap-Delta `<= 0,0 MB`; **aber `F3` weist je einen JVM-Determinismus-Befund bei `trigger_order` aus (`#1715`)**.
- **Bezug auf Teil A:** Schnittstellentests und F1-Entwurf stehen in `docs/analysis-reports/seats_5_6_part_a_report.md`.

---

## 1. Übersicht je Nachweis (streng getrennt nach 5/6 Sitzen × SIMULATE/PLAY)

| # | Nachweis | 5 SIMULATE | 5 PLAY | 6 SIMULATE | 6 PLAY | Belege & Grenzen (`n/N`) |
|---|---|---|---|---|---|---|
| **F1** | Festlegungen `ALL`/`MULTIPLE`, 6 ohne Replay-Anspruch | Entwurf (Owner) | Entwurf (Owner) | Entwurf (Owner) | Entwurf (Owner) | Teil A Abschnitt 4; Freigabe bleibt Owner-Vorbehalt (`AGENTS.md` §8, E15 Q5). |
| **F2** | Vollständigkeit, `2` Tische × `12` Seeds (B2) | **Belegt (`SIMULATED_RESULT`)** | Schnittstelle Teil A, Echt-PLAY **`NOT_RUN`** | **Belegt (`SIMULATED_RESULT`)** | Schnittstelle Teil A, Echt-PLAY **`NOT_RUN`** | `5P`: `24/24` `finished` (`A5` `12/12`, `B5` `12/12`), `17/17` Klassen, Sitze `0..4` lückenlos. `6P`: `24/24` `finished` (`A6` `12/12`, `B6` `12/12`), `17/17` Klassen, Sitze `0..5` lückenlos. |
| **F3** | Identität (`1` gegen `W` Worker, Position in JVM, `N >= 20`, B3) | **BEFUND / FAIL (`#1715`)** | Tape-Twin **`NOT_RUN`** | **BEFUND / FAIL (`#1715`; ohne Replay)** | nicht anwendbar (F1) | B3a (`up`/`down`, `N=24`): semantisch/Sieger/Entscheidungen/Frame-Zahl `24/24` (`5P`) & `24/24` (`6P`); **ad-hoc-norm. Frames `22/24` (`5P`, Seed `11` FAIL)** bzw. `24/24` (`6P`). B3b (`w1`/`w3` Pool, `N=20`): semantisch `20/20` (`5P`, norm. Frames `20/20`) & `20/20` (`6P`), **ad-hoc-norm. Frames `19/20` (`6P`, `s2000-t5` FAIL)** — nach `AGENTS.md` §10 (`NEUTRAL`) und Teil A §5 B3 ist jede normalisierte Frame-Abweichung ein Befund/FAIL (`#1715`). |
| **F4** | Verdeckte Information je Sitz `5` und `6` | **`CODE_DERIVED` (`0` Ausnahmen in `313/313` Partien)** | Schnittstelle Teil A **`PASS (Test)`**, Live-Mensch-Browser **`NOT_RUN`** | **`CODE_DERIVED` (`0` Ausnahmen in `313/313` Partien)** | Schnittstelle Teil A **`PASS (Test)`**, Live-Mensch-Browser **`NOT_RUN`** | `audit_actor_scoped_frame` (`full_game.py:1604`) bricht fail-closed per `FullGameConformanceError` ab; `.jsonl.gz` schreibt keinen Zähler (`CODE_DERIVED`, kein separater Log-Zähler). Live-PLAY mit echtem Mensch-Sitz und Browser-UI bei `5/6` Sitzen: **`NOT_RUN`**. |
| **F5** | Acht Regelpunkte aus Plan §2 | Schnittstelle `PASS (Test)`, gezielte Szenarien **`NOT_RUN`** | wie links | Schnittstelle `PASS (Test)`, gezielte Szenarien **`NOT_RUN`** | wie links (+ 6P-Tape ausgeschlossen) | B2 liefert nur Vorkommens-Zähler im Normalspiel (z. B. `trigger_order`: `478` Frames in `5P` über Sitze `0..4`, `1023` Frames in `6P` über Sitze `0..5` ohne Fehler); dedizierte 5/6-Regelszenarien und `5P`-Replay-Tape-MATCH bleiben **`NOT_RUN` / `UNKNOWN`**. |
| **F6** | Laufzeit `4/5/6`, Speicher, Pool-Durchsatz (B4) | **Gemessen (`SIMULATED_RESULT`)**, `p99 = UNKNOWN` | **`UNKNOWN`** (nur B2 Einzel-JVM gemessen) | **Gemessen (`SIMULATED_RESULT`)**, `p99 = UNKNOWN` | **`UNKNOWN`** (nur B2 Einzel-JVM gemessen) | Tisch `A` Seeds `1–10`: Wall-Median `12,91 s` (`4P`) → `20,18 s` (`5P`, `1,56x`) → `28,73 s` (`6P`, `2,22x`); Pool `w3` (`B6`): `607,3` (`5P`) bzw. `379,2` (`6P`) Partien/h; `p99 = UNKNOWN` (`N=24 < 100`, keine Frame-Zeitstempel). |
| **F7** | Piloten: Auslassungen & Zielverteilung (B5) | **Erhoben (`SIMULATED_RESULT`)**, **keine menschl. Referenz** | nicht anwendbar (KI-Metrik) | **Erhoben (`SIMULATED_RESULT`)**, **keine menschl. Referenz** | nicht anwendbar (KI-Metrik) | Sieger/Skips je Tisch (`A4`, `A5`, `B5`, `A6`, `B6`) getrennt ausgewiesen; `declare_attacker`-Zielverteilung (`2738` `5P`- / `3026` `6P`-Frames) lag vor Log-Löschung nur aggregiert je Sitzzahl vor (**je Tisch `A5`/`B5`/`A6`/`B6` getrennt: `UNKNOWN`**). |
| **F8** | Gepaarte Serie mit voller Sitz-Rotation (B6) | **Belegt (`SIMULATED_RESULT`)** | nicht anwendbar | **Belegt (`SIMULATED_RESULT`)** | nicht anwendbar | `5P`: `25/25` Paare (`50/50` Partien, je `10` pro Sitz `0..4`, `0/25` zensiert). `6P`: `36/36` Paare (`72/72` Partien, je `12` pro Sitz `0..5`, `0/36` zensiert). **SIMULATE-UI hinter Sperre** (`2–6` Sitze planen/Rotationsblöcke/`UNKNOWN`) inzwischen mit `#1702` (`#1708`/`#1709`) auf `main`; Start weiter durch `launch.MAX_RELEASED_SEATS = 4` / `PAIRED_RELEASED_SEATS = 4` gesperrt. |

---

## 2. Schritt B0 (Rauchtest) und Tische

Alle verwendeten Tische entsprachen unverändert der Vorgabe aus Abschnitt 5 von `docs/analysis-reports/seats_5_6_part_a_report.md` (kein Precon musste ersetzt werden):

- **`A4`:** `2023_eldrazi_unbound`, `2026_lorehold_spirit`, `2024_animated_army`, `2022_token_triumph`
- **`A5`:** `A4` + `2023_veloci_ramp_tor` · **`A6`:** `A5` + `2023_blood_rites`
- **`B5`:** `2024_death_toll`, `2024_deep_clue_sea`, `2023_divine_convocation`, `2023_fae_dominion`, `2024_family_matters` · **`B6`:** `B5` + `2023_tinker_time`
- **Variante (B3b, B6):** `base = 2023_eldrazi_unbound`, `var = 2023_divine_convocation` gegen die übrigen `4` (`A5`) bzw. `5` (`A6`) Gegner.

**Ergebnis B0-Smoke (Seed `1`, `play-batch`, `FAST`, `loadavg 0,05` vor Start):**
- `A6`: `finished`, `0` unsupported, `38,22 s` Wall, `79,01 s` CPU, `3273` Frames (`5963` Entsch., `2690` übersprungen), Sieger Sitz `[4]`.
- `B6`: `finished`, `0` unsupported, `23,05 s` Wall, `46,48 s` CPU, `2679` Frames (`5065` Entsch., `2386` übersprungen), Sieger Sitz `[0]`.
- `A6` mit Variante `2023_divine_convocation`: `finished`, `0` unsupported, `27,16 s` Wall, `53,44 s` CPU, `3817` Frames (`6399` Entsch., `2582` übersprungen), Sieger Sitz `[5]`.
- Hinweis zu `games._checked_id`: Studio-Spiel-IDs akzeptieren nur Kleinbuchstaben, Ziffern, `-` und `_` (`s2b-a5-s1` statt `s2b-A5-s1`).

---

## 3. Schritt B2 (= F2 Vollständigkeit, Klassenabdeckung, F4-Live-Audit)

Sequenzielle Einzel-JVM-Läufe (`play-batch`, `FAST`, `loadavg 0,90`, Swap-Delta `0,0 MB`, Gesamtdauer `1311,3 s`):

| Tisch | Sitze | Seeds | `n/N` `finished` | Klassen aus `_SUPPORTED_CLASSES` (`17`) | Sitze in Frames | Fehler / Abbrüche |
|---|---|---|---|---|---|---|
| `A4` (Basis) | `4` | `1–12` | `12/12` | `13/17` (`amount`, `pile`, `replacement_effect`, `target_amount` kamen nicht vor) | `0..3` lückenlos | `0/12` |
| `A5` | `5` | `1–12` | `12/12` | zusammen mit `B5`: **`17/17`** | `0..4` lückenlos | `0/12` |
| `B5` | `5` | `1–12` | `12/12` | (`missing = []` über `24` Partien) | `0..4` lückenlos | `0/12` |
| `A6` | `6` | `1–12` | `12/12` | zusammen mit `B6`: **`17/17`** | `0..5` lückenlos | `0/12` |
| `B6` | `6` | `1–12` | `12/12` | (`missing = []` über `24` Partien) | `0..5` lückenlos | `0/12` |

**Beobachtete Frame-Zahlen je Klasse (B2, `N = 12` für `4P`; Summe `A+B` `N = 24` je für `5P`/`6P`, aus `aggregated_summary.json`) und Sitze:**
- `5P` (`65.384` Frames gesamt): `amount=3`, `announce_x=97`, `choice=770`, `choose_object=685`, `choose_use=1176`, `declare_attacker=2738`, `declare_blocker=1364`, `mana_payment=16260`, `mode=150`, `mulligan=170`, `multi_amount=89`, `pile=3`, `priority=39878`, `replacement_effect=18`, `target=1474`, `target_amount=31`, `trigger_order=478`. Frame-Verteilung je Sitz `0..4`: `13504 / 11824 / 12846 / 13020 / 14190`.
- `6P` (`82.014` Frames gesamt): `amount=3`, `announce_x=560`, `choice=1189`, `choose_object=881`, `choose_use=1539`, `declare_attacker=3026`, `declare_blocker=1195`, `mana_payment=17625`, `mode=114`, `mulligan=200`, `multi_amount=83`, `pile=1`, `priority=52672`, `replacement_effect=24`, `target=1847`, `target_amount=32`, `trigger_order=1023`. Frame-Verteilung je Sitz `0..5`: `13319 / 11665 / 13372 / 11514 / 17380 / 14764`.
- **F4 Live-Audit (`CODE_DERIVED`):** Alle `60/60` B2-Partien sowie alle `253/253` übrigen B0/B3/B6-Partien beendeten sich regulär ohne `FullGameConformanceError` (`audit_actor_scoped_frame` in `full_game.py:1604` läuft fail-closed bei jeder Entscheidung). Hinweis: `.jsonl.gz` schreibt das Feld `hidden_information_audit` nicht separat aus (`play.close_recorded_game`), die Ziffer `0` Verstöße ist daher `CODE_DERIVED`, nicht als Log-Feld beobachtet.

---

## 4. Schritt B3 (= F3 Identität, `N >= 20` je Sitzzahl) — **BEFUND / FAIL (`#1715`)**

### 4.1 B3a: Position in einer JVM (`gamesPerJvm=12`, auf- und absteigend gegen Einzel-JVM B2)

`FAST12` (`play-batch` mit `-Dcommanderlab.fullGame.gamesPerJvm=12`), getrennte `--data`-Ordner `up` (`1..12`) und `down` (`12..1`), identische Spiel-IDs `s2b-a{5,6}-s{1..12}`. Hinweis: `BatchRecordingRunner` (`play-batch`) schreibt im Log kein `jvm_life_id`/`position_in_jvm` (nur `GamePool` tut dies); dass jeder 12er-Lauf innerhalb eines `play-batch`-Prozesses lief, ist `CODE_DERIVED` aus dem Aufruf (`gamesPerJvm=12`, `played_events=12/12`) und den verkürzten Wandzeiten (`5P`: `175,3 s` up / `167,8 s` down vs. `245,4 s` für `12` Einzel-JVMs; `6P`: `254,7 s` up / `256,9 s` down vs. `357,2 s`).

| Sitze | Vergleich (`n/N`) | `semantic_transcript_sha256` | `winner_seats` | `decision_count` | `frame_count` | Roh-`frame_digest` | Ad-hoc-`[xxx]`-norm. `frame_digest` |
|---|---|---|---|---|---|---|---|
| `5` | `up` vs. `single` (`n/12`) | `12/12` | `12/12` | `12/12` | `12/12` | `0/12` | **`11/12`** (**FAIL: Seed `11`**) |
| `5` | `down` vs. `single` (`n/12`) | `12/12` | `12/12` | `12/12` | `12/12` | `0/12` | **`11/12`** (**FAIL: Seed `11`**) |
| `5` | **Summe `up+down` (`n/24`)** | `24/24` | `24/24` | `24/24` | `24/24` | `0/24` | **`22/24` (BEFUND)** |
| `6` | `up` vs. `single` (`n/12`) | `12/12` | `12/12` | `12/12` | `12/12` | `0/12` | `12/12` |
| `6` | `down` vs. `single` (`n/12`) | `12/12` | `12/12` | `12/12` | `12/12` | `0/12` | `12/12` |
| `6` | **Summe `up+down` (`n/24`)** | `24/24` | `24/24` | `24/24` | `24/24` | `0/24` | `24/24` |

- **Verwendetes Normalisierungswerkzeug (`P3` offengelegt) & Korrektur zu Teil A Z. 294:** Die Roh- vs. bereinigten Digests in `4.1` und `4.2` wurden **nicht** mit `frame_digest.normalize_frame` oder `semantic_replay/canonicalization.py` gerechnet, sondern mit einem Ad-hoc-Normalisierer über serialisierte Studio-Frames in `run_b3a.py:34` bzw. `run_b3b.py:24` (`re.sub(r"\[[0-9a-f]{3}\]", "[<id>]", json.dumps(frame, sort_keys=True))`). Damit ist zugleich Teil A Zeile 294 („Frames enthalten heute keine Objekt-IDs“) empirisch widerlegt: Studio-`.jsonl.gz`-Frames tragen in `mana_payment`/`choose_use`-Prompts und `replacement_effect`-Labels laufabhängige 3-Hex-Objekt-IDs (`[xxx]`), sodass der rohe Studio-`frame_digest` zwischen JVMs laufabhängig (`0/24`), aber nach Bereinigung dieser IDs reproduzierbar verglichen werden kann.
- **Befund `5P Seed 11` (FAIL nach Teil A §5 B3 / `AGENTS.md` §10):** `up` und `down` sind untereinander in `3089/3089` Frames identisch; gegen `single` weichen die **3 Frames `2204–2206`** von `3089` ab (`Quintorius, Field Historian` `+1/+0`-Fähigkeit auf Spirits), ab Frame `2207` stimmen alle verbleibenden `883` Frames wieder überein (`semantic_transcript_sha256` `44f7dcca…`, `decision_count=5008`, `winner_seats` identisch). Auslöser bei Frame `2200` (`trigger_order`, Seat `0`): zwei gleichlautende `Kaldra Compleat`-Trigger (`Phyrexian Germ Token — Whenever {this} deals combat damage to a creature, exile that permanent.`). **Ursache (korrigiert nach Review `7041054725`, Issue `#1715`):** `XmageFullGamePlayer.java:2652-2656` sortiert `trigger_order` nach `abilityLabel(ability, game)` und `zoneChangeCounter` (`"Native UUIDs must never sequence triggers"`), **nicht** nach `abilitySortKey`; bei Gleichstand beider Schlüssel bleibt die Reihenfolge der Eingangsliste erhalten. Deren Herkunft in XMage ist **`UNKNOWN`** (nicht verifiziert) und wechselt zwischen JVMs.

### 4.2 B3b: Serien-Pool `workers=1` gegen `workers=3` (`compare-decks`, `POOL=1`, `N = 20` je Sitzzahl)

`compare-decks --pairs 10 --look-every 10 --base-seed 2000 --rotate-seats --allow-unreleased-seats` (`gamesPerJvm=16`, getrennte Ordner `w1` und `w3`, `20` Partien je Lauf):

| Sitze | Vergleich (`n/N`) | `semantic_transcript_sha256` | `winner_seats` | `decision_count` | `frame_count` | Roh-`frame_digest` | Ad-hoc-`[xxx]`-norm. `frame_digest` |
|---|---|---|---|---|---|---|---|
| `5` | `w1` vs. `w3` (`n/20`) | `20/20` | `20/20` | `20/20` | `20/20` | `0/20` | `20/20` |
| `6` | `w1` vs. `w3` (`n/20`) | `20/20` | `20/20` | `20/20` | `20/20` | `0/20` | **`19/20`** (**FAIL: `s2000-t5`**) |

- **Befund `6P s2b-id-6-base-s2000-t5` (FAIL / Zustandsdivergenz, `#1715`):** Bei Frames `2596–2597` (`trigger_order`, Seat `5`) lösen `3` gleichlautende `Kaldra Compleat`-Exil-Trigger zwischen `w1` und `w3` umgeordnet auf (gleicher Gleichstands-Mechanismus in `XmageFullGamePlayer.java:2652-2656`, Herkunft der Eingangsreihenfolge `UNKNOWN`). Dadurch **lief der Spielzustand selbst auseinander**: in den Frames `2601–2606` (von `2900` Frames, ab `2607` wieder gleich) lag `Topiary Stomper` einmal bereits im Exil und einmal noch auf dem Spielfeld, während `semantic_transcript_sha256`, `winner_seats` und `decision_count` gleich blieben — der semantische Hash erfasst diese Zustandsdivergenz also nicht. Nach `AGENTS.md` §10 (`NEUTRAL`) und Teil A §5 B3 ist dies ein Befund / FAIL (als eigenständiges Gate-Issue **`#1715`** unabhängig von der Sitzzahl eröffnet).

---

## 5. Schritt B4 (= F6 Laufzeit, Speicher und Verhältnisse 5/4 sowie 6/4)

**Einzel-JVM (`play-batch`, `FAST`), streng je Tisch getrennt (`A4`/`A5`/`B5`/`A6`/`B6`, niemals über Gegnersätze gepoolt):**

| Kohorte (Tisch) | `n` | Wall Median (Min..Max) [s] | CPU Median (Min..Max) [s] | MaxRSS Median (Min..Max) [MiB] | Entsch. Median (Min..Max) | Skip Median (Min..Max) |
|---|---|---|---|---|---|---|
| `A4` (`4P`, Seeds `1–10`) | `10` | `12,91` (`8,43..26,16`) | `30,83` (`22,31..52,14`) | `749,4` (`672,2..1341,4`) | `2703,5` (`1680..4539`) | `985,0` (`607..1405`) |
| `A5` (`5P`, Seeds `1–10`) | `10` | `20,18` (`13,46..27,07`) | `42,76` (`33,73..53,10`) | `776,9` (`742,7..850,0`) | `4534,0` (`2939..5813`) | `1592,0` (`865..1994`) |
| `A6` (`6P`, Seeds `1–10`) | `10` | `28,73` (`21,08..41,39`) | `54,56` (`44,60..68,55`) | `969,4` (`933,5..1050,2`) | `6329,0` (`4839..8270`) | `2521,5` (`2182..3105`) |
| `A4` (`4P`, Seeds `1–12`) | `12` | `12,91` (`8,43..26,16`) | `30,83` (`22,31..52,14`) | `749,4` (`672,2..1341,4`) | `2703,5` (`1680..4539`) | `985,0` (`607..1491`) |
| `A5` (`5P`, Seeds `1–12`) | `12` | `20,18` (`13,46..27,07`) | `42,76` (`33,73..53,10`) | `783,0` (`742,7..850,0`) | `4665,0` (`2939..5813`) | `1697,5` (`865..1994`) |
| `B5` (`5P`, Seeds `1–12`) | `12` | `18,45` (`11,83..36,43`) | `40,20` (`29,36..61,97`) | `798,0` (`700,1..810,8`) | `4077,0` (`2505..7173`) | `1859,5` (`1344..2784`) |
| `A6` (`6P`, Seeds `1–12`) | `12` | `28,16` (`21,08..41,39`) | `53,27` (`44,60..68,55`) | `969,4` (`915,9..1050,2`) | `6329,0` (`4839..8270`) | `2498,0` (`1904..3105`) |
| `B6` (`6P`, Seeds `1–12`) | `12` | `21,75` (`15,13..48,12`) | `45,09` (`33,63..77,66`) | `800,2` (`738,6..890,6`) | `4873,0` (`3564..9451`) | `2329,0` (`1817..4132`) |

- **Hinweis zu `A4` Seeds `1–10` vs. `1–12`:** Bei `A4` lagen Seeds `11` und `12` in Wallzeit, CPU, MaxRSS, Entscheidungen und Skips jeweils beidseits des 10-Seed-Medians, sodass alle `5` Mediane unverändert blieben (nur `Skip` Max stieg von `1405` auf `1491`).
- **Skalierungsverhältnisse auf jeweils identischen Seeds (`A5`/`A6` gegen `A4`, Tisch `B` hat keine `B4`-Basis):**
  - **Seeds `1–10` (`A5`/`A6` vs. `A4`):** `5/4` Wall **`1,56x`** (Median der Seed-Paar-Ratios: `1,63x`), CPU **`1,39x`** (paarweise `1,35x`); `6/4` Wall **`2,22x`** (`2,63x`), CPU **`1,77x`** (`1,92x`).
  - **Seeds `1–12` (`A5`/`A6` `n=12` vs. `A4` `n=12`):** `5/4` Wall **`1,56x`** (`1,63x`), CPU **`1,39x`** (`1,35x`); `6/4` Wall **`2,18x`** (`2,45x`), CPU **`1,73x`** (`1,90x`).

**Serien-Pool (`COMMANDER_LAB_STUDIO_SERIES_POOL=1`, `gamesPerJvm=16`, B3b & B6):**

| Lauf | Sitze | Worker | `n/N` | Wandzeit (s) | Durchsatz (Partien/h) | Peak-RSS Summe [MiB] | Peak Einzel-JVM [MiB] | Swap-Delta [MB] |
|---|---|---|---|---|---|---|---|---|
| B3b `5p-w1` | `5` | `1` | `20/20` | `267,51` | `269,1` | `1419,5` | `1419,5` | `0,0` |
| B3b `5p-w3` | `5` | `3` | `20/20` | `140,95` | `510,8` | `4200,5` | `1420,2` | `0,0` |
| B6 F8 `5p` | `5` | `3` | `50/50` | `296,38` | **`607,3`** | `4445,3` | `—` (`Summe gemessen`) | `0,0` |
| B3b `6p-w1` | `6` | `1` | `20/20` | `388,80` | `185,2` | `1448,1` | `1448,1` | `-0,25` |
| B3b `6p-w3` | `6` | `3` | `20/20` | `198,61` | `362,5` | `4263,0` | `1448,4` | `0,0` |
| B6 F8 `6p` | `6` | `3` | `72/72` | `683,57` | **`379,2`** | `4406,8` | `—` (`Summe gemessen`) | `-0,25` |

- **`p99`-Entscheidungslatenz:** **`UNKNOWN`** (`N = 24 < 100`, Frames tragen keine Zeitstempel).
- **Vorschlag Zeitgrenzen & Worker-Deckel (Budget bleibt Owner-Entscheid):**
  - Unter `16 GiB` WSL2-RAM gilt für die konfigurierte Heap-Obergrenze `-Xmx3g` je JVM (`src/commander_lab/studio/launch.py:156`) ohne eigene Obergrenze streng genommen **`workers <= 4`** (oder bis `5`) als harte Reserve; die empirische Schätzung **`workers <= 6`** beruht ausschließlich auf dem hier beobachteten RSS-Peak von `~1,42–1,45 GiB` je Pool-JVM (`~8,5 GiB` bei 6 Workern).
  - Bestehende Limits (`120 s` je Einzelanfrage, `50.000` Entscheidungen, `1800 s` je Pool-Partie) lagen über den hier beobachteten Maxima (`48,12 s` Wallzeit, `9451` Entscheidungen in `B6`).

---

## 6. Schritt B5 (= F7 Piloten: Angriffsziele, Auslassungen, `forced_decisions_skipped`)

**Gültigkeitshinweis (Pflichtangabe):** **Für `5` und `6` Sitze gibt es keine menschliche Referenz.** Der Auslassungs-Zähler ist ein beobachtender Vorschlag (`chosen == []` trat `0`-mal auf; in diesem Format antwortet die Bridge bei Verzicht explizit mit `"Do not attack with ..."`).

**Je Tisch getrennt ausgewiesen (`b2_results.jsonl`, `N = 12` je Tisch, `#1706` keine Summierung über verschiedene Gegnersätze):**

| Tisch (`n = 12`) | Sitze | Sieger je Sitz `0..N-1` (`12/12` Siege) | `forced_decisions_skipped` / `decision_count` | `declare_attacker`-Ziele / Auslassungen |
|---|---|---|---|---|
| `A4` | `4` | `S0: 5`, `S1: 4`, `S2: 0`, `S3: 3` | `11.922 / 33.949` (`35,12 %`) | unten vollständig (`1019` Frames) |
| `A5` | `5` | `S0: 6`, `S1: 2`, `S2: 0`, `S3: 1`, `S4: 3` | `18.588 / 53.555` (`34,71 %`) | **je Tisch `UNKNOWN`** (vor Rohlog-Löschung mit `B5` zusammengefasst) |
| `B5` | `5` | `S0: 5`, `S1: 1`, `S2: 2`, `S3: 2`, `S4: 2` | `22.250 / 52.667` (`42,25 %`) | **je Tisch `UNKNOWN`** (vor Rohlog-Löschung mit `A5` zusammengefasst) |
| `A6` | `6` | `S0: 1`, `S1: 2`, `S2: 1`, `S3: 1`, `S4: 5`, `S5: 2` | `29.620 / 77.716` (`38,11 %`) | **je Tisch `UNKNOWN`** (vor Rohlog-Löschung mit `B6` zusammengefasst) |
| `B6` | `6` | `S0: 3`, `S1: 0`, `S2: 0`, `S3: 1`, `S4: 5`, `S5: 3` | `29.931 / 63.849` (`46,88 %`) | **je Tisch `UNKNOWN`** (vor Rohlog-Löschung mit `A6` zusammengefasst) |

*Technische Gesamtwerte je Sitzzahl für `declare_attacker` (`b5_exact.json`; für `5P`/`6P` ungetrennt über `A+B` wegen vor der Einzelauswertung gelöschter `.jsonl.gz`-Logs — explizit kein Gegnersatz-Pool-Vergleich gemäß `#1706`):*
- `4P` (`A4`, `12` Partien, `1019` `declare_attacker`-Frames): `756` Seat-Angriffe (`S0: 191`, `S1: 141`, `S2: 240`, `S3: 184`), `86` Planeswalker, `177 / 1019` (`17,37 %`) `"Do not attack with …"`, `0 / 1019` `chosen == []` (bei `12/1019` Seat-Angriffen fehlte vor `"attacks …"` der Name, verdeckter Angreifer ohne UUID).
- `5P` (`A5+B5` ungetrennt, `24` Partien, `2738` Frames): `1682` Seat-Angriffe (`S0: 297`, `S1: 379`, `S2: 306`, `S3: 362`, `S4: 338`), `136` Planeswalker, `920 / 2738` (`33,60 %`) `"Do not attack with …"`, `0 / 2738` `chosen == []` (`8/2738` Seat- und `1` PW-Angriff mit verdecktem Angreifer ohne UUID).
- `6P` (`A6+B6` ungetrennt, `24` Partien, `3026` Frames): `1887` Seat-Angriffe (`S0: 371`, `S1: 363`, `S2: 283`, `S3: 319`, `S4: 226`, `S5: 325`), `162` Planeswalker, `977 / 3026` (`32,29 %`) `"Do not attack with …"`, `0 / 3026` `chosen == []` (`4/3026` Seat-Angriffe mit verdecktem Angreifer ohne UUID).

---

## 7. Schritt B6 (= F8 Gepaarte Serie im Pool, `N = 25` bzw. `36` Paare)

`compare-decks` mit `COMMANDER_LAB_STUDIO_SERIES_POOL=1`, `--workers 3`, `--games-per-jvm 16`, `--base-seed 3000`, `--rotate-seats`, `--allow-unreleased-seats`:

| Sitze | Budget `pairs_played` | Partien geloggt (`finished`) | Seeds | Verteilung je Test-Sitz | `pairs_censored` / `failure_classes` | JVM-Leben (`gamesPerJvm=16`) | Kohortenreinheit |
|---|---|---|---|---|---|---|---|
| **`5`** | **`25/25`** | **`50/50`** (`25` Base + `25` Var) | `3000–3004` (`5` in Folge) | `{0: 10, 1: 10, 2: 10, 3: 10, 4: 10}` | `0/25` zensiert, `{}` (`0` Ausfälle) | `4` Leben (`w1-1: 16, w1-2: 2, w2-1: 16, w3-1: 16`) | `table_sizes_seen == [5]` |
| **`6`** | **`36/36`** | **`72/72`** (`36` Base + `36` Var) | `3000–3005` (`6` in Folge) | `{0: 12, 1: 12, 2: 12, 3: 12, 4: 12, 5: 12}` | `0/36` zensiert, `{}` (`0` Ausfälle) | `6` Leben (`w1-1: 16, w1-2: 7, w2-1: 16, w2-2: 9, w3-1: 16, w3-2: 8`) | `table_sizes_seen == [6]` |

Reine technische Kennzahl (`SIMULATED_RESULT`, hier **nicht** als Deck-Aussage berichtet): `5P` `status=NOT_DECIDED`, `stop_reason=BUDGET_EXHAUSTED`, `4` vs. `2` diskordante Paare (`19` Unentschieden); `6P` `status=NOT_DECIDED`, `stop_reason=BUDGET_EXHAUSTED`, `5` vs. `7` diskordante Paare (`24` Unentschieden). Keine stillen Ausfälle (`2 * Budget = Anzahl Logs`).

---

## 8. B7-Status, Bridge-Determinismus-Befund `#1715` & Voraussetzungen vor Owner-Freigabe

- **B7 Spielabbrüche / Fork-Fehler:** `0/313` Partien fehlgeschlagen (alle `313/313` mit `status="finished"`). Bekannt offen aus früheren Arbeiten bleibt `#1628` (`needs:owner`).
- **Offener Bridge-Determinismus-Befund (`#1715`, F3 = BEFUND / FAIL):** In `2/24` (`5P` B3a `Seed 11`) und `1/20` (`6P` B3b `s2000-t5`) wichen die ad-hoc-normalisierten Frames nach gleichlautendem `trigger_order`-Gleichstand zwischen JVMs ab (bei `s2000-t5` inklusive echter Zustandsdivergenz `Topiary Stomper` bei identischem `semantic_transcript_sha256`).
- **Was für `SIMULATE` (`5` und `6` Sitze) inzwischen vorliegt:**
  - `SIMULATE-UI` hinter der Sperre (`#1702` / PR `#1708` + `#1709`, auf `main`): Tischgröße `2–6` planen, Rotationsblöcke `N²`, Aufwand bei `!= 4` Sitzen als `UNKNOWN`, Start weiter durch `launch.MAX_RELEASED_SEATS = 4` / `PAIRED_RELEASED_SEATS = 4` gesperrt.
  - CLI-Echt-Engine-Beobachtungen aus diesem Bericht: Vollständigkeit (`48/48` B2, `17/17` Klassen), semantisch/Sieger/Entscheidungen (`88/88` in B3a+B3b), Pool-Skalierung (`607,3` bzw. `379,2` Partien/h), Latin-Square-Rotation (`25/25` bzw. `36/36`).
- **Was vor einer Owner-Freigabe (`5` oder `6` Sitze) weiterhin offen / `BEFUND` / `NOT_RUN` / `UNKNOWN` ist:**
  1. **Klärung / Entscheidung zu `#1715`** (`trigger_order`-Gleichstand und Erfassung von Zustandsdivergenzen im semantischen Hash) sowie **Owner-Entscheid F1** (`ALL`/`MULTIPLE`, 6 Sitze ohne Replay-Anspruch) + expliziter Freigabe-PR (`MAX_RELEASED_SEATS`, `partie.js`, `paired.js`, `AGENTS.md` §1 / `STUDIO_SCOPE.md`).
  2. **F5 gezielte 5/6-Regelszenarien & 5P-Replay-Tape-MATCH:** Alle 8 Regelpunkte aus Plan §2 gezielt am Engine-Pin sowie ein 5-Sitz-Replay-Twin-Aufruf (`semantic_replay.gate`) sind `NOT_RUN`.
  3. **PLAY Live-Browser-Echt-Engine (`5/6` Sitze mit Mensch-Sitz):** Interaktives Spielen/Vorspulen/Concede bei 5/6 Sitzen im echten Browser mit echter Engine ist `NOT_RUN`.
  4. **Natives Windows & `p99`-Entscheidungslatenz & `declare_attacker`-Einzeltabellen (`A5`/`B5`/`A6`/`B6`):** Alle bleiben **`UNKNOWN`**.
