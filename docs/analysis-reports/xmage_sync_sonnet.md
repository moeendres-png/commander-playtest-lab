# Upstream-Abgleich XMage: Fork moeendres-png/mage gegen magefree/mage

Stand der Messung: 2026-11-19. Rein lesende Git-/Dateianalyse; kein Push, kein Repin, keine Änderung am Fork,
keine Builds, keine Test-Suiten. Alle Zahlen sind gemessen (Befehl angegeben); Vermutungen sind als
"Vermutung" markiert, Nichtmessbares als UNKNOWN. Kein Build ausgeführt: ob der gemergte Stand kompiliert oder
Tests besteht, ist UNKNOWN.

## 0. Quellen und Bezugspunkte (wichtig für das Lesen der Zahlen)

- Pin (CPL `config/rules_engines.json`, `primary_engine.commit`): `f4d12f6e8066203fba7aa38bd35ea3358117393d`,
  2026-11-05, Kopf der Fork-Branches `claude/trial-ue4-20261031` und `claude/xmage-mp-candidate-20260929`
  (`git ls-remote https://github.com/moeendres-png/mage`). Sealed/qualifiziert: Epoche `5bd29ab6f318-c6942825587a`
  (PB-03 Lauf 42513112953, AF00-AF11 PASS; `architecture_freeze.current_qualification`).
- WICHTIG: Der Fork-`master` (`16dc17ea`, 2026-10-20, lokal `/home/user/mage`, 177 Commits, flach) ist NICHT die Pin-Linie.
  Er ist von der Kandidatenlinie seit 2026-08-16 (gemeinsame Basis `ff09f5425`, zugleich seine Merge-Base mit Upstream) abgezweigt:
  184 eigene Commits (C12-Containment/Witness-Härtung, opencode-zai-Workflows), die Kandidatenlinie hat 870 eigene (`git rev-list --count origin/master..origin/cand`
  und umgekehrt). Seine Merge-Base mit Upstream ist 2026-08-16, also ~13 Wochen alt. Er ist weder Pin noch Merge-Ziel. Der Pin-Commit `f4d12f6e8`
  ist im lokalen Klon `/home/user/mage` nicht vorhanden (`git cat-file -t f4d12f6e8` schlägt dort fehl); ich habe ihn
  stattdessen aus GitHub (anonym, öffentlich lesbar) in den Scratch-Klon geholt. Alle Fork-Zahlen unten beziehen sich auf
  die Kandidatenlinie = Pin, nicht auf `master`.
- Upstream: `magefree/mage` master `5769a6cbf0dedfe33fae414af98c4950bdcf283f` (2026-11-18), Version laut POM `1.4.63`.
- Methode: Klon `/home/user/magefree/mage` (flach, dann `git fetch --depth=3000 origin master`, 3320 Commits, zurück bis
  2026-01-15); Scratch `.../scratchpad/xmage_sync/fork` (Fork-Kandidatenlinie, `--depth=3000 --filter=blob:none`,
  5307 Commits) mit Remote `upstream` auf den Klon. Merge-Test mit `git merge-tree --write-tree` (gleiche ort-Strategie
  wie `git merge`, schreibt nur Objekte, kein Arbeitsbaum), danach `git merge --abort` nicht nötig. Scratch (`.../scratchpad/xmage_sync`) wurde am Ende gelöscht; `git merge --abort` war nicht nötig, weil kein Arbeitsbaum-Merge lief.

## 1. Stand

| Größe | Wert | Beleg |
|---|---|---|
| Merge-Base Fork-Pin gegen Upstream | `fab0f23b78ddd755102cebfe20d618be87af59d0`, 2026-10-20 03:58 +0200, "[MBC] Fix Grizzlegom, Hurloon Hero Rulebreaker removing the maximum deck size (#16519)" (Upstream 1.4.62; im Pin-Hinweis als "magefree/mage master fab0f23b, 18 conflicted files resolved" beschrieben) | `git merge-base origin/cand upstream/master` |
| Alter der Merge-Base | 30 Tage (4 Wochen); Trigger T6 der Lab-Roadmap (> 6 Wochen) NICHT erreicht | `scripts/upstream_delta.py` Zeile 57 |
| Upstream-Commits seit Merge-Base | 540 (539 ohne Merges); 347 im Oktober, 192 im November | `git rev-list --count MB..upstream/master` |
| davon bereits im Pin (patch-gleich, per cherry-pick) | 13 (22fca32e3 Payment cancel, 4dc8f311d, 12be750f9, 859591d00, e18157de1, e3511aa34, 4cd6618bc, 84e418873, 8db89716e, 9e29c64c7, b80a73ab1, 52a91b208, 78ded2409) | `git cherry origin/cand upstream/master MB` |
| Upstream-Commits, die dem Pin FEHLEN | 526 (ohne Merges) | `git cherry` (Zeilen mit `+`) |
| davon topologisch nach dem letzten Pick (78ded2409, 2026-10-28) | 356 Commits, 1044 Dateien, +54240/-4162 | `git rev-list --no-merges --count 78ded2409..upstream/master`, `git diff --shortstat` |
| Upstream-Commits mit Datum >= Pin-Datum (2026-11-05) | 159 | `git log --no-merges --since=2026-11-05` |
| Upstream-Delta gesamt (Baum gegen Baum, MB gegen Upstream-HEAD) | 1328 Dateien, +70060/-5283 | `git diff --shortstat MB upstream/master` |
| Fork-eigene Commits seit Merge-Base | 225 (206 ohne Merges) | `git rev-list --count MB..origin/cand` |
| Fork-eigene Dateien | 762 Dateien, +43342/-870 | `git diff --shortstat MB origin/cand` |
| Dateien, die beide Seiten geändert haben | 191 (davon 62 im Kern `Mage/src/main/java`, 77 Kartenklassen) | `comm -12` der Namenslisten |

Fork-eigene Commits nach Kategorie (206 ohne Merges; HEURISTIK nach Commit-Titel, daher Näherung):

| Kategorie | Commits |
|---|---:|
| Mehrspieler-Regelfixes (F-18..F-23, F-28/F-29, F-43..F-45, SBA-Priorität, Leaver, APNAP, Monarch, Commander-Zonen-Reihenfolge) | 76 |
| Bridge-Haken / native Nähte (Commander-History-Restore WS39/WS42, Rules-RNG WS54/WS212, Concede WS211, RG-02/06A/07/08 Restore/Validierung, WS81/83/85 CR 614.12, WS206 Kampfschaden) | 48 |
| Kartenimplementierungen/Ports/Tests (Precons, Marvel MSC, Wakanda, Doctor Who, Prepare/SOS) | 44 |
| Determinismus (Rules-RNG, Insertion-Order-Sammlungen, feste Spielerreihenfolge) | 17 |
| Upstream-Cherry-Picks | 13 |
| Anpassung eigener Fork-Karten an die Picks | 3 |
| Performance (lazy Playable-Calculation-Copy `16e57239e`, lazy Triggers `456b0e227`, Card-Scanner `99b18b8f7`) | 3 |
| Build (Guava 33.7.2-jre, jsoup 1.23.2: `f8db5f939`) | 1 |
| Sonstiges (Duplikat-SetCardInfo-Bereinigung) | 1 |

Fork-eigene Dateien nach Gruppe (Baumvergleich MB gegen Kandidatenlinie, `scratchpad/xmage_sync/cat.py`):
Kartenklassen 300 (+9649/-402), Mage.Tests 176 (+14966/-39), Kern `Mage/src/main/java/mage` 158 (+2588/-366),
Fork-Doku/Research 83 (+4122), `commander-lab/` Handoff-Ordner 24 (+10938), Set-Dateien 9, Mage/src sonstiges 5,
`.github` 2 (u. a. `maven.yml`: Checkout auf exakten Head-SHA; `ws39-retained-base.yml`), AI 1 (4 Zeilen), Verify 1, pom 1.
Größte Kern-Änderungen des Forks: `CombatGroup.java` +305/-17, `GameImpl.java` +278/-21, `PhaseOutHeldBySourceEffect.java` +190,
`GainAbilityControlledSpellsEffect.java` +175/-25, `Game.java` +138/-7, `BecomesFaceDownCreatureEffect.java` +134,
`ContinuousEffects.java` +120/-9, `CommanderPlaysCountState.java` +97 (neu), `GameRandom.java` +89 (neu), `Library.java` +74.

## 2. Upstream-Änderungen seit der Merge-Base nach Modul

Netto (Baum gegen Baum) und Commits je Modul (ein Commit kann mehrere Module berühren; Zeilen der Commit-Spalte sind
die Summe über Commits, also höher als netto). Befehl: `git diff --numstat MB upstream/master | python3 cat.py`,
`git log --no-merges --numstat MB..upstream/master | python3 classify.py`.

| Modul | Dateien | +Zeilen | -Zeilen | Commits (berührend) |
|---|---:|---:|---:|---:|
| Mage.Sets Karten (`Mage.Sets/src/mage/cards`) | 742 (321 neu, 419 geändert, 1 gelöscht, 1 umbenannt) | 23299 | 2934 | 413 |
| Mage.Sets Set-Dateien (`.../sets`) | 31 | 1106 | 81 | 343 |
| Mage.Tests | 230 (192 neu, 38 geändert) | 26766 | 229 | 195 |
| Kern `Mage/src/main/java/mage` | 188 | 3220 | 978 | 113 |
| Mage/src/main/resources (Rating-CSVs für Draft-KI) | 37 | 9419 | 42 | 4 |
| Mage.Client (+Plugins, Reports) | 38 | 3405 | 568 | 20 |
| Mage.Server (+Server.Plugins ohne AI, Common, Player.Human) | 42 (großteils pom) | 834 | 116 | 17 |
| Mage.Player.AI* (nur ComputerPlayer/ComputerPlayer6, Draft-Bots) | 6 | 79 | 256 | 9 |
| Mage.Verify | 2 | 66 | 10 | 12 |
| Utils (Perl/Daten) | 6 | 1853 | 59 | in 25 Build-Commits |
| pom.xml (Version) / .devcontainer / .github | 38 pom, 1, 1 | je 1 Zeile | je 1 Zeile | 25 (Build, gesamt) |

Commits nach Autor (Hinweis auf Aktivität): Muz 225, Oleg Agafonov 138, Muz Ali 73, Darío Barrabino 64, matoro 6.

### (a) Regel-/Engine-Korrekturen im Kern (113 Commits berühren `Mage/src/main/java/mage`, davon ~35 echte Regel-/Engine-Fixes, der Rest Kartenhilfsklassen, SubTypes, Draft/Deckbau)

Auswahl der wichtigsten (Hash, Datum, Titel). "[PICKED]" = schon im Pin. Spalte "CP" = Cherry-Pick EINZELN auf den Pin
(`git merge-tree --merge-base=<c>^ origin/cand <c>`): `ok` = textlich sauber, `Kx` = x Konfliktdateien. Textlich sauber heißt NICHT
semantisch/kompilierbar sauber und sagt nichts über Abhängigkeiten zwischen Commits.

| Hash | Datum | Titel | CP |
|---|---|---|---|
| 10300e9e5 | 2026-11-10 | game: fixed that cards and effects still counted or affected opponents who left the game until the end of the turn (10 Kerndateien; Game.getOpponents-Standard wird auf "nur im Spiel" gedreht) | K3 |
| 9b054c07a | 2026-11-13 | refactor: game checks use isInGame instead of hasLeft (#16780) | ok |
| 5304a55ed | 2026-11-12 | game: fixed that some cards can choose players who left the game (Black Vise ...) | ok |
| e4fc332dc | 2026-11-13 | Balance - fixed that players who left the game count as having nothing (#16731) | ok |
| e6d056a0d | 2026-11-10 | Convoke multitapping and other alternative mana payment improvements (#16508): 24 Dateien, `ConvokeAbility` 482 Zeilen geändert, ManaPool, ManaUtil, `Player.playMana`-Vertrag | ok |
| 34c0ae6d3 | 2026-11-10 | OneShotNonTargetEffect improvements (#16637) (AbilityImpl, 7 Kerndateien) | ok |
| 22741d9ec | 2026-11-10 | Copy effects - improved combo support with copy of copies (GameImpl) | ok |
| f43b37fd3 | 2026-11-09 | Copy a spell or ability for each it could target - fixed that it can be copied with non-legal targets | ok |
| ca09637f6 | 2026-11-15 | Copy abilities - fixed that some cards can wrongly target spells on stack | ok |
| 338eb7d2c | 2026-11-14 | Becomes a copy - fixed that the returned permanent became a copy after a blink in response | ok |
| 6fdee6b75 | 2026-11-15 | Sanctum Lurker and support planeswalkers that keep 0 loyalty (#16785) (GameImpl, Permanent) | ok |
| 643a7fc70 | 2026-11-15 | Mana abilities improves with fixed event (ACTIVATED_ABILITY) (#16793) (breit, 6+ Kerndateien) | K1 |
| 5be3c49b3 / 081d8586c | 2026-11-15 | stack object filters / Loot exhaust mana ability used the stack (Abhängigkeiten von 643a7fc70) | K2 / K2 |
| 4dfbc176c | 2026-11-03 | Entering attacking - fixed that some effects wrongly prevent it (Combat) | ok |
| 761255b43 | 2026-10-31 | Tapped and attacking - fixed that entering tokens was able to choose battle permanents (Combat) | K2 |
| 09897e7a0 | 2026-10-31 | Attacking that player - fixed that it wrongly ask defender to attack (7 Kerndateien) | K3 |
| 7984dbb80 | 2026-10-31 | Sneak ability - fully implemented attacking and tapped parts | ok |
| ffb1095ca | 2026-11-04 | Aura, morph and dfc improves (#16715) (9 Kerndateien) | ok |
| 4142596fb | 2026-11-04 | refactor: improved aura attachment usages with shared code | K23 |
| be0d20487 / 31c3adcc8 | 2026-11-07 | Prepared cards - removed copy hacks / gui hacks (überschneidet sich mit den eigenen Prepare-Fixes des Forks) | K1 / K4 |
| 5f60910db | 2026-11-07 | Scry - fixed that it can wrongly raise triggers on scry 0 | ok |
| 5d16aab70 | 2026-11-13 | Enters with counters effects - fixed that double-faced cards enter without counters | ok |
| 5f04616c6 | 2026-10-21 | Melded permanents can't be turned face down (712.16) (#16562) | ok |
| 669acc9f0 | 2026-11-03 | [SOI] Fix Sage of Ancient Lore's back face dying as a 0/0 on transform (#16587) | ok |
| 8d69687be | 2026-11-06 | refactor: simplified DetainAllEffect ... fixed data leaks between game states | ok |
| 46b0c1922 | 2026-11-13 | Put to battlefield effects - better compatibility with double faced cards (Aetherplasm, Push // Pull ...) | ok |

Einzel-Cherry-Pick-Test über 107 nicht gepickte Kern-berührende Commits (113 Kern-Commits + 2 Karten-Zusatz, abzüglich 8 bereits gepickter): 51 textlich sauber, 56 mit Konflikten
(`scratchpad/xmage_sync/cp_test.sh`; Ergebnisse `cp_results.txt`). Konflikte entstehen vor allem dort, wo der Fork dasselbe Feature
parallel gebaut hat (Marvel-/Precon-Karten, CONNIVED, mustAttackDefenders, Surveil/Seek-Ereignisse).

### (b) Kartenimplementierungen und unsere Decks

Methode: Kartennamen aus den Decklisten des CPL-Repos (`data/decks/deckbau/chulane_current.json`, `data/decks/rogshai_current.json`,
`data/decks/opponents/kaervek/current/deck.json`, `data/opponents/hosts_of_mordor_precon.json`, `data/decks/precons/*.json`,
`data/collections/owner_collection_2026-10-12.txt`) gegen die in Upstream geänderten/neuen Kartenklassen
(`git diff --name-status -M MB HEAD -- Mage.Sets/src/mage/cards`, Namen aus den `SetCardInfo`-Registrierungen, 94580 Zeilen).
Schlüssel: "geändert" = Kartenklasse seit MB im Upstream editiert (auch Refactor/Text); "neu" = Klasse neu angelegt.

| Kartenmenge | verschiedene Karten (Nenner) | upstream geändert | upstream neu |
|---|---:|---:|---:|
| Chulane (Owner-Deck, `chulane_current.json`) | 83 | 2 (Fabled Passage, Tezzeret, Betrayer of Flesh) | 0 |
| RogShai (historisch; Sitz im Referenz-Pod R1) | 87 | 1 (Fabled Passage) | 0 |
| Kaervek (Referenz-Pod) | 77 | 0 | 0 |
| Hosts of Mordor (Referenz-Pod) | 84 | 0 | 0 |
| Lorehold Spirit 2026 (Referenz-Pod R1; Kartenmenge von `data/opponents/lorehold_spirit_precon.json` und `data/decks/precons/2026_lorehold_spirit.json` gleich, je 85) | 85 | 4 (Conspiracy Theorist, Fabled Passage, Guardian Scalelord, Lorehold Archivist) | 0 |
| Open Hostility 2016 | 88 | 1 (Spinerock Knoll) | 0 |
| Animated Army 2024 | 84 | 0 | 0 |
| Token Triumph 2022 | 73 | 0 | 0 |
| alle 173 Precons (Vereinigung) | 5824 | 109 (1,9 %) | 35 |
| Owner-Sammlung | 1403 | 7 (0,5 %) | 0 |

Was die Änderungen an UNSEREN Karten sind (Commit je Karte, `git log MB..HEAD -- <Datei>`):
Fabled Passage `46b0c1922` (DFC-Kompatibilität der Put-to-battlefield-Effekte; Kernklassen, wirkt breiter als die eine Karte);
Tezzeret, Betrayer of Flesh `643a7fc70` (Mana-Ability-Ereignis-Refactor, K1 beim Einzel-Pick);
Conspiracy Theorist `8d69687be` (Datenleck zwischen Spielzuständen in DetainAll, also ein Zustands-/Determinismus-Thema);
Guardian Scalelord `71f14b090` (Filter-Refactor, vermutlich ohne Verhaltensänderung: Vermutung);
Lorehold Archivist `11a71fb12` (nur Regeltext);
Spinerock Knoll `10300e9e5` (Leaver-Semantik).
Mittelbar (Kernklassen, die viele Karten nutzen): Convoke/Improvise/Delve/Assist-Karten sind von `e6d056a0d` betroffen:
Chulane 1 (Bennie Bracks, Zoologist), RogShai 1 (Dig through Time), Token Triumph 6 (Conclave Tribunal, Devouring Light, Hour of Reckoning,
March of the Multitudes, Nissa's Expedition, Scatter the Seeds), alle Precons 56. Wie viele unserer Karten indirekt über geänderte
Kernklassen anders spielen: UNKNOWN (nicht ohne Läufe messbar).
Wichtig: Keine Karte aus Chulane, den vier genannten Precons oder dem Referenz-Pod ist upstream neu hinzugekommen (0 neu); Upstream
liefert für unsere Decks also keine neu spielbaren Karten. Die 35 neuen Precon-Karten gehören zu den 173 Precons (Marvel MSC u. a.).

Doppelimplementierung: 36 Kartenklassen (37 Dateien mit Tests dazu) hat der Fork für Precons selbst gebaut UND upstream hat dieselbe Klasse
unter demselben Namen gebaut (Archnemesis, Avenge, Dack Fayden Helping Hand, Eye of Duskmantle, Feather, Galactus, Glorious Purpose,
Immortal Obligation, Jace Multiverse Architect, Jhoira, Kang Dynasty, Tamiyo Upriser Crowned, Teferi's Reproach, The Ur-Sphinx, Venser u. a.).
Keine davon steht in Chulane, den vier Precons oder dem Referenz-Pod (nur in der 173er-Precon-Bibliothek). Das ist der Hauptgrund
der Add/Add-Konflikte in Abschnitt 3.

Sonstige Kartenänderungen: 313 Commits "Implement" (Neukarten, u. a. TRK/TRC Star Trek, MDD, MSC, HOB), 71 reine Kartenfix-Commits
(z. B. d9b802438/a8d0e329c Thieves' Auction, c9a47f72c Planeswalker's Mischief, bc8b8322b Wyll's Reversal, 7819c3408, 9cbac5bd9, 7f47d1eac,
9c15725d2 Muldrotha, 0a6687023 Aminatou's Augury, 3989092ed Breathkeeper Seraph, e6685cb20 mehrere Permanent-Bedingungen).

### (c) Performance

Ergebnis: in den 540 Commits gibt es KEINEN Performance-Commit im Sinne der Suche (Titel-Stichwörter perf/speed/optimi/memory/cache/leak:
8 Treffer, alle Fehlalarme: Karten "Warp Speed", "Optimization Annex", Testlogs "tests: improved debug logs" `e2dada0bc`,
"tests: faster startup with fast db scan" `d77a85c94` (nur Testharness), `8d69687be` (Datenleck, kein Tempo)). Änderungen an den heißen Pfaden
sind klein: `PlayerImpl.java` 11 Commits, `PermanentImpl.java` 6, `Combat.java` 6, `GameImpl.java` 5, `AbilityImpl.java` 4, `GameState.java` 2,
`ContinuousEffects`/`TriggeredAbilities` 0. Die Performance-Vorsprünge des Forks (lazy Playable-Calculation-Kopie `16e57239e`, lazy Trigger-Kopie
`456b0e227`) gibt es nur im Fork; Upstream bringt dafür nichts, und ein Merge könnte sie nur durch Konflikt-/Semantikprobleme gefährden
(`GameImpl.java` ist auf beiden Seiten geändert, auto-merge ohne Konflikt; Wirkung auf die lazy Kopie UNKNOWN ohne Lauf).

### (d) KI/Simulation

`ComputerPlayer.java` (Draft-Bots und Deckbau: 3ee94c604, 5dd555817, 3023d91cb, c1d444ef8, 74b72005e, 9c11e51bc) und `ComputerPlayer6.java`
(9b054c07a, isInGame), plus `e6d056a0d` (KI zahlt Convoke/Delve mit mehreren Kreaturen). Test-Harness: `TestPlayer.java` (3ddf73e69, e6d056a0d),
`CardTestPlayerAPIImpl.java` (d77a85c94, e6d056a0d). Für uns ohne Gewicht, weil die Produktion externe Piloten nutzt und keine
`isComputer()`-Pfade (`XmageFullGamePlayer extends PlayerImpl`, `engine-bridge/.../XmageFullGamePlayer.java:83`). Das Bridge-Gate ist von
den Draft-Bot-Änderungen nicht berührt. Die Test-Harness-Änderungen betreffen nur Mage.Tests im Fork-CI.

### (e) Server / Client / UI (für uns irrelevant)

Mage.Client 35 Dateien (Bilder-Download scryfall `8f98f1f7a`, Karten-Popup `4327eaaa8`, Dialog-Render `31ede542b`), Mage.Server 11 Dateien
(Encoding-Hinweise `825273133`, Draft-Vorschläge `fad302f6a`, Draft-Kartenratings `ce761b6f8`/`f2b317fe0`). Die Bridge importiert keine Klasse
aus Mage.Client/Mage.Server/Mage.Common (siehe Abschnitt 3, 175 Referenzen, alle aus `Mage`, `Mage.Sets`, `Mage.Server.Plugins` Spieltypen).

### (f) Build / JDK / Abhängigkeiten (Risiko für die Build-Kette)

Gemessen: alle 38 `pom.xml` ändern sich nur um die Version `1.4.62` -> `1.4.63` (Wurzel-POM 2/2 Zeilen: `<version>` und `<mage-version>`), keine
Plugin-, JDK-, Compiler- oder Dependency-Änderung (`git diff MB upstream/master -- pom.xml '*/pom.xml'`). `.github/labeler.yml` 1 Zeile,
`.devcontainer` Perl-Module. Versions-Bump-Commits: `193afe3d9` (2026-10-31), `d386d6c2b` (2026-10-31), `c5a5215fa` (2026-11-17).
Der Fork hat selbst Guava 33.4.8 -> 33.7.2-jre und jsoup 1.21.2 -> 1.23.2 gehoben (Pin-Commit `f8db5f939`); Upstream hat das nicht, die Zeilen
konfligieren nicht (kein Konflikt in `pom.xml`). Risiko: Bridge-Build-Kette greift an der Versionsnummer, nicht an Plugins:
`engine-bridge/pom.xml:17` (`xmage.version` 1.4.62), `XmageProvider.java:22` (`ENGINE_VERSION`), `JsonlBridgeTest.java:73`,
`scripts/run_replay_twin_campaign.py:38,59` (`mage-1.4.62.jar`). Entweder die Version beim Merge auf 1.4.62 halten (die drei Bump-Commits
auslassen/zurücknehmen) oder diese vier Stellen mitziehen. JDK: Bridge `maven.compiler.release 17` (`engine-bridge/pom.xml:16`), Upstream-Poms
unverändert; kein JDK-Risiko gemessen.

## 3. Trockener Merge-Test

Befehl: `git merge-tree --write-tree --name-only origin/cand upstream/master` (Pin-Linie gegen Upstream-HEAD `5769a6cbf`).
Ergebnis: Exit 1 (Konflikte), Ergebnisbaum `21328549c23f1899f74a3ebceffb99601074f96a` (nur im Scratch, nichts geschrieben außer Objekten).

| Konflikttyp | Dateien |
|---|---:|
| Add/Add Kartenklassen | 35 |
| Add/Add Mage.Tests | 35 |
| Inhalt Kartenklassen (Flickerform, Henzie Toolbox Torre, Tawnos's Coffin) | 3 |
| Inhalt Set-Dateien (MurdersAtKarlovManorCommander, RealityFractureCommander) | 2 |
| Inhalt Kern (`Mage/src/main/java/mage`) | 12 |
| GESAMT | 87 (17 Inhalt + 70 Add/Add) |

Alle 87 Dateien liegen in Fork-eigenen Änderungen (ein Konflikt entsteht nur, wo beide Seiten ändern; die 191 Dateien mit Änderungen
auf beiden Seiten sind die Obermenge). Die 12 Kernkonflikte (je 1 Hunk, klein: 5 bis 71 Konfliktzeilen):
`MageIdentifier` (beide Seiten hängen eine Konstante an; zusätzlich steht `EyeOfDuskmantleAlternateCast` im gemergten Baum schon außerhalb des Hunks, Zeile 66, und nochmals auf der Upstream-Seite des Hunks, Zeile 105: eine vierte Dublette, die bei naiver Auflösung als doppelte Enum-Konstante bliebe), `OnOpponentsTurnCondition`, `OpponentsTurnCondition` (Fork: `getOpponentsInGame`, Upstream:
`getOpponents(id,false)`), `RequirementEffect` (`mustAttackDefenders`: Fork gibt `null` für "beliebig", Upstream `emptySet()`), `ConniveSourceEffect`,
`ConvokeAbility` (71 Zeilen), `SneakAbility`, `Game` (Javadoc von `getOpponents`), `Combat` (Fork: Mehr-Verteidiger-Pflicht mit `defendersForcedToAttack`;
Upstream: `requiredDefenders`-Schleife), `GameEvent` (Fork `SURVEILED_INTO_GRAVEYARD`, Upstream `SOUGHT`), `TokenImpl`, `PlayerImpl` (`seekCards`).

NICHT als Konflikt gemeldete, aber im gemergten Baum belegte Brüche (diese sind der eigentliche Risikokern):

1. `GameEvent.EventType` deklariert `CONNIVED` zweimal (Zeile 80 Upstream, Zeile 102 Fork): echter Kompilierfehler (doppelte Enum-Konstante),
   ohne Konfliktmarke automatisch gemergt (`git cat-file -p 21328549:Mage/src/main/java/mage/game/events/GameEvent.java | grep -n CONNIVED`).
2. `Game.getOpponents(UUID)` ist im gemergten Baum `return getOpponents(playerId, true)` (Zeile 203-204) und damit identisch mit dem Fork-API
   `getOpponentsInGame` (Zeile 211-212). Der Fork hatte das Standardverhalten bewusst als Snapshot (inklusive Spieler, die in diesem Zug ausschieden) belassen
   und `getOpponentsInGame` als explizites Gegenstück eingeführt (F-23, Commits `f099e9785`, `df6b8f3ea`, `8ba669876` ...). Upstream dreht den Standard
   (`10300e9e5`, `9b054c07a`). Nur die Javadoc stand im Konflikt, die Semantikänderung wurde still übernommen. Das betrifft genau die Leaver-/Mehrspieler-
   Qualifikationstests des Forks. Eine Regelentscheidung (welche Semantik gilt) ist nötig, bevor irgendetwas zusammengeführt wird.
3. 35 doppelt registrierte `SetCardInfo`-Einträge (gleicher Name und gleiche Nummer zweimal) in drei Set-Dateien: `MarvelSuperHeroesCommander` 25
   (ohne Konfliktmarke!), `MurdersAtKarlovManorCommander` 4, `RealityFractureCommander` 6. Dasselbe Problem hatte der Fork schon beim Merge von
   `fab0f23b` (Commit `043579bb7` "Drop SetCardInfo registrations that the upstream merge duplicated"). Folge: Mage.Verify-/Kartenbank-Fehler.
4. Determinismus: neue Upstream-Zeilen mit `RandomUtil.` (2 im Kern, 0 in Karten), `Collectors.toSet()` (2 Kern, 6 Karten), `new HashSet/HashMap`
   (6 Kern, 20 Karten). Konkret `PlayerImpl.seekCards` (liegt in einem Konflikt-Hunk; RISIKO, falls die Upstream-Seite genommen wird) ruft `RandomUtil.randomFromCollection(cards)` auf der Nicht-Regel-Zufallsquelle und
   sammelt mit `Collectors.toSet()`; der Fork nutzt dort `game.getRulesRandom()` und `LinkedHashSet` (WS54). Ein Merge würde dort die
   Wiederholbarkeit gleicher Seeds (Zwillingsreplay) wieder öffnen, bis ein Determinismus-Audit nachzieht.
5. Fork-eigene Karten gegen geänderte Upstream-Kernverträge: `Combat`/`RequirementEffect` (null gegen leere Menge), Surveil/Seek-Ereignisse, Prepare-Lebenszyklus
   (Upstream hat Prepare am 2026-11-07 neu geschrieben, `be0d20487`, `31c3adcc8`).

### Würde `engine-bridge` noch kompilieren? (statisch, ohne Build)

Methode: alle `mage.`-Referenzen aus `engine-bridge/src` (main und test, Importe und voll qualifizierte Namen) = 175 Klassen; 172 auflösbar im Upstream-HEAD,
1 nur im Fork (`mage.watchers.common.CommanderPlaysCountState`), 2 sind Stack-Namenstexte (`...AnyColorPermanentTypesManaEffect`,
`...Vault112SadisticSimulationChapterEffect`, Strings in `XmageFullGamePlayer.java:87` bzw. Tests; beide Klassen existieren upstream unverändert).
Davon unverändert seit MB: 143 Klassen; geändert: 29 (Ability, AbilityImpl, Modes, SpecialAction, ManaCostsImpl, RequirementEffect,
BecomesFaceDownCreatureEffect, ConditionalAnyColorManaAbility, CardImpl, ExpansionSet, CounterType, StaticFilters, Game, GameImpl, Combat, Commander,
Dungeon, Draft, GameEvent, Permanent, PermanentImpl, Spell, StackObject, Player, PlayerImpl, Target, CardUtil, ThreadUtils, CommanderInfoWatcher).
Entfernte oder geänderte öffentliche Signaturen in diesen 29 (Diff der Deklarationszeilen): einzige echte Entfernung `CardUtil.setSourceCostsTag`
(von der Bridge nicht aufgerufen; der Pin hat die Kartenanpassung dazu schon, `dbafa37ab`); `Ability` verliert nur eine `@Deprecated`-Annotation.
Neu hinzugekommene abstrakte/Interface-Mitglieder: `Player.seekCards`, `Game.restoreStateKeepingStack`, `Target.hasChangedZones`: `PlayerImpl`, `GameImpl`
und `TargetImpl` implementieren sie, die Bridge hat nur zwei `PlayerImpl`-Unterklassen (`XmageFullGamePlayer`, `XmageBridgePlayer`) und drei
`Watcher`-Unterklassen, keine eigene `Game`-/`Target`-Implementierung, daher kein Zwang zur Mehrimplementierung.
Fork-eigene APIs, die die Bridge nutzt (17 Methoden aus 48 vom Fork neu angelegten öffentlichen): u. a. `GameImpl.canConcede`, `getRulesSeed`,
`setRulesSeed`, `isRulesSeedExplicit`, `setRequireExplicitSeed`, `getRulesRandomCalls`, `CommanderInfoWatcher.restoreDamageStateForGameLoad`,
`BecomesFaceDownCreatureEffect.restoreFaceDownStateForGameLoad`, `Library.restoreOrderForGameLoad`, `CommanderPlaysCountWatcher.restoreStateForGameLoad`,
`CommanderPlaysCountState`. Alle sind im gemergten Baum noch vorhanden (geprüft per `git cat-file -p 21328549:<Datei> | grep`).
Ergebnis (BELEGT): kein Wegfall einer von der Bridge referenzierten öffentlichen Klasse oder Methode durch Upstream. (UNKNOWN: Parametertypen jeder
einzelnen Aufrufstelle, Verhalten, und ob der gemergte Baum insgesamt kompiliert; Punkt 1 oben (doppeltes `CONNIVED`) zeigt, dass er es ohne Handarbeit nicht tut.)
Verhaltensrisiko für die Bridge (nicht Kompilierung): (i) `playMana`-Vertrag/Spezialzahlung (`e6d056a0d`: "Special mana payments no longer add mana to the
pool"; die Bridge hat Mana-Rahmen und Aktivierungsschlüssel um `playMana`, `XmageFullGamePlayer.java:2301-2327`) -> Entscheidungsrahmen für
Convoke/Delve/Improvise/Assist-Karten würden sich ändern; (ii) die Bridge spiegelt `PlayerImpl.getManaAvailable` für die Playable-Berechnung
(`REPIN_RUNBOOK.md` §3, `XmageFullGamePlayer.manaAvailableInPlayableCalcCopy`): der Methodenkörper ist zwischen MB und Upstream-HEAD unverändert
(md5 gleich), also keine neue Abgleichspflicht aus Upstream, aber nach einem Merge gegen die Fork-Version zu prüfen; (iii) Stack-Frame-basierte Erkennung
(`StackWalker`, `CardUtil#castSpellWithAttributes`): CardUtil upstream nur um `setSourceCostsTag` verkürzt.

## 4. Empfehlung in Stufen

Vorbemerkung zur Qualifikation (gilt für JEDE Option, die den Pin bewegt, auch für einen einzelnen Cherry-Pick): `AGENTS.md` §1/§10 und
`docs/claude/REPIN_RUNBOOK.md`: jeder Repin ändert `primary_engine.commit`, das Jar ist nicht byte-reproduzierbar, daher wird jeder Rebuild durch PB-03
neu qualifiziert. Das Studio-Bridge-Gate (`AGENTS.md` §10, `docs/STUDIO_PLAN_SIMULATOR.md`) gilt nur auf GLEICHEM Pin (BEFORE und AFTER "same pin"); ein Pin-Wechsel
fällt nicht darunter. Der Aufwand der Requalifikation ist weitgehend fest (unabhängig davon, ob 1 oder 526 Commits kommen); nur Risiko und
Konfliktarbeit wachsen mit der Menge. Neu qualifiziert werden müsste bei jedem Repin:
- Fork: `maven.yml` per `workflow_dispatch` am Kandidatenzweig (Mage.Tests zuletzt 7189 Läufe, 0 Fehler; Mage.Verify damals bekannte 15 Karten- und 3 Set-Fehler, Stand Lock v7, danach nicht neu gelesen);
- Lab-Repin-PR: `config/rules_engines.json` (Pin, abgeleitete Fähigkeiten), vier Workflows, `XmageProvider.java`, `JsonlBridgeTest.java`,
  `XmageCandidateEngineFingerprintTest.java`, `real_rows.py`, Pin-Authority-Tests, neuer `SUCCESSOR_SOURCE_LOCK.json` (v16) samt Guard-Test;
- Workflow "XMage Full Game Conformance" (zuletzt 1110 Läufe) gegen das exakt gebaute Fork-Jar;
- PB-03 Nr. 1 -> Seal 1 -> AF11-Neuadjudikation für den neuen Pin (AF11 bleibt bis dahin UNKNOWN, nicht PASS) -> PB-03 Nr. 2 -> Seal 2 -> erst dann
  `architecture_freeze.current_qualification` auf die neue Epoche; die Owner-signierte Freeze-Identität (`evidence_epoch f881d56fb33f-aef9f7f660b4`) bleibt;
- Identitäts-Gates (Runbook §2): 46 Precon-Pods und 36 Real-Pod-Seeds müssten hash-gleich zum alten Pin sein, "es sei denn, die Änderung soll einen Hash bewegen".
  Bei Option 1 (und jedem Cherry-Pick mit Verhaltensänderung: Leaver, Convoke, Kampf, Kopien) ist ein Hash-Wechsel zu erwarten; dann gibt es einen NEUEN Referenzsatz
  (`docs/performance/REFERENCE_36_SEEDS_*`) und NEUE Basislinien; Studio-Serienergebnisse und Referenzläufe unter dem alten Pin sind mit denen unter dem neuen Pin
  nicht vergleichbar und dürfen nicht gemischt werden (Kohorten nie addieren, `AGENTS.md` §1). Die Simulationsgewichtung bleibt ohnehin 0 bis G-SIM.
- `BRIDGE_AHEAD_OF_QUALIFICATION` (`docs/STUDIO_SCOPE.md`, "Engine und Bridge"): solange `engine-bridge/` vom versiegelten Stand abweicht, ist das sichtbar; eine
  Requalifikation auf dem aktuellen `main` würde die Bridge mitversiegeln. Das ist ein Nebennutzen, aber auch eine Bedingung: der Seal muss dann auf einem
  Lab-Stand erfolgen, der die gewünschte Studio-Bridge enthält.
- Rückfallweg bei allen Optionen: Pin in `config/rules_engines.json` auf `f4d12f6e8066203fba7aa38bd35ea3358117393d` zurücksetzen (Lab-PR), alte Epoche
  `5bd29ab6f318-c6942825587a` bleibt unberührt als Qualifikation (versiegelte Epochen werden nie umgeschrieben); die Kandidatenlinie im Fork wird nur
  fast-forward verschoben, der alte Pin-Commit bleibt als Commit erhalten (kein Force-Push, `AGENTS.md` §10).

### Option 1: vollständiger Merge von `upstream/master`

- Aufwand (Vermutung, nicht gemessen): größer als der letzte Merge (`fab0f23b`: "18 conflicted files resolved"). Jetzt 87 Konfliktdateien
  (davon 70 Add/Add Doppelimplementierungen), dazu die nicht markierten Brüche aus Abschnitt 3 (doppeltes `CONNIVED`, gedrehter `getOpponents`-Standard,
  35 doppelte `SetCardInfo`, `null` gegen leere Menge in `mustAttackDefenders`), ein Determinismus-Audit der neuen Upstream-Zeilen, Neulauf Mage.Tests/Verify
  und der Fork-Regressionsserien (F-18..F-45, RG-*, WS*), danach die komplette Kette oben. Realistisch mehrere Arbeitstage Agentenzeit plus CI-Wartezeit;
  der v12-Repin brauchte 1 h 40 vom PR-Merge bis zum zweiten Seal (nur Warten), das ist die Untergrenze der Kette, nicht der Merge-Arbeit.
- Risiko: HOCH. Es ändert still Leaver-Semantik im Mehrspielerspiel (unsere Rules-Authority-Kernlinie), Zahlungsfluss (Convoke), Kampf-Pflichten, Prepare,
  Kopier-/Aura-Logik; 526 Commits unqualifiziert in einem Schritt; Hash-Wechsel auf allen Referenzpods zu erwarten.
- Nutzen für UNSERE Decks: gering gemessen: 0 neue Karten, 2 von 83 Chulane-Karten upstream geändert (Fabled Passage, Tezzeret), 0 Performance-Gewinn.
- Qualifikation: volle Kette (siehe Vorbemerkung) mit neuem Referenzsatz und neuem Siegel; Vergleich zum alten Pin bricht.
- Reihenfolge: (1) Owner-Entscheid und Regelentscheidung zur Leaver-Semantik; (2) Merge in einem Fork-Branch (kein Push ohne Owner-Go); (3) Konflikte lösen, Upstream-Version
  der 36 Doppelkarten übernehmen und Fork-Tests anpassen, Fork-Hooks (F-23, RNG, Restore) erhalten; (4) Fork-CI, Mage.Tests und Verify; (5) Lab-Repin-PR und Kette.
- Rückfallweg: Pin zurücksetzen (siehe oben); der Fork-Branch kann unverschoben bleiben.

### Option 2: selektiver Cherry-Pick (ein gebündelter Repin "v16")

- Kandidaten (Hash siehe Abschnitt 2a), textlich sauber auf den Pin (`ok`): `46b0c1922` (Put-to-battlefield/DFC: berührt Fabled Passage in Chulane, RogShai,
  Lorehold), `8d69687be` (Datenleck zwischen Spielzuständen, Conspiracy Theorist), `5f04616c6`, `669acc9f0`, `5d16aab70`, `5f60910db`, `22741d9ec`, `f43b37fd3`,
  `ca09637f6`, `338eb7d2c`, `4dfbc176c`, `7984dbb80`, `ffb1095ca`, `6fdee6b75`, `34c0ae6d3`; Convoke `e6d056a0d` nur bewusst (Verhaltensänderung der Zahlung, Bridge-Rahmen).
  Leaver-Gruppe (`9b054c07a`, `5304a55ed`, `e4fc332dc`, `10300e9e5`) NUR nach Regelentscheid gegen F-23, nicht blind.
  Nicht empfohlen: `643a7fc70`/`5be3c49b3`/`081d8586c` (Mana-Ability-Ereignis-Refactor, K1-K2), `4142596fb` (K23), `be0d20487`/`31c3adcc8` (Prepare-Neuschrieb, kollidiert mit eigenen Fixes),
  alle Doppelimplementierungen der Precon-Karten.
- Grenzen (UNKNOWN): ob die Picks untereinander abhängen und in welcher Reihenfolge; "textlich sauber" ist kein Kompilier- oder Verhaltensbeleg (Einzeltest je Commit gegen den Pin,
  nicht als Folge). Jeder Pick braucht seine Mage.Tests-Läufe im Fork.
- Aufwand: klein bis mittel (Vermutung: 1 bis 2 Arbeitstage plus feste Kette). Risiko: mittel, kontrollierbar, weil jeder Pick einzeln reviewt und getestet wird.
- Qualifikation: dieselbe feste Kette wie Option 1 (ein Repin), aber Hash-Wechsel nur dort, wo ein Pick Verhalten ändert; mehrere Repins hintereinander vermeiden (Bündel).
- Reihenfolge: Regelentscheid Leaver; Picks einzeln gegen den Pin testen; Bündel bauen; Fork-CI; Lab-Repin (v16).
- Rückfallweg: wie oben.

### Option 3: nichts tun, nur beobachten

- Aufwand: null; vorhandenes Werkzeug `scripts/upstream_delta.py` (U-1, `docs/performance/UPSTREAM_DELTA_2026-10-23.md`) kann den Abstand regelmäßig messen. Trigger der Lab-Roadmap
  (manuell nach dem Skript ausgewertet): T1 REVIEW (siehe Abschnitt 2b: 6 verschiedene Karten unserer Decks upstream geändert, 11 inklusive Owner-Sammlung; 1 breite Kernänderung `46b0c1922`), T2 MET (Upstream-POM 1.4.63 > 1.4.62),
  T3 UNKNOWN (`scripts/upstream_delta.py` gegen den blob:none-Klon lief nach 100 s nicht durch und wurde abgebrochen), T4 OWNER, T5 MET (12 Kernkonfliktdateien), T6 NOT_MET (4 Wochen < 6).
- Risiko: der Abstand wächst weiter (ca. 125 Commits pro Woche seit MB (539 Commits in 30 Tagen)), Konflikte mit den parallelen Fork-Features nehmen zu, je länger man wartet. Fehlende Upstream-Regelkorrekturen
  bleiben im Pin (z. B. DFC-Put-to-battlefield, Kopie von Kopien, Datenleck DetainAll), wirken aber nur auf die in Abschnitt 2b genannten Karten und Mechaniken.
- Qualifikation: keine Änderung, Siegel und Epoche `5bd29ab6f318-c6942825587a` bleiben gültig, Studio-Bridge-Gate unverändert.
- Rückfallweg: nicht nötig.

### Meine Einschätzung (Vermutung, nicht Beschluss)

Option 1 nicht jetzt: 3 stille Brüche plus ein gedrehter Leaver-Standard sind ein Regelfall, nicht ein Konfliktfall, und der Nutzen für Chulane und die vier Precons ist
nach den Zahlen klein (0 neue Karten, 2 geänderte Chulane-Karten). Option 3 ist heute die billigste ehrliche Haltung; Option 2 lohnt sich als EIN Bündel, sobald ein konkreter
Fund in unseren Decks (z. B. Fabled-Passage-/DFC-Thema, Convoke-Rahmen) ihn begründet, oder wenn der Owner ohnehin einen Repin plant (feste Kette). Vorarbeit ohne Pin-Bewegung und ohne
Owner-Go möglich: Regelentscheid zur Leaver-Semantik (Lead/Coordinator, `AGENTS.md` §8), Pick-Abhängigkeiten im Scratch klären, `upstream_delta.py` mit dem neuen Upstream laufen lassen.

### Nur der Owner entscheidet (`AGENTS.md` §8 Owner-only, §10)

Jeder Push in `moeendres-png/mage` (auch ein Merge-/Pick-Branch), die Fast-Forward-Bewegung der Kandidatenlinie `claude/xmage-mp-candidate-20260929`, der Repin selbst
(`config/rules_engines.json`), das Siegeln/Entsiegeln von `qualification/`-Records (ein neuer Nachfolger-Lock ist neu, kein Umschreiben, braucht aber das Go laut Runbook `owner_go`),
`WS17_SHA256SUMS` nur im Rahmen von `production-qualification.yml`. Die Wahl der Option, ob ein Hash-Wechsel der Referenzläufe akzeptiert wird, und ob 1.4.63 als Engine-Version
übernommen oder bei 1.4.62 geblieben wird, sind Owner-Entscheide (Vermutung: Versionsentscheid kann der Lead treffen, Pin-Fan-out ist aber Teil des Repins). Die Regelfrage
(Leaver-Semantik: Snapshot oder im Spiel) ist Rules-Adjudikation und liegt nach `AGENTS.md` §8 beim Lead/Coordinator, nicht beim Worker.

## 5. Ablauf / Reproduktion (Befehle)

```
git ls-remote https://github.com/moeendres-png/mage | grep -E 'f4d12f6e|refs/heads/master'
git -C /home/user/magefree/mage fetch --depth=3000 origin master
git -C <scratch>/fork fetch --depth=3000 --filter=blob:none origin claude/xmage-mp-candidate-20260929:refs/remotes/origin/cand
git -C <scratch>/fork merge-base origin/cand upstream/master              # fab0f23b7...
git -C <scratch>/fork cherry origin/cand upstream/master <MB>              # 13 gepickt / 526 fehlen
git -C <scratch>/fork merge-tree --write-tree --name-only origin/cand upstream/master   # 87 Konflikte
```
Hilfsskripte lagen in `.../scratchpad/xmage_sync/` (cat.py, classify.py, api_check.py, cp_test.sh) und wurden zusammen mit dem Scratch-Klon gelöscht;
`/home/user/magefree/mage` (Upstream-Klon, Tiefe 3000) bleibt bestehen.
Grenzen: Commit-Zählung folgt der flachen Historie (Tiefe 3000, beide Klone decken MB ab); Kategorien der Fork-Commits per Titel-Heuristik; Kartennamen-Abgleich
über `SetCardInfo` (Doppelseitige Karten nach Vorderseite; Namen mit Akzent könnten verpassen); Modul-Zeilen "Commits"-Spalte sind Summen über Commits.
