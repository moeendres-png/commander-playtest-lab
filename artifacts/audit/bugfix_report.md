# Bugfix report

- **BUG-86-001 (critical)**: Require a successful external runtime probe and reject legacy/unattested bridge results. — `passed`
- **BUG-86-002 (high)**: Execute every message type against the bridge and record actual structured responses/errors. — `passed`
- **BUG-86-003 (high)**: Keep prepared status until all real integration gates pass. — `passed`
- **BUG-86-004 (high)**: Introduce atomic write helpers and apply them to key run, process-state and registry artifacts. — `passed`
- **BUG-86-005 (medium)**: Use SQLite backup API with checkpoint and validate restored database. — `passed`
- **BUG-86-006 (medium)**: Seal complete experiment design and reject changes under the same ID. — `passed`
