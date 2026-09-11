"""WS-A1D Docker pin-authority regression tests.

The sole machine-readable authority for current engine pins is
``config/rules_engines.json``. These tests prove the supported Docker/Compose
engine path resolves build identity from that manifest at build time, cannot
silently materialize a stale engine or the wrong provider repository, and
fails closed when authority is missing or inconsistent.

Resolver behavior is tested functionally through
``scripts/docker_resolve_engine_pin.py``. Dockerfile/Compose/devcontainer/docs
properties are tested structurally (no second volatile pin may live there).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

STALE_XMAGE_PIN = "06d166b098ad36b277edef01116472203d5a047e"
STALE_FORGE_PIN = "852066bf4f761b302ed17cb011999d8a8fe08ad6"
CANONICAL_XMAGE_PIN = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
CANONICAL_FORGE_PIN = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
_HEX40 = re.compile(r"[0-9a-f]{40}")
_MANIFEST_REL = "config/rules_engines.json"


def _manifest(repo_root: Path) -> dict:
    return json.loads((repo_root / _MANIFEST_REL).read_text(encoding="utf-8"))


def _resolver(repo_root: Path):
    return _load_script(repo_root, "scripts/docker_resolve_engine_pin.py")


def _load_script(repo_root: Path, rel: str):
    path = repo_root / rel
    name = Path(rel).stem
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve string annotations,
    # mirroring what the normal import system guarantees.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_xmage_resolves_canonical_fork_identity(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    pin = module.resolve("xmage", manifest)
    assert pin.provider == "xmage"
    assert pin.repository == manifest["primary_engine"]["repository"]
    assert pin.commit == manifest["primary_engine"]["commit"] == CANONICAL_XMAGE_PIN
    assert pin.protocol_version == manifest["protocol_version"]
    assert "mage" in pin.repository.lower()
    assert "forge" not in pin.repository.lower()


def test_forge_resolves_canonical_identity(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    pin = module.resolve("forge", manifest)
    assert pin.provider == "forge"
    assert pin.repository == manifest["secondary_engine"]["repository"]
    assert pin.commit == manifest["secondary_engine"]["commit"] == CANONICAL_FORGE_PIN
    assert pin.protocol_version == manifest["protocol_version"]
    assert "forge" in pin.repository.lower()
    assert "mage" not in pin.repository.lower()


def test_providers_resolve_distinct_identities(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    xmage = module.resolve("xmage", manifest)
    forge = module.resolve("forge", manifest)
    assert xmage.repository != forge.repository
    assert xmage.commit != forge.commit


def test_unknown_provider_fails_closed(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    for bad in ("upstream", "XMAGE", "", "tactical", "primary_engine"):
        try:
            module.resolve(bad, manifest)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"provider {bad!r} did not fail closed")


def test_missing_section_fails_closed(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    for key in ("primary_engine", "secondary_engine"):
        mutated = copy.deepcopy(manifest)
        del mutated[key]
        provider = "xmage" if key == "primary_engine" else "forge"
        try:
            module.resolve(provider, mutated)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"missing {key} did not fail closed")


def test_malformed_commit_fails_closed(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    for bad in ("", "short", STALE_XMAGE_PIN.upper(), "g" * 40, "0" * 39, "0" * 41):
        mutated = copy.deepcopy(manifest)
        mutated["primary_engine"]["commit"] = bad
        try:
            module.resolve("xmage", mutated)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"commit {bad!r} did not fail closed")


def test_malformed_repository_fails_closed(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    for bad in (
        "",
        "https://github.com/magefree/mage",
        "http://github.com/moeendres-png/mage.git",
        "git@github.com:moeendres-png/mage.git",
        "https://example.com/mage.git",
    ):
        mutated = copy.deepcopy(manifest)
        mutated["primary_engine"]["repository"] = bad
        try:
            module.resolve("xmage", mutated)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"repository {bad!r} did not fail closed")


def test_cross_wired_repository_fails_closed(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    mutated = copy.deepcopy(manifest)
    mutated["primary_engine"]["repository"], mutated["secondary_engine"]["repository"] = (
        mutated["secondary_engine"]["repository"],
        mutated["primary_engine"]["repository"],
    )
    for provider in ("xmage", "forge"):
        try:
            module.resolve(provider, mutated)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"cross-wired {provider} repository did not fail closed")


def test_missing_protocol_fails_closed(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    mutated = copy.deepcopy(manifest)
    del mutated["protocol_version"]
    try:
        module.resolve("xmage", mutated)
    except module.PinResolutionError:
        return
    raise AssertionError("missing protocol_version did not fail closed")


def test_cli_shell_output_resolves_without_stale_defaults(repo_root: Path) -> None:
    script = repo_root / "scripts/docker_resolve_engine_pin.py"
    for provider, prefix in (("xmage", "XMAGE"), ("forge", "FORGE")):
        completed = subprocess.run(
            [sys.executable, str(script), "--provider", provider],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        values = dict(
            line.split("=", 1) for line in completed.stdout.strip().splitlines() if "=" in line
        )
        assert (
            values[f"{prefix}_ENGINE_COMMIT"]
            == _manifest(repo_root)[
                "primary_engine" if provider == "xmage" else "secondary_engine"
            ]["commit"]
        )
        assert values[f"{prefix}_ENGINE_REPOSITORY"].endswith(".git")
        assert (
            values[f"{prefix}_ENGINE_PROTOCOL_VERSION"] == _manifest(repo_root)["protocol_version"]
        )
        assert STALE_XMAGE_PIN not in completed.stdout
        assert STALE_FORGE_PIN not in completed.stdout


def test_cli_failures_are_nonzero_without_stdout_identity(repo_root: Path) -> None:
    script = repo_root / "scripts/docker_resolve_engine_pin.py"
    cases = [
        ["--provider", "upstream"],
        ["--provider", "xmage", "--manifest", str(repo_root / "does-not-exist.json")],
    ]
    for args in cases:
        completed = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode != 0, args
        assert _HEX40.search(completed.stdout) is None, args


def test_dockerfiles_declare_required_args_without_pin_defaults(repo_root: Path) -> None:
    for rel in ("docker/xmage/Dockerfile", "docker/forge/Dockerfile"):
        text = (repo_root / rel).read_text(encoding="utf-8")
        assert _HEX40.search(text) is None, rel
        for arg in ("ARG ENGINE_REPOSITORY", "ARG ENGINE_COMMIT", "ARG ENGINE_PROTOCOL_VERSION"):
            matches = [line for line in text.splitlines() if line.startswith(arg)]
            assert len(matches) == 1, (rel, arg)
            assert "=" not in matches[0], (rel, arg)
        assert "engine-provenance.json" in text, rel
        assert "git clone" in text, rel


def test_dockerfiles_refuse_cross_provider_repositories(repo_root: Path) -> None:
    xmage_text = (repo_root / "docker/xmage/Dockerfile").read_text(encoding="utf-8")
    forge_text = (repo_root / "docker/forge/Dockerfile").read_text(encoding="utf-8")
    assert "magefree/mage" not in xmage_text
    assert "forge" in xmage_text.lower()
    assert "mage" in forge_text.lower()


def test_compose_resolves_build_identity_from_wrapper(repo_root: Path) -> None:
    text = (repo_root / "docker-compose.engine.yml").read_text(encoding="utf-8")
    assert _HEX40.search(text) is None
    assert "1.0.0" not in text
    xmage_dockerfile = text.index("docker/xmage/Dockerfile")
    forge_dockerfile = text.index("docker/forge/Dockerfile")
    xmage_args = text.index("XMAGE_ENGINE_REPOSITORY")
    forge_args = text.index("FORGE_ENGINE_REPOSITORY")
    assert xmage_dockerfile < xmage_args < forge_dockerfile < forge_args
    for var in (
        "XMAGE_ENGINE_REPOSITORY",
        "XMAGE_ENGINE_COMMIT",
        "XMAGE_ENGINE_PROTOCOL_VERSION",
        "FORGE_ENGINE_REPOSITORY",
        "FORGE_ENGINE_COMMIT",
        "FORGE_ENGINE_PROTOCOL_VERSION",
    ):
        assert "${" + var + ":?" in text, var
    assert text.count('ENGINE_PROTOCOL_VERSION: "2.0.0"') == 2


def test_compose_protocol_matches_manifest(repo_root: Path) -> None:
    text = (repo_root / "docker-compose.engine.yml").read_text(encoding="utf-8")
    protocol = _manifest(repo_root)["protocol_version"]
    assert protocol == "2.0.0"
    assert f'ENGINE_PROTOCOL_VERSION: "{protocol}"' in text


def test_devcontainer_and_env_example_match_manifest_protocol(repo_root: Path) -> None:
    protocol = _manifest(repo_root)["protocol_version"]
    devcontainer = (repo_root / ".devcontainer/devcontainer.json").read_text(encoding="utf-8")
    assert '"ENGINE_PROTOCOL_VERSION": "1.0.0"' not in devcontainer
    assert protocol in devcontainer
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert f"ENGINE_PROTOCOL_VERSION={protocol}" in env_example


def test_docs_establish_no_competing_pin_authority(repo_root: Path) -> None:
    for rel in (
        "docs/engine_setup.md",
        "integrations/xmage/README.md",
        "integrations/forge/README.md",
    ):
        text = (repo_root / rel).read_text(encoding="utf-8")
        assert _HEX40.search(text) is None, rel
        assert "config/rules_engines.json" in text, rel


def test_stale_pins_survive_only_as_historical_provenance(repo_root: Path) -> None:
    live_surfaces = [
        "docker/xmage/Dockerfile",
        "docker/forge/Dockerfile",
        "docker-compose.engine.yml",
        ".devcontainer/devcontainer.json",
        "scripts/docker_resolve_engine_pin.py",
        "scripts/docker_build_engine.sh",
        "scripts/verify_container_provenance.py",
        "scripts/engine_container_entrypoint.sh",
        "docs/engine_setup.md",
        "integrations/xmage/README.md",
        "integrations/forge/README.md",
    ]
    for rel in live_surfaces:
        text = (repo_root / rel).read_text(encoding="utf-8")
        assert STALE_XMAGE_PIN not in text, rel
        assert STALE_FORGE_PIN not in text, rel
    provenance = (repo_root / "src/commander_lab/engine/rules/phase85.py").read_text(
        encoding="utf-8"
    )
    assert STALE_XMAGE_PIN in provenance
    assert STALE_FORGE_PIN in provenance
    assert '"executed": False' in provenance


def test_build_wrapper_uses_manifest_resolver(repo_root: Path) -> None:
    text = (repo_root / "scripts/docker_build_engine.sh").read_text(encoding="utf-8")
    assert "docker_resolve_engine_pin.py" in text
    assert "docker-compose.engine.yml" in text
    assert "set -euo pipefail" in text


def test_manifest_authority_and_provider_truth_preserved(repo_root: Path) -> None:
    config = _manifest(repo_root)
    assert config["primary_engine"]["commit"] == CANONICAL_XMAGE_PIN
    assert config["secondary_engine"]["commit"] == CANONICAL_FORGE_PIN
    assert config["protocol_version"] == "2.0.0"
    assert config["provider_decision"] == "NO_PROVIDER_READY"
    assert config["current_runtime"]["provider_selected"] is False
    assert config["current_runtime"]["production_provider"] is None


def _gate_module(repo_root: Path):
    return _load_script(repo_root, "scripts/verify_container_provenance.py")


def _gate_fixture(tmp_path: Path, repo_root: Path, provider: str = "xmage"):

    manifest = _manifest(repo_root)
    manifest_path = tmp_path / "rules_engines.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    resolver = _resolver(repo_root)
    pin = resolver.resolve(provider, manifest)
    provenance = {
        "provider": pin.provider,
        "repository": pin.repository,
        "commit": pin.commit,
        "protocol_version": pin.protocol_version,
    }
    provenance_path = tmp_path / "engine-provenance.json"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    return provenance_path, manifest_path


def test_provenance_gate_accepts_canonical_image(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    assert module.check("xmage", provenance_path, manifest_path) == 0


def test_provenance_gate_rejects_stale_commit(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["commit"] = STALE_XMAGE_PIN
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert module.check("xmage", provenance_path, manifest_path) == 3


def test_provenance_gate_rejects_cross_wired_repository(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["repository"] = _manifest(repo_root)["secondary_engine"]["repository"]
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert module.check("xmage", provenance_path, manifest_path) == 3


def test_provenance_gate_rejects_protocol_mismatch(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["protocol_version"] = "1.0.0"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert module.check("xmage", provenance_path, manifest_path) == 3


def test_provenance_gate_fails_without_record_or_manifest(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    assert module.check("xmage", tmp_path / "absent.json", manifest_path) == 3
    assert module.check("xmage", provenance_path, tmp_path / "absent.json") == 3


def test_provenance_gate_rejects_unreadable_record(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    provenance_path.write_text("{not json", encoding="utf-8")
    assert module.check("xmage", provenance_path, manifest_path) == 3


def test_entrypoint_enforces_provenance_gate(repo_root: Path) -> None:
    text = (repo_root / "scripts/engine_container_entrypoint.sh").read_text(encoding="utf-8")
    assert "verify_container_provenance.py" in text
    assert "ENGINE_START_COMMAND is required" in text


def test_provenance_gate_fails_for_unknown_provider(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    assert module.check("upstream", provenance_path, manifest_path) == 3
    assert module.check("", provenance_path, manifest_path) == 3


def test_provenance_gate_fails_for_unreadable_manifest(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, _ = _gate_fixture(tmp_path, repo_root)
    bad_manifest = tmp_path / "bad-manifest.json"
    bad_manifest.write_text("{not json", encoding="utf-8")
    assert module.check("xmage", provenance_path, bad_manifest) == 3


def test_provenance_gate_fails_for_provider_mismatch(tmp_path: Path, repo_root: Path) -> None:
    module = _gate_module(repo_root)
    provenance_path, manifest_path = _gate_fixture(tmp_path, repo_root)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["provider"] = "forge"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert module.check("xmage", provenance_path, manifest_path) == 3


def test_resolver_requires_manifest_provider_field(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    assert module.resolve("xmage", manifest).provider == "xmage"
    assert module.resolve("forge", manifest).provider == "forge"
    swapped = copy.deepcopy(manifest)
    swapped["primary_engine"]["provider"] = "forge"
    swapped["secondary_engine"]["provider"] = "xmage"
    for provider in ("xmage", "forge"):
        try:
            module.resolve(provider, swapped)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"swapped provider field accepted for {provider!r}")


def test_resolver_rejects_missing_or_malformed_provider_field(repo_root: Path) -> None:
    module = _resolver(repo_root)
    manifest = _manifest(repo_root)
    for bad in ("", "XMAGE", "Forge ", "tactical", None, 42):
        mutated = copy.deepcopy(manifest)
        mutated["primary_engine"]["provider"] = bad
        try:
            module.resolve("xmage", mutated)
        except module.PinResolutionError:
            continue
        raise AssertionError(f"provider field {bad!r} did not fail closed")
    mutated = copy.deepcopy(manifest)
    del mutated["secondary_engine"]["provider"]
    try:
        module.resolve("forge", mutated)
    except module.PinResolutionError:
        return
    raise AssertionError("missing provider field did not fail closed")


def _gnu_bash() -> str:
    executable = shutil.which("bash")
    if executable is None:
        pytest.skip("bash is unavailable on this runner")
    return executable


def _run_entrypoint(
    repo_root: Path, tmp_path: Path, extra_env: dict
) -> tuple[subprocess.CompletedProcess, bool]:
    marker = tmp_path / "engine-started.marker"
    if marker.exists():
        marker.unlink()
    env = dict(os.environ)
    env["ENGINE_START_COMMAND"] = 'touch "$WS_A1D_MARKER"'
    env["WS_A1D_MARKER"] = str(marker)
    env["CONTAINER_GATE_SCRIPT"] = str(repo_root / "scripts/verify_container_provenance.py")
    env.update(extra_env)
    completed = subprocess.run(
        [_gnu_bash(), str(repo_root / "scripts/engine_container_entrypoint.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return completed, marker.exists()


def test_entrypoint_starts_engine_for_canonical_provenance(tmp_path: Path, repo_root: Path) -> None:
    provenance = tmp_path / "engine-provenance.json"
    manifest = tmp_path / "rules_engines.json"
    live_manifest = _manifest(repo_root)
    manifest.write_text(json.dumps(live_manifest), encoding="utf-8")
    provenance.write_text(
        json.dumps(
            {
                "provider": "xmage",
                "repository": live_manifest["primary_engine"]["repository"],
                "commit": live_manifest["primary_engine"]["commit"],
                "protocol_version": live_manifest["protocol_version"],
            }
        ),
        encoding="utf-8",
    )
    completed, started = _run_entrypoint(
        repo_root,
        tmp_path,
        {
            "ENGINE_PROVIDER": "xmage",
            "CONTAINER_PROVENANCE_PATH": str(provenance),
            "PIN_MANIFEST_PATH": str(manifest),
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert started


def _entrypoint_negative_cases(tmp_path: Path, repo_root: Path) -> dict:
    live_manifest = _manifest(repo_root)
    manifest = tmp_path / "rules_engines.json"
    manifest.write_text(json.dumps(live_manifest), encoding="utf-8")
    provenance = tmp_path / "engine-provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "provider": "xmage",
                "repository": live_manifest["primary_engine"]["repository"],
                "commit": live_manifest["primary_engine"]["commit"],
                "protocol_version": live_manifest["protocol_version"],
            }
        ),
        encoding="utf-8",
    )
    stale = tmp_path / "stale-provenance.json"
    stale.write_text(
        json.dumps(
            {
                "provider": "xmage",
                "repository": live_manifest["primary_engine"]["repository"],
                "commit": STALE_XMAGE_PIN,
                "protocol_version": live_manifest["protocol_version"],
            }
        ),
        encoding="utf-8",
    )
    base = {
        "ENGINE_PROVIDER": "xmage",
        "CONTAINER_PROVENANCE_PATH": str(provenance),
        "PIN_MANIFEST_PATH": str(manifest),
    }
    return {
        "missing-provenance": {
            **base,
            "CONTAINER_PROVENANCE_PATH": str(tmp_path / "absent.json"),
        },
        "missing-manifest": {**base, "PIN_MANIFEST_PATH": str(tmp_path / "absent.json")},
        "stale-commit": {**base, "CONTAINER_PROVENANCE_PATH": str(stale)},
        "missing-gate": {**base, "CONTAINER_GATE_SCRIPT": str(tmp_path / "absent-gate.py")},
        "missing-python": {**base, "PYTHON3_BIN": "/nonexistent/python3-ws-a1d"},
    }


def test_entrypoint_never_starts_engine_without_proven_authority(
    tmp_path: Path, repo_root: Path
) -> None:
    for name, extra_env in _entrypoint_negative_cases(tmp_path, repo_root).items():
        completed, started = _run_entrypoint(repo_root, tmp_path, extra_env)
        assert completed.returncode != 0, name
        assert not started, name


def _install_fake_docker(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    shim = bindir / "docker"
    argv_log = tmp_path / "docker-argv.log"
    env_log = tmp_path / "docker-env.log"
    shim.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$FAKE_DOCKER_ARGV"\n'
        'env > "$FAKE_DOCKER_ENV"\nexit 0\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("FAKE_DOCKER_ARGV", str(argv_log))
    monkeypatch.setenv("FAKE_DOCKER_ENV", str(env_log))
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    return argv_log, env_log


def _fake_docker_env(env_log: Path) -> dict:
    values: dict[str, str] = {}
    for line in env_log.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _assert_complete_wrapper_environment(repo_root: Path, env: dict) -> None:
    manifest = _manifest(repo_root)
    assert env["XMAGE_ENGINE_REPOSITORY"] == manifest["primary_engine"]["repository"]
    assert env["XMAGE_ENGINE_COMMIT"] == manifest["primary_engine"]["commit"]
    assert env["XMAGE_ENGINE_PROTOCOL_VERSION"] == manifest["protocol_version"]
    assert env["FORGE_ENGINE_REPOSITORY"] == manifest["secondary_engine"]["repository"]
    assert env["FORGE_ENGINE_COMMIT"] == manifest["secondary_engine"]["commit"]
    assert env["FORGE_ENGINE_PROTOCOL_VERSION"] == manifest["protocol_version"]


def test_wrapper_exports_both_identities_for_xmage(
    tmp_path: Path, repo_root: Path, monkeypatch
) -> None:
    argv_log, env_log = _install_fake_docker(tmp_path, monkeypatch)
    completed = subprocess.run(
        [_gnu_bash(), str(repo_root / "scripts/docker_build_engine.sh"), "xmage", "build"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0, completed.stderr
    _assert_complete_wrapper_environment(repo_root, _fake_docker_env(env_log))
    argv = argv_log.read_text(encoding="utf-8").split()
    assert "--profile" in argv
    assert argv[argv.index("--profile") + 1] == "xmage"


def test_wrapper_exports_both_identities_for_forge(
    tmp_path: Path, repo_root: Path, monkeypatch
) -> None:
    argv_log, env_log = _install_fake_docker(tmp_path, monkeypatch)
    completed = subprocess.run(
        [_gnu_bash(), str(repo_root / "scripts/docker_build_engine.sh"), "forge", "build"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0, completed.stderr
    _assert_complete_wrapper_environment(repo_root, _fake_docker_env(env_log))
    argv = argv_log.read_text(encoding="utf-8").split()
    assert "--profile" in argv
    assert argv[argv.index("--profile") + 1] == "forge"


def test_wrapper_never_invokes_docker_without_authority(
    tmp_path: Path, repo_root: Path, monkeypatch
) -> None:
    argv_log, env_log = _install_fake_docker(tmp_path, monkeypatch)
    malformed = tmp_path / "malformed-manifest.json"
    malformed.write_text("{not json", encoding="utf-8")
    missing_section = tmp_path / "missing-section.json"
    mutated = copy.deepcopy(_manifest(repo_root))
    del mutated["secondary_engine"]
    missing_section.write_text(json.dumps(mutated), encoding="utf-8")
    cases = [
        (["bogus"], dict()),
        (
            ["xmage", "build"],
            {"PIN_MANIFEST_PATH": str(malformed)},
        ),
        (
            ["forge", "build"],
            {"PIN_MANIFEST_PATH": str(tmp_path / "absent-manifest.json")},
        ),
        (
            ["xmage", "build"],
            {"PIN_MANIFEST_PATH": str(missing_section)},
        ),
    ]
    for args, extra_env in cases:
        for log in (argv_log, env_log):
            if log.exists():
                log.unlink()
        env = dict(os.environ)
        env.update(extra_env)
        completed = subprocess.run(
            [_gnu_bash(), str(repo_root / "scripts/docker_build_engine.sh"), *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(repo_root),
            env=env,
        )
        assert completed.returncode != 0, args
        assert not argv_log.exists(), args
        assert not env_log.exists(), args
