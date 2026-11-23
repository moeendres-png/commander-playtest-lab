# Commander Studio einfach starten

Stand: 2026-11-22, Refs #1519, #1167. Für den Owner-PC (Windows); unter Linux/WSL gilt dasselbe
mit `scripts/studio_oneclick.sh`. **Auf Windows ist der Starter noch nie gelaufen: der Owner-PC
ist der erste echte Lauf** (zu prüfen am PC, `docs/STUDIO_ABNAHME_PROTOKOLL.md`).

## So startest du

1. Im Programmordner doppelt auf **`Studio starten.cmd`** klicken.
2. Lesen, was das Fenster sagt; nur bei „(J/N)“ antwortest du. Programme (Python, Java)
   installiert er nie ohne dein „J“; die Python-Pakete in `.venv` und das Engine-Paket holt er
   ohne Rückfrage, weil das der Zweck des Starters ist.
3. Am Ende steht „Alles bereit.“ oder „Es fehlt: …“, und der Browser öffnet das Studio.

Der Starter macht jedes Mal dieselben acht Schritte und überspringt, was schon fertig ist:
Python und Java prüfen, das Programm aktualisieren (nur wenn du auf `main` bist und nichts
geändert hast), die Python-Pakete einrichten, die Engine bereitstellen, die Schnellstart-Datei
der Engine bauen, die Systemprüfung, die ersten Daten importieren, das Studio starten. Beim ersten
Mal fragt er einmal, ob er eine Verknüpfung „Commander Studio“ auf den Desktop legen soll.

Nur prüfen, ohne etwas zu ändern (in einer Eingabeaufforderung im Programmordner; ob die
Schalter dort ankommen, ist am PC zu prüfen):

```bat
"Studio starten.cmd" --nur-pruefen
```

Weitere Schalter: `--ohne-start` (nur einrichten), `--ohne-update` (kein Aktualisieren),
`--pakete-neu` (Python-Pakete neu installieren), `--port 8766` (anderer Port),
`--scryfall <Datei>` (Kartendaten-Datei an anderem Ort), `--ja` (Rückfragen mit Ja beantworten;
Programm-Installationen fragt er trotzdem). Der alte Weg über `scripts/studio_start.ps1` bleibt
(`docs/STUDIO_OWNER_PC_SETUP.md`, Abschnitt 4).

## Was jedes Rot oder Gelb bedeutet

| Meldung | Bedeutung | Was du tust |
|---|---|---|
| Python zu alt oder fehlt | Ohne Python 3.12 läuft nichts. | `winget install --id Python.Python.3.12 -e`, Fenster schließen, neu starten. |
| Java fehlt oder ist zu alt | Das Studio startet, aber ohne Partien und Serien. | „J“ beim Angebot oder `winget install --id EclipseAdoptium.Temurin.17.JDK -e`, dann neu starten. |
| Nicht aktualisiert (gelb) | Anderer Zweig als `main`, geänderte Dateien, eine andere Gegenstelle als `main` von `moeendres-png/commander-playtest-lab` oder kein Netz. Der Starter fasst deine Dateien nie an. | Nichts nötig; für den neuesten Stand auf `main` wechseln. |
| „N neue Änderungen geholt“ | Er hat den neuen Programmstand geholt, zeigt bis zu zehn Betreffzeilen und startet sich neu. | Nichts nötig. Ohne Aktualisieren: `--ohne-update`. |
| Python-Pakete ohne feste Prüfsummen (gelb) | Die Lock-Datei klappte nicht; nach deinem „J“ lief der Rückfall `pip install -e ".[api]"`. | Nichts nötig zum Starten; er versucht die Lock-Datei bei jedem Start erneut. |
| Python-Pakete | Die Installation ist gescheitert. | Die Meldungen von pip lesen, Netz prüfen, neu starten. Bei kaputter `.venv`: den Ordner umbenennen (z. B. `.venv-alt`). |
| Engine fehlt | Kein geprüftes Engine-Paket. Der Starter holt es mit dem GitHub-Programm `gh`. | Einmal `winget install --id GitHub.cli -e` und `gh auth login`, dann neu starten. Sonst bietet er den Eigenbau mit Maven an (dauert lange). |
| Engine-Version passt nicht | Die Engine gehört nicht zum Pin in `config/rules_engines.json` oder antwortet nicht. Sie wird nie ungeprüft benutzt. | Neu starten; der Starter holt die passende Engine. |
| Engine älter als der Programmstand (gelb) | Die Engine-Quellen haben sich seit dem Bau der Engine geändert, und es gibt noch kein neueres Paket. | Nichts nötig; später neu starten. |
| Schnellstart-Datei (gelb) | Partien starten etwas langsamer. | Nichts nötig; der Starter baut sie beim nächsten Mal. |
| Kartendaten fehlen (gelb) | Für den ersten Import fehlt die Scryfall-Datei „Oracle Cards“. Sie wird nie automatisch geladen. | Bei scryfall.com/docs/api/bulk-data „Oracle Cards“ laden und in `%LOCALAPPDATA%\CommanderStudio\kartendaten\` legen, neu starten. |
| Erster Import nicht vollständig | `import-all` ist abgebrochen. | Meldungen lesen; beim nächsten Start versucht er es erneut. |
| Port belegt | Ein anderes Programm nutzt Port 8765. | Mit `--port 8766` starten. |
| Das Studio läuft schon | Der Starter öffnet nur den Browser und ändert nichts. | Zum Aktualisieren erst das Studio schließen (Strg+C in seinem Fenster), dann neu starten. |
| Datenordner | Kein Schreibrecht oder Ordner im Programmordner. | `COMMANDER_LAB_STUDIO_DATA` auf einen Ordner außerhalb des Programmordners setzen. |

## Was der Starter nie tut

- Er installiert keine Programme ohne dein getipptes „J“ und ändert nie Fork oder Pin der Engine.
- Er setzt nichts zurück (`reset`, `stash`, `clean`) und löscht keine Dateien von dir.
- Aus dem Netz holt er ohne Rückfrage: den neuen Programmstand (`git pull`, bei jedem Start),
  die Python-Pakete von PyPI (nur beim ersten Mal und wenn sich `requirements/lock.txt` ändert,
  jede Datei mit fester Prüfsumme; im Rückfall ohne feste Prüfsumme, dann gelb) und das
  Engine-Paket aus GitHub Actions über `gh`. Das ist alles neu gegenüber dem Handbetrieb. Nur nach deinem „J“ kommen
  winget-Installationen und der Eigenbau mit Maven dazu (Engine-Quellen und Maven-Bibliotheken).
  Keine Preise, keine Nutzungsdaten, kein Upload.
- Er gibt keine Zugangsschlüssel aus und speichert keine.
- Sammlung und Decks bleiben im Datenordner (`%LOCALAPPDATA%\CommanderStudio`), nie im
  Programmordner. Das Studio hört nur auf `127.0.0.1`.

Grundlage: Owner-Wunsch vom 2026-11-22 (Register `docs/OWNER_DECISIONS_STUDIO_20261118.md`,
E20). Code: `src/commander_lab/studio/oneclick.py`; Tests: `tests/unit/test_studio_oneclick.py`
und `tests/unit/test_studio_oneclick_static.py`.
