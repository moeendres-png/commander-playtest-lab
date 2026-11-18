# Commander Studio: Ist-Lage, Recherche und Optionen für den Abschluss (2026-11-18)

**Status: Entwurf zur Owner-Entscheidung, nicht verbindlich.** Nichts hier ändert eine Owner-Regel (`AGENTS.md`);
Entscheidungen stehen als Optionen mit Empfehlung. Refs #1167, #1369.

| Datei | Inhalt | Herkunft |
|---|---|---|
| `design_options.md` | SIMULATE-Empfehlung, Scope BUILD/PLAY/SIMULATE als Optionen, Roadmap, zwölf Owner-Entscheide | Planungssynthese, liest die übrigen Dateien; Code-Befunde nur gelesen, nicht ausgeführt |
| `ist_lage_cpl.md` | Live-Ist-Lage `commander-playtest-lab` (Doku gegen Messung), Stand main 8e2852d07 | Messung per `gh api`, grep, Code lesen |
| `ist_lage_dbs.md` | Live-Ist-Lage `deckbuild-studio`, Stand main 1b4305e | wie oben |
| `play_qol.md` | Recherche PLAY/QoL (16 Quellen) | Web, Abruf 2026-11-18; Zusammenfassungen maschinell, einzelne Aussagen am Original geprüft (siehe `design_options.md` §1) |
| `simulate_projects.md` | Recherche SIMULATE in anderen Projekten (29 Quellen) | wie oben |
| `simulate_methods.md` | Methodik gepaarter Serien, Mindeststandard (19 Quellen, eigene Rechenskripte) | wie oben |

Grenzen: Lizenzaussagen sind keine Rechtsberatung; „unbekannt“ heißt nicht belegt; kein Engine-Lauf, kein Test ausgeführt.
Pfade unter `/tmp/…` in den Berichten sind flüchtige Arbeitsverzeichnisse und nicht mehr abrufbar.

## Stand und Lesehinweise (Ergänzung nach Review)

- **Stand der Ist-Lage-Zahlen:** `main` 8e2852d07 und deckbuild-studio-`main` 1b4305e am 2026-11-18 gegen 16:20 UTC. Seither: `main` = de69830cf (#1511
  gemergt, die fünf P2 aus der Prüfung zu #1509 sind behoben), `play/board-click` ist als WIP-Branch gepusht, #1510 steht weiter offen
  (Einordnung im Kommentar dort). Alle anderen Zahlen als Momentaufnahme lesen.
- **Evidenz-Kennzeichen je Datei verschieden:** in `play_qol.md` und `simulate_methods.md` bedeutet `[S]` „Seite abgerufen und gelesen“;
  in `simulate_projects.md` bedeutet `[F]` „Seite abgerufen“ und `[S]` „nur Suchtreffer“. Maßgeblich ist die Legende am Kopf der jeweiligen Datei.
- **Überholte Empfehlungen:** siehe Nachtrag am Kopf von `design_options.md` (Owner-Antworten 2026-11-18).
- Namen von Agent-Sitzungen sind neutral („Agent-Session A“). `ist_lage_dbs.md` enthält Angaben aus einem privaten Repo (PR-Titel, Zahlen); vor einer
  Veröffentlichung des Repos zu prüfen.
