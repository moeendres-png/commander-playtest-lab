# Evidence Index Requirements (canonical)

Status: canonical companion to `docs/RETENTION_AND_LIFECYCLE_POLICY.md`.
Established by: WS-A1R. No evidence is deleted or migrated by this document.

## 1. Purpose

Before any evidence branch, artifact payload, handoff, or report can transition
to `ARCHIVE_ELIGIBLE` / `DELETE_ELIGIBLE`, its provenance must exist as a compact
manifest entry AND its unique objects must have a verified durable retention
anchor (Retention Policy §6). The index entry identifies the provenance unit; it
does not store it:

- `INDEX != STORAGE`: the entry is a finding aid, not a copy.
- `SHA != RETENTION ANCHOR`: recording a commit/tree/blob SHA as text preserves
  no bytes. Ref deletion on SHA evidence alone destroys the only durable copy
  once the last retaining ref is gone and collection occurs.

Prefer compact manifests over indefinitely retaining redundant multi-MB payloads
**only** when every field below is preserved, byte-identity of payloads is
proven, AND the surviving copy is itself anchored with its own locator.

## 2. Minimum index entry fields

- `workstream`: owning workstream id (e.g. `WS-48`, `J-P2`, `research/d6-…`).
- `repository`: full `owner/name`.
- `branch`: full ref at retirement.
- `commit`: full 40-hex HEAD SHA. Tree SHA where available (`git rev-parse HEAD^{tree}`).
- `source_pins`: engine commits / releases consumed (`config/rules_engines.json`
  snapshot or explicit SHAs), bridge protocol version, Lab HEAD/tree.
- `classification`: one of `DIRECTLY_VERIFIED`, `CODE_DERIVED`,
  `TECHNICALLY_CONFORMANT`, `EXTERNALLY_RULE_VALIDATED`, `MODELED`, `SYNTHETIC`,
  `UNKNOWN`. `UNKNOWN != PASS`.
- `result`: `PASS` / `FAIL` / `PARTIAL` / `TERMINAL` / `SUPERSEDED` + one-line cause.
- `artifacts`: material paths with SHA256 hashes (payloads retained or
  content-addressed copies). Hashes, not adjectives, carry identity.
- `superseded_by` / `supersedes`: successor/predecessor workstream or `NONE`.
- `retention_anchor_type`: one of `canonical_history`, `retained_ref`,
  `archival_bundle`, `proven_equivalent` (Retention Policy §6), or `UNKNOWN`
  (fails closed: ref must be retained).
- `retention_anchor_locator`: ref name, bundle path/URL, or equivalent pointer;
  `NONE` is accepted only with `retained_ref=self` semantics recorded explicitly.
- `retention_anchor_verified`: how recoverability was proven (command + output
  reference); `UNVERIFIED` fails closed.
- `retention_anchor_hash`: SHA256 of the bundle/manifest entry where applicable.
- `retention_reason`: why this entry (and any retained payload) is kept.
- `retirement_approved_by`: Coordinator/human identity + date (for
  `ARCHIVE_ELIGIBLE` and above).

## 3. Template (copy per entry; store under `qualification/` manifests)

```yaml
workstream: WS-NN
repository: moeendres-png/commander-playtest-lab
branch: wsNN/slug
commit: <40-hex>
tree: <40-hex or UNKNOWN with reason>
source_pins: {lab_head: <sha>, xmage: <sha or NONE>, forge: <sha or NONE>, bridge_protocol: <ver>}
classification: UNKNOWN
result: TERMINAL
cause: <one line>
artifacts: [{path: <repo-relative>, sha256: <hex>}]
superseded_by: NONE
retention_anchor_type: retained_ref
retention_anchor_locator: <branch ref or bundle path/URL>
retention_anchor_verified: <command + evidence ref, e.g. merge-base proof>
retention_anchor_hash: <sha256 or N/A with reason>
retention_reason: <why>
retirement_approved_by: NONE
```

## 4. Non-goals

- No bulk re-indexing is ordered here (that is WS-A3-class work).
- No payload deletion is authorized here (see Retention Policy §5).
- Filenames containing CURRENT/FINAL/LATEST confer no authority; the index entry
  identifies authority. Identification is not storage: retirement approval
  (`retirement_approved_by`) never substitutes for the technical retention proof
  above — both are required, separately evidenced.
