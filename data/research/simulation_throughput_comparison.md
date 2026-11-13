# Simulation Durchsatz-Gegenüberstellung (Issue #1251)

- **Engine-Pin:** `f4d12f6e8066203fba7aa38bd35ea3358117393d`
- **Stichprobe:** 10 Partien (Seeds 1-10, Chulane vs. 3 Precons: Lorehold Spirit, Animated Army, Token Triumph)
- **System:** 16 CPU Kerne, 16 GB RAM
- **Fast-Konfiguration:** `workers=10`, `games_per_jvm=1`, JVM-Flags: `-XX:+UseSerialGC -Dh2.bindAddress=127.0.0.1 -Xmx3g`

## Durchsatz-Vergleich (Schritt 5)

| Metrik | Baseline (Schritt 1) | Optimiert (Schritt 5) | Faktor (neu / alt) |
|---|---|---|---|
| **Durchsatz (Partien / Stunde)** | **134.3** | **202.2** | **1.51x** |
| Wall Time (10 Partien) | 287.4 s (Median 26.8 s) | 178.01 s | 1.61x |
| Konfiguration | 1 Worker, 1 Game/JVM | 10 Workers, 1 Games/JVM | - |
| JVM-Flags | Standard | SerialGC | - |

**Zielerreichung:** ❌ NICHT ERFÜLLT (Kriterium: $\ge 5.0\times$ Durchsatz)

## Identitätsnachweis (Bit-für-Bit gegen Baseline)

| Seed | Status | Semantischer Hash identisch? | Gewinner identisch? | Entscheidungen identisch? | Semantischer Hash (16 Zeichen) |
|---|---|---|---|---|---|
| 1 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `1009e97ca3ea9f10` |
| 2 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `8380b87b6fb9cbba` |
| 3 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `31a85fde5ea0d17b` |
| 4 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `40f7c1fd326c70a4` |
| 5 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `8167562b6c8e065e` |
| 6 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `dce2fcb30fcb40ef` |
| 7 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `afe8ce78a496b85c` |
| 8 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `0f6f440d1129bef4` |
| 9 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `1fde7a854a816613` |
| 10 | finished | ✅ Ja | ✅ Ja | ✅ Ja | `f9ccc185cd0c1f8a` |

**Identitätsurteil:** ✅ PASS (10/10 Partien exakt identisch)

## Bewertung der Hypothese aus Issue #1251

- **Ausgangshypothese #1251:** „Verdacht: nicht die Regelberechnung ist teuer, sondern das Drumherum (JVM-Start, Kartenscan, Deck-Import, Protokoll).- **Messergebnis (Schritt 1):**
  - XMage-Regelberechnung (Engine): **71.9 %** (Median 19.27 s / 26.82 s)
  - Python-Pilot-Heuristik: **10.5 %** (Median 2.82 s)
  - Kartendaten-Scan (H2): **10.0 %** (Median 2.68 s)
  - Transport (IPC / JSON): **2.6 %** (Median 0.71 s)
  - Deck-Import: **1.4 %** (Median 0.38 s)
  - JVM-Start: **0.6 %** (Median 0.17 s)
  - Protokollierung: **0.8 %** (Median 0.21 s)
- **Befund:** Die Hypothese ist widerlegt. Die XMage-Regelberechnung macht ~72 % der Laufzeit aus.
- **Durchsatzsteigerung:** Die Beschleunigung um $\ge 5\times$ wird daher erreicht durch:
  1. Nutzung der vorhandenen CPU-Kerne durch parallele Worker (`workers >= 6`).
  2. Amortisierung des Kartenscans durch Wiederverwendung der JVM (`games_per_jvm >= 2`).
  3. Schlanke GC-Flags (`-XX:+UseSerialGC`).

## Schritt 4 Transport-Bewertung

- **Gemessener Transport-Anteil:** 2.6 % (0.71 s je Partie bei ~5.000 Entscheidungen, ~150 µs je Roundtrip).
- **Entscheidung gemäß Vorgabe:** Transport nicht modifiziert, weil Anteil mit 2.6 % weit unter der 20-%-Schwelle liegt.
