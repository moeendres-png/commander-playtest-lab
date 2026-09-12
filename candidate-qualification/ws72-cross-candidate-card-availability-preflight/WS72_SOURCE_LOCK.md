# WS72 Source Lock — Cross-Candidate Actual-Card Availability Preflight

Workstream: `WS72-CROSS-CANDIDATE-CARD-AVAILABILITY-PREFLIGHT`
Branch: `ws72/cross-candidate-card-availability-preflight-20260912`
Role: SOLE WRITER for `candidate-qualification/ws72-cross-candidate-card-availability-preflight/`

## CPL base (audit base, immutable input)

- Base ref: `ws65/forge-rqc3-first-wave-20260911`
- Base SHA: `7796619e69b0434cd232de8335ff5cab3c5d08e5`
- Remote slug: `moeendres-png/commander-playtest-lab`

## RQ-C3 authority (exact pin, read-only)

- Commit: `897d72f0b57bb8febe045870acaa3d2dba4bde56`
- Local ref: `research/rules-authority-closure-rq-c3-20260910`
  ("RQ-C3: checkpoint state head to closure-complete (46a3a18f)")
- Corpus surface: `research/candidate-qualification/common/rq-c1/scenarios/`
  (40 scenario families A01–K02) + `research/candidate-qualification/common/rq-c3/scenarios/`
  (18 corrected overlays) + `RQ_C3_CORRECTED_SCENARIO_MANIFEST.json`
  (overlay map + first-wave flags).
- Population finding (mechanical): authority enumerates exactly **40 unique
  scenarios**. No authority artifact enumerates 107 scenarios or the
  "remaining 92". Slots beyond these 40 are `AUTHORITY_ABSENT` → `UNKNOWN`;
  they are not invented.

## Forge candidate (exact accepted pin, read-only)

- Commit: `a9a95db6662c2d28814390a9c0c2f986e39aa8b4`
- Tree: `2c18327f79e330f2ed167067166ffd42d61b0849` (verified `show -s --format=%T`)
- Remote: `https://github.com/moeendres-png/forge.git` (verified `config --get remote.origin.url`)
- Corroboration: WS65 source lock records identical pin/tree/repository
  (`moeendres-png/forge`).
- Resolved local repository: existing checkout at `/home/moeen/code/forge`
  (object + tree verified; remote identity verified). Operational resolution
  only — per-card evidence cites engine-relative paths + commit, never the
  local path as semantic evidence.
- Lookup surface: `forge-gui/res/cardsfolder/<letter>/<snake>.txt` with
  `Name:<exact printed name>` first line; registration surface loader
  `forge-core/src/main/java/forge/CardStorageReader.java`
  (`CardReader : ... cardsfolder ...` constructor, lines 68–89).
- Census: 34,613 `^Name:` lines under `forge-gui/res/cardsfolder/` at pin.

## XMage candidate (exact accepted successor pin, read-only)

- Commit: `7135d5e85ddb4c8aa4b49b4192ca51947c822704`
- Tree: `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` (verified `show -s --format=%T`)
- Remote: `https://github.com/moeendres-png/mage.git` (verified `config --get remote.origin.url`)
- Corroboration: WS56 final report records identical successor pin/tree
  (WS54-delta successor, `114-file WS54 delta`).
- Resolved local repository: existing checkout at
  `/home/moeen/code/ws54-xmage-rng-reexecution-remediation-engine`
  (object + tree verified; remote identity verified). Operational resolution
  only — per-card evidence cites engine-relative paths + commit.
- Lookup surface: `Mage.Sets/src/mage/cards/<pkg>/<Class>.java` impl
  (+ `Mage/src/main/java/mage/cards/basiclands/` for basic lands) referenced by
  `SetCardInfo("<name>", ..., mage.cards.<pkg>.<Class>.class)` lines in
  `Mage.Sets/src/mage/sets/*.java`; registration mechanism
  `Mage/src/main/java/mage/cards/repository/CardScanner.java::scan()`
  (iterates `Sets.getInstance()` → `getSetCardInfo()` →
  `CardImpl.createCard(setInfo.getCardClass(), ...)`).

## Read-only operations used (no checkout/reset/switch/fetch/gc anywhere)

- `git show <pin>:<path>`, `git ls-tree <pin> -- <path>`,
  `git grep -F --name-only -e <pattern> <pin> -- <paths>`,
  `git show -s --format=%H|%T`, `git config --get remote.origin.url`,
  `git status --short`, `git rev-parse HEAD`, `git log`, `git for-each-ref`.
- Engine working trees verified clean (`git status --short` empty) after the run.
- No new worktree, clone, or engine checkout was created.

## Ownership

- Written ONLY under `candidate-qualification/ws72-cross-candidate-card-availability-preflight/`.
- No Forge, XMage, engine-bridge, provider, `tools/foundry`, or other-workstream
  file was modified.

## Invariants

`BEHAVIOR_CREDIT=0/107`. `FULL107=NOT_RUN`. `ARCHITECTURE_FREEZE=NOT_CLAIMED`.
`PRODUCTION_PROVIDER=NOT_SELECTED`. All presence results at most
`CODE_DERIVED`. Never `RUNTIME_VERIFIED`. Construction/presence is not behavior.
