# RQ-X1 — Runtime Mirror Spec (DESIGN ONLY — DO NOT EXECUTE; DO NOT SELF-AUTHORIZE)

Pin to mirror: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c` (`/tmp/rq-xmage-src`
read-only; the mirror NEVER modifies it — all instrumentation is
out-of-process: client callbacks, log capture, fresh-checkout copies for
any throwaway experiments, separate worktree/branch for mirror code).

## Value verdict

`XMAGE_RUNTIME_MIRROR_VALUE = MEDIUM`

- WHY NOT LOW: R-1/R-2/R-3 (engine legal sets, UUID+ZCC binding,
  server-redacted views) are source-strong but RUNTIME-UNCONFIRMED. A narrow
  mirror is the only way to promote them toward runtime evidence, and the
  questions are crisply falsifiable in days, not months.
- WHY NOT HIGH: C-2/C-3 (global RNG, no replay) are ALREADY DECIDED at source
  level against seed/replay support — the mirror would quantify, not
  discover. No source evidence suggests the mirror could reverse the RNG
  verdict upward; the realistic best case is "bounded single-game journaling
  works; cross-game determinism fails closed as predicted."
- WHY NOT VERY_HIGH: nothing in the audit indicates XMage hides a positive
  surprise large enough to single-handedly reverse the Forge-centric lead;
  the lead-reversal condition is architectural/strategic (Coordinator
  authority), not hidden-evidence-shaped.

## Smallest mirror that could decide the issue (5 probes, stop-early)

All probes OUT-OF-PROCESS against a stock test-mode server + scripted
`TestPlayer` games. No engine edits. No adapter product code — throwaway
capture scripts only, on a separate branch/worktree if any CPL file is
created (mirror code is NOT part of RQ-X1 and NOT authorized here).

**M-1. Legal-set fidelity probe (promotes R-1; ~1 day).**
Capture every `GameClientMessage` options payload (target UUID sets, Choice
sets, mode maps, amount bounds) across scripted 2P games covering cast,
activate, target, mode, X, attack, block, trigger-order, replacement-choice.
Assert: (a) every prompt carries a non-empty machine-readable legal set
(except documented booleans); (b) every echoed member is accepted; (c)
mutated echoes (random UUID, member-removed, stale member) are rejected or
re-prompted — never executed. DECIDES: whether wire legality is complete and
fail-closed at runtime. STOP-EARLY: any executed illegal echo ⇒ seam
UNSOUND, downgrade R-1, skip M-2.

**M-2. Binding/staleness probe (promotes R-2; ~1 day, needs M-1 PASS).**
Two identical tokens/copies on board; select each by UUID; assert distinct
resolution. Delay an echo past a zone change (scripted removal in between);
assert old UUID is NOT applied to the new object (fizzle/re-prompt/null).
Submit the same valid UUID twice; record behavior (idempotent vs double-apply
vs reject) — any double-apply is a pilot-safety finding. DECIDES: exact
binding + duplicate/stale behavior at runtime.

**M-3. Hidden-info adversarial probe (promotes R-3; ~2 days).**
Man-in-the-middle capture of ALL `GameView`/`CardsView`/`GameClientMessage`
bytes per recipient across games using hidden zones (hand, library, morph,
manifest, foretell, hidden exile, look-at, search, sideboard). Assert:
(a) no hidden card name/rules/PT leak to unauthorized recipient; (b) log
strings contain no hidden names; (c) record ALL UUID/set-number exposures as
accepted-tracking-risk or finding. DECIDES: whether server-redaction holds
under byte-level observation (still not a proof, but the strongest available
negative evidence). STOP-EARLY: any hidden-name leak ⇒ R-3 downgraded to
UI_ONLY-class, pilot must re-derive projection.

**M-4. RNG falsification probe (quantifies C-2; ~1 day, decisive by design).**
The R-A…R-D experiment from `XMAGE_RULES_RNG.md` §4 executed for real:
seed-reset equality (R-A), no-arg-shuffle determinism (R-B), AI/setup
cross-contamination (R-C), bookmark-restore divergence (R-D). PREDICTED:
R-A passes narrowly, R-B/R-C/R-D FAIL. DECIDES (on first FAIL): seed-based
determinism is impossible without engine changes — closes the question
empirically. If ALL pass (unexpected), escalate to concurrency + version-pin
follow-up before any determinism claim.

**M-5. Journal-completeness probe (quantifies C-3 + C-1; ~2 days, needs M-1).**
Record options+selections+views per decision for full scripted games (2P, 3P
FFA, 4P Commander FFA); assert the journal SUFFICES to re-drive an identical
fresh game to identical decision points with identical offered sets
(re-drive open-loop: feed recorded selections at each prompt, compare offered
sets). RNG-affected branches expected to DIVERGE (per M-4) — record the
divergence boundary precisely. DECIDES: the exact envelope where adapter-side
journaling works and where determinism fails — i.e. theStatement of what a
production adapter could and could not guarantee.

## Authorization boundary

This spec is EVIDENCE for a Coordinator/user decision. Executing ANY probe
requires a NEW workstream contract (branch, worktree, ownership, gates) and
explicit user authorization. RQ-X1's no-mirror hard gate remains in force.
Cost estimate (for planning only): ~5-7 days single worker, mostly M-3/M-5
capture harnessing; M-1/M-2/M-4 are small.
