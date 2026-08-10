# J-P3B Runbook — XMage Feasibility Spike

Status: `FROZEN_BY_J_P3A_NOT_EXECUTED`

XMage wird ausschließlich gegen den in J-P3A eingefrorenen, provider-neutralen Vertrag getestet. Kriterien, Gewichte, Fixtures und Knock-outs dürfen während oder nach dem Spike nicht zugunsten eines Providers verändert werden.

## Frozen identities

```text
contract_hash = 89e0813ec66787328dd4b204f57cb5c404694dec29d249fbbb8785fad0a6d2c6
scoring_hash = 67bc2d99e604f22c3a0d6cc3e00682fe9ac5cb86faccae979418eb2cf40d6227
fixture_hash = cfea9c136b9126c4d367b0c91ebfe4089a47490c7d60dfae5e78dd307eb47dbb
provider_pin = xmage_1.4.60V3 @ d2fa0a244708465e9ff7fcb3c37641e749a292a8
```

Vor jeder Providerarbeit alle vier Identitäten erneut verifizieren. Ein Mismatch ist fail-closed zu behandeln und darf nicht durch stilles Repinning repariert werden.

## Evidenzgrenze

```text
Tactical Oracle -> XMage evidence = forbidden
mock/fake backend -> XMage evidence = forbidden
handshake-only -> full external validation = forbidden
structural simulation -> XMage fixture result = forbidden
```

XMage-Evidenz setzt reale Source/Binaries und eine reale Runtime am eingefrorenen Pin voraus. Bestehende Mock-/Differentialpfade dürfen nur Adaptermechanik prüfen.

## Ausführungsreihenfolge

1. Host-OS, Architektur, Java/JVM, Maven und relevante Environment-Versionen protokollieren.
2. Frozen Source und/oder offizielles Release-Artefakt beziehen und Identität/Hashes sichern.
3. Build mit den Anforderungen des Frozen Tags ausführen; Command, stdout/stderr, Exitcode und Artefakthashes speichern.
4. Realen XMage-Prozess reproduzierbar und zeitlich begrenzt starten.
5. Bounded shutdown und vollständiges Process Reaping nachweisen.
6. Nur minimalen Spike-Controller anbinden; Bridge-Commit und erforderliche Provider-Forktiefe protokollieren.
7. Handshake und Capability-Attestation getrennt erfassen.
8. Benötigte echte Testdecks importieren.
9. Reale Vier-Spieler-Commander-Session inklusive Ishai/Rograkh-Partnerkonfiguration erzeugen/starten.
10. Raw State vor einem Choice Point lesen.
11. Provider-native Legal-Action-Liste oder exakte native Choice-Anforderung mit gültigen Optionen erfassen.
12. Aktion programmatisch über den nativen Control Path einreichen.
13. Providerantwort, resultierenden State sowie Events/Trace sichern.
14. Absichtlich illegale oder stale Action einreichen und Ablehnung ohne State Mutation nachweisen.
15. Alle technisch ausführbaren Frozen Fixtures ausführen; nicht mögliche als `UNSUPPORTED` dokumentieren.
16. Replay oder äquivalenten geordneten Raw Trace sichern und definierte State Checkpoints vergleichen.
17. Evidenzset einfrieren, erst danach anhand des Frozen 100-Punkte-Modells scoren.
18. Knock-outs ausschließlich mit den in P3A festgelegten Evidenzschwellen bewerten.
19. `J_P3_XMAGE_SPIKE_REPORT.md`, Raw Evidence und Partial Matrix erzeugen.
20. Keine Forge-Ergebnisse antizipieren und keinen Provider auswählen.

## Native Integrationshypothese

P3A fand statisch `Mage.Server`, Remote-Interfaces `PlayerActions`/`GamePlay`, typisierte Spielerantworten und `sendPlayerAction`, View/Server-State-Flächen sowie `Replays`. Das sind Einstiegshypothesen, **keine** validierten Bridge-Capabilities. Eine dünne isolierbare Adapterlage ist einem invasiven Eingriff in Rules Semantics vorzuziehen.

## Capability checklist

Alle beginnen mit `NOT_RUN`:

```text
process_start = NOT_RUN
bounded_shutdown = NOT_RUN
handshake = NOT_RUN
capabilities = NOT_RUN
deck_import = NOT_RUN
4_player_commander = NOT_RUN
partner_commanders = NOT_RUN
seed_or_reproducible_initialization = NOT_RUN
state_read = NOT_RUN
legal_actions = NOT_RUN
programmatic_action_submission = NOT_RUN
illegal_action_rejection = NOT_RUN
stack = NOT_RUN
priority = NOT_RUN
commander_tax = NOT_RUN
per_opponent_commander_damage = NOT_RUN
events = NOT_RUN
replay_or_equivalent_raw_trace = NOT_RUN
```

Zulässige spätere Featurewerte: `PASS`, `PARTIAL`, `UNSUPPORTED`, `INFRASTRUCTURE_BLOCKED`, `NOT_RUN`.

## Fixture checklist

```text
P3-FX-001 commander_cast = NOT_RUN
P3-FX-002 commander_tax = NOT_RUN
P3-FX-003 partner_commanders = NOT_RUN
P3-FX-004 per_opponent_commander_damage = NOT_RUN
P3-FX-005 kediss_normal_damage = NOT_RUN
P3-FX-006 jeska_multiplier = NOT_RUN
P3-FX-007 boardwipe = NOT_RUN
P3-FX-008 counter = NOT_RUN
P3-FX-009 protection = NOT_RUN
P3-FX-010 trigger = NOT_RUN
P3-FX-011 replacement = NOT_RUN
P3-FX-012 stack_priority = NOT_RUN
P3-FX-013 illegal_action_rejection = NOT_RUN
P3-FX-014 replay_state_consistency = NOT_RUN
```

## Raw Evidence layout

```text
J_P3_XMAGE_RAW_EVIDENCE/
  provider_identity.json
  environment.json
  acquisition/
  build/
  runtime/
  handshake/
  decks/
  states/
  legal_actions/
  submitted_actions/
  rejections/
  events/
  fixtures/
  replay_or_trace/
  failures/
  manifest.json
```

`manifest.json` muss Dateipfade, SHA-256, Medientyp, Ursprung, Provider-Pin, Spike-Controller/Bridge-Identität und Erstellungszeitpunkt binden. Rohbelege dürfen nicht nachträglich überschrieben werden, ohne die Manifestidentität zu ändern.

## Ergebnisklassifikation

Gesamtstatus ausschließlich:

```text
PASS
PARTIAL
KNOCKED_OUT
INFRASTRUCTURE_BLOCKED
```

Ein externer Download-/DNS-/Runner-/Registry-Fehler ist nur dann `INFRASTRUCTURE_BLOCKED`, wenn er tatsächlich die reale Ausführung blockiert. Alle unabhängig ausführbaren Arbeiten sind trotzdem abzuschließen.

```text
provider_selected = false
NEXT_EXPECTED_PHASE_AFTER_SUCCESSFUL_P3B = J-P3C
```
