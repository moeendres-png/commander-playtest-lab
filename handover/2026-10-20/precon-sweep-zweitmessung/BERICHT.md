# Precon-Pod-Sweep — unabhängige Zweitmessung (M1)

**Zwischenbericht nach Schritt 2 (Reproduktion), Stand 2026-10-20.** Der Endbericht ersetzt diese Datei nach den Schritten 3–6.

Source Lock: Lab `ed2fbae26` (main, Merge #926) · Engine-Pin `043579bb7829fa866ade893909c9ba4825a18b23` (XMage 1.4.62) · Reine Messung, keine Repo-Änderung, kein Fix, kein Repin.

## Schritt 0 — Setup (LOCAL_OBSERVED)

- Maschine: 2 Kerne, ~8 GB RAM, JDK Temurin 17.0.20.1, Maven 3.9.9 (Details: `versions.txt`).
- Mage am Pin gebaut: BUILD SUCCESS (7 Module, 9:02 Min), Artefakte 1.4.62 lokal installiert.
- Bridge `mvn verify`: **1120/1124 Tests grün.** 4 Fehler, alle in `XmageFullGameReplayExportTest`: In einer frischen JVM schlägt die Card-Repository-Initialisierung fehl (`XMAGE_CARD_REPOSITORY_INIT_FAILED`); im Isolationstest identisch reproduziert. Die Bridge redigiert die Ursache per Design; die H2-Trace-Datei der geteilten DB (`engine-bridge/target/db/`) zeigt fehlende Tabellen/Indexe — DB-Zustand als Ursache ist eine Hypothese (CODE_DERIVED, nicht belegt), Plattenplatz und Fremdprozesse sind ausgeschlossen (95 GB frei, keine Java-Prozesse). Surefire-Report der Klasse: `surefire_replay_export.xml`. Import- und Full-Game-Pfade (die M1/M2 benutzen) sind von dem Befund nicht betroffen.
- Mess-JAR danach per `mvn package -DskipTests` gebaut: sha256 **`3dd2720419e1a8a86ea309b60c50e383c156d34dd141f01ca4a7302560d8572d`** (`jar_sha256.txt`). Referenz-JAR der Erstmessung: `3f6531d7…` — Byte-Identität ist laut Auftrag nicht gefordert; die Kalibrierung unten ist der Vergleichbarkeitsnachweis.

## Schritt 1 — Kalibrierung (LOCAL_OBSERVED): BESTANDEN

`measure_precon_imports.py --enumerate-missing`, frisches Workdir, produktiver Importpfad: **182/195 OK, 13 FAILED, 0 Infrastrukturfehler**, 62,6 s. Fehlende Karten: **31 distinkte Namen, 33 Einträge — Deck für Deck und Zone für Zone identisch** zur Referenz (`docs/PRECON_VALIDATION.md`). Das Setup ist damit vergleichbar; kein STOPP.

## Schritt 2 — Reproduktion Plan-Seed 1 / Spiel-Seed 1 (LOCAL_OBSERVED)

| Größe | Erstmessung (Referenz) | Diese Messung |
|---|---|---|
| Pods | 46 | 46 |
| ok | 37 | 37 |
| failed | 9 | 9 |
| Fehlerfamilie | XMAGE_ACTION_EXECUTION_FAILED (9×) | XMAGE_ACTION_EXECUTION_FAILED (9×) |
| Failed Pods | 005, 008, 011, 027, 028, 035, 037, 040, 042 | **identisch, keine Differenz** |
| Decks in ≥1 ok-Pod | 146 | 146 |
| Decks nur in failed Pods | 36 | 36 |

**Die Reproduktion trifft die Referenz in jeder verglichenen Größe exakt.** Die Semantic-Hashes aller 37 ok-Pods stehen vollständig in `sweep_p1g1.json` (Spalte `semantic`) und unten in der ok-Pod-Tabelle; der maschinenübergreifende Hash-Vergleich erfolgt mit beiden Messdateien auf Claudes Seite. Laufzeit hier: Summe der Pod-Zeiten 2660,8 s bei `--workers 1` (2 Kerne) gegenüber ~55 Min auf 4 Kernen mit `--workers 2` in der Erstmessung.

### Messvorfälle (gehören zur Ehrlichkeit der Messung, nicht zum Engine-Ergebnis)

1. **Erster Sweep-Versuch (Umgebungsfehler, verworfen):** 46/46 `ENGINE_FAILURE` in je ~0,45 s. Ursache per Tee-Mitschnitt der Bridge-Streams bewiesen: `precon_pod_sweep.py` lädt `commander_lab` aus der installierten Venv, die auf den Haupt-Clone (Stand vor dem Repin) zeigt — das Szenario band Engine-Commit `348b37db`, die Bridge meldete korrekt `043579bb`, der Handshake beendet fail-closed vor jedem Deck-Import. Korrektur ohne Repo-Änderung: `PYTHONPATH` auf die Worktree-`src`. Die verworfenene Datei liegt als `sweep_p1g1_attempt1_venv-mismatch.json` nur in den Arbeitsdaten, nicht in dieser Abgabe.
2. **Runtime-Neustart nach Pod 027:** Der Sweep-Prozess wurde von einem VM-Neustart gekillt (28/46 Pods waren inkrementell gespeichert). Die restlichen 18 Pods wurden mit der Sweep-eigenen Maschinerie nachgefahren (gleicher Plan — Konsistenz gegen die 28 vorhandenen Zeilen geprüft —, gleiche Seeds, `bench._play`, sequentiell) und in dieselbe Berichtsdatei zusammengeführt (Skript: `replay/continue_sweep.py`). Messmethode unverändert.
3. Kein Pod dieses Laufs zeigt `XMAGE_CARD_REPOSITORY_INIT_FAILED`, `BRIDGE_TIMEOUT` oder `DECISION_ADVANCE_TIMEOUT`; kein ok-Pod ohne `semantic`-Hash. (Vorgabe aus dem Nachtrag: Solche Zeilen würden gesondert gemeldet und nicht als Engine-Abbrüche gezählt.)

### ok-Pods (37)

| Pod | Winners (Seats) | Decisions | wall_s | semantic (SHA-256) |
|---|---|---|---|---|
| pod-000 | 3 | 2241 | 92.4 | `510a11272479332ee2ff621b1d4580bd6f84d4d81839b1bfe3d782491b908385` |
| pod-001 | 1 | 2856 | 55.62 | `c38bebff830f02236f5b878bcbd1077a465931862fa3e688a814c427bc838958` |
| pod-002 | 1 | 5938 | 84.56 | `090d0f2fe72567894182f8ec112d096525971c717fbb6e68bc98112a849cba0c` |
| pod-003 | 3 | 2143 | 40.49 | `9cc0e11a9663a7107a81d3776b1f032445f16cfb045be3c63fdb70e4381299fd` |
| pod-004 | 3 | 3675 | 63.22 | `9f8854db0872c86d9ba00a0de6b625fe09bdd1cc76d89d34aeb0c58b0404a117` |
| pod-006 | 1 | 3191 | 55.03 | `15e886971a46c1c0e404faf71b6fa56e998e24e165f6164eb233d3d45dfc4957` |
| pod-007 | 1 | 5611 | 85.75 | `ee779af472fa2abaa270dc6e077736ff22aa71f03fa50193894f0a0add4d6706` |
| pod-009 | 4 | 2976 | 54.12 | `e4a966445592b3d86a4b8eaaf6b9dd6fef49ce78e9d613186dac5372397a0393` |
| pod-010 | 1 | 5643 | 115.33 | `dae9ca4e3279d8b2f43815d165db8a92d1c23f4757bd5fdec26eb8ea35a45cb3` |
| pod-012 | 2 | 3252 | 68.83 | `21e723d7861e2ca6a980772653eea6620b6cd71701335961236fdbbda1276fa0` |
| pod-013 | 1 | 3056 | 64.73 | `f6cfa282b978922d7cbe5a8405ba865535b3fc87f848bc8eb68f45bf1e14b13b` |
| pod-014 | 2 | 5182 | 89.19 | `c8d24c81cb21c2b41baad46d1146f279ef6d1f11f8cd1704d87424e5e09e4ce4` |
| pod-015 | 2 | 3320 | 67.58 | `55022d792b3d5fbe43250faebd9a8eff8d504f532c2c8a26cc99c151d052b818` |
| pod-016 | 2 | 2022 | 49.45 | `38101d74528531253d472f579931d839313ce35650c69eb73dab336fd03e7db5` |
| pod-017 | 4 | 2517 | 51.89 | `0e6fc99a39b924ffa095e2d230e48e0b6a7262929104f4f841d30f19e3074544` |
| pod-018 | 2 | 2359 | 51.15 | `a9be4ede18f8ff8ceb1a4ea7f00c903fc0351e6d524cf79e95c1c21f698a5040` |
| pod-019 | 1 | 3341 | 62.76 | `de7e9b399ada28b74f4fab099e97ae2bbaf0f86abf436a3dd6574322f357b2c9` |
| pod-020 | 1 | 2200 | 46.2 | `aa31f7d9943f17662223fcdb8f03fa1f2ab6630f065fb745fd75c7e89fec4356` |
| pod-021 | 2 | 3190 | 68.25 | `61f92c114ddd816fe00fabd87a3d31ff5247c80aef7549cafb65d52a555d961b` |
| pod-022 | 1 | 1972 | 36.51 | `16e21f2532811a00f6a40616e9727f0c2400077f4836df630fb85fcd1189e782` |
| pod-023 | 4 | 2771 | 53.47 | `d5e57f52f212006a0086e0d662de221f11c0ae77a483ad04e23441551cdcb135` |
| pod-024 | 1 | 2958 | 53.31 | `9c674a201e767fd977de26c412067adc63799e7f8322f6b096a44b3a0f73d7b1` |
| pod-025 | 1 | 2071 | 44.97 | `6a9c1803bc785a159e77c1d078324c4bcc256d17d060c0b15f0ea042fecec9e4` |
| pod-026 | 2 | 3359 | 54.16 | `b224ad58f9f6cb45cb0fd98a76e448232ab25bde1a94061d7faa16648645d1ce` |
| pod-029 | 3 | 3017 | 52.35 | `ff71f5b7710535ff153b830e83ea86ff49dfecf1c8bb5ee700002bc08bf1a50c` |
| pod-030 | 2 | 5180 | 95.04 | `e89a039ea00065ba08059c39be4cb7895423ac35f5d09ddf842cfc064b6241cb` |
| pod-031 | 3 | 4197 | 67.1 | `15b3ec09f1653d35b0fecf4d8071f21368cc0deb2b50efe1f184ce52a4d58622` |
| pod-032 | 3 | 4735 | 85.99 | `a8d7be94a13aaf7257ce3d104e56f502b0085be0928b204a8ae9d0d12ce28b19` |
| pod-033 | 1 | 4047 | 63.51 | `1b23f691ee603dc477aa2f126c3efb1ccfc1951f3f7829607efa11b14d4866f2` |
| pod-034 | 1 | 4260 | 66.91 | `03ece1c82f407bca90a973d934c4d16c2d9b9b578fa509860b143cf2e4fd62d1` |
| pod-036 | 1 | 3172 | 58.32 | `8435682a336e030e834435da602b6b2e7c7d1c441ffadf88c5949f71ff6b91a1` |
| pod-038 | 1 | 2710 | 51.71 | `235c4656eb2b011e56c1272bfc5e83604a4d6a70d4a4d097c28b9031c2eab049` |
| pod-039 | 2 | 4715 | 66.24 | `dda5b7007b95614e2ef52f66a291dfd13998a0ba4a21c14435adf31546e581fd` |
| pod-041 | 4 | 2299 | 47.27 | `314e663d96d8e7170732dd1c95034616d264ad282dac824395869d2e89a7517c` |
| pod-043 | 1 | 3105 | 56.97 | `dac2d9552ca989706154bb1482ab0e7d69647bc92f3b9aeb8ce4c24c5e3ce082` |
| pod-044 | 3 | 2688 | 48.15 | `0cdc5a9ed001621bf1cb7540a7752263525e9cf00f52d6542d45557956e17423` |
| pod-045 | 2 | 3391 | 60.14 | `aec71fc529baa75de273b15d2fd4810f91c24dd61ce996e8a5863c984e9e07c4` |

Auffälligkeiten: keine leeren Winners; Decisions min 1972 / Median 3172 / max 5938; wall_s Median 58.3 s, kein Pod über dem 3-Fachen. Keine Deutung an dieser Stelle.

### Failed Pods (9) — nur Befund, Ursachenanalyse folgt in Schritt 4

| Pod | Decks | wall_s | Fehlerfamilie |
|---|---|---|---|
| pod-005 | 2026_dance_of_the_elements, 2021_lorehold_legacies, 2025_limit_break_collector_s_edition__final_fantasy_vii_, 2013_power_hungry | 38.81 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-008 | 2025_revival_trance_collector_s_edition__final_fantasy_vi_, 2022_legends__legacy, 2022_party_time, 2018_nature_s_vengeance | 50.96 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-011 | 2023_rebellion_rising, 2024_quick_draw, 2022_bedecked_brokers, 2022_tyranid_swarm_collector_s_edition | 36.94 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-027 | 2024_hail__caesar, 2026_quandrix_unlimited, 2020_timeless_wisdom, 2023_eldrazi_unbound | 41.77 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-028 | 2023_ahoy_mateys, 2017_vampiric_bloodlust, 2021_quantum_quandrix, 2013_eternal_bargain | 22.05 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-035 | 2025_jeskai_striker, 2025_counter_blitz_collector_s_edition__final_fantasy_x_, 2022_riveteers_rampage, 2021_planar_portal | 41.01 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-037 | 2024_peace_offering, 2025_temur_roar, 2023_from_cute_to_brute, 2021_dungeons_of_death | 30.11 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-040 | 2025_mardu_surge, 2021_phantom_premonition, 2022_buckle_up, 2023_the_hosts_of_mordor | 38.36 | XMAGE_ACTION_EXECUTION_FAILED |
| pod-042 | 2013_nature_of_the_beast, 2024_desert_bloom, 2017_arcane_wizardry, 2021_coven_counters | 32.15 | XMAGE_ACTION_EXECUTION_FAILED |

Die der Erstmessung per Einzel-Replay zugeordneten Karten (Osgir, Grim Hireling ×2, Collective Effort, Ruthless Radrat, Skeletal Scrying, Peerless Recycling, Imposter Mech, Marath) werden im Fehlerkatalog (Schritt 4) gegen die neuen Läufe abgeglichen; neue Fälle aus den Läufen 2 und 3 kommen dort hinzu.

## Nächste Schritte

Sweep Plan-Seed 2 / Spiel-Seed 1, danach Plan-Seed 3 / Spiel-Seed 1 (sequentiell), dann Fehlerkatalog, ok-Pod-Tabellen und Abdeckung über alle Läufe als Endbericht in diesem Ordner.
