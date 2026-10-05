from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXACT_BLOBS = {
    ".claude/skills/repo-map/scripts/repo_map.py": "93b62e37430d669f413ffaac26bc4dba2c7e4710",
    ".claude/skills/find-docs/SKILL.upstream.md": "314f5789977ef3783c3e713dd600a73494ef9195",
    ".claude/skills/licenses/repo-map-MIT.txt": "14fac913ccf80234b1848540089a3bbcb6e5283d",
    ".claude/skills/licenses/context7-MIT.txt": "17900de42d69131467aaa7a53fa88b92d238dc63",
}


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def test_exact_efficiency_vendor_blobs() -> None:
    for relative, expected in EXACT_BLOBS.items():
        path = ROOT / relative
        assert path.is_file(), relative
        assert git_blob_sha(path.read_bytes()) == expected, relative


def test_efficiency_python_helpers_compile() -> None:
    for relative in (
        ".claude/skills/repo-map/scripts/repo_map.py",
        "scripts/claude_rtk_hook.py",
        "scripts/verify_claude_efficiency_setup.py",
    ):
        path = ROOT / relative
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
