from __future__ import annotations

import json

import pytest

import commander_lab.current_model_resolution as current_model_resolution
from commander_lab.current_model_resolution import (
    CurrentModelResolutionError,
    _require_hex_digest,
    load_current_model_resolution,
)
from commander_lab.model_resolution_software_identity import model_resolution_software_identity


def _current_payload(repo_root) -> dict[str, object]:
    source = repo_root / current_model_resolution.CURRENT_MODEL_RESOLUTION_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _install_payload(tmp_path, monkeypatch, payload: dict[str, object]) -> None:
    current = tmp_path / "MODEL_RESOLUTION_CURRENT.json"
    current.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(current_model_resolution, "CURRENT_MODEL_RESOLUTION_PATH", current)


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


def test_current_model_resolution_without_software_identity_fails_closed(
    repo_root, tmp_path, monkeypatch
) -> None:
    payload = _current_payload(repo_root)
    payload.pop("software_identity", None)
    _install_payload(tmp_path, monkeypatch, payload)

    with pytest.raises(CurrentModelResolutionError, match="no content-addressed software identity"):
        load_current_model_resolution(repo_root)


def test_repository_current_model_resolution_loads_with_scoped_freshness(repo_root) -> None:
    loaded = load_current_model_resolution(repo_root)

    assert loaded["status"] == "MEASURED"
    assert loaded["effective_resolution"] == pytest.approx(0.3749999999999998)
    assert loaded["freshness_validated"] is True
    assert loaded["software_identity"]["schema_version"] == "1.1.0"
    assert (
        loaded["software_identity"]["identity_sha256"]
        == "9802486ddfa37c226447fac970154b7a7cfe2f607e561c13c7ffb7be2f533c9a"
    )


def test_current_model_resolution_loads_with_fresh_live_provenance(
    repo_root, tmp_path, monkeypatch
) -> None:
    payload = _current_payload(repo_root)
    payload["software_identity"] = model_resolution_software_identity(repo_root)
    _install_payload(tmp_path, monkeypatch, payload)

    loaded = load_current_model_resolution(repo_root)

    assert loaded["status"] == "MEASURED"
    assert loaded["effective_resolution"] == pytest.approx(0.3749999999999998)
    assert loaded["freshness_validated"] is True
    assert loaded["evidence_class"] == "structural_model_estimates"
    identity = loaded["software_identity"]
    assert len(identity["resolution_source_manifest_sha256"]) == 64
    assert len(identity["measurement_entrypoint_blob_sha1"]) == 40
    assert len(identity["package_manifest_blob_sha1"]) == 40
    assert len(identity["identity_sha256"]) == 64
    assert identity["scope_paths"]
    assert set(identity["source_objects"]) == set(identity["scope_paths"])
    artifact = loaded["measurement_artifact"]
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
    payload = _current_payload(repo_root)
    payload["software_identity"] = model_resolution_software_identity(repo_root)
    payload[field] = "0" * 64
    _install_payload(tmp_path, monkeypatch, payload)

    with pytest.raises(CurrentModelResolutionError, match="stale for the live decision inputs"):
        current_model_resolution.load_current_model_resolution(repo_root)


def test_current_model_resolution_stale_software_identity_fails_closed(
    repo_root, tmp_path, monkeypatch
) -> None:
    payload = _current_payload(repo_root)
    identity = model_resolution_software_identity(repo_root)
    identity["identity_sha256"] = "0" * 64
    payload["software_identity"] = identity
    _install_payload(tmp_path, monkeypatch, payload)

    with pytest.raises(CurrentModelResolutionError, match="stale for the live software identity"):
        current_model_resolution.load_current_model_resolution(repo_root)
