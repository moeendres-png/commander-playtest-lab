"""Shadow context-router guardrails: broad-on-uncertainty, no authority promotion."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import context_router as router  # noqa: E402


def git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def scratch(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(["init", "-b", "work"], repo)
    git(["config", "user.email", "router@example.invalid"], repo)
    git(["config", "user.name", "router"], repo)
    (repo / "tools").mkdir()
    (repo / "tools" / "foundry").mkdir()
    (repo / "tools" / "foundry" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "pkg").mkdir()
    (repo / "src" / "pkg" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    git(["add", "."], repo)
    git(["commit", "-m", "fixture"], repo)
    return {
        "root": repo,
        "head": git(["rev-parse", "HEAD"], repo),
        "tree": git(["rev-parse", "HEAD^{tree}"], repo),
        "branch": "work",
    }


def write_profiles(root: Path, *, slug: str = "example/repo") -> Path:
    profiles = root / "profiles"
    profiles.mkdir()
    for name in ("cpl", "mage", "forge"):
        repo_slug = slug if name == "cpl" else f"example/{name}"
        (profiles / f"{name}.json").write_text(
            json.dumps({"profile": name, "repo_slug": repo_slug}),
            encoding="utf-8",
        )
    return profiles


def write_state(path: Path, scratch: dict, **overrides: object) -> Path:
    doc = {
        "schema_version": "2.0",
        "repository": "example/repo",
        "worktree": str(scratch["root"]),
        "branch": scratch["branch"],
        "audit_base_sha": scratch["head"],
        "audit_base_tree": scratch["tree"],
        "state_written_against_head": scratch["head"],
        "validated_head": scratch["head"],
        "objective": "Maintain Foundry context tooling.",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": "ROUTER-TEST",
        "status": "ACTIVE",
        "hard_gates": [],
        "authority_gates": [],
        "files_modified": ["tools/foundry/x.py"],
        "exact_next_action": "Run focused tooling validation.",
    }
    doc.update(overrides)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_foundry_path_routes_bounded_without_repeating_state(
    scratch: dict, tmp_path: Path
) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert plan["route_mode"] == "BOUNDED_ON_DEMAND"
    assert "foundry" in plan["selected_domains"]
    assert plan["full_state_read_required"] is False
    assert "tools/foundry/x.py" in plan["read_next"]
    assert plan["default_activation_authorized"] is False
    assert "AGENTS.md remains privileged" in plan["policy_note"]


def test_no_route_broadens_to_full_state(scratch: dict, tmp_path: Path) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        objective="PRIVATE_SENTINEL opaque work.",
        exact_next_action="Continue opaque task.",
        files_modified=[],
    )
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert plan["full_state_read_required"] is True
    assert plan["read_next"] == [str(state)]
    assert "PRIVATE_SENTINEL" not in json.dumps(plan)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("authority_gates", ["needs coordinator"], "authority gate present"),
        ("failure_class", "UNKNOWN", "failure class UNKNOWN"),
        ("invalidated_gates", ["old pass invalid"], "invalidated gates present"),
        ("status", "STALE", "state status requires rebaseline"),
    ],
)
def test_risky_state_forces_broad_context(
    scratch: dict,
    tmp_path: Path,
    field: str,
    value: object,
    reason: str,
) -> None:
    state = write_state(tmp_path / "state.yaml", scratch, **{field: value})
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert reason in plan["broad_context_reasons"]


def test_many_changed_paths_force_broad_context(scratch: dict, tmp_path: Path) -> None:
    paths = [f"tools/foundry/f{i}.py" for i in range(router.MAX_CHANGED_PATHS + 1)]
    state = write_state(tmp_path / "state.yaml", scratch, files_modified=paths)
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert any("files_modified exceeds" in x for x in plan["broad_context_reasons"])


def test_profile_repository_mismatch_rejected(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    profiles = write_profiles(tmp_path, slug="other/repo")
    with pytest.raises(router.RouterError, match="repository"):
        router.derive_plan(str(state), str(scratch["root"]), "cpl", profiles)


def test_branch_identity_reuses_capsule_fail_closed_gate(
    scratch: dict, tmp_path: Path
) -> None:
    state = write_state(tmp_path / "state.yaml", scratch, branch="wrong")
    with pytest.raises(router.RouterError, match="branch mismatch"):
        router.derive_plan(
            str(state),
            str(scratch["root"]),
            "cpl",
            write_profiles(tmp_path),
        )


def test_engine_bridge_without_provider_broadens_instead_of_guessing(
    scratch: dict, tmp_path: Path
) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        objective="Repair a protocol bridge.",
        files_modified=["engine-bridge/src/main/java/example/Bridge.java"],
    )
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert "engine_bridge" in plan["selected_domains"]
    assert "mage" not in plan["selected_domains"]
    assert "forge" not in plan["selected_domains"]
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert "engine bridge provider ambiguous" in plan["broad_context_reasons"]


def test_text_signals_use_word_boundaries(scratch: dict, tmp_path: Path) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        objective="Process image metadata.",
        files_modified=[],
        exact_next_action="Inspect image output.",
    )
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert "mage" not in plan["selected_domains"]


def test_engine_profile_requests_map_only_on_demand(
    scratch: dict, tmp_path: Path
) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        repository="example/mage",
        objective="Inspect callback navigation.",
        files_modified=[],
    )
    profiles = write_profiles(tmp_path)
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "mage",
        profiles,
    )
    assert "mage" in plan["selected_domains"]
    assert plan["repo_maps"] == [
        {
            "profile": "mage",
            "mode": "ON_DEMAND_ONLY",
            "command": (
                "python3 tools/foundry/context_router.py repo-map "
                "--workdir <DECLARED_REFERENCE_ROOT> --max-depth 3"
            ),
        }
    ]


def test_repo_map_is_bounded_to_committed_names(
    scratch: dict, tmp_path: Path
) -> None:
    secret = scratch["root"] / "src" / "pkg" / "private.txt"
    secret.write_text("PRIVATE_SENTINEL\n", encoding="utf-8")
    result = router.build_repo_map(str(scratch["root"]), max_depth=2)
    dumped = json.dumps(result)
    assert result["_kind"].startswith("DERIVED_ON_DEMAND")
    assert result["HEAD"] == scratch["head"]
    assert result["tree"] == scratch["tree"]
    assert "src/pkg" in result["directories"]
    assert "PRIVATE_SENTINEL" not in dumped
    assert result["dirty_entries"] == 1


def test_repo_map_prefix_and_depth_are_explicit(scratch: dict) -> None:
    result = router.build_repo_map(
        str(scratch["root"]),
        max_depth=2,
        prefixes=["src"],
    )
    assert result["prefixes"] == ["src"]
    assert all(path.startswith("src") for path in result["directories"])
    with pytest.raises(router.RouterError, match="max-depth"):
        router.build_repo_map(str(scratch["root"]), max_depth=7)
    with pytest.raises(router.RouterError, match="safe repository-relative"):
        router.build_repo_map(str(scratch["root"]), prefixes=["../escape"])


def test_plan_is_deterministic(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    profiles = write_profiles(tmp_path)
    first = router.derive_plan(str(state), str(scratch["root"]), "cpl", profiles)
    second = router.derive_plan(str(state), str(scratch["root"]), "cpl", profiles)
    assert first == second
