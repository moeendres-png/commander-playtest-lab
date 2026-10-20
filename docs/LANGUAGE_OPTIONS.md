# Programmiersprachen-Optionen für commander-playtest-lab

## Aktuelle Architektur

| Komponente | Sprache | Warum |
|------------|---------|-------|
| XMage Engine (Fork) | Java | XMage ist Java; Fork muss Java bleiben |
| Engine Bridge | Java | Läuft in der JVM, kommuniziert via JSON |
| Pilot (Entscheidungslogik) | Python | rund 4800 Zeilen Entscheidungslogik (Stand 2026-10-20) |
| Analyse/Orchestrierung | Python | Data-Science-Ökosystem (pandas, numpy) |
| Kommunikation | JSON über stdin/stdout | Sprachagnostisches Protokoll |

## Theoretisch mögliche Sprachen

### Für den Pilot (ersetzt Python-Pilot)

Der Pilot kommuniziert via JSON über stdin/stdout mit der Bridge. **Jede Sprache,
die JSON lesen/schreiben und über stdin/stdout kommunizieren kann, ist theoretisch
möglich:**

| Sprache | Machbarkeit | Aufwand | Empfehlung |
|---------|-------------|---------|------------|
| **Python** (aktuell) | ✅ Läuft | – | ✅ Behalten |
| **Rust** | ✅ Möglich | Hoch (rund 4800 Zeilen neu) | ⚠️ Nur bei Bedarf |
| **Go** | ✅ Möglich | Hoch (rund 4800 Zeilen neu) | ⚠️ Nur bei Bedarf |
| **JavaScript/Node.js** | ✅ Möglich | Hoch | ❌ Kein Vorteil |
| **C++** | ✅ Möglich | Sehr hoch | ❌ Kein Vorteil |
| **Java** | ✅ Möglich | Hoch | ⚠️ Möglich, aber... |

**Warum Python behalten:**
- Pilot ist nur 2,6% der Wall-Time → Sprachwechsel bringt keinen Speedup
- 3400 Zeilen getestete Logik neu zu schreiben = hohes Fehlerrisiko
- Python-Ökosystem für Analyse (pandas, matplotlib) ist unübertroffen
- Die Bottlenecks sind in Java (Engine), nicht im Pilot

**Wann ein Wechsel Sinn machen würde:**
- Wenn der Pilot CPU-limitiert wäre (ist er nicht: 2,6%)
- Wenn Memory ein Problem wäre (ist es nicht)
- Wenn Latenz kritisch wäre (ist sie nicht, Batch-Verarbeitung)

### Für die Engine (ersetzt Java-Fork)

| Option | Machbarkeit |
|--------|-------------|
| **Java** (aktuell) | ✅ Muss bleiben |
| Andere Sprache | ❌ Unmöglich |

**Begründung:** Der Fork ist eine Modifikation von XMage (Java). Ein Rewrite in
einer anderen Sprache würde bedeuten, die komplette MTG-Regelengine neu zu
implementieren – Jahre Arbeit, extrem fehleranfällig. Die 2104 Karten-Facts und
die qualifizierte Regelkorrektheit wären verloren.

### Für Analyse/Orchestrierung (ersetzt Python-Scripts)

| Sprache | Machbarkeit | Anmerkung |
|---------|-------------|-----------|
| **Python** (aktuell) | ✅ | pandas, numpy, scipy, matplotlib |
| **R** | ✅ Möglich | Gut für Statistik, schlechter für Orchestrierung |
| **Julia** | ✅ Möglich | Schnell, aber kleines Ökosystem |
| **Rust/Go** | ⚠️ Möglich | Kein Data-Science-Ökosystem |

**Empfehlung:** Python behalten. Das Ökosystem ist der Grund, nicht die Sprache.

## Fazit

**Theoretisch möglich:** Fast jede Sprache für den Pilot (via JSON-Bridge).

**Praktisch sinnvoll:** Keine. Die Architektur ist richtig:
- Java für die Engine (muss so sein)
- Python für Pilot + Analyse (Ökosystem-Vorteil, kein Performance-Problem)

Ein Sprachwechsel würde Monate kosten, hohes Risiko bergen und keinen messbaren
Nutzen bringen. Die Bottlenecks sind algorithmisch (GameState-Copies), nicht
sprachbedingt.
