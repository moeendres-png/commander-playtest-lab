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
