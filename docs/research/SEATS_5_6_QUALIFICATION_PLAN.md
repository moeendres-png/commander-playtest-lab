# Qualifikationsplan für 5 und 6 Plätze: Ist-Stand, Regelfälle, Prüfplan

- **Dokument-ID:** `docs/research/SEATS_5_6_QUALIFICATION_PLAN.md`
- **Datum:** 2026-11-13
- **Kontext:** GitHub-Issue #1212, Teil B (5 und 6 Plätze). Reine Recherche, kein Produktcode. Begleitdokument zu `docs/research/PILOT_STRENGTH_OPTIONS.md` (Teil A: stärkere Piloten ohne Java-Vorausschau); die Quellenliste steht dort in Abschnitt 9 und gilt für beide Dateien.
- **Quellenstand:** Repo `commander-playtest-lab`, main `53f4836b`; Engine-Pin v15 `f4d12f6e80` (`config/rules_engines.json`). Alle Code-Fundstellen beziehen sich auf diesen Stand.
- **Regeln:** Die Freigabe von 5 und 6 Plätzen ist eine Owner-Entscheidung (A8, `docs/OWNER_DECISIONS_STUDIO_20261112.md`) und wird hier nicht vorweggenommen. Nicht Belegbares ist als `UNKNOWN` geführt; Evidenz-Klassen nach `AGENTS.md` §4 stehen an den tragenden Aussagen. Keine Deck- oder Sammlungsdaten des Owners in diesem Dokument.

---

## 1. Was der Stand heute hergibt

**Produkt-Rahmen** [CODE_DERIVED aus den Owner-Dokumenten]: Permanentes Maximum **6 Plätze**, Default **4**, gültig für PLAY und SIMULATE (2–6 Sitze) — `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md` („Binding product scope"); `docs/OWNER_DECISIONS_STUDIO_20261112.md` A3. Die Freigabe von 5 und 6 Sitzen braucht **eigene Qualifikation und eigenes Owner-Go** (A8; offene Owner-Entscheidung Nr. 4) und steht in der Roadmap **zuletzt** — nach S-1 bis S-4 bzw. nach 4-Platz-PLAY im Alltagsgebrauch (`docs/STUDIO_ROADMAP_20261112.md` S-6, P-7).

**Code lässt 2–6 generisch zu, kein 4er-Zwang** [CODE_DERIVED]:

- Python-Runner: `XmageFullGameRunner.MIN_PLAYERS = 2`, `MAX_PLAYERS = 6`, Durchsetzung in `_validate_inputs` (ausserhalb 2–6 → Fehler; Decks/Piloten-Kardinalität = `player_count`, Sitze exakt 1..N) — `src/commander_lab/engine/rules/full_game.py:1172-1173, 1686-1692`.
- Szenario-Schema `player_count` mit `ge=2, le=6` — `src/commander_lab/candidates/models.py:224`; Vergleichs-Modell max. 5 Gegner → Pod 2–6 — `src/commander_lab/engine/rules/full_game_comparison.py:87`.
- Pilot-Policy erzwingt 2–6 Laufzeit-Piloten — `src/commander_lab/engine/rules/full_game_pilot/state.py:77-83`.
- `player_count` ist Pflichtfeld des Szenarios; „4" ist Produkt-/Skript-Default (Smoke-Skript fix 4: `scripts/run_real_4p_full_game_smoke.py:124`), kein Lane-Zwang. Der Referenzsatz des Studio-Bridge-Gates ist ausschliesslich ein 4-Platz-Pod (Seeds 1–36) — `docs/STUDIO_PLAN_SIMULATOR.md`, Abschnitt „Reference set for the Studio bridge gate".

**Bridge (Java, im Baum) ebenso 2–6** [CODE_DERIVED]:

- `XmageFullGameSession.MIN/MAX_PLAYERS = 2/6`; Ablehnung ausserhalb **vor** Spiel-Erzeugung — `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java:41-43, 100-105`.
- Spiel-Erzeugung generisch: 2 Plätze = `CommanderDuel`, sonst `CommanderFreeForAll` mit `setNumPlayers(playerCount)`; kein 5/6-Sonderpfad — `engine-bridge/src/main/java/org/commanderlab/xmage/XmageCommanderGames.java:35-57`.
- **Einflussbereich ist hart auf `ALL` gesetzt** (Duel wie FreeForAll) — `XmageCommanderGames.java:43, 51`. Das ist die heutige Voreinstellung; ob `ALL` die gewollte Produkt-Einstellung für 5/6 ist, ist **nirgends als Produkt-Entscheid dokumentiert** → Festlegungspunkt in Phase 0 des Prüfplans (Abschnitt 4). Die Angriffsoption ist ebenso hart gesetzt: `MultiplayerAttackOption.MULTIPLE` (Angriff auf mehrere Verteidiger) für Duel wie FreeForAll — `XmageCommanderGames.java:42, 50`. Auch das ist eine heutige Voreinstellung ohne dokumentierten Produkt-Entscheid → Festlegungspunkt in Phase 0 (Abschnitt 4), gemeinsam mit dem Einflussbereich. Die Zugreihenfolge ergibt sich aus der Engine-Spielart FreeForAll; ihre Details sind nur im Fork prüfbar (unten).

**Tests: vorhanden, aber fast nur Schema/Policy/Mock** [CODE_DERIVED]:

- Parametrisiert 2–6 (Policy-Annahme, Pilot-State-Skalierung, Input-Validierung, Handshake, Batch-Kardinalität; Ablehnung von 1 und 7): `tests/unit/test_xmage_variable_player.py` — Python-Unit-Tests mit Fixtures, **keine echte Bridge-Partie**.
- Owner-Cap-Guard ausdrücklich nur Schema: „admission != successful XMage six-player runtime qualification" — `tests/unit/test_owner_player_cap.py:3, 34-36`.
- 5-Platz-Sitz-Mapping über eine ScriptedBridge (Mock, kein Live-Spiel): `tests/unit/test_ws223_cardinality_regression.py:406`.
- Historischer 6-Platz-Live-Beleg (Archiv, älterer Stand): volles 6P-Gate PASS mit 7.284 Entscheidungen und Replay-MATCH — `docs/archive/workstream_lab_sixplayer_20260921/R19_SIXPLAYER_ROOT_CAUSE.md:40-47`. Die Owner-Entscheidung zum 6er-Maximum führt den aktuellen Stand dagegen selbst als „6P behavior UNKNOWN / not run".
- Auf dem aktuellen Stand `53f4836b` wurde in dieser Recherche **kein** frischer 5P- oder 6P-Vollspiel-Lauf gefunden; der einzige Real-Smoke ist 4P.

**Harte Lücke bei 6 Plätzen: Replay/Tape nur 2–5** [CODE_DERIVED]: `TapeGameManifest.player_count` und `TapeSeatPrincipal.seat` sind auf `le=5` begrenzt — `src/commander_lab/semantic_replay/tape.py:49, 58`. Eine 6-Platz-Partie ist heute nicht als Tape-Manifest abbildbar; die Owner-Entscheidung führt das als „Known capability gap for 6P; do not quietly widen without review and tests" (`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`). Für **5 Plätze** deckt das Tape-Schema den Bereich ab.

**Nur im Fork prüfbar / UNKNOWN:** Ob das gepinnte `CommanderFreeForAll`/`GameCommanderImpl` (Pin v15 `f4d12f6e80`) bei 5/6 Plätzen reg korrekt spielt (Elimination, APNAP, Einflussbereich-Semantik der Engine), steht nicht im Baum — der Fork liegt nicht in dieser Arbeitskopie. Das Phase-3-Audit sagt selbst: Die gepinnte Engine habe kein explizites 6er-Cap, das qualifiziere Mehrspieler-Korrektheit aber nicht (`docs/research/PLAYGROUP_LIVE_PHASE3_PLAYER_CAPACITY_4P_6P_8P_20261108.md` §2). Upstream-Aussagen („bis 10 Spieler") sind keine Pin-Evidenz.

**Veralteter Widerspruch im Baum:** `docs/OPERATIONAL_SIMULATION_POLICY.md:10-12` nennt die Lane noch 2–5 — der Code-Stand ist 2–6; das Policy-Dokument ist an dieser Stelle nachzuziehen.

## 2. Regelfälle, die sich gegenüber 4 Plätzen ändern und eigene Tests brauchen

Die folgenden Punkte sind **Prüfpunkte** (aus den Regeln des Formats und den Lücken des Ist-Stands abgeleitet), keine Behauptungen über den Pin — ihre Korrektheit am Pin ist je `UNKNOWN`, bis Phase 3 des Prüfplans sie belegt:

1. **APNAP-Verkettung:** Gleichzeitig getriggerte Fähigkeiten von fünf/sechs Spielern in aktiver/nichtaktiver Reihenfolge; Stapel-Abarbeitung über mehr als zwei nichtaktive Spieler hinweg.
2. **Ausscheiden mitten in Stack/Kampf:** Ein Spieler verlässt die Partie, während seine Objekte auf dem Stapel, seine Kontrolleffekte und laufende Kampfzuweisungen bestehen — mit vier bzw. fünf verbleibenden Gegnern statt zwei/drei.
3. **Commander-Schaden je Paar:** Die 21-Schaden-Schwelle gilt je einzelnem Commander; geordnete Angreifer-Verteidiger-Paare wachsen von 12 (4 Plätze) auf 20 (5) bzw. 30 (6) — Verwechslungs- und Zählfehler zeigen sich erst hier.
4. **Einflussbereich `ALL` bei 5/6:** Zu prüfen ist nicht eine Reichweiten-Regel (die Bridge stellt `ALL` fest ein), sondern dass Sichtbarkeit und Zielmengen bei 5/6 exakt der 4-Platz-Semantik entsprechen und **kein** Frame verdeckte Information eines anderen Platzes enthält (Hidden-Info-Test je Platz, `AGENTS.md` §5).
5. **Mehrfach-Verteidiger-Kampf:** Angriffs-Deklarationen gegen mehrere Verteidiger/Planeswalker gleichzeitig und Blocker-Zuordnungen, wenn in aufeinanderfolgenden Prioritätsfenstern mehrere Besitzer angreifen.
6. **Concede-/Terminal-Pfade:** Mehrere Concedes, letzter verbleibender Spieler, Partieende bei 5/6 — inklusive der Frage, ob die Partie für die übrigen Plätze korrekt weiterläuft bzw. endet.
7. **Sitz- und Zugreihenfolge:** Sitze 5 und 6 existieren erstmals; Pod-Planung und Sitz-Rotation in Serien müssen sie abdecken (Sitzvorteil ist belegt, Abschnitt 4 von `PILOT_STRENGTH_OPTIONS.md` — ohne Rotation ist jede 5/6-Serie verzerrt).
8. **Replay-Asymmetrie:** 5 Plätze sind Tape-fähig, 6 nicht (Abschnitt 1) — Nachweise sind getrennt zu führen; ein 6P-Lauf darf keinen Replay-PASS „mitverdienen".

## 3. Laufzeit-Skalierung: Erwartung und Messaufbau

**Dokumentierte Werte (historisch, kein A/B, verschiedene Pods)** [Berichtsebene: `docs/research/PLAYGROUP_LIVE_PHASE3_PLAYER_CAPACITY_4P_6P_8P_20261108.md` §3 mit Primärquellen]:

| Stand | 4 Plätze | 6 Plätze |
|---|---|---|
| 2026-11-06, 1 Worker, Seed 1, verschiedene Pods | 1.892 Entscheidungen, 50,36 s | 4.511 Entscheidungen, 161,93 s (2,38× Entscheidungen, 3,22× Zeit) |
| 2026-11-05, Pin v14, Ø je Partie | 2.990 Entscheidungen | 4.025 Entscheidungen (1,35×) |

Dazu: Dokumentierte 6P-Ressourcen-Warnfälle (mehrere GiB Entscheidungs-Objekte → Ressourcen-Stopp, danach Disk-gestützte Berichte; ein 3.696-Fähigkeiten-Stapel in 6P) — die Extreme treiben Decks/Schleifen, nicht die Sitzzahl allein. Roadmap-Richtwert: Eine 4-Platz-Partie dauert etwa eine Minute auf vier Kernen; für S-6 ist **zuerst die Laufzeit zu messen** (`docs/STUDIO_ROADMAP_20261112.md` S-6).

**Erwartung** [MODELED]: Die Entscheidungszahl wächst mit der Platzzahl überproportional zur reinen Zugzahl (jede Runde hat mehr Prioritäts-Durchläufe und mehr Kampf-/Trigger-Anlässe), die Partiezeit folgt der Entscheidungszahl plus Piloten-Anteil. 5 Plätze liegen dazwischen, näher an 6 als an 4, was die Entscheidungen je Runde angeht. **Messwerte für 5 Plätze: nicht gefunden — UNKNOWN.** Ein kontrolliertes 4/5/6-Benchmark auf dem aktuellen Head existiert nicht (`NEW_HEAD_BENCHMARK = NOT_RUN`, Phase-3-Audit §9).

**Messaufbau (wenige Partien genügen, weil Laufzeit gemessen wird, nicht Siegquoten):** Dasselbe Pod wird um einen bzw. zwei Precon-Plätze erweitert (gleiche Decks, feste Seeds, eine JVM je Partie), gemessen werden Wandzeit, Entscheidungen, Piloten-Zeitanteil, RSS-Spitze und p99-Entscheidungslatenz; berichtet wird je Platzzahl mit Nennern, gegen die 4-Platz-Werte derselben Seeds. Das in Phase-3 §6 vorgeschlagene Protokoll (10 Seeds × 2 Pod-Typen, RSS/GC/Stack/p99) ist dafür die Vorlage — es ist Vorschlag, nicht gelaufen.

## 4. Prüfplan (Nachweise vor einer Freigabe — ohne die Freigabe vorwegzunehmen)

Jede Phase endet mit einem getrennten Ergebnis je Nachweis (`PASS`/`FAIL`/`UNKNOWN`); ein `UNKNOWN` wird nicht durch ein benachbartes `PASS` geheilt. Die Freigabe selbst ist Owner-Entscheid A8.

| Phase | Inhalt | Abnahme (Plan) |
|---|---|---|
| **0 — Festlegungen** | (a) Einflussbereich `ALL` und Angriffsoption `MULTIPLE` für 5/6 als Produkt-Einstellungen bestätigen oder ändern (Owner). (b) Tape-Lücke 6P entscheiden: Tape-Erweiterung als eigene, reviewte Änderung mit Tests — oder 6P-Freigabe ausdrücklich **ohne** Replay-Anspruch. (c) `docs/OPERATIONAL_SIMULATION_POLICY.md` auf 2–6 nachziehen. | Drei dokumentierte Festlegungen; ohne (a)/(b) keine Phase 5. |
| **1 — Schema/Policy (Bestand)** | Vorhandene Unit-Tests (Abschnitt 1) auf dem aktuellen Head grün: variable Platzzahl 2–6, Cap-Guard, Sitz-Mapping. | Testlauf auf Head `53f4836b`-Nachfolger dokumentiert; keine neuen Ansprüche aus Schema-Tests ableiten (sie belegen Zulässigkeit, keine Partie). |
| **2 — Live-Smoke** | Je **eine** vollständige Partie mit 5 und mit 6 Plätzen (festes Precon-Pod, fester Seed, aktueller Pin). | Beide Partien enden `game_over`; keine `ENGINE_FAILURE`; jede gestellte Frage gehört zu den 17 unterstützten Klassen und wurde beantwortet; Sitz-/Zugreihenfolge im Log lückenlos. |
| **3 — Regelfall-Tests** | Die acht Prüfpunkte aus Abschnitt 2 als gezielte Szenarien (Lab-/Bridge-Tests). Wo ein Test eine echte Lücke trifft, muss er auf dem Stand **vor** dem Fix fehlschlagen (Changed-Line-Prinzip); was nicht testbar ist, bleibt `UNKNOWN` und wird so berichtet. Inklusive Hidden-Info-Test je Platz (kein Frame enthält verdeckte Information eines anderen Platzes). | Je Prüfpunkt ein benannter Test mit Ergebnis; Liste der nicht abgedeckten Punkte als `UNKNOWN` im Bericht. |
| **4 — Laufzeit-Messung** | Messaufbau aus Abschnitt 3 auf dem aktuellen Head. | Messbericht mit Nennern liegt vor (Wandzeit, Entscheidungen, RSS, p99 je Platzzahl). Ein Laufzeit-Budget je Partie für 5/6 ist **Owner-Festlegung** — hier wird keine Zahl erfunden. |
| **5 — Serien-Tauglichkeit** | Kleine gepaarte Serie an 5 und an 6 Plätzen mit Sitzrotation (Partienzahlen nach dem Plan aus #1211). Twin-Replay: für 5 Plätze Tape-MATCH als Nachweis; für 6 Plätze nur, falls Phase 0(b) die Tape-Erweiterung gebracht hat — sonst steht der Replay-Status ausdrücklich auf `UNKNOWN`. | Serie ohne fehlgeschlagene Partien (Fehlschläge werden separat berichtet, nicht als Niederlagen gezählt, Owner S3); Replay-Ergebnis getrennt nach 5/6 ausgewiesen. |
| **6 — Bericht und Owner-Vorlage** | Qualifikationsergebnis je Nachweis (Phasen 1–5) in einem Bericht; offene `UNKNOWN`s unverdeckt. | Bericht liegt vor; die Freigabe-Entscheidung trifft der Owner (A8). Dieses Dokument trifft sie nicht. |

**Offen / UNKNOWN am Ende dieses Dokuments:** Regelkorrektheit des Pins bei 5/6 (nur im Fork bzw. über Phase 2/3 belegbar); Laufzeit für 5 Plätze; ob `ALL` und `MULTIPLE` die endgültigen Einstellungen für Einflussbereich und Angriffsoption sind; ob das Tape auf 6 Plätze erweitert wird. Keiner dieser Punkte ist durch Schema-Tests oder den historischen 6P-Live-Lauf von 2026-09-21 beantwortet.

---
