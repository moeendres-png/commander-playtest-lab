# Repository Retention and Lifecycle Policy (canonical)

Status: canonical policy for `moeendres-png/commander-playtest-lab` (pre-freeze).
Established by: WS-A1R. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
`PRODUCTION_PROVIDER = NOT SELECTED`.

This policy governs branches, PRs, generated evidence, handoffs, Source Locks,
and historical qualification reports. It creates **no deletion authorization**:
every destructive action additionally requires the approvals in §5.

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
| `MERGED` | Fully merged into `main`; no unique commits | Delete ref 7+ days after merge unless claimed in `.foundry/WORKSTREAM_STATE.yaml`; record SHA in the deleter's handoff |
| `SUPERSEDED` | Replaced by a named successor branch | Keep until successor's evidence is indexed (see `docs/EVIDENCE_INDEX_REQUIREMENTS.md`); then `ARCHIVE_ELIGIBLE` |
| `TERMINAL_EVIDENCE` | Completed/failed-closed workstream whose branch carries unique evidence (WS closeouts, finalist convergence, `runs/*`) | Keep until manifest-indexed; then `ARCHIVE_ELIGIBLE`. Never fast-track |
| `ARCHIVE_ELIGIBLE` | Indexed; ref may be retired but objects stay reachable via manifest SHA | Close PR (never merge) → delete ref → keep manifest. Requires §5 approval |
| `DELETE_ELIGIBLE` | Indexed **and** proven redundant (byte-identical evidence elsewhere, `tmp/*`, `noop`, exact-duplicate experiment variants) | Delete ref only. Requires §5 approval |
| `UNKNOWN` | Unclassified (old `agent/*`, `telemetry/*`, `roadmap/*`, pre-policy branches) | Classify per-branch before any other transition. Bulk transitions forbidden |

`runs/*`: `TERMINAL_EVIDENCE` by default; retire only after the run manifest
(objectives, SHAs, seeds, result hashes) is indexed.
`tmp/*`, `noop`, `*-unused`, `*-stop`, `do-not-use`: presumed `DELETE_ELIGIBLE`
candidates, still requiring §5 proof + approval — presumption is not proof.

## 3. PR lifecycle

- Open PRs are work-review instruments, not permanent evidence records. Where
  equivalent immutable/indexed provenance exists (manifest SHA + handoff), prefer
  closing over perpetual openness.
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
  requires byte-identity proof first.
- Handoffs and Source Locks: retained; retirement only via `ARCHIVE_ELIGIBLE`.
- Large future corpora (>5MB): GitHub Releases attachments + SHA256 manifests
  in-repo (pattern: `WS17_SHA256SUMS`). No new artifact classes without a manifest.

## 5. Deletion eligibility (fail closed)

All must hold, evidenced in the deleting workstream's handoff:

1. No active workstream/branch/worktree depends on the object
   (check `.foundry/WORKSTREAM_STATE.yaml` lineage + worktree inventory).
2. No unique evidence depends on it (manifest index entry cites a canonical copy).
3. Provenance remains reconstructable (full commit SHA + tree SHA retained in index).
4. Canonical replacement is known (path or manifest pointer, not "somewhere in history").
5. No CI/workflow depends on it (grep `.github/workflows`, scripts, Dockerfiles).
6. No active PR depends on it as head or base.
7. Required commit/tree identities are retained outside the ref.
8. Coordinator/human destructive approval is recorded (who, when, scope).

## 6. What this policy does not authorize

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
- `SCHEMA_RENAME_primary_secondary = DEFERRED` (Freeze-adjacent). `primary_engine`
  / `secondary_engine` are runtime-contract keys (consumers:
  `src/commander_lab/technical_truth.py`, `scripts/run_external_b4f_*.py`,
  `.github/workflows/release-artifacts.yml`); terminology is clarified in
  `authority_note.role_terminology` instead. Rename only with contract migration.
