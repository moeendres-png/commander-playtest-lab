from __future__ import annotations

from commander_lab.model_resolution_software_identity import (
    MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION,
    model_resolution_software_identity,
)


def test_model_resolution_software_identity_is_content_addressed(repo_root) -> None:
    identity = model_resolution_software_identity(repo_root)

    assert identity["schema_version"] == "1.0.0"
    assert identity["identity_version"] == MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION
    assert len(identity["commander_lab_tree_sha1"]) == 40
    assert len(identity["measurement_entrypoint_blob_sha1"]) == 40
    assert len(identity["package_manifest_blob_sha1"]) == 40
    assert len(identity["identity_sha256"]) == 64
    assert (
        identity["freshness_semantics"]
        == "content_addressed_relevant_software_not_commit_identity"
    )


def test_model_resolution_software_identity_is_stable_within_same_checkout(repo_root) -> None:
    first = model_resolution_software_identity(repo_root)
    second = model_resolution_software_identity(repo_root)

    assert first == second
