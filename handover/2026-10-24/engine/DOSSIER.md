# Engine-Effizienz: Dossier der Mess-Lane (2026-10-24)

Quellen: externes RESEARCH.md (dieser Ordner), JFR-Profil des Dirigenten an
unserer Bridge (Pin v13, 1.933 Samples, wiedergegeben in seiner
GEGENPRUEFUNG Teil 2 — dort die Primärquelle), eigene Messungen der
Mess-Lane (Pin v11, LOCAL_OBSERVED). Jede Zahl trägt ihre Herkunft.

## 1. Wo die Zeit hingeht

Eigene Zerlegung (ein Pod, 3.588 Entscheidungen, Pin v11): Engine
(Java-Bridge) ~96 % der Wandzeit, Pilot ~1 %, JSON/Protokoll ~0,2 %,
Start ~3 % (batch-amortisiert ~0).

JFR-Profil des Dirigenten (Pin v13, Anteile an den Samples des
Spiel-Threads): `Player.getPlayable` ~47 %; irgendeine `.copy(`-Methode
~50 %; `GameState.*` ~52 %; `XmageFullGameDecisionController.bindViews`
(State-View bauen) ~17 %, davon `publicPermanent` ~6 % (`getRule()` mit
`toLowerCase` je Fähigkeit); Gson/JsonObject-Aufbau ~22 % (überlappt mit
den Views); GC ~6 %; **JVM-Start ~21 s pro Spiel-JVM**.

**Damit ist die Kernfrage des Forschungsberichts beantwortet: Ja, die
Bridge kopiert pro Entscheidung.** `getPlayable` läuft bei jedem
Prioritätsfenster (auch Pass-/Mana-only) und kopiert alle Karten des
Spiels (~400 `CardImpl`), nicht nur die relevanten Zonen.

## 2. Eigene Gegenproben (Pin v11, derselbe Pod, alle hash-identisch `c0c2737…`)

Kindprozess-CPU je Pod (3.588 Entscheidungen): G1 (Standard) 99,5 s;
Parallel GC 92,5 s (−7 %); Serial GC (`--fast`) 90,6 s (−9 % — bestätigt
die im Repo dokumentierten −10 %). Wandzeit streut stärker (104/80/87 s,
Einzel-Pods): GC-Wahl ist ein einstelliger Prozenthebel, nicht der Batzen
(Dirigent: E6 nachrangig — dem wird nicht widersprochen).

Protokoll: Die Tape-Frames sind klein (Anfrage Median 445 B, Antwort
268 B; ein ganzes Spiel 2,7 MB beide Richtungen). Nicht die Leitung ist
teuer, sondern der View-Aufbau in der Bridge (17 %, s. o.). Ein
Codec-Wechsel (Forschungshebel) lohnt nicht — unabhängig bestätigt
(Dirigent: E7 nicht lohnend).

## 3. Korrektur zum eigenen README-Zwischenstand

AppCDS: Der Dirigent weist zu Recht darauf hin, dass T-3 das Archiv
gemessen hat (−1,4 % Wand bei einem Spiel pro JVM, unter der
3-%-Schwelle; für `--fast`-Sweeps aktiv, sofern `<jar>.jsa` liegt). Die
README-Formulierung „AppCDS lief nie" gilt nur für Läufe ohne `.jsa` —
u. a. alle Läufe der Mess-Lane. Der eigentliche Startkosten-Block ist
die JVM-/Repository-Initialisierung (~21 s pro Spiel-JVM nach dem
Dirigenten-Profil), gedrückt wird er durch `games-per-jvm`-Batching (E8,
Betrieb), nicht durch CDS allein.

## 4. Hebel (Übernahme der Dirigenten-Bewertung E1–E9, GEGENPRUEFUNG Teil 2)

1. **E1 Weniger `getPlayable`-Kopien** — größter Hebel (v7-Vorläufer:
   −16,8 % CPU bei identischen Transkripten). Ansatz: nur Karten kopieren,
   die der Spieler spielen könnte (Hand/Friedhof/Exil/Befehlszone/
   Spielfeld-Fähigkeiten), nicht fremde Bibliotheken. Risiko mittel —
   Beweis nur per Hash-Twin. **Die Mess-Lane liefert die Twin-Basis:
   #999 M7, 50 Spiele auf aktuellem main (Pin v13).**
2. **E3 `getRule()`/View-Aufbau cachen** — Risiko gering bei sauberem
   Cache-Schlüssel (Fähigkeits-ID); isoliert prüfbar, getrennt committbar.
3. **E2 Fenster ohne mögliche Aktion überspringen** — erst nach E1, nur
   mit konservativem Prädikat + Hash-Twin über ≥100 Spiele (Risiko hoch).
4. **E4 Views nur bei Bedarf** — blockiert durch Owner-Entscheidung O5
   (Transkriptformat/Hash). Empfehlung des Dirigenten: vorerst nein.
5. Nicht verfolgen: E5 (klein), E6 (nachrangig), E7 (s. o.), E9 (kein
   Profil-Beleg, hohes Risiko). E8 ist Betrieb: mehr Worker, solange RAM
   reicht (Box 7 GB, eine JVM ~1,2 GB → realistisch 4–5 Worker mit
   Batching; Worker-Skalierung als Messung noch offen).

Erwartung des Dirigenten (seine Messungen, keine Zusage): E1+E3 zusammen
15–30 % Wandzeit, abhängig von der Brettgröße.

## 5. Qualitäts-Gate (unverändert)

Jede Engine-Änderung nur mit Hash-Twin: feste Seeds/Decks,
Entscheidungsfolge + semantischer Hash bit-identisch vorher/nachher.
Die M7-Basis aus #999 macht „bit-identisch" zu einem prüfbaren
Ausgangszustand statt zu einer Behauptung.
