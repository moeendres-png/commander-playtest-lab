#!/usr/bin/env python3
"""B11: separate CI/tooling from the installed base product's security evidence."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts import verify_packaging_smoke as packaging
except ModuleNotFoundError:
    import verify_packaging_smoke as packaging  # type: ignore[no-redef]

SCHEMA = "security-evidence-scopes/1"
SCOPES = ("ci-tooling", "runtime-product")
TOOLS = {"pip-audit": "2.10.1", "cyclonedx-bom": "7.3.0", "pip-licenses": "5.5.5"}
STEPS = (
    "prepare-scopes",
    "audit-tooling",
    "audit-product",
    "sbom-tooling",
    "sbom-product",
    "licenses-tooling",
    "licenses-product",
)
INVENTORY_PROBE = """import importlib.metadata as m, json, platform, sys
print(json.dumps({'python':sys.version.split()[0], 'platform':platform.platform(),
'packages':sorted([{'name':d.metadata['Name'],'version':d.version} for d in m.distributions()],key=lambda d:d['name'].lower())}))
"""


def canonical_inventory(rows: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        name = packaging.normalize_distribution_name(row["name"])
        if not name or name in result or not isinstance(row["version"], str) or not row["version"]:
            raise ValueError("invalid/duplicate distribution")
        result[name] = row["version"]
    return dict(sorted(result.items()))


def inventory(interpreter: Path, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(interpreter), "-I", "-c", INVENTORY_PROBE],
        cwd=cwd,
        env=packaging.isolated_child_environment(),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    record = json.loads(result.stdout)
    record["packages"] = canonical_inventory(record["packages"])
    return record


def assert_inventory(observed: dict[str, str], expected: dict[str, str]) -> None:
    if observed != expected:
        raise ValueError(
            f"scope inventory mismatch: missing={sorted(expected.keys() - observed.keys())}, extra={sorted(observed.keys() - expected.keys())}, changed={sorted(n for n in expected.keys() & observed.keys() if expected[n] != observed[n])}"
        )


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source(repo: Path) -> dict[str, Any]:
    sha, tree = packaging.read_source_identity(repo)
    result: dict[str, Any] = {
        "sha": sha,
        "tree": tree,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "extras": [],
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "inputs": {},
    }
    for name in (
        "pyproject.toml",
        "requirements/lock.txt",
        "scripts/security_evidence.py",
        "scripts/verify_packaging_smoke.py",
        ".github/workflows/ci.yml",
    ):
        path = repo / name
        result["inputs"][name] = packaging.sha256_file(path)
        committed = packaging._git_text(repo, "rev-parse", f"{sha}:{name}")
        if committed is None or packaging._git_blob_id(path.read_bytes()) != committed:
            raise ValueError("source input differs from committed bytes: " + name)
    return result


def prepare(args: argparse.Namespace) -> int:
    repo, out = args.repo.resolve(), args.out.resolve()
    record: dict[str, Any] = {"schema": SCHEMA, "status": "NOT_RUN", "steps": {}, "scopes": {}}
    destination = out / "SCOPES.json"
    out.mkdir(parents=True, exist_ok=True)
    try:
        record["source"] = source(repo)
        blocks = packaging.lock_blocks((repo / "requirements/lock.txt").read_text())
        # All generator packages/transitives must match the installed hash lock.
        record["tools"] = {name: importlib.metadata.version(name) for name in TOOLS}
        if record["tools"] != TOOLS:
            raise ValueError("security tool version mismatch")
        tooling = inventory(Path(sys.executable), out.parent)
        contract = packaging.read_package_contract(repo / "pyproject.toml")
        for name, version in tooling["packages"].items():
            if name in {"pip", contract.normalized_name}:
                continue  # bootstrap installer and explicitly source-bound project
            if name not in blocks or blocks[name][0] != version:
                raise ValueError("tooling distribution is outside the hash lock: " + name)
        tooling["scope"] = "complete CI environment, includes bootstrap pip; not shipped product"
        tooling["bootstrap_pip"] = {
            "version": tooling["packages"].get("pip"),
            "used_for_audit_resolution": False,
        }
        record["scopes"]["ci-tooling"] = tooling
        runtime = args.runtime.resolve()
        smoke = out / "RUNTIME_WHEEL_SMOKE.json"
        result = packaging.main(
            [
                "smoke",
                "--repo",
                str(repo),
                "--wheel-dir",
                str(args.wheel_dir.resolve()),
                "--venv-dir",
                str(runtime),
                "--scratch-dir",
                str(runtime.parent),
                "--output",
                str(smoke),
            ]
        )
        if result:
            raise ValueError("runtime wheel smoke did not PASS")
        wheel = json.loads(smoke.read_text())
        record["wheel"] = {
            "filename": wheel["wheel_filename"],
            "sha256": wheel["wheel_sha256"],
            "smoke_sha256": packaging.sha256_file(smoke),
        }
        closure = wheel["dependency_closure"]["requirements"]
        expected = dict(item.split("==", 1) for item in closure)
        expected[contract.normalized_name] = contract.version
        interpreter = packaging.venv_bin(runtime, "python")
        # pip check ran inside B9. Remove bootstrap installer before any product
        # inventory/SBOM/license collection, so it cannot become a shipped component.
        if "pip" not in expected:
            subprocess.run(
                [str(interpreter), "-I", "-m", "pip", "uninstall", "-y", "pip"],
                cwd=runtime.parent,
                env=packaging.isolated_child_environment(),
                check=True,
                timeout=120,
            )
        product = inventory(interpreter, runtime.parent)
        assert_inventory(product["packages"], expected)
        product["scope"] = (
            "actual wheel plus wheel-declared base runtime closure; no extras; bootstrap pip removed"
        )
        product["dependency_closure"] = closure
        product["interpreter"] = str(interpreter)
        record["scopes"]["runtime-product"] = product
        for scope in SCOPES:
            directory = out / scope
            directory.mkdir(parents=True, exist_ok=True)
            write(directory / "inventory.json", record["scopes"][scope])
            packages = record["scopes"][scope]["packages"]
            # The private local project has no public vulnerability-service identity.
            # It remains in both inventories/SBOMs/licenses, explicitly excluded only
            # from public dependency queries, as previously with --exclude-editable.
            (directory / "requirements.txt").write_text(
                "".join(f"{n}=={v}\n" for n, v in packages.items() if n != contract.normalized_name)
            )
        record["dependency_audit_exclusion"] = {
            "name": contract.normalized_name,
            "reason": "private project bound by source/wheel, not a public PyPI lookup",
        }
        record["status"] = "PASS"
    except Exception as exc:
        record["status"] = "FAIL"
        record["error"] = f"{type(exc).__name__}: {exc}"
    write(destination, record)
    print("SECURITY_SCOPE_PREPARE=" + record["status"])
    return 0 if record["status"] == "PASS" else 1


def sbom_inventory(document: dict[str, Any]) -> dict[str, str]:
    rows = [
        {"name": item["name"], "version": item["version"]}
        for item in document.get("components", [])
    ]
    root = document.get("metadata", {}).get("component")
    if root and root.get("version") and not any(row["name"] == root["name"] for row in rows):
        rows.append({"name": root["name"], "version": root["version"]})
    return canonical_inventory(rows)


def license_inventory(document: list[dict[str, Any]]) -> dict[str, str]:
    return canonical_inventory(
        [{"name": item["Name"], "version": item["Version"]} for item in document]
    )


def validate_artifacts(out: Path, record: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for scope in SCOPES:
        expected = record["scopes"][scope]["packages"]
        directory = out / scope
        for name in (
            "inventory.json",
            "requirements.txt",
            "sbom.cdx.json",
            "licenses.json",
            "dependency-audit.json",
        ):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("artifact is not a regular file")
        assert_inventory(
            json.loads((directory / "inventory.json").read_text())["packages"], expected
        )
        assert_inventory(
            sbom_inventory(json.loads((directory / "sbom.cdx.json").read_text())), expected
        )
        assert_inventory(
            license_inventory(json.loads((directory / "licenses.json").read_text())), expected
        )
        audit = json.loads((directory / "dependency-audit.json").read_text())
        exclusion = record["dependency_audit_exclusion"]["name"]
        rows = [
            {"name": item["name"], "version": item["version"]} for item in audit["dependencies"]
        ]
        assert_inventory(
            canonical_inventory(rows), {n: v for n, v in expected.items() if n != exclusion}
        )
        if any(item.get("vulns") or item.get("skip_reason") for item in audit["dependencies"]):
            raise ValueError("vulnerable or uncollected dependency in " + scope)
        for name in (
            "inventory.json",
            "requirements.txt",
            "sbom.cdx.json",
            "licenses.json",
            "dependency-audit.json",
        ):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("artifact is not a regular file")
            result.append(
                {
                    "scope": scope,
                    "path": path.relative_to(out).as_posix(),
                    "sha256": packaging.sha256_file(path),
                }
            )
    return result


def seal(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    index: dict[str, Any] = {"schema": SCHEMA, "status": "NOT_RUN", "artifacts": [], "steps": {}}
    try:
        record = json.loads((out / "SCOPES.json").read_text())
        index["source"] = record.get("source")
        index["tools"] = record.get("tools")
        steps = json.loads(os.environ.get("B11_STEP_RESULTS", "{}"))
        index["steps"] = {name: steps.get(name, {}).get("outcome", "NOT_RUN") for name in STEPS}
        if record.get("schema") != SCHEMA or record.get("status") != "PASS":
            raise ValueError("scope preparation did not PASS")
        if any(value != "success" for value in index["steps"].values()):
            raise ValueError("a required security evidence step failed or was not run")
        if source(args.repo.resolve()) != record["source"]:
            raise ValueError("source drift")
        assert_inventory(
            inventory(Path(sys.executable), out.parent)["packages"],
            record["scopes"]["ci-tooling"]["packages"],
        )
        if {name: importlib.metadata.version(name) for name in TOOLS} != record["tools"]:
            raise ValueError("security tooling drift")
        current = inventory(
            packaging.venv_bin(args.runtime.resolve(), "python"), args.runtime.resolve().parent
        )
        assert_inventory(current["packages"], record["scopes"]["runtime-product"]["packages"])
        if (
            packaging.sha256_file(out / "RUNTIME_WHEEL_SMOKE.json")
            != record["wheel"]["smoke_sha256"]
        ):
            raise ValueError("wheel smoke digest drift")
        contract = packaging.read_package_contract(args.repo / "pyproject.toml")
        wheel = packaging.select_project_wheel(args.wheel_dir, contract)
        if packaging.sha256_file(wheel) != record["wheel"]["sha256"]:
            raise ValueError("wheel digest drift")
        index["artifacts"] = validate_artifacts(out, record)
        index["scopes_sha256"] = packaging.sha256_file(out / "SCOPES.json")
        index["wheel"] = record["wheel"]
        index["status"] = "PASS"
    except Exception as exc:
        index["status"] = "FAIL"
        index["error"] = f"{type(exc).__name__}: {exc}"
    write(out / "SECURITY_EVIDENCE_INDEX.json", index)
    print("SECURITY_EVIDENCE=" + index["status"])
    return 0 if index["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "seal"))
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/security"))
    args = parser.parse_args()
    return prepare(args) if args.mode == "prepare" else seal(args)


if __name__ == "__main__":
    sys.exit(main())
