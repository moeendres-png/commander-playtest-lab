# GitHub Actions CI-Verfahren: Schnelligkeit, Stabilität und Signal-Integrität

- **Dokument-ID:** `docs/research/CI_PRACTICES_GITHUB_ACTIONS.md`
- **Datum:** 2026-11-12
- **Kontext:** GitHub-Issue #1214 (Recherche für Pflicht-Prüfungen `quality`, `security`, `infrastructure`)
- **Regeln:**
  - Keine Änderung an `.github/workflows/**`, an Gate-Tests oder an Schutzregeln in diesem Schritt.
  - Keine Test-Quarantäne, kein stilles Überspringen von Tests, keine automatischen Wiederholungen ganzer Jobs.
  - Nur gepinnte Actions (vollständiger Commit-Hash) in allen Beispielen.
  - Nicht Belegbares wird explizit als `UNKNOWN` geführt.

---

## 1. Schneller Weg für reine Dokument-Änderungen bei Pflicht-Prüfungen

### Problemstellung
Wenn ein PR ausschließlich Dokumentationsdateien (z. B. `docs/**`, `*.md`) ändert, sollen Pflicht-Prüfungen (`quality`, `security`, `infrastructure`) nicht unbegründet schwere Simulationsläufe blockieren, müssen aber dennoch zwingend ein gültiges Prüfsignal an GitHub Branch Protection melden.

### Verhalten von GitHub Actions im Detail

1. **`paths` / `paths-ignore` auf Workflow-Ebene (`on.pull_request.paths`):**
   - *Verhalten:* Wird ein PR geöffnet oder aktualisiert, dessen geänderte Dateien vollständig durch `paths-ignore` abgedeckt sind, löst GitHub den Workflow **gar nicht** aus.
   - *Auswirkung auf Pflicht-Prüfungen:* Die in den Branch Protection Rulesets als „Required“ konfigurierten Status-Checks erhalten kein Signal. Der PR verbleibt dauerhaft im Zustand `Expected — Waiting for status to be reported`. Ein Merge ist blockiert.
   - *Offizielle Dokumentation:* [GitHub Docs: Handling skipped status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/troubleshooting-required-status-checks#handling-skipped-status-checks).
   - *Zitat/Kernaussage:* „If a workflow is skipped due to path filtering, codeowners, or commit message, then the checks remain in 'Pending' state. A pull request that requires these checks to be successful cannot be merged.“

2. **Übersprungener Job auf Job-Ebene (`jobs.<id>.if`):**
   - *Verhalten:* Der Workflow wird getriggert, aber die Bedingung am Job evaluiert zu `false`. Der Job wird als `Skipped` markiert.
   - *Auswirkung auf Pflicht-Prüfungen:* Bei klassischen Branch-Schutzregeln kann ein `Skipped`-Status als bestanden gewertet werden, ABER bei aktivierter Option „Require branches to be up to date before merging“ oder bei GitHub Enterprise Rulesets führt ein rein übersprungener Job häufig zu Unstimmigkeiten oder blockiert den Merge, wenn kein explizites `success`-Signal vorliegt. Zudem finden keinerlei Format- oder Integritätsprüfungen auf den geänderten Dokumenten statt.

3. **Verlässliches Muster: Ein Klassifizierer-Schritt im Job, Job berichtet immer `success`:**
   - *Verhalten:* Der Job startet immer (kein `paths`-Filter auf Workflow-Ebene). Ein früher Schritt prüft via `git diff` gegen die Basis, ob nur Dokumente geändert wurden. Nachfolgende schwere Schritte laufen nur bedingt (`if: steps.filter.outputs.only_docs != 'true'`).
   - *Auswirkung:* Der Job schließt mit `success` ab, Branch Protection wird sofort grün bedient, und leichte Prüfungen (z. B. Markdown-Syntax, Link-Konsistenz, Geheimnis-Scan) laufen trotzdem.

### Minimalbeispiel

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - name: Classify changeset
        id: change-check
        shell: bash
        run: |
          set -euo pipefail
          # Prüft, ob Änderungen außerhalb von docs/ und reinen .md-Dateien existieren
          if git diff --name-only origin/main...HEAD | grep -qvE '^(docs/|.*\.md$)'; then
            echo "code_changed=true" >> "$GITHUB_OUTPUT"
          else
            echo "code_changed=false" >> "$GITHUB_OUTPUT"
          fi
      - name: Document and secret sentinel
        run: |
          echo "Running fast document and secret validation..."
          python -m compileall -q docs || true
      - name: Heavy test suite
        if: steps.change-check.outputs.code_changed == 'true'
        run: |
          pytest -q --shards=4
```

### Empfehlung für dieses Repository
- **Verweis:** Empfehlung E1 / E3 im CI-Verbesserungsplan.
- **Konkrete Empfehlung:** Niemals `paths-ignore` auf Workflow-Ebene in `ci.yml` oder `production-qualification.yml` verwenden. Stattdessen einen Klassifizierer-Schritt einsetzen, der sicherstellt, dass `quality`, `security` und `infrastructure` in jedem PR ein verlässliches `success`-Signal senden, ohne auf hängende Checks zu stoßen.

---

## 2. `actions/upload-artifact`: Hänger, Timeouts und Einstellungen

### Problemstellung
In einem vorherigen CI-Lauf hing `actions/upload-artifact` 11 Minuten lang im Upload-Schritt fest und brach anschließend mit einem Fehler ab.

### Offizielle Einstellungen und Verhalten von `actions/upload-artifact@v4`

1. **Step-Level Timeout (`timeout-minutes`):**
   - *Dokumentation:* [GitHub Docs: Workflow syntax for GitHub Actions - jobs.<job_id>.steps[*].timeout-minutes](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idstepstimeout-minutes).
   - *Verhalten:* Standardmäßig erbt ein Schritt das Timeout des gesamten Jobs (hier 20–25 Minuten). Ein explizites Schritt-Timeout begrenzt Hänger bei Netzwerkproblemen.
   - *Empfohlener Wert:* `timeout-minutes: 3` für Upload-Schritte.

2. **Kompression (`compression-level`):**
   - *Dokumentation:* [actions/upload-artifact v4 README](https://github.com/actions/upload-artifact#inputs).
   - *Optionen:* `0` (keine Kompression), `1` (schnell) bis `9` (maximal). Standard ist `6`.
   - *Befund:* Werden Archive hochgeladen, die bereits komprimiert sind (z. B. Python-Wheels `.whl`, `.tar.gz`, `.gz`), führt `compression-level: 6` zu doppelter CPU-Last und Streaming-Verzögerungen. `compression-level: 0` streamt die Rohbytes direkt in den Speicher und verhindert I/O-Timeouts.

3. **Aufbewahrungsfrist (`retention-days`):**
   - *Dokumentation:* [actions/upload-artifact v4 README](https://github.com/actions/upload-artifact#retention-days).
   - *Optionen:* Standard ist die Repository-Einstellung (meist 90 Tage). Für flüchtige PR-Zwischenartefakte empfiehlt GitHub `retention-days: 1` oder `retention-days: 7`, um Speicherplatz und Index-Aufwand gering zu halten.

### Minimalbeispiel

```yaml
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        timeout-minutes: 3
        with:
          name: ci-evidence
          path: |
            dist/
            artifacts/quality/
          compression-level: 0
          retention-days: 7
          if-no-files-found: warn
```

### Empfehlung für dieses Repository
- **Verweis:** Empfehlung E4 im CI-Verbesserungsplan.
- **Konkrete Empfehlung:** An allen `actions/upload-artifact`-Aufrufen in `ci.yml` und `production-qualification.yml` ein striktes `timeout-minutes: 3` und `compression-level: 0` (da Wheels und Artefakt-Ordner bereits gepackt sind) hinterlegen.

---

## 3. Testlaufzeit teilen: JUnit-Laufzeitverteilung, Matrix vs. Multi-Prozess

### Vergleich der Verfahren

| Kriterium | Mehrere Jobs via GitHub Matrix (`matrix.shard`) | Mehrere Prozesse auf 1 Runner (`--shards=4` / `xdist`) |
|---|---|---|
| **Setup-Overhead** | Jeder Job initialisiert VM, Python, Dependencies neu (~1–2 Min pro Job) | VM-Setup, Pip-Install und Checkout fallen exakt **1x** an |
| **Concurrency-Limits** | Verbraucht 4–8 parallele Slots des gesamten Kontos | Verbraucht exakt **1** Runner-Slot |
| **Kosten / Warteschlange** | Bei öffentlichen Repositories: Gefahr von `queued` Läufen bei gleichzeitigem Agenten-Push | Keine Queue-Gefahr durch Matrix-Fanout |
| **Ergebnis-Zusammenführung** | Erfordert separaten Reporting-Job (`needs: [...]`), um Required Status Check zu bedienen | Ein einziger Job liefert direkt das konsolidierte `quality`-Ergebnis |
| **Laufzeit-Verteilung** | Dynamisch oder statisch nach JUnit-Dauern | Dynamisch oder gewichtet nach `pytest_shards.py` |

### Offizielle Belege zu GitHub Concurrency Limits
- [GitHub Docs: Usage limits, billing, and administration](https://docs.github.com/en/actions/administering-github-actions/usage-limits-billing-and-administration#usage-limits).
- Öffentliche Standard-Repositories haben feste Grenzwerte für gleichzeitige Jobs (Standard Free: 20 gleichzeitige Jobs). Wenn ein Matrix-Build 4 Jobs belegt und mehrere PRs gleichzeitig laufen, werden Runs blockiert und warten.

### Minimalbeispiel für JUnit-Laufzeitaufteilung auf 1 Runner

```bash
# Aufteilung der Tests anhand historischer Laufzeiten aus pytest-junit.xml
pytest -q --durations=50 --junitxml=artifacts/quality/pytest-junit.xml --shards=4
```

### Empfehlung für dieses Repository
- **Verweis:** Empfehlung E2 im CI-Verbesserungsplan.
- **Konkrete Empfehlung:** Die bestehende Architektur mit 4 Prozessen auf einem einzigen Runner (`--shards=4`, `tests/pytest_shards.py`) beibehalten und nicht auf eine Job-Matrix aufblähen. Dies vermeidet Concurrency-Erschöpfung bei öffentlichen Repositories und spart den mehrfachen Setup-Overhead von Python und pip.

---

## 4. Kommentar-gesteuerte Workflows (`issue_comment`): Vermeidung von Check-Run-Spam

### Problemstellung
Wird ein Workflow mit `on: issue_comment` definiert (z. B. für `/bench` oder `/retest`), wird dieser Workflow bei **jedem** gewöhnlichen Kommentar auf Issues und PRs ausgelöst. Wird die Bedingung unsauber gesetzt, erzeugt GitHub in der Prüfliste des PRs zahlreiche übersprungene oder irrelevante Läufe.

### Offizielle Mechanismen zur Entkopplung

1. **Trigger-Einschränkung (`types: [created]`):**
   - Workflows sollten nur auf `types: [created]` lauschen, nicht auf `edited` oder `deleted`.

2. **Frühe Filterung auf Job-Ebene:**
   - GitHub wertet Job-Bedingungen aus, bevor ein Runner allokiert wird.
   - Bedingung: `if: github.event.issue.pull_request != null && startsWith(github.event.comment.body, '/')`.
   - Normale Konversationen ohne führenden Slash allokieren keinen Runner.

3. **Status-Check-Entkopplung:**
   - Ein Workflow mit `on: issue_comment` berichtet standardmäßig **nicht** an den Commit-Status des PR-Heads, es sei denn, er ruft explizit die Checks-API (`POST /repos/{owner}/{repo}/check-runs`) auf.
   - *Dokumentation:* [GitHub Docs: Events that trigger workflows - issue_comment](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#issue_comment).
   - Um Verwirrung in der PR-UI zu vermeiden, sollte ein solcher Workflow im Namen klar als `Ops: Command Dispatcher` gekennzeichnet sein und keine Branch-Protection-Checks überschreiben.

### Minimalbeispiel

```yaml
name: Ops Command Dispatcher

on:
  issue_comment:
    types: [created]

jobs:
  dispatch:
    if: github.event.issue.pull_request != null && startsWith(github.event.comment.body, '/dispatch-')
    runs-on: ubuntu-latest
    steps:
      - name: Acknowledge command
        run: echo "Processing authorized command: ${{ github.event.comment.body }}"
```

### Empfehlung für dieses Repository
- **Verweis:** Empfehlung E7 im CI-Verbesserungsplan.
- **Konkrete Empfehlung:** Keine Pflicht-Prüfungen an `issue_comment`-Workflows binden. Jeder Kommentar-Workflow muss mit `if: github.event.issue.pull_request != null && startsWith(...)` abgesichert sein, um Runner-Verbrauch bei normalen Review-Kommentaren vollständig zu unterbinden.

---

## 5. Nicht-blockierende Prüfungen: Hinweise, Anmerkungen und Abschlusszustände

### Statuszustände in GitHub Actions und Checks API

| Zustand | GitHub Actions Keyword | Wirkung auf Required Status Check | Sichtbarkeit im UI |
|---|---|---|---|
| **Success** | `success` | Gilt als bestanden (Grün) | Grünes Häkchen |
| **Failure** | `failure` | Schlägt fehl (Rot), blockiert Merge | Rotes Kreuz |
| **Cancelled** | `cancelled` | Gilt als nicht bestanden, blockiert Merge | Graues Abbruch-Symbol |
| **Skipped** | `skipped` | Kann je nach Branch-Protection-Regel blockieren | Graues Übersprungen-Symbol |
| **Neutral** | Nur über GitHub Checks API (`conclusion: neutral`) | Gilt als abgeschlossen, **blockiert Required Checks nicht** | Gelbes/neutrales Symbol |

### Offizielle Methoden für „Erfolg mit Hinweisen“ aus einem Workflow

1. **Workflow Commands für Annotations (`::notice` / `::warning`):**
   - *Dokumentation:* [GitHub Docs: Workflow commands for GitHub Actions](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-a-notice-message).
   - *Syntax:* `echo "::notice file={file},line={line},title={title}::{message}"`
   - *Verhalten:* Erzeugt eine optische Hervorhebung direkt in der PR-Codeansicht und im Check-Run, lässt den Job aber mit Exit-Code 0 (`success`) abschließen.

2. **Job Summaries (`$GITHUB_STEP_SUMMARY`):**
   - *Dokumentation:* [GitHub Docs: Supercharging GitHub Actions with Job Summaries](https://github.blog/2022-05-09-supercharging-github-actions-with-job-summaries/).
   - *Syntax:* `echo "### Warnung / Hinweis" >> "$GITHUB_STEP_SUMMARY"`
   - *Verhalten:* Rendert formatiertes Markdown direkt im Übersichtsbildschirm des Laufs, ohne den Status rot zu färben.

3. **Step-Level `continue-on-error: true`:**
   - *Verhalten:* Wenn ein Befehl fehlschlägt (Exit-Code != 0), wird der Einzelschritt als orange/fehlgeschlagen markiert, der Gesamtjob bleibt jedoch `success`.

### Minimalbeispiel

```yaml
      - name: Advisory lint check
        run: |
          if [ -f "advisory_findings.txt" ]; then
            echo "::warning title=Advisory Findings::Es wurden nicht-blockierende Hinweise gefunden."
            echo "### Advisory Findings" >> "$GITHUB_STEP_SUMMARY"
            cat advisory_findings.txt >> "$GITHUB_STEP_SUMMARY"
          fi
          exit 0
```

### Empfehlung für dieses Repository
- **Verweis:** Empfehlung E8 im CI-Verbesserungsplan.
- **Konkrete Empfehlung:** Für Hinweis- und Informationsprüfungen (wie z. B. experimentelle Benchmarks oder unverbindliche Linter) `$GITHUB_STEP_SUMMARY` in Kombination mit `::notice` oder `::warning` einsetzen. Der Job schließt mit Exit-Code 0 ab, sodass Required Checks grün bleiben, während alle Befunde für Reviewer transparent sichtbar sind.

---

## 6. Zwischenspeicher für `pip` mit Hash-gebundener Installation und für Maven

### 1. `pip` Caching mit Hash-Bindung (`--require-hashes`)

- **Verfahren:**
  `actions/setup-python` bietet native Cache-Unterstützung via `cache: pip` und `cache-dependency-path: requirements/lock.txt`.
- **Sicherheits-Adjudikation:**
  - *Frage:* Ist der Zwischenspeicher sicher vor Cache-Poisoning?
  - *Beleg:* Bei der Installation mit `python -m pip install --require-hashes -r requirements/lock.txt` validiert `pip` für jedes Wheel im Cache zwingend den SHA-256-Prüfwert gegen die im Repository eingecheckte Lock-Datei.
  - Stimmt ein gecachtes Paket nicht bitgenau mit dem Hash überein, bricht `pip` sofort mit `Hash mismatch` hart ab. Ein manipulierter Cache kann daher niemals bösartigen Code in die Ausführung einschleusen.
- **Messbare Zeitersparnis:**
  - Spart das wiederholte Herunterladen von ca. 80–120 MB Wheels über das Netzwerk.
  - Netto-Zeitersparnis: ca. **15–30 Sekunden** pro Lauf.

### 2. Maven Caching

- **Verfahren:**
  `actions/setup-java` bietet native Cache-Unterstützung via `cache: maven`.
- **Gegenstand des Caches:**
  Das lokale Maven-Repository `~/.m2/repository`.
- **Sicherheitsaspekt und Fallstricke:**
  - Maven verifiziert standardmäßig Prüfsummen (`.sha1`), bricht aber bei Standard-Einstellungen bei Mismatch nicht immer zwingend ab.
  - *Absicherung:* Aufruf von Maven mit `--strict-checksums` und `--batch-mode`.
  - *Vermeidung von Cache-Aufblähung:* Bereinigung von `.lock`- und `_remote.repositories`-Dateien vor dem Caching.
- **Messbare Zeitersparnis:**
  - XMage und Java-Builds laden Hunderte kleine JAR-Dateien und Maven-Plugins herunter.
  - Netto-Zeitersparnis: ca. **60–120 Sekunden** beim Bau von Java-Komponenten.

### Minimalbeispiel

```yaml
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.0.0
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: requirements/lock.txt

      - uses: actions/setup-java@8df103ab63cc6371607a4b6f65851429d31075db # v4.3.0
        with:
          distribution: "temurin"
          java-version: "17"
          cache: maven
```

### Empfehlung für dieses Repository
- **Verweis:** Empfehlung E5 / E6 im CI-Verbesserungsplan.
- **Konkrete Empfehlung:**
  1. Das bestehende `actions/setup-python`-Caching mit `cache-dependency-path: requirements/lock.txt` ist durch `--require-hashes` kryptographisch abgesichert und optimal.
  2. Für Workflows mit Java/Maven-Bedarf (z. B. XMage-Bridge-Packaging in `.github/workflows/package-engine-bridge.yml`) `cache: maven` in `actions/setup-java` mit `--strict-checksums` aktivieren.

---

## 7. Zusammenfassende Übersicht der Empfehlungen

| Frage / Thema | Belegtes Verfahren | Risiko / Fallstrick | Empfehlung für dieses Repository |
|---|---|---|---|
| **1. Doc-Only CI** | Klassifizierer-Schritt im Job (`git diff`); Job berichtet immer `success` | `paths-ignore` blockiert Required Checks auf `Pending` | Schrittweiser Filter in `ci.yml`, kein `paths-ignore` auf Workflow-Ebene |
| **2. Artifact Upload** | `timeout-minutes: 3` auf Step-Ebene + `compression-level: 0` | 11-Minuten-Hänger blockiert Job-Timeout | Step-Timeout und `compression-level: 0` für gepackte Artefakte setzen |
| **3. Testlaufzeiten** | Multi-Prozess auf 1 Runner (`--shards=4`, `pytest_shards.py`) | Matrix-Jobs erschöpfen Concurrency-Limits öffentlicher Repos | Single-Runner 4-Prozess-Modell beibehalten |
| **4. Issue Comments** | Frühes Job-`if` auf `pull_request` + Slash-Kommando-Präfix | Unnötige Workflow-Runs müllen PR-Checks-Tab zu | Strikte Filterung auf Job-Ebene, keine Bindung an PR-Head-Status |
| **5. Hinweise/Advisories** | `$GITHUB_STEP_SUMMARY` und `::notice` / `::warning` | Falscher Exit-Code färbt PR rot | `exit 0` mit Step-Summary-Rendering kombinieren |
| **6. Pip/Maven Cache** | `actions/setup-python` + `--require-hashes`; `setup-java` + strict checksums | Cache-Poisoning bei ungesicherten Downloads | Durch `--require-hashes` vollständig geschützt; spart messbar 15–30 s (pip) bzw. 60–120 s (Maven) |
