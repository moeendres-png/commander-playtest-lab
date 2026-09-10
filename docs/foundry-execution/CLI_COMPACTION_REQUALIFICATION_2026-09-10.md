# CLI / Compaction Requalification — 2026-09-10 (Checkpoint F)

Pin: OpenCode CLI **1.18.29** (`.github/workflows/opencode.yml` asserts exact).
Installed local: **1.18.30**. Latest official stable (verified via release API):
**v1.18.30**. 1.18.29 binary downloaded to isolated `/tmp` (never installed;
live workstream TUIs untouched).

## 1. Bounded comparison 1.18.29 vs 1.18.30 (isolated HOME, no model calls)

| Surface | 1.18.29 | 1.18.30 | Verdict |
|---|---|---|---|
| project config load (`debug config`) | model lock + share + effort resolve | identical | SAME |
| HIGH/XHIGH availability (variants, default high) | resolve | identical | SAME |
| permission resolution order + `--auto`+deny semantics | 72-probe battery | 72-probe battery, **zero verdict diffs** | SAME |
| skill discovery (`debug skill`) | 8 skills | 8 skills | SAME |
| agent discovery (`debug agent`) | implementer/high resolves | identical | SAME |
| launcher bundle resolution (CONTENT+DIR in engine-like CWD) | model lock + implementer/high + canonical skills | identical | SAME |
| `session list`, `stats`, `export [id]`, `run --variant/--format/--continue` | present, same syntax | present | SAME surface |
| export JSON *shape* (turns/tokens/cost markers) | not observed (no isolated sessions; real store untouched while live TUIs run) | DIRECTLY_VERIFIED via live export | UNKNOWN for .29 |
| compaction keys (`auto/prune/tail_turns`) | accepted, echoed | identical | SAME |
| declarative session-compacting hook (`experimental.session.*`) | n/a (tested .30) | silently dropped (`experimental: {}`) | ABSENT |

## 2. What 1.18.30 changed (release notes)

Provider SDK updates (Azure/OpenAI), Bedrock DeepSeek ID preservation, Astra
system prompt for GPT-6 models, GitLab reasoning variants. **Nothing** touches
config schema, permission resolution, `--auto`/deny semantics, compaction,
sessions, stats/export, or AGENTS/instructions discovery.

## 3. Verdicts

- `CLI_UPGRADE_CANDIDATE = NO` — 1.18.30 offers no material improvement for
  long-horizon Muse use on any tested surface; enforcement is bit-identical.
- `CLI_PIN_CHANGE = NOT_AUTHORIZED` — pin stays 1.18.29 until the Coordinator
  authorizes migration on new evidence.
- Evidence generated on installed 1.18.30 transfers to the pin for the SAME
  surfaces above (config, resolution, enforcement, skills, launcher
  compatibility, compaction keys). Export-shape telemetry stays .30-scoped.
- `COMPACTION_HOOK = INTENTIONALLY_DEFERRED` — verified: no declarative
  project-level compacting hook exists in the supported schema (unknown keys
  are dropped, not honored); the only hook surface is the TS plugin API
  (`experimental.session.compacting` transform), which is message compression,
  not a state writer, and would need a repo plugin plus cross-version API
  qualification. Resumability rests on Git + state 2.0 + sealed evidence,
  which is version-independent. Revisit only if a pinned version ships a
  supported declarative hook.

## 4. Method honesty

No model calls were spent; no live session, store, binary, or global config
was touched. The .29 binary ran only `debug`/`session`/`stats` (read-only)
under an isolated HOME. The one deliberate UNKNOWN (export shape on .29) is
cheaper to keep than to risk the live session store.
