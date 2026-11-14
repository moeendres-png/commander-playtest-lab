# Fresh-Eyes-Review: #1299-Vorprüfung (wt-1299, Basis dc7ccaa11)

- **Datum:** 2026-11-13
- **Art:** Unabhängiges adversarial Review, frischer Kontext. Geprüft: uncommitteter
  Diff in `frame_digest.py`, `scripts/benchmark_xmage_full_games.py`, beiden
  Testdateien; Bericht `FORCED_PASS_PRECHECK_1299_2026-11-13.md` nur auf
  Konsistenz Code↔Behauptungen.
- **Verdict: PASS mit Auflagen** (kein P1, kein P2; 4× P3, davon keine
  push-blockierend).

## Geprüft und OHNE Befund

1. **Standard-Verhalten (Modus aus):** `FrameDigest.observe`
   (frame_digest.py:210) prüft `self.skip_forced and …` — bei `False` läuft
   exakt der alte Pfad (Normalisierung, Zähler, Hashes unverändert).
   `FrameDigestResult.skipped` hat Default 0 (Z. 196), Konstruktionen mit
   3 Argumenten bleiben gleichwertig. Bestands-Tests inkl. gepinnter Digests
   laufen unverändert: beide Testdateien **64 passed** (vom Reviewer selbst
   gelaufen), `ruff check`/`ruff format --check` PASS, `mypy frame_digest.py`
   PASS — alle Berichtsangaben dazu stimmen.
2. **`is_forced_frame` (frame_digest.py:169–186) ist exakt die Issue-Definition:**
   `legal_options` muss eine Sequence (nicht str/bytes) der Länge 1 sein;
   Bounds per `_selection_bound` mit derselben Vorrangfolge wie die Policy
   (policy.py:97–98: `minimum_selections` vor `min_selections`);
   `type(x) is int` schließt `bool` (int-Subtyp), `float` und `str` aus —
   alle drei Fälle sind getestet. Fehlende Bounds ⇒ `None` ⇒ nie erzwungen
   (konservative Richtung: kein falsches Auslassen gefunden; Abweichungen
   zur Policy wie `int(1.0)` fallen ebenfalls auf die sichere Seite).
   Feldlage verifiziert: Die Bridge schreibt die Bounds und `legal_options`
   top-level in denselben Request, den der Digest beobachtet
   (`XmageFullGameDecisionController.java:190–192`;
   `_ObservingPolicy.decide` beobachtet exakt den Request der Policy).
3. **Auslassen VOR der Normalisierung:** In `observe` vor
   `_normalize_request` und vor jeder `_Normalizer`-Berührung — ausgelassene
   Frames vergeben keine `id#<n>`-Nummern; der geteilte Normalisierer sieht
   nur die Restfolge, daher sind Gesamt- und Pro-Platz-Digests byte-gleich
   zu einem Lauf ohne diese Frames (unter der Tor-Prämisse identischer
   Rest-Frames; Test `test_skip_forced_ignores_forced_frames_and_nothing_else`
   belegt Gesamt-, Sitz-Digest und Zähler, inkl. verändertem erzwungenem
   Frame als Inhalt).
4. **`compare`-Modus-Guard (benchmark:404):** `bool(...) != bool(...)` ist
   richtungssymmetrisch; fehlendes Feld in Alt-Berichten ⇒ `False`, wird also
   gegen einen Skip-Bericht korrekt abgelehnt und gegen einen neuen
   Standard-Bericht (`False`) korrekt durchgelassen; kein Crash-Pfad.
   Empirisch gegen die Basis geprüft (Scratch-Kopie, nur die zwei Dateien
   auf HEAD zurückgesetzt): Der Mixed-Mode-Test **fällt auf der Basis mit
   `assert 0 == 1`** — compare winkte gemischte Modi vorher durch.
5. **Teil-A-Belege (Stichproben, alle exakt):** policy.py-Pops an Z. 66
   (`_special_mana_pending`), Z. 76 (`_last_payment_offer`), Z. 87
   (`_block_frame_asks`), Z. 92 (`_phyrexian_life_promised`) und Z. 183–194
   (11 Prioritäts-Pops, Anfang `_priority_cost_facts`, Ende
   `_counter_cost_progress`); full_game.py Z. 1577 `decision_count += 1`,
   Audit/`policy.decide` im selben Block wie berichtet; priority.py
   Z. 48–53 erzwungener Pass ohne Guard-Berührung; Java-Bounds Z. 190.
   Berichts-Zählung „5 + 2 neue Tests" stimmt mit dem Diff überein.

## Findings (alle P3)

- **P3-1 — Standard-Läufe schreiben neue Report-Felder.**
  `scripts/benchmark_xmage_full_games.py:155` (`frames_skipped_forced` in
  jeder Zeile, auch im Standard-Modus mit Wert 0) und Z. 306
  (`frame_digest_skip_forced: false` im Report-Kopf). Die *Digests* bleiben
  byte-identisch (Behauptung des Berichts ist dafür korrekt), aber die
  JSON-Form von Standard-Berichten ist nicht mehr dieselbe wie vor der
  Änderung. `compare` liest nur benannte Felder und behandelt alte/neue
  Standard-Berichte korrekt — funktional unschädlich, sollte aber im
  PR-Text als additive Änderung benannt sein statt unter „Standard
  unverändert" zu verschwinden.
- **P3-2 — `compare`-Guard nur in einer Richtung getestet.**
  `test_compare_rejects_mixed_frame_digest_modes` prüft plain→skipped und
  skipped→skipped, nicht skipped als Datei A gegen plain als Datei B und
  nicht Alt-Bericht (Feld fehlt) gegen Skip-Bericht. Der Code ist symmetrisch
  (`!=` auf `bool(get(...))`), daher kein Fehler vermutet — ein Test je
  Richtung würde die Tor-Eigenschaft aber festnageln.
- **P3-3 — Verdrahtung ohne Test:** `FrameDigestRunner(skip_forced_frames=…)`
  und die Durchreichung in `_runner`/`_play`/`_play_batch` haben keinen
  Test, der einen Lauf mit aktivem Modus zeigt (nur Flag-Validierung und
  Digest-Ebene sind getestet). Ein kleiner Test über `_runner(...,
  frame_digest=True, skip_forced_frames=True)` → `digest_for` mit einem
  erzwungenen Frame würde die Kette schließen.
- **P3-4 — Changed-Line-Nachweis der 5 Digest-Tests läuft über den Import.**
  Auf der Basis scheitern sie an der Collection (`ImportError:
  is_forced_frame`), nicht an einer Verhaltens-Assertion; der Bericht sagt
  das wörtlich so — ehrlich, aber die schwächste Form des Nachweises.
  (Der Benchmark-Mixed-Mode-Test dagegen fällt auf der Basis per Assertion,
  siehe oben; und `test_skip_forced_flag_needs_the_frame_digest` besteht
  auch auf der Basis — im Bericht korrekt offengelegt.)

## Anmerkung ohne Finding

Eine Klasse bleibt bewusst außerhalb: Ein Sitz, dessen Frames *alle*
erzwungen sind, fehlt im Skip-Modus in `by_seat` — in beiden verglichenen
Läufen gleich, tor-korrekt. Die `frames`-Zahl unterscheidet sich im
Skip-Modus per Design von einem Standard-Lauf; `compare` vergleicht sie nur
innerhalb desselben Modus (durch den Guard erzwungen).
