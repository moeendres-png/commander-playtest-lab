# 5 und 6 Sitze, Teil B (`#1661`): Echt-Engine-Läufe (B0–B7) am Owner-PC (WSL2)

- **Datum:** 2026-11-20 · **Refs:** `#1661`, `#1656`, `#1612`, `#1652`, `#1698`, `#1628`
- **Einordnung:** `SIMULATED_RESULT` / `DIRECTLY_VERIFIED` (Owner-PC-Echt-Engine-Messung unter WSL2, **kein Qualifikationsbeleg**).
- **Keine Freigabe:** `launch.MAX_RELEASED_SEATS = 4` (`src/commander_lab/studio/launch.py:37`), `OPPONENT_COUNTS = [1, 2, 3]` (`src/commander_lab/studio/static/partie.js:11`) und die Serien-/`compare-decks`-Sperre bleiben unverändert. Für alle `5`- und `6`-Sitz-Läufe mit `compare-decks` wurde `--allow-unreleased-seats` ausschließlich lokal auf der CLI gesetzt.
- **Basisstand & Engine-Pin:** Alle 313 Echt-Engine-Läufe auf `main` @ `5b406c86562cb9010584aed6d4e8433f5a33ecec` (Branch nach Laufabschluss per Fast-Forward auf `93154893b` ohne Bridge- oder Pin-Änderung synchronisiert), Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`, Release-Bridge-JAR `840e50abefdaa023072c8c03953e8689a6189a96d3837c5f0c72baf6f8086f6f`, Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (gesiegelte Epoche `5bd29ab6f318-c6942825587a`).
- **Gerät & Bridge-Start (WSL2):** `AMD Ryzen 7 7700 8-Core Processor` (`8C/16T`, `3792,8 MHz`), `15.992,19 MB` (`15,6 GiB`) WSL2-RAM, `8,0 GiB` Swap, `Linux 6.6.87.2-microsoft-standard-WSL2`, `OpenJDK 21.0.13.1`, `Python 3.14.4`. Alle `313/313` Partien liefen mit `SerialGC`, `-Dh2.bindAddress=127.0.0.1`, AppCDS (`xmage-engine-bridge.jsa`, `308 MB`, SHA-256 `f36ee5ed47382681d54be2949e1fb1e136bdbe74dd72dfeaa958547b892ea87`) und `-Dcommanderlab.fullGame.skipForcedDecisions=true` identisch zwischen `play-batch` (`FAST`/`FAST12`) und `compare-decks` (`series_engine`, Standard `gamesPerJvm=16`). Nativer Windows-Host: `UNKNOWN` / `NOT_RUN`.
- **Gesamtbilanz Echt-Engine (`313/313` Partien regulär beendet):** B0 (`3/3`) + B2 (`60/60`: `12` × 4P, `24` × 5P, `24` × 6P) + B3a (`48/48`) + B3b (`80/80`) + B6 (`122/122`), `0` Abbrüche, `0` B7-Fork-Defekte, Swap-Delta durchweg `<= 0,0 MB`.
- **Bezug auf Teil A:** Schnittstellentests und F1-Entwurf stehen in `docs/analysis-reports/seats_5_6_part_a_report.md`.

---

## 1. Übersicht je Nachweis (streng getrennt nach 5/6 Sitzen × SIMULATE/PLAY)

| # | Nachweis | 5 SIMULATE | 5 PLAY | 6 SIMULATE | 6 PLAY | Belege & Grenzen (`n/N`) |
|---|---|---|---|---|---|---|
| **F1** | Festlegungen `ALL`/`MULTIPLE`, 6 ohne Replay-Anspruch | Entwurf (Owner) | Entwurf (Owner) | Entwurf (Owner) | Entwurf (Owner) | Teil A Abschnitt 4; Freigabe bleibt Owner-Vorbehalt (`AGENTS.md` §8, E15 Q5). |
| **F2** | Vollständigkeit, `2` Tische × `12` Seeds (B2) | **PASS (`SIMULATED_RESULT`)** | Schnittstelle Teil A, Echt-PLAY **`NOT_RUN`** | **PASS (`SIMULATED_RESULT`)** | Schnittstelle Teil A, Echt-PLAY **`NOT_RUN`** | `5P`: `24/24` `finished` (`A5` `12/12`, `B5` `12/12`), `17/17` Klassen, Sitze `0..4` lückenlos. `6P`: `24/24` `finished` (`A6` `12/12`, `B6` `12/12`), `17/17` Klassen, Sitze `0..5` lückenlos. |
| **F3** | Identität (`1` gegen `W` Worker, Position in JVM, `N >= 20`, B3) | **PASS (`SIMULATED_RESULT`)** | Tape-Twin **`NOT_RUN`** | **PASS (`SIMULATED_RESULT`, ohne Replay)** | nicht anwendbar (F1) | B3a (`up`/`down`, `N=24`): semantisch/Sieger/Entscheidungen/Frame-Zahl `24/24` (`5P`) & `24/24` (`6P`); norm. Frames `22/24` (`5P`, Seed `11` Kaldra-Tiebreak) bzw. `24/24` (`6P`). B3b (`w1`/`w3` Pool, `N=20`): semantisch `20/20` (`5P`, norm. Frames `20/20`) & `20/20` (`6P`, norm. Frames `19/20`, `s2000-t5` Kaldra-Tiebreak). |
| **F4** | Verdeckte Information je Sitz `5` und `6` | **PASS (Live-Audit `0` Verstöße)** | Schnittstelle Teil A **`PASS (Test)`**, Live-Mensch-Browser **`NOT_RUN`** | **PASS (Live-Audit `0` Verstöße)** | Schnittstelle Teil A **`PASS (Test)`**, Live-Mensch-Browser **`NOT_RUN`** | In allen `313/313` Echt-Engine-Partien (`B0–B6`) lief `audit_actor_scoped_frame` (`full_game.py:1604`) fail-closed je Entscheidung ohne Verstoß (`.jsonl.gz` speichert keinen separaten Audit-Zähler). Live-PLAY mit echtem Mensch-Sitz und Browser-UI bei `5/6` Sitzen: **`NOT_RUN`**. |
| **F5** | Acht Regelpunkte aus Plan §2 | Schnittstelle `PASS (Test)`, gezielte Szenarien **`NOT_RUN`** | wie links | Schnittstelle `PASS (Test)`, gezielte Szenarien **`NOT_RUN`** | wie links (+ 6P-Tape ausgeschlossen) | B2 liefert nur Vorkommens-Zähler im Normalspiel (z. B. `trigger_order`: `478` Frames in `5P` über Sitze `0..4`, `1023` Frames in `6P` über Sitze `0..5` ohne Fehler); dedizierte 5/6-Regelszenarien und `5P`-Replay-Tape-MATCH bleiben **`NOT_RUN` / `UNKNOWN`**. |
| **F6** | Laufzeit `4/5/6`, Speicher, Pool-Durchsatz (B4) | **Gemessen (`SIMULATED_RESULT`)**, `p99 = UNKNOWN` | **`UNKNOWN`** (nur B2 Einzel-JVM gemessen) | **Gemessen (`SIMULATED_RESULT`)**, `p99 = UNKNOWN` | **`UNKNOWN`** (nur B2 Einzel-JVM gemessen) | Tisch `A` Seeds `1–10`: Wall-Median `12,91 s` (`4P`) → `20,18 s` (`5P`, `1,56x`) → `28,73 s` (`6P`, `2,23x`); Pool `w3` (`B6`): `607,3` (`5P`) bzw. `379,2` (`6P`) Partien/h; `p99 = UNKNOWN` (`N=24 < 100`, keine Frame-Zeitstempel). |
| **F7** | Piloten: Auslassungen & Zielverteilung (B5) | **Erhoben (`SIMULATED_RESULT`)**, **keine menschl. Referenz** | nicht anwendbar (KI-Metrik) | **Erhoben (`SIMULATED_RESULT`)**, **keine menschl. Referenz** | nicht anwendbar (KI-Metrik) | Alle `6783` `declare_attacker`-Frames aus B2 ausgewertet (`0` leere `chosen == []`, explizite Nicht-Angriffe `33,60 %` bei `5P` vs. `32,29 %` bei `6P` vs. `17,37 %` bei `4P`). |
| **F8** | Gepaarte Serie mit voller Sitz-Rotation (B6) | **PASS (`SIMULATED_RESULT`)** | nicht anwendbar | **PASS (`SIMULATED_RESULT`)** | nicht anwendbar | `5P`: `25/25` Paare (`50/50` Partien, je `10` pro Sitz `0..4`, `0/25` zensiert). `6P`: `36/36` Paare (`72/72` Partien, je `12` pro Sitz `0..5`, `0/36` zensiert). Strikte Kohortentrennung belegt. **UI-Lücke bleibt:** `POD_PRESETS` / `PAIRED_TABLE_SEATS = 4` nur über CLI (`--allow-unreleased-seats`). |

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

**Beobachtete Frame-Zahlen je Klasse (B2, `N = 12` für 4P; `N = 24` je für 5P/6P) und Sitze:**
- `5P` (`65.384` Frames gesamt): `amount=3`, `announce_x=97`, `choice=770`, `choose_object=685`, `choose_use=1176`, `declare_attacker=2738`, `declare_blocker=1364`, `mana_payment=16260`, `mode=150`, `mulligan=170`, `multi_amount=89`, `pile=3`, `priority=39878`, `replacement_effect=18`, `target=1474`, `target_amount=31`, `trigger_order=478`. Frame-Verteilung je Sitz `0..4`: `13504 / 11824 / 12846 / 13020 / 14190`.
- `6P` (`82.014` Frames gesamt): `amount=3`, `announce_x=560`, `choice=1189`, `choose_object=881`, `choose_use=1539`, `declare_attacker=3026`, `declare_blocker=1195`, `mana_payment=17625`, `mode=114`, `mulligan=200`, `multi_amount=83`, `pile=1`, `priority=52672`, `replacement_effect=24`, `target=1847`, `target_amount=32`, `trigger_order=1023`. Frame-Verteilung je Sitz `0..5`: `13319 / 11665 / 13372 / 11514 / 17380 / 14764`.
- **F4 Live-Audit:** Alle `60/60` B2-Partien sowie alle `253/253` übrigen B0/B3/B6-Partien durchliefen `audit_actor_scoped_frame` bei jeder einzelnen Entscheidung mit `0` Verstößen (`FullGameConformanceError` wurde `0`-mal ausgelöst). Hinweis: Die Log-Datei `.jsonl.gz` schreibt das Feld `hidden_information_audit` nicht separat aus (`play.close_recorded_game`).

---

## 4. Schritt B3 (= F3 Identität, `N >= 20` je Sitzzahl)

### 4.1 B3a: Position in einer JVM (`gamesPerJvm=12`, auf- und absteigend gegen Einzel-JVM B2)

`FAST12` (`play-batch` mit `-Dcommanderlab.fullGame.gamesPerJvm=12`), getrennte `--data`-Ordner `up` (`1..12`) und `down` (`12..1`), identische Spiel-IDs `s2b-a{5,6}-s{1..12}`. Hinweis: `BatchRecordingRunner` (`play-batch`) speichert im Log kein `jvm_life_id`/`position_in_jvm` (nur `GamePool` tut dies), jedoch lief jeder 12er-Lauf innerhalb genau eines `play-batch`-Prozesses (`played_events=12/12`, Wandzeiten `5P`: `175,3 s` up / `167,8 s` down vs. `245,4 s` für `12` Einzel-JVMs; `6P`: `254,7 s` up / `256,9 s` down vs. `357,2 s`).

| Sitze | Vergleich (`n/N`) | `semantic_transcript_sha256` | `winner_seats` | `decision_count` | `frame_count` | Roh-`frame_digest` | `[xxx]`-bereinigter `frame_digest` |
|---|---|---|---|---|---|---|---|
| `5` | `up` vs. `single` (`n/12`) | **`12/12`** | **`12/12`** | **`12/12`** | **`12/12`** | `0/12` | **`11/12`** (Abw. Seed `11`) |
| `5` | `down` vs. `single` (`n/12`) | **`12/12`** | **`12/12`** | **`12/12`** | **`12/12`** | `0/12` | **`11/12`** (Abw. Seed `11`) |
| `5` | **Summe `up+down` (`n/24`)** | **`24/24`** | **`24/24`** | **`24/24`** | **`24/24`** | `0/24` | **`22/24`** |
| `6` | `up` vs. `single` (`n/12`) | **`12/12`** | **`12/12`** | **`12/12`** | **`12/12`** | `0/12` | **`12/12`** |
| `6` | `down` vs. `single` (`n/12`) | **`12/12`** | **`12/12`** | **`12/12`** | **`12/12`** | `0/12` | **`12/12`** |
| `6` | **Summe `up+down` (`n/24`)** | **`24/24`** | **`24/24`** | **`24/24`** | **`24/24`** | `0/24` | **`24/24`** |

- **Erklärung Roh- vs. bereinigtem `frame_digest`:** `identity_row` hasht unveränderte Studio-Frames; durch ephemere 3-Hex-Objekt-IDs (`[xxx]`) in `mana_payment`/`choose_use`-Prompts und `replacement_effect`-Labels weicht der rohe `frame_digest` zwischen getrennten JVMs deterministisch ab (`0/24`), obwohl Zugfolge, Board und Entscheidungen identisch sind.
- **Einzige Abweichung nach `[xxx]`-Bereinigung (`5P Seed 11`):** `up` und `down` sind untereinander zu `100 %` (`3089/3089` Frames) identisch; gegen `single` weichen nur die **3 Frames `2204–2206`** von `3089` ab (`Quintorius, Field Historian` +2/+0-Aura auf `Spirit Token`). Ursache: bei Frame `2200` (`trigger_order`, Seat `0`) liegen zwei gleichlautende `Kaldra Compleat`-Trigger auf dem Stapel (`Phyrexian Germ Token — Whenever {this} deals combat damage to a creature, exile that permanent.`), deren Tiebreak (`abilitySortKey`) zwischen JVMs tauschte; ab Frame `2207` sind alle `883` verbleibenden Frames bis Spielende wieder deckungsgleich (`semantic_transcript_sha256` `44f7dcca…`, `decision_count=5008`, `winner_seats` identisch).

### 4.2 B3b: Serien-Pool `workers=1` gegen `workers=3` (`compare-decks`, `POOL=1`, `N = 20` je Sitzzahl)

`compare-decks --pairs 10 --look-every 10 --base-seed 2000 --rotate-seats --allow-unreleased-seats` (`gamesPerJvm=16`, getrennte Ordner `w1` und `w3`, `20` Partien je Lauf):

| Sitze | Vergleich (`n/N`) | `semantic_transcript_sha256` | `winner_seats` | `decision_count` | `frame_count` | Roh-`frame_digest` | `[xxx]`-bereinigter `frame_digest` |
|---|---|---|---|---|---|---|---|
| `5` | `w1` vs. `w3` (`n/20`) | **`20/20`** | **`20/20`** | **`20/20`** | **`20/20`** | `0/20` | **`20/20`** |
| `6` | `w1` vs. `w3` (`n/20`) | **`20/20`** | **`20/20`** | **`20/20`** | **`20/20`** | `0/20` | **`19/20`** (`s2000-t5`) |

- **Einzige Abweichung nach `[xxx]`-Bereinigung (`6P s2b-id-6-base-s2000-t5`):** Dieselbe Ursache wie in B3a: bei Frames `2596–2597` (`trigger_order`, Seat `5`) lösen `3` gleichlautende `Kaldra Compleat`-Exil-Trigger leicht umgeordnet auf (`Topiary Stomper` in Frames `2601–2606` bereits im Exil vs. noch auf dem Spielfeld); ab Frame `2607` (insgesamt `2900` Frames) und im Ergebnis (`semantic_transcript_sha256`, `winner_seats`, `decision_count`) zu `100 %` identisch.

---

## 5. Schritt B4 (= F6 Laufzeit, Speicher und Verhältnisse 5/4 sowie 6/4)

**Einzel-JVM (`play-batch`, `FAST`), Tisch `A` Seeds `1–10` (`N = 10` je Sitzzahl) sowie Gesamtsets B2 (`N = 12`/`24`):**

| Kohorte | `n` | Wall Median (Min..Max) [s] | CPU Median (Min..Max) [s] | MaxRSS Median (Min..Max) [MiB] | Entsch. Median (Min..Max) | Skip Median (Min..Max) |
|---|---|---|---|---|---|---|
| `A4` (`4P`, Seeds `1–10`) | `10` | `12,91` (`8,43..26,16`) | `30,83` (`22,31..52,14`) | `749,4` (`672,2..1341,4`) | `2703,5` (`1680..4539`) | `985,0` (`607..1405`) |
| `A5` (`5P`, Seeds `1–10`) | `10` | `20,18` (`13,46..27,07`) | `42,76` (`33,73..53,10`) | `776,9` (`742,7..850,0`) | `4534,0` (`2939..5813`) | `1592,0` (`865..1994`) |
| `A6` (`6P`, Seeds `1–10`) | `10` | `28,73` (`21,08..41,39`) | `54,56` (`44,60..68,55`) | `969,4` (`933,5..1050,2`) | `6329,0` (`4839..8270`) | `2521,5` (`2182..3105`) |
| `A4` (`4P`, Seeds `1–12`) | `12` | `12,91` (`8,43..26,16`) | `30,83` (`22,31..52,14`) | `749,4` (`672,2..1341,4`) | `2703,5` (`1680..4539`) | `985,0` (`607..1491`) |
| `A5+B5` (`5P`, alle B2) | `24` | `18,94` (`11,83..36,43`) | `40,56` (`29,36..61,97`) | `785,1` (`700,1..850,0`) | `4231,5` (`2505..7173`) | `1777,0` (`865..2784`) |
| `A6+B6` (`6P`, alle B2) | `24` | `25,80` (`15,13..48,12`) | `51,75` (`33,63..77,66`) | `903,3` (`738,6..1050,2`) | `5896,0` (`3564..9451`) | `2441,5` (`1817..4132`) |

**Skalierungsverhältnisse auf denselben Seeds (`A5`/`A6` vs. `A4`):**
- **Seeds `1–10`:**
  - `5/4`: Median-Wall-Verhältnis **`1,56x`** (Median der Seed-Paar-Ratios: `1,63x`), Median-CPU-Verhältnis **`1,39x`** (paarweise `1,35x`).
  - `6/4`: Median-Wall-Verhältnis **`2,23x`** (Median der Seed-Paar-Ratios: `2,63x`), Median-CPU-Verhältnis **`1,77x`** (paarweise `1,92x`).
- **Seeds `1–12`:**
  - `5/4`: Wall **`1,56x`** (`1,63x`), CPU **`1,39x`** (`1,35x`).
  - `6/4`: Wall **`2,18x`** (`2,45x`), CPU **`1,73x`** (`1,90x`).

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
- **Vorschlag Zeitgrenzen & Worker-Deckel (nur Empfehlung, Budget ist Owner-Sache):**
  - Bei `16 GiB` WSL2-RAM (`~1,42 GiB`/Pool-JVM): für `5/6`-Sitz-Serien **`workers <= 6`** (geschätzt `~8,5 GiB` Peak-RSS, sichere Reserve zum System und zu 8 physischen Kernen).
  - Bestehende Limits (`120 s` je Einzelanfrage, `50.000` Entscheidungen, `1800 s` je Pool-Partie) können unverändert bleiben: beobachtetes Maximum in `6P` lag bei `48,12 s` Wallzeit und `9451` Entscheidungen.

---

## 6. Schritt B5 (= F7 Piloten: Angriffsziele, Auslassungen, `forced_decisions_skipped`)

Auswertung der B2-Logs (`N = 12` für `4P`, `N = 24` je für `5P` und `6P`, `SIMULATED_RESULT`):

**Gültigkeitshinweis (Pflichtangabe):** **Für `5` und `6` Sitze gibt es keine menschliche Referenz.** Der Auslassungs-Zähler ist ein beobachtender Vorschlag (`chosen == []` trat `0`-mal auf; in diesem Format antwortet die Bridge bei Verzicht explizit mit `"Do not attack with ..."`).

| Sitze | `declare_attacker`-Frames | Angriffe auf Sitze `0..N-1` (inkl. verdeckter Angreifer) | Angriffe auf Planeswalker | Explizit `"Do not attack with …"` (`Auslassungs-Zähler`) | `chosen == []` | Sieger je Sitz `0..N-1` (`n/N`) | `forced_decisions_skipped` / `decision_count` |
|---|---|---|---|---|---|---|---|
| `4P` (`12`) | `1019` | `756` (`Sitz 0: 191`, `S1: 141`, `S2: 240`, `S3: 184`) | `86` | `177 / 1019` (**`17,37 %`**) | `0 / 1019` | `S0: 5`, `S1: 4`, `S2: 0`, `S3: 3` (`12/12` Siege) | `11.922 / 33.949` (`35,12 %`) |
| `5P` (`24`) | `2738` | `1682` (`S0: 297`, `S1: 379`, `S2: 306`, `S3: 362`, `S4: 338`) | `136` | `920 / 2738` (**`33,60 %`**) | `0 / 2738` | `S0: 11`, `S1: 3`, `S2: 2`, `S3: 3`, `S4: 5` (`24/24` Siege) | `40.838 / 106.222` (**`38,45 %`**) |
| `6P` (`24`) | `3026` | `1887` (`S0: 371`, `S1: 363`, `S2: 283`, `S3: 319`, `S4: 226`, `S5: 325`) | `162` | `977 / 3026` (**`32,29 %`**) | `0 / 3026` | `S0: 4`, `S1: 2`, `S2: 1`, `S3: 2`, `S4: 10`, `S5: 5` (`24/24` Siege) | `59.551 / 141.565` (**`42,07 %`**) |

Beobachtung zu `#1651`-Nebenbefund (`declare_attacker`): Bei `12/1019` (`4P`), `8/2738` (`5P`) und `4/3026` (`6P`) Seat-Angriffen sowie `1` Planeswalker-Angriff in `5P` fehlte vor `"attacks …"` der Name (verdeckte Angreifer, enthält keine UUID). Keine Änderung nötig für diesen Bericht.

---

## 7. Schritt B6 (= F8 Gepaarte Serie im Pool, `N = 25` bzw. `36` Paare)

`compare-decks` mit `COMMANDER_LAB_STUDIO_SERIES_POOL=1`, `--workers 3`, `--games-per-jvm 16`, `--base-seed 3000`, `--rotate-seats`, `--allow-unreleased-seats`:

| Sitze | Budget `pairs_played` | Partien geloggt (`finished`) | Seeds | Verteilung je Test-Sitz | `pairs_censored` / `failure_classes` | JVM-Leben (`gamesPerJvm=16`) | Kohortenreinheit |
|---|---|---|---|---|---|---|---|
| **`5`** | **`25/25`** | **`50/50`** (`25` Base + `25` Var) | `3000–3004` (`5` in Folge) | `{0: 10, 1: 10, 2: 10, 3: 10, 4: 10}` | `0/25` zensiert, `{}` (`0` Ausfälle) | `4` Leben (`w1-1: 16, w1-2: 2, w2-1: 16, w3-1: 16`) | `table_sizes_seen == [5]` |
| **`6`** | **`36/36`** | **`72/72`** (`36` Base + `36` Var) | `3000–3005` (`6` in Folge) | `{0: 12, 1: 12, 2: 12, 3: 12, 4: 12, 5: 12}` | `0/36` zensiert, `{}` (`0` Ausfälle) | `6` Leben (`w1-1: 16, w1-2: 7, w2-1: 16, w2-2: 9, w3-1: 16, w3-2: 8`) | `table_sizes_seen == [6]` |

Reine technische Kennzahl (`SIMULATED_RESULT`, hier **nicht** als Deck-Aussage berichtet): `5P` `status=NOT_DECIDED`, `stop_reason=BUDGET_EXHAUSTED`, `4` vs. `2` diskordante Paare (`19` Unentschieden); `6P` `status=NOT_DECIDED`, `stop_reason=BUDGET_EXHAUSTED`, `5` vs. `7` diskordante Paare (`24` Unentschieden). Keine stillen Ausfälle (`2 * Budget = Anzahl Logs`).

---

## 8. B7 Fork-Befunde & verbleibende Voraussetzungen vor einer Owner-Freigabe

- **B7 Fork-Befunde aus Teil B:** **keiner** (`0/313` Partien fehlgeschlagen). Bekannt offen aus früheren Arbeiten bleibt `#1628` (`needs:owner`).
- **Was für `SIMULATE` per CLI (`5` und `6` Sitze) nun gemessen ist:** Vollständigkeit (`48/48` B2, `17/17` Klassen, lückenlose Sitze), Positions- und Pool-Identität (`88/88` semantisch/Sieger/Entscheidungen/Frame-Zahl über `48/48` B3a + `40/40` B3b; bekannte `[xxx]`-Prompt-IDs sowie zwei `Kaldra Compleat`-Trigger-Tiebreaks ohne Ergebniswirkung), Pool-Skalierung mit `gamesPerJvm=16` (`607,3` bzw. `379,2` Partien/h bei `~4,4 GiB` für 3 Worker), vollständige Latin-Square-Rotation (`25/25` bzw. `36/36`, `0` zensiert).
- **Was noch offen / `NOT_RUN` / `UNKNOWN` vor einer Owner-Freigabe (`5` oder `6` Sitze) bleibt:**
  1. **Owner-Entscheid F1** (Teil A Abschnitt 4: `ALL`/`MULTIPLE`, 6 Sitze ohne Replay-Anspruch) sowie expliziter Freigabe-PR (`MAX_RELEASED_SEATS`, `partie.js`, `AGENTS.md` §1 / `STUDIO_SCOPE.md`).
  2. **SIMULATE-UI für 5/6 Sitze** (Teil A B-3 / Punkt 5: `POD_PRESETS` / `paired.js` `PAIRED_TABLE_SEATS = 4` kennen bisher nur Vierertische). *Hinweis:* B-2 (Kartenauswertung nach Tischgröße) wurde inzwischen in `main` umgesetzt (`#1693`, `#1700`), UI-Presets für 5/6 bleiben offen.
  3. **F5 gezielte 5/6-Regelszenarien & 5P-Replay-Tape-MATCH:** Alle 8 Regelpunkte aus Plan §2 gezielt am Engine-Pin sowie ein 5-Sitz-Replay-Twin-Aufruf (`semantic_replay.gate`) sind `NOT_RUN`.
  4. **PLAY Live-Browser-Echt-Engine (`5/6` Sitze mit Mensch-Sitz):** Interaktives Spielen/Vorspulen/Concede bei 5/6 Sitzen im echten Browser mit echter Engine ist `NOT_RUN`.
  5. **Natives Windows & `p99`-Entscheidungslatenz:** Beide bleiben `UNKNOWN`.
