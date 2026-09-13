# WS91 — Root-State Migration

## Pre-removal identity (verified before removal)

- Path: `.foundry/WORKSTREAM_STATE.yaml`
- Git blob: `6cf09d17cc141215efc8d1c06c5c0845b5f201ef`
- Content: historical WS-A1D-H4 Docker workstream state (schema 2.0,
  `ownership: WS-A1D-H4 session`, branch
  `architecture/ws-a1d-h4-docker-materialization-20260911`,
  `audit_base_sha: e207286200854bf9bff557e67bf3b37b5e428392`,
  `validated_head: 1aab012196b391260b2287f94cbcaa04f625e509`).
- It described the historical WS-A1D-H4 workstream and must not function as
  global/current Foundry ownership state.

## Archive (byte-identical, evidence only)

- Path: `research/architecture-closure/ws91-d1-current-main-integration/HISTORICAL-WS-A1D-H4-archived-root-state.yaml`
- Method: byte copy of the working-tree file before removal.
- Verified: `git hash-object` of the archive ==
  `6cf09d17cc141215efc8d1c06c5c0845b5f201ef` (identical to the audit-base root
  blob). `ROOT_STATE_ARCHIVE_BYTE_IDENTICAL = PASS`.
- The archived file is evidence only. It never becomes ownership authority:
  no tool, skill, agent, doc, or test reads it as live state
  (`ROOT_OPERATIONAL_STATE_PRESENT = 0` after removal).

## Removal

- `.foundry/WORKSTREAM_STATE.yaml` removed from the operational surface.
- Kept: `.foundry/WORKSTREAM_STATE.schema.json` (validator, still referenced
  by `tools/foundry/state.py` and the schema-kept regression test).
- Post-removal `.foundry/` contains schema/config only (verified by listing
  at validation time).

## Caller safety (explicit-state authority in force)

- `tools/foundry/launcher.py`: `--state` required; empty state refuses
  (`LAUNCH_REFUSED` / `ValueError`); no silent fallback.
- `tools/foundry/bootstrap.py`: `--state` required; `None` fails closed;
  `--init-state` writes only the explicit path; ownership conflicts fail closed.
- `tools/foundry/worktree_inventory.py`: ownership from the explicit
  `WORKTREE=STATE` map only (`--worktree-state`, repeatable); no map, missing
  file, or conventional root file alone yields `UNKNOWN`; malformed/conflicting
  maps fail closed.
- No `.opencode/**/*.md` file names `WORKSTREAM_STATE` anymore (verified by
  search). `AGENTS.md`, execution index, routing, resumability, skills, and
  agents name only the explicit dedicated state path.
- `tools/foundry/context_capsule.py` (WS78, unchanged) resolves explicit flag,
  then `FOUNDRY_STATE_PATH`, then a CWD default that fails closed with
  `CAPSULE_REJECT` when the root file is absent — never fabricated ownership.
- `tools/foundry/state.py` validator docstring still names the historical
  filename (unchanged schema tool, not an ownership fallback).
