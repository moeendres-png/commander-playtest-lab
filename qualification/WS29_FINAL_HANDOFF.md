# COMMANDER SIMULATION FOUNDRY

# WS-29 — CANONICAL CR + 29-CARD AUTHORITY CLOSURE — FINAL HANDOFF

## Source Lock

Repository: `moeendres-png/commander-playtest-lab`

Canonical `main` at WS-29 branch creation:

- commit: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- tree: `551c0d55a171508618d2b7d29e0f49b19893f886`

Provider-neutral work branch:

- `ws29/canonical-authority-closure`
- parent immediately before this final handoff commit: `ba30ce2b4bba2dfb372aed2e7d78c107fad6f477`
- final closure head: **the commit containing this file**

The exact final closure commit SHA/tree SHA cannot be embedded into the file that creates that commit without changing the commit itself. They are therefore recorded after commit by the exact-head `WS-29 Final Authority Closure` CI evidence and in Draft PR #142 without mutating the branch again.

Input state:

- WS-04: available through project handoff evidence.
- WS-11: available through project handoff evidence.
- WS-17 / WS-17R: available through project handoff/repository evidence.
- WS-25: available and used for Forge runtime-status reconciliation.
- WS-26: available and used for XMage runtime-status reconciliation.
- WS-27: `INPUT_UNAVAILABLE`; no supplied file and no matching connected Drive/GitHub artifact was found. It was never treated as satisfied.
- WS-26 `ACTUAL_CARD_AUTHORITY_LOCK.json`: reverified rather than blindly trusted.

No candidate engine semantics were changed in WS-29.

## Official Comprehensive Rules Lock

Official Wizards Rules page:

- `https://magic.wizards.com/en/rules`

Current linked CR identity used by WS-29:

- Comprehensive Rules effective: **August 7, 2026**
- official PDF: `https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.pdf`
- official TXT URL: `https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt`

CR rule 108.1 establishes Oracle as authoritative card wording and identifies Gatherer as the Oracle source.

## CR Raw-Byte / SHA256 Result

`OFFICIAL_CR_RAW_BYTES = PASS` via direct byte-preserving acquisition of the official Wizards PDF from a clean GitHub Actions runner.

Official PDF lock:

- HTTP status: `200`
- final URL: unchanged
- Content-Type: `application/pdf`
- Content-Length: `2524708`
- raw byte count: `2524708`
- Last-Modified: `Thu, 30 Jul 2026 16:08:21 GMT`
- ETag: `"ac73bb08d50387bb93dcffb9d236545d:1785776413.840035"`
- retrieval UTC: `2026-08-30T18:47:55.653374Z`
- SHA-256: `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`
- PDF magic header: verified

Official TXT raw-byte acquisition:

- HTTP status from GitHub Actions: `404`
- retrieval UTC: `2026-08-30T18:47:55.633819Z`
- raw SHA-256: **not claimed**
- result: `TXT_RAW_BYTES = UNKNOWN`

No hash was derived from browser-parsed TXT text.

The prior successful network authority run was:

- head: `2eb550eaebea01ce5a13532613833f0c485fc31e`
- run ID: `33329086402`
- job ID: `99304293860`
- artifact ID: `9737109224`
- artifact ZIP SHA-256: `a5115a2e206317ff7eef049f1591aca8342638c032e45f159f6b73e18a0601ed`

## Gatherer Access Result

`GATHERER_DIRECT_ACCESS = PASS` from GitHub Actions.

Allowed public paths were tested independently of the Coordinator browser environment:

- legacy Gatherer root redirect / modern root: HTTP 200;
- public exact-name search: HTTP 200;
- public card-detail pages: HTTP 200.

Only ordinary public GET requests, a normal browser User-Agent, standard redirects, and public search/detail URLs were used.

No CAPTCHA bypass, authentication bypass, private API, credentialed scraping, reverse-engineered private endpoint, or anti-bot circumvention was used.

## Authority Policy

WS-29 freezes the following fail-closed authority rules:

1. Direct official Wizards authority is required for `AUTHORITY_PASS`.
2. Current official CR outranks engine behavior.
3. Current official Oracle/Gatherer is the authoritative current card-text source.
4. Official release notes/rulings can establish interaction-level authority and are supplemental when current Gatherer is available.
5. Printed card images/previews alone are narrower than full current Oracle authority.
6. Historical release notes do not automatically prove current Oracle equivalence.
7. Scryfall, MTGJSON, engine card data, and other secondary sources are discovery/cross-check aids only.
8. Engine implementation never establishes authority.
9. Provider agreement never establishes authority.
10. Authority closure never upgrades candidate runtime evidence.

Frozen machine-readable policy is in `qualification/ws29/CARD_AUTHORITY_LEDGER.json`.

## 29-Card Authority Matrix

All frozen cards reached terminal current authority status.

| ID | Card | Current authority | Fixture discriminator |
|---|---|---|---|
| CARD_01 | Ishai, Ojutai Dragonspeaker | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_02 | Rograkh, Son of Rohgahh | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_03 | Esior, Wardwing Familiar | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_04 | Kediss, Emberclaw Familiar | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_05 | Veyran, Voice of Duality | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_06 | Harmonic Prodigy | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_07 | Narset, Parter of Veils | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_08 | Jeska, Thrice Reborn | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_09 | Magma Opus | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_10 | Wash Away | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_11 | Wear // Tear | FULL_CURRENT_ORACLE_LOCK, both faces | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_12 | Dig Through Time | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_13 | Flare of Duplication | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_14 | Vandalblast | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_15 | Finale of Revelation | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_16 | Psychosis Crawler | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_17 | Kaervek the Merciless | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_18 | Shriekmaw | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_19 | Butcher of Malakir | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_20 | Syphon Mind | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_21 | Gratuitous Violence | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_22 | Bolt Bend | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_23 | Makeshift Mannequin | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_24 | Warstorm Surge | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_25 | Basilisk Collar | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_26 | Burn Down the House | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_27 | Path of Ancestry | FULL_CURRENT_ORACLE_LOCK | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_28 | Find // Finality | FULL_CURRENT_ORACLE_LOCK, both faces | DISCRIMINATOR_AUTHORITY_PASS |
| CARD_29 | Boseiju Reaches Skyward // Branch of Boseiju | FULL_CURRENT_ORACLE_LOCK, both faces | DISCRIMINATOR_AUTHORITY_PASS |

Totals:

- `FULL_CURRENT_ORACLE_LOCK`: **29/29**
- `DISCRIMINATOR_AUTHORITY_PASS`: **29/29**
- `AUTHORITY_BLOCKED`: **0/29**
- `CURRENTNESS_UNPROVEN`: **0/29**
- `PRINTED_TEXT_ONLY` as terminal primary status: **0/29**

The frozen Gatherer acquisition corpus from the source network run has SHA-256:

`f75e1c322a15d94fb89f1409cd42ea9e2095cc25810d845bcf8518d4d5634b10`

## Currentness Analysis

Older official release-note material was not promoted directly to full current Oracle authority.

Currentness was instead closed by fetching every relevant card face from current public official Gatherer on August 30, 2026. Therefore historical release-note warnings about later Oracle/rules changes do not leave the frozen 29-card corpus in `CURRENTNESS_UNPROVEN`.

Official release notes/rulings remain useful as interaction-level supporting authority where present, but current Gatherer is the current Oracle lock.

Split/transforming identities were handled face-by-face:

- CARD_11: Wear and Tear separately resolved to official Gatherer faces;
- CARD_28: Find and Finality separately resolved;
- CARD_29: Boseiju Reaches Skyward and Branch of Boseiju separately resolved.

## CARD_02 / CARD_04 / CARD_24 Reconciliation

### CARD_02 — Rograkh, Son of Rohgahh

Authority component: **PASS / retained and strengthened**.

Current Gatherer establishes the current card identity, mana cost `0`, current rules text, and `0/1` characteristics. Current CR establishes Commander command-zone casting and commander tax semantics.

Runtime evidence remains separate:

- Forge runtime: `PASS` from WS-25 evidence;
- XMage runtime: `PASS` from WS-26 evidence.

No runtime PASS was inferred from authority.

### CARD_04 — Kediss, Emberclaw Familiar

Authority component: **PASS / retained**.

Current Gatherer supplies current Oracle authority. Official Commander Legends material additionally supports the tested damage interaction, including that the added damage is not combat damage and does not recursively retrigger Kediss.

XMage runtime `PASS` remains valid as runtime evidence; Forge is not upgraded to runtime PASS.

### CARD_24 — Warstorm Surge

Authority component: **PASS / retained**.

Current Gatherer supplies current Oracle authority. Recent official Avatar release-note material additionally supports the entering-creature damage discriminator and damage-source semantics.

XMage runtime `PASS` remains valid as runtime evidence; Forge is not upgraded to runtime PASS.

No cross-workstream authority downgrade is required for CARD_02, CARD_04, or CARD_24.

## Provider-Neutral Expected Semantics

`qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json` contains 29 frozen provider-neutral expected-semantic records.

Each record contains:

- fixture ID;
- card identity;
- relevant face;
- exact player count;
- initial semantic state;
- required decisions;
- legal-result constraints;
- expected events;
- expected terminal/postcondition;
- relevant CR references;
- direct official Gatherer source URLs;
- retrieval timestamps;
- raw response SHA-256 where acquired;
- authority classification;
- explicit runtime independence.

Scope is exactly **4 players** for all 29 actual-card fixtures, matching the frozen actual-card qualification denominator.

No Forge or XMage internal representation is encoded.

## Forge Authority Delta

Pre-WS-29 Forge state from WS-25:

- CARD_02 runtime PASS;
- 28 other actual-card fixtures authority-blocked / not authoritatively adjudicable.

Post-WS-29 authority state:

- CARD_02 runtime PASS remains unchanged;
- the other **28/28** cards are now authority-ready for runtime adjudication;
- remaining Forge card-authority blockers: **0**.

This is an authority-only delta. No additional Forge card received runtime PASS in WS-29.

## XMage Authority Delta

Pre-WS-29 XMage runtime PASS claims retained for:

- CARD_02;
- CARD_04;
- CARD_24.

WS-29 confirms that the authority component of those precise tested postconditions is supported.

The other 26 cards now possess current authority but remain in their prior XMage runtime state unless separately executed and proven.

Authority closure does not convert them into XMage runtime PASS.

## Tests / Evidence

Fail-closed test:

- `tests/qualification/test_ws29_authority_manifests.py`

It hard-gates:

- exact SHA-256 of all four frozen WS-29 manifests;
- exact 29-card denominator and identities;
- `FULL_CURRENT_ORACLE_LOCK` for every card;
- direct official Gatherer URL requirements;
- per-face HTTP 200 and response hashes;
- currentness closure;
- exactly 4P fixture scope;
- provider-neutral expected-semantic completeness;
- cross-manifest identity equality;
- CR PDF byte lock and TXT `UNKNOWN` preservation;
- zero card-authority blockers;
- Forge authority delta without runtime promotion;
- XMage authority reconciliation without runtime promotion.

Final CI workflow:

- `.github/workflows/ws29-final-authority-closure.yml`

It additionally fails closed if WS-29 modifies repository paths outside the explicitly authorized provider-neutral WS-29 surface.

The exact final closure commit/tree, test result, manifest hashes, Handoff SHA-256, run ID, and CI evidence SHA-256 are materialized by CI. The final artifact ID and artifact digest are recorded in Draft PR #142 after the exact-head run, avoiding self-referential mutation of this final commit.

## Exact Stable Hashes

Frozen committed manifest SHA-256 values:

- `qualification/ws29/CARD_AUTHORITY_LEDGER.json`
  - `a810c9262597db5a1162c6fd8240bd154938e98efe58b0e0cddb29541344e3c4`
- `qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json`
  - `bde2177e91fe9ed0e0399e1637d3b47226c402bfe2c0350cf6bccf87f19c5201`
- `qualification/ws29/WS29_SOURCE_LOCK.json`
  - `c4306b9bdd16b81100a13e0ff49691bbe43418ac54f4d666a223c52c32bbc910`
- `qualification/ws29/UNRESOLVED_AUTHORITY_REGISTER.json`
  - `6765db1613c5f30e27c84998f39fafb30db3645c0cc5fc8e896f5cc20d0e89d9`

Current official CR PDF SHA-256:

- `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`

Frozen Gatherer 29-card acquisition manifest SHA-256:

- `f75e1c322a15d94fb89f1409cd42ea9e2095cc25810d845bcf8518d4d5634b10`

Prior network-evidence artifact ZIP SHA-256:

- `a5115a2e206317ff7eef049f1591aca8342638c032e45f159f6b73e18a0601ed`

## PASS / FAIL / UNKNOWN

WS-29 overall: **PASS / CLOSED**

Gate results represented by this handoff and enforced by final CI:

- fresh canonical main Source Lock: **PASS**
- current Wizards Rules-page lock: **PASS**
- official CR raw acquisition: **PASS via PDF**
- current CR PDF SHA-256: **PASS**
- official TXT raw acquisition: **UNKNOWN, HTTP 404**
- Gatherer direct access from GitHub Actions: **PASS**
- 29-card terminal authority classification: **PASS, 29/29 FULL_CURRENT_ORACLE_LOCK**
- direct official source for every authority PASS: **PASS**
- currentness closure for 29-card corpus: **PASS**
- provider-neutral expected semantics: **PASS, 29/29**
- CARD_02/04/24 authority reconciliation: **PASS**
- Forge authority-blocker delta: **PASS, 28 newly authority-ready / 0 still authority-blocked**
- XMage authority reconciliation: **PASS**
- candidate runtime non-promotion rule: **PASS**
- frozen-manifest fail-closed validation: **PASS required by exact-head final CI**
- provider-neutral diff boundary: **PASS required by exact-head final CI**
- WS-27 input: **INPUT_UNAVAILABLE**, explicitly preserved

`UNKNOWN` for the TXT byte path does not make the CR raw-byte gate UNKNOWN because the official current PDF was byte-exactly acquired, identified, measured, and SHA-256 locked.

## Remaining Authority Blockers

Frozen 29-card corpus:

- **none**.

Non-card unresolved provenance items preserved explicitly:

1. `CR_TXT_RAW_BYTES = UNKNOWN`
   - reason: direct Actions GET returned HTTP 404;
   - no browser-derived byte hash was fabricated;
   - CR raw-byte gate remains PASS via official PDF.
2. `WS27_INPUT = INPUT_UNAVAILABLE`
   - reason: requested input was not supplied/found;
   - it was not silently marked satisfied;
   - direct current-Wizards requalification independently closed the 29-card authority scope.

These are recorded in `qualification/ws29/UNRESOLVED_AUTHORITY_REGISTER.json` and do not leave any frozen card authority-blocked.

## Outputs

Committed provider-neutral outputs:

- `qualification/ws29/CARD_AUTHORITY_LEDGER.json`
- `qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json`
- `qualification/ws29/WS29_SOURCE_LOCK.json`
- `qualification/ws29/UNRESOLVED_AUTHORITY_REGISTER.json`
- `tests/qualification/test_ws29_authority_manifests.py`
- `scripts/ws29_fetch_wizards_authority.py`
- `scripts/ws29_fetch_gatherer_corpus.py`
- `scripts/ws29_materialize_static.py`
- `.github/workflows/ws29-wizards-authority.yml`
- `.github/workflows/ws29-materialize-static.yml`
- `.github/workflows/ws29-final-authority-closure.yml`
- `qualification/WS29_FINAL_HANDOFF.md`

Raw copyrighted CR/Gatherer documents are not committed as proof material.

## Draft PR

Draft PR:

- **#142 — WS-29: canonical CR + 29-card authority closure**
- `https://github.com/moeendres-png/commander-playtest-lab/pull/142`
- base: `main`
- head: `ws29/canonical-authority-closure`
- state: Draft

The PR body is the post-commit location for the exact final closure commit/tree, CI run/job, final validation artifact ID, artifact digest, and final validation-file SHA-256. Recording those values there does not mutate the already-tested branch head.

## Dependencies Unblocked

WS-29 removes the shared canonical card-authority asymmetry before final Forge/XMage Architecture Freeze comparison.

Unblocked:

- Forge can now execute/adjudicate the 28 previously authority-blocked actual-card fixtures against direct current Wizards authority.
- XMage CARD_02/CARD_04/CARD_24 runtime evidence has an independently reverified current authority component.
- Both providers can be compared against the same 29-card authority denominator without weakening Source Truth.
- Provider-neutral expected semantic postconditions are available for all 29 frozen fixtures.

Not unblocked by WS-29 alone:

- runtime PASS for unexecuted cards;
- provider selection;
- final Architecture Freeze;
- any denominator change.

## Exact Next Action

Run and require `WS-29 Final Authority Closure` on the exact commit containing this handoff. After it is green, append the immutable final commit/tree, CI run/job IDs, final CI evidence SHA-256, artifact ID, and artifact digest to Draft PR #142 **without changing the branch head**.

Then hand WS-29 to the Coordinator as **PASS / CLOSED** and proceed to the next Forge/XMage runtime/Architecture-Freeze comparison workstream. Do not select the final Rules Core inside WS-29.
