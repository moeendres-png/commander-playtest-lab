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
  Kohorte `SIMULATED_RESULT` (Abschnitt 6.3).

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
  (Abschnitt 6.5).
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
  rechtlicher und technischer Klärung des API-Zugangs; kein Scraping.

Grenzen: Chulane bleibt Fokus und Standard („nur Sammlung“, `include_unowned` aus). Die
Kollektionstrennung bleibt: Zukauf-Karten sind ein Merkmal im Deck, keine Änderung der Sammlung.
Preise, Preisdaten und Kaufabwicklung bleiben Owner-vorbehalten (`AGENTS.md` §8). Kohorten werden
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
- **Q4 Experimente:** eine Nacht je Frage (5.400 Partien); rundenbegrenzte Frühphasen-Serie (L1) als
  eigener Experiment-Typ nach einem Messversuch.
- **Q5 Sitze:** Qualifikation 5/6 jetzt (die acht Prüfpunkte aus `docs/research/SEATS_5_6_QUALIFICATION_PLAN.md` §2, in der Charta „F1–F8“ genannt; der Teil-A-Bericht `docs/analysis-reports/seats_5_6_part_a_report.md` §1 nummeriert anders: dort ist F1 die Festlegung `ALL`/`MULTIPLE`/6 ohne Replay-Anspruch und F5 die acht Regelpunkte aus Plan §2, so auch im Abschnitt „Entscheide 2026-11-20/21“);
  **die Freigabe selbst bleibt eine eigene Owner-Entscheidung nach dem Nachweis** (`AGENTS.md` §8)
  und gilt dann für SIMULATE und PLAY (eingeschränkt durch Option A vom 2026-11-20: PLAY 5/6 bleibt
  getrennt, Abschnitt „Entscheide 2026-11-20/21“ Nr. 1). **Die technische Sperre (`launch.MAX_RELEASED_SEATS = 4`, §3) und
  „aktiv sind 2 bis 4 Sitze“ (§4) bleiben bis zur Owner-Freigabe unverändert;** „PLAY bis dahin ‚nicht
  qualifiziert‘ sichtbar“ heißt nur: die Oberfläche weist darauf hin, dass 5/6 noch nicht freigegeben
  sind, sie macht 5/6 nicht spielbar. 7/8 zurückgestellt bis zur 6er-Messung.
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
  Merkmal; Preise bleiben Owner-Vorbehalt; Chulane bleibt Standard „nur Sammlung“, `include_unowned` aus, E14). Die
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
Freigabe 5/6 Sitze, Fork, Siegel/`qualification/`/WS17, Preise, #1108, Bezahldienste,
Kollektionstrennung). Der Owner spielt vor dem PLAY-Bedienungs-Paket selbst eine ganze Partie;
Abbruchkriterien in der Charta §6.

### Entscheide 2026-11-20/21 (#1661, #1167)

Owner, 2026-11-20 und 2026-11-21. Die Owner-Aussagen sind nicht wörtlich überliefert; der
Co-Lead hat sie in den unten genannten Kommentaren festgehalten (von den drei
Entscheid-Kommentaren nennt nur 7038409631 als Ort den Session-Chat; die Frage in 7031730010 nennt
ihn ebenfalls). Der Inhalt ist hier sinngemäß nach diesen Kommentaren übernommen (keine Anführungszeichen, siehe „Lesart“).

1. **Freigabe 5/6 Sitze: Option A = warten** (2026-11-20, #1661, Kommentar 7043554602). Keine
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
     (Option A, Punkt 1), Fork-Push und Repin, Siegel/`qualification/`/WS17, Sichtbarkeit
     (#1108), Bezahldienste, die Sammlungstrennung und Preise.

### Entscheide 2026-11-21 (Owner-Antworten 2a und 8a, #1656, #1167)

Owner, 2026-11-21, Wortlaut des Owners nach dem Kommentar des Co-Leads: „Mach weiter mit deinen
Empfehlungen und PLAY teste ich später, mach sonst schon mal alles fertig“. Der Co-Lead hat das als
Annahme seiner Empfehlungen eingetragen (1b, 2a, 3a, 4a, 5a, 6a, 7a, 8a; #1656, Kommentar
7060377220, gleichlautend #1167, Kommentar 7060377370). Die Zuordnung zu den Optionen ist die
Eintragung des Co-Leads, kein Owner-Wortlaut (keine Anführungszeichen, siehe „Lesart“). Hier
stehen nur 2a und 8a; 7a (Studio-Daten-Gate in `AGENTS.md` §10 bis nach Phase 1 zurückgestellt)
ist in E15 Q10 vermerkt, die übrigen Antworten betreffen eigene Pakete und stehen in den beiden
Kommentaren.

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
   SIMULATE-Freigabe-PR. Ob #1692 neben (a) bis (c) Voraussetzung bleibt, ist weiter offen
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

## 3. Was aufgehoben, geändert oder neu ist

| Bisher | Jetzt | Quelle |
|---|---|---|
| Optionspapier: B-X1 („deckbuild-studio kanonisch“), Vertrag „Deck-Snapshot v1“, Frage O2 (Vorschläge, nie beschlossen) | verworfen; BUILD bleibt hier (E1) | O1 |
| B11 (`OWNER_DECISIONS_STUDIO_20261112.md`): Simulation zählt nicht in die Tierliste | bedingt: Gewicht 0, bis G-SIM erfüllt ist und der Owner Gewicht und Darstellung bestätigt (E2) | O3 |
| S2 und Einfrierung neuer Pilot-Mikro-Messreihen (2026-11-10) | nur für die reine Zählung von Pilot-Auslassungen aufgehoben (E3) | O4 |
| K4 „keine Kombination“, E1.a „Rubrik-Gewicht 0“, Ablehnung einer modellgestützten Einschätzung, A4 „nur objektive Daten“ | nur für das neue, gekennzeichnete Gesamtrating aufgehoben (E6) | Owner 18.11., angenommen 18.11. |
| PLAY „fertig“, wenn der Owner eine ganze Partie spielt (`STUDIO_ROADMAP_20261112.md`) | Abnahme nach AK-1 bis AK-8 (E4) | O6 |
| 5 und 6 Sitze: nur durch Regel nicht freigegeben; Code nimmt 2 bis 6 Sitze an (`studio/launch.py`: `MIN_SEATS, MAX_SEATS = 2, 6`) | neu: technische Sperre für 5 und 6 Sitze; aufgehoben wird sie nur per Owner-Freigabe. Im Studio-Startpfad (Partie, PLAY) ist sie mit PR #1515 auf `main` (`launch.MAX_RELEASED_SEATS = 4`). In den Serien-Routen und in `compare-decks` gilt sie seit PR #1536 (`compare-decks` mit Schalter `--allow-unreleased-seats`, standardmäßig aus). | Empfehlung O11 des Optionspapiers, Owner-GO 2026-11-18 |
| `docs/STUDIO_TARGET_SCOPE.md` als Zielumfang (PR #1510) | ersetzt durch `STUDIO_SCOPE.md` (seit 2026-11-21 archiviert, bindende Regeln in Abschnitt 6) | Owner 2026-11-18 (Abschnitt 1), Optionspapier §D.1 |
| G-SIM Punkt 2: Stichprobe 200/20, eigene Owner-Bestätigung nötig; S2 nur für die Zählung aufgehoben | Pilot-Audit dreiteilig; S2 zusätzlich nur für dieses Audit aufgehoben | E7, C1 |
| Weg in die Tierliste: „nach G-SIM eigenes Design“ | Stufen 0 / 1 / 2; Gewicht größer 0 erst in Stufe 2 | E7, C3 |
| Review eines MATERIAL-PR aus frischem Kontext | zusätzlich Kreuz-Review durch den jeweils anderen Agenten, soweit zwei parallel arbeiten | E7, C7 |
| Owner-Entscheidung 2026-10-15 (`owner_decision_20261015_batch_games_per_jvm`): jedes Ergebnis ruht auf dem sauberen Herunterfahren des Prozesses | gilt nur für `run_batch` und die Konformanz-Evidenz; für Studio-Serien ruht das Ergebnis auf dem bestätigten `shutdown_game` je Partie in eigenem Ergebnistyp (E9) | Owner 2026-11-19, #1612 |
| „Keine Preise, kein Kaufmodus“ (B1) und „kein Multi-Commander über den Chulane-Fokus hinaus“ (B2), soweit BUILD betroffen | Zukauf-Modus im BUILD ohne Preise und TAM als zweiter Commander im BUILD erlaubt; Preise bleiben Owner-Vorbehalt, Chulane bleibt Standard (E14) | Owner 2026-11-19, #1187 |
| E6 (Gesamtrating mit Rubrik und Tierlisten-Gewichte), B11/E2 (Gewicht `simulation` 0 bis G-SIM), A4 („nur objektive Daten“), E7/C7 (jeder MATERIAL-PR mit Kreuz-Review), Rundenlimit nur nach Owner-Entscheid (`STUDIO_SCOPE.md` am Commit `aef76b8e`, Zeilen 101–102 und 269), 5/6 Sitze (E15 Q5), Datei-Schnitt Schema 21 → 22 | beschlossen; wirksam sind schon Gesamtrating v1, Layers, Rubrik v1, Turnier-Signal und Gewicht `simulation` entfernt (#1684, #1686, #1691, #1696), die zweite Tierlisten-Skala ist mit #1701 entfernt (#1680), die Evidenz R0–R3 ist mit #1717 als Paket 1 im Serien-Verlauf gebaut (höchstens R1 erreichbar; Erfassung für R2/R3 sowie Evidenz im Diff und in der Kürzen-/Tauschen-Spalte offen, Q1-c, #1666) (Q1), Vorschläge als eigene Klasse (Q2), MATERIAL in A/B (Q10, umgesetzt in `AGENTS.md` §10 mit dem Doku-Wahrheits-Pass #1697), rundenbegrenzte Frühphasen-Serie als Experiment-Typ nach Messversuch (Q4: gilt als Owner-Entscheid für dieses Rundenlimit, weiterhin mit vollen Piloten, kein Goldfish-/Passiv-Modus, `STUDIO_SCOPE.md` am Commit `aef76b8e`, Zeilen 268–269), Qualifikation 5/6 (Q5, Sperre bleibt), Gegner aus Studio-Deck-Ständen (Q6), Pilot-Regeln (Q8), drei Dateien (Q9), Ältere Lanes bleiben (Q11) | Owner 2026-11-20 (E15) |
| 5/6-Freigabe: Owner-Wunsch „wenn es problemlos geht“; Vorab-Ermächtigung verneint (Option B, #1167, Kommentar 7038409631, Punkt 2; Beleg-Zusammenfassung mit der Ein-Seiten-Evidenz #1661, Kommentar 7043142024 vorgelegt) | Option A = warten (neue Liste A/B/C): frühestens nach #1715 (mit 4-Sitz-Vergleichsmessung n/N), F5 (die acht Regelpunkte aus Plan §2 als gezielte Szenarien) und Replay-Tape mindestens für 5 Sitze und Owner-Entscheid zu F1, dann finales Ja und Freigabe-PR mit Review; `launch.MAX_RELEASED_SEATS = 4` bleibt; PLAY 5/6 bleibt getrennt (nicht Teil des SIMULATE-Freigabe-PR), Q5 „gilt dann für SIMULATE und PLAY“ ist insoweit eingeschränkt und offen; ob #1692 Voraussetzung bleibt, ist offen (Entscheide 2026-11-20/21, Nr. 1 und 3) | Owner 2026-11-20 (#1661) |
| Abweichende Frame-Folge bei Seed 123 (#1692): Wegnormalisieren als Umklassifizierung dem Owner vorgelegt (#1661, Kommentar 7043142024) | keine Umklassifizierung: bleibt FAIL (`NEUTRAL`), nichts in `UNORDERED_LISTS`, #1692 offen bis zur Ursache auf der Bridge-Seite (Entscheide 2026-11-20/21, Nr. 2) | Owner 2026-11-20 (#1661) |
| Kreuz-Review der Klasse A durch eine Sitzung des anderen Agenten (E7/C7, E15 Q10) | bestätigt als Option 1 (`AGENTS.md` §10 wie geschrieben, Klasse B nur Frischkontext-Review); befristete Ausnahme seit 2026-11-21: Co-Lead alleiniger Writer, zweites Frischkontext-Review auf einem anderen Modell ersetzt das Kreuz-Review, solange der andere Agent nicht verfügbar ist (Entscheide 2026-11-20/21, Nr. 4) | Owner 2026-11-20 und 2026-11-21 (#1167) |
| Entscheid-Dokumente: „fortgeschrieben, nie gelöscht“ (diese Datei, `AGENTS.md` §9 „archived, never deleted“) | überholter Wortlaut darf mit Begründung, Datum und Verweis im PR ersetzt oder entfernt werden; Git-Historie bleibt Quelle (E10) | Owner 2026-11-19, #1612 |
| F1 offen (Entscheide 2026-11-20/21, Nr. 3): Einflussbereich, Angriffsoption, 6 Sitze ohne Replay-Anspruch | angenommen wie im Entwurf des Teil-A-Berichts §4, Wortlaut mit Pfad und Commit-SHA kopiert; schließt nur Voraussetzung (c), `launch.MAX_RELEASED_SEATS = 4` bleibt, (a) und (b) und das finale Ja fehlen, PLAY 5/6 bleibt getrennt (Entscheide 2026-11-21, Nr. 5) | Owner 2026-11-21 (2a; #1656, #1167) |
| Pflichtlektüre: `AGENTS.md`, `CLAUDE.md`, `STUDIO_SCOPE.md` (verbindlicher Scope), beide Entscheid-Dateien, `STUDIO_PLAN_SIMULATOR.md`, Onboarding; seit E15 Q10 zuerst Charta v2 und Register, Scope blieb verbindlich | Charta v2 und Entscheid-Register sind die Pflichtlektüre; Scope, Plan und Roadmap sind archiviert, ihre bindenden Regeln stehen in Abschnitt 6, der Referenzsatz des Bridge-Gates in `docs/STUDIO_BRIDGE_GATE_TOOLING.md` (Entscheide 2026-11-21, Nr. 6) | Owner 2026-11-21 (8a; #1656, #1167) |

## 4. Gilt unverändert

- XMage ist die alleinige Regelautorität (`AGENTS.md` §2, A2).
- Keine Erste-, Zufalls- oder Standard-Option in produktionserreichbaren Pfaden (`AGENTS.md` §2).
- Keine Preise und keine Kaufabwicklung (B1, `AGENTS.md` §12); ein Zukauf-Modus im BUILD ohne Preise ist seit 2026-11-19 erlaubt (E14).
- Jede Zahl mit n/N und Herkunft; „unbekannt“ statt 0 (A4, A5).
- Kohorten werden nie gemischt oder addiert (A5, B3).
- Chulane ist das Standard-Owner-Deck und der Fokus (`docs/OWNER_DECK_FOCUS_CURRENT.md`); TAM kommt im BUILD als zweiter Commander dazu (E14).
- Keine neuen Abhängigkeiten und keine Änderung an `pyproject.toml` ohne Owner-Go (`AGENTS.md`
  §4, §10).
- Sitze: Höchstzahl 6 (`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`), Standard 4. Aktiv sind
  2 bis 4 Sitze; 5 und 6 sind nicht freigegeben (eigene Qualifikation und Owner-Freigabe, A3,
  A8). Zur technischen Sperre siehe Abschnitt 3.
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
- Freigabe von 5 und 6 Sitzen.
- Sichtbarkeit der Repositorys und #1108.
- Bezahldienste, Preisdaten und Kaufabwicklung (T3 aus E14).

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
dem Doppelpunkt ist die Zeile dort. Diese Stände sind die letzten auf `main` vor der Archivierung.

**Lesart (Einordnung des Co-Leads, Einspruch des Owners jederzeit möglich).** Die Regeln sind
wortlautnah übernommen und nicht neu gefasst. Wo eine Regel gleichlautend in `AGENTS.md` steht, ist
sie hier nur wiederholt, damit sie nicht an einer archivierten Datei hängt; bei Widerspruch gilt
`AGENTS.md`. Für Änderungen an diesem Abschnitt gilt dasselbe wie für die übrigen Owner-Entscheide
(R33).

### 6.1 Alle Bereiche

| # | Regel | Quelle |
|---|---|---|
| R1 | Bei Widerspruch gehen die Owner-Entscheide vor; Git, Tests und Issues sind Source Truth für den technischen Stand (gleichlautend `AGENTS.md` §3). | SC:9-10 |
| R2 | Die Engine nimmt 2 bis 6 Sitze an (`studio/launch.py`: `MIN_SEATS, MAX_SEATS = 2, 6`); ihr Verhalten bei 5 und 6 Sitzen ist nicht qualifiziert und gilt als `UNKNOWN`. Der Schalter `--allow-unreleased-seats` von `compare-decks` bleibt standardmäßig aus und wird nur nach Owner-Freigabe gesetzt. | SC:37-42 |

### 6.2 PLAY

| # | Regel | Quelle |
|---|---|---|
| R3 | Die Abnahme-Partien (AK-1 bis AK-8, E4) werden schon nach P0 gespielt; die Reihenfolge der P1-Punkte folgt aus AK-8. | SC:58-59 |
| R4 | P1a ist nur Seite, ohne Bridge-Änderung: Stack-Schiene mit Zielen aus dem veröffentlichten Zustand, Tastatur mit sichtbarem Fokus, Yield-Modi nur über die Pass-Option, die die Engine anbietet (jede andere Entscheidung hält an, jeder automatische Pass steht im Protokoll), Wiedergabe einer beendeten Partie Zug für Zug. | SC:64 |
| R5 | P1b: Commander-Steuer und Commander-Schaden nur als Engine-Werte, nie auf der Seite errechnet; neuer Frame-Inhalt ist eine `BEHAVIOUR`-Änderung unter dem Studio-Bridge-Gate (`AGENTS.md` §10). Erst nach AK-8 und nach den P1a-Punkten, die AK-8 vorzieht. | SC:65 |
| R6 | Nur auf Owner-Wunsch (P2): serverseitiges Yield (vorher unabhängiges Review gegen `AGENTS.md` §2), Bedienung per Berührung, Mensch auf einem anderen Sitz als 1, Bildvergleichs-Tests (neue Abhängigkeit). Nicht geplant: freies Rückgängig (P4), Erklärung einzelner KI-Entscheidungen, passiver Gegner (P3); zu Speichern und Wiederaufnehmen E5 und E15 Q7. | SC:66 |
| R22 | Der Echt-Engine-Test des Mensch-Sitzes läuft in einem CI-Job und ist dort nicht übersprungen. | SC:158 (S1, Abnahme 3) |
| R24 | Jeder P1-Punkt hat einen Test, der ohne die Änderung fällt. | SC:161 |

### 6.3 SIMULATE

| # | Regel | Quelle |
|---|---|---|
| R7 | Gepaarte Serien laufen nur parallel, wenn die Identität belegt ist: jedes Spiel im Stapel hat denselben semantischen Hash wie allein gespielt, gepaart-parallel n identisch von N mit N ≥ 20 Spielen; sonst laufen gepaarte Serien mit einem Worker. | SC:78, SC:158 (S1, Abnahme 2), PL:45 |
| R8 | Der Serienplan liegt als Datei vor dem ersten Spiel vor. Die Konsistenz-Tafel trennt drei Herkunftsklassen (exakt gerechnet; in der Engine gemessen und pilotunabhängig; in der Engine gemessen und pilotabhängig). Jedes Ergebnis trägt den Gültigkeitsblock (Sitzkurve neben der Playgroup-Referenz, Zählung der Pilot-Auslassungen nach E3, fester Satz zur KI-Gültigkeit). | SC:79 |
| R9 | Simulationsergebnisse stehen nie in einer Spalte mit EDHREC-, Playgroup- oder TopDeck-Zahlen und werden nie über Commander oder Deck-Stände summiert. Eine Serie zu einem anderen Deck-Stand wird nie als Ergebnis des aktuellen Standes gezeigt. | SC:92-94, RM:61 |
| R10 | SIMULATE entscheidet Pakete und Bauachsen (Landzahl, Ramp-, Schutzpaket), nicht einzelne Kartentausche; die Oberfläche sagt das. | SC:98-99 |

### 6.4 Engine, Bridge und Aufräumen

| # | Regel | Quelle |
|---|---|---|
| R11 | Änderungen unter `engine-bridge/` für das Studio laufen über das Studio-Bridge-Gate (gleichlautend `AGENTS.md` §10). Der feste Referenzsatz, die Befehle und die Pflichtangaben eines Ergebnisses („What a result must always say“) stehen seit dieser Übernahme wörtlich in `docs/STUDIO_BRIDGE_GATE_TOOLING.md`. | SC:108-109, PL:58-92 |
| R12 | Eine Bridge-Änderung, die Frame-Inhalt entfernt, ist `BEHAVIOUR`, nicht `NEUTRAL`. | PL:48 |
| R13 | Engine-Vorausschau (S5) nur als gemessenes Experiment unter dem Studio-Bridge-Gate, deklariert `BEHAVIOUR`: Die Bridge meldet nur die akteurgebundene Sicht des fragenden Sitzes auf die Kopie; verdeckte Zonen der Kopie werden aus öffentlicher Information und dem Wissen des Sitzes neu bestimmt; die Kopie nutzt ihren eigenen aufgezeichneten Zufall, nie den der echten Partie; jede Wahl in der Kopie trifft ein Pilot oder sie beendet die Vorausschau (fail-closed, keine Engine-KI); ein Test belegt, dass keine verdeckte Kartenidentität zurückkommt. Standard aus; Standard wird sie nur, wenn eine gepaarte Serie einen Nutzen zeigt. Als Serien-Pilot nicht (E15 Q8). | PL:49 |
| R14 | Eine schlanke Bridge (S4, #1264 ohne gemessenen Gewinn geparkt) nur als neuer Messversuch unter dem Studio-Bridge-Gate, nicht als Meilenstein. | SC:274 |
| R15 | Plan-Entscheid D4, Wortlaut des Plans: „Code that the Studio never reaches and that belongs to removed things is deleted (S3). Git history keeps it. Sealed qualification records are not touched.“ | PL:21 |
| R16 | Plan-Entscheid D5 (auf ihn verweist `AGENTS.md` §8), Wortlaut des Plans: „`pyproject.toml` may change for S3: its two console scripts become unused once the workflows that call them are removed (S3 a and c). The digest in `WS17_SHA256SUMS` is regenerated in the same PR with `scripts/regenerate_hash_manifests.py`; `tests/qualification/test_ws17_qualification.py` verifies it.“ Die Grenzen aus `AGENTS.md` §8 zu `WS17_SHA256SUMS` gelten unverändert. | PL:22 |
| R17 | Plan-Entscheid D6, Wortlaut des Plans: „The rule "at least 10 seeds for a pilot change" is withdrawn. How many games a statement needs follows from its interval, which every result shows.“ | PL:23 |

### 6.5 Betrieb und Release

| # | Regel | Quelle |
|---|---|---|
| R18 | Messwerkzeuge für Bridge-Gate und Serien-Identität müssen unter Windows laufen. | SC:122-124, SC:158 (S1, Abnahme 4) |
| R19 | Das Release-Artefakt (`.github/workflows/release-artifacts.yml`, mit `xmage-engine-bridge.jar`, dessen `.sha256` und `ENGINE_PIN.txt`; `retention-days: 30`) wird vor dem Abschluss neu erzeugt. Ein dauerhaftes GitHub-Release ist eine Veröffentlichung und Owner-Entscheid (E15 Q11, `AGENTS.md` §8). | SC:125-128 |
| R20 | Zum Abschluss: neue Qualifikations-Epoche (Versiegeln braucht das Owner-Go) oder dauerhaft sichtbar „vor Qualifikation“. | SC:134-135 |
| R21 | Die Owner-PC-Seite (`docs/STUDIO_OWNER_PC_SETUP.md`) wird einmal von null in sauberer Umgebung durchgespielt; jede Abweichung ist ein Befund. | SC:158 (S1, Abnahme 5) |

### 6.6 Abnahme und Abschlusskriterien

| # | Regel | Quelle |
|---|---|---|
| R23 | Im Abnahme-Protokoll bekommt jede Zeile Wert, Herkunft (Datei oder Bildschirmfoto) und Urteil PASS, FAIL oder `UNKNOWN`; AK-3 steht als Tabelle n je Entscheidungsklasse, nicht vorgekommen = `UNKNOWN`. Vorlage: `docs/STUDIO_ABNAHME_PROTOKOLL.md`. | SC:165-173 |
| R25 | Abschluss 1, PLAY: AK-1 bis AK-8 erfüllt und vom Owner bestätigt. | SC:188 |
| R26 | Abschluss 2, SIMULATE: Eine vom Owner gestellte Chulane-Frage ist mit Serienplan, Ergebnis, Intervall, nachweisbarer Differenz und Gültigkeitsblock beantwortet und im Deck-Verlauf sichtbar. | SC:189-190 |
| R27 | Abschluss 3, BUILD: Ein Deck geht ohne Handarbeit aus dem Deckbauer in Partie und Serie; die Tierliste (#1369) ist vom Owner abgenommen (das Gesamtrating daraus ist seit E15 Q1 entfernt). | SC:191-192 |
| R28 | Abschluss 4, Regeln: Komponente `simulation` existiert nicht mehr (E15 Q1), durch Test gesichert; 5 und 6 Sitze technisch gesperrt oder vom Owner freigegeben; keine Zahl ohne n/N. | SC:193 |
| R29 | Abschluss 5, Doku: die Charta v2, dieses Register und keine offenen Widersprüche in den Studio-Dokumenten (in der Quelle „diese Datei, die Entscheidungsdatei“; angepasst, weil der Scope archiviert ist). | SC:194 |
| R30 | Abschluss 6, Betrieb: Einrichtung am Owner-PC aus dem Release-Paket nachvollzogen; Zustand der Bridge gegenüber dem Siegel ehrlich ausgewiesen. | SC:195-196 |

### 6.7 Abarbeitung (für alle Agents)

So wird Studio-Arbeit abgearbeitet, von jedem Agenten gleich. Die Reihenfolge der Arbeit folgt der
Charta v2 (§3 Nr. 4 und §4, Planung des Co-Leads nach `AGENTS.md` §8); die Roadmap-Phasen 0 bis 5
und der Phasenplan S0 bis S6 des archivierten Scopes sind Verlauf, ihre noch offenen Abnahmen
stehen in R7 und R18 bis R30. Claims nach E8 und `AGENTS.md` §11 (Claim-Tabelle in #1167,
Verfall 24 Stunden nach unbeantworteter Rückfrage bei einem Claim ohne gepushten Meilenstein),
Owner-Entscheide wörtlich mit Quelle (Lesart oben), Kreuz-Review der Klasse A und seine befristete
Ausnahme nach „Entscheide 2026-11-20/21“ Nr. 4; Simulation nach E15 Q1. Flächen-Karte und
Kollisionsdateien: `docs/STUDIO_AGENT_ONBOARDING.md`.

| # | Regel | Quelle |
|---|---|---|
| R31 | Ein Paket = ein Issue bzw. ein Branch = ein PR. Commits und PR-Texte sagen `Refs #N`, nie `Closes #N` (`AGENTS.md` §10). | SC:221-222 |
| R32 | Studio-Ergänzung zu `AGENTS.md` §10 (ändert §10 nicht): Texte der Oberfläche, die Aussagen über Ratings oder Simulationsergebnisse machen, sind review-pflichtig; eine solche Änderung wird wie MATERIAL behandelt. Ein Merge vor dem erforderlichen Review ist nach §10 ein Gate-Verstoß, soweit die Änderung unter die MATERIAL-Liste in §10 fällt. | SC:227-230 |
| R33 | Governance-Dateien: Änderungen an `AGENTS.md` und `CLAUDE.md` erfolgen durch Lead oder Coordinator nach `AGENTS.md` §8. Inhaltliche Änderungen an den Owner-Entscheiden (`docs/OWNER_DECISIONS_*`, einschließlich dieses Abschnitts) und an Owner-vorbehaltenen Regeln nur auf ausdrückliche Owner-Anweisung oder nach Owner-Freigabe einer vorgelegten Option; die Quelle steht im PR. Andere Agents legen Option und Empfehlung vor. Entscheide von Lead oder Coordinator innerhalb des Scopes nach `AGENTS.md` §8 bleiben unberührt und stehen im Issue oder PR; E10 (Überarbeiten überholten Wortlauts mit Begründung, Datum und Verweis) bleibt unberührt. Bei Unsicherheit wird mit dem Owner geplant (Owner, 2026-11-18). | SC:239-245 |
| R34 | Was nicht belegt ist, heißt `UNKNOWN`, nie PASS. Punkte, die eine echte Engine oder den Owner-PC brauchen, werden als solche ausgewiesen und nicht durch Tests mit nachgebautem Client als erledigt gemeldet. | SC:248-250 |

### 6.8 Nicht übernommen aus `docs/STUDIO_TARGET_SCOPE.md`

Die strittigen Einzelpunkte gelten nach Abschnitt 1 („Folge für `docs/STUDIO_TARGET_SCOPE.md`“)
weiter als nicht gebaut; Passiv-/Goldfish-Modus und Rundenlimit regelt Abschnitt 3 (E15 Q4),
Pilot-Fehlentscheidungsberichte E3 und E7 (C1), „Resolve All“ E5 (Einordnung). Zusätzlich gilt:

| # | Regel | Quelle |
|---|---|---|
| R35 | Multi-Commander über den Chulane-Fokus hinaus (B2) hat für PLAY und Serien keine Owner-Quelle, soweit E14 (BUILD), E15 Q3 (TAM-Simulation erst nach Zählung der Sim-Bereitschaft je Kohorte) und E15 Q6 (Studio-Deck-Stände als Gegner-Sitze) es nicht abdecken. | SC:272 |
| R36 | Spaltenansicht im Deckbauer: keine Owner-Quelle; als BUILD-Wunsch dem Owner vorzulegen, nicht ohne Owner-Entscheid zu bauen. | SC:273 |
