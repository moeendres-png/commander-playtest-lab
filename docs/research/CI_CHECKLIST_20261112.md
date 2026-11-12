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
| **P1** | **Step-Level Timeout & `compression-level: 0` für Artefakt-Uploads** | Verhindert Hänger bei Uploads; eliminiert doppelte Kompression bereits gepackter Wheels/Archive (*Bericht Abschn. 2, S. 3; actions/upload-artifact v4 README*) | Bei extrem instabilem Netzwerk könnte ein Upload nach 3 Minuten abbrechen | `.github/workflows/ci.yml` (Schritte `actions/upload-artifact` mit `name: ci-evidence` [Z. 141] und `name: security-evidence` [Z. 237]), `.github/workflows/production-qualification.yml` (Schritt `actions/upload-artifact` [Z. 117]) |
| **P2** | **Klassifizierer-Schritt für reine Dokument-Änderungen in Pflicht-Prüfungen (Grundsatzentscheidung)** | Verkürzt Laufzeit bei reinen Doku-PRs auf wenige Minuten (Schätzung); verhindert `Pending`-Hänger der Branch Protection (*Bericht Abschn. 1, S. 1–2; GitHub Docs: Handling skipped status checks*) | **Hohes Risiko:** Schwächt Pflicht-Checks (`quality`, `security`, `infrastructure`), falls Tests/Scans übersprungen werden. Zwingend explizite Owner-Freigabe erforderlich. | `.github/workflows/ci.yml` (Jobs `quality`, `security`), `.github/workflows/production-qualification.yml` (Job `infrastructure`) |
| **P3** | **Strikte Maven-Flags (`--strict-checksums`, `--batch-mode`) in Java-Builds** | Erhöht Build-Reproduzierbarkeit und Schutz vor korrupten Artefakten (*Bericht Abschn. 6, S. 6–7*). Hinweis: `cache: maven` ist in `package-engine-bridge.yml` bereits aktiv (Z. 41). | Strengere Checksum-Prüfung schlägt bei defekten Upstream-Metadaten fehl | `.github/workflows/package-engine-bridge.yml` (Schritte mit `mvn`-Aufrufen) |
| **P4** | **Beibehaltung des Single-Runner-Modells (`--shards=4`)** | Spart mehrfachen VM-Setup- und Pip-Overhead; vermeidet Queue-Blockaden durch Runner-Limits (*Bericht Abschn. 3, S. 4; GitHub Docs: Usage limits*) | 1 Runner teilt sich CPU-Ressourcen für 4 Teilprozesse | `.github/workflows/ci.yml` (Job `quality`, Schritt `Test suite` [Z. 64], `tests/pytest_shards.py`) |
| **P5** | **Nicht-blockierende Prüfungen via `$GITHUB_STEP_SUMMARY` & `::notice`** | Transparente Darstellung beratender Befunde direkt in der PR-Zusammenfassung bei grünem Exit-Code 0 (*Bericht Abschn. 5, S. 5–6; GitHub Blog: Supercharging GitHub Actions with Job Summaries*) | Reine Hinweise könnten von Reviewern übersehen werden, wenn sie nicht blockieren | Zukünftige Benchmark- und Doku-Audit-Schritte in `.github/workflows/` |
| **P6** | **ChatOps-Entkopplung für künftige `issue_comment`-Workflows** | Vollständiges Unterbinden von Runner-Allokationen bei normalen PR-Kommentaren (*Bericht Abschn. 4, S. 5; GitHub Docs: Events that trigger workflows - issue_comment*) | Tippfehler im Slash-Kommando führen zu stillem Ignorieren | Zukünftige `.github/workflows/*comment*.yml` |

---

## 2. Detaillierte Maßnahmenbeschreibung

### P1: Step-Level Timeout & `compression-level: 0` für Artefakt-Uploads

- **Konkrete Maßnahme:**
  An den bestehenden Aufrufen von `actions/upload-artifact` wird ein explizites `timeout-minutes: 3` hinterlegt und der Parameter `compression-level: 0` gesetzt, sofern bereits komprimierte Artefakte (Wheels, `.tar.gz`, gecachte JSONL) übertragen werden.
- **Erwarteter Effekt:**
  - Vermeidung von Deadlocks/Hängern im GitHub-Blob-Storage-Uploader.
  - Wegfall der CPU-seitigen Neukompression spart I/O-Last und CPU-Zyklen.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 2; offizielle Dokumentation von `actions/upload-artifact@v4`.
- **Risiko:**
  Sollte das Netzwerk temporär gedrosselt sein, bricht der Upload nach 3 Minuten ab.
  *Abmilderung:* `timeout-minutes: 3` reicht bei typischen Artefaktgrößen des Repos (< 50 MB, Schätzung) bei normaler GitHub-Runner-Netzwerkanbindung (heuristischer Richtwert) im Regelfall aus.
- **Exakte Datei und Stelle:**
  - `.github/workflows/ci.yml`: Unbenannter `actions/upload-artifact`-Schritt mit `name: ci-evidence` (Zeile 141) sowie unbenannter Schritt mit `name: security-evidence` (Zeile 237).
  - `.github/workflows/production-qualification.yml`: Unbenannter `actions/upload-artifact`-Schritt mit `name: production-qualification-${{ github.sha }}` (Zeile 117).
- **Entscheidungsfrage an den Owner:**
  > Soll für sämtliche Artefakt-Uploads in `ci.yml` und `production-qualification.yml` verbindlich `timeout-minutes: 3` und `compression-level: 0` festgeschrieben werden?

---

### P2: Klassifizierer-Schritt für reine Dokumentenänderungen (Grundsatzentscheidung)

- **Konkrete Maßnahme (Vorschlag zur Grundsatzentscheidung):**
  Prüfung, ob in den Pflicht-Jobs `quality` und `security` (`ci.yml`) sowie `infrastructure` (`production-qualification.yml`) ein Pfadfilter-Klassifizierer vorgeschaltet werden soll, wenn ausschließlich Dokumente (`docs/**`, `*.md`) geändert wurden. Es wird **kein** `paths-ignore` auf Workflow-Ebene verwendet.
- **Erwarteter Effekt:**
  - Reine Dokumentations-PRs könnten schneller ein valides `success`-Signal an die Branch Protection melden (Schätzung: wenige Minuten statt voller Testlauf).
  - Die Pflicht-Checks bleiben zu keinem Zeitpunkt im Zustand `Pending / Expected` hängen.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 1; GitHub Docs "Handling skipped status checks".
- **Kritisches Risiko / Einschränkung:**
  **Pflicht-Checks `quality` und `security`, die Erfolg melden, ohne `pytest`, `mypy` und den Secret-Scan auszuführen, schwächen die Schutzwirkung der Branch Protection fundamental.** Ein fehlerhafter Pfad-Regex könnte Code-Änderungen als Dokumentänderung einstufen. Dies darf **keinesfalls als Routine-Maßnahme** eingeführt werden, sondern bedarf einer expliziten Risiko-Abwägung durch den Owner.
- **Exakte Datei und Stelle:**
  - `.github/workflows/ci.yml`: Jobs `quality` und `security`, nach `Checkout repository source`.
  - `.github/workflows/production-qualification.yml`: Job `infrastructure`.
- **Entscheidungsfrage an den Owner:**
  > Soll die Schutzwirkung der Pflicht-Checks für reine Dokumentations-PRs zugunsten kürzerer Durchlaufzeiten durch einen Pfad-Klassifizierer gelockert werden, oder bleibt die vollständige Test- und Scan-Ausführung für jeden Commit zwingend obligatorisch?

---

### P3: Strikte Maven-Flags (`--strict-checksums`, `--batch-mode`) in Java-Builds

- **Konkrete Maßnahme:**
  In Workflows mit Maven-Aufrufen für Java-Komponenten werden die Aufrufe einheitlich mit `--strict-checksums` und `--batch-mode` versehen. *(Hinweis: `cache: maven` ist in `.github/workflows/package-engine-bridge.yml` im Schritt `Set up JDK 17` [Zeilen 36–41] bereits aktiv).*
- **Erwarteter Effekt:**
  - Erhöhte Build-Reproduzierbarkeit und sofortiger Abbruch bei beschädigten oder manipulierten Upstream-Artefakten.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 6.
- **Risiko:**
  Strengere Checksum-Prüfung schlägt fehl, falls Upstream-Repositories unvollständige SHA-Metadaten bereitstellen.
- **Exakte Datei und Stelle:**
  - `.github/workflows/package-engine-bridge.yml`: Maven-Befehlsaufrufe.
- **Entscheidungsfrage an den Owner:**
  > Sollen alle Maven-Aufrufe in den Engine-Bridge-Workflows verbindlich mit `--strict-checksums` und `--batch-mode` gehärtet werden?

---

### P4: Beibehaltung des Single-Runner-Modells (4 Prozesse via `pytest_shards.py`)

- **Konkrete Maßnahme:**
  Die Ausführung der Python-Testsuite verbleibt auf einem einzigen GitHub-Runner und nutzt dort 4 parallele Prozesse (`pytest --shards=4`, gesteuert durch `tests/pytest_shards.py`). Auf ein Aufblähen in eine GitHub-Matrix (`strategy.matrix`) wird verzichtet.
- **Erwarteter Effekt:**
  - Entfall von mehrfachem VM-Initialisierungs- und `pip install`-Overhead.
  - Keine Erschöpfung des Kontingents paralleler Runner (Limit 20 Slots bei Standard-Accounts), insbesondere wenn mehrere Agenten gleichzeitig Branches aktualisieren.
  - Ein einziges konsolidiertes Prüfsignal für `quality` ohne vorgeschalteten Aggregator-Job.
  - *Quelle:* `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`, Abschnitt 3; GitHub Docs "Usage limits, billing, and administration".
- **Risiko:**
  Ein Runner besitzt begrenzte CPU-Kerne. Bei stark wachsendem Testvolumen könnte eine Single-VM an Durchsatzgrenzen stoßen.
  *Abmilderung:* Gemäß Workflow-Kommentar (`ci.yml` Zeilen 71–73) läuft der Schritt `Test suite` auf einem 4-Kern-Runner ("four parallel pytest processes on the 4-core runner"). Die 4 Shards nutzen diese Ressourcen direkt lokal ohne Virtualisierungs-Overhead.
- **Exakte Datei und Stelle:**
  - `.github/workflows/ci.yml`: Job `quality`, Schritt `Test suite` (Zeile 64).
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
  *Abmilderung:* Dokumentation der erlaubten Slash-Befehle in den entsprechenden Projektdokumenten (`AGENTS.md`).
- **Exakte Datei und Stelle:**
  - Richtlinie für künftige Kommentar-Workflows in `.github/workflows/`.
- **Entscheidungsfrage an den Owner:**
  > Welche konkreten ChatOps-Befehle (z. B. `/bench`, `/retest`) sollen künftig unterstützt und autorisiert werden?
