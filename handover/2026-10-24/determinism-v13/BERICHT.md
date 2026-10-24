# #1001: v13-Rest-Nichtdeterminismus — Rate, Locate, Ursache, Vorschlag

**Auftrag:** Issue #1001 (Folgeauftrag aus dem #999-Bericht, M7 + P9).
**Stop-Bedingung:** Bericht in `handover/2026-10-24/determinism-v13/` auf `muse/claude-handover`.
**Fences eingehalten:** Kein Pilot-Code, kein `engine-bridge/**`, kein Fork, keine Decks geändert.
Patches unten sind Text, nicht angewendet.

## Source Lock (DIRECTLY_VERIFIED)

- Lab: `main` @ `77a20020c14368a8cc8d71bcce11918f3afa81c3` (exakt das #1001-Minimum),
  Worktree `wt-1001`. `config/rules_engines.json` nennt Pin v13 `90f5c4d3f8`.
- Fork: `wt-mage-v13` @ `90f5c4d3f8d3b799b15b6675fcce40bb0dd4738e` (identisch zum Pin).
- Bridge-JAR frisch im Worktree gebaut (Fork-Install + Bridge-Package, beides Exit 0):
  `~/workspace/tmp/1001/bridge_v13.jar`, sha256
  `38307d4baed77938ed92d7c5bec62d5905a387f136aac8db7c29c2caf34428f7`.
  Hinweis: Dieser Hash unterscheidet sich vom #999-JAR (`87ece5e4…`), obwohl
  Bridge-Quellen (`diff -r engine-bridge`, ohne `target/`) und Fork-Pin byte-identisch
  sind — JARs betten Build-Zeitstempel ein. Provenienz ist Quellen + Pin, nicht JAR-Hash.
- Treiber: `run_rate.py` (je Fall 10×, frische JVM je Spiel, Transkript + Hash je Lauf),
  `compare_runs.py` (erste Differenz mit der Normalisierung aus `determinism_probe.py`),
  Probe `play`/`compare`/`locate` aus `scripts/determinism_probe.py`.

## Item 1 — Rate (DIRECTLY_VERIFIED)

Befehl je Fall (sequenziell, eine JVM zur Zeit):

```
PYTHONPATH=src python ~/workspace/tmp/1001/run_rate.py <pod025|p9|control> 10
```

| Fall | geplant | ok | Fehler | distinkte semantische Hashes |
|---|---|---|---|---|
| pod-025, Seed 1 | 10 | 10 | 0 | 3: `8e3fa0b8…` ×8, `bd41ef03…` ×1, `268d0bb7…` ×1 |
| P9 `custom/rogshai#variant1\|seed=3\|seat=3` | 10 | 10 | 0 | 2: `4d30fc73…` ×6, `8d9c5bd9…` ×4 |
| Kontrolle (stabiler M7-Pod pod-000, Seed 1) | 10 | 10 | 0 | 1: `9fc88690…` ×10 |

Wrong-Reason-Kontrolle bestanden: Der stabile Pod zeigt 10/10 denselben Hash —
die Divergenzen der beiden anderen Fälle sind kein Messartefakt.

Mess-Artefakt, offengelegt: Der erste Durchlauf (3 Ketten parallel auf der
2-CPU-Box) lief in 28/30 Spielen in `BRIDGE_TIMEOUT` — Last-Konkurrenz, keine
Engine-Aussage. Alle 28 Fehler-Dateien gelöscht, sequenziell neu gespielt:
30/30 ok. Ein einzelner Retry hatte das bereits vorher gezeigt (P9 Run 9/10
solo ok). Die Timeout-Diagnostik-Hashes waren je Fall identisch
(`bda59511…`, `c90afea…`, `69ffa6e5…`), d. h. die Timeouts schlugen an
derselben Stelle zu — konsistent mit Überlast, nicht mit Spielinhalt.

**Einschränkung des Hashes (wichtig für die Rate):** Der semantische Hash
(`full_game.py: semantic_transcript`) enthält je Frame nur Prompt, *gewählte*
Labels und Outcomes — nicht die *angebotenen* Optionen und nicht den
`pilot_state`. Zwei Spiele mit derselben Wahl bei unterschiedlichem Angebot
haben denselben Hash. Die Rate zählt daher eine Untergrenze der
Verhaltensvarianten: pod-025 zeigt mindestens 4 Varianten (s. Item 2/3),
nicht 3.

## Item 2 — Locate (DIRECTLY_VERIFIED)

### pod-025

Transkript-Ebene (eigene Rate-Transkripte, Probe-Normalisierung):

```
python compare_runs.py rate/pod025/run-01.json rate/pod025/run-02.json
python compare_runs.py rate/pod025/run-01.json rate/pod025/run-10.json
```

- Erste Differenz, beide Paare: **Frame-Index 3246 (Seq 3247)**, direkt nach
  `choose_use` Sitz 0 „Use effect of Sakashima the Impostor?" (Seq 3245, Antwort
  in allen Läufen identisch: `Yes`).
- run-01 vs run-02: A `choose_object` Sitz 0 „Select a creature" `[Lucius the Eternal]`;
  B `choose_use` Sitz 2 „Move Kalemne … (EXILED)?". B stellt die Ersatz-Fragen
  zuerst, A die Kopie-Wahl zuerst — keine „Extra-Frage", sondern andere
  Reihenfolge plus (s. unten) entfallene Kopie-Wahl in B.
- run-01 vs run-10: beide `choose_object` Sitz 0 „Select a creature", aber
  A `[Lucius the Eternal]`, B `[Taurean Mauler]`. Danach 130 abweichende Frames
  von 3962 — keine Rekonvergenz.
- run-02 hat nach Seq 3247 überhaupt keine Kopie-Wahl mehr; Sakashima betritt
  als er selbst (belegt Seq 3379: „Choose creatures blocked by Sakashima the
  Impostor" — „Sakashima the Impostor blocks Taurean Mauler").

Probe-Ebene (`locate --mode none --baseline`, Dumps in
`probe_pod025_none/`):

```
python scripts/determinism_probe.py compare probe_pod025_none/standard.jsonl.gz \
  probe_pod025_none/standard-again-run1.jsonl.gz
→ ANSWERS_DIFFER, 1981 Entscheidungen, 359 Requests / 42 Antworten abweichend
```

- Erste *Request*-Differenz: **Entscheidung 1622** (`choose_use` Sakashima) —
  nur im `pilot_state` sichtbar: Schlachtfeld-Größen, Bibliotheks-Anzahlen und
  offenbarte Karten differieren bereits, obwohl alle Antworten bis dahin
  identisch sind.
- Erste *Antwort*-Differenz: **Entscheidung 1623** (`choose_object`
  „Select a creature"): links `[Taurean Mauler]`, rechts `[Lucius the Eternal]`.

### P9-Fall

```
python compare_runs.py rate/p9/run-01.json rate/p9/run-02.json
```

- Erste Differenz: **Frame-Index 1240 (Seq 1241)**, exakt die #999-Signatur:
  `choose_use` Sitz 2, A „Move Rograkh, Son of Rohgahh … (GRAVEYARD)?",
  B „Move Ishai, Ojutai Dragonspeaker … (GRAVEYARD)?".
- Kontext: Seq 1235–1239 Tergrid's Shadow — jeder Gegner opfert 2 Kreaturen;
  Sitz 2 opfert Ishai + Rograkh in einem Vorgang (Seq 1237, beide Ziele gewählt),
  danach die Ersatz-Fragen in variabler Reihenfolge.

## Item 3 — Ursache

### (a) P9: Opfer-Reihenfolge in einem HashSet — GEFUNDEN

Kette, jede Stufe belegt:

1. `Mage/src/main/java/mage/abilities/effects/common/SacrificeAllEffect.java:82`
   sammelt alle gewählten Permanents (APNAP-Reihenfolge der Wählenden) in
   `Set<UUID> perms = new HashSet<>()`, und `:109` opfert sie in
   `for (UUID permID : perms)` — also in HashSet-Reihenfolge.
   `UUID.hashCode()` ist wertbasiert über zufällige (pro Lauf neue) UUIDs:
   Die Reihenfolge variiert von Lauf zu Lauf.
2. Die Friedhofs-Ankunftsreihenfolge ist die Opfer-Reihenfolge.
3. `Mage/src/main/java/mage/game/GameImpl.java:2718–2765` fragt die
   Kommandanten-Ersatz-Fragen in Friedhofs-Reihenfolge zuerst (danach Exil
   nach Name sortiert). Der dortige Kommentar dokumentiert bereits den
   v13-Fix für die Frage-Reihenfolge bei gegebener Friedhofs-Reihenfolge —
   der Fix greift nicht, weil die Friedhofs-Reihenfolge selbst variiert.
   Ergebnis: Rograkh-zuerst vs. Ishai-zuerst (Seq 1241).
4. State-Diff-Beleg aus den Probe-Dumps (`probe_p9/a.jsonl.gz` vs `b.jsonl.gz`,
   beide 2938 Entscheidungen, Probe-`compare`):
   `REQUESTS_DIFFER_ANSWERS_SAME`, nur 2 Requests abweichend, 0 Antworten.
   Erste Differenz an Entscheidung 620 (`choose_use`, Zug 14):
   `.req.pilot_state.players[2].graveyard[1].name` = Ishai | Rograkh,
   `.req.pilot_state.players[2].graveyard[2].name` = Rograkh | Ishai,
   `.req.prompt` = „Move Ishai … (GRAVEYARD)?" | „Move Rograkh … (GRAVEYARD)?".
   Kontext-Entscheidungen 617–619 sind die Tergrid's-Shadow-Opfer
   (Elvish Mystic, Rograkh, Prowler). Die Zustände differieren also genau an
   der benannten Stelle (Friedhofs-Reihenfolge Sitz 2) unmittelbar vor der
   divergierenden Anfrage, und die Anfrage folgt der Friedhofs-Reihenfolge.
   Zusatz: In diesen beiden Läufen sind die Antworten identisch (beide
   Fragen je Position gleich beantwortet) — die Divergenz ist hier
   spielneutral; sie wäre es nicht, sobald der Pilot je Kommandant
   unterschiedlich antwortet.

Evidenzklasse: Code-Stellen DIRECTLY_VERIFIED (gelesen, Zeilen zitiert);
Kette CODE_DERIVED + Dump-Beleg (s. Anhang nach P9-Probe).

### (b) pod-025: Chaos-Mutation-Spielerreihenfolge in einem HashSet — GEFUNDEN

Kette, jede Stufe belegt:

1. Ziele identisch: Entscheidung 1608 (`target`, „Select creatures controlled
   by different players"), Sig in beiden Spielen identisch:
   `[Warchief Giant, Kalemne, Zndrsplt]` — Controller Sitz 1, 2, 0.
   Exil-Zonen an Entscheidung 1622 in beiden Spielen identisch.
2. `Mage.Sets/src/mage/cards/c/ChaosMutation.java:74` sammelt die Ziele in
   `.collect(Collectors.toSet())` — ein `HashSet<Permanent>`.
   `CardImpl`/`PermanentImpl` überschreiben `hashCode`/`equals` nicht
   (grep: kein Treffer) → Identity-Hashing → Iterationsreihenfolge variiert
   je JVM. `:78–80` baut daraus die `players`-Liste, `:86` die
   Offenbarungs-Schleife in genau dieser Reihenfolge.
3. Sitz 0 offenbart Sakashima the Impostor (in beiden Spielen identisch:
   Risky Move, Path of Ancestry, Sword of Vengeance, Sakashima).
   Beim Betreten Sakashimas pausiert die Schleife an der Kopie-Wahl
   (Entscheidung 1622 `choose_use` → 1623 `choose_object`).
4. An der Pause liegen nur die Kreaturen der *bereits* verarbeiteten Spieler
   aus: Spiel A (Reihenfolge Sitz 2 vor Sitz 0): nur Taurean Mauler →
   Kopie-Wahl `[Taurean Mauler]`. Spiel B (Sitz 1 vor Sitz 0): nur Lucius →
   `[Lucius]`. Sitz 0 zuerst (run-02): noch keine Kreatur aus →
   keine Kopie-Wahl, Sakashima betritt als er selbst.
   Sakashima kopiert laut Implementierung *jede* Kreatur auf dem Schlachtfeld
   (`SakashimaTheImpostor.java`: `CopyPermanentEffect` mit
   `FILTER_PERMANENT_CREATURE`) — die Singleton-Angebote sind also exakt die
   jeweils ausliegenden Kreaturen, kein Filter-Artefakt.
5. Kausaltest (`locate --mode 2`, konstanter Identity-Hash → Einfüge-Reihenfolge
   = Ziel-Reihenfolge = Sitz 1, 2, 0 = Sitz 0 zuletzt): 6/6 Mode-2-Spiele
   identisch (Hash `8e3fa0b8…`), alle mit der vorhergesagten Variante
   `[Lucius the Eternal, Taurean Mauler]` an Entscheidung 1623 — eine Variante,
   die in den 10 plain Rate-Läufen nicht vorkam. Das bestätigt die Klasse
   (Hash-Ordnung) und die vorhergesagte Einfüge-Reihenfolge; die
   entscheidende Evidenz bleibt Kette 1–4 (Code + Dumps).

Evidenzklasse: DIRECTLY_VERIFIED (Code-Zeilen, Dump-Diffs, Mode-2-Läufe).

## Item 4 — Vorschlag (Patch-Texte, NICHT angewendet)

### P-A: SacrificeAllEffect — LinkedHashSet statt HashSet

```diff
--- a/Mage/src/main/java/mage/abilities/effects/common/SacrificeAllEffect.java
+++ b/Mage/src/main/java/mage/abilities/effects/common/SacrificeAllEffect.java
@@ -79,7 +79,7 @@
-        Set<UUID> perms = new HashSet<>();
+        Set<UUID> perms = new LinkedHashSet<>();
```

Wirkung: Die Opfer-Reihenfolge ist die Wahl-Reihenfolge (APNAP der Wählenden,
dann je Spieler die Auswahl-Reihenfolge) — deterministisch, regelkonform
(keine Regel schreibt eine Opfer-Reihenfolge vor; die bisherige war
willkürlich, nicht regelgefordert). Kein Options-Text ändert sich.

Verträglichkeit mit den 49 stabilen M7-Paaren (gemessen an den
`base_twin`-Transkripten): 9 stabile Spiele enthalten Mehrfach-Opfer, aber
in keinem wird ein Vorgang mit zwei Kommandanten geopfert (max. 1 Kommandant
je Vorgang, nur pod-023: Breya + je ein Nicht-Kommandant) — die
Ersatz-Frage-Reihenfolge ändert sich dort also nicht. Rest-Annahme
(CODE_DERIVED, nicht gemessen): Zwei Kommandanten desselben Owners aus
*verschiedenen* Vorgängen in derselben SBA-Prüfung wären ebenfalls betroffen;
in den Transkripten nicht belegt. Der semantische Hash sieht
Friedhofs-Reihenfolge ohnehin nicht (nur Prompts/gewählte Labels/Outcomes) —
eine Hash-Änderung tritt nur dort auf, wo die Frage-Reihenfolge sichtbar wird,
und das ist in den stabilen Paaren nicht der Fall.

### P-B: ChaosMutationEffect — Ziel-Reihenfolge erhalten statt HashSet

```diff
--- a/Mage.Sets/src/mage/cards/c/ChaosMutation.java
+++ b/Mage.Sets/src/mage/cards/c/ChaosMutation.java
@@ -70,10 +70,10 @@
-        Set<Permanent> permanents = this
+        List<Permanent> permanents = this
                 .getTargetPointer()
                 .getTargets(game, source)
                 .stream()
                 .map(game::getPermanent)
                 .filter(Objects::nonNull)
-                .collect(Collectors.toSet());
+                .collect(Collectors.toList());
```

(Alternativ `LinkedHashSet`, falls ein Set-Typ benötigt wird — die
Duplikatfreiheit ist durch die Zielwahl bereits garantiert: Ziele sind
verschiedene Permanents.) Die `players`-Liste folgt dann der
Ziel-Reihenfolge (Entscheidung 1608: Warchief Giant, Kalemne, Zndrsplt →
Sitz 1, 2, 0 → Sitz 0 zuletzt). Kein Options-Text ändert sich.

Verträglichkeit mit den 49 stabilen M7-Paaren (gemessen): Chaos Mutation
wird in genau einem der 50 Twin-Spiele gewirkt — pod-025 selbst (10
Mana-Payment-Prompts = 1 Cast). In den 49 stabilen Paaren kommt die Karte
nicht vor → keine Hash-Änderung durch P-B.

### Was die Fixes nicht abdecken (ehrliche Grenze)

Beide Fixes beseitigen die zwei hier isolierten Ordnungsquellen. Sie sind
kein Beweis, dass v13 danach vollständig deterministisch ist: Die
#999-Restrate (~1–2 %) beruhte auf genau diesen zwei Fällen; ob weitere
HashSet-Iterationen an anderen Stellen (andere Karten/Effekte) dieselbe
Klasse zeigen, ist mit dieser Stichprobe (pod-025, P9, Kontrolle) nicht
ausgeschlossen. Empfohlen: Nach dem #979-Batch die M7-Twins (50 Pods) und
die P9-Replays erneut laufen lassen — erst dann ist die Restrate neu zu
beziffern, nicht vorher.

## Testkommando

```
python -m pytest tests/unit -q -k "determinism_probe"
→ 31 passed, 2908 deselected (wt-1001, 9,52 s)
```

## Anhang — Befehle und Dateien

- Rate: `~/workspace/tmp/1001/rate/{pod025,p9,control}/run-*.json` (je 10, mit
  Transkript + semantischem Hash).
- Vergleiche: `~/workspace/tmp/1001/compare_runs.py` (erste Differenz,
  Probe-Normalisierung).
- Probe-Dumps pod-025: `~/workspace/tmp/1001/probe_pod025_none/`
  (standard + standard-again-run1), `~/workspace/tmp/1001/probe_pod025_mode2/`
  (standard + hashCode=2-run1..3 + extra-run4..6).
- Probe-Dumps P9: `~/workspace/tmp/1001/probe_p9/` (a + b).
- Bau: `~/workspace/tmp/1001/build_1001.sh`, Logs `mvn_fork.log`/`mvn_bridge.log`.
