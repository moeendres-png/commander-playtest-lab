# XMage-Projekte: Verbesserungen, Erweiterungen, Nutzungen (Recherche 2026-11-19)

Methode: WebSearch plus WebFetch auf öffentliche GitHub-Seiten und Projektseiten. Nicht geklont. Kein HTTP 429, kein robots-Verbot festgestellt. Lizenzangaben stammen aus der Repo-Seite. Wo die Seite keinen Typ nennt, steht "unklar". Keine Zugangsdaten, keine Kontaktdaten gesendet.

Legende: [B] = Seite gelesen, URL genannt. [V] = vermutet bzw. nur aus Suchausschnitt, nicht gelesen.

## Gerankte Liste

1. **GregorStocks/mage-bench** [B]
   URL: https://github.com/GregorStocks/mage-bench
   Zweck: Benchmark, in dem LLMs gegeneinander Magic spielen, 1v1 und Multiplayer-Commander.
   Lizenz: LICENSE.txt vorhanden, Typ nicht angezeigt, also unklar.
   Aktivität: Datum nicht sichtbar. Die Projektseite nennt Spiel-IDs bis 27.03.2026.
   Größe: 71 Sterne, 13 Forks, 5 PRs.
   Nutzbar: Die README sagt "Unmodified from upstream" für den XMage-Server. Die Spiellogik und XMage-Workarounds liegen in einer Java-Bridge (Mage.Client.Bridge). Der Ordner puppeteer/ ist Python und startet Prozesse, verbindet Piloten und Bridge-Clients. Config round-robin-commander: 4 Piloten in einer Commander-Partie mit Coverage-optimiertem Matchmaking. Ideen für Pod-Setup und Headless-Client-Muster.
   Reife: aktiv gepflegt laut Repo-Struktur, Datum unbelegt.
   Kompatibilität: Hoch. Server unverändert, also passt zu unserer Bridge-Architektur. Der Client ist LLM-zentriert (MCP), nicht RL.
   Risiken: Lizenz unklar. Ergebnisse durch LLM-Kosten und Latenz geprägt, nicht für Massensimulation gebaut. Java 21+, Python 3.11+.

2. **jackmaiorino/mage** [B]
   URL: https://github.com/jackmaiorino/mage
   Zweck: XMage-Fork mit Self-Play-RL-Agenten (PPO, Population-Based Training, Transformer-Policy). Der Autor nennt es ein Lernprojekt.
   Lizenz: nicht angegeben (LICENSE.txt, Typ unklar).
   Aktivität: Datum nicht sichtbar. 7 Sterne, 1 Fork. Commit-Historie 50.348.
   Nutzbar: Eigenes Maven-Modul Mage.Server.Plugins/Mage.Player.AIRL für RL. Inferenz via ONNX Runtime in Java, Training in Python. Batched TCP-Protokoll zu einem GPU-Dienst (gpu_service_host.py). Pure-Python- und Py4J-Modus für Einzelprozess-Läufe. Engine-Änderungen zum Maskieren des Aktionsraums sind dokumentiert. Konkrete Liste fehlt auf der Seite. Durchsatz laut Seite: 5,7 Episoden/s auf HPC-Cluster. Gewinnrate ca. 50 % gegen XMage-Heuristik-KI (v2). Decks sind Pauper, nicht Commander.
   Reife: Früh/Experiment. Ausführliche Doku mit Meilensteinen v1 bis v3.
   Kompatibilität: Hoch fürs Architekturmuster (Java-Runner + Python-Training). Die Engine-Änderungen wären gegen unseren Fork zu prüfen. Regelautorität bleibt XMage.
   Risiken: Lizenz unklar, Code-Qualität unbekannt, Commander nicht belegt, Heap-Verbrauch laut anderer Quelle hoch [V].

3. **wingedsheep/argentum-engine** [B] (Fork-Quelle des Eintrags unten)
   URL: https://github.com/wingedsheep/argentum-engine
   Zweck: MTG-Regel-Engine und Online-Plattform in Kotlin, KEIN XMage.
   Lizenz: LICENSE-Datei vorhanden, Typ unklar.
   Aktivität: Datum nicht sichtbar. 87 Sterne, 47 Forks. 17.385 Commits.
   Nutzbar: Gym-Schicht mit reset/step/observe/legalActions, fork(), snapshot/restore, stepBatch() für parallele Rollouts. HTTP-Server (Port 8081) für Python-Trainer, Endpunkte /envs und /envs/{id}/step. gym-trainer mit JVM-PUCT-MCTS (AlphaZeroSearch) und Self-Play. Free-for-All 2 bis 6 Spieler (CR 806). Commander nicht belegt, nur "commander-loop" mit EDHREC-Decks.
   Reife: aktiv (viele Commits), Datum unbelegt.
   Kompatibilität: Methodisch sehr passend (Snapshot/Restore, stateDigest für MCTS). Aber eigene Engine, keine XMage-Regelautorität. Nur als Referenz für Gym-API-Design geeignet.
   Risiken: Lizenz unklar, Regeldifferenzen zu XMage, Kotlin/JVM statt Java.

4. **Card-Forge/forge** [B]
   URL: https://github.com/Card-Forge/forge ; Wiki-Seite zur KI: https://github.com/Card-Forge/forge/wiki/ai
   Zweck: Open-Source-MTG-Regel-Engine in Java, mit Commander-Format.
   Lizenz: GPL-3.0 [B]. Copyleft, bei Übernahme von Code relevant.
   Aktivität: Datum nicht sichtbar. 2,9k Sterne, 1,3k Forks, 76.295 Commits.
   Nutzbar: Simulation-Modus ohne GUI laut Wiki [B]: Parameter -d (Decks), -n (Anzahl), -m (Best-of), -f (Format), -t (Turnier: Bracket, RoundRobin, Swiss), -p (Spieler pro Paarung), -q (nur Ergebnis), -c (Zeitlimit). Ergebnisse am Ende, Logs für Auswertung. Ideal als Vergleichsbasis für Headless-Massensimulation und Deck-Bewertung.
   KI-Ansatz laut Wiki [B]: regelbasiert, nicht trainiert, Heuristiken. Schwach bei Combo.
   MCTS-Stufe laut Forum: ComputerPlayerMCTS und Minimax-Varianten, nicht thread-sicher, skaliert schlecht [V], Quelle slightlymagic.net-Forum (Ausschnitt, nicht gelesen).
   Python-Anbindung: keine native API, nur Subprozess-Aufruf und Log-Parsing [V, Forum-Ausschnitt].
   Reife: sehr aktiv und ausgereift.
   Kompatibilität: Mittel. Als Vergleichs-Simulator nützlich. Nicht als Engine-Ersatz, weil Regelautorität bei XMage bleibt.
   Risiken: GPL-3.0 (Copyleft). Forge-Regeln weichen von XMage ab. Nur als externer Prozess nutzen, kein Code-Import ohne Lizenzprüfung.

5. **CarmaNayeli/xmage-llm-bridge** [B]
   URL: https://github.com/CarmaNayeli/xmage-llm-bridge
   Zweck: LLM-gesteuerter Bot für XMage. Unterklasse von ComputerPlayer, serialisiert Spielzustand als JSON-Request/Response für ein externes Modell, Ziel Commander.
   Lizenz: MIT [B].
   Aktivität: Datum nicht sichtbar. 0 Sterne, 0 Forks, 8 offene PRs, kein Release. Design-Dokument xmage-llm-bridge-design.md vorhanden.
   Nutzbar: Konkretes Muster für Spielzustands-Export und Entscheidungsschnittstelle in XMage (Unterklasse ComputerPlayer). Passt zu unserer Bridge.
   Reife: Frühphase, keine Releases.
   Kompatibilität: Hoch vom Muster her, da unsere Bridge ebenfalls auf ComputerPlayer aufbaut [V, nicht verifiziert].
   Risiken: Keine Sicherheitsangaben (Bindung, Authentifizierung) auf der Seite. Lizenz MIT ist gut, Code ungeprüft.

6. **Necodenomikhon/mage** [B]: Spiegel von jackmaiorino/mage, gleiche Beschreibung. Lizenz unklar, 0 Sterne. Kein eigener Fund, nur Kopie. Nicht separat bewerten.

7. **magefree/mage** (Upstream) [B]
   URL: https://github.com/magefree/mage
   Lizenz: MIT. 2,4k Sterne, 991 Forks. Topics: ai, computer-opponents, java. README mit "Performance tweaks" und KI-Gegnern. "headless" und "performance" nicht in der Beschreibung.
   Relevante Issues [B] bzw. Suchausschnitt [V]:
   - #5340 (2018, offen): "Tackling performance issues and Loadbalancing". Vorschlag, KI auf eigenen Server auszulagern. Netty-Branch existiert, wurde zurückgezogen wegen Performance-Problemen. Aussage "It's no CPU problem", Engpass laut Thread Bandbreite (~120 Mbit). Quelle: https://github.com/magefree/mage/issues/5340 [B].
   - #5079 [V]: KI braucht 10 bis 20 s pro Trigger bei großem Angriff.
   - #9388 [V]: KI-gegen-KI-Turnier hängt, ConcurrentModificationException.
   - Release 1.4.56 [V]: AI-vs-AI in Turnieren parallel. Nicht gelesen.

8. **VIXAL-OS/discord-mtg-bot** [B]: MIT, Python, Discord-Bot mit optionaler XMage-Bridge (Tier 2.5) für Kartendatenbank (87.000+ Karten). Kein Simulator, eher Kartendaten-Quelle. Sicherheit: Schlüssel über .env bzw. Umgebungsvariablen. Zweck nicht passend, Hinweis für Kartendaten.

9. **Adamychen/xmage-nexus** [B]: Browser-/Desktop-Client für XMage (React, Java-Proxy). Lizenz unklar, 24 Sterne. Kein Simulator. Hat headless self-test gegen den Proxy und einen deterministischen SIM-Bot nur im Dev-Modus [B]. Für Headless-Test-Muster interessant, nicht als Simulator.

10. **lucasdavid/jmagic** [B]: MIT, Java, Zweck "environment in which we (and AI agents) can play MTG". 4 Sterne, 67 Commits. Keine Erwähnung von XMage, Gym, MCTS oder Commander. Früh, kaum nutzbar.

11. **arcanite24/playmat** [V]: Web-Client-Fork für XMage, Merge-PR #122 vom 2026-10-30. Nicht gelesen, nur Suchausschnitt. Kein Simulator.

12. **Argentum-Forks (Klone wie rwaldron/argentum-engine)** [B]: Fork ohne Sterne, Lizenz unklar. Keine eigene Entwicklung gefunden.

## Nicht gefunden / verworfen
- Kein offizieller XMage-Python-Gym-Wrapper gefunden.
- Mehrere Fork-Namen (ryegleason, crenshawda, Grumme2, 18ths, bhza, petrich0r, zeffirojoe) aus Suchergebnis, nur Namen, nicht gelesen. Keine Bewertung möglich.
- "MageZero": Aussage "kein Python-Gym bei XMage" und "alle Projekte nutzen einen eigenen Fork" nur aus Mirror-Seite https://www.neura.market/directories/md-directory/architecture-md-magezero-faq-goals-monpkk87 [V]. Repo nicht gefunden, daher nicht verifiziert.
- Rust-Port-Plan aus Session-Log https://traces.com/... ist kein Projekt, nur ein Plan [V].
- mtg-kernel (Manifund-Förderantrag, Rust-Kernel, XMage-Bridge zum Vergleich) [V]. Kein Code gelesen.
- MTG-Causal-RL (Python, Gymnasium, nicht Java) [V]. Nicht XMage.
- Mage-Bench-"about"-Seite nennt Repo-Link, Lizenz nicht angegeben [B] (mage-bench.pages.dev/about).
- Reddit/Discord: keine relevanten Treffer gefunden. Kein Fund zu XMage-Reddit-Threads im Suchergebnis.

## Belegt vs. vermutet (Kurz)
- Belegt [B]: Lizenzen Forge (GPL-3.0), jackmaiorino (unklar), mage-bench (unklar), argentum (unklar), xmage-llm-bridge (MIT), jmagic (MIT), magefree/mage (MIT). Forge-Sim-Parameter. mage-bench-Architektur. argentum Gym-Endpunkte. jackmaiorino Architektur und Durchsatz.
- Vermutet [V]: MageZero-Aussagen, Forge-MCTS-Stufe, Python-Anbindung Forge nur via Subprozess, Issue-Details ab #5079, Release 1.4.56, Heap-Verbrauch XMage.

## Top 5 (Kurzform für Hand-back)
1. mage-bench: Pod-Setup mit unverändertem Server und Java-Bridge als Vorlage.
2. jackmaiorino/mage: PPO-Training mit Java-Runner und Python-Training, Protokollmuster.
3. argentum-engine: Gym-API-Design (snapshot/restore, stepBatch) als Referenz, nicht als Engine.
4. Forge: GPL-3.0-Vergleichssimulator via CLI-Sim-Modus, nur als externer Prozess.
5. xmage-llm-bridge: MIT-Muster für ComputerPlayer-Unterklasse mit JSON-Schnittstelle.
