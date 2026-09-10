# Evidence Index Requirements (canonical)

Status: canonical companion to `docs/RETENTION_AND_LIFECYCLE_POLICY.md`.
Established by: WS-A1R. No evidence is deleted or migrated by this document.

## 1. Purpose

Before any evidence branch, artifact payload, handoff, or report can transition
to `ARCHIVE_ELIGIBLE` / `DELETE_ELIGIBLE`, its provenance must exist as a compact
manifest entry. The index entry — not the live ref — becomes the provenance unit.
Prefer compact manifests over indefinitely retaining redundant multi-MB payloads
**only** when every field below is preserved and byte-identity of payloads is
proven where payloads are dropped.

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
retention_reason: <why>
retirement_approved_by: NONE
```

## 4. Non-goals

- No bulk re-indexing is ordered here (that is WS-A3-class work).
- No payload deletion is authorized here (see Retention Policy §5).
- Filenames containing CURRENT/FINAL/LATEST confer no authority; the index entry does.
