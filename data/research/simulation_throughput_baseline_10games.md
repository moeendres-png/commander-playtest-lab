### Schritt 1: Messbericht — Zeitanteile einer Partie (Ist-Zustand Baseline)

- **Engine-Stand (Commit):** `f4d12f6e8066203fba7aa38bd35ea3358117393d`
- **Gemessene Partien:** 10 Partien desselben Settings (Chulane vs. Precon-Pod)
- **Median Gesamtlaufzeit:** 26.82 s
- **Durchsatz (Ist-Wert):** **134.3 Partien / Stunde** (Einzelausführung, 1 Worker)

#### Zeitanteile je Phase (Median, Streuung & Prozentanteil)

| Phase | Median [s] | Min [s] | Max [s] | Streuung (StdAbw) [s] | Anteil [%] |
|---|---|---|---|---|---|
| **1. JVM-Start & Handshake** | 0.172 | 0.167 | 0.188 | 0.006 | **0.6 %** |
| **2. Laden Kartendaten (CardScanner/H2)** | 2.675 | 2.618 | 2.777 | 0.048 | **10.0 %** |
| **3. Deck-Import & Game-Init** | 0.383 | 0.340 | 0.427 | 0.031 | **1.4 %** |
| **4a. XMage Regelberechnung (Engine)** | 19.268 | 10.016 | 47.984 | 10.883 | **71.9 %** |
| **4b. Pilot-Entscheidungen (Python KI)** | 2.820 | 1.222 | 7.763 | 2.308 | **10.5 %** |
| **4c. Transport (JSON / IPC Pipe)** | 0.711 | 0.426 | 1.333 | 0.262 | **2.6 %** |
| **5. Protokollschreiben (Event-Log / Disk)** | 0.205 | 0.101 | 0.522 | 0.122 | **0.8 %** |
| **GESAMT (Wall Time)** | **26.815** | 15.236 | 61.603 | 13.510 | **100.0 %** |

#### Auswertung der Annahme aus #1251 („Rahmen, nicht Regelberechnung“)

- **Regelberechnung (XMage Engine):** 71.9 % der Laufzeit.
- **Rahmen (Start, Laden, Import, Pilot, Transport, Protokoll):** 26.0 % der Laufzeit.
