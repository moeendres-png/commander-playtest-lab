# Owner-Entscheide: Commander Studio, Stand 2026-11-18

**Zweck.** Diese Datei schreibt die Owner-Antworten vom 2026-11-18 zum Optionspapier
„Studio-Abschluss“ und die Owner-Entscheide vom 17.11. (PLAY) und 18.11. (Tierliste) verbindlich
fest. Sie ergänzt `docs/OWNER_DECISIONS_STUDIO_20261112.md` und
`docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md` und ersetzt dort nur die Zeilen, die
unten unter „Was aufgehoben, geändert oder neu ist“ stehen. Der Scope je Bereich, der daraus
folgte, stand in `STUDIO_SCOPE.md`; diese Datei ist seit der Owner-Antwort 8a vom 2026-11-21
archiviert, ihre weiter bindenden Regeln stehen in Abschnitt 6. Nur Governance: Code, Engine-Pin, versiegelte
Nachweise, kanonische Decks und Bestand ändern sich mit dieser Datei nicht.

**Lesart.** Jeder Punkt nennt seine Quelle. Owner-Wortlaut steht in Anführungszeichen und ist
unverändert übernommen. Was keine Owner-Aussage ist, sondern eine Einordnung der Lead-Sitzung,
ist als solche gekennzeichnet. Eine spätere Owner-Anweisung geht vor; dann wird diese Datei
fortgeschrieben. Überholter Wortlaut darf nach E10 ersetzt werden; die Git-Historie bleibt die
Quelle.

**Quellen.**
- Owner-Antworten 2026-11-18 (O1, O3, O4, O6) und „Sonst arbeite weiter nach deinen
  Empfehlungen“, festgehalten in #1167, Kommentar 6985613347.
- „Bitte nach deinen neuen hier ausgemachten scope arbeiten …“, „Bei Unsicherheiten …“ und „Und
  bitte hinterlege …“ (Owner, 2026-11-18, Session-Chat): wörtlich festgehalten in PR #1514,
  Kommentar 6987989133.
- „hier mein GO für alle deinen Empfehlungen“ (Owner, 2026-11-18, Session-Chat): wörtlich vom Lead
  übermittelt; in Kommentar 6987989133 nur sinngemäß referenziert, ohne eigene Kommentar-ID.
- Annahme der Empfehlungen C1 bis C8 (Owner, 2026-11-18, Session-Chat), wörtlich festgehalten in
  #1167, Kommentar 6991938155 (E7).
- Owner-Entscheide PLAY 2026-11-17, festgehalten in #1167, Kommentar 6953814299.
- Owner-Entscheide Tierliste 2026-11-18, festgehalten in #1369, Kommentar 6967718221.
- Optionspapier `docs/research/studio_abschluss_20261118/design_options.md` mit
  `simulate_methods.md` (Entwurf in PR #1512, Zweig `docs/studio-abschluss-optionen`; zum Zeitpunkt
  dieser Datei nicht auf `main`). Es ist keine Owner-Quelle. Seine Teile B-X1, „Deck-Snapshot v1“
  und O2 sind durch O1 verworfen. Was hier aus ihm gilt, ist unten wörtlich oder inhaltlich
  übernommen, damit diese Datei für sich allein trägt.
- Owner-Entscheide 2026-11-20 und 2026-11-21 (Abschnitt „Entscheide 2026-11-20/21“), vom
  Co-Lead festgehalten in #1167, Kommentar 7038409631 (Kreuz-Review Option 1), #1661, Kommentar
  7043554602 (5/6-Freigabe, Seed 123, F1) und #1167, Kommentar 7053750538 (alleiniger Writer,
  Kreuz-Review-Ersatz).
- Owner-Antworten vom 2026-11-21 auf die gebündelten Fragen (eingetragen als 1b, 2a, 3a, 4a, 5a,
  6a, 7a, 8a), vom Co-Lead festgehalten in #1656, Kommentar 7060377220, und gleichlautend in
  #1167, Kommentar 7060377370 (Fragen und Optionen: #1656, Kommentar 7060268350); Abschnitt
  „Entscheide 2026-11-21“ und Abschnitt 6.
- Owner-Entscheid 2026-11-21 zu Preisen für TAM (Abschnitt „Preise für TAM (2026-11-21)“): Owner-Wortlaut
  im Einleitungsabsatz von #1656, Kommentar 7062128464 (vom Co-Lead festgehalten); Punkt 3 dort ist
  die Einordnung des Co-Leads.

## 1. Owner-Wortlaut vom 2026-11-18

- **O1:** „nein das war vom prompt falsch das im Projekt bestehende BUILD ist weiterhin
  deckbauer für das projekt hier“
- **O3:** „Wenn der simulationspart perfekt funktioniert also regelkonform und die Piloten
  perfekt spielen und die Ergebnisse davon useful sind und sinnvoll dann können die Ergebnisse
  davon auch gerne in die tierlist fließen aber muss sinnvoll aufgebaut und umgesetzt sein“
- **O4:** „ja alte Entscheide und Angaben sind aufgehoben bitte arbeite nach deinen Empfehlungen
  weiter und ändere wie gesagt gerne scope und dann agents.md und claude.md“
- **O6:** „ja“ (auf die Abnahme-Definition PLAY, Frage O6 des Optionspapiers)
- „Sonst arbeite weiter nach deinen Empfehlungen“
- Auf die Frage, ob `docs/STUDIO_TARGET_SCOPE.md` (gemergt mit PR #1510) oder der neue Scope
  gilt: „Bitte nach deinen neuen hier ausgemachten scope arbeiten und das so hinterlegen“
- „hier mein GO für alle deinen Empfehlungen“
- „Bei Unsicherheiten nochmal mit mir zusammen planen sonst gerne nach deinen Empfehlungen
  arbeiten“ (schränkt das GO ein: Wo eine Empfehlung unsicher ist, wird sie mit dem Owner geplant,
  nicht allein umgesetzt.)
- „Und bitte hinterlege meine Entscheidungen und Empfehlungen in seine prs und issues die es
  betreffen damit er richtig weiter arbeitet und bitte pass agents.md bzw die entsprechenden
  dateien auch an dsmit er weiß was wie abgearbeitet wird“ (Grundlage für den Abschnitt
  „Abarbeitung (für alle Agents)“ im archivierten `STUDIO_SCOPE.md`, seit 2026-11-21 Abschnitt 6.7)

**Folge für `docs/STUDIO_TARGET_SCOPE.md`.** Verbindlich war `STUDIO_SCOPE.md` (seit 2026-11-21
archiviert, bindende Regeln in Abschnitt 6); das Ersetzen
des Zieldokuments war Empfehlung §D.1 des Optionspapiers und ist vom GO gedeckt. Für die dort
genannte Freigabe „S-B, O1-A bis O4-A“ gibt es keine belegte Owner-Quelle. Falls der Owner diese
Optionen in einer anderen Sitzung freigegeben hat, entscheidet er die strittigen Einzelpunkte
(Liste im archivierten `STUDIO_SCOPE.md`, Abschnitt „Nicht übernommen“; weiter bindend in
Abschnitt 6.8) neu; bis dahin wird aus ihnen nichts gebaut.

**Einordnung der Lead-Sitzung zu O4 (Einspruch des Owners jederzeit möglich).** „Alte Entscheide
und Angaben sind aufgehoben“ bezieht sich auf die Punkte, zu denen das Optionspapier eine
Änderung empfohlen hat. Aufgehoben oder geändert ist genau, was in Abschnitt 3 steht. Alle
anderen Owner-Entscheide gelten unverändert weiter (Abschnitt 4); die Owner-Vorbehalte
(Abschnitt 5) berührt „nach deinen Empfehlungen“ nicht.

## 2. Entscheide

### E1 (O1): BUILD bleibt hier

Der Studio-BUILD in diesem Repository bleibt der Deckbauer des Projekts. `deckbuild-studio` ist
eine eigene Ausgründung außerhalb der PLAY/SIMULATE-Pipeline dieses Repositorys; sie wird von hier
aus nicht angefasst. Ein Austauschvertrag zwischen beiden wird nicht gebaut. Der vorhandene
generische Text-Import (`scripts/import_deck.py`: eine Karte je Zeile, optional mit Anzahl) bleibt
unverändert. Er hat keine eigene Behandlung für Exporte aus `deckbuild-studio`; der dort
berichtete Zusatz „(Commander)“ im Kartennamen wird nicht entfernt.

### E2 (O3): B11 wird bedingt, Reife-Tor G-SIM

> **Überholt für Gewicht und Stufen (2026-11-20, E15 Q1):** das Gewicht `simulation` und die Stufen 0 bis 2
> sind entfernt; G-SIM wird vom Tor zum Reifegrad R0-R3. Der Text unten bleibt als Verlauf.

Simulationsergebnisse dürfen in die Tierliste fließen, aber erst, wenn das Reife-Tor G-SIM erfüllt
ist **und** der Owner das konkrete Gewicht und die Darstellung bestätigt hat. Bis dahin gilt:

- Das Gewicht `simulation` bleibt 0 in Standard und allen Voreinstellungen, in Code und Test
  (`tests/unit/test_studio_simulation_weight_zero.py`). Ein Agent hebt es nicht an.
- K5 gilt unverändert: Die gemessenen Partie-Ergebnisebenen (Tempo, Ausspielquote,
  Standfestigkeit, Sieg-Abstand, Großpod) tragen kein Gewicht, auch nicht im Gesamtrating; sie
  werden nur getrennt angezeigt.
- Ergebnisse aus SIMULATE erscheinen bis dahin nur im Deckbauer und im Deck-Verlauf als eigene
  Kohorte `SIMULATED_RESULT` (SC:91-92 und SC:251, Wortlaut in SR9, Abschnitt 6.3).

**G-SIM.** „Perfekt“ ist nicht prüfbar; G-SIM ersetzt es durch messbare Größen. Ursprünglich ein
Vorschlag der Lead-Sitzung. Punkt 2, Punkt 5 und die Stufen zur Tierliste hat der Owner am
2026-11-18 angenommen (E7, C1 bis C3); ihre Schwellen bleiben Vorschlag. Die übrigen Punkte bleiben
Vorschlag, den der Owner bei der Prüfung bestätigt oder ändert. G-SIM ist erfüllt, wenn alle
sieben Punkte belegt sind:

| # | Kriterium | Messung |
|---|---|---|
| 1 | Regelkonformität | Jedes Ergebnis weist den Bridge-Zustand aus. Freigabe nur mit einer qualifizierten, versiegelten Epoche, die den eingesetzten Stand von `engine-bridge/` abdeckt, oder mit einer ausdrücklichen Owner-Annahme „vor Qualifikation“ je Freigabe. |
| 2 | Pilotgültigkeit | Pilot-Audit, dreiteilig (vom Owner angenommen am 2026-11-18, C1: Vollzählung, 240 wertbare Entscheidungen aus 24 Partien mit Schweregraden, Goldfälle, Aussagegrenze; Einzelheiten Vorschlag der Plan-Lane (Gesamtplan und Pilot-Gültigkeitsstudie der Lead-Sitzung, nicht im Repository), nicht wörtlich im Owner-Kommentar: Annotatoren und Verblindung, die Schwellen 14/240, 2/240 und 5/120): (a) Vollzählung der Auslassungen (E3) und der vorhandenen Entscheidungszähler je Serie und Sitz, n/N; (b) geschichtete Stichprobe von mindestens 240 wertbaren Entscheidungen (mindestens zwei legale Optionen mit verschiedener Spielfolge) aus mindestens 24 Partien mit Sitzrotation, die Hälfte vom Chulane-Sitz, Schichten und Seeds vor den Partien festgelegt; Urteil mit Schweregraden, verblindet aus der Sicht des entscheidenden Sitzes durch zwei unabhängige Annotatoren, der Owner als Referenz für eine Kalibrierprobe und alle strittigen Fälle (Owner-Zeit etwa 2 bis 2,5 Stunden). Bestanden, wenn die Wilson-Obergrenze (95 %) der klaren Fehlentscheidungen höchstens 10 % beträgt (höchstens 14 von 240), die der spielentscheidenden höchstens 3 % (höchstens 2 von 240) und die des Chulane-Sitzes höchstens 10 % (höchstens 5 von 120); (c) alle spielentscheidenden Fälle eines eingefrorenen Satzes von Goldfällen werden vertretbar beantwortet. Das Ergebnis gilt für genau einen Pilot-Fingerabdruck und legt die Aussagegrenze fest (geprüfte Decktypen, ausgeschlossene Kartenrollen). Voraussetzungen: Audit-Mitschnitt im Studio-Pfad und Pilot-Fingerabdruck über die verhaltensbestimmenden Dateien. |
| 3 | Sitzbalance | Sitzrotation je Block. Die simulierte Sitzkurve steht neben der Referenz: Playgroup, Vierer-Partien, Sitz 1 bis 4 = 29,1 / 25,7 / 23,6 / 21,5 %, n = 300.240, Stand 16.11.2026, Casual, Selbstangabe, Sitz nicht randomisiert, Unentschieden ausgeschlossen. |
| 4 | Statistik | Der Mindeststandard unten (zwölf Punkte) ist erfüllt, jeder Punkt mit Test oder Beispielergebnis. |
| 5 | Nutzen | Mindestens eine vom Owner gestellte Chulane-Frage auf Paket- oder Bauachsen-Ebene ist mit vorab abgelegtem Serienplan beantwortet (vom Owner angenommen am 2026-11-18, C2). Erste Frage: Landzahl-Achse 33 / 36 / 39 Länder (Basis 36); getauscht werden je drei Karten, die der Owner vor dem Lauf benennt. Der Plan enthält die erwartete Richtung, eine Negativkontrolle (Basis gegen Basis), eine Positivkontrolle (absichtlich verschlechterte Liste, 27 Länder) und eine exakte Gegenprobe (zuerst ausgeteilte Hand gegen die hypergeometrische Verteilung). Erfüllt, wenn beide Kontrollen und die Gegenprobe bestehen, das Ergebnis Intervall, nachweisbare Differenz und Aussagegrenze nennt und der Owner es danach als sinnvoll bestätigt. „Kein nachweisbarer Unterschied“ ist ein gültiges Ergebnis. |
| 6 | Kohorte | Eigene Kohorte `SIMULATED_RESULT`, nie mit Nutzungs- oder Turnierdaten addiert; eigene Achse mit eigener Konfidenz. |
| 7 | Owner | Der Owner bestätigt Gewicht und Darstellung, nach den Stufen unten. |

**Lesart zu Punkt 2.** Die Stichprobe begrenzt die Quote klarer Fehlentscheidungen nach oben; sie
belegt weder Spielstärke gegen Menschen noch menschenähnliches Spiel. Eine auffällige
Entscheidungsklasse schließt die zugehörigen Kartenrollen von Simulationsaussagen aus, statt das
Tor insgesamt scheitern zu lassen. Die Schwellen sind Setzungen; ein Vergleichswert für menschliche
Spieler ist nicht belegt.

**Stufen zur Tierliste (vom Owner angenommen am 2026-11-18, C3; die Prüfungen vor Stufe 2 sind Einzelheiten Vorschlag der Plan-Lane (Gesamtplan und Pilot-Gültigkeitsstudie der Lead-Sitzung, nicht im Repository), nicht wörtlich im Owner-Kommentar).** Stufe 0: wie heute, Gewicht 0.
Stufe 1, nach G-SIM 1 bis 6 und Owner-Go zur Darstellung: getrennte Markierung an Karten eines
bestätigten Paket-Ergebnisses, ohne Gewicht, ohne Sortierung, mit Intervall, n und Aussagegrenze.
Stufe 2, Gewicht größer 0: erst nach einer Hold-out-Prüfung (ein vorab benanntes Außenkriterium
wird mit dem Simulationsbeitrag nicht schlechter vorhergesagt als ohne), einer Halbierungs-Prüfung
über unabhängige Seed-Hälften, stabilem Vorzeichen unter zwei weiteren Pilot-Stilen und einem
Pilot-Audit mit Obergrenze höchstens 5 % (Schwelle Vorschlag); der Beitrag ist gedeckelt und gilt
nur für Karten mit gemessenem Effekt. K5 und B11 gelten bis einschließlich Stufe 1 unverändert.

**Mindeststandard für SIMULATE-Ergebnisse (G-SIM Punkt 4).** Nach `simulate_methods.md` §5 des
Optionspapiers, mit den vier unten markierten Anpassungen (a bis d):

1. Einheit ist der Seed-Block: Zahlen, Intervalle, Bootstrap und Stopp-Regel zählen je Block.
2. Jede Zahl mit n/N und Herkunft; „unbekannt“ statt 0; Timeouts, Unentschieden, Abstürze und
   Abbrüche als eigene Klassen, nie gestrichen und nie als Niederlage.
3. Anteile mit Wilson- oder Jeffreys-Intervall, nie Wald.
4. Deckvergleiche gepaart auf Blockebene, mit Tabelle der diskordanten Blöcke (Anpassung c).
5. Gemeinsame Seeds nur mit Platz-Ausrichtung der Bibliothek und gemessener Wirkung (Diskordanz
   gegen den Unabhängigkeitswert).
6. Stichprobenplanung vorab; das Ergebnis nennt die nachweisbare Differenz („kein nachweisbarer
   Unterschied bei n = …; nachweisbar wären mindestens x Prozentpunkte“), nie „Karte ist egal“.
7. Balancierte Sitzrotation, Sitz als eigener Faktor, Sitzkurve im Ergebnis.
8. Mehrfachvergleiche: Familie vorab festlegen, Bestätigung mit Holm, Erkundung und Bestätigung
   auf verschiedenen Seeds.
9. Stopp-Regel vorab festgelegt (feste Blockzahl oder Fehlerniveau-Verteilung), kein freies
   Nachsehen.
10. Nicht-Gewinn-Kennzahlen exakt gerechnet, wo möglich; Zeit bis Ereignis mit „nicht erreicht“
    als eigene Klasse (n/N).
11. KI-Gültigkeit als Aussagegrenze: „gilt für diese Piloten, diese Pods, diese Engine-Version“,
    mit Sitzkurven-Prüfung und Zählung der Pilot-Auslassungen (Anpassung d).
12. Herkunftsfelder je Ergebnis: Seeds bzw. Block-IDs, Sitzplan, Pods, Engine-Commit,
    Bridge-JAR-SHA-256 und Bridge-Zustand, Piloten, Deck-Hashes, Zweck der Serie (Anpassungen a, b).

*Anpassung a:* Der Satz in Punkt 12 der Quelle, Ergebnisse flössen nie in die Tierliste, ist
durch O3 ersetzt: nur über G-SIM und die Owner-Bestätigung. *Anpassung b:* Die Empfehlung der
Quelle zu einem hochentropischen Root-Seed ohne Seed-Arithmetik wird nicht wörtlich umgesetzt.
Der Startspieler ist `seed % Spielerzahl` (`src/commander_lab/engine/rules/full_game.py`);
fortlaufende Seeds balancieren die Zugreihenfolge und bleiben. *Anpassung c:* Statt der
Newcombe-Methode 10 oder eines gepaarten Block-Bootstraps genügt das im Repository schon
qualifizierte cluster-robuste t-Intervall je Seed (Optionspapier §A.1); es wird nicht doppelt
gebaut. *Anpassung d:* Die Quelle verlangt in Punkt 11 eine Pilot-Fehlerquote aus manueller
Stichprobe. Für A2 gilt Punkt 11 nur in der schwachen Form (Sitzkurve, Zählung der
Auslassungen); die manuelle Stichprobe gehört nur zum Pilot-Audit nach G-SIM Punkt 2.

### E3 (O4): Pilot-Auslassungen dürfen gezählt werden

Das Zählen von Pilot-Auslassungen ist zulässig: wie oft die Engine eine Option anbot (etwa Land
spielen, Commander wirken) und der Pilot sie bis Zug T nicht nahm, als Zählung n/N aus dem
Protokoll. Die Einfrierung neuer Pilot-Mikro-Messreihen (S2, 2026-11-10) ist nur dafür
aufgehoben: reine Zählung aus vorhandenen Protokollen, keine Bewertung einzelner Entscheidungen
als Produkt, keine Änderung an einem Piloten. Ergänzung (E7, C1): Für den Pilot-Audit nach G-SIM
Punkt 2 ist S2 zusätzlich aufgehoben, nur für dieses Audit: Die Bewertung einzelner Entscheidungen
ist dort als Prüfwerkzeug zulässig, nicht als Produkt, ohne Anzeige außerhalb des Prüfberichts
und ohne Änderung an einem Piloten aus dem Audit heraus ohne eigenen gepaarten Nachweis.

### E4 (O6): Abnahme-Definition PLAY

Angenommen ist die Abnahme-Definition AK-1 bis AK-8 (Optionspapier §C.2). Sie schärft den Satz aus
`STUDIO_ROADMAP_20261112.md` (seit 2026-11-21 archiviert): Der Owner spielt eine ganze Partie mit
Chulane gegen drei KI-Sitze am eigenen Rechner ohne Zeitlimit.

| # | Kriterium | Messung |
|---|---|---|
| AK-1 | Drei vollständige Vierer-Partien Chulane gegen drei KI am Owner-PC, jede bis zum von der Engine gemeldeten Spielende | drei Spielprotokolle mit Spiel-ID, JAR-SHA-256, Bridge-Zustand |
| AK-2 | Kein Hänger: keine offene Entscheidung, die die Seite nicht beantworten kann; kein Neustart, keine Entwicklerkonsole | Zählung 0 über die drei Partien; jeder Hänger ist ein Befund mit Protokollstelle |
| AK-3 | Abdeckung der Entscheidungsklassen: wie oft ein Mensch jede der 17 Klassen in echten Partien beantwortet hat | Tabelle n je Klasse aus den Protokollen; nicht vorgekommene Klassen stehen als `UNKNOWN`, nicht als bestanden |
| AK-4 | Brett-Klick für Ziel, Angreifer, Blocker, Karte aus der Hand, Fähigkeit eines Permanents; die Listen bleiben als Ausweichweg | Test: jeder Klick sendet nur eine `option_id` aus `legal_options` |
| AK-5 | Verdeckte Information: keine Handkarte eines KI-Sitzes in irgendeiner Antwort während der Partie; nach Spielende offen | vorhandener Test bleibt grün; Sichtprüfung nach Spielende |
| AK-6 | Tempo: Zahl der Entscheidungen, die der Mensch je Partie treffen musste, mit und ohne Vorspulen; Wartezeit zwischen zwei eigenen Entscheidungen (Median) | aus dem Protokoll; Zielwerte erst nach der ersten Messung festlegen |
| AK-7 | Banner „Brücke vor Qualifikation“ sichtbar; nichts als versiegelt abgedeckt dargestellt | Sichtprüfung |
| AK-8 | Urteil des Owners in einem Satz je Partie: was hat gestört | Kommentar im Issue |

### E5: Entscheide vom 2026-11-17 (PLAY), Wortlaut

Vom Owner am 2026-11-18 mit der Anweisung, nach den Empfehlungen weiterzuarbeiten („Sonst
arbeite weiter nach deinen Empfehlungen“, „hier mein GO für alle deinen Empfehlungen“), angenommen
(Empfehlung O5 des Optionspapiers: bestätigen und aufnehmen); Einspruch jederzeit möglich. Wortlaut aus #1167,
Kommentar 6953814299:

1. Nach der Partie aufdecken ist gewollt (KI-Hände nach Spielende sichtbar; während der Partie
   weiter verborgen).
2. Timeout, der das Spiel beendet: „Nein, nicht bei Play“ (Mensch wartet unbegrenzt).
3. Auto-Pass darf bleiben; „brauch irgendwas, was das Spiel schneller spielen lässt, bis ich
   wieder dran bin“.
4. Speichern/Wiederaufnehmen: „wenn sinnvoll, wenn nicht, nicht“.
5. Ziele/Angriffe/Blocks sollen anklickbar sein; es soll sich „möglichst wie ein fertiges
   Kartenspiel anfühlen“.
6. „Stufe zeigen“ bleibt standardmäßig an und das Wort „Urteil“ im Diff-Vorfilter entfällt
   (Empfehlung angenommen).

**Einordnung der Lead-Sitzung (17.11.).** Vorspulen sendet ausschließlich die Pass-Option, die die
Engine auf eine Prioritätsabfrage selbst angeboten hat, und hält bei jeder anderen Entscheidung
(`docs/STUDIO_GAME_VIEWER.md`). Speichern und Wiederaufnehmen wird nicht gebaut: Die Engine hat
keinen Zustands-Restore, die Partie läge nur im Arbeitsspeicher.

### E6: Entscheide vom 2026-11-18 (Tierliste, Kartenverständnis), Wortlaut

Vom Owner am 2026-11-18 mit der Anweisung, nach den Empfehlungen weiterzuarbeiten, angenommen
(Empfehlung O5 des Optionspapiers, Zitate wie in E5); Einspruch jederzeit möglich. Wortlaut aus #1369, Kommentar 6967718221:

- Auf die Empfehlungen K1–K7 aus `docs/research/TIERLISTE_ZWEITER_INDEX_PLAN_20261118.md`: „Sonst
  deine Empfehlungen umsetzen“ — mit der folgenden Änderung zu K4/K2:
- „nur einfach Text der Karte ablesen reicht nicht aus, du musst schon auch genau dahinter
  verstehen was es bei jeder Karte wirklich impliziert oder bedeutet und man muss immer Mana Value
  und Kosten und Synergie und so mit einbeziehen“
- „ein Gesamtrating wär trotzdem irgendwie auch cool auch wenn ich deine Einzelwertung unbedingt
  auch haben will und die Tierlist-Ansicht am besten mainly dann darauf basieren soll“
- „Am coolsten wäre wenn dieses Ranking auch eben möglichst Fakten- und Daten-basiert ist
  natürlich, aber dein dabei erzeugtes Kartenverständnis, das wir dann aufbauen, auch einfließen
  soll bzw. auch in sinnvollen Punkten Daten-basiert ist; … statt Ranking S bis F einen
  Zahlenscore … für das, was wir aufbauen wollen mit den Rubriken, und die zweite
  Gesamtbewertung der Karten (neben dem aktuellen Rating)“

**Einordnung der Lead-Sitzung (18.11.).** Für das neue, zweite Gesamtrating sind drei frühere
Festlegungen aufgehoben: die Empfehlung K4 „keine Kombination“, die frühere Ablehnung einer
modellgestützten „Eigenen Einschätzung“ und E1.a „Rubrik-Gewicht 0“ (nur für das neue Rating).
Unverändert bleiben der bestehende Nutzungsindex mit seinen Gewichten und den Schnitten
54/35/20/5, B11 (jetzt bedingt nach E2) und K5. Das neue Rating steht zunächst wählbar neben dem
Nutzungsindex; Standard wird es erst nach Validierung (Bracket-5-Hold-out nicht schlechter als
Nutzung, Trennschärfe auf Karten mit wenig Nutzung, Stabilität unter Gewichtsvarianten, Top und
Bottom 30 mit Begründungen vom Owner gesehen).

**Verhältnis zu „nur objektive Daten“ (A4, B4).** Das Gesamtrating ist eine ausdrücklich
gekennzeichnete, generierte Zweitansicht: Es enthält ein Modellurteil, einen Lauf je Karte, und
ist nicht validiert. Der Nutzungsindex bleibt der objektive Standard der Tierliste. Die Ausnahme
von „nur objektive Daten“ gilt nur für dieses gekennzeichnete Rating, für keine andere Ansicht und
keinen anderen Wert.

### E7: Annahme der Empfehlungen C1 bis C8 (2026-11-18)

Owner, 2026-11-18 (Session-Chat, wörtlich festgehalten in #1167, Kommentar 6991938155): „Ja zu
deinem Empfehlungen bitte so in den issues hinterlegen damit gemini das auch richtig abarbeitet“
(gemeint: die Empfehlungen C1 bis C8 des Gesamtplans der Lead-Sitzung). Angenommen:

- **C1** G-SIM Punkt 2 dreiteilig (Tabelle oben), mit Aufhebung von S2 nur für dieses Audit (E3);
  Schwellen bleiben Vorschlag.
- **C2** Erste Frage für G-SIM Punkt 5: Landzahl-Achse 33 / 36 / 39 mit Negativ- und
  Positivkontrolle und exakter Gegenprobe.
- **C3** Stufen 0 / 1 / 2 zur Tierliste (oben); K5 und B11 bis einschließlich Stufe 1.
- **C4** PLAY P1 geteilt in P1a (nur Seite) und P1b (neuer Frame-Inhalt unter dem
  Studio-Bridge-Gate) (Abschnitt 6.2).
- **C5** Betrieb: Owner-PC Windows, Release-Artefakt, Backup, keine Telemetrie nach außen
  (Wortlaut SR39 in Abschnitt 6.5).
- **C6** Tierliste: Standard bleibt „Nutzung“; Guide v2.2 wird nicht ausgerollt; Ankerfrage 7 gilt
  als gewolltes Urteil; eine menschliche Referenz ist optional.
- **C7** Kreuz-Review: Arbeiten zwei Agenten parallel, wird ein MATERIAL-PR von einer Sitzung des
  jeweils anderen Agenten geprüft; der Review-Kommentar nennt die prüfende Sitzung neutral, die
  Head-SHA, die Befehle und das Urteil; der Autor mergt frühestens danach (`AGENTS.md` §10). Wer
  Development Lead ist und fremde PRs mergt, bleibt Owner-Sache und ist damit nicht geregelt.
- **C8** `docs/research/studio_abschluss_20261118/ist_lage_dbs.md` prüfen, gegebenenfalls kürzen. Sichtbarkeit
  und #1108 bleiben Owner-Sache, ohne Empfehlung.

Die Einschränkung „Bei Unsicherheiten nochmal mit mir zusammen planen“ (Abschnitt 1) gilt weiter.

### E8: Claims für alle Agenten (2026-11-18)

Owner, 2026-11-18 (Session-Chat, wörtlich festgehalten in #1167, Kommentar 6992745252): „claime du
auch bitte immer deine Arbeit wie die anderen Agenten und schreib das vielleicht als Dauerregel ins
agents.md damit es zu keiner doppelarbeit kommt“. Umgesetzt als Dauerregel in `AGENTS.md` §11
(„Claims“); die Einzelheiten (Prüfung vor dem Start, Freigabe, Verfall 24 Stunden nach einer
unbeantworteten Rückfrage bei einem Claim ohne gepushten Meilenstein, Übernahme danach) sind
Ausgestaltung des Leads nach `AGENTS.md` §8.

### E9 (E-1a): Studio-Serien, Ergebnis auf bestätigtem `shutdown_game` (2026-11-19, #1612)

Owner, 2026-11-19 (Session-Chat, festgehalten in #1612): „E-1a ok.“ Für Studio-Serien ruht das
Partie-Ergebnis auf dem bestätigten `shutdown_game` je Partie, in einem **eigenen Ergebnistyp**
(D-2 P2). Auflagen aus dem Evidenz-Review: kein Subtyp von `FullGameConformanceResult`; die
Bestätigung (Ack) wird fail-closed gelesen; Hash-Identität auf dem Referenzsatz, auch über
Look-Fenster-Grenzen; Budget höchstens 56 Partien je JVM bis zur Neumessung;
`bridge_jar_sha256` und `BRIDGE_AHEAD_OF_QUALIFICATION` bleiben sichtbar. D-2 P2 bis P5 dürfen
gebaut werden; P2 und D-3 berühren beide `full_game.py`, die Reihenfolge wird im Claim
abgestimmt. Der Satz der Owner-Entscheidung vom 2026-10-15 (jedes Ergebnis ruhe auf dem sauberen
Herunterfahren des Prozesses) gilt damit nur für `run_batch` und die Konformanz-Evidenz, nicht für
Studio-`SIMULATED_RESULT`
(`docs/owner_decision_20261015_batch_games_per_jvm/OWNER_DECISION_BATCH_GAMES_PER_JVM.md`).
Batched Ergebnisse bleiben Messungen, keine Qualifikationsbeweise.

### E10: Alte Owner-Entscheidungen dürfen überarbeitet werden (2026-11-19)

Owner, 2026-11-19 (Session-Chat, festgehalten in #1612): „Merke dir allgemein dass du alte owner
Entscheidungen gerne erstmal entfernen kannst und komplett auch überarbeiten“. Folge: Alte
Owner-Entscheidungen (Entscheid-Dokumente wie `docs/OWNER_DECISIONS_*` und `docs/owner_decision_*`,
ältere Festlegungen in Issues und Docs) dürfen vom Lead und vom Co-Lead zuerst entfernt oder
vollständig überarbeitet werden, wenn sie dem aktuellen Scope oder neuen Entscheiden im Weg stehen
oder veraltet sind. Vorgehen: Der überholte Wortlaut wird nicht still gelöscht, sondern im PR mit
Begründung, Datum und Verweis auf diesen Entscheid ersetzt oder entfernt; die Git-Historie bleibt
die Quelle. Die Owner-Vorbehalte in `AGENTS.md` §8 (Fork-Push und Repin, Siegel, `qualification/`
und WS17, 5 und 6 Sitze, Sichtbarkeit und #1108, Bezahldienste, Kollektionstrennung) bleiben
bestehen, solange der Owner sie nicht ausdrücklich nennt.

### E11: Go D, Brownfield-Bewertung (2026-11-19, #1612)

Owner, 2026-11-19 (Session-Chat, festgehalten in #1612): „Und ja Go D“. Gemeint ist die
Brownfield-Bewertung (Option D: kein Neubau, Härten plus drei Ersatz-Nähte D-1 bis D-3). Die
Entscheide des Co-Leads zu den fünf Punkten der Bewertung stehen in #1612; sie sind durch das Go
gedeckt. Fork-Push, Repin, Siegel, `qualification/` und WS17 bleiben Owner-Vorbehalt (Abschnitt 5).

### E12: MTGJSON-Guard, Option A (2026-11-19, #1553)

Owner, 2026-11-19 (Session-Chat, festgehalten in #1553): „Option A. Aber spiele sowieso lieber auf
englisch“. Der MTGJSON-Guard (`tests/unit/test_studio_mtgjson_guard.py`) wird um genau eine Datei
erweitert (`studio/german_names.py`), mit Begründung und Verweis auf diesen Entscheid im Test.
MTGJSON-Druckdaten sind damit als Quelle für deutsche Namen freigegeben: nur diese Datei, nur
Namen, keine Preise, keine anderen Produktionspfade. Der Negativtest des Guards bleibt
unverändert. Anzeige bleibt der Oracle-Name; deutsche Namen dienen nur Suche und Import-Auflösung.
Die Rechte an den MTGJSON-Kartendaten sind laut `docs/research/OPEN_SOURCE_LANES_20261117.md`
ungeklärt; die Freigabe ist die ausdrückliche Owner-Entscheidung dazu.

### E13: Effizienz-Lane #1558, Freigaben (2026-11-18/19)

Owner, 2026-11-18 (Session-Chat, festgehalten in #1558): „Hier mein Go für deine Empfehlungen“
(gedeckt: #1568, #1560, #1573, #1569, #1562, #1563, #1564, #1566, #1567, #1572) und „Go #1570
#1571 #1574“. Für #1570, #1571 und #1574 galten die Auflagen: Pflicht-Check-Namen (`quality`,
`security`, `infrastructure`), Bedeutung und Strenge unverändert; kein Test gestrichen oder
geschwächt; MATERIAL-Review durch einen anderen Agenten auf exakter Head-SHA; die
`WS17_SHA256SUMS`-Digestzeile nur innerhalb einer Änderung an
`.github/workflows/production-qualification.yml` regenerieren. Nicht gedeckt blieben neue
Python-Abhängigkeiten, `pyproject.toml`, Siegel/`qualification/` und das Branch-Ruleset.
Stand 2026-11-19: #1570 und #1571 sind umgesetzt (geschlossen). #1574 ist nicht umgesetzt
(geschlossen als `not_planned`): Eine Messung (n = 20) ergab, dass Teilen nach Einzeltests die
Laufzeit höchstens um 1 bis 10 s senkt, bei neuer MATERIAL-Läuferlogik; die Prämisse des Issues
traf nicht zu (Entscheid des Co-Leads in #1574). Die Freigabe ist damit nicht verbraucht, aber
auch nicht Auftrag, etwas anderes in `production-qualification.yml` zu ändern.

### E14: TAM in Studio BUILD und Zukauf-Modus ohne Preise (2026-11-19, #1187, #1636)

Owner, 2026-11-19 (Session-Chat, Wortlaut in #1187, Kommentar 7018395774). Zu TAM im Builder:
„TAM Commander Studio (zweiter Commander, Google Drive) das soll später noch in den BUILDER part
… da sind zukäufe als feature schon erlaubt“. Zu Zukauf und Preisen: „1. ja erstmal ohne Preis,
aber für später: am besten sollen bei den zukäufen auch die preisdaten angezeigt werden (…
günstigste angebot eines deutschen anbieters auf cardmarket in mind Zustand Excellent …)“. Zum
381-Korpus: „2. Ja, getrennt nach Kohorte“. Zum Start: „3. bitte kümmer dich jetzt darum …“.

Folge: Ein Zukauf-Modus im BUILD ist als Feature erlaubt, zunächst ohne Preise. TAM ist ein
zweiter Commander im BUILD. Plan (Unter-Issues von #1187):

- **T1 (Datenbasis und Import):** idempotenter, SHA-256-geprüfter Import von `TAM_91`
  (`tam:active_91`), `TAM_CHANDRA_381` getrennt nach Kohorte (`tam:curated_b2_4`,
  `tam:curated_unbracketed`) und EDHREC-78-Ansichten (`OBSERVED_THEME`); `spellbook_shells.py`
  auf beliebige Commander und Identitäten verallgemeinert. Keine Rohdecks im öffentlichen
  Repository.
- **T2 (BUILD Zukauf-Modus ohne Preise):** Opt-in `include_unowned` im Deckbauer-Pool, Kennzeichnung
  `Im Besitz (n)` gegenüber `Fehlt / Zukauf (0)`, Deck-Aufteilung, Export `Zukauf-Liste` (nur
  Kartennamen und Anzahl), wörtliche Oracle-/Tagger-Schnellfilter für TAM-Superfriends.
- **T3 (später, `needs:owner`):** Preisdaten für Zukäufe (günstigstes Angebot eines deutschen
  Anbieters auf Cardmarket, mindestens Zustand Excellent, Minimum aus Foil und Non-Foil) erst nach
  rechtlicher und technischer Klärung des API-Zugangs; kein Scraping. Für TAM überholt durch
  „Preise für TAM (2026-11-21)“: Preisanzeige für den TAM-Zukauf ist freigegeben (#1637); die
  Klärung des Cardmarket-Zugangs bleibt Teil von #1637.

Grenzen: Chulane bleibt Fokus und Standard („nur Sammlung“, `include_unowned` aus). Die
Kollektionstrennung bleibt: Zukauf-Karten sind ein Merkmal im Deck, keine Änderung der Sammlung.
Preise, Preisdaten und Kaufabwicklung bleiben Owner-vorbehalten (`AGENTS.md` §8), außer
Preisanzeige für den TAM-Zukauf (2026-11-21, „Preise für TAM“; Kaufabwicklung bleibt vorbehalten). Kohorten werden
nie gemischt; Chulane-Daten bleiben von TAM-Daten strikt getrennt (`commander_binding`).
Überholt (E10, 2026-11-19): „kein Kaufmodus“ (B1) und „Multi-Commander über den Chulane-Fokus
hinaus“ (B2) gelten für BUILD nicht mehr in dieser Form.

### E15: Charta v2 (Brownfield 2), Q1 bis Q11 (2026-11-20)

Owner, 2026-11-20 (Session-Chat, Wortlaut festgehalten in #1612, Kommentar 7031156076): „Go Q1–Q11“,
auf die Vorlage `docs/STUDIO_CHARTA_V2.md` §5 (Empfehlung jeweils: ja; Abweichungen hat der Owner
nicht genannt). **Der Go gilt nur für Q1 bis Q11 (§5 der Charta).** Der Paketplan (§4 der Charta)
ist die Planung des Co-Lead im Rahmen von `AGENTS.md` §8 und seiner Entscheidungsbefugnis, kein
Owner-Entscheid; Owner-Vorbehalte (Abschnitt 5 dieser Datei, `AGENTS.md` §8) bleiben unberührt.

- **Q1 Entfernen:** Gesamtrating v1, Rubrik-v1-Signale, Rating-Layers, Turnier-Conversion und die
  zweite S–D-Skala fallen weg; das Gewicht `simulation` verlässt den Tierlisten-Index und Stufe 2;
  Simulation erscheint als Evidenz mit Reifegrad R0–R3 im Deckbauer; Rubrik v2 bleibt als
  „Kartenverständnis (Modellurteil)“ nur für Chulane. Ändert E6, O3/E2/B11 (G-SIM wird vom Tor zum
  Reifegrad). Umsetzung in eigenen Paketen mit Review, nicht in einem Zug.
- **Q2 Vorschläge:** Der Builder darf Vorschläge machen (Klasse VORSCHLAG, getrennt von den
  Zahlen); der Klick „Übernehmen“ gilt als Owner-Entscheid zur Chulane-Basis. Ändert A4.
- **Q3 TAM:** Standardkohorte `tam:active_91` (daneben `tam:curated_b2_4`, nie addiert);
  Datensammlung für TAM gezielt fortsetzen, für Chulane zurückstellen; TAM-Simulation erst nach
  Zählung der Sim-Bereitschaft je Kohorte (Angleichung von `STUDIO_SCOPE.md` mit E14 erledigt).
  Anmerkung (8a): Der Pfad `docs/STUDIO_SCOPE.md:31-32`/`:270` in Charta §5 Q3 liegt seit
  2026-11-21 im Archiv (Thema `superseded`, `docs/README.md`, Abschnitt „Archive“). Mit `:270` ist die Zeile
  „Multi-Commander“ gemeint; bei Abfassung der Charta (`bc0c1e7e`) war sie Zeile 270, am
  archivierten Stand (`aef76b8e`) ist sie Zeile 272. Der Owner-Text der Charta bleibt unverändert.
- **Q4 Experimente:** eine Nacht je Frage (5.400 Partien); rundenbegrenzte Frühphasen-Serie (L1) als
  eigener Experiment-Typ nach einem Messversuch.
- **Q5 Sitze:** Qualifikation 5/6 jetzt (die acht Prüfpunkte aus `docs/research/SEATS_5_6_QUALIFICATION_PLAN.md` §2, in der Charta „F1–F8“ genannt; der Teil-A-Bericht `docs/analysis-reports/seats_5_6_part_a_report.md` §1 nummeriert anders: dort ist F1 die Festlegung `ALL`/`MULTIPLE`/6 ohne Replay-Anspruch und F5 die acht Regelpunkte aus Plan §2, so auch im Abschnitt „Entscheide 2026-11-20/21“);
  **die Freigabe selbst bleibt eine eigene Owner-Entscheidung nach dem Nachweis** (`AGENTS.md` §8)
  und gilt dann für SIMULATE und PLAY (eingeschränkt durch Option A vom 2026-11-20: PLAY 5/6 bleibt
  getrennt, Abschnitt „Entscheide 2026-11-20/21“ Nr. 1). **Die technische Sperre (`launch.MAX_RELEASED_SEATS = 4`, §3) und
  „aktiv sind 2 bis 4 Sitze“ (§4) bleiben bis zur Owner-Freigabe unverändert;** „PLAY bis dahin ‚nicht
  qualifiziert‘ sichtbar“ heißt nur: die Oberfläche weist darauf hin, dass 5/6 noch nicht freigegeben
  sind, sie macht 5/6 nicht spielbar. 7/8 zurückgestellt bis zur 6er-Messung.
  **[Stand vor E16: überholt durch das bedingte Go vom 2026-11-22, siehe E16; Sperre und „2 bis 4 Sitze“ gelten nur noch bis zur Wirkung von E16, 7/8 s. E16 Nr. 4.]**
- **Q6 Gegner:** beliebige Studio-Deck-Stände als Gegner-Sitze (Chulane bleibt das einzige
  optimierte Deck); Korpus-Gegner in PLAY v1 später.
- **Q7 PLAY:** Zahlungs-Vorschlag aus dem Piloten-Planer, vom Menschen ausgelöst, nur angebotene
  Optionen, im Protokoll markiert (Auslegung `AGENTS.md` §2: der Mensch entscheidet, XMage bietet
  an; Wortlaut im PLAY-Paket mit Frischkontext-Review nach §8: der Vorschlag ist beim Öffnen einer
  Entscheidung nicht vorbelegt, der Planer sieht nur, was der menschliche Sitz sieht (§5), die Seite
  sendet nur eine `option_id` aus `legal_options`, vom Piloten vorgeschlagene Zahlungen werden
  markiert und in der Mensch-Kohorte nicht als menschliche Entscheidung gezählt); Speichern/Fortsetzen zurückgestellt; der Owner spielt vor
  dem Bedienungs-Paket eine ganze Partie.
- **Q8 Piloten:** Vorausschau (S5) nicht als Serien-Pilot; Pilot-Änderungen nur mit gepaartem
  Nachweis; Pilot-Audit nach der ersten Nachtserie.
- **Q9 Daten:** Schema 22 als Dateischnitt (drei Dateien: `reference`, `studio`, `simulate`) mit
  Migration über die Export-Datei des Nutzerzustands (Sicherung, am echten Zustand vorab bewiesen,
  keine eigene Owner-Sitzung); Decks dürfen Karten ohne Besitz enthalten (TAM-Zukauf, Besitz als
  Merkmal; Preise bleiben Owner-Vorbehalt außer TAM-Zukauf (2026-11-21, „Preise für TAM“); Chulane bleibt Standard „nur Sammlung“, `include_unowned` aus, E14). Die
  Export-Datei mit dem echten Nutzerzustand gehört nicht ins öffentliche Repository und nicht in die CI
  (`AGENTS.md` §12).
- **Q10 Governance:** MATERIAL teilt sich in Inhalt (Klasse A: Kreuz-Review) und bloße Größe
  (Klasse B); „Studio-Daten-Gate“ für Schema-Änderungen; die Charta mit Entscheid-Register ersetzt
  die Pflichtlektüre. Ändert E7/C7; **bis zu diesem Governance-PR gelten `AGENTS.md` §1 (inklusive Gesamtrating-/G-SIM-Aussagen) und §10
  unverändert**: jeder MATERIAL-PR braucht weiter ein Frischkontext-Review (bei zwei parallel
  arbeitenden Agenten zusätzlich ein Kreuz-Review); ob Klasse B das Frischkontext-Review behält, legt
  der Governance-PR fest. Auch die Texte zu Q1 (Gesamtrating, Gewicht `simulation`) ändern sich in
  `AGENTS.md` §1 erst mit dem jeweiligen Paket. **Umgesetzt (Doku-Wahrheits-Pass, Refs #1667):** `AGENTS.md` §1 (Q1 nach #1684/#1686/#1691/#1696) und §10 (Klassen A/B; die Klasse B behält das Frischkontext-Review und verliert nur das Kreuz-Review); die Lesereihenfolge (zuerst Charta v2 und dieses Register, damals blieb `STUDIO_SCOPE.md` der verbindliche Scope; seit 8a sind Charta v2 und Register die Pflichtlektüre) ist mit dem Governance-PR zu den Entscheiden 2026-11-20/21 in `AGENTS.md` §1, `CLAUDE.md` und `docs/STUDIO_AGENT_ONBOARDING.md` nachgezogen (Refs #1667); die Archivierung alter Pflichtlektüre-Dateien ist mit der Owner-Antwort 8a vom 2026-11-21 erledigt (Abschnitt „Entscheide 2026-11-21“, Abschnitt 6); das „Studio-Daten-Gate“ für Schema-Änderungen ist nach der Owner-Antwort 7a bis nach Phase 1 zurückgestellt (#1667).
- **Q11 Ältere Lanes** werden erst mit der Abschluss-Epoche entfernt (PB-03, `qualification/`);
  Release-Archiv lokal ablegen statt dauerhaftem GitHub-Release, solange #1108 offen ist.

Grenzen: Der Go deckt Q1 bis Q11, nicht die Owner-Vorbehalte aus Abschnitt 5 (insbesondere
Freigabe 5/6 Sitze, Fork, Siegel/`qualification/`/WS17, Preise (außer TAM-Zukauf, 2026-11-21), #1108, Bezahldienste,
Kollektionstrennung). Der Owner spielt vor dem PLAY-Bedienungs-Paket selbst eine ganze Partie;
Abbruchkriterien in der Charta §6.

### Entscheide 2026-11-20/21 (#1661, #1167)

Owner, 2026-11-20 und 2026-11-21. Die Owner-Aussagen sind nicht wörtlich überliefert; der
Co-Lead hat sie in den unten genannten Kommentaren festgehalten (von den drei
Entscheid-Kommentaren nennt nur 7038409631 als Ort den Session-Chat; die Frage in 7031730010 nennt
ihn ebenfalls). Der Inhalt ist hier sinngemäß nach diesen Kommentaren übernommen (keine Anführungszeichen, siehe „Lesart“).

1. **Freigabe 5/6 Sitze: Option A = warten** (2026-11-20, #1661, Kommentar 7043554602; **historischer Stand vor E16, überholt durch das bedingte Go vom 2026-11-22, siehe E16**). Keine
   Freigabe; `launch.MAX_RELEASED_SEATS = 4` bleibt. SIMULATE 5/6 wird frühestens freigegeben,
   wenn (a) #1715 geklärt ist, einschließlich einer 4-Sitz-Vergleichsmessung mit n/N, (b) F5
   (die acht Regelpunkte aus Plan §2 als gezielte Szenarien) und das Replay-Tape mindestens für
   5 Sitze vorliegen und (c) der Owner F1 entschieden hat (Punkt 3; erfüllt am 2026-11-21, Abschnitt
   „Entscheide 2026-11-21“, 2a). Danach folgen das finale Ja
   des Owners und ein Freigabe-PR mit Review. PLAY 5/6 bleibt nach Option A getrennt und ist
   nicht Teil dieses SIMULATE-Freigabe-PR; Q5 („gilt dann für SIMULATE und PLAY“, E15) ist
   insoweit eingeschränkt, die Freigabe von PLAY 5/6 ist offen. Option A stammt aus der neuen Liste A/B/C der
   Ein-Seiten-Evidenz (#1661, Kommentar 7043142024; B: jetzt 5 und 6 mit Warntext, C: nur 5
   Sitze). Davon getrennt: Die früher am selben Tag festgehaltene Option B (#1167, Kommentar
   7038409631, Punkt 2) beantwortete die Frage nach einer Vorab-Ermächtigung (#1661, Kommentar
   7031730010): Der Co-Lead legt nach dem Nachweis eine Beleg-Zusammenfassung vor, die Freigabe
   mergt er erst nach dem finalen Ja, ohne Vorab-Ermächtigung. Die Beleg-Zusammenfassung ist mit
   der Ein-Seiten-Evidenz vorgelegt; Option B ist damit nicht abgelöst. Ob die dort genannten Nachweise (unter anderem #1692 geklärt)
   neben (a) bis (c) Freigabe-Voraussetzung bleiben, ist offen.
2. **Seed 123: keine Umklassifizierung** (2026-11-20, #1661, Kommentar 7043554602). Eine
   abweichende normalisierte Frame-Folge bleibt beim Bridge-Gate-Typ `NEUTRAL` ein FAIL
   (`AGENTS.md` §10). Für Seed 123 wird nichts in `UNORDERED_LISTS` (`engine/rules/frame_digest.py`)
   aufgenommen, insbesondere nicht `legal_options`. #1692 bleibt offen, bis die Ursache auf der
   Bridge-Seite geklärt ist.
3. **F1 war am 2026-11-20 offen** (#1661, Kommentar 7043554602): Einflussbereich `ALL`,
   Angriffsoption `MULTIPLE` und 6 Sitze ohne Replay-Anspruch
   (`docs/research/SEATS_5_6_QUALIFICATION_PLAN.md`, Phase 0). F1 ist eine Voraussetzung von
   Option A (Punkt 1) und nicht dasselbe wie Punkt 2. Am 2026-11-21 hat der Owner F1 entschieden
   (Abschnitt „Entscheide 2026-11-21“, 2a); geändert nach E10, weil „bleibt offen“ überholt ist.
4. **Kreuz-Review: Option 1** (2026-11-20, #1167, Kommentar 7038409631). `AGENTS.md` §10 gilt
   wie geschrieben. Das Kreuz-Review ist nur für Klasse A nötig, in beiden Richtungen zwischen
   den zwei parallel arbeitenden Agenten: Die Klasse-A-PRs des einen prüft eine Sitzung des
   anderen. Für Klasse B (nur Größe) genügt das Frischkontext-Review. Jeder Review-Kommentar
   nennt die Klasse. Bei Klasse A fordert der Autor das Kreuz-Review in #1167 an.

   **Alleiniger Writer seit 2026-11-21** (#1167, Kommentar 7053750538): Die Co-Lead-Sitzung ist
   alleiniger Writer für das Projekt. Alle Claims sind auf den Co-Lead übergegangen, auch die des
   anderen Agenten und der zweiten Sitzung. Im selben Kommentar bittet der Co-Lead andere Agenten,
   keine Branches mehr zu pushen außer in Absprache in #1167.

   **Befristete Ausnahme seit 2026-11-21** (gleiche Quelle):
   - Solange der andere Agent nicht verfügbar ist, ersetzt ein zweites Frischkontext-Review das
     Kreuz-Review der Klasse A. Es läuft auf einem anderen Modell als das erste Review, ohne
     Beteiligung des Autors und ohne die Befunde des ersten Reviews im Auftrag. Der
     Review-Kommentar nennt „Kreuz-Review-Ersatz (Owner-Entscheid 2026-11-21)“, die Klasse und
     die exakte Head-SHA.
   - **Befristet:** Die Ausnahme gilt nur, solange der andere Agent nicht verfügbar ist.
   - Die Ausnahme ändert nur, wer das Kreuz-Review leistet. Das Frischkontext-Review und die
     übrigen Merge-Bedingungen aus `AGENTS.md` §10 gelten unverändert.
   - **Weiter owner-vorbehalten** (Abschnitt 5, `AGENTS.md` §8): die Freigabe von 5/6 Sitzen
     (Option A, Punkt 1; seit dem 2026-11-22 als bedingtes Go erteilt, E16), Fork-Push und Repin, Siegel/`qualification/`/WS17, Sichtbarkeit
     (#1108), Bezahldienste, die Sammlungstrennung und Preise (außer TAM-Zukauf, 2026-11-21,
     „Preise für TAM“).

### Preise für TAM (2026-11-21, #1637, #1187)

Owner, 2026-11-21 (Wortlaut vom Co-Lead festgehalten in #1656, Kommentar 7062128464): „bei TAM
dürfen gerne Preise rein also das kannst du aus der agents md entfernen bzw anpassen, da ich für
tam hauptsächlich noch planeswalker + key cards kaufen muss um das deck so zu spielen wie ich will
sind hier Preise erlaubt“.

Herkunft: Owner (Reichweite) / Co-Lead (Umfang). Die Reichweite ist die Owner-Aussage oben;
den Umfang hat der Co-Lead festgelegt (#1656, Kommentar 7062128464, Punkt 3, und die
Review-Runden zu PR #1740 und PR #1741). Der Umfang ist keine Owner-Aussage.

Reichweite (Owner): Preise sind für den TAM-Zukauf erlaubt (vor allem Planeswalker und
Schlüsselkarten, wie der Owner als Grund nennt; das ist ein Beispiel, kein Filter). Chulane bleibt
unverändert Standard „nur Sammlung“ ohne Preise. Preise für andere Zwecke bleiben Owner-Vorbehalt
(`AGENTS.md` §8, §12).

Umfang und Grenzen (Co-Lead): Ein Preis wird nur für Karten angezeigt, die noch nicht im Besitz
sind, und nur in der TAM-Zukaufansicht. Karten im Besitz liegen in der gemeinsamen Sammlung und
tragen keinen Preis. Die Planungsfunktionen sind abschließend: Summe, Sortierung und Budgetfilter
der TAM-Zukauf-Liste, Kennzeichnung als Richtwert. Preise fließen nie in Vorschläge, Kürzen/Tauschen,
Evidenz/Reife, Rating, Tierliste, Ranking oder Simulationszahlen. Nicht erlaubt sind außerdem
Kaufabschluss und Kaufabwicklung, Bezahldienste und Scraping einer Seite ohne öffentliche API
(`AGENTS.md` §8). Preise werden nur aus einer Quelle gesammelt, die im Quellregister
(`src/commander_lab/studio/sources.py`) mit Zugangsstatus `ok` oder `ok_with_conditions` geführt ist (nie
`unclear` oder `prohibited`; Cardmarket erst nach geklärtem Zugang; Owner-Ausnahme 2026-11-22 unten); diese Preisabrufe sind die
einzige Ausnahme zu SR39 („nach außen gehen nur Abrufe öffentlicher Kartenbilder und
Kartendaten“, `AGENTS.md` §12). Jeder Preis trägt eine
ehrliche Quelle und einen Zeitstempel, ein fehlender Preis heißt „unbekannt“, nie 0 €. Ein
Cardmarket-API-Schlüssel bleibt `LOCAL_ONLY` beim Owner und kommt nie ins Repository
(`AGENTS.md` §12, Secrets). TAM-Preis-Schnappschüsse bleiben im lokalen Studio-Store und kommen
nicht ins Repository, bis der Owner anders entscheidet; Tests nutzen nur synthetische Werte.

Anmerkung zum Archiv: Der archivierte Scope (`STUDIO_SCOPE.md`, Thema `superseded`, Stand
`aef76b8e`, Zeilen 33 bis 34) sagt noch, der Zukauf-Modus im BUILD ohne Preise sei erlaubt und
Preisdaten dafür blieben Owner-Vorbehalt (T3). Der Archivtext bleibt unverändert; für den
TAM-Zukauf gilt dieser Eintrag.

Folgepaket #1637 (Plan aus dem Issue, kein Entscheid; Nummerierung wie dort): Quellen sind
(1) offizieller Cardmarket-API-Zugang nur mit lokalem Schlüssel beim Owner (`LOCAL_ONLY`), die
Klärung des Zugangs bleibt Teil von #1637; (2) Scryfall-Bulk `prices.eur`/`prices.eur_foil` als
Richtwert mit klarer Kennzeichnung, denn sie kennt weder das Verkäuferland DE noch den Zustand EX
und ist damit nicht die Zielgröße des Owners aus E14 (günstigstes Angebot eines deutschen
Anbieters, mindestens Excellent, Minimum aus Foil und Non-Foil); (3) Export der Zukauf-Liste in
Cardmarkets Wants-Liste und Shopping Wizard (Schritt (3) liegt außerhalb der abschließenden Planungsfunktionen, ist
ein Abruf-Gegenstück mit Datenausgang und nahe an der Kaufabwicklung: er braucht einen eigenen Entscheid und ist
von „Preise für TAM“ nicht gedeckt).

#### Owner-Ausnahme Cardmarket für den TAM-Zukauf (2026-11-22, #1637)

Owner, 2026-11-22, Session-Chat, wörtlich in zeitlicher Reihenfolge nach der Niederschrift des
Co-Leads in #1637, Kommentar 7077232382:

1. „ich will eigentlich für die Zukäufe speziell die cardmarket Preise deutscher Anbieter und da das
   günstigste jeder Variante der Karte (egal ob foil, etc (manchmal sind auch foil günstiger)) und
   mind excellent Zustand“
2. „Kannst die cardmarket Preise nicht einfach über den richtigen link (wo die Filter schon passend
   eingestellt sind) nicht scrapen? Das wäre z.b. der richtige link für Rograkh dafür:
   https://www.cardmarket.com/de/Magic/Cards/Rograkh-Son-of-Rohgahh?sellerCountry=7&language=1,3&minCondition=3“
3. „Bitte die Regel für hier aufheben und kümmer dich vollständig darum dir die Preise so zu
   besorgen wie ich meinte“
4. „Wieso kannst du dich nicht darum kümmern die Preise selber zu scrapen? Will kein Skript bei
   meinem Browser laufen lassen, entweder du kümmerst dich selber vollständig drum oder wir weichen
   auf etwas anderes aus was die Preise der karten auch möglichst gut repräsentiert und du aber
   automatisch suchen kannst“
5. „Ja passt, das mit dem direkt abfragen auch gut, mach weiter“ (auf den Vorschlag des Co-Leads:
   Näherungspreis aus lokalen Scryfall-Daten, ein höflicher „Direkt abrufen“-Knopf mit Abbruch bei
   Sperre, Link und Preisfeld als Rückfall; danach ersetzt durch den offiziellen
   Preisführer-Download als Hauptquelle).

Der Beispiel-Link in Satz 2 ist die einzige Grundlage für die Filternummern im Code
(`sellerCountry=7` Deutschland, `language=1,3` Englisch und Deutsch, `minCondition=3` Excellent).

Reichweite (Co-Lead-Auslegung, kein Owner-Wortlaut): Mit Satz 3 hebt der Owner die Regel
„kein Scraping einer Seite ohne öffentliche API“ (`AGENTS.md` §8, §12) für die Cardmarket-Preise der
TAM-Zukauf-Liste auf; der Co-Lead liest das auch als Freigabe einer Cardmarket-Quelle, deren
Zugangsstatus `unclear` ist („Cardmarket erst nach geklärtem Zugang“). Nach Satz 4 ist ein Skript im
Browser des Owners nicht gewollt.

Umfang und Grenzen (Co-Lead, umgesetzt in PR zu #1637, WP-10b):

- **Hauptweg:** der Cardmarket-Preisführer, den Cardmarket zum Download veröffentlicht
  (`downloads.s3.cardmarket.com`, `price_guide_1.json` und `products_singles_1.json`): nur auf
  Befehl des Owners (`python -m commander_lab.studio import-cardmarket-priceguide`), je Datei
  höchstens ein Abruf, eine lokale Kopie jünger als 24 Stunden wird wiederverwendet, ehrlicher
  User-Agent, keine Cookies, kein Konto, kein Schlüssel, kein Proxy, keine Umleitung; jede Antwort
  außer HTTP 200 stoppt sofort und wird vermerkt, danach 24 Stunden kein neuer Abruf (höchstens
  ein Abruf je Datei und Tag). Download-Ordner und eingelesene Dateien liegen nie im Repository. Zuordnung Karte zu Produkt über `cardmarket_id` der spielbaren
  Papierdrucke der lokalen Scryfall-Datei; je Karte der niedrigste `low`/`low-foil` (mit Druck und
  Finish) und der niedrigste `trend`/`trend-foil`. Anzeige „Cardmarket ab x,xx € (Trend y,yy €) ·
  ohne Filter Land/Sprache/Zustand · Stand …“: der Preisführer kennt weder Verkäuferland noch
  Sprache noch Zustand, der Aufschlag für Deutschland, Englisch/Deutsch und Excellent ist ohne
  Angebotsdaten nicht belegbar. Ein Preisführer älter als 14 Tage wird als veraltet markiert und
  zählt nicht; ohne Produktliste (`--file` ohne `--products`) steht „Namen nicht geprüft“.
- **Genauer Preis von Hand:** je Karte ein Link auf die Cardmarket-Kartenseite mit den Filtern des
  Owners (Standard Land Deutschland, Sprache Englisch und Deutsch, Mindestzustand Excellent;
  änderbar), den nur der Browser des Owners öffnet; der Owner trägt den abgelesenen Preis ein (oder
  eine CSV `Name;Preis;Datum`). Anzeige „Cardmarket DE/EX/EN+DE: x,xx € (eingetragen am …)“; älter als
  14 Tage gilt als veraltet und zählt nicht.
- **Vorrang:** eingetragener Preis > Preisführer (`low`, sonst `trend`) > Scryfall-Näherung
  (`prices.eur`/`prices.eur_foil`, Cardmarket-Trend); immer mit Quelle und Datum, fehlend
  „unbekannt“, nie 0 €.
- **Nicht erlaubt:** Umgehung von Zugangsschutz (kein Stealth-Browser, kein Lösen oder Umgehen
  einer Bot-Prüfung, keine Proxys oder IP-Wechsel, keine vorgetäuschte Browser-Kennung), das Lesen
  von Cardmarket-Seiten durch das Studio, Hintergrund- oder Massenabrufe, andere Quellen als
  Cardmarket und Preise außerhalb der TAM-Zukaufansicht. Die übrigen Grenzen von „Preise für TAM“
  gelten unverändert (nur nicht besessene Karten, nur Summe/Sortierung/Budgetfilter, nie in
  Wertung, Tierliste, Ranking, Vorschläge, Kürzen/Tauschen, Evidenz, Simulation oder
  Kartenverständnis; Chulane nie; Preisdaten nur im lokalen Studio-Store, nie committet; Tests nur
  synthetisch).
- **AGB-Lage:** Die Nutzungsbedingungen zu automatisiertem Abruf sind UNBELEGT (nicht gelesen);
  `robots.txt` trägt einen Rechtevorbehalt (EU-Richtlinie 2019/790). Das Risiko (etwa eine Sperre)
  liegt beim Owner. Im Quellregister steht der Preisführer deshalb mit Zugangsstatus `unclear`
  (`cardmarket:price-guide`).

Preis-Wächter beim Bau (mit diesem Eintrag nicht geändert; Zeilen am Stand `86802c05`, `main` mit
#1740):

- **Bleibt** (Repo-Daten, Chulane, Bewertung):
  `scripts/data_wave1/_common.py:67-69` (`PRICE_KEYS`),
  `tests/unit/test_audit_committed_research_data.py:12,29`,
  `tests/unit/test_studio_strength.py:216-228`, `tests/unit/test_studio_swap.py:221`,
  `tests/unit/test_studio_card_duel.py:135,348`; ebenso, als Einordnung der Review-Runde zu
  PR #1741 (Sammlungsimport und Daten-Seite sind nicht die TAM-Zukaufansicht):
  `tests/unit/test_studio_db_a_1404.py:22-31,139` und `tests/unit/test_studio_data_page.py:53`.
- **Nur für die TAM-Anzeige eng zu öffnen:** `tests/unit/test_studio_static_guards.py:14-15,72`
  (`PRICE_WORDS`; der Kommentar zitiert B1 und `AGENTS.md` §12),
  `tests/unit/test_studio_builder.py:966`, `data/provenance/source_inventory.json:44` und
  `src/commander_lab/studio/sources.py:157` („strip price fields on write“);
  `tests/unit/test_no_personal_collection_metadata.py:30,62` (`PURCHASE_TEXT`) nur für das Wort
  `Cardmarket` in `data/provenance/source_inventory.json`, wenn Cardmarket dort als Preisquelle
  geführt wird; `data/collections` und die übrigen gescannten Ordner bleiben auf Kaufdaten
  geprüft.

### Entscheide 2026-11-21 (Owner-Antworten 1b bis 8a, #1656, #1167)

Owner, 2026-11-21, Wortlaut des Owners nach dem Kommentar des Co-Leads: „Mach weiter mit deinen
Empfehlungen und PLAY teste ich später, mach sonst schon mal alles fertig“. Der Co-Lead hat das als
Annahme seiner Empfehlungen eingetragen (1b, 2a, 3a, 4a, 5a, 6a, 7a, 8a; #1656, Kommentar
7060377220, gleichlautend #1167, Kommentar 7060377370). Die Zuordnung zu den Optionen ist die
Eintragung des Co-Leads, kein Owner-Wortlaut (keine Anführungszeichen, siehe „Lesart“). 2a und
8a stehen in Nr. 5 und 6, 1b, 3a, 4a, 5a und 6a in Nr. 7; 7a (Studio-Daten-Gate in `AGENTS.md` §10
bis nach Phase 1 zurückgestellt) ist in E15 Q10 vermerkt. Nr. 8 hält den Owner-Wunsch zu 5/6
Sitzen aus #1656, Kommentar 7062128464, fest.

5. **F1 angenommen (2a).** F1 ist so angenommen, wie der Entwurf im Teil-A-Bericht §4 sie
   formuliert. Angenommener Wortlaut, wörtlich kopiert aus
   `docs/analysis-reports/seats_5_6_part_a_report.md` am Commit
   `f844573782adea7f0a0cb274bb9ac85de78b9ad4` (letzter Commit der Datei auf `main` beim Kopieren),
   Zeilen 120 bis 127. Spätere Änderungen an der Berichtsdatei ändern das Angenommene nicht;
   maßgeblich ist der Text unten:

```text
**F1, Entwurf der drei Sätze für den Owner (Owner legt fest):**
1. „Bei 5 und 6 Sitzen gilt dieselbe Engine-Einstellung wie bei 2 bis 4 Sitzen: Einflussbereich
   `ALL` (jeder Spieler wirkt auf alle) und Angriffsoption `MULTIPLE` (Angriff auf mehrere
   Gegner in einem Kampf); das ist eine Produkt-Einstellung, keine Regelvereinfachung.“
2. „5 Sitze werden mit Replay-Nachweis qualifiziert (Tape-MATCH wie bei 4 Sitzen).“
3. „6 Sitze werden ohne Replay-Anspruch freigegeben; die Oberfläche sagt das, und ein
   6-Sitz-Lauf zählt nie als Replay-PASS. Eine Tape-Erweiterung auf 6 ist eine eigene, geprüfte
   Änderung.“ (Alternative für den Owner: erst Tape erweitern, dann 6 freigeben.)
```

   **Einordnung des Co-Leads (Einspruch des Owners jederzeit möglich).** Die Anführungszeichen im
   Block oben stammen aus dem Bericht; die Sätze sind ein Entwurf, den der Owner angenommen hat,
   kein Owner-Wortlaut. Angenommen sind die drei Sätze; die Alternative in Klammern („erst Tape
   erweitern, dann 6 freigeben“) ist nicht gewählt. F1 schließt **nur Voraussetzung (c)** der
   SIMULATE-Freigabe von 5/6 (Punkt 1). Weiter fehlen (a) die Klärung von #1715 mit einer
   4-Sitz-Vergleichsmessung mit n/N und (b) F5 (die acht Regelpunkte aus Plan §2 als gezielte
   Szenarien) mit dem Replay-Tape mindestens für 5 Sitze; danach folgen das finale Ja des Owners
   und ein Freigabe-PR mit Review. **Die Sperre `launch.MAX_RELEASED_SEATS = 4` bleibt**, „aktiv
   sind 2 bis 4 Sitze“ bleibt, und die Freigabe von 5/6 bleibt owner-vorbehalten (Abschnitt 5,
   `AGENTS.md` §8). PLAY 5/6 bleibt nach Option A getrennt und ist nicht Teil des
   SIMULATE-Freigabe-PR. **[Stand vor E16: überholt durch das bedingte Go vom 2026-11-22, siehe E16.]** Ob #1692 neben (a) bis (c) Voraussetzung bleibt, ist weiter offen
   (Punkt 1).

6. **Pflichtlektüre und Archiv (8a).** Charta v2 (`docs/STUDIO_CHARTA_V2.md`) und dieses
   Entscheid-Register (diese Datei mit dem älteren Teil `docs/OWNER_DECISIONS_STUDIO_20261112.md`)
   sind die Pflichtlektüre für Studio-Arbeit. `STUDIO_SCOPE.md`, `STUDIO_PLAN_SIMULATOR.md` und
   `STUDIO_ROADMAP_20261112.md` sind archiviert (Thema `superseded`, `docs/README.md`, Abschnitt
   „Archive“). Vorher sind alle bindenden Regeln dieser drei Dateien, die weder in der Charta noch
   in diesem Register standen, in Abschnitt 6 übernommen; Archivieren hebt die Bindung nicht auf.
   Der Referenzsatz des Studio-Bridge-Gates steht seitdem wörtlich in
   `docs/STUDIO_BRIDGE_GATE_TOOLING.md`. Dass dieses Register die Datei
   `docs/OWNER_DECISIONS_STUDIO_20261112.md` als älteren Teil einschließt, ist Einordnung des
   Co-Leads: Sie bleibt als Owner-Entscheid-Dokument stehen und wird von dieser Datei ergänzt
   (Zweck oben).

7. **Übrige Antworten (1b, 3a, 4a, 5a, 6a).** Inhalt nach der Eintragung des Co-Leads in #1656,
   Kommentar 7060377220 (sinngemäß, kein Owner-Wortlaut):
   - **1b:** PLAY (ganze Partie über die Seite) testet der Owner später; #1662 Teile 2 bis 4
     bleiben bis dahin `needs:owner`. Vorher soll #1728 (D-3 Paket 2) auf `main` sein und die
     Pille „simuliert … KI auf allen Plätzen“ in `partie.html` für Mensch-Partien ehrlich sein.
   - **3a (Erfassung R2/R3):** Nachweise für die Reifegrade R2 und R3 als eigenes Paket, dreiwertig
     je Pilot-Fingerabdruck und JAR (bestanden, durchgefallen, nicht erfasst), nur über den
     Kontroll- bzw. Audit-Pfad, nie aus einer Anfrage. Randbedingung: „Bridge gesiegelt“ wird aus
     dem echten Siegel gelesen, nicht aus einem gespeicherten Merker; „vom Owner angenommen“ kommt
     nur aus einer Aktion des Owners; ein Agent setzt keines von beiden.
   - **4a:** Holm-Korrektur je Tisch als eigene Familie; die Oberfläche weist „nicht über Tische
     korrigiert“ aus.
   - **5a:** Knopf „Plan zurückziehen“ (Status `withdrawn`, bleibt sichtbar). Ein Plan ist nur
     zurückziehbar, solange er keine Partien hat und kein anderes Mitglied seiner Familie einen
     Blick (Look) oder ein Ergebnis hat; danach bleibt er Platzhalter p = 1. Dafür ein
     Mutationstest.
   - **6a:** Export für Schema 22 (#1703): Migrationsnachweis am PC des Owners ohne Upload; der
     Co-Lead bereitet Befehl und Checkliste vor, die Ausführung bleibt Owner-Sache.

8. **5/6-Sitz-SIMULATE gewünscht (2026-11-21).** Owner-Wortlaut (vom Co-Lead festgehalten in
   #1656, Kommentar 7062128464, Einleitungsabsatz): „und will unbedingt dass 5/6 Spieler
   Simulationen gehen, kümmer dich vollständig drum und bis zu 8 Spieler war ein Wunsch schau ob
   das sinnvoll ist und feasible“.

   **Auslegung des Co-Leads (Punkte 4 und 5 desselben Kommentars; keine Owner-Aussage):** Das ist
   ein Arbeitsauftrag, keine Freigabe. Der Co-Lead führt die Voraussetzungen (a) bis (c) aus Nr. 1
   und 5 durch und bereitet den Freigabe-PR vor. **Die Sperre `launch.MAX_RELEASED_SEATS = 4`
   bleibt**, bis die Voraussetzungen belegt sind und der Owner das finale Ja gegeben hat; die
   Freigabe von 5/6 bleibt owner-vorbehalten (Abschnitt 5, `AGENTS.md` §8). Bis zu 8 Sitze sind ein
   Wunsch: Sinn und Machbarkeit prüft ein Papier unter #1672, nichts davon ist freigegeben.
   **[Stand vor E16: die Sperre und der Vorbehalt dieses Absatzes sind durch das bedingte Go vom
   2026-11-22 überholt; zu 7/8 gilt die Owner-Anweisung vom 2026-11-22, siehe E16 Nr. 4.]**

### E16: Freigabe 5/6 Sitze, bedingtes Go (2026-11-22, #1656, #1661, #1743)

Owner, 2026-11-22, Session-Chat. Der Co-Lead hat die Antworten in #1656, Kommentar 7071394052,
festgehalten („wörtlich soweit in Anführungszeichen“). Das Register übernimmt nur, was dort in
Anführungszeichen steht, als Owner-Wortlaut; alles andere unten ist als Auslegung des Co-Leads
gekennzeichnet (Einspruch des Owners jederzeit möglich).

1. **Owner-Wortlaut zu 5/6 Sitzen:** „Ja 5/6 sitze freigegeben wenn alles dabei funktioniert“, für
   SIMULATE und PLAY (so der Co-Lead im selben Kommentar). Das ist ein **bedingtes Go**: Es ersetzt
   „Option A = warten“ (Entscheide 2026-11-20/21, Nr. 1) und den Vorbehalt „finales Ja nach der
   Beleg-Seite“; die Einschränkung, PLAY 5/6 bleibe getrennt und nicht Teil des
   SIMULATE-Freigabe-PR, gilt damit nicht mehr (E15 Q5 „gilt dann für SIMULATE und PLAY“ ist wieder
   voll wirksam). Die frühere Auslegung des Co-Leads, die Sperre `launch.MAX_RELEASED_SEATS = 4`
   bleibe bis zu einem weiteren Ja, ist durch dieses Go überholt.

2. **Auslegung des Co-Leads (keine Owner-Aussage) der Bedingung „alles funktioniert“:**
   (a) Determinismus bei 5 und 6 Sitzen gemessen und gleich. Stand der Messungen (alle
   `SIMULATED_RESULT`, lokal beobachtet, kein Qualifikationsbeleg): 4 Sitze ohne Abweichung in 188
   Vergleichen (Spur G 4 × 36 = 144, Spur S 12 + 12 + 20 = 44; #1715, Kommentar 7070359771); 5
   Sitze 8/8 und 8/8; 6 Sitze: Transkript, Sieger, Entscheidungen und Frames 8/8, normalisierte
   Frame-Digests 7/8 (Seed 4, Frame 3694, Entscheidung „Choose replacement effect“, `damage` 0
   gegen 4; 2 von 3 Wiederholungen weichen ab). Das ist `LOCAL_OBSERVED` (N = 8 Seeds und 3
   Wiederholungen eines Seeds), allgemein `UNKNOWN`; die Ursache ist nicht gezeigt (passt zur
   Diagnose zu #1715). Bedingung (a) für 6 Sitze gilt mit dem Owner-Wort (Nr. 6, Abweichung als beobachteter
   Lauf-zu-Lauf-Effekt, Ursache UNKNOWN) als erfüllt; ein Fork-Eingriff dazu braucht ein eigenes Owner-Go (`AGENTS.md` §8). (b) F5 und die
   Tape-Gates auf `main` (F5-3 nur PARTIAL wegen einer bekannten Engine-Abweichung), (c) die
   Real-Engine-Tests für PLAY 5/6 laufen grün, (d) die CI des Freigabe-PR #1743 ist grün (inklusive
   `pb03-runtime`; die Konformanz, soweit ihr Pfadfilter greift), (e) Abnahme durch den Owner nach der Freigabe: eine eigene
   PLAY-Partie mit 5 Sitzen; geht sie nicht, wird die Freigabe zurückgenommen. Werden (a) bis (d)
   erfüllt, merged der Co-Lead #1743 und meldet es sofort. Die Belege stehen im PR-Text von #1743
   und in den Kommentaren in #1661 und #1715; das Register führt sie nicht.

3. **Umsetzung:** Zwei Sperren, je eine Zeile in `studio/launch.py`: `MAX_RELEASED_SEATS` (SIMULATE
   und Partien ohne Mensch-Sitz) und `MAX_RELEASED_PLAY_SEATS` (Partie mit Mensch-Sitz), beide 6;
   die Oberfläche (`partie.js`, `paired.js`) folgt je einer Liste, Wächter-Tests halten Konstante und
   Seite gleich. **Zurücksetzen** (Auslegung des Co-Leads, fail-closed; bei Misserfolg von (e), auf Owner-Wunsch
   oder bei einem Defekt, jederzeit): die Konstante auf 4 setzen, plus die zugehörige Liste in `partie.js`
   bzw. `paired.js`; das ist ein Einzeiler je Pfad. Eine erneute Freigabe oder geänderte
   Bedingungen sind Owner-Sache. Die Obergrenze des Codes bleibt 6 (`MIN_SEATS, MAX_SEATS = 2, 6`).

4. **7/8 Sitze (nur als Hinweis):** Der Owner hat am selben Tag für SIMULATE angewiesen („ja kümmer
   dich drum, dass es halt geht und führe es auch ein für die Simulationen“, #1656, Kommentar
   7071394052, Punkt 6; Einordnung des Co-Leads: direkte Owner-Anweisung im Sinne von
   `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`). Vorgehen laut Co-Lead: erst ein isolierter
   Machbarkeitsversuch (#1672), nie als 4P/6P-Beleg; PLAY 7/8 ist nicht beauftragt. Dieser Eintrag
   ändert die Obergrenze 6 im Code nicht.

5. **Aufgehobene Aussagen (historischer Stand vor E16):** Die Sätze „die Sperre bleibt bei 4“,
   „aktiv sind 2 bis 4 Sitze“ und „PLAY 5/6 ist nicht Teil des SIMULATE-Freigabe-PR“ in Q5 (E15), in
   „Entscheide 2026-11-20/21“ Nr. 1, in „Entscheide 2026-11-21“ Nr. 5 und Nr. 8, in der Tabelle
   in Abschnitt 3, in Abschnitt 4 („Gilt unverändert“, Sitze) und in
   `docs/OWNER_DECISIONS_STUDIO_20261112.md` (A3, Einleitung) beschreiben den Stand vor dem Go vom
   2026-11-22 und sind dort mit einem Verweis auf E16 gekennzeichnet; sie bleiben als Verlauf stehen
   (E10). Der Vorbehalt in `AGENTS.md` §8 nennt die Freigabe jetzt als erteilt, mit Zitat, und das
   fail-closed Zurücksetzen als erlaubt (gekennzeichnet als Auslegung des Co-Leads, Nr. 3); sonst
   bleibt §8 unverändert.

6. **Owner-Antwort zu 6 Sitzen und zur beobachteten Abweichung (2026-11-22, Session-Chat,
   Niederschrift des Co-Leads).** Quelle: #1656 Kommentar 7077442218, gleichlautend #1661 Kommentar
   7077442365 und #1715 Kommentar 7077442522. Die dem Owner gestellte Frage steht dort wörtlich
   (Frage des Co-Leads, kein Owner-Wortlaut):

   > Bei 6 Sitzen weicht in 1 von 8 Testpartien ein Beobachtungs-Detail ab (ein Schadensmarker steht
   > in einem Kampfschaden-Frame mal bei 0, mal bei 4); Entscheidungen, Sieger und Transkript waren
   > in allen Fällen gleich, bei 4 und 5 Sitzen gab es 0 Abweichungen. Das Gleiche passiert auch
   > zwischen zwei identischen Läufen (Engine-Zufall, kein Fehler im Studio). Wie soll ich 5/6
   > freigeben?

   Einordnung zur Prämisse „Engine-Zufall, kein Fehler im Studio“: **beobachtet, Ursache nicht
   gezeigt.** Belegt ist nur, dass bei Seed 4 in 2 von 3 Wiederholungen der normalisierte Digest
   abweicht (`LOCAL_OBSERVED`, N = 8 Seeds und 3 Wiederholungen eines Seeds, #1661 Kommentar
   7077057382 und #1715 Kommentar 7077057577); ob Engine oder Bridge die Ursache ist, ist `UNKNOWN`,
   und „in allen Fällen gleich“ gilt für Entscheidungen, Sieger und Transkript nur für diese
   beobachteten Läufe (allgemein `UNKNOWN`). Antwort des Owners (Auswahl, Wortlaut):
   **„Beide freigeben (Empfehlung)“**, also 5 und 6 Sitze zusammen. Der Co-Lead hat im selben
   Kommentar festgehalten, die Abweichung stehe im Register; dort steht sie als **beobachteter
   Lauf-zu-Lauf-Effekt, Ursache UNKNOWN** (nicht als „bekannte Engine-Eigenschaft“). Ein Eingriff in
   die Engine (Fork) bräuchte ein eigenes Owner-Go (`AGENTS.md` §8). Das Zurücksetzen der Sperren auf
   4 Sitze ist jederzeit möglich (fail-closed, Nr. 3); eine Neufreigabe entscheidet nur der Owner.
   Der Pool-Pfad (`COMMANDER_LAB_STUDIO_SERIES_POOL`, standardmäßig aus) bleibt für 5 und 6 Sitze
   abgewiesen (Entscheidung des Co-Leads wegen #1715, Pool-Identität; keine Wandzeit-Grenze für 5/6).
   Die Serienplanung (`paired_series.py`) rechnet bei 5/6 Sitzen seit #1756 mit der Basis-Siegrate
   1/N (20 % bzw. 16,7 %; planende Streuung 0,582 bzw. 0,542); die Dauer wird bei 5/6 als grobe
   Orientierung angegeben, nie als Mindestdauer, gemessen ist nur der Vierertisch.

### E17: Streuung der Kartenbewertung H, Option B (2026-11-22, #1404, #1758)

Owner, 2026-11-22, Session-Chat; Niederschrift des Co-Leads in #1404, Kommentar 7081544721. Owner-
Wortlaut (nur der Text in Anführungszeichen): „2a) ja zu 3: B also deine Empfehlung und stell
einfach sicher dass das rating der karten möglichst gut ist 4: ja“. Alles Weitere ist Auslegung
des Co-Leads bzw. der umsetzenden Sitzung (Einspruch des Owners jederzeit möglich).

1. **Option B (Auslegung des Co-Leads im selben Kommentar):** Die Streuung der Kartenbewertung H
   wird in der Tierliste als Mindestwert „±8“ angezeigt, die Marken werden etwas gröber gefasst;
   keine Paarvergleiche. Grundlage ist der zweite Rater-Lauf
   (`docs/analysis-reports/rating_second_run_20261122.md`, #1758): Einzelstreuung 8,1 [7,3; 8,9],
   n/N = 265/300 (ohne die 35 Prüfer-markierten Karten), über der bisherigen Anzeige „±5–8“; Urteil
   nach Plan „teilweise bestätigt“ (G1-Schwellen), Modellfamilie ungeprüft (A3), daher wird der
   Lauf in der Anzeige nicht „unabhängig“ genannt.
2. **Umsetzung (umsetzende Sitzung, nur Anzeige und Schwellen):** Mindeststreuung `SPREAD_FLOOR = 8`
   und Rauschgate `NOISE_GATE = SPREAD_FLOOR` in `src/commander_lab/studio/understanding_field.py`
   (eine Konstante; Tests binden sie an die aus den Rohdaten nachgerechnete 8,1). Keine angezeigte
   Streuung, kein Band und keine Marke liegt unter ±8 (Bänder: H bis 10 „±8“, H 40 bis 55 „≈±10“,
   ab H 60 „≈−15/+8“); Unterschiede von H unter 8 Punkten sind kein Rangunterschied; ein H-Zweifel
   des Rating-Audits A, dessen Spanne näher als 8 Punkte am Wert liegt, erscheint ohne Warnmarke
   (heute 0 von 33 H-Zweifeln). H hatte schon vorher keine Stufe, keinen Rang und keine Sortierung
   (E15 Q1); die Stufen S bis D der Tierliste beruhen auf dem Nutzungsindex und sind unberührt. Die
   Rohwerte bleiben unverändert, `intervall` bleibt `null`; kein Preis- oder Simulationseinfluss,
   Chulane-Fokus unverändert.
3. **„möglichst gut“ (Auslegung des Co-Leads):** Die Güte der Kartenbewertung wird über eine zweite
   unabhängige Bewertung weiterer Karten und Mittelung nach einer vorab festgelegten Regel
   verbessert, nicht über stille Korrekturen; das ist ein eigener Arbeitsschritt, nicht Teil der
   Anzeige-Änderung.

## 3. Was aufgehoben, geändert oder neu ist

| Bisher | Jetzt | Quelle |
|---|---|---|
| Optionspapier: B-X1 („deckbuild-studio kanonisch“), Vertrag „Deck-Snapshot v1“, Frage O2 (Vorschläge, nie beschlossen) | verworfen; BUILD bleibt hier (E1) | O1 |
| B11 (`OWNER_DECISIONS_STUDIO_20261112.md`): Simulation zählt nicht in die Tierliste | bedingt: Gewicht 0, bis G-SIM erfüllt ist und der Owner Gewicht und Darstellung bestätigt (E2) | O3 |
| S2 und Einfrierung neuer Pilot-Mikro-Messreihen (2026-11-10) | nur für die reine Zählung von Pilot-Auslassungen aufgehoben (E3) | O4 |
| K4 „keine Kombination“, E1.a „Rubrik-Gewicht 0“, Ablehnung einer modellgestützten Einschätzung, A4 „nur objektive Daten“ | nur für das neue, gekennzeichnete Gesamtrating aufgehoben (E6) | Owner 18.11., angenommen 18.11. |
| PLAY „fertig“, wenn der Owner eine ganze Partie spielt (`STUDIO_ROADMAP_20261112.md`) | Abnahme nach AK-1 bis AK-8 (E4) | O6 |
| 5 und 6 Sitze: nur durch Regel nicht freigegeben; Code nimmt 2 bis 6 Sitze an (`studio/launch.py`: `MIN_SEATS, MAX_SEATS = 2, 6`) | neu: technische Sperre für 5 und 6 Sitze; aufgehoben wird sie nur per Owner-Freigabe. Im Studio-Startpfad (Partie, PLAY) ist sie mit PR #1515 auf `main` (`launch.MAX_RELEASED_SEATS = 4`). In den Serien-Routen und in `compare-decks` gilt sie seit PR #1536 (`compare-decks` mit Schalter `--allow-unreleased-seats`, standardmäßig aus). **Seit E16 (2026-11-22) zwei Sperren, `MAX_RELEASED_SEATS` und `MAX_RELEASED_PLAY_SEATS`, beide auf 6 freigegeben; Stand vor E16 wie hier beschrieben.** | Empfehlung O11 des Optionspapiers, Owner-GO 2026-11-18 |
| `docs/STUDIO_TARGET_SCOPE.md` als Zielumfang (PR #1510) | ersetzt durch `STUDIO_SCOPE.md` (seit 2026-11-21 archiviert, bindende Regeln in Abschnitt 6) | Owner 2026-11-18 (Abschnitt 1), Optionspapier §D.1 |
| G-SIM Punkt 2: Stichprobe 200/20, eigene Owner-Bestätigung nötig; S2 nur für die Zählung aufgehoben | Pilot-Audit dreiteilig; S2 zusätzlich nur für dieses Audit aufgehoben | E7, C1 |
| Weg in die Tierliste: „nach G-SIM eigenes Design“ | Stufen 0 / 1 / 2; Gewicht größer 0 erst in Stufe 2 | E7, C3 |
| Review eines MATERIAL-PR aus frischem Kontext | zusätzlich Kreuz-Review durch den jeweils anderen Agenten, soweit zwei parallel arbeiten | E7, C7 |
| Owner-Entscheidung 2026-10-15 (`owner_decision_20261015_batch_games_per_jvm`): jedes Ergebnis ruht auf dem sauberen Herunterfahren des Prozesses | gilt nur für `run_batch` und die Konformanz-Evidenz; für Studio-Serien ruht das Ergebnis auf dem bestätigten `shutdown_game` je Partie in eigenem Ergebnistyp (E9) | Owner 2026-11-19, #1612 |
| „Keine Preise, kein Kaufmodus“ (B1) und „kein Multi-Commander über den Chulane-Fokus hinaus“ (B2), soweit BUILD betroffen | Zukauf-Modus im BUILD ohne Preise und TAM als zweiter Commander im BUILD erlaubt; Preise bleiben Owner-Vorbehalt, Chulane bleibt Standard (E14); für TAM überholt durch „Preise für TAM (2026-11-21)“ | Owner 2026-11-19, #1187 |
| Preise und Preisdaten für Zukäufe bleiben Owner-Vorbehalt (E14, T3; `AGENTS.md` §8, §12) | Preisanzeige für noch nicht besessene Karten in der TAM-Zukaufansicht erlaubt (vor allem Planeswalker und Schlüsselkarten), Planungsfunktionen abschließend Summe, Sortierung und Budgetfilter der TAM-Zukauf-Liste und Kennzeichnung als Richtwert (Umfang vom Co-Lead); mit Quelle aus dem Quellregister und Zeitstempel, fehlend „unbekannt“; Schnappschüsse nur im lokalen Studio-Store; Preise nie in Vorschläge, Kürzen/Tauschen, Evidenz/Reife, Rating, Tierliste, Ranking oder Simulationszahlen; keine Kaufabwicklung, keine Bezahldienste, kein Scraping; Chulane bleibt „nur Sammlung“ ohne Preise; andere Preise bleiben Owner-Vorbehalt („Preise für TAM (2026-11-21)“) | Owner 2026-11-21, #1656 |
| E6 (Gesamtrating mit Rubrik und Tierlisten-Gewichte), B11/E2 (Gewicht `simulation` 0 bis G-SIM), A4 („nur objektive Daten“), E7/C7 (jeder MATERIAL-PR mit Kreuz-Review), Rundenlimit nur nach Owner-Entscheid (`STUDIO_SCOPE.md` am Commit `aef76b8e`, Zeilen 101–102 und 269), 5/6 Sitze (E15 Q5), Datei-Schnitt Schema 21 → 22 | beschlossen; wirksam sind schon Gesamtrating v1, Layers, Rubrik v1, Turnier-Signal und Gewicht `simulation` entfernt (#1684, #1686, #1691, #1696), die zweite Tierlisten-Skala ist mit #1701 entfernt (#1680), die Evidenz R0–R3 ist mit #1717 als Paket 1 im Serien-Verlauf gebaut (höchstens R1 erreichbar; Erfassung für R2/R3 sowie Evidenz im Diff und in der Kürzen-/Tauschen-Spalte offen, Q1-c, #1666) (Q1), Vorschläge als eigene Klasse (Q2), MATERIAL in A/B (Q10, umgesetzt in `AGENTS.md` §10 mit dem Doku-Wahrheits-Pass #1697), rundenbegrenzte Frühphasen-Serie als Experiment-Typ nach Messversuch (Q4: gilt als Owner-Entscheid für dieses Rundenlimit, weiterhin mit vollen Piloten, kein Goldfish-/Passiv-Modus, `STUDIO_SCOPE.md` am Commit `aef76b8e`, Zeilen 268–269), Qualifikation 5/6 (Q5, Sperre bleibt), Gegner aus Studio-Deck-Ständen (Q6), Pilot-Regeln (Q8), drei Dateien (Q9), Ältere Lanes bleiben (Q11) | Owner 2026-11-20 (E15) |
| 5/6-Freigabe: Owner-Wunsch „wenn es problemlos geht“; Vorab-Ermächtigung verneint (Option B, #1167, Kommentar 7038409631, Punkt 2; Beleg-Zusammenfassung mit der Ein-Seiten-Evidenz #1661, Kommentar 7043142024 vorgelegt) | Option A = warten (neue Liste A/B/C): frühestens nach #1715 (mit 4-Sitz-Vergleichsmessung n/N), F5 (die acht Regelpunkte aus Plan §2 als gezielte Szenarien) und Replay-Tape mindestens für 5 Sitze und Owner-Entscheid zu F1, dann finales Ja und Freigabe-PR mit Review; `launch.MAX_RELEASED_SEATS = 4` bleibt; PLAY 5/6 bleibt getrennt (nicht Teil des SIMULATE-Freigabe-PR), Q5 „gilt dann für SIMULATE und PLAY“ ist insoweit eingeschränkt und offen; ob #1692 Voraussetzung bleibt, ist offen (Entscheide 2026-11-20/21, Nr. 1 und 3). **Historischer Stand vor E16, überholt durch das bedingte Go vom 2026-11-22 (E16).** | Owner 2026-11-20 (#1661) |
| Abweichende Frame-Folge bei Seed 123 (#1692): Wegnormalisieren als Umklassifizierung dem Owner vorgelegt (#1661, Kommentar 7043142024) | keine Umklassifizierung: bleibt FAIL (`NEUTRAL`), nichts in `UNORDERED_LISTS`, #1692 offen bis zur Ursache auf der Bridge-Seite (Entscheide 2026-11-20/21, Nr. 2) | Owner 2026-11-20 (#1661) |
| Kreuz-Review der Klasse A durch eine Sitzung des anderen Agenten (E7/C7, E15 Q10) | bestätigt als Option 1 (`AGENTS.md` §10 wie geschrieben, Klasse B nur Frischkontext-Review); befristete Ausnahme seit 2026-11-21: Co-Lead alleiniger Writer, zweites Frischkontext-Review auf einem anderen Modell ersetzt das Kreuz-Review, solange der andere Agent nicht verfügbar ist (Entscheide 2026-11-20/21, Nr. 4) | Owner 2026-11-20 und 2026-11-21 (#1167) |
| Entscheid-Dokumente: „fortgeschrieben, nie gelöscht“ (diese Datei, `AGENTS.md` §9 „archived, never deleted“) | überholter Wortlaut darf mit Begründung, Datum und Verweis im PR ersetzt oder entfernt werden; Git-Historie bleibt Quelle (E10) | Owner 2026-11-19, #1612 |
| F1 offen (Entscheide 2026-11-20/21, Nr. 3): Einflussbereich, Angriffsoption, 6 Sitze ohne Replay-Anspruch | angenommen wie im Entwurf des Teil-A-Berichts §4, Wortlaut mit Pfad und Commit-SHA kopiert; schließt nur Voraussetzung (c), `launch.MAX_RELEASED_SEATS = 4` bleibt, (a) und (b) und das finale Ja fehlen, PLAY 5/6 bleibt getrennt (Entscheide 2026-11-21, Nr. 5; **Stand vor E16**, das bedingte Go vom 2026-11-22 überholt die Sperre und die Trennung) | Owner 2026-11-21 (2a; #1656, #1167) |
| 5/6-Freigabe „nur nach finalem Ja“ (Entscheide 2026-11-20/21, Nr. 1; 2026-11-21, Nr. 5 und 8) | bedingtes Go: „Ja 5/6 sitze freigegeben wenn alles dabei funktioniert“, SIMULATE und PLAY; beide Sperren auf 6, Rücknahme ein Einzeiler (E16) | Owner 2026-11-22 (#1656, Kommentar 7071394052) |
| Pflichtlektüre: `AGENTS.md`, `CLAUDE.md`, `STUDIO_SCOPE.md` (verbindlicher Scope), beide Entscheid-Dateien, `STUDIO_PLAN_SIMULATOR.md`, Onboarding; seit E15 Q10 zuerst Charta v2 und Register, Scope blieb verbindlich | Charta v2 und Entscheid-Register sind die Pflichtlektüre; Scope, Plan und Roadmap sind archiviert, ihre bindenden Regeln stehen in Abschnitt 6, der Referenzsatz des Bridge-Gates in `docs/STUDIO_BRIDGE_GATE_TOOLING.md` (Entscheide 2026-11-21, Nr. 6) | Owner 2026-11-21 (8a; #1656, #1167) |

## 4. Gilt unverändert

- XMage ist die alleinige Regelautorität (`AGENTS.md` §2, A2).
- Keine Erste-, Zufalls- oder Standard-Option in produktionserreichbaren Pfaden (`AGENTS.md` §2).
- Keine Preise und keine Kaufabwicklung (B1, `AGENTS.md` §12); ein Zukauf-Modus im BUILD ohne Preise ist seit 2026-11-19 erlaubt (E14), Preisanzeige für den TAM-Zukauf seit 2026-11-21 („Preise für TAM“); Kaufabwicklung bleibt ausgeschlossen.
- Jede Zahl mit n/N und Herkunft; „unbekannt“ statt 0 (A4, A5).
- Kohorten werden nie gemischt oder addiert (A5, B3).
- Chulane ist das Standard-Owner-Deck und der Fokus (`docs/OWNER_DECK_FOCUS_CURRENT.md`); TAM kommt im BUILD als zweiter Commander dazu (E14).
- Keine neuen Abhängigkeiten und keine Änderung an `pyproject.toml` ohne Owner-Go (`AGENTS.md`
  §4, §10).
- Sitze: Höchstzahl 6 (`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`), Standard 4. Aktiv sind
  2 bis 4 Sitze; 5 und 6 sind nicht freigegeben (eigene Qualifikation und Owner-Freigabe, A3,
  A8). Zur technischen Sperre siehe Abschnitt 3. **[Stand vor E16: überholt durch das bedingte Go
  vom 2026-11-22, siehe E16.]**
- Sammlungstrennung (Lesart des Optionspapiers, Owner-Bestätigung offen): Die Sammlung dieses Repositorys (`collection_1655`) und die von
  `deckbuild-studio` bleiben getrennte Bestände und werden nicht verrechnet.
- Merge-Gate nach `AGENTS.md` §10.

## 5. Weiter owner-vorbehalten

Nicht durch die Anweisung, nach den Empfehlungen zu arbeiten, oder das GO abgedeckt; maßgeblich ist die Liste in
`AGENTS.md` §8:

- Pushes in den Fork `moeendres-png/mage` und Repins der Engine.
- Versiegeln, Entsiegeln oder Umschreiben von Datensätzen unter `qualification/`.
- `pyproject.toml`, `requirements/lock.txt` und dessen Digest (außer innerhalb einer
  Neuversiegelung oder der D5-Freigabe, `AGENTS.md` §4, §10).
- Freigabe von 5 und 6 Sitzen (erteilt als bedingtes Go am 2026-11-22, E16; Zurücksetzen der Sperren auf 4 ist nach der Auslegung des Co-Leads (E16 Nr. 3) jederzeit fail-closed erlaubt, eine erneute Freigabe oder geänderte Bedingungen sind Owner-Sache).
- Sichtbarkeit der Repositorys und #1108.
- Bezahldienste, Preisdaten und Kaufabwicklung (T3 aus E14); ausgenommen ist die Preisanzeige für den TAM-Zukauf (2026-11-21, „Preise für TAM“).

## 6. Aus Scope, Plan und Roadmap übernommene Regeln (Owner-Antwort 8a, 2026-11-21)

**Warum.** Nach der Owner-Antwort 8a (Abschnitt „Entscheide 2026-11-21“, Punkt 6) sind
`STUDIO_SCOPE.md`, `STUDIO_PLAN_SIMULATOR.md` und `STUDIO_ROADMAP_20261112.md` archiviert.
Archivieren hebt die Bindung nicht auf: Jede bindende Regel dieser drei Dateien (Muss, Darf-nicht,
Gate, Reihenfolge, Grenzwert), die nicht schon in der Charta v2 (§5) oder in den Abschnitten 1 bis
5 dieses Registers stand, gilt aus diesem Abschnitt weiter. Was dort nur Stand, Empfehlung oder
überholt war, ist nicht übernommen. Die Prüftabelle (jede geprüfte Regel mit Quelle und Ergebnis:
übernommen, schon vorhanden mit Fundstelle, oder nicht bindend) steht im PR, der diesen Abschnitt
eingeführt hat (Refs #1667).

**Quellenstand.** „SC“ meint `STUDIO_SCOPE.md` am Commit
`aef76b8e0b345ab61c216bfeb7890bf2d7b9998f`, „PL“ `STUDIO_PLAN_SIMULATOR.md` und „RM“
`STUDIO_ROADMAP_20261112.md` am Commit `41938a58dc8489aa3121a98bab3c64990ac9a7c3`; die Zahl nach
dem Doppelpunkt ist die Zeile dort. Für Plan und Roadmap ist das der letzte Stand auf `main` vor der
Archivierung. Beim Scope ist der letzte Stand auf `main` `86802c05` (#1740, Preis-Satz in den
Zeilen 34 bis 35); gepinnt ist `aef76b8e`, und die Archivkopie ist byte-gleich mit `aef76b8e`. Die
Preis-Ausnahme steht nur in diesem Register („Preise für TAM“).
SR37, SR38 und SR39 sind nach den Reviews nachgetragen (Reste, die zunächst als „schon vorhanden“ galten) und stehen bei ihrem Thema, nicht am Ende der Nummernfolge.
„SR“ steht für eine übernommene Scope-Regel (bis zur Review-Runde zu PR #1741 hießen sie R1 bis R39); „R1“ hat damit drei getrennte Bedeutungen: der Reifegrad R1 (R0 bis R3 der Simulations-Evidenz, E15 Q1, `AGENTS.md` §1), der Referenzsatz „R1“ des Bridge-Gates (36 Seeds des echten Vierer-Pods, `docs/STUDIO_BRIDGE_GATE_TOOLING.md`, `docs/STUDIO_OWNER_PC_SETUP.md`) und hier nur als SR1 die Scope-Regel.

**Lesart (Einordnung des Co-Leads, Einspruch des Owners jederzeit möglich).** Die Regeln in den
Tabellen sind wortlautnah übernommen und nicht neu gefasst; Einordnungen außerhalb der Tabellen
(etwa zur Reihenfolge in 6.7) sind als solche gekennzeichnet. Wo eine Regel gleichlautend in `AGENTS.md` steht, ist
sie hier nur wiederholt, damit sie nicht an einer archivierten Datei hängt; bei Widerspruch gilt
`AGENTS.md`. Die Anführungszeichen in SR15 bis SR17 umschließen den Wortlaut des Plans, der die
Owner-Entscheide vom 2026-11-12 (abends) festhielt; sie sind kein Owner-Wortlaut. Für Änderungen
an diesem Abschnitt gilt dasselbe wie für die übrigen Owner-Entscheide (SR33).

### 6.1 Alle Bereiche

| # | Regel | Quelle |
|---|---|---|
| SR1 | Bei Widerspruch gehen die Owner-Entscheide vor; Git, Tests und Issues sind Source Truth für den technischen Stand (gleichlautend `AGENTS.md` §3). | SC:9-10 |
| SR2 | Die Engine nimmt 2 bis 6 Sitze an (`studio/launch.py`: `MIN_SEATS, MAX_SEATS = 2, 6`); ihr Verhalten bei 5 und 6 Sitzen ist nicht qualifiziert und gilt als `UNKNOWN`. Der Schalter `--allow-unreleased-seats` von `compare-decks` bleibt standardmäßig aus und wird nur nach Owner-Freigabe gesetzt. | SC:37-42 |

### 6.2 PLAY

| # | Regel | Quelle |
|---|---|---|
| SR3 | Die Abnahme-Partien (AK-1 bis AK-8, E4) werden schon nach P0 gespielt; die Reihenfolge der P1-Punkte folgt aus AK-8. | SC:58-59 |
| SR4 | P1a ist nur Seite, ohne Bridge-Änderung: Stack-Schiene mit Zielen aus dem veröffentlichten Zustand, Tastatur mit sichtbarem Fokus, Yield-Modi nur über die Pass-Option, die die Engine anbietet (jede andere Entscheidung hält an, jeder automatische Pass steht im Protokoll), Wiedergabe einer beendeten Partie Zug für Zug. | SC:64 |
| SR5 | P1b: Commander-Steuer und Commander-Schaden nur als Engine-Werte, nie auf der Seite errechnet; neuer Frame-Inhalt ist eine `BEHAVIOUR`-Änderung unter dem Studio-Bridge-Gate (`AGENTS.md` §10). Erst nach AK-8 und nach den P1a-Punkten, die AK-8 vorzieht. | SC:65 |
| SR6 | Nur auf Owner-Wunsch (P2): serverseitiges Yield (vorher unabhängiges Review gegen `AGENTS.md` §2), Bedienung per Berührung, Mensch auf einem anderen Sitz als 1, Bildvergleichs-Tests (neue Abhängigkeit). Nicht geplant: freies Rückgängig (P4), Erklärung einzelner KI-Entscheidungen, passiver Gegner (P3); zu Speichern und Wiederaufnehmen E5 und E15 Q7. | SC:66 |
| SR22 | Der Echt-Engine-Test des Mensch-Sitzes läuft in einem CI-Job und ist dort nicht übersprungen. | SC:158 (S1, Abnahme 3) |
| SR24 | Jeder P1-Punkt hat einen Test, der ohne die Änderung fällt. | SC:161 |

### 6.3 SIMULATE

| # | Regel | Quelle |
|---|---|---|
| SR7 | Gepaarte Serien laufen nur parallel, wenn die Identität belegt ist: jedes Spiel im Stapel hat denselben semantischen Hash wie allein gespielt, gepaart-parallel n identisch von N mit N ≥ 20 Spielen; sonst laufen gepaarte Serien mit einem Worker. | SC:78, SC:158 (S1, Abnahme 2), PL:45 |
| SR8 | Der Serienplan liegt als Datei vor dem ersten Spiel vor. Die Konsistenz-Tafel trennt drei Herkunftsklassen (exakt gerechnet; in der Engine gemessen und pilotunabhängig; in der Engine gemessen und pilotabhängig). Jedes Ergebnis trägt den Gültigkeitsblock (Sitzkurve neben der Playgroup-Referenz, Zählung der Pilot-Auslassungen nach E3, fester Satz zur KI-Gültigkeit). | SC:79 |
| SR9 | Simulationsergebnisse erscheinen (Wortlaut SC:91-94) „nur im Deckbauer (Vergleich zweier Stände) und im Deck-Verlauf, als eigene Kohorte `SIMULATED_RESULT`, nie in einer Spalte mit EDHREC-, Playgroup- oder TopDeck-Zahlen, nie über Commander oder Deck-Stände summiert. Eine Serie zu einem anderen Deck-Stand wird nie als Ergebnis des aktuellen Standes gezeigt.“ Dazu SC:251: „Ergebnisse nur als `SIMULATED_RESULT` mit Herkunft“. Das Gewicht und der Reifegrad stehen in E15 Q1. | SC:91-94, SC:251, RM:61 |
| SR10 | SIMULATE entscheidet Pakete und Bauachsen (Landzahl, Ramp-, Schutzpaket), nicht einzelne Kartentausche; die Oberfläche sagt das. | SC:98-99 |
| SR38 | Später, nur bei Bedarf (A3): rundenbegrenzte Serien mit vollen Piloten, Kontrollgrößen, Zufalls-Pods, Vorausschau-Piloten (S5, #1265; Vorausschau nicht als Serien-Pilot, E15 Q8). Rundenlimit (E15 Q4), neue Abhängigkeiten und 5/6 Sitze brauchen einen Owner-Entscheid. | SC:100-102 |

### 6.4 Engine, Bridge und Aufräumen

| # | Regel | Quelle |
|---|---|---|
| SR11 | Änderungen unter `engine-bridge/` für das Studio laufen über das Studio-Bridge-Gate (gleichlautend `AGENTS.md` §10). Der feste Referenzsatz, die Befehle und die Pflichtangaben eines Ergebnisses („What a result must always say“) stehen seit dieser Übernahme wörtlich in `docs/STUDIO_BRIDGE_GATE_TOOLING.md`. | SC:108-109, PL:58-92 |
| SR12 | Eine Bridge-Änderung, die Frame-Inhalt entfernt, ist `BEHAVIOUR`, nicht `NEUTRAL`. | PL:48 |
| SR13 | Engine-Vorausschau (S5) nur als gemessenes Experiment unter dem Studio-Bridge-Gate, deklariert `BEHAVIOUR`: Die Bridge meldet nur die akteurgebundene Sicht des fragenden Sitzes auf die Kopie; verdeckte Zonen der Kopie werden aus öffentlicher Information und dem Wissen des Sitzes neu bestimmt; die Kopie nutzt ihren eigenen aufgezeichneten Zufall, nie den der echten Partie; jede Wahl in der Kopie trifft ein Pilot oder sie beendet die Vorausschau (fail-closed, keine Engine-KI); ein Test belegt, dass keine verdeckte Kartenidentität zurückkommt. Standard aus; Standard wird sie nur, wenn eine gepaarte Serie einen Nutzen zeigt. Als Serien-Pilot nicht (E15 Q8). | PL:49 |
| SR14 | Eine schlanke Bridge (S4, #1264 ohne gemessenen Gewinn geparkt) nur als neuer Messversuch unter dem Studio-Bridge-Gate, nicht als Meilenstein. | SC:274 |
| SR15 | Plan-Entscheid D4, Wortlaut des Plans: „Code that the Studio never reaches and that belongs to removed things is deleted (S3). Git history keeps it. Sealed qualification records are not touched.“ | PL:21 |
| SR16 | Plan-Entscheid D5 (auf ihn verweist `AGENTS.md` §8), Wortlaut des Plans: „`pyproject.toml` may change for S3: its two console scripts become unused once the workflows that call them are removed (S3 a and c). The digest in `WS17_SHA256SUMS` is regenerated in the same PR with `scripts/regenerate_hash_manifests.py`; `tests/qualification/test_ws17_qualification.py` verifies it.“ Die Grenzen aus `AGENTS.md` §8 zu `WS17_SHA256SUMS` gelten unverändert. | PL:22 |
| SR17 | Plan-Entscheid D6, Wortlaut des Plans: „The rule "at least 10 seeds for a pilot change" is withdrawn. How many games a statement needs follows from its interval, which every result shows.“ | PL:23 |

### 6.5 Betrieb und Release

| # | Regel | Quelle |
|---|---|---|
| SR37 | Plattform: Der Owner-PC ist Windows; Start über `scripts/studio_start.ps1`, Datenordner standardmäßig `%LOCALAPPDATA%\CommanderStudio` (`docs/STUDIO_OWNER_PC_SETUP.md`). Linux/WSL (`scripts/studio_start.sh`) ist nur Ausweichweg; ob am Owner-PC WSL vorhanden ist: `UNKNOWN`. | SC:119-121 |
| SR18 | Messwerkzeuge für Bridge-Gate und Serien-Identität müssen unter Windows laufen. | SC:122-124, SC:158 (S1, Abnahme 4) |
| SR19 | Das Release-Artefakt (`.github/workflows/release-artifacts.yml`, zum abgenommenen Commit, mit `xmage-engine-bridge.jar`, dessen `.sha256` und `ENGINE_PIN.txt`; `retention-days: 30`) wird vor dem Abschluss neu erzeugt. Ein dauerhaftes GitHub-Release ist eine Veröffentlichung und Owner-Entscheid (E15 Q11, `AGENTS.md` §8). | SC:125-128 |
| SR39 | Backup und Telemetrie: Der Studio-Datenordner (Deck-Verlauf, Markierungen, Serien, Partien) liegt nur auf dem Owner-PC; Sicherung und Rückspiel sind eine Anforderung, noch nicht gebaut (eigenes Paket). Das Studio sendet keine Nutzungs- oder Messdaten nach außen; nach außen gehen nur Abrufe öffentlicher Kartenbilder und Kartendaten (`AGENTS.md` §12). Messwerte der Abnahme kommen als Dateien zurück. (Ausnahme: Preisabrufe für TAM nach „Preise für TAM“.) | SC:129-133 |
| SR20 | Zum Abschluss: neue Qualifikations-Epoche (Versiegeln braucht das Owner-Go) oder dauerhaft sichtbar „vor Qualifikation“. | SC:134-135 |
| SR21 | Die Owner-PC-Seite (`docs/STUDIO_OWNER_PC_SETUP.md`) wird einmal von null in sauberer Umgebung durchgespielt; jede Abweichung ist ein Befund. | SC:158 (S1, Abnahme 5) |

### 6.6 Abnahme und Abschlusskriterien

| # | Regel | Quelle |
|---|---|---|
| SR23 | Im Abnahme-Protokoll bekommt jede Zeile Wert, Herkunft (Datei oder Bildschirmfoto) und Urteil PASS, FAIL oder `UNKNOWN`; AK-3 steht als Tabelle n je Entscheidungsklasse, nicht vorgekommen = `UNKNOWN`. Vorlage: `docs/STUDIO_ABNAHME_PROTOKOLL.md`. | SC:165-173 |
| SR25 | Abschluss 1, PLAY: AK-1 bis AK-8 erfüllt und vom Owner bestätigt. | SC:188 |
| SR26 | Abschluss 2, SIMULATE: Eine vom Owner gestellte Chulane-Frage ist mit Serienplan, Ergebnis, Intervall, nachweisbarer Differenz und Gültigkeitsblock beantwortet und im Deck-Verlauf sichtbar. | SC:189-190 |
| SR27 | Abschluss 3, BUILD: Ein Deck geht ohne Handarbeit aus dem Deckbauer in Partie und Serie; die Tierliste (#1369) ist vom Owner abgenommen (das Gesamtrating daraus ist seit E15 Q1 entfernt). | SC:191-192 |
| SR28 | Abschluss 4, Regeln: Komponente `simulation` existiert nicht mehr (E15 Q1), durch Test gesichert; 5 und 6 Sitze technisch gesperrt oder vom Owner freigegeben; keine Zahl ohne n/N. | SC:193 |
| SR29 | Abschluss 5, Doku: die Charta v2, dieses Register und keine offenen Widersprüche in den Studio-Dokumenten (in der Quelle „diese Datei, die Entscheidungsdatei“; angepasst, weil der Scope archiviert ist). | SC:194 |
| SR30 | Abschluss 6, Betrieb: Einrichtung am Owner-PC aus dem Release-Paket nachvollzogen; Zustand der Bridge gegenüber dem Siegel ehrlich ausgewiesen. | SC:195-196 |

### 6.7 Abarbeitung (für alle Agents)

So wird Studio-Arbeit abgearbeitet, von jedem Agenten gleich.

Reihenfolge, Wortlaut der Quelle (SC:208-210; Wortlaut des archivierten Scopes, kein
Owner-Wortlaut; innere Anführungszeichen als ‚…‘ gesetzt): „die Phasen 0 bis 5 aus
‚Roadmap-Phasen‘, verfeinert durch den Phasenplan S0 bis S6; Phase 1 (PLAY P0) und Phase 2
(SIMULATE A1) laufen parallel, weil ihre Flächen getrennt sind.“

Einordnung des Co-Leads, nicht Wortlaut (Einspruch des Owners jederzeit möglich): Die
Roadmap-Phasen 0 bis 5 und der Phasenplan S0 bis S6 sind Verlauf; die
weitere Reihenfolge der Arbeit folgt der Charta v2 (§3 Nr. 4 und §4, Planung des Co-Leads nach
`AGENTS.md` §8). Die noch offenen Abnahmen aus Scope und Roadmap stehen in SR7 und SR18 bis SR30.

Claims nach E8 und `AGENTS.md` §11 (Claim-Tabelle in #1167,
Verfall 24 Stunden nach unbeantworteter Rückfrage bei einem Claim ohne gepushten Meilenstein),
Owner-Entscheide wörtlich mit Quelle (Lesart oben; die Owner-Antworten vom 2026-11-21 stehen in „Entscheide 2026-11-21“ Nr. 5 bis 8), Kreuz-Review der Klasse A und seine befristete
Ausnahme nach „Entscheide 2026-11-20/21“ Nr. 4; Simulation nach E15 Q1 und SR9 (`SIMULATED_RESULT`). Flächen-Karte und
Kollisionsdateien: `docs/STUDIO_AGENT_ONBOARDING.md`.

| # | Regel | Quelle |
|---|---|---|
| SR31 | Ein Paket = ein Issue bzw. ein Branch = ein PR. Commits und PR-Texte sagen `Refs #N`, nie `Closes #N` (`AGENTS.md` §10). | SC:221-222 |
| SR32 | Studio-Ergänzung zu `AGENTS.md` §10 (ändert §10 nicht): Texte der Oberfläche, die Aussagen über Ratings oder Simulationsergebnisse machen, sind review-pflichtig; eine solche Änderung wird wie MATERIAL behandelt. Ein Merge vor dem erforderlichen Review ist nach §10 ein Gate-Verstoß, soweit die Änderung unter die MATERIAL-Liste in §10 fällt. | SC:227-230 |
| SR33 | Governance-Dateien: Änderungen an `AGENTS.md` und `CLAUDE.md` erfolgen durch Lead oder Coordinator nach `AGENTS.md` §8. Inhaltliche Änderungen am Scope (in der Quelle „diese Datei“; Nachfolger sind die vom Owner angenommene Charta v2 §5 und dieser Abschnitt), an den Owner-Entscheiden (`docs/OWNER_DECISIONS_*`) und an Owner-vorbehaltenen Regeln nur auf ausdrückliche Owner-Anweisung oder nach Owner-Freigabe einer vorgelegten Option; die Quelle steht im PR. Andere Agents legen Option und Empfehlung vor. Entscheide von Lead oder Coordinator innerhalb des Scopes nach `AGENTS.md` §8 bleiben unberührt und stehen im Issue oder PR; E10 (Überarbeiten überholten Wortlauts mit Begründung, Datum und Verweis) bleibt unberührt. Bei Unsicherheit wird mit dem Owner geplant (Owner, 2026-11-18). | SC:239-245 |
| SR34 | Was nicht belegt ist, heißt `UNKNOWN`, nie PASS. Punkte, die eine echte Engine oder den Owner-PC brauchen, werden als solche ausgewiesen und nicht durch Tests mit nachgebautem Client als erledigt gemeldet. | SC:248-250 |

### 6.8 Nicht übernommen aus `docs/STUDIO_TARGET_SCOPE.md`

Die strittigen Einzelpunkte gelten nach Abschnitt 1 („Folge für `docs/STUDIO_TARGET_SCOPE.md`“)
weiter als nicht gebaut; Passiv-/Goldfish-Modus und Rundenlimit regelt Abschnitt 3 (E15 Q4),
Pilot-Fehlentscheidungsberichte E3 und E7 (C1), „Resolve All“ E5 (Einordnung). Zusätzlich gilt:

| # | Regel | Quelle |
|---|---|---|
| SR35 | Multi-Commander über den Chulane-Fokus hinaus (B2) hat für PLAY und Serien keine Owner-Quelle, soweit E14 (BUILD), E15 Q3 (TAM-Simulation erst nach Zählung der Sim-Bereitschaft je Kohorte) und E15 Q6 (Studio-Deck-Stände als Gegner-Sitze) es nicht abdecken. | SC:272 |
| SR36 | Spaltenansicht im Deckbauer: keine Owner-Quelle; als BUILD-Wunsch dem Owner vorzulegen, nicht ohne Owner-Entscheid zu bauen. | SC:273 |
