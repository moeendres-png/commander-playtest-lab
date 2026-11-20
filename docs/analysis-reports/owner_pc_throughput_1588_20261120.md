# Durchsatz-Messung am Owner-PC (WSL2): Worker × Partien je JVM (#1588)

- **Datum:** 2026-11-20 · **Refs:** `#1588`, `#1587`, `#1558`, `#1692`
- **Einordnung:** `SIMULATED_RESULT` / `DIRECTLY_VERIFIED` (Messung, **kein Qualifikationsbeleg**).
- **Messstand:** Lab `0fb8fce19a3c88167bb9a7c6188aff9de00dee1c` (Release-Artefakt `14605622120`, Workflow-Run `44684028692`), Engine-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d`, `bridge_jar_sha256` `840e50abefdaa023072c8c03953e8689a6189a96d3837c5f0c72baf6f8086f6f`, Zustand `BRIDGE_AHEAD_OF_QUALIFICATION` (Epoche `5bd29ab6f318-c6942825587a`).
- **Gerät & Laufzeit (WSL2):** `AMD Ryzen 7 7700 8-Core Processor` (`K = 8` physische / `16` logische Kerne, `3792,8 MHz` Basistakt), `15.992,19 MB` (`15,6 GiB`) WSL2-RAM, `8,0 GiB` Swap, `Linux 6.6.87.2-microsoft-standard-WSL2`, `OpenJDK 21.0.13.1`, `Python 3.14.4`. Nativer Windows-Host-RAM und native Windows-Laufzeit: `UNKNOWN`.
- **Bridge-Start:** `--fast` (SerialGC + AppCDS `xmage-engine-bridge.jsa`, `308 MB`, SHA-256 `f36ee5ed47382681d54be2949e1fb1e136bdbe74dd72dfeaa9585547b892ea87`), `--private-card-repository`, `-Dcommanderlab.fullGame.skipForcedDecisions=true`, `--frame-digest-skip-forced`.
- **Tisch (`pod="real"`, 2 Custom-/Turnier-Decks + 2 Precons):** `rogshai_current` (`data/decks/rogshai_current.json`), `kaervek/current` (`data/decks/opponents/kaervek/current/deck.json`), `hosts_of_mordor_precon`, `lorehold_spirit_precon` (`scripts/run_real_4p_full_game_smoke.py`; Hinweis: in `#1588` standen abweichend 4 Precons, `benchmark_xmage_full_games.py run` ohne `--coverage-pods` spielt diesen `real`-Tisch).
- **Vorab-Smoke (`smoke_s1.json`, Seed 1, `W=1, G=1`):** `1/1` ok, `14,09 s`, `2488` Entscheidungen, `1533` Frames (`5` Zwangs-Frames übersprungen).

## 1. Exaktes `#1588`-Protokoll (48 Seeds, 7 Läufe, `336/336` Partien ok)

| Zelle | Worker (angef. / max. aktiv) | G | `n/N` | Wandzeit (s) | Partien/h | Peak-RSS Summe / Max JVM (MB) | Swap-Delta (MB) | CPU vorher (%) | Identität (Transkript / Frames) |
|---|---|---|---|---|---|---|---|---|---|
| `c1_w1_g8_s48` (Ref) | 1 / 1 | 8 | `48/48` | `514,10` | `336,12` | `1028,58` / `1028,58` | `0,0` | `0,28` | Referenz (`48/48`) |
| `c2_w4_g8_s48` | 4 / 4 | 8 | `48/48` | `278,74` | `619,93` | `3876,60` / `1051,14` | `0,0` | `0,38` | `48/48` / `48/48` |
| `c3a_w7_g8_s48_r1` | 7 / 6 | 8 | `48/48` | `245,47` | `703,96` | `5982,64` / `1041,86` | `0,0` | `3,41` | `48/48` / `48/48` |
| `c3b_w7_g8_s48_r2` | 7 / 6 | 8 | `48/48` | `247,80` | `697,34` | `5844,57` / `1027,20` | `0,0` | `0,13` | `48/48` / `48/48` |
| `c4_w8_g8_s48` | 8 / 6 | 8 | `48/48` | `243,81` | `708,75` | `5885,96` / `1034,42` | `0,0` | `0,44` | `48/48` / `48/48` |
| `c5_w7_g24_s48` | 7 / 2 | 24 | `48/48` | `291,52` | `592,76` | `2016,95` / `1037,11` | `0,0` | `0,34` | `48/48` / `48/48` |
| `c6_w8_g24_s48` | 8 / 2 | 24 | `48/48` | `290,15` | `595,55` | `2092,93` / `1061,04` | `0,0` | `0,34` | `48/48` / `48/48` |

**Chunking-Befund:** `benchmark_xmage_full_games.py` teilt `48` Seeds in `ceil(48 / G)` Chunks (`ThreadPoolExecutor(max_workers=W)`). Dadurch laufen real höchstens `min(W, ceil(48 / G))` JVMs gleichzeitig: bei `G=8` genau `6` JVMs (identisch für `W=6, 7, 8`), bei `G=24` nur `2` JVMs (6 Kerne bleiben ungenutzt).

## 2. Gesättigte Vollbelegung (`N = W × G`, 9 Läufe, `944/944` Partien ok)

| Zelle | Worker (angef. / max. aktiv) | G | Seeds | `n/N` | Wandzeit (s) | Partien/h | Peak-RSS Summe / Max JVM (MB) | Swap-Delta (MB) | CPU vorher (%) | Identität Überlapp (Transkript / Frames) |
|---|---|---|---|---|---|---|---|---|---|---|
| `s1_w4_g8_s64` | 4 / 4 | 8 | `1–64` | `64/64` | `328,91` | `700,50` | `4004,89` / `1084,41` | `0,0` | `0,19` | `64/64` / `64/64` |
| `s2_w6_g8_s48` | 6 / 6 | 8 | `1–48` | `48/48` | `242,77` | `711,78` | `5924,83` / `1065,32` | `0,0` | `0,34` | `48/48` / `48/48` (`compare` vs. `c1`) |
| `s3_w7_g8_s56` | 7 / 7 | 8 | `1–56` | `56/56` | `281,10` | `717,18` | `6881,92` / `1051,23` | `0,0` | `0,16` | `56/56` / `56/56` |
| `s4_w8_g8_s64` | 8 / 8 | 8 | `1–64` | `64/64` | `323,22` | `712,83` | `7846,08` / `1035,57` | `0,0` | `0,34` | `64/64` / `64/64` |
| `s5_w6_g16_s96` | 6 / 6 | 16 | `1–96` | `96/96` | `439,39` | `786,54` | `6079,14` / `1059,95` | `0,0` | `0,47` | `96/96` / `95/96` (Seed `94`) |
| `s6_w7_g16_s112` | 7 / 7 | 16 | `1–112` | `112/112` | `495,11` | `814,36` | `7122,01` / `1082,30` | `0,0` | `0,38` | `112/112` / `111/112` (Seed `94`) |
| `s7_w6_g24_s144` | 6 / 6 | 24 | `1–144` | `144/144` | `605,18` | `856,60` | `6122,07` / `1069,86` | `0,0` | `0,38` | `144/144` / `142/144` (Seeds `94, 123`) |
| `s8_w7_g24_s168` | 7 / 7 | 24 | `1–168` | `168/168` | `705,05` | `857,81` | `7160,47` / `1053,02` | `0,0` | `0,41` | `168/168` / `165/168` (Seeds `94, 123, 147`) |
| `s9_w8_g24_s192` | 8 / 8 | 24 | `1–192` | `192/192` | `789,04` | `876,00` | `8243,92` / `1097,54` | `0,0` | `0,50` | `168/168` / `165/168` (Seeds `94, 123, 147`; `169–192` einmalig) |

## 3. Auswertung, `#1587` und Nebenbefund (`frame_digest`)

- **Volle Stabilität & Speicherreserve:** Alle `1280/1280` Messpartien über 16 Zellen (+ `1/1` Smoke) endeten mit `status=ok`, `0` Fehlern und `0,0 MB` Swap-Delta. Selbst `8` gleichzeitige JVMs × `24` Partien (`s9`) blieben bei `8243,92 MB` Peak-RSS (min. freier RAM `5211,88 MB` von `15992,19 MB`).
- **Einordnung für `#1587` (`G = 8 → 16 → 24`):** Bei `G=8` stagniert der Durchsatz über `W=6/7/8` bei `711,8–717,2 Partien/h`. Erhöhen auf `G=16` steigert ihn auf `786,54/h` (`6W`, `+10,5 %`) bzw. `814,36/h` (`7W`, `+13,6 %`); `G=24` erreicht `856,60/h` (`6W`, `+20,3 %`), `857,81/h` (`7W`, `+19,6 %`) und maximal `876,00/h` (`8W`, `+22,9 %` gegenüber `8W/8G`, aber nur `+2,3 %` über `6W/24G` bei `+2121,85 MB` Mehrbedarf). Der Einzel-JVM-Peak-RSS wächst von `G=8` (`1027–1084 MB`) über `G=16` (`1060–1082 MB`) auf `G=24` (`1053–1098 MB`) kaum an. **Empfehlung:** `#1587` (`DEFAULT_GAMES_PER_JVM = 16`) bestätigt; für reine Durchsatz-Serien ohne enge Chunk-Grenzen liefert `W=6` oder `W=7` mit `G=16` (`~787–814/h`) bzw. `G=24` (`~857–858/h`) den besten Kompromiss aus Tempo, `~6,1–7,2 GB` RAM und freiem Systemkern.
- **Nebenbefund Frame-Digest (`3/168` Seeds, Folge-Issue `#1692`):** Über alle `168/168` mehrfach gespielten Seeds (`1–168`) sind `semantic`, `decisions`, `winners` und `frames`-Anzahl **100 % identisch** (`48/48` in Block 1 auch beim `frame_digest`). Auf `3/168` Seeds in Block 2 (`94`, `123`, `147`) wich allein `frame_digest` ab:
  - **Seed `94` (`DIRECTLY_VERIFIED`):** Auch in zwei getrennten `W=1, G=1`-Einzelläufen identischer Spielverlauf (`semantic=f6ca19d59ffb842d`, `decisions=3633`, `winners=(4,)`, `frames=2290`), erste Abweichung an Frame `1146` (`seat=0`, `decision_class=replacement_effect`) bei `.legal_options[0].metadata.xmage_key` = `<uuid1>_<uuid2>`, da `_UUID_RE` in `src/commander_lab/engine/rules/frame_digest.py:82` `\b...\b` nutzt und an `_` nicht matcht.
  - **Seeds `123` und `147` (`UNKNOWN` für Einzel-Frame-Stelle):** Spielverlauf (`01238ff52e3cd74d` bzw. `02878e8a26721643`), Entscheidungen (`4744` / `3724`), Sieger (`[4]` / `[2]`) und `frames` (`3431` / `2816`) identisch; Einzel-Frame-Diff noch nicht inspiziert.

## 4. `UNKNOWN` / Offen

- **Natives Windows:** Laufzeit, Hardware-RAM im Windows-Host, `benchmark_xmage_full_games.py` ohne WSL2 und `studio doctor` direkt unter Windows bleiben `UNKNOWN`.
- **Chulane-Pilotblock & PLAY-Abnahme:** Gepaarter Chulane-Pilotblock (Block E / `#1521`), Block D-Identitätslauf im Studio-Pfad sowie PLAY AK-1 bis AK-8 sind weiterhin `UNKNOWN`.

## 5. Lokale Rohdateien (außerhalb des Repos, `AGENTS.md` §11)

- `smoke_s1.json` (`1`): `4f62df15cd3479934d380640a39464909aa1e1d20aaf1007db59d3b063ccc075`
- `c1_w1_g8_s48.json` (`1–48`): `cd432d5197ee90996254f0aed429a444f3060bd8b2553f0d0c5efd0cf0c92b4c`
- `c2_w4_g8_s48.json` (`1–48`): `d58a0d93b4d578f4bc1beb92173f62ea26f9e94dc9511872126ac1043cdeda0e`
- `c3a_w7_g8_s48_r1.json` (`1–48`): `dc89510fa737db5e592a20742f1e5e21d994aca000a4e8c7825976a850f640ca`
- `c3b_w7_g8_s48_r2.json` (`1–48`): `5cef64c35d939baa232beda7d099fcfdad523fe56aee3545afb07dd1ac46dba6`
- `c4_w8_g8_s48.json` (`1–48`): `3d537155b362445a6f3224f29a92884944ad84b83d61b7595b417c2ac23d244c`
- `c5_w7_g24_s48.json` (`1–48`): `81d8814de9b0bb00cb3976e2ade1af3292b85e5a2aacfe2bd8dbcec2ab8e70e6`
- `c6_w8_g24_s48.json` (`1–48`): `63d92acb6ea4158b377ec1b802009b4bdafdc63f712b7f03727ae9709034301d`
- `s1_w4_g8_s64.json` (`1–64`): `c517ad62d2930b7c9ad6f51e4a27314685878491be0efedc710f52e5b68e17cd`
- `s2_w6_g8_s48.json` (`1–48`): `ddf3deb97ab19332a2a4f071aefc5a96cac8d3af443f916965687f5f7b2f227a`
- `s3_w7_g8_s56.json` (`1–56`): `5c1cd24ee41e84c5d84af42f1673bc306df0f78f1f3ed1a4ca1c98662ffa95dd`
- `s4_w8_g8_s64.json` (`1–64`): `7382f5892ea8f48564c57d4c5d5e91993a58d36f1dcbcb0a6e3fc77d6b4ea057`
- `s5_w6_g16_s96.json` (`1–96`): `15496216de793304ffa0ad18787f0bea05a6b186985a5aeaad6a3ec88a6a96f9`
- `s6_w7_g16_s112.json` (`1–112`): `7b007bb42f5bbe338c81ea465e85653a1f00a5b163ba6f41c4a2db4d814e7675`
- `s7_w6_g24_s144.json` (`1–144`): `c9a41f8afb0a0db5a295ad5aa56f0cdcd8fb86e15532802f50ca235714b50418`
- `s8_w7_g24_s168.json` (`1–168`): `304e1a43a7740c01101110661e101d54d64368205635417ec759e51807257877`
- `s9_w8_g24_s192.json` (`1–192`): `aa5ff6da3e73187381f12f7f3897f314c4ecf0a96aa22bf1fdee1ee98413116b`
- `telemetry.json`: `b6a4d8c6a3ce98acbac54ce7f93accf20a10ca8b85701f915e5f629e5643700e`
