from __future__ import annotations

import re
from pathlib import Path

import yaml

POLICY = "docs/RETENTION_AND_LIFECYCLE_POLICY.md"
INDEX_REQ = "docs/EVIDENCE_INDEX_REQUIREMENTS.md"

# Exact strings from the defective revision. If any reappears, the
# SHA-as-storage fallacy is back.
FORBIDDEN = [
    "objects stay reachable via manifest SHA",
    "Delete ref 7+ days after merge",
    "becomes the provenance unit",
]


def _read(repo_root: Path, rel: str) -> str:
    return (repo_root / rel).read_text(encoding="utf-8")


def test_sha_alone_is_insufficient_retention(repo_root: Path) -> None:
    policy = _read(repo_root, POLICY)
    index = _read(repo_root, INDEX_REQ)
    for text in (policy, index):
        assert "SHA != RETENTION ANCHOR" in text
    assert "INDEX != STORAGE" in index
    for bad in FORBIDDEN:
        assert bad not in policy, bad
        assert bad not in index, bad


def test_unique_unmerged_commits_require_durable_anchor(repo_root: Path) -> None:
    policy = _read(repo_root, POLICY)
    assert "verified durable retention anchor" in policy
    for anchor in ("canonical_history", "retained_ref", "archival_bundle"):
        assert anchor in policy
    assert "If B is UNKNOWN: fail closed, retain the ref" in policy


def test_unknown_retention_fails_closed(repo_root: Path) -> None:
    policy = _read(repo_root, POLICY).lower()
    index = _read(repo_root, INDEX_REQ)
    assert "unknown" in policy and "fail closed" in policy
    assert "UNKNOWN" in index  # anchor type + template default


def test_index_template_carries_anchor_fields(repo_root: Path) -> None:
    text = _read(repo_root, INDEX_REQ)
    block = re.search(r"```yaml\n(.*?)```", text, re.DOTALL)
    assert block is not None
    template = yaml.safe_load(block.group(1))
    for key in (
        "retention_anchor_type",
        "retention_anchor_locator",
        "retention_anchor_verified",
        "retention_anchor_hash",
    ):
        assert key in template, key


def test_merged_cleanup_requires_verified_reachability(repo_root: Path) -> None:
    policy = _read(repo_root, POLICY)
    assert "merge-base" in policy
    assert "never inferred from PR state" in policy
    assert "ligible for deletion adjudication no earlier than 7 days" in policy
    assert "No automatic deletion timer" in policy


def test_approval_does_not_imply_technical_proof(repo_root: Path) -> None:
    policy = _read(repo_root, POLICY)
    assert "never implies retention was technically proven" in policy
    assert "separately evidenced" in policy
