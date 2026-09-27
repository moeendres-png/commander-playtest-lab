# Security and supply chain

- Secret-bearing values are redacted from structured logs.
- Subprocess commands remain explicit argument arrays; shell execution is not used for untrusted tool payloads.
- Run paths are constrained and manifests reject path traversal.
- SQLite integrity: `{'status': 'passed', 'integrity': True, 'foreign_keys': True, 'schema_version': 1}`
- Project dependency versions are bounded in `pyproject.toml`; a fully resolved lock/audit requires network-enabled CI.
- External-engine binaries are not bundled or claimed present.
