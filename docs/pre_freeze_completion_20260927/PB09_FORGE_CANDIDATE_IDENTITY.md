# PB-09 — the Forge candidate identity, and why the 79-vs-30 comparison is not admissible

Date: 2026-09-27
Classification: `DIRECTLY_VERIFIED` (git history in `/home/moeen/code/forge` = `moeendres-png/forge`)
Coordinator disposition: **leave as an open evidence-integrity blocker**; do not repin, do not optimize toward a provider.

This supersedes the earlier framing in `PRE_FREEZE_COMPARISON_PACKAGE.md` §7.1 and
`CAMPAIGN_STATE.md` §7, which concluded that the Rules-Core pin was satisfied. **That conclusion was
wrong and is corrected here.**

---

## 1. The correction

Earlier this campaign reported:

> Rules-Core pin: SATISFIED. `a37a865a` is an ancestor of `ef958ee9`, so the executed build included
> the pinned upstream release.

The ancestry fact is true and was verified. The inference drawn from it was not. Ancestry proves the
pinned upstream release is *in the history*; it does not prove the executed tree *equals* that
release at the Rules Core. It does not — and the divergence is in the module that decides Magic
legality.

## 2. What actually ran

| Identity | Commit | Date | Status |
|---|---|---|---|
| Pinned Forge Rules-Core (`config/rules_engines.json` → `secondary_engine.commit`) | `a37a865a532` — `[maven-release-plugin] prepare release forge-2.0.14` | upstream | **ancestor of the executed commit, but NOT what ran** |
| Pinned Lab bridge source (`secondary_engine.bridge_source.commit`) | `4753bb7c72e` | 2026-09-12 | not an ancestor of the executed commit; 328 commits behind on a divergent history |
| **Executed** (WSR22 `SOURCE_LOCK.json` `candidate_identities.forge_commit`, and `FULL107_FORGE_RUNTIME_LOG_INDEX.json`) | `ef958ee91ac` — `master`, "Merge pull request #3 from moeendres-png/merge-wsr19-into-master" | 2026-09-21 | the artifact that produced 79 PASS / 21 UNKNOWN / 7 BLOCKED |

`ef958ee9` is an ancestor of `wsr24/forge-candidate-evidence-closure-20260927` = `18bba95a`, exactly
the `historical_wsr20_reference.evidence_tip` WSR22 records.

## 3. The divergence is in the Rules Core, not just the bridge

`git diff --name-only 4753bb7c72ea60d653121e0bab989077b4009f9c ef958ee91ac6c9ce0152189f2654bf6e05abf273`
returns **1211 changed files**. Broken down by module, counting only `src/main/java`:

| Module | Role | Engine-source files changed |
|---|---|---|
| **`forge-game`** | **the Forge Rules Core** (cards, abilities, zones, the stack, combat, SBA, replacement/prevention) | **61** |
| `forge-ai` | engine-internal AI / decision layer | 40 |
| `forge-gui` | user interface | 16 |
| `forge-core` | core utilities | 7 |
| `forge-protocol2-bridge/` | the Lab Protocol-2 bridge module (244 files total) | 222 (module files, not engine) |

**47 commits touch `forge-game/src/main/java/` between the pin and the executed commit.** These are
Lab workstreams, not upstream syncs. Verbatim from the history:

| Commit | Subject |
|---|---|
| `2ee2d1cf089` | **WS40 migrate combat damage legality into Forge Core** |
| `a4e3a125ed2` / `abe3379b19b` / `d2fd8f666f2` | WS40 noncombat amount distribution transaction / view / selection |
| `f91b7f7787d` | WS40 allow progressive trample and legacy combat assignments |
| `7aeb14b098e` / `f83b77aa75e` | WS40 add native restored spell cast history / bind restored history to caller and stack ability |
| `14007552537` | **WS45 add typed native Commander relation history** |
| `b839b87b2ce` | WS45 type qualification knowledge and RNG history |
| `bec01196dfd` | WS45 add native restored qualification history |
| `867207a92ea` / `6d570a5e17e` / `a248bf22ca9` | WS45 native semantic observation state / typed engine observation policy / validated native extra-turn history |
| `d1a65fd4a37` | WS45 fix native partner API invocation |
| `66caae16015` | WS45 expose deterministic GameState identity mapping |
| `a9a95db6662` / `aa5c00aa32d` | **WS59 forge RQ-C3 engine remediation** for A04/C01/G04; WS76 immediate-concession snapshot hardening + corrected H01 Clone/Humility oracle |
| `c4d67145a6f` | **WS217 native Core-owned chooser-divided allocation seam (CR 601.2d)** |
| `bc347e62255` | **WS234 systemic Cleave identity plus Aftermath script fix with actual-card behavior tests** |

Roughly 22 of the 47 carry a `WS*`/`ws*`/`wsr*` workstream tag; the remainder are their merge and
follow-on commits inside the same Lab campaign. None is an upstream release bump.

**So the executed Forge candidate is a Lab-authored fork of the Forge Rules Core.** Lab migrated
combat-damage legality into Core, added Commander relation history, extra-turn history, restored
spell-cast history, a CR 601.2d chooser-divided allocation seam, Cleave identity and an Aftermath
script fix.

## 4. Consequence for the comparison

**The Forge 79 PASS versus XMage 30 PASS difference is not admissible as a provider capability
ranking, for a stronger reason than the Coordinator cautioned.**

- The XMage side executed **pristine pinned XMage** at `b1959698…`, exactly main's pin (verified).
- The Forge side executed a **Rules-Core fork carrying Lab's own Rules engineering** — including
  Rules fixes for the very obligation families the comparison measures (combat damage, chooser
  allocation, Commander relations, mode identity, actual-card behavior).

So the comparison does not contrast two upstream engines. It contrasts pristine XMage against a
Lab-modified Forge. Any apparent Forge advantage partly measures **Lab's Forge fork**, not Forge.
This is `EVIDENCE_ASYMMETRY` of the most consequential kind, and it is invisible unless the
candidate identity is pinned.

Two further consequences follow:

1. **PB-03's premise weakens further.** PB-03 showed the 33 XMage BLOCKED rows are a *Lab harness
   defect*, not an XMage capability limit. PB-09 now shows part of the Forge column is a *Lab engine
   fork*. Both sides of the same 107-row denominator are shaped by Lab work — one by a harness
   shortcut, the other by engine modification. Neither column is a clean candidate measurement.
2. **AF11 licensing must be recomputed.** AF11 records "XMage MIT, Forge GPL-3.0" from the source
   lock. That is the *upstream* licence label. The executed artifact is a Lab-authored derivative of
   GPL-3.0, so the licence posture of the candidate that actually ran is not the one AF11 recorded.

## 5. What must NOT be done

- **Do not repin `config/rules_engines.json` to `ef958ee9` to make the evidence consistent.** That
  would silently designate a Lab Rules-Core fork as "the Forge candidate" and launder 47 Rules-touching
  Lab commits into a provider pin. The Coordinator owns provider and candidate identity.
- **Do not edit `ef958ee9` into any provenance or evidence field.** The executed commit is a
  historical fact and stays recorded.
- **Do not read the Forge column as Forge's capability.** It is at least partly Lab's.
- **Do not discard the Forge evidence.** It is valid evidence *of a Lab-modified Forge*; it is not
  valid evidence *of pinned Forge*.

## 6. The decision the Coordinator owns

One question, and it is a provider/architecture question, not a coding question:

> **Which artifact is the Forge candidate for Architecture Freeze: upstream `forge-2.0.14`
> (`a37a865a`) as pinned, or the Lab fork (`ef958ee9`) that the evidence actually executed?**

The two admissible resolutions, with their honest consequences:

- **Pinned upstream.** Then the Forge evidence must be re-run at `a37a865a` + the pinned bridge
  `4753bb7c`, and the current Forge column is discarded. Expect the 79 PASS to fall, because it
  currently includes Lab's Rules work. Cost: one full Forge requalification.
- **Lab fork.** Then the pin manifest must be corrected to record the fork, the 47 Rules-touching Lab
  commits must be listed as part of the candidate, AF11's licence posture must be recomputed for a
  GPL-3.0 derivative, and the Coordinator must decide whether a self-modified GPL-3.5 fork is an
  acceptable production dependency for this project. Cost: documentation plus a licence ruling, no
  requalification.

Either way, **PB-09 is cheap to resolve and blocks sound comparison**, which is why it now ranks
ahead of PB-03: PB-03 improves one column, PB-09 determines whether either column means anything.

## 7. Interim standing until it is resolved

| Item | Classification |
|---|---|
| Forge FULL107 79/21/7 | `REQUIRES_RECONCILIATION` — valid for a Lab fork, not for the pinned candidate |
| Forge AF00 `SOURCE_AND_BUILD_LOCK = PASS` | **unsupported**; the executed Rules Core is not the pinned one |
| Forge AF11 `INTEROP_LICENSE_TOPOLOGY` | licence posture requires recomputation for a GPL-3.0 derivative |
| Forge `engine_commit_source=env:FORGE_ENGINE_SHA` (PB-05) | still not build-proven; a build-derived commit is required regardless of which candidate wins |
| XMage FULL107 30/44/33 and AF00 | unaffected; XMage ran at exactly its pin |
| Same-semantics denominator (25/107) | unaffected, but too small to separate the candidates on its own |

`PROVIDER_COMPARISON_COMPLETE = NO` for this reason independently of PB-03.
`PRODUCTION_PROVIDER = NOT SELECTED`. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
