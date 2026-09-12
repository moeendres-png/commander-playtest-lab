# WS77 Final Report — Forge Ghalta + Fire Covenant Provider Transport Remediation

Sole-writer workstream for the WS77-owned provider overlay. No behavior credit
claimed or granted (`BEHAVIOR_CREDIT=0/107`; `FULL107=NOT_RUN`).

## 1. Binding causality (WS67 + WS77 diagnosis)

WS67 proved engine-direct PASS for both packets with no Forge fix required.
WS77 reproduced both external-provider paths on the exact WS68 overlay +
accepted pin (`a9a95db`) with a file-logging diagnostic provider build, and
traced the exact provider↔engine call sequences:

### Ghalta — WS65 premise refuted, no provider defect

The scenario card is **Ghalta, Stampede Tyrant** (printed `{5}{G}{G}{G}`,
**no** `ReduceCost`). The engine billed exactly `{5}{G}{G}{G}` — authoritative
and correct. The WS65 intent supplied 6 of 8 mana (authored for Primal
Hunger's 6): the provider loop tapped exactly the 6 scripted sources, applied
each mana natively (`{5}{G}{G}{G}` → `{2}`), exhausted native sources
(`NO_SOURCES`), returned false (`RESULT_FALSE`), and the engine natively
rolled back. Every step conformant. P1 controls exactly 6 lands on turn 21
(`MINTED-149/154` are P2's Swamps, not P1's). Failure class: **HARNESS intent
shortfall**, never provider/engine defect.

### Fire Covenant X-billing hypothesis refuted; division defect found + repaired

- X-billing: engine billed exactly the printed `{1}{B}{R}`; announced life-X
  never entered the mana bill on the provider path either (`{1}{B}{R}` → `{B}`
  persists across 10 further taps → `RESULT_FALSE`). `{R}`+`{1}` paid natively;
  `{B}` was unpayable (fixture deck ships zero black sources). Conformant
  fail-closed rollback — **not** an X-billing defect.
- Division: with a corrected fixture (black mana present, X=5, 1 target),
  payment completes in full and the spell reaches the stack — then the engine
  NPEs at resolution (`DamageDealEffect` unboxes null `getDividedValue`).
  Root cause is a **provider transport defect**: the inherited
  `chooseTargetsFor` never mirrors `PlayerControllerHuman`'s controller-side
  divided-as-you-choose allocation, so no allocation is ever recorded (Human
  assigns; AI assigns in brains). Repaired in the WS77 overlay (Part 1).

## 2. The repair (WS77-owned overlay v2, `ws77_provider_overlay.py`)

- **Part 1 — divided-as-you-choose allocation transport** (Human parity,
  generic, no card names): after successful target selection, determined
  shapes are assigned natively with zero discretion (single target takes the
  whole engine-authoritative remainder; N targets with amount N take 1 each);
  impossible division returns false exactly as Human aborts (native rollback
  follows); discretionary multi-target division and `DividedUpTo` fail closed
  (`ControlledStop`, no first/default/random). Non-divided spells untouched.
- **Part 2 — observation only**: additive milestones on the three silent
  `applyManaToCost` early-false exits plus the `payManaCost` unpaid return, so
  future forensics can distinguish underpayment-rollback from silent drop.
- Post-conditions enforced: no card names, no cost solving, no stack/resolution
  injection, concession seam count 2, combat-cost labels 2, divided exits 2.

## 3. Qualification (actual cards, final build `565f0384`, accepted pin)

| Scenario | Result |
|---|---|
| WS77-A GHALTA-REDUCED (Primal Hunger, bill `{4}{G}{G}`, 6 taps) | PASS: cast/stack/resolve 12/12, turn-25 attack, 12 combat damage |
| WS77-B GHALTA-FULLPAY (Stampede Tyrant, bill `{5}{G}{G}{G}`, 8 taps) | PASS: cast/stack/resolve 12/12 + ETB resolve, turn-33 attack, 12 combat damage |
| WS77-C COVENANT-X5 (X=5, 1 target) | PASS: `DIVIDED_SINGLE`, mana `{1}{B}{R}` in 3 taps, life-5 PAY, resolve (5 to Bear-8, dies) |
| WS77-D FIREBALL-CONTROL (X=3, mana-X) | PASS: `UNDIVIDED`, mana `{3}{R}` in 4 taps, no life confirm, resolve (3 to P2) |
| WS77-R E01-PAY / E01-DECLINE / A04 / C01 | PASS: all frame-identical to WS68 (628/29, 626/28, 1379/47, 975/34) |

All terminals are harness-side intent exhaustion (`BLOCKED_AT`, class HARNESS),
the same termination shape as WS65/WS68 evidence. Hidden-info PASS throughout.

## 4. Terminal distinctions

- `GHALTA_PROVIDER_TRANSPORT=PASS` (conformant; corrected-scenario proof)
- `COVENANT_NONMANA_X_TRANSPORT=PASS` (division transport repaired + proven)
- `G02_GHALTA_REENTRY_PREREQUISITE=READY`
- `G03_GHALTA_REENTRY_PREREQUISITE=READY`
- `G04_COVENANT_ROUTE_PREREQUISITE=READY`
- `PAYCOMBATCOST_REGRESSION=PASS`, `E01_REENTRY_PREREQUISITE=READY` (preserved)
- `CONCESSION_TRANSPORT=PARTIAL`, `G04_OVERALL_REENTRY_PREREQUISITE=NOT_READY`
  (concession out of scope; unchanged even though the Covenant route is correct)
- `WS77_PROVIDER_REMEDIATION=PASS`
- `ACCEPTED_FORGE_PIN=a9a95db6662c2d28814390a9c0c2f986e39aa8b4`
- `BEHAVIOR_CREDIT=0/107`, `FULL107=NOT_RUN`, `ARCHITECTURE_FREEZE=NOT_CLAIMED`,
  `PRODUCTION_PROVIDER=NOT_SELECTED`

## 5. Known limitations (not blockers)

- Multi-target discretionary divided allocation fails closed
  (`DIVIDED_DISCRETIONARY`) by design — a future workstream may externalize it
  through the qualified `amountDistribution` family. No actual-card prerequisite
  needs it (Covenant route uses 1 target; "any number" includes one).
- `DividedUpTo` choice fails closed (no protocol for the discretionary amount).
- Opponent `declare_attacker`/`declare_blocker` entries in these lines are
  turn-bound (v23 precedent); unbound combat entries are ignored by the
  inherited runner binding (observed, worked around, no evidence impact).

## 6. Provenance

- Code head (validated): `c74914c8` (overlay v2 + build + runner + state).
  Clean-head rebuild reproduces digests exactly; witness re-run reproduces the
  Covenant journal exactly (390/20).
- Evidence: scenario dirs (fixture, intent, journal.gz, receipt, adjudication),
  `BUILD_RECEIPT.json`, `REGRESSION_MATRIX.json`, `SOURCE_LOCK.md`, state file.
- Evidence/state descendants do not promote the validated head.
