from pathlib import Path


def _release_workflow() -> str:
    return Path(".github/workflows/release-artifacts.yml").read_text(encoding="utf-8")


def test_release_workflow_runs_on_canonical_main_and_pull_requests() -> None:
    workflow = _release_workflow()
    assert 'branches:\n      - main\n      - "release/**"' in workflow
    assert "\n  pull_request:\n" in workflow


def test_release_artifacts_are_bound_to_checked_out_github_sha() -> None:
    workflow = _release_workflow()
    assert 'git -C "$repo_dir" checkout --detach "$GITHUB_SHA"' in workflow
    assert 'test "$(git -C "$repo_dir" rev-parse HEAD)" = "$GITHUB_SHA"' in workflow
    assert '"git_head": sha' in workflow
    assert "printf 'release=%s\\ngit_head=%s\\nroundtrip=pending\\n'" in workflow


def _release_status_script() -> str:
    workflow = _release_workflow()
    step = workflow.index("- name: Write current release status and evidence boundary")
    start = workflow.index("python - <<'PY'\n", step) + len("python - <<'PY'\n")
    end = workflow.index("\n          PY\n", start)
    lines = workflow[start:end].splitlines()
    return "\n".join(line[10:] if line.startswith(" " * 10) else line for line in lines) + "\n"


def _run_release_status(tmp_path: Path, mutate=None):
    import json
    import os
    import shutil
    import subprocess
    import sys

    for rel in (
        "data/collections/current/ACTIVE_OWN_DECKS_CURRENT.json",
        "data/decks/manifest.json",
        "config/rules_engines.json",
        "docs/J_P3_PROVIDER_DECISION.json",
    ):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(rel, tmp_path / rel)
    if mutate is not None:
        path = tmp_path / "config/rules_engines.json"
        rules = json.loads(path.read_text(encoding="utf-8"))
        mutate(rules)
        path.write_text(json.dumps(rules), encoding="utf-8")
    (tmp_path / "release").mkdir()
    env = {**os.environ, "GITHUB_SHA": "0" * 40, "VERSION": "0.0.0-test"}
    return subprocess.run(
        [sys.executable, "-c", _release_status_script()],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_status_reports_the_d5_provider_record(tmp_path: Path) -> None:
    import json

    completed = _run_release_status(tmp_path)
    assert completed.returncode == 0, completed.stderr
    status = json.loads((tmp_path / "release/PLAYTEST_LAB_CURRENT_STATUS.json").read_text())
    assert status["external_engine_provider_decision"] == "XMAGE_SELECTED"
    assert status["external_engine_production_ready"] is True
    assert status["current_external_engine_validation_level"] == (
        "external_rules_engine_full_game_lane"
    )
    assert status["xmage_missing_required_capabilities"] == []


def _set(path: tuple[str, ...], value):
    def mutate(rules):
        node = rules
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


import pytest  # noqa: E402


@pytest.mark.parametrize(
    "mutate",
    [
        _set(("primary_engine", "production_ready"), False),
        _set(("current_runtime", "required_missing_capabilities"), ["replay_supported"]),
        _set(("primary_engine", "missing_required_capabilities"), ["replay_supported"]),
        _set(("current_runtime", "provider_selected"), False),
        _set(("production_bridge",), "b4d_event_log_lifecycle_bridge"),
        _set(("architecture_freeze", "runtime_switch"), "PENDING_D5"),
        _set(("secondary_engine",), {"provider": "other", "production_ready": False}),
        _set(("provider_decision",), "FORGE_SELECTED"),
    ],
)
def test_release_status_refuses_an_inconsistent_provider_record(tmp_path: Path, mutate) -> None:
    completed = _run_release_status(tmp_path, mutate)
    assert completed.returncode != 0
    assert "release refuses" in completed.stderr


def test_release_status_still_refuses_readiness_under_no_provider_ready(tmp_path: Path) -> None:
    def mutate(rules):
        rules["provider_decision"] = "NO_PROVIDER_READY"

    completed = _run_release_status(tmp_path, mutate)
    assert completed.returncode != 0
    assert "while NO_PROVIDER_READY" in completed.stderr
