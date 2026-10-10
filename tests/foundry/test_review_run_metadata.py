"""Exercise the actual review launcher input without weakening the verifier."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/opencode.yml"


def _step():
    job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["opencode-bunny-review"]
    steps = job["steps"]
    index = next(i for i, s in enumerate(steps) if s["name"] == "Write public review run metadata")
    assert index < next(i for i, s in enumerate(steps) if s["name"] == "Run opencode")
    return steps[index]


def _launch(tmp_path, overrides=None):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    environment = dict(os.environ)
    environment.update(
        {
            "REVIEW_RUN_URL": "https://github.com/owner/repo/actions/runs/1234",
            "REVIEW_RUN_ATTEMPT": "2",
            "REVIEW_TRIGGER_COMMENT_ID": "5678",
            "REVIEW_WORKFLOW_SHA": "a" * 40,
            "UNRELATED_SECRET_SENTINEL": "must-not-appear",
        }
    )
    environment.update(overrides or {})
    return subprocess.run(
        ["bash", "-c", _step()["run"]],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_actual_launcher_writes_only_public_identity_and_keeps_checkout_clean(tmp_path):
    result = _launch(tmp_path)
    assert result.returncode == 0, result.stderr
    path = tmp_path / ".opencode/review-run-metadata.json"
    assert json.loads(path.read_text()) == {
        "run_url": "https://github.com/owner/repo/actions/runs/1234",
        "run_attempt": 2,
        "trigger_comment_id": 5678,
        "workflow_sha": "a" * 40,
    }
    assert path.stat().st_mode & 0o222 == 0
    assert "must-not-appear" not in path.read_text() + result.stdout + result.stderr
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True
    )
    assert status.stdout == ""


@pytest.mark.parametrize("key", ["REVIEW_RUN_ATTEMPT", "REVIEW_TRIGGER_COMMENT_ID"])
def test_malformed_launcher_identity_refuses_before_creating_input(tmp_path, key):
    result = _launch(tmp_path, {key: "unknown"})
    assert result.returncode != 0
    assert not (tmp_path / ".opencode/review-run-metadata.json").exists()


def test_launcher_uses_own_run_context_and_preserves_native_prompt_and_permissions():
    step = _step()
    assert step["env"] == {
        "REVIEW_RUN_URL": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}",
        "REVIEW_RUN_ATTEMPT": "${{ github.run_attempt }}",
        "REVIEW_TRIGGER_COMMENT_ID": "${{ github.event.comment.id }}",
        "REVIEW_WORKFLOW_SHA": "${{ github.workflow_sha }}",
    }
    job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["opencode-bunny-review"]
    run = next(s for s in job["steps"] if s["name"] == "Run opencode")
    assert (
        run["run"]
        .rstrip()
        .endswith(
            'python3 -I "$watchdog" --log "$RUNNER_TEMP/opencode-review.log" -- opencode github run'
        )
    )
    assert run["env"]["PROMPT"] == ""
    agent = (ROOT / ".opencode/agents/foundry-reviewer.md").read_text()
    assert "read tool" in agent and "LAST absolute Actions run link" in agent
    assert "review-run-metadata.json" in agent
