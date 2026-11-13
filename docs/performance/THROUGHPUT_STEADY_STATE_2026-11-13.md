# Stationäre Durchsatz-Nachmessung und JVM-Profil (Issue #1279)

- **Datum:** 2026-11-13
- **Hardware:** AMD Ryzen 7 7700 8-Core Processor (16 Threads), 16 GB RAM
- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d` (`config/rules_engines.json` unverändert)
- **Tisch / Pod:** Chulane (`data/decks/deckbau/chulane_current.json`) gegen 3 Precons (Lorehold Spirit, Animated Army, Token Triumph)
- **Rohdaten-Ablage:** `docs/performance/measurements-2026-11-13/`
- **Ausgeführte Läufe:** A0 (Bezug), A2 (unten als „Lauf B") und A3 (unten als „Lauf A") sowie das JFR-Profil (Teil B). Die Läufe A1 (4 Arbeiter) und A4 (12 Arbeiter) aus der Tabelle in Issue #1279 wurden nicht gefahren; für die Entscheidungsregeln ist das folgenlos (die Bestwert-Regel ist bereits durch A2/A3 ausgelöst). AppCDS wurde nicht verwendet; ob ein Archiv vorlag, ist nicht festgestellt (UNKNOWN).

---

## 1. Stationärer Durchsatz (Tabelle)

Formel: $\text{Durchsatz (Partien / Stunde)} = \frac{\text{Gesamtzahl Partien}}{\text{Gesamtwandzeit (s)}} \times 3600$

| Lauf | Arbeiter | Partien je JVM | JVM-Optionen | Partien | Gesamtwandzeit (s) | Durchsatz (Partien/h) | Prozess-CPU (s) | Peak-RSS Summe (MB) | Swap Delta (MB) | Gescheitert |
|---|---|---|---|---|---|---|---|---|---|---|
| **A0 (Bezug)** | 1 | 1 | Standard | 12 | **315.1** | **137.1** | 643.8 | 12489.5 | -9.0 | 0 |
| **Lauf A (A3)** | 8 | 8 | SerialGC | 96 | **658.6** | **524.7** | 3262.6 | 12247.3 | +2935.9 | 0 |
| **Lauf B (A2)** | 6 | 8 | SerialGC | 96 | **638.6** | **541.2** | 2961.8 | 10486.5 | -10.5 | 0 |
| **JFR (warm)** | 1 | 12 | SerialGC | 12 | **257.0** | **168.1** | 276.0 | 1197.4 | -9.0 | 0 |

---

## 2. Kalt vs. Warm Analyse (Kaltstart-Anteil je JVM)

Vergleich der 1. Partie in der JVM (Kaltstart: JVM-Start + Kartendaten-Scan) gegenüber dem Mittelwert der Folgepartien (warme JVM):

| Lauf | Kalt Wandzeit (s) | Warm Wandzeit (Mittel, s) | Wandzeit-Delta (s) | Kalt CPU (s) | Warm CPU (Mittel, s) | CPU-Delta (s) |
|---|---|---|---|---|---|---|
| **Lauf A (8W, 8g/JVM)** | 59.56 | 42.26 | **+17.30 s** | 76.32 | 27.85 | **+48.47 s** |
| **Lauf B (6W, 8g/JVM)** | 44.04 | 36.26 | **+7.78 s** | 64.24 | 26.00 | **+38.24 s** |
| **JFR (1W, 12g/JVM)** | 16.27 | 21.52 | **+-5.25 s** | 40.67 | 21.19 | **+19.48 s** |

---

## 3. Speicheranalyse (Peak-RSS)

| Lauf | Peak-RSS Max je JVM (MB) | Peak-RSS Summe aller JVMs (MB) | Swap vor Lauf (MB) | Swap nach Lauf (MB) | Swap Delta (MB) |
|---|---|---|---|---|---|
| **A0 (1W, 1g/JVM)** | 1246.2 | 12489.5 | 3389.9 | 3380.9 | -9.0 |
| **Lauf A (8W, 8g/JVM)** | 1221.4 | 12247.3 | 2616.8 | 5552.7 | +2935.9 |
| **Lauf B (6W, 8g/JVM)** | 975.0 | 10486.5 | 3380.9 | 3370.4 | -10.5 |
| **JFR (1W, 12g/JVM)** | 1197.4 | 1197.4 | 3398.9 | 3389.9 | -9.0 |

---

## 4. Identitätsnachweis (Seeds 1 bis 12 über alle Läufe)

| Seed | A0 (Bezug) Hash (16) | Lauf A Hash (16) | Lauf B Hash (16) | JFR Hash (16) | Identisch? |
|---|---|---|---|---|---|
| 1 | `1009e97ca3ea9f10` | `1009e97ca3ea9f10` | `1009e97ca3ea9f10` | `1009e97ca3ea9f10` | ✅ Ja |
| 2 | `8380b87b6fb9cbba` | `8380b87b6fb9cbba` | `8380b87b6fb9cbba` | `8380b87b6fb9cbba` | ✅ Ja |
| 3 | `31a85fde5ea0d17b` | `31a85fde5ea0d17b` | `31a85fde5ea0d17b` | `31a85fde5ea0d17b` | ✅ Ja |
| 4 | `40f7c1fd326c70a4` | `40f7c1fd326c70a4` | `40f7c1fd326c70a4` | `40f7c1fd326c70a4` | ✅ Ja |
| 5 | `8167562b6c8e065e` | `8167562b6c8e065e` | `8167562b6c8e065e` | `8167562b6c8e065e` | ✅ Ja |
| 6 | `dce2fcb30fcb40ef` | `dce2fcb30fcb40ef` | `dce2fcb30fcb40ef` | `dce2fcb30fcb40ef` | ✅ Ja |
| 7 | `afe8ce78a496b85c` | `afe8ce78a496b85c` | `afe8ce78a496b85c` | `afe8ce78a496b85c` | ✅ Ja |
| 8 | `0f6f440d1129bef4` | `0f6f440d1129bef4` | `0f6f440d1129bef4` | `0f6f440d1129bef4` | ✅ Ja |
| 9 | `1fde7a854a816613` | `1fde7a854a816613` | `1fde7a854a816613` | `1fde7a854a816613` | ✅ Ja |
| 10 | `f9ccc185cd0c1f8a` | `f9ccc185cd0c1f8a` | `f9ccc185cd0c1f8a` | `f9ccc185cd0c1f8a` | ✅ Ja |
| 11 | `93a5b167b61067f1` | `93a5b167b61067f1` | `93a5b167b61067f1` | `93a5b167b61067f1` | ✅ Ja |
| 12 | `1e60696af00c597e` | `1e60696af00c597e` | `1e60696af00c597e` | `1e60696af00c597e` | ✅ Ja |

---

## 5. Java Flight Recorder (JFR) Profil in warmer JVM (Part B)

- **Aufzeichnungs-Fenster:** 10 warme Partien (Seeds 3 bis 12, nach 2 Aufwärm-Partien verworfen).
- **Profil-Datei:** `docs/performance/measurements-2026-11-13/warm_profile.jfr`
- **Gesamte CPU-Samples:** 7230

### Zeitanteile der Subsysteme (in % der CPU-Zeit)

| Subsystem | Anteil an CPU-Zeit (%) | Details / Hotspots |
|---|---|---|
| **(a) XMage-Kern gesamt** | **65.1 %** | Spielsimulation, Regelberechnung (`mage.*`) |
| ↳ *darin `GameImpl.copy`* | *2.1 %* | Spielstand-Kopien für KI-Vorschau |
| ↳ *darin `getPlayable` / Simulation* | *1.5 %* | Ermittlung legaler Aktionen |
| ↳ *darin `getManaAvailable`* | *2.2 %* | Mana-Berechnung |
| **(b) Bridge-Code des Labs** | **5.2 %** | `bindViews`, Spielstand-Sichten, Prüfsummen |
| **(c) Sonstiges / Runtime / GC** | **29.7 %** | JVM-Laufzeitumgebung |
| **(d) Warten / Idle** | **nicht gemessen (UNKNOWN)** | Wartezeit/Idle wurde nicht erhoben: Die Auswertung aggregiert nur `jdk.ExecutionSample`; ThreadPark/JavaMonitorWait (Wartezeit auf Pilot/Pipes) wurden nicht gemessen. Der Wert ist UNKNOWN, nicht 0. |

### Top-Pakete im Profil

| Paket | Samples |
|---|---|
| `java.util` | 1963 |
| `mage.abilities.effects` | 797 |
| `mage.abilities` | 734 |
| `java.lang` | 689 |
| `com.google.gson.internal` | 485 |
| `mage.util` | 365 |
| `java.util.regex` | 274 |
| `mage.abilities.mana` | 224 |
| `com.google.gson` | 198 |
| `com.google.gson.internal.bind` | 152 |

---

## 6. Entscheidungsregeln-Urteil (nach Issue #1279)

- **Bester gemessener Durchsatz:** **541.2 Partien / Stunde**
  - Urteil: $\ge 500$ Partien/h ERREICHT. Durchsatz genügt für Nacht-Serien (4.000 Partien). Keine Fork-Arbeit nötig.
- **Bridge-Anteil (b):** **5.2 % unter reiner Stack-Attribution — eine exklusive Untergrenze, kein Bridge-Anteil im Sinne von #1279-B.** Die Klassifikation zählt einen Sample nur dann als Bridge, wenn der Stack ein Bridge-Merkmal enthält und kein einziges `mage.*`-Frame; von der Bridge angestoßene Arbeit in Engine-, Gson- oder JDK-Frames (u. a. die JSON-Serialisierung der Sichten und des Zustands-Hashs) fällt damit an „XMage" oder „Sonstiges". Der inklusive Bridge-Anteil (`bindViews`, Zustands-Hash, `deepCopy`) ist aus den vorliegenden Aggregaten nicht bestimmbar. **Inklusive Neuauswertung liegt inzwischen vor (Kommentar auf #1281): 2.680 von 7.230 Samples = 37,1 %.** Wartezeit/Idle wurde auch dort nicht gemessen (UNKNOWN, s. Abschnitt 5).
  - Urteil: Inklusive Neuauswertung liegt vor (37,1 %, Kommentar auf #1281); der #1264-Entscheid fällt nach Muses Verifikation der Neuauswertung.
- **Spielstand-Kopien (`GameImpl.copy`):** **2.1 %**
