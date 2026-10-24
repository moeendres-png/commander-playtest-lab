# Max-Review — 00_ABDECKUNG.md (Pass A: Lesen mit Abdeckungsnachweis)

Stand: Lab-main `ee47312a70d1515a8e587bbdba98db03f610d16f` (Worktree `~/workspace/github/wt-maxreview`),
Engine-Pin `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e` (v13, Fork-Worktree `~/workspace/github/wt-mage-v13`),
Bridge-Jar selbst gebaut, SHA256 `0fda80ece7e0aa9446c24552bb7d4e9f1a2f987509f3215a4d614e29da5fddb9`.
Lese-Agenten: nur lesend, keine Writes/Pushes/Spiele/Builds. Laufzeitverhalten ist in
allen Bereichen NICHT GEPRÜFT — alle Befunde hier sind Lese-/Code-Befunde.
Sammlungsdaten (`data/collections/**`, `data/coverage_decks/collection/**`) wurden
weder gelesen noch zitiert.

## Bereich 1 — Agentenregeln und Mission (90 Dateien)

Gelesen (alle): `AGENTS.md` (390 Zeilen), `CLAUDE.md` (66), `docs/PROJECT_MISSION.md` (71),
`docs/MODULE_MAP.md` (149), `docs/CURRENT_EXECUTION_AUTHORITY.md` (52).
`docs/claude/**`, alle gelesen: `REPIN_RUNBOOK.md` (96), `SESSION_PLAYBOOK.md` (167),
`handoffs/STRUCTURAL_CALIBRATION_AND_BRIDGE_EFFICIENCY_2026-10-12.md` (125), `state/HANDOFF.md` (27).
`docs/performance/**` Berichte, alle gelesen: `BATCHING_QUALIFICATION_2026-10-22.md` (204),
`CI_QUALITY_SHARDS_2026-10-21.md` (81), `DETERMINISM_PROBE.md` (110),
`PILOT_RANK_SENSITIVITY_PROTOCOL.md` (150), `PRECON_IMPORT_V13_2026-10-23.md` (36),
`REFERENCE_36_SEEDS_2026-10-24.md` (67), `T3_APPCDS_EVIDENCE_LANES_2026-10-23.md` (42),
`UPSTREAM_DELTA_2026-10-23.md` (159), `V12_BRIDGE_UND_MOTOR_2026-10-22.md` (106),
`XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md` (217), `XMAGE_FULL_GAME_SPEED_2026-10-12.md` (113);
`xmage-card-scan-bulk-lookup.patch` (92) teilweise (Kopf, ca. 30 Zeilen).
`measurements-2026-10-12/**` teilweise (Kopf/Struktur, außer Logs gelesen):
`README.md` (32), `single_copy.patch` (17, gelesen), `tools/bench4p.py` (97),
`tools/coverage_ab.sh` (13, gelesen), `tools/jfragg2.py` (64), `tools/single_copy.patch` (17, gelesen),
`results/ab_*.json` (je 45–49 Zeilen, je 4 Spiele), `coverage_*.log` (14–20, gelesen),
`par_lazy_r1.log` (1, gelesen).
`measurements-2026-10-21/**` alle teilweise (Kopf/Schlüssel; `wc -l = 0` = einzeiliges JSON, nicht leer):
`A1_*.json` (249–483), `A2_*.json` (893), `C1_*.json` (446), `R1_*/R2_*.json` (441–841),
je `.time.json` (0), `failpath.log` (8, gelesen).
`measurements-2026-10-22/-10-23/-10-24/**` alle teilweise:
`batching-memory-with-deck-release.json` (1686), `batching-qualification-v12.json` (4604, 44 Batches),
`bridge-release-decks.patch` (90, Kopf 30 Zeilen), `precon-imports-v12.json` (1029),
`s1/pod*-40.json` (0, minifiziert, je 160 Spiele), `s1/result.json` (104), `t3/*.json` (59–62, je 4 Spiele),
`upstream-delta.json` (1502), `real36_main_053708e56_run{1,2}.json` (483, je 36 Spiele).
NICHT gelesen in Bereich 1: keine der angefragten Dateien (nur die genannten Teil-Lektüren).

Kernbefunde: Mission = praktischer Simulator für echte Deckbau-Entscheidungen; Korrektheit ist
Mittel, nicht oberste Doktrin (`docs/PROJECT_MISSION.md:6,11-13,18-19`). Rollen: Owner entscheidet
Weniges, Koordinator-Sitzung mit Delegation entscheidet Technik/Qualifikation
(`AGENTS.md:136,167,224,242-247,317-323`). Evidenz: nur die Rules Engine entscheidet Legalität;
UNKNOWN ≠ PASS; lokale Beobachtung ≠ Qualifikations-Kredit (`AGENTS.md:45`,
`docs/PROJECT_MISSION.md:47-55`, `docs/claude/SESSION_PLAYBOOK.md:66`).
Performance-Vorgaben: nur interleaved messen (ABBA, CPU vor Wall); Batching nur Mess-Lane;
Evidence-Lanes immer 1 Spiel/JVM; Hebel unter 3 % werden verworfen und dokumentiert
(`docs/claude/REPIN_RUNBOOK.md:44-46`, `docs/performance/BATCHING_QUALIFICATION_2026-10-22.md:6`,
`docs/performance/V12_BRIDGE_UND_MOTOR_2026-10-22.md:73`,
`docs/performance/T3_APPCDS_EVIDENCE_LANES_2026-10-23.md:25-26`).

## Bereich 2 — Bridge und Protokoll (250 Dateien, 87.702 Zeilen)

Gelesen: `engine-bridge/pom.xml` (138), `config/rules_engines.json` (115).
Main `engine-bridge/src/main/java/org/commanderlab/xmage/` (39 Dateien, 25.033 Zeilen):
vollständig gelesen (15): `ActorSafeIdentity.java` (73), `Main.java` (123), `XmageAuditEventLog.java` (131),
`XmageCommanderGames.java` (59), `XmageFullGameJsonlBridge.java` (771), `XmageLibraryShuffleWatcher.java` (46),
`XmageLondonMulligan.java` (52), `XmageProvider.java` (192), `XmageRulesSeedBinding.java` (72),
`XmageSeating.java` (66), `XmageStableOrder.java` (123), `XmageStartingPlayerPrompt.java` (44),
`XmageStateFingerprint.java` (160).
Teilweise (23, Kopf/Kernabschnitte/Grep): `ExternalDecisionController.java` (808),
`JsonlBridge.java` (1200), `Phase6DifferentialAdapter.java` (419), `XmageActionExecutor.java` (280),
`XmageBridgePlayer.java` (669), `XmageCausalEliminationReconstruction.java` (96),
`XmageCausalStackReconstruction.java` (667), `XmageControlDivergenceReconstruction.java` (294),
`XmageDeckImporter.java` (504), `XmageFirstTurnSetupWatcher.java` (214),
`XmageFullGameActionProjection.java` (973), `XmageFullGameDecisionController.java` (1071),
`XmageFullGamePlayer.java` (4216), `XmageFullGameReplay.java` (125),
`XmageFullGameReplayVerifier.java` (262), `XmageFullGameSession.java` (1367),
`XmageFullGameStateRedactor.java` (862, Z. 390–630 gelesen), `XmageGameManager.java` (1683),
`XmageHiddenStateRestoration.java` (418), `XmageMidgameCausalBridge.java` (978),
`XmageMidgameJsonlBridge.java` (1711), `XmageNativeStateRestoration.java` (2913),
`XmagePublicEventWatcher.java` (290), `XmageRulesRngResultTape.java` (187),
`XmageTemporalProgressionDriver.java` (246).
NICHT gelesen (1): `XmageLosslessHiddenPlan.java` (668, kein Inhalt geöffnet).
Tests `engine-bridge/src/test/java/org/commanderlab/xmage/` (209 Dateien, 62.530 Zeilen):
alle NICHT gelesen, nur inventarisiert (vollständige Name:Zeilen-Liste liegt beim Koordinator-Bericht;
Schwerpunkte: `XmageFullGameDecisionClassMatrixTest` (1538), `XmageMidgameCausalTest` (2204),
`XmageActualCardCorpusTest` (2477), `XmagePb03Tier1RowsTest` (1940), zahlreiche Multiplayer-Tests).

Kernbefunde: drei JSONL-Lanes über stdin/stdout, eine Zeile = ein Request/Response; Transport 2.0.0
(`Main.java:21,37,41`, `XmageFullGameJsonlBridge.java:56-60`, `XmageProvider.java:25`,
`XmageFullGameDecisionController.java:34`; Serialisierung Gson, kein Jackson gefunden).
Entscheidungsklassen: exakt 17 deklarierte Klassen, nur diese werden publiziert
(`XmageFullGameDecisionController.java:460-464`: priority, target, choose_object, target_amount,
mana_payment, mode, announce_x, amount, multi_amount, trigger_order, choice, replacement_effect,
pile, choose_use, mulligan, declare_attacker, declare_blocker); Projektion entscheidungsgebunden,
nicht global (`XmageFullGameActionProjection.java:89,806,859`; Inline-Limit 256).
Zustandsansichten principal-scoped; Roh-Engine-Objekte verlassen die JVM nie; Gegner-Hand und
Bibliotheksreihenfolge bewusst nicht ausgegeben (`XmageFullGameStateRedactor.java:390,471,488-507,554`;
Fremd-Principals als `op-<seat>`-Tokens, `ActorSafeIdentity.java:73`-Logik).
Fehlerpfade fail-closed, harte Pflichtfelder, drei Timeout-Ebenen
(`XmageFullGameJsonlBridge.java:177,205,220`, `XmageFullGameSession.java:42-43,1107`,
`XmageFullGameDecisionController.java:80,127-145,215`, `XmageBridgePlayer.java:140`).
Pin: `rules_engines.json` alleinige maschinenlesbare Autorität, Commit `90f5c4d3f8` (v13),
Engine 1.4.62 (`config/rules_engines.json:41,77-78`, `XmageProvider.java:22-23`,
`engine-bridge/pom.xml:16-18`); Freeze-Identität bleibt bewusst auf älterem Commit
(„A pin move never edits architecture_freeze") — Pin ≠ Freeze-Identität, so vorgesehen.

## Bereich 3 — CPL-Kern (28.518 Zeilen gelistet; Basis `src/commander_lab/`)

Schwerpunkt, alle gelesen (10.372 Zeilen): `engine/rules/full_game.py` (1751),
`engine/rules/full_game_batch.py` (783), `engine/rules/full_game_comparison.py` (855),
`engine/rules/full_game_pilot/__init__.py` (9), `engine/rules/full_game_pilot/choices.py` (906),
`engine/rules/full_game_pilot/combat.py` (266), `engine/rules/full_game_pilot/common.py` (704),
`engine/rules/full_game_pilot/payment.py` (1320), `engine/rules/full_game_pilot/policy.py` (315),
`engine/rules/full_game_pilot/priority.py` (364), `engine/rules/full_game_pilot/state.py` (908),
`engine/rules/full_game_pilot_views.py` (1756), `engine/rules/full_game_pilot_targets.py` (202),
`engine/rules/full_game_pilot_blocks.py` (233).
Rest `engine/rules/`, teilweise (Funktionsliste + Kernaussagen, 3741 Zeilen): `__init__.py` (83, vollständig),
`base.py` (132), `bridge.py` (814), `failure_privacy.py` (219), `manager.py` (38), `phase85.py` (321),
`project.py` (214), `protocol.py` (77), `registry.py` (254), `replay.py` (84), `tactical.py` (1158),
`validation.py` (224), `wire_types.py` (123).
`agents/`, teilweise (4152 Zeilen): `card_knowledge.py` (389, vollständig), `pilots.py` (1806,
BasePilot-Kern Z. ~290–690 vollständig, Spezialpiloten nur Inventar + Stichproben), `ensemble.py` (568),
`validation.py` (460), `openai_workflow.py` (385), `guardrails.py` (121), `live_routing.py` (118),
`demo.py` (104), `optimization_orchestrator.py` (102), `__init__.py` (71), `tracing.py` (28).
`mulligan/`, teilweise (1343): `lab.py` (1178), `canonical.py` (162), `__init__.py` (3).
`decision/`, teilweise (1621): `quality.py` (704), `context.py` (463), `information.py` (338),
`bundle.py` (115), `__init__.py` (1).
`optimization/`, teilweise (1374): `experiments.py` (497), `search.py` (374), `constraints.py` (262),
`jp5.py` (166), `__init__.py` (75).
`engine/structural/`, teilweise (5915): `simulator.py` (2109), `profiles.py` (1228), `fixtures.py` (538),
`simulator_fidelity.py` (349), `batch.py` (335), `xmage_calibration.py` (308), `card_facts.py` (260),
`project.py` (203), `fact_fidelity.py` (178), `telemetry.py` (176), `validation.py` (84),
`triggers.py` (68), `scheduling.py` (40), `__init__.py` (39).
Alle relativ genannten Pfade liegen unter `src/commander_lab/`; kein angefragter Pfad fehlt.
NICHT gelesen: keine der angefragten Dateien; Laufzeitverhalten NICHT GEPRÜFT.

Kernbefunde: Pilot-Architektur — XMage entscheidet Legalität, Lab-Pilot nur Ranking; Unbekanntes
fällt geschlossen aus (`full_game_pilot/policy.py:29,52-58`, `full_game.py:959,131`).
Priority-Fluss stark gefiltert vor der Wahl (`priority.py:24,113`; X-Zauber ohne Rest-Mana,
Ausnahmen in `payment.py:60`; Utility aus `agents/pilots.py:670`; Mana-Fähigkeiten, die nur Mana
floaten, auf `STANDALONE_MANA_ABILITY_UTILITY = -1.0`, `agents/pilots.py:287,527`).
Targets/Blöcke: Seitenlogik ±8 (`full_game_pilot_targets.py:28,45,100`, `state.py` `_target_alignment`);
Angriffs-Score (`full_game_pilot_views.py:1466`), Block-Score (`:1587`);
deklarationsweite Block-Runde (`combat.py:92`, `full_game_pilot_blocks.py`; Leiter bei Ablehnung:
Urteil → maximal → leer → Einzelblöcke → Fail-closed-Fehler).
Mulligan im Spiel: Score-Modell, kein Landzählen, Keep ab 3 Mulligans erzwungen
(`choices.py:86,106`; Modell `agents/pilots.py:355,349,442`); `mulligan/lab.py` und
`mulligan/canonical.py` sind Offline-Evaluierung, nicht die Im-Spiel-Regel.
Kartenwissen: gedruckter Katalog + kuratierte Profile; unbekannte Karten = kein Wissen, nie erfunden
(`agents/card_knowledge.py:25,130,211,256,314,352`). Auffälligkeit: zahlreiche hartcodierte
Einzelkarten-/Prompt-Sonderfälle in `full_game_pilot_views.py`/`choices.py` (Engine-Lücken-Workaround,
Wartungsfläche).
Strukturell: `engine/structural/simulator.py:201` (`StructuralSimulator`, `structural-0.6.1`)
ist sauber als `structural_model_estimates` gelabelt, kein Regelentscheider in der Full-Game-Lane.
`decision/` und `optimization/` sind Deckbuilding-/Bewertungs-Werkzeuge, keine Spiel-Entscheidungslogik
(Grep über `engine/rules/` + `agents/pilots.py` fand keinen Import; repo-weite Importfreiheit NICHT GEPRÜFT).
Dichteste Stelle: Zahlungs-/X-Logik (`payment.py:444,487,871,1178`).

## Bereich 4 — Skripte/Tests/Config

`scripts/` (109 Dateien, 33.872 Zeilen; alle teilweise außer 5 winzigen Shell-Skripten gelesen).
Größte Läufer: `run_midgame_capability_probe.py` (3263), `run_current_boundary_qualification.py` (1845),
`pilot_decision_report.py` (1422), `benchmark_xmage_full_games.py` (297, semantischer Transkript-SHA
als Identitätsbar). Messung läuft auf der echten Engine, nicht auf Modellen; Structural-Modell-Messung
(`calibrate_structural_vs_xmage.py`, `measure_model_resolution.py`) ist in den Skripten selbst getrennt.
`tests/` (455 `test_*.py`-Dateien, 4710 gezählte `def test_`-Definitionen — Definitionszahl, NICHT
Laufzeit-Fallzahl; parametrisierte Fälle vervielfachen sie, Ausmaß NICHT GEPRÜFT; alle Bereiche nur
teilweise: Zählung + Stichproben): unit 295 Dateien (inkl. 10 Fixture-Helfer ohne Tests), 2260 Defs,
53.276 Zeilen; integration 21 Dateien, 40 Defs, 1279 Zeilen; qualification 92 Dateien (inkl. 1 Helfer),
1580 Defs, 39.010 Zeilen; golden 4 Dateien, 8 Defs, 177 Zeilen; differential 2 Dateien, 22 Defs,
443 Zeilen; property 5 Dateien, 8 Defs, 253 Zeilen; fuzz 1 Datei, 5 Defs, 188 Zeilen; mutation 1 Datei,
3 Defs, 24 Zeilen; architecture 2 Dateien, 8 Defs, 162 Zeilen; contract 4 Dateien, 16 Defs, 380 Zeilen;
agent_evals 1 Datei, 4 Defs, 98 Zeilen; foundry 34 Dateien (inkl. conftest.py), 730 Defs, 15.094 Zeilen
(eigenes Subsystem: Agent-Harness/Review/Push-Tooling, NICHT Simulator-Tests); regressions 4 Dateien,
14 Defs, 308 Zeilen; top-level 2 Dateien, 12 Defs, 358 Zeilen; Hilfsdateien ohne `def test_` 17 Stück
(u. a. `tests/conftest.py` 159 Zeilen, `tests/pytest_shards.py` 274 Zeilen).
Testauswahl gelesen, nicht ausgeführt: Quality-Job `pytest … --shards=4 --ignore=tests/qualification`
(`.github/workflows/ci.yml:74`), Infrastructure-Job nur `pytest -q tests/qualification`
(`.github/workflows/production-qualification.yml:42`); Shard-Gewichte decken 335 Dateien ab
(`tests/pytest_shard_weights.json`), Rest läuft im letzten Shard mit (dadurch nicht tot).
Ob Ownership-Guard / Hygiene-Zähler aktuell grün sind: NICHT GEPRÜFT.
`config/` (15 Dateien; alle vollständig gelesen außer SpotBugs-Baseline teilweise):
`rules_engines.json` (115, sole Pin-Autorität, `primary_engine.commit` = `90f5c4d3f8…` Z. 41,
Freeze an `engine_commit b479fe74…` Z. 102, `current_qualification` Epoche zum v13-Pin AF00–AF11 PASS,
Maven 3.9.16, Protokoll 2.0.0, `required_missing_capabilities: []`, Vorgänger-Historie v5–v13);
`default.yaml` (19), `evals.yaml` (19, unit/property/differential 1.0, golden 0.95 Z. 6,
golden_critical 1.0, min. 250 Property-Fälle, min. 3 externe Differential-Fälle,
max. 2 % abgebrochene Property-Spiele), `structural.yaml` (15), `calibration_policy.json` (19),
`pilot_ensembles.json` (33), `phase7_optimization.json` (36), `J_P5_ROBUST_OBJECTIVE_v1.json` (1),
`J_P5_SEARCH_POLICY_v1.json` (30), `J_P6_BENCHMARK_POLICY_v1.json` (38), `deck_decision_registry.json` (21),
`openai_mcp_stdio.json` (32), `openai_workflow.json` (22), `protected_cards.json` (1, leer `{}`),
`spotbugs-baseline.json` (125, teilweise).

Kernbefunde: Pin-Autorität zentral, aber Freeze ≠ aktueller Pin. Test-Schieflage: riesige
Unit-/Qualifikations-Blöcke, dünne echte Spiel-Abdeckung (Integration 40, Golden 8, Property 8,
Fuzz 5, Mutation 3 Definitionen); `config/evals.yaml:6` erlaubt Golden sogar 0,95 statt 1,0.
Tote Tests im engen Sinn: keine durch Nicht-Einsammlung, aber 15 Repin-Dateien per Design stillgelegt
(`tests/qualification/test_xmage_precon_commander_cards_repin_v13_20261023.py:93`,
`superseded_by_later_repin`-Skip; gezählt per `grep -rln superseded_by_later_repin`).
Falsche-Grund-Kontrollen an drei Stellen — teils dokumentiert, teils still:
(i) `tests/conftest.py:73` (`clean_tracked_worktree`, session-autouse) patcht Dirty-Worktree-Prüfungen
auf „sauber" — 41 ehemals failing Tests laufen dadurch grün, ohne dass Dirty-State je geprüft wird;
nur `real_worktree_checks`-Fixture (`:112`) erreicht echte Prüfungen.
(ii) `tests/fixtures/fake_external_engine_bridge.py:27` meldet `engine_version: "fixture-not-real"`,
behauptet aber `validation_level: external_rules_engine` — ein Protokoll-Test dagegen beweist nichts
über die echte Engine; einziger Importeur `tests/contract/test_phase85_protocol.py:52`.
(iii) `tests/qualification/test_current_boundary_native_suite_receipt.py:9` läuft „end to end with
a faked Maven process" und beweist nur den Receipt-Pfad, nicht den Engine-Lauf.
Ergänzend: `tests/unit/test_structural_xmage_calibration.py:231` skippt statt zu failen, wenn
Card-Facts nicht exportiert sind. Hygiene-Kontrolle existiert (`scripts/test_hygiene_scan.py:41`,
Gruppen `no_assertion`/`trivial_only`/`unguarded_loop`), aktuelle Zählerstände NICHT GEPRÜFT.

## Bereich 5 — Fork-Diff (Methode: Upstream-Vergleich, eingeschränkt)

Basis: Merge `7e4360a22` (2026-10-20) mit zweitem Parent `fab0f23b7` (2026-10-20, Upstream bis
„Fix Grizzlegom … (#16519)"); lokaler `upstream/master` = `bb0ed0f72` (2026-10-18),
Merge-Base HEAD↔upstream ebenfalls `bb0ed0f72`. Kein Fetch erlaubt → Upstream nach `fab0f23b7`
NICHT GEPRÜFT. `git log fab0f23b7..HEAD`: 150 Commits, 2026-09-14 bis 2026-10-23
(moeendres-png 106, Claude 39, foundry-implementer 5). `git diff fab0f23b7..HEAD`: 620 Dateien,
+36.739/−520 Zeilen (Mage.Sets 250, Mage.Tests 142, Mage 116, research 83, commander-lab 24, sonstige 5).
Shallow-Clone: 5 Grenz-Commits ohne lesbares Einzel-Diff (`10a739229` Merge PR #55 2026-10-07,
`2115a3dac` 2026-09-28, `73b85e1a0` 2026-09-29 F-23, `97c2b27e5` 2026-09-14 WS206,
`b784414cc` 2026-09-20 Server-Memory-Leaks) — deren Dateien sind als abweichend belegt, aber nicht
sicher einzeln attribuierbar. Keine `.dck`-Datei, kein `data/collections/**`,
kein `coverage_decks/collection/**` im Diff. Zeilenweise Prüfung aller 620 Dateien: NICHT GEPRÜFT
(Stichproben bei Schlüssel-Commits); Laufzeit/Builds/Tests: NICHT GEPRÜFT; `research/`- und
`commander-lab/`-Inhalte über Dateinamen hinaus: NICHT GEPRÜFT; `origin/master` (`16dc17ea`,
2026-10-20) nicht als Basis verwendet (HEAD ist detached Pin).

Kernbefunde: Eigene Karten: netto 51 neue Karten-Dateien in `Mage.Sets/src/mage/cards/`
(u. a. AminatouVeilPiercer, CosmicCrucible, DackFaydenHelpingHand, GalactusDevourerOfWorlds,
JaceMultiverseArchitect, KangDynasty, MoleculeMan, ScarletWitchChaoticAvenger, TeferisReproach,
WinterCynicalOpportunist, ZinniaValleysVoice). Einordnende Commits: `fe4fd1c44` (2026-10-23, 10 Karten
vierer Precon-Commander-Decks, 23 Dateien, +2.286); `7e97fb28c` (2026-10-12, Marvel-Super-Heroes-Commander,
alle 34 registriert); `7369bebc3` (2026-10-13, Secrets-of-Strixhaven-Prepare + nur
`DurnanOfTheYawningPortal.java` neu); `82a6261eb` (2026-10-13, Wakanda-Batch + KangDynasty-Fix +
Combat-Lücke in `Mage/.../game/combat/Combat.java`, 14 Zeilen); `90f5c4d3f` (2026-10-23, nur Jace-Tests).
Kein Doppel-Claim: ältere Batches (z. B. `c6954ac5e`, 11 Precon-Karten) tauchen netto teilweise nicht
mehr als neu auf, weil Upstream sie bis `fab0f23b7` ebenfalls implementiert hat; `043579bb7` (2026-10-20)
löscht 23 doppelte `SetCardInfo`-Registrierungen. Keine neue Set-Klasse vs. `fab0f23b7`; nur 5 bestehende
Set-Klassen geändert (194 geänderte Karten-Dateien + 5 Set-Klassen = 199 geänderte `Mage.Sets`-Dateien).
Regeländerungen, stärkster Block Determinismus/Reihenfolge: `381ab8695` (2026-10-20, 113 Dateien,
+223/−133, „Object sets: keep insertion order instead of identity-hash order");
`4da49dc22` (2026-10-22, 14 Dateien, +71/−25, identity-gehashte Collections in Einfüge-/
Deklarationsreihenfolge); `dd71626b3` (2026-10-22, 18 Dateien, +33/−20, feste Spielerreihenfolge);
`bd499587d` (2026-10-20, Counter-Typen in Enum-Reihenfolge); `537ce62cc` (2026-10-21, Token eines
Events in gegebener Reihenfolge); `69b33b3b8` (2026-10-11, Commander-Zonen-Entscheidungen deterministisch,
`GameImpl.java` +7/−1); `db8b588dc` (2026-10-20, technischer Gewinner und Pool of Vigorous Growth aus
Spiel-Rules-RNG); `456b0e227` (2026-10-21, Playable-Berechnung kopiert Trigger erst bei erster Verwendung);
neue Rules-RNG-Klasse `Mage/.../util/GameRandom.java` (+89, Header „WS54: authoritative game-scoped
Rules RNG"), `RandomUtil.java` +35/−2 — Unsicherheit: einzige `fab..HEAD`-Log-Zuordnung für
`GameRandom.java` ist Shallow-Grenz-Commit `97c2b27e5`, einführender Einzel-Commit lokal nicht isolierbar.
Konkret gelesener Hunk: `Mage/.../effects/common/SacrificeAllEffect.java` ab Z. ~80
(Opfer-Entscheidungen in APNAP-Reihenfolge statt Controller-Reihenfolge).
Regeländerungen Mehrspieler/Verlassen/Priority/Combat (F-/WS-/RG-Serie): `8af3d6181` (2026-10-03,
Priority-Reparatur nach State-Based-Eliminierung, `GameImpl.java` +7, Test +521); `aac1bcedc` (2026-09-30,
F-44); `278666580` (2026-09-29, `GameImpl.leave`); F-43 Combat-Quellen-Revalidierung (`895742a7b`,
`2520a248c`, `2c7806a15`, `e3c924678`, 2026-09-30; netto `CombatGroup.java` +305/−17, `Combat.java` +64/−11);
F-45 `9dbda865f` (Merge `37e4df6c9`); F-Serie Betreff-Zählung in `fab..HEAD`: F-23: 33, F-22: 4,
F-43: 3, F-20: 3, F-21: 2, F-18: 2, F-19: 1, F-28: 1, F-29: 1, F-44: 1, F-45: 1;
`2b3f0f767` (2026-09-14, WS211, autoritative Concede-Aktionsfläche); `97c2b27e5` (2026-09-14, WS206,
engine-side combat-damage legality — Shallow-Grenze, Einzel-Diff NICHT LESBAR, nur Netto-Abweichung
in `CombatGroup.java`/`Combat.java` belegt, nicht als verifizierter Einzel-Befund auszugeben);
RG-Qualifikationen Betreff-Zählung: RG-06A: 12, RG-07: 8, RG-02: 7, RG-08: 2 (belegte Seams u. a.
`266ece50b` RG-06A geordnete-Bibliothek/Face-Down-Restore in `players/Library.java`, netto Library +74/−4;
ob jede RG-Serie eine Produktions-Verhaltensänderung ist, nicht zeilenweise verifiziert);
weitere Netto-Diff-Engine-Dateien ohne sichere Einzel-Zuordnung: `GainAbilityControlledSpellsEffect.java`
(+175/−25), `BecomesFaceDownCreatureEffect.java` (+134/−3), `Game.java` (+127/−7),
`ContinuousEffects.java` (+120/−9), `SmoothedLondonMulligan.java` (+8/−8, keine Mulligan-Regeländerung
behauptet, Inhalt nicht zeilenweise geprüft); `348b37db5` (2026-10-17, enters-prepared copy lifetime,
`BecomePreparedSourceEffect.java` +7/−5).
Performance: nur zwei klar als Performance betitelte Änderungen; Rest NICHT GEPRÜFT:
`16e57239e` (2026-10-13, Playable-Berechnung kopiert Karte erst bei erster Lektüre, `GameImpl.java`
+63/−3; Laufzeitgewinn nicht gemessen); `99b18b8f7` (2026-10-13, Merge-PR #58 card-scan-bulk-lookup,
`CardRepository.java` +26, `CardScanner.java` +7/−1); kein weiterer `fab..HEAD`-Commit-Betreff enthält
perf/speed/cache/bulk (Grep über alle 150 Betreffe); Determinismus-Umstellungen auf Einfügereihenfolge
können Performance-Nebeneffekte haben — NICHT GEPRÜFT, nicht als Verbesserung behauptet.
Sonstige Fork-Abweichungen: Tests/Harness (kein Produktionsverhalten): 142 Dateien `Mage.Tests/`
(Schwerpunkte `cards/single/msc` 55, `commander/multiplayer` 25, `cards/single/soc` 8, `cards/single/frc` 8,
`multiplayer/apnap` 7, `serverside/ws211` 3, `serverside/rg02` 3, `serverside/ws206` 2 u. a.) + 5 Dateien
`Mage/src/test/`; neue Engine-Hilfsklassen (Netto-Diff, Produktion): `GameRandom.java` (+89),
`watchers/common/CommanderPlaysCountState.java` (+97), `CommanderPlaysCountWatcher.java` (+69),
`CommanderInfoWatcher.java` (+32), `abilities/common/ConnivesCreatureYouControlTriggeredAbility.java` (+54);
Nicht-Produktion im Diff: `research/` 83 Dateien, `commander-lab/` 24 Dateien (Inhalte nicht ausgewertet),
`.github/workflows/maven.yml` + `ws39-retained-base.yml`, `.foundry/sba-priority-20261003.yaml`,
`foundry/ws39/README.md`, `Mage.Server.Plugins/Mage.Player.AIMCTS/.../SimulatedPlayerMCTS.java` (1 Datei,
Inhalt nicht geprüft); Upstream-Nachzug/Pflege: Merge `7e4360a22` (Upstream `fab0f23b7` in Kandidatenlinie
`c39ab8a9`), danach `6a4d41895` (Test-Anpassung an Upstream-Verhalten) und `043579bb7` Duplikat-Bereinigung.

## NICHT gelesen / NICHT GEPRÜFT (ehrliche Liste für 99_OFFEN.md)

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageLosslessHiddenPlan.java` (668 Zeilen) NICHT gelesen.
- Alle 209 Bridge-Testdateien (62.530 Zeilen) nur inventarisiert, inhaltlich NICHT gelesen.
- Timeout-/Fail-closed-Aussagen sind Code-Befunde, keine Laufzeit-Verifikation; Flushing/EOF/Backpressure NICHT GEPRÜFT.
- Bereich 3: Schwerpunkt-Dateien vollständig, Rest nur teilweise; `decision/`-/`optimization/`-Importfreiheit nur in `engine/rules/` + `agents/pilots.py` gegrept, repo-weit NICHT GEPRÜFT; Laufzeitverhalten NICHT GEPRÜFT.
- Bereich 4: alle Skripte außer 5 Shell-Skripten nur teilweise (Kopf/Docstring/Def-Liste); alle Testbereiche nur teilweise (Zählung + Stichproben); `config/spotbugs-baseline.json` nur teilweise; ob Tests grün laufen, Hygiene-Zähler 0 sind, Ownership-Guard grün ist, oder namensungleiche Skripte indirekt getestet sind: NICHT GEPRÜFT.
- Bereich 5: Upstream nach `fab0f23b7` (2026-10-20) NICHT GEPRÜFT (kein Fetch erlaubt); 5 Shallow-Grenz-Commits ohne isolierbares Einzel-Diff; RG-/WS-Seams und `SmoothedLondonMulligan.java` brauchen Zeilenprüfung, bevor sie als Regeländerung gemeldet werden; `research/`- und `commander-lab/`-Inhalte über Dateinamen hinaus NICHT GEPRÜFT; `origin/master` (`16dc17ea`) nicht als Basis verwendet.
- Bereich 1: Messwerte in `docs/performance/measurements-**` nur als Kopf/Struktur gelesen; Richtigkeit der Messwerte selbst NICHT GEPRÜFT (keine Spiele nachgerechnet, keine Hashes verifiziert); ob HANDOFF inzwischen regeneriert wurde und ob die E1-Lanen-Differenz lane-bedingt ist, braucht Blick auf aktuellen Stand außerhalb der Lektüre.
- Handover-Lieferungen (`handover/**`), `~/workspace/tmp/**`-Spiele und die 24-/36-Seed-Läufe der Pilotphasen: in Pass A NICHT gelesen — sie sind Gegenstand von Pass B (Reproduktion/Auswertung), nicht der Lese-Abdeckung.
- Keine Datei wurde in die Repos geschrieben (Ausnahme außerhalb der Worktrees: `/tmp/fork_diff_files.txt`, reine Diff-Dateiliste, kein Bericht).
