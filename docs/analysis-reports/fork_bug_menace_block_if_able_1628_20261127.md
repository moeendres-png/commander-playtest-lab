# Fork-Bug-Dossier: Menace und Pflicht „block if able“ (CR 509.1c, Issue #1628)

- **Datum:** 2026-11-27
- **Repository-Stand (`origin/main`):** `f13666f2c2288ab242fba7e4681a15e55ea0466b`
- **Gepinnter XMage-Fork (`config/rules_engines.json`):** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (Repo `moeendres-png/mage`, Version `1.4.62`, Requalifikation `v15`)
- **Upstream-Stand (`magefree/mage` `master`):** `900ee9ace38d58e9cf15cb9ebc7c51fb7c285d01` (`Combat.java` Blob-SHA `67f2a6f2ab0491ab4be3f6e8ccdb3e3a890b732f`)
- **Evidenzklasse:** `CODE_DERIVED` + `DIRECTLY_VERIFIED` (Code-Stellen im lokalen Pin-Checkout und in Upstream geprüft; Seed-3-Beleg aus PR `#1625` / `ev1584`)
- **Hinweis:** Reine Analyse und Entscheidungsoptionen. Kein Fork-Fix, kein Fork-Push, kein Repin (`AGENTS.md` §8: Owner-Vorbehalt; Owner-Entscheidung 2026-11-24 Option A: parken/dokumentiert lassen).

---

## 1. Ausgangsbefund und Beleg-Provenienz (`#1625` / `ev1584`)

- **Herkunft:** Review-Befund zu PR `#1625` (`#1584`), dokumentiert in `docs/analysis-reports/ev1584/pr_body.md` (Berichts-Branch im Remote, Commit `cef4825644ac`). Die rohe Spieldatei `a3.jsonl.gz` (Frames `2983–2998`) liegt nicht im Git-Repository (`AGENTS.md` §12).
- **Beobachtetes Spielgeschehen (Seed 3, Zug 40):**
  - Sitz 0 aktiviert `Brutal Hordechief` („Creatures your opponents control block this turn if able, and you choose how those creatures block“) und greift Sitz 1 (9 Leben) mit `Iroas, God of Victory`, `Stalking Vengeance` und `Sun Titan` an.
  - `Iroas, God of Victory` verleiht allen angreifenden/kontrollierten Kreaturen von Sitz 0 **Menace** (`getMinBlockedBy() == 2`).
  - Sitz 1 kontrolliert 16 Kreaturen; Sitz 0 (als Block-Bestimmer ≠ Verteidiger) wird in 16 Block-Frames (`2983–2998`) je Kreatur gefragt und antwortet jeweils mit `[]` („kein Block“).
  - Die Engine akzeptiert die leere Blockerklärung ohne Nachfrage.
- **Regelverstoß gegen CR 509.1c:** CR 509.1c verlangt, dass eine legale Blockerklärung die **maximale Zahl** an erfüllten Block-Anforderungen erreicht, ohne eine Restriktion (hier Menace: mindestens 2 Blocker pro Angreifer) zu verletzen. Bei 16 potenziellen Blockern und 3 Menace-Angreifern erfüllen Paare auf Menace-Angreifern bis zu 16 Anforderungen; die leere Erklärung erfüllt 0 und ist nach CR 509.1c illegal.

---

## 2. Verifikation am aktuellen Pin `f4d12f6e80`

Die Kette von den Karten in `Mage.Sets` bis zur Validierung in `Combat.checkBlockRequirementsAfter` wurde am aktuellen Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` geprüft:

1. **`BrutalHordechief.java` (`Mage.Sets/src/mage/cards/b/BrutalHordechief.java`, Z. 39–45):**
   - Aktivierte Fähigkeit fügt `new BlocksIfAbleAllEffect(StaticFilters.FILTER_OPPONENTS_PERMANENT_CREATURES, Duration.EndOfTurn)` sowie `new ChooseBlockersEffect(Duration.EndOfTurn)` hinzu.
2. **`IroasGodOfVictory.java` (`Mage.Sets/src/mage/cards/i/IroasGodOfVictory.java`, Z. 52–54):**
   - `GainAbilityAllEffect(new MenaceAbility(false), Duration.WhileOnBattlefield, filter)` setzt `minBlockedBy = 2` auf den Angreifern.
3. **`BlocksIfAbleAllEffect.java` (`Mage/src/main/java/mage/abilities/effects/common/combat/BlocksIfAbleAllEffect.java`, Z. 44–51):**
   - `mustBlock(game)` liefert `true` und **`mustBlockAny(game)` liefert `true`**.
4. **`Combat.java` (`Mage/src/main/java/mage/game/combat/Combat.java`) — drei Menace-Abkürzungen je Blocker:**
   - **(a) `mustBlockAllAttackers` für bereits blockende Kreaturen (Z. 1014–1024):**
     ```java
     if (attackingCreature.getMinBlockedBy() > 1) {
         ...
         if (attackingCreature.getMinBlockedBy() >= alreadyBlockingCreatures) {
             continue; // Attacker can't be blocked by the current blocker amount so check next attacker
         }
     }
     ```
   - **(b) `mustBlockAny || mustBlockAllAttackers` für noch nicht blockende Kreaturen (Z. 1094–1127 — der `BrutalHordechief`-Pfad):**
     ```java
     if (attackingCreature.getMinBlockedBy() > 1) {
         int alreadyBlockingCreatures = 0;
         ...
         if (attackingCreature.getMinBlockedBy() >= alreadyBlockingCreatures) {
             continue; // Attacker can't be blocked by the current blocker amount so check next attacker
         }
     } else {
         mayBlock = true;
         break;
     }
     ```
     Bei einer leeren Blockerklärung ist `alreadyBlockingCreatures == 0` und bei Menace `getMinBlockedBy() == 2`. Da `2 >= 0` immer `true` ist, überspringt die Schleife **jeden** Menace-Angreifer per `continue;`. `mayBlock` bleibt `false` — die leere Blockerklärung wird akzeptiert.
   - **(c) `creatureMustBlockAttackers` (Z. 1231–1260, inkl. XMage-eigenem `TODO` in Z. 1244–1245):**
     ```java
     if (attackingCreature.getMinBlockedBy() > 1) { // e.g. Menace
         if (attackersGroup.getBlockers().size() + 1 < attackingCreature.getMinBlockedBy()) {
             blockIsValid = true;
         }
     }
     ```
     Auch hier wird jeder erzwungene Blocker isoliert geprüft (`0 + 1 < 2` ist `true`), statt die Gesamtzahl verfügbarer Pflichtblocker zu berücksichtigen, die gemeinsam einen Menace-Angreifer legal blocken könnten.
   - **Gegenbeispiel im selben Verfahren (`mustBeBlockedByAtLeastX`, Z. 1162–1171):** Für „must be blocked by“-Effekte (z. B. `Neyith of the Dire Hunt`) prüft XMage bereits die Summe `mustBeBlockedByAtLeastX.get(id).size() < minPossibleBlockersMap.get(id)` — genau diese Gruppenbetrachtung fehlt bei `mustBlockAny` / `mustBlockAllAttackers` / `creatureMustBlockAttackers`.

---

## 3. Upstream-Stand (`magefree/mage`)

Geprüft gegen `magefree/mage` `master` (`900ee9ace38d58e9cf15cb9ebc7c51fb7c285d01`, `Combat.java` SHA `67f2a6f2ab0491ab4be3f6e8ccdb3e3a890b732f`, Stand 2026-11-27):

- **Dieselbe Lücke besteht unverändert in Upstream:**
  - `Combat.java` Z. `1070–1078` (`mustBlockAllAttackers`: `getMinBlockedBy() >= alreadyBlockingCreatures` → `continue;`)
  - `Combat.java` Z. `1173–1181` (`mustBlockAny || mustBlockAllAttackers`: `getMinBlockedBy() >= alreadyBlockingCreatures` → `continue;`)
  - `Combat.java` Z. `1310–1312` (`creatureMustBlockAttackers`: `attackersGroup.getBlockers().size() + 1 < attackingCreature.getMinBlockedBy()` → `blockIsValid = true;`)
- **Offene Upstream-Issues zum Themenkreis Menace + Blockpflicht:** `#6914` („"must block" plus "menace" bug observed“), `#6429` (`Nacatl War-Pride` + `Iroas`), `#10374` (`Slayer's Cleaver`), `#11661` (Anforderungen vs. Restriktionen), `#13290`, `#13305`. Das geschlossene `#13182` behebt nur ein Einzel-Paar-Deadlock und löst die Gruppenprüfung bei Menace nicht.

---

## 4. Entscheidungsoptionen und Risikoabwägung

| Option | Beschreibung | Risiko & Aufwand | Einordnung |
|---|---|---|---|
| **Option A (Empfohlen, entspricht Owner-Entscheid 2026-11-24)** | Als bekannte, seltene Engine-Lücke dokumentiert lassen und **mit dem nächsten ohnehin anstehenden Fork-Repin / Upstream-Sync bündeln** (gemeinsam mit `#1093` Master Chef). | **Aufwand:** 0 zusätzliche Kettenkosten jetzt. **Risiko:** Gering — tritt nur bei Kombination aus Menace (`minBlockedBy > 1`) und globaler Blockpflicht (`Brutal Hordechief`, `mustBlockAny`) auf; bei 1 verfügbarem Blocker wäre leerer Block ohnehin legal. | **Empfohlen** (`#1628`, Kommentar 7130951401). |
| **Option B** | Gezielter Einzel-Fix im Fork über eine eigene Kette (`v16`: Fork-Push, Repin, 2× PB-03, 2× Siegel, neue 36-Seed-Referenz). | **Aufwand:** Hoch (volle Kette für seltenen Randfall). **Risiko:** Mittel bis hoch — Eingriffe in `Combat.checkBlockRequirementsAfter` bergen bei gemischten Block-Restriktionen (Menace + `maxBlockedBy` + `can't block` + mehrere Angreifer) das Risiko neuer Endlos-Re-Asks / Deadlocks (vgl. Upstream `#11661`, `#13290`). | Nicht empfohlen als Einzel-Kette. |
| **Option C** | Fix zuerst an Upstream (`magefree/mage`) melden/einreichen und bei einem späteren Upstream-Merge übernehmen. | **Aufwand:** Gering lokal, aber unbestimmter Zeitplan bis Upstream-Merge. Vermeidet dauerhafte Fork-Divergenz in `Combat.java`. | Ergänzend zu Option A sinnvoll. |

---

## 5. Test-Entwurf für die spätere Kette (aus Seed 3 abgeleitet)

1. **Positiv-Repro (auf Pin `f4d12f6e80` ROT, nach Fix GRÜN):**
   - Aufbau: `Iroas, God of Victory` (Menace für eigene Angreifer) + `Brutal Hordechief` (aktiviert) auf Seite von Spieler A; Spieler B kontrolliert **2** ungetappte `Grizzly Bears`. Spieler A greift mit `Sun Titan` (oder `Iroas` + `Sun Titan`) an.
   - Erwartung: Eine leere Blockerklärung (`[]`) von Spieler A (als Block-Bestimmer) muss von `Combat.checkBlockRequirementsAfter` **abgelehnt** werden; erst eine Erklärung, bei der beide `Grizzly Bears` denselben Menace-Angreifer blocken, wird akzeptiert.
2. **Grenz-Negativ-Kontrolle (auf Pin `f4d12f6e80` und nach Fix GRÜN):**
   - Aufbau identisch, aber Spieler B kontrolliert nur **1** ungetappten `Grizzly Bears`.
   - Erwartung: Die leere Blockerklärung **muss akzeptiert** werden (kein Deadlock), da 1 einzelner Blocker einen Menace-Angreifer (`minBlockedBy == 2`) legal nicht blocken kann.
3. **Mehr-Angreifer-Kontrolle (CR 509.1c Maximierung):**
   - Aufbau: 2 Menace-Angreifer + **3** ungetappte Pflichtblocker auf Seite des Verteidigers.
   - Erwartung: Mindestens 2 Blocker müssen gemeinsam auf einen Menace-Angreifer gelegt werden (der 3. allein kann keinen zweiten Menace-Angreifer blocken → 2 erfüllte Anforderungen statt 0).
