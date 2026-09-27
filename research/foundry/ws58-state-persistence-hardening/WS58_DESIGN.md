# WS58 Bounded Design — Canonical State-Write Path

## Decision: extend `tools/foundry/state.py`, no new module

`state.py` already owns `validate()`, `migrate()`, and the ancestry checks, and
is stdlib+PyYAML-only. A separate `state_writer.py` would split the
validate-vs-write authority across two files and invite drift. All new code
lives in `state.py`; `bootstrap.py` only swaps its raw `write_text` for the
shared primitive. `safe_push.py` is untouched and keeps validating
independently (it must never trust writer provenance).

`src/commander_lab/storage/atomic.py` (tmp + fsync + `os.replace` + dir fsync)
is the in-repo precedent for the atomic pattern, but it is not importable from
the layer-separated foundry tools, so `state.py` carries a small self-contained
equivalent. No general configuration framework is created.

## Serialization choke point

- `dump_state(doc) -> str`: the ONLY serializer, `yaml.safe_dump(doc,
  sort_keys=False, allow_unicode=True)` on a parsed mapping. No string
  concatenation anywhere on the write path, so free-form scalars containing
  `:`, `#`, quotes, newlines, Unicode, brackets, or leading punctuation
  round-trip by construction (quoted/escaped by the serializer, never by hand).
- Inputs are parsed structures only: CLI `--write-from` / `--patch-file` read a
  file via `yaml.safe_load` (JSON is a subset of YAML, so one parser covers
  both); Python callers pass dicts. Non-mapping input is rejected.

## Validate-before-replace (`write_state`)

`write_state(state_path, doc, *, workdir=None, allow_identity_change=False)`:

1. `doc` must be a dict, else `StateWriteError` (a `ValueError`).
2. `errors = validate(doc)`; any error fails closed BEFORE touching disk.
   No coercion exists anywhere: `ARGENTUM_ENGINE_DEFECT` is rejected, never
   normalized to `ENGINE_DEFECT`.
3. Identity: if the on-disk file parses to a mapping, each of
   `IMMUTABLE_IDENTITY_FIELDS = (repository, worktree, branch, audit_base_sha,
   audit_base_tree)` must compare equal, else `StateWriteError`, unless
   `allow_identity_change=True` (the explicit rebind escape hatch; default
   refuses). If the on-disk file is missing or unparseable, identity cannot be
   compared, so replacement requires `allow_identity_change=True` (this is also
   the rescue path for a WS54-class corrupt file).
4. Validation credit: `validated_head` is taken exactly as given — never
   auto-promoted to HEAD. If `workdir` is supplied and `validated_head` is not
   null, it must descend from the proposed `audit_base_sha`
   (`VALIDATED_OUTSIDE_LOCK` otherwise) and be an ancestor-or-equal of live
   `HEAD` (`VALIDATED_REWRITTEN` otherwise), via `git merge-base
   --is-ancestor`. Without `workdir`, only SHA shape is checked (same as
   `validate()`); callers that claim validation credit must pass `workdir`.
5. Serialize via `dump_state`, persist via `atomic_write_text`, then read back
   and re-`validate()` the on-disk bytes (proves no malformed YAML was
   emitted). Returns the written mapping.

## Narrow checkpoint (`update_state`)

`update_state(state_path, patch, *, workdir=None, validated_head=_UNSET,
allow_identity_change=False)`:

- Loads the existing file (must parse to a mapping).
- `patch` must be a mapping of ordinary mutable fields. `"validated_head"` as
  a patch key is REJECTED — changing validation credit requires the explicit
  `validated_head=` parameter (`None` = honest null, `str` = claimed SHA).
  Omission (`_UNSET`) preserves the existing value: promotion is impossible by
  accident.
- Immutable fields in `patch` are rejected unless `allow_identity_change=True`.
- Merges and delegates to `write_state`, so every update gets validate +
  identity + ancestry + atomicity + readback.

Deliberately NOT provided: generic `--set key=value` CLI, unknown-field
rejection beyond `validate()` (forward-compat preserved), identity mutation
without the explicit flag, or any auto-stamping of `validated_head`.

## Atomic persistence (`atomic_write_text`)

Same-directory `tempfile.mkstemp(prefix=".<name>.")` → write → `flush()` →
`os.fsync()` → `os.replace()` → best-effort directory fsync → cleanup temp on
any failure. Directory-fsync adjudication: attempted always (Linux-safe via
`os.open(dir, O_RDONLY)`); failure is suppressed, never fatal — it is a
durability hint, while `os.replace` atomicity is the correctness guarantee. A
crash at any point leaves either the old complete file or the new complete
file, never a truncation. Existing file mode is preserved; new files use
`0o644` (repo convention for state YAML).

## CLI (flat flags, backward compatible)

- `--write-from INPUT` — full-document replacement from a JSON/YAML file.
- `--patch-file PATCH` — mapping of mutable updates merged onto the existing
  file (update mode; mutually exclusive with `--write-from`).
- `--set-validated-head SHA` / `--clear-validated-head` — explicit validation
  credit change (update mode only).
- `--stamp-head` — set `state_written_against_head` from live `--workdir`
  HEAD (update mode only; requires `--workdir`). Descriptive stamp only, never
  a validation claim.
- `--allow-identity-change` — explicit rebind for either mode.
- `--workdir` reused for ancestry checks. Exit `0` + `STATE_WRITTEN` on
  success; nonzero + `STATE_REJECT: <reason>` with the prior file
  byte-identical on any failure.
- `--migrate --in-place` is reimplemented on top of validate-before-replace +
  atomic write (semantics preserved: `validated_head` reset to null).

## Integration

- `bootstrap.py --init-state`: `init_state()` constructor unchanged; the
  `Path.write_text(yaml.safe_dump(doc))` becomes
  `state_mod.write_state(path, doc, workdir=...)` (create path; `validated_head`
  null so ancestry is vacuous, validation + atomicity now enforced).
- `safe_push.py`: no changes; independent validation retained.
- Launcher semantics: unchanged.
