# Max-Review Pass 2 — Lese-Befunde im Detail

Alle Befunde CODE_DERIVED (Dateien gelesen, nicht zur Laufzeit geübt), außer
wo DIRECTLY_VERIFIED vermerkt ist. Quellen: Worktree `wt-maxreview2`
(@ `217c34d95`) für Repo-Dateien, GitHub-API (2026-10-25) für Fork/Upstream.
Pass-1-Lücken, die hiermit geschlossen werden, sind je Befund benannt.

## 1. XmageLosslessHiddenPlan.java — vollständig gelesen (668 Zeilen)

- Pfad: `engine-bridge/src/main/java/org/commanderlab/xmage/` (nicht
  org/mage/bridge). Zeilenzahl per `wc -l` verifiziert: 668
  (der Auftragstext nannte 669 — Datei hat 668 Zeilen).
- Schließt Pass-1-Lücke O-04-Teil „668 Zeilen ungelesen".
- Inhalt: SLOT-04 fail-closed Parser — vollständige Bibliothek top-to-bottom
  + expliziter nativer FaceDownType + vollständige Hand; keine Inferenz; jede
  Abweichung benannter Fehlercode (u. a. PARTIAL_LIBRARY_REQUEST,
  LIBRARY_POSITION_MISMATCH, FACE_DOWN_TYPE_ON_FACE_UP_OBJECT). Ein
  Face-down-Objekt pro Request.
- Anwendung nur über native RG-06A-APIs; Verifikation nennt
  Spieler/semantisches Objekt/Position, nie Kartenidentität (kein Leak in
  Arrival-Response).
- Tests: kein eigenes `XmageLosslessHiddenPlanTest`; HiddenPlan-Abdeckung läuft
  über `XmageNativeStateRestorationTest` (1.066 Z.) u. a. Restoration-Tests.
  Bridge-Tests dazu laufen im Bridge-Build mit (s. 00_BERICHT §6).

## 2. Bridge-Testdateien — klassifiziert (209 Dateien, 62.530 Zeilen)

- Bestand exakt wie Pass-1-Inventar, alle in
  `engine-bridge/src/test/java/org/commanderlab/xmage/`.
- Themen nach Namensgruppen: Multiplayer* (~60, Engine-direkte
  Multiplayer-Qualifikation), FullGame* (Decision-Klassen, Replacement,
  Inventory, Shutdown), Midgame* (Kausal-/Midgame-Rows), Restoration*
  (Checkpoint/Commander-Damage/Native), Corpus/Capability (ActualCardCorpus
  2.477 Z., Pb03Tier1Rows 1.940 Z.).
- Vollständig gelesen (klein, entscheidungsrelevant):
  - `PoolCoversManaCostDirectionTest.java` (44 Z.): sichert `cost.enough(pool)`
    gegen invertierten Aufruf — stützt #1007-Ursache-(2)-Richtung
    (Flag-Semantik ist richtungsempfindlich; die Hybrid-Doppelzählung ist ein
    weiterer, hier nicht abgedeckter Fall).
  - `XmageBlockCapacityTest.java` (33 Z.): CR 509.1a, maxBlocks=0 = beliebig
    viele (Palace Guard etc.); 0 angebotene Angreifer = keine
    Block-Entscheidung.
  - `XmagePb03CapabilityManifestTest.java` (41 Z.): Manifest ohne
    Global-Promotion; supported: qualified turn-1, commander damage matrices;
    unsupported: stack spells, controller/owner divergence;
    `starting_state_injection_supported=false`.

## 3. Fork-PR #64 / #62 — rekonstruiert (GitHub-API, DIRECTLY_VERIFIED)

- Fork-PR #64: „XMage upstream update: merge magefree/mage master (fab0f23b)
  into the candidate line", closed, merged 2026-10-20T10:47:35Z, Head
  043579bb, Base claude/xmage-mp-candidate-20260929. → Upstream-Baseline des
  Forks ist `fab0f23b` (2026-10-20), wie in Pass 1 vermutet.
- Fork-PR #62: „Add /oc-zai lane: Z.ai GLM-4.7-Flash", closed, merged
  2026-10-20T09:47:16Z. ZAI-Thema von Hans am 2026-10-24 als geklärt bestätigt
  → keine weitere Verfolgung.

## 4. Repo-weite „keine zweite Engine"-Grep — geschlossen, mit Grenzbefund

- Grep repo-weit: `def .*legal|is_legal|legal_options=|legal_actions=` →
  Definitionen nur in `engine/rules/*` (base/bridge/tactical/validation/
  full_game, sanktionierte Provider-Schicht) oder in Qualification-/Replay-Code,
  der Engine-angebotene Optionen konsumiert (Parametername `legal` ≠
  Rekonstruktion).
- `random.choice/randint` außerhalb Tests: kein Treffer in Produktions-Pilotnähe.
- **GRENZBEFUND (kein Verdikt, Adjudizierung an Coordinator/Owner nach §8
  AGENTS.md):** `engine/structural/simulator.py` — `StructuralSimulator`,
  „fast role-based Commander simulator", eigene Turn-/Lebens-/Schadens-Schleife,
  eigenes `random.Random(config.seed)`, Ergebnisse gelabelt
  `structural_model_estimates`, Docstring: „deliberately models deck structure
  rather than comprehensive Magic rules". Importeure (produktionsnah):
  `agents/ensemble.py`, `agents/validation.py`, `cli/app.py`, `evals/runner.py`,
  `mulligan/lab.py`, `optimization/experiments.py`.
  - Pass-1-Aussage „keine zweite Engine" war auf engine/rules + pilots.py
    gestützt und damit zu eng formuliert. Korrekte Aussage: keine zweite
    *Rules*-Engine mit Legalitäts-Anspruch; daneben existiert ein deklarierter,
    als Schätzung gelabelter Struktur-Simulator, dessen Produktions-
    Erreichbarkeit im Bericht zu benennen ist. Ob seine Nutzung in einem Pfad
    XMage-Autorität substituiert, ist eine Coordinator-/Owner-Adjudizierung,
    keine Mess-Aussage.
  - Nebenbefund: `optimization/search.py: all_legal_single_swaps` — „legal" =
    Deckbau-Legalität (Farbidentität etc.), keine Spielregeln; keine
    Verwechslungsgefahr, wenn benannt.

## 5. Upstream nach 2026-10-20 — geschlossen (GitHub-API, DIRECTLY_VERIFIED)

- Fork `origin/master` nach Pin v13: nur Workflow-Commits (PR #62 ZAI-Lane,
  PR #55 C12-Egress-Fix). KEINE Engine-/Karten-Commits nach dem Pin.
- `upstream/master` (magefree): git-Fetch zweimal an Netzfehlern gescheitert
  (early EOF nach 63 Min.; TLS-Disconnect im Retry) — stattdessen API +
  ls-remote: Tip live `518aef19` (2026-10-25, „Animations rework"), lokaler
  Ref `bb0ed0f72` datiert 2026-10-18 (vor dem Fenster).
- **72 Commits seit 2026-10-20** (vollständige erste Seite, <100):
  überwiegend neue Karten-Implementierungen (Star-Trek-Set u. a.) +
  App/GUI-Fixes; Baseline `fab0f23b` (2026-10-20) im Fenster bestätigt.
- Folgerung: Upstream ist weitergezogen, der Fork hat nichts davon gemergt —
  Pin v13 unberührt, kein Fork-Handlungsbedarf aus dieser Prüfung (ein
  künftiger Upstream-Merge wäre eine neue Owner-Entscheidung).
