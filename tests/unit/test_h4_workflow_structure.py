"""WS-A1D-H4 workflow-structure regression tests (no Docker required).

Locks the Coordinator's remote-review remediation for
``.github/workflows/h4-docker-materialization.yml`` so the lane cannot
silently regress:

* both Docker jobs must supply a benign build-time ``ENGINE_START_COMMAND``
  for Compose model resolution plus a unique explicit
  ``COMPOSE_PROJECT_NAME``;
* image evidence must bind to the exact ``<project>-<service>`` image
  reference and its immutable image ID (no provider-label discovery, no
  invented verdict tags);
* the XMage handshake step must override the benign value with the real
  bridge command; Forge must attempt no bridge and stay
  ``EVIDENCE_PARTIAL`` / ``bridge_handshake=NOT_RUN``;
* negative controls must forward ``PIN_MANIFEST_PATH`` via
  ``compose run -e``;
* the ``workflow_dispatch`` comment must state truthful GitHub semantics.

Plain-text assertions only (no extra dependencies, no Docker, no pins).
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_REL = ".github/workflows/h4-docker-materialization.yml"


def _text(repo_root: Path) -> str:
    return (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")


def _job_block(text: str, job: str) -> str:
    if job == "preflight":
        pattern = r"(?m)^  preflight:\s*$"
    elif job == "h4-xmage":
        pattern = r"(?m)^  h4-xmage:\s*$"
    elif job == "h4-forge-image":
        pattern = r"(?m)^  h4-forge-image:\s*$"
    else:
        raise AssertionError(f"unknown job {job!r}")
    match = re.search(pattern, text)
    assert match is not None, f"job {job} is missing from the H4 workflow"
    rest = text[match.end() :]
    following = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", rest)
    return rest[: following.start() if following else len(rest)]


def test_both_docker_jobs_define_benign_build_time_start_command(repo_root):
    text = _text(repo_root)
    for job in ("h4-xmage", "h4-forge-image"):
        block = _job_block(text, job)
        assert 'ENGINE_START_COMMAND: "true"' in block, (
            f"{job} must provide a benign build-time ENGINE_START_COMMAND "
            "for Compose model resolution"
        )


def test_both_jobs_use_unique_explicit_compose_project_name(repo_root):
    text = _text(repo_root)
    xmage = _job_block(text, "h4-xmage")
    forge = _job_block(text, "h4-forge-image")
    assert "COMPOSE_PROJECT_NAME: h4-xmage-${{ github.run_id }}" in xmage
    assert "COMPOSE_PROJECT_NAME: h4-forge-${{ github.run_id }}" in forge
    assert "h4-xmage-${{ github.run_id }}" != "h4-forge-${{ github.run_id }}"


def test_no_label_based_image_discovery_and_no_invented_tags(repo_root):
    text = _text(repo_root)
    assert "docker images" not in text, "provider-label image discovery is forbidden"
    assert "--filter" not in text, "label-filter image discovery is forbidden"
    assert "GITHUB_SHA::12" not in text, "fabricated logical image tags are forbidden"


def test_image_binding_uses_exact_compose_project_service_ref(repo_root):
    text = _text(repo_root)
    cases = (
        ("h4-xmage", "xmage", "h4-evidence-xmage"),
        ("h4-forge-image", "forge", "h4-evidence-forge"),
    )
    for job, service, evidence in cases:
        block = _job_block(text, job)
        assert f'IMAGE_REF="${{COMPOSE_PROJECT_NAME}}-{service}"' in block
        assert 'IMAGE_ID="$(docker image inspect --format \'{{.Id}}\' "$IMAGE_REF")"' in block
        assert f"{evidence}/image-ref.txt" in block
        assert f"{evidence}/image-id.txt" in block
        assert f'docker image inspect "$IMAGE_REF" > {evidence}/docker-inspect.json' in block
        assert 'docker run --rm --entrypoint cat "$IMAGE_ID"' in block
        assert 'docker run --rm --entrypoint git "$IMAGE_ID"' in block


def test_verdict_receives_recorded_truthful_ref_and_id(repo_root):
    text = _text(repo_root)
    cases = (("h4-xmage", "h4-evidence-xmage"), ("h4-forge-image", "h4-evidence-forge"))
    for job, evidence in cases:
        block = _job_block(text, job)
        assert f'--image-id "$(cat {evidence}/image-id.txt)"' in block
        assert f'--image-tag "$(cat {evidence}/image-ref.txt)"' in block


def test_xmage_handshake_overrides_benign_start_command(repo_root):
    text = _text(repo_root)
    block = _job_block(text, "h4-xmage")
    assert (
        "export ENGINE_START_COMMAND='java -jar /workspace/vendor/engine-binaries/xmage/bridge.jar'"
        in block
    )


def test_forge_has_no_bridge_and_stays_partial(repo_root):
    text = _text(repo_root)
    block = _job_block(text, "h4-forge-image")
    assert "emit-handshake" not in block, "Forge must not attempt a bridge handshake"
    assert "handshake-transcript" not in block, "Forge must not fabricate a transcript"
    assert "forge-bridge-absence.txt" in block
    assert "EVIDENCE_PARTIAL" in block
    assert "bridge_handshake']['status']=='NOT_RUN'" in block


def test_negatives_forward_pin_manifest_path_via_compose_run_e(repo_root):
    text = _text(repo_root)
    for job in ("h4-xmage", "h4-forge-image"):
        block = _job_block(text, job)
        assert "-e PIN_MANIFEST_PATH=" in block, (
            f"{job} negatives must forward the manifest override into the "
            "container with compose run -e (host exports never reach it)"
        )


def test_workflow_dispatch_comment_matches_github_semantics(repo_root):
    text = _text(repo_root)
    assert "`pull_request` is the initial remote-execution path" in text
    assert "merge ref" in text
    assert "once this workflow exists on the default branch" in text
    assert "Do not attempt workflow_dispatch before merge" in text
    assert "covers manual runs (post-merge or branch" not in text


def _setup_python_blocks(job_block: str) -> list:
    """Return the raw text of each setup-python step inside a job block."""
    lines = job_block.splitlines()
    blocks = []
    current: list | None = None
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 6 and stripped.startswith("- "):
            if current is not None:
                blocks.append("\n".join(current))
                current = None
            if "actions/setup-python@" in stripped:
                current = [line]
        elif current is not None:
            if stripped == "" or indent >= 8:
                current.append(line)
            else:
                blocks.append("\n".join(current))
                current = None
    if current is not None:
        blocks.append("\n".join(current))
    return blocks


def test_docker_heavy_jobs_use_no_setup_python_pip_cache(repo_root):
    # Run 34573843323: the Forge job's substantive H4 evidence completed, but
    # the setup-python post-job pip-cache save traversed Docker-overlay state
    # and failed the job. Docker-heavy jobs must not use the pip cache.
    text = _text(repo_root)
    for job in ("h4-xmage", "h4-forge-image"):
        steps = _setup_python_blocks(_job_block(text, job))
        assert len(steps) == 1, f"{job} must keep exactly one setup-python step"
        assert 'python-version: "3.12"' in steps[0], f"{job} setup-python step was gutted"
        assert "cache: pip" not in steps[0], (
            f"{job} must not use setup-python pip caching (Docker-overlay hygiene)"
        )


def test_preflight_may_retain_setup_python_pip_cache(repo_root):
    text = _text(repo_root)
    steps = _setup_python_blocks(_job_block(text, "preflight"))
    assert len(steps) == 1, "preflight must keep exactly one setup-python step"
    assert "cache: pip" in steps[0], "preflight is Docker-free and may retain the pip cache"
