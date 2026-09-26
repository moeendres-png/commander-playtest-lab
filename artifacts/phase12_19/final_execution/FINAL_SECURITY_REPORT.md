# Final Security Report

- Tracked-file secret scan: passed, 0 findings.
- AST dangerous-call scan: passed, 0 shell=True/eval/exec/extractall calls.
- SQL dynamic identifier review: one DROP TABLE site, constrained to a constant legacy-table allow-list.
- Atomic-write/integrity regression coverage: passed.
- Dependency vulnerability audit (`pip-audit`): blocked because tool installation is unavailable in this runtime.
- Official CycloneDX SBOM and license scan: blocked; fallback inventories are retained and labeled.
- `pip check`: environment conflict outside Commander Lab metadata (moviepy/Pillow).
- External rules engines: no external process executed, so no external-engine security/runtime claim is made.
