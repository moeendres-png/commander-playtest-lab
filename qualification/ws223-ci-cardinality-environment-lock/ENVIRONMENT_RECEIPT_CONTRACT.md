# WS223 Environment Receipt Contract

## Producer

`scripts/write_environment_receipt.py --lane <lane> --output <path>`
(stdlib only; collects nothing ambient except the five named values below).

## Receipt contents

| Field | Source |
|---|---|
| `python_implementation` / `python_version` | `platform` module |
| `dependency_lock_digest` | sha256 of `requirements/lock.txt` (`null` if absent — itself a signal) |
| `resolved_dependency_set_digest` / `resolved_dependency_count` | sha256 over sorted `pip freeze --exclude-editable` |
| `java.runtime` / `java.java_home` | `java -version` + `$JAVA_HOME` |
| `container_image_ref` | `--image-ref` or `$WS223_IMAGE_REF` (`null` outside containers) |
| `pythonhashseed` | `$PYTHONHASHSEED` or `"unset"` |
| `tool_versions` | `importlib.metadata` for pip/setuptools/wheel/pytest/pydantic/PyYAML |
| `engine_pins` | `$XMAGE_COMMIT` + `config/rules_engines.json` primary commit |
| `repo_head` | `git rev-parse HEAD` |
| `identity_sha256` | sha256 over the canonical subset above (sorted, compact) |
| `generated_at` | informational only — excluded from `identity_sha256` |

## Guarantees

- No secrets: only named values are collected; the ambient environment is
  never dumped.
- No clock in identity: wall-clock appears once, outside the digest, so two
  runs of the same environment produce the same `identity_sha256`.
- Emitted by merge-gate lanes (`ci-quality`, `cardinality-conformance`)
  today; available to all lanes via the same command (rollout recorded in
  future work, not silently assumed).

## Enforcement

`tests/unit/test_ws223_environment_identity.py` executes the script against
a scratch output, re-verifies `identity_sha256` independently, and asserts
the schema keys.
