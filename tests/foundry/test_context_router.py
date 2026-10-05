"""Shadow context-router guardrails: broad-on-uncertainty, no authority promotion."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from tools.foundry import context_router as router


def git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def scratch(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(["init", "-b", "work"], repo)
    git(["config", "user.email", "router@example.invalid"], repo)
    git(["config", "user.name", "router"], repo)
    git(["remote", "add", "origin", "https://github.com/example/repo.git"], repo)
    (repo / "tools").mkdir()
    (repo / "tools" / "foundry").mkdir()
    (repo / "tools" / "foundry" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "pkg").mkdir()
    (repo / "src" / "pkg" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    git(["add", "."], repo)
    git(["commit", "-m", "fixture"], repo)
    return {"root": repo, "branch": "work"}


def live_head(scratch: dict) -> str:
    return git(["rev-parse", "HEAD"], scratch["root"])


def live_tree(scratch: dict) -> str:
    return git(["rev-parse", "HEAD^{tree}"], scratch["root"])


def profile(name: str = "mage", slug: str = "example/repo") -> dict:
    return {"profile": name, "repo_slug": slug}


def declared_reference(
    scratch: dict,
    *,
    label: str = "mage",
    slug: str = "example/repo",
    commit: str | None = None,
    tree: str | None = None,
) -> dict:
    return {
        "label": label,
        "root": str(scratch["root"]),
        "repo_slug": slug,
        "commit": commit or live_head(scratch),
        "tree": tree or live_tree(scratch),
        "cleanliness": "clean",
        "intent": "read-only",
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
    head = live_head(scratch)
    tree = live_tree(scratch)
    doc = {
        "schema_version": "2.0",
        "repository": "example/repo",
        "worktree": str(scratch["root"]),
        "branch": scratch["branch"],
        "audit_base_sha": head,
        "audit_base_tree": tree,
        "state_written_against_head": head,
        "validated_head": head,
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


def test_foundry_path_routes_bounded_without_repeating_state(scratch: dict, tmp_path: Path) -> None:
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


def test_no_route_broadens_without_leaking_state_path_or_prose(
    scratch: dict, tmp_path: Path
) -> None:
    state = write_state(
        tmp_path / "private-state.yaml",
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
    dumped = json.dumps(plan)
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert plan["full_state_read_required"] is True
    assert plan["full_state_reference"] == "$FOUNDRY_STATE_PATH"
    assert plan["read_next"] == ["$FOUNDRY_STATE_PATH"]
    assert str(state) not in dumped
    assert "PRIVATE_SENTINEL" not in dumped


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("authority_gates", ["needs coordinator"], "authority gate present"),
        ("failure_class", "UNKNOWN", "failure class UNKNOWN"),
        ("invalidated_gates", ["old pass invalid"], "invalidated gates present"),
        ("status", "STALE", "state status is not ACTIVE"),
        ("status", "SUPERSEDED", "state status is not ACTIVE"),
        ("status", "WAITING", "state status is not ACTIVE"),
        ("status", "BLOCKED", "state status is not ACTIVE"),
        ("status", "COMPLETE", "state status is not ACTIVE"),
    ],
)
def test_risky_or_nonactive_state_forces_broad_context(
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


def test_head_drift_forces_broad_context(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    (scratch["root"] / "later.txt").write_text("later\n", encoding="utf-8")
    git(["add", "later.txt"], scratch["root"])
    git(["commit", "-m", "later"], scratch["root"])

    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert plan["head_drift"] is True
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert "state HEAD drift" in plan["broad_context_reasons"]


def test_dirty_worktree_forces_broad_context(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    (scratch["root"] / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert plan["tree_clean"] is False
    assert plan["route_mode"] == "BROAD_FALLBACK"
    assert "worktree is dirty" in plan["broad_context_reasons"]


@pytest.mark.parametrize(
    "changed_path,expected_domain",
    [
        (".github/workflows/deploy.yaml", "ci"),
        (".opencode/agents/helper.md", "foundry"),
        (".foundry/repo-profiles/mage.json", "foundry"),
    ],
)
def test_dot_directory_path_signals_are_reachable(
    scratch: dict,
    tmp_path: Path,
    changed_path: str,
    expected_domain: str,
) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        objective="Maintain repository configuration.",
        files_modified=[changed_path],
    )
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert expected_domain in plan["selected_domains"]


@pytest.mark.parametrize(
    "objective,expected_domain",
    [
        ("Inspect the context router.", "foundry"),
        ("Inspect Space Bunny executor routing.", "execution_routing"),
        ("Inspect GitHub Action workflow behavior.", "ci"),
        ("Inspect qualification current boundary.", "qualification"),
        ("Inspect evidence provenance.", "evidence"),
    ],
)
def test_text_signal_table_has_positive_controls(
    scratch: dict,
    tmp_path: Path,
    objective: str,
    expected_domain: str,
) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        objective=objective,
        files_modified=[],
    )
    plan = router.derive_plan(
        str(state),
        str(scratch["root"]),
        "cpl",
        write_profiles(tmp_path),
    )
    assert expected_domain in plan["selected_domains"]


def test_provider_words_in_prose_do_not_grant_provider_route(scratch: dict, tmp_path: Path) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        objective="Repair a protocol bridge.",
        dependencies=["Compare against XMage and Forge later."],
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
    assert plan["repo_maps"] == []


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
    assert any("files_modified exceeds" in item for item in plan["broad_context_reasons"])


def test_profile_repository_mismatch_rejected(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    profiles = write_profiles(tmp_path, slug="other/repo")
    with pytest.raises(router.RouterError, match="repository"):
        router.derive_plan(str(state), str(scratch["root"]), "cpl", profiles)


def test_plan_rejects_wrong_workdir_remote_identity(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    git(["remote", "set-url", "origin", "https://github.com/example/other.git"], scratch["root"])
    with pytest.raises(router.RouterError, match="selected canonical repository"):
        router.derive_plan(
            str(state),
            str(scratch["root"]),
            "cpl",
            write_profiles(tmp_path),
        )


def test_plan_rejects_url_rewrite_configuration(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    git(
        ["config", "url.https://mirror.invalid/.insteadOf", "https://github.com/"],
        scratch["root"],
    )
    with pytest.raises(router.RouterError, match="URL rewrite"):
        router.derive_plan(
            str(state),
            str(scratch["root"]),
            "cpl",
            write_profiles(tmp_path),
        )


def test_plan_requires_exact_state_worktree_and_toplevel(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    with pytest.raises(router.RouterError, match="state worktree"):
        router.derive_plan(
            str(state),
            str(scratch["root"] / "src"),
            "cpl",
            write_profiles(tmp_path),
        )


def test_branch_identity_reuses_capsule_fail_closed_gate(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch, branch="wrong")
    with pytest.raises(router.RouterError, match="branch mismatch"):
        router.derive_plan(
            str(state),
            str(scratch["root"]),
            "cpl",
            write_profiles(tmp_path),
        )


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/etc/passwd",
        "../escape.py",
        "src/../escape.py",
        "C:\\secret\\file.py",
        "src/*.py",
        "src/:magic",
        " src/file.py",
    ],
)
def test_changed_paths_reject_unsafe_or_magic_paths(
    scratch: dict, tmp_path: Path, unsafe_path: str
) -> None:
    state = write_state(
        tmp_path / "state.yaml",
        scratch,
        files_modified=[unsafe_path],
    )
    with pytest.raises(router.RouterError, match="bounded repository-relative path"):
        router.derive_plan(
            str(state),
            str(scratch["root"]),
            "cpl",
            write_profiles(tmp_path),
        )


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
    assert "foundry" not in plan["selected_domains"]


def test_engine_profile_requests_map_only_when_bounded(scratch: dict, tmp_path: Path) -> None:
    git(["remote", "set-url", "origin", "https://github.com/example/mage.git"], scratch["root"])
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
                "--profile mage --workdir <DECLARED_REFERENCE_ROOT> --max-depth 3"
            ),
        }
    ]

    blocked = write_state(
        tmp_path / "blocked.yaml",
        scratch,
        repository="example/mage",
        authority_gates=["needs owner"],
        files_modified=[],
    )
    blocked_plan = router.derive_plan(
        str(blocked),
        str(scratch["root"]),
        "mage",
        profiles,
    )
    assert blocked_plan["route_mode"] == "BROAD_FALLBACK"
    assert blocked_plan["repo_maps"] == []


def test_declared_reference_loader_binds_profile_root_head_tree(
    scratch: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = declared_reference(scratch)
    monkeypatch.setenv("FOUNDRY_REFERENCE_ROOTS", json.dumps([ref]))
    loaded = router._load_declared_reference("mage", str(scratch["root"]), profile())
    assert loaded == ref


def test_declared_reference_loader_rejects_missing_or_suppressed_context(
    scratch: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FOUNDRY_REFERENCE_ROOTS", raising=False)
    with pytest.raises(router.RouterError, match="requires FOUNDRY_REFERENCE_ROOTS"):
        router._load_declared_reference("mage", str(scratch["root"]), profile())

    monkeypatch.setenv("FOUNDRY_REFERENCE_ROOTS", json.dumps([declared_reference(scratch)]))
    monkeypatch.setenv("FOUNDRY_ROUTING_SUPPRESSED", "1")
    with pytest.raises(router.RouterError, match="routing is suppressed"):
        router._load_declared_reference("mage", str(scratch["root"]), profile())


def test_declared_reference_loader_rejects_malformed_reference(
    scratch: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = declared_reference(scratch)
    bad["commit"] = "not-a-sha"
    monkeypatch.setenv("FOUNDRY_REFERENCE_ROOTS", json.dumps([bad]))
    with pytest.raises(router.RouterError, match="malformed"):
        router._load_declared_reference("mage", str(scratch["root"]), profile())


def test_repo_map_is_bounded_to_committed_names(scratch: dict) -> None:
    secret = scratch["root"] / "src" / "pkg" / "private.txt"
    secret.write_text("PRIVATE_SENTINEL\n", encoding="utf-8")
    git(["add", "src/pkg/private.txt"], scratch["root"])
    git(["commit", "-m", "private fixture"], scratch["root"])
    ref = declared_reference(scratch)
    result = router.build_repo_map(
        str(scratch["root"]),
        profile="mage",
        profile_data=profile(),
        reference=ref,
        max_depth=2,
    )
    dumped = json.dumps(result)
    assert result["_kind"].startswith("DERIVED_ON_DEMAND")
    assert result["HEAD"] == live_head(scratch)
    assert result["tree"] == live_tree(scratch)
    assert result["expected_HEAD"] == ref["commit"]
    assert result["expected_tree"] == ref["tree"]
    assert result["expected_repo_slug"] == "example/repo"
    assert "src/pkg" in result["directories"]
    assert "PRIVATE_SENTINEL" not in dumped
    assert result["dirty_entries"] == 0


def test_repo_map_prefix_scopes_directories_and_root_entries(scratch: dict) -> None:
    ref = declared_reference(scratch)
    result = router.build_repo_map(
        str(scratch["root"]),
        profile="mage",
        profile_data=profile(),
        reference=ref,
        max_depth=2,
        prefixes=["src"],
    )
    assert result["prefixes"] == ["src"]
    assert all(path.startswith("src") for path in result["directories"])
    assert result["root_entries"] == ["src"]


def test_repo_map_depth_and_prefix_bounds_are_explicit(scratch: dict) -> None:
    ref = declared_reference(scratch)
    with pytest.raises(router.RouterError, match="max-depth"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=ref,
            max_depth=7,
        )
    with pytest.raises(router.RouterError, match="deeper than max-depth"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=ref,
            max_depth=1,
            prefixes=["src/pkg"],
        )
    prefixes = [f"src/p{i}" for i in range(router.MAX_MAP_PREFIXES + 1)]
    with pytest.raises(router.RouterError, match="at most"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=ref,
            prefixes=prefixes,
        )


@pytest.mark.parametrize(
    "unsafe_prefix",
    ["/src", "../src", "src/*", ":(glob)src/**", "C:\\src"],
)
def test_repo_map_rejects_unsafe_prefixes(scratch: dict, unsafe_prefix: str) -> None:
    with pytest.raises(router.RouterError, match="bounded repository-relative path"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=declared_reference(scratch),
            prefixes=[unsafe_prefix],
        )


def test_repo_map_rejects_wrong_profile_repository(scratch: dict) -> None:
    with pytest.raises(router.RouterError, match="does not match profile"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(slug="example/other"),
            reference=declared_reference(scratch),
        )


def test_repo_map_rejects_source_lock_drift(scratch: dict) -> None:
    with pytest.raises(router.RouterError, match="verification failed"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=declared_reference(scratch, commit="f" * 40),
        )


def test_repo_map_rejects_subdirectory_root(scratch: dict) -> None:
    with pytest.raises(router.RouterError, match="declared reference root"):
        router.build_repo_map(
            str(scratch["root"] / "src"),
            profile="mage",
            profile_data=profile(),
            reference=declared_reference(scratch),
        )


def test_repo_map_rejects_url_rewrite_configuration(scratch: dict) -> None:
    git(
        ["config", "url.https://mirror.invalid/.insteadOf", "https://github.com/"],
        scratch["root"],
    )
    with pytest.raises(router.RouterError, match="URL rewrite"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=declared_reference(scratch),
        )


def test_repo_map_does_not_use_recursive_ls_tree(
    scratch: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    original = router._git

    def recording_git(args: list[str], workdir: str) -> str:
        calls.append(args)
        return original(args, workdir)

    monkeypatch.setattr(router, "_git", recording_git)
    router.build_repo_map(
        str(scratch["root"]),
        profile="mage",
        profile_data=profile(),
        reference=declared_reference(scratch),
        max_depth=2,
    )
    assert all("-r" not in args for args in calls)


def test_repo_map_output_caps_fail_closed(scratch: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router, "MAX_MAP_DIRECTORIES", 1)
    with pytest.raises(router.RouterError, match="directories"):
        router.build_repo_map(
            str(scratch["root"]),
            profile="mage",
            profile_data=profile(),
            reference=declared_reference(scratch),
        )


def test_plan_is_deterministic(scratch: dict, tmp_path: Path) -> None:
    state = write_state(tmp_path / "state.yaml", scratch)
    profiles = write_profiles(tmp_path)
    first = router.derive_plan(str(state), str(scratch["root"]), "cpl", profiles)
    second = router.derive_plan(str(state), str(scratch["root"]), "cpl", profiles)
    assert first == second
