# #1715 Ursachenanalyse (nur gelesen): trigger_order-Gleichstand und EXILED-Fallback

Stand: Lab `main` 5d338376, Fork-Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json:50`),
Fork über `gh api` (REST) gelesen. Keine Änderung, kein Kommentar, kein Push. `SIMULATED_RESULT`-Daten nur aus den Berichten.
Abkürzungen: **V** = VERIFIED_IN_CODE, **H** = HYPOTHESE, **U** = UNKNOWN. Fork-Pfade relativ zu `Mage/src/main/java/mage/`.

## (1) Herkunft der Eingangsreihenfolge bei Gleichstand (Kaldra-Fall)
- **V** Bridge sortiert stabil (`List.sort` = TimSort) nur nach `abilityLabel` + `getZoneChangeCounter(sourceId)`:
  `engine-bridge/.../XmageFullGamePlayer.java:2650-2656`; `abilityLabel` = Quellname + `ability.toString()` (`:4131-4136`),
  enthält also weder Ziel noch auslösendes Ereignis. Gleichstand behält die Reihenfolge von `abilities`.
- **V** `abilities` kommt aus `game/GameImpl.java:2616` (`state.getTriggered(playerId)`) → `:2636 chooseTriggeredAbility`.
- **V** `getTriggered` filtert eine `ArrayList` in Einfügereihenfolge (`game/GameState.java:99, 1269-1271, 1293-1296`).
  Diese Stufe ist deterministisch; die Reihenfolge ist die Reihenfolge, in der Trigger *ausgelöst* wurden.
- **V** Auslösen: `GameState.handleEvent` (`:1075-1079`) → `TriggeredAbilities.checkTriggers` iteriert eine
  `LinkedHashMap` in Einfügereihenfolge (`abilities/TriggeredAbilities.java:20, 106-110`) → `checkTrigger` (`:220-287`)
  → `TriggeredAbilityImpl.trigger` → `game.addTriggeredAbility` (Kopie + `newId()`, `GameImpl.java:2477-2478`).
  Die Trigger-Sammlung selbst ist also **nicht** HashMap-geordnet.
- **V** Kaldra Compleat verleiht `DealsDamageToACreatureTriggeredAbility` (`Mage.Sets/.../k/KaldraCompleat.java:63-74`),
  die je `DAMAGED_PERMANENT`-Ereignis einmal auslöst (`abilities/common/DealsDamageToACreatureTriggeredAbility.java:49-50`).
  Mehrere gleichlautende Trigger derselben Quelle (gleiches Label, gleicher ZCC) unterscheiden sich nur im Ereignis.
- **V** Die Ereignisreihenfolge entsteht im Kampfschaden: `game/combat/CombatGroup.java:321` `Map<UUID,Integer> assigned = new HashMap<>()`,
  iteriert bei `:426` per `entrySet()` → `blocker.markDamage(...)` → `PermanentImpl.markDamage` ruft sofort `doDamage`
  (`game/permanent/PermanentImpl.java:1299-1301`) → `game.fireEvent(DamagedPermanentEvent)` (`:1216-1218`) →
  `GameImpl.fireEvent` = `state.handleEvent` (`GameImpl.java:3883-3885`). Gleiches Muster `CombatGroup.java:464/500` und `:559/612`.
- **V** Schlüssel sind Objekt-UUIDs aus `UUID.randomUUID()` (`cards/CardImpl.java:148`, `MageObjectImpl.java:58`);
  die `HashMap`-Iterationsreihenfolge hängt von `UUID.hashCode()` ab und wechselt damit zwischen Partien/JVMs.
- **H** Genau dieser Pfad erklärt Seed 11 (5P, 2 Trigger) und `s2000-t5` (6P, 3 Trigger): Kaldra-Germ von 2 bzw. 3
  Kreaturen geblockt, Schaden über `assigned` verteilt. Plausibel, aber nicht an den Spiellogs geprüft (Blocker-Anzahl `U`).
- **H** In `up` vs. `down` (gleiche JVM, Seed 11 gleich, gegen `single` verschieden) ist Gleichheit dann Zufall (≈1/2 bei 2 Triggern);
  keine JVM-weite Ordnung. Andere Gleichstandsquellen (zwei gleiche Quellen mit gleichem ZCC, verzögerte Trigger) sind `U`.
- **V Nebenbefund:** `abilityOptionId` = `stableId("trigger", sourceId, originalId)` (`XmageFullGamePlayer.java:4138-4144`);
  Kopie übernimmt, `newId()` ändert `originalId` nicht (`abilities/AbilityImpl.java:115, 156-165`). Gleichlautende Trigger derselben Quelle
  bekommen also **dieselbe Options-ID**; `byId.put` (`:2658-2666`) behält die letzte. **H** Welche Instanz aufgelöst wird,
  hängt dann allein von der Eingangsreihenfolge ab, nicht von der Pilotenwahl. **V** Der Controller prüft nur doppelte *gewählte* IDs (`XmageFullGameDecisionController.java:755-757`), nicht doppelte *angebotene*.

## (2) Seed 123: EXILED → `UUID::toString`
- **V** `objectKey` setzt Position nur für LIBRARY/GRAVEYARD/HAND, sonst `-1` (`XmageStableOrder.java:64-75`);
  `contentKey` = `""` für Nicht-Permanente (`:88-91`); letzter Schlüssel `UUID::toString` (`:39`).
- **V** Die verglichenen UUIDs sind Karten-`objectId`s aus `UUID.randomUUID()` (`cards/CardImpl.java:148`), pro Partie neu,
  **nicht** aus dem Seed: der Seed bindet nur die Regel-RNG (`GameImpl.java:157, 201-203, 301-312`;
  Bridge `XmageGameManager.java:320-322`). `UUID.randomUUID` ist nicht seedbar. Fähigkeiten: `AbilityImpl.java:103, 159, 170`.
  Der Klassenkommentar sagt selbst „random per game“ (`XmageStableOrder.java:21, 30-31`).
- **Hypothese aus PR #1716 damit bestätigt (V für den Mechanismus):** zwei exilierte `Plains` gleichen Namens/ZCC werden
  nach Zufalls-UUID geordnet → `[id#3359,id#3360]` vs. umgekehrt. Die konkrete Frame-Stelle 2620 ist Beobachtung aus PR #1716.
- **V** Das Exil des Forks hat eine Einfügeordnung (`game/ExileZone.java:10` → `cards/CardsImpl.java:19` `LinkedHashSet<UUID>`);
  die Bridge nutzt sie in `objectKey` nicht.

## (3) Sitzzahl-Unabhängigkeit
- **V** Keiner der Pfade aus (1) und (2) liest die Sitzzahl (CombatGroup-HashMap, Trigger-Sortierung, `objectKey`).
- **V (Beobachtung, Bericht)** Der EXILED-Fall ist bereits ein **4P**-Fall (Seed 123, `pod="real"`, PR #1716 / `#1588`).
- **U** Ein 4P-Fall des trigger_order-Gleichstands ist nicht gemessen; Auftreten erfordert Mehrfachblock + Mehrfach-Trigger.

## (4) Vergleicht der Bridge-Gate-Referenzsatz über JVMs?
- **V** Ja, konstruktionsbedingt: BEFORE- und AFTER-Lauf sind getrennte Prozesse mit verschiedenen Jars
  (`docs/STUDIO_PLAN_SIMULATOR.md:58-67`, `AGENTS.md:345-351`). `--frame-digest` ist Standard (`scripts/benchmark_xmage_full_games.py:649-654`,
  `BooleanOptionalAction`, `default=True`), auch ohne Flag in den Gate-Befehlen. `compare` vergleicht `frame_digest`,
  `frames`, `frame_digest_by_seat` (`:446-452`), Exit 1 bei Frame-Abweichung (`:484`); mit `--expect-games` fehlt ohne Digest
  das Gate (`:397-405`, `docs/STUDIO_BRIDGE_GATE_TOOLING.md:21-25`). Normalisierung `id#<n>` nach erstem Auftreten
  (`src/commander_lab/engine/rules/frame_digest.py:16, 103-127`): eine Vertauschung gleichartiger Objekte ändert den Digest.
- **H** Warum der semantische Hash `s2000-t5` nicht sieht: gleichlautende Trigger tragen dieselbe Options-ID (Nebenbefund (1)),
  die aufgezeichnete Wahl ist also gleich, egal welche Instanz auflöst; erst spätere Frames unterscheiden sich.
  Der Frame-Digest fängt das, der semantische Hash nicht.
- **Vorhandene 4P-n/N (Bericht `docs/analysis-reports/owner_pc_throughput_1588_20261120.md:43-45`, `real`-Tisch,
  getrennte JVMs):** Seeds 1–48 (enthält den Referenzsatz 1–36) `48/48` Frame-Digest gleich; über 1–168 `165/168`;
  Abweichungen 94 und 147 = `_UUID_RE` (PR #1716, offen), 123 = EXILED-Fallback. trigger_order-Fälle: `0/168` beobachtet.
- **H** Da jede Gleichstandsstelle ein ca. 50/50-Münzwurf je Lauf ist, belegt `48/48` nur, dass im Referenzsatz bisher
  keine solche Stelle getroffen wurde, nicht ihre Abwesenheit; trifft ein Gate-Lauf eine, scheitert `compare` echt
  (Exit 1), obwohl die Bridge-Änderung unschuldig ist (Flake-FAIL, nicht nur eine gedruckte Zahl).

## (5) Wo läge ein Fix, und ist er Owner-Sache?
- **Bridge-Option (H, viable):** (a) `XmageStableOrder.objectKey` gibt EXILED eine Position aus der Einfügeordnung der
  `ExileZone`; (b) `trigger_order` bekommt einen Gleichstandsschlüssel aus regelsichtbarem Inhalt (z. B. `objectKey`/
  `contentKey` des Ziels bzw. betroffenen Objekts der Trigger-Instanz) und eindeutige Options-IDs. Bleibt ein Rest völlig
  ununterscheidbarer Objekte, ist die Reihenfolge regelseitig egal, beeinflusst aber `id#`-Nummerierung → `U`, ob vollständig lösbar.
  Einordnung: `engine-bridge/` unter dem Studio-Bridge-Gate (`AGENTS.md:338-361`), Art `BEHAVIOUR` (angebotene Reihenfolge
  ändert sich); kein neues Seal, PB-03 läuft, `BRIDGE_AHEAD_OF_QUALIFICATION`. Kein Fork, kein Pin, kein WS17.
- **Fork-Option (H):** `HashMap` → `LinkedHashMap` in `CombatGroup.java:321/464/559` (wie frühere Fork-Determinismus-Commits,
  `config/rules_engines.json:4`). Ordnet nach `blockers`-Liste; behebt (1) an der Quelle, nicht (2). Fork-Push, Repin,
  Requalifikation/Seals sind **Owner-only** (`AGENTS.md:217-221`). `WS17_SHA256SUMS` nur bei Workflow-Änderung (`AGENTS.md:218-220`).
- **Empfehlung (H):** Bridge-Option zuerst (ohne Owner-Gate möglich), Fork-Option als Owner-Entscheid notieren.
  Issue-Frage (3) „semantischer Hash soll Zustandsdivergenz erfassen“ ist nicht Teil dieser Analyse (`U`).
