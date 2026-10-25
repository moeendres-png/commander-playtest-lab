# Max-Review Pass 2 — Hauptbericht

- **Stand:** 2026-10-25. **Neues Verzeichnis, neue Dateien:** Diese Lieferung
  liegt unter `handover/2026-10-25/max-review-pass2/` (Staging:
  `~/workspace/tmp/pass2-report-staging/`). Der Pass-1-Bericht
  (`handover/2026-10-24/max-review/`, Commit `11d1fefa`) bleibt byte-identisch
  und wird hier nur als Struktur-Vorbild gelesen, nie ergänzt oder verändert.
- **Lock:** Lab-Main `217c34d95` (#1007), Pin v13
  `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e` (unverändert, versiegelt).
- **JAR:** `bridge_pass2.jar`, 79.535.050 Bytes, sha256
  `6ba47e027154b56388dd173a3f67752aa4e2b7058451a6ae0a9690785f9c2940`,
  gebaut 2026-10-25 10:15 aus Lab `217c34d95` + Fork v13. Bridge-Diffs leer
  (`54da28d63..ee47312a7`, `c0e5f7f1..053708e56`, `ee47312a7..217c34d95`,
  Haupt-Clone, alle Commits verifiziert) → JAR für alle vier Ketten gültig.
- **Methode:** Alle Ketten: Real-Pod, gleiche Seeds, gleiches JAR, gleicher
  Treiber (`phase4b_play.py`), Vergleich über semantischen Hash
  (Prompt + gewählte Labels + Outcomes je Frame; angebotene Optionen, Pilot-State
  und Friedhofs-Reihenfolge NICHT enthalten) und Sieger. Jede Zahl trägt ihre
  Evidenzklasse (s. §9); UNKNOWN ist niemals PASS.
- **Grundlagen:** Arbeitsnotizen `~/workspace/tmp/max-review/pass2-notes.md`
  (gelesen, vollständig); Ketten-Verzeichnisse `~/workspace/tmp/max-review/`
  (`pass2-a/`, `pass2-b/`, `pass2-c-base/`, `pass2-c-head/`, `pass2-d-base/`,
  `pass2-d-head/`, `abort24/`); Detailtabellen in `01_KETTEN.md`,
  Lese-Befunde in `02_LESEBEFUNDE.md`, R-Paket in `r-paket/`.
  Dieser Entwurf trifft keine Aussortier-, Merge- oder Folge-Entscheidungen.

## Ergebnis zuerst

- **Alle vier Ketten: 24/24 Spiele ok.** Kein Abbruch, kein BRIDGE_ERROR im
  Endstand (ein BRIDGE_TIMEOUT in Kette B, Seed 19, per Retry behoben).
- **#1007 (Phase 5, Zahlungs-Plan) EXAKT reproduziert:** 48/48 ok, 23/48
  bit-identisch (Kette A 12/24 + Kette D 11/24), 25 divergieren; rohe
  Mana-Payment-Cancels 136 → 82 exakt; Sieger gleich 31/48.
- **#1006 (Phase 3, Kampf) auf Spielebene verifiziert:** 24/24 ok, Sieger
  gleich 24/24 — stützt #1006s „0 Siegerwechsel". Die Block-Runden-Metrik
  (19→15) ist aus den Transkripten NICHT reproduzierbar (s. §3); der zählbare
  Proxy ist exakt: Blocker-Entscheidungen mit Block 139 → 154.
- **#1004 (Target-Seiten) gemessen, Abgleich offen:** 24/24 ok, nur 1/24
  bit-identisch, Sieger gleich 13/24. #1004s eigene Real-Game-Aussage dazu
  ist nicht geprüft — der PR-Sign-off war Replay-basiert (B-20).
- **Lese-Lücken aus Pass 1 geschlossen:** `XmageLosslessHiddenPlan.java`
  vollständig gelesen (668 Zeilen, nicht 669 — Datei per `wc -l` verifiziert);
  209 Bridge-Testdateien (62.530 Zeilen) klassifiziert; Fork-#64/#62
  rekonstruiert; „keine zweite Engine"-Grep repo-weit geschlossen MIT
  benanntem Grenzbefund (`engine/structural/simulator.py`, kein Verdikt);
  Upstream nach 2026-10-20: 72 Commits, Fork hat nichts gemergt, Pin unberührt.
- **JAR-/Test-Offenlegung:** Bridge-Build 1150/1154 Tests grün, 4 Fehler nur
  in `XmageFullGameReplayExportTest` (INIT_FAILED), Negativkontrolle am alten
  Stand identisch → kein Regressions-Befund. Der Pass-1-Build nutzte
  `-Dmaven.test.skip=true` (Tests geskippt, nicht grün); der Pass-2-Build ist
  schärfer (s. §6).

## §1 Lock und Artefakte

- Lab-Main `217c34d95` (#1007 gemergt), Pin v13 unverändert. Worktree
  `wt-maxreview2` @ `217c34d95`, `.runtime` (388 MB) kopiert, Toolchain
  verifiziert (JDK 17.0.20.1, Maven 3.9.9, `mvn-proxy.sh`).
  DIRECTLY_VERIFIED (Notizen + JAR-Hash).
- `~/.m2` war nach einem Runtime-Restart leer (nur settings.xml) → gezielter
  Fork-Install neu gelaufen (`-pl Mage.Server.Plugins/Mage.Deck.Constructed,
  Mage.Game.CommanderFreeForAll,Mage.Game.CommanderDuel -am`, BUILD SUCCESS,
  1:52 min). Das ist die bekannte Lektion 12 (AGENTS.md): nach jedem Restart
  zuerst Fork-Install, dann Bridge-Build.
- Smoke-Test BESTANDEN (DIRECTLY_VERIFIED): Seed 1, Pod real, neues JAR →
  status ok, semantischer Hash bit-identisch zum abort24-Korpus
  (`ee47312a7`), gleicher Sieger [1]. Die Eignung des JARs für die Ketten
  beweist dieser Smoke-Test (echtes Spiel über das JAR), nicht die 4
  Replay-Export-Tests (s. §6).

## §2 #1007 — Tabellenzeile (Phase 5, Zahlungs-Plan)

PR-Body (API, gelesen): 136/2.948 → 82/3.122 gecancelte Zahlungen, 56 → 4
vermeidbar; Ursache (2) = Bridge-Flag `pool_covers_mana_cost` zählt Hybrid-Pip
als beide Farben → eigentlicher Fix gehört in Bridge + #979-Batch.
Eigener Check: `tests/unit/test_pilot_payment_plan.py` an `217c34d95`:
**48 passed** (entspricht PR-Angabe 48 Unit-Tests). DIRECTLY_VERIFIED.

| Maß | #1007-Angabe | Pass-2-Messung | Urteil |
|---|---|---|---|
| Spiele ok | 48/48 | 48/48 (A 24/24 + D 24/24) | bestätigt |
| Hash bit-identisch | 23 | 23 (A 12/24 + D 11/24) | **exakt** |
| Hash divergiert | 25 | 25 (A 12 + D 13) | **exakt** |
| Rohe Mana-Payment-Cancels | 136 → 82 | 136 (Baseline-Recount) → 82 (Head) | **exakt** |
| Sieger gleich | (keine Angabe) | 31/48 (A 15/24 + D 16/24) | gemessen, kein Abgleich |
| Entscheidungen (Frames) | — | 171.976 → 173.700 (+1,0 %) | gemessen |

- Head-Cancels: 79/82 mit genau 1 angebotener Option (erzwungen).
  DIRECTLY_VERIFIED (Notizen).
- Top-Cast weiter Bitter Downfall (29 vs 32). DIRECTLY_VERIFIED (Notizen).
- Sieger-Wechsel-Seeds: A: 2, 3, 8, 10, 12, 13, 16, 18, 20; D: 26, 29, 31, 36,
  41, 44, 46, 47. Vollständige Tabellen in `01_KETTEN.md`.
- #1007s Gewinnraten-Aussage bleibt UNDECIDED (keine neue Power-Analyse in
  Pass 2; 48 Paare sehen nur ≥ ~5 Punkte — M4-Lektion, MODELED).

## §3 #1006 — B-20-Korrektur (Phase 3, Kampf)

Pass-1-Vermerk B-20 lautete: #1006 nur teilweise verifiziert (Tests grün,
Sign-off-Zahlen aus Repo nicht reproduzierbar). Korrektur durch Pass 2:

**Verifiziert (DIRECTLY_VERIFIED, Kette B, 24 Paare, Base `54da28d63` vs Head
`ee47312a7`):**
- 24/24 ok nach Retry (Seed 19 erst BRIDGE_TIMEOUT, Retry ok + Hash
  bit-identisch zur Baseline, Sieger [2] = Baseline).
- Hash bit-identisch 10/24, divergiert 14/24.
- **Sieger gleich 24/24** — stützt #1006s „0 Siegerwechsel" auf Spielebene.
  Das ist die Spiele-Aussage; die Replay-Aussage (29/362 Block-Antworten
  geändert) bleibt Replay, nicht Real-Game.

**NICHT reproduzierbar (UNKNOWN, B-20-Ausweitung auf #1006s Real-Game-Metrik):**
- Die Metrik „Runden mit tödlichem Rest gleiche Positionen 19→15 (vermeidbar
  6→2)" ist aus den Transkript-Dateien NICHT ableitbar. Die Dateien enthalten
  ausschließlich Entscheidungen (Frames `decision_requested` /
  `decision_accepted` mit Prompt, legalen und gewählten Labels) — keine Leben,
  keine Power/Toughness, keine Schadens-Events, keine Spiel-Events. Die Metrik
  braucht zustandsbehaftetes Replay wie #1006s Harness, der nicht im Repo
  liegt. Wer sie prüfen will, braucht den Harness oder ein neues
  Replay-Protokoll — aus den vorliegenden Artefakten ist sie UNKNOWN, nicht
  widerlegt und nicht bestätigt.
- Gleiches gilt für die 86→97-Zweitnummer („Blocks 139/86 → 154/97") und die
  Chump-Zahlen (28(24) → 43(37)): ohne P/T nicht ableitbar.

**Zählbarer Proxy, exakt bestätigt (DIRECTLY_VERIFIED):**
- Blocker-Entscheidungen (`declare_blocker`, accepted-Frames) mit mindestens
  einem gewählten Block: **139 (Base, 362 Entscheidungen) → 154 (Head, 373
  Entscheidungen)** = #1006s „Blocks 139 → 154" auf echten Spielen.
  Hinweis: Die erste Zählung über `decision_requested`-Frames ergab 0/362,
  weil die Auswahl nur in den `decision_accepted`-Frames steht — korrigiert
  und verifiziert.

## §4 #1004 — Vergleich (Target-Seiten)

**Gemessen (DIRECTLY_VERIFIED, Kette C, 24 Paare, Base `c0e5f7f1` vs Head
`053708e56`):**
- 24/24 ok (Base fertig 13:14, Head fertig 13:55, je nach Restart-Resume).
- Hash bit-identisch nur 1/24 (Seed 17), divergiert 23/24.
- Sieger gleich 13/24; Wechsel-Seeds: 4, 5, 7, 8, 9, 10, 12, 15, 16, 22, 24.

**Offen (UNKNOWN, kein Verdikt):**
- #1004s eigene Real-Game-Aussage zu Bit-Identität/Sieger wurde in Pass 2
  nicht gegen den PR-Body geprüft. Der PR-Sign-off war Replay-basiert
  (B-20-Muster: Replay-Daten/Skripte nicht im PR-Diff). Ob 1/24 Bit-Identität
  für eine Target-Seiten-Änderung erwartet, plausibel oder auffällig ist,
  sagt dieser Bericht NICHT — dafür fehlt der Abgleich mit #1004s
  Eigenaussage und eine Mechanismus-Analyse der divergierenden Seeds.
  Die 17-Metriken-Vergleiche (Holm) wurden für die Pass-2-Ketten nicht neu
  gerechnet; berichtet werden nur Hash und Sieger.

## §5 Lese-Befunde (Kurzform; Details in 02_LESEBEFUNDE.md)

- **`XmageLosslessHiddenPlan.java` vollständig gelesen, 668 Zeilen**
  (CODE_DERIVED; Datei per `wc -l` verifiziert — der Auftragstext nannte 669,
  die Datei hat 668 Zeilen). Pfad
  `engine-bridge/src/main/java/org/commanderlab/xmage/` (nicht org/mage/bridge).
  SLOT-04 fail-closed Parser: vollständige Bibliothek top-to-bottom + expliziter
  nativer FaceDownType + vollständige Hand; keine Inferenz; jede Abweichung
  benannter Fehlercode (PARTIAL_LIBRARY_REQUEST, LIBRARY_POSITION_MISMATCH,
  FACE_DOWN_TYPE_ON_FACE_UP_OBJECT, …). Ein Face-down-Objekt pro Request.
  Anwendung nur über native RG-06A-APIs; Verifikation nennt Spieler/semantisches
  Objekt/Position, nie Kartenidentität (kein Leak in Arrival-Response).
  Schließt O-04-Teil „668 Zeilen ungelesen" aus Pass 1. Kein eigenes
  `XmageLosslessHiddenPlanTest`; Abdeckung läuft über
  `XmageNativeStateRestorationTest` (1.066 Z.) u. a. Restoration-Tests.
- **Bridge-Testdateien klassifiziert:** Bestand exakt wie Pass-1-Inventar:
  **209 Dateien, 62.530 Zeilen**, alle in
  `engine-bridge/src/test/java/org/commanderlab/xmage/`. Themen: Multiplayer*
  (~60, Engine-direkte Multiplayer-Qualifikation), FullGame* (Decision-Klassen,
  Replacement, Inventory, Shutdown), Midgame* (Kausal-/Midgame-Rows),
  Restoration* (Checkpoint/Commander-Damage/Native), Corpus/Capability
  (ActualCardCorpus 2.477 Z., Pb03Tier1Rows 1.940 Z.). Vollständig gelesen
  (klein, entscheidungsrelevant): `PoolCoversManaCostDirectionTest.java`
  (44 Z., sichert `cost.enough(pool)` gegen invertierten Aufruf — stützt
  #1007-Ursache-(2)-Richtung; Hybrid-Doppelzählung hier nicht abgedeckt),
  `XmageBlockCapacityTest.java` (33 Z., CR 509.1a, maxBlocks=0 = beliebig viele),
  `XmagePb03CapabilityManifestTest.java` (41 Z., Manifest ohne Global-Promotion;
  supported: qualified turn-1, commander damage matrices; unsupported: stack
  spells, controller/owner divergence; `starting_state_injection_supported=false`).
- **Fork-#64/#62 rekonstruiert (GitHub-API, 2026-10-25, DIRECTLY_VERIFIED):**
  Fork-PR #64 „XMage upstream update: merge magefree/mage master (fab0f23b)
  into the candidate line", closed, merged 2026-10-20T10:47:35Z, Head 043579bb
  → Upstream-Baseline des Forks ist `fab0f23b` (2026-10-20), wie in Pass 1
  vermutet. Fork-PR #62 „Add /oc-zai lane: Z.ai GLM-4.7-Flash", closed,
  merged 2026-10-20T09:47:16Z. ZAI-Thema von Hans am 2026-10-24 als geklärt
  bestätigt → keine weitere Verfolgung.
- **Repo-weite „keine zweite Engine"-Grep — Abdeckung geschlossen, mit
  Grenzbefund (CODE_DERIVED, kein Verdikt):** Grep
  `def .*legal|is_legal|legal_options=|legal_actions=` → Definitionen nur in
  `engine/rules/*` (sanktionierte Provider-Schicht) oder in Qualification-/
  Replay-Code, der Engine-angebotene Optionen konsumiert (Parametername `legal`
  ≠ Rekonstruktion). `random.choice/randint` außerhalb Tests: kein Treffer in
  Produktions-Pilotnähe. **Grenzbefund, Adjudizierung an Coordinator/Owner
  (§8 AGENTS.md), keine Mess-Aussage:** `engine/structural/simulator.py` —
  `StructuralSimulator`, „fast role-based Commander simulator", eigene
  Turn-/Lebens-/Schadens-Schleife, eigenes `random.Random(config.seed)`,
  Ergebnisse gelabelt `structural_model_estimates`, Docstring: „deliberately
  models deck structure rather than comprehensive Magic rules". Importeure
  (produktionsnah): `agents/ensemble.py`, `agents/validation.py`, `cli/app.py`,
  `evals/runner.py`, `mulligan/lab.py`, `optimization/experiments.py`.
  Korrekte Aussage: keine zweite *Rules*-Engine mit Legalitäts-Anspruch;
  daneben existiert ein deklarierter, als Schätzung gelabelter
  Struktur-Simulator, dessen Produktions-Erreichbarkeit zu benennen ist. Ob
  seine Nutzung in einem Pfad XMage-Autorität substituiert, ist eine
  Coordinator-/Owner-Adjudizierung. Nebenbefund:
  `optimization/search.py: all_legal_single_swaps` — „legal" = Deckbau-Legalität
  (Farbidentität etc.), keine Spielregeln; keine Verwechslungsgefahr, wenn
  benannt. Pass-1-Aussage „keine zweite Engine" war auf engine/rules +
  pilots.py gestützt und damit zu eng formuliert.
- **Upstream nach 2026-10-20 — geschlossen (GitHub-API, DIRECTLY_VERIFIED):**
  Fork `origin/master` nach Pin v13: nur Workflow-Commits (PR #62 ZAI-Lane,
  PR #55 C12-Egress-Fix). KEINE Engine-/Karten-Commits nach dem Pin.
  `upstream/master` (magefree): git-Fetch zweimal an Netzfehlern gescheitert
  (early EOF nach 63 Min.; TLS-Disconnect im Retry) — stattdessen API +
  ls-remote: Tip live `518aef19` (2026-10-25, „Animations rework"), lokaler
  Ref `bb0ed0f72` datiert 2026-10-18 (vor dem Fenster). **72 Commits seit
  2026-10-20** (vollständige erste Seite, <100): überwiegend neue
  Karten-Implementierungen (Star-Trek-Set u. a.) + App/GUI-Fixes; Baseline
  `fab0f23b` (2026-10-20) im Fenster bestätigt. Folgerung: Upstream ist
  weitergezogen, der Fork hat nichts davon gemergt — Pin v13 unberührt, kein
  Fork-Handlungsbedarf aus dieser Prüfung (ein künftiger Upstream-Merge wäre
  eine neue Owner-Entscheidung).

## §6 JAR-/Test-Offenlegung (Bridge-Build)

- Voll-Lauf an `217c34d95`: **1150/1154 Tests grün, 1 skipped, 4 Fehler —
  alle in `XmageFullGameReplayExportTest`, alle
  `XMAGE_CARD_REPOSITORY_INIT_FAILED`** (fresh-JVM-Replays; die frische JVM
  läuft mit user.dir = Surefire-WorkingDirectory `target/`, ohne das
  Karten-Repo des Worktree-Roots).
- **Negativkontrolle (DIRECTLY_VERIFIED):** dieselbe Klasse am ALTEN Stand
  `ee47312a7` (wt-maxreview) → **identischer Fehler, 4× INIT_FAILED**. Kein
  Regressions-Befund für 217c34d95, kein #1007-Bezug. Der alte „Exit 0"-Build
  hat keine Surefire-Reports zu dieser Klasse (Tests damals geskippt oder
  Reports bereinigt) — er beweist für diese 4 Tests nichts. Hypothese (nicht
  verifiziert, kein Befund): H2-DB-Kollision — die In-Prozess-Test-JVM hält die
  DB unter `target/db`, die frische JVM kollidiert darauf. Test-Infra-Thema,
  nicht Produkt-Defekt; gehört in Claudes Lane, nicht in Pass 2.
- Konsequenz: JAR mit `-Dtest='!XmageFullGameReplayExportTest'` gebaut (alle
  übrigen 1150 Tests als Gate). Exklusions-Build: **1148 Tests, 0 Failures,
  0 Errors, 1 Skipped** (stale ReplayExport-Report aus dem Voll-Lauf
  herausgerechnet; Klasse im Exklusions-Lauf nicht gelaufen).
- **Korrektur zum Pass-1-Build:** `build_jar.sh` (Pass 1) nutzte
  `-Dmaven.test.skip=true` für Fork-Install UND Bridge-Package — das alte
  „Exit 0" bedeutet Tests geskippt, nicht Tests grün. Der Pass-2-Build
  (1150 Tests als Gate) ist damit schärfer als der Pass-1-Build.

## §7 Restart-Muster (Betriebsbefund, kein Produkt-Befund)

Runtime-Restarts killen auch detached Ketten, ohne Benachrichtigung — in
Pass 2 dreimal beobachtet: Kette B bei Seed 18/24, C-Base bei Seed 13/24,
D-Base bei Seed 38/48 (still ~14:08, entdeckt auf Nachfrage 15:31).
Resume-Skripte funktionieren: Neustart überspringt fertige Seeds, kein
Verlust, keine Duplikate (B, C-Base, D-Base je per Resume fertig).
Betriebsregel für lange Ketten: pro Spiel sofort schreiben, Resume-fähig
bauen, Fortschritt nach jedem Seed prüfen — kein blindes Vertrauen auf
„läuft noch".

## §8 Offene Punkte und Grenzen dieses Berichts

1. #1004-Real-Game-Abgleich: #1004s eigene Aussage zu Bit-Identität/Sieger
   nicht geprüft; 17-Metriken-Vergleiche für Pass-2-Ketten nicht gerechnet.
   (UNKNOWN — kein Verdikt zu 1/24 Bit-Identität.)
2. #1006-Block-Runden-Metrik 19→15 (vermeidbar 6→2) und Chump-Zahlen aus
   Transkripten nicht ableitbar; Harness nicht im Repo. (UNKNOWN.)
3. Gewinnraten-Aussagen aus 48 Paaren: UNDECIDED (Power-Lektion aus M4).
4. Semantischer Hash sieht Angebots-Unterschiede nicht (nur gewählte Labels)
   — Divergenzraten sind Untergrenzen der Verhaltensänderung; „bit-identisch"
   heißt nicht „identisches Spiel in jeder Hinsicht".
5. Mess-Lücke: „bessere Entscheidungen" ohne Ground Truth schwer zu messen
   (Win-Rate schwach gepowert, Fixtures bräuchten handgeprüfte Optima).
6. R-Paket (`r-paket/`, 7 Dateien, byte-identisch zur Quelle
   `~/workspace/tmp/max-review/pass2-r/`): REPORT, R09_OOM_FIX,
   PR_BODY_R09, R11_STATISTIK, R12_M4_PROTOKOLL, R13_KARTENABDECKUNG,
   R14_POD_REALISMUS — R-09 verifiziert, R-11–R-14 Analysen, Details dort.
7. Keine Aussage zu #1014, #992-Akzeptanz, Meta-Lane oder Folge-PRs — andere
   Lanes, andere Entscheidungen.

## §9 Evidenzklassen

- **DIRECTLY_VERIFIED:** gemessen/gelesen in dieser Prüfung (Ketten-Dateien,
  API-Antworten, Testläufe, `wc -l`).
- **CODE_DERIVED:** aus gelesenen Dateien abgeleitet, nicht zur Laufzeit geübt.
- **MODELED:** Rechnung/Modell (z. B. Power-Aussagen), keine Messung.
- **UNKNOWN:** nicht prüfbar aus den vorliegenden Artefakten — niemals PASS.
- **PARTIAL ≠ FULL, NOT_RUN ≠ PASS, CODE_DERIVED ≠ RUNTIME_VERIFIED.**

## Quellen

- Arbeitsnotizen: `~/workspace/tmp/max-review/pass2-notes.md`.
- Ketten: `~/workspace/tmp/max-review/pass2-a/`, `pass2-b/`,
  `pass2-c-base/`, `pass2-c-head/`, `pass2-d-base/`, `pass2-d-head/`,
  `abort24/` (je 24 `real_seed*.json`, Status/Hash/Sieger pro Seed).
- Treiber: `~/workspace/tmp/phase4b/phase4b_play.py`; JAR:
  `~/workspace/tmp/max-review/bridge_pass2.jar`.
- Commits: Lab `217c34d95` (#1007), `ee47312a7` (#1006-Head),
  `54da28d63` (#1006-Base), `c0e5f7f1` (#1004-Base), `053708e56` (#1004-Head);
  Fork-Pin v13 `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e`; Fork-#64
  (Head `043579bb`, merged 2026-10-20T10:47:35Z), Fork-#62 (merged
  2026-10-20T09:47:16Z); Upstream-Baseline `fab0f23b`, Upstream-Tip
  `518aef19` (2026-10-25).
- Pass-1-Bericht (nur gelesen): `handover/2026-10-24/max-review/` auf
  `muse/claude-handover`, Commit `11d1fefa`.
