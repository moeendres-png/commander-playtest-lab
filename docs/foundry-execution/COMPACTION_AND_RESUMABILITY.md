# Compaction and Resumability

`COMPACTION_HOOK = DEFERRED`

Exact technical reason: the pinned OpenCode CLI configuration schema
(`https://opencode.ai/config.json`, verified against the live schema) defines a
`compaction` object with only `auto`, `prune`, `tail_turns`,
`preserve_recent_tokens`, and `reserved` fields, plus a `compaction` system agent
for summaries. There is no supported project-level session-compacting hook
(`experimental.session.compacting` or equivalent) in which to inject
Objective, Source Lock, Gates, or Exact Next Action. Implementing such a hook
would require inventing unsupported configuration, which is forbidden.

Resumability therefore rests on Git plus `.foundry/WORKSTREAM_STATE.yaml` plus
sealed evidence, which works from any fresh context:

1. verify branch, worktree, HEAD, and `git status`;
2. read `.foundry/WORKSTREAM_STATE.yaml` (validated by `tools/foundry/state.py`);
3. reverify only the mutable facts needed for the Exact Next Action;
4. continue without rerunning valid evidence (see the `continuation` skill).

Compaction summaries, when OpenCode produces them automatically, are lossy and
never authoritative. If a future pinned OpenCode version gains a supported
compaction hook, this record should be revisited and the hook implemented
minimally against the state-file field list.
