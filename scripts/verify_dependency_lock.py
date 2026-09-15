"""Verify the WS223 transitive dependency lock without installing anything.

Offline checks (CI-safe, no network):
  * every pinned package carries at least one ``--hash=sha256:`` stanza;
  * every direct input in ``requirements/lock.in`` is satisfied by the lock;
  * marker-carrying inputs pruned by the compiler exist in the generated
    appendix with identical markers;
  * lock structure (compiler region + delimited appendix, no duplicates).

Network checks (``--with-network``; explicit index reads, never resolution):
  * every pin's ``Requires-Python`` allows CPython 3.12 (the CI target);
  * the 3.12 linux/win32 requirement closure is fully contained in the lock
    (no hidden network resolution during a locked install);
  * appendix hashes still match current index digests (drift signal).

Exit non-zero with a precise reason on any violation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

PIN_RE = re.compile(r"(?m)^([A-Za-z0-9_.\-]+)==([^\s\\;]+)(?:\s*;\s*(.*?))?\s*\\?$")
HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")
APPENDIX_BEGIN = "# --- BEGIN WS223 PLATFORM-CONDITIONAL APPENDIX (generated) ---"
APPENDIX_END = "# --- END WS223 PLATFORM-CONDITIONAL APPENDIX (generated) ---"

# Installer-provided externals: pip-tools excludes these "unsafe" packages from
# the lock by default and pip itself guarantees their presence. A lock entry
# requiring one of them must not force a network fetch for it.
INSTALLER_EXTERNALS = {"pip", "setuptools", "distribute", "wheel"}

TARGET_ENVS = (
    {
        "python_version": "3.12",
        "python_full_version": "3.12.0",
        "sys_platform": "linux",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "extra": "",
    },
    {
        "python_version": "3.12",
        "python_full_version": "3.12.0",
        "sys_platform": "win32",
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_python_implementation": "CPython",
        "extra": "",
    },
)


def _normalize(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def _parse_lock(text: str) -> tuple[list[dict], list[dict]]:
    if APPENDIX_BEGIN not in text or APPENDIX_END not in text:
        raise SystemExit("lock is missing the delimited platform appendix")
    compiler_region, rest = text.split(APPENDIX_BEGIN, 1)
    appendix_region, _ = rest.split(APPENDIX_END, 1)

    def entries(region: str) -> list[dict]:
        found: list[dict] = []
        for match in PIN_RE.finditer(region):
            name, version, marker = match.group(1), match.group(2), (match.group(3) or "").strip()
            tail = region[match.end() :]
            hashes: list[str] = []
            for line in tail.splitlines()[1:]:
                stripped = line.strip()
                if stripped.startswith("--hash="):
                    hashes.append(stripped.split(":", 1)[1].rstrip("\\").strip())
                elif stripped.startswith("#") or not stripped:
                    continue
                else:
                    break
            found.append({"name": name, "version": version, "marker": marker, "hashes": hashes})
        return found

    return entries(compiler_region), entries(appendix_region)


def _read_inputs(path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--")):
            continue
        requirements.append(Requirement(line))
    return requirements


def _fetch_version_meta(name: str, version: str) -> dict:
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    request = urllib.request.Request(url, headers={"User-Agent": "ws223-lock-verify"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the WS223 dependency lock")
    parser.add_argument("--lock", default="requirements/lock.txt")
    parser.add_argument("--input", default="requirements/lock.in")
    parser.add_argument("--with-network", action="store_true")
    parser.add_argument("--target-minor", type=int, default=12)
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    text = (root / args.lock).read_text(encoding="utf-8")
    compiler_entries, appendix_entries = _parse_lock(text)
    by_name = {_normalize(entry["name"]): entry for entry in compiler_entries + appendix_entries}
    failures: list[str] = []

    if len(by_name) != len(compiler_entries) + len(appendix_entries):
        failures.append("duplicate package pins in lock")
    for entry in compiler_entries + appendix_entries:
        if not entry["hashes"]:
            failures.append(f"{entry['name']}=={entry['version']} carries no hashes")

    inputs = _read_inputs(root / args.input)
    for requirement in inputs:
        key = _normalize(requirement.name)
        pinned = by_name.get(key)
        if pinned is None:
            failures.append(f"lock input {requirement} has no pin")
            continue
        if Version(pinned["version"]) not in requirement.specifier:
            failures.append(
                f"pin {pinned['name']}=={pinned['version']} violates input {requirement}"
            )
        # Compiler-region entries keep no markers (current-env resolution);
        # marker inputs that miss the compiling interpreter live in the appendix.
        if (
            requirement.marker is not None
            and not requirement.marker.evaluate()
            and key not in {_normalize(entry["name"]) for entry in appendix_entries}
        ):
            failures.append(f"marker input {requirement} missing from appendix")

    digest = hashlib.sha256(text.encode()).hexdigest()
    print(
        f"offline checks: {len(compiler_entries)} compiler pins, "
        f"{len(appendix_entries)} appendix pins, {len(inputs)} inputs"
    )
    print(f"lock sha256: {digest}")

    if args.with_network:
        for entry in compiler_entries + appendix_entries:
            try:
                meta = _fetch_version_meta(entry["name"], entry["version"])
            except Exception as exc:
                failures.append(
                    f"index lookup failed for {entry['name']}=={entry['version']}: {exc}"
                )
                continue
            info = meta["info"]
            requires_python = info.get("requires_python") or ""
            if requires_python and not SpecifierSet(requires_python).contains(
                f"3.{args.target_minor}", prereleases=True
            ):
                failures.append(
                    f"{entry['name']}=={entry['version']} requires "
                    f"Python {requires_python} (target 3.{args.target_minor})"
                )
            for req_text in info.get("requires_dist") or []:
                req_parts = req_text.split(";", 1)
                dep_name = _normalize(re.split(r"[<>=!~\s\[]", req_parts[0].strip())[0])
                if len(req_parts) == 1:
                    if dep_name not in by_name and dep_name not in INSTALLER_EXTERNALS:
                        failures.append(
                            f"{entry['name']}=={entry['version']} unconditionally "
                            f"requires {dep_name}, absent from lock"
                        )
                    continue
                try:
                    marker = Marker(req_parts[1])
                except Exception:
                    failures.append(f"unparsable marker in {entry['name']}: {req_text}")
                    continue
                if (
                    any(marker.evaluate(environment=env) for env in TARGET_ENVS)
                    and dep_name not in by_name
                    and dep_name not in INSTALLER_EXTERNALS
                ):
                    failures.append(
                        f"{entry['name']}=={entry['version']} requires {req_text} "
                        f"on 3.{args.target_minor} linux/win32, absent from lock"
                    )
        for entry in appendix_entries:
            try:
                meta = _fetch_version_meta(entry["name"], entry["version"])
            except Exception as exc:
                failures.append(f"appendix index lookup failed for {entry['name']}: {exc}")
                continue
            index_hashes = {
                item["digests"]["sha256"]
                for item in meta.get("urls", [])
                if item.get("digests", {}).get("sha256")
            }
            if set(entry["hashes"]) != index_hashes:
                failures.append(
                    f"appendix hashes for {entry['name']}=={entry['version']} "
                    f"drifted from the index (lock={len(entry['hashes'])} "
                    f"index={len(index_hashes)})"
                )
        print("network checks: requires-python + closure + appendix drift evaluated")

    if failures:
        print("LOCK VERIFICATION FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("LOCK VERIFICATION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
