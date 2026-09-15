"""Generate the platform-conditional appendix for requirements/lock.txt.

pip-compile resolves for the compiling interpreter and prunes requirements
whose markers do not match it, so win32-only closure entries can never come
out of the compiler on Linux. This script resolves exactly those entries
from index metadata (no downloads: hashes come from the PEP 691/JSON
``digests``) and emits pip-compatible ``--hash`` stanzas with their markers.

Usage:
    python scripts/generate_lock_appendix.py --input requirements/lock.in \\
        --output requirements/lock-appendix.txt

The caller concatenates the compiler output and the appendix into
``requirements/lock.txt``; see requirements/LOCK_PROVENANCE.json.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

APPENDIX_BEGIN = "# --- BEGIN WS223 PLATFORM-CONDITIONAL APPENDIX (generated) ---"
APPENDIX_END = "# --- END WS223 PLATFORM-CONDITIONAL APPENDIX (generated) ---"
PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "ws223-lock-appendix"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def _candidate_versions(name: str) -> list[str]:
    request = urllib.request.Request(
        f"https://pypi.org/pypi/{name}/json", headers={"User-Agent": "ws223-lock-appendix"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return sorted(json.loads(response.read())["releases"], key=Version)


def _requires_python_allows(requires_python: str | None, major: int, minor: int) -> bool:
    if not requires_python:
        return True
    from packaging.specifiers import SpecifierSet

    return SpecifierSet(requires_python).contains(f"{major}.{minor}", prereleases=True)


def _has_interpreter_files(files: list[dict], major: int, minor: int) -> bool:
    tag = f"cp{major}{minor}"
    for entry in files:
        filename = entry.get("filename", "")
        if filename.endswith(".whl"):
            if tag in filename or "py3-none-any" in filename or "py2.py3-none-any" in filename:
                return True
        elif filename.endswith((".tar.gz", ".zip")):
            return True
    return False


def _resolve(name: str, spec: str, major: int, minor: int) -> tuple[str, list[dict]]:
    from packaging.specifiers import SpecifierSet

    specifier = SpecifierSet(spec)
    for version in reversed(_candidate_versions(name)):
        if Version(version) not in specifier:
            continue
        meta = _fetch_json(PYPI_JSON.format(name=name, version=version))
        info = meta["info"]
        if info.get("yanked", False):
            continue
        if not _requires_python_allows(info.get("requires_python"), major, minor):
            continue
        files = [entry for entry in meta.get("urls", []) if entry.get("digests", {}).get("sha256")]
        if not files or not _has_interpreter_files(files, major, minor):
            continue
        return version, files
    raise SystemExit(f"no {major}.{minor}-compatible release of {name}{spec} found")


def _stanza(name: str, version: str, marker: str, files: list[dict], via: str) -> str:
    lines = [f"{name}=={version} ; {marker} \\"]
    for entry in sorted(files, key=lambda item: item["filename"]):
        lines.append(f"    --hash=sha256:{entry['digests']['sha256']} \\")
    lines[-1] = lines[-1].rstrip(" \\")
    lines.append(f"    # via {via}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the win32 lock appendix")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--python-major", type=int, default=3)
    parser.add_argument("--python-minor", type=int, default=12)
    args = parser.parse_args(argv)

    entries: list[str] = []
    provenance: list[dict[str, str]] = []
    for raw in Path(args.input).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--")):
            continue
        requirement = Requirement(line)
        if requirement.marker is None:
            continue
        # pip-compile prunes inputs whose markers miss the compiling
        # interpreter; exactly those entries belong in the appendix.
        if requirement.marker.evaluate():
            continue
        spec = str(requirement.specifier) or ">=0"
        version, files = _resolve(requirement.name, spec, args.python_major, args.python_minor)
        entries.append(
            _stanza(
                requirement.name,
                version,
                str(requirement.marker),
                files,
                "ws223-platform-conditional-appendix",
            )
        )
        provenance.append(
            {
                "name": requirement.name,
                "specifier": spec,
                "marker": str(requirement.marker),
                "resolved": version,
                "files": str(len(files)),
            }
        )
    Path(args.output).write_text(
        APPENDIX_BEGIN + "\n" + "\n".join(entries) + "\n" + APPENDIX_END + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
