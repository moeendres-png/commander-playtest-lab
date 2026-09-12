# WS73 Source Lock — Full107 Contract Reconciliation and Current-Candidate Readiness

Workstream: `WS73-FULL107-CONTRACT-RECONCILIATION`
Branch: `ws73/full107-contract-reconciliation-20260912`
Role: SOLE EVIDENCE WRITER for `candidate-qualification/ws73-full107-contract-reconciliation/`
Audit base (immutable input): `7a92ab471a92c3c57522044d5326276d578f69d0` / tree `b245382998e0e72b2fa46c01d5902139ed2921f7` (WS72 COMPLETE head)
Worktree HEAD at lock: `7a92ab471a92c3c57522044d5326276d578f69d0` / tree `b245382998e0e72b2fa46c01d5902139ed2921f7`
Remote slug (expected): `moeendres-png/commander-playtest-lab`
Source ref (expected): `ws72/cross-candidate-card-availability-preflight-20260912`

## Authority pins (all read-only `git show`; no behavior execution; no engine/provider edits)

### WS47 contract pin (Source Authority for Full107)
- Commit: `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8`
- Tree: `f596c54d2cb229b9827c6c94a278175e8312c65c`
- Namespace tree `qualification/ws47`: `12af73695c801a42a0193ee895d5fc0843d16b0c`
- Files (exact, byte-verified):
  - `qualification/ws47/WS47_FREEZE_RESULT.json` sha256 `5ded22fca8263296e95a17e9718a241139ff084b29b92edb99d4e5a6f6d810d7` bytes 589
  - `qualification/ws47/SEMANTIC_FIXTURE_SCHEMA_v1_0_5.json` sha256 `4e7a14485fc824b466df12ad1e1928ade8079370d145f60973b23a79630d98d9` bytes 7111
  - `qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json` sha256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3` bytes 1354211
  - `qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json` sha256 `9e40e574a7b9ed47519632e79ca12e06525b97c901e63f2f08aeefabab1087a1` bytes 2754
- Contract facts (DIRECTLY_VERIFIED):
  - `record_count = 135`, `provider_denominator = 107`, `schema_version = commander-lab.semantic-fixture-materialization/1.0.5`
  - `canonical_bundle_digest = 631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01`
  - `materialization_sha256 (file) = 0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`
  - `common_fixture_manifest_sha256 = e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
  - `protocol = commander-lab.rules-service/1.1.0`

### RQ-C1 authority
- Commit: `714ad417c1c090eb4ddf1ccd0828a2e869a80a74` / tree `709a5944c9826dbaaa433052f3538425c8f0573b`
- File: `research/candidate-qualification/common/rq-c1/RQ_C1_FULL107_RELATION.md` sha256 `3087bb781672c6a098522722c950e679d459eeaa07be4388fab528166e71b0ab`
- Manifest: `research/candidate-qualification/common/rq-c1/RQ_C1_SCENARIO_MANIFEST.json` sha256 `98f2753d373f68b27942617346308b87bbe134e23c2aecda1b169758676b71f1`
- Corpus: 40 actual-card ARCHITECTURE_REVERSER_SUBSET scenarios, 15 First Wave; runs before Full107; Full107 SEPARATE evidence contract; RQ-C1 does not grant/imply/pre-count Full107 credit.

### RQ-C3 authority
- Commit: `897d72f0b57bb8febe045870acaa3d2dba4bde56` / tree `1b8c8a46f1b81277f73a0ec808055dde25fadbe5`
- Manifest: `research/candidate-qualification/common/rq-c3/RQ_C3_CORRECTED_SCENARIO_MANIFEST.json` sha256 `32dfaced5647f9ee0fa0909fa70c98bee303487f9d5dbb232e118c22ad9fc652`
- Corpus: 18 corrected scenarios (15 First Wave + F02/H02/K02 non-FW derivatives); all `behavior_credit 0`, `candidate_behavior_status NOT_RUN`; `BEHAVIOR_CREDIT_CHANGE = 0`, `FULL107 = NOT_RUN`.

### Current candidate evidence (read-only)
- XMage WS60 terminal: `731891ec5ed8e7611fc9a636bab5fc3c400108eb` / tree `21abfa179156954726ddbb8a8decbc9a8fcdb5f3` — RQ-C3 First Wave 14/15 semantic PASS (B01 UNKNOWN), filed `14/107`.
- Forge WS65 terminal: `7796619e69b0434cd232de8335ff5cab3c5d08e5` / tree `48ec3eafcca668f3fa165e3977af5836b3add059` — RQ-C3 First Wave 9/15 semantic PASS (6 UNKNOWN), filed `9/107`.
- WS72 preflight: `7a92ab471a92c3c57522044d5326276d578f69d0` / tree `b245382998e0e72b2fa46c01d5902139ed2921f7` — 40-scenario / 55-card corpus ALL_FOUND in both exact pins; `FULL107 = NOT_RUN`; `BEHAVIOR_CREDIT = 0/107`.

### Current accepted candidate pins (cited from WS62/WS65/WS56/WS60/WS72; external repos, no local object)
- Forge: `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` / tree `2c18327f79e330f2ed167067166ffd42d61b0849` / `https://github.com/moeendres-png/forge.git` (WS59 remediation on `66caae16015bd403bc0a52fa6689afb5508f74d0`; corroborated by WS62 `WS62_FORGE_PIN.json`, WS65 source lock, WS72 source lock).
- XMage: `7135d5e85ddb4c8aa4b49b4192ca51947c822704` / tree `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` / `https://github.com/moeendres-png/mage.git` (WS56 successor requalification PASS `1dc43619`; corroborated by WS60 report, WS72 source lock).

### Historical Full107 material (read-only branch reads)
- Forge WS48 construction: old pin `66caae16015bd403bc0a52fa6689afb5508f74d0` / tree `40fc8f29ce4de31a964972461db2b48b4221e07f`; runs `34260903310` (construction 107/107) + `34263710979` (independent readback 107/107); `behavior_credit 0/107`; `construction_credit 107/107` (at old pin only).
- XMage WS49 construction: old pin `0c1f455ea8c8fa48ab9d638ad5068ec242800428` / tree `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`; runs `34305543900`/`34305822709` (construction 107/107, superseded) + `34377227629` (G49-08 independent normalization 107/107 PASS); `behavior_credit 0/107`; sealed behavior run `34412882569` credit `0/107` (no promotion).

### Active remediation (outcomes conditional; never assumed)
- WS67 (Forge engine remediation): ACTIVE — Ghalta-entry, Covenant X-mauling, Clone/Humility scope (see WS65 remediation packets).
- WS68 (Forge provider transport remediation): ACTIVE branch `ws68/forge-provider-transport-remediation-20260912` head `903b3f4a6ff9f5228a3d8210429d5a0689383ec9` — payCombatCost + two-phase concession overlay (intents E01-pay/decline, G04, A04, C01).

## Ownership and invariants
- Written ONLY under `candidate-qualification/ws73-full107-contract-reconciliation/`.
- No Forge, XMage, engine-bridge, provider, `tools/foundry`, or other-workstream file modified.
- No behavior executed. No engine edits. No provider edits.
- Evidence labels used: only `DIRECTLY_VERIFIED`, `CODE_DERIVED`, `TECHNICALLY_CONFORMANT`, `EXTERNALLY_RULE_VALIDATED`, `MODELED`, `SYNTHETIC`, `UNKNOWN`. Never `RUNTIME_VERIFIED`.
- `BEHAVIOR_CREDIT_CHANGE = 0`. `FULL107 = NOT_RUN`. `ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

## Read-only operations used
- `git rev-parse HEAD`, `git rev-parse HEAD^{tree}`, `git branch --show-current`, `git status --porcelain=v1`
- `git show <pin>:<path>`, `git ls-tree`, `git rev-parse <pin>^{tree}`, `git log --oneline`
- `python3` deterministic JSON derivation (sorted keys, no timestamps) + `sha256sum` equivalence via `hashlib.sha256`
- Engine pins cited from in-repo WS62/WS65/WS56/WS60/WS72 source locks (no new clone/checkout/fetch).
