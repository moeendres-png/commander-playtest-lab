# Fork-Bug-Dossier: Master Chef (+1/+1-Marker bei Commander-ETB, Issue #1093)

- **Datum:** 2026-11-27
- **Repository-Stand (`origin/main`):** `f13666f2c2288ab242fba7e4681a15e55ea0466b`
- **Gepinnter XMage-Fork (`config/rules_engines.json`):** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (Repo `moeendres-png/mage`, Version `1.4.62`, Requalifikation `v15`)
- **Upstream-Issue:** `magefree/mage#12239` („[[Master Chef]] not adding +1/+1 counter to commander as commander ETBs“)
- **Evidenzklasse:** `BELEGT_REPRODUZIERT` (`DIRECTLY_VERIFIED` am aktuellen Pin `f4d12f6e80` in einem temporären, isolierten lokalen Pin-Checkout unter `$HOME/studio-analyse/mage-repro-1093`, danach gelöscht; der lokale Fork-Checkout blieb unverändert auf `f4d12f6e80` mit sauberem `git status`).
- **Hinweis:** Reine Analyse und Fix-Entwurf als Entscheidungsgrundlage. Kein Fork-Fix, kein Fork-Push, kein Repin (`AGENTS.md` §8: Owner-Vorbehalt).

---

## 1. Reproduktion am aktuellen Pin `f4d12f6e80`

- **Testumgebung:** Temporärer lokaler Checkout von Pin `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`$HOME/studio-analyse/mage-repro-1093`), OpenJDK `21.0.13.1`, Maven `3.9.12`.
- **Befehl:** `mvn -B -pl Mage.Tests -Dtest=MasterChefCommanderEtbReproTest test`
- **Ergebnis:** `Tests run: 2, Failures: 1, Errors: 0, Skipped: 0` (`BUILD FAILURE` durch erwartete Rot-Kontrolle):
  1. **Szenario 1 (Bug-Repro, `test_CommanderEntersAfterMasterChef_MissingCounterBug`):** `Master Chef` (`{2}{G}`) liegt bereits auf dem Schlachtfeld von `playerA`; `playerA` wirkt seinen Commander `Thrasios, Triton Hero` (`{G}{U}`) aus `Zone.COMMAND`.
     - **Befund:** **FAIL** — `commander should enter with +1/+1 counter - permanent Thrasios, Triton Hero must have 1 +1/+1 expected:<1> but was:<0>`.
     - Damit ist der Fehler am **aktuellen Pin `f4d12f6e80`** (zuvor nur am alten Pin `2ec507b721` / Bridge v14 belegt) erneut `BELEGT_REPRODUZIERT`.
  2. **Szenario 2 (Kontrolle, `test_OtherCreatureControl_GetsCounter`):** `Thrasios, Triton Hero` und `Master Chef` liegen auf dem Schlachtfeld von `playerA`; `playerA` wirkt `Grizzly Bears` (`{1}{G}`) aus `Zone.HAND`.
     - **Befund:** **PASS** — `Grizzly Bears` tritt mit `1` `+1/+1`-Marker ein. Die Klausel „Other creatures you control enter the battlefield with an additional +1/+1 counter on them“ funktioniert.
- **Bereinigung:** Temporärer Checkout `$HOME/studio-analyse/mage-repro-1093` unmittelbar nach dem Lauf gelöscht; lokaler Fork-Checkout unverändert (`git status --porcelain` leer, `HEAD = f4d12f6e8066203fba7aa38bd35ea3358117393d`).

---

## 2. Code-belegte Ursache am Pin `f4d12f6e80`

Die im Issue bisher nur gelesene Ursache lässt sich im Quellcode des Pins `f4d12f6e80` direkt belegen:

1. **`MasterChef.java` (`Mage.Sets/src/mage/cards/m/MasterChef.java`, Z. 30–42):**
   - Die erste Klausel (eigene Commander-Kreaturen) ist als `SimpleStaticAbility` mit `GainAbilityAllEffect` modelliert:
     ```java
     Ability ability = new SimpleStaticAbility(new GainAbilityAllEffect(
         new EntersBattlefieldAbility(
             new AddCountersSourceEffect(CounterType.P1P1.createInstance())
                 .setText("with an additional +1/+1 counter on it")
         ), Duration.WhileOnBattlefield, StaticFilters.FILTER_CREATURES_OWNED_COMMANDER)
         ...
     );
     ```
   - Die zweite Klausel („andere Kreaturen“) hängt auf demselben `GainAbilityAllEffect`-Weg über `MasterChefReplacementEffect` (`ReplacementEffectImpl`, `Duration.WhileOnBattlefield`, `EventType.ENTERS_THE_BATTLEFIELD`) — dort funktioniert sie, weil der Commander beim Eintritt der *anderen* Kreatur bereits auf dem Schlachtfeld liegt.
2. **`GainAbilityAllEffect.java` (`Mage/src/main/java/mage/abilities/effects/common/continuous/GainAbilityAllEffect.java`, Z. 94–97):**
   - Im kontinuierlichen Effekt (Layer 6, `apply(Game, Ability)`) iteriert `GainAbilityAllEffect` ausschließlich über `game.getBattlefield().getActivePermanents(filter, source.getControllerId(), source, game)`.
3. **`EntersBattlefieldAbility.java` & `EntersBattlefieldEffect.java`:**
   - `EntersBattlefieldAbility` kapselt einen `EntersBattlefieldEffect` (`ReplacementEffectImpl`, `EventType.ENTERS_THE_BATTLEFIELD`, `applies`: `event.getTargetId().equals(source.getSourceId())`).
   - Nach CR 614.12 wird geprüft, welche Ersatzeffekte auf ein *eintretendes* Objekt wirken, **bevor** es Teil von `game.getBattlefield().getActivePermanents(...)` ist. Da `GainAbilityAllEffect` nur bereits auf dem Schlachtfeld liegende Permanente erfasst, besitzt der eintretende Commander die geliehene `EntersBattlefieldAbility` zum Zeitpunkt der ETB-Ersatzprüfung noch nicht — der `+1/+1`-Marker fehlt.

---

## 3. Upstream-Stand (`magefree/mage#12239`)

- **Status (geprüft am 2026-11-27):** **`OPEN`** (`updated_at: 2025-09-21T01:00:07Z`, `magefree/mage` `master` HEAD `900ee9ace38d58e9cf15cb9ebc7c51fb7c285d01`).
- **Dateihistorie:** `Mage.Sets/src/mage/cards/m/MasterChef.java` wurde seit `90d35e0543` (`2023-06-24T03:43:15Z`, `[CLB] Implement Master Chef (#9527)`) in Upstream nicht mehr geändert. Es liegt kein Upstream-Fix und kein offener Fix-PR vor.

---

## 4. Reichweite im Lab und Entscheidungs-Einordnung

- **Betroffenes Deck:** Precon-Gegner `2021_witherbloom_witchcraft` (Commander `Willowdusk, Essence Seer`), **nicht** Chulane.
- **Bedingung:** Tritt nur auf, wenn `Master Chef` vor dem eigenen Commander auf dem Schlachtfeld liegt (oder der Commander nach ihm wieder eintritt).
- **Owner-Vorbehalt (`AGENTS.md` §8):** Umsetzung im Fork erfordert eine vollständige Fork-Kette (Fork-Push, Repin auf `v16`, PB-03-Läufe, Siegel, 36-Seed-Referenz). Gemäß Owner-Entscheidung vom 2026-11-09 (`#1093`, Kommentar 6737905291) und Einschätzung vom 2026-11-14 wird der Fix **nicht isoliert** gefahren, sondern mit der nächsten ohnehin anstehenden Fork-Kette gebündelt.

---

## 5. Fix-Entwurf (nur Dossier — keine Fork-Änderung)

### 5.1 Ansatz

Statt dem Commander indirekt eine `EntersBattlefieldAbility` zu verleihen (was `GainAbilityAllEffect` erst nach dem Eintritt tut), prüft `Master Chef` beim Eintritt einer Kreatur über einen eigenen `ReplacementEffectImpl` auf `Master Chef` selbst, ob die eintretende Kreatur ein vom Controller von `Master Chef` besessener Commander ist, und wendet den `+1/+1`-Marker direkt auf dem eintretenden Permanent an. (Die zweite Klausel über `GainAbilityAllEffect` für *andere* Kreaturen kann unverändert bleiben, weil der Commander nach seinem Eintritt auf dem Schlachtfeld liegt — alternativ lässt sich auch prüfen, ob `MasterChef` zusätzlich den eigenen Commander im Blick behält, solange dieser auf dem Schlachtfeld liegt.)

**Skizze für `MasterChef.java` (Ersatzeffekt für die Commander-ETB-Klausel):**

```java
class MasterChefCommanderEntersReplacementEffect extends ReplacementEffectImpl {

    MasterChefCommanderEntersReplacementEffect() {
        super(Duration.WhileOnBattlefield, Outcome.BoostCreature);
        staticText = "Commander creatures you own enter the battlefield with an additional +1/+1 counter on them";
    }

    private MasterChefCommanderEntersReplacementEffect(final MasterChefCommanderEntersReplacementEffect effect) {
        super(effect);
    }

    @Override
    public boolean checksEventType(GameEvent event, Game game) {
        return event.getType() == GameEvent.EventType.ENTERS_THE_BATTLEFIELD;
    }

    @Override
    public boolean applies(GameEvent event, Ability source, Game game) {
        Permanent creature = ((EntersTheBattlefieldEvent) event).getTarget();
        return creature != null
                && creature.isCreature(game)
                && creature.isOwnedBy(source.getControllerId())
                && game.isCommanderObject(source.getControllerId(), creature);
    }

    @Override
    public boolean replaceEvent(GameEvent event, Ability source, Game game) {
        Permanent creature = ((EntersTheBattlefieldEvent) event).getTarget();
        if (creature != null) {
            creature.addCounters(
                CounterType.P1P1.createInstance(),
                source.getControllerId(),
                source,
                game,
                event.getAppliedEffects()
            );
        }
        return false;
    }

    @Override
    public MasterChefCommanderEntersReplacementEffect copy() {
        return new MasterChefCommanderEntersReplacementEffect(this);
    }
}
```

**Hinweise für die spätere Implementierung (Review-Punkte bei Kette v16):**
- **Wortlaut / Regeltext-Treue (CR 614.12 vs. Layer 6):** Mit dem direkten Ersatzeffekt auf `Master Chef` entfällt die Abhängigkeit von der geliehenen Fähigkeit auf dem eintretenden Commander. Zu prüfen ist der Randfall „Commander verliert vor/beim Eintritt alle Fähigkeiten“ (z. B. `Humility` / `Dress Down`): In CR 614.12 wirkt ein statischer Fähigkeit-entziehender Effekt (`Humility`) bereits auf den eintretenden Commander, sodass er bei geliehener Fähigkeit *keinen* Marker bekäme, während ein direkter Ersatzeffekt auf dem Enchantment `Master Chef` auch unter `Humility` feuert. Falls diese Feinheit relevant ist, kann in `applies` optional geprüft oder dokumentiert werden; für alle normalen Partien (inkl. `2021_witherbloom_witchcraft`) löst der direkte Ersatzeffekt das Problem sauber.
- **Commander-Prüfung (`isCommanderObject`):** Vor dem Merge in `Mage.Tests` verifizieren, ob `game.isCommanderObject(source.getControllerId(), creature)` beim `EntersTheBattlefieldEvent` für Commander aus `Zone.COMMAND` und anderen Zonen (z. B. Hand/Friedhof) sowie für `Partner`-Commander und geklonte Commander (`Clone` ist kein Commander-Objekt!) exakt `true`/`false` liefert (`StaticFilters.FILTER_CREATURES_OWNED_COMMANDER` als Referenz gegenprüfen).
- **Keine Doppelzählung:** Sicherstellen, dass `MasterChefReplacementEffect` (für „other creatures“) weiterhin `!source.getSourceId().equals(creature.getId())` prüft und der neue Effekt nur auf eigene Commander-Kreaturen greift — sonst erhielte der Commander einen Marker aus seiner eigenen Klausel und keinen falschen zweiten.

### 5.2 Test-Entwurf für die spätere Kette

1. **Rot-Kontrolle (Szenario 1):** `Master Chef` auf Schlachtfeld, Commander (`Thrasios, Triton Hero`) aus `Zone.COMMAND` wirken → auf Pin `f4d12f6e80` **rot** (`expected:<1> but was:<0>`), nach Fix **grün** (`1` `+1/+1`-Marker).
2. **Positiv-Kontrolle (Szenario 2):** Commander + `Master Chef` auf Schlachtfeld, `Grizzly Bears` wirken → `1` `+1/+1`-Marker (auch nach Fix grün).
3. **Negativ-Kontrolle (nicht-eigener Commander):** Gegner-Commander tritt ein, während `playerA` `Master Chef` kontrolliert → `0` `+1/+1`-Marker auf dem Gegner-Commander.
