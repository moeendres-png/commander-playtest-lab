# Repository Retention and Lifecycle Policy (canonical)

Status: canonical policy for `moeendres-png/commander-playtest-lab` (pre-freeze).
Established by: WS-A1R. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
`PRODUCTION_PROVIDER = NOT SELECTED`.

This policy governs branches, PRs, generated evidence, handoffs, Source Locks,
and historical qualification reports. It creates **no deletion authorization**:
every destructive action additionally requires the approvals in §5.

## 0. Identity is not storage (foundational rule)

Identity/provenance metadata (repository, branch, commit SHA, tree SHA, artifact
SHA256, Source Locks, supersession relations) **identifies** evidence. It does
**not** by itself preserve the underlying object/content:

- `INDEX != STORAGE`: a manifest entry is a finding aid, not a copy.
- `SHA != RETENTION ANCHOR`: a SHA recorded as text in Markdown/YAML is not a Git
  ref and does not keep an otherwise unreachable commit/tree/blob retrievable
  after the last retaining ref is removed and garbage collection/hosting
  retention occurs.

Deleting a remote ref is therefore forbidden for any branch with UNIQUE
source/evidence until BOTH hold: (A) provenance/identity is indexed per
`docs/EVIDENCE_INDEX_REQUIREMENTS.md`, AND (B) the underlying unique Git/content
object closure has a verified durable retention anchor (§6). A manifest SHA alone
satisfies A, never B. If B is UNKNOWN: fail closed, retain the ref.

## 1. Core distinction

- `OPERATIONALLY_OBSOLETE`: no live workstream depends on the object, but it may
  still carry unique provenance. Default: retain (or archive-pointer), never delete.
- `SAFE_TO_DELETE`: obsolete **and** every eligibility proof in §5 holds **and**
  Coordinator/human destructive approval is recorded. Nothing in this repository is
  `SAFE_TO_DELETE` by age, name, or supersession alone.

When uncertain, default to archive/retain. Git history is never rewritten to
enforce this policy.

## 2. Branch lifecycle states and exit criteria

| State | Meaning | Exit criteria |
|---|---|---|
| `ACTIVE` | Owned live workstream (exactly one owner, one worktree) | Workstream completes → `MERGED`, `TERMINAL_EVIDENCE`, or `SUPERSEDED` |
| `MERGED` | Required commits verified reachable from retained canonical history (ancestry proven via merge-base/contains, never inferred from PR state, PR title, or branch name); no unique commits outside canonical history | Eligible for deletion adjudication no earlier than 7 days after verified merge unless claimed in `.foundry/WORKSTREAM_STATE.yaml`; §5 proofs + approval still mandatory. No automatic deletion timer |
| `SUPERSEDED` | Replaced by a named successor branch | Keep until successor's evidence is indexed AND retention-anchored (§6); then `ARCHIVE_ELIGIBLE` |
| `TERMINAL_EVIDENCE` | Completed/failed-closed workstream whose branch carries unique evidence (WS closeouts, finalist convergence, `runs/*`) | Keep until manifest-indexed AND retention-anchored (§6). Never fast-track. If no anchor mechanism exists yet, keeping the ref IS the anchor — retain |
| `ARCHIVE_ELIGIBLE` | Indexed AND retention-anchored: recoverability provably no longer depends on the live ref. A manifest SHA alone never qualifies | Close PR (never merge) → delete ref → keep manifest AND anchor. Requires §5 approval |
| `DELETE_ELIGIBLE` | Indexed, retention-anchored, **and** proven redundant by explicit evidence: same-commit reachability through another retained ref, or every unique object otherwise durably retained and verified. Name patterns (`tmp`, `noop`, `unused`, `stop`, `do-not-use`) are candidate signals only, never proof | Delete ref only. Requires §5 approval |
| `UNKNOWN` | Unclassified (old `agent/*`, `telemetry/*`, `roadmap/*`, pre-policy branches) | Classify per-branch before any other transition. Bulk transitions forbidden |

`runs/*`: `TERMINAL_EVIDENCE` by default; retire only after the run manifest
(objectives, SHAs, seeds, result hashes) is indexed AND the unique run objects
are retention-anchored (§6).
`tmp/*`, `noop`, `*-unused`, `*-stop`, `do-not-use`: presumed `DELETE_ELIGIBLE`
candidates, still requiring §5 proof + approval — presumption is not proof. A
junk-looking name never substitutes for the redundancy proof in §2.

## 3. PR lifecycle

- Open PRs are work-review instruments, not permanent evidence records. Where
  equivalent immutable/indexed provenance exists (manifest index entry + handoff)
  AND the underlying objects are retention-anchored (§6), prefer closing over
  perpetual openness. PR metadata is not Git reachability: closing a PR never
  preserves objects by itself.
- `MERGED` PRs: no action (record stands).
- Terminal PRs (COMPLETE / TERMINAL / SUPERSEDED by title): keep open until the
  underlying branch reaches `ARCHIVE_ELIGIBLE`; then close **unmerged** with a
  comment citing the manifest index entry.
- This policy closes no existing PR by itself. Each closure is a separately
  approved action citing the index entry.

## 4. Generated evidence, handoffs, Source Locks, reports

- `qualification/` manifests, source locks, `SHA256SUMS`, evidence indexes:
  append-only. Superseded verdicts are retained with a supersession pointer, never
  overwritten.
- `artifacts/`, `data/`: freeze writes to closed phase/run directories
  (`artifacts/phase12_*`, `data/canonical_import/*`). New output goes to new
  dated directories. Dedup (single content-addressed copy + manifest pointers)
  requires byte-identity proof first AND requires the surviving copy itself to
  live in retained history or durable indexed storage with its own locator —
  a pointer to a deleted payload preserves nothing.
- Handoffs and Source Locks: retained; retirement only via `ARCHIVE_ELIGIBLE`.
- Large future corpora (>5MB): GitHub Releases attachments + SHA256 manifests
  in-repo (pattern: `WS17_SHA256SUMS`). No new artifact classes without a manifest.

## 5. Deletion eligibility (fail closed)

All must hold, evidenced in the deleting workstream's handoff:

1. No active workstream/branch/worktree depends on the object
   (check `.foundry/WORKSTREAM_STATE.yaml` lineage + worktree inventory).
2. No unique evidence depends on it, OR every unique object has a verified
   durable retention anchor (§6) with type, locator, and verification recorded
   in the index entry. A manifest SHA citing the object satisfies identity, not
   retention.
3. Provenance remains reconstructable (full commit SHA + tree SHA in the index)
   AND the objects those SHAs name remain retrievable via the §6 anchor.
4. Canonical replacement is known (retained path or anchored copy with locator,
   not "somewhere in history" and not a bare manifest pointer).
5. No CI/workflow depends on it (grep `.github/workflows`, scripts, Dockerfiles).
6. No active PR depends on it as head or base.
7. Required commit/tree/blob identities are named in the index AND their content
   is retrievable via the §6 anchor (naming without retrievability fails this item).
8. Technical retention eligibility (items 1–7) is proven in the handoff; UNKNOWN
   on any item fails closed and retains the ref.
9. Coordinator/human destructive approval is recorded (who, when, scope).

Items 1–8 establish technical eligibility; item 9 is the independent approval.
Retirement approval never implies retention was technically proven — both are
required, separately evidenced.

## 6. Durable retention anchors

Accepted anchor types for unique Git/content objects (use the strongest available;
record `retention_anchor_type`, `retention_anchor_locator`,
`retention_anchor_verified`, `retention_anchor_hash` in the index entry):

1. `canonical_history`: required commits are reachable from a permanently retained
   canonical ref/history (e.g. actually merged into protected `main`). Prove
   ancestry (`git merge-base --is-ancestor` / `git branch --contains`); never
   infer from PR state, PR title, or branch name. External (non-Git) artifacts on
   such branches still need their own anchor.
2. `retained_ref`: another explicitly retained Git ref points to or contains the
   commit. Name the ref; deleting THAT ref later re-opens this proof.
3. `archival_bundle`: a verified archival Git bundle (or proven-equivalent
   lossless archive) containing the required commit/tree/blob closure exists in
   durable project storage, with its own SHA256 and provenance locator, verified
   by test-restore or `git verify-bundle` + object listing. (Mechanism defined
   here; implementation belongs to a later archival workstream — do not invent
   unproven equivalents to turn a policy red into green.)
4. `proven_equivalent`: another mechanism proven — with evidence, not assertion —
   to preserve reconstruction. The proof is part of the index entry.

If the anchor is UNKNOWN, fail closed and retain the ref. Keeping the current
branch ref is always a valid anchor and the preferred one when no other anchor
exists yet.

## 7. What this policy does not authorize

No repository creation/merger/split/archival/deletion; no history rewrite; no force
push; no rebase of shared history; no license decision; no branch-protection
mutation; no Provider Selection; no Freeze claim. See Appendix G for the recorded
gates owned elsewhere.

## Appendix G. Recorded Authority Gates and follow-up specs (WS-A1R)

- `LICENSE_DECISION = AUTHORITY_GATE` (human/legal). Factual input:
  lab has no LICENSE file; forks inherit MIT (mage) / GPL-3.0 (forge);
  contributors on record: moeendres-png, codex, github-actions[bot];
  legal-topology review pack exists on branch
  `research/legal-topology-review-pack-20260910` (`LEGAL_CLEARANCE = NONE`).
- `BRANCH_PROTECTION = AUTHORITY_GATE` (human governance workstream). Needed:
  lab `main` protection (required PRs, required CI, no direct push); eventually
  mirror-master protection on both forks compatible with upstream sync
  (sync-via-fast-forward-only or admin-mediated). WS-A1R mutated no settings.
- `DESTRUCTIVE_CLEANUP = AUTHORITY_GATE` (Coordinator + human). Pre-authorized
  enumerations exist (audit §L spotlights); each wave needs its own approval citing
  `docs/EVIDENCE_INDEX_REQUIREMENTS.md` entries. WS-A1R deleted nothing.
- `PIN_DIVERGENCE_DOCKERFILES = AUTHORITY_GATE` (re-pin workstream). Facts:
  `docker/forge/Dockerfile` defaults to `852066bf` (manifest: `a37a865a`);
  `docker/xmage/Dockerfile` defaults to `06d166b0` (manifest: `77d7646d`);
  `docker-compose.engine.yml` passes no build-arg override, so a default container
  build materializes superseded engines. Changing the defaults changes built
  artifacts and requires requalification — out of WS-A1R scope. Follow-up: a
  dedicated re-pin workstream (re-pin Dockerfiles to manifest, rebuild, rerun the
  B3/B4 regression chain, update `docs/engine_setup.md` container section).
  Resolution (WS-A1D): Dockerfiles now declare required build args without
  defaults, resolved from the manifest at build time by
  `scripts/docker_build_engine.sh` via `scripts/docker_resolve_engine_pin.py`;
  Compose requires wrapper-exported variables and otherwise fails closed;
  Compose/devcontainer protocol corrected to `2.0.0`; image provenance is
  recorded (`/opt/engine-provenance.json`) and enforced by a container-start
  gate (`scripts/verify_container_provenance.py`); `docs/engine_setup.md`
  documents the wrapper flow. B3/B4 were adjudicated UNAFFECTED (direct-source
  path, no Docker consumption). Remaining: real image materialization on a host
  with Docker (NOT_RUN on the WS-A1D execution host: no Docker client there).
  Remediation 01 (post-publication review): provenance gate and entrypoint are
  now unconditional fail-closed (any unprovable identity stops startup); the
  wrapper resolves/exports both provider identities; the resolver validates the
  manifest `provider` field.
- `SCHEMA_RENAME_primary_secondary = DEFERRED` (Freeze-adjacent). `primary_engine`
  / `secondary_engine` are runtime-contract keys (consumers:
  `src/commander_lab/technical_truth.py`, `scripts/run_external_b4f_*.py`,
  `.github/workflows/release-artifacts.yml`); terminology is clarified in
  `authority_note.role_terminology` instead. Rename only with contract migration.
