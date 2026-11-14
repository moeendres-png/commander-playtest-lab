# Issue #1299 Vorprüfung: Bedingung 3 (Pilot-Zustand) + Bedingung 2 (Frame-Digest-Modus, Python-Teil)

- **Datum:** 2026-11-13
- **Art:** Vorprüfung zu #1299 (E4). **Keine Bridge-Änderung**, kein Push, kein PR.
  Teil A ist ein Code-Audit (**CODE_DERIVED**, keine Laufzeit-Messung);
  Teil B ist eine Python-Implementierung mit Tests (lokal, uncommittet).

## Messstand (Lesson 19)

- **Lab-Stand:** `dc7ccaa11` (Merge PR #1281, 2026-11-13), frischer Worktree
  `wt-1299` auf exakt diesem Commit, lokaler Branch `muse/1299-forced-pass-precheck`.
- **Engine-Pin:** `f4d12f6e80` (v15) — für diese Vorprüfung nicht benutzt
  (keine Partie gespielt; Teil A liest Python-Code, Teil B ist reine Digest-Logik).

## Teil A — Bedingung 3: Leitet ein Pilot Zustand aus erzwungenen Fragen ab?

### Ist-Zustand: Python kürzt erzwungene Fragen heute NICHT ab

Jede von der Bridge gestellte Frage läuft in `XmageFullGameRunner._drive`
(`src/commander_lab/engine/rules/full_game.py`) denselben vollen Weg:
Zählung (`decision_count += 1`, Z. 1577, inkl. `max_decisions`-Deckel),
Hidden-Information-Audit (`audit_actor_scoped_frame`, Z. 1604, falls aktiv),
`policy.decide(decision)` (Z. 1613), Antwort an die Bridge. Es gibt auf der
Python-Seite **keine** Ein-Options-Abkürzung. Die einzige Abkürzung sitzt
*innerhalb* der Policy, nur für die Klasse `priority`:
`_decide_priority` gibt bei `len(options) == 1` sofort die Pass-Option zurück
(`full_game_pilot/priority.py` Z. 48–53, Kommentar dort: „without touching
guard memory") — aber erst, nachdem die Eingangs-Übergänge von `decide()`
(siehe unten) bereits gelaufen sind.

### Pilot-Inventar

Produktiv gibt es genau **eine** Policy: `ExternalPilotDecisionPolicy`
(`full_game_pilot/policy.py`, `decide` ab Z. 52). Sie wird benutzt vom
Benchmark (`scripts/benchmark_xmage_full_games.py`), vom Studio
(`RecordingPolicy`, `studio/games.py` Z. 324, zeichnet nur Frage+Antwort auf —
Protokoll, kein Pilot-Zustand) und vom Digest-Beobachter
(`_ObservingPolicy`, `frame_digest.py`). Die darunter liegenden Bewerter
(`BasePilot`-Unterklassen in `src/commander_lab/agents/pilots.py`) sind je
Aufruf zustandslos: Attribut-Zuweisungen existieren nur in `__init__`
(Z. 312–337, Konfiguration); die „Stil-Reserve" (`reserve_mana_target`) ist
ein statischer Konfigurationswert, kein pro Frage fortgeschriebener Zustand.
Das Urteil unten gilt daher für die Policy-Schicht und damit für jeden
Pilot-Binding gleichermaßen.

### NEIN — kein Zustands-AUFBAU aus erzwungenen Fragen (belegt)

- **Prioritätsfenster zählen:** Der No-Progress-Guard
  (`_priority_last_fingerprint`, `_priority_repeat_count`,
  `_priority_step_windows`, `_priority_latched`) wird bei `len(options) == 1`
  ausdrücklich **nicht** angefasst (priority.py Z. 48–53). Ein erzwungenes
  Pass-Fenster kann den Guard weder auslösen noch zurücksetzen noch den
  Latch verändern (vgl. state.py Z. 179: „a single forced pass would just
  resume the loop" — by design).
- **Stil-/Mana-Reserven:** `_mana_hold` (Halten von Mana für ein Instant)
  wird nur im diskretionären Prioritäts-Pfad vermerkt
  (priority.py Z. 216–224; `payment.py` Z. 786–800). Erzwungene Pässe laufen
  daran vorbei (Rückkehr in Z. 53).
- **Wiederholungszähler:** `_priority_repeat_count` und `_mana_repeat_count`
  (payment.py Z. 918–920) werden nur in diskretionären Pfaden geschrieben.
- **Mulligan-Zähler:** `_mulligan_count` zählt vom Piloten *gewählte*
  Mulligans (choices.py Z. 117–130); ein erzwungenes Keep schreibt nichts.
- **Merken nach der Entscheidung:** Für eine Pass-Auswahl schreiben
  `_remember_priority_cost_facts` (payment.py Z. 1613 ff., quellen-guarded:
  ohne `source_object_id` kein Eintrag) und `_remember_own_cast`
  (state.py Z. 315–326, `pass_priority`/`mana_ability` ausgeschlossen)
  **nichts**.
- **RNG:** Der Zufall je Frage wird aus dem von der Bridge gelieferten
  `decision_offset` abgeleitet (state.py Z. 901–904:
  `seed:seat:decision_offset:decision_class`), nicht aus einem
  Python-Zähler. Übersprungene Fragen verschieben den RNG späterer
  Fragen nicht, solange die Bridge echte Offsets weitergibt.

### JA — Zustands-LÖSCHUNG ist an jede Frage gekoppelt, auch an erzwungene

`ExternalPilotDecisionPolicy.decide` führt bei **jeder** Frage — vor jeder
Auswahl, unabhängig von der Optionszahl — Lebenszyklus-Übergänge aus
(policy.py):

| Stelle | Übergang | Verbraucher (spätere Entscheidung) |
|---|---|---|
| Z. 66 | `_special_mana_pending.pop`, `_payment_source.pop` (alle Klassen außer `mana_payment`/`choose_object`) | Delve-artige Zahlungs-Fortsetzung (`choose_object`-Sonderpfad, policy.py Z. 206) |
| Z. 76 | `_last_payment_offer.pop`, `_outer_unpaid_mana.pop` (die meisten Klassen) | Mana-Wiederholungsfragen lesen das letzte Angebot: payment.py Z. 943, 965 |
| Z. 87 | `_block_frame_asks.pop`, `_block_round.pop` (jede Nicht-Blocker-Frage) | Block-Leiter zählt Fragen je Runde neu: combat.py Z. 306–311 |
| Z. 92 | `_phyrexian_life_promised.pop`, `_selection_ended/_selection_reopened.discard` (jede Nicht-`choose_use`-Frage) | Phyrexian-Zahlungs-Versprechen (#920) |
| Z. 183–194 | Prioritäts-Zweig: Pops von `_priority_cost_facts`, `_optional_mana_commitments`, `_boolean_repeat`, `_priority_spends_source`, `_priority_x_counter_caps`, `_failed_x_announcements`, `_reserved_counters`, `_last_priority_label`, `_last_priority_source`, `_life_dig_yes`, `_counter_cost_progress` — bei **jeder** Prioritäts-Frage, auch dem erzwungenen Pass | `_priority_cost_facts` wird von der folgenden `announce_x`-Frage konsumiert (payment.py Z. 1674 ff.); die Speicher sind dokumentiert als „cleared on the seat's next priority decision" (state.py-Kommentare, payment.py-Docstring Z. 1613 ff.) |

Dazu: Bei erzwungenen Fragen **anderer Klassen** als `priority`
(Ein-Options-`target`/`choice`/…) läuft heute der volle Klassen-Entscheider
inkl. Buchhaltung (z. B. `_equipped_to`, policy.py Z. 278;
Running-Selection-Abschluss, Z. 312–317; Copy-Cast-Buchhaltung, Z. 305–310).

### Urteil zu Bedingung 3

**Nicht sauber erfüllt.** Belegt ist: Kein Pilot *baut* aus erzwungenen
Fragen Zustand auf (kein Zählen von Prioritätsfenstern, keine Reserven).
Aber das *Ablaufen* von Zustand ist an erzwungene Fragen gebunden: Beantwortet
die Bridge sie selbst, ohne dass Python sie sieht, leben die oben gelisteten
Speicher bis zur nächsten Python-gesehenen Frage weiter. Ob das in einer
realen Partie eine spätere diskretionäre Antwort ändert, ist aus dem
Python-Code allein **UNKNOWN** — es hängt an der Frage-Reihenfolge der
Engine (die Verbraucher sitzen in Folge-Fragen derselben Interaktion; für
den Prioritäts-Zweig ist ein Dazwischenkommen einer Prioritäts-Frage
mitten in einem Cast CODE_DERIVED nicht zu sehen, für die Eingangs-Pops
mit klassenübergreifenden Verbrauchern wie `_last_payment_offer` ließ
sich die Unerreichbarkeit nicht ausschließen).

**Konsequenz (wie im Issue vorgesehen):** Die Bridge-Einstellung bleibt
für diese Policy **aus**, bis entweder (a) die Bridge beim Selbst-
Beantworten dieselben Lebenszyklus-Übergänge in Python auslöst (leichte
„Frage vorbeigezogen"-Meldung ohne Entscheidungs-Round-Trip), oder (b)
ein Zwillingslauf (gleiche Partien mit/ohne Überspringen, alle
diskretionären Antworten identisch) die Wirkungslosigkeit belegt.
Der Nachweis in (b) kann mit dem Frame-Digest-Modus aus Teil B laufen
(Digests der verbleibenden Fragen), ersetzt aber nicht den Vergleich der
Antworten selbst (Transkript-Hash, Bedingung 1).

## Teil B — Bedingung 2, Python-Teil: Frame-Digest-Modus „erzwungene Fragen auslassen"

### Ort und Design

Die echte Implementierung ist `src/commander_lab/engine/rules/frame_digest.py`
(nicht im Benchmark-Skript; PR #1281 hat sie dort nur verdrahtet). Neu:

- `is_forced_frame(request)`: erzwungen ⇔ `legal_options` ist eine Liste
  mit **genau einem** Eintrag **und** `minimum_selections ==
  maximum_selections == 1` als echte `int` (nicht `bool`/`float`/`str`).
  Die Schreibweisen `min_selections`/`max_selections` zählen wie in der
  Policy (policy.py Z. 97–98). **Fehlende Bounds ⇒ nie erzwungen**
  (kein Feld erfunden, keine Heuristik).
- `FrameDigest(skip_forced=True)`: lässt erzwungene Fragen **vor** der
  Normalisierung aus — sie verbrauchen auch keine Laufzeit-Identitäts-
  Nummern, daher ist der Digest der verbleibenden Fragen byte-gleich zu
  einem Lauf, der die erzwungenen Fragen nie erhalten hat (pro Platz
  ebenso; der geteilte Normalisierer sieht dieselbe Restfolge).
  `FrameDigestResult.skipped` zählt die ausgelassenen Fragen;
  `frames` zählt wie bisher die verdauten Fragen. Standard ist **aus**;
  der Standard-Digest ist byte-identisch zum bisherigen Verfahren
  (Bestands-Tests unverändert grün, inkl. des gepinnten
  Transkript-Hash-Tests).
- `FrameDigestRunner(..., skip_forced_frames=True)` reicht den Modus durch.
- Benchmark (`scripts/benchmark_xmage_full_games.py`):
  `run --frame-digest-skip-forced` (Fehler ohne `--frame-digest`),
  Report-Feld `frame_digest_skip_forced`, Zeilen-Feld
  `frames_skipped_forced`, und `compare` **lehnt gemischte Modi ab**
  („frame digest modes differ", Exit 1), damit Vorher/Nachher denselben
  Modus rechnen wie Bedingung 2 verlangt.

### Feldlage (keine Lücke im echten Pfad)

Die Frames tragen die Bounds top-level: Die Bridge schreibt
`minimum_selections` in den Request
(`engine-bridge/.../XmageFullGameDecisionController.java` Z. 190), die
Policy liest sie top-level (policy.py Z. 97–98), und der Digest beobachtet
denselben Request (`_ObservingPolicy.decide`, frame_digest.py). Bounds
fehlen nur in synthetischen/Test-Frames — dort greift der Modus bewusst
nicht (Test unten).

### Tests (exakte Zahlen)

Neue Tests: 5 in `tests/unit/test_frame_digest.py`, 2 in
`tests/unit/test_benchmark_xmage_full_games.py`. Abdeckung nach
Ausgabeklasse (Lesson 3): Modus AUS = Digest unverändert und erzwungener
Frame ist Inhalt; zwei Folgen, die sich **nur** in erzwungenen Frames
unterscheiden ⇒ Modus-Digest **gleich**, ohne Modus **verschieden**
(Known-Positive beider Klassen, inkl. Sitz-Digests und Zähler
`frames`/`skipped`); Änderung an einem diskretionären Frame ⇒ Digest
ändert sich auch im Modus (Negativ-Kontrolle); Bounds-Varianten
(fehlend, 0/1, 1/2, float, bool, String, 0/2 Optionen, Nicht-Liste) ⇒
nie übersprungen.

- `tests/unit/test_frame_digest.py` + `tests/unit/test_benchmark_xmage_full_games.py`:
  **64 passed** (davon 7 neu).
- Guard-Dateien zu den geänderten Pfaden (Ritual Schritt 11):
  `test_full_game_batch_games_per_jvm.py`, `test_pilot_comparison_protocol.py`,
  `test_rank_sensitivity.py`, `test_test_hygiene.py`,
  `test_any_usage_ratchet.py`: **77 passed**.
- `ruff check` auf den 4 geänderten Dateien: PASS. `ruff format --check`:
  PASS (frame_digest.py einmalig formatiert, danach Tests erneut grün).
  `mypy src/commander_lab/engine/rules/frame_digest.py`: PASS
  (das Benchmark-Skript liegt nicht im mypy-Scope von CI).
- Changed-Line-Gegenprobe: Ohne die `frame_digest.py`-Änderung schlagen
  die neuen Tests fehl (Import von `is_forced_frame`); ohne die
  Skript-Änderung schlägt `test_compare_rejects_mixed_frame_digest_modes`
  fehl. Ehrliche Schwäche: `test_skip_forced_flag_needs_the_frame_digest`
  besteht auch ohne Änderung (argparse verwirft das unbekannte Flag
  ebenfalls mit SystemExit) — er pinnt den CLI-Vertrag nur vorwärts.
- Volle Suite: **NOT_RUN** (Umfang dieser Vorprüfung: die zwei Testdateien
  + Guard-Dateien oben).

## Offene Punkte / UNKNOWN

1. Erreichbarkeit des Lösch-Risikos aus Teil A in realen Partien:
   **UNKNOWN** (siehe Urteil; entscheidet der Zwillingslauf oder das
   Bridge-Design mit Übergangs-Meldung).
2. `decision_count`/`max_decisions` in `_drive` zählen heute alle Fragen;
   beantwortet die Bridge erzwungene selbst, sinkt der Python-Zähler —
   Semantik-Frage für das Studio-Tor (Claude), kein Pilot-Zustand.
3. Menschen-Platz (Bedingung 5): nicht geprüft, Einstellung bleibt dort
   aus; die menschliche Policy ist nicht `ExternalPilotDecisionPolicy`.

## Fazit für die Bridge-Umsetzung (Claude)

- **Teil B steht:** Der Digest-Modus ist implementiert und getestet;
  das Tor kann Vorher/Nachher mit `--frame-digest-skip-forced` auf beiden
  Seiten rechnen, `compare` erzwingt denselben Modus.
- **Teil A gibt die harte Liste vor:** Die Bridge-Umsetzung muss die
  Lebenszyklus-Pops (policy.py Z. 66, 76, 87, 92, 183–194) entweder
  wirkungsgleich nachbilden/auslösen oder per Zwillingslauf als
  wirkungslos belegen — vorher bleibt die Einstellung für die produktive
  Policy aus (Bedingung 3 nicht erfüllt).

## Geänderte Dateien (uncommittet im Worktree wt-1299)

- `src/commander_lab/engine/rules/frame_digest.py` (Modus + Prädikat)
- `scripts/benchmark_xmage_full_games.py` (Flag, Report-/Zeilen-Felder, Modus-Guard in `compare`)
- `tests/unit/test_frame_digest.py`, `tests/unit/test_benchmark_xmage_full_games.py` (7 neue Tests)
- dieser Bericht (neu)
