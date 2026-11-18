# Commander Studio: verbindlicher Scope (Stand 2026-11-18)

**Was diese Datei ist.** Der verbindliche Scope der drei Studio-Bereiche BUILD, PLAY und SIMULATE
sowie von Engine/Bridge und Betrieb bis zum Projektabschluss. Grundlage sind die Owner-Antworten
vom 2026-11-18 in `docs/OWNER_DECISIONS_STUDIO_20261118.md` (zitiert als E1 bis E6, G-SIM) und
die älteren Owner-Entscheide in `docs/OWNER_DECISIONS_STUDIO_20261112.md` (zitiert als A1 bis P7).
Inhaltlich folgt sie den Empfehlungen des Optionspapiers
`docs/research/studio_abschluss_20261118/design_options.md` (Entwurf in PR #1512), angepasst an
O1 und O3. Bei Widerspruch gehen die Owner-Entscheide vor; Git, Tests und Issues sind Source Truth
für den technischen Stand (`AGENTS.md` §3).

Diese Datei ersetzt das Zieldokument `docs/STUDIO_TARGET_SCOPE.md`, das am 2026-11-18 mit PR #1510
gemergt wurde. Grundlage ist die Owner-Aussage vom 2026-11-18 auf die Frage, welcher Scope gilt:
„Bitte nach deinen neuen hier ausgemachten scope arbeiten und das so hinterlegen“, dazu „hier mein
GO für alle deinen Empfehlungen“, eingeschränkt durch „Bei Unsicherheiten nochmal mit mir zusammen
planen“ (deckt Empfehlung §D.1 des Optionspapiers: Zieldokument ersetzen; Wortlaut und genaue
Quellen in `docs/OWNER_DECISIONS_STUDIO_20261118.md`: die Scope- und Unsicherheits-Zitate stehen
wörtlich in PR #1514, Kommentar 6987989133; das GO-Zitat ist vom Lead wörtlich übermittelt, ohne
eigene Kommentar-ID). Für die dort genannte Freigabe „S-B,
O1-A bis O4-A“ gibt es keine belegte Owner-Quelle. Das Zieldokument bleibt als Verlaufsdokument
erhalten (`AGENTS.md` §9), ist aber keine Pflichtlektüre und keine Scope-Quelle mehr; die
strittigen Punkte stehen am Ende dieser Datei. `docs/STUDIO_ROADMAP_20261112.md` und
`docs/STUDIO_PLAN_SIMULATOR.md` bleiben als Planungs- und Verlaufsdokumente bestehen; wo sie dieser
Datei widersprechen, gilt diese Datei.

## Feste Regeln für alle Bereiche

- XMage ist die alleinige Regelautorität; keine Erste-, Zufalls- oder Standard-Option
  (`AGENTS.md` §2).
- Jede Zahl mit n/N und Herkunft, „unbekannt“ statt 0, Kohorten nie gemischt (A4, A5).
- Chulane ist das einzige aktive Owner-Deck (`docs/OWNER_DECK_FOCUS_CURRENT.md`).
- Keine Preise, kein Kaufmodus, keine Bezahldienste (A1, B1).
- Keine neue Abhängigkeit und keine Änderung an `pyproject.toml` ohne Owner-Go.
- Sitze: Höchstzahl 6, Standard 4. Aktiv sind 2 bis 4 Sitze; 5 und 6 sind nicht freigegeben
  (eigene Qualifikation und Owner-Freigabe, A3, A8). Die Engine nimmt 2 bis 6 Sitze an
  (Verhalten bei 5/6 nicht qualifiziert: `UNKNOWN`; `studio/launch.py`: `MIN_SEATS, MAX_SEATS = 2, 6`). Technische Sperre (neu, Empfehlung O11 mit
  Owner-GO): im Studio-Startpfad (Partie, PLAY) seit PR #1515 auf `main`
  (`MAX_RELEASED_SEATS = 4`), in den Serien-Routen und im Befehl `compare-decks` seit PR #1536
  (`compare-decks` hat den Schalter `--allow-unreleased-seats`, standardmäßig aus; setzen nur nach
  Owner-Freigabe).
  Aufgehoben wird sie nur per Owner-Freigabe.

## BUILD

| Punkt | Scope | Quelle |
|---|---|---|
| Deckbauer | Der Studio-BUILD dieses Repositorys bleibt der Deckbauer des Projekts. `deckbuild-studio` ist eine eigene Ausgründung außerhalb der PLAY/SIMULATE-Pipeline; kein Austauschvertrag, kein Einfrieren des Deckbauers hier. Der generische Text-Import `scripts/import_deck.py` bleibt, wie er ist. | E1 |
| Tierliste | Standardansicht ist der Nutzungsindex (objektiv, Schnitte 54/35/20/5). Das Kartenverständnis-Gesamtrating (#1369) ist eine wählbare, gekennzeichnete, generierte Zweitansicht; Standard erst nach der Validierung aus E6. Standard bleibt „Nutzung“; Guide v2.2 wird nicht ausgerollt; Ankerfrage 7 gilt als gewolltes Urteil; eine menschliche Referenz ist optional. | B10, E6, E7 (C6) |
| Simulation in der Tierliste | Gewicht `simulation` = 0 in Code und Test, bis G-SIM erfüllt ist und der Owner Gewicht und Darstellung bestätigt. K5: gemessene Partie-Ergebnisebenen ohne Gewicht. | B11 (bedingt), E2 |
| Offene Punkte | Folgepunkte des Gesamtratings (#1369); Validierung vor einem Standardwechsel; Datenlücken für eine objektivere Bewertung (#1261). Pausiert und owner-vorbehalten: #1210, #1187/#1176. | Issues |

## PLAY

Ziel: Der Owner spielt ganze Partien mit Chulane gegen KI-Sitze am eigenen Rechner, ohne
Zeitlimit, und es fühlt sich „möglichst wie ein fertiges Kartenspiel“ an (E5). Abnahme nach
AK-1 bis AK-8 (E4); die Abnahme-Partien werden schon nach P0 gespielt, die Reihenfolge in P1
folgt aus AK-8.

| Stufe | Inhalt |
|---|---|
| P0 | (1) Den gesicherten Brett-Klick-Stand fertigstellen: Ziel, Angreifer, Blocker, Karte aus der Hand, Fähigkeit eines Permanents; jeder Klick sendet nur eine `option_id` aus `legal_options`, die Listen bleiben als Ausweichweg (AK-4). (2) Echt-Engine-Test des Mensch-Sitzes ohne Menschen: ein vorhandener Pilot beantwortet die Entscheidungen über die PLAY-Routen; reiner Test, keine Erste- oder Zufallsoption. (3) Technische Sperre für 5 und 6 Sitze im Studio-Startpfad (Partie); die Sperre der Serien-Routen gehört zum SIMULATE-Zweig. Aufgehoben wird sie nur per Owner-Freigabe. (4) Abnahme-Partien am Owner-PC. Stand 2026-11-18: (1) bis (3) mit PR #1515 gemergt. Der Echt-Engine-Lauf dort beantwortete nur Mulligan, Priorität, Ziel und Objektwahl; Angriff, Block, Mana-Zahlung und Mulligan mit Zurücklegen gegen die laufende Engine sind `UNKNOWN` und Gegenstand von P0b (in Arbeit). (4) offen. |
| P1a (nur Seite) | Stack-Schiene mit Zielen aus dem veröffentlichten Zustand; Tastatur mit sichtbarem Fokus; Yield-Modi nur über die Pass-Option, die die Engine anbietet (jede andere Entscheidung hält an, jeder automatische Pass steht im Protokoll); Wiedergabe einer beendeten Partie Zug für Zug. Keine Bridge-Änderung. Reihenfolge aus AK-8. |
| P1b (Bridge-Gate) | Anzeige von Commander-Steuer und Commander-Schaden nur als Engine-Werte, nie auf der Seite errechnet; neuer Frame-Inhalt ist eine `BEHAVIOUR`-Änderung unter dem Studio-Bridge-Gate (`AGENTS.md` §10). Erst nach AK-8 und nach P1a-Punkten, die AK-8 vorzieht. |
| P2 | Nur auf Owner-Wunsch: serverseitiges Yield (vorher unabhängiges Review gegen `AGENTS.md` §2), Bedienung per Berührung, Mensch auf einem anderen Sitz als 1, Bildvergleichs-Tests (neue Abhängigkeit). Nicht geplant: Speichern und Wiederaufnehmen (kein Zustands-Restore der Engine, E5), freies Rückgängig (P4), Erklärung einzelner KI-Entscheidungen, passiver Gegner (P3). |

Fest aus E5: KI-Hände nach Spielende offen, während der Partie nicht ausgeliefert; kein Timeout,
der eine PLAY-Partie beendet; Vorspulen sendet nur die Pass-Option der Engine auf
Prioritätsabfragen.

## SIMULATE

Option A2 „Deck-Labor mit Messprotokoll“, geliefert in zwei Schritten.

| Schritt | Inhalt |
|---|---|
| A1 | Platz-Ausrichtung der Variante an der Basis in gepaarten Studio-Serien verdrahten (vorhandene Funktion `align_to_baseline_slots`); gepaarte Serien parallel spielen (Nachweis: jedes Spiel im Stapel hat denselben semantischen Hash wie allein gespielt); Planung mit nachweisbarer Differenz im Startdialog und im Ergebnis; zensurbewusste Zeit-Kennzahlen („erreicht in n von N“); Seed-Plan je Serie (Erkundung oder Bestätigung, fortlaufende Seeds bleiben); erster Pilotblock am Owner-PC zur Messung von Paar-Streuung, Diskordanz und Durchsatz. |
| A2 | Serienplan als Datei vor dem ersten Spiel; Zwei-Stufen-Ablauf (Erkundung, Bestätigung auf frischen Seeds mit Holm); Konsistenz-Tafel in drei getrennten Herkunftsklassen (exakt gerechnet, in der Engine gemessen und pilotunabhängig, in der Engine gemessen und pilotabhängig); Gültigkeitsblock an jedem Ergebnis (Sitzkurve neben der Playgroup-Referenz, Zählung der Pilot-Auslassungen nach E3, fester Satz zur KI-Gültigkeit). |

- **Mindeststandard:** die zwölf Punkte in `docs/OWNER_DECISIONS_STUDIO_20261118.md` (G-SIM
  Punkt 4); nach A2 je Punkt mit Test oder Beispielergebnis belegt. Punkt 11 gilt für A2 nur in
  der schwachen Form (Sitzkurve, Zählung der Pilot-Auslassungen). Eine manuelle Stichprobe von
  Pilot-Entscheidungen gehört nur zum dreiteiligen Pilot-Audit nach G-SIM Punkt 2 (vom Owner
  angenommen, E7/C1; S2 ist nur für dieses Audit aufgehoben, Schwellen Vorschlag). Voraussetzungen
  dafür: Audit-Mitschnitt im Studio-Pfad und Pilot-Fingerabdruck über die verhaltensbestimmenden
  Dateien.
- **Erste Chulane-Frage (G-SIM Punkt 5, E7/C2):** Landzahl-Achse 33 / 36 / 39 mit Negativkontrolle
  (Basis gegen Basis), Positivkontrolle (27 Länder) und exakter Gegenprobe gegen die
  hypergeometrische Verteilung; die drei Tauschkarten benennt der Owner vor dem Lauf.
- **Wo Ergebnisse erscheinen:** nur im Deckbauer (Vergleich zweier Stände) und im Deck-Verlauf,
  als eigene Kohorte `SIMULATED_RESULT`, nie in einer Spalte mit EDHREC-, Playgroup- oder
  TopDeck-Zahlen, nie über Commander oder Deck-Stände summiert. Eine Serie zu einem anderen
  Deck-Stand wird nie als Ergebnis des aktuellen Standes gezeigt.
- **Weg in die Tierliste:** in Stufen (E2, E7/C3). Stufe 0: heute, Gewicht 0, nichts aus
  Simulation auf der Tierliste. Stufe 1, nach G-SIM 1 bis 6 und Owner-Go zur Darstellung:
  getrennte Markierung ohne Gewicht und ohne Sortierung, mit Intervall, n und Aussagegrenze.
  Stufe 2: Gewicht größer 0 erst nach Hold-out- und Halbierungs-Prüfung, gedeckelt
  (`docs/OWNER_DECISIONS_STUDIO_20261118.md`). K5 und B11 gelten bis einschließlich Stufe 1.
- **Ehrliche Reichweite:** SIMULATE entscheidet Pakete und Bauachsen (Landzahl, Ramp-, Schutzpaket),
  nicht einzelne Kartentausche; die Oberfläche sagt das.
- **Später, nur bei Bedarf (A3):** rundenbegrenzte Serien mit vollen Piloten, Kontrollgrößen,
  Zufalls-Pods, Vorausschau-Piloten (S5, #1265). Rundenlimit, neue Abhängigkeiten und 5/6 Sitze
  brauchen einen Owner-Entscheid.

## Engine und Bridge

- XMage allein (`AGENTS.md` §1, §2); der Pin steht in `config/rules_engines.json`. Fork-Push und
  Repin nur mit Owner-Go.
- Änderungen unter `engine-bridge/` für das Studio laufen über das Studio-Bridge-Gate
  (`AGENTS.md` §10).
- Siegel-Stand ehrlich ausweisen: Spielprotokolle und Serienergebnisse tragen die Bridge-JAR-SHA-256,
  und `BRIDGE_AHEAD_OF_QUALIFICATION` ist sichtbar, solange `engine-bridge/` vom versiegelten Stand
  abweicht (#1401, PR #1411). Nichts auf einer späteren Bridge wird als von der versiegelten
  Epoche abgedeckt dargestellt.

## Release und Betrieb

- Release-Paket mit Bridge-JAR und eine nachvollziehbare Einrichtung am Owner-PC nach
  `docs/STUDIO_OWNER_PC_SETUP.md`.
- **Plattform:** Der Owner-PC ist Windows; Start über `scripts/studio_start.ps1`, Datenordner
  standardmäßig `%LOCALAPPDATA%\CommanderStudio` (`docs/STUDIO_OWNER_PC_SETUP.md`). Linux/WSL
  (`scripts/studio_start.sh`) ist nur Ausweichweg; ob am Owner-PC WSL vorhanden ist: `UNKNOWN`.
  Messwerkzeuge für Bridge-Gate und Serien-Identität müssen unter Windows laufen. Stand:
  `scripts/benchmark_xmage_full_games.py` und `scripts/check_studio_series_identity.py`
  importieren `resource`, das es unter Windows nicht gibt (offen, eigenes Paket).
- **Release-Paket:** das Artefakt des Workflows `.github/workflows/release-artifacts.yml` zum
  abgenommenen Commit (mit `xmage-engine-bridge.jar`, dessen `.sha256` und `ENGINE_PIN.txt`). Das
  Artefakt hält 30 Tage (`retention-days: 30`) und wird vor dem Abschluss neu erzeugt. Ein
  dauerhaftes GitHub-Release wäre eine Veröffentlichung und ist Owner-Entscheid.
- **Backup:** Der Studio-Datenordner (Deck-Verlauf, Markierungen, Serien, Partien) liegt nur auf
  dem Owner-PC. Sicherung und Rückspiel sind eine Anforderung, noch nicht gebaut (eigenes Paket).
- **Keine Telemetrie:** Das Studio sendet keine Nutzungs- oder Messdaten nach außen. Nach außen
  gehen nur Abrufe öffentlicher Kartenbilder und Kartendaten (`AGENTS.md` §12). Messwerte der
  Abnahme kommen als Dateien zurück.
- Zum Abschluss: neue Qualifikations-Epoche (Versiegeln braucht das Owner-Go) oder dauerhaft
  sichtbar „vor Qualifikation“.

## Roadmap-Phasen

Keine Kalenderdaten: Die Dauer hängt an Owner-Zeit am PC und an Nutzungslimits der Sitzungen.

| Phase | Inhalt | Abnahme |
|---|---|---|
| 0 Sichern und klären | Offene Stände gepusht; Claim-Tabelle in #1167; diese Datei und die Entscheidungsdatei | beide gemergt, Doku-Drift bereinigt |
| 1 PLAY P0 | Brett-Klick, Echt-Engine-Test, Sitz-Sperre im Startpfad (Stand 2026-11-18: gemergt mit PR #1515; P0b in Arbeit; Abnahme-Partien offen) | Tests grün auf exaktem Head, Review; drei Abnahme-Partien (AK-1 bis AK-8) |
| 2 SIMULATE A1 (parallel zu 1) | Ausrichtung, parallele gepaarte Serie, Planung, Zensur, Seed-Plan, Sitz-Sperre der Serien-Routen (Stand 2026-11-18: PR #1516 gemergt; Serien-Sitz-Sperre mit PR #1536 gemergt) | Starthand-Gleichheitstest, Hash-Nachweis Stapel gegen Einzelspiel; Pilotblock am Owner-PC |
| 3 BUILD-Klärung | Doku und Verifikation des vorhandenen Starts aus dem Deckbauer (Knopf „Mit diesem Stand eine Partie spielen“) und des Serienstarts zu einem Deck-Stand | ein Chulane-Stand geht ohne Handarbeit in Partie und Serie |
| 4 SIMULATE A2 und PLAY P1 | Serienplan, Zwei-Stufen-Ablauf, Konsistenz-Tafel, Gültigkeitsblock, Anzeige im Deck-Verlauf; P1 nach AK-8 priorisiert | zwölf Punkte des Mindeststandards belegt; eine Nachtserie zu einer echten Chulane-Frage |
| 5 Abschluss | Bridge-Siegel oder dauerhaft „vor Qualifikation“; Release-Paket; Einrichtung von null | Abschlusskriterien unten |

## Phasenplan S0 bis S6

Quelle: Gesamtplan der Lead-Sitzung (Teil D), als Verfeinerung der Roadmap-Phasen durch den Lead
nach `AGENTS.md` §8. Er legt zwei Owner-Sitzungen am PC fest, weil alles Messbare daran hängt. `UNKNOWN` ist nie PASS.

| Schritt | Phase | Inhalt | Abnahme |
|---|---|---|---|
| S0 Laufendes schließen | 0 bis 2 | PRs #1515, #1516, #1517 (gemergt); P0b; diese Onboarding-Regeln (`docs/STUDIO_AGENT_ONBOARDING.md`) | gemergt mit PASS-Kommentar auf exakter Head-SHA; Claim-Tabelle in #1167 nennt Paket, Halter und Branch |
| S1 Bereit für den Owner-PC | 1 bis 3 | Serien-Sitz-Sperre (gemergt mit PR #1536); Identitätsnachweis des parallelen gepaarten Pfads; Echt-Engine-Test des Mensch-Sitzes in CI; Messskripte unter Windows; Owner-PC-Seite aktualisiert | (1) Serien und `compare-decks` lehnen 5 und 6 Sitze ab, mit Test, der ohne die Prüfung fällt; (2) gepaart-parallel n identisch von N mit N ≥ 20 Spielen, sonst laufen gepaarte Serien mit einem Worker; (3) der Echt-Engine-Test läuft in einem CI-Job und ist dort nicht übersprungen; (4) die Messskripte starten unter Windows; (5) die Owner-PC-Seite ist einmal von null in sauberer Umgebung durchgespielt, jede Abweichung ist ein Befund |
| S2 Owner-Sitzung 1 (am PC) | 1, 2 | Einrichtung, drei Abnahme-Partien, Pilotblock | ausgefülltes Abnahme-Protokoll mit Dateien; AK-1 bis AK-8 je PASS, FAIL oder `UNKNOWN`; Pilotblock liefert Durchsatz, Diskordanz, Paar-Streuung und Sitzkurve je mit n/N |
| S3 Auswerten | 4 | P1-Reihenfolge aus AK-8; Budget-Tabelle mit gemessenem Durchsatz und gemessener Diskordanz; Schwellen des Pilot-Audits mit dem Owner kalibrieren (Owner-Zeit etwa 2 bis 2,5 Stunden; C1 bis C3 und C6 sind angenommen, E7) | Kommentar in #1167 mit den Messwerten und der P1-Liste; Owner-Antworten in einer Entscheidungsdatei |
| S4 Bauen (parallel) | 4 | SIMULATE A2; PLAY P1a, danach P1b; Backup | zwölf Punkte des Mindeststandards je mit Test oder Beispielergebnis; jeder P1-Punkt mit Test, der ohne die Änderung fällt |
| S5 Owner-Sitzung 2 (am PC) | 4 | Nachtserie zur ersten Chulane-Frage (Landzahl-Achse mit Kontrollen); Spielprobe P1; optional Pilot-Audit (spätestens bevor G-SIM Punkt 2 als erfüllt gelten soll) | Frage beantwortet mit Serienplan, Intervall, nachweisbarer Differenz und Gültigkeitsblock |
| S6 Abschluss | 5 | Epoche oder „vor Qualifikation“; Release-Paket; Tierliste-Abnahme; Pilot-Audit, falls nicht in S5 gemacht und G-SIM Punkt 2 angestrebt | Abschlusskriterien 1 bis 6 je mit Beleg; Einrichtung von null aus dem Paket |

**Abnahme-Protokoll (Gerüst; die ausfüllbare Vorlage ist ein eigenes Paket).** Jede Zeile bekommt
Wert, Herkunft (Datei oder Bildschirmfoto) und Urteil PASS, FAIL oder `UNKNOWN`.

- A Einrichtung: Betriebssystem, Kerne, Arbeitsspeicher; Java-Version; Ausgabe von
  `python -m commander_lab.studio doctor`; Herkunft der JAR (Artefakt, Commit);
  `bridge_jar_sha256`, Engine-Pin, Bridge-Zustand; Dauer und jede Stelle, an der die Anleitung
  nicht stimmte.
- B PLAY je Partie (drei): Spiel-ID, Seed, Pod, Dauer; AK-1 bis AK-8 je Zeile; AK-3 als Tabelle n
  je Entscheidungsklasse (nicht vorgekommen = `UNKNOWN`).
- C PLAY-Störfälle (einmal): Tab neu laden; Seite schließen und wieder öffnen; Aufgeben.
- D SIMULATE-Identität: n identisch von N (Hash, Sieger, Entscheidungszahl), Worker, Spiele je JVM.
- E SIMULATE-Pilotblock: Serien-ID, Deck-Hashes, Platz-Ausrichtung; Paare geplant, fertig,
  zensiert, Fehlerklassen; Wanduhr und Spiele je Stunde; Diskordanz neben dem
  Unabhängigkeitswert; Paar-Streuung; Sitzkurve je Sitz n/N neben der Referenz mit Datum.
- F Kreislauf: Chulane-Stand, Partie, Serie, Eintrag im Deck-Verlauf ohne Handarbeit (ja/nein, wo
  es hakte).
- G Rückgabe: Spielprotokolle, Serien-Dateien, `doctor`-Ausgabe; alles `SIMULATED_RESULT`, kein
  Qualifikationsbeleg.

## Abschlusskriterien

Das Projekt ist abgeschlossen, wenn:

1. PLAY: AK-1 bis AK-8 erfüllt und vom Owner bestätigt.
2. SIMULATE: Eine vom Owner gestellte Chulane-Frage ist mit Serienplan, Ergebnis, Intervall,
   nachweisbarer Differenz und Gültigkeitsblock beantwortet und im Deck-Verlauf sichtbar.
3. BUILD: Ein Deck geht ohne Handarbeit aus dem Deckbauer in Partie und Serie; die Tierliste
   (#1369) ist vom Owner abgenommen.
4. Regeln: `simulation`-Gewicht 0 durch Test gesichert, solange G-SIM nicht erfüllt und bestätigt
   ist; 5 und 6 Sitze technisch gesperrt oder vom Owner freigegeben; keine Zahl ohne n/N.
5. Doku: diese Datei, die Entscheidungsdatei und keine offenen Widersprüche in den Studio-Dokumenten.
6. Betrieb: Einrichtung am Owner-PC aus dem Release-Paket nachvollzogen; Zustand der Bridge
   gegenüber dem Siegel ehrlich ausgewiesen.

## Zuständigkeiten

Wer welche Fläche hält, steht in der Claim-Tabelle im Übersichts-Issue #1167 (Kommentar
6985613347 und Nachfolger), nicht in `AGENTS.md` oder `CLAUDE.md`. Vor einer Änderung an einer
geclaimten Fläche zuerst dort kommentieren (`AGENTS.md` §11).

## Abarbeitung (für alle Agents)

So wird der Scope oben abgearbeitet, von jedem Agenten gleich.

1. **Reihenfolge:** die Phasen 0 bis 5 aus „Roadmap-Phasen“, verfeinert durch den Phasenplan S0
   bis S6; Phase 1 (PLAY P0) und Phase 2 (SIMULATE A1) laufen parallel, weil ihre Flächen getrennt
   sind.
2. **Claims:** Die Claim-Tabelle im Übersichts-Issue #1167 ist maßgeblich. Eine Fläche hat einen
   Halter. Jeder Agent, auch Lead und Coordinator, claimt seine Arbeit vor dem Start (Owner,
   2026-11-18, E8). Ausgestaltung des Leads nach `AGENTS.md` §8 (E8): Kommentar im Issue und Zeile
   in der Claim-Tabelle von #1167 (Fläche, Branch, Stand); vorher Claim-Tabelle und offene PRs und
   Branches prüfen, damit keine Doppelarbeit entsteht; Freigabe bei Merge, Übergabe oder Abbruch.
   Bei einem Claim ohne gepushten Meilenstein darf jeder im Issue nachfragen; sind danach 24 Stunden
   ohne Antwort oder Push vergangen, verfällt der Claim und darf von anderen übernommen werden. Der
   aktive Branch eines anderen Agenten bleibt ohne Übergabe unberührt (`AGENTS.md` §11).
   Bei Überschneidung zuerst dort kommentieren, dann arbeiten. Flächen-Karte und
   Kollisionsdateien: `docs/STUDIO_AGENT_ONBOARDING.md`.
3. **Pakete:** ein Paket = ein Issue bzw. ein Branch = ein PR. Commits und PR-Texte sagen
   `Refs #N`, nie `Closes #N` (`AGENTS.md` §10).
4. **Review vor Merge:** Eine MATERIAL-Änderung braucht vor dem Merge einen Review aus frischem
   Kontext mit Ergebnis PASS, festgehalten als PR-Kommentar mit der exakten Head-SHA, die gemergt
   wird. Welche Änderung MATERIAL ist, legt die Liste in `AGENTS.md` §10 fest (unter anderem mehr
   als 300 geänderte Zeilen, Policy-Text, Workflows, Engine, Bridge, Gates, Qualifikation).
   Studio-Ergänzung zu §10 (ändert §10 nicht): Zusätzlich zur MATERIAL-Liste sind Texte der
   Oberfläche, die Aussagen über Ratings oder Simulationsergebnisse machen, review-pflichtig; eine
   solche Änderung wird wie MATERIAL behandelt. Ein Merge vor dem erforderlichen Review ist nach
   §10 ein Gate-Verstoß, soweit die Änderung unter die MATERIAL-Liste in §10 fällt. Kreuz-Review
   (E7/C7): Arbeiten zwei Agenten parallel, prüft eine Sitzung des jeweils anderen Agenten den
   MATERIAL-PR; der Autor mergt frühestens nach diesem Kommentar. Wer Development Lead ist und
   fremde PRs mergt, bleibt Owner-Sache. Anlass dieser Klarstellung sind zwei Merges vom
   2026-11-18 (#1509, #1510), bei denen Review-Befunde bzw. ein Halte-Hinweis erst nach dem Merge
   aufgelöst wurden.
5. **Governance-Dateien:** Änderungen an `AGENTS.md` und `CLAUDE.md` erfolgen durch Lead oder
   Coordinator nach `AGENTS.md` §8. Inhaltliche Änderungen am Scope (diese Datei), an den
   Owner-Entscheiden (`docs/OWNER_DECISIONS_*`) und an Owner-vorbehaltenen Regeln nur auf
   ausdrückliche Owner-Anweisung oder nach Owner-Freigabe einer vorgelegten Option; die Quelle
   steht im PR. Andere Agents legen Option und Empfehlung vor. Entscheide von Lead oder
   Coordinator innerhalb des Scopes nach `AGENTS.md` §8 bleiben unberührt und stehen im Issue oder
   PR. Bei Unsicherheit wird mit dem Owner geplant (Owner, 2026-11-18).
6. **Owner-Entscheide** werden wörtlich in `docs/OWNER_DECISIONS_STUDIO_<Datum>.md` festgehalten,
   mit Quelle; Einordnungen von Agenten sind als solche gekennzeichnet.
7. **Belege:** Was nicht belegt ist, heißt `UNKNOWN`, nie PASS. Punkte, die eine echte Engine oder
   den Owner-PC brauchen, werden als solche ausgewiesen und nicht durch Tests mit nachgebautem
   Client als erledigt gemeldet.
8. **Simulation:** Ergebnisse nur als `SIMULATED_RESULT` mit Herkunft; kein Einfluss auf die
   Tierliste, bevor G-SIM erfüllt und vom Owner bestätigt ist (E2).

Regeln für Hilfs-Agenten (keine rekursiven Teams, kurze Berichte) stehen in `CLAUDE.md`.

## Nicht übernommen aus `docs/STUDIO_TARGET_SCOPE.md`

Empfehlung der Lead-Sitzung. Falls der Owner „S-B, O1-A bis O4-A“ doch in einer anderen Sitzung
freigegeben hat, entscheidet er die strittigen Einzelpunkte unten neu; bis dahin wird aus ihnen
nichts gebaut. Übernommen sind die Teile, die mit den Owner-Entscheiden übereinstimmen (Herkunftsfelder,
`simulation`-Gewicht 0 bis G-SIM, 2 bis 4 Sitze aktiv, kein Fork-Push, parallele gepaarte Serien,
Ergebnis-Rückfluss getrennt von der Tierliste, Release-Paket mit Bridge-JAR). Nicht übernommen:

| Punkt | Grund |
|---|---|
| „Passive-AI-Goldfish-/Resistance-Modus“ | gegen P3: Die KI spielt immer mit voller Stärke. |
| Rundenlimit, „6-Turn-Goldfish“ | keine Owner-Quelle; als A3-Option mit vollen Piloten nur nach Owner-Entscheid. |
| Pilot-Fehlentscheidungsberichte | Lesart der Lead-Sitzung: fällt unter S2 (Einfrierung vom 2026-11-10); O4 hob S2 nur für die Zählung von Auslassungen auf (E3). Eine manuelle Stichprobe (G-SIM Punkt 2) braucht eine eigene Owner-Bestätigung. |
| „Resolve All“ | nur in der Form der Yield-Modi oben: ausschließlich die Pass-Option der Engine, jede andere Entscheidung hält an. |
| Multi-Commander | über den Chulane-Fokus hinaus (B2); keine Owner-Quelle. |
| Spaltenansicht im Deckbauer | keine Owner-Quelle; als BUILD-Wunsch dem Owner vorzulegen (der Deckbauer bleibt hier, E1). |
| Schlanke Bridge S4 als Meilenstein | #1264 ohne gemessenen Gewinn geparkt; nur als neuer Messversuch unter dem Studio-Bridge-Gate. |
