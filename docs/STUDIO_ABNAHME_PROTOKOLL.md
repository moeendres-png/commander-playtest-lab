# Commander Studio: Abnahme-Protokoll (Owner-PC)

Stand: 2026-11-18, Refs #1519, #1167. Ausfüllbare Vorlage für Einrichtung, PLAY-Abnahme
(AK-1 bis AK-8 nach `docs/OWNER_DECISIONS_STUDIO_20261118.md`, E4), Störfälle, Serien-Messungen und
Kreislauf. Einrichtung und Vorbedingungen: `docs/STUDIO_OWNER_PC_SETUP.md`.

> **Verbindliche Einordnung:**
> - Alle Spiel- und Serienergebnisse sind `SIMULATED_RESULT` und **kein Qualifikationsbeleg**
>   (`docs/STUDIO_SCOPE.md`, `AGENTS.md` §4).
> - **Jede Zahl braucht `n/N` und Herkunft** (Dateipfad, JSON-Ausgabe oder Bildschirmfoto).
> - **Fehlendes oder nicht Vorgekommenes bleibt `UNKNOWN`**, niemals `0` und niemals `PASS`.

---

## Block A: Einrichtung (zu prüfen am PC)

| Feld | Wert | Herkunft (Befehl / Datei / Screenshot) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|
| Datum / Uhrzeit | | | `UNKNOWN` |
| Betriebssystem (Windows-Version) | | | `UNKNOWN` |
| Hardware (CPU-Kerne / RAM / freier Platz) | | | `UNKNOWN` |
| Repo-Commit (`git rev-parse HEAD`) | | | `UNKNOWN` |
| Studio-Datenordner (`%LOCALAPPDATA%\CommanderStudio`) | | `scripts/studio_start.ps1` | `UNKNOWN` |
| Python-Version (`.venv\Scripts\python.exe --version`, Soll >= 3.12) | | `studio/doctor.py` | `UNKNOWN` |
| Java-Version (`java -version`, Soll >= 17) | | `studio/launch.py` | `UNKNOWN` |
| `python -m commander_lab.studio doctor --json` | | `studio/__main__.py` (`doctor`) | `UNKNOWN` |
| `python scripts/provision_engine_bridge.py --status` | | `scripts/provision_engine_bridge.py` | `UNKNOWN` |
| Bridge-JAR SHA-256 (`xmage-engine-bridge.jar.sha256`) | | `<Datenordner>\engine\` | `UNKNOWN` |
| `ENGINE_PIN.txt` vs. `config/rules_engines.json` | | `studio/launch.py` | `UNKNOWN` |
| `bridge_qualification`-Status in UI | | `partie.js` / `ui.js` | `UNKNOWN` |
| AppCDS (`python -m commander_lab.studio build-appcds`, optional) | | `studio/__main__.py` (`build-appcds`) | `UNKNOWN` |
| Start via `.\scripts\studio_start.ps1` (Server auf `127.0.0.1:8765`) | | `scripts/studio_start.ps1` | `UNKNOWN` |

---

## Block B: Drei Partien (AK-1 bis AK-8)

### Partiedaten (je Partie ausfüllen)

| Feld | Partie 1 | Partie 2 | Partie 3 |
|---|---|---|---|
| `game_id` | | | |
| Seed | | | |
| Deck-Revision (Chulane) | | | |
| Pod (`precon` / `mixed` / `optimized`) | | | |
| `bridge_jar_sha256` | | | |
| `bridge_qualification` (`ALIGNED_WITH_SEALED_EPOCH` / `BRIDGE_AHEAD_OF_QUALIFICATION` / `UNKNOWN`) | | | |
| Ergebnis / Sieger | | | |
| Wanduhr-Dauer (Minuten) | | | |
| Protokollpfad (`games\<game_id>.jsonl.gz`) | | | |
| Logpfad (`games\<game_id>.out`) | | | |

### Abnahmekriterien AK-1 bis AK-8

| # | Kriterium | Soll / Messung (`OWNER_DECISIONS_STUDIO_20261118.md` E4) | Wert (Partie 1 / 2 / 3) | Herkunft (Datei oder Bildschirmfoto) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|---|---|
| AK-1 | Drei vollständige Vierer-Partien | Chulane gegen 3 KI am Owner-PC, jede bis zum von der Engine gemeldeten Spielende (`n/N = ?/3`) | | `games\<game_id>.jsonl.gz` | `UNKNOWN` |
| AK-2 | Kein Hänger | 0 offene Entscheidungen ohne Antwortmöglichkeit; kein Neustart, keine Entwicklerkonsole | | `games\<game_id>.out` + Screenshot | `UNKNOWN` |
| AK-3 | Abdeckung Entscheidungsklassen | Anzahl `n` je Klasse (17 Klassen, Tabelle unten); nicht vorgekommene bleiben `UNKNOWN` | siehe Tabelle AK-3 | `games\<game_id>.jsonl.gz` | `UNKNOWN` |
| AK-4 | Brett-Klick + Listen-Ausweichweg | Ziel, Angreifer, Blocker, Karte aus der Hand, Fähigkeit eines Permanents per Klick; sendet nur `option_id` aus `legal_options` | | Screenshot / UI-Beobachtung | `UNKNOWN` |
| AK-5 | Verdeckte Information | Keine KI-Handkarte während der Partie sichtbar; nach Spielende aufgedeckt | | Screenshot während/nach Spielende | `UNKNOWN` |
| AK-6 | Tempo | Entscheidungen des Menschen je Partie (mit/ohne Vorspulen); Median-Wartezeit zwischen zwei eigenen Entscheidungen | | `games\<game_id>.jsonl.gz` | `UNKNOWN` |
| AK-7 | Banner Bridge-Zustand | Banner `BRIDGE_AHEAD_OF_QUALIFICATION` sichtbar (falls Bridge vor Qualifikation); nichts als versiegelt abgedeckt dargestellt | | Screenshot | `UNKNOWN` |
| AK-8 | Urteil des Owners (1 Satz je Partie) | Was hat gestört? (je Partie ein Satz) | | Kommentar im Issue | `UNKNOWN` |

### AK-3: Abdeckung der 17 Entscheidungsklassen

Quelle der 17 Engine-Klassen: `XmageFullGameDecisionController.java` / `src/commander_lab/studio/static/partie.js` (`CLASSES`). Nicht vorgekommene Klassen (`0`) sind ausdrücklich **`UNKNOWN`**, nicht bestanden.

| # | Klasse (`decision_class`) | UI-Bezeichnung (`partie.js`) | `n` (Partie 1 / 2 / 3 / Summe) | Herkunft (Protokoll) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|---|---|
| 1 | `priority` | Aktion | | | `UNKNOWN` |
| 2 | `mana_payment` | Mana zahlen | | | `UNKNOWN` |
| 3 | `choose_object` | Auswahl | | | `UNKNOWN` |
| 4 | `choose_use` | Ja oder Nein | | | `UNKNOWN` |
| 5 | `target` | Ziel | | | `UNKNOWN` |
| 6 | `declare_attacker` | Angriff | | | `UNKNOWN` |
| 7 | `declare_blocker` | Block | | | `UNKNOWN` |
| 8 | `mulligan` | Mulligan | | | `UNKNOWN` |
| 9 | `choice` | Wahl | | | `UNKNOWN` |
| 10 | `trigger_order` | Reihenfolge | | | `UNKNOWN` |
| 11 | `announce_x` | Wert für X | | | `UNKNOWN` |
| 12 | `amount` | Anzahl | | | `UNKNOWN` |
| 13 | `multi_amount` | Verteilung | | | `UNKNOWN` |
| 14 | `mode` | Modus | | | `UNKNOWN` |
| 15 | `pile` | Stapelwahl | | | `UNKNOWN` |
| 16 | `target_amount` | Zielmenge | | | `UNKNOWN` |
| 17 | `replacement_effect` | Ersatzeffekt | | | `UNKNOWN` |

---

## Block C: Störfälle (zu prüfen am PC)

| # | Störfall | Erwartung / Prüffrage | Beobachtung / Wert | Herkunft (Datei oder Screenshot) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|---|---|
| C1 | Browser-Tab neu laden (während Mensch-Entscheidung) | Seite lädt Partie-Zustand und offene Entscheidung ohne Hänger nach; kein Datenverlust im Log | | `games\<game_id>.out` + Screenshot | `UNKNOWN` |
| C2 | Seite schließen und neu öffnen (während laufender Partie) | Partie läuft im Studio-Prozess weiter (`STUDIO_GAME_VIEWER.md`) und lässt sich wieder öffnen und fortsetzen | | `games\<game_id>.out` + Screenshot | `UNKNOWN` |
| C3 | Aufgeben (`Concede`) | Partie endet sauber als aufgegeben, Protokoll wird geschlossen, KI-Hände werden nach Spielende aufgedeckt | | `games\<game_id>.jsonl.gz` + Screenshot | `UNKNOWN` |

---

## Block D: Identitätsnachweis (parallele gepaarte Serien)

> **Hinweis:** Die endgültigen Messbefehle für Block D liefert Paket #1521; bis dahin sind die
> Befehlsfelder als Platzhalter markiert. Für den vorhandenen Einzel-gegen-Batch-Vergleich (Seeds
> 1–6) existiert `python scripts/check_studio_series_identity.py` (`docs/STUDIO_GAME_VIEWER.md`).
> Ergebnis ist `SIMULATED_RESULT`, kein Qualifikationsbeleg.

| Feld | Wert | Herkunft (Befehl / Datei) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|
| Messbefehl | `[Platzhalter aus Paket #1521]` | Paket #1521 | `UNKNOWN` |
| `series_id` / `batch_id` | | | `UNKNOWN` |
| Identische `semantic_transcript_sha256` (`n/N`) | | | `UNKNOWN` |
| Wanduhr-Dauer (einzeln vs. parallel) | | | `UNKNOWN` |
| `bridge_jar_sha256` und `bridge_qualification` | | | `UNKNOWN` |

---

## Block E: Pilotblock (gepaarte Serie am Owner-PC)

> **Hinweis:** Die endgültigen Messbefehle für Block E liefert Paket #1521; bis dahin Platzhalter.
> Alle Werte sind `SIMULATED_RESULT` und kein Qualifikationsbeleg. Playgroup-Referenz für
> Sitzkurve (4er-Partien): Sitz 1–4 = 29,1 / 25,7 / 23,6 / 21,5 %, `n = 300.240`, Stand 16.11.2026
> (`docs/OWNER_DECISIONS_STUDIO_20261118.md`, G-SIM Punkt 3).

| Kennzahl | Wert | Herkunft (`games\<batch_id>.series.json` / Befehl) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|
| Messbefehl | `[Platzhalter aus Paket #1521]` | Paket #1521 | `UNKNOWN` |
| Durchsatz (Spiele/min, Kerne/RAM, `workers`, `games_per_jvm`) | | | `UNKNOWN` |
| Diskordanz (`n_discordant / N_pairs`) neben Unabhängigkeitswert | | | `UNKNOWN` |
| Paar-Streuung (Standardfehler / t-Intervall) | | | `UNKNOWN` |
| Sitzkurve Sitz 1 (`n/N`, %) | | | `UNKNOWN` |
| Sitzkurve Sitz 2 (`n/N`, %) | | | `UNKNOWN` |
| Sitzkurve Sitz 3 (`n/N`, %) | | | `UNKNOWN` |
| Sitzkurve Sitz 4 (`n/N`, %) | | | `UNKNOWN` |
| Unentschieden / Timeouts / Abbrüche / Abstürze (`n/N`, eigene Klassen) | | | `UNKNOWN` |

---

## Block F: Kreislauf Deck-Stand → Partie → Serie → Verlauf

> **Hinweis:** Beleg für den durchgehenden Weg im Studio (verknüpft mit Paket #1531).
> Serienergebnisse erscheinen ausschließlich als `SIMULATED_RESULT` im Deck-Verlauf, niemals in der
> Tierliste/im Rating (`simulation`-Gewicht = 0).

| Schritt | Prüfung | Wert (`deck_id` / `revision_id` / `game_id` / `batch_id`) | Herkunft (Datei / Screenshot) | Urteil (`PASS` / `FAIL` / `UNKNOWN`) |
|---|---|---|---|---|
| F1 | Deck-Stand im Deckbauer prüfen („Mit der Engine prüfen“) | | Screenshot | `UNKNOWN` |
| F2 | Aus Deck-Stand Partie starten („Mit diesem Stand eine Partie spielen“) | | `games\<game_id>.jsonl.gz` | `UNKNOWN` |
| F3 | Aus Deck-Stand gepaarte/Batch-Serie starten | | `games\<batch_id>.series.json` | `UNKNOWN` |
| F4 | Partie und Serie im Deck-Verlauf als `SIMULATED_RESULT` sichtbar (Tierliste unberührt) | | Screenshot | `UNKNOWN` |

---

## Block G: Dateien, die zurückgegeben werden

Checkliste für die Rückgabe nach der Abnahme-Sitzung am Owner-PC:

- [ ] Ausgefülltes `docs/STUDIO_ABNAHME_PROTOKOLL.md` (alle Blöcke A–F)
- [ ] JSON-Ausgabe von `python -m commander_lab.studio doctor --json`
- [ ] JSON-Ausgabe von `python scripts/provision_engine_bridge.py --status`
- [ ] Spielprotokolle und Logs der drei Partien (AK-1): `games\<game_id>.jsonl.gz` und `games\<game_id>.out`
- [ ] Logs eventueller Störfälle oder Hänger (Block C): `games\<game_id>.out` und `.jsonl.gz`
- [ ] Serien-Dateien aus Block D/E/F (sofern durchgeführt): `games\<batch_id>.series.json` bzw. Benchmark-JSON
- [ ] Bildschirmfotos: Preflight/Banner (`BRIDGE_AHEAD_OF_QUALIFICATION`), Spielbrett (Brett-Klick), Endansicht mit aufgedeckten KI-Händen, Deck-Verlauf
