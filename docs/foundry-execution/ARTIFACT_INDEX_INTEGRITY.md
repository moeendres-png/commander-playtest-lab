# Artifact-index integrity

The existing `tools/foundry/evidence.py artifact-index` command inventories bytes;
it does not qualify behavior, promote evidence, or validate claimed source/run IDs.

```
python tools/foundry/evidence.py artifact-index --root RUN_DIR --run RUN_ID --source-sha COMMIT --output RUN_DIR/manifest.json
```

Every supplied root must exist as a non-symlink directory. An existing empty root
can legitimately return an empty inventory; a missing root is an error. Symlink
files/directories remain intentionally excluded. Non-regular matched files fail.
Overlapping roots and patterns produce one entry per canonical absolute path;
hard links at distinct paths remain distinct artifacts. Paths in new manifests
are absolute, normalized paths. Consumers must not assume the caller's spelling.

Size and SHA-256 come from the same open regular-file descriptor. Identity, size,
mtime and ctime are checked before/after reading and against the final path. Detected
mutation, disappearance, replacement or traversal failure aborts the inventory.
On platforms supporting O_NOFOLLOW/O_NONBLOCK these prevent final-component link
following and blocking on a substituted special file. This is not a host sandbox.

The named output is excluded, so repeated runs never index their previous manifest.
It is replaced atomically only after indexing/serialization completes. Index/write
failure returns 1 with ARTIFACT_INDEX_FAIL and preserves the prior output. Successful
commands return 0. Output-parent directories must already exist; output symlinks fail.
Inputs are not modified. `report` behavior and evidence verdict vocabulary are unchanged.

Stop artifact producers before indexing. This is per-file drift detection, not an
atomic directory snapshot: changes between traversal phases or after a file was
hashed are not fully excluded. A hostile writer able to defeat metadata checks is
outside the guarantee. Timestamp generated_utc varies; artifact rows for unchanged
inputs are deterministic. Hashes establish byte identity, never Rules Correctness.
