# WS223 Environment Identity Inventory (tip, 2026-09-15, independently verified)

## Python dependencies

| Layer | State | Verdict |
|---|---|---|
| `pyproject.toml [project].dependencies` | `pydantic>=2.10,<3`, `openpyxl>=3.1,<4`, `PyYAML>=6.0,<7`, `typer>=0.15,<1` (ranges) | NOT_LOCKED |
| `dev` extra | `pytest>=8.3,<10`, `pytest-asyncio>=1.4,<2`, `hypothesis>=6.120,<7`, `httpx2>=2.7,<3` (real on PyPI, verified), `jsonschema>=4.23,<5`, `ruff>=0.9,<1`, `mypy>=1.14,<2`, `types-openpyxl`, `types-PyYAML` | NOT_LOCKED |
| `api` extra | `fastapi>=0.115,<1`, `uvicorn>=0.34,<1` | NOT_LOCKED |
| `openai` extra | `openai>=2.45,<3`, `openai-agents>=0.18.3,<0.19` | NOT_LOCKED |
| `requirements/runtime.lock` | 6 pins, header disclaims non-transitive | NOT_LOCKED (transitively) |
| `requirements/quality-tools.*` | requested (bare names) + verified-upstream pins, no hashes | NOT_LOCKED (transitively) |
| Undeclared but imported | `jsonschema` used by `qualification/harness.py`; reachable only transitively (fragile) | GAP → folded into lock inputs explicitly with provenance note |

## Interpreters and JVM

| Identity | State |
|---|---|
| CI Python | `3.12` in all 16 workflows (coherent) |
| CI JDK (JVM lanes: conformance, external-integration, h4) | Temurin 17 via `setup-java` (major pin; patch floats, recorded per-run in receipt) |
| Bytecode authority | `engine-bridge/pom.xml: maven.compiler.release=17` → JDK floor is 17 |
| Containers (`docker/xmage`, `docker/forge`) | `FROM eclipse-temurin:21-jdk` floating; observed 2026-09-15 = manifest `sha256:1f79c734…` pushed 2026-09-10, newer than any `21.0.11_*` version tag → drift proven, no readable tag for these bytes |
| Local default | Ubuntu OpenJDK 21.0.12 (lane-independent; receipt will record actual) |

## PYTHONHASHSEED

Present (value `"0"`): `ci.yml`, `external-engine-integration.yml`,
`h4-docker-materialization.yml` (top + job), `xmage-full-game-conformance.yml`
= 4/16 files. Absent in 12, including `production-qualification.yml`
(runs `tests/qualification`), `core-workflow-acceptance.yml`,
`decision-support-regression.yml`, `windows-runtime.yml`. `opencode.yml` is an
agent lane with no Python execution → exempt (documented).

## Cache keys

- `setup-python cache: pip` in 15 files, none with explicit
  `cache-dependency-path` (implicit default `**/requirements*.txt`; lock must
  live under `requirements/` to stay matched, plus explicit key added).
- `setup-java cache: maven` (pom-bound automatically; coherent).
- No card-data/generated caches with lock binding found; Maven/card-data
  caches keyed on `pom.xml`/default paths — recorded, unchanged except pip.

## Receipts

None exist. No workflow emits a machine-readable environment receipt.
