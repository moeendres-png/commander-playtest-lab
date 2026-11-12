# Recherche: Bedienung des Menschen-Platzes in digitalen Magic-Programmen (Vorlage für PLAY)

- **Dokument-ID:** `docs/research/PLAY_HUMAN_SEAT_UX.md`
- **Datum:** 2026-11-12
- **Kontext:** GitHub-Issue #1213 (Grundlagenermittlung für den Menschen-Platz in Commander Studio PLAY, #1169)
- **Bezugsdokumente:** `docs/STUDIO_GAME_VIEWER.md`, `docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`, `src/commander_lab/studio/static/partie.*`
- **Regeln:**
  - Reine Recherche, kein Produktcode, keine Java-Bridge-Änderung.
  - Nur öffentlich belegbare Aussagen mit Links; keine Bildschirmfotos fremder Programme im Repository.
  - Kein freies Rückgängigmachen (Undo) und kein Regelsandkasten (die Engine bleibt alleinige Regeln-Autorität).
  - Keine Sammlungs- oder Deckdaten des Owners.

---

## 1. Programmübersicht und offizielle Quellen

| Programm | Herausgeber / Projekt | Typ | Offizielle Quellen / Dokumentation |
|---|---|---|---|
| **XMage (Client)** | Open-Source-Community (`magefree`) | Desktop (Java Swing) | [XMage GitHub Repository](https://github.com/magefree/mage), [XMage Hotkeys Wiki](https://github.com/magefree/mage/wiki/Hotkeys), Client UI Source (`Mage.Client`) |
| **Forge** | Open-Source-Community (`Card-Forge`) | Desktop (Java / LibGDX) | [Forge Git Repository](https://git.cardforge.org/cardforge/forge), [Forge Wiki & Docs](https://cardforge.org/) |
| **MTG Arena** | Wizards of the Coast | Kommerziell / Desktop & Mobile | [MTG Arena Hotkeys & Gameplay Guide](https://draftsim.com/mtg-arena-hotkeys/), [Wizards Support Portal](https://mtgarena-support.wizards.com/hc/en-us) |
| **Magic Online (MTGO)** | Daybreak Games / Wizards of the Coast | Kommerziell (Windows Desktop) | [MTGO Official Game Rules & Hotkeys](https://help.mtgo.com/hc/en-us/articles/6046461937947-Keyboard-Shortcuts), [MTGO User Manual](https://www.mtgo.com/game-rules) |

---

## 2. Detaillierter Vergleich nach den sechs Kernfragen

### Frage 1: Priorität – Anzeige, Passen, Haltepunkte und Schutz vor versehentlichem Durchlaufen

| Programm | „Du bist dran“-Anzeige | Pass-Mechanismus & Hotkeys | Haltepunkte (Stops) & „Passen bis“ | Schutz vor versehentlichem Durchlaufen |
|---|---|---|---|---|
| **XMage** | Pfeil auf aktiven Spieler; leuchtender Avatar-Rahmen; Text im oberen Feedback-Panel (`[Player]: Priority`). | Button `Pass` / `OK`; Hotkey `F2` (OK/Priority); `F4` (Pass until end of turn/stack); `F9` (Pass priority until turn ends unless attacked/targeted). | Phasen-Leiste mit 10 konfigurierbaren Stopps je Zug (Upkeep bis End Step), getrennt für eigenen und fremden Zug einstellbar. | Hotkey `F3` hebt alle Skips sofort auf; Stopps auf Phasen erzwingen Halt selbst bei aktivem Auto-Pass. |
| **Forge** | Prompt-Bereich leuchtet gelb/grün; Phase-Tracker zeigt aktiven Step; Buttons werden interaktiv. | Button `OK` / `Pass Priority`; `Leertaste` für OK; `F4` für Turn-Ende; `F6` (Yield to all). | Phase-Track mit Checkboxen für jeden Einzelschritt (getrennt nach „My Turn“ und „Opponent Turn“). | Stapel-Ereignisse brechen automatische Skips ab, es sei denn, für einen spezifischen Trigger wurde explizit „Always Yield“ aktiviert. |
| **MTG Arena** | Spieler-Porträt pulsiert blau; großer Button unten rechts wechselt zu `Pass` oder `Resolve`; Phasen-Icon leuchtet. | `Leertaste` für Pass/Resolve; `Enter` für „Pass Turn“ (Soft Pass: hält bei gegnerischen Aktionen an); `Shift+Enter` (Hard Pass). | Klick auf Phasen-Symbole setzt temporären Stopp für den aktuellen Zug. „Full Control“-Modus (`Ctrl` oder `Shift+Ctrl`) erzwingt Halt bei jeder Priorität. | Soft Pass hält bei gegnerischem Cast oder Angriff an; Zündschnur/Timeout-System („Rope“) verhindert unendliches Blockieren. |
| **MTGO** | Pfeil zeigt auf aktiven Spieler; Menüleiste oben wechselt Farbe; Prompt: „Cast Spells or Activate Abilities“. | `F2` (Pass/Yield to current action); `F4` (Pass until something is on stack); `F6` (Yield all priority this turn); `F8` (Yield if no possible plays). | Phase Ladder mit 14 umschaltbaren Stopps (7 Phasen getrennt nach eigenem und gegnerischem Zug). | `F3` entfernt alle aktiven Yields sofort; Not-Halt bei neuen Objekten auf dem Stapel. |

---

### Frage 2: Ziele und Mehrfachauswahl – Zielwahl, Angreifer, Blocker, Schadensverteilung

| Programm | Zielauswahl (Spells/Abilities) | Angreifer & Blocker deklarieren | Min/Max-Anzeige & Validierung | Bestätigung |
|---|---|---|---|---|
| **XMage** | Klick auf Karten im Spielfeld/Friedhof oder Spieler-Avatar; rote Ziellinien von Quelle zum Ziel. | Klick auf Angreifer, Klick auf Zielspieler/Planeswalker; Blocker-Klick -> Klick auf Angreifer; Schadensverteilung per Schieberegler. | Text im Prompt: `Choose up to X targets (Y chosen)`, `Select at least 1`. | Button `Done` wird erst aktiv, wenn Mindestanzahl erreicht ist; `Cancel` bricht Aktion ab. |
| **Forge** | Klick auf klickbare Zielkarten; farbige Ziel-Bögen; Prompt zeigt verbleibende Zielanzahl. | Angreifer-Klick oder „All Attack“; Blocker-Zuweisung per Klick-Paarung; Schadensverteilung per Dropdown/Nummernfeld. | Prompt zeigt: `Select X targets. Currently selected: Y`. | `OK`-Button schließt Auswahl ab; ungültige Anzahlen deaktivieren Bestätigung. |
| **MTG Arena** | Legale Ziele leuchten intensiv auf (orange/blau); Pfeil folgt Mauszeiger; Zähler über den Karten. | Einzelklick tippt Angreifer nach vorne, „All Attack“-Button; Drag & Drop vom Blocker auf den Angreifer; Schadensreihenfolge per Klick-Reihenfolge. | Banner oben: `Choose 1 of 2 targets`, `Assign Combat Damage: X remaining`. | Großer blauer Button: `Submit 1 Target` bzw. `All Attack` / `Done`. |
| **MTGO** | Klick auf hervorgehobene Karten/Spieler; Pfeile verbinden Quelle und Ziele. | Klick auf Angreifer -> Dropdown/Klick auf Zielspieler; Blocker-Pfeile; manuelle Punkte-Verteilung bei Multi-Blockern. | Header-Prompt: `Select targets for [Spell] (0 of X selected)`. | Button `Done` / `OK` in der oberen Leiste. |

---

### Frage 3: Mana bezahlen – Automatisch, manuell und Abbruch

| Programm | Automatisches Tappen | Manuelles Tappen | Abbruch / Zurückrollen unvollständiger Zahlungen |
|---|---|---|---|
| **XMage** | Auto-Mana-Engine (Standard): XMage wählt optimale Farbkombination aus Ländern und Pool automatisch aus. | Manuelles Anklicken von Ländern/Manaquellen vor oder während des Spruch-Casts. | `Cancel`-Button bricht Spruch-Ansage ab und enttappt zuvor im selben Schritt aktivierte Länder (sofern keine irreversiblen Effekte auftraten). |
| **Forge** | Option `Auto-Pay Mana` (Checkbox in Einstellungen, standardmäßig aktiv); ermittelt Kombination automatisch. | Manuelles Anklicken von Manaquellen; Anzeige des Manapools im Seitenpanel. | `ESC` oder `Cancel` im Prompt bricht Bezahlung ab und setzt Zustand vor Beginn des Castings zurück. |
| **MTG Arena** | Auto-Tapper zeigt visuelle Vorschau (betroffene Länder leuchten weiß auf, bevor der Spruch losgelassen wird). | Länder können manuell getappt werden; Mana landet in sichtbarer Blase („Floating Mana“) neben dem Avatar. | `Z`-Taste oder `Cancel`-Button bricht unfertige Aktionen vor Bestätigung ab (solange der Spruch noch nicht auf den Stapel gelegt wurde). |
| **MTGO** | Teil-Automatik (Spruch anklicken -> MTGO fragt nach Farboptionen) oder manuelles Vorab-Tappen. | Manuelles Tappen in den Pool; Pool-Symbole werden per Klick verbraucht. | `ESC` oder `Cancel` bricht Ansage ab, solange keine irreversiblen Manafähigkeiten (z. B. Selvala, Chromatic Sphere) involviert sind. |

---

### Frage 4: Stapel und ausgelöste Fähigkeiten – Darstellung, Reihenfolge und Durchwinken

| Programm | Darstellung des Stapels | Reihenfolge bei mehreren gleichzeitigen Triggern | Durchwinken gleicher Auslöser (Auto-Yield) |
|---|---|---|---|
| **XMage** | Horizontaler oder vertikaler Bereich („Stack“); Karten überlappen chronologisch; Pfeile zeigen Ziele an. | Dialogfenster: `Choose order of triggered abilities on the stack`; Klick bestimmt Reihenfolge. | Rechtsklick auf Fähigkeit: `Always yield`, `Always yes`, `Always no`; Einstellung `Auto-order triggers`. |
| **Forge** | Eigene Stack-Komponente am Bildschirmrand; Karten liegen gestapelt von oben nach unten. | Dialog zur manuellen Anordnung ausgelöster Fähigkeiten mit Pfeiltasten/Klicks. | Kontextmenü-Option `Always Yes` / `Always Yield` für repetitive Trigger (z. B. Soul Warden). |
| **MTG Arena** | Dreidimensional überlappender Stapel in der Bildschirmmitte; jeder Zauber liegt physisch auf dem vorherigen. | Einstellung `Auto-order triggered abilities` (standardmäßig ein); wenn aus: Dialogfenster zur Reihenfolge. | Option `Resolve All` winkt alle aktuellen Stapelobjekte ohne Zwischenhalt durch; kein persistentes „Always Yield“. |
| **MTGO** | Eigenes verschiebbares Stack-Fenster; jede Karte zeigt Name, Quelle und ausgewählte Ziele. | Trigger-Auswahlfenster: Spieler klickt Fähigkeiten in der gewünschten Auflösungsreihenfolge an. | Rechtsklick: `Always yield to this ability`, `Yield until end of turn`, `Save targets`. |

---

### Frage 5: Mehrspieler (3 bis 6 Spieler) – Tischansicht, Angriffsziele und Protokoll

| Programm | Tischansicht bei 3–6 Spielern | Angriffsziele (Player vs. Planeswalker) | Protokollierung (Game Log) |
|---|---|---|---|
| **XMage** | Polygonales / geteiltes Layout; Schlachtfelder werden in Zonen skaliert; Avatare der Gegner oben/seitlich. | Eigener Dialog oder Klick-Zuweisung: Klick auf Angreifer, dann Klick auf spezifischen Gegner oder dessen Planeswalker. | Chronologisches Textprotokoll im Chatfenster; Aktionen sind farblich nach Spielern codiert. |
| **Forge** | Bis zu 8 Spieler unterstützt; Schlachtfelder werden in einem Ring/Raster angeordnet. | Dropdown oder Klick-Zielwahl pro angreifender Kreatur. | Chat-/Ereignis-Panel mit vollständiger Historie aller Phasen und Aktionen. |
| **MTG Arena** | **UNKNOWN / Nicht unterstützt:** MTG Arena unterstützt nativ nur 2 Spieler (1v1). Kein 4-Player-Commander. | Nur 1 Gegner (bzw. dessen Planeswalker). | Kein persistentes Textprotokoll im Spielbildschirm (nur visuelle Historie am linken Rand). |
| **MTGO** | 4-Player-Tische: Vier getrennte Quadranten/Rechtecke; verkleinerte Kartendarstellung. | Klare Farb-Pfeile vom Angreifer auf den gewählten Zielspieler oder Planeswalker. | Vollständiges Spielprotokoll im Chat; listet Phasenwechsel, Manazahlungen und Ziele präzise auf. |

---

## 3. Analyse für Commander Studio: Reine Anzeige vs. Ausschluss wegen Regelwissen

Gemäß `AGENTS.md` und `docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md` gilt das verbindliche Architektur-Prinzip:
> **Single Source Rules Authority:** Die Rules Engine (XMage) entscheidet alleine über Legalität, Kosten, Timing, Stapel und Priorität. Der Front-End-Client rechnet keine Regeln aus, besitzt kein zweites Regelsystem und filtert keine Aktionen eigenmächtig.

### Was ist reine Anzeige (im Front-End machbar, KEIN Regelwissen erforderlich):

1. **Optionen rendern:**
   - Die Engine sendet im Game-State eine Liste autoritativer Entscheidungs-Optionen (`DecisionOption`), z. B. `PASS`, `CAST(CardId)`, `ACTIVATE(CardId, AbilityIndex)`.
   - Das Front-End stellt diese Optionen als klickbare Buttons oder als leuchtende Handkarten dar. Klickt der Benutzer, wird exakt die Option-ID oder der Index an den Server übermittelt (`POST /api/games/{id}/decision { "choice_index": 2 }`).
2. **Prioritäts-Sentinel („Du bist am Zug“):**
   - Wenn der Engine-Request an den menschlichen Sitz adressiert ist (`decision_request.seat == human_seat`), schaltet die Web-UI in den aktiven Zustand und schaltet die Interaktionselemente frei.
3. **Ziele hervorheben:**
   - Die Engine liefert bei Zielwahlen die exakte Liste legaler Ziel-IDs (`legal_target_ids: ["perm-12", "player-3"]`).
   - Das Front-End hängt lediglich eine CSS-Klasse `.legal-target` an die entsprechenden DOM-Elemente an.
4. **Stapel und Spielverlauf:**
   - Die geordnete Liste der Stapelobjekte und das Ereignisprotokoll werden 1:1 aus dem Game-State gerendert.
5. **Auto-Forward / Geschwindigkeitsregler (Client-Orchestrierung):**
   - Solange die KI-Gegner agieren und keine Entscheidung für den Menschen vorliegt, läuft die Partie mit der vom Benutzer eingestellten Geschwindigkeit ab (z. B. 500 ms pro Schritt).

### Was scheidet STRIKT aus (erfordert Regelwissen und ist im Client verboten):

1. **Clientseitige Berechnung legaler Angreifer und Blocker:**
   - Ob eine Kreatur angreifen oder blocken darf (Einsatzverzögerung, Vigilance, Fliegen, Bedrohlich, Schutz, Kosten wie Propaganda), darf **niemals** im JavaScript berechnet werden. Die Optionen müssen von der Engine kommen.
2. **Clientseitiger Auto-Tapper für Mana:**
   - Eine Vorabberechnung im Browser, welche Länder für einen Spruch getappt werden müssen, erfordert tiefes Regelwissen (Manakosten, Farbreduktionen, Manafähigkeiten, Restriktionen). Im Studio wählt der Spieler entweder eine von der Engine autorisierte Mana-Option oder die Engine wickelt Mana-Zahlung intern autoritativ ab.
3. **Clientseitige Ziel-Gültigkeitsprüfung:**
   - Hexproof, Shroud, Ward, Schutz vor Farben oder Timing-Restriktionen dürfen nicht im Front-End interpretiert werden.
4. **Freies Rückgängigmachen (Undo / Sandbox-Rollback):**
   - Ein beliebiges Zurückrollen von Spielzügen („Take back“) erfordert Save-State-Management und Regel-Rückabwicklungen im Engine-Kern und ist im Projekt explizit untersagt (`docs/OWNER_DECISION_STUDIO_BUILD_PLAY_SIMULATE_20261110.md`).

---

## 4. Empfehlung: „Kleinste brauchbare Bedienung“ (Minimal Viable Human Seat UX)

Die kleinste brauchbare Bedienung für Commander Studio PLAY (#1169) basiert direkt auf der vorhandenen Zuschauer-Ansicht `partie.html` und ergänzt diese um eine minimale Entscheidungsleiste.

| Nr. | Bedien-Element | Beschreibung | Bediente Engine-Entscheidungsklasse |
|---|---|---|---|
| **1** | **Prioritäts-Aktionsleiste** | Fester Balken am unteren Bildschirmrand: Großer grüner `Pass`-Button sowie Buttons für alle legalen Aktionen (`Spruch wirken`, `Fähigkeit aktivieren`). Karten auf der Hand, die in den legalen Optionen enthalten sind, erhalten einen goldenen Rahmen und sind direkt anklickbar. | `PRIORITY_ACTION` (Passen oder Aktion wählen) |
| **2** | **Zielauswahl-Overlay** | Erscheint, wenn die Engine eine Zielwahl verlangt: Banner mit Text `Wähle Ziel für [Karte] (X von Y gewählt)`. Nur die von der Engine übermittelten `legal_target_ids` sind klickbar. Sobald die Mindestanzahl erreicht ist, wird `Ziele bestätigen` aktiv. | `SELECT_TARGETS` (Auswahl aus legaler Zielmenge) |
| **3** | **Kampf-Zuweisung** | Bei Angreifer-Deklaration: Klick auf eigene Kreatur, Klick auf Ziel (Gegner-Avatar oder Planeswalker aus den Engine-Optionen). Button `Angriff bestätigen` übermittelt das Mapping. Bei Blockern analog (Klick auf Blocker -> Klick auf Angreifer). | `DECLARE_ATTACKERS`, `DECLARE_BLOCKERS` |
| **4** | **Trigger-Reihenfolge-Modal** | Einfache Liste mit Drag & Drop oder Klick-Nummerierung, um gleichzeitig auslösende Fähigkeiten auf den Stapel zu legen. Button `Reihenfolge bestätigen`. | `ORDER_TRIGGERED_ABILITIES` (Stapel-Anordnung) |
| **5** | **Mehrfachauswahl / Mana-Entscheidung** | Schlichtes modales Auswahlfenster (Radio-Buttons oder Kacheln) für diskrete Entscheidungen (z. B. Farbwahl bei Mana, Modus-Wahl bei modalen Sprüchen wie „Wähle zwei“). | `MODAL_CHOICE`, `MANA_PAYMENT_ALTERNATIVE` |
| **6** | **Tempo- & Auto-Run-Schalter** | Schieberegler für KI-Schrittgeschwindigkeit (z. B. 100 ms bis 2000 ms) sowie Checkbox `Auto-Pass, bis ich am Zug bin`. Lässt Züge anderer Spieler flüssig durchlaufen, bis die Engine wieder den Menschen adressiert. | Client-Orchestrierung (keine Engine-Entscheidung) |
