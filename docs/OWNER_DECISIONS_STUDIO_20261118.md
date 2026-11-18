# Owner-Entscheide: Commander Studio, Stand 2026-11-18

**Zweck.** Diese Datei schreibt die Owner-Antworten vom 2026-11-18 zum Optionspapier
„Studio-Abschluss“ und die Owner-Entscheide vom 17.11. (PLAY) und 18.11. (Tierliste) verbindlich
fest. Sie ergänzt `docs/OWNER_DECISIONS_STUDIO_20261112.md` und
`docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md` und ersetzt dort nur die Zeilen, die
unten unter „Was aufgehoben, geändert oder neu ist“ stehen. Der verbindliche Scope je Bereich, der
daraus folgt, steht in `docs/STUDIO_SCOPE.md`. Nur Governance: Code, Engine-Pin, versiegelte
Nachweise, kanonische Decks und Bestand ändern sich mit dieser Datei nicht.

**Lesart.** Jeder Punkt nennt seine Quelle. Owner-Wortlaut steht in Anführungszeichen und ist
unverändert übernommen. Was keine Owner-Aussage ist, sondern eine Einordnung der Lead-Sitzung,
ist als solche gekennzeichnet. Eine spätere Owner-Anweisung geht vor; dann wird diese Datei
fortgeschrieben, nie gelöscht (`AGENTS.md` §9).

**Quellen.**
- Owner-Antworten 2026-11-18 (O1, O3, O4, O6), festgehalten in #1167, Kommentar 6985613347.
- Owner-Aussagen 2026-11-18 in der Lead-Sitzung zu Scope und Empfehlungen (Abschnitt 1, letzte
  beiden Zitate), vom Lead in PR #1514 übermittelt.
- Owner-Entscheide PLAY 2026-11-17, festgehalten in #1167, Kommentar 6953814299.
- Owner-Entscheide Tierliste 2026-11-18, festgehalten in #1369, Kommentar 6967718221.
- Optionspapier `docs/research/studio_abschluss_20261118/design_options.md` mit
  `simulate_methods.md` (Entwurf in PR #1512, Zweig `docs/studio-abschluss-optionen`; zum Zeitpunkt
  dieser Datei nicht auf `main`). Es ist keine Owner-Quelle. Seine Teile B-X1, „Deck-Snapshot v1“
  und O2 sind durch O1 verworfen. Was hier aus ihm gilt, ist unten wörtlich oder inhaltlich
  übernommen, damit diese Datei für sich allein trägt.

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
- „GO für alle deinen Empfehlungen“

**Folge für `docs/STUDIO_TARGET_SCOPE.md`.** Verbindlich ist `docs/STUDIO_SCOPE.md`; das Ersetzen
des Zieldokuments war Empfehlung §D.1 des Optionspapiers und ist vom GO gedeckt. Für die dort
genannte Freigabe „S-B, O1-A bis O4-A“ gibt es keine belegte Owner-Quelle. Falls der Owner diese
Optionen in einer anderen Sitzung freigegeben hat, entscheidet er die strittigen Einzelpunkte
(Liste in `docs/STUDIO_SCOPE.md`) neu; bis dahin wird aus ihnen nichts gebaut.

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

Simulationsergebnisse dürfen in die Tierliste fließen, aber erst, wenn das Reife-Tor G-SIM erfüllt
ist **und** der Owner das konkrete Gewicht und die Darstellung bestätigt hat. Bis dahin gilt:

- Das Gewicht `simulation` bleibt 0 in Standard und allen Voreinstellungen, in Code und Test
  (`tests/unit/test_studio_simulation_weight_zero.py`). Ein Agent hebt es nicht an.
- K5 gilt unverändert: Die gemessenen Partie-Ergebnisebenen (Tempo, Ausspielquote,
  Standfestigkeit, Sieg-Abstand, Großpod) tragen kein Gewicht, auch nicht im Gesamtrating; sie
  werden nur getrennt angezeigt.
- Ergebnisse aus SIMULATE erscheinen bis dahin nur im Deckbauer und im Deck-Verlauf als eigene
  Kohorte `SIMULATED_RESULT` (`docs/STUDIO_SCOPE.md`).

**G-SIM, Vorschlag der Lead-Sitzung.** „Perfekt“ ist nicht prüfbar; G-SIM ersetzt es durch
messbare Größen. Die Kriterien und Schwellen sind ein Vorschlag, den der Owner bei der Prüfung
bestätigt oder ändert. G-SIM ist erfüllt, wenn alle sieben Punkte belegt sind:

| # | Kriterium | Messung |
|---|---|---|
| 1 | Regelkonformität | Jedes Ergebnis weist den Bridge-Zustand aus. Freigabe nur mit einer qualifizierten, versiegelten Epoche, die den eingesetzten Stand von `engine-bridge/` abdeckt, oder mit einer ausdrücklichen Owner-Annahme „vor Qualifikation“ je Freigabe. |
| 2 | Pilotgültigkeit | Manuelle Stichprobe von Pilot-Entscheidungen: mindestens 200 Entscheidungen aus mindestens 20 Partien, mehrere Decks. Die Quote klarer Fehlentscheidungen hat eine Wilson-Obergrenze (95 %) von höchstens 10 % (Schwelle: Vorschlag). Diese Stichprobe ist eine Bewertung einzelner Pilot-Entscheidungen und fällt unter die Einfrierung S2; O4 hob S2 nur für die Zählung auf. Sie braucht deshalb eine eigene Owner-Bestätigung (Aufhebung von S2 für diese Stichprobe), bevor sie gemacht wird. Dazu die Zählung der Pilot-Auslassungen je Serie (E3). |
| 3 | Sitzbalance | Sitzrotation je Block. Die simulierte Sitzkurve steht neben der Referenz: Playgroup, Vierer-Partien, Sitz 1 bis 4 = 29,1 / 25,7 / 23,6 / 21,5 %, n = 300.240, Stand 16.11.2026, Casual, Selbstangabe, Sitz nicht randomisiert, Unentschieden ausgeschlossen. |
| 4 | Statistik | Der Mindeststandard unten (zwölf Punkte) ist erfüllt, jeder Punkt mit Test oder Beispielergebnis. |
| 5 | Nutzen | Mindestens eine echte Chulane-Frage ist beantwortet, und der Owner hat das Ergebnis als sinnvoll bestätigt. |
| 6 | Kohorte | Eigene Kohorte `SIMULATED_RESULT`, nie mit Nutzungs- oder Turnierdaten addiert; eigene Achse mit eigener Konfidenz. |
| 7 | Owner | Der Owner bestätigt Gewicht und Darstellung. Danach entsteht ein eigenes Design für den Weg in die Tierliste. |

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
Auslassungen); die manuelle Stichprobe gehört nur zu G-SIM Punkt 2 und steht unter dem dortigen
Vorbehalt.

### E3 (O4): Pilot-Auslassungen dürfen gezählt werden

Das Zählen von Pilot-Auslassungen ist zulässig: wie oft die Engine eine Option anbot (etwa Land
spielen, Commander wirken) und der Pilot sie bis Zug T nicht nahm, als Zählung n/N aus dem
Protokoll. Die Einfrierung neuer Pilot-Mikro-Messreihen (S2, 2026-11-10) ist nur dafür
aufgehoben: reine Zählung aus vorhandenen Protokollen, keine Bewertung einzelner Entscheidungen
als Produkt, keine Änderung an einem Piloten.

### E4 (O6): Abnahme-Definition PLAY

Angenommen ist die Abnahme-Definition AK-1 bis AK-8 (Optionspapier §C.2). Sie schärft den Satz aus
`docs/STUDIO_ROADMAP_20261112.md`: Der Owner spielt eine ganze Partie mit Chulane gegen drei
KI-Sitze am eigenen Rechner ohne Zeitlimit.

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
arbeite weiter nach deinen Empfehlungen“, „GO für alle deinen Empfehlungen“), angenommen
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

## 3. Was aufgehoben, geändert oder neu ist

| Bisher | Jetzt | Quelle |
|---|---|---|
| Optionspapier: B-X1 („deckbuild-studio kanonisch“), Vertrag „Deck-Snapshot v1“, Frage O2 (Vorschläge, nie beschlossen) | verworfen; BUILD bleibt hier (E1) | O1 |
| B11 (`OWNER_DECISIONS_STUDIO_20261112.md`): Simulation zählt nicht in die Tierliste | bedingt: Gewicht 0, bis G-SIM erfüllt ist und der Owner Gewicht und Darstellung bestätigt (E2) | O3 |
| S2 und Einfrierung neuer Pilot-Mikro-Messreihen (2026-11-10) | nur für die reine Zählung von Pilot-Auslassungen aufgehoben (E3) | O4 |
| K4 „keine Kombination“, E1.a „Rubrik-Gewicht 0“, Ablehnung einer modellgestützten Einschätzung, A4 „nur objektive Daten“ | nur für das neue, gekennzeichnete Gesamtrating aufgehoben (E6) | Owner 18.11., angenommen 18.11. |
| PLAY „fertig“, wenn der Owner eine ganze Partie spielt (`STUDIO_ROADMAP_20261112.md`) | Abnahme nach AK-1 bis AK-8 (E4) | O6 |
| 5 und 6 Sitze: nur durch Regel nicht freigegeben; Code nimmt 2 bis 6 Sitze an (`studio/launch.py`: `MIN_SEATS, MAX_SEATS = 2, 6`) | neu: technische Sperre für 5 und 6 Sitze, nur mit ausdrücklichem Schalter, standardmäßig aus. Im Studio-Startpfad kommt sie mit dem PR „Brett-Klick/Sitz-Sperre“ (PLAY P0), in den Serien-Routen mit dem SIMULATE-Zweig. Bis dahin ist sie nicht durchgesetzt. | Empfehlung O11 des Optionspapiers, Owner-GO 2026-11-18 |
| `docs/STUDIO_TARGET_SCOPE.md` als Zielumfang (PR #1510) | ersetzt durch `docs/STUDIO_SCOPE.md` | Owner 2026-11-18 (Abschnitt 1), Optionspapier §D.1 |

## 4. Gilt unverändert

- XMage ist die alleinige Regelautorität (`AGENTS.md` §2, A2).
- Keine Erste-, Zufalls- oder Standard-Option in produktionserreichbaren Pfaden (`AGENTS.md` §2).
- Keine Preise, kein Kaufmodus (B1, `AGENTS.md` §12).
- Jede Zahl mit n/N und Herkunft; „unbekannt“ statt 0 (A4, A5).
- Kohorten werden nie gemischt oder addiert (A5, B3).
- Chulane ist das einzige aktive Owner-Deck (`docs/OWNER_DECK_FOCUS_CURRENT.md`).
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
- Bezahldienste.
