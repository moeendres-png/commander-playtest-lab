from __future__ import annotations

import pytest

from commander_lab.current_model_resolution import (
    CurrentModelResolutionError,
    _require_hex_digest,
)


def test_model_resolution_provenance_distinguishes_git_sha1_from_sha256() -> None:
    git_sha = "a" * 40
    sha256 = "b" * 64

    assert _require_hex_digest({"source_head": git_sha}, "source_head", length=40) == git_sha
    assert (
        _require_hex_digest(
            {"measurement_json_sha256": sha256},
            "measurement_json_sha256",
            length=64,
        )
        == sha256
    )

    with pytest.raises(CurrentModelResolutionError):
        _require_hex_digest({"source_head": sha256}, "source_head", length=40)
    with pytest.raises(CurrentModelResolutionError):
        _require_hex_digest(
            {"measurement_json_sha256": git_sha},
            "measurement_json_sha256",
            length=64,
        )
    with pytest.raises(CurrentModelResolutionError):
        _require_hex_digest({"source_head": "z" * 40}, "source_head", length=40)
