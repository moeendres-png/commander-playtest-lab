# Phase 8 — 40 praktische Integrations-/Release-Testfälle

**Stand:** 2026-11-08 · **Alle Tests sind in dieser Phase SPEZIFIZIERT, NICHT NEU AUSGEFÜHRT.** Dieser Katalog verbindet Playgroup-Live-Phasen #1135–#1141 mit dem aktuellen Lab (`main@79b549ba576d5cc612b4ab92cd17b28ebe25d0e6`). Quelle, Requirements und umsetzbare Abhängigkeiten im [Masterroadmap](PLAYGROUP_LIVE_PHASE8_MASTER_ROADMAP_20261108.md).

**Valid execution contract:** Für jedes zukünftige Ergebnis zwingend `lab_git_sha`, `engine_pin` aus `config/rules_engines.json`, `bridge_jar_sha256`, `deck_hash` für jeden Sitz, `pilot_policy`, `pod`, `seed`, `player_count` (2–6), `current_actor`, `terminal_status`/Fehler, `event_digest`, `decision_digest`, `peak_process_rss`, `wall_seconds`, `disk_spool_bytes`, `test_id`, `test_artifact_path`. **Keine** privaten `data/collections/**` Dateien oder Playgroup-Deckuploads. Öffentliche Fixture-Decks; Chulane nur aus explizit freigegebener und source-gelockter Owner-Baseline.

## G. Governance, Merge und Rules-Authority (6 Fälle)

| ID | Praktischer Versuch / Eingabe | Pass-Bedingung | Ausführbarkeit |
|---|---|---|---|
| G01 | PR #1134 Chulane-Fokus gegen neuen Main integrieren; CI-Definition-Shadow prüfen | Neuer `test_deckbau_chulane_focus.py` unabhängig geprüft, vorgeschriebenes Review dokumentiert, kein CI-Bypass; RogShai-Referenzen bleiben historisch | Jetzt als Review |
| G02 | PR #1135 mit #1134 README-/Policy-Kollision prüfen | 4P Standard, operativ max 6, 6P Qualifikation und 2–5 Replay-Gap explizit; neuer `test_owner_player_cap.py` autorisiert, kein Gate-Bypass | Jetzt als Review |
| G03 | Alle PRs #1136–#1141 auf geändertem Main auf Diff/CI/Quelle kontrollieren | Docs-Fakten und Referenzen erhalten, keine Copy von Playgroup-Proprietärquellen, keine neue operative Rule-Änderung | Jetzt als Review |
| G04 | Realen Simulator mit 7, 8 und 10 Sitz-Requests füttern, inklusive Job-, API- und Deckvergleichs-Pfad | Jeder neue operative Request wird **vor JVM-Allocation** zurückgewiesen; 6 nur bei konkret erlaubter Lane | Aktuelle Schema-Tests; neue Gateway-Lane später |
| G05 | Gemergte Quelle mit `AGENTS.md`/Pin/Owner-Deck-Hash abgleichen | Keine unangekündigte Engine-Pin-, Rules-, Active-Deck- oder sealed evidence-Mutation; exact source lock identisch | Jetzt Review; nach Merge recheck |
| G06 | Pauschale Aussage `CI green => full-play PASS` in automatischem Report provozieren | CI-Scope und echte Full-Game-Gates separat, fehlender native Smoke bleibt `NOT_RUN`/unknown | Reporting-Gate planbar |

## E. XMage 4P-Verhalten, native Entscheidung und Reproduzierbarkeit (8 Fälle)

| ID | Praktischer Versuch / Eingabe | Pass-Bedingung | Ausführbarkeit |
|---|---|---|---|
| E01 | Chulane vs. drei public precons: 4P vollständige Partie, aktiver XMage-Pin | Tatsächlicher Terminal-Status, Native-Deck-Readiness, keine ungeprüfte Engine-Fallback-Option, Source-locked Decks und Seeds | Bestehender Runner; Pin/JAR notwendig |
| E02 | Fremder Counter gegen Chulane-Creature, mehrteiliger Stack und Priority-Rotation | Offered actor/options, vollständige LIFO-Auflösung, native Instants/Triggers; keine UI/Policy-Legalitätserfindung | Bestehende XMage fixtures + Real game |
| E03 | Chulane Creature Cast + Trigger, Bounce (Whitemane Lion), Draw/Land | Native Triggermenge, Reihenfolge, echte eigene Kartenziehung; keine künstlichen Wiederholungen | Bestehendes XMage; neue feste Goldens |
| E04 | Gegner gezieltes Removal auf Chulane, Schutz/Counter verfügbar/nicht verfügbar | Nur real in Hand/Mana angebotene legale Antworten; kein Phantom-Counter/Auto-Pass | Bestehendes XMage; neue Goldens |
| E05 | Commander Tax und 21 Commander-Schaden von zwei unterschiedlichen Quellen | Native Tax +2 pro Cast aus command zone, unabhängige Quellensummen; Verlust exakt Regelkonform | Bestehendes XMage; Goldens erweitern |
| E06 | Chulane + Manufactor/Clue + Psychosis Crawler, echte 4P Win-Bedingung | Tokenquelle und Damage durch native Rules und Ereignisse; keine gefälschten Siegstatus | Bestehendes XMage; source card support zuerst |
| E07 | Gleiches seed/pod/deck/pilot, reproduzierbare Spielentscheidungen im frischen Prozess | Vergleichbare decision-set/actor/event digests und zugelassene deterministische Replay-Scope; `UNKNOWN` bei Abweichung | Bestehende replay verifier, exact source |
| E08 | Falscher Actor, stale decision_id, off-menu option, illegal mana target | Native Bridge abgewiesen, keine Zustandsänderung, keine erste Option als Fallback | Bestehende Fail-Closed-Tests, browser später |

## V. Read-only Browser-Viewer, Sichtschutz und UI (8 Fälle)

| ID | Praktischer Versuch / Eingabe | Pass-Bedingung | Ausführbarkeit |
|---|---|---|---|
| V01 | 4P echte laufende XMage-Partie als read-only Chulane-Board öffnen | Alle vier HUDs, Chulane-Hand, Battlefield, Stack, Priority und native Ereignisse korrekt dargestellt | V1/V2 Implementierung nötig |
| V02 | Spectator ohne Sitzberechtigung liest dieselbe Partie | Nur öffentliche Board-/Hand-**Anzahlen**, keinerlei fremde private Kartennamen, Bilder, IDs, Mana-Pool oder Deck/Seed | Auth-Gateway/Viewer nötig |
| V03 | Gegner schaut in Library, macht Scry/Surveil und reveal-to-one | Actor-spezifische temporäre Identität nur während XMage-Erlaubnis; Snapshot/Event/Cache Byteprüfung leckt nichts | Actor-safe arbiträre View nötig |
| V04 | Spieler kontrolliert Gegnerzug nach CR 723; Zuschauer bleibt verbunden | Entscheidung beim native berechtigten Controller, aktive Runde ≠ Entscheidungsauth, keine Hand-Leaks | Actor authorization gateway nötig |
| V05 | Face-down Morph/Disguise, Foretell, Face-down Exile in öffentlichem Log | Namen/Bilder nicht über Kartenrenderer/Tooltip/DOM/Cache/Events offengelegt | Browser end-to-end nötig |
| V06 | Chulane mit 15+ Creatures, 25+ Clues, 10+ Treasure Tokens | Grafische Gruppierung **ohne** native Objekte zu verschmelzen; genaue Auswahl und Counts | Phase4 UI build nötig |
| V07 | Tablet/Phone Landscape, Touch, Keyboard, 4P & 6P Wireframe | Own hand/priority/stack lesbar, Fokus ohne Auth-Eskalation; reduzierter Animationsmodus | Browser layout tests nötig |
| V08 | Hohe Stack-/Triggerdichte, fehlende Karte/Art, Bildfehler und Rendering-Drosselung | Accessibility/Details und Optionsauswahl bleiben korrekt, keine native Ereignisse gedroppt, nicht Blockieren der Engine | UI + load fixtures nötig |

## N. Human multiplayer, Reconnect, Eventstream & Replay (6 Fälle)

| ID | Praktischer Versuch / Eingabe | Pass-Bedingung | Ausführbarkeit |
|---|---|---|---|
| N01 | 4P ein menschlicher Sitz und KI; native „cast → target → priority pass“ über Web | Exakte `decision_id/option_id` nur aktueller berechtigter Actor, keine alternative Rules-Engine | Human native gateway nötig |
| N02 | Doppelklick, Netzwerk-Retry, alte Browser-Tab-Session und Replay eines `choose` | Writer-Epoch+Nonce verhindern doppelte/alte Aktionen; off-menu, stale und wrong seat verboten | Gateway + transport injector nötig |
| N03 | 4P Netzwerkunterbrechung bei laufender Entscheidung, Rejoin innerhalb Deadline | Neue Auth, aktueller redacted Snapshot, gültiger pending Offer, korrekte Eventoffets; Deadline **unverändert** | Gateway reconnect nötig |
| N04 | Rejoin nach Native Decision Timeout (120s) oder abgestürzter JVM | Ehrlicher Fehler/Terminal, **kein** Auto-Pass, Skip, zufälliger Cast oder unechte Resume-Fortsetzung | Gateway + fault injection nötig |
| N05 | Öffentlicher Spectator sendet unberechtigten Cast, fragt private Replay-Datei an | Schreibzugriff verweigert; nur öffentliche Timeline, keine `scope=orchestration_only`-Daten/Seeds/Decks | Spectator & ACL nötig |
| N06 | Browserhistorie nach 4P und 6P Session, alte Eventoffets, Source-locked Replay-Verifikator | Idempotent public snapshot/event timeline; Semantic Tape **6P nicht als PASS**, solange Schema nur 2–5 erlaubt | Viewer replay 4P neu; 6P gap |

## A. Card Insights und KI als empirische Funktionsprüfung (6 Fälle)

| ID | Praktischer Versuch / Eingabe | Pass-Bedingung | Ausführbarkeit |
|---|---|---|---|
| A01 | Chulane 4P: Karten aus Opening-Hand, natürliche Draws, zurückgebouncter Whitemane Lion | Korrekte physische Card-Instance + eigene Handintervalle, Rückkehr **nicht als neuer natürlicher Draw** | Actor-private CardCollector neu |
| A02 | Instant mehrere gegnerische Züge gehalten, legal mehrfach angeboten, einmal gecastet | Handverweildauer und Cast-vs-Offer-Nenner sauber; korrekt gehalten ≠ „dead draw“ | CardCollector + reducer neu |
| A03 | 3-MV Creature on/before own turn 3, Flexkosten, Commander aus Zone | Cast-on-Curve versioniert, Deckkarten getrennt von Commander, Land nicht als spell cast | New metric reducer |
| A04 | Manufactor Clues/Treasure, Chulane native draw/land, Crawler damage | Direkt von Rules-Event verknüpfte Card Contribution oder `UNKNOWN`; kein Oracle-Ratespiel | Native source attribution neu |
| A05 | Playgroup globale Card-Statistik mit lokaler Chulane-Winrate vergleichen | Quellen/Datum/CC BY-Attribution, externe Daten **nicht** als unser Chulane-Pod gewertet | Reporting review jetzt, dashboard später |
| A06 | KI-Kontrast: gleicher 4P Pod, Seeds/Seat-Rotationen, normal vs. kalibrierter Pilot | Native-only legal options, echte Interaktionsgelegenheiten, fehlende Win-/Rank-Power als UNDERPOWERED/UNKNOWN, CPU-Kosten dokumentiert | Bestehende Runner, neue Pilotstudie nur nach Daten |

## S. Kapazität, 6P-Spezialgates und Release (6 Fälle)

| ID | Praktischer Versuch / Eingabe | Pass-Bedingung | Ausführbarkeit |
|---|---|---|---|
| S01 | Kontrollierte 4P / 6P public-pod Games: gleiche Engine, Hardware, Pilot; mehr Seeds | CPU/RSS/GC/Wall/Decisions/Stack/Trace getrennt, Reports mit Fehlern und Konfidenz, keine naive `3.2×` Extrapolation | Bestehender Runner; Host/JAR erforderlich |
| S02 | 6P großes Trigger-/Token-Board, mehrere tausend Stack-Einträge | Ressourcenstopp dokumentiert, disk-backed Decisionspool, kein Spielresultat erfunden | Full Game 6P + telemetry |
| S03 | 6P spectators + action permission + CR 723 | 6P actor isolation, keine private Sicht, Verbindungsabbruch safe, reale Session qualified | Neue gateway; extra 6P E2E |
| S04 | 6P `TapeGameManifest` anlegen und Replay ausführen | Aktuell bewusst `UNQUALIFIED`; erst nach **separater** Schema-/Native-Qualifikation PASS | Aktueller Gap prüfbar; später fix |
| S05 | Fiktiver 8P-URL/API-Button und 7+/10P Jobs | Kein operatives Produkt mit mehr als sechs; native Mage-Forschung muss komplett isoliert sein | Current gate tests + UI API later |
| S06 | Lokaler End-to-End-Launch ohne Paid-Keys, Lizenzen und Versionswerte | 4P Standard lokal ohne Pflichtkosten; Regel-/Privacy-/CI-Gates bestanden, 6P nur wo qualifiziert; CI/branch SHA dokumentiert | Erst nach V2/I1/N1 etc. |

## Run order and evidence promotion

**Now (Review + available source tests):** G01–G06; E01–E08 when exact pinned JAR/fixtures available; S01/S02 on measured target hardware. They should be reported individually as PASS/FAIL/UNKNOWN/SKIPPED, not one blanket release claim.

**After read-only integration (V1/V2):** V01–V08. **After human gateway / session orchestration (I1/N1):** N01–N05. **After Replay work (R1):** N06, S04. **After CardCollector / Pilot trial (A1/P1):** A01–A06. **After 6P capacity (S1):** S03/S05/S06.

**Preserve falsifiability:** A scenario is evaluated **only if** an actual source-locked execution artifact with source and outcomes exists. A successful unit/lint/doc CI check on any Phase 1–8 planning PR **cannot** certify these cases. Current verdict for this new catalog = **40 SPECIFIED; 0 newly executed as part of Phase 8**.

**Sources:** Phases 1–7 draft PRs #1135–#1141; source files and current-CI status documented in [Masterroadmap](PLAYGROUP_LIVE_PHASE8_MASTER_ROADMAP_20261108.md). Private `data/collections/**` inventory and personal secrets were not accessed.
