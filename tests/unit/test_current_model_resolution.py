from __future__ import annotations

import json

import pytest

import commander_lab.current_model_resolution as current_model_resolution
from commander_lab.current_model_resolution import (
    CurrentModelResolutionError,
    _require_hex_digest,
    load_current_model_resolution,
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


def test_current_model_resolution_loads_with_fresh_live_provenance(repo_root) -> None:
    payload = load_current_model_resolution(repo_root)

    assert payload["status"] == "MEASURED"
    assert payload["effective_resolution"] == pytest.approx(0.392857142857143)
    assert payload["freshness_validated"] is True
    assert payload["evidence_class"] == "structural_model_estimates"
    artifact = payload["measurement_artifact"]
    assert len(artifact["source_head"]) == 40
    assert len(artifact["measurement_json_sha256"]) == 64
    assert len(artifact["report_hash"]) == 64


@pytest.mark.parametrize(
    "field",
    (
        "structural_control_deck_hash",
        "data_snapshot_hash",
        "opponent_registry_hash",
    ),
)
def test_current_model_resolution_stale_live_hashes_fail_closed(
    repo_root, tmp_path, monkeypatch, field: str
) -> None:
    source = repo_root / current_model_resolution.CURRENT_MODEL_RESOLUTION_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload[field] = "0" * 64
    stale = tmp_path / "MODEL_RESOLUTION_CURRENT.json"
    stale.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(current_model_resolution, "CURRENT_MODEL_RESOLUTION_PATH", stale)

    with pytest.raises(CurrentModelResolutionError, match="stale for the live decision inputs"):
        current_model_resolution.load_current_model_resolution(repo_root)
