# CI / Gate Skills — upstream provenance and adaptation ledger

Imported: 2026-10-05  
Target repository: `moeendres-png/commander-playtest-lab`

These skills are workflow guidance only. Repository-root `AGENTS.md`, the current
execution-authority document and the active workstream contract remain authoritative.

## Source locks

| Source | Commit | Tree | License |
| --- | --- | --- | --- |
| Trail of Bits `trailofbits/skills` | `82fe8226252622fa807643bdca1710901198553a` | `9cf630657892690adfb649b3125269253e549c3a` | CC BY-SA 4.0 |
| Superpowers via `openai/plugins` | `5fd93af4cd0c623e020d0cc7e9ce178b4ac1f70f` | `36c126d32c3a612d7e75cef5a8513c3ad757bd76` | MIT, copyright Jesse Vincent |
| `tphakala/claude-gate-skill` | `6d352f7d06b83e98102847f3ef91da5061c262de` | `15c6b2c5775e53e4ccf56e2b95b9b0857c90afb0` | MIT, copyright Tomi P. Hakala |

License texts are retained under `.claude/skills/licenses/`.

## Imported skills

### `post-patch-validation`

Source:
`plugins/post-patch-validation/skills/post-patch-validation/`

Imported:
- `SKILL.md`
- `references/evidence-model.md`
- `scripts/post_patch_validation.py`
- `scripts/pyproject.toml`

Import state: **byte-identical to the pinned upstream blobs**.

Purpose: reproducible vulnerable-base vs patched-head validation with independent
controls, exploit reproduction, root-cause variants, behavior preservation,
regression/security checks and suite evidence. Its source/build/runtime evidence
levels supplement rather than replace Commander evidence classifications.

### `differential-review`

Source:
`plugins/differential-review/skills/differential-review/`

Imported:
- `SKILL.md`
- `methodology.md`
- `adversarial.md`
- `patterns.md`
- `reporting.md`
- `agents/adversarial-modeler.md`

Adaptation state: supporting files remain byte-identical; `SKILL.md` is a marked
local adaptation.

Local adaptations:
- removes hard dependency on the separately packaged `audit-context-building` and
  `issue-writer` skills;
- uses project-native source locking, Git history, callers/tests and persisted GitHub
  reports instead;
- treats the bundled adversarial-modeler prompt as a lens usable inline or by any
  available fresh reviewer rather than assuming a plugin-registered subagent.

Because the Trail of Bits source is CC BY-SA 4.0, this adapted `SKILL.md` remains
subject to the applicable attribution/share-alike terms.

### `agentic-actions-auditor`

Source:
`plugins/agentic-actions-auditor/skills/agentic-actions-auditor/`

Imported:
- `SKILL.md`
- foundations/action profiles/cross-file-resolution references
- all nine A–I attack-vector references

Import state: **byte-identical to the pinned upstream blobs**.

Purpose: static security review of GitHub Actions that invoke AI agents, including
prompt-injection data flows, `pull_request_target`, runtime untrusted fetches,
AI-output execution, dangerous sandboxes and wildcard allowlists.

### `verification-before-completion`

Source:
`plugins/superpowers/skills/verification-before-completion/SKILL.md`

Import state: **byte-identical to the pinned upstream blob**.

Purpose: forbids success/completion claims without fresh verification evidence
matching the exact claim.

### `systematic-debugging`

Source:
`plugins/superpowers/skills/systematic-debugging/`

Imported:
- `SKILL.md`
- `root-cause-tracing.md`
- `defense-in-depth.md`
- `condition-based-waiting.md`
- supporting example/script

Adaptation state: supporting files remain byte-identical; `SKILL.md` is a marked
local adaptation.

Local adaptations:
- removes the missing hard dependency on `superpowers:test-driven-development`;
- points completion verification to the locally imported
  `verification-before-completion`;
- converts the upstream “ask the human after three failed fixes” wording into the
  project's authority-gate rule: ask only at a genuine owner/authority gate,
  otherwise persist blocker + exact next action.

### `commander-quality-gate` — adapted from upstream `gate`

Upstream source:
`tphakala/claude-gate-skill/SKILL.md`.

The upstream file is retained byte-identically at:
`.claude/skills/commander-quality-gate/references/upstream-gate-SKILL.md`.

The active `commander-quality-gate/SKILL.md` is a new Commander-specific adaptation,
not a byte-identical copy. It keeps the upstream concepts that fit this project:
mechanical checks before interpretation, explicit review coverage, bounded repair
rounds, no SKIP-as-PASS, fix-wave re-review and continuous learning from escaped
defects. It replaces generic repo assumptions with Commander Source Truth, evidence
classes, workstream ownership, exact-head CI, base-drift adjudication and protected
merge discipline.

## Authority / evidence guardrails

None of these skills may:

- expand branch/file ownership;
- fabricate or infer legal Magic actions;
- treat green CI as Rules qualification;
- promote source/build/construction evidence to runtime behavior;
- treat `UNKNOWN`, `NOT_RUN` or `PARTIAL` as PASS/FULL;
- select the Production Provider;
- claim Architecture Freeze;
- create the Production Repository;
- bypass protected-branch required checks.

Where upstream guidance conflicts with project policy, project policy governs.
