# WS226 MANIFEST_REPAIR — terminal same-commit refresh over the combined tree

Method (WS221 S4 invariant preserved: committed edit to a seal-covered artifact
must refresh its applicable hash manifest in the same commit):

1. After ALL semantic bytes + WS226 standing outputs + WS226 docs are stable,
   recompute `qualification/SHA256SUMS` (inner): every `qualification/**` file
   except `SHA256SUMS` itself, `sha256(file) + '  ' + rel-from-qualification`,
   sorted byte-order, LF, no trailing spaces.
2. Recompute `WS17_SHA256SUMS` (outer): `pyproject.toml`,
   `.github/workflows/production-qualification.yml`,
   `tests/qualification/test_ws17_qualification.py`, plus every
   `qualification/**` file (including the refreshed `qualification/SHA256SUMS`
   line with its NEW digest), same format, rel-from-root, sorted.
3. No historical artifact altered to make hashes match; no file excluded;
   hash comparison untouched (same `test_all_ws17_hash_manifests…` logic).
4. Prove: byte hashes verify, coverage sets equal expected, deliberate
   single-byte mismatch still fails (negative control in F_CI_02_VALIDATION).

Stale-manifest root cause (CODE_DERIVED):
- Base manifests == anchor `67db0733` bytes (miss 127 WS218/WS223 paths).
- WS225 manifests cover +WS220/WS221/WS225 (98) but miss WS218/WS223 (127) +
  WS222 (72) + WS224 (35) + WS226 (~40).
- Neither sibling manifest is final; WS226 recomputes terminally.

Result: F-CI-02 GREEN on the final combined tree (see F_CI_02_VALIDATION).
