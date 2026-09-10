# Legal Review Questionnaire for Counsel

Date (UTC): 2026-09-10 · Workstream: `research/legal-topology-review-pack-20260910`
Companion facts: `docs/research/LEGAL_TOPOLOGY_REVIEW_PACK_2026-09-10.md` ·
machine ledger: `research/legal-topology-review/license-evidence-index.json`

```text
LEGAL_CLEARANCE = NONE
ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
```

How to use this document: each question states the **observed facts** (with
source locks), the **precise question**, and the **architectural decision it
gates**. Nothing here presupposes the answer. "Distribute/convey" below means
any transfer of built artifacts, container images, or data payloads beyond the
developers' own machines (including production hosts, registries, and any
future publication).

---

## A. Code-license questions

### Q1 — Forge GPL grant scope and the T1/T2 postures

Facts: root `LICENSE` of `moeendres-png/forge @ 66caae16` is the GPL-3.0 text
(SOURCE_VERIFIED, fetched 2026-09-10). In-repo SPDX header
(`qualification/providers/forge/gpl/Ws23ForgeBootstrap.java` @ WS48 `10a7f8f6`)
says `GPL-3.0-or-later`; D3 report records "GPL-3.0-or-later". Per-file grant
scope ("only" vs "or later") was not audited file-by-file. Docker builds clone
`Card-Forge/forge @ 852066bf` (tag `forge-2.0.13`); license file not read at
that pin.
Question: on what terms, if any, may the project (a) ship a combined
proprietary+Forge JVM artifact (T1), and (b) ship a separately built Forge
provider JVM and container images containing a Maven-built Forge tree plus
`forge-gui/res` data (T2)? Does the answer differ between the fork pin
`66caae16` and the image pin `852066bf`?
Gates: T1 (currently BLOCKED pending review) and T2 (leading-hypothesis shape).

### Q2 — Manabrew posture and missing pin

Facts: Manabrew (`github.com/witchesofthehill/manabrew`) is REPORT_CITED as
AGPL-3.0-or-later own code with a vendored `forge/` tree staying
GPL-3.0-or-later; no Manabrew commit is pinned in any project evidence; nothing
from Manabrew is in the main tree; D3 verdict is embedded-`NOT_USABLE`,
docs-`REFERENCE_ONLY`.
Question: what must be pinned and reviewed (exact commit, `LICENSE.md`,
`Cargo.toml` workspace, vendored-tree provenance, `THIRD-PARTY-NOTICES.md`)
before even reference-only reliance continues, and what would have to change
(relicense or otherwise) for any posture beyond reference-only?
Gates: T7 (BLOCKED) and continued T8.

### Q3 — Forge card scripts as a data layer

Facts: 33,666 GPL-licensed (REPORT_CITED) card-script `*.txt` under
`forge-gui/res/cardsfolder` at `Card-Forge/forge @ 8c7e9af`; shipped inside any
Forge docker image; read corpus-style (`git show`, provenance-tagged) by D3;
required at runtime by the WS48 bootstrap (`cardsfolder`, `tokenscripts`,
`editions`, `blockdata`, `lists/TypeLists.txt`).
Question: what are the storage, runtime-parsing, and redistribution terms for
this script corpus in each posture (bundled in image vs. fetched at deploy
time vs. read-only qualification corpus vs. shapes observed for clean-room
scaffolding)?
Gates: T2 payload, T3 corpus practice, D3-lineage tooling.

### Q4 — phase.rs dual license and NOTICE

Facts: `phase-rs/phase @ a0f9c55` carries `LICENSE-MIT` + `LICENSE-APACHE`,
`NOTICE` (307 bytes, contents not read), `DMCA.md`; workspace declares
`MIT OR Apache-2.0` (SOURCE_VERIFIED). Posture is reference-only; D4 blocks
any core use on non-license grounds anyway.
Question: for a future (currently unauthorized) permissive-licensed reuse —
including patterns-as-ideas that grow into code — what attribution/NOTICE
obligations attach, and does the `DMCA.md` posture impose any handling
requirement on reference materials?
Gates: T9 (any future activation is a new trigger regardless).

### Q5 — XMage beyond the root LICENSE

Facts: root `LICENSE.txt` at `moeendres-png/mage @ 0c1f455e` is MIT © 2010
betasteward@gmail.com (SOURCE_VERIFIED). Not audited: per-module uniformity at
the pin; the prebuilt `org.mage:{mage,mage-deck-constructed,
mage-game-commanderfreeforall}:1.4.61` Maven artifacts the bridge compiles
against; mage build's transitive dependencies; card-data payloads the mage
build bundles or fetches; the `magefree/mage @ 06d166b0` image pin (never
license-read).
Question: what packaging, transitive-dependency, and data-payload review is
required before distributing the bridge JVM and container images (T4/T5), and
what attribution chain must shipped scenario/test files derived from the mage
corpus carry (T6, cf. D2's per-record provenance rule)?
Gates: T4/T5/T6.

### Q6 — Bridge third-party libraries (gson, JUnit)

Facts: `engine-bridge/pom.xml` (main) declares `com.google.code.gson:gson:2.13.2`
(compile) and `org.junit.jupiter:5.8.1` (test). Licenses inferred from artifact
names only — UNKNOWN.
Question: confirm the distribution-relevant terms of these (and any transitive)
bridge dependencies for image publication.
Gates: T4/T5.

### Q7 — Container/image distribution mechanics

Facts: `docker/forge/Dockerfile` and `docker/xmage/Dockerfile` clone upstream
at pinned commits and Maven-build inside the image; `docker-compose.engine.yml`
bind-mounts the workspace and exposes loopback ports; `integrations/forge/README.md`
asserts a separate-process posture (in-repo claim, not clearance).
Question: which distribution acts (image build, registry push, production-host
deployment, bind-mounted volumes containing GPL-side logs/traces) constitute
conveyance of GPL-family components, and what source/notice mechanics must
accompany each?
Gates: T2/T5 image publication and deployment.

### Q8 — Clean-room, donor, and differential practices

Facts: D3 built `d3q6-cleanroom-0.1.0` from the public wiki + observed corpus
shapes (byte-span parsing, minimal wiki-curated tables, `behavior_pass=false`,
no source copied); D2 re-derives all assertions and mandates per-record
provenance blocks; Manabrew parity *concept* followed at the architectural
level only; WS47/WS48/WS49 traces are schema-validated, never imported as truth.
Question: are these controls adequate to keep donor/differential learnings
(T3/T6) and clean-room scaffolding (D3 lineage) outside derivative-work
exposure, and what additional controls (quarantine, author segregation,
provenance retention period) do you require going forward?
Gates: T3/T6/T8, D3-lineage tooling, reverser R3 fallback.

---

## B. Data / content / IP questions (independent of code licenses)

### Q9 — Oracle-text storage and Scryfall derivation

Facts: `data/cards/*.json` store Oracle text, mana costs, type lines, legality
with `source_name: Scryfall` + `?utm_source=api` URLs; README calls it a "local
project dataset"; `project_inferred` rows are flagged for replacement by a
"version-pinned Oracle snapshot". No Scryfall terms document is in the repo.
Question: under what terms may Oracle text be stored, enriched, version-pinned,
and distributed (including inside published images/datasets), and what
attribution or API-terms compliance steps are required?
Gates: T10; any future Oracle snapshot ingestion or dataset publication.

### Q10 — EDHREC-derived deck data

Facts: `artifacts/meta_knowledge_base/*` embed EDHREC average-deck sources and
edhrec.com URLs. EDHREC terms/scraping policy not reviewed.
Question: what are the storage, analysis-use, and republication terms for this
aggregator-derived data?
Gates: T10; matchup-analysis features built on these sources.

### Q11 — Wizards of the Coast content and marks

Facts: `data/opponents/*.json` cite official WotC Commander decklists;
`qualification/manifests/AUTHORITY_LOCK_v1.json` names WotC/Gatherer as rules
authority; Oracle text and card names are stored as facts; "Magic: The
Gathering", "Commander", mana symbols, and card-face trade dress are WotC marks
or potentially protected expression.
Question: what copyright, trademark, and Fan-Content-Policy (or equivalent)
constraints apply to storing decklists/Oracle text, running simulations over
real Commander decks, naming WotC properties in the product, and any future
display of card text, symbols, or art?
Gates: T10; product naming; any UI/display work.

### Q12 — Card art and asset red line

Facts: no card images, art, or symbol assets are stored in the repo
(SOURCE_VERIFIED); XMage/Forge builds may fetch/cache their own.
Question: confirm the red line — no art/asset ingestion, reproduction, or
caching in our tree, images, or evidence artifacts without a fresh review —
and advise what our builds must exclude or disable to hold it.
Gates: T10; build hardening for T2/T5 images.

### Q13 — Takedown posture and data provenance going forward

Facts: the phase.rs pin ships a `DMCA.md`; our own notice-and-takedown
handling, data-provenance retention policy, and contributor content warranties
are undefined in this pack.
Question: what standing posture (contact point, takedown handling, provenance
retention, contributor terms) should the project adopt before publishing
images, datasets, or qualification evidence derived from third-party game
content?
Gates: any publication act (images, datasets, evidence, paper, demo).

---

## C. Decision consequences (for counsel's awareness, not instruction)

- If T1/T2 postures are narrowed or ruled out, the recorded fallback is T3
  (Forge donor/differential-only) with XMage-first becoming primary on topology
  burden (D1–D7 reverser R3) — a behavior-program consequence, offered so
  counsel understands the stakes, not as a request to prefer any answer.
- No engineering team will treat counsel's factual answers as clearance to
  select a provider or freeze architecture; provider selection and Architecture
  Freeze remain separate, explicitly unclaimed decisions.

Materials attached for review: the Review Pack (§§1–5, 8) and
`research/legal-topology-review/license-evidence-index.json`. Primary sources
to inspect firsthand: `LICENSE` @ `moeendres-png/forge@66caae16`;
`LICENSE.txt` @ `moeendres-png/mage@0c1f455e`; `Cargo.toml`/`LICENSE-MIT`/
`LICENSE-APACHE`/`NOTICE` @ `phase-rs/phase@a0f9c55`; Manabrew `LICENSE.md` +
workspace `Cargo.toml` at a to-be-pinned commit (Q2); Scryfall/EDHREC terms;
WotC Fan Content Policy and Gatherer terms.

```text
LEGAL_CLEARANCE = NONE
ARCHITECTURE_FREEZE = NOT CLAIMED
PRODUCTION_PROVIDER = NOT SELECTED
```
