# WS223 Cache Identity Contract

## pip caches (`actions/setup-python`, `cache: pip`)

Every step sets an explicit `cache-dependency-path`:

- Locked lanes: `requirements/lock.txt` + `pyproject.toml`. Any lock-byte
  change invalidates the cache, so a stale environment can never masquerade
  as the newly locked one. (The action default `**/requirements*.txt` would
  already match, but implicit matching is not a contract.)
- `windows-runtime.yml` (range-install exception): `pyproject.toml`.
- Docker-heavy H4 jobs intentionally set NO pip cache (documented
  Docker-overlay post-cache failure); they still install from the lock.

## Maven caches (`actions/setup-java`, `cache: maven`)

Keyed on `pom.xml` by the action; coherent with the `maven.compiler.release`
floor. No change required; recorded here so the inventory is complete.

## No other build caches

No card-data, generated-artifact, or custom caches with environment binding
were found. If one is introduced, it must key on `requirements/lock.txt`
(or the Maven equivalent) per this contract. Useful caching is preserved;
only masquerading is removed.

## Enforcement

`tests/unit/test_ws223_environment_identity.py` asserts explicit keys on
every pip-cache step and lock binding on every locked lane.
