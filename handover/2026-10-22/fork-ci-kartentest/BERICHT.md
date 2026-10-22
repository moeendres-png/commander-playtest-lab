# Stufe 4 der Effizienz-Offensive: Fork-CI, Kartentest-Zeit — Messung und Empfehlung

Stand: 2026-10-22 · Fork `moeendres-png/mage` @ `456b0e22` (Pin v11) · Messung: Muse
(lokale VM, JDK 17 wie die CI-Matrix, Worktree `wt-mage-v11`)
Auftrag: Klären, ob der Test-Job der Fork-CI die Kartendatenbank zwischen Läufen
behalten und Kartentests gebündelt laufen lassen soll. **Nichts gepusht, keine
Workflow-Datei geändert, kein Code angefasst.**

## Empfehlung: NEIN

Der belastbar gemessene Gewinn liegt bei **~30 s je CI-Lauf** (nur Mage.Tests) —
klar unter der ~1-Minute-Schwelle des Auftrags. Nur zusammen mit der zweiten,
ungemessenen Datenbank von Mage.Verify kratzt die Summe an der Schwelle
(~50–65 s brutto), ohne sie sicher zu reißen. Die Schrittzeit der CI streut
ohnehin zwischen 341 s und 474 s; ~30 s gehen darin unter. Der fertige
Workflow-Diff liegt trotzdem im Anhang — falls die Verify-Annahme später
gemessen wird und die Rechnung kippt, ist er ohne weitere Arbeit einsetzbar.

## Ausgangslage Fork-CI (DIRECTLY_VERIFIED, Actions-API, 2026-10-22)

- `.github/workflows/maven.yml`: ein Job, JDK 17 (temurin), `setup-java` mit
  `cache: maven` (cached nur Maven-Abhängigkeiten), danach ein Schritt
  `mvn test -B …` — **kein `clean`**, kein Cache für die Kartendatenbank, kein
  eigener Mage.Tests-Schritt (die ganze Suite läuft in dem einen Schritt).
- Schritt „Build and test": Referenzlauf 39654101249 (Pin `456b0e22`) **474 s**;
  zwei weitere grüne Läufe 341 s und 375 s; Gesamtlaufzeiten ~360–505 s.
- Referenz-Zahlen dieses Laufs: Mage.Tests 7467 Läufe / 0 Fehler /
  126 übersprungen; Mage.Verify 28 / 0 / 8.
- **Bündelung ist bereits Realität:** Keine Surefire-Overrides in den POMs →
  Defaults `forkCount=1`, `reuseForks=true` → eine JVM für die ganze
  Mage.Tests-Suite; der Datenbankbau fällt pro Lauf genau einmal an
  (plus einmal in Mage.Verify, s. u.). Hier ist nichts zu holen.

## Mechanik der Kartendatenbank (CODE_DERIVED)

- H2-Datei `./db/cards.h2` relativ zum Arbeitsverzeichnis
  (`DatabaseUtils.java:29`) → in den Tests `Mage.Tests/db/cards.h2.mv.db`,
  gemessen **262 MB** (eine Datei; dazu eine kleine `.trace.db`, die nicht in
  einen Cache gehört).
- Neubau-Auslöser in `CardRepository` (Konstruktor): DB-Datei fehlt, oder
  `CARD_DB_VERSION` (54) veraltet, oder „neuer Build". Der Build-Check
  (`RepositoryUtil.isNewBuildRun`) liest die Build-Zeit aus dem
  **Jar-Manifest**; unter `mvn test` im Reactor kommen die Klassen aus
  `target/classes` → `JarVersion.getBuildTime` liefert die Konstante
  `"runtime"` → Check wirkungslos → **eine wiederhergestellte DB würde in der
  CI tatsächlich wiederverwendet** (inkrementeller Scan statt Vollbau).
  Umkehrschluss: Wechselt die CI je auf `package`/`verify` (Jar-Modus), wird
  der Cache wirkungslos — aber auch dann nicht schädlich.
- `CardScanner.scan()` ergänzt Karten nur (add-only) und aktualisiert
  Set-Daten; **CardInfo bestehender Karten wird nie aktualisiert.** Eine
  veraltete DB zeigt also alte Kartendaten → falsch grüne/rote Läufe möglich.
  Genau dagegen muss der Cache-Schlüssel gebaut sein (s. Risiken).
- `mvn clean` löscht `Mage.Tests/db` (Fileset in `Mage.Tests/pom.xml`) —
  für die CI irrelevant, weil der Workflow ohne `clean` fährt und der
  Cache-Restore vor dem Build läge.

## Messung lokal (DIRECTLY_VERIFIED)

Gleiche Auswahl in allen Läufen: 4 Testklassen
(AffinityForArtifactsTest, AnnihilatorTest, AssistTest, AwakenTest),
`mvn -o -B -pl Mage.Tests -am test -Dtest=…`, JDK 17, Pin `456b0e22`.
Kalt = `Mage.Tests/db` vor dem Lauf gelöscht; warm = DB aus dem Kaltlauf
vorhanden. **Testzahlen in allen 7 Läufen identisch: 17 Läufe, 0 Fehler,
0 übersprungen** (inkl. Aufwärm-Lauf).

| Lauf   | Wandzeit | Maven gesamt |
|--------|----------|--------------|
| kalt 1 | 80,0 s   | ~76 s        |
| kalt 2 | 65,0 s   | ~62 s        |
| kalt 3 | 64,8 s   | ~62 s        |
| warm 1 | 27,7 s   | 24,9 s       |
| warm 2 | 22,9 s   | 20,6 s       |
| warm 3 | 25,6 s   | 23,1 s       |

- Median kalt 65,0 s, warm 25,6 s → **Delta ≈ 39 s** auf dieser VM (2 CPUs).
- Claudes Container-Werte (JDK 21): kalt 39,4 s / warm 9,9 s → Delta ≈ 30 s.
- Für die CI (4 vCPUs, JDK 17) sind ~**25–35 s** für Mage.Tests realistisch.
- DB-Datei komprimiert ~85 MB (gzip; actions/cache nutzt zstd, ähnliche
  Größe) → Restore/Save kosten zusammen nur wenige Sekunden (~2–5 s).

## Der zweite Datenbankbau: Mage.Verify (CODE_DERIVED, nicht gemessen)

`VerifyCardDataTest` nutzt denselben `CardRepository`/`CardScanner`-Pfad,
aber mit eigenem Modul-Arbeitsverzeichnis → eigene `Mage.Verify/db`, die auf
einem frischen Runner ebenfalls voll gebaut wird (~gleiche Größenordnung).
Beide DBs gecacht: ~50–65 s brutto, abzüglich ~5 s Transfer ≈ **~45–60 s
netto** — an der Schwelle, nicht sicher darüber. Das ist der einzige Punkt,
der die Empfehlung bei Nachmessung kippen könnte.

## Risiken (für den Fall einer späteren Umsetzung)

1. **Veraltete DB / falsch grün:** beherrschbar nur über einen strengen
   Schlüssel ohne `restore-keys` (ein Prefix-Treffer auf älteren Stand wäre
   genau das Stale-Szenario). Schlüssel = Hash über alle Quellen, die
   CardInfo-Inhalte formen: `Mage.Sets/src/**` (alle Karten-/Set-Klassen),
   `Mage/src/**` (Repository, Scanner, CardInfo-Ableitung, Versionskonstanten)
   plus die POMs (H2/ORMLite-Versionen). Jede relevante Änderung → Miss →
   normaler Lauf wie heute + neuer Cache-Eintrag. Ein Stale-Treffer bräuchte
   eine CardInfo-wirksame Änderung außerhalb all dieser Pfade; keine bekannt.
2. **H2-Lock-Startrennen (XMAGE_CARD_REPOSITORY_INIT_FAILED, #731/#878):**
   Entstand bei parallelem Erstbau derselben DB durch mehrere JVMs. In der
   Fork-CI gibt es einen Maven-Prozess, einen Surefire-Fork; der Restore
   läuft vor dem Build, einseitig. Kein neues Rennen — der kritische Erstbau
   entfiele sogar. Nur die `.mv.db`-Datei cachen (keine `.lock.db`/`.trace.db`),
   Cache-Schreiben passiert im Post-Schritt nach JVM-Ende.
3. **`mvn clean`:** in der CI nicht verwendet (s. o.); lokal unverändert.
4. **Cache-Hygiene:** Jeder Karten-Quellstand erzeugt einen neuen ~85-MB-
   Eintrag; GitHub räumt ab 10 GB LRU auf — bei der aktuellen Laufkadenz
   unkritisch. Korrupter Restore wäre der neue Fehlermodus (H2-Fehler → roter
   Lauf bis zum nächsten Schlüsselwechsel); Eintrittswahrscheinlichkeit
   gering, aber nicht null — ein weiterer Grund für die Schwelle.

## Anhang: fertiger Workflow-Diff (als Text, NICHT empfohlen)

Einfügen in `.github/workflows/maven.yml` zwischen „Setup JDK" und
„Build and test" (Hans setzt ihn ggf. selbst im Web-UI):

```diff
     - name: Setup JDK ${{ matrix.java }}
       uses: actions/setup-java@v5
       with:
         java-version: ${{ matrix.java }}
         distribution: ${{ matrix.distribution }}
         java-package: ${{ matrix.package }}
         cache: maven
+    - name: Cache card databases (Mage.Tests + Mage.Verify)
+      uses: actions/cache@v4
+      with:
+        path: |
+          Mage.Tests/db/cards.h2.mv.db
+          Mage.Verify/db/cards.h2.mv.db
+        key: xmage-carddb-${{ hashFiles('Mage.Sets/src/**', 'Mage/src/**', 'pom.xml', 'Mage/pom.xml', 'Mage.Sets/pom.xml', 'Mage.Tests/pom.xml', 'Mage.Verify/pom.xml') }}
     - name: Build and test
       run: mvn test -B -Dxmage.dataCollectors.printGameLogs=false -Dlog4j.configuration=file:${GITHUB_WORKSPACE}/.travis/log4j.properties
```

Bewusst **ohne** `restore-keys`: Ein Teiltreffer auf einen älteren
Kartenstand wäre das Falsch-grün-Risiko aus Risiko 1; ein Miss kostet nur
einen normalen Lauf.

## Evidenz

- CI-Zeiten/Zahlen: GitHub-Actions-API (öffentlich), Läufe 39654101249,
  39678290036, 39488646515 — DIRECTLY_VERIFIED.
- Mechanik: `DatabaseUtils.java`, `CardRepository.java`,
  `RepositoryUtil.java`, `JarVersion.java`, `CardScanner.java`,
  `Mage.Tests/pom.xml` @ `456b0e22` — CODE_DERIVED.
- Deltas: lokale Messung oben (7 Läufe, identische Testzahlen) —
  DIRECTLY_VERIFIED für diese Auswahl; Vollsuite nicht lokal gefahren.
  CI-Übertragung (~25–35 s) ist eine Schätzung aus zwei Messpunkten
  (diese VM + Claudes Container) — MODELED.
- Mage.Verify-Zweitbau: CODE_DERIVED, Betrag nicht gemessen (UNKNOWN ≈
  gleiche Größenordnung wie Mage.Tests).
