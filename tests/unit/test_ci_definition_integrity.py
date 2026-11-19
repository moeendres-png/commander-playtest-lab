from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_required_check_definitions.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci-definition-integrity.yml"

spec = importlib.util.spec_from_file_location("ci_definition_integrity", SCRIPT)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

PIN = "a" * 40

CI_YAML = f"""name: CI
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - uses: ./.github/actions/quality-bootstrap
      - name: Ruff lint
        run: ruff check .
      - name: Ruff format
        if: ${{{{ success() || failure() }}}}
        run: ruff format --check .
      - name: Mypy strict
        if: ${{{{ success() || failure() }}}}
        run: |
          set -o pipefail
          mypy src/commander_lab | tee mypy.txt
      - name: Test suite
        if: ${{{{ success() || failure() }}}}
        run: pytest -q
      - name: Compile
        if: ${{{{ success() || failure() }}}}
        run: python -m compileall -q src tests
      - name: Secret-pattern scan
        if: ${{{{ success() || failure() }}}}
        run: |
          matches="$(git grep -n secret || true)"
          if [[ -n "$matches" ]]; then
            echo "Potential secret material found."
            exit 1
          fi
      - name: Build wheel
        if: ${{{{ success() || failure() }}}}
        run: python -m pip wheel --no-deps --wheel-dir dist .
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - name: Dependency audit
        run: pip-audit --strict --no-deps -r requirements.txt
      - name: CycloneDX SBOM
        run: cyclonedx-py environment --output-format JSON --output-file sbom.json
      - name: License report
        run: pip-licenses --format=json --output-file=licenses.json
"""

PRODUCTION_YAML = f"""name: Production Qualification
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
jobs:
  infrastructure:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - name: Validate qualification infrastructure
        run: pytest -q tests/qualification
      - name: Validate canonical fixture manifest
        run: python qualification/harness.py validate qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json
"""

LOCAL_ACTION_YAML = f"""name: quality bootstrap
runs:
  using: composite
  steps:
    - uses: actions/setup-python@{PIN}
      with:
        python-version: "3.12"
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=CI02 Fixture",
            "-c",
            "user.email=ci02@example.invalid",
            *args,
        ],
        text=True,
    ).strip()


def write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def yaml_doc(path: Path) -> dict[Any, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def write_yaml(path: Path, document: dict[Any, Any]) -> None:
    rendered = yaml.safe_dump(document, sort_keys=False)
    # PyYAML 1.1 treats the GitHub Actions key "on" as boolean True.
    rendered = re.sub(r"^true:", "on:", rendered, count=1, flags=re.MULTILINE)
    path.write_text(rendered, encoding="utf-8")


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    git(tmp_path, "init", "-q")
    write(tmp_path, ".github/workflows/ci.yml", CI_YAML)
    write(tmp_path, ".github/workflows/production-qualification.yml", PRODUCTION_YAML)
    write(
        tmp_path,
        ".github/workflows/repository-tree-integrity.yml",
        "name: trusted tree guard\n",
    )
    write(
        tmp_path,
        ".github/workflows/ci-definition-integrity.yml",
        "name: trusted definition guard\n",
    )
    write(tmp_path, "scripts/verify_repository_tree.py", "# trusted\n")
    write(tmp_path, "scripts/verify_required_check_definitions.py", "# trusted\n")
    write(tmp_path, ".github/actions/quality-bootstrap/action.yml", LOCAL_ACTION_YAML)
    write(tmp_path, "pyproject.toml", "[build-system]\nrequires=[]\n")
    write(tmp_path, "requirements/lock.txt", "# fixture\n")
    write(tmp_path, "qualification/harness.py", "# fixture harness\n")
    write(tmp_path, "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json", "{}\n")
    write(
        tmp_path,
        "qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json",
        "{}\n",
    )
    write(tmp_path, "tests/qualification/test_fixture.py", "def test_fixture(): assert True\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "trusted base")
    return tmp_path, git(tmp_path, "rev-parse", "HEAD")


def candidate(
    repository: Path,
    base: str,
    mutate: Callable[[Path], None],
    message: str,
) -> str:
    git(repository, "reset", "--hard", base)
    mutate(repository)
    git(repository, "add", "-A")
    git(repository, "commit", "-qm", message)
    head = git(repository, "rev-parse", "HEAD")
    # The validator receives the candidate commit object while the working tree
    # remains on trusted base. Candidate contents are never checked out by it.
    git(repository, "reset", "--hard", base)
    return head


def classification(repository: Path, base: str, head: str) -> str:
    return guard.inspect_required_check_definitions(repository, base, head)[
        "overall_classification"
    ]


def mutate_yaml(repo: Path, relative: str, edit: Callable[[dict[Any, Any]], None]) -> None:
    path = repo / relative
    document = yaml_doc(path)
    edit(document)
    write_yaml(path, document)


def events(document: dict[Any, Any]) -> dict[str, Any]:
    value = document.get("on", document.get(True))
    assert isinstance(value, dict)
    return value


def remove_step_containing(document: dict[Any, Any], job: str, needle: str) -> None:
    steps = document["jobs"][job]["steps"]
    document["jobs"][job]["steps"] = [
        step for step in steps if needle not in str(step.get("run", ""))
    ]


def test_fixture_trusted_base_passes(repository: tuple[Path, str]) -> None:
    repo, base = repository
    report = guard.inspect_required_check_definitions(repo, base, base)
    assert report["overall_classification"] == "PASS"
    assert report["candidate_code_executed"] is False


def test_real_repository_current_tree_positive_control() -> None:
    head = git(ROOT, "rev-parse", "HEAD")
    report = guard.inspect_required_check_definitions(ROOT, head, head)
    assert report["overall_classification"] == "PASS", json.dumps(report, indent=2, sort_keys=True)
    assert report["trusted_validator"]["tree"] == git(ROOT, "rev-parse", "HEAD^{tree}")
    assert report["comparison_base"]["tree"] == report["trusted_validator"]["tree"]
    assert report["candidate"]["tree"] == report["trusted_validator"]["tree"]


def test_harmless_unprotected_documentation_change_passes(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, "docs/harmless.md", "documentation only\n"),
        "docs only",
    )
    assert classification(repo, base, head) == "PASS"


def test_quality_job_removed_fails(repository: tuple[Path, str]) -> None:
    repo, base = repository

    def mutate(root: Path) -> None:
        mutate_yaml(root, ".github/workflows/ci.yml", lambda d: d["jobs"].pop("quality"))

    head = candidate(repo, base, mutate, "remove quality")
    assert classification(repo, base, head) == "FAIL"


def test_quality_trivial_success_fails(repository: tuple[Path, str]) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"] = [{"name": "fake", "run": "echo PASS"}]

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", edit),
        "trivial quality",
    )
    assert classification(repo, base, head) == "FAIL"


@pytest.mark.parametrize("needle", ["pytest -q", "mypy src/commander_lab"])
def test_quality_core_command_removed_fails(repository: tuple[Path, str], needle: str) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        remove_step_containing(document, "quality", needle)

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", edit),
        f"remove {needle}",
    )
    assert classification(repo, base, head) == "FAIL"


def test_continue_on_error_on_required_job_fails(repository: tuple[Path, str]) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["continue-on-error"] = True

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", edit),
        "mask quality",
    )
    assert classification(repo, base, head) == "FAIL"


def test_pull_request_trigger_removed_fails(repository: tuple[Path, str]) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        events(document).pop("pull_request")

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", edit),
        "remove pr trigger",
    )
    assert classification(repo, base, head) == "FAIL"


@pytest.mark.parametrize(
    ("workflow", "job"),
    [
        (".github/workflows/ci.yml", "security"),
        (".github/workflows/production-qualification.yml", "infrastructure"),
    ],
)
def test_required_job_replaced_by_echo_pass_fails(
    repository: tuple[Path, str], workflow: str, job: str
) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        document["jobs"][job]["steps"] = [{"name": "fake", "run": "echo PASS"}]

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, workflow, edit),
        f"trivialize {job}",
    )
    assert classification(repo, base, head) == "FAIL"


def test_mutable_third_party_action_tag_fails(repository: tuple[Path, str]) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"][0]["uses"] = "actions/checkout@v5"

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", edit),
        "mutable action",
    )
    assert classification(repo, base, head) == "FAIL"


def test_consumed_local_action_change_requires_review(repository: tuple[Path, str]) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(
            root,
            ".github/actions/quality-bootstrap/action.yml",
            LOCAL_ACTION_YAML + "# candidate edit\n",
        ),
        "change consumed action",
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert any(
        item["impact"] == "required_workflow_consumed_local_action"
        for item in report["changed_protected_surfaces"]
    )


def test_candidate_cannot_replace_or_execute_trusted_validator(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(
            root,
            "scripts/verify_required_check_definitions.py",
            "raise RuntimeError('candidate validator executed')\n",
        ),
        "replace validator",
    )
    before_head = git(repo, "rev-parse", "HEAD")
    before_status = git(repo, "status", "--porcelain")
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert report["candidate_code_executed"] is False
    assert git(repo, "rev-parse", "HEAD") == before_head == base
    assert git(repo, "status", "--porcelain") == before_status == ""


def test_unknown_relevant_workflow_construction_is_not_pass(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository

    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"] = "${{ fromJSON(vars.REQUIRED_STEPS) }}"

    head = candidate(
        repo,
        base,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", edit),
        "dynamic steps",
    )
    assert classification(repo, base, head) == "UNKNOWN"


def test_source_bound_machine_report(repository: tuple[Path, str], tmp_path: Path) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, "docs/report-control.md", "control\n"),
        "report control",
    )
    output = tmp_path / "CI_DEFINITION_INTEGRITY.json"
    assert (
        guard.main(
            [
                "--repo",
                str(repo),
                "--base",
                base,
                "--head",
                head,
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["trusted_validator"] == {
        "sha": base,
        "tree": git(repo, "rev-parse", f"{base}^{{tree}}"),
    }
    assert report["comparison_base"] == {
        "sha": base,
        "tree": git(repo, "rev-parse", f"{base}^{{tree}}"),
        "derivation": "explicit_single_base",
    }
    assert report["candidate"] == {
        "sha": head,
        "tree": git(repo, "rev-parse", f"{head}^{{tree}}"),
    }
    assert report["candidate_code_executed"] is False
    assert report["inspected_files"]
    assert report["invariant_results"]


def test_shadow_workflow_executes_trusted_base_only() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    trigger = document.get("on", document.get(True))
    assert isinstance(trigger, dict)
    assert set(trigger) == {"pull_request_target"}
    pr_target = trigger["pull_request_target"]
    assert pr_target["branches"] == ["main"]
    assert set(pr_target["types"]) == {
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
        "edited",
    }
    assert document["permissions"] == {"contents": "read"}

    steps = document["jobs"]["ci-definition-integrity-shadow"]["steps"]
    checkouts = [step for step in steps if "actions/checkout@" in step.get("uses", "")]
    assert len(checkouts) == 1
    checkout = checkouts[0]
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    # Full history, so the validator can derive the trusted/candidate merge base.
    assert checkout["with"]["fetch-depth"] == 0

    inspect = next(step for step in steps if step.get("id") == "inspect")
    assert inspect["env"]["TRUSTED_SHA"] == "${{ github.sha }}"
    assert "BASE_SHA" not in inspect["env"]
    assert inspect["env"]["BASE_REF"] == "${{ github.event.pull_request.base.ref }}"
    assert inspect["env"]["CANDIDATE_SHA"] == "${{ github.event.pull_request.head.sha }}"
    assert inspect["env"]["PR_NUMBER"] == "${{ github.event.pull_request.number }}"
    assert 'git fetch --no-tags origin "refs/pull/$PR_NUMBER/head"' in inspect["run"]
    assert '--trusted "$TRUSTED_SHA"' in inspect["run"]
    assert "--base" not in inspect["run"]
    assert 'test "$BASE_REF" = "main"' in inspect["run"]
    assert 'test "$(git rev-parse FETCH_HEAD)" = "$CANDIDATE_SHA"' in inspect["run"]
    assert "github.event.pull_request.base.sha" not in WORKFLOW.read_text(encoding="utf-8")
    assert "git checkout" not in inspect["run"]
    assert "git switch" not in inspect["run"]

    for step in steps:
        run = step.get("run", "")
        assert "${{ github.event.pull_request.head" not in run


@pytest.mark.parametrize(
    "mutation",
    [
        "quality_removed",
        "quality_trivial",
        "pytest_removed",
        "mypy_removed",
        "continue_on_error",
        "pr_trigger_removed",
        "security_trivial",
        "infrastructure_trivial",
        "mutable_action",
        "critical_local_action_changed",
        "validator_changed",
        "unknown_dynamic_steps",
        "pr_path_filter",
        "pr_types_closed",
        "job_name_changed",
        "job_needs",
        "job_if_false",
        "custom_shell",
        "pytest_masked_exit_zero",
    ],
)
def test_required_mutation_campaign_never_silently_passes(
    repository: tuple[Path, str], mutation: str
) -> None:
    repo, base = repository

    def mutate(root: Path) -> None:
        if mutation == "critical_local_action_changed":
            write(
                root,
                ".github/actions/quality-bootstrap/action.yml",
                LOCAL_ACTION_YAML + "# mutation\n",
            )
            return
        if mutation == "validator_changed":
            write(
                root,
                "scripts/verify_required_check_definitions.py",
                "raise RuntimeError('must not execute')\n",
            )
            return

        workflow = (
            ".github/workflows/production-qualification.yml"
            if mutation == "infrastructure_trivial"
            else ".github/workflows/ci.yml"
        )

        def edit(document: dict[Any, Any]) -> None:
            if mutation == "quality_removed":
                document["jobs"].pop("quality")
            elif mutation == "quality_trivial":
                document["jobs"]["quality"]["steps"] = [{"run": "echo PASS"}]
            elif mutation == "pytest_removed":
                remove_step_containing(document, "quality", "pytest -q")
            elif mutation == "mypy_removed":
                remove_step_containing(document, "quality", "mypy src/commander_lab")
            elif mutation == "continue_on_error":
                document["jobs"]["quality"]["continue-on-error"] = True
            elif mutation == "pr_trigger_removed":
                events(document).pop("pull_request")
            elif mutation == "security_trivial":
                document["jobs"]["security"]["steps"] = [{"run": "echo PASS"}]
            elif mutation == "infrastructure_trivial":
                document["jobs"]["infrastructure"]["steps"] = [{"run": "echo PASS"}]
            elif mutation == "mutable_action":
                document["jobs"]["quality"]["steps"][0]["uses"] = "actions/checkout@v5"
            elif mutation == "unknown_dynamic_steps":
                document["jobs"]["quality"]["steps"] = "${{ fromJSON(vars.REQUIRED_STEPS) }}"
            elif mutation == "pr_path_filter":
                events(document)["pull_request"] = {"paths": ["docs/**"]}
            elif mutation == "pr_types_closed":
                events(document)["pull_request"] = {"types": ["closed"]}
            elif mutation == "job_name_changed":
                document["jobs"]["quality"]["name"] = "not-quality"
            elif mutation == "job_needs":
                document["jobs"]["quality"]["needs"] = "candidate-controlled-preflight"
            elif mutation == "job_if_false":
                document["jobs"]["quality"]["if"] = False
            elif mutation in {"custom_shell", "pytest_masked_exit_zero"}:
                step = next(
                    item
                    for item in document["jobs"]["quality"]["steps"]
                    if "pytest -q" in str(item.get("run", ""))
                )
                if mutation == "custom_shell":
                    step["shell"] = "bash {0}"
                else:
                    step["run"] = "pytest -q || exit 0"
            else:
                raise AssertionError(mutation)

        mutate_yaml(root, workflow, edit)

    head = candidate(repo, base, mutate, f"mutation {mutation}")
    assert classification(repo, base, head) in {
        "FAIL",
        "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED",
        "UNKNOWN",
    }


def test_chained_required_command_is_recognized_as_command_segment() -> None:
    run = "mkdir -p artifacts/security && cyclonedx-py environment --output-format JSON"
    assert guard._matching_command_is_enforcing(run, guard.CATEGORY_PATTERNS["sbom"])


def test_critical_command_or_success_masking_is_not_enforcing() -> None:
    assert not guard._matching_command_is_enforcing(
        "pytest -q || exit 0", guard.CATEGORY_PATTERNS["pytest"]
    )


def test_added_test_is_reported_but_needs_no_review(repository: tuple[Path, str]) -> None:
    # Package B (2026-11-14, Owner): a new test module cannot weaken a gate, so it no longer
    # makes the shadow check red; the report still lists it.
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(
            root, "tests/unit/test_new_gate_signal.py", "def test_signal(): assert True\n"
        ),
        "add quality test",
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "PASS"
    assert report["benign_test_changes"] == ["tests/unit/test_new_gate_signal.py"]
    assert any(
        item["impact"] == "test_added_no_review_needed"
        for item in report["changed_protected_surfaces"]
    )
    assert guard._exit_code(report["overall_classification"]) == 0


def _qualification_test(root: Path, text: str) -> None:
    write(root, "tests/qualification/test_fixture.py", text)


BASE_TEST = "def test_fixture(): assert True\n"


@pytest.mark.parametrize(
    "new_text",
    [
        BASE_TEST + "def test_more(): assert 1 == 1\n",  # a plain test function appended
        "import os\n"
        + BASE_TEST
        + "def test_more(): assert os.sep\n",  # import of a non-test module
        BASE_TEST
        + "import pytest\n@pytest.mark.parametrize('x', [1, 2])\ndef test_p(x, y=3): assert x\n",
        BASE_TEST + "import pytest\n@pytest.mark.slow\ndef test_marked(): assert True\n",
        "# a comment\n" + BASE_TEST,
    ],
)
def test_appended_plain_test_function_needs_no_review(
    repository: tuple[Path, str], new_text: str
) -> None:
    repo, base = repository
    head = candidate(repo, base, lambda root: _qualification_test(root, new_text), "extend")
    assert classification(repo, base, head) == "PASS"


@pytest.mark.parametrize(
    "new_text",
    [
        "def test_other(): assert True\n",  # test_fixture removed
        "def test_renamed(): assert True\n",  # renamed
        "def test_fixture(): pass\n",  # assertion dropped
        "def test_fixture():\n    assert True\n    assert 2 > 1\n",  # existing body changed, even if stronger
        "def test_fixture():\n    return\n    assert True\n",  # early return
        "def test_fixture():\n    assert True is True\n",
        "import pytest\n@pytest.mark.skip\ndef test_fixture(): assert True\n",
        "import pytest\n@getattr(pytest.mark, 'skip')\ndef test_fixture(): assert True\n",
        "import pytest\n@pytest.mark.parametrize('x', [1])\ndef test_fixture(x=1): assert True\n",
        BASE_TEST + "import pytest\npytestmark = pytest.mark.skip\n",  # module-wide skip
        BASE_TEST + "def test_fixture(): pass\n",  # redefinition shadows the real test
        BASE_TEST + "if True:\n    pass\n",  # new module-level code
        BASE_TEST + "import os\nLIMIT = 3\n",  # a constant is not an allowed addition
        BASE_TEST + "def _helper(): return 1\n",  # nor is a helper function
        BASE_TEST + "class TestMore:\n    def test_a(self): assert True\n",  # nor a class
        # Probe (1): an added autouse fixture that skips every test of the module.
        BASE_TEST
        + "import pytest\n@pytest.fixture(autouse=True)\ndef _skip_all():\n    pytest.skip('x')\n",
        # Probe (2): an added setup_module.
        BASE_TEST
        + "import pytest\ndef setup_module(module):\n    pytest.skip('x', allow_module_level=True)\n",
        # Probe (3): an added class whose body rewrites the module namespace.
        BASE_TEST + "class _Neuter:\n    globals().update({'test_fixture': lambda: None})\n",
        # Probe (4): a decorator with a side effect on a new helper function.
        BASE_TEST
        + "def _hit(f):\n    globals().update({'test_fixture': lambda: None})\n    return f\n@_hit\ndef _helper(): pass\n",
        # The same decorator on a new test function.
        BASE_TEST + "def _hit(f):\n    return f\n@_hit\ndef test_x(): assert True\n",
        # Probe (6): a star import.
        "from os.path import *\n" + BASE_TEST,
        BASE_TEST + "from os.path import *\n",
        BASE_TEST + "from tests.unit import test_other\n",  # an import of another test module
        BASE_TEST + "from . import helpers\n",  # a relative import
        BASE_TEST
        + "import pytest\n@pytest.mark.skip\ndef test_x(): assert True\n",  # a skip marker
        BASE_TEST + "import pytest\n@pytest.mark.usefixtures('f')\ndef test_x(): assert True\n",
        BASE_TEST + "def test_x(a=print('side effect')): assert True\n",  # non-literal default
        BASE_TEST + "def test_x():\n    globals().update({'test_fixture': lambda: None})\n",
        BASE_TEST + "pytestmark = 1\n",
        BASE_TEST + "def pytest_collection_modifyitems(items): items.clear()\n",
        BASE_TEST + "__test__ = False\n",
        "def test_fixture(: syntax error\n",
    ],
)
def test_weakened_test_still_requires_review(repository: tuple[Path, str], new_text: str) -> None:
    repo, base = repository
    head = candidate(repo, base, lambda root: _qualification_test(root, new_text), "weaken test")
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert report["benign_test_changes"] == []


PARAM_BASE = "import pytest\nCASES = [1, 2, 3]\n@pytest.mark.parametrize('x', CASES)\ndef test_p(x): assert x\n"


@pytest.mark.parametrize(
    "new_text",
    [
        PARAM_BASE.replace("[1, 2, 3]", "[1]"),  # shrunk parametrize list
        PARAM_BASE.replace("CASES, ", "").replace("'x', CASES", "'x', [1]"),
        PARAM_BASE.replace("import pytest\n", "import pytest\nimport os\n") + "CASES = [1]\n",
    ],
)
def test_shrunk_parametrization_still_requires_review(
    repository: tuple[Path, str], new_text: str
) -> None:
    repo, base = repository

    def mutate(root: Path) -> None:
        _qualification_test(root, PARAM_BASE)

    base_with_params = candidate(repo, base, mutate, "param base")
    head = candidate(
        repo, base_with_params, lambda root: _qualification_test(root, new_text), "shrink"
    )
    report = guard.inspect_required_check_definitions(repo, base_with_params, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def test_new_test_file_needs_no_review(repository: tuple[Path, str]) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, "tests/unit/test_brand_new.py", "def test_new(): assert True\n"),
        "new file",
    )
    assert classification(repo, base, head) == "PASS"


# The runner and lists of the required test checks are gate inputs, never benign.
@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("tests/pytest_shards.py", "def exit_status(codes):\n    return 0\n"),  # probe (a)
        ("tests/pytest_docs_tests.json", '{"files": ["tests/unit/test_one.py"]}\n'),  # probe (c)
        ("scripts/ci_change_scope.py", "# changed\n"),
        ("scripts/ci_gate.py", "# changed\n"),
        ("tests/conftest.py", "import pytest\n"),
        ("tests/unit/helpers.py", "VALUE = 1\n"),  # a non-test helper under tests/
        ("tests/unit/conftest.py", "import pytest\n"),
    ],
)
def test_gate_inputs_under_tests_and_scripts_always_require_review(
    repository: tuple[Path, str], path: str, text: str
) -> None:
    repo, base = repository
    head = candidate(repo, base, lambda root: write(root, path, text), "gate input")
    assert classification(repo, base, head) == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def test_every_assert_replaced_by_assert_true_requires_review(
    repository: tuple[Path, str],
) -> None:
    # Probe (b): the assertion count per file stays the same, the strength does not.
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: _qualification_test(root, "def test_fixture(): assert True is not False\n"),
        "assert true",
    )
    assert classification(repo, base, head) == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def test_weight_table_change_needs_no_review(repository: tuple[Path, str]) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, "tests/pytest_shard_weights.json", '{"files": {}}\n'),
        "weights",
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "PASS"
    assert report["benign_test_changes"] == ["tests/pytest_shard_weights.json"]


def test_removed_test_file_still_requires_review(repository: tuple[Path, str]) -> None:
    repo, base = repository
    head = candidate(
        repo, base, lambda root: (root / "tests/qualification/test_fixture.py").unlink(), "remove"
    )
    assert classification(repo, base, head) == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def test_conftest_and_other_test_data_still_require_review(repository: tuple[Path, str]) -> None:
    repo, base = repository
    for path in ("tests/conftest.py", "tests/unit/data.json", "tests/pytest_docs_tests.json"):
        head = candidate(repo, base, lambda root, p=path: write(root, p, "x = 1\n"), "control")
        assert classification(repo, base, head) == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED", path


def test_a_gate_script_change_still_requires_review(repository: tuple[Path, str]) -> None:
    repo, base = repository
    head = candidate(
        repo, base, lambda root: write(root, "scripts/ci_gate.py", "# changed\n"), "gate script"
    )
    assert classification(repo, base, head) == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def test_a_removed_test_in_a_mixed_change_keeps_the_review_requirement(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository

    def mutate(root: Path) -> None:
        write(root, "tests/unit/test_new.py", "def test_a(): assert True\n")
        (root / "tests/qualification/test_fixture.py").unlink()

    head = candidate(repo, base, mutate, "mixed")
    assert classification(repo, base, head) == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


@pytest.mark.parametrize(
    "run",
    [
        "pytest -q || true",
        "pytest -q || exit 0",
        "pytest -q || echo PASS",
        "pytest -q; true",
        "pytest -q; exit 0",
    ],
)
def test_critical_command_success_masking_is_not_enforcing(run: str) -> None:
    assert not guard._matching_command_is_enforcing(run, guard.CATEGORY_PATTERNS["pytest"])


@pytest.mark.parametrize(
    ("path", "impact"),
    [
        ("conftest.py", "pytest_control_surface"),
        ("src/ruff.toml", "quality_tool_configuration"),
        ("tools/pyproject.toml", "quality_tool_configuration"),
    ],
)
def test_quality_control_surface_change_requires_review(
    repository: tuple[Path, str], path: str, impact: str
) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, path, "# candidate quality control surface\n"),
        f"change {path}",
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert any(
        item["path"] == path and item["impact"] == impact
        for item in report["changed_protected_surfaces"]
    )


# --------------------------------------------------------------------------- #
# Three identities: trusted validator source, comparison base, candidate
# --------------------------------------------------------------------------- #


def _commit(repo: Path, mutate: Callable[[Path], None], message: str) -> str:
    mutate(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def stale_history(repository: tuple[Path, str]) -> dict[str, str]:
    """A candidate that forked from main before main kept evolving.

    fork -- candidate (docs only)
       \
        main1 (main tightens ci.yml) -- main2 (main docs) = trusted
    """
    repo, fork = repository
    git(repo, "checkout", "-q", "-b", "candidate-branch")
    candidate_sha = _commit(
        repo, lambda root: write(root, "docs/candidate.md", "candidate\n"), "candidate docs"
    )
    git(repo, "checkout", "-q", "-")

    def tighten(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["timeout-minutes"] = 29

    _commit(
        repo,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", tighten),
        "main tightens ci",
    )
    trusted = _commit(
        repo, lambda root: write(root, "docs/main-later.md", "main\n"), "main docs later"
    )
    return {"fork": fork, "candidate": candidate_sha, "trusted": trusted}


def test_stale_candidate_is_measured_from_its_merge_base_not_current_main(
    repository: tuple[Path, str], stale_history: dict[str, str]
) -> None:
    repo, _ = repository
    report = guard.inspect_candidate(repo, stale_history["trusted"], stale_history["candidate"])
    assert report["overall_classification"] == "PASS", report["reasons"]
    assert report["trusted_validator"]["sha"] == stale_history["trusted"]
    assert report["comparison_base"]["sha"] == stale_history["fork"]
    assert report["comparison_base"]["derivation"] == "merge_base"
    assert report["candidate"]["sha"] == stale_history["candidate"]
    # Only the candidate's own change; main's later ci.yml change is not its.
    assert report["changed_files"] == ["docs/candidate.md"]
    assert report["candidate_code_executed"] is False


def test_fail_before_current_main_as_comparison_base_misattributes_main_changes(
    repository: tuple[Path, str], stale_history: dict[str, str]
) -> None:
    """The single-base diff against current main charges the candidate with
    main's own later workflow change: the false positive the merge base removes."""
    repo, _ = repository
    report = guard.inspect_required_check_definitions(
        repo, stale_history["trusted"], stale_history["candidate"]
    )
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert ".github/workflows/ci.yml" in report["changed_files"]


def test_stale_candidate_changing_a_required_workflow_is_never_pass(
    repository: tuple[Path, str], stale_history: dict[str, str]
) -> None:
    repo, _ = repository
    git(repo, "checkout", "-q", stale_history["candidate"])

    def trivialize(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"] = [{"run": "echo PASS"}]

    mutated = _commit(
        repo,
        lambda root: mutate_yaml(root, ".github/workflows/ci.yml", trivialize),
        "trivialize quality",
    )
    git(repo, "checkout", "-q", stale_history["trusted"])
    report = guard.inspect_candidate(repo, stale_history["trusted"], mutated)
    assert report["overall_classification"] in {"FAIL", "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"}
    assert report["comparison_base"]["sha"] == stale_history["fork"]


def test_stale_candidate_replacing_the_validator_is_never_pass_nor_executed(
    repository: tuple[Path, str], stale_history: dict[str, str]
) -> None:
    repo, _ = repository
    git(repo, "checkout", "-q", stale_history["candidate"])
    replaced = _commit(
        repo,
        lambda root: write(
            root,
            "scripts/verify_required_check_definitions.py",
            "raise SystemExit('candidate validator executed')\n",
        ),
        "replace validator",
    )
    git(repo, "checkout", "-q", stale_history["trusted"])
    before = git(repo, "status", "--porcelain")
    report = guard.inspect_candidate(repo, stale_history["trusted"], replaced)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert (
        "trusted_policy_changed:scripts/verify_required_check_definitions.py" in (report["reasons"])
    )
    assert report["candidate_code_executed"] is False
    assert git(repo, "rev-parse", "HEAD") == stale_history["trusted"]
    assert git(repo, "status", "--porcelain") == before


def test_candidate_that_merged_main_is_measured_from_the_merged_main(
    repository: tuple[Path, str], stale_history: dict[str, str]
) -> None:
    repo, _ = repository
    git(repo, "checkout", "-q", stale_history["candidate"])
    git(repo, "merge", "-q", "--no-edit", stale_history["trusted"])
    merged = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", stale_history["trusted"])
    report = guard.inspect_candidate(repo, stale_history["trusted"], merged)
    assert report["comparison_base"]["sha"] == stale_history["trusted"]
    assert report["changed_files"] == ["docs/candidate.md"]
    assert report["overall_classification"] == "PASS"


def test_no_unique_comparison_base_fails_closed(repository: tuple[Path, str]) -> None:
    repo, base = repository
    git(repo, "checkout", "-q", "--orphan", "unrelated")
    git(repo, "rm", "-rqf", ".")
    unrelated = _commit(repo, lambda root: write(root, "README.md", "x\n"), "unrelated root")
    git(repo, "checkout", "-q", "-f", base)
    report = guard.inspect_candidate(repo, base, unrelated)
    assert report["overall_classification"] == "UNKNOWN"
    assert report["reasons"][0].startswith("comparison_base_")
    assert report["candidate_code_executed"] is False


def test_cli_three_identity_mode_writes_a_source_bound_report(
    repository: tuple[Path, str], stale_history: dict[str, str], tmp_path: Path
) -> None:
    repo, _ = repository
    output = tmp_path / "CI_DEFINITION_INTEGRITY.json"
    code = guard.main(
        [
            "--repo",
            str(repo),
            "--trusted",
            stale_history["trusted"],
            "--head",
            stale_history["candidate"],
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert report["schema_version"] == 2
    assert {key: report[key]["sha"] for key in ("trusted_validator", "comparison_base")} == {
        "trusted_validator": stale_history["trusted"],
        "comparison_base": stale_history["fork"],
    }
    for key in ("trusted_validator", "comparison_base", "candidate"):
        assert report[key]["tree"] == git(repo, "rev-parse", f"{report[key]['sha']}^{{tree}}")


# --------------------------------------------------------------------------- #
# A required job that is a gate over other jobs (`needs`): precise acceptance.
# --------------------------------------------------------------------------- #

GATED_CI_YAML = f"""name: CI
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      packaging: ${{{{ steps.scope.outputs.packaging }}}}
    steps:
      - uses: actions/checkout@{PIN}
      - id: scope
        run: python3 scripts/ci_change_scope.py
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - uses: ./.github/actions/quality-bootstrap
      - name: Ruff lint
        run: ruff check .
      - name: Ruff format
        if: ${{{{ success() || failure() }}}}
        run: ruff format --check .
      - name: Mypy strict
        if: ${{{{ success() || failure() }}}}
        run: |
          set -o pipefail
          mypy src/commander_lab | tee mypy.txt
      - name: Compile
        if: ${{{{ success() || failure() }}}}
        run: python -m compileall -q src tests
      - name: Secret-pattern scan
        if: ${{{{ success() || failure() }}}}
        run: |
          matches="$(git grep -n secret || true)"
          if [[ -n "$matches" ]]; then
            echo "Potential secret material found."
            exit 1
          fi
      - name: Build wheel
        if: ${{{{ success() || failure() }}}}
        run: python -m pip wheel --no-deps --wheel-dir dist .
  tests:
    needs: changes
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix: ${{{{ fromJSON(needs.changes.outputs.test_matrix) }}}}
    steps:
      - uses: actions/checkout@{PIN}
      - name: Test suite
        run: |
          set -euo pipefail
          pytest -q --shards=4 tests/unit
  packaging:
    needs: changes
    if: ${{{{ needs.changes.outputs.packaging == 'true' }}}}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - run: python scripts/verify_packaging_smoke.py smoke
  quality:
    if: always()
    needs: [changes, lint, tests, packaging]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - name: Every needed job succeeded
        shell: bash
        env:
          CHANGES: ${{{{ needs.changes.result }}}}
          LINT: ${{{{ needs.lint.result }}}}
          TESTS: ${{{{ needs.tests.result }}}}
          PACKAGING: ${{{{ needs.packaging.result }}}}
          PACKAGING_NEEDED: ${{{{ needs.changes.outputs.packaging }}}}
        run: |
          set -euo pipefail
          python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" --job tests="$TESTS" --job packaging="$PACKAGING" --allow-skipped packaging --packaging-needed "$PACKAGING_NEEDED"
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PIN}
      - name: Dependency audit
        run: pip-audit --strict --no-deps -r requirements.txt
      - name: CycloneDX SBOM
        run: cyclonedx-py environment --output-format JSON --output-file sbom.json
      - name: License report
        run: pip-licenses --format=json --output-file=licenses.json
"""


def _gated_report(
    repository: tuple[Path, str], edit: Callable[[dict[Any, Any]], None] | None = None
) -> dict[str, Any]:
    repo, base = repository

    def mutate(root: Path) -> None:
        write(root, ".github/workflows/ci.yml", GATED_CI_YAML)
        if edit is not None:
            mutate_yaml(root, ".github/workflows/ci.yml", edit)

    head = candidate(repo, base, mutate, "gated quality")
    return guard.inspect_required_check_definitions(repo, base, head)


def _quality_findings(report: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        item["id"]: item
        for item in report["invariant_results"]
        if str(item["id"]).startswith("quality.")
    }


def _gate_step(document: dict[Any, Any]) -> dict[str, Any]:
    return document["jobs"]["quality"]["steps"][1]


def test_gate_job_with_complete_pattern_is_accepted(repository: tuple[Path, str]) -> None:
    report = _gated_report(repository)
    findings = _quality_findings(report)
    assert [k for k, v in findings.items() if v["status"] != "PASS"] == []
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def _flagged(report: dict[str, Any]) -> bool:
    return any(item["status"] != "PASS" for item in _quality_findings(report).values())


@pytest.mark.parametrize(
    "condition",
    ["success() || failure()", "!cancelled()", "${{ needs.lint.result == 'success' }}", None],
)
def test_gate_requires_job_if_exactly_always(
    repository: tuple[Path, str], condition: str | None
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        if condition is None:
            document["jobs"]["quality"].pop("if")
        else:
            document["jobs"]["quality"]["if"] = condition

    report = _gated_report(repository, edit)
    assert _flagged(report)
    assert _quality_findings(report)["quality.job_if"]["status"] != "PASS" or (
        _quality_findings(report)["quality.needs"]["status"] != "PASS"
    )


def test_gate_accepts_the_expression_spelling_of_always(repository: tuple[Path, str]) -> None:
    report = _gated_report(
        repository, lambda d: d["jobs"]["quality"].update({"if": "${{ always() }}"})
    )
    assert not _flagged(report)


@pytest.mark.parametrize("dropped", ["changes", "lint", "tests", "packaging"])
def test_gate_must_inspect_every_needed_job_result(
    repository: tuple[Path, str], dropped: str
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        env = _gate_step(document)["env"]
        env[dropped.upper()] = "success"

    report = _gated_report(repository, edit)
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


@pytest.mark.parametrize(
    "step_edit",
    [
        {"if": "failure()"},
        {"if": "success()"},
        {"if": "${{ success() || failure() }}"},
        {"continue-on-error": True},
    ],
)
def test_gate_step_inspecting_results_must_always_run_and_block(
    repository: tuple[Path, str], step_edit: dict[str, Any]
) -> None:
    report = _gated_report(repository, lambda d: _gate_step(d).update(step_edit))
    assert _flagged(report)
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


def test_gate_step_masked_with_or_true_is_not_inspection(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        step = _gate_step(document)
        step["run"] = step["run"].rstrip("\n") + " || true\n"

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_gate_job_continue_on_error_is_flagged(repository: tuple[Path, str]) -> None:
    report = _gated_report(
        repository, lambda d: d["jobs"]["quality"].update({"continue-on-error": True})
    )
    assert _flagged(report)


@pytest.mark.parametrize("needed", ["lint", "tests", "changes"])
def test_needed_job_that_may_fail_silently_is_flagged(
    repository: tuple[Path, str], needed: str
) -> None:
    report = _gated_report(
        repository, lambda d: d["jobs"][needed].update({"continue-on-error": True})
    )
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


@pytest.mark.parametrize("needed", ["lint", "tests"])
def test_needed_job_with_skip_condition_is_flagged(
    repository: tuple[Path, str], needed: str
) -> None:
    report = _gated_report(
        repository,
        lambda d: d["jobs"][needed].update({"if": "${{ github.event_name == 'push' }}"}),
    )
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


def test_skippable_job_requires_gate_to_mention_skipped(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        step = _gate_step(document)
        step["run"] = step["run"].replace("--allow-skipped packaging ", "")

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_skippable_job_condition_must_come_from_a_needed_jobs_output(
    repository: tuple[Path, str],
) -> None:
    report = _gated_report(
        repository,
        lambda d: d["jobs"]["packaging"].update({"if": "${{ github.actor != 'nobody' }}"}),
    )
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


def test_skippable_job_condition_output_must_be_inspected_by_the_gate(
    repository: tuple[Path, str],
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        _gate_step(document)["env"].pop("PACKAGING_NEEDED")

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_transitive_dependency_outside_the_gate_needs_is_flagged(
    repository: tuple[Path, str],
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["prepare"] = {"runs-on": "ubuntu-latest", "steps": [{"run": "true"}]}
        document["jobs"]["tests"]["needs"] = ["changes", "prepare"]

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_needs_naming_a_missing_job_is_flagged(repository: tuple[Path, str]) -> None:
    report = _gated_report(
        repository, lambda d: d["jobs"]["quality"].update({"needs": ["changes", "lint", "ghost"]})
    )
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


@pytest.mark.parametrize(
    ("job", "needle"),
    [("lint", "ruff check"), ("lint", "mypy src"), ("tests", "pytest -q")],
)
def test_gate_does_not_hide_a_missing_required_command_in_a_needed_job(
    repository: tuple[Path, str], job: str, needle: str
) -> None:
    report = _gated_report(repository, lambda d: remove_step_containing(d, job, needle))
    assert report["overall_classification"] == "FAIL"


def test_commands_only_in_a_skippable_job_do_not_count(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        remove_step_containing(document, "tests", "pytest -q")
        document["jobs"]["packaging"]["steps"].append({"run": "pytest -q"})

    assert _gated_report(repository, edit)["overall_classification"] == "FAIL"


@pytest.mark.parametrize(
    "forged_step",
    [
        {
            "uses": f"actions/checkout@{PIN}",
            "env": {
                "A": "${{ needs.changes.result }}",
                "B": "${{ needs.lint.result }}",
                "C": "${{ needs.tests.result }}",
                "D": "${{ needs.packaging.result }}",
                "E": "${{ needs.changes.outputs.packaging }}",
            },
        },
        {
            "name": "passive echo",
            "env": {
                "A": "${{ needs.changes.result }}",
                "B": "${{ needs.lint.result }}",
                "C": "${{ needs.tests.result }}",
                "D": "${{ needs.packaging.result }}",
                "E": "${{ needs.changes.outputs.packaging }}",
            },
            "run": 'echo "skipped $A $B $C $D $E"',
        },
        {
            "name": "set +e around ci_gate",
            "env": {
                "CHANGES": "${{ needs.changes.result }}",
                "LINT": "${{ needs.lint.result }}",
                "TESTS": "${{ needs.tests.result }}",
                "PACKAGING": "${{ needs.packaging.result }}",
                "PACKAGING_NEEDED": "${{ needs.changes.outputs.packaging }}",
            },
            "run": (
                "set +e\n"
                'python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" '
                '--job tests="$TESTS" --job packaging="$PACKAGING" '
                '--allow-skipped packaging --packaging-needed "$PACKAGING_NEEDED"\n'
                "exit 0\n"
            ),
        },
        {
            "name": "negated ci_gate",
            "env": {
                "CHANGES": "${{ needs.changes.result }}",
                "LINT": "${{ needs.lint.result }}",
                "TESTS": "${{ needs.tests.result }}",
                "PACKAGING": "${{ needs.packaging.result }}",
                "PACKAGING_NEEDED": "${{ needs.changes.outputs.packaging }}",
            },
            "run": (
                "set -euo pipefail\n"
                '! python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" '
                '--job tests="$TESTS" --job packaging="$PACKAGING" '
                '--allow-skipped packaging --packaging-needed "$PACKAGING_NEEDED"\n'
            ),
        },
        {
            "name": "preceding command shadows env",
            "env": {
                "CHANGES": "${{ needs.changes.result }}",
                "LINT": "${{ needs.lint.result }}",
                "TESTS": "${{ needs.tests.result }}",
                "PACKAGING": "${{ needs.packaging.result }}",
                "PACKAGING_NEEDED": "${{ needs.changes.outputs.packaging }}",
            },
            "run": (
                "set -euo pipefail\n"
                "LINT=success\n"
                'python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" '
                '--job tests="$TESTS" --job packaging="$PACKAGING" '
                '--allow-skipped packaging --packaging-needed "$PACKAGING_NEEDED"\n'
            ),
        },
        {
            "name": "working-directory override",
            "working-directory": "tmp",
            "env": {
                "CHANGES": "${{ needs.changes.result }}",
                "LINT": "${{ needs.lint.result }}",
                "TESTS": "${{ needs.tests.result }}",
                "PACKAGING": "${{ needs.packaging.result }}",
                "PACKAGING_NEEDED": "${{ needs.changes.outputs.packaging }}",
            },
            "run": (
                "set -euo pipefail\n"
                'python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" '
                '--job tests="$TESTS" --job packaging="$PACKAGING" '
                '--allow-skipped packaging --packaging-needed "$PACKAGING_NEEDED"\n'
            ),
        },
    ],
)
def test_forged_gate_step_never_satisfies_quality_needs(
    repository: tuple[Path, str], forged_step: dict[str, Any]
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"][1] = forged_step

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


@pytest.mark.parametrize(
    "bad_if",
    [
        "${{ needs.changes.outputs.packaging == 'true' && false }}",
        "${{ needs.lint.outputs.packaging == 'true' }}",
        "${{ needs.changes.outputs.other == 'true' }}",
    ],
)
def test_skippable_job_rejects_compound_or_unlinked_output_condition(
    repository: tuple[Path, str], bad_if: str
) -> None:
    report = _gated_report(repository, lambda d: d["jobs"]["packaging"].update({"if": bad_if}))
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


def test_matrix_job_cannot_be_skippable(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["tests"]["if"] = "${{ needs.changes.outputs.packaging == 'true' }}"
        step = _gate_step(document)
        step["run"] = step["run"].replace(
            "--allow-skipped packaging",
            "--allow-skipped packaging --allow-skipped tests",
        )

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_non_skippable_job_in_allow_skipped_is_rejected(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        step = _gate_step(document)
        step["run"] = step["run"].replace(
            "--allow-skipped packaging",
            "--allow-skipped packaging --allow-skipped lint",
        )

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_hardcoded_packaging_needed_in_gate_is_rejected(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        _gate_step(document)["env"]["PACKAGING_NEEDED"] = "false"

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


_TWO_PART_GATE_CALL = (
    "set -euo pipefail\n"
    'python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" '
    '--job tests="$TESTS" --job packaging-1="$PACKAGING_1" --job packaging-2="$PACKAGING_2" '
    "--allow-skipped packaging-1 --allow-skipped packaging-2 "
    '--packaging-needed "$PACKAGING_NEEDED"\n'
)


def _two_part_packaging(document: dict[Any, Any]) -> None:
    """#1570 shape: two skippable packaging jobs and slim checkouts for `changes` and the gate."""
    jobs = document["jobs"]
    part = jobs.pop("packaging")
    jobs["packaging-1"] = json.loads(json.dumps(part))
    jobs["packaging-2"] = json.loads(json.dumps(part))
    jobs["quality"]["needs"] = ["changes", "lint", "tests", "packaging-1", "packaging-2"]
    sparse = {"persist-credentials": False, "sparse-checkout-cone-mode": False}
    jobs["changes"]["steps"][0]["with"] = {
        **sparse,
        "sparse-checkout": "scripts/ci_change_scope.py\n/pyproject.toml\n",
    }
    jobs["quality"]["steps"][0]["with"] = {**sparse, "sparse-checkout": "scripts/ci_gate.py"}
    step = _gate_step(document)
    env = step["env"]
    env.pop("PACKAGING")
    env["PACKAGING_1"] = "${{ needs.packaging-1.result }}"
    env["PACKAGING_2"] = "${{ needs.packaging-2.result }}"
    step["run"] = _TWO_PART_GATE_CALL


def test_two_skippable_packaging_parts_with_slim_checkouts_are_accepted(
    repository: tuple[Path, str],
) -> None:
    """The trusted verifier recognises the #1570 gate shape without any change of its own."""
    report = _gated_report(repository, _two_part_packaging)
    findings = _quality_findings(report)
    assert [k for k, v in findings.items() if v["status"] != "PASS"] == []
    assert findings["quality.needs"]["reason"] == "required_job_is_a_verified_gate_over_its_needs"
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"


def _drop_allow_skipped_part_2(document: dict[Any, Any]) -> None:
    step = _gate_step(document)
    step["run"] = step["run"].replace("--allow-skipped packaging-2 ", "")


def _bind_part_2_to_part_1(document: dict[Any, Any]) -> None:
    _gate_step(document)["env"]["PACKAGING_2"] = "${{ needs.packaging-1.result }}"


def _hardcode_part_2(document: dict[Any, Any]) -> None:
    _gate_step(document)["env"]["PACKAGING_2"] = "success"


def _part_2_other_condition(document: dict[Any, Any]) -> None:
    document["jobs"]["packaging-2"]["if"] = "${{ github.event_name == 'push' }}"


def _part_2_as_matrix(document: dict[Any, Any]) -> None:
    document["jobs"]["packaging-2"]["strategy"] = {"matrix": {"half": [1, 2]}}


def _part_2_may_fail_silently(document: dict[Any, Any]) -> None:
    document["jobs"]["packaging-2"]["continue-on-error"] = True


def _gate_checkout_from_a_local_action(document: dict[Any, Any]) -> None:
    document["jobs"]["quality"]["steps"][0]["uses"] = "./.github/actions/checkout"


@pytest.mark.parametrize(
    "mutation",
    [
        _drop_allow_skipped_part_2,
        _bind_part_2_to_part_1,
        _hardcode_part_2,
        _part_2_other_condition,
        _part_2_as_matrix,
        _part_2_may_fail_silently,
        _gate_checkout_from_a_local_action,
    ],
)
def test_two_part_packaging_gate_mutations_are_flagged(
    repository: tuple[Path, str], mutation: Callable[[dict[Any, Any]], None]
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        _two_part_packaging(document)
        mutation(document)

    assert _flagged(_gated_report(repository, edit))


@pytest.mark.parametrize(
    "mutate_fn",
    [
        lambda d: d.update({"defaults": {"run": {"shell": "python {0}"}}}),
        lambda d: d["jobs"]["quality"].update({"defaults": {"run": {"shell": "sh"}}}),
        lambda d: d["jobs"]["lint"].update({"defaults": {"run": {"shell": "python {0}"}}}),
        lambda d: d["jobs"]["lint"].update({"defaults": {"run": {"working-directory": "sub"}}}),
        lambda d: d["jobs"]["quality"].update({"strategy": {"continue-on-error": True}}),
        lambda d: d["jobs"]["tests"]["strategy"].update({"continue-on-error": True}),
        lambda d: d["jobs"]["tests"]["strategy"].update({"matrix": {}}),
        lambda d: d["jobs"]["tests"]["strategy"].update({"matrix": {"slot": []}}),
        lambda d: d["jobs"]["tests"]["strategy"].update(
            {"matrix": {"slot": [1], "exclude": [{"slot": 1}]}}
        ),
        lambda d: d["jobs"]["tests"]["strategy"].update(
            {"matrix": "${{ fromJSON(vars.TEST_MATRIX) }}"}
        ),
    ],
)
def test_unsafe_defaults_or_matrix_on_gate_or_needed_jobs_are_flagged(
    repository: tuple[Path, str], mutate_fn: Callable[[dict[Any, Any]], None]
) -> None:
    assert _flagged(_gated_report(repository, mutate_fn))


@pytest.mark.parametrize(
    "script_path",
    [
        "scripts/ci_change_scope.py",
        "scripts/ci_gate.py",
        "scripts/verify_packaging_smoke.py",
    ],
)
def test_gate_helper_scripts_are_protected_entrypoint_surfaces(
    repository: tuple[Path, str], script_path: str
) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, script_path, "# modified gate helper\n"),
        f"modify {script_path}",
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED"
    assert any(
        item["path"] == script_path
        and item["impact"] == "required_check_entrypoint_or_configuration"
        for item in report["changed_protected_surfaces"]
    )


_GATE_ENV = {
    "CHANGES": "${{ needs.changes.result }}",
    "LINT": "${{ needs.lint.result }}",
    "TESTS": "${{ needs.tests.result }}",
    "PACKAGING": "${{ needs.packaging.result }}",
    "PACKAGING_NEEDED": "${{ needs.changes.outputs.packaging }}",
}
_GATE_CALL = (
    'python3 scripts/ci_gate.py --job changes="$CHANGES" --job lint="$LINT" '
    '--job tests="$TESTS" --job packaging="$PACKAGING" '
    '--allow-skipped packaging --packaging-needed "$PACKAGING_NEEDED"'
)


@pytest.mark.parametrize(
    "run",
    [
        'echo "$CHANGES $LINT $TESTS $PACKAGING $PACKAGING_NEEDED skipped"\n',
        f"set -euo pipefail\nset +e\n{_GATE_CALL}\necho done\n",
        '[ "$TESTS" != failure ] && echo fine\n',
        f"set -euo pipefail\n{_GATE_CALL}\necho done\n",
        f"set -euo pipefail\n{_GATE_CALL}\nexit 0\n",
        f"set -euo pipefail\n{_GATE_CALL}; true\n",
        f"set -euo pipefail\n{_GATE_CALL} || true\n",
        f"set -euo pipefail\necho start\n{_GATE_CALL}\n",
    ],
)
def test_text_mention_or_extra_command_does_not_make_a_gate(
    repository: tuple[Path, str], run: str
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"][1] = {
            "name": "forged",
            "shell": "bash",
            "env": dict(_GATE_ENV),
            "run": run,
        }

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_gate_call_without_one_needed_result_is_not_a_gate(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        step = document["jobs"]["quality"]["steps"][1]
        step["run"] = step["run"].replace(' --job lint="$LINT"', "")

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


@pytest.mark.parametrize(
    "extra_step",
    [
        {"run": "cp /dev/null scripts/ci_gate.py"},
        {"run": 'echo "$RUNNER_TEMP/fake-bin" >> "$GITHUB_PATH"'},
        {"uses": "./.github/actions/quality-bootstrap"},
        {"uses": "docker://alpine:3.20"},
        {"uses": "actions/checkout@v5"},
        {"name": "empty step"},
    ],
)
def test_step_before_the_gate_that_can_alter_it_is_rejected(
    repository: tuple[Path, str], extra_step: dict[str, Any]
) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"].insert(1, extra_step)

    report = _gated_report(repository, edit)
    assert _quality_findings(report)["quality.needs"]["status"] != "PASS"


def test_step_after_the_gate_is_rejected(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"].append({"run": "echo done"})

    assert _quality_findings(_gated_report(repository, edit))["quality.needs"]["status"] != "PASS"


def test_pinned_actions_before_the_gate_are_accepted(repository: tuple[Path, str]) -> None:
    def edit(document: dict[Any, Any]) -> None:
        document["jobs"]["quality"]["steps"].insert(1, {"uses": f"actions/cache@{PIN}"})

    assert not _flagged(_gated_report(repository, edit))


NEW_MODULE_PROBES = {
    "autouse fixture": "import pytest\n@pytest.fixture(autouse=True)\ndef _f():\n    pass\ndef test_a(): assert True\n",
    "setup_module": "def setup_module(m): pass\ndef test_a(): assert True\n",
    "teardown_module": "def teardown_module(m): pass\ndef test_a(): assert True\n",
    "pytestmark": "import pytest\npytestmark = pytest.mark.skip\ndef test_a(): assert True\n",
    "__test__": "__test__ = False\ndef test_a(): assert True\n",
    "collect_ignore": "collect_ignore = ['x']\ndef test_a(): assert True\n",
    "collect_ignore_glob": "collect_ignore_glob = ['x']\ndef test_a(): assert True\n",
    "pytest_ hook": "def pytest_collection_modifyitems(items): items.clear()\ndef test_a(): assert True\n",
    # Probe (5): a new file that rewrites another test module before collection.
    "absolute test import": "import tests.unit.test_other as m\nm.test_x = lambda: None\ndef test_a(): assert True\n",
    "from tests import": "from tests.unit import test_other\ndef test_a(): assert True\n",
    "relative import": "from . import test_other\ndef test_a(): assert True\n",
    "relative module import": "from .test_other import test_x\ndef test_a(): assert True\n",
    "star import": "from os.path import *\ndef test_a(): assert True\n",
    "importlib": "import importlib\nm = importlib.import_module('x')\ndef test_a(): assert True\n",
    "__import__": "m = __import__('x')\ndef test_a(): assert True\n",
    "globals at module level": "globals().update({})\ndef test_a(): assert True\n",
    "setattr at module level": "import os\nsetattr(os, 'x', 1)\ndef test_a(): assert True\n",
    "delattr at module level": "import os\ndelattr(os, 'x')\ndef test_a(): assert True\n",
    "sys.modules": "import sys\nsys.modules['x'] = None\ndef test_a(): assert True\n",
    "class body rewrite": "class _N:\n    globals().update({})\ndef test_a(): assert True\n",
    "decorator side effect": "def _d(f):\n    return f\n@_d\ndef test_a(): assert True\n_x = globals()\n",
    "monkeypatch at module level": "monkeypatch = None\ndef test_a(): assert True\n",
    "importlib in a body": "def test_a():\n    import importlib\n    importlib.reload(importlib)\n",
    "globals in a body": "def test_a():\n    globals().update({})\n",
}


@pytest.mark.parametrize("name", sorted(NEW_MODULE_PROBES))
def test_new_test_module_that_can_reach_other_tests_requires_review(
    repository: tuple[Path, str], name: str
) -> None:
    repo, base = repository
    head = candidate(
        repo,
        base,
        lambda root: write(root, "tests/unit/test_aaa_probe.py", NEW_MODULE_PROBES[name]),
        "probe",
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "GATE_DEFINITION_CHANGED_REVIEW_REQUIRED", name
    assert report["benign_test_changes"] == []


def test_ordinary_new_test_module_with_fixtures_helpers_and_classes_is_benign(
    repository: tuple[Path, str],
) -> None:
    text = (
        "import json\nimport pytest\nfrom pathlib import Path\n"
        "LIMIT = 3\n"
        "@pytest.fixture\ndef data(tmp_path):\n    return tmp_path / 'x'\n"
        "def _helper(value):\n    return value + LIMIT\n"
        "class TestThing:\n"
        "    def test_one(self, data, monkeypatch):\n"
        "        monkeypatch.setenv('A', '1')\n"
        "        assert _helper(1) == 4\n"
        "@pytest.mark.parametrize('x', [1, 2])\ndef test_two(x):\n    assert x\n"
    )
    repo, base = repository
    head = candidate(
        repo, base, lambda root: write(root, "tests/unit/test_ordinary.py", text), "ordinary"
    )
    report = guard.inspect_required_check_definitions(repo, base, head)
    assert report["overall_classification"] == "PASS"
    assert report["benign_test_changes"] == ["tests/unit/test_ordinary.py"]
