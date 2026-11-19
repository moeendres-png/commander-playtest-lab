# Charta PLAY: „Mit dem Deck, das ich baue oder reinstelle, Commander spielen“

Stand 2026-11-19, Lab `main` 8f46af28 (Clone, nur gelesen), Engine-Pin f4d12f6e8 (Fork nur gelesen).
Gemergt und hier berücksichtigt: #1621 (P1a), #1619 (Replay), #1623 (erzwungene KI-Pässe von der
Engine), #1633 (KI-Pause nur für sichtbare Schritte, Stufe „ohne Pause“), #1634 (neue
Entscheidungen sofort melden). Offen: #1644 (`snapshot()` ohne Tiefenkopien).
Keine Suite, keine Engine, kein Build gestartet: alle Messzahlen stammen aus den genannten Berichten
und sind älter als #1633/#1634. Aufwände sind grobe Schätzungen (Vermutung), in Agent-Tagen.

## 1. Ergebnis zuerst: die Entscheidungen

1. **PLAY ist ein Spieltisch, kein Partie-Betrachter.** Heute ist die Seite ein Zuschauer-Werkzeug mit
   angebauter Entscheidungsleiste (`partie.js:2` „Spectator view“; die eigene Hand liegt in der
   Seitenleiste, `partie.html:63-70`). Zielbild: ich unten, Gegner oben, Stapel und Ereignisse in
   der Mitte.
2. **Das Tempo-Problem ist mit #1623, #1633 und #1634 im Kern gelöst.** Die alten Kosten (727 s
   Pause, 113 s Abfragetakt je Partie, `eff_sim_play.md` §5.2) gelten nicht mehr; nachgemessen ist
   der neue Stand nicht (`UNKNOWN`, Rechenwert etwa 198 sichtbare Schritte × 0,25 s = 50 s).
   Was bleibt, sind **eigene Klicks**, nicht Wartezeit.
3. **Kleinste Version, die täglich benutzt wird („PLAY v1“), ohne Bridge-Änderung, etwa 7 bis 9
   Agent-Tage:** (a) eigene Kohorte für Mensch-Partien; (b) ein Bedienelement fürs Passen statt
   drei; (c) Tisch: Gegner auch aus eigenen Deck-Ständen, letzter Tisch gemerkt, „nochmal“;
   (d) Rückweg: Nachspiel-Blatt mit Notiz und „diese Karte ersetzen“ am Deck-Stand.
4. **Vorher spielt der Owner eine ganze Partie am PC** (Abnahme-Partien offen,
   `STUDIO_SCOPE.md:61`). Bis heute hat kein Mensch eine Partie über die Seite zu Ende gespielt;
   alle Belege sind Testskripte. Die Reihenfolge ab Paket 5 hängt an diesem Urteil.
5. **Größter Klick-Hebel nach dem Passen ist die Mana-Zahlung** (36/346, 279/1.408, 377/1.035
   Entscheidungen des Menschen je Partie, `PLAY_HUMAN_SEAT_UX.md:151,170`). Empfehlung: „Zahlung
   vorschlagen“ mit dem vorhandenen Zahlungs-Planer der Piloten, vom Menschen ausgelöst, jede
   Antwort eine von XMage angebotene Option. Braucht ein Owner-Ja (Auslegung `AGENTS.md` §2).
6. **Passen bleibt auf der Seite, Vorspulen auf den Server zu ziehen lohnt nicht mehr.** Der
   Transportverlust je Pass war der 150-ms-Takt; den hat #1634 beseitigt. Rest: POST 10,6 ms +
   GET 3,9 ms (`eff_sim_play.md` §5.1), bei 181 Pässen etwa 3 s (Rechenwert).
7. **Ein Protokolltreiber (D-3) ja, nach v1, als reine Wartbarkeits-Naht.** #1593 hing nicht an ihm
   (als Long-Poll in `play.py:1018` gebaut). Server-Sent Events sind damit unnötig.
8. **Frontend bleibt plain JS ohne Abhängigkeit, wird aber in ES-Module mit `node --test` zerlegt.**
   Das reicht für Brett, Stapel und Kampf (Klick-Bedienung, wenige hundert DOM-Knoten). Kein
   Framework, kein Canvas, kein Drag-and-drop.
9. **Live-Ereignisse aus der Engine statt aus Etiketten-Texten.** Die Bridge kann das öffentliche
   Ereignisband schon während der Partie liefern (`get_event_log` mit `after_offset`,
   `XmageFullGameJsonlBridge.java:91,535-541`); `play.py` ruft es nur am Ende (`play.py:984`).
10. **Sitze: 5 und 6 für PLAY getrennt von SIMULATE freigeben lassen, 7 und 8 zurückstellen.** 8 ist
    aufwendig: die Grenze 6 steht an mindestens sechs Stellen in Java und Python (Abschnitt 6).
11. **Replay ist fertig (#1619), kein weiterer Ausbau. Speichern/Fortsetzen und freies Rückgängig:
    nicht bauen.**
12. **Eine Gegner-KI für PLAY und SIMULATE.** Kein eigener PLAY-Pilot, kein Schwierigkeitsgrad, der
    schwächt. Profil = Deck + Stil; die Seite sagt ehrlich „Heuristik ohne Vorausschau“.

## 2. Nutzer-Kreislauf und was jeder Schritt braucht

| Schritt | Heute (belegt) | Fehlt |
|---|---|---|
| Deck bearbeiten/importieren | Deckbauer mit Ständen; Knopf übergibt `partie.html?neu=1&revision=…` (`app.js:507`, `partie.js:1801`, Test `test_studio_play_from_builder.py`) | nichts für v1 |
| Tisch stellen | Dialog: eigener Stand, „Sitz 1 selbst spielen“, 2 bis 4 Spieler (`partie.js:11`), Gegner würfeln, Pod-Knöpfe (`launch.py:41`), Stil je Sitz in 5 Stufen (`partie.js:1579-1585`), Seed | Gegner nur aus Precons: `launch.py:788-789` kennt nur `_precons()` (173 Dateien plus 2 Extras), ein eigener Stand oder ein Korpus-Deck gibt 404. Kein gemerkter Tisch. Kein gemeinsames Tisch-Objekt mit SIMULATE |
| Starten | 6,3 s bis zur ersten eigenen Entscheidung (`eff_sim_play.md` §5.1); die Seite sagt „etwa 20 Sekunden“ (`partie.js:1635`) | Text berichtigen |
| Spielen | alle 17 Klassen generisch (`partie.js:868-1104`), Brett-Klick (`boardclick.js`), Vorspulen in 3 Modi (`vorspulen.js:9-13`), Auto-Pass (`partie.js:841-859`), Stapel-Schiene und eigener Kampf-Zwischenstand (`play_p1a.js`), Aufgeben, kein Zeitlimit (`play.py:67`), Pause nur für sichtbare KI-Schritte (`play.py:139`), sofortige Meldung (`follow.js`, `web.py:2522-2523`) | weniger Klicks (Abschnitt 4), Brett-Aufbau, Kampf- und Ereignis-Sicht aus der Engine |
| Auswerten | KI-Hände nach Spielende offen (`play.py:1046`); Wiedergabe Schritt, Zug vor/zurück, Sprung zu einem Zug (`partie.html:33-41`, `replay.js`) | kein Nachspiel-Blatt, keine Notiz, kein Bezug Partie ↔ Deck-Stand außer der Deck-ID |
| Zurück in den Deckbau | nur der Navigationslink | kein „diese Karte ersetzen“, keine Markierung am Stand (`partie.js` bezieht sich nur im Start-Dialog auf einen Stand) |

## 3. Ist-Befund (kurz)

**Vorhanden und tragfähig.** Entscheidungen nur als `option_id` aus `legal_options`, serverseitig
geprüft (`play.py:1103-1105`), danach von XMage. Echt-Engine-Abdeckung über die PLAY-Routen: 13 von
17 Klassen beantwortet, 4 `UNKNOWN` (`target_amount`, `announce_x`, `amount`, `pile`;
`PLAY_HUMAN_SEAT_UX.md:148-166`). Serien-Schalter für PLAY (`play.py:1200`): KI-Frames
1.455 → 837 bei gleichem Hash (#1591).

**Befunde, die das Zielbild treffen.**
- B1 Drei sich überlagernde Pass-Mechanismen (Auto-Pass-Kästchen, Vorspulen mit 3 Modi,
  Halt-Kästchen; `partie.html:45-53`), dazu ein Tempo-Regler mit jetzt 7 Stufen (`partie.js:13`),
  den das Vorspulen selbst auf 0 stellt und zurückstellt (`partie.js:778-822`).
- B2 Zwei Zustandsformen: aufgezeichnete Frames ohne Objekt-IDs (`games.py:98-111`), offene
  Entscheidung mit IDs; die Seite rechnet um (`partie.js:621-692`). Klicken geht deshalb nur auf
  der offenen Entscheidung.
- B3 Kampf-Anzeige stammt aus zerlegten Etiketten-Texten (`games.py:148-169`, „ attacks “), nicht
  aus einem Engine-Kampfzustand. Folgefehler (Code-Lesung, nicht im Browser beobachtet):
  `partie.js:453-466` vergleicht das Angriffsziel mit sechs Namensmustern, darunter
  `Full Game Seat N` und `Full Game Seat N+1` (Zeilen 459-460); bei Ziel „Full Game Seat 3“
  werden damit zwei Sitze als angegriffen markiert.
- B4 Kohorten: Mensch-Partien tragen `data_class: SIMULATED_RESULT` (`games.py:328`), und
  `card_outcomes.py:323-371` filtert nicht nach `human_seats` (kein Treffer für „human“ in der
  Datei). Sobald der Owner spielt, zählen seine Partien in `/api/outcomes` als Pilot-Ergebnis.
- B5 Schwärzung ist eine Verbotsliste (`hand` entfernen) über Frames aus der Sicht des jeweils
  entscheidenden KI-Sitzes (`games.py:548-576`). Der Lecktest deckt Hände ab; ob jedes andere
  private Feld der Bridge (`looked_at`, `granted_library`, `revealed_by_seat`) nie in einen Frame
  gelangt, habe ich nicht belegt: `UNKNOWN`. #1644 lässt die zweite Schwärzung in `snapshot()`
  weg; das macht die erste Stelle zur einzigen.
- B6 Zwei Protokolltreiber: `play.py:808-1013` schreibt Start, Handshake, Import und Schleife neu
  und nutzt private Methoden des Runners (`play.py:815,829,836,987`); 18 `type: ignore` in der
  Datei (gezählt auf 8f46af28).
- B7 Commander-Steuer veröffentlicht die Engine nicht; die Seite zeigt „Steuer unbekannt“
  (`partie.js:615`). Angriff, Block, Anhänge, Einsatzverzögerung und Token-Merkmal fehlen im
  veröffentlichten Zustand (Felder des `XmageFullGameStateRedactor`: Name, ID, getappt, Stärke,
  Widerstand, Schaden, Marken, verdeckt).

## 4. Entscheidungen im Einzelnen

### 4.1 Mindest-Bedienung für eine flüssige Partie

| Thema | Empfehlung | Begründung | Tage | Abnahme |
|---|---|---|---|---|
| Passen | **Ein Bedienelement.** Leertaste = einmal passen; Enter = „weiter, bis etwas passiert“ (Gegner-Objekt auf dem Stapel, jede Nicht-Prioritäts-Frage, mein Zug); Umschalt+Enter = bis zu meinem Zug. Logik bleibt in `vorspulen.js` (reine Funktion, per `node` getestet); gesendet wird nur die angebotene Option `pass_priority`, jeder automatische Pass steht im Protokoll | 297 von 346 Entscheidungen sind Priorität (86 %); die vorhandenen Regeln nehmen 181 bis 226 ab (`eff_sim_play.md` §5.3). Vom Owner-Entscheid 17.11. gedeckt | 1,5 | gleiche Partie von Hand und mit „weiter“: gleicher Transkript-Hash; Test: nie eine andere Option als die angebotene |
| KI-Tempo | erledigt (#1633). Regler von 7 auf 3 Stufen kürzen (ohne Pause, 250 ms, 1 s) | 7 Stufen sind Bedienlast ohne Nutzen | 0,5 | – |
| Mana | **Zahlungs-Vorschlag** aus dem Piloten-Planer (`full_game_pilot/payment.py`), Mensch bestätigt einmal je Zauber; Abbruch über die Engine-Option `cancel_mana_payment`. Ohne eindeutigen Plan: von Hand | bis 36 % der eigenen Entscheidungen; XMage selbst hat keine Auto-Zahlung über Länder (`PLAY_HUMAN_SEAT_UX.md:54`) | 2 bis 3 | jede gesendete Option stammt aus `legal_options`; Protokoll markiert „Vorschlag“; Echt-Engine-Test |
| Angriff/Block | Auswahl am Brett vormerken, dann die Engine-Fragen je Kreatur aus dem Vorgemerkten beantworten; passt eine Antwort nicht zu den angebotenen Optionen, hält es an | die Engine fragt je Angreifer einzeln (`boardclick.js`, Kopfkommentar) | 2 | Test: sendet nur angebotene Optionen, Halt bei Abweichung |
| Stapel | Schiene bleibt; Ziele und Kontrolleur erst mit Engine-Daten (P1b) | ohne Stapel kann man nicht antworten | 0 | – |
| Commander-Schaden/-Steuer | Schaden wie heute aus der Engine; Steuer bleibt „unbekannt“ bis P1b | Regel bleibt bei XMage | P1b | Sichtprüfung |
| Mulligan | bleibt; Kontext (Zielgröße, „frei“) mit P1b | funktioniert, belegt | P1b | – |
| Zeitlimit, Pause | keins; Pause ergibt sich daraus. Sitzung überlebt Neuladen der Seite | Owner 17.11. | 0 | Störfall-Probe C des Abnahme-Protokolls |
| Rückgängig | nur, was die Engine anbietet (Zahlung abbrechen). `rollbackTurnsAllowed` bleibt aus (`XmageFullGameSession.java:212`): Zurückrollen nach gesehenen Karten bricht die verborgene Information | – | 0 | – |
| Speichern/Fortsetzen | **nicht bauen.** Ein Wiederaufsetzen durch Neu-Abspielen (gleicher Seed, gleiche Antworten) ist denkbar, aber unbelegt: das Protokoll hält Etiketten, keine wiederholbaren Antworten (`games.py:209-223`) | Owner: „wenn sinnvoll“. Erst prüfen, wenn echte Partien zeigen, dass eine Sitzung einen Neustart überleben muss | Spike 1 bis 2, Bau 3 bis 5 | – |

### 4.2 Bewertung der vorhandenen Teile

| Teil | Nutzen für „Commander spielen“ | Urteil |
|---|---|---|
| Brett-Klick | hoch | bleibt, wird Kern |
| Stapel-Schiene | hoch | bleibt |
| Sofortige Meldung (#1634), Pause nur sichtbar (#1633), Engine-Pässe (#1623) | hoch | bleiben |
| Vorspulen, 3 Modi + Auto-Pass-Kästchen + Halt-Kästchen | hoch, aber dreifach | zu einem Bedienelement (4.1) |
| Tempo-Regler mit 7 Stufen | gering | auf 3 |
| Eigener Kampf-Zwischenstand (eigene Angaben) | mittel, Notlösung | ersetzen durch Engine-Ereignisse (Paket 6) |
| Replay (#1619, `replay.js` 132 Zeilen) | gering fürs Spielen, mittel fürs Auswerten | bleibt, kein Ausbau |
| „Plan“-Knopf je Sitz (abgeleiteter Spielplan, den der Pilot nicht liest, `PILOT_STRENGTH_OPTIONS.md` §2.1) | keiner | aus dem Brett nehmen |
| KI auf allen Plätzen zuschauen | gehört zu SIMULATE | bleibt als Ansicht, nicht PLAY-Ziel |
| Berührung, Bildvergleich, KI-Erklärungen, Mensch auf anderem Sitz, Pässe auf dem Server | gering | zurückgestellt |

### 4.3 Gegner-KI

- **Qualität:** Heuristik ohne Suche, Stil nur als Gewichts-Interpolation (`PILOT_STRENGTH_OPTIONS.md`
  §1, §2.1); in PLAY fest `NEAR_OPTIMAL_HEURISTIC` (`play.py:334`). Empfehlung: derselbe Pilot wie
  SIMULATE, jede Verbesserung dort wirkt hier mit. Wie stark er gegen einen Menschen ist: `UNKNOWN`.
- **Profil am Tisch:** Deck + Stil (5 Stufen) je KI-Sitz, mit dem Tisch gespeichert.
- **Tempo ohne Qualitätsverlust:** nur Anzeige ändern, nie die Entscheidungsfolge; Nachweis je Paket
  über den Transkript-Hash (424/424 identisch als Grundlage, `eff_sim_play.md` §0). Die KI rechnet
  8 ms je Entscheidung, 8,9 s je Partie (§5.1).

### 4.4 Architektur

1. **Treiber (D-3, 3 bis 5):** öffentliche typisierte Sitzung in `engine/rules/full_game.py` (öffnen,
   nächste Entscheidung, antworten, Ereignisse ab Offset, aufgeben, Ergebnis); `play.py` behält
   Thread, Warteschlange, KI-Taktung und Long-Poll. Abnahme wie #1612.
2. **Server/Client:** Server besitzt Sitzung, Tisch-Sicht für den Mensch-Sitz, Zahlungs-Vorschlag,
   Taktung, Protokoll. Client zeichnet, ordnet Klick → `option_id`, merkt Auswahlen vor, passt
   nach der einen Regel. Transport bleibt Long-Poll mit `revision` (`play.py:1018`); unter der CSP
   unkritisch (`default-src 'self'`, `web.py:106-107`).
3. **Zustandsmodell:** die vorhandene `revision` wird zur Version einer einzigen Tisch-Sicht mit
   Objekt-IDs auch in der Historie, offener Entscheidung (`decision_id`, Klasse, Grenzen,
   `legal_options`) und Engine-Ereignissen seit der letzten Version. Sicht als Erlaubnisliste je
   Sitz statt Verbotsliste (B5), Lecktest je Zone.
4. **Frontend:** `partie.js` (1.813 Zeilen, ein globaler Zustand) in ES-Module teilen: Brett-Modell,
   Klick-Zuordnung, Makros als reine Funktionen mit `node --test` (Muster `boardclick.js`,
   `vorspulen.js`, `follow.js`, `replay.js`); dünne DOM-Schicht. Kein neues MIME-Risiko: `nosniff`
   gilt schon für die heutigen Skripte (`web.py:595`).
5. **Persistenz:** Partie-Protokoll bleibt JSONL.gz. Neu: Tabelle `play_session` (Spiel-ID,
   Stand-ID, Deck-Hash, Tisch, Seed, Sitz, Ergebnis, Dauer, eigene Klicks, JAR-SHA, Bridge-Zustand)
   und `play_note` (Spiel, Karte, Markierung, Text). Datenklasse `PLAYED_GAME`, nie in einer Zahl
   mit `SIMULATED_RESULT`. KI-Hände liegen lokal im Protokoll und werden erst nach Spielende
   ausgeliefert (unverändert).
6. **Anbindung:** ein `TableSpec` (Sitze, Deck-Verweis als Stand, Precon oder Korpus-Kopie, Stil,
   Seed-Regel) für PLAY und SIMULATE: „diesen Tisch spielen“ und „diesen Tisch simulieren“ starten
   aus demselben Objekt mit demselben Deck-Hash.

## 5. Paket-Schnitt, Reihenfolge, Abnahme

| # | Paket | Tage | Gate | Abnahme |
|---|---|---|---|---|
| 0 | Owner spielt eine Partie auf dem heutigen Stand | 0, Owner 1 bis 2 h | – | AK-1 bis AK-8 je PASS/FAIL/`UNKNOWN`, ein Satz „was störte“; Wartezeit und Klicks neu gemessen |
| 1 | Kohorte: `PLAYED_GAME`, Filter in `card_outcomes` | 0,5 | Tests | Test fällt ohne Filter |
| 2 | Bedienung: ein Pass-Element mit Tasten, Regler auf 3 Stufen, Starttext | 2 | Tests, Hash | 4.1 Zeilen 1 und 2 |
| 3 | Tisch: Gegner aus eigenen Ständen, Tisch merken, „nochmal“, `TableSpec` | 2 | Tests | zwei eigene Decks gegeneinander starten |
| 4 | Rückweg: Nachspiel-Blatt (gezogen, gewirkt, auf der Hand geblieben aus Engine-Ereignissen und letztem Frame), Notiz, „ersetzen“ → Sprung in den Tausch-Dialog des Stands | 3 bis 4 | Tests | Markierung erscheint am Stand im Deckbau |
| – | **PLAY v1 fertig** (1 bis 4) | **7 bis 9** | | Abschnitt 7 |
| 5 | Mana-Vorschlag, Kampf-Vormerken | 4 bis 5 | Echt-Engine-Test, Owner-Ja | 4.1 |
| 6 | Brett neu (ich unten, Gegner-Streifen, Live-Ereignisse aus `get_event_log`), ES-Module | 5 bis 8 | Tests | 6 Sitze ohne Scrollen bei 1080p |
| 7 | D-3 Protokolltreiber | 3 bis 5 | MATERIAL | #1612 |
| 8 | P1b: Steuer, Kampf-Sicht, Anhänge, Mulligan-Kontext | 4 bis 6 | Studio-Bridge-Gate `BEHAVIOUR` | Referenzsatz-Hash gleich |
| 9 | 5/6 Sitze für PLAY | 6 bis 10 | Owner-Freigabe | Abschnitt 6 |

Kollisionen: Pakete 1 bis 4 berühren `play.py` kaum; #1644 ändert `snapshot()` und sollte vor
Paket 4 gemergt sein. `partie.*` hat einen Halter (#1167), Pakete 2 und 6 brauchen den Claim.

## 6. Mehrspieler 2 bis 6 und 8

- **Engine:** `CommanderFreeForAllType.maxPlayers = 10` im Fork (Zeile 16). **Bridge:**
  `MAX_PLAYERS = 6` (`XmageFullGameSession.java:43`). **Python:** `full_game.py:278,1173`,
  `models.py:224-225`, Replay-Band nur bis 5 (`tape.py:49,58,98`). **Studio:** gesperrt auf 4
  (`launch.py:37`, `partie.js:11`); höchstens 5 Gegner (`web.py:253,271`).
- **5/6 für PLAY:** kein frischer Echt-Lauf auf dem heutigen Stand; Regelkorrektheit am Pin
  `UNKNOWN` (`SEATS_5_6_QUALIFICATION_PLAN.md` §1). Empfehlung: getrennte Freigabe „PLAY 5/6“ auf
  Phasen 0, 2, 3 und 4 des Plans (Festlegungen, je eine Echt-Partie, Regelfall-Tests samt
  Leck-Test je Sitz, Laufzeit), sichtbar als „nicht qualifiziert“; SIMULATE 5/6 braucht zusätzlich
  Phase 5. Die Freigabe trifft der Owner.
- **Dauer:** historisch 4 → 6 Sitze 1.892 → 4.511 Entscheidungen (n = 1, verschiedene Pods, selbe
  Quelle §3). Für den Menschen heißt das mehr Prioritäts-Fragen: Paket 2 ist Voraussetzung.
- **Brett:** heute zweispaltiges Raster gleicher Felder (`partie.css:12-14`): 6 Sitze = 3 Reihen,
  8 = 4, also Scrollen. Paket 6 löst das mit Gegner-Streifen.
- **7/8:** zurückstellen. Nötig wären eine Bridge-Änderung unter Gate, alle Grenzen oben, das
  Replay-Band, die Pilot-Policy 2 bis 6 und ein neuer Owner-Entscheid statt des 6er-Maximums:
  geschätzt 4 bis 6 Tage zusätzlich zu Paket 9, Spieldauer ungemessen.

## 7. „Fertig“ für PLAY v1

1. Vom Stand im Deckbau zur ersten eigenen Entscheidung in höchstens 2 Klicks und 10 s.
2. Eine Vierer-Partie gegen drei KI endet ohne Hänger; eigene Klicks je Partie und Wartezeit
   stehen im Nachspiel-Blatt (Zielwerte nach Paket 0; Vorschlag: Median unter 1 s Wartezeit, wenn
   kein Gegner etwas Sichtbares tut).
3. Nach Spielende ein Blatt mit Ergebnis, Notiz und Karten-Markierungen; „ersetzen“ führt in den
   Deckbau zum selben Stand.
4. Gegner aus Precons und eigenen Ständen; kein Wert der Mensch-Partien in einer Simulationszahl.

## 8. Risiken und Abbruchkriterien

- Paket 0 zeigt ein anderes Hauptproblem (Hänger, Lesbarkeit): dann zuerst das, Pakete 2 bis 4 neu ordnen.
- Das eine Pass-Element ändert einen Transkript-Hash: zurück auf den heutigen Stand, Ursache klären.
- Mana-Vorschlag ohne Owner-Ja: entfällt, Paket 5 nur Kampf-Vormerken.
- Ein Paket überschreitet sein Budget um mehr als 50 %: anhalten, neu schneiden.

## 9. UNKNOWN

Bedienbarkeit durch einen Menschen (keine Partie gespielt); Wartezeit und Klicks nach
#1633/#1634 (nicht nachgemessen); Spielstärke der KI gegen Menschen; vier Entscheidungsklassen ohne
Echt-Beleg; ob `get_event_log` während der Partie über die PLAY-Sitzung die erwarteten Ereignisse
liefert (nur Quelltext gelesen); Vollständigkeit der Schwärzung jenseits der Hand (B5); Stabilität
der Objekt-IDs über zwei Läufe (für ein Fortsetzen); Laufzeit und Regelkorrektheit bei 5 bis 8
Sitzen; Verhalten am Windows-PC.

## 10. Owner-Fragen (mit Empfehlung)

1. Darf ein vom Menschen ausgelöster Zahlungs-Vorschlag des Piloten-Planers Mana-Fragen beantworten? **Ja**, markiert im Protokoll.
2. Gegner aus dem Korpus in v1 oder später? **Später**; v1 mit Precons und eigenen Ständen.
3. 5/6 Sitze für PLAY getrennt von SIMULATE freigeben, sichtbar „nicht qualifiziert“? **Ja, nach Paket 9**; 7/8 zurückstellen.
4. Speichern/Fortsetzen endgültig streichen? **Zurückstellen**, nach zehn echten Partien neu fragen.
5. Wann spielt der Owner die erste Partie (Paket 0)? **Vor Paket 2**, weil ihr Urteil die Reihenfolge ab Paket 5 bestimmt.
