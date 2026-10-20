# Audit-Synthese — Alle Audit-Befunde von Muse (2026-10-19/20)

**Autor:** Muse (Mess- und Verifikations-Lane) · **Datum:** 2026-10-20
**Zweck:** Konsolidierte Fassung aller meiner Audits für die Claude-Threads. Ersetzt keine
Einzelberichte (Quellen in §6), bündelt aber Befunde, Evidenzklassen und — in §3 —
alle Korrekturen an meinen eigenen früheren Aussagen. **§3 ist verbindlich mitzuführen,
wer ältere Analysen zitiert.**
**Source Lock:** CPL `origin/main` = `f994bd1aa` · mage `master` = `10a73922` ·
Pin = `348b37db` (`config/rules_engines.json`) · Fork-Head (geprüft) = `10931648`
**Abkürzungen:** EK = Evidenzklasse · St = Status

---

## 1. Management Summary

1. Die Qualifikation steht auf dem Pin `348b37db`. Der Fork-Head `10931648` ist **nicht**
   qualifiziert: 29/35 Semantic-Hash-Abweichungen + reproduzierbarer Seed-10-Crash.
2. **Bisektion (V0–V4): Die drei Performance-Hunks sind entlastet.** Ursache der Drift
   sind 6 existierende Turbulent-Dual-Lands, deren echte Implementierungen im Fork durch
   fähigkeitslose „Simplified"-Versionen ersetzt wurden; eine (Turbulent Steppe) liegt
   im Smoke-Pod und gibt kein Mana.
3. Die **Seed-10-Crash-Ursache ist weiter UNKNOWN** — der V5-Diskriminator (nur die
   6 Karten zurück) entscheidet die Zuordnung.
4. **Precon-Lage ist ungemessen:** Sowohl „221 fehlende Karten" als auch „192/195
   importierbar" sind UNKNOWN. Nachmessung über den produktiven Import-Pfad läuft bei Muse.
5. Der Laufzeit-Kern ist verifiziert: Twin-Determinismus, RNG-Seeding und
   Hidden-Info-Scoping bestehen (WS2) — die Probleme liegen in Karten-Daten und
   Fork-Deltas, nicht in der Spielschleife.
6. Das Upstream-Delta (108 Commits, 5 garantierte Konflikte) ist ein eigenes Projekt.
   Verbindliche Reihenfolge: Karten-Fix → Upstream-Update → Requal PB-03 → Repin (Owner-Go).
7. Prozess: Claude ist alleiniger Writer seiner Workstreams und führt Fixes autonom
   aus (Hans, 2026-10-20). Workflow-Dateien kann nur Hans per Web-UI ändern
   (GitHub-App ohne `workflows`-Permission) — die /oc-zai-Workflows waren deshalb
   bis heute wirkungslos.

---

## 2. Befunde je Audit

### 2.1 Phase-A-Projekt-Audit (2026-10-19)

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| A1 | Source Locks beider Repos verifiziert (CPL main `f994bd1aa`, Pin `348b37db`, mage master `10a73922`); Pin-Autorität ist `config/rules_engines.json` | DIRECTLY_VERIFIED | erledigt | Alle Messungen referenzieren diesen Lock |
| A2 | Keine Ownership-Kollisionen: alle offenen PRs (#914–#918) stammten von Muse, Merges durch Hans | DIRECTLY_VERIFIED | erledigt (überholt) | Seit 2026-10-20 Thread-Aufteilung + Claude als alleiniger Writer (§1.7) |
| A3 | Actual-Card-Coverage: Level 1–2 belegt (6432 Karten existieren in der DB, 195/195 Precons importieren), **Level 3–7 UNKNOWN** (Konstruierbarkeit, Castbarkeit, Resolution, Interaktionen, Oracle-Abgleich ungetestet) | UNKNOWN | offen | Nenner sind die 195 Precon-Decks, nicht „alle Karten" |
| A4 | Hidden-Info, RNG und Replay: PASS nach WS2 (6/6 Spiele ohne ConformanceError; Twin 3/3) | DIRECTLY_VERIFIED | erledigt | Details §2.4 |
| A5 | Blocker-Rangfolge der Phase A: (1) Precon ENGINE_FAILURE, (2) ausstehender 36-Seed-Vergleich, (3) PR-Reviews | DIRECTLY_VERIFIED | teilweise überholt | (2) ist gelaufen und wurde zur Bisektion (§2.6); (1) steht als #920 (§2.8) |

### 2.2 Phase-4-Modul-Inventur (Fork-Hot-Paths, 2026-10-19)

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| P4-1 | Hot-Paths inventarisiert: `GameImpl` 4542 Zeilen, `GameState` 1762 Zeilen; `getPlayable()` ≈ 47 % der Spiel-CPU, davon ≈ 35 % Game-State-Kopien | MODELED (Fremdmessung aus #877 übernommen, nicht selbst gemessen) | erledigt (Inventur) | Optimierungsziele waren korrekt gewählt — die Semantik-Nebenwirkungen nicht |
| P4-2 | Alle 5 Fork-Optimierungen (P1, P2, Nested-Copy, `singleton`, Trigger-Pre-Check) waren als „implementiert, 36-Seed-Nachweis ausstehend" inventarisiert | DIRECTLY_VERIFIED | überholt | Der ausstehende Nachweis schlug fehl → Bisektion (§2.6) |
| P4-3 | P3 (`getActivePermanents`-Cache) und P4 (`AsThoughEffects`-Cache) bewusst **nicht** implementiert (Invalidierungs- bzw. Semantikrisiko) | — (Entscheidung) | erledigt | Nur mit ausgiebigen Tests wieder aufgreifen |
| P4-4 | Evidenz-Regel je Optimierung: Baseline-Messung + 36-Seed-Hash-Gleichheit als Gleichwertigkeitsnachweis | — (Standard) | erledigt | Genau dieser Nachweis trennte später Drift von Rauschen |

### 2.3 WS1 — Performance-Hypothesen (gemessen 2026-10-19)

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| W1-1 | **H1 widerlegt** (Annahme zum Qualifikations-/Testlaufzeit-Anteil trifft nicht zu; Anteil < 50 %) | DIRECTLY_VERIFIED (Messung) | erledigt | K9 (CI-Gate-Trennung) verworfen (§2.5) |
| W1-2 | **H2 widerlegt:** Transport-/Bridge-Overhead nur 0,8 % (< 5 %-Schwelle) — die Bridge ist nicht der Flaschenhals | DIRECTLY_VERIFIED (Messung) | erledigt | Keine Transport-Optimierung nötig |
| W1-3 | **H3 gemessen:** 68 s pro Kartentest, davon 33 s JVM-Start; ein K5-Korpus von 20–50 Karten kostet 23–57 Min | DIRECTLY_VERIFIED (Messung) | erledigt | Karten-Tests müssen JVM-Starts amortisieren (Harness-Design, K5) |

### 2.4 WS2 — Laufzeit-Verifikation (2026-10-19)

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| W2-1 | **Twin-Determinismus PASS:** 3/3 Seeds mit identischen SemanticReplayTape-Fingerprints bei gleichen Seeds | DIRECTLY_VERIFIED | erledigt | Determinismus ist verlässliche Messbasis (Bisektion baute darauf) |
| W2-2 | **RNG-Seeding PASS:** `setRulesSeed`/`requireExplicitSeed` greifen; verschiedene Seeds → verschiedene Spiele | DIRECTLY_VERIFIED | erledigt | Kein versteckter RNG |
| W2-3 | **Hidden-Info-Audit PASS:** 6/6 Spiele ohne `FullGameConformanceError`; Observations principal-scoped | DIRECTLY_VERIFIED | erledigt | D17-/Scoping-Architektur hält im Lauf |
| W2-4 | Precon-Decks scheitern in echten Spielen mit ENGINE_FAILURE (an der Baseline-JAR beobachtet) | DIRECTLY_VERIFIED (Beobachtung) | offen | Ursache UNKNOWN → §2.8, Issue #920 |

### 2.5 Architektur-Transfer (XMage → CPL, K1–K9)

Ausgangslage: Die wertvollsten XMage-Ideen waren bereits übertragen; der Fork liegt bei
RNG (GameRandom), Hidden-Info-Scoping (ActorSafeIdentity) und Replay-Tape **vor** Upstream.
Größte festgestellte Lücke: keine actual-card-driven Tests durch den Produktionspfad (→ K5).

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| K1 | Bridge-Classpath-Ratchet: keine AI-Player-Klassen in der Engine-JVM (D17); `BridgeClasspathTest` + zwei Negativkontrollen (Poison-Jar, verbotene ArtifactId) | DIRECTLY_VERIFIED | **gemergt** (PR #913, main `f994bd1aa`) | erledigt |
| K2 | Twin-/Replay-Verhalten: kein Transfer nötig — WS2-Twin-Läufe belegen Gleichstand | DIRECTLY_VERIFIED | geschlossen (keine Änderung) | — |
| K3 | PrincipalView-Contract + Leak-Test (PUBLIC/PRIVATE-Feldvertrag, `assertNoLeak()`) | DIRECTLY_VERIFIED (Tests) | PR #915 offen — Änderungen angefordert (Tests müssen echte Bridge-Ausgabe prüfen) | Nacharbeit Muse (O6) |
| K4 | Mana-Konformanz: Engine liefert strukturierte Kostendaten; kein Regex-Parsing vorhanden noch nötig; Konformanz-Test | DIRECTLY_VERIFIED | PR #916 offen, von Thread 2 mergefähig befunden | Merge durch Hans (O7) |
| K5 | Scenario-Harness: scripted Szenarien + Strict-Modus durch die Full-Game-Bridge (Framework; Korpus-Ausbau durch H3-Kosten begrenzt, W1-3) | DIRECTLY_VERIFIED (Framework) | PR #917 offen — Änderungen angefordert | Nacharbeit Muse (O6) |

| K6 | Engine-Event-Tap (typisierte GameEvents, nur public, mit Sequenz) | DIRECTLY_VERIFIED | PR #918 offen — Änderungen angefordert (nur 6 der 18 behaupteten Event-Typen existieren im Watcher) | Nacharbeit bei Muse |
| K7 | In-Engine-Simulation/Bookmarks | — | T4, nur Referenz — D17 verbietet Piloten in der JVM | nicht implementieren |
| K8 | Mage.Verify-MTGJSON-Cross-Check | — | T4, durch `xmage_card_facts.json` abgedeckt (Kartenanzahl der Datei widersprüchlich überliefert, s. §3 Korr-11) | kein Transfer |
| K9 | CI-Gate-Trennung | MODELED | **widerlegt** durch H1 | geschlossen |

Verworfen (T5): AI-Player-Module in der Bridge (D17-Verstoß), Mage.Client/Server für
Headless, Upstream-`RandomUtil` als RNG-Vorbild.

Restrisiken aus dem Transfer-Report, weiterhin gültig:
- `full_game_pilot_views.py` deutet Engine-Text heuristisch (Regex) nahe der
  Rules-Authority — CODE_DERIVED-Risiko, von K4 adressiert.
- Lokaler `mage`-Checkout (`master`) ≠ Pin-Branch: Wer Fork-Code liest, muss den
  Pin-Stand verwenden, sonst fehlen GameRandom/`setRulesSeed`/PRs #26–#61.
- Kein per-op-RNG-Tap; Tape trackt Engine-RNG nur koordinatenbasiert (dokumentierte Lücke).

### 2.6 Fork-Patch-Analyse + Bisektion (aktuellster Stand, 2026-10-20)

Ausgangslage: JAR A (Fork-Head `10931648`) vs. JAR B (Baseline-Pin): 35/36 vs. 36/36
Seeds OK, Seed 10 reproduzierbar ENGINE_FAILURE nur in A, 29/35 vergleichbare Seeds mit
abweichenden Semantic Hashes.

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| B1 | **Bisektion V0–V4:** Kein Einzel-Revert (V1=H-PI aus, V2=H-CI aus, V3=H-TA aus) und auch V4 (alle aus) ändert etwas — alle Varianten liefern bit-identisch Seed 5 = `4ca08e0e…` (Mismatch) und Seed 10 FAILED. Baseline vorher exakt kalibriert (beide Baseline-Hashes reproduziert) | DIRECTLY_VERIFIED | erledigt | H-PI/H-CI/H-TA sind als Ursache **ausgeschlossen** |
| B2 | **Ursache der Hash-Abweichungen:** Fork-Diff Pin..Head in `Mage.Sets/cards`: 48 Dateien neu, nur 6 modifiziert — alle 6 sind Turbulent-Dual-Lands, ersetzt durch „Simplified implementation" **ohne** Mana-Abilities und ETB-Effekt (Pin-Version von Turbulent Steppe: `RedManaAbility` + `WhiteManaAbility` + `EntersBattlefieldTappedUnlessAbility`) | DIRECTLY_VERIFIED | offen (Fix ausstehend) | Fix = echte Implementierungen wiederherstellen (Claude-Thread 1) |
| B3 | Turbulent Steppe ist die einzige geänderte Karte im Smoke-Pod (`.deck.cards[11]`, Lorehold Spirit Precon; Pod = 319 distinkte Karten) und gibt im Fork kein Mana → abweichende Verläufe ab den ersten Zügen; Fork-Trajektorie Seed 5: 3980 Decisions/Winner [3] vs. Baseline 5765/[1] | DIRECTLY_VERIFIED | erledigt (Zuordnung Seed 5) | Erklärt 29/35 ohne jeden Core-Hunk |
| B4 | **Seed-10-Crash: Ursache UNKNOWN.** Ein mana-loses Land muss die Engine nicht crashen lassen; Zuordnung erst durch V5 | UNKNOWN | offen | V5-Diskriminator: nur die 6 Turbulent-Dateien auf Pin zurück, Rest Fork-Head (~10 Min) |
| B5 | Verbleibendes Delta V4↔Pin neben den Karten: 48 neue Karten + 10 Set-Dateien (u. a. Kartennummern 2000+), P1-Fast-Path und `AbilitiesImpl.singleton` bleiben aktiv — falls V5 nicht alles heilt, ist dort weiterzusuchen | CODE_DERIVED (Diff-Aufzählung) | offen | Reihenfolge nach V5-Ergebnis |
| B6 | H-CI (CardImpl-Fast-Path) bleibt ein realer Delta zum Pin (Pin baut immer frische Aggregat-Liste) — aber nach B1 **nicht** die Ursache der gemessenen Abweichungen; Fix-Empfehlung aus der korrigierten Rangfolge (Fast-Path entfernen/defensive Kopie) bleibt als Hygiene bestehen, ohne Bug-Behauptung | CODE_DERIVED | offen | Nicht mit B1 verwechseln: unschädlich ≠ bewiesen korrekt |
| B7 | Laufzeiten für Anschlussplanung: volle Maven-Modul-Kette ~10,5 Min, Core-Rebuild ~21 s, Bridge ~60–80 s, Orakel (2 Seeds) 2,5–4 Min, 36-Seed-Lauf ~34 Min | DIRECTLY_VERIFIED | erledigt | — |
| B8 | Abschlusskonfiguration (36 Seeds, 0 Mismatches) ist **nicht gelaufen** — im Hunk-Rahmen existiert keine saubere Konfiguration; Lauf erst nach Fork-Fix sinnvoll, dann Wiederholung auf Claudes Stand | NOT_RUN | offen | Kein PASS ableitbar |

### 2.7 Upstream-Delta

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| U1 | Fork liegt **108 Commits** hinter `upstream/master` @ `bb0ed0f7` (Snapshot 2026-10-19): ~29 neue Karten, ~49 Bug-Fixes (u. a. Mana-Abilities 605.1a, „Triggers an additional time", Elesh-Norn-Fix, Convoke/Blitz-Kosten, Party-StackOverflow) | CODE_DERIVED (Commit-Klassifikation) | offen | Übernahme lohnt sich, ist aber eigenes Projekt |
| U2 | **5 garantierte Konflikte:** Upstream ändert GameImpl/GameState/CardImpl/PlayerImpl/AbilitiesImpl — exakt die Fork-Patch-Dateien; dazu Fork-APIs (`getRulesSeed` u. a.), die Upstream nicht hat. Repin-Versuch auf 1.4.62 (`eb69d05b`) wurde bereits zurückgenommen, weil die Bridge gegen Upstream nicht baut | DIRECTLY_VERIFIED (fehlgeschlagener Repin) | erledigt (als Befund) | Kein Repin ohne Portierung + Requal |
| U3 | Verbindliche Reihenfolge: **Patch-Fix (36 Seeds, 0 Mismatches) → Update-Branch `update-upstream-2026-10` → Requal PB-03 → Repin nur mit Owner-Go.** Vor Umsetzung will Hans die Analyse-Punkte 1–3 (Delta, strukturelle Gründe, Übernahme-Analyse) sehen | — (Entscheidung) | offen | Kein Upstream-Start vor Fork-Fix |

### 2.8 Precon-Audit

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| PC1 | **Beide Kennzahlen sind UNKNOWN:** „195/195 Crash, 221 fehlende Karten" (Muse-Übergabe) und „192/195 importierbar, 0 fehlende Karten" (PR #914). Keine Entscheidung darf auf einer der beiden aufbauen | UNKNOWN | offen | Issue #920 bleibt offen |
| PC2 | Herkunft der 221: Dateinamen-Heuristik (Kartenname → Klassenname gegen Java-Dateilisten): 6350 unique Karten, 316 im Baseline fehlend, 95 durch vereinfachte Karten abgedeckt, 221 „fehlend". Heuristik ignoriert Set-Registrierungen und Sonderfälle | MODELED (heuristisch abgeleitet) | widerlegt als Messung | Nie als gemessene Zahl zitieren |
| PC3 | Gegenindiz zur Fehlende-Karten-These: `2011_counterpunch` (nur alte Karten, Commander existiert) crashte im Sweep ebenfalls | DIRECTLY_VERIFIED (Sweep-Beobachtung) | offen | Spricht für Laufzeit-/Pfad-Ursache statt fehlender Karten |
| PC4 | Muses Sweep (195/195 ENGINE_FAILURE, wall_s=0.0) lief über den Benchmark-Pfad (`_setup`/`_play`), **nicht** über den produktiven Import-Pfad — Pfad-Artefakt nicht ausgeschlossen | DIRECTLY_VERIFIED (Methodik) | offen | Nachmessung muss den produktiven Pfad nehmen |
| PC5 | Nicht ausgelieferte Hintergrund-Research (2026-10-19, **unverifiziert**): produktionsnahe JSONL-Validierung ergab 190/195 OK; 4× `CARD_IDENTITY_MISMATCH` (Split-Name „Vorderseite // Rückseite" in `commander.commanders` vs. `oracle_name` nur Front) → gefixt 194/195; 2026_multiverse_reforged (Jace ohne `CanBeYourCommanderAbility`) sei im Fork-Head bereits gefixt; die 3 Sweep-Fehler (Eye of Duskmantle, Arachnogenesis, type=OTHER) reproduzierten nicht | UNKNOWN (nicht re-verifiziert) | offen | Nur als Hypothesenliste für die Nachmessung verwenden |
| PC6 | **Validator-Root-Cause gelöst:** „Fehlende Karten" bei der Deck-Validierung waren stale Card-DB-Rows (SET, 999); CardScanner überspringt doppelte Set+Nummer-Schlüssel. Fix: DB gelöscht + Rescan; Commit `7541e4fd` vergab eindeutige Kartennummern (2000+) | DIRECTLY_VERIFIED | erledigt | Bei künftigen „missing cards" zuerst DB-Zustand prüfen |
| PC7 | 195 Precons liegen nur auf Branch `muse/precon-pilot-improvements` (nicht auf main); 3 illegale Decks entfernt (Trade Secrets gebannt, Mossfire Valley ×2, Dockside Extortionist gebannt) | DIRECTLY_VERIFIED | erledigt | — |

### 2.9 Simplified Cards

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| S1 | Alle vereinfachten Karten sind **SYNTHETIC**: korrekte Kosten/Typ/P-T/Basis-Keywords, komplexe Fähigkeiten weggelassen; Import/Parsing beweist keine Kartenfunktion | SYNTHETIC | offen | Pro Karte In-Game-Smoke-Test ausstehend |
| S2 | **Anzahl widersprüchlich:** Simplified-Doku und WS2 sprechen von ~45, Source-Lock-Audit von ~35, die Übergabe von 95. Der Fork-Diff (Bisektion) zählt 48 neue + 6 ersetzte Kartendateien. Keine der Doku-Zahlen ist am Diff verifiziert | UNKNOWN (Zählung) | offen | Verbindlich nur die Diff-Zählung (48 + 6) verwenden |
| S3 | **Dokumentationslücke mit Folgen:** Die Simplified-Doku listet nur neu angelegte Karten. Die 6 **ersetzten Bestandskarten** (Turbulent-Lands, §2.6 B2) stehen nicht darin — ausgerechnet sie verursachten den Semantik-Bug | DIRECTLY_VERIFIED | erledigt (als Befund) | Doku um „ersetzte Bestandskarten" ergänzen; Ersetzungen künftig wie Neuanlagen dokumentieren |
| S4 | Stichprobe der Doku-Tabelle zeigt Einträge mit „(see source)" statt konkreter weggelassener Fähigkeit (u. a. Ichor Elixir, Susan Foreman) — Doku an diesen Stellen unvollständig | CODE_DERIVED | offen | Bei Vollimplementierung nachpflegen |

### 2.10 /oc-zai-Lane und CI-Befunde (Claude-Thread 2, von Muse an lokalen Dateien gegengeprüft)

| # | Befund | EK | St | Konsequenz |
|---|--------|----|----|------------|
| Z1 | **Beide /oc-zai-Workflows ungültig** (#919 CPL, mage #62): Job-Level `env: OPENCODE_CONFIG_CONTENT: ${{ env.ZAI_PROVIDER_CONFIG }}` nutzt den dort verbotenen `env`-Kontext (actionlint; `opencode.yml` als Kontrolle sauber). Jeder Push erzeugte nur Läufe ohne Jobs — /oc-zai und /oc-zai-review reagierten nie | DIRECTLY_VERIFIED | offen (Fix bereit) | Korrigierte Dateien durch Hans per Web-UI einspielen (GitHub-App hat keine `workflows`-Permission); Test der Lane erst nach Merge von #919 |
| Z2 | Z.ai-Modellwahl: `glm-4.7-flash` kostenlos (nur Rate-Limit), `glm-5.3-flash` kostenpflichtig; Standard-API-Key genügt | CODE_DERIVED (Anbieter-Doku) | erledigt | Lane läuft auf `zai/glm-4.7-flash`, VARIANT max |
| Z3 | mage #62: `VerifyCardDataTest` (`test_checkMissingSetData`, `test_verifyCards`, 2 von 6835 Tests) ist **pre-existing rot auf master `10a73922`, seit 08.10.**, identische Zahlen — nicht PR-verursacht; der PR ändert nur die Workflow-Datei | DIRECTLY_VERIFIED | offen (Merge-Entscheidung Hans) | #62-Rot nicht dem PR anlasten; Grund des Qualify-Fehlers separat diagnostizieren (Thread 2) |
| Z4 | #914: CI-Trio (`quality`/`security`/`infrastructure`) grün auf Head `4f3af5ea`; PR ist noch Draft, hinter main, Text veraltet. Pilot-Vergleich (11/12) ist als Kommentar gepostet — Merge-Bedingung erfüllt | DIRECTLY_VERIFIED | offen | Text aktualisieren + Draft lösen (Hans/Thread 2) |
| Z5 | #919 nach Muses Fix: Tests grün (13/13 WS223-Identitätstests; `opencode-zai.yml` in beiden Ausnahmelisten klassifiziert); Workflow selbst bleibt bis Z1-Fix wirkungslos | DIRECTLY_VERIFIED | offen | Abhängig von Z1 |
| Z6 | `ci-definition-integrity-shadow` ist rot by design und kein Blocker; required Checks sind `quality`, `security`, `infrastructure` | — (Repo-Regel) | erledigt | In CI-Auswertungen nicht als Fehler zählen |

---

## 3. Korrigierte und widerlegte frühere Befunde

Diese Sektion ist verbindlich: Wer eine ältere Analyse zitiert, muss diese Korrekturen mitführen.

| # | Frühere Behauptung (Quelle) | Korrektur | Evidenz |
|---|------------------------------|-----------|---------|
| Korr-1 | „P2 (CardImpl-Fast-Path) ist mit ~80 % der Übeltäter, Aliasing-Bug bestätigt" (Patch-Analyse 2026-10-19) | **Widerlegt.** V2 (nur H-CI aus) ändert nichts; kein Hunk ist die Ursache (B1). Zusätzlich war der vorgeschlagene Fix („unmodifiable wrapper") unbrauchbar — 176 mutierende Aufrufstellen, und `MageObjectImpl.getAbilities()` gibt auch am Pin direkt zurück | DIRECTLY_VERIFIED (Bisektion) |
| Korr-2 | Korrigierte Rangfolge „PlayerImpl nested-copy ist Hauptverdächtiger" (fork-patches/README, 2026-10-20) | **Ebenfalls widerlegt** — V1 (nur H-PI aus) ändert nichts. Die Rangfolge war reine Code-Lektüre ohne Laufzeit-Beleg | DIRECTLY_VERIFIED (Bisektion) |
| Korr-3 | „Es sind nicht die neuen Karten" (Problem-Analyse Seed10/Mismatches) | **Falsch in der Sache:** Neue Karten sind es zwar nicht, aber die 6 **modifizierten** Karten sind es. Die Analyse unterschied nicht zwischen hinzugefügten und ersetzten Karten | DIRECTLY_VERIFIED (Diff + Bisektion) |
| Korr-4 | „8 semantische Mismatches" (erste 36-Seed-Auswertung) | Späterer vollständiger Lauf ergab **29/35** Mismatches; die 8 war ein Zwischenstand | DIRECTLY_VERIFIED |
| Korr-5 | „221 fehlende Karten verursachen 195/195 Precon-Crashes" (Claude-Übergabe 2026-10-19) | **UNKNOWN** — Heuristik statt Messung (PC2), Gegenindiz PC3, Pfad-Artefakt PC4. Ebenso ist „192/195 importierbar" aus PR #914 UNKNOWN | s. §2.8 |
| Korr-6 | „~45 vereinfachte Karten" als Gesamtzahl des Fork-Deltas (Simplified-Doku, WS2) | Fork-Diff zählt 48 neue + 6 ersetzte Dateien; „~35" (Source Lock) und „95" (Übergabe) stimmen ebenfalls nicht mit dem Diff überein (S2) | DIRECTLY_VERIFIED (Diff) |
| Korr-7 | Reihenfolge „ZUERST P2-Bug fixen, dann Upstream-Update" (Upstream-Analyse) | Entfällt mit Korr-1: Es gibt keinen bestätigten P2-Bug. Reihenfolge bleibt Patch-Fix → Update → Requal → Repin, aber der „Fix" ist der Turbulent-Fix aus B2 | DIRECTLY_VERIFIED |
| Korr-8 | „Precon-Crash = vereinfachte Karte crasht zur Laufzeit" (WS2-Vermutung, Precon-Issue-Draft) | Unbewiesene Hypothese; WS2 maß am Baseline-JAR über einen anderen Pfad als der spätere Sweep. Ursache weiterhin UNKNOWN (PC1) | UNKNOWN |
| Korr-9 | „/oc-zai-Lane implementiert, nur ungetestet" (Übergabe) | Die Workflows waren **ungültig** und konnten nie laufen (Z1) — „ungetestet" untertrieb den Zustand | DIRECTLY_VERIFIED |
| Korr-10 | Übergabe-Artefakt mit veraltetem Dateiinhalt (Muse, API-Push 2026-10-19 23:39, brach #914-CI: F401/E402/Format) | Behoben und Lehre institutionalisiert: nach jedem API-Push Remote-Inhalt gegen lokal diffen (CDN-Lag beachten) | DIRECTLY_VERIFIED |
| Korr-11 | `xmage_card_facts.json`: Transfer-Report nennt 7296 abgedeckte Karten; Source-Lock-Audit nennt 2104 und vermerkt, die 7296-Erweiterung sei revertiert worden (brach Phase-10-Test) | Aktueller Dateistand aus den Quellen nicht entscheidbar — als offene Zählfrage markiert, keine der beiden Zahlen ohne Dateicheck zitieren | UNKNOWN |

---

## 4. Offene Punkte mit Owner

| # | Punkt | Owner | Abhängigkeit / nächster Schritt |
|---|-------|-------|----------------------------------|
| O1 | Fork-Fix: echte Implementierungen der 6 Turbulent-Lands wiederherstellen | Claude-Thread 1 | Danach V5-Äquivalent + 36-Seed-Lauf; Fork-Push erst nach Hans-Go |
| O2 | V5-Diskriminator bzw. Verifikation des Fixes (Seed 5 → Baseline-Hash? Seed 10 → OK?) | Claude-Thread 1 (führt Fix + Verifikation autonom aus; Muse wiederholt den 36-Seed-Lauf nur auf Zuruf) | Löst B4 (Crash-Zuordnung) |
| O3 | Seed-10-Crash-Ursache, falls nach O1 weiter offen | Claude-Thread 1 | Kandidaten: B5 (Set-Registrierungen, P1, singleton) |
| O4 | Precon-Nachmessung über den produktiven Import-Pfad + Abgleich mit Set-Registrierungen des Forks; Issue #920 danach korrigieren/schließen | Muse | PC1–PC5 als Hypothesenliste; keine Entscheidung vor Messung |
| O5 | Reviews #915–#918 abschließen | Claude-Thread 2 | #916 mergefähig; #915/#917/#918 mit Änderungsforderungen |
| O6 | Nacharbeit #915/#917/#918: Tests gegen echte Bridge-Ausgabe statt handgebauter Mengen; #918 auf die 6 realen Event-Typen begrenzen | Muse | Nach Thread-2-Review |
| O7 | #916 mergen; #914 PR-Text aktualisieren, Draft lösen | Hans (Merge), Claude-Thread 2 (Text) | CI-Trio auf #914 bereits grün |
| O8 | /oc-zai-Fix-Dateien in beiden Repos per Web-UI einspielen | Hans | Danach Merge #919 → Lane-Test `/oc-zai-review` (Thread 2) |
| O9 | mage #62: Merge-Entscheidung trotz pre-existing rotem Verify | Hans | Diagnose des Qualify-Fehlers: Claude-Thread 2 |
| O10 | Upstream-Update: Analyse-Punkte 1–3 an Hans (Delta-Messung, strukturelle Gründe, Übernahme-Analyse) | Claude (leitend) | Umsetzung erst nach O1/O2; Repin nur mit Owner-Go |
| O11 | Simplified-Doku vervollständigen: ersetzte Bestandskarten aufnehmen, „(see source)"-Einträge konkretisieren | Muse | S3/S4 |
| O12 | In-Game-Smoke-Tests je vereinfachter Karte (wird sie gespielt, ohne zu crashen?) | offen (Muse/Claude nach Priorisierung) | S1; abhängig von O4-Methodik |

---

## 5. Methodik & Evidenz-Standard

**Evidenzklassen** (jede Feststellung trägt eine; fehlt sie, gilt UNKNOWN):

| Klasse | Bedeutung |
|--------|-----------|
| DIRECTLY_VERIFIED | Selbst ausgeführt/beobachtet (Lauf, Messung, Diff, Hash-Vergleich) |
| CODE_DERIVED | Aus Code-Lektüre abgeleitet, nicht laufzeitgeprüft |
| TECHNICALLY_CONFORMANT | Baut/entspricht der Spezifikation, ohne Verhaltensnachweis |
| EXTERNALLY_RULE_VALIDATED | Gegen die offiziellen Regeln validiert |
| MODELED | Modell/Schätzung mit benannten Annahmen |
| SYNTHETIC | Vereinfachte Ersatz-Implementierung; Verhalten ≠ Original |
| UNKNOWN | Nicht gemessen / nicht belegt — **niemals PASS** |

**Korollare:** PARTIAL ≠ FULL · NOT_RUN ≠ PASS · CODE_DERIVED ≠ RUNTIME_VERIFIED ·
Import/Parsing beweist keine Kartenfunktion · grüner Workflow beweist keine Rules-Qualifikation.

**Arbeitsregeln, die aus Fehlern entstanden sind:**
- **„A compile is not a test."** Vor jedem OK steht der Lauf, der die geänderte Zeile
  ausführt (Java: ein echtes Spiel; Python: ein Test, der ohne die Änderung fehlschlägt).
- **Kalibrierungs-Prinzip:** Vor jeder Bisektion/Vergleichsmessung muss die Baseline
  ihre bekannten Hashes exakt reproduzieren (so geschehen vor V0–V4) — sonst ist das
  Setup nicht vergleichbar und alle Varianten-Ergebnisse wertlos.
- **Unverifizierte Engine-Annahme = Blocker.** Engine-Konventionen (Indexierung,
  Reihenfolge, Reinheit von Methoden) werden an realem Code/realen Daten belegt,
  nicht aus Erfahrung übertragen (Beleg: H-TA-Annahme „checkEventType ist pure" war
  nie verifiziert; PR #57 zeigt, dass Iterationsordnung eine reale Fehlerklasse ist).
- **Verdächtigen-Rangfolgen aus Code-Lektüre sind Hypothesen, keine Befunde** —
  zweimal in diesem Projekt von der Messung widerlegt (Korr-1, Korr-2).
- **Zahlen tragen ihre Herkunft:** Heuristisch abgeleitete Counts (PC2) werden nie
  als Messwerte weitergereicht.

---

## 6. Quellen

- `Phase-A-Project-Audit-Report.md`
- `Phase4-Audit-Modul-Inventur.md`
- `WS1-Handoff-2026-10-19.md`
- `WS2-Handoff-2026-10-19.md`
- `K2-Handoff-2026-10-19.md`
- `XMage-Architektur-Transfer-Report.md`
- `Source-Lock-Audit-2026-10-19.md`
- `Patch-Analyse-2026-10-19.md` (Rangfolge widerlegt, s. §3 Korr-1)
- `Problem-Analyse-Seed10-Mismatches.md`
- `XMage-Upstream-Update-Analyse-2026-10-19.md`
- `Simplified-Cards-Documentation.md`
- `Precon-Issue-Draft.md`
- `Claude-Uebergabe-Komplett-2026-10-19.md`
- `bericht.md` (Bisektion V0–V4, 2026-10-20; abgelegt unter `handover/2026-10-20/bisektion/`)
- `handover/2026-10-19/fork-patches/README.md` (Branch `muse/claude-handover`; Rangfolge widerlegt, s. §3 Korr-2)
