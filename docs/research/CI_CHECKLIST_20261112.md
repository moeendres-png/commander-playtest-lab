# Priorisierte CI-Checkliste: Schnelligkeit, Stabilität und Signal-Integrität

- **Dokument-ID:** `docs/research/CI_CHECKLIST_20261112.md`
- **Datum:** 2026-11-12
- **Kontext:** GitHub-Issue #1214 (Umsetzbare Checkliste basierend auf `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`)
- **Status:** *Vorschlags- und Entscheidungsgrundlage für den Owner — keine Maßnahme ist als bereits beschlossen oder umgesetzt zu betrachten.*
- **Verbindliche Rahmenbedingungen:**
  - Keine direkten Workflow-Änderungen in diesem Dokumentationsschritt.
  - Alle offenen architektonischen Punkte sind als Entscheidungsfragen an den Owner formuliert.
  - Jede Maßnahme führt exakte Datei-, Stellen- und Quellenangaben aus dem Recherchebericht.

---

## 1. Priorisierte Maßnahmen-Matrix

| Prio | Maßnahme | Erwarteter Effekt (mit Quellenbeleg) | Risiko / Fallstrick | Betroffene Datei & Stelle |
|---|---|---|---|---|
| **P1** | **Step-Level Timeout & `compression-level: 0` für Artefakt-Uploads** | Verhindert 11-minütige Hänger bei Uploads; eliminiert doppelte Kompression bereits gepackter Wheels/Archive (*Bericht Abschn. 2, S. 3; actions/upload-artifact v4 README*) | Bei extrem instabilem Netzwerk könnte ein Upload nach 3 Minuten abbrechen | `.github/workflows/ci.yml` (Schritt `Upload distribution and test evidence`), `.github/workflows/production-qualification.yml` (Schritt `Upload qualification artifacts`) |
| **P2** | **Klassifizierer-Schritt für reine Dokument-Änderungen in Pflicht-Prüfungen** | Reduziert CI-Laufzeit bei reinen Doku-PRs von ca. 8–13 min auf < 2 min; verhindert `Pending`-Hänger der Branch Protection (*Bericht Abschn. 1, S. 1–2; GitHub Docs: Handling skipped status checks*) | Fehlerhafter Pfad-Regex könnte Code-Änderungen als Doku einstufen und Tests überspringen (Fail-Closed-Absicherung zwingend) | `.github/workflows/ci.yml` (Jobs `quality` und `security`, vor Schritt `Run pytest shards`) |
| **P3** | **Maven-Zwischenspeicher mit `--strict-checksums` in Java-Builds** | Spart das wiederholte Herunterladen von Maven-Plugins und Abhängigkeiten; Zeitersparnis ca. 60–120 s pro Java-Build (*Bericht Abschn. 6, S. 6–7; actions/setup-java v4 README*) | Cache-Poisoning bei unsicheren Mirrors (Abhilfe: `--strict-checksums` und `--batch-mode`) | `.github/workflows/package-engine-bridge.yml` (Schritt `Set up JDK 17`) |
| **P4** | **Beibehaltung des Single-Runner-Modells (`--shards=4`)** | Spart 4-fachen VM-Setup- und Pip-Overhead (~4–8 min Runner-Zeit kumuliert); vermeidet Queue-Blockaden durch Concurrency-Limits (*Bericht Abschn. 3, S. 4; GitHub Docs: Usage limits*) | 1 Runner teilt sich CPU-Ressourcen für 4 Teilprozesse | `.github/workflows/ci.yml` (Job `quality`, Schritt `Run pytest shards`, `tests/pytest_shards.py`) |
| **P5** | **Nicht-blockierende Prüfungen via `$GITHUB_STEP_SUMMARY` & `::notice`** | Transparente Darstellung beratender Befunde direkt in der PR-Zusammenfassung bei grünem Exit-Code 0 (*Bericht Abschn. 5, S. 5–6; GitHub Blog: Supercharging GitHub Actions with Job Summaries*) | Reine Hinweise könnten von Reviewern übersehen werden, wenn sie nicht blockieren | Zukünftige Benchmark- und Doku-Audit-Schritte in `.github/workflows/` |
| **P6** | **ChatOps-Entkopplung für künftige `issue_comment`-Workflows** | Vollständiges Unterbinden von Runner-Allokationen bei normalen PR-Kommentaren (*Bericht Abschn. 4, S. 5; GitHub Docs: Events that trigger workflows - issue_comment*) | Tippfehler im Slash-Kommando führen zu stillem Ignorieren | Zukünftige `.github/workflows/*comment*.yml` |

---

## 2. Detaillierte Maßnahmenbeschreibung

### P1: Step-Level Timeout & `compression-level: 0` für Artefakt-Uploads

- **Konkrete Maßnahme:**
  An jedem Aufruf von `actions/upload-artifact` wird ein explizites `timeout-minutes: 3` hinterlegt und der Parameter `compression-level: 0` gesetzt, sofern bereits komprimierte Artefakte (Wheels, `.tar.gz`, gecachte JSONL) übertragen werden.
- **Erwarteter Effekt:**
  - Vermeidung von Deadlocks/Hängern im GitHub-Blob-Storage-Uploader, die in früheren Läufen bis zu 11 Minuten ungenutzte Runner-Zeit blockierten.
  - Wegfall der CPU-seitigen Neukompression spart 10–20 Sekunden I/O-Last.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 2; offizielle Dokumentation von `actions/upload-artifact@v4`.
- **Risiko:**
  Sollte das Netzwerk temporär gedrosselt sein, bricht der Upload nach 3 Minuten ab.
  *Abmilderung:* `timeout-minutes: 3` reicht bei typischen Artefaktgrößen des Repos (< 50 MB) bei normaler GitHub-Runner-Bandbreite (ca. 50–100 MB/s) um ein Vielfaches aus.
- **Exakte Datei und Stelle:**
  - `.github/workflows/ci.yml`: Schritt `Upload distribution and test evidence` (Zeilen ca. 85–95).
  - `.github/workflows/production-qualification.yml`: Schritt `Upload qualification artifacts` (Zeilen ca. 120–130).
- **Entscheidungsfrage an den Owner:**
  > Soll für sämtliche Artefakt-Uploads in `ci.yml` und `production-qualification.yml` verbindlich `timeout-minutes: 3` und `compression-level: 0` festgeschrieben werden?

---

### P2: Klassifizierer-Schritt für reine Dokumentenänderungen

- **Konkrete Maßnahme:**
  In den Pflicht-Jobs `quality` und `security` wird als erster Schritt nach dem Checkout eine Änderungssatz-Prüfung (`git diff`) ausgeführt. Sind ausschließlich Dateien unter `docs/**` oder `*.md` betroffen, überspringen nachfolgende schwere Schritte (`pytest`, Typprüfungen) die Ausführung. Der Job schließt nach Ausführung einer schnellen Syntax- und Secret-Sentinel-Prüfung mit `success` ab. Es wird **kein** `paths-ignore` auf Workflow-Ebene verwendet.
- **Erwarteter Effekt:**
  - Reine Dokumentations-PRs melden innerhalb von 1–2 Minuten ein valides, grünes `success`-Signal an die GitHub Branch Protection.
  - Die Pflicht-Checks `quality` und `security` bleiben zu keinem Zeitpunkt im Zustand `Pending / Expected` hängen.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 1; GitHub Docs "Handling skipped status checks".
- **Risiko:**
  Ein zu lockerer Regulärer Ausdruck könnte Codeänderungen als Dokumentänderung klassifizieren und Tests fälschlicherweise auslassen.
  *Abmilderung:* Strikter Negativ-Filter (`grep -qvE '^(docs/|.*\.md$)'`), der bei der kleinsten Unklarheit oder Existenz von Python-/Java-/Workflow-Code sofort `code_changed=true` ausgibt (Fail-Closed).
- **Exakte Datei und Stelle:**
  - `.github/workflows/ci.yml`: Jobs `quality` und `security`, direkt nach dem Schritt `Checkout repository source`.
- **Entscheidungsfrage an den Owner:**
  > Gibt der Owner die Einführung eines Klassifizierer-Schritts für `quality` und `security` in `ci.yml` frei, und welche Verzeichnisse sollen exakt als reine Dokumentationspfade gelten (`docs/`, `*.md`)?

---

### P3: Maven-Zwischenspeicher mit `--strict-checksums` in Java-Builds

- **Konkrete Maßnahme:**
  In Workflows, die Maven-Aufrufe für Java-Komponenten enthalten, wird `cache: maven` in `actions/setup-java` aktiviert. Maven-Aufrufe werden mit `--strict-checksums` und `--batch-mode` versehen.
- **Erwarteter Effekt:**
  - Das lokale Maven-Repository (`~/.m2/repository`) bleibt über Workflow-Läufe hinweg gecacht.
  - Beseitigt redundante Downloads von Dutzenden XMage- und Build-Plugins über Maven Central.
  - Netto-Laufzeitverkürzung bei Java-Builds um ca. 60–120 Sekunden.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 6; offizielle Dokumentation `actions/setup-java@v4`.
- **Risiko:**
  Beschädigte oder manipulierte Artefakte im Cache.
  *Abmilderung:* Der Schalter `--strict-checksums` erzwingt den sofortigen Abbruch bei Prüfsummen-Abweichungen; GitHub Actions isoliert Caches strikt per Branch/Repository.
- **Exakte Datei und Stelle:**
  - `.github/workflows/package-engine-bridge.yml`: Schritt `Set up JDK 17` (Hinzufügen von `cache: maven`).
- **Entscheidungsfrage an den Owner:**
  > Soll `cache: maven` in `package-engine-bridge.yml` für `actions/setup-java` aktiviert werden?

---

### P4: Beibehaltung des Single-Runner-Modells (4 Prozesse via `pytest_shards.py`)

- **Konkrete Maßnahme:**
  Die Ausführung der Python-Testsuite verbleibt auf einem einzigen GitHub-Runner und nutzt dort 4 parallele Prozesse (`pytest --shards=4`, gesteuert durch `tests/pytest_shards.py`). Auf ein Aufblähen in eine GitHub-Matrix (`strategy.matrix`) wird verzichtet.
- **Erwarteter Effekt:**
  - Entfall von mehrfachem VM-Initialisierungs- und `pip install`-Overhead (ca. 1–2 Minuten pro Matrix-Job).
  - Keine Erschöpfung des Kontingents paralleler Runner (Limit 20 Slots bei Standard-Accounts), insbesondere wenn mehrere Agenten gleichzeitig Branches aktualisieren.
  - Ein einziges konsolidiertes Prüfsignal für `quality` ohne vorgeschalteten Aggregator-Job.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 3; GitHub Docs "Usage limits, billing, and administration".
- **Risiko:**
  Ein Runner besitzt begrenzte CPU-Kerne (Standard: 2 vCPUs). Bei wachsendem Testvolumen könnte eine Single-VM an Durchsatzgrenzen stoßen.
  *Abmilderung:* Aktuelle Laufzeit liegt stabil bei ca. 8–12 Minuten; Profiling zeigt, dass Sharding auf 4 Prozesse die 2 vCPUs optimal auslastet.
- **Exakte Datei und Stelle:**
  - `.github/workflows/ci.yml`: Job `quality`, Schritt `Run pytest shards`.
- **Entscheidungsfrage an den Owner:**
  > Bestätigt der Owner die architektonische Entscheidung, das Single-Runner-Mehrprozess-Modell (`pytest --shards=4`) als Standard beizubehalten?

---

### P5: Nicht-blockierende Hinweise via `$GITHUB_STEP_SUMMARY` & `::notice`

- **Konkrete Maßnahme:**
  Analytische und informative Auswertungen (wie z. B. Benchmark-Vergleiche, statistische Divergenzen oder optionale Linter-Prüfungen) schreiben ihre Berichte direkt in `$GITHUB_STEP_SUMMARY` und nutzen `::notice` oder `::warning`. Sie beenden ihren Schritt stets mit Exit-Code 0.
- **Erwarteter Effekt:**
  - Ausführliche Markdown-Berichte sind für Reviewer und Entwickler direkt im Übersichtsbildschirm des GitHub-Runs sichtbar.
  - Keine fälschliche Rotfärbung von PRs bei rein informativen oder statistischen Befunden.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 5; GitHub Blog "Supercharging GitHub Actions with Job Summaries".
- **Risiko:**
  Reine Warnungen erzeugen keinen Merge-Blocker und könnten übersehen werden.
  *Abmilderung:* Harte Integritätskriterien (z. B. Syntaxfehler, fehlschlagende Unit-Tests, Any-Ratchet) bleiben weiterhin strikt blockierend mit Exit-Code != 0.
- **Exakte Datei und Stelle:**
  - Informative Hilfsskripte und zukünftige Benchmark-Jobs in `.github/workflows/`.
- **Entscheidungsfrage an den Owner:**
  > Für welche spezifischen Prüfungen (z. B. Telemetrie-Abweichungen oder Benchmark-Toleranzen) soll dieses Hinweis-Format verbindlich eingesetzt werden?

---

### P6: ChatOps-Entkopplung für künftige `issue_comment`-Workflows

- **Konkrete Maßnahme:**
  Falls künftig ChatOps-Workflows (z. B. `/bench`, `/qualify`) eingerichtet werden, müssen diese an der Job-Bedingung `if: github.event.issue.pull_request != null && startsWith(github.event.comment.body, '/...')` filtern und dürfen nicht an den PR-Head-Statuscheck gebunden werden.
- **Erwarteter Effekt:**
  - Vermeidung von Runner-Verbrauch und unübersichtlichen Check-Runs bei normalen Diskussionen und Code-Reviews im PR.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 4; GitHub Docs "Events that trigger workflows - issue_comment".
- **Risiko:**
  Tippfehler im Befehl führen dazu, dass der Workflow gar nicht startet.
  *Abmilderung:* Dokumentation der erlaubten Slash-Befehle in `CONTRIBUTING.md` bzw. `AGENTS.md`.
- **Exakte Datei und Stelle:**
  - Richtlinie für künftige Kommentar-Workflows in `.github/workflows/`.
- **Entscheidungsfrage an den Owner:**
  > Welche konkreten ChatOps-Befehle (z. B. `/bench`, `/retest`) sollen künftig unterstützt und autorisiert werden?
