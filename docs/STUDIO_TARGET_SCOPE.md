# Commander Studio — Best-Of-All-Worlds Zielumfang

> **Überholt:** Owner 2026-11-18: „Bitte nach deinen neuen hier ausgemachten scope arbeiten und das
> so hinterlegen“ (wörtlich in PR #1514, Kommentar 6987989133) und „hier mein GO für alle deinen
> Empfehlungen“ (vom Lead wörtlich übermittelt, ohne eigene Kommentar-ID). Der verbindliche Scope steht in
> `docs/STUDIO_SCOPE.md`, die Owner-Entscheide in `docs/OWNER_DECISIONS_STUDIO_20261118.md`. Für die
> Freigabe „S-B, O1-A bis O4-A“ unten gibt es keine belegte Owner-Quelle; falls der Owner sie in
> einer anderen Sitzung gegeben hat, entscheidet er die strittigen Punkte (Liste in
> `docs/STUDIO_SCOPE.md`) neu, bis dahin wird aus ihnen nichts gebaut. Diese Datei bleibt als
> Verlaufsdokument erhalten.

Stand: 2026-11-18 (Owner-Freigabe: Option S-B, O1-A, O2-A, O3-A, O4-A), Refs #1167, #1169, #1172, #1251, #1265, #1369.
Diese Seite definiert den verbindlichen Zielumfang für **BUILD**, **PLAY**, **SIMULATE**,
**Engine-Durchsatz**, **Release-Packaging** und **Environment-Diagnose** in
`moeendres-png/commander-playtest-lab` (ohne `moeendres-png/deckbuild-studio`, per Owner-Entscheid
ausdrücklich nicht im Umfang). Governance und Verbindlichkeit richten sich nach `AGENTS.md`;
Git, Tests und versiegelte Belege sind Source Truth (`AGENTS.md` §3).

## Zuständigkeitsgrenze & Arbeitsteilung: Tierliste vs. Simulator/Studio

- **Tierliste (`#1369`, Gesamtrating, Bracket-/Nutzungsachsen, Rater-Kalibrierung — eigene parallele Lane):**
  bleibt ein eigenes Arbeitspaket getrennt vom Simulator. Simulationsergebnisse fließen **nicht** in
  den Tierliste-Gesamtscore (`simulation`-Gewicht bleibt überall `0`, `AGENTS.md` §1, Option O2-A). *(Überholt 2026-11-20, E15 Q1: Gesamtrating und Gewicht sind entfernt.)*
- **BUILD, PLAY, SIMULATE, Bridge & Bereitstellung:** folgen den Meilensteinen dieses
  Zielumfangs. XMage bleibt die alleinige Regel-Autorität (`AGENTS.md` §2, Option O1-A); in BUILD
  sind ausschließlich exakte kombinatorische Zug-/Manarechnungen ohne Regelbehauptung zulässig.
  Alle simulierten Resultate werden strikt als `SIMULATED_RESULT` mit voller Herkunft
  (`engine_commit`, `bridge_jar_sha256`, `bridge_qualification_state`, Seeds, Pod, Intervall)
  ausgewiesen.

## 1. Governance, Bereitstellung & Diagnose (`#1167`, `#1172`)

- **Release-Artifacts inkl. Bridge-JAR (`.github/workflows/release-artifacts.yml`):** Baut
  `engine-bridge` gegen den gepinnten XMage-Commit aus `config/rules_engines.json`
  (`primary_engine.commit`) und paketiert `release/xmage-engine-bridge.jar`,
  `release/xmage-engine-bridge.jar.sha256` und `release/ENGINE_PIN.txt` zusammen mit Wheel,
  Sdist und Quellarchiv inklusive Laufzeitprüfung und SHA-256-Summen.
- **Lokale Systemdiagnose (`python -m commander_lab.studio doctor [--json]`):** Prüft Python
  (>= 3.12), Kern- und Studio-Abhängigkeiten, Java (>= 17), Engine-JAR oder Override-Befehl,
  `ENGINE_PIN.txt` gegen `config/rules_engines.json`, optionales AppCDS-Archiv (`.jsa`),
  Pilot-Kartenwissen und Studio-Datenordner; liefert klaren `PASS`/`WARN`/`FAIL`-Status samt
  Behebungshinweisen und passenden Exit-Code (`0` / `1`).

## 2. SIMULATE — Durchsatz, Telemetrie & Pilotqualität (`#1251`, `#1265`, Option S-B)

- **Parallele O'Brien-Fleming-Batches (`studio/play_batch.py`, `paired_comparison.py`,
  `paired_series.py`):** Sequenzielle Look-Fenster werden über konfigurierbare `workers` und
  `games_per_jvm` mit den schnellen JVM-Flags (`launch.series_engine`) in parallelen
  Engine-Batches ausgeführt — unter Erhalt der exakten Sitzreihenfolge, Paarung, Zensierung
  und Seed-Reproduzierbarkeit.
- **Schlanke Bridge S4 & AppCDS (`engine-bridge/`):** Eine Zustandssicht pro Entscheidung statt
  zwei, Zustands-Hash nur wo genutzt und Polling ohne unnötige Tiefenkopie, plus optionales
  AppCDS-Archiv (`provision_engine_bridge.py --appcds`). Freigabe ausschließlich über das
  **Studio-Bridge-Gate (`NEUTRAL`)** mit `identical 36/36` und `frames identical 36/36` auf
  Referenzsatz R1.
- **Rundenlimit, 6-Turn-Goldfish & Log-Telemetrie (`max_turns`):** Optionales Zuglimit in der
  Bridge (Standard unbegrenzt — `BEHAVIOUR`-Gate mit unverändertem Default auf R1), gepaarte
  Telemetrie über alle Sitze 1–4: T1–T4 verpasste Land-Drops, erster Commander-Cast-Turn,
  verrottete ungespielte Handkarten, Win-Condition-Klassifikation (Combat vs. Combo/Drain/Alt-Win),
  Timeout-/Draw-Ursache sowie Pilot-Fehlentscheidungsberichte.
- **Pilot-Qualitätsverbesserung & optionales S5-Experiment (`#1265`, Option O3-A):** Ersatz harter
  Platzhalterwerte (`ramp_mana`, `tokens`, Unsicherheiten) im Feature-State des Full-Game-Piloten
  und Behebung der häufigsten empirischen Verlust-/Fehlentscheidungsmuster mit reproduzierbarem
  Vorher/Nachher-Vergleich (>= 30 Paare). Erst *nach* S4 und dem State-Fix wird S5 Look-Ahead
  (`#1265`) als gemessenes Experiment (>= 30 Paare) geprüft und nur bei klarem Gewinn behalten.

## 3. PLAY — Best-Of-All-Worlds Mensch-vs-KI & Goldfish (`#1169`)

- **Alleinige Regelhoheit & Datenschutz (`AGENTS.md` §2, §5):** Die GUI berechnet keinerlei
  Regeln, Legalität, Kosten oder Kampfregeln selbst und erlaubt kein freies Undo. Während einer
  laufenden Partie bleiben verdeckte Karten der KI-Sitze sowie fremde `private_selection`-Daten
  geschwärzt (Aufdeckung nach Spielende zulässig).
- **Tisch- & Interaktionsmodell (`partie.html` / `partie.css` / `partie.js`):**
  - Unterer Seat-0-Handfächer mit Hover-Zoom; Klick-zu-Aktion (Spielen, Tappen, Aktivieren,
    Zielen, Angreifer/Blocker zuweisen) strikt über gelieferte `pending_decision.legal_options`
    und stabile Objekt-IDs, Multi-Option-Popover bei Mehrdeutigkeit.
  - Kontraststarke Bedienhinweise ohne CSS-Filter auf Scryfall-Kartenbildern (`referrerpolicy="no-referrer"`).
  - SVG-Pfeile für Stack-Ziele und Kampfzuweisungen; interaktiver Stapel-Rail; vollständige
    Zoneneinsicht mit Kartendaten (`loadFacts`).
  - Dynamischer Primär-CTA, **Resolve All** / **Hold Priority**, sitzungsgebundene Auto-Yields
    und Tastaturkürzel; Floating-6-Pip-Mana-Pool; Commander-Damage-Matrix, Commander-Tax und
    Ausscheidungsanzeige.
  - Umschaltbarer **Passive-AI-Goldfish-/Resistance-Modus** am Spieltisch.

## 4. BUILD — Geschlossener Deckbau-Kreislauf

- **Visuelle Spalten- / Stapelansicht** nach Kategorie/CMC im Deckbuilder als Umschaltansicht.
- **Multi-Commander / Partner-Unterstützung** sowie **1-Klick-Start** in den Play- oder
  6-Turn-Goldfish-Tisch direkt für die gewählte Deck-Revision.
- **Mana-/Kastbarkeitsanalyse (`studio/castability.py`):** Einbindung der Tap-Verzögerung und
  `+1 Wastes vs. +1 Basic`-Sensitivität als exakte kombinatorische Zählung ohne Regelbehauptung.
- **Ergebnis-Rückfluss (`/api/outcomes` & Serien-Historie):** Anzeige objektiver
  Öffnungshand-/Karten-Outcomes (`SIMULATED_RESULT`, n/N, Wilson-CI) und gespeicherter gepaarter
  Serien direkt in SIMULATE und im Deckbuilder, strikt getrennt vom Tierliste-Score
  (`simulation`-Gewicht bleibt `0`).

## 5. Gepinnte Architektur & Grenzen

- Der XMage-Fork (`moeendres-png/mage`) und Pin in `config/rules_engines.json`
  (`primary_engine.commit`) werden ohne gesonderten Owner-Entscheid nicht verändert (`#1093`
  bleibt Owner-Gate).
- Zwei bis vier Sitze sind der aktive Regelbetrieb; fünf und sechs Sitze bleiben bis zu
  gesonderter Qualifikation und expliziter Owner-Freigabe zurückgestellt.
- Abschluss-Hygiene (`#1108` Teil 2, Doku-Bereinigung) und Owner-PC-Echt-Engine-Abnahme bilden den
  Abschluss nach Umsetzung der Produkt-Meilensteine.
