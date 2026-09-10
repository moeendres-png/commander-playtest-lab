# Legal Topology Review Pack — Commander Simulator Next

Date (UTC): 2026-09-10 · Execution: OpenCode Go + `opencode-go/muse-spark-1.3-contributor` · Effort: HIGH
Workstream: `research/legal-topology-review-pack-20260910` (research/documentation only)

**This document provides no legal clearance and no legal advice.** It assembles
source-locked facts, text topology diagrams, license provenance, dependency
boundaries, unresolved questions, and decision consequences for HUMAN legal review.

```text
LEGAL_CLEARANCE = NONE
ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
```

Claim classifications used below: `SOURCE_VERIFIED` (firsthand-verified in this
workstream on 2026-09-10) · `REPORT_CITED` (taken from a named prior report or
branch, verified to exist but not re-verified at the object level here) ·
`UNKNOWN` (not established) · `HUMAN_LEGAL_REVIEW_REQUIRED` (needs counsel).

Rule for readers: no statement in this pack beginning "the license requires /
permits / obliges" is made. License *texts observed* are quoted or cited by
path; what they *oblige* is a question for counsel (see companion
`docs/research/LEGAL_REVIEW_QUESTIONS_2026-09-10.md`).

---

## 1. Source lock (freshly verified 2026-09-10, this worktree)

| Item | Lock | Verification |
|---|---|---|
| Repository | `moeendres-png/commander-playtest-lab`, origin `https://github.com/moeendres-png/commander-playtest-lab.git` | SOURCE_VERIFIED (`git remote -v`) |
| This branch / worktree | `research/legal-topology-review-pack-20260910` @ `/home/moeen/code/legal-topology-review-pack-20260910`, worktree clean | SOURCE_VERIFIED (`git status --short` empty) |
| Canonical main | `c162871ba416c338d37f83a44fbd5b054e79ca0e` (HEAD == origin/main) | SOURCE_VERIFIED |
| D1–D7 reconciliation | `research/d1-d7-final-architecture-reconciliation-20260910` @ `6e6ac21f268fd32ecb04872f0c80a020695f01b7` | SOURCE_VERIFIED (matches assignment expectation) |
| WS48 Forge qualification | `ws48/forge-v1.0.5-successor-qualification` @ `10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d` | SOURCE_VERIFIED (matches expectation) |
| WS49 XMage remediation | `ws49/xmage-v1.0.5-native-remediation` @ `1cd1276524cf60dcb2e5f84276b57dc45a5c8bd5` | SOURCE_VERIFIED (matches expectation) |
| D2 XMage corpus probe | `research/xmage-corpus-reuse-20260910` @ `bf2c4711ff184cd3489f5f77f36cf6e709a2631b` | SOURCE_VERIFIED (present in this clone) |
| D3 Q6 import probe | `moeendres-png/mage` `research/d3-q6-import-automation-20260910` @ `a766f9006c006feed9b05e336f4ba2d07cdb8ea9` | SOURCE_VERIFIED (ref exists via ls-remote; report fetched raw at pin) |
| Forge engine pin (D1/WS48) | `moeendres-png/forge` @ `66caae16015bd403bc0a52fa6689afb5508f74d0` | REPORT_CITED (objects absent from this clone; cross-agreed D1/WS48 per D1–D7 ledger) |
| XMage engine pin (D2/WS49) | `moeendres-png/mage` @ `0c1f455ea8c8fa48ab9d638ad5068ec242800428` | REPORT_CITED (objects absent; D2 claims DIRECTLY_VERIFIED read at pin) |
| Forge corpus pin (D3) | `Card-Forge/forge` @ `8c7e9afb8e6caee88644b94e25da5852e36f8928` | REPORT_CITED (D3 report) |
| phase.rs pin (D4) | `phase-rs/phase` @ `a0f9c55d7aef13e4875ac8137c016948e5f66e12` | REPORT_CITED for behavior; SOURCE_VERIFIED for license-file presence (see §3.5) |
| Manabrew | `github.com/witchesofthehill/manabrew`, **no pinned commit in any project evidence** | REPORT_CITED (D3 report; identity corroborated by public web search, not by counsel) |

Own-code license stance: `pyproject.toml` (`[project] license`) declares
`LicenseRef-Proprietary` at main HEAD — SOURCE_VERIFIED. The main tree contains
no root `LICENSE*` file (SOURCE_VERIFIED by glob).

---

## 2. What exists where today (distribution-relevant inventory)

### 2.1 Production main tree (`c162871b`) — no engine source bundled

- `docs/phase8-rules-engine-integration.md:7` states: "The repository does not
  bundle either upstream engine." — SOURCE_VERIFIED (file read at HEAD).
- `vendor/` contains only `README.md` (offline-input drop point; nothing
  vendored) — SOURCE_VERIFIED.
- `src/commander_lab/engine/rules/bridge.py` — `JsonLineBridgeClient` spawns the
  engine side via `subprocess.Popen` (stdin/stdout/stderr pipes, JSONL
  request/response with `request_id` matching) using caller-supplied commands
  from `COMMANDER_LAB_FORGE_BRIDGE_CMD` / `COMMANDER_LAB_XMAGE_BRIDGE_CMD`.
  `full_game.py` repeats the pattern (`COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD`,
  requires an explicit full-game subcommand). — SOURCE_VERIFIED.
- `engine-bridge/pom.xml` (main) compiles `org.commanderlab:xmage-engine-bridge`
  against Maven artifacts `org.mage:mage`, `org.mage:mage-deck-constructed`,
  `org.mage:mage-game-commanderfreeforall`, all version `1.4.61`, plus
  `com.google.code.gson:gson:2.13.2` and test-scoped JUnit — SOURCE_VERIFIED.
  Build-time link against XMage artifacts is therefore structurally present in
  the bridge module; runtime contact is a separate JVM process over JSONL stdio.
  Whether Maven Central hosts `org.mage:1.4.61` and under what distribution
  terms is UNKNOWN (pom declares the coordinates only).
- `docker/forge/Dockerfile` (main) clones `https://github.com/Card-Forge/forge.git`
  and checks out detached `ENGINE_COMMIT=852066bf4f761b302ed17cb011999d8a8fe08ad6`,
  then Maven-builds it inside the image — SOURCE_VERIFIED.
- `docker/xmage/Dockerfile` (main) clones `https://github.com/magefree/mage.git`
  at `ENGINE_COMMIT=06d166b098ad36b277edef01116472203d5a047e` (matches the frozen
  P3A XMage pin recorded in `docs/J_P3_XMAGE_SPIKE_REPORT.md:35-36`) —
  SOURCE_VERIFIED.
- `integrations/forge/README.md` (main) records pinned upstream
  `forge-2.0.13` / `852066bf4f761b302ed17cb011999d8a8fe08ad6` and states Forge
  "remains a separate-process GPL-3.0 differential backend" and that the
  directory "contains no claimed Forge runtime" — SOURCE_VERIFIED as an in-repo
  claim (the GPL-3.0 label here is an in-repo assertion, not an upstream
  license-file read; the upstream file read is §3.1).
- `docker-compose.engine.yml` defines `xmage` and `forge` services as
  separately built images (`ENGINE_MODE: external`, protocol `1.0.0`) with the
  workspace bind-mounted — SOURCE_VERIFIED.
- `candidate-qualification/` does **not** exist on main (SOURCE_VERIFIED); it
  exists only on the WS48 branch (see §2.2).
- Current main contains **zero** references to Manabrew or phase.rs
  (SOURCE_VERIFIED by case-insensitive grep over docs/data/src/scripts).

### 2.2 WS48 branch (`10a7f8f6`) — GPL-segregated qualification harness code

- `qualification/providers/forge/gpl/` contains `Ws23ForgeAuthority.java`,
  `Ws23ForgeBootstrap.java`, `Ws23ForgeGateD.java`, `Ws40SuccessorState.java`,
  `Ws45StrictObservation.java` — SOURCE_VERIFIED (branch tree listing).
- `Ws23ForgeBootstrap.java` head (SOURCE_VERIFIED via `git show` at the pin):
  `// SPDX-License-Identifier: GPL-3.0-or-later`, `package forge.game.player;`,
  imports `forge.CardStorageReader`, `forge.StaticData`, `forge.card.CardType`,
  `forge.util.*`; class doc: "GPL-side headless bootstrap. This class is
  compiled only into the separate Forge provider JVM."
- Factual topology consequence (no legal conclusion drawn): project-authored
  Forge-touching harness code is (a) labeled GPL-3.0-or-later at the file level,
  (b) placed in the JVM package namespace `forge.*`, (c) compiled against Forge
  classes, and (d) documented as confined to a separate provider JVM. This is
  the repository's own segregation practice for GPL-side code; whether it is
  sufficient for any particular distribution posture is HUMAN_LEGAL_REVIEW_REQUIRED.
- R1e drive path references Forge `66caae16` classes (`StaticData.java:66-68`,
  `FModel.initialize` tokenReader path, 839 tokenscripts) — REPORT_CITED (R1e
  commit message).

### 2.3 WS49 branch (`1cd12765`) — XMage bridge player compiled against mage

- Head commit modifies `engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java`
  (+61/−lines) alongside runner/test changes — SOURCE_VERIFIED (branch stat).
  The bridge player is compiled against mage classes into the separate bridge
  JVM (same build-link / separate-process-runtime shape as §2.1).

---

## 3. License provenance per component (exact paths)

### 3.1 Forge — GPL-3.0 text observed at the D1/WS48 pin

- Path: `moeendres-png/forge` @ `66caae16`, root file `LICENSE` — fetched raw
  2026-09-10 — SOURCE_VERIFIED. Content is the full GNU General Public License
  version 3 text (Preamble + Terms §§0–17 + How-to-Apply appendix).
- GitHub repository metadata at that commit page displays "License: GPL-3.0"
  and "forked from Card-Forge/forge" — SOURCE_VERIFIED (page fetch).
- Qualifier note: the D3 report records the Forge repo license as
  "GPL-3.0-or-later (repo `LICENSE`)" (REPORT_CITED); the WS48-authored
  `Ws23ForgeBootstrap.java` SPDX header says `GPL-3.0-or-later`
  (SOURCE_VERIFIED on WS48). The fetched `LICENSE` file is the GPL-3.0 text,
  which contains the standard "or any later version" application mechanism;
  which grant ("only" vs "or later") covers which Forge source files was **not**
  established file-by-file here — HUMAN_LEGAL_REVIEW_REQUIRED (Question Q1).
- Per-file header audit at the pin: NOT performed — UNKNOWN.

### 3.2 XMage — MIT text observed at the D2/WS49 pin

- Path: `moeendres-png/mage` @ `0c1f455e`, root file `LICENSE.txt` — fetched raw
  2026-09-10 — SOURCE_VERIFIED. Content is the MIT License,
  `Copyright (c) 2010 betasteward@gmail.com`, with the standard include-the-notice
  condition. This matches the D2 report's DIRECTLY_VERIFIED license record
  (`D2_XMAGE_CORPUS_REUSE_REPORT.md` @ `bf2c4711`, verified present in this
  clone) — REPORT_CITED for D2's reading, now corroborated firsthand.
- D2 provenance rule (REPORT_CITED): every adapted draft carries
  repository/branch/commit/tree/source_path/source_method/license, and "any
  downstream importer must keep the per-record provenance block intact."
- Transitive-license surface of the XMage build (mage module POMs, bundled
  third-party jars, card-data payloads shipped by the mage build): NOT audited
  here — UNKNOWN (Question Q5). `engine-bridge` additionally links gson
  (Apache-2.0 presumed by artifact naming only — UNKNOWN, Question Q6).

### 3.3 Forge card scripts — GPL-licensed data payload with its own boundary

- Location at corpus pin: `forge-gui/res/cardsfolder`, 33,666 `*.txt` at
  `Card-Forge/forge` @ `8c7e9af` — REPORT_CITED (D3 report §3; population count
  and pin subject "Fix Nori, Teller of Tales (#11713)" 2026-08-27).
- License recorded by D3 as GPL-3.0-or-later (repo `LICENSE`) — REPORT_CITED.
- Why this is a separate row from §3.1: card scripts are *data consumed by* the
  engine (parsed at runtime, including by the D3 clean-room prototype from
  `git show` output, never cloned as a tree). Counsel must treat the
  code-vs-data posture separately: shipping a Forge build (docker image)
  carries `cardsfolder`/`tokenscripts`/`editions` payloads; the WS48 bootstrap
  explicitly requires `forge-gui/res/{cardsfolder,tokenscripts,editions,
  blockdata,lists/TypeLists.txt}` at runtime (SOURCE_VERIFIED, file head).
  Whether parsing GPL-licensed script data at runtime implicates the engine
  license, and whether clean-room reimplementations trained on observed script
  shapes raise derivative-work questions, is HUMAN_LEGAL_REVIEW_REQUIRED
  (Questions Q3, Q8).

### 3.4 Manabrew — AGPL-3.0-or-later own code over a GPL Forge derivative; no pin

- Upstream identity: `github.com/witchesofthehill/manabrew` — REPORT_CITED (D3
  report) with public-web corroboration (project README describes a Rust/Tauri
  client + Rust engine + Java Forge interop + parity harness; engine and card
  data described as derivative of Forge GPL-3.0-or-later; own code AGPL-3.0-or-later).
- License facts, all REPORT_CITED (D3 report §2, verified-2026-09-10 by its
  author; `LICENSE.md`/`Cargo.toml` texts not re-fetched here):
  workspace engine + `forge-carddb` + `forge-card-script` (current) + `parity` =
  AGPL-3.0-or-later; vendored `forge/` tree stays GPL-3.0-or-later;
  `forge-card-script` 0.1.1 (crates.io) = GPL-3.0-or-later;
  `tree-sitter-forge-card-script` = MIT (© 2026 khaliostr).
- D3 reuse verdicts (REPORT_CITED): Manabrew embedded reuse `NOT_USABLE`;
  Manabrew docs/patterns `REFERENCE_ONLY`; tree-sitter grammar
  `USE_EXTERNAL_ISOLATED_TOOL` (kept as subprocess); Forge wiki + Manabrew
  `PARITY_AND_IR.md` / `forge-dsl-semantics.md` docs `REFERENCE_ONLY`.
- Critical gap for counsel: **no Manabrew commit is pinned anywhere in project
  evidence** — the exact texts counsel would opine on are unidentified.
  UNKNOWN (Question Q2). The tree-sitter grammar likewise has no recorded pin —
  UNKNOWN.

### 3.5 phase.rs — dual-license files observed at the D4 pin; reference-only

- `phase-rs/phase` @ `a0f9c55` exists; root contains `LICENSE-MIT`,
  `LICENSE-APACHE`, `NOTICE` (307 bytes), `DMCA.md` — SOURCE_VERIFIED (GitHub
  API tree listing at the ref; blob SHAs recorded in fetch transcript).
- `Cargo.toml` `[workspace.package]`: `version = "0.78.0"`,
  `license = "MIT OR Apache-2.0"` — SOURCE_VERIFIED (raw fetch at pin).
- `LICENSE-MIT`/`LICENSE-APACHE` full texts and `NOTICE` contents: NOT read —
  UNKNOWN (counsel will want NOTICE attribution terms; Question Q4).
- Project posture: ARCHITECTURE_REFERENCE_ONLY per D4 (REPORT_CITED, D1–D7
  ledger); nothing from phase.rs is present in the main tree (§2.1);
  correctness UNKNOWN 14/14 (REPORT_CITED). The D4 source report itself is
  LOCAL_PRESERVED_REPORT, not REMOTE_VERIFIED (REPORT_CITED, D1–D7 erratum
  record). The main reconciliation report additionally flags a
  `fallback_action` pattern in phase.rs as a negative example for the
  no-fallback legality rule — REPORT_CITED (not a license fact; included so
  counsel does not mistake a Rules-architecture note for clearance).

### 3.6 Card data / Oracle / script / asset / trademark boundaries

Code-license facts above do **not** cover the following distinct layers
(each needs separate HUMAN legal review; see Questions Q9–Q13):

| Layer | What the repo holds (SOURCE_VERIFIED unless noted) | License/IP status |
|---|---|---|
| Local Oracle subset | `data/cards/oracle_subset.json`, `official_precon_oracle_cards.json` (956K total `data/cards/`); README: "local project dataset, not a complete MTG Oracle database"; `project_inferred` rows flagged for replacement by a "version-pinned Oracle snapshot" | Terms under which Oracle text may be stored/redistributed: UNKNOWN |
| Scryfall-derived fields | Entries cite `source_name: Scryfall` + `source_path` card URLs with `?utm_source=api` (bulk + named-card lookups) | Scryfall API/data terms compliance: UNKNOWN; no terms doc in repo |
| EDHREC-derived decks | `artifacts/meta_knowledge_base/*` embed EDHREC average-deck sources (`edhrec-rogsi-optimized-2026`, `-control-2026`, edhrec.com URLs) | EDHREC terms/scraping policy: UNKNOWN |
| WotC decklists | `data/opponents/*.json` cite "Wizards of the Coast — <deck> Commander decklist(s)" as `source_name` | Republication posture for WotC list content: UNKNOWN |
| Card images / art / symbols | None in repo (no `*.jpg/*.png/*.jpeg/*.webp` under `data/`) | No current exposure; any future asset ingestion is a new review trigger |
| Card names / Oracle text / IP | Oracle text, names, mechanics stored as facts; `qualification/manifests/AUTHORITY_LOCK_v1.json` names "Wizards of the Coast" / "Wizards Gatherer / official Oracle" as authority (and records a Gatherer-fetch failure, secondary sources not promoted) | WotC IP (copyright in card text? trademark in "Magic", "Commander", mana symbols? Fan Content Policy applicability?): UNKNOWN |
| Forge `cardsfolder` scripts | Not in main tree; pulled at docker-build time (§2.1) or read via `git show` (D3) | §3.3 |
| XMage card data payloads | Whatever the mage build at the pin downloads/bundles (e.g. card image/data caches) | UNKNOWN — never inventoried here |

---

## 4. Candidate production topologies (text diagrams + boundaries)

Legend: `[A] ==> [B]` = in-process call/link · `[A] --stdio/JSONL--> [B]` =
separate-OS-process boundary · `((net))` = network hop. "Distribute" below means
any conveyance of built artifacts or images to third parties or production hosts.

### T1 — Forge-centric embedded core (Java, same JVM)

```text
[proprietary core + Forge classes, one JVM] ==> engine answers
```

- What would be distributed: a combined JVM artifact containing Forge classes
  (and necessarily `forge-gui/res` data payloads per §2.2 bootstrap requirements).
- Current-state facts: nothing like this exists on main (§2.1); the only
  Forge-linking code in the project is GPL-marked harness code on WS48 (§2.2).
- Status: **REQUIRES HUMAN REVIEW before any implementation** — the D1–D7
  adjudication already records "embedding into a non-GPL core off the table"
  as *architecture input, not clearance* (REPORT_CITED). Counsel question: on
  what terms, if any, could a proprietary core ship a Forge-combined artifact
  (Q1, Q7)? No work in this direction is authorized by this pack.

### T2 — Forge separate-process / service boundary (leading-hypothesis shape)

```text
[proprietary core / pilots] --stdio JSONL (bridge protocol 1.0.0)--> [Forge provider JVM]
[proprietary core / pilots] --loopback TCP/runtime logs--> [engine container]
```

- What would be distributed: (a) proprietary core + JSONL bridge client
  (`bridge.py`/`full_game.py` shape, SOURCE_VERIFIED); (b) separately built
  Forge provider JVM (WS48 `qualification/providers/forge/gpl/*` lineage,
  GPL-marked, SOURCE_VERIFIED); (c) container images whose Dockerfiles clone
  and Maven-build `Card-Forge/forge @ 852066bf` (SOURCE_VERIFIED) — image
  contents therefore include the Forge build plus `forge-gui/res` data.
- Linking/process/data boundaries: no shared address space; contact is
  versioned JSONL over stdio plus log files (`*.bridge.stdout.jsonl`,
  `*.bridge.stderr.log`); engine started from env-configured commands.
  Hidden-info posture rides on principal-scoped observations per frame
  (WS49 R-h pattern for XMage; Forge-side observation gating is part of the
  unqualified discriminator per D1–D7 §5) — a Rules-correctness fact, included
  because observation content defines what data crosses the boundary.
- Status: **LEGAL_REVIEW_REQUIRED** (unchanged from D1–D7 input). Counsel
  questions: provider-JVM distribution terms; image-layer conveyance (Q1, Q7);
  whether protocol/observation schemas or pilot code shaped by engine behavior
  raise any derivative-work question (Q8); container/volume topology
  (bind-mounted workspace in compose file) implications (Q7).

### T3 — Forge donor / differential-only use

```text
[Forge JVM, local-only] --trace snapshots--> [schema-validated comparator] ==> [proprietary core learns NOTHING except pass/fail divergence reports]
```

- What would be distributed: proprietary core only; Forge never ships.
  Forge artifacts used: pinned source/data for local qualification runs
  (WS47 contract v1.0.5 denominator 107, REPORT_CITED), D2-style corpus reads,
  D3-style script-shape reads with per-row provenance.
- Status: **lowest license exposure of the Forge postures, STILL REQUIRES
  HUMAN REVIEW** (distribution of *learnings*: clean-room controls per D3 §9 —
  `behavior_pass=false`, ideas-only reuse, no source copied — are engineering
  hygiene, not a legal conclusion; Q8). Note D1–D7 reverser R3: if counsel
  rules out T1/T2 postures, Forge drops to this posture and XMage-first becomes
  primary on topology burden regardless of behavior momentum (REPORT_CITED).

### T4 — XMage embedded / wrapped core

```text
[proprietary core + engine-bridge + org.mage artifacts, JVM(s)] ==> engine answers
```

- What would be distributed: bridge JVM(s) containing `org.mage:1.4.61`
  classes; `engine-bridge` module as built (SOURCE_VERIFIED pom coordinates).
- MIT-license-class facts observed: root `LICENSE.txt` MIT at the source pin
  (§3.2). NOT established: per-module license uniformity across the mage tree
  at the pin; license of prebuilt `org.mage:1.4.61` Maven artifacts vs the
  source tree; transitive dependency licenses (gson, JUnit, mage's own deps);
  card-data payloads bundled/fetched by the mage build. All UNKNOWN (Q5, Q6).
- Status: **REQUIRES HUMAN REVIEW (packaging/transitive/data review)** — the
  "permissive-license class advantage" recorded in D1–D7 is a relative
  architecture input, explicitly "packaging/transitive/data/IP/trademark review
  still required", and is **not** clearance. Nothing in this pack calls XMage
  "legally cleared".

### T5 — XMage separate-process use (current implemented shape)

```text
[proprietary core] --stdio JSONL--> [xmage-engine-bridge JVM + org.mage:1.4.61] (docker/xmage image: magefree/mage @ 06d166b0, Maven-built)
```

- Same distribution set as T4, minus any in-process combination with the
  proprietary core; the bridge is already structured this way (§2.1, §2.3).
- Status: **REQUIRES HUMAN REVIEW** on the same open items as T4 (Q5, Q6) plus
  image-layer conveyance (Q7). The process boundary is an engineering fact that
  counsel may weigh; this pack assigns it no legal effect.

### T6 — XMage donor / differential-only use

```text
[mage @ pin, local-only] --test/corpus reads + trace snapshots--> [scenario scaffolding (D2: ~40-45% authoring assist) + differential reference; assertions re-derived, never imported]
```

- D2 guardrails (REPORT_CITED): no outcome copied as truth; per-record
  provenance blocks mandatory for downstream importers; `runCode`/
  `rollbackTurns` engine-internal hooks UNUSABLE (rewrite bucket boundary).
- Status: **REQUIRES HUMAN REVIEW**, lightest XMage posture; open item is
  mainly the provenance-attribution chain for MIT-noticed content reused in
  shipped test/scenario files (Q5) plus the clean-room/derivation questions
  shared with T3 (Q8).

### T7 — Manabrew embedded use (engine, forge-carddb, forge-card-script, parity)

```text
[proprietary core + manabrew crates] ==> engine answers   (NOTHING of this shape exists anywhere in the project)
```

- Status: **NOT CLEARED; embedded reuse recorded NOT_USABLE** (REPORT_CITED, D3
  verdict: AGPL network clause + GPL derivation). No pin, no prototype, no
  main-tree reference exists. Reactivation only on relicense or on counsel
  direction (counsel: Q2). This pack authorizes no contact beyond existing
  reference-only reads.

### T8 — Manabrew reference-only use (current and only posture)

```text
[public docs: PARITY_AND_IR.md, forge-dsl-semantics.md, wiki] --ideas only--> [clean-room prototype d3q6-cleanroom-0.1.0]
```

- Controls observed in D3 (REPORT_CITED): no Manabrew/Forge source cloned,
  vendored, linked, or reimplemented from source; token tables curated from
  public wiki + observed corpus; grammar idea followed, MIT grammar kept as
  subprocess even though embeddable.
- Status: **current posture; confirm with counsel that the documented
  clean-room controls are adequate going forward** (Q8). Any widening (e.g.
  vendoring `forge-card-script` from crates.io, currently GPL-3.0-or-later per
  D3) is a new review trigger.

### T9 — phase.rs reference-only / potential future use

```text
[today: nothing]      [future IF reactivated: permissive-licensed patterns (typed legal actions, actor-authenticated reducer, viewer projections, seeded RNG, replay journal) used as ideas]
```

- License facts at pin: MIT OR Apache-2.0 + NOTICE + DMCA.md present (§3.5).
- D4 blocks reactivation on non-license grounds anyway (14/14 correctness
  UNKNOWN, misparse backlog, LLM provenance, continuity risk; REPORT_CITED).
  Promotion criteria exist (D1–D7 main report §10 area) but no requalification
  is authorized here.
- Status: **reference-only; any future use is a new review trigger** (NOTICE
  attribution terms UNKNOWN, Q4; no license obstacle *asserted* — counsel
  confirms, Q4).

### T10 — Card data / Oracle / script / asset / trademark boundaries

- No engine topology changes what §3.6 lists: Oracle-text storage, Scryfall and
  EDHREC derivation chains, WotC decklist republication, card art (currently
  absent — keep it that way until reviewed), and WotC trademarks ("Magic: The
  Gathering", "Commander", mana-symbol iconography, card-face trade dress) each
  need independent HUMAN review (Q9–Q13). The `DMCA.md` at the phase.rs pin is
  a reminder that at least one candidate upstream operates under an explicit
  takedown posture; our own takedown/notice posture is UNKNOWN (Q13).

---

## 5. Dependencies whose licenses materially affect topology

| Dependency | Coordinates / pin | Role in topology | License fact | Class |
|---|---|---|---|---|
| Forge engine | `moeendres-png/forge @ 66caae16` (D1/WS48) | T1/T2/T3 engine | GPL-3.0 text in root `LICENSE` | SOURCE_VERIFIED (file text at pin) |
| Forge upstream build | `Card-Forge/forge @ 852066bf` (tag `forge-2.0.13`) | T2 docker image contents | Assumed same GPL family — NOT read at this pin | UNKNOWN (Q1) |
| Forge card scripts | `forge-gui/res/cardsfolder` @ `8c7e9af` (33,666 files) | T2 image payload; T3 read corpus | GPL-3.0-or-later per D3 | REPORT_CITED |
| XMage engine | `moeendres-png/mage @ 0c1f455e` | T4/T5/T6 engine | MIT (`LICENSE.txt`, © 2010 betasteward) | SOURCE_VERIFIED (file text at pin) |
| XMage Maven artifacts | `org.mage:{mage,mage-deck-constructed,mage-game-commanderfreeforall}:1.4.61` | T4/T5 bridge link | UNKNOWN (coordinates only) | UNKNOWN (Q5) |
| XMage upstream build | `magefree/mage @ 06d166b0` | T5 docker image | UNKNOWN (never license-read) | UNKNOWN (Q5) |
| Manabrew workspace | `witchesofthehill/manabrew`, unpinned | T7 (rejected) / T8 (current) | AGPL-3.0-or-later own code; vendored `forge/` GPL-3.0-or-later | REPORT_CITED (Q2) |
| forge-card-script crate | v0.1.1, crates.io | T8 boundary (do not vendor) | GPL-3.0-or-later | REPORT_CITED |
| tree-sitter grammar | unpinned, © 2026 khaliostr | T8 isolated-tool candidate | MIT | REPORT_CITED |
| phase.rs | `phase-rs/phase @ a0f9c55`, v0.78.0 | T9 (reference only) | MIT OR Apache-2.0 (+NOTICE, unread) | SOURCE_VERIFIED (presence + Cargo expression) |
| gson | `com.google.code.gson:gson:2.13.2` | T4/T5 bridge dep | UNKNOWN (name-inferred only) | UNKNOWN (Q6) |
| JUnit Jupiter | `org.junit.jupiter:5.8.1` (test scope) | bridge tests | UNKNOWN | UNKNOWN (Q6) |
| Scryfall data | API-derived Oracle/card fields in `data/` | T10 data layer | UNKNOWN | UNKNOWN (Q9) |
| EDHREC data | average-deck sources in `artifacts/meta_knowledge_base/` | T10 data layer | UNKNOWN | UNKNOWN (Q10) |
| WotC content | decklists (`data/opponents/`), Oracle text, marks | T10 data/IP layer | UNKNOWN | UNKNOWN (Q11–Q13) |

Out of scope for this pack (flagged, not analyzed): Python dependency tree
licenses (`artifacts/phase12_19/FALLBACK_LICENSE_REPORT.json` exists on main
but is an importlib-metadata fallback with `official_pip_licenses_execution:
blocked` and UNKNOWN entries — SOURCE_VERIFIED as read; it is a build-hygiene
artifact, not a topology input, and several entries are UNKNOWN); Optuna/Ray
(D5/D6, no migration authorized); Tauri/React (Manabrew-internal, not ours).

---

## 6. Decision table (architecture paths × review posture)

| # | Path | Posture for counsel | Rationale pointer |
|---|---|---|---|
| 1 | Forge-centric embedded core (T1) | **BLOCKED pending HUMAN review** — no implementation authorized | GPL-3.0 observed (§3.1); D1–D7 keeps embedding "off the table" as input, not clearance |
| 2 | Forge separate-process/service (T2) | **CONDITIONALLY VIABLE pending HUMAN review** — current leading-hypothesis shape, not selected | Segregated provider-JVM practice exists (§2.2); image conveyance + grant scope open (Q1, Q7) |
| 3 | Forge donor/differential-only (T3) | **VIABLE pending HUMAN review** — lightest Forge posture; fallback if R3 fires | No Forge distribution; clean-room controls need counsel confirmation (Q8) |
| 4 | XMage embedded/wrapped core (T4) | **CONDITIONALLY VIABLE pending HUMAN review** — permissive class does not equal clearance | MIT root verified (§3.2); transitive/data/packaging open (Q5, Q6) |
| 5 | XMage separate-process use (T5) | **CONDITIONALLY VIABLE pending HUMAN review** — current implemented shape, not selected | Same opens as T4 (Q5–Q7) |
| 6 | XMage donor/differential-only (T6) | **VIABLE pending HUMAN review** | D2 guardrails observed; attribution chain to confirm (Q5, Q8) |
| 7 | Manabrew embedded use (T7) | **BLOCKED — not cleared** (D3 `NOT_USABLE` stands) | AGPL-3.0-or-later + GPL derivation (REPORT_CITED); no pin exists |
| 8 | Manabrew reference-only (T8) | **Current posture — confirm controls with counsel** | D3 clean-room controls documented (Q8) |
| 9 | phase.rs reference/future (T9) | **Reference-only; future use is a new trigger** | MIT OR Apache-2.0 verified at pin; NOTICE unread (Q4); D4 non-license blocks stand |
| 10 | Card data / Oracle / script / asset / trademark (T10) | **BLOCKED — no clearance claimed; full HUMAN review required** | §3.6: every sub-layer UNKNOWN (Q9–Q13) |

Reading guide: "VIABLE" above means *no known license-class bar was observed in
this pack's evidence* — it is not, and must never be quoted as, legal clearance.
Every row except the pure-fact rows requires HUMAN_LEGAL_REVIEW_REQUIRED before
a distribution-affecting decision (provider selection, image publication,
vendoring, asset ingestion, or Architecture Freeze).

---

## 7. What this pack explicitly does not do

- No GPL/AGPL obligation analysis beyond naming the observed license texts.
- No derivative-work, linking, "aggregate", network-use, or fair-use conclusions.
- No Oracle-text/IP/trademark conclusions.
- No provider selection; no Architecture Freeze claim; no clearance language.
- No runtime-code modification (none made; `git status` clean except these docs).
- No WS50 (`qualification/providers/forge/*` untouched) or Task 2A paths touched.

---

## 8. Provenance of inherited claims (so counsel can weight them)

- D1–D7 reconciliation report + evidence-index.json + discriminator matrix +
  qualification roadmap @ `6e6ac21` (present in this clone; read via `git show`)
  — REPORT_CITED for all D-verdicts, pins, and the R1–R4 reverser set.
- D2 report @ `bf2c4711` (present in this clone) — REPORT_CITED for MIT read
  method and provenance rule; corroborated firsthand at the mage pin (§3.2).
- D3 report @ `a766f900` (mage remote; fetched raw at pin 2026-09-10) —
  REPORT_CITED for §2 license table, corpus facts, and clean-room controls.
- D4: LOCAL_PRESERVED_REPORT (`~/restart-preserve/...`, not REMOTE_VERIFIED) —
  REPORT_CITED; phase.rs license facts independently corroborated (§3.5).
- WS48 R1e commit message @ `10a7f8f6` — REPORT_CITED for native-path detail.
- Public web sources (Manabrew README, crates.io records, GitHub metadata) —
  corroboration only, never authority.
- No filename containing FINAL/LATEST/CURRENT was relied on for freshness; all
  pins are commit SHAs verified or cited as above.

---

## 9. Files delivered by this workstream

- `docs/research/LEGAL_TOPOLOGY_REVIEW_PACK_2026-09-10.md` (this file)
- `research/legal-topology-review/license-evidence-index.json` (machine-readable
  evidence ledger for §§1–5)
- `docs/research/LEGAL_REVIEW_QUESTIONS_2026-09-10.md` (counsel questionnaire)

```text
LEGAL_CLEARANCE = NONE
ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
```
